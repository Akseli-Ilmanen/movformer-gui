"""Video synchronization classes for timeline and spectrogram integration."""

import napari
import av
import numpy as np
from qtpy.QtCore import QTimer, QObject, Signal, Qt, QThread
from qtpy.QtGui import QIntValidator
from qtpy.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QScrollBar
)
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
    """Base class for video synchronization with shared state and signals."""
    
    frame_changed = Signal(int)

    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__()
        self.viewer = viewer
        self.app_state = app_state
        self.video_source = video_source
        self.audio_source = audio_source
        
        self._is_playing = False
        self.total_frames = 0
        self.total_duration = 0.0
        
        self.sr = getattr(app_state.ds, 'sr', None) if hasattr(app_state, 'ds') else None
        if self.sr is None and audio_source:
            try:
                with AudioLoader(audio_source) as data:
                    self.sr = data.rate
            except:
                self.sr = 44100
    
    @property
    def fps(self) -> float:
        """Video's actual framerate from dataset."""
        return self.app_state.ds.fps
    
    @property
    def fps_playback(self) -> float:
        """Current playback framerate. User may change."""
        return self.app_state.fps_playback
    
    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def toggle_pause_resume(self):
        if self.is_playing:
            self.pause()
        else:
            self.start()
            
    
    def _emit_frame_changed(self, frame_number: int):
        self.app_state.current_frame = frame_number
        self.frame_changed.emit(frame_number)
    

    
        
class NapariVideoSync(VideoSync):
    """Video player integrated with napari's built-in video controls."""
    
    stop_playback_signal = Signal()

    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        self.qt_viewer = getattr(viewer.window, '_qt_viewer', None)
        self.video_layer = None
        
        self.stop_playback_signal.connect(self.stop)
        self._monitor_timer = QTimer()
        self._player: Optional[PlayAudio] = None
        self._monitor_end_frame = 0
        
        self._setup_video_layer()
    
    @property
    def is_playing(self) -> bool:
        return self._napari_is_playing()
    
    def _setup_video_layer(self) -> None:
        if not self.video_source:
            return

        for layer in self.viewer.layers:
            if layer.name == "video" and hasattr(layer, 'data'):
                self.video_layer = layer
                break
        
        if not self.video_layer:
            show_error("Video layer not found. Load video first.")
            return
        
        if hasattr(self.video_layer.data, 'shape'):
            self.total_frames = self.video_layer.data.shape[0]
            self.total_duration = self.total_frames / self.fps
        
        self.viewer.dims.events.current_step.connect(self._on_napari_step_change)
    
    def _on_napari_step_change(self, event=None):
        if hasattr(self.viewer.dims, 'current_step') and len(self.viewer.dims.current_step) > 0:
            frame_number = self.viewer.dims.current_step[0]
            self._emit_frame_changed(frame_number)
            

    
    def _napari_is_playing(self) -> bool:
        if _get_current_play_status and self.qt_viewer:
            try:
                return _get_current_play_status(self.qt_viewer)
            except:
                return False
        return False
    
    
    def seek_to_frame(self, frame_number: int):
        if not self.video_layer:
            return
        
        self.viewer.dims.current_step = (frame_number,) + self.viewer.dims.current_step[1:]
        self._emit_frame_changed(frame_number)
    
    def start(self):
        if not self._napari_is_playing():
            self.qt_viewer.dims.play()

    def resume(self):
        self.start()
        
    def pause(self):
        self.stop()

    def stop(self):
        if self._napari_is_playing():
            self.qt_viewer.dims.stop()    


    def play_segment(self, start_frame: int, end_frame: int):
        start_time = start_frame / self.fps
        end_time = end_frame / self.fps
        
        self.seek_to_frame(start_frame)
        self._monitor_end_frame = end_frame
        
        if self.audio_source and self.sr:
            with AudioLoader(self.audio_source) as data:
                start_sample = int(start_time * self.sr)
                end_sample = int(end_time * self.sr)
                segment = data[start_sample:end_sample]

            if segment.shape[0] > 1:
                segment = segment[:, 0]

            slow_down_factor = self.fps_playback / self.fps
            rate = slow_down_factor * self.sr
            
            self._player = PlayAudio()
            self._player.play(data=segment, rate=float(rate), blocking=False)

        frame_time = 1.0 / self.fps_playback
        self.qt_viewer.dims.play(axis=0, fps=self.fps_playback)
        
        def check_playback():
            if not _get_current_play_status(self.qt_viewer):
                self._monitor_timer.stop()
          
                if self._monitor_player:
                    self._player.stop()
                    self._player.__exit__(None, None, None)
                    del self._monitor_player
                return
                
            if self.app_state.current_frame >= self._monitor_end_frame:
                self._monitor_timer.stop()
                self.stop_playback_signal.emit()
 
                if self._player:
                    self._player.stop()
                    self._player.__exit__(None, None, None)
                    del self._monitor_player
        
        self._monitor_timer.timeout.connect(check_playback)
        self._monitor_timer.start(int(frame_time * 50))
        
        
     

