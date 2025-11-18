"""
Display manager for initializing and configuring the 3D display.
"""

import tkinter as tk
import random
from typing import List, Tuple, Any
from .part_manager import Part

from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_TOC_sRGB
from OCC.Core.Aspect import Aspect_GFM_VER, Aspect_TypeOfLine, Aspect_TOTP_RIGHT_LOWER
from OCC.Core.AIS import AIS_ColoredShape

from ..config import ViewerConfig
from ..loaders import StepLoader
from .log_manager import logger


class CanvasManager:
    """Manages 3D display initialization, configuration, and model rendering."""

    def __init__(self, root: tk.Tk, config: ViewerConfig):
        self.root = root
        self.config = config
        self.display = None
        self.canvas = None
        self.resize_state = {"pending": False, "initialized": False}

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
        self.canvas.configure(
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            bg=self.config.DARK_BG,
            width=0,
            height=0,
        )

        self.root.update_idletasks()
        self.display = self.canvas._display

        return self.display

    def display_model(
        self, shape, explode_manager, planar_alignment_manager
    ) -> List[Tuple]:
        """
        Display the loaded model with colored parts using AIS_ColoredShape.

        Args:
            shape: The STEP shape to display
            explode_manager: Manager for explosion effects
            planar_alignment_manager: Manager for planar alignment

        Returns:
            List of Part namedtuples
        """
        from ..controllers.material_renderer import MaterialRenderer

        solids = StepLoader.extract_solids(shape)
        palette = self.config.PART_PALETTE.copy()
        parts_list: List[Part] = []

        if len(solids) == 0:
            logger.info("No individual solids found, displaying shape as single object")
            color = Quantity_Color(
                palette[0][0], palette[0][1], palette[0][2], Quantity_TOC_RGB
            )
            # Create AIS_ColoredShape instead of AIS_Shape
            ais_colored_shape = AIS_ColoredShape(shape)
            ais_colored_shape.SetColor(color)
            ais_colored_shape.SetTransparency(0.0)
            ais_colored_shape.SetDisplayMode(1)
            self.display.Context.Display(ais_colored_shape, False)
            MaterialRenderer.apply_matte_material(ais_colored_shape, color)
            parts_list.append(
                Part(
                shape=shape,
                pallete=palette[0],
                ais_colored_shape=ais_colored_shape)
                )
        else:
            random.shuffle(palette)
            for i, solid in enumerate(solids):
                r, g, b = palette[i % len(palette)]
                color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
                # Create AIS_ColoredShape instead of AIS_Shape
                ais_colored_shape = AIS_ColoredShape(solid)
                ais_colored_shape.SetColor(color)
                ais_colored_shape.SetTransparency(0.0)
                ais_colored_shape.SetDisplayMode(1)
                self.display.Context.Display(ais_colored_shape, False)
                MaterialRenderer.apply_matte_material(ais_colored_shape, color)
                parts_list.append(
                    Part(
                        shape=solid,
                        pallete=(r, g, b),
                        ais_colored_shape=ais_colored_shape))

            logger.info(f"Assigned colors to {len(solids)} solid(s)")

        self.display.Context.UpdateCurrentViewer()
        self.display.FitAll()
        self.display.Repaint()

        return parts_list

    def configure_display(self, parts_list: List[Part], color_manager):
        """
        Configure display settings (background, antialiasing, selection).

        Args:
            parts_list: List of Part namedtuples
            color_manager: Manager for color configuration
        """
        # Background color
        bg_color = Quantity_Color(
            self.config.BACKGROUND_COLOR[0],
            self.config.BACKGROUND_COLOR[1],
            self.config.BACKGROUND_COLOR[2],
            Quantity_TOC_sRGB,
        )
        self.display.View.SetBgGradientStyle(Aspect_GFM_VER)
        self.display.View.SetBgGradientColors(bg_color, bg_color)
        self.display.View.SetBackgroundColor(bg_color)

        # Antialiasing
        render_params = self.display.View.ChangeRenderingParams()
        render_params.IsAntialiasingEnabled = True
        render_params.NbMsaaSamples = self.config.MSAA_SAMPLES
        render_params.AddLights = False
        render_params.Shading = False

        # xyz widget
        self.display.View.TriedronDisplay(
            Aspect_TOTP_RIGHT_LOWER,
            Quantity_Color(1.0, 1.0, 1.0, Quantity_TOC_RGB),
            0.1,
            True,
        )

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
            select_drawer.FaceBoundaryAspect().SetWidth(
                self.config.SELECTION_OUTLINE_WIDTH
            )
            select_drawer.FaceBoundaryAspect().SetTypeOfLine(
                Aspect_TypeOfLine.Aspect_TOL_SOLID
            )

            logger.info("Context-level selection styling applied successfully")
        except Exception as e:
            logger.warning(f"Could not configure selection style: {e}")

        # Enable face selection for all parts
        for part in parts_list:
            self.display.Context.Activate(part.ais_colored_shape, 4, False)  # 4 = TopAbs_FACE
            part.ais_colored_shape.SetHilightMode(1)

    def setup_resize_handler(self):
        """Setup resize event handler with debouncing."""

        def on_resize(event):
            if not self.resize_state["initialized"]:
                return

            if not self.resize_state["pending"]:
                self.resize_state["pending"] = True

                def do_resize():
                    try:
                        self.display.View.MustBeResized()
                        self.display.View.Redraw()
                    except Exception as e:
                        logger.warning(f"Could not resize view: {e}")
                    finally:
                        self.resize_state["pending"] = False

                self.root.after(10, do_resize)

        self.canvas.bind("<Configure>", on_resize)

    def final_update(self):
        """Final update after UI is fully initialized."""
        try:
            self.display.View.MustBeResized()
            self.display.Context.UpdateCurrentViewer()
            self.display.FitAll()
            self.display.Repaint()
            self.resize_state["initialized"] = True
        except Exception as e:
            logger.warning(f"Could not perform final update: {e}")
