"""The main napari widget for the ``movement`` package."""

from napari.viewer import Viewer
from qt_niu.collapsible_widget import CollapsibleWidgetContainer

from movformer_gui.labels_widget import LabelsWidget


class MetaWidget(CollapsibleWidgetContainer):
    """The widget to rule all ``MovFormer`` napari widgets.

    This is a container of collapsible widgets, each responsible
    for handing specific tasks in the MovFormer napari workflow.
    """

    def __init__(self, napari_viewer: Viewer, parent=None):
        """Initialize the meta-widget."""
        super().__init__()

        # Add the playback widget
        self.add_widget(
            LabelsWidget(napari_viewer, parent=self),
            collapsible=True,
            widget_title="Labelling controls",
        )

        self.loader = self.collapsible_widgets[0]
        self.loader.expand()  # expand the loader widget by default
