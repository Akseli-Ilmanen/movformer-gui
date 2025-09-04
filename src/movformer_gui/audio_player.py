"""
Minimal audio player synchronized with napari video playback.

Features:
- Volume control via a slider
- Start playback aligned to current napari frame (or given time)
- Pause/stop playback
- Resync to napari when drift is significant
"""

from audioio import AudioLoader
from audioio import play
from napari.utils.notifications import show_error
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


class AudioPlayer(QWidget):
    """
    Audio player widget that synchronizes with napari video playback.
    """

    playback_position_changed = Signal(float)  # Emits current time in seconds

    def __init__(self, napari_viewer, app_state=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.viewer = napari_viewer
        self.app_state = app_state
        self.audio_loader: AudioLoader | None = None
        self.audio_sr: int | None = None
        self.audio_player: PlayAudio | None = PlayAudio(verbose=0)
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.current_time: float = 0.0  # Current playback time in seconds
        self.duration: float = 0.0

        self._setup_ui()
        self._connect_napari_events()

    def _setup_ui(self) -> None:
        """Setup the audio player UI."""
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Vol:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setToolTip("Adjust playback volume")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider, stretch=1)
        self.setLayout(layout)

    def _on_volume_changed(self, value: int) -> None:
        """Update playback volume in real time if playing."""
        if self.is_playing and self.audio_player is not None:
            # No direct API to change volume mid-playback, so restart block
            self._start_playback(self.current_time)

    def _connect_napari_events(self) -> None:
        """Connect to napari viewer events for synchronization."""
        if hasattr(self.viewer.dims, "events"):
            self.viewer.dims.events.current_step.connect(self._on_napari_frame_changed)

    def set_audio_loader(self, audio_loader: AudioLoader) -> None:
        """Set the AudioLoader to be used for playback."""
        self.audio_loader = audio_loader
        self.audio_sr = audio_loader.rate
        self.duration = audio_loader.frames / audio_loader.rate

    def load_audio_file(self, file_path: str, buffersize: float = 60.0) -> bool:
        """
        Create an AudioLoader from file and set it for playback.
        Returns True on success, False otherwise.
        """
        if not file_path:
            show_error("No audio file specified")
            return False
        try:
            loader = AudioLoader(file_path, buffersize=buffersize)
        except (FileNotFoundError, ValueError, OSError) as e:
            show_error(f"Failed to load audio file: {e}")
            return False
        self.set_audio_loader(loader)
        return True

    def _start_playback(self, start_time: float | None = None) -> None:
        """
        Start audio playback from given time or current napari frame.
        """
        if self.audio_player is None or self.audio_loader is None:
            show_error("Audio player not available or no audio data loaded")
            return

        # Determine start time
        if start_time is None:
            try:
                current_frame = self.viewer.dims.current_step[0]
                start_time = current_frame / self.app_state.fps_playback
            except (AttributeError, IndexError, ZeroDivisionError):
                start_time = 0.0

        # Clamp to valid range
        start_time = max(0.0, min(start_time, self.duration))
        self.current_time = start_time

        # Stop any ongoing playback then start from requested time
        self._stop_playback()
        sr = self.audio_sr
        block_duration = getattr(self.app_state, "audio_buffer", 60.0)
        start_sample = int(self.current_time * sr)
        end_sample = int(min(start_sample + block_duration * sr, self.audio_loader.frames))
        block = self.audio_loader[start_sample:end_sample]
        if block is None or len(block) == 0:
            show_error("No audio data available for playback.")
            return

        volume = self.volume_slider.value() / 100.0
        scaled_data = block * volume

        try:
            self.audio_player.play(scaled_data, sr, blocking=False)
            self.is_playing = True
            self.is_paused = False
        except (RuntimeError, ValueError, OSError) as e:
            show_error(f"Failed to start audio playback: {e}")

    def _stop_playback(self) -> None:
        """
        Stop only the audio without resetting position.
        """
        if self.audio_player is not None:
            try:
                self.audio_player.stop()
            except (RuntimeError, AttributeError) as e:
                show_error(f"Failed to stop audio playback: {e}")
        self.is_playing = False
        self.is_paused = False

    def _on_napari_frame_changed(self, event) -> None:
        """
        Update audio position to match napari frame if slightly mismatched.
        """
        if not self.is_playing or self.audio_loader is None:
            return
        try:
            current_frame = self.viewer.dims.current_step[0]
            target_time = current_frame / self.app_state.fps_playback
            # If audio and video are out of sync by >20ms, seek audio
            if abs(self.current_time - target_time) > 0.02:
                self.current_time = target_time
                self._stop_playback()
                self._start_playback(start_time=target_time)
            else:
                self.current_time = target_time
        except (AttributeError, IndexError, ZeroDivisionError) as e:
            show_error(f"Failed to sync audio with napari frame: {e}")

    def closeEvent(self, event) -> None:
        """
        Handle widget close event.
        """
        self._stop_playback()
        if self.audio_player is not None:
            self.audio_player.close()
        super().closeEvent(event)
