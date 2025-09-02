"""Integrated line plot combining matplotlib features with PyQtGraph performance."""

import pyqtgraph as pg
import numpy as np
from qtpy.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from qtpy.QtCore import Signal, QTimer
from movformer.utils.xr_utils import sel_valid
from src.movformer_gui.plot_utils import (
    plot_ds_variable, 
    clear_plot_items, 
    apply_view_settings,
    get_motif_colours
)


class IntegratedLinePlot(QWidget):
    """Main line plot widget combining all features.
    
    Combines:
    - PyQtGraph performance
    - Matplotlib-style colored segments
    - Changepoint markers
    - Label rectangles
    - Spectrogram support (if implemented)
    - Enhanced navigation
    """
    
    plot_clicked = Signal(object)
    
    def __init__(self, napari_viewer, app_state):
        super().__init__()
        self.viewer = napari_viewer
        self.app_state = app_state
        
        # Main layout
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # Create main plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget = pg.PlotWidget(background='white')
        self.plot_item = self.plot_widget.plotItem
        self.vb = self.plot_item.vb
        
        # Track plot items
        self.plot_items = []  # All items created by plot_ds_variable
        self.label_items = []  # Label rectangles
        
        # Current time marker
        self.time_marker = pg.InfiniteLine(angle=90, pen='r')
        self.plot_item.addItem(self.time_marker)
        
        layout.addWidget(self.plot_widget, 1)
        
        # Connect signals
        self.plot_widget.scene().sigMouseClicked.connect(self.on_click)
        
        # Update timer for smooth sync
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_time_marker)
        self.update_timer.start(50)  # 20 FPS update
    
        
    def update_plot(self, t0=None, t1=None, viewer_time=None):
        """Update the line plot with current data and time window.
        
        This method name matches the original matplotlib version for compatibility.
        """
        if not hasattr(self.app_state, 'ds'):
            return
            
        # Clear previous plot items
        clear_plot_items(self.plot_item, self.plot_items)
        
        # Get data and plot using plot_utils
        ds_kwargs = self.app_state.get_ds_kwargs()
        
        # Determine color variable if selected
        color_var = None
        if (hasattr(self.app_state, 'colors_sel') and 
            self.app_state.colors_sel != "None"):
            color_var = self.app_state.colors_sel
        
        # Plot the main variable with all features
        self.plot_items = plot_ds_variable(
            self.plot_item,
            self.app_state.ds,
            ds_kwargs,
            self.app_state.features_sel,
            color_variable=color_var
        )
        
        # Apply view settings (preserving xlim if provided)
        preserve_xlim = None
        if t0 is not None and t1 is not None:
            preserve_xlim = (t0, t1)
        apply_view_settings(self.plot_item, self.app_state, preserve_xlim)
        
        # Update time marker
        if viewer_time is not None:
            self.time_marker.setValue(viewer_time)
        elif hasattr(self.app_state, 'current_time'):
            self.time_marker.setValue(self.app_state.current_time)

    
  
    def update_time_marker(self):
        """Update current time marker position."""
        if hasattr(self.app_state, 'current_time'):
            self.time_marker.setValue(self.app_state.current_time)
    
    def update_yrange(self, ymin, ymax, window_size):
        """Apply axis limits from state values.
        
        Args:
            ymin: Minimum y-axis value
            ymax: Maximum y-axis value
            window_size: Window size for x-axis (not used in PyQtGraph, handled by view settings)
        """
        if ymin is not None and ymax is not None:
            self.plot_item.setYRange(ymin, ymax)
            
    def on_click(self, event):
        """Handle mouse clicks on plot."""
        pos = self.plot_item.vb.mapSceneToView(event.scenePos())
        
        # Create a click info object with button information
        click_info = {
            'x': pos.x(),
            'button': event.button()  # Qt.LeftButton=1, Qt.RightButton=2
        }
        self.plot_clicked.emit(click_info)

    
    # Properties for matplotlib compatibility
    @property
    def ax(self):
        """Compatibility property - returns plot_item which is roughly equivalent to matplotlib ax."""
        return self.plot_item
    
    @property
    def canvas(self):
        """Compatibility property - returns plot_widget for canvas-like operations."""
        return self.plot_widget