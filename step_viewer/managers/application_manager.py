from typing import Optional, Tuple
import tkinter as tk

from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir, gp_Lin
from OCC.Core.IntAna import IntAna_IntConicQuad

from ..config import ViewerConfig
from . import (
    ColorManager,
    SelectionManager,
    ExplodeManager,
    DeduplicationManager,
    PlanarAlignmentManager,
    PlateManager,
    EventManager,
    UIManager,
    CanvasManager,
)
from .plate_arrangement_manager import PlateArrangementManager
from .part_manager import PartManager
from .units_manager import UnitsManager, UnitSystem
from .log_manager import logger
from ..controllers import (
    MouseController,
    KeyboardController,
    TreeController,
    ExclusionZoneController,
    PlateController,
    FeatureController,
)
from ..loaders import StepLoader


class ApplicationManager:
    """Main coordinator class for the STEP viewer application."""

    def __init__(self, filename: str, config: Optional[ViewerConfig] = None):
        self.filename = filename
        self.config = config or ViewerConfig()
        self.root = tk.Tk()
        self.ui = UIManager(self.root, self.config)
        self.shape = None
        self.display = None
        self.display_manager = None
        self.tree_controller = None
        self.exclusion_zone_controller = None
        self.part_manager = None
        self.plate_controller = None
        self.plate_arrangement_manager = None
        self.planar_alignment_manager = None
        self.event_manager = None
        self.feature_controller = None
        self.explode_manager = None

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

        # Initialize display manager
        self.display_manager = CanvasManager(self.root, self.config)
        self.display = self.display_manager.init_display(right_panel)
        self.canvas = self.display_manager.canvas
        self.view = self.display_manager.display.View

        # Setup managers and controllers
        self._setup_managers_controllers()

        # Display the model and migrate parts into the central PartManager
        parts = self.display_manager.display_model(
            self.shape, self.explode_manager, self.planar_alignment_manager
        )
        self.part_manager.set_parts(parts)

        # Reinitialize managers that depend on parts data now that parts are loaded
        self.explode_manager.initialize_parts()
        self.planar_alignment_manager.initialize_parts()

        # Register base colors for all parts in the selection manager
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

        for part in self.part_manager.get_parts():
            color = Quantity_Color(
                part.pallete[0], part.pallete[1], part.pallete[2], Quantity_TOC_RGB
            )
            self.selection_manager.register_part_base_color(
                part.ais_colored_shape, color
            )

        # Configure display settings and populate UI from the PartManager
        self.display_manager.configure_display(
            self.part_manager.get_parts(), self.color_manager
        )
        self.ui.populate_parts_tree(self.part_manager.get_parts())

        # Setup UI controllers
        self._setup_ui_controllers()

        # Setup explode slider callback
        self._setup_explode_slider()

        # Setup view buttons
        self._setup_view_buttons()

        # Bind events
        self._bind_events()

        # Setup resize handler
        self.display_manager.setup_resize_handler()

        # Final setup
        self.root.after(150, self.display_manager.final_update)
        self.root.mainloop()

    def _setup_managers_controllers(self):
        """Setup all core controllers and managers."""
        # Initialize managers
        self.color_manager = ColorManager(self.config)

        # Initialize units manager with configured default unit system
        default_unit = (
            UnitSystem.METRIC
            if self.config.DEFAULT_UNIT_SYSTEM == "mm"
            else UnitSystem.IMPERIAL
        )
        self.units_manager = UnitsManager(default_unit)

        self.part_manager = PartManager()
        self.plate_manager = PlateManager(
            self.config.SHEET_WIDTH_MM, self.config.SHEET_HEIGHT_MM
        )
        self.planar_alignment_manager = PlanarAlignmentManager(
            self.part_manager, self.plate_manager
        )
        self.selection_manager = SelectionManager(
            self.display,
            self.color_manager,
            self.part_manager,
            self.planar_alignment_manager,
            self.config,
        )
        self.selection_manager.set_selection_label(self.ui.selection_label)
        self.explode_manager = ExplodeManager(self.part_manager, self.selection_manager)
        self.deduplication_manager = DeduplicationManager()
        self.plate_arrangement_manager = PlateArrangementManager(self.plate_manager)

        # Initialize controllers
        self.mouse_controller = MouseController(
            self.view,
            self.display,
            self.part_manager,
            self.selection_manager,
            self.root,
        )
        self.keyboard_controller = KeyboardController(
            self.display,
            self.selection_manager,
            self.color_manager,
            self.root,
            self.config,
        )
        self.keyboard_controller.set_ui_labels(
            self.ui.mode_label, self.ui.selection_label
        )

    def _setup_ui_controllers(self):
        """Setup UI-specific controllers."""
        self.tree_controller = TreeController(
            self.ui,
            self.canvas,
            self.display,
            self.part_manager,
            self.deduplication_manager,
        )
        self.tree_controller.setup_tree_selection()

        # Feature controller for toggles
        self.feature_controller = FeatureController(
            self.root,
            self.display,
            self.ui,
            self.part_manager,
            self.deduplication_manager,
            self.explode_manager,
            self.planar_alignment_manager,
            self.plate_manager,
            self.selection_manager,
            self.tree_controller,
        )

        # Plate controller
        self.plate_controller = PlateController(
            self.root,
            self.canvas,
            self.display,
            self.ui,
            self.plate_manager,
            self.plate_manager,
            self.planar_alignment_manager,
            self.plate_arrangement_manager,
            self.selection_manager,
            self.units_manager,
        )
        self.plate_controller.set_parts_list(self.part_manager)
        self.plate_controller.setup_controls()

        # Exclusion zone controller
        self.exclusion_zone_controller = ExclusionZoneController(
            self.root,
            self.canvas,
            self.display,
            self.ui,
            self.plate_manager,
            self.planar_alignment_manager,
        )
        self.exclusion_zone_controller.setup_controls()

    def _bind_events(self):
        """Bind mouse and keyboard events."""
        self.event_manager = EventManager(
            self.root,
            self.canvas,
            self.mouse_controller,
            self.keyboard_controller,
            self.exclusion_zone_controller,
            self._get_world_coordinates,
        )
        self.event_manager.bind_events(
            self.feature_controller.toggle_duplicate_visibility,
            self.feature_controller.toggle_planar_alignment,
            self.feature_controller.select_largest_faces,
        )

    def _get_world_coordinates(
        self, screen_x: int, screen_y: int
    ) -> Tuple[float, float, float]:
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
            logger.warning(f"Could not convert screen coordinates: {e}")
            return (0.0, 0.0, 0.0)

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

    def _setup_view_buttons(self):
        """Setup view preset button callbacks."""
        view_controller = self.keyboard_controller.view_helper

        self.ui.view_buttons["front"].config(
            command=lambda: view_controller.set_front_view()
        )
        self.ui.view_buttons["back"].config(
            command=lambda: view_controller.set_back_view()
        )
        self.ui.view_buttons["right"].config(
            command=lambda: view_controller.set_right_view()
        )
        self.ui.view_buttons["left"].config(
            command=lambda: view_controller.set_left_view()
        )
        self.ui.view_buttons["top"].config(
            command=lambda: view_controller.set_top_view()
        )
        self.ui.view_buttons["bottom"].config(
            command=lambda: view_controller.set_bottom_view()
        )
        self.ui.view_buttons["isometric"].config(
            command=lambda: view_controller.set_isometric_view()
        )
