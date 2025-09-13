#!/usr/bin/env python3
"""
Check current validation logic for ds['labels'] to see what it validates.
"""
import xarray as xr
import numpy as np

# Create mock dataset to test validation
def create_mock_dataset():
    """Create a mock dataset with labels to test validation."""
    time_coords = np.arange(0, 100, 0.1)  # 1000 time points
    individuals = ['mouse1', 'mouse2']
    trials = np.arange(5)

    # Create labels with time and individuals dimensions (proper structure)
    labels_proper = xr.DataArray(
        np.random.randint(0, 5, size=(len(trials), len(time_coords), len(individuals))),
        coords={'trials': trials, 'time': time_coords, 'individuals': individuals},
        dims=['trials', 'time', 'individuals'],
        name='labels'
    )

    # Create labels missing individuals dimension (improper)
    labels_missing_individuals = xr.DataArray(
        np.random.randint(0, 5, size=(len(trials), len(time_coords))),
        coords={'trials': trials, 'time': time_coords},
        dims=['trials', 'time'],
        name='labels'
    )

    # Create labels with float values (but whole numbers)
    labels_float_whole = xr.DataArray(
        np.random.randint(0, 5, size=(len(trials), len(time_coords), len(individuals))).astype(float),
        coords={'trials': trials, 'time': time_coords, 'individuals': individuals},
        dims=['trials', 'time', 'individuals'],
        name='labels'
    )

    # Create labels with non-whole float values (should fail)
    labels_float_nonwhole = xr.DataArray(
        np.random.random(size=(len(trials), len(time_coords), len(individuals))),
        coords={'trials': trials, 'time': time_coords, 'individuals': individuals},
        dims=['trials', 'time', 'individuals'],
        name='labels'
    )

    # Test datasets
    ds_proper = xr.Dataset({'labels': labels_proper})
    ds_missing_individuals = xr.Dataset({'labels': labels_missing_individuals})
    ds_float_whole = xr.Dataset({'labels': labels_float_whole})
    ds_float_nonwhole = xr.Dataset({'labels': labels_float_nonwhole})

    return ds_proper, ds_missing_individuals, ds_float_whole, ds_float_nonwhole

def check_labels_validation(ds):
    """Check what the current validation does for labels."""
    print(f"Dataset labels coordinates: {ds['labels'].coords}")
    print(f"Dataset labels dimensions: {ds['labels'].dims}")
    print(f"Dataset labels shape: {ds['labels'].shape}")
    print(f"Dataset labels dtype: {ds['labels'].dtype}")

    # Check what current validation does (from the code I saw)
    labels = ds['labels'].values
    if not isinstance(labels, np.ndarray):
        labels = np.array(labels)

    print(f"Labels is numpy array: {isinstance(labels, np.ndarray)}")
    print(f"Labels dtype is integer: {np.issubdtype(labels.dtype, np.integer)}")
    print(f"Labels dtype is floating: {np.issubdtype(labels.dtype, np.floating)}")

    if np.issubdtype(labels.dtype, np.floating):
        all_whole = np.all(np.equal(np.mod(labels, 1), 0))
        print(f"All float values are whole numbers: {all_whole}")

    # Check for required coordinates
    has_time = 'time' in ds['labels'].coords
    has_individuals = 'individuals' in ds['labels'].coords
    print(f"Has 'time' coordinate: {has_time}")
    print(f"Has 'individuals' coordinate: {has_individuals}")

    return has_time, has_individuals

if __name__ == "__main__":
    datasets = create_mock_dataset()
    names = ['proper', 'missing_individuals', 'float_whole', 'float_nonwhole']

    for ds, name in zip(datasets, names):
        print(f"\n=== Testing {name} dataset ===")
        has_time, has_individuals = check_labels_validation(ds)
        print(f"Validation result - time: {has_time}, individuals: {has_individuals}")