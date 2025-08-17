"""Widget for displaying a line plot and syncing napari frame to plot click."""

import numpy as np
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
from qtpy.QtWidgets import QVBoxLayout, QWidget


class LinePlotWidget(QWidget):
    """Widget to display a line plot and sync napari frame to plot click."""

    def __init__(self, viewer, data, time):
        """Initialize the plot widget with napari viewer, data, and time axis."""
        super().__init__()
        self.viewer = viewer
        self.data = data
        self.time = time

        self.fig = Figure(figsize=(6, 2))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.plot(self.time, self.data)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.mpl_connect("button_press_event", self.on_click)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def on_click(self, event):
        """Jump napari viewer to frame corresponding to clicked time."""
        if event.inaxes == self.ax:
            idx = (np.abs(self.time - event.xdata)).argmin()
            self.viewer.dims.set_current_step(0, idx)
