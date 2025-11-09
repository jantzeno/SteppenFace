#!/usr/bin/env python3
"""
STEP File Viewer with Solid CAD Representation
Displays STEP files using OpenCASCADE's native BREP representation with face selection capabilities.
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import tkinter as tk
from tkinter import ttk

try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE
    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial
    from OCC.Core.AIS import AIS_Shape
    from OCC.Core.Prs3d import Prs3d_Drawer
    from OCC.Core.Aspect import Aspect_TypeOfLine
except ImportError:
    print("Error: pythonocc-core is not installed.")
    print("Install it using: conda install -c conda-forge pythonocc-core")
    sys.exit(1)


# ============================================================================
# Configuration Class - Single Responsibility: Hold configuration values
# ============================================================================
class ViewerConfig:
    """Configuration settings for the STEP viewer."""

    # Display settings
    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 768
    BACKGROUND_COLOR = (17/255.0, 18/255.0, 22/255.0)
    MSAA_SAMPLES = 4  # Anti-aliasing quality

    # Color scheme
    DARK_BG = '#111216'
    PANEL_BG = '#1a1b1f'
    SEPARATOR_BG = '#2a2b2f'
    SELECTION_MODE_BG = '#2a2520'

    # Selection settings
    SELECTION_COLOR = (1.0, 0.5, 0.0)
    SELECTION_OUTLINE_COLOR = (0.07, 0.07, 0.09)
    SELECTION_OUTLINE_WIDTH = 2.0
    SELECTION_TRANSPARENCY = 0.1

    # Color presets
    SELECTION_COLOR_PRESETS = [
        ((1.0, 0.5, 0.0), "Orange"),
        ((1.0, 0.0, 0.0), "Red"),
        ((0.0, 1.0, 0.0), "Green"),
        ((0.0, 0.0, 1.0), "Blue"),
        ((1.0, 0.0, 1.0), "Magenta"),
        ((0.0, 1.0, 1.0), "Cyan"),
        ((1.0, 1.0, 0.0), "Yellow"),
    ]

    OUTLINE_COLOR_PRESETS = [
        ((0.07, 0.07, 0.09), "Dark Gray"),
        ((0.0, 0.0, 0.0), "Black"),
        ((1.0, 1.0, 1.0), "White"),
        ((1.0, 1.0, 0.0), "Yellow"),
        ((0.0, 1.0, 1.0), "Cyan"),
    ]

    # Part colors (colorblind-friendly palette)
    PART_PALETTE = [
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


# ============================================================================
# Material Renderer - Single Responsibility: Apply materials to shapes
# ============================================================================
class MaterialRenderer:
    """Handles material application to CAD shapes."""

    @staticmethod
    def apply_matte_material(ais_shape, color: Quantity_Color, edge_color: Optional[Quantity_Color] = None):
        """
        Apply a matte plastic material with edge coloring.

        Args:
            ais_shape: The AIS shape object
            color: Quantity_Color for the shape
            edge_color: Optional edge color (defaults to dark gray)
        """
        material = Graphic3d_MaterialAspect(Graphic3d_NameOfMaterial.Graphic3d_NOM_PLASTIC)
        material.SetAmbientColor(color)
        material.SetDiffuseColor(color)
        dark_color = Quantity_Color(0.05, 0.05, 0.05, Quantity_TOC_RGB)
        material.SetSpecularColor(dark_color)
        ais_shape.SetMaterial(material)

        if edge_color is None:
            edge_color = Quantity_Color(0.15, 0.15, 0.15, Quantity_TOC_RGB)

        drawer = ais_shape.Attributes()
        drawer.SetFaceBoundaryDraw(True)
        drawer.FaceBoundaryAspect().SetColor(edge_color)
        drawer.FaceBoundaryAspect().SetWidth(1.0)


# ============================================================================
# Color Manager - Single Responsibility: Manage color presets and cycling
# ============================================================================
class ColorManager:
    """Manages selection colors and color cycling."""

    def __init__(self, config: ViewerConfig):
        self.config = config
        self.fill_index = 0
        self.outline_index = 0

    def get_current_fill_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Get current fill color preset."""
        return self.config.SELECTION_COLOR_PRESETS[self.fill_index]

    def get_current_outline_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Get current outline color preset."""
        return self.config.OUTLINE_COLOR_PRESETS[self.outline_index]

    def cycle_fill_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Cycle to next fill color preset."""
        self.fill_index = (self.fill_index + 1) % len(self.config.SELECTION_COLOR_PRESETS)
        return self.get_current_fill_color()

    def cycle_outline_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Cycle to next outline color preset."""
        self.outline_index = (self.outline_index + 1) % len(self.config.OUTLINE_COLOR_PRESETS)
        return self.get_current_outline_color()

    def get_fill_quantity_color(self) -> Quantity_Color:
        """Get current fill color as Quantity_Color."""
        rgb, _ = self.get_current_fill_color()
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)

    def get_outline_quantity_color(self) -> Quantity_Color:
        """Get current outline color as Quantity_Color."""
        rgb, _ = self.get_current_outline_color()
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)


# ============================================================================
# Selection Manager - Single Responsibility: Handle face selection state
# ============================================================================
class SelectionManager:
    """Manages face selection state and highlighting."""

    def __init__(self, display, color_manager: ColorManager, config: ViewerConfig):
        self.display = display
        self.color_manager = color_manager
        self.config = config
        self.is_selection_mode = False
        self.highlighted_faces: Dict[int, AIS_Shape] = {}
        self.selection_label = None

    def set_selection_label(self, label):
        """Set reference to the selection count label."""
        self.selection_label = label

    def toggle_mode(self) -> bool:
        """Toggle between navigation and selection mode. Returns new mode state."""
        self.is_selection_mode = not self.is_selection_mode
        return self.is_selection_mode

    def select_face_at_position(self, x: int, y: int, view, root) -> bool:
        """
        Select or deselect a face at the given screen position.

        Returns:
            True if a face was selected/deselected, False otherwise
        """
        try:
            self.display.Context.MoveTo(x, y, view, True)

            if not self.display.Context.HasDetected():
                return False

            detected_shape = self.display.Context.DetectedShape()
            if detected_shape.IsNull():
                return False

            face_hash = detected_shape.__hash__()

            if face_hash in self.highlighted_faces:
                # Deselect
                ais_highlight = self.highlighted_faces[face_hash]
                self.display.Context.Remove(ais_highlight, True)
                del self.highlighted_faces[face_hash]
                action = "Deselected"
            else:
                # Select
                ais_highlight = AIS_Shape(detected_shape)
                ais_highlight.SetColor(self.color_manager.get_fill_quantity_color())
                ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)

                drawer = ais_highlight.Attributes()
                drawer.SetFaceBoundaryDraw(True)
                drawer.FaceBoundaryAspect().SetColor(self.color_manager.get_outline_quantity_color())
                drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
                drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

                self.display.Context.Display(ais_highlight, True)
                self.highlighted_faces[face_hash] = ais_highlight
                action = "Selected"

            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()
            root.update_idletasks()
            root.update()

            count = len(self.highlighted_faces)
            if self.selection_label:
                self.selection_label.config(text=f"Selected: {count} face{'s' if count != 1 else ''}")

            print(f"{action} face (total: {count})")
            return True

        except Exception as e:
            print(f"Error selecting face: {e}")
            return False

    def clear_all(self, root):
        """Clear all selected faces."""
        for ais_highlight in self.highlighted_faces.values():
            self.display.Context.Remove(ais_highlight, True)

        self.highlighted_faces.clear()
        self.display.Context.ClearSelected(True)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        if self.selection_label:
            self.selection_label.config(text="Selected: 0 faces")

        print("Cleared all selections")

    def update_all_colors(self, root):
        """Update colors of all currently selected faces."""
        fill_color = self.color_manager.get_fill_quantity_color()
        outline_color = self.color_manager.get_outline_quantity_color()

        for ais_highlight in self.highlighted_faces.values():
            ais_highlight.SetColor(fill_color)
            ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)

            drawer = ais_highlight.Attributes()
            drawer.SetFaceBoundaryDraw(True)
            drawer.FaceBoundaryAspect().SetColor(outline_color)
            drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
            drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

            self.display.Context.Redisplay(ais_highlight, True)

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        fill_rgb, fill_name = self.color_manager.get_current_fill_color()
        outline_rgb, outline_name = self.color_manager.get_current_outline_color()
        print(f"\nSelection colors updated:")
        print(f"  Fill: {fill_name} RGB{fill_rgb}")
        print(f"  Outline: {outline_name} RGB{outline_rgb}\n")

    def get_selection_count(self) -> int:
        """Get number of currently selected faces."""
        return len(self.highlighted_faces)


# ============================================================================
# Mouse Controller - Single Responsibility: Handle mouse interactions
# ============================================================================
class MouseController:
    """Handles all mouse events for navigation and selection."""

    def __init__(self, view, display, selection_manager: SelectionManager, root):
        self.view = view
        self.display = display
        self.selection_manager = selection_manager
        self.root = root
        self.start_x = 0
        self.start_y = 0
        self.button = None

    def on_left_press(self, event):
        """Handle left mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 1

        if not self.selection_manager.is_selection_mode:
            self.view.StartRotation(event.x, event.y)

    def on_left_motion(self, event):
        """Handle left mouse button drag."""
        if self.button == 1 and not self.selection_manager.is_selection_mode:
            self.view.Rotation(event.x, event.y)
            self.display.Context.UpdateCurrentViewer()
            self.root.update_idletasks()

    def on_right_press(self, event):
        """Handle right mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 3

    def on_right_motion(self, event):
        """Handle right mouse button drag."""
        if self.button == 3:
            dx = event.x - self.start_x
            dy = self.start_y - event.y
            self.view.Pan(dx, dy)
            self.display.Context.UpdateCurrentViewer()
            self.root.update_idletasks()
            self.start_x = event.x
            self.start_y = event.y

    def on_release(self, event):
        """Handle mouse button release."""
        # Check if this was a click (not a drag) in selection mode
        if self.button == 1 and self.selection_manager.is_selection_mode:
            dx = abs(event.x - self.start_x)
            dy = abs(event.y - self.start_y)
            if dx < 5 and dy < 5:
                self.selection_manager.select_face_at_position(event.x, event.y, self.view, self.root)

        self.button = None

    def on_wheel(self, event):
        """Handle mouse wheel zoom."""
        if event.delta > 0 or event.num == 4:
            self.display.ZoomFactor(1.1)
        elif event.delta < 0 or event.num == 5:
            self.display.ZoomFactor(0.9)


# ============================================================================
# Keyboard Controller - Single Responsibility: Handle keyboard shortcuts
# ============================================================================
class KeyboardController:
    """Handles all keyboard shortcuts."""

    def __init__(self, display, selection_manager: SelectionManager, color_manager: ColorManager,
                 root, config: ViewerConfig):
        self.display = display
        self.selection_manager = selection_manager
        self.color_manager = color_manager
        self.root = root
        self.config = config
        self.mode_label = None
        self.selection_label = None

    def set_ui_labels(self, mode_label, selection_label):
        """Set references to UI labels for updates."""
        self.mode_label = mode_label
        self.selection_label = selection_label

    def on_key_f(self, event):
        """Fit all objects in view."""
        self.display.FitAll()

    def on_key_q(self, event):
        """Quit application."""
        self.root.quit()

    def on_key_s(self, event):
        """Toggle selection mode."""
        is_selection = self.selection_manager.toggle_mode()

        if is_selection:
            print("\n*** FACE SELECTION MODE ***")
            print("  - Left click: Select/deselect faces")
            print("  - Right click: Pan")
            print("  - Mouse wheel: Zoom")
            print("  - 's': Exit selection mode")
            print("  - 'c': Clear all selections")
            print("  - '1': Cycle selection fill color")
            print("  - '2': Cycle outline color")

            fill_rgb, fill_name = self.color_manager.get_current_fill_color()
            outline_rgb, outline_name = self.color_manager.get_current_outline_color()
            print(f"\n  CURRENT COLORS:")
            print(f"    Fill: {fill_name} RGB{fill_rgb}")
            print(f"    Outline: {outline_name} RGB{outline_rgb}")
            print(f"    Outline width: {self.config.SELECTION_OUTLINE_WIDTH}px\n")

            self.root.configure(bg=self.config.SELECTION_MODE_BG)
            if self.mode_label:
                self.mode_label.config(text="Mode: Selection", fg='#00ff00')
        else:
            print("\n*** NAVIGATION MODE ***")
            print("  - Left click: Rotate")
            print("  - Right click: Pan")
            print("  - Mouse wheel: Zoom")
            print("  - 's': Enter selection mode")

            self.root.configure(bg=self.config.DARK_BG)
            if self.mode_label:
                self.mode_label.config(text="Mode: Navigation", fg='#00e0ff')

    def on_key_c(self, event):
        """Clear all selections."""
        self.selection_manager.clear_all(self.root)

    def on_key_1(self, event):
        """Cycle selection fill color."""
        self.color_manager.cycle_fill_color()
        self.selection_manager.update_all_colors(self.root)

    def on_key_2(self, event):
        """Cycle outline color."""
        self.color_manager.cycle_outline_color()
        self.selection_manager.update_all_colors(self.root)


# ============================================================================
# STEP Loader - Single Responsibility: Load and parse STEP files
# ============================================================================
class StepLoader:
    """Loads STEP files and extracts geometry."""

    @staticmethod
    def load_file(filename: str):
        """
        Load a STEP file and return the shape.

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

        # Report entities
        explorer_solid = TopExp_Explorer(shape, TopAbs_SOLID)
        solid_count = sum(1 for _ in iter(lambda: explorer_solid.More() and not explorer_solid.Next(), False))

        explorer_face = TopExp_Explorer(shape, TopAbs_FACE)
        face_count = sum(1 for _ in iter(lambda: explorer_face.More() and not explorer_face.Next(), False))

        print(f"  Solids: {solid_count}")
        print(f"  Faces: {face_count}")

        return shape

    @staticmethod
    def extract_solids(shape) -> List:
        """Extract all solids from a shape."""
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        solids = []
        while explorer.More():
            solids.append(explorer.Current())
            explorer.Next()
        return solids


