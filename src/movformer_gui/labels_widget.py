"""Widget for labeling segments in movement data."""
import xarray as xr
import threading
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
import numpy as np
import pyqtgraph as pg
from napari.viewer import Viewer
from napari.utils.notifications import show_info
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from movformer.features.changepoints import snap_to_nearest_changepoint
from movformer.utils.labels import load_motif_mapping
from movformer.utils.xr_utils import sel_valid


class LabelsWidget(QWidget):
    """Widget for labeling movement motifs in time series data."""

    def __init__(self, napari_viewer: Viewer, app_state, parent=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.app_state = app_state
        self.lineplot = None  # Will be set after creation

        # Make widget focusable for keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

        # Remove Qt event filter and key event logic
        # Instead, rely on napari's @viewer.bind_key for global shortcuts
        # Shortcut bindings are now handled outside the widget

        # Labeling state
        self.motif_mappings: dict[int, dict[str, Any]] = {}
        self.ready_for_click = False
        self.first_click = None
        self.second_click = None
        self.selected_motif_id = 0

        # Current motif selection for editing
        self.current_motif_pos: list[int] | None = None  # [start, end] idx of selected motif
        self.current_motif_id: int | None = None  # ID of currently selected motif
        
        # Edit mode state  
        self.old_motif_pos: list[int] | None = None  # Original position when editing
        self.old_motif_id: int | None = None  # Original ID when editing


        # UI components
        self.motifs_table = None

        self._setup_ui()


        self.motif_mappings = load_motif_mapping("mapping.txt") # HARD CODED FOR NOW
        self._populate_motifs_table()

        self._sync_disabled = False
        self._in_labeling_operation = False  # Add flag to prevent re-entrance
        self._operation_lock = threading.Lock()  # Thread-safe flag

    def _mark_changes_unsaved(self):
        """Mark that changes have been made and are not saved."""
        self.app_state.changes_saved = False

    def set_lineplot(self, lineplot):
        """Set the lineplot reference and connect click handler."""
        self.lineplot = lineplot
        self.lineplot.plot_clicked.connect(self._on_plot_clicked)

    def plot_all_motifs(self, time_data=None, labels=None):
        """Plot all motifs for current trial and keypoint based on current labels state.

        This implements state-based plotting similar to the MATLAB plot_motifs() function.
        It clears all existing motif rectangles and redraws them based on the current labels.
        """
        if labels is None or self.lineplot is None:
            return

        # Clear existing motif rectangles
        if hasattr(self.lineplot, "label_items"):
            for item in self.lineplot.label_items:
                try:
                    self.lineplot.plot_item.removeItem(item)
                except:
                    pass
            self.lineplot.label_items.clear()

        try:
            # Find all labeled segments and plot them
            current_motif_id = 0
            segment_start = None

            for i, label in enumerate(labels):
                if label != 0:  # Start of a motif or continuing one
                    if label != current_motif_id:  # New motif starts
                        # End previous motif if it exists
                        if current_motif_id != 0 and segment_start is not None:
                            self._draw_motif_rectangle(
                                time_data[segment_start],
                                time_data[i - 1],
                                current_motif_id,
                                None,  # ylim not needed for PyQtGraph
                            )

                        # Start new motif
                        current_motif_id = label
                        segment_start = i

                else:  # End of current motif
                    if current_motif_id != 0 and segment_start is not None:
                        self._draw_motif_rectangle(time_data[segment_start], time_data[i - 1], current_motif_id, None)
                        current_motif_id = 0
                        segment_start = None

            # Handle case where motif continues to the end
            if current_motif_id != 0 and segment_start is not None:
                self._draw_motif_rectangle(time_data[segment_start], time_data[-1], current_motif_id, None)

        except (KeyError, IndexError, AttributeError) as e:
            print(f"Error plotting motifs: {e}")

    def _draw_motif_rectangle(self, start_time, end_time, motif_id, ylim):
        """Draw motif rectangle using PyQtGraph."""
        if motif_id not in self.motif_mappings:
            return

        color = self.motif_mappings[motif_id]["color"]
        # Convert to 0-255 RGB
        color_rgb = tuple(int(c * 255) for c in color)

        rect = pg.LinearRegionItem(
            values=(start_time, end_time),
            orientation="vertical",
            brush=(*color_rgb, 180),  # Semi-transparent
            movable=False,
        )
        rect.setZValue(-10)
        self.lineplot.plot_item.addItem(rect)
        self.lineplot.label_items.append(rect)

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

    def _create_control_buttons(self):
        """Create control buttons for labeling operations."""
        self.controls_widget = QWidget()
        layout = QVBoxLayout()
        self.controls_widget.setLayout(layout)

        # First row - existing buttons
        first_row = QWidget()
        first_layout = QHBoxLayout()
        first_row.setLayout(first_layout)

        # Delete button
        self.delete_button = QPushButton("Delete (Ctrl + D)")
        self.delete_button.clicked.connect(self._delete_motif)
        first_layout.addWidget(self.delete_button)

        # Edit button
        self.edit_button = QPushButton("Edit (Ctrl + E)")
        self.edit_button.clicked.connect(self._edit_motif)
        first_layout.addWidget(self.edit_button)

        # Play button
        self.play_button = QPushButton("Play (Right-click)")
        self.play_button.clicked.connect(self._play_segment)
        first_layout.addWidget(self.play_button)

        # Second row - save controls
        second_row = QWidget()
        second_layout = QHBoxLayout()
        second_row.setLayout(second_layout)

        # Save button
        self.save_button = QPushButton("Save updated .nc")
        self.save_button.clicked.connect(self._save_updated_nc)
        second_layout.addWidget(self.save_button)

        # Timestamp versions checkbox
        self.timestamp_checkbox = QCheckBox("Timestamp versions")
        self.timestamp_checkbox.setChecked(True)  # Default to enabled
        second_layout.addWidget(self.timestamp_checkbox)

        layout.addWidget(first_row)
        layout.addWidget(second_row)

    MOTIF_ID_TO_KEY = {}

    # Row 1: 1-0 (Motifs 1-10)
    number_keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
    for i, key in enumerate(number_keys):
        motif_id = i + 1 if key != '0' else 10
        MOTIF_ID_TO_KEY[motif_id] = key

    # Row 2: Q-P (Motifs 11-20)
    qwerty_row = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']
    for i, key in enumerate(qwerty_row):
        motif_id = i + 11
        MOTIF_ID_TO_KEY[motif_id] = key.upper()  # Display as uppercase for clarity

    # Row 3: A-; (Motifs 21-30)
    home_row = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';']
    for i, key in enumerate(home_row):
        motif_id = i + 21
        MOTIF_ID_TO_KEY[motif_id] = key.upper() if key != ';' else ';'  # Keep ; as is

    # Also provide reverse mapping for key to motif_id
    KEY_TO_MOTIF_ID = {v.lower(): k for k, v in MOTIF_ID_TO_KEY.items()}
    
    def _populate_motifs_table(self):    
        """Populate the motifs table with loaded mappings."""
        self.motifs_table.setRowCount(len(self.motif_mappings))
        for row, (motif_id, data) in enumerate(self.motif_mappings.items()):
            # ID column
            id_item = QTableWidgetItem(str(motif_id))
            id_item.setData(Qt.UserRole, motif_id)
            self.motifs_table.setItem(row, 0, id_item)

            # Name column with keyboard shortcut
            shortcut = self.MOTIF_ID_TO_KEY.get(motif_id, "?")
            name_with_shortcut = f"{data['name']} (Press {shortcut})"
            name_item = QTableWidgetItem(name_with_shortcut)
            self.motifs_table.setItem(row, 1, name_item)

            # Color column
            color_item = QTableWidgetItem()
            color = data["color"]
            qcolor = QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
            color_item.setBackground(qcolor)
            self.motifs_table.setItem(row, 2, color_item)

    @contextmanager
    def _disable_sync_during_labeling(self) -> Generator[None, None, None]:
        """Context manager to temporarily disable sync manager during labeling operations."""

        # Prevent re-entrance (event loop protection)
        if self._in_labeling_operation:
            # If already in a labeling operation, just yield without doing anything
            yield
            return

        with self._operation_lock:
            if self._in_labeling_operation:
                yield
                return

            self._in_labeling_operation = True

        sync_manager = getattr(self.app_state, "sync_manager", None)

        # Store original state
        was_monitoring = False
        if sync_manager and hasattr(sync_manager, "_monitoring_enabled"):
            was_monitoring = sync_manager._monitoring_enabled
            sync_manager._monitoring_enabled = False
        elif sync_manager:
            sync_manager._monitoring_enabled = False
            was_monitoring = True

        self._sync_disabled = True

        try:
            yield
        except Exception as e:
            # Log the exception but don't re-raise to prevent event system issues
            print(f"Exception in labeling operation: {e}")
        finally:
            # Always restore state
            self._sync_disabled = False
            if sync_manager:
                sync_manager._monitoring_enabled = was_monitoring

            with self._operation_lock:
                self._in_labeling_operation = False

    def activate_motif(self, motif_key):
        """Activate a motif by shortcu1t: select row, set up for labeling, and scroll to row."""
        with self._disable_sync_during_labeling():
            # Convert key to motif ID using centralized1 mapping
            motif_id = self.KEY_TO_MOTIF_ID.get(str(motif_key).lower(), motif_key)
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
                    self.motifs_table.scrollToItem(item)
                    break
            self.ready_for_click = True
            self.first_click = None
            self.second_click = None

            print(
                f"Ready to label motif {motif_id} ({self.motif_mappings[motif_id]['name']}) - click twice to define region"
            )

    def _on_plot_clicked(self, click_info):
        """Handle mouse clicks on the lineplot widget.

        Args:
            click_info: dict with 'x' (time coordinate) and 'button' (Qt button constant)
        """

        x_clicked = click_info["x"]
        button = click_info["button"]

        if x_clicked is None:
            return

        # Get current data from app_state
        ds_kwargs = self.app_state.get_ds_kwargs()
        labels, filt_kwargs = sel_valid(self.app_state.ds.labels, ds_kwargs)



        if button == Qt.LeftButton and not self.ready_for_click:
            # Select motif -> Then can delete or edit
            self._check_motif_click(x_clicked, labels)

        # Handle right-click - play video of motif if clicking on one
        elif button == Qt.RightButton:
            if self._check_motif_click(x_clicked, labels):
                self._play_segment()
            return

        # Handle left-click for labeling/editing (only in label mode)
        elif button == Qt.LeftButton and self.ready_for_click:
            # Snap to nearest changepoint if available
            x_clicked_idx = int(x_clicked * self.app_state.ds.fps)  # Convert to frame index
            x_snapped = self._snap_to_changepoint(x_clicked_idx)

            if self.first_click is None:
                # First click - just store the position
                self.first_click = x_snapped
            else:
                # Second click - store position and automatically apply
                self.second_click = x_snapped
                self._apply_motif()  # Automatically apply after two clicks




    def _check_motif_click(self, x_clicked: float, labels: np.ndarray) -> bool:
        """Check if the click is on an existing motif and select it if so. Move left and right until you find its start and stop idxs."""

        # Check if there's a motif at this position
        frame_idx = int(x_clicked * self.app_state.ds.fps)
        motif_id = int(labels[frame_idx])

        if motif_id != 0:
            motif_start = frame_idx
            motif_end = frame_idx

       
            while motif_start > 0 and labels[motif_start - 1] == motif_id:
                motif_start -= 1

   
            while motif_end < len(labels) - 1 and labels[motif_end + 1] == motif_id:
                motif_end += 1

            self.current_motif_id = motif_id
            self.current_motif_pos = [motif_start, motif_end]
            self.selected_motif_id = motif_id
            return True
        else:
            return False

    def _snap_to_changepoint(self, x_clicked_idx: float) -> float:
        """Snap the clicked x-coordinate to the nearest changepoint."""

        ds_kwargs = self.app_state.get_ds_kwargs()

        cp_ds = self.app_state.ds.sel(**ds_kwargs).filter_by_attrs(type="changepoints")
        if len(cp_ds.data_vars) == 0:
            return x_clicked_idx

        snapped_val, _ = snap_to_nearest_changepoint(x_clicked_idx, cp_ds)
        return snapped_val

    def _apply_motif(self):
        """Apply the selected motif to the selected time range."""
        with self._disable_sync_during_labeling():
            if self.first_click is None or self.second_click is None:
                return

            ds_kwargs = self.app_state.get_ds_kwargs()
            labels, filt_kwargs = sel_valid(self.app_state.ds.labels, ds_kwargs)

            start_idx = self.first_click
            end_idx = self.second_click

            # Handle overlapping labels (as in MATLAB code)
            if labels[end_idx] != 0:
                end_idx = end_idx - 1

            # Check if we're in edit mode
            if hasattr(self, 'old_motif_pos') and self.old_motif_pos is not None:
                # Edit mode: clear old motif first
                old_start, old_end = self.old_motif_pos
                labels[old_start : old_end + 1] = 0
                print(f"Editing motif {self.old_motif_id}: moved from {old_start}-{old_end} to {start_idx}-{end_idx}")
                
                # Clean up edit mode variables
                self.old_motif_pos = None
                self.old_motif_id = None
                self.current_motif_pos = None
                self.current_motif_id = None

            # Apply the new label
            labels[start_idx : end_idx + 1] = self.selected_motif_id

            # Reset selection
            self.first_click = None
            self.second_click = None
            self.ready_for_click = False

            # Save updated labels back to dataset
            self.app_state.ds["labels"].loc[filt_kwargs] = labels
            
            # Mark changes as unsaved
            self._mark_changes_unsaved()

   
            time_data = self.app_state.ds.time.values
            self.plot_all_motifs(time_data, labels)

    def _delete_motif(self):
        with self._disable_sync_during_labeling():
            if self.current_motif_pos is None:
                return

            start, end = self.current_motif_pos

    
            ds_kwargs = self.app_state.get_ds_kwargs()


            labels, filt_kwargs = sel_valid(self.app_state.ds.labels, ds_kwargs)


            # Clear labels in the selected range (set to 0)
            labels[start : end + 1] = 0


            self.current_motif_pos = None
            self.current_motif_id = None

            # Save updated labels back to dataset
            self.app_state.ds["labels"].loc[filt_kwargs] = labels
            
            # Mark changes as unsaved
            self._mark_changes_unsaved()

    
            time_data = self.app_state.ds.time.values
            self.plot_all_motifs(time_data, labels)

    def _edit_motif(self):
        """Enter edit mode for adjusting motif boundaries."""
        if self.current_motif_pos is None:
            print("No motif selected. Right-click on a motif first to select it.")
            return

        # Store the old motif info for later cleanup
        self.old_motif_pos = self.current_motif_pos.copy()
        self.old_motif_id = self.current_motif_id
        
        # Enter editing mode - user needs to click twice to set new boundaries
        self.ready_for_click = True
        self.first_click = None
        self.second_click = None
        
        print(f"Edit mode: Click twice to set new boundaries for motif {self.current_motif_id}")
        return

    def _play_segment(self):

        if not self.app_state.sync_state == "napari_video_mode":
            return

        if not self.current_motif_id or len(self.current_motif_pos) != 2:
            return

        if hasattr(self.app_state, "sync_manager") and self.app_state.sync_manager:

            start_frame = self.current_motif_pos[0]
            end_frame = self.current_motif_pos[1]

            self.app_state.sync_manager.play_segment(start_frame, end_frame)

    def _save_updated_nc(self):
        """Save the updated NetCDF file with optional timestamp versioning."""
        if not hasattr(self.app_state, 'nc_file_path'):
            raise ValueError("No NetCDF file path specified in app_state.")

        nc_path = Path(self.app_state.nc_file_path)
        ds = self.app_state.ds
        
        # Close to allow being overwritten
        ds.close()       
        ds.to_netcdf(nc_path, mode='w')
      
        if self.timestamp_checkbox.isChecked():
            versions_dir = nc_path.parent / "versions"
            versions_dir.mkdir(exist_ok=True)
            

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned_filename = f"{nc_path.stem}_{timestamp}{nc_path.suffix}"
            versioned_path = versions_dir / versioned_filename
            

            if nc_path.exists():
                shutil.copy2(nc_path, versioned_path)
        

    
        self.app_state.ds = xr.open_dataset(nc_path)
        
        # Mark changes as saved after successful save
        self.app_state.changes_saved = True

        show_info(f"✅ File saved successfully: {nc_path.name}")