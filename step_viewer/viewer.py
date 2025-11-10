"""
Main STEP viewer application.
"""

import random
from typing import Optional
import tkinter as tk

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_TOC_sRGB
from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine, Aspect_TOTP_RIGHT_LOWER

from .config import ViewerConfig
from .managers import ColorManager, SelectionManager, ExplodeManager, DeduplicationManager, PlanarAlignmentManager
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

        # Setup explode slider callback
        self._setup_explode_slider()

        # Setup view buttons
        self._setup_view_buttons()

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
        self.planar_alignment_manager = PlanarAlignmentManager()

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
        self.canvas.bind("<d>", lambda e: self.toggle_duplicate_visibility())
        self.canvas.bind("<D>", lambda e: self.toggle_duplicate_visibility())
        self.canvas.bind("<p>", lambda e: self.toggle_planar_alignment())
        self.canvas.bind("<P>", lambda e: self.toggle_planar_alignment())

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

        if is_aligned:
            print("Planar alignment enabled - parts laid flat")
        else:
            print("Planar alignment disabled - parts restored")

        # Update face highlight transformations if any faces are selected
        if self.selection_manager.get_selection_count() > 0:
            self.selection_manager.update_all_transformations(self.root)
