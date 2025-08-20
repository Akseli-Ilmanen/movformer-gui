try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .meta_widget import MetaWidget
from .data_widget import DataWidget
from .labels_widget import LabelsWidget
from .lineplot import LinePlot
from plot_utils import get_motif_colours, plot_ds_variable
from file_utils import load_motif_mapping

__all__ = (
    "MetaWidget",
    "DataWidget", 
    "LabelsWidget",
    "LinePlotWidget",
    "get_motif_colours",
    "plot_ds_variable",
    "load_motif_mapping",
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
