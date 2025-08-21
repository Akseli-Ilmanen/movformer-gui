"""Observable application state container with change notifications."""

from dataclasses import dataclass, field
from pathlib import Path

import xarray as xr
import yaml
from qtpy.QtCore import QObject, QTimer, Signal


@dataclass
class AppState:
    """Data container for all shared application state."""

    # Dataset and data loading (NOT saved to YAML)
    ds: xr.Dataset | None = None

    # File paths (saved to YAML)
    file_path: str | None = None
    video_folder: str | None = None
    audio_folder: str | None = None

    # Current selections (saved to YAML)
    current_trial: int | None = None
    current_keypoint: str | None = None
    current_variable: str | None = None
    current_color_variable: str | None = None
    current_camera: str | None = None
    current_mic: str | None = None

    # Trial filtering (saved to YAML)
    current_trial_condition_key: str | None = None
    current_trial_condition_value: str | None = None

    # Available options (populated from dataset, NOT saved to YAML)
    trials: list | None = None
    keypoints: list | None = None
    available_variables: list | None = None
    color_variables: list | None = None
    cameras: list | None = None
    mics: list | None = None
    trial_condition_keys: list | None = None

    # Playback settings (saved to YAML)
    fps_playback: float = 30.0

    # UI state (NOT saved to YAML)
    ready: bool = False

    # Configuration for which attributes to save to YAML
    _saveable_attributes: set[str] = field(
        default_factory=lambda: {
            "file_path",
            "video_folder",
            "audio_folder",
            "current_trial",
            "current_keypoint",
            "current_variable",
            "current_color_variable",
            "current_camera",
            "current_mic",
            "current_trial_condition_key",
            "current_trial_condition_value",
            "fps_playback",
        }
    )


