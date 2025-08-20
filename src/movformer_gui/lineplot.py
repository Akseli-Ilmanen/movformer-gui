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

    def __init__(self, napari_viewer: Viewer):
        """Initialize the plot widget with napari viewer and optional ds."""
        super().__init__()
        self.viewer = napari_viewer
        self.time = None  # Will be set when data is loaded
        self.fig = Figure(figsize=(8, 3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)    

        # Click handling is connected by the DataWidget after construction

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)



    def updateLinePlot(self, ds, current_trial, current_keypoint, current_variable, current_color_variable=None):
        """Update the plot with data from ds."""
        self.ax.clear()
        
        # Store time data for click handling
        self.time = ds["time"].values
        
        plot_ds_variable(self.ax, ds, current_variable, current_trial, current_keypoint, current_color_variable)
        
        # Apply any user-specified axes settings from persistent state
        self.apply_axes_from_state()
        self.canvas.draw()



    # ---- Axes settings application --------------------------------------------
    def apply_axes_from_state(self, ymin=None, ymax=None, window_s=None):
        """Apply axes limits from persisted state to the matplotlib Axes.

        Args:
            ymin: Y-axis minimum value
            ymax: Y-axis maximum value
            window_s: Time window size in seconds
        """

        # If no parameters provided, try to get them from object attributes (for backward compatibility)
        if ymin is None:
            ymin = getattr(self, "lineplot_ylim_min", None)
        if ymax is None:
            ymax = getattr(self, "lineplot_ylim_max", None)
        if window_s is None:
            window_s = getattr(self, "lineplot_window_size_s", None)

        if ymin is not None and ymax is not None:
            self.ax.set_ylim(float(ymin), float(ymax))
            

        window_s_f = float(window_s) if window_s is not None else None
        if self.time is not None and window_s_f is not None and window_s_f > 0:
            t0 = float(self.time[0])
            t1 = float(self.time[-1])
            end = min(t0 + window_s_f, t1)
            self.ax.set_xlim(t0, end)

