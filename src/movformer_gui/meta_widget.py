"""Widget container for other collapsible widgets."""

from pathlib import Path

from napari.layers import Image
from napari.viewer import Viewer
from qt_niu.collapsible_widget import CollapsibleWidgetContainer
from qtpy.QtWidgets import QWidget, QVBoxLayout, QSlider

from movformer_gui.napari_video_sync import NapariVideoPlayer

from .app_state import ObservableAppState
from .data_widget import DataWidget
from .labels_widget import LabelsWidget
from .integrated_lineplot import IntegratedLinePlot
from .navigation_widget import NavigationWidget
from .plot_widgets import PlotsWidget


from .shortcuts_dialog import ShortcutsWidget
from qtpy.QtWidgets import QLabel, QHBoxLayout


from .integrated_lineplot import IntegratedLinePlot

class MetaWidget(CollapsibleWidgetContainer):

    def __init__(self, napari_viewer: Viewer):
        """Initialize the meta-widget."""
        super().__init__()

        # Store the napari viewer reference
        self.viewer = napari_viewer

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


    def _create_widgets(self):
        """Create all widgets with app_state passed to each one."""



        # LinePlot widget docked at the bottom
        self.lineplot = IntegratedLinePlot(self.viewer, self.app_state)
        self.viewer.window.add_dock_widget(self.lineplot, area="bottom")




        # Create all widgets with app_state
        self.plots_widget = PlotsWidget(self.viewer, self.app_state)
        self.labels_widget = LabelsWidget(self.viewer, self.app_state)
        self.shortcuts_widget = ShortcutsWidget(self.app_state)
        self.navigation_widget = NavigationWidget(self.viewer, self.app_state)
        self.sync_manager = NapariVideoPlayer(self.viewer, self.app_state, None)
        self.data_widget = DataWidget(self.viewer, self.app_state, self)
        

        # Set navigation_widget reference in app_state for property callback
        self.app_state.lineplot = self.lineplot
        self.app_state.sync_manager = self.sync_manager



                

        # Set up cross-references between widgets, so they can talk to each other

            
        # Needs data widget for updating plots after navigation
        self.navigation_widget.set_data_widget(self.data_widget)
        

        # Labels and plot widgets need lineplot read info (e.g. xClicked) and apply plotting
        self.labels_widget.set_lineplot(self.lineplot)
        self.plots_widget.set_lineplot(self.lineplot)
        
        
        # The one widget to rule them all (loading data, updating plots, managing sync)
        self.data_widget.set_references(self.lineplot, self.labels_widget, self.plots_widget, self.navigation_widget)
        

        # Add widgets to collapsible container
        self.add_widget(
            self.shortcuts_widget,
            collapsible=True,
            widget_title="Shortcuts and Help",  # Add explain images and helpful GitHub links
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

    def closeEvent(self, event):
        """Handle close event by stopping auto-save and saving state one final time."""
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
        keys_to_override = [str(i) for i in range(10)]
        
        from napari.layers import Image, Points, Shapes, Labels, Tracks, Surface
        layer_types = [Image, Points, Shapes, Labels, Tracks, Surface]
        
        for layer_type in layer_types:
            for key in keys_to_override:
                try:
                    layer_type.bind_key(key, None)
                except Exception as e:
                    print(f"Could not unbind {key} from {layer_type.__name__}: {e}")

        for key in keys_to_override:
            try:
    
                if hasattr(self.viewer, 'keymap') and key in self.viewer.keymap:
                    del self.viewer.keymap[key]
                
                if hasattr(self.viewer, '_keymap') and key in self.viewer._keymap:
                    del self.viewer._keymap[key] 
            except Exception as e:
                print(f"Could not remove {key} from viewer keymap: {e}")
                
                
    
    def _bind_global_shortcuts(self, labels_widget, data_widget):
        """Bind all global shortcuts using napari's @viewer.bind_key syntax."""


        # Manually unbind previous keys.
        self._override_napari_shortcuts()
   


        # # Pause/play video/audio
        # @viewer.bind_key("space", overwrite=True)
        # def toggle_play_pause(v):
        #     self.data_widget.toggle_play_pause()
        viewer = self.viewer

        @viewer.bind_key("m", overwrite=True)
        def next_trial(v):
            self.navigation_widget.next_trial()

        @viewer.bind_key("n", overwrite=True)
        def prev_trial(v):
            self.navigation_widget.prev_trial()

        # Arrow key plot navigation
        @viewer.bind_key("Up", overwrite=True)
        def shift_yrange_up(v):
            self.plots_widget._shift_yrange(0.05)  # Shift Y range up by 5%

        @viewer.bind_key("Down", overwrite=True)
        def shift_yrange_down(v):
            self.plots_widget._shift_yrange(-0.05)  # Shift Y range down by 5%

        @viewer.bind_key("Shift-Up", overwrite=True)
        def adjust_ylim_up(v):
            self.plots_widget._adjust_ylim(0.05)  # Increase Y limits by 5%

        @viewer.bind_key("Shift-Down", overwrite=True)
        def adjust_ylim_down(v):
            self.plots_widget._adjust_ylim(-0.05)  # Decrease Y limits by 5%

        @viewer.bind_key("Left", overwrite=True)
        def jump_plot_left(v):
            self.plots_widget._jump_plot(-1)  # Jump left by configured jump size

        @viewer.bind_key("Right", overwrite=True)
        def jump_plot_right(v):
            self.plots_widget._jump_plot(1)  # Jump right by configured jump size

        @viewer.bind_key("Shift-Left", overwrite=True)
        def adjust_window_smaller(v):
            self.plots_widget._adjust_window_size(0.8)  # Make window 20% smaller

        @viewer.bind_key("Shift-Right", overwrite=True)
        def adjust_window_larger(v):
            self.plots_widget._adjust_window_size(1.2)  # Make window 20% larger


        # Motif labeling (0-9, q, w, r, t)
        for key, motif_key in zip(
            [
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "0",
                "Q",
                "W",
                "R",
                "T",
            ],
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            strict=False,
        ):

            def make_label_func(mk):
                def label_func(v):
                    labels_widget.activate_motif(mk)

                return label_func

            self.viewer.bind_key(key, make_label_func(motif_key), overwrite=True)

        # In native napari GUI, oen can use:
        # - Ctr + Alt + P for play/pause the viewer

        # Left click to label a motif (Press shortcut, then left-click, left-click)
        # Right click on a motif to play it

        # Edit motif (E)
        @viewer.bind_key("e", overwrite=True)
        def edit_motif(v):
            labels_widget._edit_motif()

        # Delete motif (D)
        @viewer.bind_key("d", overwrite=True)
        def delete_motif(v):
            labels_widget._delete_motif()

