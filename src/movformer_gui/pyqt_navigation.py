"""Enhanced navigation for PyQtGraph plots with audian-style shortcuts."""

from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QWidget
import pyqtgraph as pg
import numpy as np


class NavigationController:
    """Keyboard navigation controller for PyQtGraph plots.
    
    Shortcuts inspired by audian:
    - Arrow keys: pan left/right
    - Shift+arrows: pan up/down  
    - +/-: zoom in/out horizontally
    - Shift +/-: zoom vertically
    - t/T: zoom out/in horizontally
    - y/Y: zoom out/in vertically
    - Home/End: jump to start/end
    - Space: play/pause
    """
    
    def __init__(self, plot_widget, app_state):
        self.plot = plot_widget
        self.app_state = app_state
        self.vb = plot_widget.plotItem.vb
        
        # Pan/zoom speeds
        self.pan_factor = 0.2  # 20% of view
        self.zoom_factor = 1.3
        
        # Install event filter
        # plot_widget.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() != event.KeyPress:
            return False
            
        key = event.key()
        modifiers = event.modifiers()
        shift = modifiers & Qt.ShiftModifier
        ctrl = modifiers & Qt.ControlModifier
        
        handled = True
        xmin, xmax = self.vb.viewRange()[0]
        ymin, ymax = self.vb.viewRange()[1]
        xrange = xmax - xmin
        yrange = ymax - ymin
        
        # Horizontal navigation
        if key == Qt.Key_Left:
            if shift:  # Fine pan
                self.pan_x(-xrange * 0.05)
            else:  # Normal pan
                self.pan_x(-xrange * self.pan_factor)
                
        elif key == Qt.Key_Right:
            if shift:
                self.pan_x(xrange * 0.05)
            else:
                self.pan_x(xrange * self.pan_factor)
                
        # Vertical navigation
        elif key == Qt.Key_Up and shift:
            self.pan_y(yrange * self.pan_factor)
        elif key == Qt.Key_Down and shift:
            self.pan_y(-yrange * self.pan_factor)
            
        # Zoom
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            if shift:
                self.zoom_y(1.0 / self.zoom_factor)
            else:
                self.zoom_x(1.0 / self.zoom_factor)
                
        elif key == Qt.Key_Minus:
            if shift:
                self.zoom_y(self.zoom_factor)
            else:
                self.zoom_x(self.zoom_factor)
                
        # T/Y shortcuts (audian-style)
        elif key == Qt.Key_T:
            if shift:  # Zoom in
                self.zoom_x(0.5)
            else:  # Zoom out
                self.zoom_x(2.0)
                
        elif key == Qt.Key_Y:
            if shift:  # Zoom in vertically
                self.zoom_y(0.5)
            else:  # Zoom out vertically
                self.zoom_y(2.0)
                
        # Jump navigation
        elif key == Qt.Key_Home:
            self.jump_to_start()
        elif key == Qt.Key_End:
            self.jump_to_end()
            
        # Playback control
        elif key == Qt.Key_Space:
            self.toggle_playback()
            
        # Reset view
        elif key == Qt.Key_R and ctrl:
            self.reset_view()
            
        else:
            handled = False
            
        return handled
        
    def pan_x(self, delta):
        """Pan horizontally by delta."""
        xmin, xmax = self.vb.viewRange()[0]
        
        # Get data bounds if available
        if hasattr(self.app_state, 'ds'):
            time = self.app_state.ds.time.values
            t_min, t_max = time[0], time[-1]
            
            # Clamp panning to data bounds
            new_xmin = max(t_min, xmin + delta)
            new_xmax = min(t_max, xmax + delta)
            
            # Maintain window size
            if new_xmax - new_xmin < xmax - xmin:
                if delta > 0:
                    new_xmax = new_xmin + (xmax - xmin)
                else:
                    new_xmin = new_xmax - (xmax - xmin)
        else:
            new_xmin = xmin + delta
            new_xmax = xmax + delta
            
        self.vb.setXRange(new_xmin, new_xmax, padding=0)
        
    def pan_y(self, delta):
        """Pan vertically by delta."""
        ymin, ymax = self.vb.viewRange()[1]
        self.vb.setYRange(ymin + delta, ymax + delta, padding=0)
        
    def zoom_x(self, factor):
        """Zoom horizontally by factor."""
        xmin, xmax = self.vb.viewRange()[0]
        center = (xmin + xmax) / 2
        new_width = (xmax - xmin) * factor
        
        # Limit zoom
        if hasattr(self.app_state, 'ds'):
            time = self.app_state.ds.time.values
            max_width = time[-1] - time[0]
            new_width = min(new_width, max_width)
            
        self.vb.setXRange(center - new_width/2, center + new_width/2, padding=0)
        
    def zoom_y(self, factor):
        """Zoom vertically by factor."""
        ymin, ymax = self.vb.viewRange()[1]
        center = (ymin + ymax) / 2
        new_height = (ymax - ymin) * factor
        self.vb.setYRange(center - new_height/2, center + new_height/2, padding=0)
        
    def jump_to_start(self):
        """Jump to beginning of data."""
        if hasattr(self.app_state, 'ds'):
            xmin, xmax = self.vb.viewRange()[0]
            window = xmax - xmin
            time = self.app_state.ds.time.values
            self.vb.setXRange(time[0], time[0] + window, padding=0)
            
    def jump_to_end(self):
        """Jump to end of data."""
        if hasattr(self.app_state, 'ds'):
            xmin, xmax = self.vb.viewRange()[0]
            window = xmax - xmin
            time = self.app_state.ds.time.values
            self.vb.setXRange(time[-1] - window, time[-1], padding=0)
            
    def toggle_playback(self):
        """Toggle video/audio playback."""
        if hasattr(self.app_state, 'sync_manager') and self.app_state.sync_manager:
            self.app_state.sync_manager.toggle_play_pause()
                
    def reset_view(self):
        """Reset to default view."""
        self.plot.autoRange()