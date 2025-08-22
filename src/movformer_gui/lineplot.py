"""Widget for displaying a line plot and syncing napari frame to plot click.

Provides time-synced line plotting. Axes settings (y-limits and x window size
in seconds) are persisted in ``gui_state.yaml`` and applied from a separate
collapsible widget in the Meta widget.
"""


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from plot_utils import plot_ds_variable
import numpy as np
from napari.viewer import Viewer
from qtpy.QtCore import Signal



class LinePlot(QWidget):
    """Widget to display a line plot and sync napari frame to plot click.
    """
    plot_clicked = Signal(object)  # Emitted with event or time index

    def __init__(self, napari_viewer: Viewer, app_state=None):
        """Initialize the plot widget with napari viewer and app_state."""
        super().__init__()
        self.viewer = napari_viewer
        self.app_state = app_state
        self.time = None  # Will be set when data is loaded
        self.plots_widget = None  # Will be set after creation
        self.fig = Figure(figsize=(8, 3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)    

        # Click handling is connected by the DataWidget after construction

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def set_plots_widget(self, plots_widget):
        """Set the plots_widget reference after creation."""
        self.plots_widget = plots_widget



    def updateLinePlot(self):
        """Update the plot with data from ds."""
        self.ax.clear()


        ds_kwargs = self.app_state.get_ds_kwargs()

        if hasattr(self.app_state, 'colors_sel'):
            plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel, self.app_state.colors_sel)
        else:
            plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel)

        # Apply any user-specified axes settings from persistent state
        self.apply_axes_from_state()
        self.canvas.draw()

        # Sync napari viewer frame after plot update
        if hasattr(self, 'plots_widget') and self.plots_widget is not None:
            self.plots_widget._sync_napari_frame()



    # ---- Axes settings application --------------------------------------------
    def apply_axes_from_state(self, ymin=None, ymax=None, window_s=None):
        """Apply axes limits from persisted state to the matplotlib Axes."""

        self.time = self.app_state.ds["time"].values

        if ymin is not None and ymax is not None:
            self.ax.set_ylim(float(ymin), float(ymax))
            
        window_s_f = float(window_s) if window_s is not None else None
        if self.time is not None and window_s_f is not None and window_s_f > 0:
            t0 = float(self.time[0])
            t1 = float(self.time[-1])
            end = min(t0 + window_s_f, t1)
            self.ax.set_xlim(t0, end)

        # Sync napari viewer frame after axes changes
        if hasattr(self, 'plots_widget') and self.plots_widget is not None:
            self.plots_widget._sync_napari_frame()

