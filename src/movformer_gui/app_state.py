"""Observable application state container with change notifications."""

from dataclasses import dataclass, field
from pathlib import Path

import xarray as xr
import yaml
from qtpy.QtCore import QObject, QTimer, Signal
from napari.settings import get_settings

@dataclass
class AppState:
    """Data container for all shared application state."""
    

    # Dataset and data loading (NOT saved to YAML)
    ds: xr.Dataset | None = None

    # File paths (saved to YAML)
    file_path: str | None = None
    video_folder: str | None = None
    audio_folder: str | None = None

    # Dynamic data from dataset info (populated from dataset, NOT saved to YAML)
    _info_data: dict = field(default_factory=dict)

    # Playback settings (saved to YAML)
    fps_playback: float = 30.0

    # Plot settings (saved to YAML)
    ymin: float | None = None
    ymax: float | None = None
    spec_ymin: float | None = None
    spec_ymax: float | None = None
    window_size: float | None = None
    jump_size: float | None = None
    audio_buffer: float | None = None
    spec_buffer: float | None = None
    plot_spectrogram: bool = False

    # UI state (NOT saved to YAML)
    ready: bool = False


    # Additional current selections not directly from info (saved to YAML)
    trials_sel_condition_value: str | None = None

    # Configuration for which attributes to save to YAML
    @property
    def _saveable_attributes(self) -> set[str]:
        base_attrs = {
            "file_path",
            "video_folder",
            "audio_folder",
            "trials_sel_condition_value",
            "fps_playback",
            "ymin",
            "ymax",
            "spec_ymin",
            "spec_ymax",
            "window_size",
            "jump_size",
            "audio_buffer",
            "spec_buffer",
            "plot_spectrogram",
        }
        # Add any attributes ending with _sel
        sel_attrs = {attr for attr in self.__dict__ if attr.endswith("_sel")}
        return base_attrs | sel_attrs






