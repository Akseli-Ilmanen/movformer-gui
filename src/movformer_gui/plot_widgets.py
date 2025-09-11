"""Enhanced plot widgets with sync mode awareness."""

from qtpy.QtWidgets import (QGridLayout, QLineEdit, QWidget, QPushButton, 
                            QVBoxLayout, QLabel, QCheckBox)
from napari.viewer import Viewer
from typing import Optional


class PlotsWidget(QWidget):
    """Plot controls with sync mode awareness.
    
    Keys used in gui_settings.yaml (via app_state):
      - ymin, ymax
      - spec_ymin, spec_ymax
      - window_size
      - audio_buffer
      - spec_buffer
    """

    def __init__(self, napari_viewer: Viewer, app_state, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state
        self.viewer = napari_viewer
        self.lineplot = None
        
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
    
        
        # Reset button
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        main_layout.addWidget(reset_button)
        
        # Grid layout for controls in 2 columns
        layout = QGridLayout()
        main_layout.addLayout(layout)

        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.spec_ymin_edit = QLineEdit()
        self.spec_ymax_edit = QLineEdit()
        self.window_s_edit = QLineEdit()
        self.audio_buffer_edit = QLineEdit()
        self.spec_buffer_edit = QLineEdit()
        
        self.apply_button = QPushButton("Apply")
        
        self.autoscale_checkbox = QCheckBox("Autoscale (y-axis)")
        self.lock_axes_checkbox = QCheckBox("Lock Axes")
        
        


        # Arrange controls in pairs (2 columns)
        # Row 0: Y min/max (lineplot)
        layout.addWidget(QLabel("Y min (lineplot):"), 0, 0)
        layout.addWidget(self.ymin_edit, 0, 1)
        layout.addWidget(QLabel("Y max (lineplot):"), 0, 2)
        layout.addWidget(self.ymax_edit, 0, 3)
        
        # Row 1: Y min/max (spectrogram)
        layout.addWidget(QLabel("Y min (spectrogram):"), 1, 0)
        layout.addWidget(self.spec_ymin_edit, 1, 1)
        layout.addWidget(QLabel("Y max (spectrogram):"), 1, 2)
        layout.addWidget(self.spec_ymax_edit, 1, 3)
        
        layout.addWidget(QLabel("Window size (s):"), 2, 0)
        layout.addWidget(self.window_s_edit, 2, 1)

        layout.setRowMinimumHeight(3, 10)

        layout.addWidget(self.autoscale_checkbox, 4, 0)
        layout.addWidget(self.lock_axes_checkbox, 4, 1)
        layout.addWidget(self.apply_button, 4, 2)

        
        layout.setRowMinimumHeight(5, 10)

        # Row 3: Audio buffer / Spectrogram buffer
        layout.addWidget(QLabel("Audio buffer (s):"), 6, 0)
        layout.addWidget(self.audio_buffer_edit, 6, 1)
        layout.addWidget(QLabel("Spectrogram buffer (x):"), 6, 2)
        layout.addWidget(self.spec_buffer_edit, 6, 3)


        # Connect edit signals
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.spec_ymin_edit.editingFinished.connect(self._on_edited)
        self.spec_ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)
        self.audio_buffer_edit.editingFinished.connect(self._on_edited)
        self.spec_buffer_edit.editingFinished.connect(self._on_edited)
        
        self.apply_button.clicked.connect(self._on_edited)
        self.autoscale_checkbox.toggled.connect(self._autoscale_y_toggle)
        self.lock_axes_checkbox.toggled.connect(self._on_lock_axes_toggled)

        
        # Load initial settings
        self._restore_or_set_default_selections()


    def set_lineplot(self, lineplot):
        """Set reference to lineplot widget."""
        self.lineplot = lineplot
        # Set reverse reference so lineplot can update our controls
        if hasattr(lineplot, 'set_plots_widget'):
            lineplot.set_plots_widget(self)



    def _restore_or_set_default_selections(self):
        """Restore selections from app_state or set defaults."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = getattr(self.app_state, attr, None)
            if value is None:
                value = self.app_state.get_with_default(attr)
                setattr(self.app_state, attr, value)
            edit.setText("" if value is None else str(value))
        
        # Restore lock axes checkbox state
        lock_axes = self.app_state.get_with_default("lock_axes")
        self.lock_axes_checkbox.setChecked(lock_axes)

    def _parse_float(self, text: str) -> Optional[float]:
        """Parse float from text input."""
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
        
    def _autoscale_y_toggle(self, checked: bool):
        """Autoscale y-axis based on current data."""
        if not self.lineplot:
            return

        if checked:
            self.lineplot.vb.enableAutoRange(x=False, y=True)
            self.lock_axes_checkbox.setChecked(False)
        else:
            self.lineplot.vb.disableAutoRange()

    def _on_lock_axes_toggled(self, checked: bool):
        """Handle lock axes checkbox toggle."""
        self.app_state.lock_axes = checked
        self.lineplot.toggle_axes_lock()
        if checked:
            self.autoscale_checkbox.setChecked(False)
        

    def _on_edited(self):
        """Handle user edits to input fields."""
        if not self.lineplot:
            return
        
        self.lock_axes_checkbox.setChecked(False)
 
        
        edits = {
            "ymin": self.ymin_edit,
            "ymax": self.ymax_edit,
            "spec_ymin": self.spec_ymin_edit,
            "spec_ymax": self.spec_ymax_edit,
            "window_size": self.window_s_edit,
            "audio_buffer": self.audio_buffer_edit,
            "spec_buffer": self.spec_buffer_edit
        }
        
        values = {}
        for attr, edit in edits.items():
            val = self._parse_float(edit.text())
            if val is None:
                val = self.app_state.get_with_default(attr)
            values[attr] = val
            if self.app_state is not None:
                setattr(self.app_state, attr, val)


        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
        if is_spectrogram:
            self.lineplot.update_yrange(
                values["spec_ymin"], 
                values["spec_ymax"], 
            )
        else:
            self.lineplot.update_yrange(
                values["ymin"], 
                values["ymax"], 
            )
            
        self.lineplot._update_window_size()
            


    def _reset_to_defaults(self):
        """Reset all plot values to defaults."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = self.app_state.get_with_default(attr)
            edit.setText("" if value is None else str(value))
            if self.app_state is not None:
                setattr(self.app_state, attr, value)
        
        # Reset lock axes checkbox
        self.lock_axes_checkbox.setChecked(False)
        self.app_state.lock_axes = False
        
        self._on_edited()



    # --- Shortcut methods (only work in napari_video_mode) ---
    def _check_interactive_mode(self) -> bool:
        """Check if we're in interactive mode."""
        return getattr(self.app_state, 'sync_state', '') == 'napari_video_mode'

    
