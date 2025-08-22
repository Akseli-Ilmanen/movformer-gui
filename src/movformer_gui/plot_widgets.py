"""Collapsible widget to control settings for all plots."""

from qtpy.QtWidgets import QFormLayout, QLineEdit, QWidget

class PlotsWidget(QWidget):
    """Plots controls.

    Keys used in gui_settings.yaml (via app_state):
      - ymin
      - ymax
      - window_size
      - jump_size
    """

    def __init__(self, app_state, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state  # Use the shared app state
        self.lineplot = None  # Will be set after creation
        self.labels_widget = None  # Will be set after creation

        layout = QFormLayout()
        self.setLayout(layout)

        self.ymin_edit = QLineEdit()
        self.ymax_edit = QLineEdit()
        self.window_s_edit = QLineEdit()
        self.jump_size_edit = QLineEdit()

        self.ymin_edit.setPlaceholderText("auto")
        self.ymax_edit.setPlaceholderText("auto")
        self.window_s_edit.setPlaceholderText("full")
        self.jump_size_edit.setPlaceholderText("1.0")

        layout.addRow("Y min:", self.ymin_edit)
        layout.addRow("Y max:", self.ymax_edit)
        layout.addRow("Window size (s):", self.window_s_edit)
        layout.addRow("Jump size (s):", self.jump_size_edit)

        # Wire events
        self.ymin_edit.editingFinished.connect(self._on_edited)
        self.ymax_edit.editingFinished.connect(self._on_edited)
        self.window_s_edit.editingFinished.connect(self._on_edited)
        self.jump_size_edit.editingFinished.connect(self._on_edited)

        # Load settings from YAML via app_state (handles None values properly)
        if self.app_state is not None:
            self._restore_or_set_default_selections()

    def set_lineplot(self, lineplot):
        """Set the lineplot reference after creation."""
        self.lineplot = lineplot

    def set_labels_widget(self, labels_widget):
        """Set the labels_widget reference after creation."""
        self.labels_widget = labels_widget

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
            ("window_size", self.window_s_edit, ""),
            ("jump_size", self.jump_size_edit, "0.2")
        ]:
            value = getattr(self.app_state, attr, None)
            if value is None and attr == "jump_size":
                edit.setText(default)
            else:
                edit.setText("" if value is None else str(value))


    def _on_edited(self):
        """Handle when user edits the input fields."""
        ymin = self._parse_float(self.ymin_edit.text())
        ymax = self._parse_float(self.ymax_edit.text())
        window_size = self._parse_float(self.window_s_edit.text())
        jump_size = self._parse_float(self.jump_size_edit.text())
        
        # Default jump_size to 0.2 if None or invalid
        if jump_size is None:
            jump_size = 0.2

        # Update app state
        if self.app_state is not None:
            self.app_state.ymin = ymin
            self.app_state.ymax = ymax
            self.app_state.window_size = window_size
            self.app_state.jump_size = jump_size

        if self.lineplot is not None:
            self.lineplot.apply_axes_from_state(ymin, ymax, window_size)
            if hasattr(self.lineplot, "canvas"):
                self.lineplot.canvas.draw()
            
            # Sync napari viewer frame after plot update
            self._sync_napari_frame()

    def _adjust_ylim(self, percentage):
        """Adjust the y-axis limits by a percentage of the current range."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        ax = self.lineplot.ax
        current_ymin, current_ymax = ax.get_ylim()
        current_range = current_ymax - current_ymin
        adjustment = current_range * percentage
        
        new_ymax = current_ymax + adjustment
        new_ymin = current_ymin - adjustment  # Also adjust ymin to keep plot centered
        
        # Update app state
        self.app_state.ymin = new_ymin
        self.app_state.ymax = new_ymax
        
        # Update the plot
        ax.set_ylim(new_ymin, new_ymax)
        self.lineplot.canvas.draw()
        
        # Update the plot widgets UI if available
        if hasattr(self, 'plots_widget') and self.plots_widget:
            self.plots_widget.ymin_edit.setText(f"{new_ymin:.3f}")
            self.plots_widget.ymax_edit.setText(f"{new_ymax:.3f}")

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

            # Sync napari viewer frame after plot update
            self._sync_napari_frame()

    def _shift_yrange(self, percentage):
        """Shift the y-axis range up or down by a percentage of the current range."""
        if not self.app_state.ready or not hasattr(self, 'lineplot') or self.lineplot is None:
            return
        
        ax = self.lineplot.ax
        current_ymin, current_ymax = ax.get_ylim()
        current_range = current_ymax - current_ymin
        shift_amount = current_range * percentage
        
        new_ymin = current_ymin + shift_amount
        new_ymax = current_ymax + shift_amount
        
        # Update app state
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
            self.lineplot.apply_axes_from_state(
                getattr(self.app_state, 'ymin', None),
                getattr(self.app_state, 'ymax', None),
                new_window_size
            )
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

            # Sync napari viewer frame after plot update
            self._sync_napari_frame()
