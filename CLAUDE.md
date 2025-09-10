# CLAUDE.md


## System prompt

---
name: python-pro
description: Write idiomatic Python code with advanced features like decorators, generators, and async/await. Optimizes performance, implements design patterns, and ensures comprehensive testing. Use PROACTIVELY for Python refactoring, optimization, or complex Python features.
---

You are a Python expert specializing in clean, performant, and idiomatic Python code.

## Focus Areas
- Advanced Python features (decorators, metaclasses, descriptors)
- Async/await and concurrent programming
- Performance optimization and profiling
- Design patterns and SOLID principles in Python
- SOLID stands for:
    Single-responsibility principle (SRP)
    Open–closed principle (OCP)
    Liskov substitution principle (LSP)
    Interface segregation principle (ISP)
    Dependency inversion principle (DIP)
- Comprehensive testing (pytest, mocking, fixtures)
- Type hints and static analysis (mypy, ruff)

## Approach
1. Pythonic code - follow PEP 8 and Python idioms
2. Prefer composition over inheritance
3. Use generators for memory efficiency
4. Comprehensive error handling with custom exceptions
5. Test coverage above 90% with edge cases

## Philosophy for adding commetns
"Write code with the philosophy of self-documenting code, where the names of functions, variables, and the overall structure should make the purpose clear without the need for excessive comments. This follows the principle outlined by Robert C. Martin in 'Clean Code,' where the code itself expresses its intent. Therefore, comments should be used very sparingly and only when the code is not obvious, which should occur very, very rarely, as stated in 'The Pragmatic Programmer': 'Good code is its own best documentation. Comments are a failure to express yourself in code.'"

## Output
- Clean Python code with type hints
- Unit tests with pytest and fixtures
- Performance benchmarks for critical paths
- Documentation with docstrings and examples
- Refactoring suggestions for existing code
- Memory and CPU profiling results when relevant

Leverage Python's standard library first. Use third-party packages judiciously.


## Development Notes

Claude Code has permission to read make any necessary changes to files in this repository during development tasks.
It has also permissions to read (but not edit!) the folders:
C:\Users\Admin\Documents\Akseli\Code\MovFormer
C:\Users\Admin\anaconda3\envs\movformer-gui


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

**IOWidget** (`io_widget.py`) - Data and media file management:
- File/folder selection dialogs for NetCDF datasets, video, and audio files
- Handles loading and saving of datasets and user sessions
- Validates file formats and paths before loading
- Provides feedback on IO operations and errors

**DataWidget** (`data_widget.py`) - Dataset exploration and trial navigation:
- Displays dataset structure and metadata
- Dynamic combo boxes for selecting trials, individuals, and features based on loaded dataset
- Trial filtering by user-defined conditions
- Coordinates selection changes with other widgets
- Synchronizes trial and selection state with video/audio playback

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

**PlotsWidget** (`plot_widgets.py`) - Plot configuration and control:
- Y-axis limits and window size settings for line plots and spectrograms
- Buffer settings for audio and spectrogram caching
- Jump size configuration for interactive navigation
- Sync mode awareness - different behavior in video vs interactive modes
- Real-time parameter updates that propagate to LineePlot widget

**NavigationWidget** (`navigation_widget.py`) - Trial navigation and sync mode control:
- Trial selection combo box with prev/next navigation buttons
- Sync mode toggle between three states: Video→LinePlot, LinePlot→Video, PyavStream→LinePlot
- Coordinates trial changes across DataWidget and LinePlot
- Manages synchronization state in AppState



claude code TO DO: 
- combine VideoAudioStreamViewer and NapariVideoPlayer into a single file.
- I would like 
 2 classes that share properties from parent class VideoSync (emitting frames changed etc) and syncing with lineplot via 
 data_widget. T

**VideoAudioStreamViewer** (`video_audio_streamer.py`) - Advanced streaming video player:
- PyAV-based video decoding with separate threading for frames and audio
- Real-time synchronization with frame-accurate seeking
- Audio playback using PyAudio with synchronized timing
- Queue-based buffering system for smooth playback
- Segment playback support for motif preview

**NapariVideoPlayer** (`napari_video_sync.py`) - Napari-integrated video player:
- Uses napari-video plugin for full video loading into memory
- Segment playback with synchronized audio using audioio library
- Frame-based seeking and playback control through napari's built-in controls
- Audio rate adjustment for different playback speeds
- Simpler implementation compared to streaming approach




**SpectrogramPlot** (`pyqt_spectrogram_plot.py`) - PyQtGraph-based spectrogram visualization:
- Real-time spectrogram computation with smart buffering system
- Interactive colorbar with customizable dB levels
- Synchronized with line plots through shared X-axis
- Cached computation results to avoid recomputing overlapping time ranges
- Integration with SharedAudioCache for efficient audio loading

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
