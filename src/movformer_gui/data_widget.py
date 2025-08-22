"""Widget for selecting start/stop times and playing a segment in napari."""
import os
import numpy as np
from napari.utils.events import Event
from napari.utils.notifications import show_error
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
    QSizePolicy,
    QApplication,
    QShortcut,
    QLabel,
    QCheckBox,
    QMessageBox,
)
from qtpy.QtGui import QKeySequence
from qtpy.QtCore import Qt


from movformer_gui.data_loader import (
    VIDEO_EXTENSIONS,
    load_dataset,
    validate_media_folder,
)
from movformer_gui.audio_player import AudioPlayer


class DataWidget(QWidget):
    """Widget to control which data is loaded, displayed and stored for next time."""

    def __init__(
        self,
        napari_viewer: Viewer,
        app_state,
        meta_widget,
        parent=None,
    ):
        super().__init__(parent=parent)
        self.parent = parent
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())
        self.app_state = app_state
        self.meta_widget = meta_widget
        self.lineplot = None  # Will be set after creation
        self.labels_widget = None  # Will be set after creation
        self.plots_widget = None  # Will be set after creation
        self.audio_player = None  # Audio player widget

        # Dictionary to store all combo boxes
        self.combos = {}
        # Dictionary to store all controls for enabling/disabling
        self.controls = []


    

        # E.g. {keypoints = ["beakTip, StickTip"], trials=[1, 2, 3, 4], ...}
        self.type_vars_dict = {} # Gets filled by load_dataset

        self._create_path_folder_widgets()
        self._create_load_button()


        # Restore UI text fields from app state
        if self.app_state.file_path:
            self.file_path_edit.setText(self.app_state.file_path)
        if self.app_state.video_folder:
            self.video_folder_edit.setText(self.app_state.video_folder)
        if self.app_state.audio_folder:
            self.audio_folder_edit.setText(self.app_state.audio_folder)




        




    def set_references(self, lineplot, labels_widget, plots_widget):
        """Set references to other widgets after creation."""
        self.lineplot = lineplot
        self.labels_widget = labels_widget
        self.plots_widget = plots_widget
        
        # Connect to app state signals for buffer changes
        self._connect_app_state_signals()

    def _connect_app_state_signals(self):
        """Connect to app state signals that should trigger spectrogram buffer clearing."""
        if hasattr(self.app_state, 'spec_buffer_changed'):
            self.app_state.spec_buffer_changed.connect(self._on_spec_buffer_changed)
        if hasattr(self.app_state, 'audio_buffer_changed'):
            self.app_state.audio_buffer_changed.connect(self._on_audio_buffer_changed)

    def _on_spec_buffer_changed(self, value):
        """Handle spectrogram buffer size change."""
        # Clear spectrogram buffer when buffer size changes
        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()

    def _on_audio_buffer_changed(self, value):
        """Handle audio buffer size change."""
        # Clear spectrogram buffer when audio buffer changes (affects audio loading)
        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()


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

    def _create_path_folder_widgets(self):
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
            browse_callback=lambda: self.on_browse_clicked("audio_file"), # folder, audio
        )



    def _create_load_button(self):
        """Create a button to load the file to the viewer."""
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("load_button")
        self.load_button.clicked.connect(lambda: self.on_load_clicked())
        self.layout().addRow(self.load_button)
        

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
                caption += "audio files"
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

        elif browse_type == "audio_file":
            result = QFileDialog.getOpenFileName(
                None,
                caption="Open audio file",
            )
            audio_file_path = result[0] if result and len(result) >= 1 else ""
            if not audio_file_path:
                return
            self.audio_folder_edit.setText(audio_file_path)
            self.app_state.audio_folder = audio_file_path

    def on_load_clicked(self):
        """Load the file and show line plot in napari dock."""
        



        # Load ds
        file_path = self.file_path_edit.text()        
        self.app_state.ds, self.type_vars_dict = load_dataset(file_path)
        self.trials = list(self.app_state.ds.trials.values)



        self._create_trial_controls()
        
        # Load audio only if a path is provided
        if self.audio_player is not None:
            audio_path = self.audio_folder_edit.text()
            if audio_path:
                self.audio_player.load_audio_file(audio_path)
                # Clear spectrogram buffer when new audio is loaded
                if hasattr(self, 'lineplot') and self.lineplot is not None:
                    self.lineplot.clear_spectrogram_buffer()

        self._restore_or_set_defaults()



        self._set_controls_enabled(True)


        self._update_plot()
        self._update_video()



        load_btn = self.findChild(QPushButton, "load_button")
        load_btn.setEnabled(False)
        load_btn.setText("Restart app to load new data")


        self._remove_ugly()


    def _remove_ugly(self):
        """Function to execute after on_load_clicked has been called."""
        # Simulate user expand/collapse so widget state and UI update as if user did it
        self.meta_widget.collapsible_widgets[0].collapse()
        QApplication.processEvents()
        self.meta_widget.collapsible_widgets[0].expand()
        QApplication.processEvents()

  

    def _create_trial_controls(self):
        """Create all trial-related controls based on info configuration."""
        
        # Create widgets in the desired order: cameras, fps_playback, mics, audio player, then gap
        
        # 1. Cameras first
        if "cameras" in self.type_vars_dict.keys():
            self._create_combo_widget("cameras", self.type_vars_dict["cameras"])
        else:
            combo = QComboBox()
            combo.setObjectName("cameras_combo")
            combo.currentTextChanged.connect(self._on_combo_changed)
            combo.addItems(["None"])
            self.layout().addRow("Cameras:", combo)
        
        # 2. Playback FPS second
        self.fps_playback_edit = QLineEdit()
        self.fps_playback_edit.setObjectName("fps_playback_edit")
        self.fps_playback_edit.setText("30")
        self.fps_playback_edit.editingFinished.connect(self._on_fps_changed)
        self.layout().addRow("Playback FPS:", self.fps_playback_edit)
        self.controls.append(self.fps_playback_edit)
        
        # 3. Mics third
        if "mics" in self.type_vars_dict.keys():
            self._create_combo_widget("mics", self.type_vars_dict["mics"])
        
            # 4. Audio player fourth (Optional)
            self.audio_player = AudioPlayer(self.viewer, app_state=self.app_state)
            self.layout().addRow("Audio Player:", self.audio_player)
            self._connect_video_audio()

        else:
            combo = QComboBox()
            combo.setObjectName("mics_combo")
            combo.currentTextChanged.connect(self._on_combo_changed)
            combo.addItems(["None"])
            self.layout().addRow("Mics:", combo)

            self.audio_player = None
        

        # DELETE IN THE FUTURE; WHEN YOU CAN AUDIO PASSED VIA MICS
        self.audio_player = AudioPlayer(self.viewer, app_state=self.app_state)
        self.layout().addRow("Audio Player:", self.audio_player)
        self._connect_video_audio()

        # Add spectrogram checkbox
        self.plot_spec_checkbox = QCheckBox("Plot spectrogram")
        self.plot_spec_checkbox.setChecked(bool(getattr(self.app_state, "plot_spectrogram", False)))
        self.plot_spec_checkbox.stateChanged.connect(self._on_plot_spectrogram_changed)
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

        
        self.trials_combo = QComboBox()
        self.trials_combo.setObjectName("trials_combo")
        self.trials_combo.currentTextChanged.connect(self._on_trial_changed)
        self.trials_combo.addItems(str(int(trial)) for trial in self.trials)
        self.layout().addRow("Trials:", self.trials_combo)
        self.controls.append(self.trials_combo)

        # Previous/Next trial buttons
        self.prev_button = QPushButton("Previous Trial")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.clicked.connect(lambda: self._update_trial(-1))
        self.controls.append(self.prev_button)

        self.next_button = QPushButton("Next Trial")
        self.next_button.setObjectName("next_button")
        self.next_button.clicked.connect(lambda: self._update_trial(1))
        self.controls.append(self.next_button)

        # Layout for navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        self.layout().addRow("Navigation:", nav_layout)

        # Initially disable trial controls until data is loaded
        self._set_controls_enabled(False)
        


    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all trial-related controls."""
        for control in self.controls:
            control.setEnabled(enabled)
        self.app_state.ready = enabled


    def _create_combo_widget(self, key, vars):
        """Create a combo box widget for a given info key."""
        
        combo = QComboBox()
        combo.setObjectName(f"{key}_combo")
        combo.currentTextChanged.connect(self._on_combo_changed)
        if key in ['colors', 'trial_conditions']:
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

        # Figure out which key this belongs to. E.g. if value 
        combo = self.sender()
        for key, value in self.combos.items():
            if value is combo:
                break
        
        self.app_state.set_key_sel(key, combo.currentText())


        if key in ["cameras", "mics"]:
            self._update_video() 
        elif key in ["features", "colors", "individuals", "keypoints"]:
            self._update_plot()
        elif key == "trial_conditions":
            self._update_trial_condition_values()
    
        


    def _on_trial_changed(self):
        if not self.app_state.ready:
            return

        current_text = self.trials_combo.currentText()
        if not current_text or current_text.strip() == '':
            return  # Skip if no valid selection
        
        try:
            trial_value = int(current_text)
            self.app_state.set_key_sel("trials", trial_value)
            self._update_plot()
            self._update_video()


            # Clear spectrogram buffer when switching trials
            if hasattr(self, 'lineplot') and self.lineplot is not None:
                self.lineplot.clear_spectrogram_buffer()

        except ValueError:
            # Handle invalid integer conversion gracefully
            return
        

    def _restore_or_set_defaults(self):
        """Restore saved selections from app_state or set defaults from available options."""
        

        for key, vars in self.type_vars_dict.items():
            combo = self.combos.get(key)

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


        if self.app_state.key_sel_exists("trials"):
            self.trials_combo.setCurrentText(str(self.app_state.get_key_sel("trials")))
            self.app_state.trials_sel = int(self.app_state.get_key_sel("trials"))
        else:
            # Default to first value
            self.trials_combo.setCurrentText(str(self.trials[0]))
            self.app_state.trials_sel =  int(self.trials[0])

  
    def _on_fps_changed(self):
        """Handle playback FPS change from UI."""
        fps = float(self.fps_playback_edit.text())
        self.app_state.fps_playback = fps
 

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

            self.trial_conditions_value_combo.addItems(
              ["None"] + [str(int(val)) for val in np.sort(unique_values)]
            )

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

            self.trials = [trial for trial in original_trials if trial in filtered_trials]
        else:
            # Reset to all trials
            self.trials = original_trials

        # Update trials dropdown
        self.trials_combo.clear()
        self.trials_combo.addItems([str(int(trial)) for trial in self.trials])

        # Update current trial if needed
        if self.app_state.trials_sel not in self.trials:
            if self.trials:
                self.app_state.trials_sel = int(self.trials[0])
                self.trials_combo.setCurrentText(str(self.app_state.trials_sel))


        self.trials_combo.blockSignals(False)
        self._update_plot()


    # Navigation methods
    def next_trial(self):
        """Go to the next trial. Can be called by shortcut."""
        self._update_trial(1)

    def prev_trial(self):
        """Go to the previous trial."""
        self._update_trial(-1)


    def _update_trial(self, direction: int):
        """Navigate to next/previous trial."""

        curr_idx = self.trials.index(self.app_state.trials_sel) 
        new_trial = self.trials[curr_idx + direction] 
 
        if 0 <= new_trial <= max(self.trials):
            self.app_state.trials_sel = new_trial

            # Update the combo box text without triggering the signal
            self.trials_combo.blockSignals(True)
            self.trials_combo.setCurrentText(str(new_trial))
            self.trials_combo.blockSignals(False)

            # Clear spectrogram buffer when switching trials
            if hasattr(self, 'lineplot') and self.lineplot is not None:
                self.lineplot.clear_spectrogram_buffer()

            self._update_video()
            self._update_plot()  




    def _update_video(self):
        """Update video display based on current selections."""
        if not self.app_state.ready:
            return

        try:
            file_name = (
                self.app_state.ds[self.app_state.cameras_sel]
                .sel(trials=self.app_state.trials_sel)
                .values.item()
            )
            video_path = os.path.join(self.app_state.video_folder, file_name)

            # Remove all previous layers
            for layer in self.viewer.layers:
                self.viewer.layers.remove(layer)

            # Open new video
            self.viewer.open(video_path)



        except (OSError, AttributeError, ValueError) as e:
            show_error(f"Error loading video: {e}")

    def _update_plot(self):
        """Update the line plot with current trial/keypoint/variable selection."""
        if not self.app_state.ready:
            return

        try:
            # Give line plot access to audio player
            if hasattr(self, "audio_player") and self.audio_player is not None:
                setattr(self.lineplot, "audio_player", self.audio_player)

            self.lineplot.updateLinePlot()

            ds = self.app_state.ds
            ds_kwargs = self.app_state.get_ds_kwargs()
            time_data = ds.time.values
            labels = ds.sel(**ds_kwargs).labels.values
            self.labels_widget.plot_all_motifs(time_data, labels)

        except (KeyError, AttributeError, ValueError) as e:
            show_error(f"Error updating plot: {e}")

    def _on_plot_spectrogram_changed(self, _state=None):
        """Handle spectrogram checkbox state change."""
        self.app_state.plot_spectrogram = bool(self.plot_spec_checkbox.isChecked())
        
        # Clear spectrogram buffer when switching plot modes
        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()
            
        self._update_plot()


    def _connect_video_audio(self):
        # Connect video to audio            
        if self.audio_player is not None:
            qt_dims = self.viewer.window._qt_viewer.dims
            qt_dims._animation_thread.started.connect(self._on_napari_play_started)
            qt_dims._animation_thread.finished.connect(self._on_napari_play_stopped)


    def _on_napari_play_started(self):
        if self.audio_player:
            self.audio_player._start_playback()


    def _on_napari_play_stopped(self):
        if self.audio_player:
            self.audio_player._stop_playback()



      