class ObservableAppState(QObject):
    """State container with change notifications."""

    # Dataset and data loading signals
    ds_changed = Signal(object)
    file_path_changed = Signal(str)
    video_folder_changed = Signal(str)
    audio_folder_changed = Signal(str)

    # Dynamic signals for current selections and available options
    data_updated = Signal()  # Emitted when info data is updated

    # Trial filtering signals
    trials_sel_condition_value_changed = Signal(object)

    # Playback settings signals
    fps_playback_changed = Signal(float)

    # Plot settings signals
    ymin_changed = Signal(object)
    ymax_changed = Signal(object)
    spec_ymin_changed = Signal(object)
    spec_ymax_changed = Signal(object)
    window_size_changed = Signal(object)
    jump_size_changed = Signal(object)
    audio_buffer_changed = Signal(object)
    spec_buffer_changed = Signal(object)

    # UI state signals
    ready_changed = Signal(bool)


    def __init__(self, yaml_path: str | None = None, auto_save_interval: int = 10000):
        super().__init__()
        self._state = AppState()
        self.settings = get_settings()  # Get napari settings instance

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



    # Playback settings properties
    @property
    def fps_playback(self):
        return self._state.fps_playback



    @fps_playback.setter
    def fps_playback(self, value):
        self._state.fps_playback = value
        self.fps_playback_changed.emit(value)
        
        # Set napari playback fps for fast/slow playback
        self.settings.application.playback_fps = value
        


    # Plot settings properties
    @property
    def ymin(self):
        return self._state.ymin

    @ymin.setter
    def ymin(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.ymin = value
        self.ymin_changed.emit(value)

    @property
    def ymax(self):
        return self._state.ymax

    @ymax.setter
    def ymax(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.ymax = value
        self.ymax_changed.emit(value)

    @property
    def spec_ymin(self):
        return self._state.spec_ymin

    @spec_ymin.setter
    def spec_ymin(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.spec_ymin = value
        self.spec_ymin_changed.emit(value)

    @property
    def spec_ymax(self):
        return self._state.spec_ymax

    @spec_ymax.setter
    def spec_ymax(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.spec_ymax = value
        self.spec_ymax_changed.emit(value)

    @property
    def window_size(self):
        return self._state.window_size

    @window_size.setter
    def window_size(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.window_size = value
        self.window_size_changed.emit(value)

    @property
    def jump_size(self):
        return self._state.jump_size

    @jump_size.setter
    def jump_size(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.jump_size = value
        self.jump_size_changed.emit(value)

    @property
    def audio_buffer(self):
        return self._state.audio_buffer

    @audio_buffer.setter
    def audio_buffer(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.audio_buffer = value
        self.audio_buffer_changed.emit(value)

    @property
    def spec_buffer(self):
        return self._state.spec_buffer

    @spec_buffer.setter
    def spec_buffer(self, value):
        # Convert numpy types to Python float
        if value is not None:
            value = float(value)
        self._state.spec_buffer = value
        self.spec_buffer_changed.emit(value)

    # UI state properties
    @property
    def ready(self):
        return self._state.ready

    @ready.setter
    def ready(self, value):
        self._state.ready = value
        self.ready_changed.emit(value)



    def get_ds_kwargs(self):
        ds_kwargs = {
            "trials": getattr(self, "trials_sel"),
        }
        # Ensure it's always int
        ds_kwargs["trials"] = int(ds_kwargs["trials"])

        if hasattr(self, "keypoints_sel"):
            ds_kwargs["keypoints"] = self.keypoints_sel
        if hasattr(self, "individuals_sel"):
            ds_kwargs["individual"] = self.individuals_sel
        return ds_kwargs
    
    def key_sel_exists(self, type_key: str) -> bool:
        """Check if a key selection exists for a given type."""
        return hasattr(self, f"{type_key}_sel")

    def get_key_sel(self, type_key: str):
        """Get current value for a given info key."""
        attr_name = f"{type_key}_sel"
        return getattr(self, attr_name, None)

    def set_key_sel(self, type_key, currentValue):
        """Set current value for a given info key."""
        if currentValue is None:
            return

        attr_name = f"{type_key}_sel"
        old_value = getattr(self, attr_name, None)
        setattr(self, attr_name, currentValue)
        
        # Emit a general data_updated signal when any _sel attribute changes
        if old_value != currentValue:
            self.data_updated.emit()


    def get_saveable_state_dict(self) -> dict:
        """Get a dictionary representation of only the saveable attributes."""
        state_dict = {}
        
        # Get base saveable attributes (non-_sel attributes)
        base_attrs = self._state._saveable_attributes - {attr for attr in self._state._saveable_attributes if attr.endswith('_sel')}
        
        # Save base attributes from _state dataclass
        for attr_name in base_attrs:
            if hasattr(self._state, attr_name):
                value = getattr(self._state, attr_name)
                if value is not None:  # Only save non-None values
                    # Ensure numeric values are Python types, not numpy
                    if isinstance(value, (int, float)) or hasattr(value, 'dtype'):
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            pass
                    state_dict[attr_name] = value
        
        # Save ALL _sel attributes from self (ObservableAppState), not just predefined ones
        for attr_name in dir(self):
            if attr_name.endswith('_sel') and not attr_name.startswith('_'):
                # Skip private attributes and methods
                try:
                    value = getattr(self, attr_name)
                    # Only save if it's not a method and has a non-None value
                    if not callable(value) and value is not None:
                        state_dict[attr_name] = value
                except (AttributeError, TypeError):
                    continue
                    
        return state_dict

    def load_from_dict(self, state_dict: dict):
        """Load state from a dictionary (e.g., from saved settings)."""
        for key, value in state_dict.items():
            if value is None:
                continue
                
            # Handle _sel attributes (including dynamically created ones)
            if key.endswith('_sel'):
                setattr(self, key, value)
            # Handle other saveable attributes that exist in the base state
            elif key in self._state._saveable_attributes and hasattr(self, key):
                setattr(self, key, value)

    def save_to_yaml(self, yaml_path: str | None = None) -> bool:
        """Save the current saveable state to a YAML file."""
        try:
            path = yaml_path or self._yaml_path
            state_dict = self.get_saveable_state_dict()

            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(state_dict, f, default_flow_style=False, sort_keys=False)
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
