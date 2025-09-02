import sys
import os
sys.path.append(r'C:\Users\Admin\Documents\Akseli\Code\MovFormer\movformer')

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .meta_widget import MetaWidget
from .data_widget import DataWidget
from .labels_widget import LabelsWidget

# Import commonly used MovFormer modules
from movformer.utils import *
from movformer.features import *
from movformer.plots import *



__all__ = (
    "MetaWidget",
    "DataWidget", 
    "LabelsWidget",
    "LinePlotWidget",
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
