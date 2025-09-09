"""Data loading utilities for the movformer GUI."""


import xarray as xr
import numpy as np
from typing import Optional, Tuple
from pathlib import Path
from napari.utils.notifications import show_error



# rewrite this code by simplfying,
# use filter attrs xarray fucnction
# and place lots of statements like these to throw error if something doesn't occur:
        # assert(feature.shape[1] == event_seq_raw.shape[0])
        # assert(feature.shape[1] == boundary_seq_raw.shape[0])


def load_dataset(file_path: str) -> Tuple[Optional[xr.Dataset], Optional[dict]]:
    """Load dataset from file path and cache metadata on the instance.

    Returns:
        Tuple of (dataset, info_dict)
    """

    # Check file extension
    if Path(file_path).suffix != '.nc':
        error_msg = (
            f"Unsupported file type: {Path(file_path).suffix}. Expected .nc file.\n"
            "See documentation:\n"
            "https://movement.neuroinformatics.dev/user_guide/input_output.html#native-saving-and-loading-with-netcdf"
        )
        show_error(error_msg)
        return None, None

    ds = xr.open_dataset(file_path).load()

    # Check minimum required coordinates and variables
    required_coords = ['trials', 'time']
    missing_coords = [coord for coord in required_coords if coord not in ds.coords]
    if missing_coords:
        error_msg = f"Dataset missing required coordinates: {missing_coords}"
        show_error(error_msg)
        return None, None

    required_vars = ["labels"]
    missing_vars = [var for var in required_vars if var not in ds.data_vars]
    if missing_vars:
        error_msg = f"Dataset missing required variables: {missing_vars}"
        show_error(error_msg)
        return None, None

    if not hasattr(ds, "fps"):
        show_error("Dataset must have 'fps' attribute for video processing.")



    # Initialize info dictionary to categorize variables by type
    name_info = {}
    data_info = {}




    name_info['trials'] = ds.coords['trials'].values.astype(int)

    if 'keypoints' in ds.coords:
        name_info['keypoints'] = ds.coords['keypoints'].values.astype(str)

    if 'individuals' in ds.coords:
        name_info['individuals'] = ds.coords['individuals'].values.astype(str)

    # Ensure 'trials', 'keypoints', 'individuals' are all 1D
    for name in ['trials', 'keypoints', 'individuals']:
        if name in ds.coords:
            arr = ds.coords[name].values
            if arr.ndim != 1:
                show_error(f"Coordinate '{name}' must be 1D, but got shape {arr.shape}")


    # Process coordinates
    for coord in ds.coords.values():
        ctype = coord.attrs.get('type') if isinstance(getattr(coord, 'attrs', None), dict) else None
        if ctype is not None:
            if ctype not in name_info:
                name_info[ctype] = []
                data_info[ctype] = []
            name_info[ctype].append(coord.name)
            data_info[ctype].append(coord)

    # Process data variables
    for var in ds.data_vars.values():
        vtype = var.attrs.get('type') if isinstance(getattr(var, 'attrs', None), dict) else None
        if vtype is not None:
            if vtype not in name_info:
                name_info[vtype] = []
                data_info[vtype] = []
            name_info[vtype].append(var.name)


    if "mics" in name_info and not hasattr(ds, "sr"):
        show_error("Dataset must have 'sr' (for sampling rate) attribute for microphone processing.")


    # Validate types against allowed keys
    allowed_keys = ['trials', 'keypoints', 'individuals', 'features', 'colors', 'trial_conditions', 'cameras', 'mics']
    invalid_types = [t for t in name_info.keys() if t not in allowed_keys]
    # Check for required keys
    required_keys = ['trials', 'features', 'cameras']
    missing_required = [k for k in required_keys if k not in name_info]
    if missing_required:
        show_error(f"Dataset missing required types: {missing_required}. Please specify these types for your variables/coordinates.")
    if invalid_types:
        error_msg = (
            f"Invalid types found in dataset: {invalid_types}. "
            f"Allowed types are: {allowed_keys}. "
            "Please specify types for your variables and coordinates, e.g.:\n"
            '    ds["pos"].attrs["type"] = "features"\n'
            '    ds["vel"].attrs["type"] = "features"\n'
            '    ds["speed"].attrs["type"] = "features"\n'
            '    ds["angle_rgb"].attrs["type"] = "colors"\n'
            '    ds["poscat"].attrs["type"] = "trial_conditions"\n'
            '    ds["num_pellets"].attrs["type"] = "trial_conditions"\n'
            '    ds["cam1_files"].attrs["type"] = "cameras"\n'
            '    ds["cam2_files"].attrs["type"] = "cameras"\n'
            '    ds["mic1_files"].attrs["type"] = "mics"\n'
            '    ds["mic2_files"].attrs["type"] = "mics"\n'
        )
        show_error(error_msg)

    # Perform comprehensive data type validation
    if not validate_dataset_types(ds, data_info):
        show_error("Dataset validation failed - see error messages above")


    return ds, name_info



