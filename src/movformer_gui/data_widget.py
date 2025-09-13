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
from .video_sync import NapariVideoSync, PyAVStreamerSync
from .audio_cache import SharedAudioCache
from movformer.utils.xr_utils import sel_valid
import napari
from movement.napari.loader_widgets import DataLoader
from pathlib import Path
from typing import Optional
from .space_plot import SpacePlot



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
        self.io_widget = io_widget  
        self.sync_manager = None  # Will be either NapariVideoSync or StreamingVideoSync
        self.lineplot = None  
        self.labels_widget = None  
        self.plots_widget = None  
        self.audio_player = None 
        self.video_path = None
        self.audio_path = None
        self.space_plot = None  

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
        
        # Store lineplot reference in app_state for video sync access
        self.app_state.lineplot_widget = lineplot

    def get_video_slider_widget(self):
        """Get the video slider widget if using PyAV stream mode."""
        if (self.sync_manager and 
            hasattr(self.sync_manager, 'get_slider_widget') and
            getattr(self.app_state, 'sync_state', '') == 'pyav_stream_mode'):
            return self.sync_manager.get_slider_widget()
        return None
    
    def _add_video_slider_to_viewer(self):
        """Add video slider widget to napari's dimension control area."""
        if (self.sync_manager and 
            hasattr(self.sync_manager, 'get_slider_widget') and
            getattr(self.app_state, 'sync_state', '') == 'pyav_stream_mode'):
            
            slider_widget = self.sync_manager.get_slider_widget()
            if slider_widget:
                try:
                    # Remove any existing video slider
                    self._remove_video_slider_from_viewer()
                    
                    # Access napari's Qt viewer and dimension controls area
                    qt_viewer = self.viewer.window._qt_viewer
                    
                    # Get the QtDims widget (napari's dimension slider container)
                    qt_dims = qt_viewer.dims
                    
                    # Add our video slider to the same layout where napari shows dimension sliders
                    # This integrates it directly into napari's native slider area
                    dims_layout = qt_dims.layout()
                    if dims_layout:
                        # Insert at the top of the dims layout to appear above any existing sliders
                        dims_layout.insertWidget(0, slider_widget)
                        
                        # Style to match napari's dimension sliders
                        slider_widget.setMinimumHeight(22)  # Match napari's SLIDERHEIGHT
                        slider_widget.setMaximumHeight(30)
                        slider_widget.setContentsMargins(0, 0, 0, 0)
                        
                        # Store reference for cleanup
                        self._video_slider_widget = slider_widget
                        self._qt_dims_layout = dims_layout
                        
                        # Show the dims widget if it was hidden
                        qt_dims.setVisible(True)
                        qt_dims.show()
                        
                except Exception as e:
                    print(f"Error adding video slider to napari dims area: {e}")
                    # Fallback to dock widget approach
                    self._add_video_slider_as_dock(slider_widget)
    
    def _add_video_slider_as_dock(self, slider_widget):
        """Fallback method to add slider as dock widget if direct integration fails."""
        try:
            self._video_slider_dock = self.viewer.window.add_dock_widget(
                slider_widget, 
                area="bottom", 
                name="Video Controls"
            )
            slider_widget.setMinimumHeight(40)
            slider_widget.setMaximumHeight(60)
        except Exception as e:
            print(f"Error adding video slider as dock: {e}")
    
    def _remove_video_slider_from_viewer(self):
        """Remove video slider widget from napari's interface."""
        try:
            if hasattr(self, '_video_slider_widget') and hasattr(self, '_qt_dims_layout'):
                self._qt_dims_layout.removeWidget(self._video_slider_widget)
                self._video_slider_widget.setParent(None)
                delattr(self, '_video_slider_widget')
                delattr(self, '_qt_dims_layout')
            

            if hasattr(self, '_video_slider_dock'):
                self.viewer.window.remove_dock_widget(self._video_slider_dock)
                delattr(self, '_video_slider_dock')
                
        except Exception as e:
            print(f"Error removing video slider from viewer: {e}")

    def on_load_clicked(self):
        """Load the file and show line plot in napari dock."""
        
        if not self.app_state.video_folder or not self.app_state.nc_file_path:
            show_error("Please select a path ending with .nc and a folder containing video files.")
            return
        
        
        self.setVisible(False)

        # Load ds
        nc_file_path = self.io_widget.get_nc_file_path()
        
        self.app_state.dt, self.type_vars_dict = load_dataset(nc_file_path)
        trials = self.app_state.dt.trials
        self.app_state.ds = self.app_state.dt.sel(trials=trials[0])

        self.navigation_widget.trials_combo.addItems([str(int(trial)) for trial in trials])
        self.app_state.trials = trials
        
        
        

        self._create_trial_controls()
        self._restore_or_set_defaults()
        self._set_controls_enabled(True)

        
        self.navigation_widget._trial_change_consequences()


        load_btn = self.io_widget.load_button
        load_btn.setEnabled(False)
        load_btn.setText("Restart app to load new data")



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
        self.io_widget.flip_video_checkbox.stateChanged.connect(self.update_video_audio)
    

        # Add spectrogram checkbox
        self.plot_spec_checkbox = QCheckBox("Plot spectrogram")
        self.plot_spec_checkbox.setChecked(bool(getattr(self.app_state, "plot_spectrogram", False)))
        self.plot_spec_checkbox.stateChanged.connect(self._on_plot_spec_checkbox_changed)
        self.layout().addRow(self.plot_spec_checkbox)
        self.controls.append(self.plot_spec_checkbox)

        # Add space plot combo
        self.space_plot_combo = QComboBox()
        self.space_plot_combo.setObjectName("space_plot_combo")
        
        # Crow lab only
        if 'angle_rgb' in self.app_state.ds.data_vars:
            self.space_plot_combo.addItems(["Layer controls", "plot_box_topview", "plot_centroid_trajectory"])
        else:
            self.space_plot_combo.addItems(["Layer controls", "plot_centroid_trajectory"])
        
        
        self.space_plot_combo.currentTextChanged.connect(self._on_space_plot_changed)
        self.layout().addRow("On the left show:", self.space_plot_combo)
        self.controls.append(self.space_plot_combo)

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
                self.update_video_audio()
            elif key == "tracking":
                self.update_tracking()
            elif key in ["features", "colors", "individuals", "keypoints"]:
                xmin, xmax = self.lineplot.get_current_xlim()
                self.update_line_plot(t0=xmin, t1=xmax)
                if key in ["individuals", "keypoints"]:
                    self.update_space_plot()
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
            
        # Restore space plot type
        space_plot_type = getattr(self.app_state, 'space_plot_type', 'None')
        if hasattr(self, 'space_plot_combo'):
            self.space_plot_combo.setCurrentText(space_plot_type)
            
   
            

       
            


    # Currently not working, I think
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

        original_trials = self.app_state.dt.trials

        if filter_condition != "None" and filter_value != "None":
            filt_dt = self.app_state.dt.filter_by_attr(filter_condition, filter_value)
            
            
            self.app_state.trials = [trial for trial in original_trials if trial in filt_dt.trials]
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
        self.update_line_plot()

    def update_line_plot(self, **kwargs):
        """Update the line plot with current trial/keypoint/variable selection."""
        if not self.app_state.ready:
            return
        
        

        try:
            self.lineplot.update_plot(**kwargs)
            # Sync logic removed; handled by AudioVideoSync classes

            ds = self.app_state.ds
            ds_kwargs = self.app_state.get_ds_kwargs()
            time_data = ds.time.values

            labels, _ = sel_valid(self.app_state.ds.labels, ds_kwargs)

            self.labels_widget.plot_all_motifs(time_data, labels)
            

        except (KeyError, AttributeError, ValueError) as e:
            show_error(f"Error updating plot: {e}")

    def update_video_audio(self):
        """Update video and audio using appropriate sync manager based on sync_state."""
        if not self.app_state.ready or not self.app_state.video_folder:
            return

        # Store current frame to preserve position when switching sync modes
        current_frame = getattr(self.app_state, 'current_frame', 0)


        for layer in list(self.viewer.layers):
            if layer.name in ["video", "Video Stream"]:
                self.viewer.layers.remove(layer)


        if self.sync_manager:
            self.sync_manager.stop()
            self.sync_manager = None
            
        # Remove any existing video slider
        self._remove_video_slider_from_viewer()

   
        video_file = self.app_state.ds.attrs[self.app_state.cameras_sel]

        video_path = os.path.join(self.app_state.video_folder, video_file)
        self.app_state.video_path = os.path.normpath(video_path)

        # Set up audio path if available
        audio_path = None
        if self.app_state.audio_folder and hasattr(self.app_state, 'mics_sel'):
            try:
                audio_file = (
                    self.app_state.ds.attrs[self.app_state.mics_sel]
                )
                audio_path = os.path.join(self.app_state.audio_folder, audio_file)
                self.app_state.audio_path = os.path.normpath(audio_path)
            except (KeyError, AttributeError):
                self.app_state.audio_path = None


        
 
        sync_state = getattr(self.app_state, 'sync_state', 'napari_video_mode')
        
        if sync_state == 'pyav_stream_mode':
            # Use fast streaming player (StreamingVideoSync)

                    
            self.sync_manager = PyAVStreamerSync(
                viewer=self.viewer,
                app_state=self.app_state,
                video_source=self.app_state.video_path,
                audio_source=self.app_state.audio_path
            )

            self.app_state.current_frame = current_frame
            self.sync_manager.start()
            self.sync_manager.pause()
            
                
            # Add video slider to viewer window
            self._add_video_slider_to_viewer()
            
        else:
            # Use accurate napari player (NapariVideoSync) for napari_video_mode

                    
            # Load video using napari-video plugin
            self.viewer.open(self.app_state.video_path, name="video", plugin="napari_video")
            video_layer = self.viewer.layers["video"]
            video_index = self.viewer.layers.index(video_layer)
            self.viewer.layers.move(video_index, 0)  # Move to bottom layer
            
            if self.io_widget.flip_video_checkbox.isChecked():
                video_layer.scale = (1, -1, 1)  


            self.sync_manager = NapariVideoSync(
                viewer=self.viewer,
                app_state=self.app_state,
                video_source=self.app_state.video_path,
                audio_source=self.app_state.audio_path
            )
            
            self.sync_manager.seek_to_frame(current_frame)


        

        # Connect sync manager frame changes to app state and lineplot
        self.sync_manager.frame_changed.connect(self._on_sync_frame_changed)



    def update_motif_label(self):
        """Update motif label display."""
        self.labels_widget.refresh_motif_shapes_layer()



    def toggle_pause_resume(self):
        """Toggle play/pause state of the video/audio stream."""
        if not self.sync_manager:
            return
        self.sync_manager.toggle_pause_resume()
        
        
        
    def set_sync_mode(self, is_playing: bool) -> None:
        """Public method to set sync mode based on playback state."""


        if self.app_state.sync_state == "pyav_stream_mode":
            self.lineplot.set_stream_mode()
        elif self.app_state.sync_state == "napari_video_mode":
            self.lineplot.set_label_mode()
            
        
    def _on_sync_frame_changed(self, frame_number: int):
        """Handle frame changes from sync manager."""
        self.app_state.current_frame = frame_number
        self.lineplot.update_time_marker_and_window(frame_number)
        
        # Update window continously
        if self.app_state.sync_state == "pyav_stream_mode":
            xlim = self.lineplot.get_current_xlim()
            self.lineplot.set_x_range(mode='center', center_on_frame=frame_number, preserve_xlim=xlim)
            
        # Only update if out of bounds
        elif self.app_state.sync_state == "napari_video_mode":
            current_time = frame_number / self.app_state.ds.fps
            xlim = self.lineplot.get_current_xlim()
            if current_time < xlim[0] or current_time > xlim[1]:
                self.lineplot.set_x_range(mode='center', center_on_frame=frame_number)



    def update_tracking(self):
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
            self.app_state.ds.attrs[self.app_state.tracking_sel]
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

            


    def closeEvent(self, event):
        """Clean up video stream and data cache."""

        SharedAudioCache.clear_cache()

        self.sync_manager.stop()

        super().closeEvent(event)

    def _on_plot_spec_checkbox_changed(self):
        """Handle spectrogram checkbox state change."""
        self.app_state.plot_spectrogram = bool(self.plot_spec_checkbox.isChecked())

        self.update_line_plot()

    def _on_space_plot_changed(self):
        """Handle space plot combo change."""
        if not self.app_state.ready:
            return
            
        plot_type = self.space_plot_combo.currentText()
        self.app_state.space_plot_type = plot_type
        self.update_space_plot()

    def update_space_plot(self):
        """Update space plot based on current selection."""
        if not self.app_state.ready:
            return

        plot_type = self.app_state.get_with_default('space_plot_type')
        
        if plot_type == "Layer controls":
            if self.space_plot:
                self.space_plot.hide()            
        else:
            # Create space plot if it doesn't exist
            if not self.space_plot:
                self.space_plot = SpacePlot(self.viewer, self.app_state)
                if self.labels_widget:
                    self.labels_widget.highlight_spaceplot.connect(self._highlight_positions_in_space_plot)
                
            # Get current selections
            individual = self.combos.get('individuals', None)
            individual_text = individual.currentText() if individual else None
            keypoints = self.combos.get('keypoints', None)
            keypoints_text = keypoints.currentText() if keypoints else None
            color_variable = self.combos.get('colors', None)
            color_variable = color_variable.currentText() if color_variable else None
            
            # Update plot
            self.space_plot.update_plot(plot_type, individual_text, keypoints_text, color_variable)
            self.space_plot.show()
            
            

    def _highlight_positions_in_space_plot(self, start_frame: int, end_frame: int):
        """Highlight positions in space plot based on current frame."""
        if self.space_plot and self.space_plot.dock_widget.isVisible():
            self.space_plot.highlight_positions(start_frame, end_frame)

    def reset_widget_state(self):
        """Reset the data widget to its default state."""
        # Clear all combo boxes in this widget
        for combo in self.combos.values():
            combo.clear()
            combo.addItems(["None"])
            combo.setCurrentText("None")
        
        # Reset checkboxes
        if hasattr(self, 'plot_spec_checkbox'):
            self.plot_spec_checkbox.setChecked(False)
        if hasattr(self, 'clear_audio_checkbox'):
            self.clear_audio_checkbox.setChecked(False)
        
        # Reset space plot combo if it exists
        if hasattr(self, 'space_plot_combo'):
            self.space_plot_combo.clear()
            self.space_plot_combo.addItems(["Layer controls"])
            self.space_plot_combo.setCurrentText("Layer controls")
        
        # Reset trial conditions combo if it exists
        if hasattr(self, 'trial_conditions_value_combo'):
            self.trial_conditions_value_combo.clear()
            self.trial_conditions_value_combo.addItems(["None"])
            self.trial_conditions_value_combo.setCurrentText("None")
            
        # Clear navigation widget trials combo
        if self.navigation_widget and hasattr(self.navigation_widget, 'trials_combo'):
            self.navigation_widget.trials_combo.clear()
        
        # Reset various state variables
        self.type_vars_dict = {}
        self.video_path = None
        self.audio_path = None
        self.fps = None
        self.source_software = None
        self.file_path = None
        self.file_name = None
        
        # Hide space plot if it exists
        if self.space_plot:
            self.space_plot.hide()
            
        print("DataWidget state reset to default")
