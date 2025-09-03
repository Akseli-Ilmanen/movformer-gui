"""Enhanced navigation widget with proper sync mode handling."""

from qtpy.QtWidgets import (QHBoxLayout, QPushButton, QWidget, QComboBox, 
                            QSlider, QLabel, QVBoxLayout)
from qtpy.QtCore import QTimer, Qt, Signal
from typing import Optional
from napari import Viewer


class NavigationWidget(QWidget):
    """Widget for trial navigation and sync toggle between video and lineplot."""
    
    sync_mode_changed = Signal(str)
    
    def __init__(self, viewer: Viewer, app_state, parent=None, 
                 time_slider=None, time_label=None):
        super().__init__(parent=parent)
        self.viewer = viewer
        self.app_state = app_state
        self.data_widget = None
        self.time_slider = time_slider
        self.time_label = time_label
        self.lineplot = None  # Will be set after creation

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

        # Sync mode selector with clear labels
        self.sync_toggle_btn = QComboBox()
        self.sync_toggle_btn.setObjectName("sync_toggle_btn")
        self.sync_toggle_btn.addItems([
            "Sync: Video → LinePlot (Follow Video)", 
            "Sync: LinePlot → Video (Interactive Plot)"
        ])
        self.sync_toggle_btn.currentIndexChanged.connect(self.toggle_sync)

        # Layout
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

        # Initialize sync state from app_state
        sync_state = getattr(self.app_state, "sync_state", None)
        if sync_state == "lineplot_to_video":
            self.sync_toggle_btn.setCurrentIndex(1)
        elif sync_state == "video_to_lineplot":
            self.sync_toggle_btn.setCurrentIndex(0)
        else:
            # Default to video_to_lineplot
            self.sync_toggle_btn.setCurrentIndex(0)
            self.app_state.sync_state = "video_to_lineplot"

    def set_data_widget(self, data_widget):
        """Set reference to data widget."""
        self.data_widget = data_widget
    
    def set_lineplot(self, lineplot):
        """Set reference to lineplot widget."""
        self.lineplot = lineplot
        
    def _setup_time_slider(self) -> None:
        """Configure the externally provided time slider for segment selection."""
        self.time_slider.setOrientation(Qt.Horizontal)
        self.time_slider.setValue(0)
        self.time_slider.sliderReleased.connect(self.on_slider_clicked)
        self.time_label = QLabel("0 / 0")
        self._last_slider_value = 0
        self.slider_clicks_enabled = False

        self.click_debounce_timer = QTimer()
        self.click_debounce_timer.setSingleShot(True)
        # Connect both debounce and enable logic if needed in future
        self.click_debounce_timer.timeout.connect(self._jump_to_segment_after_debounce)



    def on_slider_clicked(self):
        """Handle user clicks on slider (only in lineplot_to_video mode)."""
            
        self.app_state.current_frame = self.time_slider.value()
        self.click_debounce_timer.start(500)

    def _jump_to_segment_after_debounce(self):
        """Jump to segment after debounce period."""
        if hasattr(self.app_state, 'stream'):
            current_time = self.app_state.current_frame / self.app_state.ds.fps
            self.app_state.stream.jump_to_segment(current_time)

    def update_slider(self):
        """Update slider position from app_state."""
        if self.time_slider:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(round(self.app_state.current_frame))
            self.time_slider.blockSignals(False)
            self._update_slider_display()
       
    def _update_slider_display(self):
        """Update the time label display."""
        if self.time_label and hasattr(self.app_state, 'num_frames'):
            current = self.time_slider.value()
            total = self.app_state.num_frames - 1
            self.time_label.setText(f"{current} / {total}")   
     
    def toggle_sync(self) -> None:
        """Toggle between sync modes."""
        current_index = self.sync_toggle_btn.currentIndex()
        
        if current_index == 0:
            new_mode = "video_to_lineplot"
        else:
            new_mode = "lineplot_to_video"
        
        self.app_state.sync_state = new_mode

        # Emit signal for other components
        self.sync_mode_changed.emit(new_mode)
        
        # Update lineplot mode if available
        if self.lineplot and self.app_state.ready:
            self.lineplot.set_sync_mode(new_mode)
            self.lineplot.update_plot()
        


    def _trial_change_consequences(self):
        """Handle consequences of trial changes."""
        if self.data_widget:
            self.data_widget._update_video_audio()
            self.data_widget._update_plot()

    def _on_trial_changed(self):
        """Handle trial selection change."""
        if not self.app_state.ready:
            return

        current_text = self.trials_combo.currentText()
        if not current_text or current_text.strip() == '':
            return
            
        try:
            trial_value = int(current_text)
            self.app_state.set_key_sel("trials", trial_value)
            self._trial_change_consequences()
            
            # Reset time to 0 on trial change
            if hasattr(self.app_state, 'current_time'):
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
        if not hasattr(self.app_state, 'trials') or not self.app_state.trials:
            return
            
        curr_idx = self.app_state.trials.index(self.app_state.trials_sel)
        new_idx = curr_idx + direction
        
        if 0 <= new_idx < len(self.app_state.trials):
            new_trial = self.app_state.trials[new_idx]
            self.app_state.trials_sel = new_trial

            # Update combo box without triggering signal
            self.trials_combo.blockSignals(True)
            self.trials_combo.setCurrentText(str(new_trial))
            self.trials_combo.blockSignals(False)

            self._trial_change_consequences()