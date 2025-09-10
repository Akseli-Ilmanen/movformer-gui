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


class IntegratedLinePlot(QWidget):
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
        self._last_window_center = None   
        self.update_window_bool = False

    
    def set_video_sync_mode(self) -> None:
        """Configure plot for video-sync mode (limited user interaction).
        
        In this mode:
        - Plot window auto-follows video playback
        - No direct plot panning/zooming with mouse
        - Plot clicks are disabled
        """
        self._interaction_enabled = False
        
        # Disable mouse interactions ON THE PLOT ONLY
        self.vb.setMouseEnabled(x=False, y=False)
        
        # Make time marker more prominent in this mode
        self.time_marker.setPen(pg.mkPen(color='r', width=3, style=pg.QtCore.Qt.SolidLine))
        self.time_marker.setZValue(1000)

        self.update_window_bool = True
                

    def set_dynamic_mode(self) -> None:
        """Interactive when video is not playing (full mouse control, plot clicks work)"""
        
        # Behave like interactive mode when not playing
        self._interaction_enabled = True
        self.vb.setMouseEnabled(x=True, y=True)
        self._apply_zoom_constraints()
        
        
        # Show time marker but make it less prominent
        self.time_marker.setPen(pg.mkPen(color='r', width=1, style=pg.QtCore.Qt.DashLine))
        self.time_marker.show()
        self.time_marker.setZValue(100)
        
        self.update_window_bool = False

        
    def _update_window_position(self) -> None:
        """Update window position to follow video when appropriate."""
        if not hasattr(self.app_state, 'current_frame') or not hasattr(self.app_state, 'ds') or self.app_state.ds is None:
            return
            
        if not self.update_window_bool:
            return
            
        current_time = self.app_state.current_frame / self.app_state.ds.fps
        
        self._update_window_size()
        
        # Apply y-axis limits from settings
        y_min = self.app_state.get_with_default('ymin')
        y_max = self.app_state.get_with_default('ymax')
        
        # Update view range without triggering signals
        if y_min is not None and y_max is not None:
            self.vb.setRange(yRange=(y_min, y_max), padding=0)


        # Update time marker position and ensure visibility
        self.time_marker.setValue(current_time)
        self.time_marker.show()
        
        # Ensure marker is on top
        self.time_marker.setZValue(1000)
        
        # Store for reference
        self._last_window_center = current_time
        
        
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
            
            
            
        
    def _update_data_bounds(self):
        """Update data bounds from current dataset for zoom constraints."""
        if not hasattr(self.app_state, 'ds') or self.app_state.ds is None:
            return
            
        # Get time bounds
        time = self.app_state.ds.time.values
        self._data_time_min = float(time[0]) if len(time) > 0 else 0.0
        self._data_time_max = float(time[-1]) if len(time) > 0 else 10.0
        
        # Set minimum time range based on data duration
        total_duration = self._data_time_max - self._data_time_min
        self._min_time_range = max(0.001, total_duration / 2**16)
        
        # Get current selection to estimate y bounds
        try:
            ds_kwargs = self.app_state.get_ds_kwargs()
            if hasattr(self.app_state, 'features_sel') and self.app_state.features_sel:
                var = self.app_state.ds[self.app_state.features_sel]
                data, _ = sel_valid(var, ds_kwargs)
                if data.size > 0:
                    self._data_y_min = float(np.nanmin(data))
                    self._data_y_max = float(np.nanmax(data))
                else:
                    self._data_y_min = -1.0
                    self._data_y_max = 1.0
            else:
                self._data_y_min = -1.0
                self._data_y_max = 1.0
        except:
            self._data_y_min = -1.0
            self._data_y_max = 1.0
            
        # Apply zoom constraints to viewbox
        self._apply_zoom_constraints()
    
    def _apply_zoom_constraints(self):
        """Apply data-aware zoom constraints to the plot viewbox."""
        if (self._data_time_min is None or self._data_time_max is None or 
            self._data_y_min is None or self._data_y_max is None):
            return
            
        # Set time axis limits with small buffer
        time_buffer = (self._data_time_max - self._data_time_min) * 0.01
        self.vb.setLimits(
            xMin=self._data_time_min - time_buffer,
            xMax=self._data_time_max + time_buffer,
            minXRange=self._min_time_range,
            maxXRange=self._data_time_max - self._data_time_min + 2*time_buffer
        )
        
        # Set y axis limits with buffer
        y_range = self._data_y_max - self._data_y_min
        if y_range > 0:
            y_buffer = y_range * 0.1
            min_y_range = max(y_range / 2**16, 0.001)
            self.vb.setLimits(
                yMin=self._data_y_min - y_buffer,
                yMax=self._data_y_max + y_buffer,
                minYRange=min_y_range,
                maxYRange=y_range + 2*y_buffer
            )

    
    def update_plot(self, t0: Optional[float] = None, 
                   t1: Optional[float] = None) -> None:
        """Update the line plot with current data and time window."""
        if not hasattr(self.app_state, 'ds'):
            return
        
        # Update data bounds for zoom constraints
        self._update_data_bounds()
        
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
        if self.update_window_bool:
            self._update_window_position()
        else:
            # In interactive state, preserve xlim if provided
            preserve_xlim = None
            if t0 is not None and t1 is not None:
                preserve_xlim = (t0, t1)
            apply_view_settings(self.plot_item, self.app_state, preserve_xlim)
            # Update dynamic mode settings in case playback state changed
            self.set_dynamic_mode()



    def update_yrange(self, ymin: Optional[float], 
                     ymax: Optional[float]) -> None:
        """Apply axis limits from state values."""

        
        if self.update_window_bool:
            return
            
        # In interactive mode, apply y-range normally
        if ymin is not None and ymax is not None:
            self.plot_item.setYRange(ymin, ymax)
    
    
    
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