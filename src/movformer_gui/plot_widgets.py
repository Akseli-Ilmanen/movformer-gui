"""Collapsible widget to control settings for all plots."""

from qtpy.QtWidgets import QFormLayout, QLineEdit, QWidget, QPushButton, QVBoxLayout, QHBoxLayout
from napari.viewer import Viewer

class PlotsWidget(QWidget):
    """Plots controls.

    Keys used in gui_settings.yaml (via app_state):
      - ymin
      - ymax
      - spec_ymin
      - spec_ymax
      - window_size
      - jump_size
    """

    def __init__(self, napari_viewer: Viewer, app_state, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state  # Use the shared app state
        self.viewer = napari_viewer  # Will be set after creation
        self.lineplot = None  # Will be set after creation
        
        
        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Reset button at the top
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        main_layout.addWidget(reset_button)
        
        # Form layout for the controls
        layout = QFormLayout()
        main_layout.addLayout(layout)

        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.spec_ymin_edit = QLineEdit()
        self.spec_ymax_edit = QLineEdit()
        self.window_s_edit = QLineEdit()
        self.jump_size_edit = QLineEdit()
        self.audio_buffer_edit = QLineEdit()
        self.spec_buffer_edit = QLineEdit()

        layout.addRow("Y min (lineplot):", self.ymin_edit)
        layout.addRow("Y max (lineplot):", self.ymax_edit)
        layout.addRow("Y min (spectrogram):", self.spec_ymin_edit)
        layout.addRow("Y max (spectrogram):", self.spec_ymax_edit)
        layout.addRow("Window size (s):", self.window_s_edit)
        layout.addRow("Jump size (s):", self.jump_size_edit)
        layout.addRow("Audio buffer (s):", self.audio_buffer_edit)
        layout.addRow("Spectrogram buffer (x):", self.spec_buffer_edit)

        # Wire events
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.spec_ymin_edit.editingFinished.connect(self._on_edited)
        self.spec_ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)
        self.jump_size_edit.editingFinished.connect(self._on_edited)
        self.audio_buffer_edit.editingFinished.connect(self._on_edited)
        self.spec_buffer_edit.editingFinished.connect(self._on_edited)

        # Load settings from YAML via app_state (handles None values properly)
        self._restore_or_set_default_selections()



        
    def set_lineplot(self, lineplot):
        """Set references to other widgets after creation."""
        self.lineplot = lineplot


        # Connect to app state signals for buffer changes
        self._connect_app_state_signals()
        
        
       # When user adjusts buffer size
    def _connect_app_state_signals(self):
        """Connect to app state signals that should trigger spectrogram buffer clearing."""
        if hasattr(self.app_state, 'spec_buffer_changed'):
            self.app_state.spec_buffer_changed.connect(self._on_spec_buffer_changed)
        if hasattr(self.app_state, 'audio_buffer_changed'):
            self.app_state.audio_buffer_changed.connect(self._on_audio_buffer_changed)

    def _on_spec_buffer_changed(self, value):
        """Handle spectrogram buffer size change."""

        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()

            
    def _on_audio_buffer_changed(self, value):
        """Handle audio buffer size change."""

        if hasattr(self, 'lineplot') and self.lineplot is not None:
            self.lineplot.clear_spectrogram_buffer()


    def _restore_or_set_default_selections(self):
        """Restore selections from app_state or set defaults if missing."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("jump_size", self.jump_size_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = getattr(self.app_state, attr, None)
            if value is None:
                value = self.app_state.get_with_default(attr)
                setattr(self.app_state, attr, value)
            edit.setText("" if value is None else str(value))




    def _parse_float(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None



    def _on_edited(self):
        """Handle when user edits the input fields."""
        edits = {
            "ymin": self.ymin_edit,
            "ymax": self.ymax_edit,
            "spec_ymin": self.spec_ymin_edit,
            "spec_ymax": self.spec_ymax_edit,
            "window_size": self.window_s_edit,
            "jump_size": self.jump_size_edit,
            "audio_buffer": self.audio_buffer_edit,
            "spec_buffer": self.spec_buffer_edit
        }
        values = {}
        for attr, edit in edits.items():
            val = self._parse_float(edit.text())
            if val is None:
                val = self.app_state.get_with_default(attr)
            values[attr] = val
            if self.app_state is not None:
                setattr(self.app_state, attr, val)

        if self.lineplot is not None:
            # Determine which y-limits to use based on current plot type
            is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
            if is_spectrogram:
                # Use spectrogram y-limits for spectrogram mode
                self.lineplot.apply_axes_from_state(values["spec_ymin"], values["spec_ymax"], values["window_size"])
            else:
                # Use line plot y-limits for line plot mode
                self.lineplot.apply_axes_from_state(values["ymin"], values["ymax"], values["window_size"])
            if hasattr(self.lineplot, "canvas"):
                self.lineplot.canvas.draw()
                
                
            # Sync logic removed; will be handled by AudioVideoSync classes


    def _reset_to_defaults(self):
        """Reset all plot values to their defaults and update the plot."""
        for attr, edit in [
            ("ymin", self.ymin_edit),
            ("ymax", self.ymax_edit),
            ("spec_ymin", self.spec_ymin_edit),
            ("spec_ymax", self.spec_ymax_edit),
            ("window_size", self.window_s_edit),
            ("jump_size", self.jump_size_edit),
            ("audio_buffer", self.audio_buffer_edit),
            ("spec_buffer", self.spec_buffer_edit)
        ]:
            value = getattr(self.app_state, attr, None) if self.app_state is not None else None
            if value is None:
                value = self.app_state.get_with_default(attr)
            # Set text field
            edit.setText("" if value is None else str(value))
            # Set app_state attribute if possible
            if self.app_state is not None:
                setattr(self.app_state, attr, value)

        # Trigger plot update
        self._on_edited()



    def _adjust_ylim(self, percentage):
        """Adjust the y-axis limits by a percentage of the current range."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        # Determine if we're currently showing spectrogram or line plot
        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
        
        if is_spectrogram:
            # Adjust spectrogram y-limits
            ax = self.lineplot.ax
            current_ymin, current_ymax = ax.get_ylim()
            current_range = current_ymax - current_ymin
            adjustment = current_range * percentage
            
            new_ymax = current_ymax + adjustment
            new_ymin = current_ymin - adjustment
            
            # Update app state for spectrogram
            self.app_state.spec_ymin = new_ymin
            self.app_state.spec_ymax = new_ymax
            
            # Update the plot
            ax.set_ylim(new_ymin, new_ymax)
            self.lineplot.canvas.draw()
            
            # Update the plot widgets UI
            self.spec_ymin_edit.setText(f"{new_ymin:.3f}")
            self.spec_ymax_edit.setText(f"{new_ymax:.3f}")
        else:
            # Adjust line plot y-limits (existing logic)
            ax = self.lineplot.ax
            current_ymin, current_ymax = ax.get_ylim()
            current_range = current_ymax - current_ymin
            adjustment = current_range * percentage
            
            new_ymax = current_ymax + adjustment
            new_ymin = current_ymin - adjustment
            
            # Update app state for line plot
            self.app_state.ymin = new_ymin
            self.app_state.ymax = new_ymax
            
            # Update the plot
            ax.set_ylim(new_ymin, new_ymax)
            self.lineplot.canvas.draw()
            
            # Update the plot widgets UI
            self.ymin_edit.setText(f"{new_ymin:.3f}")
            self.ymax_edit.setText(f"{new_ymax:.3f}")

    # Sync logic removed; handled by AudioVideoSync classes


    def _shift_plot(self, window_fraction):
        """Shift the plot view by a fraction of the current window size."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        ax = self.lineplot.ax
        current_xmin, current_xmax = ax.get_xlim()
        current_window = current_xmax - current_xmin
        shift_amount = current_window * window_fraction
        
        # Get the full time range to prevent shifting beyond data bounds
        if hasattr(self.app_state, 'ds') and self.app_state.ds is not None:
            full_time = self.app_state.ds["time"].values
            time_min, time_max = float(full_time[0]), float(full_time[-1])
            
            new_xmin = current_xmin + shift_amount
            new_xmax = current_xmax + shift_amount
            
            # Clamp to data bounds
            if new_xmin < time_min:
                new_xmin = time_min
                new_xmax = new_xmin + current_window
            elif new_xmax > time_max:
                new_xmax = time_max
                new_xmin = new_xmax - current_window
            
            # Update the plot
            ax.set_xlim(new_xmin, new_xmax)
            self.lineplot.canvas.draw()

            # Clear spectrogram buffer when shifting significantly
            if hasattr(self.lineplot, 'clear_spectrogram_buffer'):
                self.lineplot.clear_spectrogram_buffer()

            # Sync logic removed; handled by AudioVideoSync classes


    def _shift_yrange(self, percentage):
        """Shift the y-axis range up or down by a percentage of the current range."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        # Determine if we're currently showing spectrogram or line plot
        is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
        
        ax = self.lineplot.ax
        current_ymin, current_ymax = ax.get_ylim()
        current_range = current_ymax - current_ymin
        shift_amount = current_range * percentage
        
        new_ymin = current_ymin + shift_amount
        new_ymax = current_ymax + shift_amount
        
        if is_spectrogram:
            # Update app state for spectrogram
            self.app_state.spec_ymin = new_ymin
            self.app_state.spec_ymax = new_ymax
            
            # Update the plot widgets UI
            self.spec_ymin_edit.setText(f"{new_ymin:.3f}")
            self.spec_ymax_edit.setText(f"{new_ymax:.3f}")
        else:
            # Update app state for line plot
            self.app_state.ymin = new_ymin
            self.app_state.ymax = new_ymax
            
            # Update the plot widgets UI
            self.ymin_edit.setText(f"{new_ymin:.3f}")
            self.ymax_edit.setText(f"{new_ymax:.3f}")
        
        # Update the plot
        ax.set_ylim(new_ymin, new_ymax)
        self.lineplot.canvas.draw()

    # Sync logic removed; handled by AudioVideoSync classes

        



    def _adjust_window_size(self, factor):
        """Adjust the window size by a multiplication factor."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        # Get current window size from app state or calculate from current view
        current_window_size = getattr(self.app_state, 'window_size', None)
        
        if current_window_size is None:
            # Calculate from current view if not set in app state
            ax = self.lineplot.ax
            current_xmin, current_xmax = ax.get_xlim()
            current_window_size = current_xmax - current_xmin
        
        new_window_size = current_window_size * factor
        
        # Update app state (ensure it's a Python float)
        self.app_state.window_size = float(new_window_size)
        


        # Apply the new window size
        if self.lineplot is not None:
            # Determine which y-limits to use based on current plot type
            is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
            if is_spectrogram:
                ymin = getattr(self.app_state, 'spec_ymin', None)
                ymax = getattr(self.app_state, 'spec_ymax', None)
            else:
                ymin = getattr(self.app_state, 'ymin', None)
                ymax = getattr(self.app_state, 'ymax', None)
                
            self.lineplot.apply_axes_from_state(ymin, ymax, new_window_size)
            if hasattr(self.lineplot, "canvas"):
                self.lineplot.canvas.draw()
        
        # Update the plot widgets UI
        self.window_s_edit.setText(f"{new_window_size:.3f}")

    # Sync logic removed; handled by AudioVideoSync classes

    def _jump_plot(self, direction):
        """Jump the plot view by the configured jump size in seconds."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        # Get jump size from app state, default to 1.0 seconds
        jump_size = getattr(self.app_state, 'jump_size', 1.0)
        if jump_size is None:
            jump_size = 1.0
            
        # Apply direction (-1 for left, +1 for right)
        jump_amount = jump_size * direction
        
        ax = self.lineplot.ax
        current_xmin, current_xmax = ax.get_xlim()
        current_window = current_xmax - current_xmin
        
        new_xmin = current_xmin + jump_amount
        new_xmax = current_xmax + jump_amount
        
        # Get the full time range to prevent jumping beyond data bounds
        if hasattr(self.app_state, 'ds') and self.app_state.ds is not None:
            full_time = self.app_state.ds["time"].values
            time_min, time_max = float(full_time[0]), float(full_time[-1])
            
            # Clamp to data bounds
            if new_xmin < time_min:
                new_xmin = time_min
                new_xmax = new_xmin + current_window
            elif new_xmax > time_max:
                new_xmax = time_max
                new_xmin = new_xmax - current_window
            
            # Update the plot
            ax.set_xlim(new_xmin, new_xmax)
            self.lineplot.canvas.draw()

            # Sync logic removed; handled by AudioVideoSync classes
