5. Read the README for more info: https://github.com/napari/napari-plugin-template
6. We've provided a template description for your plugin page on the napari hub at `.napari-hub/DESCRIPTION.md`.
You'll likely want to edit this before you publish your plugin.
7. Consider customizing the rest of your plugin metadata for display on the napari hub:
https://github.com/chanzuckerberg/napari-hub/blob/main/docs/customizing-plugin-listing.md


can do somethign similar to `movement launch` with:

def main():
    # Start napari viewer
    viewer = napari.Viewer()
    
    # Add your plugin
    from movformer_gui.meta_widget import MetaWidget
    widget = MetaWidget(viewer)
    viewer.window.add_dock_widget(widget, name="MovFormer GUI")




Move some of the code about `_update_plot` in `data_widget` to lineploit_widget