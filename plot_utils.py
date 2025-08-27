import matplotlib.pyplot as plt
import numpy as np
from xarray_utils import sel_valid

def get_motif_colours(seed=9):
    # cmap_names = ['tab20']
    # colors = []
    # for name in cmap_names:
    #     cmap = plt.get_cmap(name)
    #     colors.extend([cmap(i) for i in range(cmap.N)])
    # category_colors = colors
    # # Remove greys (indices 14 and 15 in tab20)
    # tabnogrey = np.concatenate([category_colors[:14], category_colors[16:]]).tolist()
    # category_colors_rgb = [tuple(float(c) for c in color[:3]) for color in tabnogrey]
    # np.random.seed(seed)
    # np.random.shuffle(category_colors_rgb)
    # category_colors_rgb = [[0, 0, 0]] + category_colors_rgb

    # Manually chosen are better
    category_colors_rgb = [
        [1, 1, 1],
        [255, 102, 178],
        [102, 158, 255],
        [153, 51, 255],
        [255, 51, 51],
        [102, 255, 102],
        [255, 153, 102],
        [0, 153, 0],
        [0, 0, 128],
        [255, 255, 0],
        [0, 204, 204],
        [128, 128, 0],
        [255, 0, 255],
        [255, 165, 0],
        [0, 128, 255],      
        [128, 0, 255],      
        [255, 128, 0]       
    ]
    return category_colors_rgb




def plot_multidim(ax, time, data, coord_labels=None):
    """
    Plot multi-dimensional data (e.g., pos, vel) over time.
    data: shape (time, space)
    coord_labels: list of labels for each dimension (e.g., ['x', 'y', 'z'])
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    for i in range(data.shape[1]):
        label = coord_labels[i] if coord_labels is not None else f"dim {i}"
        ax.plot(time, data[:, i], label=label)

    return ax


def plot_singledim(ax, time, data, color_data=None, changepoints=None):
    """
    Plot single-dimensional data (e.g., speed) over time.
    Optionally color the curve and mark changepoints.
    """

    if color_data is not None and color_data.shape[1] == 3:
        # color_data: shape (time, 3)
        for i in range(len(data) - 1):
            x_vals = [time[i], time[i+1]]
            y_vals = [data[i], data[i+1]]
            color = color_data[i] if i < len(color_data) else [0, 0, 0]
            ax.plot(x_vals, y_vals, color=color, linewidth=2)
    else:
        ax.plot(time, data, label="Speed")

    if changepoints is not None:
        idxs = np.where(changepoints)[0]
        ax.scatter(time[idxs], data[idxs], edgecolor='black', facecolor='none', s=50, marker='o', label="Changepoints")


    return ax

def plot_ds_variable(ax, ds, ds_kwargs, variable, color_variable=None):
    """
    Plot a variable from ds for a given trial and keypoint.
    Handles both multi-dimensional (e.g., pos, vel) and single-dimensional (e.g., speed) variables.

    e.g. ds_kwargs: {trials=20, keypoints="beakTip", individuals="Freddy"}

    """
    # Use ds.sel for direct selection
    var = ds[variable]
    time = ds["time"].values

    
    data = sel_valid(var, ds_kwargs) 
    
    
    # (time, XX), e.g. (time, space)
    if data.ndim == 2:

        valid_keys = set(data.coords)
        filt_kwargs = {k: v for k, v in ds_kwargs.items() if k in valid_keys}

        coord_dims = var.sel(**filt_kwargs).dims[-1]
        coord_labels = list(ds[coord_dims].values)
        ax = plot_multidim(ax, time, data, coord_labels=coord_labels)

    # (time, )
    elif data.ndim == 1:

        color_data = None
        changepoints = None  # Initialize changepoints variable
        
        for v in ds.data_vars:
            if v == color_variable and ds.attrs["plotColors"] == variable:

                color_data = sel_valid(ds[v], ds_kwargs)
          
        if hasattr(ds, "plotChangepoints") and ds.attrs["plotChangepoints"] == variable:
            changepoints = ds["changepoints"].sel(**ds_kwargs).values

        ax = plot_singledim(ax, time, data, color_data=color_data, changepoints=changepoints)

    else:
        print(f"Variable '{variable}' not supported for plotting.")


    if hasattr(ds, "boundary_events"):
        boundary_events_raw = ds["boundary_events"].sel(trials=ds_kwargs["trials"]).values
        valid_events = boundary_events_raw[~np.isnan(boundary_events_raw)]
        eventsIdxs = valid_events.astype(int)
        eventsIdxs = eventsIdxs[(eventsIdxs >= 0) & (eventsIdxs < len(time))]
        
        for event in eventsIdxs:
            ax.axvline(x=time[event], color='k')


    ylabel = var.attrs.get("ylabel", variable)
    title = ", ".join([f"{k}={v}" for k, v in ds_kwargs.items()])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc='upper right')

    return ax

      