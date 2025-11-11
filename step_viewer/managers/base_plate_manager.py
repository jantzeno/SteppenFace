"""
Base plate manager for visualizing the material sheet in planar view.
"""

from typing import Optional

from OCC.Core.gp import gp_Pnt
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NOM_PLASTIC
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.AIS import AIS_Shape


class BasePlateManager:
    """Manages the base plate/platter visualization for planar view."""

    def __init__(self, width_mm: float, height_mm: float):
        """
        Initialize base plate manager.

        Args:
            width_mm: Width of the base plate in mm
            height_mm: Height of the base plate in mm
        """
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.base_plate_ais: Optional[AIS_Shape] = None
        self.is_visible = False

    def set_size(self, width_mm: float, height_mm: float):
        """
        Update the base plate size.

        Args:
            width_mm: Width of the base plate in mm
            height_mm: Height of the base plate in mm
        """
        self.width_mm = width_mm
        self.height_mm = height_mm
        # If base plate is currently shown, it needs to be recreated
        if self.is_visible and self.base_plate_ais is not None:
            # Will need to recreate on next show
            self.base_plate_ais = None

    def show(self, display):
        """
        Show the base plate in the display.

        Args:
            display: The OCC display context
        """
        if self.base_plate_ais is None:
            self._create_base_plate()

        if self.base_plate_ais is not None:
            display.Context.Display(self.base_plate_ais, True)
            self.is_visible = True

    def hide(self, display):
        """
        Hide the base plate from the display.

        Args:
            display: The OCC display context
        """
        if self.base_plate_ais is not None:
            display.Context.Erase(self.base_plate_ais, True)
            self.is_visible = False

    def _create_base_plate(self):
        """Create the base plate geometry and AIS object."""
        # Create a rectangular face at Z=0
        p1 = gp_Pnt(0, 0, 0)
        p2 = gp_Pnt(self.width_mm, 0, 0)
        p3 = gp_Pnt(self.width_mm, self.height_mm, 0)
        p4 = gp_Pnt(0, self.height_mm, 0)

        # Create the base plate face using a polygon wire
        wire_builder = BRepBuilderAPI_MakePolygon()
        wire_builder.Add(p1)
        wire_builder.Add(p2)
        wire_builder.Add(p3)
        wire_builder.Add(p4)
        wire_builder.Close()
        wire = wire_builder.Wire()

        face_builder = BRepBuilderAPI_MakeFace(wire)
        base_plate_face = face_builder.Face()

        # Create AIS_Shape for visualization
        self.base_plate_ais = AIS_Shape(base_plate_face)

        # Style the base plate - semi-transparent gray
        base_color = Quantity_Color(0.3, 0.3, 0.3, Quantity_TOC_RGB)
        self.base_plate_ais.SetColor(base_color)
        self.base_plate_ais.SetTransparency(0.7)  # Semi-transparent

        # Set material to make it look like a flat surface
        material = Graphic3d_MaterialAspect(Graphic3d_NOM_PLASTIC)
        self.base_plate_ais.SetMaterial(material)

    def is_plate_visible(self) -> bool:
        """Check if the base plate is currently visible."""
        return self.is_visible
