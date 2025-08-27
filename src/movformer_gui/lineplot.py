"""Widget for displaying a line plot and syncing napari frame to plot click.

Provides time-synced line plotting. Axes settings (y-limits and x window size
in seconds) are persisted in ``gui_state.yaml`` and applied from a separate
collapsible widget in the Meta widget.
"""

from typing import Optional, Tuple, Any
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from qtpy.QtCore import Signal, QTimer

from plot_utils import plot_ds_variable
import numpy as np
from napari.viewer import Viewer
from movformer_gui.spectrogram import BufferedSpectrogram


class LinePlot(QWidget):
    """Widget to display a line plot and sync napari frame to plot click."""

    plot_clicked = Signal(object)

    def __init__(self, napari_viewer: Viewer, app_state: Optional[Any] = None, audio_player: Optional[Any] = None) -> None:
        super().__init__()
        self.viewer = napari_viewer
        self.app_state = app_state
        self.time = None
        self.plots_widget = None
        self.fig = Figure(figsize=(8, 12))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.buffered_spec = BufferedSpectrogram(app_state)
        
        # Debounce timer for smooth updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._perform_sync_update)
        self.update_timer.setSingleShot(True)
        self.pending_sync_time = None
        
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def clear_spectrogram_buffer(self) -> None:
        """Clear the spectrogram buffer and reset state."""
        self.buffered_spec.clear_buffer()
        self.buffered_spec.current_audio_path = None

    def sync_to_viewer_time(self) -> None:
        """Sync plot window to viewer time if outside current xlim."""
        if not hasattr(self.app_state, 'current_time') or not self.app_state.sync_state == "video_to_lineplot":
            return

        curr_time = self.app_state.current_time
        
        # Get current limits
        try:
            xmin, xmax = self.ax.get_xlim()
        except:
            # Axes might not be initialized yet
            return
        
        # Check if viewer time is outside current window
        if curr_time < xmin or curr_time > xmax:
            window_size = self.app_state.get_with_default("window_size")
            
            # Get time data bounds
            if hasattr(self.app_state, 'ds') and 'time' in self.app_state.ds:
                time_data = self.app_state.ds["time"].values
                t0 = max(curr_time - window_size / 2, float(time_data[0]))
                t1 = min(curr_time + window_size / 2, float(time_data[-1]))
            else:
                t0 = curr_time - window_size / 2
                t1 = curr_time + window_size / 2
                
            self.updateLinePlot(t0, t1, curr_time)
        else:
            # Just update the marker
            self.update_current_time_marker(curr_time)

    def request_sync_update(self) -> None:
        """Request a sync update with debouncing to prevent excessive redraws."""
        self.pending_sync_time = self.app_state.current_time
        
        # Cancel pending update and schedule new one
        self.update_timer.stop()
        self.update_timer.start(50)  # 50ms debounce delay
        
    def _perform_sync_update(self) -> None:
        """Perform the actual sync update after debounce delay."""
        if self.pending_sync_time is None:
            return
            
        viewer_time = self.pending_sync_time
        
        try:
            xmin, xmax = self.ax.get_xlim()
        except:
            return
            
        # Check if we need to pan the window
        window_size = self.app_state.get_with_default("window_size")
        margin = window_size * 0.1  # 10% margin before panning
        
        if viewer_time < xmin + margin or viewer_time > xmax - margin:
            # Smooth panning: keep some context
            if viewer_time < xmin + margin:
                # Panning left
                new_t0 = viewer_time - margin
                new_t1 = new_t0 + window_size
            else:
                # Panning right
                new_t1 = viewer_time + margin
                new_t0 = new_t1 - window_size
                
            # Clamp to data bounds
            if hasattr(self.app_state, 'ds') and 'time' in self.app_state.ds:
                time_data = self.app_state.ds["time"].values
                new_t0 = max(float(time_data[0]), new_t0)
                new_t1 = min(float(time_data[-1]), new_t1)
            
            self.updateLinePlot(new_t0, new_t1, viewer_time)
        else:
            # Just update marker
            self.update_current_time_marker(viewer_time)
            
        self.pending_sync_time = None


    def update_current_time_marker(self, viewer_time: float) -> None:
        """Update only the current time marker without redrawing entire plot.
        
        This is more efficient when the plot data doesn't need to change,
        only the position marker needs updating.
        """
        # Remove old vertical line if it exists
        for line in self.ax.lines:
            if line.get_label() == 'Current Frame':
                line.remove()
                break
        
        # Add new vertical line
        if viewer_time is not None:
            self.ax.axvline(x=viewer_time, color='red', linestyle='--', label='Current Frame')
        
        # Redraw only the artists that changed (more efficient)
        self.canvas.draw_idle()

    def updateLinePlot(self, t0: Optional[float] = None, t1: Optional[float] = None, 
                       viewer_time: Optional[float] = None) -> None:
        """Update the line plot with current data and time window."""
        self.ax.clear()
        
        if not hasattr(self.app_state, 'ds'):
            return
            
        ds_kwargs = self.app_state.get_ds_kwargs()
        t = self.app_state.ds["time"].values
        window_size = self.app_state.get_with_default("window_size")

        # Logic 1: t0 and t1 can be provided by user clicking on timeline
        if t0 is None or t1 is None:
            # Logic 2: t0 and t1 are determined by xlim
            t0_data = float(t[0]) if len(t) > 0 else 0.0
            t1_data = float(t[-1]) if len(t) > 0 else t0_data
            current_xlim = self.ax.get_xlim()
            t0 = max(t0_data, current_xlim[0])
            t1 = min(t1_data, current_xlim[1])

        # Check if we should plot spectrogram
        if (getattr(self.app_state, "plot_spectrogram", False) and 
            hasattr(self.app_state, 'audio_path') and 
            self.app_state.audio_path):
            
            spec_buffer = self.app_state.get_with_default("spec_buffer")
            try:
                # Use audio_path directly instead of audio_loader
                self.buffered_spec.plot_on_axes(
                    self.ax,
                    self.app_state.audio_path,  # Pass path, not loader
                    t0, t1,
                    window_size=window_size,
                    spec_buffer=spec_buffer
                )
                
                # Apply y-limits for spectrogram
                spec_ymin = self.app_state.get_with_default("spec_ymin")
                spec_ymax = self.app_state.get_with_default("spec_ymax")
                
                if spec_ymin is not None and spec_ymax is not None:
                    self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
                    
            except Exception as e:
                print(f"Failed to plot spectrogram: {e}")
                # Fall back to regular plot
                self._plot_regular(ds_kwargs)
        else:
            self._plot_regular(ds_kwargs)

        # Add vertical line for current viewer time
        if viewer_time is not None:
            self.ax.axvline(x=viewer_time, color='red', linestyle='--', label='Current Frame')
        elif hasattr(self.app_state, 'current_time'):
            # Use current time from app_state if no viewer_time provided
            self.ax.axvline(x=self.app_state.current_time, color='red', 
                          linestyle='--', label='Current Frame')
            
        self.apply_axes_from_state(preserve_xlim=(t0, t1))
        self.canvas.draw()
        
        # Update buffer when plot window changes and sync_state is lineplot_to_video
        if (hasattr(self.app_state, 'audio_video_sync') and 
            self.app_state.audio_video_sync and 
            getattr(self.app_state, 'sync_state') == 'lineplot_to_video'):
            sync_controller = self.app_state.audio_video_sync
            if hasattr(sync_controller, 'media_buffer'):
                xlim = (t0, t1)
                start_time, end_time = sync_controller.media_buffer.get_buffer_window(
                    'lineplot_to_video', xlim=xlim
                )
                sync_controller.media_buffer.prepare_audio_buffer(start_time, end_time)

    def _plot_regular(self, ds_kwargs: dict) -> None:
        """Helper method to plot regular (non-spectrogram) data."""
        try:
            if hasattr(self.app_state, 'colors_sel') and self.app_state.colors_sel != "None":
                plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, 
                               self.app_state.features_sel, self.app_state.colors_sel)
            else:
                plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, 
                               self.app_state.features_sel)
        except Exception as e:
            print(f"Failed to run plot_ds_variable: {e}")

    def apply_axes_from_state(
        self,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
        window_s: Optional[float] = None,
        preserve_xlim: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Apply axis limits from app state or provided values."""
        
        if not hasattr(self.app_state, 'ds'):
            return
            
        time = self.app_state.ds["time"].values
        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)

        # Set y-limits
        if is_spectrogram:
            spec_ymin = self.app_state.get_with_default("spec_ymin")
            spec_ymax = self.app_state.get_with_default("spec_ymax")
            if spec_ymin is not None and spec_ymax is not None:
                self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
        else:
            # Use regular y-limits
            ymin_val = self.app_state.get_with_default("ymin")
            ymax_val = self.app_state.get_with_default("ymax")
            if ymin_val is not None and ymax_val is not None:
                self.ax.set_ylim(float(ymin_val), float(ymax_val))

        # Set x-limits
        if time is not None and len(time) > 0:
            t0, t1 = float(time[0]), float(time[-1])
            
            if preserve_xlim and len(preserve_xlim) == 2:
                # Use provided xlim
                xmin = max(t0, preserve_xlim[0])
                xmax = min(t1, preserve_xlim[1])
                if xmax > xmin:
                    self.ax.set_xlim(xmin, xmax)
            else:
                # Use window size
                window_size = self.app_state.get_with_default("window_size")
                if window_size > 0:
                    # Set initial window at start of data
                    self.ax.set_xlim(t0, min(t0 + float(window_size), t1))