class ObservableAppState(QObject):
    """State container with change notifications."""

    # Dataset and data loading signals
    ds_changed = Signal(object)
    file_path_changed = Signal(str)
    video_folder_changed = Signal(str)
    audio_folder_changed = Signal(str)

    # Current selection signals
    current_trial_changed = Signal(object)
    current_keypoint_changed = Signal(str)
    current_variable_changed = Signal(str)
    current_color_variable_changed = Signal(object)
    current_camera_changed = Signal(str)
    current_mic_changed = Signal(str)

    # Trial filtering signals
    current_trial_condition_key_changed = Signal(object)
    current_trial_condition_value_changed = Signal(object)

    # Available options signals
    trials_changed = Signal(list)
    keypoints_changed = Signal(list)
    available_variables_changed = Signal(list)
    color_variables_changed = Signal(list)
    cameras_changed = Signal(list)
    mics_changed = Signal(list)
    trial_condition_keys_changed = Signal(list)

    # Playback settings signals
    fps_playback_changed = Signal(float)

    # UI state signals
    ready_changed = Signal(bool)

    def __init__(self, yaml_path: str | None = None, auto_save_interval: int = 10000):
        super().__init__()
        self._state = AppState()

        # YAML persistence
        self._yaml_path = yaml_path or "gui_settings.yaml"

        # Auto-save timer (10 seconds by default)
        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self.save_to_yaml)
        self._auto_save_timer.start(auto_save_interval)  # milliseconds

    # Dataset and data loading properties
    @property
    def ds(self):
        return self._state.ds

    @ds.setter
    def ds(self, value):
        self._state.ds = value
        self.ds_changed.emit(value)

    @property
    def file_path(self):
        return self._state.file_path

    @file_path.setter
    def file_path(self, value):
        self._state.file_path = value
        self.file_path_changed.emit(value)

    @property
    def video_folder(self):
        return self._state.video_folder

    @video_folder.setter
    def video_folder(self, value):
        self._state.video_folder = value
        self.video_folder_changed.emit(value)

    @property
    def audio_folder(self):
        return self._state.audio_folder

    @audio_folder.setter
    def audio_folder(self, value):
        self._state.audio_folder = value
        self.audio_folder_changed.emit(value)

    # Current selection properties
    @property
    def current_trial(self):
        return self._state.current_trial

    @current_trial.setter
    def current_trial(self, value):
        self._state.current_trial = value
        self.current_trial_changed.emit(value)

    @property
    def current_keypoint(self):
        return self._state.current_keypoint

    @current_keypoint.setter
    def current_keypoint(self, value):
        self._state.current_keypoint = value
        self.current_keypoint_changed.emit(value)

    @property
    def current_variable(self):
        return self._state.current_variable

    @current_variable.setter
    def current_variable(self, value):
        self._state.current_variable = value
        self.current_variable_changed.emit(value)

    @property
    def current_color_variable(self):
        return self._state.current_color_variable

    @current_color_variable.setter
    def current_color_variable(self, value):
        self._state.current_color_variable = value
        self.current_color_variable_changed.emit(value)

    @property
    def current_camera(self):
        return self._state.current_camera

    @current_camera.setter
    def current_camera(self, value):
        self._state.current_camera = value
        self.current_camera_changed.emit(value)

    @property
    def current_mic(self):
        return self._state.current_mic

    @current_mic.setter
    def current_mic(self, value):
        self._state.current_mic = value
        self.current_mic_changed.emit(value)

    # Trial filtering properties
    @property
    def current_trial_condition_key(self):
        return self._state.current_trial_condition_key

    @current_trial_condition_key.setter
    def current_trial_condition_key(self, value):
        self._state.current_trial_condition_key = value
        self.current_trial_condition_key_changed.emit(value)

    @property
    def current_trial_condition_value(self):
        return self._state.current_trial_condition_value

    @current_trial_condition_value.setter
    def current_trial_condition_value(self, value):
        self._state.current_trial_condition_value = value
        self.current_trial_condition_value_changed.emit(value)

    # Available options properties
    @property
    def trials(self):
        return self._state.trials

    @trials.setter
    def trials(self, value):
        self._state.trials = value
        self.trials_changed.emit(value)

    @property
    def keypoints(self):
        return self._state.keypoints

    @keypoints.setter
    def keypoints(self, value):
        self._state.keypoints = value
        self.keypoints_changed.emit(value)

    @property
    def available_variables(self):
        return self._state.available_variables

    @available_variables.setter
    def available_variables(self, value):
        self._state.available_variables = value
        self.available_variables_changed.emit(value)

    @property
    def color_variables(self):
        return self._state.color_variables

    @color_variables.setter
    def color_variables(self, value):
        self._state.color_variables = value
        self.color_variables_changed.emit(value)

    @property
    def cameras(self):
        return self._state.cameras

    @cameras.setter
    def cameras(self, value):
        self._state.cameras = value
        self.cameras_changed.emit(value)

    @property
    def mics(self):
        return self._state.mics

    @mics.setter
    def mics(self, value):
        self._state.mics = value
        self.mics_changed.emit(value)

    @property
    def trial_condition_keys(self):
        return self._state.trial_condition_keys

    @trial_condition_keys.setter
    def trial_condition_keys(self, value):
        self._state.trial_condition_keys = value
        self.trial_condition_keys_changed.emit(value)

    # Playback settings properties
    @property
    def fps_playback(self):
        return self._state.fps_playback

    @fps_playback.setter
    def fps_playback(self, value):
        self._state.fps_playback = value
        self.fps_playback_changed.emit(value)

    # UI state properties
    @property
    def ready(self):
        return self._state.ready

    @ready.setter
    def ready(self, value):
        self._state.ready = value
        self.ready_changed.emit(value)

    def get_saveable_state_dict(self) -> dict:
        """Get a dictionary representation of only the saveable attributes."""
        state_dict = {}
        for attr_name in self._state._saveable_attributes:
            if hasattr(self._state, attr_name):
                value = getattr(self._state, attr_name)
                if value is not None:  # Only save non-None values
                    state_dict[attr_name] = value
        return state_dict

    def load_from_dict(self, state_dict: dict):
        """Load state from a dictionary (e.g., from saved settings)."""
        for key, value in state_dict.items():
            if key in self._state._saveable_attributes and hasattr(self, key) and value is not None:
                setattr(self, key, value)

    def save_to_yaml(self, yaml_path: str | None = None) -> bool:
        """Save the current saveable state to a YAML file."""
        try:
            path = yaml_path or self._yaml_path
            state_dict = self.get_saveable_state_dict()

            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(state_dict, f, default_flow_style=False, sort_keys=False)

            print(f"State saved to {path}")
            return True

        except (OSError, yaml.YAMLError) as e:
            print(f"Error saving state to YAML: {e}")
            return False

    def load_from_yaml(self, yaml_path: str | None = None) -> bool:
        """Load state from a YAML file."""
        try:
            path = yaml_path or self._yaml_path

            if not Path(path).exists():
                print(f"YAML file {path} not found, using defaults")
                return False

            with open(path, encoding="utf-8") as f:
                state_dict = yaml.safe_load(f) or {}

            self.load_from_dict(state_dict)
            print(f"State loaded from {path}")
            return True

        except (OSError, yaml.YAMLError) as e:
            print(f"Error loading state from YAML: {e}")
            return False

    def stop_auto_save(self):
        """Stop the auto-save timer (useful when closing the application)."""
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
            # Save one final time before stopping
            self.save_to_yaml()
