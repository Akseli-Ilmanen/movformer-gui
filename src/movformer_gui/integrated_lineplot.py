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
        
        # Connect click handler only in lineplot_to_video mode
        self.plot_widget.scene().sigMouseClicked.connect(self._handle_click)
        
        # Timer for smooth window updates in video_to_lineplot mode
        self.window_update_timer = QTimer()
        self.window_update_timer.timeout.connect(self._update_window_position)
        self.window_update_timer.start(33)  # ~30 FPS for smooth following
        
        # Store interaction state
        self._interaction_enabled = True
        self._last_window_center = None
        
        # Connect state changes
        if hasattr(self.app_state, 'sync_state_changed'):
            self.app_state.sync_state_changed.connect(self._on_sync_mode_changed)
    
    def _on_sync_mode_changed(self, sync_state: str) -> None:
        """Handle sync mode changes."""
        if sync_state == "video_to_lineplot":
            self._set_video_sync_mode()
        else:
            self._set_interactive_mode()
    
    def _set_video_sync_mode(self) -> None:
        """Configure plot for video-sync mode (limited user interaction).
        
        In this mode:
        - Plot window auto-follows video playback
        - No direct plot panning/zooming with mouse
        - Timeline slider remains active for seeking
        - Space bar remains active for play/pause
        - Plot clicks are disabled
        """
        self._interaction_enabled = False
        
        # Disable mouse interactions ON THE PLOT ONLY
        self.vb.setMouseEnabled(x=False, y=False)
        
        
        # Make time marker more prominent in this mode
        self.time_marker.setPen(pg.mkPen(color='r', width=3, style=pg.QtCore.Qt.SolidLine))
        self.time_marker.setZValue(1000)

    def _set_interactive_mode(self) -> None:
        """Configure plot for interactive mode (full user control).
        
        In this mode:
        - Full mouse control of plot (pan, zoom)
        - Plot clicks jump video to that time
        - All keyboard shortcuts work
        - Manual control of view window
        """
        self._interaction_enabled = True
        
        # Enable full mouse interactions with the plot
        self.vb.setMouseEnabled(x=True, y=True)
        
        
        # Hide time marker in interactive mode
        self.time_marker.hide()
        

        
    def _update_window_position(self) -> None:
        """Update window position to follow video in video_to_lineplot mode."""
        if not hasattr(self.app_state, 'sync_state'):
            return
            
        if self.app_state.sync_state != "video_to_lineplot":
            return
            
        if not hasattr(self.app_state, 'current_frame') or not hasattr(self.app_state, 'ds') or self.app_state.ds is None:
            return
            
        if not hasattr(self.app_state.ds, 'fps'):
            return
        
        current_time = self.app_state.current_frame / self.app_state.ds.fps
        window_size = self.app_state.get_with_default('window_size')
        
        # Calculate window bounds centered on current time
        half_window = window_size / 2.0
        x_min = current_time - half_window
        x_max = current_time + half_window
        
        # Apply y-axis limits from settings
        y_min = self.app_state.get_with_default('ymin')
        y_max = self.app_state.get_with_default('ymax')
        
        # Update view range without triggering signals


        if y_min is not None and y_max is not None:
            self.vb.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0)
        else:
            self.vb.setRange(xRange=(x_min, x_max), padding=0)

        # Update time marker position and ensure visibility
        self.time_marker.setValue(current_time)
        self.time_marker.show()
        
        # Ensure marker is on top
        self.time_marker.setZValue(1000)
        
        # Store for reference
        self._last_window_center = current_time
        

    
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
        
        # Handle view settings based on sync mode
        if self.app_state.sync_state == "video_to_lineplot":
            # In video sync mode, immediately apply centered window
            self._update_window_position()
        else:
            # In interactive mode, preserve xlim if provided
            preserve_xlim = None
            if t0 is not None and t1 is not None:
                preserve_xlim = (t0, t1)
            apply_view_settings(self.plot_item, self.app_state, preserve_xlim)
        

        current_time = self.app_state.current_frame / self.app_state.ds.fps
        self.time_marker.setValue(current_time)


    def update_yrange(self, ymin: Optional[float], 
                     ymax: Optional[float], 
                     window_size: Optional[float]) -> None:
        """Apply axis limits from state values."""
        if self.app_state.sync_state == "video_to_lineplot":
            # In video sync mode, update will happen via _update_window_position
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
    
    def set_sync_mode(self, mode: str) -> None:
        """Public method to set sync mode."""
        if mode == "video_to_lineplot":
            self._set_video_sync_mode()
        else:
            self._set_interactive_mode()
    
    def get_current_xlim(self) -> Tuple[float, float]:
        """Get current x-axis limits."""
        x_range, _ = self.vb.viewRange()
        return x_range
    
    def get_current_ylim(self) -> Tuple[float, float]:
        """Get current y-axis limits."""
        _, y_range = self.vb.viewRange()
        return y_range