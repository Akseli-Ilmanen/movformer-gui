"""Widget for displaying a line plot and syncing napari frame to plot click."""

import numpy as np
try:
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
    )
except ImportError:
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvasQTAgg as FigureCanvas,
    )
from matplotlib.figure import Figure
from qtpy.QtWidgets import QVBoxLayout, QWidget
from plot_utils import plot_ds_variable

class LinePlotWidget(QWidget):
    """Widget to display a line plot and sync napari frame to plot click."""

    def __init__(self, viewer, ds=None):
        """Initialize the plot widget with napari viewer and optional ds."""
        super().__init__()
        self.viewer = viewer
        self.time = None  # Will be set when data is loaded
        self.fig = Figure(figsize=(8, 3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        


        # self.canvas.mpl_connect("button_press_event", self.on_click)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def updateLinePlot(self, ds, current_trial, current_keypoint, current_variable, current_color_variable=None):
        """Update the plot with data from ds."""
        self.ax.clear()
        
        # Store time data for click handling
        self.time = ds["time"].values
        
        plot_ds_variable(self.ax, ds, current_variable, current_trial, current_keypoint)
        self.canvas.draw()


    # def on_click(self, event):
    #     """Jump napari viewer to frame corresponding to clicked time."""
    #     if event.inaxes == self.ax:
    #         # Find closest time index
    #         idx = (np.abs(self.time - event.xdata)).argmin()
    #         # Update napari viewer frame
    #         if hasattr(self.viewer.dims, 'set_current_step'):
    #             self.viewer.dims.set_current_step(0, idx)
    #         else:
    #             # Fallback for different napari versions
    #             self.viewer.dims.current_step = (idx,) + self.viewer.dims.current_step[1:]
