"""VideoAudioStreamViewer manages synchronized video and optional audio playback within a napari viewer."""

import napari
import av
import numpy as np
from qtpy.QtCore import QTimer
import threading
import queue
import time
from typing import Optional, Union
import pyaudio
from napari.utils.notifications import show_error


class VideoAudioStreamViewer:
    """
    Simplified video/audio streaming with synchronized playback.
    
    Methods:
        start(): Begins playback by initializing video/audio streams, starting timers and threads, and setting state to running. 
                 Only call when the video/audio path changes is set/changes.
        resume(): Continues playback from a paused state, updating timers and state flags.
        pause(): Temporarily halts playback, records pause time for synchronization, and updates state flags.
        stop(): Terminates playback, releases resources, resets state, and clears queues.
    """

    
    def __init__(self,
                 viewer: napari.Viewer,
                 app_state,
                 video_source: str,
                 audio_source: Optional[str] = None,
                 enable_audio: bool = True,
                 audio_buffer_size: int = 1024):
        """Initialize video stream viewer with optional audio."""
        self.video_source = video_source
        self.audio_source = audio_source
        self.viewer = viewer
        self.app_state = app_state
        self.enable_audio = enable_audio
        self.audio_buffer_size = audio_buffer_size
        
        # Core state
        self.is_running = False
        self.is_paused = False
        self.current_position = 0.0
        self.seek_requested = False
        self.seek_position = 0.0
        self.seek_complete = threading.Event()  # Synchronization for seek completion
        
        # Video components
        self.video_container = None
        self.video_stream = None
        self.total_duration = 0.0
        self.frame_time_playback = 0.0
        self.image_layer = None
        
        # Audio components
        self.audio_container = None
        self.audio_stream = None
        self.audio_player = None
        self.audio_output = None
        self.audio_sample_rate = 44100
        self.audio_channels = 2
        
        # Threading
        self.frame_queue = queue.Queue(maxsize=30)
        self.decode_thread = None
        self.audio_thread = None
        self.start_time = None
        
        # Timer for frame updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)
    
    def _initialize_video(self):
        """Initialize video stream."""
        try:
            self.video_container = av.open(self.video_source)
            self.video_stream = self.video_container.streams.video[0]
            self.frame_time_playback = 1.0 / self.app_state.fps_playback
            self.total_duration = float(self.video_stream.duration * self.video_stream.time_base)
        except Exception as e:
            show_error(f"Video initialization failed: {e}")
            raise
    
    def _initialize_audio(self):
        """Initialize audio stream if enabled."""
        if not self.enable_audio or not self.audio_source:
            return
            
        try:
            self.audio_container = av.open(self.audio_source)
            self.audio_stream = self.audio_container.streams.audio[0]
            self.audio_sample_rate = self.audio_stream.sample_rate
            self.audio_channels = self.audio_stream.channels
            
            self.audio_player = pyaudio.PyAudio()
            self.audio_output = self.audio_player.open(
                format=pyaudio.paInt16,
                channels=self.audio_channels,
                rate=self.audio_sample_rate,
                output=True,
                frames_per_buffer=self.audio_buffer_size
            )
        except Exception as e:
            show_error(f"Audio initialization failed: {e}")
            self.enable_audio = False
    
    def start(self):
        """Start streaming video and audio to napari."""
        self._initialize_video()
        self._initialize_audio()
        
        # Initialize napari image layer with first frame
        first_frame = self._get_frame_at_position(0)
        if first_frame is not None:
            self.image_layer = self.viewer.add_image(first_frame, name='Video Stream')
        
        self.is_running = True
        self.start_time = time.time()
        
        # Start decode thread
        self.decode_thread = threading.Thread(target=self._decode_frames, daemon=True)
        self.decode_thread.start()
        
        # Start audio thread if enabled
        if self.enable_audio and self.audio_stream:
            self.audio_thread = threading.Thread(target=self._play_audio, daemon=True)
            self.audio_thread.start()
        
        # Start frame update timer
        self.timer.start(int(self.frame_time_playback * 1000))
    
    def _get_frame_at_position(self, position_seconds: float):
        """Get a single frame at specific position."""
        seek_target = int(position_seconds / self.video_stream.time_base)
        self.video_container.seek(seek_target, stream=self.video_stream)
        
        for packet in self.video_container.demux(self.video_stream):
            for frame in packet.decode():
                return frame.to_ndarray(format='rgb24')
        return None
    
    def _decode_frames(self):
        """Decode video frames in separate thread."""
        while self.is_running:
            try:
                # Handle seek requests
                if self.seek_requested:
                    self._clear_frame_queue()
                    seek_target = int(self.seek_position / self.video_stream.time_base)
                    self.video_container.seek(seek_target, stream=self.video_stream)
                    self.current_position = self.seek_position
                    self.start_time = time.time() - self.seek_position
                    self.seek_requested = False
                    self.seek_complete.set()  # Signal seek completion
                
                if self.is_paused:
                    time.sleep(0.01)
                    continue
                
                # Decode and queue frames
                for packet in self.video_container.demux(self.video_stream):
                    if not self.is_running or self.seek_requested:
                        break
                    
                    if self.is_paused:
                        break
                    
                    for frame in packet.decode():
                        frame_time = float(frame.pts * self.video_stream.time_base)
                        img = frame.to_ndarray(format='rgb24')
                        
                        try:
                            self.frame_queue.put((img, frame_time), timeout=0.1)
                        except queue.Full:
                            pass  # Skip frame if queue full
                        
                        # Basic sync with real-time
                        if self.start_time:
                            elapsed = time.time() - self.start_time
                            if frame_time > elapsed + 0.1:
                                time.sleep(min(frame_time - elapsed, 0.1))
                                
            except Exception as e:
                if getattr(self.video_stream.codec_context, 'name', None) == 'av1':
                    show_error("AV1 format detected. Consider using H.264 for better compatibility.")
                else:
                    print(f"Video decode error: {e}")
                break
    
    def _play_audio(self):
        """Play audio in separate thread."""
        if not self.audio_stream or not self.enable_audio:
            return
            
        while self.is_running:
            try:
                # Handle seek for audio
                if self.seek_requested and self.audio_container != self.video_container:
                    seek_target = int(self.seek_position / self.audio_stream.time_base)
                    self.audio_container.seek(seek_target, stream=self.audio_stream)
                    
                    # Wait for video seek completion
                    while self.seek_requested:
                        time.sleep(0.01)
                
                if self.is_paused:
                    time.sleep(0.01)
                    continue
                
                # Decode and play audio
                for packet in self.audio_container.demux(self.audio_stream):
                    if not self.is_running or self.seek_requested or self.is_paused:
                        break
                    
                    for frame in packet.decode():
                        audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                        if self.audio_output:
                            self.audio_output.write(audio_data)
                            
            except Exception as e:
                print(f"Audio error: {e}")
                break
    
    def _update_frame(self):
        """Update napari image layer with new frame."""
        try:
            if not self.frame_queue.empty():
                frame, timestamp = self.frame_queue.get(block=False)
                if self.image_layer is not None:
                    self.image_layer.data = frame
                    self.current_position = timestamp
                    self.app_state.current_frame = round(timestamp * self.app_state.ds.fps)
        except queue.Empty:
            pass
    
    def _clear_frame_queue(self):
        """Clear the frame queue."""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get(block=False)
            except queue.Empty:
                break
    
    def seek(self, position: Union[float, int], wait_for_completion: bool = True) -> bool:
        """
        Seek to specific position in seconds.
        
        Args:
            position: Target position in seconds
            wait_for_completion: If True, blocks until seek is complete
            
        Returns:
            True if seek completed successfully, False if timeout
        """
        position = max(0, min(position, self.total_duration))
        self.seek_position = position
        self.seek_complete.clear()  # Reset the event
        self.seek_requested = True
        self.app_state.current_frame = round(position * self.app_state.ds.fps)
        
        if wait_for_completion:
            # Wait up to 2 seconds for seek to complete
            return self.seek_complete.wait(timeout=2.0)
        return True
    
    def play_segment(self, start_time: float, end_time: float):
        print(f"[play_segment] Starting: current_pos={self.current_position:.2f}, target={start_time:.2f}")
        
        was_paused = self.is_paused
        if not was_paused:
            self.pause()
            print(f"[play_segment] Paused playback")
            time.sleep(0.05)
        
        if not self.seek(start_time, wait_for_completion=True):
            print(f"[play_segment] Seek timeout!")
            return
        
        print(f"[play_segment] Seek complete: current_pos={self.current_position:.2f}")
        self.resume()
        print(f"[play_segment] Resumed playback")
        
        # Start monitoring thread for end position
        def pause_at_end():
            while self.is_running and not self.is_paused:
                if self.current_position >= end_time:
                    self.pause()
                    break
                time.sleep(0.01)  # Check more frequently
        
        threading.Thread(target=pause_at_end, daemon=True).start()
    
    def pause(self):
        """Pause playback."""
        self.is_paused = True
        # Record pause time for proper resume synchronization
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.pause_position = self.current_position
    
    def resume(self):
        """Resume playback."""
        if self.is_paused:
            # Recalculate start_time based on current position
            self.start_time = time.time() - self.current_position
            self.is_paused = False
    
    def toggle_pause(self):
        """Toggle between pause and play."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
    
    def set_audio_enabled(self, enabled: bool):
        """Enable/disable audio playback."""
        self.enable_audio = enabled
        if self.audio_output:
            if enabled:
                self.audio_output.start_stream()
            else:
                self.audio_output.stop_stream()
    
    def get_current_position(self) -> float:
        """Get current playback position in seconds."""
        return self.current_position
    
    def get_duration(self) -> float:
        """Get total video duration in seconds."""
        return self.total_duration
    
    def stop(self):
        """Stop playback and cleanup resources."""
        self.is_running = False
        self.timer.stop()
        
        # Cleanup video
        if self.video_container:
            self.video_container.close()
        
        # Cleanup audio
        if self.audio_output:
            self.audio_output.stop_stream()
            self.audio_output.close()
        if self.audio_player:
            self.audio_player.terminate()
        if self.audio_container and self.audio_container != self.video_container:
            self.audio_container.close()