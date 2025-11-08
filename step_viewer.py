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
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial
    import random
except ImportError:
    print("Error: pythonocc-core is not installed.")
    print("Install it using: conda install -c conda-forge pythonocc-core")
    sys.exit(1)


def get_colorblind_friendly_palette():
    """
    Generate a colorblind-friendly color palette with vibrant, pleasant colors.
    Uses colors that are distinguishable for most types of color blindness.
    Returns list of (R, G, B) tuples with values in range 0-1.
    """
    # Colorblind-friendly palette (Tol's bright scheme)
    # More vibrant colors that work well for deuteranopia, protanopia, and tritanopia
    palette = [
        (0.90, 0.40, 0.60),  # Rose/Pink
        (0.40, 0.50, 0.90),  # Bright blue
        (1.00, 0.60, 0.20),  # Orange
        (0.45, 0.85, 0.45),  # Green
        (0.95, 0.90, 0.25),  # Yellow
        (0.65, 0.35, 0.85),  # Purple
        (0.30, 0.75, 0.90),  # Cyan
        (0.95, 0.35, 0.35),  # Red
        (0.50, 0.70, 0.50),  # Gray-green
        (0.80, 0.60, 0.90),  # Lavender
        (0.60, 0.90, 0.70),  # Mint
        (0.90, 0.75, 0.45),  # Tan/Beige
    ]
    return palette


def assign_random_colors_to_solids(shape, display):
    """
    Assign random colorblind-friendly colors to each solid in the shape.

    Args:
        shape: The TopoDS_Shape containing solids
        display: The display object
    """
    palette = get_colorblind_friendly_palette()

    # Explore and collect all solids
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []

    while explorer.More():
        solid = explorer.Current()
        solids.append(solid)
        explorer.Next()

    if len(solids) == 0:
        # No solids found, display the whole shape with a default color
        print("No individual solids found, displaying shape as single object")
        color = Quantity_Color(palette[0][0], palette[0][1], palette[0][2], Quantity_TOC_RGB)
        ais_shape = display.DisplayShape(shape, color=color, update=False)[0]

        # Set material to reduce lighting effects - use a matte plastic material
        material = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial.Graphic3d_NOM_PLASTIC)
        material.SetAmbientColor(color)
        material.SetDiffuseColor(color)
        # Set specular to a very low intensity to reduce shininess
        dark_color = Quantity_Color(0.05, 0.05, 0.05, Quantity_TOC_RGB)
        material.SetSpecularColor(dark_color)
        ais_shape.SetMaterial(material)

        # Force the display to update
        display.Context.UpdateCurrentViewer()
        display.FitAll()
        display.Repaint()
        return

    # Shuffle the palette to get random color assignment
    random.shuffle(palette)

    # Assign a color to each solid
    for i, solid in enumerate(solids):
        # Cycle through palette if we have more solids than colors
        color_index = i % len(palette)
        r, g, b = palette[color_index]

        color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
        ais_shape = display.DisplayShape(solid, color=color, update=False)[0]

        # Set material properties to reduce lighting effects and keep colors consistent
        material = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial.Graphic3d_NOM_PLASTIC)
        material.SetAmbientColor(color)
        material.SetDiffuseColor(color)
        # Set specular to a very low intensity to reduce shininess and highlights
        dark_color = Quantity_Color(0.05, 0.05, 0.05, Quantity_TOC_RGB)
        material.SetSpecularColor(dark_color)
        ais_shape.SetMaterial(material)

    print(f"Assigned colors to {len(solids)} solid(s)")

    # Force the display to update and show all shapes immediately
    display.Context.UpdateCurrentViewer()
    display.FitAll()
    display.Repaint()


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

    # Don't set background here - will set it after display is fully initialized

    # Remove any canvas border/padding and window borders
    try:
        canvas = display._parent
        root = canvas.winfo_toplevel()

        # The canvas is a Frame containing the actual OpenGL widget
        # Set background of everything to match
        canvas.configure(borderwidth=0, highlightthickness=0, relief='flat', bg='#111216')
        root.configure(borderwidth=0, highlightthickness=0, bg='#111216')

        # Configure all children when they exist
        for child in canvas.winfo_children():
            try:
                child.configure(borderwidth=0, highlightthickness=0)
                if child.winfo_class() != 'Togl':
                    child.configure(bg='#111216')
            except:
                pass

        # Try to find and hide all root widgets except the canvas
        for widget in root.winfo_children():
            if widget != canvas:
                try:
                    widget.pack_forget()
                    widget.grid_forget()
                    widget.place_forget()
                except:
                    pass

        # Ensure Frame fills completely with no gaps
        canvas.pack_forget()
        canvas.grid_forget()
        canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    except:
        pass

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
    except Exception as e:
        print(f"Warning: Could not customize controls: {e}")
        print("Some features may not work as expected")

    # Display the shape with randomized colorblind-friendly colors for each solid
    # This uses the actual BREP geometry, not triangulated meshes
    assign_random_colors_to_solids(shape, display)

    # Set background color after display is fully initialized
    # Use sRGB color space explicitly
    from OCC.Core.Quantity import Quantity_TOC_sRGB
    from OCC.Core.Aspect import Aspect_GFM_VER
    bg_color = Quantity_Color(17/255.0, 18/255.0, 22/255.0, Quantity_TOC_sRGB)

    # Try using vertical gradient with same color (should be solid)
    # This might render differently than NONE and avoid the lines
    display.View.SetBgGradientStyle(Aspect_GFM_VER)

    # Set both gradient colors to the same value for solid background
    display.View.SetBgGradientColors(bg_color, bg_color)

    # Also set background color
    display.View.SetBackgroundColor(bg_color)

    # Force immediate redraw to apply background
    display.View.Redraw()

    print("\nViewer Controls:")
    print("  - Left mouse button: Rotate")
    print("  - Right mouse button: Pan")
    print("  - Mouse wheel: Zoom")
    print("  - 'f': Fit all")
    print("  - 'q' or ESC: Quit")

    # Final update to ensure everything is rendered before starting the loop
    display.View.Redraw()

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
