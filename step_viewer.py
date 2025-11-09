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


# ============================================================================
# SELECTION COLOR CONFIGURATION
# Customize these colors to change how selected faces appear
# ============================================================================
# Selection fill color (RGB values 0.0 to 1.0)
SELECTION_COLOR = (1.0, 0.5, 0.0)

# Selection outline/border color (RGB values 0.0 to 1.0)
SELECTION_OUTLINE_COLOR = (0.07, 0.07, 0.09)

# Selection outline width in pixels
SELECTION_OUTLINE_WIDTH = 2.0

# Selection transparency (0.0 = opaque, 1.0 = fully transparent)
SELECTION_TRANSPARENCY = 0.1

# Color presets for quick switching (cycle with '1' key)
SELECTION_COLOR_PRESETS = [
    ((1.0, 0.5, 0.0), "Orange"),
    ((1.0, 0.0, 0.0), "Red"),
    ((0.0, 1.0, 0.0), "Green"),
    ((0.0, 0.0, 1.0), "Blue"),
    ((1.0, 0.0, 1.0), "Magenta"),
    ((0.0, 1.0, 1.0), "Cyan"),
    ((1.0, 1.0, 0.0), "Yellow"),
]

# Outline color presets (cycle with '2' key)
OUTLINE_COLOR_PRESETS = [
    ((0.07, 0.07, 0.09), "Dark Gray"),
    ((0.0, 0.0, 0.0), "Black"),
    ((1.0, 1.0, 1.0), "White"),
    ((1.0, 1.0, 0.0), "Yellow"),
    ((0.0, 1.0, 1.0), "Cyan"),
]
# ============================================================================


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


