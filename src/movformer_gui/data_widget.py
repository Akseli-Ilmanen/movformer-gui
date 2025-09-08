"""Widget for selecting start/stop times and playing a segment in napari."""

import os
from pathlib import Path

import numpy as np
from movement.napari.loader_widgets import DataLoader
from napari.utils.notifications import show_error
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


from .audio_cache import SharedAudioCache
from .data_loader import load_dataset
from .video_sync import NapariVideoSync, StreamingVideoSync
from .audio_cache import SharedAudioCache
from movformer.utils.xr_utils import sel_valid
import napari
from movement.napari.loader_widgets import DataLoader
from pathlib import Path
from typing import Optional

class DataWidget(DataLoader, QWidget):
    """Widget to control which data is loaded, displayed and stored for next time."""

    def __init__(
        self,
        napari_viewer: Viewer,
        app_state,
        meta_widget,
        io_widget,
        parent=None,
    ):
        DataLoader.__init__(self, napari_viewer)  # Pass required args for DataLoader
        QWidget.__init__(self, parent=parent)
        self.parent = parent
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())
        self.app_state = app_state
        self.meta_widget = meta_widget
        self.io_widget = io_widget  # Reference to I/O widget
        self.sync_manager = None  # Will be either NapariVideoSync or StreamingVideoSync
        self.lineplot = None  # Will be set after creation
        self.labels_widget = None  # Will be set after creation
        self.plots_widget = None  # Will be set after creation
        self.audio_player = None  # Audio player widget
        self.video_path = None
        self.audio_path = None

        # Dictionary to store all combo boxes
        self.combos = {}
        # Dictionary to store all controls for enabling/disabling
        self.controls = []

        # Tracking stuff
        self.fps = None
        self.source_software = None
        self.file_path = None
        self.file_name = None

        self.app_state.audio_video_sync = None
        # E.g. {keypoints = ["beakTip, StickTip"], trials=[1, 2, 3, 4], ...}
        self.type_vars_dict = {}  # Gets filled by load_dataset

    def set_references(self, lineplot, labels_widget, plots_widget, navigation_widget):
        """Set references to other widgets after creation."""
        self.lineplot = lineplot
        self.labels_widget = labels_widget
        self.plots_widget = plots_widget
        self.navigation_widget = navigation_widget



    def on_load_clicked(self):
        """Load the file and show line plot in napari dock."""
        self.setVisible(False)

        # Load ds
        nc_file_path = self.io_widget.get_nc_file_path()
        self.app_state.ds, self.type_vars_dict = load_dataset(nc_file_path)
        self.app_state.trials = list(self.app_state.ds.trials.values)
        self.navigation_widget.trials_combo.addItems([str(int(trial)) for trial in self.app_state.trials])

        self._create_trial_controls()

        self._restore_or_set_defaults()

        self._set_controls_enabled(True)

        self._update_plot()
        self._update_video_audio()
        self._update_tracking()

        load_btn = self.io_widget.load_button
        load_btn.setEnabled(False)
        load_btn.setText("Restart app to load new data")

        self.app_state.current_frame = 0

        self.setVisible(True)
        self._remove_ugly()

    def _remove_ugly(self):
        """Function to execute after on_load_clicked has been called."""
        # Simulate user expand/collapse so widget state and UI update as if user did it
        self.meta_widget.collapsible_widgets[1].collapse()
        QApplication.processEvents()
        self.meta_widget.collapsible_widgets[1].expand()
        QApplication.processEvents()

    def _create_trial_controls(self):
        """Create all trial-related controls based on info configuration."""

        # Create device combos in IOWidget
        self.io_widget.create_device_controls(self.type_vars_dict)

        # Add spectrogram checkbox
        self.plot_spec_checkbox = QCheckBox("Plot spectrogram")
        self.plot_spec_checkbox.setChecked(bool(getattr(self.app_state, "plot_spectrogram", False)))
        self.plot_spec_checkbox.stateChanged.connect(self._on_plot_spec_checkbox_changed)
        self.layout().addRow(self.plot_spec_checkbox)
        self.controls.append(self.plot_spec_checkbox)

        # 5. Add gap (empty row) for separation
        gap_label = QLabel("")
        gap_label.setFixedHeight(10)  # Create visual gap
        self.layout().addRow(gap_label)

        # 6. Now add remaining controls
        remaining_type_vars = ["individuals", "keypoints", "features", "colors", "trial_conditions"]
        for type_var in remaining_type_vars:
            if type_var in self.type_vars_dict.keys():
                self._create_combo_widget(type_var, self.type_vars_dict[type_var])
            else:
                combo = QComboBox()
                combo.setObjectName(f"{type_var}_combo")
                combo.currentTextChanged.connect(self._on_combo_changed)
                combo.addItems(["None"])
                self.layout().addRow(f"{type_var.capitalize()}:", combo)

        # Initially disable trial controls until data is loaded
        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all trial-related controls."""
        for control in self.controls:
            control.setEnabled(enabled)
        # Also enable/disable IOWidget device controls
        self.io_widget.set_controls_enabled(enabled)
        self.app_state.ready = enabled

    def _create_combo_widget(self, key, vars):
        """Create a combo box widget for a given info key."""

        combo = QComboBox()
        combo.setObjectName(f"{key}_combo")
        combo.currentTextChanged.connect(self._on_combo_changed)
        if key in ["colors", "trial_conditions"]:
            colour_variables = ["None"] + [str(var) for var in vars]
            combo.addItems(colour_variables)
        else:
            combo.addItems([str(var) for var in vars])

        self.layout().addRow(f"{key.capitalize()}:", combo)

        self.combos[key] = combo
        self.controls.append(combo)

        if key == "trial_conditions":
            self.trial_conditions_value_combo = QComboBox()
            self.trial_conditions_value_combo.setObjectName("trial_condition_value_combo")
            self.trial_conditions_value_combo.addItem("None")
            self.trial_conditions_value_combo.currentTextChanged.connect(self._on_trial_condition_values_changed)
            self.layout().addRow("Filter by condition:", self.trial_conditions_value_combo)
            self.controls.append(self.trial_conditions_value_combo)
        return combo

    def _on_combo_changed(self):
        if not self.app_state.ready:
            return

        # Figure out which key this belongs to
        combo = self.sender()
        key = None
        
        # Check IOWidget combos first
        for io_key, io_value in self.io_widget.combos.items():
            if io_value is combo:
                key = io_key
                break
        
        # Check DataWidget combos if not found in IOWidget
        if key is None:
            for data_key, data_value in self.combos.items():
                if data_value is combo:
                    key = data_key
                    break

        if key:
            self.app_state.set_key_sel(key, combo.currentText())

            if key in ["cameras", "mics"]:
                self._update_video_audio()
            elif key == "tracking":
                self._update_tracking()
            elif key in ["features", "colors", "individuals", "keypoints"]:
                self._update_plot()
            elif key == "trial_conditions":
                self._update_trial_condition_values()

    def _restore_or_set_defaults(self):
        """Restore saved selections from app_state or set defaults from available options."""

        for key, vars in self.type_vars_dict.items():
            # Check IOWidget combos first, then DataWidget combos
            combo = self.io_widget.combos.get(key) or self.combos.get(key)

            if combo is not None:
            
                if self.app_state.key_sel_exists(key):
                    combo.setCurrentText(str(self.app_state.get_key_sel(key)))
                    
                elif key == "trial_conditions":
                    # Always default to None
                    combo.setCurrentText("None")
                    self.app_state.set_key_sel(key, "None")
                else:
                    # Default to first value
                    combo.setCurrentText(str(vars[0]))
                    self.app_state.set_key_sel(key, str(vars[0]))
                    
                if key == "individuals":
                   individual = self.app_state.get_key_sel("individuals")

                   if self.all_data_vars_nan(individual):
                       first_individual_with_data = self.find_first_individual_with_data()
                       combo.setCurrentText(first_individual_with_data)
                       self.app_state.set_key_sel(key, first_individual_with_data)
                       


        if self.app_state.key_sel_exists("trials"):
            self.navigation_widget.trials_combo.setCurrentText(str(self.app_state.get_key_sel("trials")))
            self.app_state.trials_sel = int(self.app_state.get_key_sel("trials"))
        else:
            # Default to first value
            self.navigation_widget.trials_combo.setCurrentText(str(self.app_state.trials[0]))
            self.app_state.trials_sel = int(self.app_state.trials[0])



    def all_data_vars_nan(self, individual) -> bool:
        """
        Check if all data variables in the selected subset are entirely NaN.
        """
        ds = self.app_state.ds
        subset = ds.sel(individuals=individual).filter_by_attrs(type="features")
        return all(subset[var].isnull().all() for var in subset.data_vars)


    def find_first_individual_with_data(self) -> str | None:
        """
        Find the first individual that has non-NaN data in any data variable.
        """
        ds = self.app_state.ds
        
        for individual in ds.individuals.values:
            individual = str(individual)
            if not self.all_data_vars_nan(individual):
                return individual
    



    def _update_trial_condition_values(self):
        """Update the trial condition value dropdown based on selected key."""
        filter_condition = self.app_state.trial_conditions_sel

        if filter_condition == "None":
            self.trial_conditions_value_combo.setCurrentText("None")
            return

        self.trial_conditions_value_combo.blockSignals(True)
        self.trial_conditions_value_combo.clear()

        if filter_condition in self.app_state.ds.coords:
            # Get unique values for the selected condition key
            unique_values = np.unique(self.app_state.ds.coords[filter_condition].values)

            self.trial_conditions_value_combo.addItems(["None"] + [str(int(val)) for val in np.sort(unique_values)])

        self.trial_conditions_value_combo.blockSignals(False)

    def _on_trial_condition_values_changed(self):
        """Update the available trials based on condition filtering."""
        filter_condition = self.app_state.trial_conditions_sel
        filter_value = self.trial_conditions_value_combo.currentText()

        original_trials = self.app_state.ds.trials.values

        if filter_condition != "None" and filter_value != "None":
            # Filter trials based on condition
            ds = self.app_state.ds.copy(deep=True)
            filtered_trials = ds.trials.where(ds[filter_condition] == int(filter_value), drop=True).values

            self.app_state.trials = [trial for trial in original_trials if trial in filtered_trials]
        else:
            # Reset to all trials
            self.app_state.trials = original_trials

        # Update trials dropdown
        self.navigation_widget.trials_combo.clear()
        self.navigation_widget.trials_combo.addItems([str(int(trial)) for trial in self.app_state.trials])

        # Update current trial if needed
        if self.app_state.trials_sel not in self.app_state.trials:
            if self.app_state.trials:
                self.app_state.trials_sel = int(self.app_state.trials[0])
                self.navigation_widget.trials_combo.setCurrentText(str(self.app_state.trials_sel))

        self.navigation_widget.trials_combo.blockSignals(False)
        self._update_plot()

    def _update_plot(self):
        """Update the line plot with current trial/keypoint/variable selection."""
        if not self.app_state.ready:
            return

        try:
            self.lineplot.update_plot()
            # Sync logic removed; handled by AudioVideoSync classes

            ds = self.app_state.ds
            ds_kwargs = self.app_state.get_ds_kwargs()
            time_data = ds.time.values

            labels, _ = sel_valid(self.app_state.ds.labels, ds_kwargs)

            self.labels_widget.plot_all_motifs(time_data, labels)

        except (KeyError, AttributeError, ValueError) as e:
            show_error(f"Error updating plot: {e}")

    def _update_video_audio(self):
        """Update video and audio using appropriate sync manager based on sync_state."""
        if not self.app_state.ready or not self.app_state.video_folder:
            return

        # Remove all previous video layers
        for layer in list(self.viewer.layers):
            if layer.name == "video":
                self.viewer.layers.remove(layer)

        # Stop existing sync manager
        if self.sync_manager:
            self.sync_manager.stop()
            self.sync_manager = None

        # Get video file path from dataset
        video_file = self.app_state.ds[self.app_state.cameras_sel].sel(trials=self.app_state.trials_sel).values.item()

        video_path = os.path.join(self.app_state.video_folder, video_file)
        self.app_state.video_path = os.path.normpath(video_path)

        # Set up audio path if available
        audio_path = None
        if self.app_state.audio_folder and hasattr(self.app_state, 'mics_sel'):
            try:
                audio_file = (
                    self.app_state.ds[self.app_state.mics_sel].sel(trials=self.app_state.trials_sel).values.item()
                )
                audio_path = os.path.join(self.app_state.audio_folder, audio_file)
                self.app_state.audio_path = os.path.normpath(audio_path)
            except (KeyError, AttributeError):
                self.app_state.audio_path = None

        # Store current frame to preserve position when switching sync modes
        current_frame = getattr(self.app_state, 'current_frame', 0)
        
        # Choose video player based on sync_state
        sync_state = getattr(self.app_state, 'sync_state', 'video_to_lineplot')
        
        if sync_state == 'pyav_to_lineplot':
            # Use fast streaming player (StreamingVideoSync)
            # Remove any existing video layers since streaming player creates its own
            for layer in list(self.viewer.layers):
                if layer.name in ["video", "Video Stream"]:
                    self.viewer.layers.remove(layer)
                    
            self.sync_manager = StreamingVideoSync(
                viewer=self.viewer,
                app_state=self.app_state,
                video_source=self.app_state.video_path,
                audio_source=self.app_state.audio_path
            )
            # Start streaming for pyav player
            self.sync_manager.start()
            self.sync_manager.pause()
            
            # Seek to current frame to preserve position
            if current_frame > 0:
                self.sync_manager.seek_to_frame(current_frame)
            
        else:
            # Use accurate napari player (NapariVideoSync) for video_to_lineplot and lineplot_to_video
            # Remove any existing video layers
            for layer in list(self.viewer.layers):
                if layer.name in ["video", "Video Stream"]:
                    self.viewer.layers.remove(layer)
                    
            # Load video using napari-video plugin
            self.viewer.open(self.app_state.video_path, name="video", plugin="napari_video")
            video_layer = self.viewer.layers["video"]
            video_index = self.viewer.layers.index(video_layer)
            self.viewer.layers.move(video_index, 0)  # Move to bottom layer
            
            self.sync_manager = NapariVideoSync(
                viewer=self.viewer,
                app_state=self.app_state,
                video_source=self.app_state.video_path,
                audio_source=self.app_state.audio_path
            )
            
            # Seek to current frame to preserve position
            if current_frame > 0:
                self.sync_manager.seek_to_frame(current_frame)

        # Connect sync manager frame changes to app state and lineplot
        self.sync_manager.frame_changed.connect(self._on_sync_frame_changed)
        
        # Store reference in app_state for compatibility with other widgets
        self.app_state.sync_manager = self.sync_manager

    def _on_sync_frame_changed(self, frame_number: int):
        """Handle frame changes from sync manager."""
        self.app_state.current_frame = frame_number
        current_time = frame_number / self.app_state.ds.fps
        self.lineplot.time_marker.setValue(current_time)
        self.lineplot._update_window_position()



    def _update_tracking(self):
        if not self.app_state.tracking_folder:
            return

        # Remove all previous layers with name "video"
        for layer in list(self.viewer.layers):
            if self.file_name and layer.name in [
                f"tracks: {self.file_name}",
                f"points: {self.file_name}",
                f"boxes: {self.file_name}",
            ]:
                self.viewer.layers.remove(layer)

        self.fps = self.app_state.ds.fps
        self.source_software = self.app_state.ds.source_software

        tracking_file = (
            self.app_state.ds[self.app_state.tracking_sel].sel(trials=self.app_state.trials_sel).values.item()
        )

        self.file_path = os.path.join(self.app_state.tracking_folder, tracking_file)
        self.file_name = Path(self.file_path).name

        self._format_data_for_layers()
        self._set_common_color_property()
        self._set_text_property()
        self._add_points_layer()
        self._add_tracks_layer()
        if self.data_bboxes is not None:
            self._add_boxes_layer()
        self._set_initial_state()

    def toggle_play_pause(self):
        """Toggle play/pause state of the video/audio stream."""
        if not self.sync_manager:
            return
        self.sync_manager.toggle_play_pause()


    def closeEvent(self, event):
        """Clean up video stream and data cache."""

        SharedAudioCache.clear_cache()

        if hasattr(self.app_state, "sync_manager") and self.app_state.sync_manager:
            self.app_state.sync_manager.stop()

        super().closeEvent(event)

    def _on_plot_spec_checkbox_changed(self):
        """Handle spectrogram checkbox state change."""
        self.app_state.plot_spectrogram = bool(self.plot_spec_checkbox.isChecked())

        self._update_plot()
