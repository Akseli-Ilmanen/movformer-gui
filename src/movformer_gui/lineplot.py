"""Widget for displaying a line plot and syncing napari frame to plot click.

Provides time-synced line plotting. Axes settings (y-limits and x window size
in seconds) are persisted in ``gui_state.yaml`` and applied from a separate
collapsible widget in the Meta widget.
"""


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from qtpy.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from plot_utils import plot_ds_variable
import numpy as np
from napari.viewer import Viewer
from qtpy.QtCore import Signal
from movformer_gui.spectrogram import Spectrogram, BufferedSpectrogram


class LinePlot(QWidget):
    """Widget to display a line plot and sync napari frame to plot click.
    """
    plot_clicked = Signal(object)  # Emitted with event or time index

    def __init__(self, napari_viewer: Viewer, app_state=None):
        """Initialize the plot widget with napari viewer and app_state."""
        super().__init__()
        self.viewer = napari_viewer
        self.app_state = app_state
        self.time = None  # Will be set when data is loaded
        self.plots_widget = None  # Will be set after creation
        self.fig = Figure(figsize=(8, 3))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)    

        # Click handling is connected by the DataWidget after construction
        
        # Initialize buffered spectrogram
        self.buffered_spec = BufferedSpectrogram()

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def set_plots_widget(self, plots_widget):
        """Set the plots_widget reference after creation."""
        self.plots_widget = plots_widget

    def clear_spectrogram_buffer(self):
        """Clear the spectrogram buffer to force recomputation."""
        if hasattr(self, 'buffered_spec'):
            self.buffered_spec.buffer_data = None
            self.buffered_spec.buffer_extent = None
            self.buffered_spec.buffer_t0 = None
            self.buffered_spec.buffer_t1 = None


    def updateLinePlot(self):
        """Update the plot with data from ds."""
        # Store current xlim values before clearing to preserve view position
        current_xlim = self.ax.get_xlim() if hasattr(self.ax, 'get_xlim') else None
        
        self.ax.clear()

        ds_kwargs = self.app_state.get_ds_kwargs()

        if getattr(self.app_state, "plot_spectrogram", False) and hasattr(self, "audio_player") and getattr(self.audio_player, "audio_loader", None):
            # Get buffer settings from app state
            spec_buffer = getattr(self.app_state, 'spec_buffer', 5.0)
            window_s = self.app_state.window_size
            
            # Determine time window for spectrogram display
            t = self.app_state.ds["time"].values
            t0 = float(t[0]) if len(t) > 0 else 0.0
            t1 = float(t[-1]) if len(t) > 0 else t0
            
            # If we have preserved xlim values, use them for the spectrogram range
            if current_xlim is not None and len(current_xlim) == 2:
                preserved_t0, preserved_t1 = current_xlim
                # Ensure the preserved range is within data bounds
                preserved_t0 = max(t0, preserved_t0)
                preserved_t1 = min(t1, preserved_t1)
                if preserved_t1 > preserved_t0:
                    t0, t1 = preserved_t0, preserved_t1
            
            # Apply window_size constraint if set
            if window_s is not None and window_s > 0 and t1 - t0 > window_s:
                t1 = t0 + float(window_s)

            # Plot spectrogram using buffered system
            try:
                # Use buffered spectrogram with configurable buffer size
                im = self.buffered_spec.plot_on_axes(
                    self.ax, 
                    self.audio_player.audio_loader, 
                    t0, t1, 
                    window_size=window_s,
                    spec_buffer=spec_buffer
                )
                
                # Apply spectrogram-specific y-limits if set
                spec_ymin = getattr(self.app_state, 'spec_ymin', None)
                spec_ymax = getattr(self.app_state, 'spec_ymax', None)
                if spec_ymin is not None and spec_ymax is not None:
                    self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
                    
            except Exception as e:
                print(f"Buffered spectrogram failed, falling back to simple spectrogram: {e}")
                try:
                    # Fallback to simple spectrogram
                    spec = Spectrogram()
                    im = spec.plot_on_axes(self.ax, self.audio_player.audio_loader, t0, t1)
                    
                    # Apply spectrogram-specific y-limits if set
                    spec_ymin = getattr(self.app_state, 'spec_ymin', None)
                    spec_ymax = getattr(self.app_state, 'spec_ymax', None)
                    if spec_ymin is not None and spec_ymax is not None:
                        self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
                except Exception as e2:
                    print(f"Simple spectrogram also failed, falling back to line plot: {e2}")
                    # Fallback to normal plot if spectrogram fails
                    from plot_utils import plot_ds_variable
                    if hasattr(self.app_state, 'colors_sel'):
                        plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel, self.app_state.colors_sel)
                    else:
                        plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel)
        else:
            # Normal line plot
            from plot_utils import plot_ds_variable
            if hasattr(self.app_state, 'colors_sel'):
                plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel, self.app_state.colors_sel)
            else:
                plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel)

        # Apply any user-specified axes settings from persisted state
        # Pass current_xlim to preserve view position unless explicitly overridden
        self.apply_axes_from_state(preserve_xlim=current_xlim)
        self.canvas.draw()

        # Sync napari viewer frame after plot update
        if hasattr(self, 'plots_widget') and self.plots_widget is not None:
            self.plots_widget._sync_napari_frame()



    # ---- Axes settings application --------------------------------------------
    def apply_axes_from_state(self, ymin=None, ymax=None, window_s=None, preserve_xlim=None):
        """Apply axes limits from persisted state to the matplotlib Axes."""

        self.time = self.app_state.ds["time"].values

        # Apply y-limits based on current plot type
        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
        
        if is_spectrogram:
            # Use spectrogram y-limits if provided
            if ymin is None and ymax is None:
                spec_ymin = getattr(self.app_state, 'spec_ymin', None)
                spec_ymax = getattr(self.app_state, 'spec_ymax', None)
                if spec_ymin is not None and spec_ymax is not None:
                    self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
            else:
                # Direct override from parameters
                if ymin is not None and ymax is not None:
                    self.ax.set_ylim(float(ymin), float(ymax))
        else:
            # Use line plot y-limits if provided
            if ymin is not None and ymax is not None:
                self.ax.set_ylim(float(ymin), float(ymax))
        
        # Handle x-axis limits
        window_s_f = float(window_s) if window_s is not None else None
        if self.time is not None and window_s_f is not None and window_s_f > 0:
            # Explicit window size override - use it (this takes precedence over preserved xlim)
            t0 = float(self.time[0])
            t1 = float(self.time[-1])
            end = min(t0 + window_s_f, t1)
            self.ax.set_xlim(t0, end)
        elif preserve_xlim is not None and len(preserve_xlim) == 2:
            # Preserve previous xlim values to maintain view position across plot mode switches
            xmin, xmax = preserve_xlim
            # Ensure the preserved limits are within data bounds
            if self.time is not None and len(self.time) > 0:
                t0, t1 = float(self.time[0]), float(self.time[-1])
                xmin = max(t0, xmin)
                xmax = min(t1, xmax)
                if xmax > xmin:  # Only set if valid range
                    self.ax.set_xlim(xmin, xmax)

        # Sync napari viewer frame after axes changes
        if hasattr(self, 'plots_widget') and self.plots_widget is not None:
            self.plots_widget._sync_napari_frame()

