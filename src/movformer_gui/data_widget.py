"""Widget for selecting start/stop times and playing a segment in napari."""

import os

import numpy as np
from napari.utils.notifications import show_error
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

from movformer_gui.app_state import ObservableAppState
from movformer_gui.data_loader import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    load_dataset,
    validate_media_folder,
)


class DataWidget(QWidget):
    """Widget to control which data is loaded, displayed and stored for next time."""

    def __init__(
        self,
        napari_viewer: Viewer,
        lineplot=None,
        parent=None,
        labels_widget=None,
        plots_widget=None,
        app_state=None,
    ):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())
        self.LinePlot = lineplot  # Use the shared LinePlot instance
        self.labels_widget = labels_widget
        self.plots_widget = plots_widget

        # Use provided app_state (should always be provided by meta_widget)
        self.app_state = app_state if app_state else ObservableAppState()

        self.create_path_folder_widgets()
        self._create_load_button()
        self._create_trial_controls()

        # Restore UI text fields from app state
        if self.app_state.file_path:
            self.file_path_edit.setText(self.app_state.file_path)
        if self.app_state.video_folder:
            self.video_folder_edit.setText(self.app_state.video_folder)
        if self.app_state.audio_folder:
            self.audio_folder_edit.setText(self.app_state.audio_folder)

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
            browse_callback=lambda: self.on_browse_clicked("file"),
        )
        self.video_folder_edit = self._create_path_widget(
            label="Video folder:",
            object_name="video_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "video"),
        )
        self.audio_folder_edit = self._create_path_widget(
            label="Audio folder:",
            object_name="audio_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "audio"),
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
        self.trial_condition_key_combo.currentTextChanged.connect(
            self._on_trial_condition_key_changed
        )

        self.trial_condition_value_combo = QComboBox()
        self.trial_condition_value_combo.setObjectName("trial_condition_value_combo")
        self.trial_condition_value_combo.addItem("None")  # Default option for no filtering
        self.trial_condition_value_combo.currentTextChanged.connect(
            self._on_trial_condition_value_changed
        )

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

    def on_browse_clicked(self, browse_type: str = "file", media_type: str | None = None):
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
            self.app_state.file_path = file_path

        elif browse_type == "folder":
            caption = "Select folder containing "
            if media_type == "video":
                caption += f"video files ({' '.join(VIDEO_EXTENSIONS)})"
            elif media_type == "audio":
                caption += f"audio files ({' '.join(AUDIO_EXTENSIONS)})"
            folder_path = QFileDialog.getExistingDirectory(None, caption=caption)

            if media_type == "video" and validate_media_folder(folder_path, "video"):
                self.video_folder_edit.setText(folder_path)
                self.app_state.video_folder = folder_path
            elif media_type == "audio" and validate_media_folder(folder_path, "audio"):
                self.audio_folder_edit.setText(folder_path)
                self.app_state.audio_folder = folder_path
            else:
                raise ValueError(
                    f"Selected folder does not contain valid {media_type} files or is empty."
                )

    def on_load_clicked(self):
        """Load the file and show line plot in napari dock."""
        file_path = self.file_path_edit.text()

        ds, info, error = load_dataset(file_path)
        if error:
            raise ValueError(f"Failed to load dataset: {error}")

        self.app_state.ds = ds

        trials = ds.coords["trial"].values.tolist()
        available_variables = [
            var
            for var in ds.data_vars
            if "type" in ds[var].attrs and ds[var].attrs["type"] == "feature"
        ]
        print(f"Successfully loaded dataset with {len(trials)} trials")

        # Update app state with loaded data
        for key, value in info.items():
            if hasattr(self.app_state, key):
                setattr(self.app_state, key, value)
            print(f"Loaded {key}: {value}")

        self.app_state.available_variables = available_variables

        # Set current selections from previous state or defaults using helper method
        self._restore_or_set_default_selections()

        # Initialize trial condition system
        if self.app_state.current_trial_condition_key:
            self._update_trial_condition_values()

        # Set FPS from app state
        self.fps_playback_edit.setText(str(self.app_state.fps_playback))

        self._update_dropdown()

        # Only start plotting after controls are enabled
        self._set_trial_controls_enabled(True)

        self._update_plot()
        self._update_video()

    def _restore_or_set_default_selections(self):
        """Restore saved selections from app_state or set defaults from available options."""

        # Configuration for each selection: (current_attr, available_attr, combo_widget)
        selection_configs = [
            ("current_trial", "trials", self.trial_combo, False),
            ("current_keypoint", "keypoints", self.keypoint_combo, False),
            (
                "current_variable",
                "available_variables",
                self.variable_combo,
            ),
            (
                "current_color_variable",
                "color_variables",
                self.color_variable_combo,
            ),
            (
                "current_trial_condition_key",
                "trial_condition_keys",
                self.trial_condition_key_combo,
            ),
        ]

        for (
            current_attr,
            available_attr,
            combo_widget,
        ) in selection_configs:
            current_value = getattr(self.app_state, current_attr)
            available_values = getattr(self.app_state, available_attr)

            if available_values:  # Only proceed if there are available options
                if current_value and current_value in available_values:
                    # Restore saved selection if it's still valid
                    combo_widget.setCurrentText(str(current_value))
                else:
                    # Set to first available option as default
                    setattr(self.app_state, current_attr, available_values[0])
                    combo_widget.setCurrentText(str(available_values[0]))

            # Current variable is required.
            elif current_attr == "current_variable":
                show_error(
                    "No feature variables found. Please specify one. E.g. ds['pos'].attrs['type'] = 'feature'"
                )

    def _update_dropdown(self):
        """Update all dropdown contents."""

        self.trial_combo.clear()
        self.trial_combo.addItems([str(trial) for trial in self.app_state.trials])

        self.keypoint_combo.clear()
        self.keypoint_combo.addItems(self.app_state.keypoints)
        self.keypoint_combo.setEnabled(bool(self.app_state.keypoints))

        self.variable_combo.clear()
        self.variable_combo.addItems(self.app_state.available_variables)

        self.color_variable_combo.clear()
        self.color_variable_combo.addItem("None")
        self.color_variable_combo.addItems(self.app_state.color_variables)

        self.trial_condition_key_combo.clear()
        self.trial_condition_key_combo.addItems(self.app_state.trial_condition_keys)

        self.trial_condition_value_combo.clear()
        self.trial_condition_value_combo.addItem("None")

        if (
            self.app_state.current_trial_condition_key
            and self.app_state.current_trial_condition_key in self.app_state.ds.coords
        ):
            unique_values = np.unique(
                self.app_state.ds.coords[self.app_state.current_trial_condition_key].values
            )
            self.trial_condition_value_combo.addItems(
                [str(int(val)) for val in np.sort(unique_values)]
            )

        self.camera_combo.clear()
        self.camera_combo.addItems(self.app_state.cameras)

        self.mic_combo.clear()
        self.mic_combo.addItems(self.app_state.mics)

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

        self.app_state.ready = enabled

    def _on_trial_changed(self, trial_text: str):
        """Handle trial selection change from UI."""
        try:
            self.app_state.current_trial = int(trial_text)
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
        if self.app_state.current_trial is None or not self.app_state.trials:
            return False
        try:
            idx = self.app_state.trials.index(self.app_state.current_trial) + direction

            if 0 <= idx < len(self.app_state.trials):
                self.app_state.current_trial = self.app_state.trials[idx]
                # Update the combo box text without triggering the signal
                self.trial_combo.blockSignals(True)
                self.trial_combo.setCurrentText(str(self.app_state.current_trial))
                self.trial_combo.blockSignals(False)
                return True
        except ValueError:
            pass
        return False

    def _on_camera_changed(self, camera: str):
        """Handle camera selection change from UI."""
        self.app_state.current_camera = camera
        self._update_video()

    def _on_mic_changed(self, mic: str):
        """Handle microphone selection change from UI."""
        self.app_state.current_mic = mic
        # TODO: Implement audio update logic here if/when needed.

    def _on_fps_changed(self):
        """Handle playback FPS change from UI."""
        fps = int(self.fps_playback_edit.text())
        self.app_state.fps_playback = fps

    def _on_keypoint_changed(self, keypoint: str):
        """Handle keypoint selection change from UI."""
        self.app_state.current_keypoint = keypoint
        self._update_plot()

    def _on_variable_changed(self, variable: str):
        """Handle variable selection change from UI."""
        self.app_state.current_variable = variable
        self._update_plot()

    def _on_color_variable_changed(self, color_variable: str):
        """Handle color variable selection change from UI."""
        if color_variable == "None":
            self.app_state.current_color_variable = None
        else:
            self.app_state.current_color_variable = color_variable
        self._update_plot()

    def _on_trial_condition_key_changed(self, condition_key: str):
        """Handle trial condition key selection change from UI."""
        self.app_state.current_trial_condition_key = condition_key if condition_key else None
        self._update_trial_condition_values()

    def _update_trial_condition_values(self):
        """Update the trial condition value dropdown based on selected key."""
        self.trial_condition_value_combo.blockSignals(True)
        self.trial_condition_value_combo.clear()
        self.trial_condition_value_combo.addItem("None")  # Default option

        if (
            self.app_state.current_trial_condition_key
            and self.app_state.current_trial_condition_key in self.app_state.ds.coords
        ):
            # Get unique values for the selected condition key
            unique_values = np.unique(
                self.app_state.ds.coords[self.app_state.current_trial_condition_key].values
            )
            self.trial_condition_value_combo.addItems(
                [str(int(val)) for val in np.sort(unique_values)]
            )

        self.trial_condition_value_combo.blockSignals(False)

    def _on_trial_condition_value_changed(self, condition_value: str):
        """Handle trial condition value selection change from UI."""
        if condition_value == "None":
            self.app_state.current_trial_condition_value = None
        else:
            self.app_state.current_trial_condition_value = condition_value

        # Block signals to prevent unnecessary updates during filtering
        self.trial_combo.blockSignals(True)
        self._update_filtered_trials()
        self.trial_combo.blockSignals(False)
        self._update_plot()

    def _update_filtered_trials(self):
        """Update the available trials based on condition filtering."""

        coord_key = self.app_state.current_trial_condition_key
        coord_value = self.app_state.current_trial_condition_value

        if coord_key and coord_value and coord_value != "None":
            # Filter trials based on condition
            ds = self.app_state.ds.copy(deep=True)
            filtered_trials = ds.trial.where(ds[coord_key] == int(coord_value), drop=True).values
            self.app_state.trials = list(filtered_trials)
        else:
            return

        # Update trials dropdown
        self.trial_combo.clear()
        self.trial_combo.addItems([str(int(trial)) for trial in self.app_state.trials])

        if self.app_state.current_trial not in self.app_state.trials:
            self.app_state.current_trial = int(self.app_state.trials[0])
            self.trial_combo.setCurrentText(str(self.app_state.current_trial))

    def _update_video(self):
        if not self.app_state.ready:
            return

        try:
            file_name = (
                self.app_state.ds[self.camera_combo.currentText()]
                .sel(trial=self.app_state.current_trial)
                .values.item()
            )
            video_path = os.path.join(self.app_state.video_folder, file_name)

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
            if hasattr(video_layer, "name"):
                video_layer.name = "video"
        except (OSError, AttributeError, ValueError) as e:
            print(f"Error loading video: {e}")

    def _update_plot(self):
        """Update the line plot with current trial/keypoint/variable selection."""
        if not self.app_state.ready:
            return

        try:
            print("1")
            self.LinePlot.updateLinePlot(
                self.app_state.ds,
                self.app_state.current_trial,
                self.app_state.current_keypoint,
                self.app_state.current_variable,
                self.app_state.current_color_variable,
            )

            print("2")
            time_data = self.app_state.ds.sel(
                trial=self.app_state.current_trial,
                keypoints=self.app_state.current_keypoint,
            ).time.values
            labels = self.app_state.ds.sel(
                trial=self.app_state.current_trial,
                keypoints=self.app_state.current_keypoint,
            ).labels.values
            self.labels_widget.plot_all_motifs(time_data, labels)

        except (KeyError, AttributeError, ValueError) as e:
            print(f"Error updating plot: {e}")
