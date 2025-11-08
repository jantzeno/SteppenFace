#!/usr/bin/env python3
"""
STEP File Viewer with Solid CAD Representation
Displays STEP files using OpenCASCADE's native BREP representation
"""

import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk

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

    Returns:
        List of tuples: [(solid, color, ais_shape), ...]
    """
    palette = get_colorblind_friendly_palette()
    parts_list = []

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

        parts_list.append((shape, palette[0], ais_shape))
        return parts_list

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

        # Store part info
        parts_list.append((solid, (r, g, b), ais_shape))

    print(f"Assigned colors to {len(solids)} solid(s)")

    # Force the display to update and show all shapes immediately
    display.Context.UpdateCurrentViewer()
    display.FitAll()
    display.Repaint()

    return parts_list


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

    # Create the Tkinter window and layout FIRST, before initializing display
    root = tk.Tk()
    root.title("STEP File Viewer")
    root.geometry("1024x768")
    root.configure(borderwidth=0, highlightthickness=0, bg='#111216')

    # Create a PanedWindow in the root
    paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg='#111216',
                                  sashwidth=5, sashrelief=tk.RAISED,
                                  borderwidth=0)
    paned_window.pack(fill=tk.BOTH, expand=True)

    # Create left panel for navigation tree
    left_panel = tk.Frame(paned_window, bg='#1a1b1f', width=250,
                         borderwidth=0, highlightthickness=0)

    # Create header label
    header = tk.Label(left_panel, text="Parts", bg='#1a1b1f', fg='#ffffff',
                     font=('Arial', 10, 'bold'), anchor='w', padx=10, pady=5)
    header.pack(fill=tk.X)

    # Create separator
    separator = tk.Frame(left_panel, bg='#2a2b2f', height=1)
    separator.pack(fill=tk.X)

    # Create Treeview for parts list
    tree_frame = tk.Frame(left_panel, bg='#1a1b1f')
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Configure style for dark theme
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Dark.Treeview",
                   background='#1a1b1f',
                   foreground='#ffffff',
                   fieldbackground='#1a1b1f',
                   borderwidth=0,
                   relief='flat')
    style.configure("Dark.Treeview.Heading",
                   background='#2a2b2f',
                   foreground='#ffffff',
                   borderwidth=0,
                   relief='flat')
    style.map("Dark.Treeview",
             background=[('selected', '#3a3b3f')],
             foreground=[('selected', '#ffffff')])

    # Create the tree
    parts_tree = ttk.Treeview(tree_frame, style="Dark.Treeview", show='tree')
    parts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=parts_tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    parts_tree.configure(yscrollcommand=scrollbar.set)

    # Create right panel for 3D viewer
    right_panel = tk.Frame(paned_window, bg='#111216',
                          borderwidth=0, highlightthickness=0)

    # Add panels to PanedWindow
    paned_window.add(left_panel, minsize=200, width=250)
    paned_window.add(right_panel, minsize=400)

    # Force layout update
    root.update_idletasks()

    # NOW initialize the display in the right panel
    from OCC.Display.tkDisplay import tkViewer3d

    # Create the 3D viewer in the right panel
    # tkViewer3d returns the canvas widget itself
    canvas = tkViewer3d(right_panel)

    # Configure and pack the canvas
    canvas.configure(borderwidth=0, highlightthickness=0, relief='flat', bg='#111216')
    canvas.pack(fill=tk.BOTH, expand=True)

    # Wait for the canvas to be visible before accessing the display
    canvas.wait_visibility()

    # Get the display object from the canvas
    display = canvas._display

    # Store tree reference for later population
    display._parts_tree = parts_tree

    print("Navigation panel created successfully")

    # Configure mouse button mappings for Tkinter backend:
    # Left button = Rotate, Right button = Pan, Wheel = Zoom
    try:
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

        # Bind mouse handlers
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
            root.quit()

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
    parts_list = assign_random_colors_to_solids(shape, display)

    # Populate the navigation tree with parts
    try:
        if hasattr(display, '_parts_tree'):
            tree = display._parts_tree

            # Add root node
            root_node = tree.insert('', 'end', text=f'Model ({len(parts_list)} part{"s" if len(parts_list) != 1 else ""})',
                                   open=True)

            # Add each part
            for i, (solid, color, ais_shape) in enumerate(parts_list):
                # Convert color to hex for display
                r, g, b = color
                hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

                # Create color indicator (using Unicode square)
                color_indicator = '■'

                # Add part to tree
                part_name = f'{color_indicator} Part {i+1}'
                tree.insert(root_node, 'end', text=part_name, tags=(f'part_{i}',))

                # Configure tag color
                tree.tag_configure(f'part_{i}', foreground=hex_color)
    except Exception as e:
        print(f"Warning: Could not populate parts tree: {e}")

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

    # Start the Tkinter event loop
    root.mainloop()


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
