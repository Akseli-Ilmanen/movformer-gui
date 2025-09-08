"""Base classes for video synchronization with lineplot and spectrogram."""

import napari
import av
import numpy as np
from qtpy.QtCore import QTimer, QObject, Signal
import threading
import queue
import time
from typing import Optional, Union
import pyaudio
from napari.utils.notifications import show_error
from napari.settings import get_settings
from audioio import AudioLoader, PlayAudio

try:
    from napari._qt.qt_viewer import QtViewer
    from napari._qt._qapp_model.qactions._view import _get_current_play_status
except ImportError:
    _get_current_play_status = None


class VideoSync(QObject):
    """Base class for video synchronization with common signals and interface."""
    
    frame_changed = Signal(int)  # Emitted when video frame changes
    time_changed = Signal(float)  # Emitted when playback time changes
    playback_state_changed = Signal(bool)  # Emitted when play/pause state changes
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__()
        self.viewer = viewer
        self.app_state = app_state
        self.video_source = video_source
        self.audio_source = audio_source
        
        # Common state
        self.current_frame = 0
        self.current_time = 0.0
        self.total_frames = 0
        self.total_duration = 0.0
        self.is_playing = False
        self.fps = getattr(app_state.ds, 'fps', 30.0) if hasattr(app_state, 'ds') else 30.0
        self.fps_playback = getattr(app_state, 'fps_playback', self.fps)
        
        # Audio properties
        self.sr = getattr(app_state.ds, 'sr', None) if hasattr(app_state, 'ds') else None
        if self.sr is None and audio_source:
            try:
                with AudioLoader(audio_source) as data:
                    self.sr = data.rate
            except:
                self.sr = 44100
    
    def start(self):
        """Start video playback. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def pause(self):
        """Pause video playback. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def resume(self):
        """Resume video playback. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def stop(self):
        """Stop video playback. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def seek(self, position: Union[float, int]):
        """Seek to position (seconds or frame). Must be implemented by subclasses."""
        raise NotImplementedError
    
    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def play_segment(self, start_time: float, end_time: float):
        """Play a specific segment. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _emit_frame_changed(self, frame_number: int):
        """Emit frame changed signal and update internal state."""
        self.current_frame = frame_number
        self.current_time = frame_number / self.fps
        self.app_state.current_frame = frame_number
        self.frame_changed.emit(frame_number)
        self.time_changed.emit(self.current_time)
    
    def _emit_playback_state_changed(self, is_playing: bool):
        """Emit playback state changed signal."""
        self.is_playing = is_playing
        self.playback_state_changed.emit(is_playing)


class StreamingVideoSync(VideoSync):
    """PyAV-based streaming video player with real-time decoding."""
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None, 
                 enable_audio: bool = True, audio_buffer_size: int = 1024):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        self.enable_audio = enable_audio
        self.audio_buffer_size = audio_buffer_size
        self.start_paused = start_paused
        
        # Queues for frames and audio
        self.frame_queue = queue.Queue(maxsize=30)
        self.audio_queue = queue.Queue(maxsize=100)
        
        # State management
        self.is_running = False
        self.is_paused = start_paused  # Start paused by default
        self.seek_requested = False
        self.seek_position = 0
        
        # Video components
        self.video_container = None
        self.video_stream = None
        self.frame_time_playback = 0
        
        # Audio components
        self.audio_container = None
        self.audio_stream = None
        self.audio_player = None
        self.audio_thread = None
        self.audio_sample_rate = 44100
        self.audio_channels = 2
        
        # Sync components
        self.start_time = None
        self.pause_time = None
        self.accumulated_pause_time = 0
        
        # UI components
        self.image_layer = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        self.wait_time = 0.1
    
    def _initialize_video(self):
        """Initialize video stream."""
        try:
            self.video_container = av.open(self.video_source)
            self.video_stream = self.video_container.streams.video[0]
            self.frame_time_playback = 1.0 / self.fps_playback
            self.total_duration = float(self.video_stream.duration * self.video_stream.time_base)
            self.total_frames = int(self.total_duration * self.fps)
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
        
        # Get first frame to initialize the layer
        first_frame = self._get_frame_at_position(0)
        if first_frame is not None:
            self.image_layer = self.viewer.add_image(
                first_frame,
                name='Video Stream'
            )
        
        # Start playback
        self.is_running = True
        if not self.start_paused:
            self.start_time = time.time()
        self._emit_playback_state_changed(not self.is_paused)
        
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
        self.timer.start(int(self.frame_time_playback * 1000))
    
    def _get_frame_at_position(self, position_seconds: float):
        """Get a single frame at specific position"""
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
                    self._clear_frame_queue()
                    
                    # Seek to requested position
                    seek_target = int(self.seek_position / self.video_stream.time_base)
                    self.video_container.seek(seek_target, stream=self.video_stream, any_frame=False, backward=True)
                    
                    # Update timing
                    self.current_time = self.seek_position
                    self.start_time = time.time() - self.seek_position
                    self.accumulated_pause_time = 0
                    
                    self.seek_requested = False
                 
                if self.is_paused:
                    time.sleep(self.wait_time) 
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
                        frame_number = int(frame_time * self.fps)
                        
                        # Convert frame to numpy array
                        img = frame.to_ndarray(format='rgb24')
                        
                        # Add frame with timestamp to queue
                        try:
                            self.frame_queue.put((img, frame_time, frame_number), timeout=self.wait_time)
                        except queue.Full:
                            # Skip frame if queue is full
                            pass
                        
                        # Sync with real-time
                        if self.start_time:
                            elapsed = time.time() - self.start_time - self.accumulated_pause_time
                            if frame_time > elapsed + self.wait_time:
                                time.sleep(min(frame_time - elapsed, self.frame_time_playback))
                                
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
                    self._clear_audio_queue()
                    
                    # Seek audio to requested position
                    if self.audio_container != self.video_container:
                        seek_target = int(self.seek_position / self.audio_stream.time_base)
                        self.audio_container.seek(seek_target, stream=self.audio_stream)
                    
                    # Wait for video seek to complete
                    while self.seek_requested:
                        time.sleep(0.01)
                
                if self.is_paused:
                    time.sleep(self.wait_time)
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
                frame, timestamp, frame_number = self.frame_queue.get(block=False)
                if self.image_layer is not None:

                    self.image_layer.data = frame
                    
                    self._emit_frame_changed(frame_number)
        except queue.Empty:
            pass
    
    def seek(self, position: Union[float, int]):
        """Seek to specific position in the video"""
        if isinstance(position, int):
            position = position / self.fps  # Convert frame to seconds
            
        if position < 0:
            position = 0
        elif position > self.total_duration:
            position = self.total_duration
            
        self.seek_position = position
        self.seek_requested = True
        
        # Wait a bit for seek to process
        time.sleep(self.wait_time)
    
    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame."""
        position = frame_number / self.fps
        self.seek(position)
    
    def play_segment(self, start_time: float, end_time: float):
        """Play a specific segment from start_time to end_time."""
        self.seek(start_time)
        # Note: End time handling would need additional logic for auto-stop
    
    def pause(self):
        """Pause playback"""
        if not self.is_paused:
            self.is_paused = True
            self.pause_time = time.time()
            self._clear_frame_queue()
            if self.enable_audio:
                self._clear_audio_queue()
            self._emit_playback_state_changed(False)
    
    def resume(self):
        """Resume playback"""
        if self.is_paused:
            if self.pause_time:
                self.accumulated_pause_time += time.time() - self.pause_time
            self.is_paused = False
            self._emit_playback_state_changed(True)
    
    def toggle_pause(self):
        """Toggle between pause and play"""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
    
    def _clear_frame_queue(self):
        """Clear all frames from the frame queue"""
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    def _clear_audio_queue(self):
        """Clear all audio data from the audio queue"""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
    
    def set_audio_enabled(self, enabled: bool):
        """Enable or disable audio playback"""
        self.enable_audio = enabled
        
        if not enabled and hasattr(self, 'audio_output') and self.audio_output:
            self.audio_output.stop_stream()
        elif enabled and hasattr(self, 'audio_output') and self.audio_output:
            self.audio_output.start_stream()

    def stop(self):
        """Stop the video stream"""
        self.is_running = False
        self.timer.stop()
        self._emit_playback_state_changed(False)
        
        # Disconnect napari events
        try:
            self.viewer.dims.events.current_step.disconnect(self._on_napari_step_change)
        except:
            pass
        
        # Clean up shortcuts
        if hasattr(self, '_shortcuts'):
            for shortcut in self._shortcuts:
                shortcut.setEnabled(False)
            self._shortcuts.clear()
        
        # Clean up video
        if self.video_container:
            self.video_container.close()
        
        # Clean up audio
        if hasattr(self, 'audio_output') and self.audio_output:
            self.audio_output.stop_stream()
            self.audio_output.close()
        if self.audio_player:
            self.audio_player.terminate()
        if self.audio_container and self.audio_container != self.video_container:
            self.audio_container.close()


