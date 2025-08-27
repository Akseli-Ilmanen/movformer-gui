"""Widget for labeling segments in movement data."""

import time as _time
from pathlib import Path
from typing import Any
import napari
import numpy as np
from matplotlib.patches import Rectangle
from napari.viewer import Viewer
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_utils import load_motif_mapping

from label_utils import snap_to_nearest_changepoint
from xarray_utils import sel_valid
import cv2
import time
from audioio import play
import random



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



        # UI components
        self.motifs_table = None

        self._setup_ui()
        path = Path(__file__).parent.parent.parent / "mapping.txt"  # change location in the future
        self.motif_mappings = load_motif_mapping(path)
        self._populate_motifs_table()

    def set_lineplot(self, lineplot):
        """Set the lineplot reference and connect click handler."""
        self.lineplot = lineplot
        self.lineplot.canvas.mpl_connect("button_press_event", self._on_plot_clicked)

    def plot_all_motifs(self, time_data=None, labels=None):
        """Plot all motifs for current trial and keypoint based on current labels state.

        This implements state-based plotting similar to the MATLAB plot_motifs() function.
        It clears all existing motif rectangles and redraws them based on the current labels.
        """
        if labels is None or self.lineplot is None:
            return

        ax = self.lineplot.ax

        # Clear all existing motif patches (similar to delete(findall(..., 'Tag', 'xregion1')))
        patches_to_remove = [
            patch
            for patch in ax.patches
            if hasattr(patch, "get_label") and patch.get_label() == "motif"
        ]
        for patch in patches_to_remove:
            patch.remove()

        try:

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
                            self._draw_motif_rectangle(
                                ax,
                                time_data[segment_start],
                                time_data[i - 1],
                                current_motif_id,
                                ylim,
                            )

                        # Start new motif
                        current_motif_id = label
                        segment_start = i

                else:  # End of current motif
                    if current_motif_id != 0 and segment_start is not None:
                        self._draw_motif_rectangle(
                            ax,
                            time_data[segment_start],
                            time_data[i - 1],
                            current_motif_id,
                            ylim,
                        )
                        current_motif_id = 0
                        segment_start = None

            # Handle case where motif continues to the end
            if current_motif_id != 0 and segment_start is not None:
                self._draw_motif_rectangle(
                    ax,
                    time_data[segment_start],
                    time_data[-1],
                    current_motif_id,
                    ylim,
                )

            if self.lineplot is not None:
                self.lineplot.canvas.draw()

        except (KeyError, IndexError, AttributeError) as e:
            print(f"Error plotting motifs: {e}")

    def _draw_motif_rectangle(
        self,
        ax,
        start_time: float,
        end_time: float,
        motif_id: int,
        ylim: tuple[float, float],
    ):
        """Draw a single motif rectangle."""
        if motif_id not in self.motif_mappings:
            return

        color = self.motif_mappings[motif_id]["color"]

        # Create rectangle
        rect = Rectangle(
            (start_time, ylim[0]),
            end_time - start_time,
            ylim[1] - ylim[0],
            facecolor=color,
            alpha=0.7,
            linewidth=1,
        )
        rect.set_label("motif")  # Tag for identification
        ax.add_patch(rect)

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
        layout = QHBoxLayout()
        self.controls_widget.setLayout(layout)

        # Delete button
        self.delete_button = QPushButton("Delete (D)")
        self.delete_button.clicked.connect(self._delete_motif)
        layout.addWidget(self.delete_button)

        # Edit button
        self.edit_button = QPushButton("Edit (E)")
        self.edit_button.clicked.connect(self._edit_motif)
        layout.addWidget(self.edit_button)

        # Play button
        self.play_button = QPushButton("Play (Right-click)")
        self.play_button.clicked.connect(self._play_segment)
        layout.addWidget(self.play_button)

    # Centralized mapping between motif_id and shortcut key
    MOTIF_ID_TO_KEY = {
        10: "0",
        11: "Q",
        12: "W",
        13: "R",
        14: "T",
    }
    # Also provide reverse mapping for key to motif_id
    KEY_TO_MOTIF_ID = {v.lower(): k for k, v in MOTIF_ID_TO_KEY.items()}
    # Add numeric keys for motif_id 0-9
    for i in range(10):
        KEY_TO_MOTIF_ID[str(i)] = i
        MOTIF_ID_TO_KEY[i] = str(i)

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

    def activate_motif(self, motif_key):
        """Activate a motif by shortcut: select row, set up for labeling, and scroll to row."""

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

    def _on_plot_clicked(self, event):
        """Handle mouse clicks on the lineplot widget."""

        x_clicked = event.xdata
        if x_clicked is None:
            return

        # Get current data from app_state
        ds_kwargs = self.app_state.get_ds_kwargs()
        
        labels = sel_valid(self.app_state.ds.labels, ds_kwargs)


        
        if event.button == 1 and not self.ready_for_click:
            # Select motif -> Then can delete or edit.
            self._check_motif_click(x_clicked, labels)

        # Handle right-click - play video of motif if clicking on one
        if event.button == 3:  # Right mouse button
            if self._check_motif_click(x_clicked, labels):
                self._play_segment()
            return

        # Handle left-click for labeling/editing (only in label mode)
        if event.button == 1 and self.ready_for_click:

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
            # Find the start and end of this motif
            motif_start = frame_idx
            motif_end = frame_idx

            # Find start
            while motif_start > 0 and labels[motif_start - 1] == motif_id:
                motif_start -= 1

            # Find end
            while motif_end < len(labels) - 1 and labels[motif_end + 1] == motif_id:
                motif_end += 1

            # Select this motif
            self.current_motif_id = motif_id
            self.current_motif_pos = [motif_start, motif_end]
            self.selected_motif_id = motif_id
            return True
        else:
            return False

    def _snap_to_changepoint(self, x_clicked_idx: float) -> float:
        """Snap the clicked x-coordinate to the nearest changepoint."""

        # Check if "changepoints" exists and is a binary vector
        if "changepoints" not in self.app_state.ds:
            return x_clicked_idx

        ds_kwargs = self.app_state.get_ds_kwargs()
        changepoints_data = self.app_state.ds.sel(**ds_kwargs)["changepoints"].values

        if changepoints_data is None or not np.array_equal(
            changepoints_data, changepoints_data.astype(bool)
        ):
            return x_clicked_idx

        # Get changepoints for current trial and keypoint
        changepoints_data = self.app_state.ds.sel(**ds_kwargs)["changepoints"].values

        # Find changepoint times
        changepoint_indices = np.where(changepoints_data)[0]
        if len(changepoint_indices) == 0:
            return x_clicked_idx

        snapped_val, _ = snap_to_nearest_changepoint(x_clicked_idx, changepoint_indices)
        return snapped_val

    def _apply_motif(self):
        """Apply the selected motif to the selected time range."""
        if self.first_click is None or self.second_click is None:
            return

        # Get current labels from app_state
        ds_kwargs = self.app_state.get_ds_kwargs()
        labels = sel_valid(self.app_state.ds.labels, ds_kwargs)


        start_idx = self.first_click
        end_idx = self.second_click

        # Handle overlapping labels (as in MATLAB code)
        if labels[end_idx] != 0:
            end_idx = end_idx - 1

        # Apply the new label
        labels[start_idx : end_idx + 1] = self.selected_motif_id

        # Reset selection
        self.first_click = None
        self.second_click = None
        self.ready_for_click = False

        # Save updated labels back to dataset
        self.app_state.ds["labels"].loc[ds_kwargs] = labels

        # Update plot
        time_data  = self.app_state.ds.time.values
        self.plot_all_motifs(time_data, labels)

    def _delete_motif(self):

        if self.current_motif_pos is None:
            return

        start, end = self.current_motif_pos

        # Get current labels from app_state
        ds_kwargs = self.app_state.get_ds_kwargs()
        labels = sel_valid(self.app_state.ds.labels, ds_kwargs)


        # Clear labels in the selected range (set to 0)
        labels[start : end + 1] = 0

        # Clear selection
        self.current_motif_pos = None
        self.current_motif_id = None

        # Save updated labels back to dataset
        self.app_state.ds["labels"].loc[ds_kwargs] = labels

        # Update plot
        time_data  = self.app_state.ds.time.values
        self.plot_all_motifs(time_data, labels)

    def _edit_motif(self):
        """Enter edit mode for adjusting motif boundaries."""

        if self.current_motif_pos is None or self.first_click is None or self.second_click is None:
            return

        old_start, old_end = self.current_motif_pos

        # Get current labels from app_state
        ds_kwargs = self.app_state.get_ds_kwargs()
        labels = sel_valid(self.app_state.ds.labels, ds_kwargs)

        
        
        # Clear labels in the selected range (set to 0)
        labels[old_start : old_end + 1] = 0

        new_start, new_end = self.first_click, self.second_click
        labels[new_start : new_end + 1] = self.selected_motif_id

        # Clear current selection
        self.current_motif_pos = None
        self.current_motif_id = None

        # Save updated labels back to dataset
        self.app_state.ds["labels"].loc[ds_kwargs] = labels

        # Update plot
        time_data  = self.app_state.ds.time.values
        self.plot_all_motifs(time_data, labels)

    
    
    def _play_segment(self):
        
        if not self.current_motif_id or len(self.current_motif_pos) != 2:
            return

        self.app_state.current_frame = round(self.current_motif_pos[0])

        start_time = self.current_motif_pos[0] / self.app_state.ds.fps
        end_time = self.current_motif_pos[1] / self.app_state.ds.fps
        print(f"Playing motif {self.current_motif_id} from {start_time:.2f}s to {end_time:.2f}s")


        # Resume if paused before jumping
        if self.app_state.stream.is_paused:
            self.app_state.stream.resume()
        
        # Sync with audio via pyav
        if self.app_state.video_path and self.app_state.audio_path:
            self.app_state.stream.jump_to_segment(start_time, end_time)


        # Video only
        elif not self.app_state.audio_path:
            self.app_state.stream.jump_to_segment(start_time, end_time)

