from typing import TYPE_CHECKING, List

from magicgui import magic_factory

from pprint import pprint
from glob import glob
import os
import sys
import dask
import dask.array as da
import re
import xarray as xr
from tifffile import imread, imsave
from pathlib import Path
import napari
from napari.utils.notifications import show_info, show_error

if TYPE_CHECKING:
    import napari

#layers created by this plugin
napari_layers = []

def file_name_patter_matcher(pattern):
    def fun(x):
        # r = r'_T[\d\.-]+.'
        r = "({0})(\d+)".format("|".join(pattern))
        rs = re.search(r, x)
        if rs:
            span = rs.span()
            return x[span[0]+2:span[1]-1]
        return '0'
    return fun

def create_zarr(metadata):
    
    da_params = {'shape' : metadata['shape'], 
                'dtype' : metadata['image_type']}
    separator = metadata['separator']
    # separate channels
    movie_dict = {}
    for channel in metadata['channels']:
        movie = list()
        # channel = [i.strip() for i in channel]
        channel = channel.strip()

        file_list = list(glob(os.path.join(metadata['path'], f"*{channel}", f"*{channel}*.tif")))
        if not metadata['dir_seprated']:
            file_list = list(glob(os.path.join(metadata['path'], f"*{separator}{channel}*.tif")))

        print("file_list", len(file_list))
        file_list.sort(key=file_name_patter_matcher(metadata['patterns']))
        print(channel, len(file_list))
        for index, file in enumerate(file_list):
            movie.append(da.from_delayed(dask.delayed(imread)(file), **da_params))

        movie_dict[channel] = movie

    
    frame_check = set(len(i) for _, i in movie_dict.items())
    print("frame_check", frame_check)

    if len(frame_check) > 1:
        print("both channels must have similar timpoints ", frame_check) 
        show_error("both channels must have similar timpoints")
        return
    
    frames = list(range(0, list(frame_check)[0]))
    print(frame_check)
    print(frames)
    
    if frames:
        # Convert dict to Dask array, preserving frame order
        da_arr = da.stack([movie for _, movie in movie_dict.items()])
        
        # Convert to Xarray DataArray
        xr_arr = xr.DataArray(data=da_arr, dims=['c', 't', 'z', 'y', 'x'], 
                                coords={'c' : metadata['channels'], 't' : frames}, attrs=metadata)
        
        # Convert to Xarray Dataset
        dset = xr_arr.to_dataset(dim='c')
        dset.to_zarr(Path(metadata['output']), consolidated=None)
        # return (dset, {'scale':metadata['scale']}, 'image')
        return dset
    return None

@magic_factory(call_button="Generate", 
               path={'label': "Path", 'widget_type':"FileEdit", 'mode':'d'},
               output={'label': "Output file", 'widget_type':"FileEdit", 'mode':'w', 'filter':'*.zarr'},
               patterns={'label':"Time point detection pattern:", 'value':"_T"},
               sunit={'label': "Unit", 'value':"um"},
               scale={'label': "X, Y, Z pixel size", 'widget_type':'ListEdit', 'value':[.210,.210,.4] },
               nchannels={'label':'Number of channles'},
               channels={'label':"Channel names", 'value':['488', '642']},
               dir_seprated={'label':"Channels are separated in dirctory"},
               separator={'label':"File name prams separator", 'value':'_'}
            )
def get_metadata(
                path:Path,
                output: Path,
                patterns:str, 
                sunit: str, 
                scale:List[float], 
                nchannels:int, 
                channels:List[str],
                dir_seprated:bool,
                separator: str,
                viewer: napari.Viewer
                ):
    
    print("napari_layers -> ", len(napari_layers))
    if len(napari_layers):
        for layer in napari_layers:
            del viewer.layers[layer.name]
        napari_layers.clear()
    viewer.reset_view()

    metadata = {}
    metadata['path'] = str(path)
    metadata['output'] = str(output)
    metadata['dir_seprated'] = dir_seprated
    metadata['patterns'] = patterns
    metadata['channels_count'] = nchannels
    metadata['channels'] = channels
    metadata['scale'] = scale
    metadata['scale_unit'] = sunit
    metadata['separator'] = separator
    
    # infer shape and dtype from first frame
    sample = list(glob(os.path.join(path, f"*{channels[0]}", "*.tif")))
    
    if not dir_seprated:
        sample = list(glob(os.path.join(path, f"*{separator}{channels[0]}*.tif")))
    
    print("sample total ", len(sample))
    if len(sample):
        sample = sample[0]


    sample_tiff = imread(sample)

    metadata['shape'] = sample_tiff.shape
    metadata['image_type'] = sample_tiff.dtype.name
    

    # call create zarr
    dset= create_zarr(metadata)
    
    if dset:
        show_info('File created')
        dset_scale = [1, *dset.attrs['scale'][::-1]]
        for channel, value in dset.data_vars.items():
            napari_layers.append(viewer.add_image(da.array(value), scale=dset_scale, name=channel, blending='additive', rendering='mip'))
