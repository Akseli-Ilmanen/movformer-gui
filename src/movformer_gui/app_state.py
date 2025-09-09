"""Refactored observable application state with napari video sync support."""

from pathlib import Path
from typing import Any

import xarray as xr
import yaml
from napari.settings import get_settings
from qtpy.QtCore import QObject, QTimer, Signal


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
        "fps_playback": (float, 30.0, True, float),
        "trials": (list[int], [], False, object),
        "nc_file_path": (str | None, None, True, str),
        "video_folder": (str | None, None, True, str),
        "audio_folder": (str | None, None, True, str),
        "tracking_folder": (str | None, None, True, str),
        "video_path": (str | None, None, True, str),
        "audio_path": (str | None, None, True, str),
        "tracking_path": (str | None, None, True, str),
        "current_frame": (int, 0, False, int),  # PRIMARY source of truth
        "num_frames": (int, 0, False, int),
        "_info_data": (dict[str, Any], {}, False, object),
        "sync_state": (str | None, None, False, object),
        "ymin": (float | None, None, True, object),
        "ymax": (float | None, None, True, object),
        "spec_ymin": (float | None, None, True, object),
        "spec_ymax": (float | None, None, True, object),
        "window_size": (float, 2.0, True, object),
        "jump_size": (float, 0.2, True, object),
        "audio_buffer": (float | None, None, True, float),
        "spec_buffer": (float | None, None, True, float),
        "video_buffer_size": (int, 300, True, int),
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
        
    }


class AppState:
    def __init__(self):
        for var, (var_type, default, _, _) in AppStateSpec.VARS.items():
            setattr(self, var, default)

    def saveable_attributes(self) -> set[str]:
        return {k for k, (_, _, save, _) in AppStateSpec.VARS.items() if save}


class ObservableAppState(QObject):
    """State container with change notifications and computed properties."""

    # Signals for state changes
    for var, (_, _, _, signal_type) in AppStateSpec.VARS.items():
        locals()[f"{var}_changed"] = Signal(signal_type)

    data_updated = Signal()


    def __init__(self, yaml_path: str | None = None, auto_save_interval: int = 30000):
        super().__init__()
        object.__setattr__(self, "_state", AppState())
        object.__setattr__(self, "_fps_cache", None)  # Cache for FPS value

        self.settings = get_settings()
        self._yaml_path = yaml_path or "gui_settings.yaml"
        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self.save_to_yaml)
        self._auto_save_timer.start(auto_save_interval)



    def _get_fps(self) -> float | None:
        """Get FPS from dataset, with caching."""
        if hasattr(self._state, "ds") and self._state.ds is not None:
            if hasattr(self._state.ds, "fps"):
                self._fps_cache = float(self._state.ds.fps)
                return self._fps_cache
        return self._fps_cache  # Return cached value if DS not available

    def get_with_default(self, key):
        """Return value from app state, or default from AppStateSpec if None."""
        value = getattr(self, key, None)
        if value is None:
            value = AppStateSpec.get_default(key)
        return value

    def __getattr__(self, name):
        if name in AppStateSpec.VARS:
            return getattr(self._state, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # Handle special attributes that don't go through state
        if name in (
            "_state",
            "_fps_cache",
            "settings",
            "_yaml_path",
            "_auto_save_timer",
            "navigation_widget",
            "lineplot",
        ):
            super().__setattr__(name, value)
            return

        # Handle state variables
        if name in AppStateSpec.VARS:
            old_value = getattr(self._state, name, None)
            setattr(self._state, name, value)

            # Emit signal if value changed
            signal = getattr(self, f"{name}_changed", None)
            if signal and old_value != value:
                signal.emit(value)

            if name == "ds":
                # Clear FPS cache when dataset changes
                self._fps_cache = None

            return

        # Handle other attributes
        super().__setattr__(name, value)

    # --- Dynamic _sel variables ---
    def get_ds_kwargs(self):
        ds_kwargs = {"trials": self.trials_sel}
        ds_kwargs["trials"] = int(ds_kwargs["trials"])

        # Only include dimensions that exist in the dataset
        if self.ds is not None:
            if hasattr(self, "keypoints_sel") and "keypoints" in self.ds.dims:
                ds_kwargs["keypoints"] = self.keypoints_sel
            if hasattr(self, "individuals_sel") and "individuals" in self.ds.dims:
                ds_kwargs["individuals"] = self.individuals_sel
        else:
            # Fallback for when dataset isn't loaded yet
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

        if old_value != currentValue:
            self.data_updated.emit()

    # --- Save/Load methods ---
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
