def snap_to_nearest_changepoint(x_clicked, changepoints):
    """
    Snap x_clicked to the nearest changepoint value.
    Returns (snapped_val, snapped_idx)
    """
    import numpy as np
    changepoints = np.asarray(changepoints)
    snapped_idx = np.argmin(np.abs(changepoints - x_clicked))
    snapped_val = int(round(changepoints[snapped_idx]))
    return snapped_val, snapped_idx


def remove_small_blocks(input_vec, min_motif_len):
    """
    Remove blocks shorter than min_motif_len from input_vec (set to 0).
    """
    import numpy as np
    if isinstance(input_vec, (str, bytes)):
        input_vec = np.array([int(c) for c in str(input_vec)])
    else:
        input_vec = np.array(input_vec)
    output_vec = input_vec.copy()
    i = 0
    while i < len(input_vec):
        if input_vec[i] != 0:
            val = input_vec[i]
            j = i
            while j < len(input_vec) and input_vec[j] == val:
                j += 1
            run_length = j - i
            if run_length < min_motif_len:
                output_vec[i:j] = 0
            i = j
        else:
            i += 1
    return output_vec


def fix_endings(labels, changepoints):
    """
    Fix situations where label ending was moved 1 backwards because previously there was a new label segment starting at that index but now is not anymore.
    """
    import numpy as np
    labels_out = np.array(labels).reshape(-1)
    change_positions = np.where(np.diff(labels_out) != 0)[0]
    segment_ends = change_positions
    for seg_end in segment_ends:
        if (seg_end + 1) in changepoints:
            if labels_out[seg_end] != 0 and labels_out[seg_end + 1] == 0:
                labels_out[seg_end + 1] = labels_out[seg_end]
    return labels_out