# ============================================================================
# Viewer UI - Single Responsibility: Build and manage UI components
# ============================================================================
class ViewerUI:
    """Manages the viewer UI components."""

    def __init__(self, root: tk.Tk, config: ViewerConfig):
        self.root = root
        self.config = config
        self.parts_tree = None
        self.mode_label = None
        self.selection_label = None

    def setup_window(self):
        """Setup the main window."""
        self.root.title("STEP File Viewer")
        self.root.geometry(f"{self.config.WINDOW_WIDTH}x{self.config.WINDOW_HEIGHT}")
        self.root.configure(borderwidth=0, highlightthickness=0, bg=self.config.DARK_BG)

    def create_layout(self):
        """Create the main layout with panels. Returns (paned_window, left_panel, right_panel)."""
        paned_window = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg=self.config.DARK_BG,
            sashwidth=5, sashrelief=tk.RAISED, borderwidth=0
        )
        paned_window.pack(fill=tk.BOTH, expand=True)

        # Left panel for parts list
        left_panel = self._create_left_panel(paned_window)

        # Right panel for 3D viewer
        right_panel = tk.Frame(paned_window, bg=self.config.DARK_BG, borderwidth=0, highlightthickness=0)
        right_panel.pack_propagate(True)

        paned_window.add(left_panel, minsize=200, width=250, stretch="never")
        paned_window.add(right_panel, minsize=400, stretch="always")

        return paned_window, left_panel, right_panel

    def _create_left_panel(self, parent):
        """Create the left navigation panel."""
        left_panel = tk.Frame(parent, bg=self.config.PANEL_BG, width=250, borderwidth=0, highlightthickness=0)

        # Header
        header = tk.Label(
            left_panel, text="Parts", bg=self.config.PANEL_BG, fg='#ffffff',
            font=('Arial', 10, 'bold'), anchor='w', padx=10, pady=5
        )
        header.pack(fill=tk.X)

        separator = tk.Frame(left_panel, bg=self.config.SEPARATOR_BG, height=1)
        separator.pack(fill=tk.X)

        # Tree view
        tree_frame = tk.Frame(left_panel, bg=self.config.PANEL_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._configure_tree_style()

        self.parts_tree = ttk.Treeview(tree_frame, style="Dark.Treeview", show='tree')
        self.parts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.parts_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.parts_tree.configure(yscrollcommand=scrollbar.set)

        # Status panel
        self._create_status_panel(left_panel)

        return left_panel

    def _configure_tree_style(self):
        """Configure dark theme for tree view."""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dark.Treeview",
                       background=self.config.PANEL_BG,
                       foreground='#ffffff',
                       fieldbackground=self.config.PANEL_BG,
                       borderwidth=0,
                       relief='flat')
        style.configure("Dark.Treeview.Heading",
                       background=self.config.SEPARATOR_BG,
                       foreground='#ffffff',
                       borderwidth=0,
                       relief='flat')
        style.map("Dark.Treeview",
                 background=[('selected', '#3a3b3f')],
                 foreground=[('selected', '#ffffff')])

    def _create_status_panel(self, parent):
        """Create status panel with mode and selection info."""
        status_separator = tk.Frame(parent, bg=self.config.SEPARATOR_BG, height=1)
        status_separator.pack(fill=tk.X)

        status_frame = tk.Frame(parent, bg=self.config.PANEL_BG)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.mode_label = tk.Label(
            status_frame, text="Mode: Navigation", bg=self.config.PANEL_BG, fg='#00e0ff',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        self.mode_label.pack(fill=tk.X)

        self.selection_label = tk.Label(
            status_frame, text="Selected: 0 faces", bg=self.config.PANEL_BG, fg='#00ff00',
            font=('Arial', 9, 'bold'), anchor='w'
        )
        self.selection_label.pack(fill=tk.X, pady=(5, 0))

    def populate_parts_tree(self, parts_list: List):
        """Populate the parts tree with parts."""
        if not self.parts_tree:
            return

        root_node = self.parts_tree.insert(
            '', 'end',
            text=f'Model ({len(parts_list)} part{"s" if len(parts_list) != 1 else ""})',
            open=True
        )

        for i, (solid, color, ais_shape) in enumerate(parts_list):
            r, g, b = color
            hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
            part_name = f'■ Part {i+1}'
            self.parts_tree.insert(root_node, 'end', text=part_name, tags=(f'part_{i}',))
            self.parts_tree.tag_configure(f'part_{i}', foreground=hex_color)


# ============================================================================
# Main STEP Viewer - Coordinator following Dependency Inversion Principle
# ============================================================================
class StepViewer:
    """Main coordinator class for the STEP viewer application."""

    def __init__(self, filename: str, config: Optional[ViewerConfig] = None):
        self.filename = filename
        self.config = config or ViewerConfig()
        self.root = tk.Tk()
        self.ui = ViewerUI(self.root, self.config)
        self.shape = None
        self.display = None
        self.parts_list = []

    def run(self):
        """Main entry point to run the viewer."""
        # Load STEP file
        self.shape = StepLoader.load_file(self.filename)
        if self.shape is None:
            return

        # Setup UI
        self.ui.setup_window()
        paned_window, left_panel, right_panel = self.ui.create_layout()

        self.root.update_idletasks()

        # Initialize 3D display
        self._init_display(right_panel)

        # Setup managers and controllers
        self._setup_controllers()

        # Display the model
        self._display_model()

        # Configure display settings
        self._configure_display()

        # Populate UI
        self.ui.populate_parts_tree(self.parts_list)

        # Print controls
        self._print_controls()

        # Final setup
        self.root.after(150, self._final_update)
        self.root.mainloop()

    def _init_display(self, parent):
        """Initialize the 3D display canvas."""
        from OCC.Display.tkDisplay import tkViewer3d

        canvas = tkViewer3d(parent)
        canvas.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        canvas.configure(borderwidth=0, highlightthickness=0, relief='flat',
                        bg=self.config.DARK_BG, width=0, height=0)

        self.root.update_idletasks()
        self.display = canvas._display
        self.canvas = canvas
        self.view = self.display.View

    def _setup_controllers(self):
        """Setup all controllers and managers."""
        # Initialize managers
        self.color_manager = ColorManager(self.config)
        self.selection_manager = SelectionManager(self.display, self.color_manager, self.config)
        self.selection_manager.set_selection_label(self.ui.selection_label)

        # Initialize controllers
        self.mouse_controller = MouseController(
            self.view, self.display, self.selection_manager, self.root
        )
        self.keyboard_controller = KeyboardController(
            self.display, self.selection_manager, self.color_manager, self.root, self.config
        )
        self.keyboard_controller.set_ui_labels(self.ui.mode_label, self.ui.selection_label)

        # Bind events
        self._bind_events()

    def _bind_events(self):
        """Bind mouse and keyboard events."""
        # Unbind OCC's default handlers
        widgets_to_unbind = [self.canvas, self.root]
        for widget in widgets_to_unbind:
            for event in ["<Button-1>", "<Button-2>", "<Button-3>",
                          "<B1-Motion>", "<B2-Motion>", "<B3-Motion>",
                          "<ButtonRelease-1>", "<ButtonRelease-2>", "<ButtonRelease-3>"]:
                try:
                    widget.unbind(event)
                except:
                    pass

        # Helper to stop event propagation
        def make_handler(func):
            def handler(event):
                func(event)
                return "break"
            return handler

        # Bind mouse events
        self.root.bind_all("<Button-1>", make_handler(self.mouse_controller.on_left_press))
        self.root.bind_all("<B1-Motion>", make_handler(self.mouse_controller.on_left_motion))
        self.root.bind_all("<ButtonRelease-1>", make_handler(self.mouse_controller.on_release))
        self.root.bind_all("<Button-3>", make_handler(self.mouse_controller.on_right_press))
        self.root.bind_all("<B3-Motion>", make_handler(self.mouse_controller.on_right_motion))
        self.root.bind_all("<ButtonRelease-3>", make_handler(self.mouse_controller.on_release))
        self.root.bind_all("<MouseWheel>", make_handler(self.mouse_controller.on_wheel))
        self.root.bind_all("<Button-4>", make_handler(self.mouse_controller.on_wheel))
        self.root.bind_all("<Button-5>", make_handler(self.mouse_controller.on_wheel))

        # Bind keyboard events
        self.canvas.bind("<f>", self.keyboard_controller.on_key_f)
        self.canvas.bind("<F>", self.keyboard_controller.on_key_f)
        self.canvas.bind("<q>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<Q>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<Escape>", self.keyboard_controller.on_key_q)
        self.canvas.bind("<s>", self.keyboard_controller.on_key_s)
        self.canvas.bind("<S>", self.keyboard_controller.on_key_s)
        self.canvas.bind("<c>", self.keyboard_controller.on_key_c)
        self.canvas.bind("<C>", self.keyboard_controller.on_key_c)
        self.canvas.bind("<Key-1>", self.keyboard_controller.on_key_1)
        self.canvas.bind("<Key-2>", self.keyboard_controller.on_key_2)

        self.canvas.focus_set()

        # Resize handler
        self._setup_resize_handler()

    def _setup_resize_handler(self):
        """Setup resize event handler with debouncing."""
        resize_state = {'pending': False, 'initialized': False}

        def on_resize(event):
            if not resize_state['initialized']:
                return

            if not resize_state['pending']:
                resize_state['pending'] = True

                def do_resize():
                    try:
                        self.display.View.MustBeResized()
                        self.display.View.Redraw()
                    except Exception as e:
                        print(f"Warning: Could not resize view: {e}")
                    finally:
                        resize_state['pending'] = False

                self.root.after(10, do_resize)

        self.canvas.bind('<Configure>', on_resize)
        self.resize_state = resize_state

    def _display_model(self):
        """Display the loaded model with colored parts."""
        import random

        solids = StepLoader.extract_solids(self.shape)
        palette = self.config.PART_PALETTE.copy()

        if len(solids) == 0:
            print("No individual solids found, displaying shape as single object")
            color = Quantity_Color(palette[0][0], palette[0][1], palette[0][2], Quantity_TOC_RGB)
            ais_shape = self.display.DisplayShape(self.shape, color=color, update=False)[0]
            MaterialRenderer.apply_matte_material(ais_shape, color)
            self.parts_list.append((self.shape, palette[0], ais_shape))
        else:
            random.shuffle(palette)
            for i, solid in enumerate(solids):
                r, g, b = palette[i % len(palette)]
                color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
                ais_shape = self.display.DisplayShape(solid, color=color, update=False)[0]
                MaterialRenderer.apply_matte_material(ais_shape, color)
                self.parts_list.append((solid, (r, g, b), ais_shape))

            print(f"Assigned colors to {len(solids)} solid(s)")

        self.display.Context.UpdateCurrentViewer()
        self.display.FitAll()
        self.display.Repaint()

    def _configure_display(self):
        """Configure display settings (background, antialiasing, selection)."""
        from OCC.Core.Quantity import Quantity_TOC_sRGB
        from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine

        # Background color
        bg_color = Quantity_Color(
            self.config.BACKGROUND_COLOR[0],
            self.config.BACKGROUND_COLOR[1],
            self.config.BACKGROUND_COLOR[2],
            Quantity_TOC_sRGB
        )
        self.display.View.SetBgGradientStyle(Aspect_GFM_VER)
        self.display.View.SetBgGradientColors(bg_color, bg_color)
        self.display.View.SetBackgroundColor(bg_color)

        # Antialiasing
        render_params = self.display.View.ChangeRenderingParams()
        render_params.IsAntialiasingEnabled = True
        render_params.NbMsaaSamples = self.config.MSAA_SAMPLES

        # Selection highlighting
        print(f"\nApplying selection colors:")
        print(f"  Fill: RGB{self.config.SELECTION_COLOR}")
        print(f"  Outline: RGB{self.config.SELECTION_OUTLINE_COLOR}")
        print(f"  Width: {self.config.SELECTION_OUTLINE_WIDTH}px\n")

        # Configure hover (disabled) and selection styles
        try:
            hover_drawer = self.display.Context.HighlightStyle()
            hover_drawer.SetTransparency(1.0)  # Invisible
            hover_drawer.SetFaceBoundaryDraw(False)

            select_color = self.color_manager.get_fill_quantity_color()
            outline_color = self.color_manager.get_outline_quantity_color()

            select_drawer = self.display.Context.SelectionStyle()
            select_drawer.SetColor(select_color)
            select_drawer.SetDisplayMode(1)
            select_drawer.SetTransparency(self.config.SELECTION_TRANSPARENCY)
            select_drawer.SetFaceBoundaryDraw(True)
            select_drawer.FaceBoundaryAspect().SetColor(outline_color)
            select_drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
            select_drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

            print("Context-level selection styling applied successfully")
        except Exception as e:
            print(f"Warning: Could not configure selection style: {e}")

        # Enable face selection for all parts
        for solid, color, ais_shape in self.parts_list:
            self.display.Context.Activate(ais_shape, 4, False)  # 4 = TopAbs_FACE
            ais_shape.SetHilightMode(1)

    def _print_controls(self):
        """Print viewer controls to console."""
        print("\n" + "="*60)
        print("SELECTION COLORS CONFIGURATION:")
        print(f"  Fill: RGB{self.config.SELECTION_COLOR}")
        print(f"  Outline: RGB{self.config.SELECTION_OUTLINE_COLOR}")
        print(f"  Outline width: {self.config.SELECTION_OUTLINE_WIDTH}px")
        print("  (Edit ViewerConfig class to customize)")
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

    def _final_update(self):
        """Final update after UI is fully initialized."""
        try:
            self.display.View.MustBeResized()
            self.display.Context.UpdateCurrentViewer()
            self.display.FitAll()
            self.display.Repaint()
            self.resize_state['initialized'] = True
        except Exception as e:
            print(f"Warning: Could not perform final update: {e}")


# ============================================================================
# Entry Point
# ============================================================================
def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python step_viewer.py <step_file>")
        print("\nExample:")
        print("  python step_viewer.py model.step")
        print("  python step_viewer.py model.stp")
        sys.exit(1)

    step_file = sys.argv[1]
    viewer = StepViewer(step_file)
    viewer.run()


if __name__ == "__main__":
    main()
