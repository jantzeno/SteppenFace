# STEP File Viewer

Experimental STEP viewer with interactive face selection, planar alignment, and plate/exclusion-zone tools — primarily for CNC preparation and visualization.

Quick start
1. Install dependencies (recommended):
- Conda: `conda install -c conda-forge pythonocc-core`
- Or: `pip install -r requirements.txt` (requires a compatible build of pythonocc-core)
2. Run the viewer:
```
python main.py path/to/model.step
```
Tip: try `sample_files/Assembly 3.step` included in the repo.

Important controls (read `main.py` for full list):
- Left mouse: rotate, Right mouse: pan, Mouse wheel: zoom
- f: fit, s: toggle selection mode, c: clear selections
- p: toggle planar alignment, d: toggle duplicate visibility

Project layout (minimal):
- `main.py` — entry point
- `step_viewer/` — package: managers, controllers, loaders, ui, rendering
- `sample_files/` — example STEP files

License: AGPL-3.0-or-later (see `LICENSE`).

Credits: built on pythonocc-core / OpenCASCADE
