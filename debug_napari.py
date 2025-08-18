#!/usr/bin/env python
"""Debug script for napari GUI."""

import napari
import sys
import os
from movformer_gui.meta_widget import MetaWidget


# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    # Reduce napari debug verbosity
    import logging
    logging.getLogger('napari').setLevel(logging.WARNING)
    
    # Start napari viewer
    viewer = napari.Viewer()
    
    # Add your plugin
    
    widget = MetaWidget(viewer)
    viewer.window.add_dock_widget(widget, name="MovFormer GUI")
    
    # Enable debugging - all print statements will show in terminal
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("DEBUG: Napari started with MovFormer GUI")
    print("DEBUG: Use Ctrl+C in terminal to stop")
    
    # Run napari
    napari.run()

if __name__ == "__main__":
    main()
