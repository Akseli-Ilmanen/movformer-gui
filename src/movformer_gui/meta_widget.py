"""The main napari widget for the ``movement`` package."""

from napari.viewer import Viewer
from qt_niu.collapsible_widget import CollapsibleWidgetContainer
from qtpy.QtGui import QCloseEvent

from movformer_gui.data_widget import DataWidget
from movformer_gui.labels_widget import LabelsWidget


class MetaWidget(CollapsibleWidgetContainer):
    """The widget to rule all ``MovFormer`` napari widgets.

    This is a container of collapsible widgets, each responsible
    for handing specific tasks in the MovFormer napari workflow.
    """

    def __init__(self, napari_viewer: Viewer, parent=None):
        """Initialize the meta-widget."""
        super().__init__()

        # Store the napari viewer reference
        self.napari_viewer = napari_viewer

        # Add the data widget
        self.data_widget = DataWidget(napari_viewer, parent=self)
        self.add_widget(
            self.data_widget,
            collapsible=True,
            widget_title="Data controls",
        )

        # Add the labels widget
        self.labels_widget = LabelsWidget(napari_viewer, parent=self)
        self.add_widget(
            self.labels_widget,
            collapsible=True,
            widget_title="Label controls",
        )

        # Connect the widgets
        self.data_widget.set_labels_widget(self.labels_widget)

        # References for compatibility
        self.loader = self.collapsible_widgets[0]
        self.loader.expand()  # expand the data widget by default

    def closeEvent(self, event):
        """Handle close event by ensuring the DataWidget and LabelsWidget are properly closed."""
        # Get widgets from collapsible containers
        data_widget = self.collapsible_widgets[0].widget if len(self.collapsible_widgets) > 0 else None
        labels_widget = self.collapsible_widgets[1].widget if len(self.collapsible_widgets) > 1 else None
        
        # Save states and close data widget
        if data_widget and hasattr(data_widget, 'save_current_state'):
            data_widget.save_current_state()
        if data_widget and hasattr(data_widget, 'closeEvent'):
            data_widget.closeEvent(event)
        
        # Save states and close labels widget
        if labels_widget and hasattr(labels_widget, 'save_current_state'):
            labels_widget.save_current_state()
        if labels_widget and hasattr(labels_widget, 'closeEvent'):
            labels_widget.closeEvent(event)
            
        super().closeEvent(event)
