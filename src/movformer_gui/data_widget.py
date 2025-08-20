"""Widget for selecting start/stop times and playing a segment in napari."""

from typing import Any, Dict, Optional
from pathlib import Path
import yaml
import numpy as np
import os
import subprocess
import platform
import xarray as xr
from typing import Optional
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)
from qtpy.QtCore import QTimer, Signal

from movformer_gui.lineplot import LinePlot
from movformer_gui.data_loader import validate_media_folder, load_dataset
from movformer_gui.data_loader import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, SUPPORTED_EXTENSIONS
from movformer_gui.state_manager import State

class DataWidget(QWidget):
    """Widget to control which data is loaded, displayed and stored for next time."""

    def __init__(self, napari_viewer: Viewer, lineplot=None, parent=None, previous_state=None, labels_widget=None, plots_widget=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())
        self.LinePlot = lineplot  # Use the shared LinePlot instance
        self.labels_widget = labels_widget
        self.plots_widget = plots_widget

        # In case yaml empty, init as None
        self.current_trial = None
        self.current_keypoint = None
        self.current_variable = None
        self.current_color_variable = None
        self.current_trial_condition_key = None
        self.current_trial_condition_value = None
        self.trial_condition_keys = []
        self.ready = False

        # Apply previous settings
        if previous_state:
            for key, value in previous_state.items():
                setattr(self, key, value)


       



        # Initialize UI components references
        # Remove: self.LinePlot = None  


        # Set up config settings auto-save timer (every 10 seconds)
        
        # self.save_timer = QTimer()
        # self.save_timer.timeout.connect(self._auto_save_state)
        # self.save_timer.start(10000)  # 10000 milliseconds = 10 seconds


        self.create_path_folder_widgets()
        self._create_load_button()
        self._create_trial_controls()

        if previous_state and hasattr(self, 'file_path'):
            self.file_path_edit.setText(getattr(self, 'file_path', ''))
        if previous_state and hasattr(self, 'video_folder'):
            self.video_folder_edit.setText(getattr(self, 'video_folder', ''))
        if previous_state and hasattr(self, 'audio_folder'):
            self.audio_folder_edit.setText(getattr(self, 'audio_folder', ''))



    def _create_path_widget(self, label: str, object_name: str, browse_callback):
        """Generalized function to create a line edit and browse button for file/folder paths."""
        line_edit = QLineEdit()
        line_edit.setObjectName(f"{object_name}_edit")
        browse_button = QPushButton("Browse")
        browse_button.setObjectName(f"{object_name}_browse_button")
        browse_button.clicked.connect(browse_callback)

        layout = QHBoxLayout()
        layout.addWidget(line_edit)
        layout.addWidget(browse_button)
        self.layout().addRow(label, layout)
        return line_edit

    def create_path_folder_widgets(self):
        """Create file path, video folder, and audio folder selectors."""
        self.file_path_edit = self._create_path_widget(
            label="File path:",
            object_name="file_path",
            browse_callback=lambda: self.on_browse_clicked("file")
        )
        self.video_folder_edit = self._create_path_widget(
            label="Video folder:",
            object_name="video_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "video")
        )
        self.audio_folder_edit = self._create_path_widget(
            label="Audio folder:",
            object_name="audio_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "audio")
        )


    def _create_load_button(self):
        """Create a button to load the file to the viewer."""
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("load_button")
        self.load_button.clicked.connect(lambda: self.on_load_clicked())
        self.layout().addRow(self.load_button)
    

    
    def _create_trial_controls(self):
        """Create controls for trial selection and navigation."""
        
        # Video file dropdown
        self.camera_combo = QComboBox()
        self.camera_combo.setObjectName("camera_combo")
        self.camera_combo.currentTextChanged.connect(self._on_camera_changed)
        self.camera_combo.addItem("")  # Initialize empty
        
        # Audio file dropdown
        self.mic_combo = QComboBox()
        self.mic_combo.setObjectName("mic_combo")
        self.mic_combo.currentTextChanged.connect(self._on_mic_changed)
        self.mic_combo.addItem("")  # Initialize empty

        self.media_combo = QHBoxLayout()
        self.media_combo.addWidget(self.camera_combo)
        self.media_combo.addWidget(self.mic_combo)
        self.layout().addRow(self.media_combo)

        # Playback FPS input (QLineEdit instead of dropdown)
        self.fps_playback_edit = QLineEdit()
        self.fps_playback_edit.setObjectName("fps_playback_edit")
        self.fps_playback_edit.setText("30")
        self.fps_playback_edit.editingFinished.connect(self._on_fps_changed)
        self.layout().addRow("Playback FPS:", self.fps_playback_edit)

        # Keypoint dropdown
        self.keypoint_combo = QComboBox()
        self.keypoint_combo.setObjectName("keypoint_combo")
        self.keypoint_combo.currentTextChanged.connect(self._on_keypoint_changed)
        self.layout().addRow("Keypoint:", self.keypoint_combo)
        
        # Variable dropdown
        self.variable_combo = QComboBox()
        self.variable_combo.setObjectName("variable_combo")
        # Don't add items here - they'll be populated when ds is loaded
        self.variable_combo.currentTextChanged.connect(self._on_variable_changed)
        self.layout().addRow("Variable:", self.variable_combo)
        
        # Color variable dropdown (for RGB coloring)
        self.color_variable_combo = QComboBox()
        self.color_variable_combo.setObjectName("color_variable_combo")
        self.color_variable_combo.addItem("None")  # Default option for no coloring
        self.color_variable_combo.currentTextChanged.connect(self._on_color_variable_changed)
        self.layout().addRow("Color Variable:", self.color_variable_combo)

        # Trial condition filtering with two dropdowns
        self.trial_condition_key_combo = QComboBox()
        self.trial_condition_key_combo.setObjectName("trial_condition_key_combo")
        self.trial_condition_key_combo.currentTextChanged.connect(self._on_trial_condition_key_changed)
        
        self.trial_condition_value_combo = QComboBox()
        self.trial_condition_value_combo.setObjectName("trial_condition_value_combo")
        self.trial_condition_value_combo.addItem("None")  # Default option for no filtering
        self.trial_condition_value_combo.currentTextChanged.connect(self._on_trial_condition_value_changed)
        
        # Create horizontal layout for the two dropdowns
        self.trial_condition_layout = QHBoxLayout()
        self.trial_condition_layout.addWidget(self.trial_condition_key_combo)
        self.trial_condition_layout.addWidget(self.trial_condition_value_combo)
        self.layout().addRow("Filter by Condition:", self.trial_condition_layout)

        # Trial dropdown
        self.trial_combo = QComboBox()
        self.trial_combo.setObjectName("trial_combo")
        self.trial_combo.currentTextChanged.connect(self._on_trial_changed)
        self.layout().addRow("Trial:", self.trial_combo)

        # Previous/Next trial buttons
        self.prev_button = QPushButton("Previous Trial")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.clicked.connect(self._on_prev_trial)
        
        self.next_button = QPushButton("Next Trial")
        self.next_button.setObjectName("next_button")
        self.next_button.clicked.connect(self._on_next_trial)
        
        # Layout for navigation buttons
        self.nav_layout = QHBoxLayout()
        self.nav_layout.addWidget(self.prev_button)
        self.nav_layout.addWidget(self.next_button)
        self.layout().addRow("Navigation:", self.nav_layout)

        
        
        # Initially disable trial controls until data is loaded
        self._set_trial_controls_enabled(False)




    def on_browse_clicked(self, browse_type: str = "file", media_type: Optional[str] = None):
        """
        Open a file or folder dialog to select a file or folder.

        Args:
            browse_type: "file" for file dialog, "folder" for folder dialog.
            media_type: "video" or "audio" (used for folder dialog caption).
        """
        if browse_type == "file":
            result = QFileDialog.getOpenFileName(
                None,
                caption="Open file containing feature data",
                filter="NetCDF files (*.nc)",
            )
            file_path = result[0] if result and len(result) >= 1 else ""
            if not file_path:
                return
            
            self.file_path_edit.setText(file_path)
            self.file_path = file_path

        elif browse_type == "folder":
            caption = "Select folder containing "
            if media_type == "video":
                caption += f"video files ({' '.join(VIDEO_EXTENSIONS)})"
            elif media_type == "audio":
                caption += f"audio files ({' '.join(AUDIO_EXTENSIONS)})"
            folder_path = QFileDialog.getExistingDirectory(
                None,
                caption=caption
            )

            if media_type == "video" and validate_media_folder(folder_path, "video"):
                self.video_folder_edit.setText(folder_path)
                self.video_folder = folder_path
            elif media_type == "audio" and validate_media_folder(folder_path, "audio"):
                self.audio_folder_edit.setText(folder_path)
                self.audio_folder = folder_path
            else:
                raise ValueError(f"Selected folder does not contain valid {media_type} files or is empty.")


    def on_load_clicked(self):
        """Load the file and show line plot in napari dock."""
        file_path = self.file_path_edit.text()

        
        ds, info, error = load_dataset(file_path)
        if error:
            raise ValueError(f"Failed to load dataset: {error}")

        
        self.ds = ds
        State.set("ds", ds)
        
        trials = ds.coords['trial'].values.tolist()
        self.available_variables = [
            var for var in ds.data_vars
            if "type" in ds[var].attrs and ds[var].attrs["type"] == "feature"
        ]
        print(f"Successfully loaded dataset with {len(trials)} trials")

        for key, value in info.items():
            setattr(self, key, value)
            print(f"Loaded {key}: {value}")
        
            if key == "cameras":
                self.cameras = value


            if key == "mics":
                self.mics = value

            
            if key == "trial_condition":
                self.trial_condition_keys = [None] + value

                

        if (self.current_trial and # check if current trial is available from last time (.yaml)
            self.current_trial in self.trials): # check if it is valid
            self.trial_combo.setCurrentText(str(self.current_trial)) # set trial
        elif self.trials:
            # Default to first value
            self.current_trial = self.trials[0]

            
        # Same logic for other variables:
        if self.keypoints:
            if (self.current_keypoint and 
                self.current_keypoint in self.keypoints):
                self.keypoint_combo.setCurrentText(self.current_keypoint)
            else:
                self.current_keypoint = self.keypoints[0]

        if (self.current_variable and 
            self.current_variable in self.available_variables):
            self.variable_combo.setCurrentText(self.current_variable)
        elif self.available_variables:
            self.current_variable = self.available_variables[0]
        else:
            raise ValueError("No feature variables found. Please specify one. E.g. ds['pos'].attrs['type'] = 'feature'")
        

        if (self.current_color_variable and 
            self.current_color_variable in self.color_variables):
            self.color_variable_combo.setCurrentText(self.current_color_variable)


        if (self.current_trial_condition_key and 
            self.current_trial_condition_key in self.trial_condition_keys):
            self.trial_condition_key_combo.setCurrentText(self.current_trial_condition_key)
        elif self.trial_condition_keys:
            self.current_trial_condition_key = self.trial_condition_keys[0]

        # Initialize trial condition system
        if hasattr(self, 'current_trial_condition_key') and self.current_trial_condition_key:
            self._update_trial_condition_values()

        if hasattr(self, 'fps_playback'):
            self.fps_playback_edit.setText(str(self.fps_playback))
        if hasattr(self, "fps_playback"):
            self.fps_playback = getattr(self, "fps_playback")
        else:
            self.fps_playback = 30
  

        self._update_dropdown()
    


        # Only start do plotting after these are enabled
        self._set_trial_controls_enabled(True)

        self._update_plot()
        self._update_video()



    def _update_dropdown(self):
        """Update all dropdown contents."""
        
        self.trial_combo.clear()
        self.trial_combo.addItems([str(trial) for trial in self.trials])

        self.keypoint_combo.clear()
        self.keypoint_combo.addItems(self.keypoints)
        self.keypoint_combo.setEnabled(bool(self.keypoints))

        self.variable_combo.clear()
        self.variable_combo.addItems(self.available_variables)

        self.color_variable_combo.clear()
        self.color_variable_combo.addItem("None")
        self.color_variable_combo.addItems(self.color_variables)

        self.trial_condition_key_combo.clear()
        self.trial_condition_key_combo.addItems(self.trial_condition_keys)

        self.trial_condition_value_combo.clear()
        self.trial_condition_value_combo.addItem("None")

        if hasattr(self, "current_trial_condition_key") and self.current_trial_condition_key and hasattr(self, "ds") and self.current_trial_condition_key in self.ds.coords:
            unique_values = np.unique(self.ds.coords[self.current_trial_condition_key].values)
            self.trial_condition_value_combo.addItems([str(int(val)) for val in np.sort(unique_values)])

        self.camera_combo.clear()
        self.camera_combo.addItems(getattr(self, "cameras", []))

        self.mic_combo.clear()
        self.mic_combo.addItems(getattr(self, "mics", []))

    
    def _set_trial_controls_enabled(self, enabled: bool):
        """Enable or disable all buttons."""
        buttons = [
            self.trial_combo,
            self.keypoint_combo,
            self.variable_combo,
            self.color_variable_combo,
            self.trial_condition_key_combo,
            self.trial_condition_value_combo,
            self.camera_combo,
            self.mic_combo,
            self.prev_button,
            self.next_button,
        ]
        for combo in buttons:
            combo.setEnabled(enabled)

        if enabled:
            self.ready = True

    
    def _on_trial_changed(self, trial_text: str):
        """Handle trial selection change from UI."""
        try:
            self.current_trial = int(trial_text)
            State.set("current_trial", int(trial_text))
        except ValueError:
            return
        
        self._update_video()
        self._update_plot()
        

    def next_trial(self):
        """Go to the next trial. Can be called by shortcut."""
        self._on_next_trial()

    def prev_trial(self):
        """Go to the previous trial."""
        self._on_prev_trial()

    def _on_prev_trial(self):
        """Navigate to previous trial."""
        if self._navigate_trial(-1):
            # Directly update video and plot without setting currentText to avoid double-calling
            self._update_video()
            self._update_plot()

    def _on_next_trial(self):
        """Navigate to next trial."""
        if self._navigate_trial(1):
            self._update_video()
            self._update_plot()

    def _navigate_trial(self, direction: int) -> bool:
        """Navigate to next/previous trial."""
        if self.current_trial is None or not self.trials:
            return False
        try:
            idx = self.trials.index(self.current_trial) + direction

            if 0 <= idx < len(self.trials):
                self.current_trial = self.trials[idx]
                # Update the combo box text without triggering the signal
                self.trial_combo.blockSignals(True)
                self.trial_combo.setCurrentText(str(self.current_trial))
                self.trial_combo.blockSignals(False)
                return True
        except ValueError:
            pass
        return False


    def _on_camera_changed(self, camera: str):
        """Handle camera selection change from UI."""
        self.current_camera = camera
        self._update_video()


    def _on_mic_changed(self, mic: str):
        """Handle microphone selection change from UI.
        """
        self.current_mic = mic
        # TODO: Implement audio update logic here if/when needed.
        pass

    def _on_fps_changed(self):
        """Handle playback FPS change from UI."""
        fps = int(self.fps_playback_edit.text())
        self.fps_playback = fps
        State.set("fps_playback", fps)



    def _on_keypoint_changed(self, keypoint: str):
        """Handle keypoint selection change from UI."""
        self.current_keypoint = keypoint
        State.set("current_keypoint", keypoint)
        self._update_plot()


    def _on_variable_changed(self, variable: str):
        """Handle variable selection change from UI."""
        self.current_variable = variable
        self._update_plot()


    def _on_color_variable_changed(self, color_variable: str):
        """Handle color variable selection change from UI."""
        if color_variable == "None":
            self.current_color_variable = None
        else:
            self.current_color_variable = color_variable
        self._update_plot()


    def _on_trial_condition_key_changed(self, condition_key: str):
        """Handle trial condition key selection change from UI."""
        self.current_trial_condition_key = condition_key if condition_key else None
        self._update_trial_condition_values()
  
        
    def _update_trial_condition_values(self):
        """Update the trial condition value dropdown based on selected key."""
        self.trial_condition_value_combo.blockSignals(True)
        self.trial_condition_value_combo.clear()
        self.trial_condition_value_combo.addItem("None")  # Default option

        if self.current_trial_condition_key and self.current_trial_condition_key in self.ds.coords:
            # Get unique values for the selected condition key
            unique_values = np.unique(self.ds.coords[self.current_trial_condition_key].values)
            self.trial_condition_value_combo.addItems([str(int(val)) for val in np.sort(unique_values)])

        self.trial_condition_value_combo.blockSignals(False)

    def _on_trial_condition_value_changed(self, condition_value: str):
        """Handle trial condition value selection change from UI."""
        if condition_value == "None":
            self.current_trial_condition_value = None
        else:
            self.current_trial_condition_value = condition_value

        # Block signals to prevent unnecessary updates during filtering
        self.trial_combo.blockSignals(True)
        self._update_filtered_trials()
        self.trial_combo.blockSignals(False)
        self._update_plot()



    def _update_filtered_trials(self):
        """Update the available trials based on condition filtering."""

            
        # Get all trials
        all_trials = self.ds.coords['trial'].values.tolist()

        coord_key = self.current_trial_condition_key
        coord_value = self.current_trial_condition_value


        if (coord_key and coord_value and coord_value != "None"):
            # Filter trials based on condition
            ds = self.ds.copy(deep=True)
            self.trials = ds.trial.where(ds[coord_key] == int(coord_value), drop=True).values

        else:
            return
        

        # Update trials dropdown
        self.trial_combo.clear()
        self.trial_combo.addItems([str(int(trial)) for trial in self.trials])

        if self.current_trial not in self.trials:
            self.current_trial = int(self.trials[0])
            self.trial_combo.setCurrentText(str(self.current_trial))


    def _update_video(self):
        if not self.ready:
            return     
    
        try:    
            file_name = self.ds[self.camera_combo.currentText()].sel(trial=self.current_trial).values.item()
            video_path = os.path.join(self.video_folder, file_name)
            

            # Remove existing video-like layers
            layers_to_remove = []
            for layer in self.viewer.layers:
                if "video" in layer.name.lower():
                    layers_to_remove.append(layer)
            for layer in layers_to_remove:
                self.viewer.layers.remove(layer)

            # Open new video
            video_layer = self.viewer.open(video_path)
            if isinstance(video_layer, list) and video_layer:
                video_layer = video_layer[0]
            if hasattr(video_layer, 'name'):
                video_layer.name = "video"
        except Exception as e:
            print(f"Error loading video: {e}")






    def _update_plot(self):
        """Update the line plot with current trial/keypoint/variable selection."""
        if not self.ready:
            return            
        
        try:
            print("1")
            self.LinePlot.updateLinePlot(
                self.ds, 
                self.current_trial, 
                self.current_keypoint, 
                self.current_variable, 
                self.current_color_variable
            )

            print("2")
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            labels = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).labels.values
            self.labels_widget.plot_all_motifs(time_data, labels)


                
        except Exception as e:
            print(f"Error updating plot: {e}")
    



