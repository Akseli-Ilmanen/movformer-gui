"""Data loading utilities for the movformer GUI."""

import os
import xarray as xr
from typing import Optional, Tuple
from pathlib import Path


# Supported file types for loading.
SUPPORTED_EXTENSIONS = ['.nc'] # for dataset file
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv']
AUDIO_EXTENSIONS = ['.wav', '.mp3', '.flac', '.aac']




def load_dataset(file_path: str) -> Tuple[Optional[xr.Dataset], Optional[dict], Optional[str]]:
    """Load dataset from file path and cache metadata on the instance.
    """
    if Path(file_path).suffix in SUPPORTED_EXTENSIONS:
        ds = xr.open_dataset(file_path)
    else:
        return None, None, f"Unsupported file extension: {Path(file_path).suffix}"

    required_coords = ['trial', 'time']
    missing_coords = [coord for coord in required_coords if coord not in ds.coords]
    if missing_coords:
        raise ValueError(f"Dataset missing required coordinates: {missing_coords}")

    info = _get_dataset_info(ds)
    return ds, info, None

def _get_dataset_info(ds: xr.Dataset) -> dict:
    """Extract generic information from the dataset.

    Only assumes ``trial`` and ``time`` exist. All variables and coordinates
    are summarized, including any declared ``type`` attributes (e.g. "feature",
    "color", "labels", "paths").
    """
    info = {
        'trials': ds.coords['trial'].values.tolist(),
        'n_timepoints': len(ds.coords['time']),
        'keypoints': ds.coords['keypoints'].values.tolist() if 'keypoints' in ds.coords else [],
        'variables': list(ds.data_vars.keys()),
        'coords': list(ds.coords.keys()),
        'variable_types': {
            name: (var.attrs.get('type') if isinstance(getattr(var, 'attrs', None), dict) else None)
            for name, var in ds.data_vars.items()
        },
        'coord_types': {
            name: (ds.coords[name].attrs.get('type') if isinstance(getattr(ds.coords[name], 'attrs', None), dict) else None)
            for name in ds.coords
        },
        'feature_variables': [],
        'color_variables': [],
    }
    
    for var_name, var in ds.data_vars.items():
        vtype = var.attrs.get('type') if isinstance(getattr(var, 'attrs', None), dict) else None
        if vtype == 'feature':
            info['feature_variables'].append(var_name)
        elif vtype == 'color':
            info['color_variables'].append(var_name)
 
    for t in ['video', 'audio']:
        vars_by_type = [name for name, typ in info['variable_types'].items() if typ == t]
        coords_by_type = [name for name, typ in info['coord_types'].items() if typ == t]
        if t == 'video':
            info['cameras'] = vars_by_type + coords_by_type
        elif t == 'audio':
            info['mics'] = vars_by_type + coords_by_type
    

    info['trial_condition'] = [name for name, typ in info['coord_types'].items() if typ == "trial_condition"]

    return info

def validate_media_folder(folder_path: str, media_type: str) -> bool:
    """Validate that the folder exists and contains files with given media type extensions.
    Args:
        folder_path: Path to the folder.
        media_type: 'video' or 'audio'.
    Returns:
        True if folder contains at least one file with the specified media type extension.
    """
    if not folder_path or not os.path.exists(folder_path):
        return False
    folder = Path(folder_path)
    extensions = VIDEO_EXTENSIONS if media_type == 'video' else AUDIO_EXTENSIONS if media_type == 'audio' else []
    for ext in extensions:
        if list(folder.glob(f'*{ext}')):
            return True
    return False


