# STEP File Viewer

A Python program to import and display STEP files with solid CAD representation using OpenCASCADE.

## Features

- Imports STEP (.step, .stp) files
- Displays models using BREP (Boundary Representation) geometry
- NO mesh triangulation - maintains true CAD solid information
- Interactive 3D viewer with rotation, pan, and zoom
- **Side navigation panel** with hierarchical parts tree
- Randomized colorblind-friendly colors for each part (vibrant, pleasant palette)
- Color-coded parts list showing each part with its assigned color
- Colors are distinguishable for deuteranopia, protanopia, and tritanopia
- Shows solid and face counts

## Installation

### Option 1: Using Conda (Recommended)

```bash
conda install -c conda-forge pythonocc-core
```

### Option 2: Using Pip

```bash
pip install pythonocc-core
```

**Note**: Installing pythonocc-core via conda is generally more reliable as it handles all the OpenCASCADE dependencies.

## Usage

```bash
python step_viewer.py <path_to_step_file>
```

### Example

```bash
python step_viewer.py model.step
```

## Viewer Controls

- **Left mouse button**: Rotate the model
- **Right mouse button**: Pan the view
- **Mouse wheel**: Zoom in/out
- **'f' key**: Fit all (reset view to show entire model)
- **'q' or ESC**: Quit the viewer

## Technical Details

This viewer uses:
- **pythonocc-core**: Python wrapper for OpenCASCADE
- **OpenCASCADE**: Professional CAD kernel with BREP solid modeling
- **Solid shaded rendering**: Displays actual surface geometry, not triangulated meshes
- **Dark background**: rgb(17, 18, 22) for comfortable viewing

The viewer maintains the original CAD topology and geometry, making it suitable for precision engineering applications.
