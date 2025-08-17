"""Widget for selecting start/stop times and playing a segment in napari."""

import numpy as np
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from movformer_gui.lineplot_widget import LinePlotWidget


class LabelsWidget(QWidget):
    """Widget to select start/stop times and play that segment in napari."""

    def __init__(self, napari_viewer: Viewer, parent=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer
        self.setLayout(QFormLayout())

        self._create_file_path_widget()
        self._create_load_button()

    def _create_file_path_widget(self):
        """Create a line edit and browse button for selecting the file path.

        This allows the user to either browse the file system,
        or type the path directly into the line edit.
        """
        # File path line edit and browse button
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setObjectName("file_path_edit")
        self.browse_button = QPushButton("Browse")
        self.browse_button.setObjectName("browse_button")
        self.browse_button.clicked.connect(self._on_browse_clicked)

        # Layout for line edit and button
        self.file_path_layout = QHBoxLayout()
        self.file_path_layout.addWidget(self.file_path_edit)
        self.file_path_layout.addWidget(self.browse_button)
        self.layout().addRow("file path:", self.file_path_layout)

    def _create_load_button(self):
        """Create a button to load the file and add layers to the viewer."""
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("load_button")
        self.load_button.clicked.connect(lambda: self._on_load_clicked())
        self.layout().addRow(self.load_button)

    def _on_browse_clicked(self):
        """Open a file dialog to select a file."""
        file_suffixes = ["*.nc", "*.npy"]

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            caption="Open file containing tracked data",
            filter=f"Valid data files ({' '.join(file_suffixes)})",
        )

        # A blank string is returned if the user cancels the dialog
        if not file_path:
            return

        # Add the file path to the line edit (text field)
        self.file_path_edit.setText(file_path)

    def _on_load_clicked(self):
        """Load the .npy file and show line plot in napari dock."""
        self.file_path = self.file_path_edit.text()
        if not self.file_path or not self.file_path.endswith(".npy"):
            return

        data = np.load(self.file_path)
        len_frames = len(data)
        fps = 30  # You may want to add a widget for fps selection
        time = np.arange(len_frames) / fps

        plot_widget = LinePlotWidget(self.viewer, data, time)
        self.viewer.window.add_dock_widget(plot_widget, area="bottom")

    def _on_play_clicked(self):
        # REPLACE WITH START AND STOPS OF THAT LABEL
        start_time = self.start_spinbox.value()
        stop_time = self.stop_spinbox.value()
        # Assume viewer.dims.current_step[0] is the frame index
        # and viewer.dims.range[0] gives (min, max, step)
        fps = self.fps_spinbox.value()
        start_frame = int(start_time * fps)
        stop_frame = int(stop_time * fps)
        self.viewer.dims.set_current_step(0, start_frame)
        self._play_segment(start_frame, stop_frame, fps)

    def _play_segment(self, start_frame, stop_frame, fps):
        import time

        for frame in range(start_frame, stop_frame + 1):
            self.viewer.dims.set_current_step(0, frame)
            if QApplication is not None:
                QApplication.processEvents()
            time.sleep(1.0 / fps)


try:
    from qtpy.QtWidgets import QApplication
except ImportError:
    QApplication = None
