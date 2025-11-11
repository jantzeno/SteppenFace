"""
Exclusion zone controller for drawing and managing exclusion zones on plates.
"""

import tkinter as tk
from typing import Optional, Tuple
from tkinter import messagebox
from OCC.Core.gp import gp_Pnt
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
from OCC.Core.AIS import AIS_Shape
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NOM_PLASTIC
from ..managers.log_manager import logger


class ExclusionZoneController:
    """Manages exclusion zone drawing and interaction."""

    def __init__(
        self, root: tk.Tk, canvas, display, ui, plate_manager, planar_alignment_manager
    ):
        self.root = root
        self.canvas = canvas
        self.display = display
        self.ui = ui
        self.plate_manager = plate_manager
        self.planar_alignment_manager = planar_alignment_manager

        # State for exclusion zone drawing
        self.exclusion_draw_mode = False
        self.exclusion_start_point: Optional[Tuple[float, float]] = None
        self.exclusion_current_plate = None
        self.exclusion_preview_shape = None  # Preview rectangle while dragging

    def setup_controls(self):
        """Setup exclusion zone control button callbacks."""
        self.ui.plate_widgets["draw_exclusion"].config(
            command=self.toggle_exclusion_draw_mode
        )
        self.ui.plate_widgets["clear_exclusions"].config(
            command=self.clear_exclusion_zones
        )

    def toggle_exclusion_draw_mode(self):
        """Toggle exclusion zone drawing mode."""
        # Only allow in planar mode
        if not self.planar_alignment_manager.is_aligned:
            messagebox.showinfo(
                "Planar View Required",
                "Please enable planar alignment (press 'P') before drawing exclusion zones.",
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        # Check if a plate is selected
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Plate Selected",
                "Please select a plate from the list before drawing exclusion zones.",
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        self.exclusion_draw_mode = not self.exclusion_draw_mode

        if self.exclusion_draw_mode:
            # Get selected plate
            plate_idx = selection[0]
            if plate_idx < len(self.plate_manager.plates):
                self.exclusion_current_plate = self.plate_manager.plates[plate_idx]
                self.ui.plate_widgets["draw_exclusion"].config(
                    bg="#ff6600"
                )  # Orange highlight
                logger.info(
                    f"Exclusion draw mode ENABLED for '{self.exclusion_current_plate.name}'"
                )
                logger.info("Click and drag on the plate to draw red exclusion zones")
        else:
            self.ui.plate_widgets["draw_exclusion"].config(bg="#3a3b3f")  # Normal color
            self.clear_exclusion_preview()
            self.exclusion_current_plate = None
            self.exclusion_start_point = None
            logger.info("Exclusion draw mode DISABLED")

        self.canvas.focus_set()

    def clear_exclusion_zones(self):
        """Clear all exclusion zones from the selected plate."""
        # Get selected plate
        selection = self.ui.plate_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Plate Selected",
                "Please select a plate to clear exclusion zones from.",
                parent=self.root,
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
                parent=self.root,
            )
            self.canvas.focus_set()
            return

        # Confirm clearing
        if messagebox.askyesno(
            "Clear Exclusion Zones",
            f"Clear all {len(plate.exclusion_zones)} exclusion zone(s) from '{plate.name}'?",
            parent=self.root,
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
            logger.info(f"Cleared all exclusion zones from '{plate.name}'")

        self.canvas.focus_set()

    def handle_click(self, x: float, y: float) -> bool:
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
            logger.warning("Click is outside the selected plate")
            return True  # Consume the click but don't start drawing

        # Start drawing exclusion zone
        self.exclusion_start_point = (x, y)
        logger.info(f"Started exclusion zone at ({x:.1f}, {y:.1f})")
        return True

    def handle_drag(self, x: float, y: float) -> bool:
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
        self.update_exclusion_preview(x, y)
        return True

    def handle_release(self, x: float, y: float) -> bool:
        """
        Handle mouse release for exclusion zone drawing.

        Args:
            x: X coordinate in world space
            y: Y coordinate in world space

        Returns:
            True if release was handled, False otherwise
        """
        if (
            not self.exclusion_draw_mode
            or not self.exclusion_start_point
            or not self.exclusion_current_plate
        ):
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
            zone = self.exclusion_current_plate.add_exclusion_zone(
                plate_x, plate_y, width, height
            )
            logger.info(
                f"Created exclusion zone {zone.id} on '{self.exclusion_current_plate.name}': "
                f"({width:.1f} x {height:.1f} mm)"
            )

            # Update display
            if self.planar_alignment_manager.is_aligned:
                self.plate_manager.update_exclusion_zones(
                    self.exclusion_current_plate.id, self.display
                )
                self.display.Repaint()
        else:
            logger.warning(
                f"Rectangle too small ({width:.1f} x {height:.1f} mm), minimum is 5x5mm"
            )

        # Clear preview and reset start point for next zone
        self.clear_exclusion_preview()
        self.exclusion_start_point = None
        return True

    def update_exclusion_preview(self, current_x: float, current_y: float):
        """
        Update the preview rectangle while dragging.

        Args:
            current_x: Current X coordinate in world space
            current_y: Current Y coordinate in world space
        """
        if not self.exclusion_start_point:
            return

        # Clear old preview
        self.clear_exclusion_preview()

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
        self.exclusion_preview_shape.SetTransparency(
            0.6
        )  # More transparent than final zones

        material = Graphic3d_MaterialAspect(Graphic3d_NOM_PLASTIC)
        self.exclusion_preview_shape.SetMaterial(material)

        # Display the preview
        self.display.Context.Display(self.exclusion_preview_shape, False)
        self.display.Context.UpdateCurrentViewer()

    def clear_exclusion_preview(self):
        """Clear the preview rectangle if it exists."""
        if self.exclusion_preview_shape is not None:
            try:
                self.display.Context.Erase(self.exclusion_preview_shape, False)
                self.display.Context.UpdateCurrentViewer()
            except:
                pass  # Ignore errors if shape was already cleared
            self.exclusion_preview_shape = None
