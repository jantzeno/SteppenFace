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
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial
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


def apply_matte_material(ais_shape, color):
    """
    Apply a matte plastic material to reduce lighting effects and maintain consistent colors.

    Args:
        ais_shape: The AIS shape object to apply material to
        color: Quantity_Color object for the shape
    """
    material = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial.Graphic3d_NOM_PLASTIC)
    material.SetAmbientColor(color)
    material.SetDiffuseColor(color)
    # Set specular to very low intensity to reduce shininess
    dark_color = Quantity_Color(0.05, 0.05, 0.05, Quantity_TOC_RGB)
    material.SetSpecularColor(dark_color)
    ais_shape.SetMaterial(material)


def assign_random_colors_to_solids(shape, display, update_display=True):
    """
    Assign random colorblind-friendly colors to each solid in the shape.

    Args:
        shape: The TopoDS_Shape containing solids
        display: The display object
        update_display: If True, update the display immediately (default True)

    Returns:
        List of tuples: [(solid, color, ais_shape), ...]
    """
    import random

    palette = get_colorblind_friendly_palette()
    parts_list = []

    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []

    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()

    if len(solids) == 0:
        print("No individual solids found, displaying shape as single object")
        color = Quantity_Color(palette[0][0], palette[0][1], palette[0][2], Quantity_TOC_RGB)
        ais_shape = display.DisplayShape(shape, color=color, update=False)[0]
        apply_matte_material(ais_shape, color)
        parts_list.append((shape, palette[0], ais_shape))

        if update_display:
            display.Context.UpdateCurrentViewer()
            display.FitAll()
            display.Repaint()

        return parts_list

    random.shuffle(palette)

    for i, solid in enumerate(solids):
        r, g, b = palette[i % len(palette)]

        color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
        ais_shape = display.DisplayShape(solid, color=color, update=False)[0]
        apply_matte_material(ais_shape, color)
        parts_list.append((solid, (r, g, b), ais_shape))

    print(f"Assigned colors to {len(solids)} solid(s)")

    if update_display:
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

    step_reader = STEPControl_Reader()
    status = step_reader.ReadFile(filename)

    if status != IFSelect_RetDone:
        print(f"Error: Failed to read STEP file '{filename}'")
        return None

    step_reader.TransferRoots()
    shape = step_reader.OneShape()

    print(f"Successfully loaded: {filename}")

    # Count and report entities
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
    shape = load_step_file(filename)
    if shape is None:
        return

    # Create the Tkinter window layout before initializing display
    root = tk.Tk()
    root.title("STEP File Viewer")
    root.geometry("1024x768")
    root.configure(borderwidth=0, highlightthickness=0, bg='#111216')

    paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg='#111216',
                                  sashwidth=5, sashrelief=tk.RAISED,
                                  borderwidth=0)
    paned_window.pack(fill=tk.BOTH, expand=True)

    # Left panel for parts list
    left_panel = tk.Frame(paned_window, bg='#1a1b1f', width=250,
                         borderwidth=0, highlightthickness=0)

    header = tk.Label(left_panel, text="Parts", bg='#1a1b1f', fg='#ffffff',
                     font=('Arial', 10, 'bold'), anchor='w', padx=10, pady=5)
    header.pack(fill=tk.X)

    separator = tk.Frame(left_panel, bg='#2a2b2f', height=1)
    separator.pack(fill=tk.X)

    tree_frame = tk.Frame(left_panel, bg='#1a1b1f')
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Configure dark theme style
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

    parts_tree = ttk.Treeview(tree_frame, style="Dark.Treeview", show='tree')
    parts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=parts_tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    parts_tree.configure(yscrollcommand=scrollbar.set)

    # Right panel for 3D viewer
    right_panel = tk.Frame(paned_window, bg='#111216',
                          borderwidth=0, highlightthickness=0)
    right_panel.pack_propagate(True)

    paned_window.add(left_panel, minsize=200, width=250, stretch="never")
    paned_window.add(right_panel, minsize=400, stretch="always")

    root.update_idletasks()

    # Initialize the display in the right panel
    from OCC.Display.tkDisplay import tkViewer3d

    canvas = tkViewer3d(right_panel)
    canvas.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
    canvas.configure(borderwidth=0, highlightthickness=0, relief='flat',
                    bg='#111216', width=0, height=0)

    root.update_idletasks()

    display = canvas._display
    display._parts_tree = parts_tree

    print("Navigation panel created successfully")

    # Configure mouse and keyboard controls
    try:
        view = display.View
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
            if event.delta > 0 or event.num == 4:
                display.ZoomFactor(1.1)
            elif event.delta < 0 or event.num == 5:
                display.ZoomFactor(0.9)

        # Mouse controls
        canvas.bind("<Button-1>", on_left_press)
        canvas.bind("<B1-Motion>", on_left_motion)
        canvas.bind("<ButtonRelease-1>", on_release)
        canvas.bind("<Button-3>", on_right_press)
        canvas.bind("<B3-Motion>", on_right_motion)
        canvas.bind("<ButtonRelease-3>", on_release)
        canvas.bind("<MouseWheel>", on_wheel)
        canvas.bind("<Button-4>", on_wheel)
        canvas.bind("<Button-5>", on_wheel)

        # Keyboard controls
        def on_key_f(event):
            """'f' key - fit all"""
            display.FitAll()

        def on_key_q(event):
            """'q' key - quit"""
            root.quit()

        canvas.bind("<f>", on_key_f)
        canvas.bind("<F>", on_key_f)
        canvas.bind("<q>", on_key_q)
        canvas.bind("<Q>", on_key_q)
        canvas.bind("<Escape>", on_key_q)

        canvas.focus_set()

        # Resize handler with debouncing
        resize_state = {'pending': False, 'initialized': False}

        def on_resize(event):
            """Handle resize events with debouncing"""
            if not resize_state['initialized']:
                return

            if not resize_state['pending']:
                resize_state['pending'] = True

                def do_resize():
                    try:
                        display.View.MustBeResized()
                        display.View.Redraw()
                    except Exception as e:
                        print(f"Warning: Could not resize view: {e}")
                    finally:
                        resize_state['pending'] = False

                root.after(10, do_resize)

        canvas.bind('<Configure>', on_resize)
        display._resize_state = resize_state

    except Exception as e:
        print(f"Warning: Could not customize controls: {e}")
        print("Some features may not work as expected")

    # Assign colors to solids (uses BREP geometry, not triangulated meshes)
    parts_list = assign_random_colors_to_solids(shape, display, update_display=False)

    # Set background color
    from OCC.Core.Quantity import Quantity_TOC_sRGB
    from OCC.Core.Aspect import Aspect_GFM_VER
    bg_color = Quantity_Color(17/255.0, 18/255.0, 22/255.0, Quantity_TOC_sRGB)

    display.View.SetBgGradientStyle(Aspect_GFM_VER)
    display.View.SetBgGradientColors(bg_color, bg_color)
    display.View.SetBackgroundColor(bg_color)

    # Populate the navigation tree
    try:
        if hasattr(display, '_parts_tree'):
            tree = display._parts_tree

            root_node = tree.insert('', 'end', text=f'Model ({len(parts_list)} part{"s" if len(parts_list) != 1 else ""})',
                                   open=True)

            for i, (solid, color, ais_shape) in enumerate(parts_list):
                r, g, b = color
                hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
                part_name = f'■ Part {i+1}'
                tree.insert(root_node, 'end', text=part_name, tags=(f'part_{i}',))
                tree.tag_configure(f'part_{i}', foreground=hex_color)
    except Exception as e:
        print(f"Warning: Could not populate parts tree: {e}")

    print("\nViewer Controls:")
    print("  - Left mouse button: Rotate")
    print("  - Right mouse button: Pan")
    print("  - Mouse wheel: Zoom")
    print("  - 'f': Fit all")
    print("  - 'q' or ESC: Quit")

    def final_update():
        """Final update after UI is fully initialized"""
        try:
            display.View.MustBeResized()
            display.Context.UpdateCurrentViewer()
            display.FitAll()
            display.Repaint()

            if hasattr(display, '_resize_state'):
                display._resize_state['initialized'] = True
        except Exception as e:
            print(f"Warning: Could not perform final update: {e}")

    root.after(150, final_update)
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
