"""Enhanced integrated line plot with video-sync mode support."""

import pyqtgraph as pg
import numpy as np
from qtpy.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from qtpy.QtCore import Signal, QTimer
from typing import Optional, Tuple
from movformer.utils.xr_utils import sel_valid
from src.movformer_gui.plot_utils import (
    plot_ds_variable, 
    clear_plot_items, 
    apply_view_settings,
    get_motif_colours
)
from movformer.features.preprocessing import interpolate_nans

class LinePlot(QWidget):
    """Main line plot widget with video-sync capabilities.
    
    Features:
    - PyQtGraph performance
    - Matplotlib-style colored segments
    - Video-sync mode with centered time marker
    - Interactive mode for lineplot-to-video sync
    """
    
    plot_clicked = Signal(object)
    
    def __init__(self, napari_viewer, app_state):
        super().__init__()
        self.viewer = napari_viewer
        self.app_state = app_state
        
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        self.plot_widget = pg.PlotWidget(background='white')
        self.plot_item = self.plot_widget.plotItem
        self.vb = self.plot_item.vb
        self.vb.setMenuEnabled(False)
        
        self.plot_items = []
        self.label_items = []
        
        # Time marker with enhanced styling
        self.time_marker = pg.InfiniteLine(
            angle=90, 
            pen=pg.mkPen('r', width=2),
            movable=False
        )
        self.plot_item.addItem(self.time_marker)
        
        layout.addWidget(self.plot_widget, 1)
        
        # Connect click handler for interactive functionality
        self.plot_widget.scene().sigMouseClicked.connect(self._handle_click)
        

  
        
        # Data bounds for smart zoom constraints
        self._data_time_min = None
        self._data_time_max = None
        self._data_y_min = None
        self._data_y_max = None
        self._min_time_range = 0.001  # Minimum zoom range for time axis
        

        # Store interaction state
        self._interaction_enabled = True

  
        
        
        # Reference to plots widget for updating controls
        self.plots_widget = None

    
    def set_stream_mode(self) -> None:
        """Configure plot for video-sync mode (limited user interaction).
        
        In this mode:
        - Plot window auto-follows video playback
        - No direct plot panning/zooming with mouse
        - Plot clicks are disabled
        """
        self._interaction_enabled = False
        self.vb.setMouseEnabled(x=False, y=False)
        self.time_marker.setPen(pg.mkPen(color='r', width=3, style=pg.QtCore.Qt.SolidLine))
        self.time_marker.setZValue(1000)
        self.app_state.lock_axes = True
                

    def set_label_mode(self) -> None:
        """Interactive when video is not playing (full mouse control, plot clicks work)"""
        

        self._interaction_enabled = True
        self.vb.setMouseEnabled(x=True, y=True)
        self.time_marker.setPen(pg.mkPen(color='r', width=1, style=pg.QtCore.Qt.DashLine))
        self.time_marker.show()
        self.time_marker.setZValue(100)


    def update_plot(self, t0: Optional[float] = None, 
                   t1: Optional[float] = None) -> None:
        """Update the line plot with current data and time window."""
        if not hasattr(self.app_state, 'ds'):
            return
        
        # Clear previous plot items
        clear_plot_items(self.plot_item, self.plot_items)  

        
        # Get data and plot
        ds_kwargs = self.app_state.get_ds_kwargs()
        
        color_var = None
        if (hasattr(self.app_state, 'colors_sel') and 
            self.app_state.colors_sel != "None"):
            color_var = self.app_state.colors_sel
        
        self.plot_items = plot_ds_variable(
            self.plot_item,
            self.app_state.ds,
            ds_kwargs,
            self.app_state.features_sel,
            color_variable=color_var
        )
    
        
        
        if self.app_state.sync_state == "pyav_stream_mode":
            self._update_window_position()
        else:
            # In interactive state, preserve xlim if provided
            preserve_xlim = None
            if t0 is not None and t1 is not None:
                preserve_xlim = (t0, t1)
            apply_view_settings(self.plot_item, self.app_state, preserve_xlim)
            # Update dynamic mode settings in case playback state changed
            self.set_label_mode()



        self.toggle_axes_lock()


    def update_yrange(self, ymin: Optional[float], 
                     ymax: Optional[float]) -> None:
        """Apply axis limits from state values."""

        
        if self.app_state.sync_state == "pyav_stream_mode":
            return
            
        # In interactive mode, apply y-range normally
        if ymin is not None and ymax is not None:
            self.plot_item.setYRange(ymin, ymax)
    
        
    def _update_window_position(self) -> None:
        """Update window position to follow video when appropriate."""
        if not hasattr(self.app_state, 'current_frame') or not hasattr(self.app_state, 'ds') or self.app_state.ds is None:
            return
            
        current_time = self.app_state.current_frame / self.app_state.ds.fps
        
        self._update_window_size()
        

        y_min = self.app_state.get_with_default('ymin')
        y_max = self.app_state.get_with_default('ymax')
    
        if y_min is not None and y_max is not None:
            self.vb.setRange(yRange=(y_min, y_max), padding=0)


        # Update time marker position and ensure visibility
        self.time_marker.setValue(current_time)
        self.time_marker.show()
        
        # Ensure marker is on top
        self.time_marker.setZValue(1000)
        


        
    def _update_window_size(self) -> None:
        """Set window size by a multiplicative factor."""
        if not hasattr(self.app_state, 'window_size'):
            return

        current_time = self.app_state.current_frame / self.app_state.ds.fps
        window_size = self.app_state.get_with_default('window_size')
        
        # Calculate window bounds centered on current time
        half_window = window_size / 2.0
        x_min = current_time - half_window
        x_max = current_time + half_window
        
        self.vb.setRange(xRange=(x_min, x_max), padding=0)
            
            
            
        
    def _apply_zoom_constraints(self):
        """Apply data-aware zoom constraints to the plot viewbox."""

    
        feature_sel = self.app_state.features_sel
        ds_kwargs = self.app_state.get_ds_kwargs()
        data, _ = sel_valid(self.app_state.ds[feature_sel], ds_kwargs)
       
        # Excluding leading and trailing NaNs for time axis limits, find xmin/xmax
        time_dim = int(np.argmax(data.shape))
        data = interpolate_nans(data, axis=time_dim)
        if data.ndim > 1:
            valid_indices = np.where(np.any(data != 0, axis=1))[0]
        else:
            valid_indices = np.nonzero(data)[0]
            
        xMinIdx = valid_indices[0]
        xMaxIdx = valid_indices[-1]

        # Convert to seconds
        time = self.app_state.ds.time.values        
        xMin = time[xMinIdx]
        xMax = time[xMaxIdx]
        xRange = xMax - xMin
        
        self.vb.setLimits(
            xMin=xMin - 1,
            xMax=xMax + 1,
            maxXRange=xRange + 1,
        )
        
        y_min = np.nanpercentile(data, 0.5)
        y_max = np.nanpercentile(data, 99.5)
        y_range = y_max - y_min
        y_buffer = (y_max - y_min) * 0.2

        if y_range > 0:
            self.vb.setLimits(
                yMin=y_min - y_buffer,
                yMax=y_max + y_buffer,
                maxYRange=y_range + y_buffer
            )

            

    def toggle_axes_lock(self):
        """Enable or disable axes locking to prevent zoom but allow panning."""
        locked = self.app_state.lock_axes
        
        if locked:
            current_xlim = self.vb.viewRange()[0]
            current_ylim = self.vb.viewRange()[1] 
            x_range = current_xlim[1] - current_xlim[0]
            

            # Set fixed x-range and allow horizontal panning only
            self.vb.setLimits(minXRange=x_range, maxXRange=x_range,
                            yMin=current_ylim[0], yMax=current_ylim[1])


            self.vb.setMouseEnabled(x=True, y=False)
            self.vb.setMenuEnabled(False)
        else:
            
            # Don't set xlim/ylim but set data-aware zoom constraints
            self._apply_zoom_constraints()
            
            
            self.vb.setMouseEnabled(x=True, y=True)
            self.vb.setMenuEnabled(True)

    def set_plots_widget(self, plots_widget):
        """Set reference to plots widget for updating controls."""
        self.plots_widget = plots_widget
    
 
    
    
    def _handle_click(self, event) -> None:
        """Handle mouse clicks on plot."""
        # Only process clicks in interactive mode
        if not self._interaction_enabled:
            return
            
        pos = self.plot_item.vb.mapSceneToView(event.scenePos())
        
        click_info = {
            'x': pos.x(),
            'button': event.button()
        }
        self.plot_clicked.emit(click_info)
    
    
    def get_current_xlim(self) -> Tuple[float, float]:
        """Get current x-axis limits."""
        return self.vb.viewRange()[0]