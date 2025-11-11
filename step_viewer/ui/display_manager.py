"""
Display manager for initializing and configuring the 3D display.
"""

import tkinter as tk
import random
from typing import List, Tuple, Any

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_TOC_sRGB
from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine, Aspect_TOTP_RIGHT_LOWER

from ..config import ViewerConfig
from ..loaders import StepLoader
from .material_renderer import MaterialRenderer
from ..managers.log_manager import logger


class DisplayManager:
    """Manages 3D display initialization, configuration, and model rendering."""

    def __init__(self, root: tk.Tk, config: ViewerConfig):
        self.root = root
        self.config = config
        self.display = None
        self.canvas = None
        self.view = None
        self.resize_state = {'pending': False, 'initialized': False}

    def init_display(self, parent) -> Any:
        """
        Initialize the 3D display canvas.

        Args:
            parent: Parent widget for the canvas

        Returns:
            The display object
        """
        from OCC.Display.tkDisplay import tkViewer3d

        self.canvas = tkViewer3d(parent)
        self.canvas.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.canvas.configure(borderwidth=0, highlightthickness=0, relief='flat',
                        bg=self.config.DARK_BG, width=0, height=0)

        self.root.update_idletasks()
        self.display = self.canvas._display
        self.view = self.display.View

        return self.display

    def display_model(self, shape, explode_manager, planar_alignment_manager) -> List[Tuple]:
        """
        Display the loaded model with colored parts.

        Args:
            shape: The STEP shape to display
            explode_manager: Manager for explosion effects
            planar_alignment_manager: Manager for planar alignment

        Returns:
            List of (solid, color_tuple, ais_shape) tuples
        """
        solids = StepLoader.extract_solids(shape)
        palette = self.config.PART_PALETTE.copy()
        parts_list = []

        if len(solids) == 0:
            logger.info("No individual solids found, displaying shape as single object")
            color = Quantity_Color(palette[0][0], palette[0][1], palette[0][2], Quantity_TOC_RGB)
            ais_shape = self.display.DisplayShape(shape, color=color, update=False)[0]
            MaterialRenderer.apply_matte_material(ais_shape, color)
            parts_list.append((shape, palette[0], ais_shape))
        else:
            random.shuffle(palette)
            for i, solid in enumerate(solids):
                r, g, b = palette[i % len(palette)]
                color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
                ais_shape = self.display.DisplayShape(solid, color=color, update=False)[0]
                MaterialRenderer.apply_matte_material(ais_shape, color)
                parts_list.append((solid, (r, g, b), ais_shape))

            logger.info(f"Assigned colors to {len(solids)} solid(s)")

        self.display.Context.UpdateCurrentViewer()
        self.display.FitAll()
        self.display.Repaint()

        # Initialize managers with parts
        explode_manager.initialize_parts(parts_list)
        planar_alignment_manager.initialize_parts(parts_list)

        return parts_list

    def configure_display(self, parts_list: List[Tuple], color_manager):
        """
        Configure display settings (background, antialiasing, selection).

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            color_manager: Manager for color configuration
        """
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
        logger.info(f"\nApplying selection colors:")
        logger.info(f"  Fill: RGB{self.config.SELECTION_COLOR}")
        logger.info(f"  Outline: RGB{self.config.SELECTION_OUTLINE_COLOR}")
        logger.info(f"  Width: {self.config.SELECTION_OUTLINE_WIDTH}px\n")

        # Configure hover (disabled) and selection styles
        try:
            hover_drawer = self.display.Context.HighlightStyle()
            hover_drawer.SetTransparency(1.0)  # Invisible
            hover_drawer.SetFaceBoundaryDraw(False)

            select_color = color_manager.get_fill_quantity_color()
            outline_color = color_manager.get_outline_quantity_color()

            select_drawer = self.display.Context.SelectionStyle()
            select_drawer.SetColor(select_color)
            select_drawer.SetDisplayMode(1)
            select_drawer.SetTransparency(self.config.SELECTION_TRANSPARENCY)
            select_drawer.SetFaceBoundaryDraw(True)
            select_drawer.FaceBoundaryAspect().SetColor(outline_color)
            select_drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
            select_drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

            logger.info("Context-level selection styling applied successfully")
        except Exception as e:
            logger.warning(f"Could not configure selection style: {e}")

        # Enable face selection for all parts
        for solid, color, ais_shape in parts_list:
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
            logger.info("XYZ axis widget added to view")
        except Exception as e:
            logger.warning(f"Could not add XYZ axis widget: {e}")

    def setup_resize_handler(self):
        """Setup resize event handler with debouncing."""
        def on_resize(event):
            if not self.resize_state['initialized']:
                return

            if not self.resize_state['pending']:
                self.resize_state['pending'] = True

                def do_resize():
                    try:
                        self.display.View.MustBeResized()
                        self.display.View.Redraw()
                    except Exception as e:
                        logger.warning(f"Could not resize view: {e}")
                    finally:
                        self.resize_state['pending'] = False

                self.root.after(10, do_resize)

        self.canvas.bind('<Configure>', on_resize)

    def final_update(self):
        """Final update after UI is fully initialized."""
        try:
            self.display.View.MustBeResized()
            self.display.Context.UpdateCurrentViewer()
            self.display.FitAll()
            self.display.Repaint()
            self.resize_state['initialized'] = True
        except Exception as e:
            logger.warning(f"Could not perform final update: {e}")

    def print_controls(self):
        """Print viewer controls to console."""
        logger.info("\n" + "="*60)
        logger.info("SELECTION COLORS CONFIGURATION:")
        logger.info(f"  Fill: RGB{self.config.SELECTION_COLOR}")
        logger.info(f"  Outline: RGB{self.config.SELECTION_OUTLINE_COLOR}")
        logger.info(f"  Outline width: {self.config.SELECTION_OUTLINE_WIDTH}px")
        logger.info("  (Edit ViewerConfig class to customize)")
        logger.info("="*60)

        logger.info("\nViewer Controls:")
        logger.info("  - Left mouse button: Rotate")
        logger.info("  - Right mouse button: Pan")
        logger.info("  - Mouse wheel: Zoom")
        logger.info("  - 'f': Fit all")
        logger.info("  - 's': Toggle face selection mode")
        logger.info("  - 'l': Select largest external face per part")
        logger.info("  - 'c': Clear all selections")
        logger.info("  - 'd': Toggle duplicate parts visibility")
        logger.info("  - 'p': Toggle planar alignment (lay parts flat)")
        logger.info("  - '1': Cycle selection fill color (in selection mode)")
        logger.info("  - '2': Cycle outline color (in selection mode)")
        logger.info("\nView Presets (Shift + number keys):")
        logger.info("  - Shift+1 (!): Front view")
        logger.info("  - Shift+2 (@): Back view")
        logger.info("  - Shift+3 (#): Right view")
        logger.info("  - Shift+4 ($): Left view")
        logger.info("  - Shift+5 (%): Top view")
        logger.info("  - Shift+6 (^): Bottom view")
        logger.info("  - Shift+7 (&): Isometric view")
        logger.info("\nOther:")
        logger.info("  - 'q' or ESC: Quit")