class VideoSliderWidget(QWidget):
    """Video playback controls with napari-style interface."""
    
    frame_changed = Signal(int)
    play_toggled = Signal(bool)
    
    def __init__(self, parent=None, total_frames=100, sync_manager=None):
        super().__init__(parent=parent)
        self.total_frames = max(1, total_frames)
        self.sync_manager = sync_manager
        self.app_state = sync_manager.app_state if sync_manager else None
        
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        self.play_button = QPushButton("▶")
        self.play_button.setMaximumWidth(30)
        self.play_button.setToolTip("Play/Pause video playback")
        self.play_button.clicked.connect(self._on_play_clicked)
        
        self.slider = QScrollBar(Qt.Orientation.Horizontal)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self.total_frames - 1)
        self.slider.setValue(0)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(int(self.app_state.ds.fps) if self.app_state else 30)
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        self.current_frame_input = QLineEdit()
        self.current_frame_input.setText("0")
        self.current_frame_input.setMaximumWidth(80)
        self.current_frame_input.setValidator(QIntValidator(0, 999999))
        self.current_frame_input.editingFinished.connect(self._on_frame_input_finished)
        self.current_frame_input.setObjectName('slice_label')
        self.current_frame_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.current_frame_input.setToolTip("Current frame number")
        
        sep = QFrame()
        sep.setFixedSize(1, 14)
        sep.setFrameStyle(QFrame.VLine)
        sep.setObjectName('slice_label_sep')
        
        self.total_frames_label = QLabel(str(self.total_frames - 1))
        self.total_frames_label.setMaximumWidth(80)
        self.total_frames_label.setObjectName('slice_label')
        self.total_frames_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(self.play_button)
        layout.addWidget(self.slider, stretch=2)
        layout.addWidget(self.current_frame_input)
        layout.addWidget(sep)
        layout.addWidget(self.total_frames_label)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    
    @property
    def current_frame(self):
        return getattr(self.sync_manager.app_state, 'current_frame', 0) if self.sync_manager else 0
    
    def set_total_frames(self, total_frames):
        self.total_frames = max(1, total_frames)
        self.slider.setMaximum(self.total_frames - 1)
        self.current_frame_input.setValidator(QIntValidator(0, self.total_frames - 1))
        self.total_frames_label.setText(str(self.total_frames - 1))
    
    def set_current_frame(self, frame_number):
        frame_number = max(0, min(frame_number, self.total_frames - 1))
        
        if self.sync_manager:
            self.sync_manager.app_state.current_frame = frame_number
        
        self.slider.blockSignals(True)
        self.current_frame_input.blockSignals(True)
        
        self.slider.setValue(frame_number)
        self.current_frame_input.setText(str(frame_number))
        
        self.slider.blockSignals(False)
        self.current_frame_input.blockSignals(False)
    

    
    def set_playing_state(self, is_playing):
        self.play_button.setText("⏸" if is_playing else "▶")
    
    def _on_play_clicked(self):
        self.play_toggled.emit(True)
    
    def _on_slider_changed(self, value):
        self.current_frame_input.setText(str(value))
        if hasattr(self.sync_manager, 'app_state') and self.sync_manager.app_state.current_frame != value:
            self.sync_manager.seek_to_frame(value)

    
    def _on_frame_input_finished(self):
        try:
            val = int(self.current_frame_input.text())
            max_allowed = self.total_frames - 1
            
            if val > max_allowed:
                val = max_allowed
                self.current_frame_input.setText(str(val))
            
            self.current_frame_input.clearFocus()
            if hasattr(self.parent(), 'setFocus'):
                self.parent().setFocus()

            if val != self.app_state.current_frame:
                self.slider.setValue(val)
                self.sync_manager.seek_to_frame(val)
                
        except ValueError:
            self.current_frame_input.setText(str(self.current_frame))


