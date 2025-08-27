"""Widget for trial navigation and sync toggle between video and lineplot."""

from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget, QComboBox, QSlider, QLabel, QVBoxLayout
from typing import Optional
from napari import Viewer
from qtpy.QtCore import QTimer
from qtpy.QtCore import Qt


class NavigationWidget(QWidget):

    def __init__(self, viewer: Viewer, app_state, parent=None, time_slider=None, time_label=None):
        super().__init__(parent=parent)
        self.viewer = viewer
        self.app_state = app_state
        self.data_widget = None
        self.time_slider = time_slider
        self.time_label = time_label



        self.trials_combo = QComboBox()
        self.trials_combo.setObjectName("trials_combo")
        self.trials_combo.currentTextChanged.connect(self._on_trial_changed)
        trial_label = QLabel("Trial:")
        trial_label.setObjectName("trial_label")



        self.prev_button = QPushButton("Previous Trial")
        self.prev_button.setObjectName("prev_button")
        self.prev_button.clicked.connect(lambda: self._update_trial(-1))

        self.next_button = QPushButton("Next Trial")
        self.next_button.setObjectName("next_button")
        self.next_button.clicked.connect(lambda: self._update_trial(1))

        self.sync_toggle_btn = QComboBox()
        self.sync_toggle_btn.setObjectName("sync_toggle_btn")
        self.sync_toggle_btn.addItems(["Sync: Video → LinePlot", "Sync: LinePlot → Video"])
        self.sync_toggle_btn.currentIndexChanged.connect(self.toggle_sync)

        # Use three rows for layout
        row1 = QHBoxLayout()
        row1.addWidget(trial_label)
        row1.addWidget(self.trials_combo)

        row2 = QHBoxLayout()
        row2.addWidget(self.prev_button)
        row2.addWidget(self.next_button)

        row3 = QHBoxLayout()
        row3.addWidget(self.sync_toggle_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addLayout(row3)
        self.setLayout(main_layout)

        if self.time_slider is not None:
            self._setup_time_slider()


        # Initialize sync_toggle_btn from app_state
        sync_state = getattr(self.app_state, "sync_state", None)
        if sync_state == "lineplot_to_video":
            self.sync_toggle_btn.setCurrentText("Sync: LinePlot → Video")
        elif sync_state == "video_to_lineplot":
            self.sync_toggle_btn.setCurrentText("Sync: Video → LinePlot")
        else:
            self.sync_toggle_btn.setCurrentText("Sync: Video → LinePlot")
            self.app_state.sync_state = "lineplot_to_video" # default




    def set_data_widget(self, data_widget):
        self.data_widget = data_widget
        
    def _setup_time_slider(self):
        """Configure the externally provided time slider for segment selection."""
        self.time_slider.setOrientation(Qt.Horizontal)
        self.time_slider.setValue(0)
        self.time_slider.sliderReleased.connect(self.on_slider_clicked)
        self.click_debounce_timer = QTimer()
        self.click_debounce_timer.setSingleShot(True)
        self.click_debounce_timer.timeout.connect(self.enable_slider_clicks)
        self.slider_clicks_enabled = False
        self.time_label = QLabel("0 / 0")

    def _setup_time_slider(self):
        """Configure the externally provided time slider for segment selection."""
        self.time_slider.setOrientation(Qt.Horizontal)
        self.time_slider.setValue(0)
        self.time_slider.sliderReleased.connect(self.on_slider_clicked)
        self.click_debounce_timer = QTimer()
        self.click_debounce_timer.setSingleShot(True)
        self.click_debounce_timer.timeout.connect(self._jump_to_segment_after_debounce)
        self._last_slider_value = 0
        self.slider_clicks_enabled = False # controlled in data widget
        

    # If user clicks multiple times on time slider, only the last click counts within <500ms
    def on_slider_clicked(self):
        """Called when user clicks/releases on slider"""
        self.app_state.current_frame = self.time_slider.value()
        self.app_state.current_time = self.app_state.current_frame / self.app_state.ds.fps

        self.click_debounce_timer.start(500)  # Restart timer on every click


    def _jump_to_segment_after_debounce(self):
        self.app_state.stream.jump_to_segment(self.app_state.current_time)


    def update_slider(self):
        """Update the time label to reflect the current frame.
        This function should only be called by app_state if sel1f.app_state.current_frame.
        Avoid calling directly, otherwise you may run into EventLoops"""
        self.time_slider.setValue(round(self.app_state.current_frame))
        self.time_label.setText(f"{self.app_state.current_frame} / {self.app_state.num_frames - 1}")
        
        
    def toggle_sync(self) -> None:
        current_index = self.sync_toggle_btn.currentIndex()
        if current_index == 0:
            self.app_state.sync_state = "video_to_lineplot"
        elif current_index == 1:
            self.app_state.sync_state = "lineplot_to_video"
        
        if self.app_state.ready:
            self.data_widget._update_video_audio()

            self.data_widget._update_plot()



    def _trial_change_consequences(self):
        """Handle consequences of trial changes."""

        self.data_widget._update_video_audio(new_trial=True)
        self.data_widget._update_plot(new_trial=True)

        # Clear spectrogram buffer when switching trials
        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()




    # Navigation via dropdown
    def _on_trial_changed(self):
        if not self.app_state.ready:
            return

        current_text = self.trials_combo.currentText()
        if not current_text or current_text.strip() == '':
            return 
        try:
            trial_value = int(current_text)
            self.app_state.set_key_sel("trials", trial_value)
            self._trial_change_consequences()
            # Reset current_time to 0 on trial change
            if hasattr(self.app_state, 'current_time'):
                self.app_state.current_time = 0
                if hasattr(self.data_widget, 'time_label'):
                    self.navigation_widget.time_label.setText(f"0 / {self.app_state.num_frames - 1}")
        except ValueError:
            return 

    # Navigation via shortcuts
    def next_trial(self):
        """Go to the next trial. Can be called by shortcut."""
        self._update_trial(1)

    def prev_trial(self):
        """Go to the previous trial."""
        self._update_trial(-1)


    def _update_trial(self, direction: int):
        """Navigate to next/previous trial."""

        curr_idx = self.app_state.trials.index(self.app_state.trials_sel) 
        new_trial = self.app_state.trials[curr_idx + direction] 
 
        if 0 <= new_trial <= max(self.app_state.trials):
            self.app_state.trials_sel = new_trial

            # Update the combo box text without triggering the signal
            self.trials_combo.blockSignals(True)
            self.trials_combo.setCurrentText(str(new_trial))
            self.trials_combo.blockSignals(False)

            self._trial_change_consequences()