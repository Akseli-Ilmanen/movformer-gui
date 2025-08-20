"""Collapsible widget to control settings for all plots."""

from qtpy.QtWidgets import QWidget, QFormLayout, QLineEdit

class PlotsWidget(QWidget):
    """Plots controls.

    Keys used in gui_settings.yaml:
      - ylim_min
      - ylim_max
      - window_size_s
    """

    def __init__(self, lineplot=None, parent=None, previous_state=None):
        super().__init__(parent=parent)
        self.plot_widget = lineplot  # Use the shared LinePlot instance

        # Load yaml
        self.parent()._load_from_yaml()


        layout = QFormLayout()
        self.setLayout(layout)

        

        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.window_s_edit = QLineEdit()

        self.ymin_edit.setPlaceholderText("auto")
        self.ymax_edit.setPlaceholderText("auto")
        self.window_s_edit.setPlaceholderText("full")

        layout.addRow("Y min:", self.ymin_edit)
        layout.addRow("Y max:", self.ymax_edit)
        layout.addRow("Window size (s):", self.window_s_edit)


        # Wire events
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)

        self._load_from_state()
        # Optionally apply axes settings immediately if plot_widget exists
        if self.plot_widget is not None:
            ymin = self._parse_float(self.ymin_edit.text())
            ymax = self._parse_float(self.ymax_edit.text())
            window_s = self._parse_float(self.window_s_edit.text())
            self.plot_widget.apply_axes_from_state(ymin, ymax, window_s)
            if hasattr(self.plot_widget, 'canvas'):
                self.plot_widget.canvas.draw()

    def set_plot_widget(self, plot_widget):
        """Provide the PlotWidget so we can apply settings immediately."""
        self.plot_widget = plot_widget
        if self.plot_widget is not None:
            ymin = self._parse_float(self.ymin_edit.text())
            ymax = self._parse_float(self.ymax_edit.text())
            window_s = self._parse_float(self.window_s_edit.text())
            self.plot_widget.apply_axes_from_state(ymin, ymax, window_s)
            if hasattr(self.plot_widget, 'canvas'):
                self.plot_widget.canvas.draw()

    def _parse_float(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _load_from_state(self):
        ymin = getattr(self, "lineplot_ylim_min", None)
        ymax = getattr(self, "lineplot_ylim_max", None)
        window_s = getattr(self, "lineplot_window_size_s", None)
        self.ymin_edit.setText("" if ymin is None else str(ymin))
        self.ymax_edit.setText("" if ymax is None else str(ymax))
        self.window_s_edit.setText("" if window_s is None else str(window_s))

    def _on_edited(self):
        self.ymin = self._parse_float(self.ymin_edit.text())
        self.ymax = self._parse_float(self.ymax_edit.text())
        self.window_size = self._parse_float(self.window_s_edit.text())


        if self.plot_widget is not None:
            # Pass the current settings to the LinePlot
            self.plot_widget.apply_axes_from_state(self.ymin, self.ymax, self.window_size)
            if hasattr(self.plot_widget, 'canvas'):
                self.plot_widget.canvas.draw()


