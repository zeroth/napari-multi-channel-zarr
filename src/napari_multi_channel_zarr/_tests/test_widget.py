import numpy as np

from napari_multi_channel_zarr import get_metadata

#TODO: add test for create_zarr function

def test_get_metadata(make_napari_viewer, capsys):
    #TODO: improve this test
    viewer = make_napari_viewer()
    my_widget = get_metadata
    viewer.window.add_dock_widget(my_widget)