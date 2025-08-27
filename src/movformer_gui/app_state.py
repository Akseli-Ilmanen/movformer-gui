import contextlib
from pathlib import Path
from typing import Any, Callable, Type
import xarray as xr
import yaml
from napari.settings import get_settings
from qtpy.QtCore import QObject, QTimer, Signal

"""Observable application state container with change notifications."""

class AppStateSpec:
    @classmethod
    def get_default(cls, key):
        """Return the default value for a given key from VARS."""
        if key in cls.VARS:
            return cls.VARS[key][1]
        raise KeyError(f"No default for key: {key}")
    # Variable name: (type, default, save_to_yaml, signal_type)
    VARS = {
        "ds": (xr.Dataset | None, None, False, object),
        "trials": (list[int], [], False, object),
        "file_path": (str | None, None, True, str),
        "video_folder": (str | None, None, True, str),
        "audio_folder": (str | None, None, True, str),
        "video_path": (str | None, None, True, str),
        "audio_path": (str | None, None, True, str),
        "current_frame": (int, 0, False, int),
        "num_frames": (int, 0, False, int),
        "current_time": (float, 0.0, False, float),
        "_info_data": (dict[str, Any], {}, False, object),
        "fps_playback": (float, 30.0, True, float),
        "sync_state": (str | None, None, True, object),
        "ymin": (float | None, None, True, object),
        "ymax": (float | None, None, True, object),
        "spec_ymin": (float | None, None, True, object),
        "spec_ymax": (float | None, None, True, object),
        "window_size": (float | None, None, True, object),
        "jump_size": (float | None, None, True, object),
        "audio_buffer": (float | None, None, True, float),
        "spec_buffer": (float | None, None, True, float),
        "video_buffer_size": (int, 300, True, int),  # Number of frames to buffer
        "plot_spectrogram": (bool, False, True, bool),
        "ready": (bool, False, False, bool),
        "trials_sel_condition_value": (str | None, None, True, object),
        "nfft": (int, 1024, True, int),
        "hop_frac": (float, 0.5, True, float),
        "vmin_db": (float, -120.0, True, float),
        "vmax_db": (float, 20.0, True, float),
        "buffer_multiplier": (float, 5.0, True, float),
        "recompute_threshold": (float, 0.5, True, float),
        "cmap": (str, "magma", True, str),    
        # Add more variables here as needed
        
        
        # User can add variables in the ds. E.g. user can specify ds["keypoints"] ...
        # The currently selected keypoint will be saved here with "_sel" suffix, e.g. 
        # "keypoints_sel"
    }

class AppState:
    def __init__(self):
        for var, (var_type, default, _, _) in AppStateSpec.VARS.items():
            setattr(self, var, default)

    def saveable_attributes(self) -> set[str]:
        return {k for k, (_, _, save, _) in AppStateSpec.VARS.items() if save}


class ObservableAppState(QObject):
    def get_with_default(self, key):
        """Return value from app state, or default from AppStateSpec if None."""
        value = getattr(self, key, None)
        if value is None:
            value = AppStateSpec.get_default(key)
        return value
    """State container with change notifications."""

    # Dynamically create signals for each variable
    for var, (_, _, _, signal_type) in AppStateSpec.VARS.items():
        locals()[f"{var}_changed"] = Signal(signal_type)
    data_updated = Signal()  # For info updates

    def __init__(self, yaml_path: str | None = None, auto_save_interval: int = 30000) -> None:
        super().__init__()
        object.__setattr__(self, "_state", AppState())
        self.settings = get_settings()
        self._yaml_path = yaml_path or "gui_settings.yaml"
        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self.save_to_yaml)
        self._auto_save_timer.start(auto_save_interval) # save settings every 30s
        self.navigation_widget = None

    @property
    def current_frame(self):
        return self._state.current_frame

    @current_frame.setter
    def current_frame(self, value):
        self._state.current_frame = value
        # No-op: update_slider now handled in __setattr__
    

    def __getattr__(self, name):
        if name in AppStateSpec.VARS:
            return getattr(self._state, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in ("_state", "settings", "_yaml_path", "_auto_save_timer"):
            super().__setattr__(name, value)
            return
        if name in AppStateSpec.VARS:
            old_value = getattr(self._state, name, None)
            setattr(self._state, name, value)
            signal = getattr(self, f"{name}_changed", None)
            if signal and old_value != value:
                signal.emit(value)
            if name == "fps_playback":
                self.settings.application.playback_fps = value
            if name == "current_frame" and getattr(self, "navigation_widget", None) is not None:
                self.navigation_widget.update_slider()
 
                if (
                    hasattr(self, 'sync_state')
                    and self.sync_state == "video_to_lineplot"
                    and hasattr(self, 'lineplot')
                ):
                    self.lineplot.request_sync_update()
            return
        super().__setattr__(name, value)
        
        


    ## ------- Dynamic _sel variables ------------
    def get_ds_kwargs(self):
        ds_kwargs = {
            "trials": getattr(self, "trials_sel"),
        }
        # Ensure it's always int
        ds_kwargs["trials"] = int(ds_kwargs["trials"])

        if hasattr(self, "keypoints_sel"):
            ds_kwargs["keypoints"] = self.keypoints_sel
        if hasattr(self, "individuals_sel"):
            ds_kwargs["individuals"] = self.individuals_sel
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
        
        
        
        
        
        
        
        


    # ---------- Save state in gui_settings.yaml ----------
    # def get_saveable_state_dict(self) -> dict:
    #     """Get a dictionary of only the saveable attributes."""
    #     state_dict = {}
    #     for attr in self._state.saveable_attributes():
    #         value = getattr(self._state, attr)
    #         if value is not None:
    #             if isinstance(value, (int, float)) or hasattr(value, "dtype"):
    #                 with contextlib.suppress(TypeError, ValueError):
    #                     value = float(value)
    #             state_dict[attr] = value
                
    #     # Save dynamic _sel attributes
    #     for attr in dir(self):
    #         if attr.endswith("_sel") and not attr.startswith("_"):
    #             try:
    #                 value = getattr(self, attr)
    #                 if not callable(value) and value is not None:
    #                     state_dict[attr] = value
    #             except (AttributeError, TypeError):
    #                 continue
    #     return state_dict
    def get_saveable_state_dict(self) -> dict:
        state_dict = {}
        for attr in self._state.saveable_attributes():
            value = getattr(self._state, attr)
            if value is not None:
                try:
                    if hasattr(value, "item"):
                        value = value.item()
                    elif hasattr(value, "dtype"):
                        value = float(value)
                except Exception as exc:
                    print(f"Error converting {attr}: {exc}")
                state_dict[attr] = value

        # Save dynamic _sel attributes
        for attr in dir(self):
            if attr.endswith("_sel") and not attr.startswith("_"):
                try:
                    value = getattr(self, attr)
                    if not callable(value) and value is not None:
                        state_dict[attr] = value
                except (AttributeError, TypeError) as exc:
                    print(f"Error accessing {attr}: {exc}")
        return state_dict

    def load_from_dict(self, state_dict: dict):
        for key, value in state_dict.items():
            if value is None:
                continue
            if key in AppStateSpec.VARS or key.endswith("_sel"):
                setattr(self, key, value)

    def save_to_yaml(self, yaml_path: str | None = None) -> bool:
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
        if self._auto_save_timer.isActive():
            self._auto_save_timer.stop()
            self.save_to_yaml()