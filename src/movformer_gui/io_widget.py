
"""Widget for input/output controls and data loading."""

from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
    QCheckBox,
)
from .app_state import AppStateSpec
from pathlib import Path


class IOWidget(QWidget):
    """Widget to control I/O paths, device selection, and data loading."""

    def __init__(self, app_state, data_widget, parent=None):
        super().__init__(parent=parent)
        self.app_state = app_state
        self.data_widget = data_widget
        self.setLayout(QFormLayout())
        
        # Dictionary to store combo boxes
        self.combos = {}
        # List to store controls for enabling/disabling
        self.controls = []
        
        

        self.reset_button = QPushButton("Reset gui_settings.yaml")
        self.reset_button.setObjectName("reset_button")
        self.reset_button.clicked.connect(self._on_reset_gui_clicked)
        self.layout().addRow(self.reset_button)

        
        
        self._create_path_folder_widgets()
        self._create_device_combos()
        self._create_load_button()

        # Restore UI text fields from app state
        if self.app_state.nc_file_path:
            self.nc_file_path_edit.setText(self.app_state.nc_file_path)
        if self.app_state.video_folder:
            self.video_folder_edit.setText(self.app_state.video_folder)
        if self.app_state.audio_folder:
            self.audio_folder_edit.setText(self.app_state.audio_folder)
        if self.app_state.tracking_folder:
            self.tracking_folder_edit.setText(self.app_state.tracking_folder)

    def _on_reset_gui_clicked(self):
        """Reset the GUI to its initial state."""
     

        self.app_state.delete_yaml()
        
        # Reset all app_state attributes to their defaults
        for var, (var_type, default, _, _) in AppStateSpec.VARS.items():
            setattr(self.app_state._state, var, default)
        
        # Clear all dynamic _sel attributes
        for attr in list(dir(self.app_state)):
            if attr.endswith("_sel") or attr.endswith("_sel_previous"):
                try:
                    delattr(self.app_state, attr)
                except AttributeError:
                    pass
        
        self._clear_all_line_edits()
        self._clear_combo_boxes()
        
        if hasattr(self, 'flip_video_checkbox'):
            self.flip_video_checkbox.setChecked(False)
        
        yaml_path = self._default_yaml_path()
        self.app_state._yaml_path = str(yaml_path)
        self.app_state.save_to_yaml()
  
  
  

    def _default_yaml_path(self) -> Path:
        """Create default YAML path (same logic as meta_widget)."""
        yaml_path = Path.cwd() / "gui_settings.yaml"
        try:
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.touch(exist_ok=True)
        except (OSError, PermissionError):
            yaml_path = Path.home() / "gui_settings.yaml"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.touch(exist_ok=True)
        return yaml_path

    def _clear_all_line_edits(self):
        """Clear all QLineEdit fields in the widget."""
        if hasattr(self, 'nc_file_path_edit'):
            self.nc_file_path_edit.clear()
        if hasattr(self, 'video_folder_edit'):
            self.video_folder_edit.clear()
        if hasattr(self, 'audio_folder_edit'):
            self.audio_folder_edit.clear()
        if hasattr(self, 'tracking_folder_edit'):
            self.tracking_folder_edit.clear()

    def _clear_combo_boxes(self):
        """Reset all combo boxes to default state."""
        for combo in self.combos.values():
            combo.clear()
            combo.addItems(["None"])
            combo.setCurrentText("None")

    def _create_path_widget(self, label: str, object_name: str, browse_callback):
        """Generalized function to create a line edit and browse button for file/folder paths."""
        line_edit = QLineEdit()
        line_edit.setObjectName(f"{object_name}_edit")
        browse_button = QPushButton("Browse")
        browse_button.setObjectName(f"{object_name}_browse_button")
        browse_button.clicked.connect(browse_callback)

        clear_button = QPushButton("Clear")
        clear_button.setObjectName(f"{object_name}_clear_button")
        clear_button.clicked.connect(lambda: self._on_clear_path_clicked(object_name, line_edit))

        layout = QHBoxLayout()
        layout.addWidget(line_edit)
        layout.addWidget(browse_button)
        layout.addWidget(clear_button)
        self.layout().addRow(label, layout)

        return line_edit

    def _on_clear_path_clicked(self, object_name: str, line_edit: QLineEdit):
        """Clear the path field and corresponding app state value."""
        line_edit.setText("")

        if object_name == "nc_file_path":
            self.app_state.nc_file_path = None
        elif object_name == "video_folder":
            self.app_state.video_folder = None
        elif object_name == "audio_folder":
            self.app_state.audio_folder = None
        elif object_name == "tracking_folder":
            self.app_state.tracking_folder = None

    def _create_path_folder_widgets(self):
        """Create file path, video folder, and audio folder selectors."""
        self.nc_file_path_edit = self._create_path_widget(
            label="File path (.nc):",
            object_name="nc_file_path",
            browse_callback=lambda: self.on_browse_clicked("file"),
        )
        self.video_folder_edit = self._create_path_widget(
            label="Video folder:",
            object_name="video_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "video"),
        )
        self.audio_folder_edit = self._create_path_widget(
            label="Audio folder:",
            object_name="audio_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "audio"),
        )
        self.tracking_folder_edit = self._create_path_widget(
            label="Tracking folder (e.g. DLC):",
            object_name="tracking_folder",
            browse_callback=lambda: self.on_browse_clicked("folder", "tracking"),
        )

    def _create_device_combos(self):
        """Create device combo boxes (cameras, mics, tracking). Called after data is loaded."""
        pass  # Will be populated when data is loaded

    def create_device_controls(self, type_vars_dict):
        """Create device combo boxes based on loaded data."""
        # Clear existing device controls
        for key in ['cameras', 'mics', 'tracking']:
            if key in self.combos:
                # Remove from layout and delete widget
                combo = self.combos[key]
                combo.setParent(None)
                combo.deleteLater()
                del self.combos[key]
                if combo in self.controls:
                    self.controls.remove(combo)

        # Create cameras combo
        if "cameras" in type_vars_dict.keys():
            self._create_combo_widget("cameras", type_vars_dict["cameras"])
        else:
            combo = QComboBox()
            combo.setObjectName("cameras_combo")
            combo.currentTextChanged.connect(self._on_combo_changed)
            combo.addItems(["None"])
            self.layout().addRow("Cameras:", combo)
            self.combos['cameras'] = combo
            self.controls.append(combo)
            
        # Add a checkbox to flip video vertically
        self.flip_video_checkbox = QCheckBox("Flip video vertically")
        self.flip_video_checkbox.setObjectName("flip_video_checkbox")
        self.layout().addRow(self.flip_video_checkbox)
        self.controls.append(self.flip_video_checkbox)

  
        # Create mics combo
        if "mics" in type_vars_dict.keys():
            self._create_combo_widget("mics", type_vars_dict["mics"])
        else:
            combo = QComboBox()
            combo.setObjectName("mics_combo")
            combo.currentTextChanged.connect(self._on_combo_changed)
            combo.addItems(["None"])
            self.layout().addRow("Mics:", combo)
            self.combos['mics'] = combo
            self.controls.append(combo)

        # Create tracking combo
        if "tracking" in type_vars_dict.keys():
            self._create_combo_widget("tracking", type_vars_dict["tracking"])

    def _create_combo_widget(self, key, vars):
        """Create a combo box widget for a given info key."""
        combo = QComboBox()
        combo.setObjectName(f"{key}_combo")
        combo.currentTextChanged.connect(self._on_combo_changed)
        combo.addItems([str(var) for var in vars])
        self.layout().addRow(f"{key.capitalize()}:", combo)
        self.combos[key] = combo
        self.controls.append(combo)
        return combo

    def _on_combo_changed(self):
        """Handle combo box changes and delegate to data widget."""
        if hasattr(self.data_widget, '_on_combo_changed'):
            self.data_widget._on_combo_changed()

    def set_controls_enabled(self, enabled: bool):
        """Enable or disable device controls."""
        for control in self.controls:
            control.setEnabled(enabled)

    def _create_load_button(self):
        """Create a button to load the file to the viewer."""
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("load_button")
        self.load_button.clicked.connect(lambda: self.data_widget.on_load_clicked())
        self.layout().addRow(self.load_button)

    def on_browse_clicked(self, browse_type: str = "file", media_type: str | None = None):
        """
        Open a file or folder dialog to select a file or folder.

        Args:
            browse_type: "file" for file dialog, "folder" for folder dialog.
            media_type: "video" or "audio" (used for folder dialog caption).
        """
        if browse_type == "file":
            result = QFileDialog.getOpenFileName(
                None,
                caption="Open file containing feature data",
                filter="NetCDF files (*.nc)",
            )
            nc_file_path = result[0] if result and len(result) >= 1 else ""
            if not nc_file_path:
                return

            self.nc_file_path_edit.setText(nc_file_path)
            self.app_state.nc_file_path = nc_file_path

        elif browse_type == "folder":
            if media_type == "video":
                caption = "Open folder with video files (e.g. mp4, mov)."
            elif media_type == "audio":
                caption = "Open folder with audio files (e.g. wav, mp3, mp4)."
            elif media_type == "tracking":
                caption = "Open folder with tracking files (e.g. .csv, .h5)."

            folder_path = QFileDialog.getExistingDirectory(None, caption=caption)

            if media_type == "video":
                self.video_folder_edit.setText(folder_path)
                self.app_state.video_folder = folder_path
            elif media_type == "audio":
                self.audio_folder_edit.setText(folder_path)
                self.app_state.audio_folder = folder_path
                # Clear audio checkbox if it exists in data_widget
                if hasattr(self.data_widget, 'clear_audio_checkbox'):
                    self.data_widget.clear_audio_checkbox.setChecked(False)
            elif media_type == "tracking":
                self.tracking_folder_edit.setText(folder_path)
                self.app_state.tracking_folder = folder_path

    def get_nc_file_path(self):
        """Get the current NetCDF file path from the text field."""
        return self.nc_file_path_edit.text()