def validate_dataset_types(ds: xr.Dataset, info: dict) -> bool:
    """Validate data types in the dataset according to specifications.
    
    Args:
        ds: The xarray Dataset to validate
        info: Dictionary containing categorized variables/coordinates
        
    Returns:
        True if all validations pass, False otherwise
    """
    validation_errors = []
    
    
    labels = ds['labels'].values
    if not isinstance(labels, np.ndarray):
        labels = np.array(labels)
    if np.issubdtype(labels.dtype, np.integer):
        pass  # valid
    elif np.issubdtype(labels.dtype, np.floating):
        if not np.all(np.equal(np.mod(labels, 1), 0)):
            validation_errors.append("Data variable 'labels' must be integers or floats representing whole numbers")
    else:
        validation_errors.append("Data variable 'labels' must be an array of integers or whole-number floats")

    
    

    # Check colors - must be numpy array of shape (N, 3)
    if 'colors' in info:
        for var in info['colors']:
            colors = var.values
            if not isinstance(colors, np.ndarray):
                validation_errors.append(f"Variable '{var.name}' with type 'colors' must be a numpy array")
                continue
            if colors.ndim < 2:
                validation_errors.append(f"Variable '{var.name}' with type 'colors' must have at least 2 dimensions, got {colors.ndim}")
                continue
            if 3 not in colors.shape:
                validation_errors.append(f"Variable '{var.name}' with type 'colors' must have one dimension of size 3, got shape {colors.shape}")
            if not np.issubdtype(colors.dtype, np.number):
                validation_errors.append(f"Variable '{var.name}' with type 'colors' must contain numeric values")
    
    # Check features - must be arrays
    if 'features' in info:
        for var in info['features']:
            if not isinstance(var.values, np.ndarray):
                validation_errors.append(f"Variable '{var.name}' with type 'features' must be an array")
    
    # Check trial_conditions - must be vector of ints
    if 'trial_conditions' in info:
        for var in info['trial_conditions']:
            conditions = var.values
            if not isinstance(conditions, np.ndarray):
                conditions = np.array(conditions)
            if len(conditions.shape) != 1:
                validation_errors.append(f"Variable '{var.name}' with type 'trial_conditions' must be a 1D vector, got shape {conditions.shape}")
            if not np.issubdtype(conditions.dtype, np.integer):
                validation_errors.append(f"Variable '{var.name}' with type 'trial_conditions' must contain integers")
    
    # Check cameras - must be array/list of strings
    if 'cameras' in info:
        for var in info['cameras']:
            cameras = var.values
            if not isinstance(cameras, np.ndarray):
                cameras = np.array(cameras)
            if not (cameras.dtype.kind in ['U', 'S', 'O']):  # Unicode, byte string, or object (string)
                validation_errors.append(f"Variable '{var.name}' with type 'cameras' must be an array of strings")
    
    # Check mics - must be array/list of strings
    if 'mics' in info:
        for var in info['mics']:
            mics = var.values
            if not isinstance(mics, np.ndarray):
                mics = np.array(mics)
            if not (mics.dtype.kind in ['U', 'S', 'O']):  # Unicode, byte string, or object (string)
                validation_errors.append(f"Variable '{var.name}' with type 'mics' must be an array of strings")
    
    # Check special data variables
    # Check changepoints - must be boolean array or only contain 0 or 1 if present
    if 'changepoints' in ds.data_vars:
        changepoints = ds['changepoints'].values
        if not isinstance(changepoints, np.ndarray):
            changepoints = np.array(changepoints)
        if not (np.issubdtype(changepoints.dtype, np.bool_) or
                (np.issubdtype(changepoints.dtype, np.integer) and np.isin(changepoints, [0, 1]).all())):
            validation_errors.append("Data variable 'changepoints' must be a boolean array or contain only 0 and 1")
    


    # Report validation errors
    if validation_errors:
        error_msg = "Dataset validation failed:\n" + "\n".join(f"• {error}" for error in validation_errors)
        show_error(error_msg)
        return False
    
    return True

