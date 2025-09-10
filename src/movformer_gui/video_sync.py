"""Base classes for video synchronization with lineplot and spectrogram."""

import napari
import av
import numpy as np
from qtpy.QtCore import QTimer, QObject, Signal, Qt, Slot
from qtpy.QtGui import QIntValidator
from qtpy.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QScrollBar
)
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
    playback_state_changed = Signal(bool)  # Emitted when play/pause state changes
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__()
        self.viewer = viewer
        self.app_state = app_state
        self.video_source = video_source
        self.audio_source = audio_source
        
        # Common state
        self.total_frames = 0
        self.total_duration = 0.0
        self.fps = app_state.ds.fps
        
        # Audio properties
        self.sr = getattr(app_state.ds, 'sr', None) if hasattr(app_state, 'ds') else None
        if self.sr is None and audio_source:
            try:
                with AudioLoader(audio_source) as data:
                    self.sr = data.rate
            except:
                self.sr = 44100
    
    @property
    def is_playing(self) -> bool:
        """Get current playing state. Must be implemented by subclasses."""
        raise NotImplementedError
        
    def toggle_play_pause(self):
        """Toggle between play and pause states."""
        if self.is_playing:
            self.pause()
        else:
            self.resume()
    
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
        """Seek to position (seconds or frame). Must be implemented by subclasses. Only needed for StreamerVideoSync."""
        raise NotImplementedError
    
    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def play_segment(self, start_time: float, end_time: float):
        """Play a specific segment. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _emit_frame_changed(self, frame_number: int):
        """Emit frame changed signal and update internal state."""
        self.app_state.current_frame = frame_number
        self.frame_changed.emit(frame_number)
    
    def _emit_playback_state_changed(self, is_playing: bool):
        """Emit playback state changed signal."""
        self.playback_state_changed.emit(is_playing)
        
class NapariVideoSync(VideoSync):
    """Napari-integrated video player using napari-video plugin."""
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        # Get QtViewer reference for internal napari functions
        self.qt_viewer = getattr(viewer.window, '_qt_viewer', None)
        
        # Video layer reference
        self.video_layer = None
        self.jump_frame = None
        
        self._setup_video_layer()
    
    @property
    def is_playing(self) -> bool:
        """Return current playing state from napari."""
        return self._napari_is_playing()
    
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
        
        # Connect to napari's dimension changes to emit frame_changed signals
        self.viewer.dims.events.current_step.connect(self._on_napari_step_change)
    
    def _on_napari_step_change(self, event=None):
        """Handle napari dimension step changes and emit frame_changed signal."""
        if hasattr(self.viewer.dims, 'current_step') and len(self.viewer.dims.current_step) > 0:
            frame_number = self.viewer.dims.current_step[0]
            
            # Check if we need to reset lineplot window when user seeks outside current range
            self._check_and_reset_lineplot_window(frame_number)
            
            self._emit_frame_changed(frame_number)
    
    def _check_and_reset_lineplot_window(self, frame_number: int):
        """Check if frame is outside current lineplot window and reset if needed."""
        if not hasattr(self.app_state, 'ds') or self.app_state.ds is None:
            return
            
        # Get current time from frame
        current_time = frame_number / self.fps
        
        # Try to get lineplot window bounds 
        lineplot_widget = getattr(self.app_state, 'lineplot_widget', None)
        if lineplot_widget and hasattr(lineplot_widget, 'vb'):
            # Get current x-axis range from lineplot
            current_range = lineplot_widget.vb.viewRange()[0]  # [xmin, xmax]
            xmin, xmax = current_range
            
            # Check if current time is outside the visible window
            if current_time < xmin or current_time > xmax:
                # Reset lineplot to center around this timepoint
                if hasattr(lineplot_widget, '_update_window_position'):
                    # Store current frame in app_state so lineplot can center on it
                    old_frame = getattr(self.app_state, 'current_frame', frame_number)
                    self.app_state.current_frame = frame_number
                    
                    # Force window update in lineplot
                    if hasattr(lineplot_widget, 'update_window_bool'):
                        old_update_bool = lineplot_widget.update_window_bool
                        lineplot_widget.update_window_bool = True
                        lineplot_widget._update_window_position()
                        lineplot_widget.update_window_bool = old_update_bool
    
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
    


    def play_segment(self, start_frame: int, end_frame: int):
        """Play a specific segment from start_frame to end_frame with audio."""
        start_time = start_frame / self.fps
        end_time = end_frame / self.fps
        fps_playback = self.app_state.fps_playback 
        
        # Video
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

            slow_down_factor = fps_playback / self.fps
            rate = slow_down_factor * self.sr
            
            player = PlayAudio()
            player.play(data=segment, rate=float(rate), blocking=False)

        
        frame_time = 1.0 / fps_playback
            
        # Use loop mode to prevent auto-reset
        self.qt_viewer.dims.play(axis=0, fps=fps_playback)
        

        
        # Monitor playback and preserve frame position when it stops
        def monitor_playback(self_ref, player_ref: Optional[PlayAudio], end_frame: int, frame_time: float):
            while _get_current_play_status(self_ref.qt_viewer):
                # Check if we've reached or passed the end frame
                if self_ref.app_state.current_frame >= end_frame:
                    
                    # Stop playback
                    self_ref.qt_viewer.dims.stop()
                    self._emit_playback_state_changed(False)
                    break
                time.sleep(frame_time / 10) 
               
            # Clean up audio
            if player_ref:
                player_ref.stop()
                player_ref.__exit__(None, None, None)
                del player_ref


        monitor_thread = threading.Thread(
            target=lambda: monitor_playback(self, player, end_frame, frame_time),
            daemon=True
        )
        monitor_thread.start()
        
        
        
        

        
        
    def stop(self):
        """Stop playback and cleanup.""" 
        # Stop napari video 
        if self._napari_is_playing():
            self.pause()
        self._emit_playback_state_changed(False)
        
        # Disconnect napari events
        try:
            self.viewer.dims.events.current_step.disconnect(self._on_napari_step_change)
        except:
            pass


class VideoSliderWidget(QWidget):
    """Basic video slider widget based on napari's QtDimSliderWidget."""
    
    frame_changed = Signal(int)
    play_toggled = Signal(bool)
    
    def __init__(self, parent=None, total_frames=100, fps=30, sync_manager=None):
        super().__init__(parent=parent)
        self.total_frames = max(1, total_frames)
        self.fps = fps
        self._is_playing = False
        self.sync_manager = sync_manager  # Reference to parent sync manager
        self.app_state = sync_manager.app_state
        
        # Create UI elements
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # Play button
        self.play_button = QPushButton("▶")
        self.play_button.setMaximumWidth(30)
        self.play_button.setToolTip("Play/Pause video playback")
        self.play_button.clicked.connect(self._on_play_clicked)
        
        # Slider (matching napari's ModifiedScrollBar behavior)
        self.slider = QScrollBar(Qt.Orientation.Horizontal)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Match napari
        self.slider.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # Match napari
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.total_frames - 1)
        self.slider.setValue(0)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(int(self.fps))  # Jump by ~1 second
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        # Current frame input (matching napari's curslice_label style)
        self.current_frame_input = QLineEdit()
        self.current_frame_input.setText("0")
        self.current_frame_input.setMaximumWidth(80)
        self.current_frame_input.setValidator(QIntValidator(0, 999999))  # Match napari's wide range
        self.current_frame_input.editingFinished.connect(self._on_frame_input_finished)
        self.current_frame_input.setObjectName('slice_label')  # Match napari styling
        self.current_frame_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.current_frame_input.setToolTip("Current frame number")
        
        # Separator (matching napari's separator style)
        sep = QFrame()
        sep.setFixedSize(1, 14)
        sep.setFrameStyle(QFrame.VLine)
        sep.setObjectName('slice_label_sep')  # Match napari styling
        
        # Total frames label (matching napari's totslice_label style) 
        self.total_frames_label = QLabel(str(self.total_frames - 1))
        self.total_frames_label.setMaximumWidth(80)
        self.total_frames_label.setObjectName('slice_label')  # Match napari styling
        self.total_frames_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Add widgets to layout (matching napari's QtDimSliderWidget layout)
        layout.addWidget(self.play_button)
        layout.addWidget(self.slider, stretch=2)
        layout.addWidget(self.current_frame_input)
        layout.addWidget(sep)
        layout.addWidget(self.total_frames_label)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Match napari alignment
    
    @property
    def current_frame(self):
        """Get current frame from app_state."""
        return getattr(self.sync_manager.app_state, 'current_frame', 0) if self.sync_manager else 0
    
    def set_total_frames(self, total_frames):
        """Update total frames and adjust UI accordingly."""
        self.total_frames = max(1, total_frames)
        self.slider.setMaximum(self.total_frames - 1)
        self.current_frame_input.setValidator(QIntValidator(0, self.total_frames - 1))
        self.total_frames_label.setText(str(self.total_frames - 1))
    
    def set_current_frame(self, frame_number):
        """Set current frame without emitting signals."""
        frame_number = max(0, min(frame_number, self.total_frames - 1))
        
        # Update app_state instead of local variable
        if self.sync_manager:
            self.sync_manager.app_state.current_frame = frame_number
        
        # Update UI without triggering signals
        self.slider.blockSignals(True)
        self.current_frame_input.blockSignals(True)
        
        self.slider.setValue(frame_number)
        self.current_frame_input.setText(str(frame_number))
        
        self.slider.blockSignals(False)
        self.current_frame_input.blockSignals(False)
    

    
    def set_playing_state(self, is_playing):
        """Update play button appearance."""
        self._is_playing = is_playing
        self.play_button.setText("⏸" if is_playing else "▶")
    
    def _on_play_clicked(self):
        """Handle play button clicks."""
        self.play_toggled.emit(not self._is_playing)
    
    def _on_slider_changed(self, value):
        """Handle slider value changes."""
        self.current_frame_input.setText(str(value))
        # Only seek if not already at this frame to prevent unnecessary operations
        if hasattr(self.sync_manager, 'app_state') and self.sync_manager.app_state.current_frame != value:
            self.sync_manager.seek_to_frame(value)

    
    def _on_frame_input_finished(self):
        """Handle frame input field changes (matching napari's _set_slice_from_label)."""
        try:
            val = int(self.current_frame_input.text())
            max_allowed = self.total_frames - 1
            
            # Clamp value to valid range
            if val > max_allowed:
                val = max_allowed
                self.current_frame_input.setText(str(val))
            
            # Clear focus and emit change (matching napari behavior)
            self.current_frame_input.clearFocus()
            if hasattr(self.parent(), 'setFocus'):
                self.parent().setFocus()

            if val != self.app_state.current_frame:
                self.slider.setValue(val)
                self.sync_manager.seek_to_frame(val)
    
                
                
        except ValueError:
            # Reset to current frame if invalid input
            self.current_frame_input.setText(str(self.current_frame))


class StreamingVideoSync(VideoSync):
    """PyAV-based streaming video player with real-time decoding."""
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None, 
                 enable_audio: bool = True, audio_buffer_size: int = 1024):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        self.enable_audio = enable_audio
        self.audio_buffer_size = audio_buffer_size
        
        # Queues for frames and audio
        self.frame_queue = queue.Queue(maxsize=30)
        self.audio_queue = queue.Queue(maxsize=100)
        
        # State management
        self.is_running = False
        self._is_playing = False
        self.seek_requested = False
        self.seek_position = 0
        self.start_position = 0.0  # Position to start playback from
        
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
        
        # Video slider widget
        self.slider_widget = VideoSliderWidget(fps=self.app_state.fps_playback, sync_manager=self)
        self.slider_widget.play_toggled.connect(self._on_slider_play_toggled)
        
        # Connect playback state changes back to slider for consistent button updates
        self.playback_state_changed.connect(self.slider_widget.set_playing_state)
        
        self.wait_time = 0.1
    
    @property
    def is_playing(self) -> bool:
        """Return current playing state."""
        return self._is_playing
    
    def _initialize_video(self):
        """Initialize video stream."""
        try:
            self.video_container = av.open(self.video_source)
            self.video_stream = self.video_container.streams.video[0]
            self.frame_time_playback = 1.0 / self.app_state.fps_playback
            self.total_duration = float(self.video_stream.duration * self.video_stream.time_base)
            self.total_frames = int(self.total_duration * self.fps)
            
            # Update slider with video properties
            self.slider_widget.set_total_frames(self.total_frames)
            
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
        first_frame = self._get_frame_at_position(self.start_position)
        if first_frame is not None:
            if self.image_layer is None:
                self.image_layer = self.viewer.add_image(
                    first_frame,
                    name='Video Stream'
                )
            else:
                self.image_layer.data = first_frame
        
        # Start playback
        self.is_running = True
        self.start_time = time.time() - self.start_position  # Account for starting position
        self.accumulated_pause_time = 0
        self.pause_time = None
        self._emit_playback_state_changed(self._is_playing)
        
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
        """Decode frames in a separate thread starting from start_position"""
        # Seek to starting position
        seek_target = int(self.start_position / self.video_stream.time_base)
        self.video_container.seek(seek_target, stream=self.video_stream, any_frame=False, backward=True)
        
        while self.is_running:
            try:
                if not self._is_playing:
                    time.sleep(self.wait_time) 
                    continue
                
                # Decode frames
                for packet in self.video_container.demux(self.video_stream):
                    if not self.is_running:
                        break

                        
                    for frame in packet.decode():
                        # Check pause state more frequently in inner loop
                        if not self._is_playing:
                            break
                            
                        # Get frame timestamp
                        frame_time = float(frame.pts * self.video_stream.time_base)
                        frame_number = int(frame_time * self.fps)
                        
                        # Skip frames before start position
                        if frame_time < self.start_position:
                            continue
                        
                        # Convert frame to numpy array
                        img = frame.to_ndarray(format='rgb24')
                        
                        # Add frame with timestamp to queue (only if still playing)
                        if self._is_playing:
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
        """Play audio in a separate thread starting from start_position"""
        if not self.audio_stream or not self.enable_audio:
            return
        
        # Seek audio to starting position
        if self.audio_container != self.video_container:
            seek_target = int(self.start_position / self.audio_stream.time_base)
            self.audio_container.seek(seek_target, stream=self.audio_stream)
            
        while self.is_running:
            try:
                if not self._is_playing:
                    time.sleep(self.wait_time)
                    continue
                
                # Decode and play audio
                for packet in self.audio_container.demux(self.audio_stream):
                    if not self.is_running or not self._is_playing:
                        break
                        
                    for frame in packet.decode():
                        # Get frame timestamp
                        frame_time = float(frame.pts * self.audio_stream.time_base) if frame.pts else 0
                        
                        # Skip frames before start position
                        if frame_time < self.start_position:
                            continue
                            
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
                    
                    # Update slider position
                    self.slider_widget.set_current_frame(frame_number)
        except queue.Empty:
            pass
    
    # Streamer -> mainly use seek
    # NapariVideo -> mainly use seek_to_frame
    def seek(self, position: Union[float, int]):
        """Seek to specific position by restarting stream."""
        if isinstance(position, int):
            position = position / self.fps  # Convert frame to seconds
            
        if position < 0:
            position = 0
        elif position > self.total_duration:
            position = self.total_duration
            
        # Store current playing state
        was_playing = self._is_playing
        
        # Stop current stream
        self.stop()
        
        # Set new starting position
        self.start_position = position
        
        # Restart stream
        self.start()
        
        # Restore playing state
        if was_playing:
            self.resume()
        else:
            self.pause()
    
    def seek_to_frame(self, frame_number: int):
        """Seek to specific frame by restarting stream."""
        self._emit_frame_changed(frame_number)
        position = frame_number / self.fps
        self.seek(position)
    
    
    def pause(self):
        """Pause playback"""
        if self._is_playing:
            self._is_playing = False
            self.pause_time = time.time()
            self._clear_frame_queue()
            if self.enable_audio:
                self._clear_audio_queue()
            self._emit_playback_state_changed(False)
    
    def resume(self):
        """Resume playback"""
        if not self._is_playing:
            if self.pause_time:
                self.accumulated_pause_time += time.time() - self.pause_time
            self._is_playing = True
            self.slider_widget.set_playing_state(True)
            self._emit_playback_state_changed(True)
    
    
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
    

    
    def _on_slider_play_toggled(self, should_play: bool):
        """Handle play/pause toggle from slider."""
        if should_play:
            self.resume()
        else:
            self.pause()
    
    def get_slider_widget(self) -> VideoSliderWidget:
        """Return the video slider widget for UI integration."""
        return self.slider_widget

    def stop(self):
        """Stop the video stream"""
        self.is_running = False
        self._is_playing = False
        self.timer.stop()
        self.slider_widget.set_playing_state(False)
        self._emit_playback_state_changed(False)
        
        # Wait for threads to finish
        if hasattr(self, 'decode_thread') and self.decode_thread and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=0.5)
        if hasattr(self, 'audio_thread') and self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=0.5)
        
        # Clear queues
        self._clear_frame_queue()
        self._clear_audio_queue()
        
        # Clean up video
        if self.video_container:
            self.video_container.close()
            self.video_container = None
            self.video_stream = None
        
        # Clean up audio
        if hasattr(self, 'audio_output') and self.audio_output:
            self.audio_output.stop_stream()
            self.audio_output.close()
            self.audio_output = None
        if self.audio_player:
            self.audio_player.terminate()
            self.audio_player = None
        if self.audio_container and self.audio_container != self.video_container:
            self.audio_container.close()
            self.audio_container = None



