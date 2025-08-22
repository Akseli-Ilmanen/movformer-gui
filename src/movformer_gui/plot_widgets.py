"""Collapsible widget to control settings for all plots."""

from qtpy.QtWidgets import QFormLayout, QLineEdit, QWidget, QPushButton, QVBoxLayout, QHBoxLayout

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

    def __init__(self, app_state, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state  # Use the shared app state
        self.data_widget = None
        self.lineplot = None  # Will be set after creation
        self.labels_widget = None  # Will be set after creation
        
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

        self.ymin_edit.setPlaceholderText("auto")
        self.ymax_edit.setPlaceholderText("auto")
        self.spec_ymin_edit.setPlaceholderText("auto")
        self.spec_ymax_edit.setPlaceholderText("auto")
        self.window_s_edit.setPlaceholderText("full")
        self.jump_size_edit.setPlaceholderText("1.0")
        self.audio_buffer_edit.setPlaceholderText("60.0")
        self.spec_buffer_edit.setPlaceholderText("5.0")

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
        if self.app_state is not None:
            self._restore_or_set_default_selections()

    def set_lineplot(self, lineplot):
        """Set the lineplot reference after creation."""
        self.lineplot = lineplot

    def set_labels_widget(self, labels_widget):
        """Set the labels_widget reference after creation."""
        self.labels_widget = labels_widget

    def set_data_widget(self, data_widget):
        """Set the data_widget reference after creation."""
        self.data_widget = data_widget

    def _sync_napari_frame(self):
        """Sync napari viewer to the current plot center time."""
        if (not self.app_state.ready or 
            not hasattr(self, 'lineplot') or 
            self.lineplot is None or 
            self.labels_widget is None):
            return
        
        try:
            # Get current plot x-axis limits
            ax = self.lineplot.ax
            xmin_time, _ = ax.get_xlim()
            
            # Convert time to frame index using dataset fps
            if hasattr(self.app_state, 'ds') and self.app_state.ds is not None:
                fps = self.app_state.ds.fps
                frame_idx = int(xmin_time * fps)
                
                # Make sure frame_idx is within bounds
                if hasattr(self.app_state.ds, 'time'):
                    max_frames = len(self.app_state.ds.time.values)
                    frame_idx = max(0, min(frame_idx, max_frames - 1))
                    
                    # Update napari viewer frame
                    self.labels_widget._set_frame(frame_idx)
        except Exception as e:
            print(f"Error syncing napari frame: {e}")

    

    def _parse_float(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _restore_or_set_default_selections(self):
        """Restore selections from app_state or set defaults if missing."""
        for attr, edit, default in [
            ("ymin", self.ymin_edit, ""),
            ("ymax", self.ymax_edit, ""),
            ("spec_ymin", self.spec_ymin_edit, ""),
            ("spec_ymax", self.spec_ymax_edit, ""),
            ("window_size", self.window_s_edit, ""),
            ("jump_size", self.jump_size_edit, "0.2"),
            ("audio_buffer", self.audio_buffer_edit, "60.0"),
            ("spec_buffer", self.spec_buffer_edit, "5.0")
        ]:
            value = getattr(self.app_state, attr, None)
            if value is None and attr in ["jump_size", "audio_buffer", "spec_buffer"]:
                edit.setText(default)
            else:
                edit.setText("" if value is None else str(value))


    def _on_edited(self):
        """Handle when user edits the input fields."""
        ymin = self._parse_float(self.ymin_edit.text())
        ymax = self._parse_float(self.ymax_edit.text())
        spec_ymin = self._parse_float(self.spec_ymin_edit.text())
        spec_ymax = self._parse_float(self.spec_ymax_edit.text())
        window_size = self._parse_float(self.window_s_edit.text())
        jump_size = self._parse_float(self.jump_size_edit.text())
        audio_buffer = self._parse_float(self.audio_buffer_edit.text())
        spec_buffer = self._parse_float(self.spec_buffer_edit.text())
        
        # Default jump_size to 0.2 if None or invalid
        if jump_size is None:
            jump_size = 0.2
        # Default audio_buffer to 60.0 if None or invalid
        if audio_buffer is None:
            audio_buffer = 60.0
        # Default spec_buffer to 5.0 if None or invalid
        if spec_buffer is None:
            spec_buffer = 5.0

        # Update app state
        if self.app_state is not None:
            self.app_state.ymin = ymin
            self.app_state.ymax = ymax
            self.app_state.spec_ymin = spec_ymin
            self.app_state.spec_ymax = spec_ymax
            self.app_state.window_size = window_size
            self.app_state.jump_size = jump_size
            self.app_state.audio_buffer = audio_buffer
            self.app_state.spec_buffer = spec_buffer

        if self.lineplot is not None:
            # Determine which y-limits to use based on current plot type
            is_spectrogram = getattr(self.app_state, "plot_spectrogram", False)
            if is_spectrogram:
                # Use spectrogram y-limits for spectrogram mode
                self.lineplot.apply_axes_from_state(spec_ymin, spec_ymax, window_size)
            else:
                # Use line plot y-limits for line plot mode
                self.lineplot.apply_axes_from_state(ymin, ymax, window_size)
                
            if hasattr(self.lineplot, "canvas"):
                self.lineplot.canvas.draw()
            
            # Sync napari viewer frame after plot update
            self._sync_napari_frame()

    def _reset_to_defaults(self):
        """Reset all plot values to their defaults and update the plot."""
        # Clear all text fields to defaults
        self.ymin_edit.clear()
        self.ymax_edit.clear()
        self.spec_ymin_edit.clear()
        self.spec_ymax_edit.clear()
        self.window_s_edit.clear()
        self.jump_size_edit.setText("0.2")  # Set jump_size to default
        self.audio_buffer_edit.setText("60.0")  # Set audio_buffer to default
        self.spec_buffer_edit.setText("5.0")  # Set spec_buffer to default
        
        # Update app state to None (which means 'auto' for most values)
        if self.app_state is not None:
            self.app_state.ymin = None
            self.app_state.ymax = None
            self.app_state.spec_ymin = None
            self.app_state.spec_ymax = None
            self.app_state.window_size = None
            self.app_state.jump_size = 0.2
            self.app_state.audio_buffer = 60.0
            self.app_state.spec_buffer = 5.0
        
        # Trigger plot update
        self._on_edited()
        
        # Update data widget plot if available
        if self.data_widget is not None:
            self.data_widget._update_plot()

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

        # Sync napari viewer frame after plot update
        self._sync_napari_frame()


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

            # Sync napari viewer frame after plot update
            self._sync_napari_frame()

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

        # Sync napari viewer frame after plot update
        self._sync_napari_frame()

        



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
        
        # Clear spectrogram buffer when window size changes significantly
        if self.lineplot is not None and hasattr(self.lineplot, 'clear_spectrogram_buffer'):
            self.lineplot.clear_spectrogram_buffer()
        
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

        # Sync napari viewer frame after plot update
        self._sync_napari_frame()

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

            # Clear spectrogram buffer when jumping significantly
            if hasattr(self.lineplot, 'clear_spectrogram_buffer'):
                self.lineplot.clear_spectrogram_buffer()

            # Sync napari viewer frame after plot update
            self._sync_napari_frame()
