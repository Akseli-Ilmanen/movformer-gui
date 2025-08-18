try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .meta_widget import MetaWidget
from .data_widget import DataWidget
from .labels_widget import LabelsWidget
from .lineplot_widget import LinePlotWidget
from .state_manager import GUIStateManager

__all__ = (
    "MetaWidget",
    "DataWidget", 
    "LabelsWidget",
    "LinePlotWidget",
    "GUIStateManager",
)

# from .reader import napari_get_reader
# from ._widget import (
#     ExampleQWidget,
#     ImageThreshold,
#     threshold_autogenerate_widget,
#     threshold_magic_widget,
# )
# from ._writer import write_multiple, write_single_image

# __all__ = (
#     "napari_get_reader",
#     "write_single_image",
#     "write_multiple",
#     "ExampleQWidget",
#     "ImageThreshold",
#     "threshold_autogenerate_widget",
#     "threshold_magic_widget",
# )
