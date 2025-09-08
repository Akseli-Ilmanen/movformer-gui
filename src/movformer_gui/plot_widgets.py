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
      - jump_size
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
        self.jump_size_edit = QLineEdit()
        self.audio_buffer_edit = QLineEdit()
        self.spec_buffer_edit = QLineEdit()

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
        
        # Row 2: Window size / Jump size
        layout.addWidget(QLabel("Window size (s):"), 2, 0)
        layout.addWidget(self.window_s_edit, 2, 1)
        layout.addWidget(QLabel("Jump size (s)*:"), 2, 2)
        layout.addWidget(self.jump_size_edit, 2, 3)
        
        # Row 3: Audio buffer / Spectrogram buffer
        layout.addWidget(QLabel("Audio buffer (s):"), 3, 0)
        layout.addWidget(self.audio_buffer_edit, 3, 1)
        layout.addWidget(QLabel("Spectrogram buffer (x):"), 3, 2)
        layout.addWidget(self.spec_buffer_edit, 3, 3)
        
        # Note about jump size
        self.jump_note_label = QLabel("*Jump size only works in LinePlot → Video mode")
        self.jump_note_label.setStyleSheet("font-size: 9pt; color: #888;")
        main_layout.addWidget(self.jump_note_label)

        # Connect edit signals
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.spec_ymin_edit.editingFinished.connect(self._on_edited)
        self.spec_ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)
        self.jump_size_edit.editingFinished.connect(self._on_edited)
        self.audio_buffer_edit.editingFinished.connect(self._on_edited)
        self.spec_buffer_edit.editingFinished.connect(self._on_edited)

        
        # Load initial settings
        self._restore_or_set_default_selections()


    def set_lineplot(self, lineplot):
        """Set reference to lineplot widget."""
        self.lineplot = lineplot



    def _restore_or_set_default_selections(self):
        """Restore selections from app_state or set defaults."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("jump_size", self.jump_size_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = getattr(self.app_state, attr, None)
            if value is None:
                value = self.app_state.get_with_default(attr)
                setattr(self.app_state, attr, value)
            edit.setText("" if value is None else str(value))

    def _parse_float(self, text: str) -> Optional[float]:
        """Parse float from text input."""
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _on_edited(self):
        """Handle user edits to input fields."""
        edits = {
            "ymin": self.ymin_edit,
            "ymax": self.ymax_edit,
            "spec_ymin": self.spec_ymin_edit,
            "spec_ymax": self.spec_ymax_edit,
            "window_size": self.window_s_edit,
            "jump_size": self.jump_size_edit,
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

        # Update plot if available
        if self.lineplot is not None:
            sync_state = getattr(self.app_state, 'sync_state', 'video_to_lineplot')
            
            if sync_state == "video_to_lineplot":
                # In video sync mode, changes will be applied automatically
                # by the lineplot's update timer
                pass
            else:
                # In interactive mode, apply changes immediately
                is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
                if is_spectrogram:
                    self.lineplot.update_yrange(
                        values["spec_ymin"], 
                        values["spec_ymax"], 
                        values["window_size"]
                    )
                else:
                    self.lineplot.update_yrange(
                        values["ymin"], 
                        values["ymax"], 
                        values["window_size"]
                    )

    def _reset_to_defaults(self):
        """Reset all plot values to defaults."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("jump_size", self.jump_size_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = self.app_state.get_with_default(attr)
            edit.setText("" if value is None else str(value))
            if self.app_state is not None:
                setattr(self.app_state, attr, value)
        
        self._on_edited()

    # --- Shortcut methods (only work in lineplot_to_video mode) ---
    
    def _check_interactive_mode(self) -> bool:
        """Check if we're in interactive mode."""
        return getattr(self.app_state, 'sync_state', '') == 'lineplot_to_video'

    
    def _adjust_window_size(self, factor: float):
        """Adjust window_size by a multiplicative factor and update relevant fields."""
        if not self._check_interactive_mode():
            return
        current = self._parse_float(self.window_s_edit.text())
        if current is None:
            current = self.app_state.get_with_default("window_size")

        new_value = current * factor
        self.window_s_edit.setText(str(new_value))
        setattr(self.app_state, "window_size", new_value)



    def _adjust_ylim(self, factor: float):
        """Adjust y-axis limits (zoom in/out)."""
        if not self._check_interactive_mode() or not self.lineplot:
            return
            
        vb = self.lineplot.plot_item.vb
        ymin, ymax = vb.viewRange()[1]
        center = (ymin + ymax) / 2
        new_range = (ymax - ymin) * (1 + factor)
        vb.setYRange(center - new_range/2, center + new_range/2)

    def _shift_yrange(self, factor: float):
        """Shift y-axis range up/down."""
        if not self._check_interactive_mode() or not self.lineplot:
            return
            
        vb = self.lineplot.plot_item.vb
        ymin, ymax = vb.viewRange()[1]
        shift = (ymax - ymin) * factor
        vb.setYRange(ymin + shift, ymax + shift)

    def _jump_plot(self, direction: int):
        """Jump plot view horizontally."""
        if not self._check_interactive_mode() or not self.lineplot:
            return