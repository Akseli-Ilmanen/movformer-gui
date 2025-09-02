"""Enhanced time axis with intelligent formatting like audian."""

import pyqtgraph as pg
from datetime import datetime, timedelta
import numpy as np


class EnhancedTimeAxisItem(pg.AxisItem):
    """Time axis with intelligent formatting based on scale.
    
    Features:
    - Auto-formats as seconds, m:s, or h:m:s based on range
    - Supports absolute time display
    - Handles file boundaries for multi-file recordings
    """
    
    def __init__(self, orientation='bottom', start_time=None, file_boundaries=None):
        super().__init__(orientation)
        self.start_time = start_time  # datetime object for absolute time
        self.file_boundaries = file_boundaries or []
        self.time_mode = 'relative'  # 'relative', 'absolute', or 'file_relative'
        
    def set_time_mode(self, mode):
        """Set time display mode."""
        self.time_mode = mode
        self.picture = None  # Force redraw
        
    def tickSpacing(self, minVal, maxVal, size):
        """Calculate optimal tick spacing."""
        if minVal == maxVal:
            return []
            
        time_range = maxVal - minVal
        
        # Determine optimal major tick spacing
        if time_range < 0.001:  # Less than 1ms
            spacings = [0.0001, 0.0002, 0.0005, 0.001]
        elif time_range < 1:  # Less than 1 second
            spacings = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
        elif time_range < 60:  # Less than 1 minute
            spacings = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 20, 30]
        elif time_range < 3600:  # Less than 1 hour
            spacings = [10, 30, 60, 120, 300, 600, 900, 1200, 1800]
        else:  # Hours
            spacings = [600, 1200, 1800, 3600, 7200, 10800, 14400, 21600]
            
        # Find optimal spacing for available pixels
        pixels_per_label = 80  # Minimum pixels between labels
        max_ticks = max(2, size // pixels_per_label)
        
        for spacing in spacings:
            n_ticks = (maxVal - minVal) / spacing
            if n_ticks <= max_ticks:
                # Minor ticks at 1/5 of major spacing
                minor_spacing = spacing / 5
                return [(spacing, 0), (minor_spacing, 0)]
                
        # Fallback
        spacing = time_range / 5
        return [(spacing, 0), (spacing/5, 0)]
        
    def tickStrings(self, values, scale, spacing):
        """Format tick strings based on time range and mode."""
        if len(values) == 0:
            return []
            
        strings = []
        
        for value in values:
            if self.time_mode == 'absolute' and self.start_time:
                # Show absolute time
                time = self.start_time + timedelta(seconds=value)
                strings.append(self._format_absolute_time(time, spacing))
                
            elif self.time_mode == 'file_relative' and self.file_boundaries:
                # Show time relative to file start
                file_idx, file_time = self._get_file_relative_time(value)
                strings.append(self._format_relative_time(file_time, spacing, file_idx))
                
            else:
                # Show relative time from start
                strings.append(self._format_relative_time(value, spacing))
                
        return strings
        
    def _format_relative_time(self, seconds, spacing, file_idx=None):
        """Format time in appropriate units."""
        prefix = f"F{file_idx}:" if file_idx is not None else ""
        
        if spacing < 0.001:
            # Microseconds precision
            return f"{prefix}{seconds:.6f}s"
        elif spacing < 0.01:
            # Milliseconds precision  
            return f"{prefix}{seconds:.3f}s"
        elif seconds < 60 and spacing < 1:
            # Seconds with decimals
            return f"{prefix}{seconds:.1f}s"
        elif seconds < 60:
            # Seconds
            return f"{prefix}{int(seconds)}s"
        elif seconds < 3600:
            # Minutes:seconds
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{prefix}{mins}:{secs:02d}"
        else:
            # Hours:minutes:seconds
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{prefix}{hours}:{mins:02d}:{secs:02d}"
            
    def _format_absolute_time(self, time, spacing):
        """Format absolute time."""
        if spacing < 1:
            # Include subseconds
            return time.strftime("%H:%M:%S.%f")[:-3]
        elif spacing < 60:
            # Seconds precision
            return time.strftime("%H:%M:%S")
        else:
            # Minutes precision
            return time.strftime("%H:%M")
            
    def _get_file_relative_time(self, value):
        """Get file index and relative time within file."""
        for i, boundary in enumerate(self.file_boundaries):
            if value < boundary:
                if i == 0:
                    return 0, value
                else:
                    return i, value - self.file_boundaries[i-1]
        # Last file
        if self.file_boundaries:
            return len(self.file_boundaries), value - self.file_boundaries[-1]
        return 0, value