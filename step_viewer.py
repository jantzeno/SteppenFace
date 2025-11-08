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
    display, start_display, add_menu, add_function_to_menu = init_display()

    # Configure mouse button mappings for Tkinter backend:
    # Left button = Rotate, Right button = Pan, Wheel = Zoom
    try:
        # Get the Tkinter canvas widget
        canvas = display._parent
        view = display.View

        # Track mouse state
        mouse_state = {'start_x': 0, 'start_y': 0, 'button': None}

        def on_left_press(event):
            """Left mouse button pressed - start rotation"""
            mouse_state['start_x'] = event.x
            mouse_state['start_y'] = event.y
            mouse_state['button'] = 1
            view.StartRotation(event.x, event.y)

        def on_left_motion(event):
            """Left mouse button dragged - rotate"""
            if mouse_state['button'] == 1:
                view.Rotation(event.x, event.y)

        def on_right_press(event):
            """Right mouse button pressed - start pan"""
            mouse_state['start_x'] = event.x
            mouse_state['start_y'] = event.y
            mouse_state['button'] = 3

        def on_right_motion(event):
            """Right mouse button dragged - pan"""
            if mouse_state['button'] == 3:
                dx = event.x - mouse_state['start_x']
                dy = mouse_state['start_y'] - event.y
                view.Pan(dx, dy)
                mouse_state['start_x'] = event.x
                mouse_state['start_y'] = event.y

        def on_release(event):
            """Mouse button released"""
            mouse_state['button'] = None

        def on_wheel(event):
            """Mouse wheel - zoom"""
            # event.delta is positive for scroll up, negative for scroll down
            if event.delta > 0 or event.num == 4:  # Scroll up or Button 4
                display.ZoomFactor(1.1)
            elif event.delta < 0 or event.num == 5:  # Scroll down or Button 5
                display.ZoomFactor(0.9)

        # Unbind existing mouse handlers (but preserve keyboard handlers)
        for event in ["<Button-1>", "<B1-Motion>", "<ButtonRelease-1>",
                      "<Button-2>", "<B2-Motion>", "<ButtonRelease-2>",
                      "<Button-3>", "<B3-Motion>", "<ButtonRelease-3>",
                      "<MouseWheel>", "<Button-4>", "<Button-5>"]:
            canvas.unbind(event)

        # Bind new mouse handlers
        # Left button (Button-1) for rotation
        canvas.bind("<Button-1>", on_left_press)
        canvas.bind("<B1-Motion>", on_left_motion)
        canvas.bind("<ButtonRelease-1>", on_release)

        # Right button (Button-3) for panning
        canvas.bind("<Button-3>", on_right_press)
        canvas.bind("<B3-Motion>", on_right_motion)
        canvas.bind("<ButtonRelease-3>", on_release)

        # Mouse wheel for zooming
        canvas.bind("<MouseWheel>", on_wheel)  # Windows/MacOS
        canvas.bind("<Button-4>", on_wheel)    # Linux scroll up
        canvas.bind("<Button-5>", on_wheel)    # Linux scroll down

        # Add keyboard bindings
        def on_key_f(event):
            """'f' key - fit all"""
            display.FitAll()

        def on_key_q(event):
            """'q' key - quit"""
            import sys
            sys.exit(0)

        # Bind keyboard commands
        canvas.bind("<f>", on_key_f)
        canvas.bind("<F>", on_key_f)
        canvas.bind("<q>", on_key_q)
        canvas.bind("<Q>", on_key_q)
        canvas.bind("<Escape>", on_key_q)

        # Give focus to canvas so it receives keyboard events
        canvas.focus_set()

        print("Controls configured successfully")
    except Exception as e:
        print(f"Warning: Could not customize controls: {e}")
        print("Some features may not work as expected")

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
