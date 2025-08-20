import re
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Union

def extract_csv_file_info(file_name: str, session_number: str) -> Tuple[str, str, str, str, str]:
    """
    Extracts session_date, trial, subject_id, and generates folder name and mp4 file name.

    Args:
        file_name: A string with the format 'YYYY-MM-DD_trial_SubjectID_DLC_3D[.csv|.m]'
        session_number: Suffix after date: 'XX' in 'YYYYMMDD_XX'

    Returns:
        session_date: The date in 'YYYY-MM-DD' format
        trial: The trial number or identifier after the date
        subject_id: The subject ID in the file
        folder_name: The folder name in 'YYYYMMDD_XX_SubjectID' format
        mp4_file_name: The MP4 filename in 'YYYY-MM-DD_trial_SubjectID-cam-1.mp4' format
    """
    pattern = r'(\d{4}-\d{2}-\d{2})_(\d+)_([A-Za-z]+)_DLC_3D'
    match = re.search(pattern, file_name)
    if not match:
        raise ValueError('Filename does not match the expected format.')
    session_date, trial, subject_id = match.groups()
    folder_name = f"{session_date.replace('-', '')}_{session_number}_{subject_id}\\"
    mp4_file_name = f"{session_date}_{str(trial).zfill(3)}_{subject_id}-cam-1.mp4"
    return session_date, trial, subject_id, folder_name, mp4_file_name


def get_all_trials_path_info(all_trials_path):
    """
    Extract subject_id, session_date, session_number, and dataset_name from a path string.
    Args:
        all_trials_path (str): Path string to parse.
    Returns:
        subject_id (str), session_date (str), session_number (str), dataset_name (str)
    """
    path = all_trials_path.replace('\\', '/')

    id_match = re.search(r'id-([^/\\]+)', path)
    subject_id = id_match.group(1) if id_match else ''

    date_sess_match = re.search(r'date-(\d{8})_(\d{2})', path)
    if date_sess_match:
        session_date = date_sess_match.group(1)
        session_number = date_sess_match.group(2)
    else:
        session_date = ''
        session_number = ''

    dataset_name = f'{session_date}-{session_number}_{subject_id}' 

    return subject_id, session_date, session_number, dataset_name


def load_motif_mapping(mapping_file: Union[str, Path] = "mapping.txt") -> Dict[int, Dict[str, np.ndarray]]:
    """
    Load motif mapping from a text file and return mapping dictionary with colors.

    Args:
        mapping_file: Path to the mapping file (default: "mapping.txt")

    Returns:
        Dictionary mapping motif_id to {'name': str, 'color': np.ndarray}

    Example mapping.txt file:
        0 background
        1 beakTip_pullOutStick
        2 beakTip_pushStick
        3 beakTip_peck
        4 beakTip_grasp
        5 beakTip_release
        6 beakTip_tap
        7 beakTip_touch
        8 beakTip_move
        9 beakTip_idle

    Example usage:
        >>> mapping = load_motif_mapping("mapping.txt")
        >>> print(mapping[1]['name'])  # 'beakTip_pullOutStick'
        >>> print(mapping[1]['color'])  # [1.0, 0.4, 0.698]
    """
    mapping_file = Path(mapping_file)
    
    motif_colors = [
        [1, 1, 1],           # background class
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
        [255, 128, 0]      #  add colours if needed
    ]
    
    motif_mappings = {}
    
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")
    
    with open(mapping_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                motif_id = int(parts[0])
                name = parts[1]
                
                color = np.array(motif_colors[motif_id]) / 255.0
                
                motif_mappings[motif_id] = {
                    'name': name,
                    'color': color
                }
    
    return motif_mappings
