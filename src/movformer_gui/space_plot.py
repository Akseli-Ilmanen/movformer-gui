"""Space plot widget for displaying box topview and centroid trajectory plots."""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel
from qtpy.QtCore import Qt
from movformer.plots.plots import plot_box_topview
from movement.plots import plot_centroid_trajectory



class SpacePlot(QWidget):
    """Widget for displaying spatial plots in napari dock area."""
    
    def __init__(self, viewer, app_state):
        super().__init__()
        self.viewer = viewer
        self.app_state = app_state
        self.dock_widget = None
        
        # Set up matplotlib figure
        self.figure = Figure(figsize=(8, 8))
        self.canvas = FigureCanvas(self.figure)
        self.ax = None
        
        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self.ds_kwargs = {}
        
        # Initially hidden
        self.hide()
    
    def show(self):
        """Show the space plot by replacing the layer controls area."""

        self.viewer.window._qt_viewer.dockLayerControls.setVisible(False)
        
        if not self.dock_widget:
            # Add space plot at the left side
            self.dock_widget = self.viewer.window.add_dock_widget(
                self, area="left", name="Space Plot"
            )
            
            # Set the dock widget to take up 20% of the window width
            main_window = self.viewer.window._qt_window
            total_width = main_window.width()
            desired_width = int(total_width * 0.2)
            
            # Set minimum height and resize the dock widget
            self.setMinimumHeight(500)
            self.setMinimumWidth(500)
            self.dock_widget.resize(desired_width, max(500, self.dock_widget.height()))
            

        super().show()
    
    def hide(self):
        """Hide the space plot dock widget and show layer controls."""
        self.viewer.window._qt_viewer.dockLayerControls.setVisible(True)
        if self.dock_widget:
            self.dock_widget.setVisible(False)

        super().hide()
    
    def update_plot(self, plot_type: str, individual: str = None, keypoints: str = None, color_variable: str = None):
        """Update the plot based on the selected type and parameters."""
        if not self.app_state.ds:
            return

        if not hasattr(self.app_state.ds, 'position') or 'x' not in self.app_state.ds.coords["space"] or 'y' not in self.app_state.ds.coords["space"]:
            raise ValueError("Dataset must have 'position' variable with 'x' and 'y' coordinates for space plots")


        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        


        
        if plot_type == "plot_box_topview":
            self._plot_box_topview(individual, keypoints, color_variable)
        elif plot_type == "plot_centroid_trajectory":
            self._plot_centroid_trajectory(individual, keypoints)
 
        
        self.canvas.draw()

    def _plot_box_topview(self, individual: str, keypoints: str, color_variable: str = None):
        """Create box topview plot."""
        ds_kwargs = {}
        

        if individual and individual != "None":
            ds_kwargs["individuals"] = individual
        if keypoints and keypoints != "None":
            ds_kwargs["keypoints"] = keypoints
            
        self.ds_kwargs = ds_kwargs
            
        # Assuming 'angle_rgb' is available in the dataset
        # You may need to adjust this based on your dataset structure
        plot_box_topview(self.ax, self.app_state.ds, color_variable, **ds_kwargs)

    
    def _plot_centroid_trajectory(self, individual: str, keypoints: str):
        """Create centroid trajectory plot."""
        if not hasattr(self.app_state.ds, 'position'):
            raise ValueError("Dataset must have 'position' variable for centroid trajectory plot")
            
        # Select data for the specific trial
        da = self.app_state.ds.position
            
        plot_centroid_trajectory(
            ax=self.ax, 
            da=da, 
            individual=individual if individual and individual != "None" else None,
            keypoints=keypoints if keypoints and keypoints != "None" else None
        )
        
        
    def highlight_positions(self, start_frame: int, end_frame: int):
        """Highlight positions in the plot based on current frame."""

        
      

        collections_to_remove = [col for col in self.ax.collections if getattr(col, '_is_highlight', False)]
        for col in collections_to_remove:
            col.remove()

        xy = self.app_state.ds.sel(space=["x", "y"], **self.ds_kwargs).position


        highlighted_points = xy[start_frame:end_frame + 1]

        if highlighted_points.time.size == 0:
            return
        
        x = highlighted_points.sel(space='x').values
        y = highlighted_points.sel(space='y').values
        
  
        scatter = self.ax.scatter(x, y, c='red', s=50, label='Current Frame Range', zorder=5)
        scatter._is_highlight = True 
        
        self.ax.legend()
        self.canvas.draw()