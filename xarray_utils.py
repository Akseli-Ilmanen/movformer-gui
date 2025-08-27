import xarray as xr

def sel_valid(da, sel_kwargs):
    """
    Selects data from an xarray DataArray using only valid coordinate keys.
    This function filters the selection keyword arguments to include only those
    keys that are present in the DataArray's coordinates. It then performs the
    selection using the filtered arguments.
    Parameters
    ----------
    da : xarray.DataArray
        The DataArray from which to select data.
    sel_kwargs : dict
        Dictionary of selection arguments, where keys are coordinate names and
        values are the labels or slices to select.
    Returns
    -------
    numpy.ndarray
        The selected data as a numpy array.
    Notes
    -----
    - Invalid keys in `sel_kwargs` (i.e., keys not present in `da.coords`) are ignored.
    """

    valid_keys = set(da.coords)
    filt_kwargs = {k: v for k, v in sel_kwargs.items() if k in valid_keys}
    da = da.sel(**filt_kwargs)
    data = da.values 
    
    return data

