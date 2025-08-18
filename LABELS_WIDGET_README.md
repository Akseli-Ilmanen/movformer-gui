# Labels Widget Documentation

The Labels Widget is a powerful tool for manually annotating movement motifs in time-series data. It allows researchers to label different behavioral segments directly from visualized movement plots.

## Features

### 1. Motif Library
- Loads motif definitions from `mapping.txt` file
- Displays available motif types with their colors
- Each motif has an ID, name, and associated color

### 2. Interactive Labeling
- **Label Mode**: Toggle on/off for segment selection
- **Click-based Selection**: Click start and end points on plots to define segments
- **Changepoint Snapping**: Automatically snaps selections to detected changepoints
- **Visual Feedback**: Shows selected segments with colored rectangles

### 3. Motif Management
- **Apply**: Confirm and save the selected motif segment
- **Delete**: Remove existing motif labels
- **Edit**: Reserved for future motif boundary adjustment features

### 4. Data Integration
- Works with xarray datasets containing movement data
- Supports multiple trials, keypoints, and variables
- Updates labels in real-time
- Integrates with changepoint detection

## Usage Instructions

### Basic Workflow
1. **Load Data**: Use the Data Widget to load your movement dataset
2. **Select Data**: Choose trial, keypoint, and variable to visualize
3. **Choose Motif**: Select a motif type from the motif library table
4. **Enable Labeling**: Check the "Label Mode" checkbox
5. **Select Segment**: Click start and end points on the plot
6. **Apply Label**: Click "Apply" to save the motif label

### Keyboard Shortcuts
- `A`: Apply selected motif segment
- `D`: Delete motif at cursor position
- `E`: Reserved for future edit functionality

### Data Format Requirements
Your dataset should include:
- **labels**: `(trial, time, keypoints)` - categorical labels array
- **changepoints**: `(trial, time, keypoints)` - binary changepoint detection
- **speed/velocity data**: For visualization and analysis

### Motif Mapping File
The `mapping.txt` file defines available motifs:
```
0 background 1 1 1
1 beakTip_pullOutStick 255 102 178
2 beakTip_diagonalToBox 102 158 255
...
```
Format: `ID name R G B` (RGB values 0-255)

## Integration with MovFormer GUI

The Labels Widget automatically integrates with the main MovFormer interface:
- Appears as a dockable panel in napari
- Syncs with data selection from the Data Widget
- Updates in real-time as you navigate between trials
- Saves state between sessions

## Technical Details

### Signal/Slot Architecture
- `labels_updated`: Emitted when labels are modified
- Connects to other widgets for synchronized updates

### State Management
- Preserves selections between sessions
- Saves motif preferences and edit states
- Restores previous work automatically

### Error Handling
- Graceful fallback if mapping file is missing
- Validates data format compatibility
- Provides user feedback for common issues

## Examples

### Creating a Demo Dataset
```python
from movformer_gui.create_demo_data import save_demo_dataset
demo_file = save_demo_dataset("my_demo.nc")
```

### Programmatic Label Access
```python
# Get current labels from widget
labels = labels_widget.get_labels()

# Labels array format: [0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, ...]
# where numbers represent motif IDs from mapping.txt
```

## Tips and Best Practices

1. **Use Changepoints**: Let the widget snap to detected changepoints for more consistent labeling
2. **Work Systematically**: Label one motif type at a time across all trials
3. **Save Frequently**: The widget auto-saves, but manual saves ensure data integrity
4. **Quality Control**: Review labeled segments using the plot visualization
5. **Collaboration**: Share mapping.txt files for consistent labeling across team members

## Troubleshooting

### Common Issues
- **Motifs not loading**: Check that mapping.txt is in the correct location
- **Clicking not working**: Ensure "Label Mode" is enabled
- **Segments not applying**: Verify a motif is selected in the table

### Performance Tips
- Work with smaller time windows for large datasets
- Use changepoint detection to reduce manual precision requirements
- Close unused dock widgets to improve responsiveness

## Future Enhancements
- Bulk labeling operations
- Label validation and consistency checks
- Export capabilities for labeled data
- Integration with machine learning models for semi-automatic labeling
