"""Widget for labeling segments in movement data."""

import numpy as np
import xarray as xr
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
import sys

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QLabel, QHeaderView, QAbstractItemView, QApplication
)
from qtpy.QtCore import Signal, Qt
from qtpy.QtGui import QColor, QCursor, QKeyEvent

from napari.viewer import Viewer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from movformer_gui.state_manager import GUIStateManager
from plot_utils import get_motif_colours


class LabelsWidget(QWidget):
    """Widget for labeling movement motifs in time series data."""
    
    # Signal emitted when labels are updated
    labels_updated = Signal(np.ndarray)
    
    # Signals for navigation
    next_trial_requested = Signal()
    prev_trial_requested = Signal()
    
    def __init__(self, napari_viewer: Viewer, parent=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.state_manager = GUIStateManager()
        
        # Make widget focusable for keyboard events
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Install global event filter for shortcuts
        self._install_global_shortcuts()
        
        # Data variables
        self.ds: Optional[xr.Dataset] = None
        self.current_trial: Optional[str] = None
        self.current_keypoint: Optional[str] = None
        self.current_variable: Optional[str] = None
        
        # Labeling state
        self.motif_mappings: Dict[int, Dict[str, Any]] = {}
        self.ready_for_click = False
        self.first_click = None
        self.second_click = None
        self.selected_motif_id = 0
        self.closer_to = 'end'  # 'start' or 'end' for motif adjustment
        self.label_mode = False
        
        # Current motif selection for editing
        self.current_motif_pos = None  # [start, end] of selected motif
        self.current_motif_id = None   # ID of currently selected motif
        
        # UI components
        self.motifs_table = None
        
        # Reference to the lineplot widget for interaction
        self.lineplot_widget = None
        
        self._setup_ui()
        self._load_motif_mappings()
    
    def _install_global_shortcuts(self):
        """Install global event filter for keyboard shortcuts."""
        # Install event filter on the napari viewer's main window
        if hasattr(self.viewer, 'window') and hasattr(self.viewer.window, '_qt_window'):
            self.viewer.window._qt_window.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Global event filter to capture keyboard shortcuts anywhere in napari."""
        from qtpy.QtCore import QEvent
        
        if hasattr(event, 'type') and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            
            # Handle navigation shortcuts globally (always active)
            if key == Qt.Key_Right and not event.modifiers():
                # Right arrow - next trial
                self.next_trial_requested.emit()
                return True  # Event handled
                
            elif key == Qt.Key_Left and not event.modifiers():
                # Left arrow - previous trial
                self.prev_trial_requested.emit()
                return True  # Event handled
            
            # Handle motif labeling shortcuts only when in label mode
            if self.label_mode:
                # Number keys 0-9 and letters q, w, r, t for motif selection
                valid_keys = {
                    Qt.Key_0: 0, Qt.Key_1: 1, Qt.Key_2: 2, Qt.Key_3: 3, Qt.Key_4: 4,
                    Qt.Key_5: 5, Qt.Key_6: 6, Qt.Key_7: 7, Qt.Key_8: 8, Qt.Key_9: 9,
                    Qt.Key_Q: 'q', Qt.Key_W: 'w', Qt.Key_R: 'r', Qt.Key_T: 't'
                }
                
                if key in valid_keys and not event.modifiers():
                    # Get the motif number/key
                    motif_key = valid_keys[key]
                    self._label_motif_with_shortcut(motif_key)
                    return True  # Event handled
                    
                elif key == Qt.Key_E and not event.modifiers():
                    # Edit current motif
                    self._edit_motif()
                    return True  # Event handled
                    
                elif key == Qt.Key_D and not event.modifiers():
                    # Delete current selection
                    self._delete_motif()
                    return True  # Event handled
                    
                elif key == Qt.Key_V and not event.modifiers():
                    # Play current motif (like in MATLAB)
                    self._play_motif()
                    return True  # Event handled
        
        # Pass event to parent
        return super().eventFilter(obj, event)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for motif labeling."""
        if not self.label_mode:
            super().keyPressEvent(event)
            return
        
        key = event.key()
        
        # Number keys 0-9 and letters q, w, r, t for motif selection
        valid_keys = {
            Qt.Key_0: 0, Qt.Key_1: 1, Qt.Key_2: 2, Qt.Key_3: 3, Qt.Key_4: 4,
            Qt.Key_5: 5, Qt.Key_6: 6, Qt.Key_7: 7, Qt.Key_8: 8, Qt.Key_9: 9,
            Qt.Key_Q: 'q', Qt.Key_W: 'w', Qt.Key_R: 'r', Qt.Key_T: 't'
        }
        
        if key in valid_keys and not event.modifiers():
            # Get the motif number/key
            motif_key = valid_keys[key]
            self._label_motif_with_shortcut(motif_key)
            
        elif key == Qt.Key_E and not event.modifiers():
            # Edit current motif
            self._edit_motif()
            
        elif key == Qt.Key_D and not event.modifiers():
            # Delete current selection
            self._delete_motif()
            
        elif key == Qt.Key_V and not event.modifiers():
            # Play current motif
            self._play_motif()
            
        else:
            super().keyPressEvent(event)
        
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create motifs table
        self._create_motifs_table()
        
        # Create control buttons
        self._create_control_buttons()
        
        layout.addWidget(self.motifs_table)
        layout.addWidget(self.controls_widget)
        
    def _create_motifs_table(self):
        """Create the motifs table showing available motif types."""
        self.motifs_table = QTableWidget()
        self.motifs_table.setColumnCount(3)
        self.motifs_table.setHorizontalHeaderLabels(["ID", "Name", "Color"])
        
        # Hide row numbers (left column)
        self.motifs_table.verticalHeader().setVisible(False)
        
        # Set column widths
        header = self.motifs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # ID column - fixed width
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name column - stretches
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Color column - fixed width
        
        # Set specific widths for ID and Color columns
        self.motifs_table.setColumnWidth(0, 20)  # ID column narrow
        self.motifs_table.setColumnWidth(2, 20)  # Color column narrow
        
        self.motifs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.motifs_table.setMaximumHeight(250)
        
        # Connect selection change
        self.motifs_table.itemSelectionChanged.connect(self._on_motif_selected)
        
    def _create_control_buttons(self):
        """Create control buttons for labeling operations."""
        self.controls_widget = QWidget()
        layout = QHBoxLayout()
        self.controls_widget.setLayout(layout)
        
        # Label mode checkbox
        self.label_mode_checkbox = QCheckBox("Label Mode")
        self.label_mode_checkbox.stateChanged.connect(self._on_label_mode_changed)
        layout.addWidget(self.label_mode_checkbox)
        
        # Delete button
        self.delete_button = QPushButton("Delete (D)")
        self.delete_button.setShortcut("D")
        self.delete_button.clicked.connect(self._delete_motif)
        layout.addWidget(self.delete_button)
        
        # Edit button
        self.edit_button = QPushButton("Edit (E)")
        self.edit_button.setShortcut("E")
        self.edit_button.clicked.connect(self._edit_motif)
        layout.addWidget(self.edit_button)
        
        # Play button
        self.play_button = QPushButton("Play (V)")
        self.play_button.setShortcut("V")
        self.play_button.clicked.connect(self._play_motif)
        layout.addWidget(self.play_button)
        
    def _load_motif_mappings(self):
        """Load motif mappings from mapping.txt file."""
        mapping_file = Path(__file__).parent.parent.parent / "mapping.txt"
        
        # Get colors from plot_utils
        motif_colors = get_motif_colours()
        
        with open(mapping_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                motif_id = int(parts[0])
                name = parts[1]
                
                color = np.array(motif_colors[motif_id]) / 255
                
                self.motif_mappings[motif_id] = {
                    'name': name,
                    'color': color
                }
    
        self._populate_motifs_table()
    
    def _populate_motifs_table(self):
        """Populate the motifs table with loaded mappings."""
        self.motifs_table.setRowCount(len(self.motif_mappings))
        
        for row, (motif_id, data) in enumerate(self.motif_mappings.items()):
            # ID column
            id_item = QTableWidgetItem(str(motif_id))
            id_item.setData(Qt.UserRole, motif_id)
            self.motifs_table.setItem(row, 0, id_item)
            
            # Name column with keyboard shortcut
            # Map motif ID to keyboard shortcut
            if motif_id <= 9:
                shortcut = str(motif_id)
            elif motif_id == 10:
                shortcut = "0"
            elif motif_id == 11:
                shortcut = "Q"
            elif motif_id == 12:
                shortcut = "W"
            elif motif_id == 13:
                shortcut = "R"
            elif motif_id == 14:
                shortcut = "T"
            else:
                shortcut = "?"
            
            name_with_shortcut = f"{data['name']} (Press {shortcut})"
            name_item = QTableWidgetItem(name_with_shortcut)
            self.motifs_table.setItem(row, 1, name_item)
            
            # Color column
            color_item = QTableWidgetItem()
            color = data['color']
            qcolor = QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
            color_item.setBackground(qcolor)
            self.motifs_table.setItem(row, 2, color_item)
    
    def set_data(self, ds: xr.Dataset, trial: str, keypoint: str, variable: str):
        """Set the ds and current selection for labeling."""
        self.ds = ds
        self.current_trial = trial
        self.current_keypoint = keypoint
        self.current_variable = variable
        
        # Replot motifs when data changes
        self._plot_all_motifs()
    
    def set_lineplot_widget(self, lineplot_widget):
        """Set reference to the lineplot widget for interaction."""
        self.lineplot_widget = lineplot_widget
        
        # Connect to plot clicks if available
        if hasattr(lineplot_widget, 'canvas'):
            lineplot_widget.canvas.mpl_connect('button_press_event', self._on_plot_clicked)
        
    def _on_motif_selected(self):
        """Handle motif selection in the table."""
        current_row = self.motifs_table.currentRow()
        if current_row >= 0:
            motif_id_item = self.motifs_table.item(current_row, 0)
            if motif_id_item:
                self.selected_motif_id = motif_id_item.data(Qt.UserRole)
    
    def _on_label_mode_changed(self, state):
        """Handle label mode checkbox change."""
        self.label_mode = state == Qt.Checked
        self.ready_for_click = self.label_mode
        
        if self.lineplot_widget:
            if self.label_mode:
                # Set cursor on lineplot widget canvas
                if hasattr(self.lineplot_widget, 'canvas'):
                    self.lineplot_widget.canvas.setCursor(QCursor(Qt.CrossCursor))
            else:
                # Reset cursor
                if hasattr(self.lineplot_widget, 'canvas'):
                    self.lineplot_widget.canvas.setCursor(QCursor(Qt.ArrowCursor))
                    
        if not self.label_mode:
            self.first_click = None
            self.second_click = None
    
    def _on_plot_clicked(self, event):
        """Handle mouse clicks on the lineplot widget."""
        if not self.lineplot_widget or not hasattr(self.lineplot_widget, 'ax'):
            return
            
        if event.inaxes != self.lineplot_widget.ax:
            return
            
        x_clicked = event.xdata
        if x_clicked is None:
            return
        
        # Handle right-click - play motif if clicking on one
        if event.button == 3:  # Right mouse button
            if self._check_motif_click(x_clicked):
                self._play_motif()
            return
        
        # Handle left-click for labeling/editing (only in label mode)
        if event.button == 1 and self.ready_for_click and self.label_mode:  # Left mouse button
            # Check if clicking on existing motif for selection
            if self._check_motif_click(x_clicked):
                return
            
            # Snap to nearest changepoint if available
            x_snapped = self._snap_to_changepoint(x_clicked)
            
            if self.first_click is None:
                # First click - just store the position
                self.first_click = x_snapped
            else:
                # Second click - store position and automatically apply
                self.second_click = x_snapped
                self._apply_motif()  # Automatically apply after two clicks
    
    def _snap_to_changepoint(self, x_clicked: float) -> float:
        """Snap the clicked x-coordinate to the nearest changepoint."""
        if 'changepoints' not in self.ds.data_vars:
            return x_clicked
            
        try:
            # Get changepoints for current trial and keypoint
            changepoints_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint)['changepoints'].values
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            
            # Find changepoint times
            changepoint_indices = np.where(changepoints_data)[0]
            if len(changepoint_indices) == 0:
                return x_clicked
                
            changepoint_times = time_data[changepoint_indices]
            
            # Find nearest changepoint - implement locally
            try:
                # Try to import from parent directory
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from label_utils import snap_to_nearest_changepoint
                snapped_val, _ = snap_to_nearest_changepoint(x_clicked, changepoint_times)
            except ImportError:
                # Implement locally if import fails
                changepoint_times = np.asarray(changepoint_times)
                snapped_idx = np.argmin(np.abs(changepoint_times - x_clicked))
                snapped_val = float(changepoint_times[snapped_idx])
            
            return snapped_val
            
        except Exception as e:
            print(f"Error snapping to changepoint: {e}")
            return x_clicked
    
    def _check_motif_click(self, x_clicked: float) -> bool:
        """Check if the click is on an existing motif and select it if so."""
        labels = self.get_labels()
        if labels is None:
            return False
            
        try:
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            
            # Find the closest time index
            time_idx = np.argmin(np.abs(time_data - x_clicked))
            
            # Check if there's a motif at this position
            motif_id = labels[time_idx]
            if motif_id != 0:
                # Find the start and end of this motif
                motif_start = time_idx
                motif_end = time_idx
                
                # Find start
                while motif_start > 0 and labels[motif_start - 1] == motif_id:
                    motif_start -= 1
                
                # Find end
                while motif_end < len(labels) - 1 and labels[motif_end + 1] == motif_id:
                    motif_end += 1
                
                # Select this motif
                self.current_motif_id = motif_id
                self.current_motif_pos = [time_data[motif_start], time_data[motif_end]]
                self.selected_motif_id = motif_id
                
                # Determine which end of the motif was clicked (for editing)
                start_dist = abs(x_clicked - self.current_motif_pos[0])
                end_dist = abs(x_clicked - self.current_motif_pos[1])
                self.closer_to = 'start' if start_dist < end_dist else 'end'
                
                print(f"Selected motif {motif_id} from {self.current_motif_pos[0]:.2f} to {self.current_motif_pos[1]:.2f}")
                return True
                
        except Exception as e:
            print(f"Error checking motif click: {e}")
            
        return False
    
    def _play_motif(self):
        """Play the currently selected motif segment."""
        if not self.current_motif_pos:
            print("No motif selected for playback")
            return
            
        if not hasattr(self, 'viewer') or not self.viewer:
            print("No viewer available for playback")
            return
            
        try:
            # Get start and end times from current motif position
            start_time = self.current_motif_pos[0]
            end_time = self.current_motif_pos[1]
            
            # Convert time to frames (assuming 30 fps, adjust as needed)
            fps = 30  # You may want to make this configurable
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps)
            
            print(f"Playing motif from frame {start_frame} to {end_frame} ({start_time:.2f}s to {end_time:.2f}s)")
            
            # Set the viewer to start frame
            self.viewer.dims.set_current_step(0, start_frame)
            
            # Play the segment
            self._play_segment(start_frame, end_frame, fps)
            
        except Exception as e:
            print(f"Error playing motif: {e}")
    
    def _play_segment(self, start_frame, end_frame, fps):
        """Play a segment of frames at the specified fps."""
        import time
        
        for frame in range(start_frame, end_frame + 1):
            self.viewer.dims.set_current_step(0, frame)
            if QApplication is not None:
                QApplication.processEvents()
            time.sleep(1.0 / fps)
    
    def _label_motif_with_shortcut(self, motif_key):
        """Handle labeling with keyboard shortcuts."""
        # Convert key to motif ID (similar to MATLAB code)
        if motif_key == 0:
            motif_id = 10
        elif motif_key == 'q':
            motif_id = 11
        elif motif_key == 'w':
            motif_id = 12
        elif motif_key == 'r':
            motif_id = 13
        elif motif_key == 't':
            motif_id = 14
        else:
            motif_id = motif_key
        
        # Check if motif ID is valid
        if motif_id not in self.motif_mappings:
            print(f"No motif defined for key {motif_key}")
            return
        
        # Set selected motif and start labeling
        self.selected_motif_id = motif_id
        
        # Find and select the corresponding row in the table
        for row in range(self.motifs_table.rowCount()):
            item = self.motifs_table.item(row, 0)  # ID column
            if item and item.data(Qt.UserRole) == motif_id:
                self.motifs_table.selectRow(row)
                break
        
        self.ready_for_click = True
        self.first_click = None
        self.second_click = None
        print(f"Ready to label motif {motif_id} ({self.motif_mappings[motif_id]['name']}) - click twice to define region")
    
    def _plot_all_motifs(self):
        """Plot all motifs for current trial and keypoint based on current labels state.
        
        This implements state-based plotting similar to the MATLAB plot_motifs() function.
        It clears all existing motif rectangles and redraws them based on the current labels.
        """
        if not self.lineplot_widget or not hasattr(self.lineplot_widget, 'ax'):
            return
            
        if self.ds is None or 'labels' not in self.ds.data_vars:
            return
            
        if not self.current_trial or not self.current_keypoint:
            return
            
        ax = self.lineplot_widget.ax
        
        # Clear all existing motif patches (similar to delete(findall(..., 'Tag', 'xregion1')))
        patches_to_remove = [patch for patch in ax.patches if hasattr(patch, 'get_label') 
                           and patch.get_label() == 'motif']
        for patch in patches_to_remove:
            patch.remove()
        
        try:
            # Get current labels for this trial and keypoint
            labels = self.get_labels()
            if labels is None:
                return
                
            # Get time data
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            
            # Get y-axis limits for rectangles
            ylim = ax.get_ylim()
            
            # Find all labeled segments and plot them
            current_motif_id = 0
            segment_start = None
            
            for i, label in enumerate(labels):
                if label != 0:  # Start of a motif or continuing one
                    if label != current_motif_id:  # New motif starts
                        # End previous motif if it exists
                        if current_motif_id != 0 and segment_start is not None:
                            self._draw_motif_rectangle(ax, time_data[segment_start], time_data[i-1], 
                                                     current_motif_id, ylim)
                        
                        # Start new motif
                        current_motif_id = label
                        segment_start = i
                else:  # End of current motif
                    if current_motif_id != 0 and segment_start is not None:
                        self._draw_motif_rectangle(ax, time_data[segment_start], time_data[i-1], 
                                                 current_motif_id, ylim)
                        current_motif_id = 0
                        segment_start = None
            
            # Handle case where motif continues to the end
            if current_motif_id != 0 and segment_start is not None:
                self._draw_motif_rectangle(ax, time_data[segment_start], time_data[-1], 
                                         current_motif_id, ylim)
            
            # Redraw the canvas
            if hasattr(self.lineplot_widget, 'canvas'):
                self.lineplot_widget.canvas.draw()
                
        except Exception as e:
            print(f"Error plotting motifs: {e}")
    
    def _draw_motif_rectangle(self, ax, start_time: float, end_time: float, motif_id: int, ylim: Tuple[float, float]):
        """Draw a single motif rectangle."""
        if motif_id not in self.motif_mappings:
            return
            
        color = self.motif_mappings[motif_id]['color']
        
        # Create rectangle
        rect = Rectangle((start_time, ylim[0]), end_time - start_time, 
                        ylim[1] - ylim[0], 
                        facecolor=color, alpha=0.7, linewidth=1)
        rect.set_label('motif')  # Tag for identification
        ax.add_patch(rect)
    
    def _apply_motif(self):
        """Apply the selected motif to the selected time range."""
        if self.first_click is None or self.second_click is None:
            return
            
        if self.ds is None or 'labels' not in self.ds.data_vars:
            return
        
        try:
            # Convert time to frame indices
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            
            start_time = min(self.first_click, self.second_click)
            end_time = max(self.first_click, self.second_click)
            
            start_idx = np.argmin(np.abs(time_data - start_time))
            end_idx = np.argmin(np.abs(time_data - end_time))
            
            # Get current labels
            labels = self.ds['labels'].values
            trial_idx = list(self.ds.coords['trial'].values).index(self.current_trial)
            keypoint_idx = list(self.ds.coords['keypoints'].values).index(self.current_keypoint)
            
            # Handle overlapping labels (as in MATLAB code)
            if labels[trial_idx, end_idx, keypoint_idx] != 0:
                end_idx = end_idx - 1
            
            # Apply the new label
            labels[trial_idx, start_idx:end_idx+1, keypoint_idx] = self.selected_motif_id
            
            # Update ds
            self.ds['labels'].values = labels
            
            # Reset selection
            self.first_click = None
            self.second_click = None
            
            # Replot all motifs (state-based plotting like in MATLAB)
            self._plot_all_motifs()
            
            # Emit signal for other widgets
            self.labels_updated.emit(labels[trial_idx, :, keypoint_idx])
            
            print(f"Applied motif {self.selected_motif_id} from {start_time:.2f} to {end_time:.2f}")
            
        except Exception as e:
            print(f"Error applying motif: {e}")
    
    def _delete_motif(self):
        """Delete motif at the current cursor position or selected segment."""
        if not self.lineplot_widget or not hasattr(self.lineplot_widget, 'ax'):
            return
            
        if self.ds is None or 'labels' not in self.ds.data_vars:
            return
            
        if not self.current_trial or not self.current_keypoint:
            return
        
        # If we have a current motif selection, delete that
        if self.current_motif_pos and self.current_motif_id:
            try:
                time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
                
                start_time, end_time = self.current_motif_pos
                start_idx = np.argmin(np.abs(time_data - start_time))
                end_idx = np.argmin(np.abs(time_data - end_time))
                
                # Get current labels
                labels = self.ds['labels'].values
                trial_idx = list(self.ds.coords['trial'].values).index(self.current_trial)
                keypoint_idx = list(self.ds.coords['keypoints'].values).index(self.current_keypoint)
                
                # Clear labels in the selected range (set to 0)
                labels[trial_idx, start_idx:end_idx+1, keypoint_idx] = 0
                
                # Update ds
                self.ds['labels'].values = labels
                
                # Clear selection
                self.current_motif_pos = None
                self.current_motif_id = None
                
                # Replot all motifs
                self._plot_all_motifs()
                
                # Emit signal for other widgets
                self.labels_updated.emit(labels[trial_idx, :, keypoint_idx])
                
                print(f"Deleted selected motif")
                
            except Exception as e:
                print(f"Error deleting selected motif: {e}")
                
        # If we have a pending selection (first_click and second_click), delete that range
        elif self.first_click is not None and self.second_click is not None:
            try:
                # Convert time to frame indices
                time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
                
                start_time = min(self.first_click, self.second_click)
                end_time = max(self.first_click, self.second_click)
                
                start_idx = np.argmin(np.abs(time_data - start_time))
                end_idx = np.argmin(np.abs(time_data - end_time))
                
                # Get current labels
                labels = self.ds['labels'].values
                trial_idx = list(self.ds.coords['trial'].values).index(self.current_trial)
                keypoint_idx = list(self.ds.coords['keypoints'].values).index(self.current_keypoint)
                
                # Clear labels in the selected range (set to 0)
                labels[trial_idx, start_idx:end_idx+1, keypoint_idx] = 0
                
                # Update ds
                self.ds['labels'].values = labels
                
                # Reset selection
                self.first_click = None
                self.second_click = None
                
                # Replot all motifs
                self._plot_all_motifs()
                
                # Emit signal for other widgets
                self.labels_updated.emit(labels[trial_idx, :, keypoint_idx])
                
                print(f"Deleted motif in selected range")
                
            except Exception as e:
                print(f"Error deleting motif range: {e}")
        else:
            print("No motif segment selected for deletion. Click on a motif or select a range first.")
    
    def _edit_motif(self):
        """Enter edit mode for adjusting motif boundaries."""
        if not self.current_motif_pos or not self.current_motif_id:
            print("No motif selected for editing. Click on a motif first.")
            return
            
        if self.ds is None or 'labels' not in self.ds.data_vars:
            return
            
        try:
            # Delete the current motif (similar to MATLAB code)
            time_data = self.ds.sel(trial=self.current_trial, keypoints=self.current_keypoint).time.values
            
            start_time, end_time = self.current_motif_pos
            start_idx = np.argmin(np.abs(time_data - start_time))
            end_idx = np.argmin(np.abs(time_data - end_time))
            
            # Get current labels
            labels = self.ds['labels'].values
            trial_idx = list(self.ds.coords['trial'].values).index(self.current_trial)
            keypoint_idx = list(self.ds.coords['keypoints'].values).index(self.current_keypoint)
            
            # Clear the motif (set to 0)
            labels[trial_idx, start_idx:end_idx+1, keypoint_idx] = 0
            self.ds['labels'].values = labels
            
            # Set up for re-labeling with the same motif ID
            self.selected_motif_id = self.current_motif_id
            self.ready_for_click = True
            self.first_click = None
            self.second_click = None
            
            # Replot to show the deletion
            self._plot_all_motifs()
            
            print(f"Deleted motif {self.current_motif_id}. Click twice to re-label with the same motif.")
            
            # Clear current selection
            self.current_motif_pos = None
            self.current_motif_id = None
            
        except Exception as e:
            print(f"Error editing motif: {e}")
    
    def update_motif_display(self):
        """Public method to update the motif display. Call this when lineplot changes."""
        self._plot_all_motifs()
    
    def get_labels(self) -> Optional[np.ndarray]:
        """Get current labels for the active trial and keypoint."""
        if self.ds is None or 'labels' not in self.ds.data_vars:
            return None
            
        try:
            trial_idx = list(self.ds.coords['trial'].values).index(self.current_trial)
            keypoint_idx = list(self.ds.coords['keypoints'].values).index(self.current_keypoint)
            return self.ds['labels'].values[trial_idx, :, keypoint_idx]
        except:
            return None
    
    def save_current_state(self):
        """Save current widget state."""
        state_updates = {
            'selected_motif_id': self.selected_motif_id,
            'label_mode': self.label_mode,
        }
        
        if state_updates:
            for key, value in state_updates.items():
                self.state_manager.set(key, value)
    
    def closeEvent(self, event):
        """Handle close event."""
        self.save_current_state()
        super().closeEvent(event)
