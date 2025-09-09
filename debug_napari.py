#!/usr/bin/env python
"""Debug script for napari GUI."""

import os
import sys

import napari
import json

# Load user_paths.json
desktop_path = os.path.join(os.environ.get("USERPROFILE", os.environ.get("HOME")), "Desktop")
with open(os.path.join(desktop_path, "user_paths.json"), "r") as f:
    paths = json.load(f)
    
user = "Akseli"
movformer_folder = paths[user].get("movformer_folder")

sys.path.insert(0, movformer_folder)



from movformer_gui.meta_widget import MetaWidget

# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main():
    # Suppress Qt geometry warnings
    import logging
    import warnings

    # Filter out Qt geometry warnings
    warnings.filterwarnings("ignore", message=".*QWindowsWindow::setGeometry.*")
    warnings.filterwarnings("ignore", category=UserWarning, module="vispy")

    # Reduce napari and vispy debug verbosity
    logging.getLogger("napari").setLevel(logging.ERROR)
    logging.getLogger("vispy").setLevel(logging.ERROR)
    logging.getLogger("qtpy").setLevel(logging.ERROR)

    import matplotlib

    matplotlib.set_loglevel("WARNING")

    # Suppress Qt warnings at the OS level
    os.environ["QT_LOGGING_RULES"] = "qt.*=false"

    # Start napari viewer
    viewer = napari.Viewer()

    # Add your plugin

    widget = MetaWidget(viewer)
    viewer.window.add_dock_widget(widget, name="MovFormer GUI")

    print("DEBUG: Napari started with MovFormer GUI")
    print("DEBUG: Use Ctrl+C in terminal to stop")

    # Run napari
    napari.run()


if __name__ == "__main__":
    main()
