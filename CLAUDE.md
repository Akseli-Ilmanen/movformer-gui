# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MovFormer-GUI is a napari plugin for labeling start/stop times of animal movements. It integrates with MovFormer, a workflow using action segmentation transformers to predict movement segments. The GUI loads NetCDF datasets containing behavioral features, displays synchronized video/audio, and allows interactive motif labeling.

## Development Commands
! for bash mode
### Testing
```bash
# Run tests with tox
tox

# Run tests with pytest directly
pytest
```

### Code Quality
```bash
# Format code with black
black src/

# Lint with ruff (auto-fix enabled in config)
ruff check src/

# Line length: 120 characters (configured in pyproject.toml)
```

### Installation
```bash
# Development install
pip install -e .

# With napari and Qt dependencies
pip install -e ".[all]"

# Testing dependencies
pip install -e ".[testing]"
```

## Architecture

### Core Components

**MetaWidget** (`meta_widget.py`) - Main container widget that orchestrates all other widgets:
- Creates and manages `ObservableAppState` with YAML persistence
- Sets up cross-references between widgets
- Binds global keyboard shortcuts for napari
- Uses CollapsibleWidgetContainer for UI organization

**ObservableAppState** (`app_state.py`) - Central state management:
- Qt signal-based reactive state container
- Automatic YAML persistence (every 10 seconds)
- Manages dataset, file paths, plot settings, current selections
- Dynamic `_sel` attributes for user selections (trials_sel, keypoints_sel, etc.)

**DataWidget** (`data_widget.py`) - Data loading and trial navigation:
- File/folder selection for NetCDF data, videos, audio
- Dynamic combo boxes based on dataset dimensions
- Trial filtering by conditions
- Video/audio synchronization with napari playback

**LinePlot** (`lineplot.py`) - Main plotting widget:
- Matplotlib-based time series visualization
- Spectrogram overlay support with buffering
- Interactive motif selection and playback
- Synchronized with napari video timeline

**LabelsWidget** (`labels_widget.py`) - Motif labeling interface:
- Interactive motif creation (click-based boundary definition)
- Motif editing and deletion
- Color-coded motif visualization
- Export functionality for labeled data

### Data Flow

1. **Loading**: DataWidget loads NetCDF dataset → populates AppState → creates dynamic UI controls
2. **Selection**: User changes selections → AppState signals → widgets update plots/video
3. **Labeling**: User presses motif key → LabelsWidget activates → click twice on LinePlot → motif created
4. **Playback**: Right-click on motif → triggers video/audio playback at that time segment

### Widget Communication

Widgets communicate through:
- **AppState signals** for data changes
- **Direct references** set in MetaWidget (e.g., lineplot.set_plots_widget())
- **Cross-widget method calls** for complex interactions

### Key Design Patterns

- **Observer Pattern**: AppState emits signals, widgets react to changes
- **Centralized State**: All application state flows through ObservableAppState
- **Widget Composition**: MetaWidget composes and coordinates specialized widgets
- **Dynamic UI**: UI controls generated based on dataset structure

## Important Implementation Details

### AppState Persistence
- Only attributes in `_saveable_attributes` are persisted to YAML
- All `*_sel` attributes (user selections) are automatically saved
- Numeric values converted to Python types (not numpy) for YAML compatibility

### Audio/Video Synchronization
- Audio playback controlled by napari animation thread events
- Spectrogram data cached in buffers for performance
- Buffer cleared when switching trials or changing audio settings

### Keyboard Shortcuts
- Bound at napari viewer level in MetaWidget._bind_global_shortcuts()
- Motif keys (1-9, 0, Q, W, R, T) mapped to motif numbers 1-14
- Navigation keys (M/N for trials, arrows for plot navigation)

### Dataset Structure Requirements
- NetCDF format with time, trials dimensions
- Expected coordinates: cameras, mics, keypoints, individuals, features
- Video files matched by filename in dataset to video folder
