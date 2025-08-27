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


from plot_utils import plot_ds_variable
import numpy as np
from napari.viewer import Viewer
from qtpy.QtCore import Signal
from movformer_gui.spectrogram import BufferedSpectrogram

# ---- Global defaults for plot settings ----
DEFAULT_WINDOW_SIZE = 3.0
DEFAULT_SPEC_BUFFER = 5.0
DEFAULT_SPEC_YMIN = None
DEFAULT_SPEC_YMAX = None
DEFAULT_YMIN = None
DEFAULT_YMAX = None


class LinePlot(QWidget):
    """Widget to display a line plot and sync napari frame to plot click.
    """

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
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
    # Sync logic removed; handled by AudioVideoSyncPlayback


    def clear_spectrogram_buffer(self) -> None:
        self.buffered_spec.buffer_data = None
        self.buffered_spec.buffer_extent = None
        self.buffered_spec.buffer_t0 = None
        self.buffered_spec.buffer_t1 = None


    # Sync logic removed; handled by AudioVideoSyncPlayback

    def sync_to_viewer_time(self) -> None:
        """Sync plot window to viewer time if outside current xlim."""
        current_frame = self.viewer.dims.current_step[0]
        viewer_time = current_frame * (1 / self.fps)
        xmin, xmax = self.ax.get_xlim()
        if viewer_time < xmin or viewer_time > xmax:
            window_size = getattr(self.app_state, 'window_size', DEFAULT_WINDOW_SIZE)
            t0 = max(viewer_time - window_size / 2, float(self.time[0]))
            t1 = min(viewer_time + window_size / 2, float(self.time[-1]))
            self.updateLinePlot(t0, t1, viewer_time)


    def updateLinePlot(self, t0: Optional[float] = None, t1: Optional[float] = None, viewer_time: Optional[float] = None) -> None:
        self.ax.clear()
        ds_kwargs = self.app_state.get_ds_kwargs()
        t = self.app_state.ds["time"].values
        window_s = getattr(self.app_state, 'window_size', DEFAULT_WINDOW_SIZE)

        # Logic 1: t0 and t1 can be provided user by clicking on timeline
        if t0 is None or t1 is None:
            # Logic 2: t0 and t1 are determined by xlim (which is modified by shortcuts in `meta_widget`). 
            t0_data = float(t[0]) if len(t) > 0 else 0.0
            t1_data = float(t[-1]) if len(t) > 0 else t0_data
            current_xlim = self.ax.get_xlim()
            t0 = max(t0_data, current_xlim[0])
            t1 = min(t1_data, current_xlim[1])

        if getattr(self.app_state, "plot_spectrogram", False) and hasattr(self, "audio_player") and getattr(self.audio_player, "audio_loader", None):
            spec_buffer = getattr(self.app_state, 'spec_buffer', DEFAULT_SPEC_BUFFER)
            try:
                self.buffered_spec.plot_on_axes(
                    self.ax,
                    self.audio_player.audio_loader,
                    t0, t1,
                    window_size=window_s,
                    spec_buffer=spec_buffer
                )
                spec_ymin = getattr(self.app_state, 'spec_ymin', DEFAULT_SPEC_YMIN)
                spec_ymax = getattr(self.app_state, 'spec_ymax', DEFAULT_SPEC_YMAX)
                if spec_ymin is not None and spec_ymax is not None:
                    self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
            except Exception as e:
                raise ValueError(f"Failed to plot spectrogram: {e}")
        else:
            try:
                if hasattr(self.app_state, 'colors_sel'):
                    plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel, self.app_state.colors_sel)
                else:
                    plot_ds_variable(self.ax, self.app_state.ds, ds_kwargs, self.app_state.features_sel)
            except Exception as e:
                raise ValueError(f"Failed to run plot_ds_variable: {e}")

        # Add vertical line of viewer_time
        if viewer_time is not None:
            current_frame = self.viewer.dims.current_step[0]
            viewer_time = current_frame * (1 / self.fps)
            self.ax.axvline(x=viewer_time, color='red', linestyle='--', label='Current Frame')
            
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
    



    # ---- Axes settings application --------------------------------------------

    def apply_axes_from_state(
        self,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
        window_s: Optional[float] = None,
        preserve_xlim: Optional[Tuple[float, float]] = None,
    ) -> None:
        
        
        time = self.app_state.ds["time"].values
        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)


        # Set y-limits
        if is_spectrogram:
            spec_ymin = ymin if ymin is not None else getattr(self.app_state, 'spec_ymin', None)
            spec_ymax = ymax if ymax is not None else getattr(self.app_state, 'spec_ymax', None)
            if spec_ymin is not None and spec_ymax is not None:
                self.ax.set_ylim(float(spec_ymin), float(spec_ymax))
        elif ymin is not None and ymax is not None:
            self.ax.set_ylim(float(ymin), float(ymax))

        # Set x-limits
        if time is not None and len(time) > 0:
            t0, t1 = float(time[0]), float(time[-1])
            window_s = window_s if window_s is not None else DEFAULT_WINDOW_SIZE
            if window_s > 0:
                self.ax.set_xlim(t0, min(t0 + float(window_s), t1))
            elif preserve_xlim and len(preserve_xlim) == 2:
                xmin = max(t0, preserve_xlim[0])
                xmax = min(t1, preserve_xlim[1])
                if xmax > xmin:
                    self.ax.set_xlim(xmin, xmax)

