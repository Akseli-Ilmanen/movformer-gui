"""Collapsible widget to control settings for all plots."""

from qtpy.QtWidgets import QFormLayout, QLineEdit, QWidget, QPushButton, QVBoxLayout, QHBoxLayout
from napari.viewer import Viewer

class PlotsWidget(QWidget):
    """Plots controls.

    Keys used in gui_settings.yaml (via app_state):
      - ymin
      - ymax
      - spec_ymin
      - spec_ymax
      - window_size
      - jump_size
    """

    def __init__(self, napari_viewer: Viewer, app_state, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state  # Use the shared app state
        self.viewer = napari_viewer  # Will be set after creation
        self.lineplot = None  # Will be set after creation
        
        
        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Reset button at the top
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        main_layout.addWidget(reset_button)
        
        # Form layout for the controls
        layout = QFormLayout()
        main_layout.addLayout(layout)

        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.spec_ymin_edit = QLineEdit()
        self.spec_ymax_edit = QLineEdit()
        self.window_s_edit = QLineEdit()
        self.jump_size_edit = QLineEdit()
        self.audio_buffer_edit = QLineEdit()
        self.spec_buffer_edit = QLineEdit()

        layout.addRow("Y min (lineplot):", self.ymin_edit)
        layout.addRow("Y max (lineplot):", self.ymax_edit)
        layout.addRow("Y min (spectrogram):", self.spec_ymin_edit)
        layout.addRow("Y max (spectrogram):", self.spec_ymax_edit)
        layout.addRow("Window size (s):", self.window_s_edit)
        layout.addRow("Jump size (s):", self.jump_size_edit)
        layout.addRow("Audio buffer (s):", self.audio_buffer_edit)
        layout.addRow("Spectrogram buffer (x):", self.spec_buffer_edit)

        # Wire events
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.spec_ymin_edit.editingFinished.connect(self._on_edited)
        self.spec_ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)
        self.jump_size_edit.editingFinished.connect(self._on_edited)
        self.audio_buffer_edit.editingFinished.connect(self._on_edited)
        self.spec_buffer_edit.editingFinished.connect(self._on_edited)

        # Load settings from YAML via app_state (handles None values properly)
        self._restore_or_set_default_selections()



        
    def set_lineplot(self, lineplot):
        """Set references to other widgets after creation."""
        self.lineplot = lineplot

        
        

    def _restore_or_set_default_selections(self):
        """Restore selections from app_state or set defaults if missing."""
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




    def _parse_float(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None



    def _on_edited(self):
        """Handle when user edits the input fields."""
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

        if self.lineplot is not None:
            # Determine which y-limits to use based on current plot type
            is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
            if is_spectrogram:
                # Use spectrogram y-limits for spectrogram mode
                self.lineplot.update_yrange(values["spec_ymin"], values["spec_ymax"], values["window_size"])
            else:
                # Use line plot y-limits for line plot mode
                self.lineplot.update_yrange(values["ymin"], values["ymax"], values["window_size"])

 

    def _reset_to_defaults(self):
        """Reset all plot values to their defaults and update the plot."""
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
            value = getattr(self.app_state, attr, None) if self.app_state is not None else None
            if value is None:
                value = self.app_state.get_with_default(attr)
            # Set text field
            edit.setText("" if value is None else str(value))
            # Set app_state attribute if possible
            if self.app_state is not None:
                setattr(self.app_state, attr, value)

        # Trigger plot update
        self._on_edited()


    def _adjust_ylim(self, factor):
        """Adjust y-axis limits."""
        if self.lineplot:
            vb = self.lineplot.plot_item.vb
            ymin, ymax = vb.viewRange()[1]
            center = (ymin + ymax) / 2
            new_range = (ymax - ymin) * (1 + factor)
            vb.setYRange(center - new_range/2, center + new_range/2)

    # Line 200 - _shift_yrange method  
    def _shift_yrange(self, factor):
        """Shift y-axis range."""
        if self.lineplot:
            vb = self.lineplot.plot_item.vb
            ymin, ymax = vb.viewRange()[1]
            shift = (ymax - ymin) * factor
            vb.setYRange(ymin + shift, ymax + shift)

    # Line 220 - _jump_plot method
    def _jump_plot(self, direction):
        """Jump plot view horizontally."""
        if self.lineplot:
            jump_size = self.app_state.get_with_default("jump_size")
            self.lineplot.nav.pan_x(direction * jump_size)

    # Line 240 - _adjust_window_size method
    def _adjust_window_size(self, factor):
        """Adjust x-axis window size."""
        if self.lineplot:
            self.lineplot.nav.zoom_x(factor)