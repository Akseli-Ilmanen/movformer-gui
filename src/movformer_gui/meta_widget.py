"""Widget container for other collapsible widgets."""

from pathlib import Path

from napari.layers import Image
from napari.viewer import Viewer
from qt_niu.collapsible_widget import CollapsibleWidgetContainer

from movformer_gui.app_state import ObservableAppState
from movformer_gui.data_widget import DataWidget
from movformer_gui.labels_widget import LabelsWidget
from movformer_gui.lineplot import LinePlot
from movformer_gui.plot_widgets import PlotsWidget
from movformer_gui.shortcuts_dialog import ShortcutsWidget


class MetaWidget(CollapsibleWidgetContainer):

    def __init__(self, napari_viewer: Viewer, parent=None):
        """Initialize the meta-widget."""
        super().__init__()

        # Store the napari viewer reference
        self.napari_viewer = napari_viewer

        # Create centralized app_state with YAML persistence
        yaml_path = self._default_yaml_path()
        print(f"Settings saved in {yaml_path}")

        self.app_state = ObservableAppState(yaml_path=str(yaml_path))
        
        # Try to load previous settings
        self.app_state.load_from_yaml()

        # Initialize all widgets with app_state
        self._create_widgets(napari_viewer)


        self.collapsible_widgets[0].expand()


        self._bind_global_shortcuts(napari_viewer, self.labels_widget, self.data_widget)


    def _create_widgets(self, napari_viewer: Viewer):
        """Create all widgets with app_state passed to each one."""
        # Initialize LinePlot early (empty) and add to napari
        self.lineplot = LinePlot(napari_viewer, self.app_state)
        napari_viewer.window.add_dock_widget(self.lineplot, area="bottom")
        # Avoid forcing geometry; cap height instead
        self.lineplot.setMaximumHeight(400)

        # Create all widgets with app_state
        self.plots_widget = PlotsWidget(self.app_state)
        self.labels_widget = LabelsWidget(napari_viewer, self.app_state)
        self.shortcuts_widget = ShortcutsWidget(self.app_state)
        self.data_widget = DataWidget(napari_viewer, self.app_state, self)

        # Set up cross-references between widgets, so they can talk to each other
        self.plots_widget.set_lineplot(self.lineplot)
        self.plots_widget.set_labels_widget(self.labels_widget)
        self.labels_widget.set_lineplot(self.lineplot)
        self.lineplot.set_plots_widget(self.plots_widget)
        self.data_widget.set_references(self.lineplot, self.labels_widget, self.plots_widget)

        # Add widgets to collapsible container
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
            widget_title="Plotting and navigation",
        )

        self.add_widget(
            self.shortcuts_widget,
            widget_title="Shortcuts & Help", # Add explain images and helpful GitHub links
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

    def _bind_global_shortcuts(self, viewer, labels_widget, data_widget):
        """Bind all global shortcuts using napari's @viewer.bind_key syntax."""

        
        
        @viewer.bind_key("m", overwrite=True)
        def next_trial(v):
            data_widget.next_trial()

        @viewer.bind_key("n", overwrite=True)
        def prev_trial(v):
            data_widget.prev_trial()

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

        # Manually unbind previous keys.
        Image.bind_key("1", None)
        Image.bind_key("2", None)

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

            viewer.bind_key(key, make_label_func(motif_key), overwrite=True)

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