class VideoDecodeThread(QThread):
    """Background video frame decoder thread."""
    
    frame_ready = Signal(object, float, int)
    error_occurred = Signal(str)
    
    def __init__(self, video_container, video_stream, fps_actual, start_position, frame_queue, parent=None):
        super().__init__(parent)
        self.video_container = video_container
        self.video_stream = video_stream
        self.fps_actual = fps_actual
        self.start_position = start_position
        self.frame_queue = frame_queue
        self._is_playing = False
        self._stop_requested = False
    
    def set_playing(self, playing):
        self._is_playing = playing
    
    def run(self):
        try:
            seek_target = int(self.start_position / self.video_stream.time_base)
            self.video_container.seek(seek_target, stream=self.video_stream, backward=True)
            
            while not self._stop_requested:
                if not self._is_playing:
                    self.msleep(50)
                    continue
                
                for packet in self.video_container.demux(self.video_stream):
                    if self._stop_requested or not self._is_playing:
                        break
                        
                    for frame in packet.decode():
                        if self._stop_requested or not self._is_playing:
                            break
                            
                        frame_time = float(frame.pts * self.video_stream.time_base)
                        frame_number = int(frame_time * self.fps_actual)
                        
                        if frame_time < self.start_position:
                            continue
                        
                        img = frame.to_ndarray(format='rgb24')
                        
                        try:
                            self.frame_queue.put((img, frame_time, frame_number), timeout=0.1)
                        except:
                            pass
                            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def requestInterruption(self):
        self._stop_requested = True
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                pass


class AudioPlaybackThread(QThread):
    """Background audio playback thread."""
    
    error_occurred = Signal(str)
    
    def __init__(self, audio_container, audio_stream, start_position, audio_output, parent=None):
        super().__init__(parent)
        self.audio_container = audio_container
        self.audio_stream = audio_stream
        self.start_position = start_position
        self.audio_output = audio_output
        self._is_playing = False
        self._stop_requested = False
    
    def set_playing(self, playing):
        self._is_playing = playing
    
    def run(self):
        if not self.audio_stream:
            return
            
        try:
            if self.audio_container:
                seek_target = int(self.start_position / self.audio_stream.time_base)
                self.audio_container.seek(seek_target, stream=self.audio_stream)
                
            while not self._stop_requested:
                if not self._is_playing:
                    self.msleep(50)
                    continue
                
                for packet in self.audio_container.demux(self.audio_stream):
                    if self._stop_requested or not self._is_playing:
                        break
                        
                    for frame in packet.decode():
                        frame_time = float(frame.pts * self.audio_stream.time_base) if frame.pts else 0
                        
                        if frame_time < self.start_position:
                            continue
                            
                        audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                        if self.audio_output:
                            self.audio_output.write(audio_data)
                            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def requestInterruption(self):
        self._stop_requested = True


