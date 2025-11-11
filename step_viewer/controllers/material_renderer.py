"""
Material rendering for CAD shapes.
"""

from typing import Optional
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NameOfMaterial


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
