"""
Main STEP viewer application.
"""

import random
from typing import Optional, Tuple
import tkinter as tk

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_TOC_sRGB
from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine, Aspect_TOTP_RIGHT_LOWER

from .config import ViewerConfig
from .managers import ColorManager, SelectionManager, ExplodeManager, DeduplicationManager, PlanarAlignmentManager, PlateManager
from .controllers import MouseController, KeyboardController
from .loaders import StepLoader
from .rendering import MaterialRenderer
from .ui import ViewerUI


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
        self.hidden_selections = {}  # Store selections for hidden duplicate parts

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

        # Populate UI (deduplication manager not initialized yet at this point)
        self.ui.populate_parts_tree(self.parts_list)

        # Setup tree selection callback
        self._setup_tree_selection()

        # Setup explode slider callback
        self._setup_explode_slider()

        # Setup view buttons
        self._setup_view_buttons()

        # Setup plate controls
        self._setup_plate_controls()

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
        self.explode_manager = ExplodeManager()
        self.explode_manager.selection_manager = self.selection_manager  # Link for transformation updates
        self.deduplication_manager = DeduplicationManager()
        self.plate_manager = PlateManager(
            self.config.SHEET_WIDTH_MM,
            self.config.SHEET_HEIGHT_MM
        )
        self.planar_alignment_manager = PlanarAlignmentManager(self.plate_manager)
        self.selection_manager.set_planar_alignment_manager(self.planar_alignment_manager)

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

    def _get_world_coordinates(self, screen_x: int, screen_y: int) -> Tuple[float, float, float]:
        """
        Convert screen coordinates to 3D world coordinates on the Z=0 plane.
        Uses ray casting to find intersection with the Z=0 plane.

        Args:
            screen_x: X coordinate in screen space
            screen_y: Y coordinate in screen space

        Returns:
            Tuple of (x, y, z) world coordinates
        """
        try:
            from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir, gp_Lin
            from OCC.Core.IntAna import IntAna_IntConicQuad

            view = self.display.View

            # Get ray from camera through screen point
            # ConvertWithProj returns 6 values: (x, y, z, dx, dy, dz)
            # where (x,y,z) is a point on the ray and (dx,dy,dz) is the normalized direction
            px, py, pz, dx, dy, dz = view.ConvertWithProj(screen_x, screen_y)

            # Create ray from point and direction
            ray_origin = gp_Pnt(px, py, pz)
            ray_dir = gp_Dir(dx, dy, dz)
            ray = gp_Lin(ray_origin, ray_dir)

            # Create Z=0 plane
            plane_origin = gp_Pnt(0, 0, 0)
            plane_normal = gp_Dir(0, 0, 1)
            z_plane = gp_Pln(plane_origin, plane_normal)

            # Calculate intersection
            intersection = IntAna_IntConicQuad(ray, z_plane, 1e-9)

            if intersection.IsDone() and intersection.NbPoints() > 0:
                # Get first intersection point
                point = intersection.Point(1)
                return (point.X(), point.Y(), 0.0)
            else:
                # Fallback: manual calculation
                # Ray equation: P = P0 + t * D
                # Plane equation: Z = 0
                # Solve for t: pz + t * dz = 0  =>  t = -pz / dz
                if abs(dz) > 1e-9:
                    t = -pz / dz
                    x = px + t * dx
                    y = py + t * dy
                    return (x, y, 0.0)
                else:
                    # Ray is parallel to Z=0 plane
                    return (px, py, 0.0)
        except Exception as e:
            print(f"Warning: Could not convert screen coordinates: {e}")
            return (0.0, 0.0, 0.0)

    def _on_left_press_wrapper(self, event):
        """Wrapper for left mouse press that handles exclusion zone drawing."""
        if self.exclusion_draw_mode and self.planar_alignment_manager.is_aligned:
            world_x, world_y, _ = self._get_world_coordinates(event.x, event.y)
            if self._handle_exclusion_zone_click(world_x, world_y):
                return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_left_press(event)

    def _on_left_motion_wrapper(self, event):
        """Wrapper for left mouse motion that handles exclusion zone drawing."""
        if self.exclusion_draw_mode and self.planar_alignment_manager.is_aligned and self.exclusion_start_point:
            world_x, world_y, _ = self._get_world_coordinates(event.x, event.y)
            if self._handle_exclusion_zone_drag(world_x, world_y):
                return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_left_motion(event)

    def _on_release_wrapper(self, event):
        """Wrapper for mouse release that handles exclusion zone drawing."""
        if self.exclusion_draw_mode and self.planar_alignment_manager.is_aligned and self.exclusion_start_point:
            world_x, world_y, _ = self._get_world_coordinates(event.x, event.y)
            if self._handle_exclusion_zone_release(world_x, world_y):
                return  # Consumed by exclusion zone drawing

        # Otherwise, delegate to normal mouse controller
        self.mouse_controller.on_release(event)

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

        # Helper to stop event propagation (but allow tree widget events)
        def make_handler(func):
            def handler(event):
                # Don't intercept events from the parts tree
                if hasattr(event.widget, 'winfo_class') and event.widget.winfo_class() == 'Treeview':
                    return
                func(event)
                return "break"
            return handler

        # Bind mouse events (wrap to handle exclusion zone drawing)
        self.root.bind_all("<Button-1>", make_handler(self._on_left_press_wrapper))
        self.root.bind_all("<B1-Motion>", make_handler(self._on_left_motion_wrapper))
        self.root.bind_all("<ButtonRelease-1>", make_handler(self._on_release_wrapper))
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
        self.canvas.bind("<d>", lambda e: self.toggle_duplicate_visibility())
        self.canvas.bind("<D>", lambda e: self.toggle_duplicate_visibility())
        self.canvas.bind("<p>", lambda e: self.toggle_planar_alignment())
        self.canvas.bind("<P>", lambda e: self.toggle_planar_alignment())
        self.canvas.bind("<l>", lambda e: self.select_largest_faces())
        self.canvas.bind("<L>", lambda e: self.select_largest_faces())
        self.canvas.bind("<o>", lambda e: self.toggle_origin())
        self.canvas.bind("<O>", lambda e: self.toggle_origin())

        # Bind view preset keys (Shift + number keys)
        self.canvas.bind("<exclam>", self.keyboard_controller.on_key_shift_1)  # Shift+1 = ! (Front)
        self.canvas.bind("<at>", self.keyboard_controller.on_key_shift_2)  # Shift+2 = @ (Back)
        self.canvas.bind("<numbersign>", self.keyboard_controller.on_key_shift_3)  # Shift+3 = # (Right)
        self.canvas.bind("<dollar>", self.keyboard_controller.on_key_shift_4)  # Shift+4 = $ (Left)
        self.canvas.bind("<percent>", self.keyboard_controller.on_key_shift_5)  # Shift+5 = % (Top)
        self.canvas.bind("<asciicircum>", self.keyboard_controller.on_key_shift_6)  # Shift+6 = ^ (Bottom)
        self.canvas.bind("<ampersand>", self.keyboard_controller.on_key_shift_7)  # Shift+7 = & (Isometric)

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

        # Initialize explode manager with parts
        self.explode_manager.initialize_parts(self.parts_list)

        # Initialize planar alignment manager with parts
        self.planar_alignment_manager.initialize_parts(self.parts_list)

    def _configure_display(self):
        """Configure display settings (background, antialiasing, selection)."""
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

        # Add XYZ axis triedron widget
        self._add_triedron()

    def _add_triedron(self):
        """Add XYZ axis orientation widget to the view."""
        try:
            # Enable the view corner trihedron
            # Arguments: position (Aspect_TypeOfTriedronPosition), color (Quantity_Color), scale, asWireframe
            self.view.TriedronDisplay(Aspect_TOTP_RIGHT_LOWER, Quantity_Color(1.0, 1.0, 1.0, Quantity_TOC_RGB), 0.1, True)
            print("XYZ axis widget added to view")
        except Exception as e:
            print(f"Warning: Could not add XYZ axis widget: {e}")

    def _setup_explode_slider(self):
        """Setup the explode slider callback."""
        def on_slider_change(value):
            factor = float(value)
            self.explode_manager.set_explosion_factor(factor, self.display, self.root)
            self.ui.explode_label.config(text=f"Explode: {factor:.2f}")

        self.ui.explode_slider.config(command=on_slider_change)

        # Setup material thickness slider callback
        def on_thickness_change(value):
            thickness = float(value)
            self.config.MATERIAL_THICKNESS_MM = thickness
            self.ui.thickness_label.config(text=f"Material: {thickness:.2f}mm")

        self.ui.thickness_slider.config(command=on_thickness_change)

    def _setup_tree_selection(self):
        """Setup tree selection to highlight parts with multi-select and toggle."""
        self.highlighted_parts = {}  # Track highlighted parts: {part_idx: (ais_shape, original_color)}

        def on_tree_click(event):
            # Get the item that was clicked
            item = self.ui.parts_tree.identify_row(event.y)
            if not item:
                return

            # Get the tag to extract part index
            tags = self.ui.parts_tree.item(item, 'tags')
            if not tags or not tags[0].startswith('part_'):
                return

            part_idx = int(tags[0].split('_')[1])

            # Toggle highlight for this part
            if part_idx in self.highlighted_parts:
                self._unhighlight_part(part_idx)
                # Deselect in tree
                self.ui.parts_tree.selection_remove(item)
            else:
                self._highlight_part(part_idx)
                # Select in tree
                self.ui.parts_tree.selection_add(item)

            # Return focus to canvas so keyboard shortcuts work
            self.canvas.focus_set()

            return "break"  # Prevent default selection behavior

        # Bind to ButtonRelease to handle clicks
        self.ui.parts_tree.bind('<ButtonRelease-1>', on_tree_click)

    def _highlight_part(self, part_idx: int):
        """Highlight a part in the 3D view."""
        if part_idx < 0 or part_idx >= len(self.parts_list):
            return

        # Already highlighted
        if part_idx in self.highlighted_parts:
            return

        _, color, ais_shape = self.parts_list[part_idx]

        # Store original color
        original_color = Quantity_Color(color[0], color[1], color[2], Quantity_TOC_RGB)

        # Create bright highlight color (yellow)
        highlight_color = Quantity_Color(1.0, 1.0, 0.0, Quantity_TOC_RGB)

        # Apply highlight
        self.display.Context.SetColor(ais_shape, highlight_color, False)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

        # Store for later restoration
        self.highlighted_parts[part_idx] = (ais_shape, original_color)

        # Update tree item to show highlighted state
        self._update_tree_highlight_indicator(part_idx, True)

        print(f"Highlighted Part {part_idx + 1} ({len(self.highlighted_parts)} selected)")

    def _unhighlight_part(self, part_idx: int):
        """Remove highlight from a specific part."""
        if part_idx not in self.highlighted_parts:
            return

        ais_shape, original_color = self.highlighted_parts[part_idx]

        # Restore original color
        self.display.Context.SetColor(ais_shape, original_color, False)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

        # Remove from tracked highlights
        del self.highlighted_parts[part_idx]

        # Update tree item to remove highlighted state
        self._update_tree_highlight_indicator(part_idx, False)

        print(f"Unhighlighted Part {part_idx + 1} ({len(self.highlighted_parts)} selected)")

    def _clear_all_part_highlights(self):
        """Clear all part highlights."""
        for part_idx in list(self.highlighted_parts.keys()):
            self._unhighlight_part(part_idx)

        # Clear tree selection
        self.ui.parts_tree.selection_remove(self.ui.parts_tree.selection())

    def _update_tree_highlight_indicator(self, part_idx: int, is_highlighted: bool):
        """Update tree item visual indicator for highlighted parts."""
        # Find the tree item for this part
        root_items = self.ui.parts_tree.get_children()
        if not root_items:
            return

        # Get all part items under the root
        root_item = root_items[0]
        part_items = self.ui.parts_tree.get_children(root_item)

        # Find the item with matching part tag
        for item in part_items:
            tags = self.ui.parts_tree.item(item, 'tags')
            if tags and tags[0] == f'part_{part_idx}':
                # Get current item text
                current_text = self.ui.parts_tree.item(item, 'text')

                if is_highlighted:
                    # Add visual indicator (star) if not already present
                    if not current_text.startswith('★ '):
                        new_text = '★ ' + current_text
                        self.ui.parts_tree.item(item, text=new_text)
                        # Make text bold and bright yellow
                        self.ui.parts_tree.tag_configure(f'part_{part_idx}', foreground='#ffff00', font=('Arial', 9, 'bold'))
                else:
                    # Remove visual indicator
                    if current_text.startswith('★ '):
                        new_text = current_text[2:]  # Remove "★ "
                        self.ui.parts_tree.item(item, text=new_text)
                        # Restore original color (need to recalculate from parts_list)
                        if part_idx < len(self.parts_list):
                            _, color, _ = self.parts_list[part_idx]
                            r, g, b = color
                            hex_color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
                            # Check if this part is hidden as duplicate
                            is_hidden = self.deduplication_manager and self.deduplication_manager.is_part_hidden(part_idx)
                            if is_hidden:
                                hex_color = '#666666'
                            self.ui.parts_tree.tag_configure(f'part_{part_idx}', foreground=hex_color, font=('Arial', 9))
                break

    def _restore_tree_highlight_indicators(self):
        """Restore highlight indicators in tree after tree refresh."""
        for part_idx in self.highlighted_parts.keys():
            self._update_tree_highlight_indicator(part_idx, True)

    def _setup_view_buttons(self):
        """Setup view preset button callbacks."""
        view_controller = self.keyboard_controller.view_controller

        self.ui.view_buttons['front'].config(command=lambda: view_controller.set_front_view())
        self.ui.view_buttons['back'].config(command=lambda: view_controller.set_back_view())
        self.ui.view_buttons['right'].config(command=lambda: view_controller.set_right_view())
        self.ui.view_buttons['left'].config(command=lambda: view_controller.set_left_view())
        self.ui.view_buttons['top'].config(command=lambda: view_controller.set_top_view())
        self.ui.view_buttons['bottom'].config(command=lambda: view_controller.set_bottom_view())
        self.ui.view_buttons['isometric'].config(command=lambda: view_controller.set_isometric_view())

    def _setup_plate_controls(self):
        """Setup plate management button callbacks."""
        from tkinter import simpledialog, messagebox

        self.ui.plate_widgets['add'].config(command=self._add_plate)
        self.ui.plate_widgets['delete'].config(command=self._delete_plate)
        self.ui.plate_widgets['rename'].config(command=self._rename_plate)
        self.ui.plate_widgets['arrange'].config(command=self._arrange_parts_on_plates)
        self.ui.plate_widgets['draw_exclusion'].config(command=self._toggle_exclusion_draw_mode)
        self.ui.plate_widgets['clear_exclusions'].config(command=self._clear_exclusion_zones)

        # Initialize plate list display
        self.ui.update_plate_list(self.plate_manager)

        # State for exclusion zone drawing
        self.exclusion_draw_mode = False
        self.exclusion_start_point = None
        self.exclusion_current_plate = None
        self.exclusion_preview_shape = None  # Preview rectangle while dragging

    def _add_plate(self):
        """Add a new plate."""
        from tkinter import simpledialog

        # Ask for plate name
        name = simpledialog.askstring(
            "Add Plate",
            "Enter name for new plate:",
            initialvalue=f"Plate {self.plate_manager.next_plate_id}",
            parent=self.root
        )

        if name:
            plate = self.plate_manager.add_plate(name)
            print(f"Added new plate: {plate.name}")

            # Update UI
            self.ui.update_plate_list(self.plate_manager)

            # If planar alignment is active, update the display
            if self.planar_alignment_manager.is_aligned:
                self.plate_manager.update_all_plates(self.display)
                self.display.Repaint()

        self.canvas.focus_set()

    def _delete_plate(self):
        """Delete the selected plate."""
        from tkinter import messagebox

        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a plate to delete.", parent=self.root)
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        # Confirm deletion
        if messagebox.askyesno(
            "Delete Plate",
            f"Delete '{plate.name}'?\nParts will not be deleted, only disassociated.",
            parent=self.root
        ):
            if self.plate_manager.remove_plate(plate.id):
                print(f"Deleted plate: {plate.name}")

                # Update UI
                self.ui.update_plate_list(self.plate_manager)

                # If planar alignment is active, update the display
                if self.planar_alignment_manager.is_aligned:
                    self.plate_manager.update_all_plates(self.display)
                    self.display.Repaint()
            else:
                messagebox.showwarning(
                    "Cannot Delete",
                    "Cannot delete the last plate.",
                    parent=self.root
                )

        self.canvas.focus_set()

    def _rename_plate(self):
        """Rename the selected plate."""
        from tkinter import simpledialog

        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a plate to rename.", parent=self.root)
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        # Ask for new name
        new_name = simpledialog.askstring(
            "Rename Plate",
            "Enter new name for plate:",
            initialvalue=plate.name,
            parent=self.root
        )

        if new_name and new_name != plate.name:
            if self.plate_manager.rename_plate(plate.id, new_name):
                print(f"Renamed plate '{plate.name}' to '{new_name}'")

                # Update UI
                self.ui.update_plate_list(self.plate_manager)

        self.canvas.focus_set()

    def _arrange_parts_on_plates(self):
        """Arrange parts on plates (placeholder for future logic)."""
        from tkinter import messagebox

        messagebox.showinfo(
            "Arrange Parts",
            "Part arrangement logic is not yet implemented.\n\n"
            "In the future, this will automatically arrange parts on the selected plate "
            "to optimize space usage.",
            parent=self.root
        )

        self.canvas.focus_set()

    def _toggle_exclusion_draw_mode(self):
        """Toggle exclusion zone drawing mode."""
        from tkinter import messagebox

        # Only allow in planar mode
        if not self.planar_alignment_manager.is_aligned:
            messagebox.showinfo(
                "Planar View Required",
                "Please enable planar alignment (press 'P') before drawing exclusion zones.",
                parent=self.root
            )
            self.canvas.focus_set()
            return

        # Check if a plate is selected
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Plate Selected",
                "Please select a plate from the list before drawing exclusion zones.",
                parent=self.root
            )
            self.canvas.focus_set()
            return

        self.exclusion_draw_mode = not self.exclusion_draw_mode

        if self.exclusion_draw_mode:
            # Get selected plate
            plate_idx = selection[0]
            if plate_idx < len(self.plate_manager.plates):
                self.exclusion_current_plate = self.plate_manager.plates[plate_idx]
                self.ui.plate_widgets['draw_exclusion'].config(bg='#ff6600')  # Orange highlight
                print(f"Exclusion draw mode ENABLED for '{self.exclusion_current_plate.name}'")
                print("Click and drag on the plate to draw red exclusion zones")
        else:
            self.ui.plate_widgets['draw_exclusion'].config(bg='#3a3b3f')  # Normal color
            self._clear_exclusion_preview()
            self.exclusion_current_plate = None
            self.exclusion_start_point = None
            print("Exclusion draw mode DISABLED")

        self.canvas.focus_set()

    def _clear_exclusion_zones(self):
        """Clear all exclusion zones from the selected plate."""
        from tkinter import messagebox

        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Plate Selected",
                "Please select a plate to clear exclusion zones from.",
                parent=self.root
            )
            self.canvas.focus_set()
            return

        plate_idx = selection[0]
        if plate_idx >= len(self.plate_manager.plates):
            self.canvas.focus_set()
            return

        plate = self.plate_manager.plates[plate_idx]

        if len(plate.exclusion_zones) == 0:
            messagebox.showinfo(
                "No Exclusion Zones",
                f"Plate '{plate.name}' has no exclusion zones to clear.",
                parent=self.root
            )
            self.canvas.focus_set()
            return

        # Confirm clearing
        if messagebox.askyesno(
            "Clear Exclusion Zones",
            f"Clear all {len(plate.exclusion_zones)} exclusion zone(s) from '{plate.name}'?",
            parent=self.root
        ):
            # Hide the zones from display BEFORE clearing the list
            if self.planar_alignment_manager.is_aligned:
                for zone in plate.exclusion_zones:
                    if zone.ais_shape is not None:
                        self.display.Context.Erase(zone.ais_shape, False)
                        zone.ais_shape = None
                self.display.Context.UpdateCurrentViewer()

            # Now clear the zones from the plate
            plate.clear_exclusion_zones()
            print(f"Cleared all exclusion zones from '{plate.name}'")

        self.canvas.focus_set()

    def _handle_exclusion_zone_click(self, x: float, y: float) -> bool:
        """
        Handle mouse click for exclusion zone drawing.

        Args:
            x: X coordinate in world space
            y: Y coordinate in world space

        Returns:
            True if click was handled, False otherwise
        """
        if not self.exclusion_draw_mode or not self.exclusion_current_plate:
            return False

        # Check if click is within the selected plate
        if not self.exclusion_current_plate.contains_point(x, y):
            print("Click is outside the selected plate")
            return True  # Consume the click but don't start drawing

        # Start drawing exclusion zone
        self.exclusion_start_point = (x, y)
        print(f"Started exclusion zone at ({x:.1f}, {y:.1f})")
        return True

    def _handle_exclusion_zone_drag(self, x: float, y: float) -> bool:
        """
        Handle mouse drag for exclusion zone drawing.

        Args:
            x: X coordinate in world space
            y: Y coordinate in world space

        Returns:
            True if drag was handled, False otherwise
        """
        if not self.exclusion_draw_mode or not self.exclusion_start_point:
            return False

        # Show preview of exclusion zone while dragging
        self._update_exclusion_preview(x, y)
        return True

    def _handle_exclusion_zone_release(self, x: float, y: float) -> bool:
        """
        Handle mouse release for exclusion zone drawing.

        Args:
            x: X coordinate in world space
            y: Y coordinate in world space

        Returns:
            True if release was handled, False otherwise
        """
        if not self.exclusion_draw_mode or not self.exclusion_start_point or not self.exclusion_current_plate:
            return False

        start_x, start_y = self.exclusion_start_point

        # Calculate rectangle dimensions
        x1, x2 = min(start_x, x), max(start_x, x)
        y1, y2 = min(start_y, y), max(start_y, y)
        width = x2 - x1
        height = y2 - y1

        # Only create if rectangle is big enough (at least 5mm)
        if width >= 5.0 and height >= 5.0:
            # Convert to plate-relative coordinates
            plate_x = x1 - self.exclusion_current_plate.x_offset
            plate_y = y1 - self.exclusion_current_plate.y_offset

            # Add exclusion zone
            zone = self.exclusion_current_plate.add_exclusion_zone(plate_x, plate_y, width, height)
            print(f"Created exclusion zone {zone.id} on '{self.exclusion_current_plate.name}': "
                  f"({width:.1f} x {height:.1f} mm)")

            # Update display
            if self.planar_alignment_manager.is_aligned:
                self.plate_manager.update_exclusion_zones(self.exclusion_current_plate.id, self.display)
                self.display.Repaint()
        else:
            print(f"Rectangle too small ({width:.1f} x {height:.1f} mm), minimum is 5x5mm")

        # Clear preview and reset start point for next zone
        self._clear_exclusion_preview()
        self.exclusion_start_point = None
        return True

    def _update_exclusion_preview(self, current_x: float, current_y: float):
        """
        Update the preview rectangle while dragging.

        Args:
            current_x: Current X coordinate in world space
            current_y: Current Y coordinate in world space
        """
        if not self.exclusion_start_point:
            return

        from OCC.Core.gp import gp_Pnt
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
        from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NOM_PLASTIC

        # Clear old preview
        self._clear_exclusion_preview()

        start_x, start_y = self.exclusion_start_point

        # Calculate rectangle bounds
        x1, x2 = min(start_x, current_x), max(start_x, current_x)
        y1, y2 = min(start_y, current_y), max(start_y, current_y)

        # Create preview rectangle at Z=0.2 (above exclusion zones at 0.1)
        z = 0.2
        p1 = gp_Pnt(x1, y1, z)
        p2 = gp_Pnt(x2, y1, z)
        p3 = gp_Pnt(x2, y2, z)
        p4 = gp_Pnt(x1, y2, z)

        # Build the face
        wire_builder = BRepBuilderAPI_MakePolygon()
        wire_builder.Add(p1)
        wire_builder.Add(p2)
        wire_builder.Add(p3)
        wire_builder.Add(p4)
        wire_builder.Close()
        wire = wire_builder.Wire()

        face_builder = BRepBuilderAPI_MakeFace(wire)
        preview_face = face_builder.Face()

        # Create AIS shape with semi-transparent yellow/orange
        self.exclusion_preview_shape = AIS_Shape(preview_face)
        preview_color = Quantity_Color(1.0, 0.6, 0.0, Quantity_TOC_RGB)  # Orange
        self.exclusion_preview_shape.SetColor(preview_color)
        self.exclusion_preview_shape.SetTransparency(0.6)  # More transparent than final zones

        material = Graphic3d_MaterialAspect(Graphic3d_NOM_PLASTIC)
        self.exclusion_preview_shape.SetMaterial(material)

        # Display the preview
        self.display.Context.Display(self.exclusion_preview_shape, False)
        self.display.Context.UpdateCurrentViewer()

    def _clear_exclusion_preview(self):
        """Clear the preview rectangle if it exists."""
        if self.exclusion_preview_shape is not None:
            try:
                self.display.Context.Erase(self.exclusion_preview_shape, False)
                self.display.Context.UpdateCurrentViewer()
            except:
                pass  # Ignore errors if shape was already cleared
            self.exclusion_preview_shape = None

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
        print("  - 'l': Select largest external face per part")
        print("  - 'c': Clear all selections")
        print("  - 'd': Toggle duplicate parts visibility")
        print("  - 'p': Toggle planar alignment (lay parts flat)")
        print("  - '1': Cycle selection fill color (in selection mode)")
        print("  - '2': Cycle outline color (in selection mode)")
        print("  - Explode slider: Separate parts")
        print("\nView Presets (Shift + number keys or click buttons):")
        print("  - Shift+1 (!): Front view")
        print("  - Shift+2 (@): Back view")
        print("  - Shift+3 (#): Right view")
        print("  - Shift+4 ($): Left view")
        print("  - Shift+5 (%): Top view")
        print("  - Shift+6 (^): Bottom view")
        print("  - Shift+7 (&): Isometric view")
        print("\nPlate Management:")
        print("  - Add Plate: Create a new material plate")
        print("  - Delete Plate: Remove selected plate (parts remain)")
        print("  - Rename Plate: Give plates descriptive names")
        print("  - Arrange Parts: Placeholder for auto-arrangement (future)")
        print("  - Draw Exclusion: Click & drag to mark off-limits areas (red zones)")
        print("  - Clear All: Remove all exclusion zones from selected plate")
        print("  - Parts are auto-assigned to plates when planar view is enabled")
        print("\nOther:")
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

    def toggle_duplicate_visibility(self):
        """Toggle visibility of duplicate parts."""
        show_duplicates = self.deduplication_manager.toggle_duplicates()

        if show_duplicates:
            # Clear hidden indices when showing all parts
            self.deduplication_manager.hidden_indices.clear()

            # Show all parts
            for solid, color, ais_shape in self.parts_list:
                self.display.Context.Display(ais_shape, False)
            print("Showing all parts (including duplicates)")

            # Restore hidden selections
            if self.hidden_selections:
                self.selection_manager.restore_hidden_selections(self.hidden_selections, self.root)
                self.hidden_selections = {}

            # Update parts tree to remove hidden indicators
            self.ui.update_parts_tree(self.parts_list, self.deduplication_manager)

            # Restore highlight indicators in the refreshed tree
            self._restore_tree_highlight_indicators()
        else:
            # Hide duplicate parts
            unique_parts, duplicate_groups = self.deduplication_manager.get_unique_parts(self.parts_list)

            # Collect AIS shapes that will be hidden
            hidden_indices = self.deduplication_manager.hidden_indices
            ais_shapes_to_hide = [self.parts_list[i][2] for i in hidden_indices]

            # Hide selections for parts that are about to be hidden
            self.hidden_selections = self.selection_manager.hide_selections_for_parts(
                ais_shapes_to_hide, self.root
            )

            # Hide all parts first
            for solid, color, ais_shape in self.parts_list:
                self.display.Context.Erase(ais_shape, False)

            # Show only unique parts
            for solid, color, ais_shape in unique_parts:
                self.display.Context.Display(ais_shape, False)

            print("Showing only unique parts (duplicates hidden)")

            # Update parts tree to show hidden status
            self.ui.update_parts_tree(self.parts_list, self.deduplication_manager)

            # Restore highlight indicators in the refreshed tree
            self._restore_tree_highlight_indicators()

        # Re-apply explosion if active
        if self.explode_manager.get_explosion_factor() > 0:
            # Get visible parts for explosion
            if show_duplicates:
                visible_parts = self.parts_list
            else:
                visible_parts, _ = self.deduplication_manager.get_unique_parts(self.parts_list)

            self.explode_manager.initialize_parts(visible_parts)
            self.explode_manager.set_explosion_factor(
                self.explode_manager.get_explosion_factor(),
                self.display,
                self.root
            )

        # Update display
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        self.root.update_idletasks()

    def toggle_planar_alignment(self):
        """Toggle planar alignment to lay parts flat."""
        # Reset explosion first if we're enabling planar alignment
        if not self.planar_alignment_manager.is_aligned:
            if self.explode_manager.get_explosion_factor() > 0:
                # Fully reset explosion and ensure display is updated
                self.explode_manager.set_explosion_factor(0.0, self.display, self.root)
                self.ui.explode_slider.set(0.0)
                self.ui.explode_label.config(text="Explode: 0.00")
                # Force display update before applying planar alignment
                self.display.Context.UpdateCurrentViewer()
                self.display.Repaint()
                self.root.update_idletasks()
            # Disable explode slider when planar alignment is active
            self.ui.explode_slider.config(state='disabled')
        else:
            # Re-enable explode slider when disabling planar alignment
            self.ui.explode_slider.config(state='normal')

        is_aligned = self.planar_alignment_manager.toggle_planar_alignment(self.display, self.root)

        # Update face highlight transformations to match their parent parts
        self.selection_manager.update_face_transformations()

        if is_aligned:
            # Associate parts with plates based on their positions
            self.plate_manager.associate_parts_by_position(self.parts_list, self.display)

            # Update plate list UI
            self.ui.update_plate_list(self.plate_manager)

            print("Planar alignment enabled - parts laid flat")
            print(f"Parts automatically associated with {self.plate_manager.get_plate_count()} plate(s)")
        else:
            print("Planar alignment disabled - parts restored")

    def toggle_origin(self):
        """Reset assembly origin or set it manually (future: click to set)."""
        if not hasattr(self, 'parts_list') or not self.parts_list:
            print("No model loaded. Load a STEP file first.")
            return

        if self.selection_manager.assembly_origin is None:
            print("Origin control: Currently using automatic assembly center.")
            print("Future feature: Click-to-set manual origin point.")
            print("For now, the assembly center is calculated automatically during face selection.")
        else:
            # Reset manual origin
            self.selection_manager.reset_assembly_origin()
            print("Manual origin reset. Now using automatic assembly center.")

    def select_largest_faces(self):
        """Select the largest external face of each part."""
        # Get the visible parts list (respecting duplicate hiding)
        if not self.deduplication_manager.show_duplicates:
            visible_parts, _ = self.deduplication_manager.get_unique_parts(self.parts_list)
        else:
            visible_parts = self.parts_list

        self.selection_manager.select_largest_external_faces(visible_parts, self.root)
