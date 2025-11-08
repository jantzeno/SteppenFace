#!/usr/bin/env python3
"""
STEP File Viewer with Solid CAD Representation
Displays STEP files using OpenCASCADE's native BREP representation
"""

import sys
from pathlib import Path

try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Display.SimpleGui import init_display
    from OCC.Core.AIS import AIS_Shape, AIS_Shaded
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE
except ImportError:
    print("Error: pythonocc-core is not installed.")
    print("Install it using: conda install -c conda-forge pythonocc-core")
    print("or: pip install pythonocc-core")
    sys.exit(1)


def load_step_file(filename):
    """
    Load a STEP file and return the shape.

    Args:
        filename: Path to the STEP file

    Returns:
        The loaded shape or None if loading failed
    """
    if not Path(filename).exists():
        print(f"Error: File '{filename}' not found.")
        return None

    # Create STEP reader
    step_reader = STEPControl_Reader()

    # Read the STEP file
    status = step_reader.ReadFile(filename)

    if status != IFSelect_RetDone:
        print(f"Error: Failed to read STEP file '{filename}'")
        return None

    # Transfer the contents to the internal data structure
    step_reader.TransferRoots()

    # Get the shape
    shape = step_reader.OneShape()

    print(f"Successfully loaded: {filename}")

    # Count entities
    explorer_solid = TopExp_Explorer(shape, TopAbs_SOLID)
    solid_count = 0
    while explorer_solid.More():
        solid_count += 1
        explorer_solid.Next()

    explorer_face = TopExp_Explorer(shape, TopAbs_FACE)
    face_count = 0
    while explorer_face.More():
        face_count += 1
        explorer_face.Next()

    print(f"  Solids: {solid_count}")
    print(f"  Faces: {face_count}")

    return shape


def display_step_file(filename):
    """
    Load and display a STEP file with solid CAD representation.

    Args:
        filename: Path to the STEP file
    """
    # Load the STEP file
    shape = load_step_file(filename)

    if shape is None:
        return

    # Initialize the display
    # Note: Mouse controls are configured at the backend level
    # Default pythonocc-core controls (Qt backend):
    #   - Left button: Rotate (orbit)
    #   - Right button: Pan (in Qt backend)
    #   - Mouse wheel: Zoom
    # These are the standard CAD navigation controls
    display, start_display, add_menu, add_function_to_menu = init_display()

    # Display the shape in shaded mode (solid representation)
    # This uses the actual BREP geometry, not triangulated meshes
    ais_shape = AIS_Shape(shape)

    # Set display mode to shaded (solid visualization)
    display.Context.SetDisplayMode(ais_shape, AIS_Shaded, True)

    # Display the shape
    display.DisplayShape(shape, update=True)

    # Fit the view to show the entire model
    display.FitAll()

    print("\nViewer Controls:")
    print("  - Left mouse button: Rotate")
    print("  - Right mouse button: Pan")
    print("  - Mouse wheel: Zoom")
    print("  - 'f': Fit all")
    print("  - 'q' or ESC: Quit")

    # Start the display loop
    start_display()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python step_viewer.py <step_file>")
        print("\nExample:")
        print("  python step_viewer.py model.step")
        print("  python step_viewer.py model.stp")
        sys.exit(1)

    step_file = sys.argv[1]
    display_step_file(step_file)


if __name__ == "__main__":
    main()
