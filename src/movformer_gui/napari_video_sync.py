"""Simplified synchronization manager with segment playback support."""

import pyaudio
import threading
import time
from pathlib import Path
from typing import Optional
from qtpy.QtCore import QObject, Signal
from napari.utils.notifications import show_error
from napari.settings import get_settings


# Import napari's internal functions
try:
    from napari._qt.qt_viewer import QtViewer
    from napari._qt._qapp_model.qactions._view import _get_current_play_status
except ImportError:
    # Fallback if internal imports fail
    _get_current_play_status = None

from audioio import AudioLoader, PlayAudio



class NapariVideoPlayer(QObject):
    """
    Use napari-video to load entire video. Audio not loaded unless in spectrogram mode. Audio playback only possible for segments.
    """
    
    frame_changed = Signal(int)  # Emitted when video frame changes
    
    def __init__(self, viewer, app_state, video_path: str, audio_path: Optional[str] = None):
        super().__init__()
        self.viewer = viewer
        self.app_state = app_state
        self.video_path = video_path if video_path else None
        self.audio_path = audio_path if audio_path else None

 
        # Get QtViewer reference for internal napari functions
        self.qt_viewer = getattr(viewer.window, '_qt_viewer', None)
        
        # Video layer reference
        self.video_layer = None
                

        self.sr = getattr(self.app_state.ds, "sr", None)
        if self.sr is None and self.audio_path:
            with AudioLoader(self.audio_path) as data:
                self.sr = data.rate

        
        # Frame tracking
        self.current_frame = 0
        self.total_frames = 0

        self._setup_video_layer()
    
    def _setup_video_layer(self) -> None:
        """Setup napari video layer reference."""
        if not self.video_path:
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
    
    def _napari_is_playing(self) -> bool:
        """Check if napari is currently playing using internal functions."""
        if _get_current_play_status and self.qt_viewer:
            try:
                return _get_current_play_status(self.qt_viewer)
            except:
                return False
        return False
    
    def play(self) -> None:
        """Start playback using napari's built-in toggle."""
        if not self._napari_is_playing():
            qt_viewer = self.qt_viewer
            qt_viewer.dims.play()

    def pause(self) -> None:
        """Pause playback using napari's built-in toggle."""
        if self._napari_is_playing():
            qt_viewer = self.qt_viewer
            qt_viewer.dims.stop()

    def seek_to_frame(self, frame_number: int) -> None:
        """Seek to specific frame."""
        if not self.video_layer:
            return
        
        # Use napari's built-in seeking
        self.viewer.dims.current_step = (frame_number,) + self.viewer.dims.current_step[1:]
        self.current_frame = frame_number
        self.app_state.current_frame = frame_number
        self.frame_changed.emit(frame_number)
    

     
    
     
    
    def play_segment(self, start_frame: int, end_frame: int) -> None:
        """Play a specific segment from start_frame to end_frame with audio."""

        # Video 
        fps_playback = self.app_state.fps_playback
        qt_dims = self.viewer.window._qt_viewer.dims
        self.seek_to_frame(start_frame)
        

        
        player: Optional[PlayAudio] = None
        
        if self.audio_path and self.sr:
            # Audio
            fps = self.app_state.ds.fps
            start_time = start_frame / fps
            end_time = end_frame / fps        
    
            
            with AudioLoader(self.audio_path) as data:
                start_sample = int(start_time * self.sr)
                end_sample = int(end_time * self.sr)
                segment = data[start_sample:end_sample]

            if segment.shape[0] > 1:
                segment = segment[:, 0]


            slow_down_factor = fps_playback / fps
            rate = slow_down_factor * self.sr
        
            player = PlayAudio()
            player.play(data=segment, rate=float(rate), blocking=False)
                
            
        qt_dims.play(axis=0, fps=fps_playback, loop_mode="once", frame_range=(start_frame, end_frame))
        
        
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


    def stop(self) -> None:
        """Stop playback and cleanup."""
        # Stop napari video
        if self._napari_is_playing():
            self.pause()