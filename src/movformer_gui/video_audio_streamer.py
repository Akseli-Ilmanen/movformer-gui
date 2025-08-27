"""VideoAudioStreamViewer manages synchronized video and optional audio playback within a napari viewer."""

import napari
import av # great library for streaming data -> no loading into memory
import numpy as np
from qtpy.QtCore import QTimer
import threading
import queue
import time
from typing import Optional, Union
import pyaudio 
    
class VideoAudioStreamViewer:
    """
    Methods:
        start(): Begins playback by initializing video/audio streams, starting timers and threads, and setting state to running. 
                 Only call when the video/audio path changes is set/changes.
        resume(): Continues playback from a paused state, updating timers and state flags.
        pause(): Temporarily halts playback, records pause time for synchronization, and updates state flags.
        stop(): Terminates playback, releases resources, resets state, and clears queues.
    """
    def __init__(self,
                 viewer: napari.Viewer,
                 app_state: None,
                 video_source: str,
                 audio_source: Optional[str] = None,
                 enable_audio: bool = True,
                 audio_buffer_size: int = 1024):
        """
        Initialize video stream viewer with optional audio
        
        Parameters:
        - video_source: video file path
        - audio_source: audio file path
        - viewer: napari viewer instance
        - enable_audio: whether to play audio
        - audio_buffer_size: audio buffer size for playback
        
        """
        self.video_source = video_source
        self.audio_source = audio_source
        self.viewer = viewer
        self.app_state = app_state
        self.enable_audio = enable_audio
        self.audio_buffer_size = audio_buffer_size
        
        # Queues for frames and audio
        self.frame_queue = queue.Queue(maxsize=30)
        self.audio_queue = queue.Queue(maxsize=100)
        
        # State management
        self.is_running = False
        self.is_paused = False
        self.current_position = 0  # in seconds
        self.seek_requested = False
        self.seek_position = 0
        
        # Video components
        self.video_container = None
        self.video_stream = None
        self.total_duration = 0
        self.frame_time_playback = 0
        
        # Audio components
        self.audio_container = None
        self.audio_stream = None
        self.audio_player = None
        self.audio_thread = None
        self.audio_sample_rate = 44100  # default
        self.audio_channels = 2
        
        # Sync components
        self.start_time = None
        self.pause_time = None
        self.accumulated_pause_time = 0
        
        # UI components
        self.image_layer = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        
    def initialize_streams(self):
        """Initialize video and audio streams"""

        # Open video container
        self.video_container = av.open(self.video_source)
        self.video_stream = self.video_container.streams.video[0]
        self.frame_time_playback = 1.0 / self.app_state.fps_playback
        self.total_duration = float(self.video_stream.duration * self.video_stream.time_base)
        
        # Initialize audio if enabled
        if self.enable_audio:
            if self.audio_source:
                # Separate audio file
                self.audio_container = av.open(self.audio_source)
            else:
                # Try to get audio from video file
                audio_streams = [s for s in self.video_container.streams 
                                if s.type == 'audio']
                if audio_streams:
                    self.audio_container = self.video_container
                    self.audio_stream = audio_streams[0]
                    
            if self.audio_container and (self.audio_stream or 
                                        any(s.type == 'audio' for s in self.audio_container.streams)):
                if not self.audio_stream:
                    self.audio_stream = [s for s in self.audio_container.streams 
                                       if s.type == 'audio'][0]
                    
                self.audio_sample_rate = self.audio_stream.sample_rate
                self.audio_channels = self.audio_stream.channels
                
                # Initialize PyAudio
                self.audio_player = pyaudio.PyAudio()
                self.audio_output = self.audio_player.open(
                    format=pyaudio.paInt16,
                    channels=self.audio_channels,
                    rate=self.audio_sample_rate,
                    output=True,
                    frames_per_buffer=self.audio_buffer_size
                )
    
    def start(self):
        """Start streaming video (and audio if enabled) to napari"""
        self.initialize_streams()
        
        
        # Get first frame to initialize the layer
        first_frame = self._get_frame_at_position(0)
        if first_frame is not None:
            self.image_layer = self.viewer.add_image(
                first_frame,
                name='Video Stream'
            )
        
        # Start playback
        self.is_running = True
        self.start_time = time.time()
        
        # Start the decoding thread
        self.decode_thread = threading.Thread(target=self._decode_frames)
        self.decode_thread.daemon = True
        self.decode_thread.start()
        
        # Start audio thread if enabled
        if self.enable_audio and self.audio_stream:
            self.audio_thread = threading.Thread(target=self._play_audio)
            self.audio_thread.daemon = True
            self.audio_thread.start()
        
        # Start the timer to update display
        self.timer.start(int(self.frame_time_playback * 1000))  # Convert to milliseconds
    
    def _get_frame_at_position(self, position_seconds: float):
        """Get a single frame at specific position"""
        # Seek to position
        seek_target = int(position_seconds / self.video_stream.time_base)
        self.video_container.seek(seek_target, stream=self.video_stream)
        
        for packet in self.video_container.demux(self.video_stream):
            for frame in packet.decode():
                return frame.to_ndarray(format='rgb24')
        return None
    
    def _decode_frames(self):
        """Decode frames in a separate thread with seek support"""
        while self.is_running:
            try:
                if self.seek_requested:
                    # Clear queues
                    while not self.frame_queue.empty():
                        self.frame_queue.get()
                    
                    # Seek to requested position
                    seek_target = int(self.seek_position / self.video_stream.time_base)
                    self.video_container.seek(seek_target, stream=self.video_stream)
                    
                    # Update timing
                    self.current_position = self.seek_position
                    self.start_time = time.time() - self.seek_position
                    self.accumulated_pause_time = 0
                    
                    self.seek_requested = False
                
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Decode frames
                for packet in self.video_container.demux(self.video_stream):
                    if not self.is_running or self.seek_requested:
                        break
                    
                    if self.is_paused:
                        break
                        
                    for frame in packet.decode():
                        # Get frame timestamp
                        frame_time = float(frame.pts * self.video_stream.time_base)
                        
                        # Convert frame to numpy array
                        img = frame.to_ndarray(format='rgb24')
                        
                        # Add frame with timestamp to queue
                        try:
                            self.frame_queue.put((img, frame_time), timeout=0.1)
                        except queue.Full:
                            # Skip frame if queue is full
                            pass
                        
                        # Sync with real-time
                        if self.start_time:
                            elapsed = time.time() - self.start_time - self.accumulated_pause_time
                            if frame_time > elapsed + 0.1:  # If ahead, wait
                                time.sleep(min(frame_time - elapsed, 0.1))
                                
            except Exception as e:
                print(f"Decoding error: {e}")
                break
    
    def _play_audio(self):
        """Play audio in a separate thread with seek support"""
        if not self.audio_stream or not self.enable_audio:
            return
            
        while self.is_running:
            try:
                if self.seek_requested:
                    # Clear audio queue
                    while not self.audio_queue.empty():
                        self.audio_queue.get()
                    
                    # Seek audio to requested position
                    if self.audio_container != self.video_container:
                        seek_target = int(self.seek_position / self.audio_stream.time_base)
                        self.audio_container.seek(seek_target, stream=self.audio_stream)
                    
                    # Wait for video seek to complete
                    while self.seek_requested:
                        time.sleep(0.01)
                
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Decode and play audio
                for packet in self.audio_container.demux(self.audio_stream):
                    if not self.is_running or self.seek_requested or self.is_paused:
                        break
                        
                    for frame in packet.decode():
                        # Convert to bytes
                        audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                        
                        # Play audio
                        if self.audio_output:
                            self.audio_output.write(audio_data)
                            
            except Exception as e:
                print(f"Audio error: {e}")
                break
    
    def update_frame(self):
        """Update the napari image layer with new frame"""
        try:
            if not self.frame_queue.empty():
                frame, timestamp = self.frame_queue.get(block=False)
                if self.image_layer is not None:
                    self.image_layer.data = frame
                    self.current_position = timestamp
                    self.app_state.current_time = timestamp
                    self.app_state.current_frame = round(self.app_state.current_time * self.app_state.ds.fps)
        except queue.Empty:
            pass
    
    def seek(self, position: Union[float, int]):
        """
        Seek to specific position in the video
        
        Parameters:
        - position: target position in seconds
        """
        if position < 0:
            position = 0
        elif position > self.total_duration:
            position = self.total_duration
            
        self.seek_position = position
        self.seek_requested = True
        
        # Wait a bit for seek to process
        time.sleep(0.1)
    
    def jump_to_segment(self, start_time: float, end_time: Optional[float] = None):
        """
        Jump to a specific segment of the video. If end is provided, will pause there = play_segment function.
        
        Parameters:
        - start_time: start position in seconds
        - end_time: optional end position (will play until this point)
        """
        self.seek(start_time)
        
        if end_time is not None:
            # Schedule a pause or stop at end_time
            def stop_at_end():
                while self.is_running and self.current_position < end_time:
                    time.sleep(0.1)
                self.pause()
            
            threading.Thread(target=stop_at_end, daemon=True).start()
    
    def pause(self):
        """Pause playback"""
        if not self.is_paused:
            self.is_paused = True
            self.pause_time = time.time()
    
    def resume(self):
        """Resume playback"""
        if self.is_paused:
            if self.pause_time:
                self.accumulated_pause_time += time.time() - self.pause_time
            self.is_paused = False
    
    def toggle_pause(self):
        """Toggle between pause and play"""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
    
    def set_audio_enabled(self, enabled: bool):
        """Enable or disable audio playback"""
        self.enable_audio = enabled
        
        if not enabled and self.audio_output:
            self.audio_output.stop_stream()
        elif enabled and self.audio_output:
            self.audio_output.start_stream()
    
    def get_current_position(self) -> float:
        """Get current playback position in seconds"""
        return self.current_position
    
    def get_duration(self) -> float:
        """Get total video duration in seconds"""
        return self.total_duration
    
    def stop(self):
        """Stop the video stream"""
        self.is_running = False
        self.timer.stop()
        
        # Clean up video
        if self.video_container:
            self.video_container.close()
        
        # Clean up audio
        if self.audio_output:
            self.audio_output.stop_stream()
            self.audio_output.close()
        if self.audio_player:
            self.audio_player.terminate()
        if self.audio_container and self.audio_container != self.video_container:
            self.audio_container.close()
            
            
