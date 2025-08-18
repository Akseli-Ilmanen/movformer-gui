"""Widget for selecting start/stop times and playing a segment in napari."""

import numpy as np
import os
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
from qtpy.QtGui import QCloseEvent

from movformer_gui.lineplot_widget import LinePlotWidget
from movformer_gui.state_manager import GUIStateManager



class DataWidget(QWidget):
    """Widget to control which is data loaded and displayed."""

    def __init__(self, napari_viewer: Viewer, parent=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())
        
        # Initialize state manager
        self.state_manager = GUIStateManager()
        
        # Initialize trial tracking variables from saved state
        self.ds = None
        self.current_trial = self.state_manager.get_value("current_trial")
        self.trials = []
        self.keypoints = []
        self.current_keypoint = self.state_manager.get_value("current_keypoint")
        self.current_variable = self.state_manager.get_value("current_variable")
        self.current_color_variable = self.state_manager.get_value("current_color_variable")
        self.plot_widget = None  # Store reference to plot widget
        self.labels_widget = None  # Store reference to labels widget (set by MetaWidget)
        self.video_file_paths = []

        self._create_file_path_widget()
        self._create_video_folder_widget()
        self._create_load_button()
        self._create_trial_controls()
        
        # Load saved paths if they exist
        saved_file_path = self.state_manager.get("file_path")
        if saved_file_path:
            self.file_path_edit.setText(saved_file_path)
        
        saved_video_folder = self.state_manager.get("video_folder_path")
        if saved_video_folder:
            self.video_folder_edit.setText(saved_video_folder)
    
    def set_labels_widget(self, labels_widget):
        """Set the labels widget reference from MetaWidget."""
        self.labels_widget = labels_widget
        

    def save_current_state(self):
        """Save all current widget values to state manager."""
        state_updates = {}
        
        # Save current selections if they exist
        if hasattr(self, 'current_trial') and self.current_trial is not None:
            state_updates["current_trial"] = self.current_trial
        
        if hasattr(self, 'current_keypoint') and self.current_keypoint is not None:
            state_updates["current_keypoint"] = self.current_keypoint
        
        if hasattr(self, 'current_variable') and self.current_variable is not None:
            state_updates["current_variable"] = self.current_variable
        
        if hasattr(self, 'current_color_variable') and self.current_color_variable is not None:
            state_updates["current_color_variable"] = self.current_color_variable
        
        # Save file paths
        if hasattr(self, 'file_path_edit'):
            file_path = self.file_path_edit.text()
            if file_path:
                state_updates["file_path"] = file_path
        
        if hasattr(self, 'video_folder_edit'):
            video_folder = self.video_folder_edit.text()
            if video_folder:
                state_updates["video_folder_path"] = video_folder
        
        # Update state manager with all changes
        if state_updates:
            self.state_manager.update(state_updates)



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

    def _create_file_path_widget(self):
        """Create file path selector."""
        self.file_path_edit = self._create_path_widget(
            label="File path:",
            object_name="file_path",
            browse_callback=self._on_browse_clicked
        )

    def _create_video_folder_widget(self):
        """Create video folder path selector."""
        self.video_folder_edit = self._create_path_widget(
            label="Video folder:",
            object_name="video_folder",
            browse_callback=self._on_video_browse_clicked
        )

    def _create_load_button(self):
        """Create a button to load the file to the viewer."""
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("load_button")
        self.load_button.clicked.connect(lambda: self._on_load_clicked())
        self.layout().addRow(self.load_button)
    
    def _create_trial_controls(self):
        """Create controls for trial selection and navigation."""
        

        
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



    def closeEvent(self, event):
        """Handle close event by ensuring state is saved."""
        # Save all current widget states first
        self.save_current_state()
        super().closeEvent(event)


    def _on_browse_clicked(self):
        """Open a file dialog to select a file."""
        file_suffixes = ["*.nc", "*.npy"]

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            caption="Open file containing feature data",
            filter=f"Valid data files ({' '.join(file_suffixes)})",
        )

        # A blank string is returned if the user cancels the dialog
        if not file_path:
            return

        # Validate file extension
        if not (file_path.endswith('.nc') or file_path.endswith('.npy')):
            print(f"Error: File must end with .nc or .npy extension")
            return

        # Add the file path to the line edit (text field)
        self.file_path_edit.setText(file_path)

    def _on_video_browse_clicked(self):
        """Open a folder dialog to select a video folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            caption="Select folder containing video files (.mp4, .mov, etc.)"
        )

        # A blank string is returned if the user cancels the dialog
        if not folder_path:
            return

        # Add the folder path to the line edit (text field)
        self.video_folder_edit.setText(folder_path)



    def _on_load_clicked(self):
        """Load the file and show line plot in napari dock."""

        self.file_path = self.file_path_edit.text()


        # Load xarray ds
        self.ds = xr.open_dataset(self.file_path)
        
        # Get video_file_names from ds coordinates if available
        video_file_names = list(self.ds["video_file_names"].values)
        self.video_file_names = video_file_names

        # Extract trial information
        self.trials = self.ds.coords["trial"].values.tolist()
        self.keypoints = self.ds.coords["keypoints"].values.tolist()
        
        # Update dropdowns
        self.trial_combo.clear()
        self.trial_combo.addItems([str(trial) for trial in self.trials])
        
        self.keypoint_combo.clear() 
        self.keypoint_combo.addItems(self.keypoints)
        
        # Populate variable dropdown with actual data variables from ds
        self.variable_combo.clear()
        available_variables = [
            var_name for var_name, var in self.ds.data_vars.items()
            if var.attrs.get("type") == "feature"
        ]
        self.variable_combo.addItems(available_variables)
        
        # Populate color variable dropdown with variables that have shape (N, 3) for RGB coloring
        self.color_variable_combo.clear()
        color_variables = [
            var_name for var_name, var in self.ds.data_vars.items()
            if var.attrs.get("type") == "color"
        ]
        self.color_variable_combo.addItems(color_variables)

        
        # Set saved values if they exist and are still valid
        if self.current_keypoint in self.keypoints:
            self.keypoint_combo.setCurrentText(self.current_keypoint)
        if self.current_trial in self.trials:
            self.trial_combo.setCurrentText(str(self.current_trial))

        if self.current_variable in available_variables:
            self.variable_combo.setCurrentText(self.current_variable)
        elif available_variables:
            # If saved variable doesn't exist, set to first available
            self.current_variable = available_variables[0]
            self.variable_combo.setCurrentText(self.current_variable)
        
        if self.current_color_variable in color_variables:
            self.color_variable_combo.setCurrentText(self.current_color_variable)
        else: 
            self.current_color_variable = None


        
        # Enable trial controls
        self._set_trial_controls_enabled(True) # REWRITE?
        
            
    
        # Create initial plot
        self._update_plot()
        return
            

    
    def _set_trial_controls_enabled(self, enabled: bool):
        """Enable or disable trial control widgets."""
        self.trial_combo.setEnabled(enabled)
        self.keypoint_combo.setEnabled(enabled)
        self.variable_combo.setEnabled(enabled)
        self.color_variable_combo.setEnabled(enabled)
        self.prev_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
    
    def _on_trial_changed(self, trial_text: str):
        """Handle trial selection change."""
        try:
            self.current_trial = int(trial_text)
            self._update_plot()
            self._update_video_path_for_trial()

            # Remove layers with 'video' tag, then open new video
            # Remove existing video layers and add new video for current trial
            for layer in list(self.viewer.layers):
                if 'video' in layer.name.lower():
                    self.viewer.layers.remove(layer)

            video_layer = self.viewer.open(self.current_video_path)
            if isinstance(video_layer, list):
                video_layer = video_layer[0]
            video_layer.name = "video"
        except ValueError:
            pass

    def _on_keypoint_changed(self, keypoint: str):
        """Handle keypoint selection change."""
        self.current_keypoint = keypoint
        self._update_plot()

    def _on_variable_changed(self, variable: str):
        """Handle variable selection change."""
        self.current_variable = variable
        self._update_plot()

    def _on_color_variable_changed(self, color_variable: str):
        """Handle color variable selection change."""
        if color_variable == "None":
            self.current_color_variable = None
        else:
            self.current_color_variable = color_variable
        self._update_plot()
    
    def _on_prev_trial(self):
        """Navigate to previous trial."""
        if not self.trials:
            return
            
        current_idx = self.trials.index(self.current_trial)
        if current_idx > 0:
            new_trial = self.trials[current_idx - 1]
            # Block signals to prevent loop
            self.trial_combo.blockSignals(True)
            self.trial_combo.setCurrentText(str(new_trial))
            self.trial_combo.blockSignals(False)
            self._on_trial_changed(str(new_trial))
    
    def _on_next_trial(self):
        """Navigate to next trial."""
        if not self.trials:
            return
        
        current_idx = self.trials.index(self.current_trial)
        if current_idx < len(self.trials) - 1:
            new_trial = self.trials[current_idx + 1]
            # Block signals to prevent loop
            self.trial_combo.blockSignals(True)
            self.trial_combo.setCurrentText(str(new_trial))
            self.trial_combo.blockSignals(False)
            self._on_trial_changed(str(new_trial))
    
    def _update_plot(self):
        """Update the line plot with current trial/keypoint/variable selection."""
        try:
            # Create or update lineplot widget
            if self.plot_widget is None:
                # Create new plot widget
                self.plot_widget = LinePlotWidget(self.viewer, self.ds)
                self.viewer.window.add_dock_widget(self.plot_widget, area="bottom")
            
            # Update plot with current selections
            self.plot_widget.updateLinePlot(
                self.ds, 
                self.current_trial, 
                self.current_keypoint, 
                self.current_variable, 
                self.current_color_variable
            )
            
            # Update labels widget with current data if it's available
            if self.labels_widget is not None:
                # Update labels widget with current data
                self.labels_widget.set_data(self.ds, self.current_trial, self.current_keypoint, self.current_variable)
                
                # Connect labels widget to lineplot widget
                self.labels_widget.set_lineplot_widget(self.plot_widget)
                
                # Connect labels updated signal if not already connected
                if not hasattr(self, '_labels_connected'):
                    self.labels_widget.labels_updated.connect(self._on_labels_updated)
                    # Connect navigation signals
                    self.labels_widget.next_trial_requested.connect(self._on_next_trial)
                    self.labels_widget.prev_trial_requested.connect(self._on_prev_trial)
                    self._labels_connected = True
            
        except Exception as e:
            print(f"Error updating plot: {e}")
    
    def _on_labels_updated(self, labels_array):
        """Handle when labels are updated in the labels widget."""
        # You could add logic here to save the labels to the ds
        # or trigger other updates as needed
        print(f"Labels updated with {len(np.unique(labels_array))} unique labels")
    

    def _update_video_path_for_trial(self):
        """Get the video file name for a given trial number."""
        

        if len(self.video_file_names) != len(self.trials):
            print(f"Number of trials does not match number of videos specified in ds.")

        trial_idx = self.trials.index(self.current_trial)
        self.current_video_path = os.path.join(self.video_folder_edit.text(), self.video_file_names[trial_idx])

    
    def _on_play_clicked(self):

        # Assume viewer.dims.current_step[0] is the frame index
        # and viewer.dims.range[0] gives (min, max, step)
        fps = self.fps_spinbox.value()
        start_frame = int(start_time * fps)
        stop_frame = int(stop_time * fps)
        self.viewer.dims.set_current_step(0, start_frame)
        self._play_segment(start_frame, stop_frame, fps)

    def _play_segment(self, start_frame, stop_frame, fps):
        import time

        for frame in range(start_frame, stop_frame + 1):
            self.viewer.dims.set_current_step(0, frame)
            if QApplication is not None:
                QApplication.processEvents()
            time.sleep(1.0 / fps)


try:
    from qtpy.QtWidgets import QApplication
except ImportError:
    QApplication = None