#     def _auto_save_state(self):
#         """Auto-save state every 10 seconds."""
#         # Check if yaml_path exists
#         if not hasattr(self, 'yaml_path'):
#             print("Error: yaml_path not set, cannot auto-save")
#             return
            
#         save_state = {}
#         save_state.update(self.save_object_attributes(self))

#         if hasattr(self, 'plots_widget') and self.plots_widget is not None:
#             save_state.update(self.save_object_attributes(self.plots_widget))
#         self._save_state_as_file(save_state)


#     # Before closing, store current state for some self.attributes
#     def closeEvent(self, event):
#         """Handle close event by stopping the timer and saving state one final time."""
#         # Stop the auto-save timer
#         if hasattr(self, 'save_timer'):
#             self.save_timer.stop()
        
#         # Save state one final time
#         save_state = {}
#         save_state.update(self.save_object_attributes(self))
#         if hasattr(self, 'plots_widget') and self.plots_widget is not None:
#             save_state.update(self.save_object_attributes(self.plots_widget))
#         self._save_state_as_file(save_state)
#         super().closeEvent(event)

#     def _save_state_as_file(self, save_state) -> None:
#         try:
#             with open(self.yaml_path, "w", encoding="utf-8") as f:
#                 yaml.dump(save_state, f, default_flow_style=False, sort_keys=False)
#         except Exception as e:
#             print(f"Error saving state file: {e}")

#     def save_object_attributes(self, obj: object, prefix: str = "") -> dict:
#         """Return a dict of saveable attributes from an object."""
#         attrs = {}


        

#         saveable_attrs = [
#             # DataWidget attributes
#             'yaml_path', 'file_path', 'video_folder', 'audio_folder', 'current_trial', 'current_keypoint', 'current_variable', 'current_color_variable',
#             'current_trial_condition_key', 'current_trial_condition_value',
#             'color_variables', 'cameras', 'mics', 'fps_playback',
#             # PlotsWidget attributes
#             'ymin', 'ymin', 'window_size'
#         ]

            
#         for attr_name in saveable_attrs:
#             if hasattr(obj, attr_name):
#                 try:
#                     value = getattr(obj, attr_name)
#                     key = f"{prefix}{attr_name}" if prefix else attr_name
#                     attrs[key] = value
#                 except Exception:
#                     continue


#         return attrs



# 4