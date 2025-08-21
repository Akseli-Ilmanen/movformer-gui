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
from movformer_gui.shortcuts_widget import ShortcutsWidget


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

        # Initialize LinePlot early (empty)
        self.lineplot = LinePlot(napari_viewer)
        napari_viewer.window.add_dock_widget(self.lineplot, area="bottom")
        self.lineplot.setFixedHeight(400)

        # Pass app_state to all widgets (plots_widget still uses old system for now)
        self.plots_widget = PlotsWidget(lineplot=self.lineplot, parent=self)

        self.labels_widget = LabelsWidget(
            napari_viewer,
            lineplot=self.lineplot,
            parent=self,
            app_state=self.app_state,
        )

        # Create shortcuts widget
        self.shortcut_widgets = ShortcutsWidget(parent=self)

        # Pass app_state to data_widget, as it's the main widget
        self.data_widget = DataWidget(
            napari_viewer,
            lineplot=self.lineplot,
            parent=self,
            app_state=self.app_state,
            labels_widget=self.labels_widget,
            plots_widget=self.plots_widget,
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
            widget_title="Plot controls",
        )

        self.add_widget(
            self.shortcut_widgets,
            collapsible=True,
            widget_title="Shortcuts",
        )

        self.collapsible_widgets[0].expand()  # expand the first widget
        self._bind_global_shortcuts(napari_viewer, self.labels_widget, self.data_widget)

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

        # Navigation
        @viewer.bind_key("m", overwrite=True)
        def next_trial(v):
            data_widget.next_trial()

        @viewer.bind_key("n", overwrite=True)
        def prev_trial(v):
            data_widget.prev_trial()

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
