# STEP File Viewer

A modular, feature-rich CAD file viewer for STEP files with interactive face selection capabilities.

## Features

- **3D Visualization**: Display STEP files with native BREP representation
- **Face Selection**: Select and highlight individual faces with customizable colors
- **Interactive Navigation**: Rotate, pan, and zoom with mouse controls
- **Color Management**: Dynamic color schemes with keyboard shortcuts
- **Parts Tree**: Navigate model hierarchy in a tree view
- **Anti-aliasing**: Smooth rendering with configurable MSAA
- **Planar Alignment**: Lay parts flat for CNC cutting visualization
- **Multi-Plate Management**: Organize parts across multiple material sheets with automatic grid layout
- **Part Association**: Automatic part-to-plate assignment based on position
- **Exclusion Zones**: Draw red rectangles to mark off-limits areas on plates (for defects, clamps, etc.)

## Installation

```bash
# Install dependencies
conda install -c conda-forge pythonocc-core
```

## Usage

```bash
python main.py path/to/model.step
```

## Project Structure

```
step_viewer/
├── __init__.py              # Package initialization
├── config.py                # Configuration settings
├── viewer.py                # Main viewer coordinator
│
├── controllers/             # Event handling
│   ├── __init__.py
│   ├── keyboard_controller.py  # Keyboard shortcuts
│   └── mouse_controller.py     # Mouse navigation
│
├── loaders/                 # File I/O
│   ├── __init__.py
│   └── step_loader.py       # STEP file loading
│
├── managers/                # Business logic
│   ├── __init__.py
│   ├── color_manager.py     # Color preset management
│   ├── selection_manager.py # Face selection state
│   ├── explode_manager.py   # Part explosion for viewing
│   ├── planar_alignment_manager.py  # Planar view management
│   ├── plate_manager.py     # Multi-plate management and visualization
│   └── deduplication_manager.py     # Duplicate part detection
│
├── rendering/               # Graphics rendering
│   ├── __init__.py
│   └── material_renderer.py # Material application
│
└── ui/                      # User interface
    ├── __init__.py
    └── viewer_ui.py         # UI components

main.py                      # Entry point script
step_viewer.py              # Legacy single-file version (kept for reference)
```

## Architecture

The application follows **SOLID design principles**:

### Single Responsibility Principle
Each class has one clear purpose:
- `ViewerConfig` - Configuration settings
- `MaterialRenderer` - Material application
- `ColorManager` - Color preset management
- `SelectionManager` - Selection state handling
- `MouseController` - Mouse event processing
- `KeyboardController` - Keyboard event processing
- `StepLoader` - STEP file I/O
- `ViewerUI` - UI component construction
- `StepViewer` - Application coordination

### Open/Closed Principle
- Easy to extend with new features
- Core logic remains unchanged when adding functionality

### Dependency Inversion Principle
- High-level modules depend on abstractions
- Controllers and managers are injected as dependencies

## Controls

### Navigation Mode (Default)
- **Left Mouse**: Rotate view
- **Right Mouse**: Pan view
- **Mouse Wheel**: Zoom in/out
- **F**: Fit all objects in view
- **S**: Toggle selection mode
- **Q or ESC**: Quit application

### Selection Mode
- **Left Click**: Select/deselect faces
- **Right Mouse**: Pan view
- **Mouse Wheel**: Zoom in/out
- **1**: Cycle selection fill color
- **2**: Cycle outline color
- **C**: Clear all selections
- **S**: Return to navigation mode

### Planar View & Plate Management
- **P**: Toggle planar alignment (lay parts flat)
- **D**: Toggle duplicate part visibility
- **L**: Auto-select largest external face per part
- **Explode Slider**: Separate parts in 3D view
- **Material Thickness Slider**: Adjust raycast threshold for external face detection
- **Plate Controls** (in sidebar):
  - **Add Plate**: Create a new material sheet
  - **Delete Plate**: Remove selected plate (parts remain in model)
  - **Rename Plate**: Assign descriptive names to plates
  - **Arrange Parts**: Placeholder for future auto-arrangement logic
  - **Draw Exclusion**: Toggle drawing mode, then click & drag on plate to create red exclusion zones
  - **Clear All**: Remove all exclusion zones from the selected plate

When planar alignment is enabled:
- Parts are automatically laid flat based on selected faces
- Parts are arranged in a grid layout
- Multiple plates are shown with automatic grid spacing
- Parts are auto-assigned to plates based on their 2D position

### Exclusion Zones
- Select a plate from the list
- Click "Draw Exclusion" to enter drawing mode (button turns orange)
- Click and drag on the plate to create red rectangular zones
- These zones mark areas where parts should not be placed (e.g., defects, clamp locations)
- Use "Clear All" to remove all exclusion zones from a plate
- Each plate has its own independent set of exclusion zones

## Configuration

Edit `step_viewer/config.py` to customize:

```python
class ViewerConfig:
    # Window settings
    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 768

    # Selection colors
    SELECTION_COLOR = (1.0, 0.5, 0.0)  # Orange
    SELECTION_OUTLINE_COLOR = (0.07, 0.07, 0.09)  # Dark gray
    SELECTION_OUTLINE_WIDTH = 2.0

    # Anti-aliasing
    MSAA_SAMPLES = 4  # 2, 4, 8, or 16

    # Color presets for cycling
    SELECTION_COLOR_PRESETS = [...]
    OUTLINE_COLOR_PRESETS = [...]
```

## Development

### Adding New Features

1. **New Color Preset**: Add to `SELECTION_COLOR_PRESETS` in `config.py`
2. **New Keyboard Shortcut**: Add method to `KeyboardController` and bind in `viewer.py`
3. **New File Format**: Create new loader in `loaders/` following `StepLoader` pattern
4. **Custom Material**: Extend `MaterialRenderer` with new material methods

### Testing

```bash
# Run the viewer with a sample file
python main.py test.step
```

## License

This project is provided as-is for educational and commercial use.

## Credits

Built with:
- [pythonocc-core](https://github.com/tpaviot/pythonocc-core) - Python bindings for OpenCASCADE
- OpenCASCADE Technology - 3D CAD kernel
