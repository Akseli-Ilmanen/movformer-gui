"""Widget container for other collapsible widgets."""

from pathlib import Path

from napari.layers import Image
from napari.viewer import Viewer
from qt_niu.collapsible_widget import CollapsibleWidgetContainer
from qtpy.QtWidgets import QApplication, QSizePolicy, QMessageBox

from .app_state import ObservableAppState
from .data_widget import DataWidget
from .integrated_lineplot import IntegratedLinePlot
from .labels_widget import LabelsWidget
from .navigation_widget import NavigationWidget
from .io_widget import IOWidget
from .plot_widgets import PlotsWidget
from .shortcuts_dialog import ShortcutsWidget


class MetaWidget(CollapsibleWidgetContainer):

    def __init__(self, napari_viewer: Viewer):
        """Initialize the meta-widget."""
        super().__init__()

        # Store the napari viewer reference
        self.viewer = napari_viewer

        # Set smaller font for this widget and all children
        self._set_compact_font()

        # Create centralized app_state with YAML persistence
        yaml_path = self._default_yaml_path()
        print(f"Settings saved in {yaml_path}")

        self.app_state = ObservableAppState(yaml_path=str(yaml_path))

        # Try to load previous settings
        self.app_state.load_from_yaml()

        # Initialize all widgets with app_state
        self._create_widgets()

        self.collapsible_widgets[1].expand()

        self._bind_global_shortcuts(self.labels_widget, self.data_widget)
        
        # Connect to napari window close event to check for unsaved changes
        if hasattr(self.viewer, 'window') and hasattr(self.viewer.window, '_qt_window'):
            original_close_event = self.viewer.window._qt_window.closeEvent
            def napari_close_event(event):
                if not self._check_unsaved_changes(event):
                    return  
                original_close_event(event)
            self.viewer.window._qt_window.closeEvent = napari_close_event

    def _create_widgets(self):
        """Create all widgets with app_state passed to each one."""

        # LinePlot widget docked at the bottom with 1/3 height from bottom
        self.lineplot = IntegratedLinePlot(self.viewer, self.app_state)

        # Set size policy to allow vertical expansion but with preferred minimum
        self.lineplot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Set minimum height to roughly 1/3 of typical screen height but leave space for notifications
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                screen_height = screen.availableGeometry().height()
            else:
                screen_height = 1080  # fallback default
        except (AttributeError, RuntimeError):
            screen_height = 1080  # fallback default
        # Reduce lineplot height to leave space for notifications (25% instead of 33%)
        lineplot_height = int(screen_height * 0.25)
        self.lineplot.setMinimumHeight(lineplot_height)
        # Set maximum height to prevent it from growing too large
        self.lineplot.setMaximumHeight(int(screen_height * 0.4))

        # Add dock widget with margins to prevent covering notifications
        dock_widget = self.viewer.window.add_dock_widget(self.lineplot, area="bottom")
        
        # Try to set margins on the dock widget to leave space for notifications
        try:
            if hasattr(dock_widget, 'setContentsMargins'):
                dock_widget.setContentsMargins(0, 0, 0, 50)  # Leave 50px at bottom for notifications
        except:
            pass
        
        # Ensure napari notifications are positioned correctly
        self._configure_notifications()

        # Create all widgets with app_state
        self.plots_widget = PlotsWidget(self.viewer, self.app_state)
        self.labels_widget = LabelsWidget(self.viewer, self.app_state)
        self.shortcuts_widget = ShortcutsWidget(self.app_state)
        self.navigation_widget = NavigationWidget(self.viewer, self.app_state)
        
        # Create I/O widget first, then pass it to data widget
        self.io_widget = IOWidget(self.app_state, None)  # Will set data_widget reference after creation
        self.data_widget = DataWidget(self.viewer, self.app_state, self, self.io_widget)
        
        # Now set the data_widget reference in io_widget
        self.io_widget.data_widget = self.data_widget


        # Set up cross-references between widgets, so they can talk to each other

        # Needs data widget for updating plots after navigation
        self.navigation_widget.set_data_widget(self.data_widget)

        # Labels and plot widgets need lineplot read info (e.g. xClicked) and apply plotting
        self.labels_widget.set_lineplot(self.lineplot)
        self.plots_widget.set_lineplot(self.lineplot)

        # The one widget to rule them all (loading data, updating plots, managing sync)
        self.data_widget.set_references(self.lineplot, self.labels_widget, self.plots_widget, self.navigation_widget)

        # Set maximum height constraints for widgets to respect lineplot 25% rule
        remaining_height = int(screen_height * 0.75)  # 3/4 of screen for other widgets
        max_widget_height = int(remaining_height / 6)  # Divide among 6 widgets roughly

        # Configure size policies and max heights for all widgets
        for widget in [
            self.shortcuts_widget,
            self.io_widget,
            self.data_widget,
            self.labels_widget,
            self.plots_widget,
            self.navigation_widget,
        ]:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            widget.setMaximumHeight(max_widget_height)

        # Add widgets to collapsible container
        self.add_widget(
            self.shortcuts_widget,
            collapsible=True,
            widget_title="Shortcuts and Help",  # Add explain images and helpful GitHub links
        )

        self.add_widget(
            self.io_widget,
            collapsible=True,
            widget_title="I/O",
        )

        self.add_widget(
            self.data_widget,
            collapsible=True,
            widget_title="Data controls",
        )

        self.add_widget(
            self.labels_widget,
            collapsible=True,
            widget_title="Label controls",
        )

        self.add_widget(
            self.plots_widget,
            collapsible=True,
            widget_title="Plotting controls",
        )

        self.add_widget(
            self.navigation_widget,
            collapsible=True,
            widget_title="Navigation controls",
        )

    def _check_unsaved_changes(self, event):
        """Check for unsaved changes and prompt user. Returns True if OK to close, False if not."""
        # Check for unsaved changes in labels widget
        if not self.app_state.changes_saved:
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Unsaved Changes")
            msg_box.setText("You have unsaved changes to your labels.")
            msg_box.setInformativeText("Would you like to save your changes before closing?")
            msg_box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg_box.setDefaultButton(QMessageBox.Save)
            
            response = msg_box.exec_()
            
            if response == QMessageBox.Save:
                # Attempt to save
                try:
                    self.labels_widget._save_updated_nc()
                    # If save was successful, changes_saved will be True now
                    return True  # OK to close
                except Exception as e:
                    error_msg = QMessageBox()
                    error_msg.setWindowTitle("Save Error")
                    error_msg.setText(f"Failed to save changes: {str(e)}")
                    error_msg.exec_()
                    event.ignore()  # Prevent closing
                    return False  # Don't close
            elif response == QMessageBox.Cancel:
                event.ignore()  # Prevent closing
                return False  # Don't close
            # If Discard was selected, continue with closing
        
        return True  # OK to close
    
    def closeEvent(self, event):
        """Handle close event by stopping auto-save and saving state one final time."""
        # This method is now mainly for the dock widget itself, not the main napari window
        if hasattr(self, "app_state") and hasattr(self.app_state, "stop_auto_save"):
            self.app_state.stop_auto_save()
        super().closeEvent(event)

    def _default_yaml_path(self) -> Path:
        yaml_path = Path.cwd() / "gui_settings.yaml"
        try:
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.touch(exist_ok=True)
        except (OSError, PermissionError):
            yaml_path = Path.home() / "gui_settings.yaml"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.touch(exist_ok=True)
        return yaml_path

    def _override_napari_shortcuts(self):
        """Aggressively unbind napari shortcuts at all levels."""
        
        
        number_keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
        qwerty_row = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']
        home_row = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';']
        control_row = ['e', 'd', 'f', 'i', 'k', 'c', 'm', 't', 'n', 'p']
        other = ['y', 'space', 'Up', 'Down']

        all_keys = number_keys + qwerty_row + home_row + control_row + other
        
        from napari.layers import Labels, Points, Shapes, Surface, Tracks, Image
        
        layer_types = [Image, Points, Shapes, Labels, Tracks, Surface]
        

        for layer_type in layer_types:
            for key in all_keys:
                try:
                    if hasattr(layer_type, 'bind_key'):
                        layer_type.bind_key(key, None)
                except Exception as e:
                    print(f"Could not unbind {key} from {layer_type.__name__}: {e}")

        for key in all_keys:
            if hasattr(self.viewer, "keymap") and key in self.viewer.keymap:
                del self.viewer.keymap[key]
            
            if hasattr(self.viewer, "_keymap") and key in self.viewer._keymap:
                del self.viewer._keymap[key]
                    


        if self.viewer.layers.selection.active:
            active_layer = self.viewer.layers.selection.active
            for key in all_keys:
                if hasattr(active_layer, 'keymap') and key in active_layer.keymap:
                    del active_layer.keymap[key]



    def _bind_global_shortcuts(self, labels_widget, data_widget):
        """Bind all global shortcuts using napari's @viewer.bind_key syntax."""

        # Manually unbind previous keys.
        self._override_napari_shortcuts()
        

        # TO ADD documentation for inbuild pyqgt graph shortcuts
        # Right click hold - pull left/right to adjust xlim, up/down to adjust ylim

        # Pause/play video/audio
        viewer = self.viewer
        @viewer.bind_key("space", overwrite=True)
        def toggle_play_pause(v):
            self.data_widget.toggle_play_pause()
        
        # In napari video, can user left, right arrow keys to go back/forward one frame
        
        # Navigation shortcuts (avoiding conflicts with motif labeling)
        @viewer.bind_key("Down", overwrite=True) 
        def next_trial(v):
            self.navigation_widget.next_trial()

        @viewer.bind_key("Up", overwrite=True)
        def prev_trial(v):
            self.navigation_widget.prev_trial()

        def setup_keybindings_grid_layout(viewer, labels_widget):
            """Setup using grid layout for motif activation"""
            
            # Row 1: 1-0 (Motifs 1-10)
            number_keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
            
            # Row 2: Q-P (Motifs 11-20)
            qwerty_row = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']
            
            # Row 3: A-; (Motifs 21-30)
            home_row = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';']
            
            # Bind number keys for motifs 1-10
            for i, key in enumerate(number_keys):
                motif_id = i + 1 if key != '0' else 10
                viewer.bind_key(key, lambda v, mk=motif_id: labels_widget.activate_motif(mk), overwrite=True)
            
            # Bind qwerty row for motifs 11-20
            for i, key in enumerate(qwerty_row):
                viewer.bind_key(key, lambda v, mk=i+11: labels_widget.activate_motif(mk), overwrite=True)
            
            # Bind home row for motifs 21-30
            for i, key in enumerate(home_row):
                viewer.bind_key(key, lambda v, mk=i+21: labels_widget.activate_motif(mk), overwrite=True)
            
            print("""
            Motif Layout:
            [ 1][ 2][ 3][ 4][ 5][ 6][ 7][ 8][ 9][10]  (1-0 keys)
            [11][12][13][14][15][16][17][18][19][20]  (Q-P keys)  
            [21][22][23][24][25][26][27][28][29][30]  (A-; keys)
            
            Control Functions (use Shift+key):
            Y: Edit motif
            Shift+D: Delete motif
            Shift+F: Toggle features
            Shift+I: Toggle individuals
            Shift+K: Toggle keypoints
            Shift+C: Toggle cameras
            Shift+M: Toggle mics
            Shift+T: Toggle tracking
            """)

        # Call the setup function
        setup_keybindings_grid_layout(viewer, labels_widget)

        # Left click to label a motif (Press shortcut, then left-click, left-click)
        # Right click on a motif to play it

        @viewer.bind_key("ctrl+e", overwrite=True)  
        def edit_motif(v):
            labels_widget._edit_motif()

        # Delete motif (Ctrl+D)
        @viewer.bind_key("ctrl+d", overwrite=True)  
        def delete_motif(v):
            labels_widget._delete_motif()

        # Toggle features selection (Ctrl+F)
        @viewer.bind_key("ctrl+f", overwrite=True)  
        def toggle_features(v):
            self.app_state.toggle_key_sel("features", self.data_widget)

        # Toggle individuals selection (Ctrl+I)
        @viewer.bind_key("ctrl+i", overwrite=True) 
        def toggle_individuals(v):
            self.app_state.toggle_key_sel("individuals", self.data_widget)

        # Toggle keypoints selection (Ctrl+K)
        @viewer.bind_key("ctrl+k", overwrite=True)  
        def toggle_keypoints(v):
            self.app_state.toggle_key_sel("keypoints", self.data_widget)

        # Toggle cameras selection (Ctrl+C)
        @viewer.bind_key("ctrl+c", overwrite=True)  
        def toggle_cameras(v):
            self.app_state.toggle_key_sel("cameras", self.data_widget)

        # Toggle mics selection (Ctrl+M)
        @viewer.bind_key("ctrl+m", overwrite=True) 
        def toggle_mics(v):
            self.app_state.toggle_key_sel("mics", self.data_widget)

        # Toggle tracking selection (Ctrl+T)
        @viewer.bind_key("ctrl+t", overwrite=True)  
        def toggle_tracking(v):
            self.app_state.toggle_key_sel("tracking", self.data_widget)

        

    def _set_compact_font(self, font_size: int = 8):
        """Apply compact font to this widget and all children."""
        from qtpy.QtGui import QFont
        
        font = QFont()
        font.setPointSize(font_size)
        self.setFont(font)
        
        # Optional: Apply stylesheet for more control
        self.setStyleSheet(f"""
            * {{
                font-size: {font_size}pt;
            }}
            QLabel {{
                font-size: {font_size}pt;
            }}
            QPushButton {{
                font-size: {font_size}pt;
            }}
            QComboBox {{
                font-size: {font_size}pt;
            }}
            QSpinBox, QDoubleSpinBox {{
                font-size: {font_size}pt;
            }}
            QLineEdit {{
                font-size: {font_size}pt;
            }}
        """)
    
    def _configure_notifications(self):
        """Configure napari notifications to be visible above docked widgets."""
        try:
            # Access napari's notification manager
            if hasattr(self.viewer.window, '_qt_viewer'):
                qt_viewer = self.viewer.window._qt_viewer
                
                # Try to access the notification overlay
                if hasattr(qt_viewer, '_overlays'):
                    for overlay in qt_viewer._overlays.values():
                        if hasattr(overlay, 'setContentsMargins'):
                            # Add bottom margin to keep notifications above docked widgets
                            overlay.setContentsMargins(0, 0, 0, 60)
                        
                        # Try to adjust positioning
                        if hasattr(overlay, 'resize') and hasattr(overlay, 'parent'):
                            parent = overlay.parent()
                            if parent:
                                parent_rect = parent.geometry()
                                # Position overlay to leave space at bottom
                                overlay.resize(parent_rect.width(), parent_rect.height() - 80)
                                
        except Exception as e:
            # Silently handle any issues with notification configuration
            print(f"Notification configuration warning: {e}")