class NapariVideoSync(VideoSync):
    """Napari-integrated video player using napari-video plugin."""
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        # Get QtViewer reference for internal napari functions
        self.qt_viewer = getattr(viewer.window, '_qt_viewer', None)
        
        # Video layer reference
        self.video_layer = None
        
        self._setup_video_layer()
    
    def _setup_video_layer(self) -> None:
        """Setup napari video layer reference."""
        if not self.video_source:
            return

        # Find existing video layer
        for layer in self.viewer.layers:
            if layer.name == "video" and hasattr(layer, 'data'):
                self.video_layer = layer
                break
        
        if not self.video_layer:
            show_error("Video layer not found. Load video first.")
            return
        
        # Get video properties
        if hasattr(self.video_layer.data, 'shape'):
            self.total_frames = self.video_layer.data.shape[0]
            self.total_duration = self.total_frames / self.fps
    
    def _napari_is_playing(self) -> bool:
        """Check if napari is currently playing using internal functions."""
        if _get_current_play_status and self.qt_viewer:
            try:
                return _get_current_play_status(self.qt_viewer)
            except:
                return False
        return False
    
    def start(self):
        """Start playback using napari's built-in player."""
        if not self._napari_is_playing():
            self.qt_viewer.dims.play()
            self._emit_playback_state_changed(True)

    def pause(self):
        """Pause playback using napari's built-in toggle."""
        if self._napari_is_playing():
            self.qt_viewer.dims.stop()
            self._emit_playback_state_changed(False)

    def resume(self):
        """Resume playback."""
        self.start()

    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame."""
        if not self.video_layer:
            return
        
        # Use napari's built-in seeking
        self.viewer.dims.current_step = (frame_number,) + self.viewer.dims.current_step[1:]
        self._emit_frame_changed(frame_number)
    
    def seek(self, position: Union[float, int]):
        """Seek to position (seconds or frame)."""
        if isinstance(position, float):
            frame_number = int(position * self.fps)
        else:
            frame_number = position
        self.seek_to_frame(frame_number)
    
    def play_segment(self, start_time: float, end_time: float):
        """Play a specific segment from start_time to end_time with audio."""
        start_frame = int(start_time * self.fps)
        end_frame = int(end_time * self.fps)
        
        # Video 
        qt_dims = self.viewer.window._qt_viewer.dims
        self.seek_to_frame(start_frame)
        
        player: Optional[PlayAudio] = None
        
        if self.audio_source and self.sr:
            # Audio
            with AudioLoader(self.audio_source) as data:
                start_sample = int(start_time * self.sr)
                end_sample = int(end_time * self.sr)
                segment = data[start_sample:end_sample]

            if segment.shape[0] > 1:
                segment = segment[:, 0]

            slow_down_factor = self.fps_playback / self.fps
            rate = slow_down_factor * self.sr
        
            player = PlayAudio()
            player.play(data=segment, rate=float(rate), blocking=False)
                
        qt_dims.play(axis=0, fps=self.fps_playback, loop_mode="once", frame_range=(start_frame, end_frame))
        
        # Monitor playback and cleanup audio when video stops
        if player:
            def monitor_playback(qt_viewer):
                while _get_current_play_status(qt_viewer):
                    time.sleep(0.1)
                player.stop()
                player.__exit__(None, None, None)
            
            monitor_thread = threading.Thread(
                target=lambda: monitor_playback(self.qt_viewer), 
                daemon=True
            )
            monitor_thread.start()

    def stop(self):
        """Stop playback and cleanup."""
        # Stop napari video
        if self._napari_is_playing():
            self.pause()
        self._emit_playback_state_changed(False)