class PyAVStreamerSync(VideoSync):
    """PyAV-based video and audio streaming with frame-accurate synchronization."""
    
    def __init__(self, viewer: napari.Viewer, app_state, video_source: str, audio_source: Optional[str] = None, 
                 enable_audio: bool = True, audio_buffer_size: int = 1024):
        super().__init__(viewer, app_state, video_source, audio_source)
        
        self.enable_audio = enable_audio
        self.audio_buffer_size = audio_buffer_size
        self.frame_queue = queue.Queue(maxsize=30)
        self.start_position = 0.0
        
        self.video_container = None
        self.video_stream = None
        self.decode_thread = None
        
        self.audio_container = None
        self.audio_stream = None
        self.audio_thread = None
        self.audio_player = None
        self.audio_output = None
        
        self.image_layer = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        
        self.slider_widget = VideoSliderWidget(sync_manager=self)
        self.slider_widget.play_toggled.connect(self._on_slider_play_toggled)
    
    def _initialize_video(self):
        try:
            self.video_container = av.open(self.video_source)
            self.video_stream = self.video_container.streams.video[0]
            self.total_duration = float(self.video_stream.duration * self.video_stream.time_base)
            self.total_frames = int(self.total_duration * self.fps)
            self.slider_widget.set_total_frames(self.total_frames)
            
        except Exception as e:
            show_error(f"Video initialization failed: {e}")
            raise
    
    def _initialize_audio(self):
        if not self.enable_audio or not self.audio_source:
            return
            
        try:
            self.audio_container = av.open(self.audio_source)
            self.audio_stream = self.audio_container.streams.audio[0]
            
            self.audio_player = pyaudio.PyAudio()
            self.audio_output = self.audio_player.open(
                format=pyaudio.paInt16,
                channels=self.audio_stream.channels,
                rate=self.audio_stream.sample_rate,
                output=True,
                frames_per_buffer=self.audio_buffer_size
            )
        except Exception as e:
            show_error(f"Audio initialization failed: {e}")
            self.enable_audio = False
    
    def start(self):
        if self._is_playing:
            return
            
        self._initialize_video()
        self._initialize_audio()
        
        self.start_position = self.app_state.current_frame / self.fps
        
        first_frame = self._get_frame_at_position(self.start_position)
        if self.image_layer is None:
            self.image_layer = self.viewer.add_image(first_frame, name='Video Stream')
        
        self.decode_thread = VideoDecodeThread(
            self.video_container, 
            self.video_stream, 
            self.fps,
            self.start_position, 
            self.frame_queue,
            parent=self
        )
        self.decode_thread.error_occurred.connect(lambda msg: print(f"Video error: {msg}"))
        self.decode_thread.set_playing(True)
        self.decode_thread.start()
        
        if self.enable_audio and self.audio_stream:
            self.audio_thread = AudioPlaybackThread(
                self.audio_container,
                self.audio_stream,
                self.start_position,
                self.audio_output,
                parent=self
            )
            self.audio_thread.error_occurred.connect(lambda msg: print(f"Audio error: {msg}"))
            self.audio_thread.set_playing(True)
            self.audio_thread.start()
        
        self.timer.start(int(1000 / self.fps_playback))
        self._is_playing = True
        self.slider_widget.set_playing_state(True)
    
    def pause(self):
        if not self._is_playing:
            return
            
        self.timer.stop()
        if self.decode_thread:
            self.decode_thread.set_playing(False)
        if self.audio_thread:
            self.audio_thread.set_playing(False)
        
        self._is_playing = False
        self.slider_widget.set_playing_state(False)
    
    def resume(self):
        if self._is_playing:
            return
            
        if self.decode_thread:
            self.decode_thread.set_playing(True)
        if self.audio_thread:
            self.audio_thread.set_playing(True)
        
        self.timer.start(int(1000 / self.fps_playback))
        self._is_playing = True
        self.slider_widget.set_playing_state(True)
    
    def stop(self):
        self.timer.stop()
        self._is_playing = False
        self.slider_widget.set_playing_state(False)
        
        if self.decode_thread:
            self.decode_thread.requestInterruption()
            self.decode_thread.quit()
            self.decode_thread.wait(1000)
            self.decode_thread = None
            
        if self.audio_thread:
            self.audio_thread.requestInterruption()
            self.audio_thread.quit()
            self.audio_thread.wait(1000)
            self.audio_thread = None
        
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                break
        
        if self.video_container:
            self.video_container.close()
            self.video_container = None
            self.video_stream = None
        
        if self.audio_output:
            self.audio_output.stop_stream()
            self.audio_output.close()
            self.audio_output = None
        if self.audio_player:
            self.audio_player.terminate()
            self.audio_player = None
        if self.audio_container and self.audio_container != self.video_container:
            self.audio_container.close()
            self.audio_container = None
    
    def seek(self, position: Union[float, int]):
        if isinstance(position, int):
            position = position / self.fps
            
        position = max(0, min(position, self.total_duration))
        
        was_playing = self._is_playing
        self.stop()
        
        self.start_position = position
        self.app_state.current_frame = int(position * self.fps)
        
        if was_playing:
            self.start()
        

    
    def seek_to_frame(self, frame_number: int):
        self._emit_frame_changed(frame_number)
        self.seek(frame_number / self.fps)
    
    def _get_frame_at_position(self, position_seconds: float):
        seek_target = int(position_seconds / self.video_stream.time_base)
        self.video_container.seek(seek_target, stream=self.video_stream, backward=True)
        
        for packet in self.video_container.demux(self.video_stream):
            for frame in packet.decode():
                return frame.to_ndarray(format='rgb24')
        return None
    
    def update_frame(self):
        try:
            frame, timestamp, frame_number = self.frame_queue.get_nowait()
            if self.image_layer:
                self.image_layer.data = frame
                self._emit_frame_changed(frame_number)
                self.slider_widget.set_current_frame(frame_number)
        except queue.Empty:
            pass
    
    def _on_slider_play_toggled(self, _):
        self.toggle_pause_resume()
    
    def get_slider_widget(self) -> VideoSliderWidget:
        return self.slider_widget


