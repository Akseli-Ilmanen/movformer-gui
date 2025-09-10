"""Enhanced navigation widget with proper sync mode handling."""

from napari import Viewer
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class NavigationWidget(QWidget):
    """Widget for trial navigation and sync toggle between video and lineplot."""


    def __init__(self, viewer: Viewer, app_state, parent=None):
        super().__init__(parent=parent)
        self.viewer = viewer
        self.app_state = app_state
        self.data_widget = None

        # Trial selection combo
        self.trials_combo = QComboBox()
        self.trials_combo.setObjectName("trials_combo")
        self.trials_combo.currentTextChanged.connect(self._on_trial_changed)
        trial_label = QLabel("Trial:")
        trial_label.setObjectName("trial_label")

        # Navigation buttons
        self.prev_button = QPushButton("Previous Trial")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.clicked.connect(lambda: self._update_trial(-1))

        self.next_button = QPushButton("Next Trial")
        self.next_button.setObjectName("next_button")
        self.next_button.clicked.connect(lambda: self._update_trial(1))

        # Playback FPS control
        self.fps_playback_edit = QLineEdit()
        self.fps_playback_edit.setObjectName("fps_playback_edit")
        self.fps_playback_edit.setText(str(app_state.get_with_default("fps_playback")))
        self.fps_playback_edit.editingFinished.connect(self._on_fps_changed)
        fps_label = QLabel("Playback FPS:")
        fps_label.setObjectName("fps_label")

        # Sync mode selector with clear labels
        self.sync_toggle_btn = QComboBox()
        self.sync_toggle_btn.setObjectName("sync_toggle_btn")
        self.sync_toggle_btn.addItems(
            [
                "Napari Video Mode (Interactive + Follow on Play)",
                "PyAV Video/Audio Stream Mode (Follow Video)",
            ]
        )
        self.sync_toggle_btn.currentIndexChanged.connect(self.toggle_sync)


        # Layout
        row1 = QHBoxLayout()
        row1.addWidget(trial_label)
        row1.addWidget(self.trials_combo)

        row2 = QHBoxLayout()
        row2.addWidget(self.prev_button)
        row2.addWidget(self.next_button)

        row3 = QHBoxLayout()
        row3.addWidget(fps_label)
        row3.addWidget(self.fps_playback_edit)

        row4 = QHBoxLayout()
        row4.addWidget(self.sync_toggle_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addLayout(row3)
        main_layout.addLayout(row4)
        self.setLayout(main_layout)

        # Initialize sync state from app_state
        sync_state = getattr(self.app_state, "sync_state", None)
        if sync_state == "napari_video_mode":
            self.sync_toggle_btn.setCurrentIndex(0)
        elif sync_state == "pyav_stream_mode":
            self.sync_toggle_btn.setCurrentIndex(1)
        else:
            # Default to napari_video_mode
            self.sync_toggle_btn.setCurrentIndex(0)
            self.app_state.sync_state = "napari_video_mode"

    def set_data_widget(self, data_widget):
        """Set reference to data widget."""
        self.data_widget = data_widget



    def toggle_sync(self) -> None:
        """Toggle between sync modes."""
        current_index = self.sync_toggle_btn.currentIndex()

        if current_index == 0:
            new_mode = "napari_video_mode"
        elif current_index == 1:
            new_mode = "pyav_stream_mode"

        # Update app state
        self.app_state.sync_state = new_mode
        
        # Trigger video player switching by updating video/audio
        if self.data_widget and self.app_state.ready:
            self.data_widget.update_video_audio()




    def _trial_change_consequences(self):
        """Handle consequences of trial changes."""
        if self.data_widget:
            self.data_widget.update_tracking()
            self.data_widget.update_video_audio()
            self.data_widget.update_motif_label()
            self.data_widget.update_plot()

    def _on_trial_changed(self):
        """Handle trial selection change."""
        if not self.app_state.ready:
            return

        current_text = self.trials_combo.currentText()
        if not current_text or current_text.strip() == "":
            return

        try:
            trial_value = int(current_text)
            self.app_state.set_key_sel("trials", trial_value)
            self._trial_change_consequences()

            # Reset time to 0 on trial change
            if hasattr(self.app_state, "current_time"):
                self._update_slider_display()
        except ValueError:
            return

    def next_trial(self):
        """Go to the next trial."""
        self._update_trial(1)

    def prev_trial(self):
        """Go to the previous trial."""
        self._update_trial(-1)

    def _update_trial(self, direction: int):
        """Navigate to next/previous trial."""
        if not hasattr(self.app_state, "trials") or not self.app_state.trials:
            return

        curr_idx = self.app_state.trials.index(self.app_state.trials_sel)
        new_idx = curr_idx + direction

        if 0 <= new_idx < len(self.app_state.trials):
            new_trial = self.app_state.trials[new_idx]
            self.app_state.trials_sel = int(new_trial)

            # Update combo box without triggering signal
            self.trials_combo.blockSignals(True)
            self.trials_combo.setCurrentText(str(new_trial))
            self.trials_combo.blockSignals(False)

            self._trial_change_consequences()

    def _on_fps_changed(self):
        """Handle playback FPS change from UI."""
        fps_playback = float(self.fps_playback_edit.text())
        self.app_state.fps_playback = fps_playback

        # Update the playback settings in the viewer if using napari mode
        qt_dims = self.viewer.window.qt_viewer.dims
        if qt_dims.slider_widgets:
            slider_widget = qt_dims.slider_widgets[0]
            slider_widget._update_play_settings(fps=fps_playback, loop_mode="once", frame_range=None)