def apply_matte_material(ais_shape, color, edge_color=None):
    """
    Apply a matte plastic material to reduce lighting effects and maintain consistent colors.

    Args:
        ais_shape: The AIS shape object to apply material to
        color: Quantity_Color object for the shape
        edge_color: Optional Quantity_Color for edges (defaults to dark gray if None)
    """
    material = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial.Graphic3d_NOM_PLASTIC)
    material.SetAmbientColor(color)
    material.SetDiffuseColor(color)
    # Set specular to very low intensity to reduce shininess
    dark_color = Quantity_Color(0.05, 0.05, 0.05, Quantity_TOC_RGB)
    material.SetSpecularColor(dark_color)
    ais_shape.SetMaterial(material)

    # Set edge color
    if edge_color is None:
        edge_color = Quantity_Color(0.15, 0.15, 0.15, Quantity_TOC_RGB)  # Dark gray

    drawer = ais_shape.Attributes()
    drawer.SetFaceBoundaryDraw(True)
    drawer.FaceBoundaryAspect().SetColor(edge_color)
    drawer.FaceBoundaryAspect().SetWidth(1.0)


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

    # Status panel at bottom of left panel
    status_separator = tk.Frame(left_panel, bg='#2a2b2f', height=1)
    status_separator.pack(fill=tk.X)

    status_frame = tk.Frame(left_panel, bg='#1a1b1f')
    status_frame.pack(fill=tk.X, padx=10, pady=10)

    mode_label = tk.Label(status_frame, text="Mode: Navigation", bg='#1a1b1f', fg='#00e0ff',
                         font=('Arial', 9, 'bold'), anchor='w')
    mode_label.pack(fill=tk.X)

    selection_label = tk.Label(status_frame, text="Selected: 0 faces", bg='#1a1b1f', fg='#00ff00',
                              font=('Arial', 9, 'bold'), anchor='w')
    selection_label.pack(fill=tk.X, pady=(5, 0))

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
    display._mode_label = mode_label
    display._selection_label = selection_label

    print("Navigation panel created successfully")

    # Configure mouse and keyboard controls
    try:
        view = display.View
        mouse_state = {'start_x': 0, 'start_y': 0, 'button': None}

        # Face selection state
        selection_state = {
            'mode': False,  # False = navigation, True = selection
            'highlighted_faces': {},  # Map face hash to AIS_Shape for highlighting
            'color_index': 0,  # Current selection color preset index
            'outline_index': 0,  # Current outline color preset index
        }

        def on_left_press(event):
            """Left mouse button pressed - start rotation or select face"""
            mouse_state['start_x'] = event.x
            mouse_state['start_y'] = event.y
            mouse_state['button'] = 1

            if not selection_state['mode']:
                # Navigation mode - start rotation
                view.StartRotation(event.x, event.y)
            # In selection mode, do nothing on press - wait for release

        def on_left_motion(event):
            """Left mouse button dragged - rotate"""
            if mouse_state['button'] == 1 and not selection_state['mode']:
                view.Rotation(event.x, event.y)
                display.Context.UpdateCurrentViewer()
                root.update_idletasks()

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
                display.Context.UpdateCurrentViewer()
                root.update_idletasks()
                mouse_state['start_x'] = event.x
                mouse_state['start_y'] = event.y

        def on_release(event):
            """Mouse button released - handle face selection if in select mode"""
            # Check if this was a click (not a drag) in selection mode
            if mouse_state['button'] == 1 and selection_state['mode']:
                dx = abs(event.x - mouse_state['start_x'])
                dy = abs(event.y - mouse_state['start_y'])
                if dx < 5 and dy < 5:
                    # This was a click, not a drag - select face
                    select_face_at_position(event.x, event.y)

            mouse_state['button'] = None

        def on_wheel(event):
            """Mouse wheel - zoom"""
            if event.delta > 0 or event.num == 4:
                display.ZoomFactor(1.1)
            elif event.delta < 0 or event.num == 5:
                display.ZoomFactor(0.9)

        def update_selection_count():
            """Update the selection count display"""
            count = len(selection_state['highlighted_faces'])

            if hasattr(display, '_selection_label'):
                text = f"Selected: {count} face{'s' if count != 1 else ''}"
                display._selection_label.config(text=text)

            return count

        def select_face_at_position(x, y):
            """Select a face at the given screen position"""
            try:
                from OCC.Core.AIS import AIS_Shape
                from OCC.Core.Prs3d import Prs3d_Drawer
                from OCC.Core.Aspect import Aspect_TypeOfLine

                # Move context to the position to detect what's under the cursor
                display.Context.MoveTo(x, y, view, True)

                # Check if we detected something
                if not display.Context.HasDetected():
                    print("No face detected at click position")
                    return

                # Get the detected shape (the face)
                detected_shape = display.Context.DetectedShape()

                if detected_shape.IsNull():
                    print("Detected shape is null")
                    return

                # Use the shape hash as a unique identifier
                face_hash = detected_shape.__hash__()

                # Check if this face is already highlighted
                if face_hash in selection_state['highlighted_faces']:
                    # Deselect - remove the highlight
                    ais_highlight = selection_state['highlighted_faces'][face_hash]
                    display.Context.Remove(ais_highlight, True)
                    del selection_state['highlighted_faces'][face_hash]
                    action = "Deselected"
                else:
                    # Select - create a highlight for this face
                    # Create a new AIS_Shape for this face
                    ais_highlight = AIS_Shape(detected_shape)

                    # Set the color
                    ais_highlight.SetColor(display._select_color)
                    ais_highlight.SetTransparency(SELECTION_TRANSPARENCY)

                    # Get the drawer and configure it
                    drawer = ais_highlight.Attributes()
                    drawer.SetFaceBoundaryDraw(True)
                    drawer.FaceBoundaryAspect().SetColor(display._outline_color)
                    drawer.FaceBoundaryAspect().SetWidth(SELECTION_OUTLINE_WIDTH)
                    drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

                    # Display the highlight (on top of original)
                    display.Context.Display(ais_highlight, True)

                    # Store it
                    selection_state['highlighted_faces'][face_hash] = ais_highlight
                    action = "Selected"

                # Update display and count
                display.Context.UpdateCurrentViewer()
                display.Repaint()
                root.update_idletasks()
                root.update()
                count = len(selection_state['highlighted_faces'])

                if hasattr(display, '_selection_label'):
                    display._selection_label.config(text=f"Selected: {count} face{'s' if count != 1 else ''}")

                print(f"{action} face (total: {count})")

            except Exception as e:
                print(f"Error in select_face_at_position: {e}")
                import traceback
                traceback.print_exc()

        def toggle_selection_mode():
            """Toggle between navigation and face selection mode"""
            selection_state['mode'] = not selection_state['mode']

            if selection_state['mode']:
                print("\n*** FACE SELECTION MODE ***")
                print("  - Left click: Select/deselect faces")
                print("  - Right click: Pan")
                print("  - Mouse wheel: Zoom")
                print("  - 's': Exit selection mode")
                print("  - 'c': Clear all selections")
                print("  - '1': Cycle selection fill color")
                print("  - '2': Cycle outline color")

                # Show current colors
                color_rgb, color_name = SELECTION_COLOR_PRESETS[selection_state['color_index']]
                outline_rgb, outline_name = OUTLINE_COLOR_PRESETS[selection_state['outline_index']]
                print(f"\n  CURRENT COLORS:")
                print(f"    Fill: {color_name} RGB{color_rgb}")
                print(f"    Outline: {outline_name} RGB{outline_rgb}")
                print(f"    Outline width: {SELECTION_OUTLINE_WIDTH}px\n")
                root.configure(bg='#2a2520')  # Change background to indicate mode
                if hasattr(display, '_mode_label'):
                    display._mode_label.config(text="Mode: Selection", fg='#00ff00')
            else:
                print("\n*** NAVIGATION MODE ***")
                print("  - Left click: Rotate")
                print("  - Right click: Pan")
                print("  - Mouse wheel: Zoom")
                print("  - 's': Enter selection mode")
                root.configure(bg='#111216')  # Restore normal background
                if hasattr(display, '_mode_label'):
                    display._mode_label.config(text="Mode: Navigation", fg='#00e0ff')

        def clear_all_selections():
            """Clear all selected faces"""
            # Remove all manually created highlights
            for face_hash, ais_highlight in list(selection_state['highlighted_faces'].items()):
                display.Context.Remove(ais_highlight, True)

            selection_state['highlighted_faces'].clear()

            # Also clear any context selections
            display.Context.ClearSelected(True)
            display.Context.UpdateCurrentViewer()
            display.Repaint()
            root.update_idletasks()
            root.update()

            # Update label
            if hasattr(display, '_selection_label'):
                display._selection_label.config(text="Selected: 0 faces")

            print("Cleared all selections")

        def update_all_selection_colors():
            """Update colors of all currently selected faces"""
            from OCC.Core.Aspect import Aspect_TypeOfLine

            # Get current colors
            color_rgb, color_name = SELECTION_COLOR_PRESETS[selection_state['color_index']]
            outline_rgb, outline_name = OUTLINE_COLOR_PRESETS[selection_state['outline_index']]

            select_color = Quantity_Color(color_rgb[0], color_rgb[1], color_rgb[2], Quantity_TOC_RGB)
            outline_color = Quantity_Color(outline_rgb[0], outline_rgb[1], outline_rgb[2], Quantity_TOC_RGB)

            # Update stored colors
            display._select_color = select_color
            display._outline_color = outline_color

            # Update all existing selections
            for face_hash, ais_highlight in selection_state['highlighted_faces'].items():
                ais_highlight.SetColor(select_color)
                ais_highlight.SetTransparency(SELECTION_TRANSPARENCY)

                drawer = ais_highlight.Attributes()
                drawer.SetFaceBoundaryDraw(True)
                drawer.FaceBoundaryAspect().SetColor(outline_color)
                drawer.FaceBoundaryAspect().SetWidth(SELECTION_OUTLINE_WIDTH)
                drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

                display.Context.Redisplay(ais_highlight, True)

            display.Context.UpdateCurrentViewer()
            display.Repaint()
            root.update_idletasks()
            root.update()

            print(f"\nSelection colors updated:")
            print(f"  Fill: {color_name} RGB{color_rgb}")
            print(f"  Outline: {outline_name} RGB{outline_rgb}\n")

        def cycle_selection_color():
            """Cycle to the next selection fill color preset"""
            selection_state['color_index'] = (selection_state['color_index'] + 1) % len(SELECTION_COLOR_PRESETS)
            update_all_selection_colors()

        def cycle_outline_color():
            """Cycle to the next outline color preset"""
            selection_state['outline_index'] = (selection_state['outline_index'] + 1) % len(OUTLINE_COLOR_PRESETS)
            update_all_selection_colors()

        # Mouse controls - bind globally to intercept all mouse events
        opengl_widget = canvas

        # Unbind OCC's default mouse handlers
        widgets_to_unbind = [canvas, root]
        for widget in widgets_to_unbind:
            for event in ["<Button-1>", "<Button-2>", "<Button-3>",
                          "<B1-Motion>", "<B2-Motion>", "<B3-Motion>",
                          "<ButtonRelease-1>", "<ButtonRelease-2>", "<ButtonRelease-3>"]:
                try:
                    widget.unbind(event)
                except:
                    pass

        # Wrapper to ensure event propagation stops
        def make_handler(func):
            """Wrapper to ensure event propagation stops"""
            def handler(event):
                func(event)
                return "break"  # Stop event propagation
            return handler

        # Bind our custom handlers globally to intercept all mouse events
        root.bind_all("<Button-1>", make_handler(on_left_press), add=False)
        root.bind_all("<B1-Motion>", make_handler(on_left_motion), add=False)
        root.bind_all("<ButtonRelease-1>", make_handler(on_release), add=False)
        root.bind_all("<Button-3>", make_handler(on_right_press), add=False)
        root.bind_all("<B3-Motion>", make_handler(on_right_motion), add=False)
        root.bind_all("<ButtonRelease-3>", make_handler(on_release), add=False)
        root.bind_all("<MouseWheel>", make_handler(on_wheel), add=False)
        root.bind_all("<Button-4>", make_handler(on_wheel), add=False)
        root.bind_all("<Button-5>", make_handler(on_wheel), add=False)

        opengl_widget.focus_set()

        # Keyboard controls
        def on_key_f(event):
            """'f' key - fit all"""
            display.FitAll()

        def on_key_q(event):
            """'q' key - quit"""
            root.quit()

        def on_key_s(event):
            """'s' key - toggle selection mode"""
            toggle_selection_mode()

        def on_key_c(event):
            """'c' key - clear all selections"""
            clear_all_selections()

        def on_key_1(event):
            """'1' key - cycle selection fill color"""
            cycle_selection_color()

        def on_key_2(event):
            """'2' key - cycle outline color"""
            cycle_outline_color()

        # Bind keyboard to the same widget as mouse
        opengl_widget.bind("<f>", on_key_f)
        opengl_widget.bind("<F>", on_key_f)
        opengl_widget.bind("<q>", on_key_q)
        opengl_widget.bind("<Q>", on_key_q)
        opengl_widget.bind("<Escape>", on_key_q)
        opengl_widget.bind("<s>", on_key_s)
        opengl_widget.bind("<S>", on_key_s)
        opengl_widget.bind("<c>", on_key_c)
        opengl_widget.bind("<C>", on_key_c)
        opengl_widget.bind("<Key-1>", on_key_1)
        opengl_widget.bind("<Key-2>", on_key_2)

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
    from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine
    from OCC.Core.Graphic3d import Graphic3d_RenderingParams
    from OCC.Core.Prs3d import Prs3d_Drawer
    from OCC.Core.AIS import AIS_Shape

    bg_color = Quantity_Color(17/255.0, 18/255.0, 22/255.0, Quantity_TOC_sRGB)

    display.View.SetBgGradientStyle(Aspect_GFM_VER)
    display.View.SetBgGradientColors(bg_color, bg_color)
    display.View.SetBackgroundColor(bg_color)

    # Enable antialiasing for smoother edges
    render_params = display.View.ChangeRenderingParams()
    render_params.IsAntialiasingEnabled = True
    # NbMsaaSamples = 2 - Lower quality, better performance
    # NbMsaaSamples = 4 - Good balance (current setting)
    # NbMsaaSamples = 8 - Higher quality, may impact performance
    # NbMsaaSamples = 16 - Maximum quality, slower on some systems
    render_params.NbMsaaSamples = 4  # 4x MSAA for good quality/performance balance

    # Configure selection highlighting BEFORE activating selection mode
    print(f"\nApplying selection colors:")
    print(f"  Fill: RGB{SELECTION_COLOR}")
    print(f"  Outline: RGB{SELECTION_OUTLINE_COLOR}")
    print(f"  Width: {SELECTION_OUTLINE_WIDTH}px\n")

    # Create selection colors
    select_color = Quantity_Color(SELECTION_COLOR[0], SELECTION_COLOR[1], SELECTION_COLOR[2], Quantity_TOC_RGB)
    outline_color = Quantity_Color(SELECTION_OUTLINE_COLOR[0], SELECTION_OUTLINE_COLOR[1], SELECTION_OUTLINE_COLOR[2], Quantity_TOC_RGB)

    # Configure at context level ONLY
    try:
        # Disable hover highlighting - no highlight on mouse-over
        hover_drawer = display.Context.HighlightStyle()
        hover_drawer.SetTransparency(1.0)  # Completely transparent = invisible
        # Ensure no face boundaries on hover
        hover_drawer.SetFaceBoundaryDraw(False)

        # Selection style (when face is selected)
        select_drawer = display.Context.SelectionStyle()
        select_drawer.SetColor(select_color)
        select_drawer.SetDisplayMode(1)  # Shaded mode
        select_drawer.SetTransparency(SELECTION_TRANSPARENCY)

        # Configure outline/border for selected faces
        select_drawer.SetFaceBoundaryDraw(True)
        select_drawer.FaceBoundaryAspect().SetColor(outline_color)
        select_drawer.FaceBoundaryAspect().SetWidth(SELECTION_OUTLINE_WIDTH)
        select_drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

        # Store select_drawer for use in selection function
        display._select_drawer = select_drawer
        display._select_color = select_color
        display._outline_color = outline_color

        print("Context-level selection styling applied successfully")
    except Exception as e:
        print(f"Warning: Could not configure context selection style: {e}")

    # NOW enable face selection mode for all parts (after configuring style)
    for solid, color, ais_shape in parts_list:
        # Activate face selection mode (mode 4) for this shape
        display.Context.Activate(ais_shape, 4, False)  # 4 = TopAbs_FACE
        # Set the shape to allow sub-shape highlighting
        ais_shape.SetHilightMode(1)  # Use shaded highlighting

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

    print("\n" + "="*60)
    print("SELECTION COLORS CONFIGURATION:")
    print(f"  Fill: RGB({SELECTION_COLOR[0]}, {SELECTION_COLOR[1]}, {SELECTION_COLOR[2]})")
    print(f"  Outline: RGB({SELECTION_OUTLINE_COLOR[0]}, {SELECTION_OUTLINE_COLOR[1]}, {SELECTION_OUTLINE_COLOR[2]})")
    print(f"  Outline width: {SELECTION_OUTLINE_WIDTH}px")
    print("  (Edit these at the top of step_viewer.py to customize)")
    print("="*60)

    print("\nViewer Controls:")
    print("  - Left mouse button: Rotate")
    print("  - Right mouse button: Pan")
    print("  - Mouse wheel: Zoom")
    print("  - 'f': Fit all")
    print("  - 's': Toggle face selection mode")
    print("  - 'c': Clear all selections")
    print("  - '1': Cycle selection fill color (in selection mode)")
    print("  - '2': Cycle outline color (in selection mode)")
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
