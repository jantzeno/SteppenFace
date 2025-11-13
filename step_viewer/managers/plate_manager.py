"""
Plate manager for handling multiple material plates/sheets with part associations.
"""

from typing import Optional, List, Tuple, Set
from dataclasses import dataclass, field
import math

from OCC.Core.gp import gp_Pnt
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
from OCC.Core.Graphic3d import Graphic3d_MaterialAspect, Graphic3d_NOM_PLASTIC
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCC.Core.AIS import AIS_Shape
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib


@dataclass
class ExclusionZone:
    """Represents a rectangular exclusion zone on a plate where parts cannot be placed."""

    id: int
    x: float  # X position relative to plate origin
    y: float  # Y position relative to plate origin
    width: float
    height: float
    ais_shape: Optional[AIS_Shape] = None  # Visual representation

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get the bounds of the exclusion zone (xmin, ymin, xmax, ymax)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a 2D point is within the exclusion zone."""
        xmin, ymin, xmax, ymax = self.get_bounds()
        return xmin <= x <= xmax and ymin <= y <= ymax

    def overlaps_rect(self, x: float, y: float, width: float, height: float) -> bool:
        """Check if a rectangle overlaps with this exclusion zone."""
        # Rectangle A: exclusion zone
        ax1, ay1, ax2, ay2 = self.get_bounds()
        # Rectangle B: input rectangle
        bx1, by1, bx2, by2 = x, y, x + width, y + height

        # Check for no overlap (then negate)
        return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


@dataclass
class Plate:
    """Represents a single material plate/sheet."""

    id: int
    name: str
    width_mm: float
    height_mm: float
    x_offset: float = 0.0  # Position in grid
    y_offset: float = 0.0  # Position in grid
    part_indices: Set[int] = field(
        default_factory=set
    )  # Parts associated with this plate
    exclusion_zones: List[ExclusionZone] = field(
        default_factory=list
    )  # Off-limits areas
    ais_shape: Optional[AIS_Shape] = None  # Visual representation
    next_exclusion_id: int = field(
        default=1, init=False
    )  # Counter for exclusion zone IDs

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get the bounds of the plate (xmin, ymin, xmax, ymax)."""
        return (
            self.x_offset,
            self.y_offset,
            self.x_offset + self.width_mm,
            self.y_offset + self.height_mm,
        )

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a 2D point is within the plate bounds."""
        xmin, ymin, xmax, ymax = self.get_bounds()
        return xmin <= x <= xmax and ymin <= y <= ymax

    def add_exclusion_zone(
        self, x: float, y: float, width: float, height: float
    ) -> ExclusionZone:
        """
        Add an exclusion zone to the plate.
        Coordinates are relative to the plate's origin (not global grid coordinates).

        Args:
            x: X position relative to plate origin
            y: Y position relative to plate origin
            width: Width of the exclusion zone
            height: Height of the exclusion zone

        Returns:
            The created ExclusionZone
        """
        zone = ExclusionZone(
            id=self.next_exclusion_id, x=x, y=y, width=width, height=height
        )
        self.exclusion_zones.append(zone)
        self.next_exclusion_id += 1
        return zone

    def remove_exclusion_zone(self, zone_id: int) -> bool:
        """
        Remove an exclusion zone by ID.

        Args:
            zone_id: ID of the exclusion zone to remove

        Returns:
            True if zone was removed, False if not found
        """
        for i, zone in enumerate(self.exclusion_zones):
            if zone.id == zone_id:
                self.exclusion_zones.pop(i)
                return True
        return False

    def clear_exclusion_zones(self):
        """Remove all exclusion zones from the plate."""
        self.exclusion_zones.clear()

    def is_area_available(
        self, x: float, y: float, width: float, height: float
    ) -> bool:
        """
        Check if a rectangular area is available (not overlapping any exclusion zones).
        Coordinates are relative to the plate's origin.

        Args:
            x: X position relative to plate origin
            y: Y position relative to plate origin
            width: Width of the area
            height: Height of the area

        Returns:
            True if area is available, False if it overlaps an exclusion zone
        """
        for zone in self.exclusion_zones:
            if zone.overlaps_rect(x, y, width, height):
                return False
        return True


class PlateManager:
    """Manages multiple material plates with automatic grid layout and part associations."""

    def __init__(
        self, default_width_mm: float = 600.0, default_height_mm: float = 400.0
    ):
        """
        Initialize plate manager.

        Args:
            default_width_mm: Default width for new plates in mm
            default_height_mm: Default height for new plates in mm
        """
        self.default_width_mm = default_width_mm
        self.default_height_mm = default_height_mm
        self.plates: List[Plate] = []
        self.next_plate_id = 1
        self.grid_spacing_mm = 50.0  # Space between plates in grid

        # Create the first default plate
        self.add_plate("Plate 1")

    def add_plate(self, name: Optional[str] = None) -> Plate:
        """
        Add a new plate with default dimensions.

        Args:
            name: Name for the plate, auto-generated if not provided

        Returns:
            The newly created Plate
        """
        if name is None:
            name = f"Plate {self.next_plate_id}"

        plate = Plate(
            id=self.next_plate_id,
            name=name,
            width_mm=self.default_width_mm,
            height_mm=self.default_height_mm,
        )

        self.plates.append(plate)
        self.next_plate_id += 1

        # Recalculate grid layout
        self._update_grid_layout()

        return plate

    def remove_plate(self, plate_id: int) -> bool:
        """
        Remove a plate by ID. Parts are not deleted, only disassociated.

        Args:
            plate_id: ID of the plate to remove

        Returns:
            True if plate was removed, False if not found
        """
        # Don't allow removing the last plate
        if len(self.plates) <= 1:
            return False

        for i, plate in enumerate(self.plates):
            if plate.id == plate_id:
                # Clear part associations
                plate.part_indices.clear()

                # Remove the plate
                self.plates.pop(i)

                # Recalculate grid layout
                self._update_grid_layout()

                return True

        return False

    def rename_plate(self, plate_id: int, new_name: str) -> bool:
        """
        Rename a plate.

        Args:
            plate_id: ID of the plate to rename
            new_name: New name for the plate

        Returns:
            True if plate was renamed, False if not found
        """
        plate = self.get_plate_by_id(plate_id)
        if plate:
            plate.name = new_name
            return True
        return False

    def get_plate_by_id(self, plate_id: int) -> Optional[Plate]:
        """Get a plate by its ID."""
        for plate in self.plates:
            if plate.id == plate_id:
                return plate
        return None

    def get_plate_count(self) -> int:
        """Get the number of plates."""
        return len(self.plates)

    def associate_part_with_plate(self, part_idx: int, plate_id: int):
        """
        Associate a part with a specific plate.

        Args:
            part_idx: Index of the part
            plate_id: ID of the plate
        """
        # Remove part from all plates first
        for plate in self.plates:
            plate.part_indices.discard(part_idx)

        # Add to the specified plate
        plate = self.get_plate_by_id(plate_id)
        if plate:
            plate.part_indices.add(part_idx)

    def associate_parts_by_position(self, parts_list: List, display=None):
        """
        Automatically associate parts with plates based on their 2D position.
        Parts are assigned to the plate whose bounds contain their center point.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            display: Optional display context for getting transformations
        """
        # Clear all existing associations
        for plate in self.plates:
            plate.part_indices.clear()

        # Associate each part based on its position
        for part_idx, (solid, color, ais_shape) in enumerate(parts_list):
            # Get the bounding box of the part
            bbox = Bnd_Box()
            brepbndlib.Add(solid, bbox, True)

            if not bbox.IsVoid():
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                # Calculate center point in XY plane
                center_x = (xmin + xmax) / 2.0
                center_y = (ymin + ymax) / 2.0

                # Apply transformation if present
                if ais_shape.HasTransformation():
                    trsf = ais_shape.LocalTransformation()
                    point = gp_Pnt(center_x, center_y, 0.0)
                    point.Transform(trsf)
                    center_x = point.X()
                    center_y = point.Y()

                # Find which plate contains this point
                assigned = False
                for plate in self.plates:
                    if plate.contains_point(center_x, center_y):
                        plate.part_indices.add(part_idx)
                        assigned = True
                        break

                # If not assigned to any plate, assign to the first plate
                if not assigned and len(self.plates) > 0:
                    self.plates[0].part_indices.add(part_idx)

    def get_parts_for_plate(self, plate_id: int) -> Set[int]:
        """
        Get the set of part indices associated with a plate.

        Args:
            plate_id: ID of the plate

        Returns:
            Set of part indices, or empty set if plate not found
        """
        plate = self.get_plate_by_id(plate_id)
        if plate:
            return plate.part_indices.copy()
        return set()

    def _update_grid_layout(self):
        """Update the grid layout positions of all plates."""
        if not self.plates:
            return

        # Calculate grid dimensions - try to make it roughly square
        num_plates = len(self.plates)
        cols = math.ceil(math.sqrt(num_plates))
        rows = math.ceil(num_plates / cols)

        # Position plates in grid
        for i, plate in enumerate(self.plates):
            col = i % cols
            row = i // cols

            plate.x_offset = col * (plate.width_mm + self.grid_spacing_mm)
            plate.y_offset = row * (plate.height_mm + self.grid_spacing_mm)

    def show_all_plates(self, display):
        """
        Show all plates and their exclusion zones in the display.

        Args:
            display: The OCC display context
        """
        for plate in self.plates:
            if plate.ais_shape is None:
                self._create_plate_geometry(plate)

            if plate.ais_shape is not None:
                display.Context.Display(plate.ais_shape, True)

            # Show exclusion zones for this plate
            self._show_exclusion_zones(plate, display)

    def hide_all_plates(self, display):
        """
        Hide all plates and their exclusion zones from the display.

        Args:
            display: The OCC display context
        """
        for plate in self.plates:
            if plate.ais_shape is not None:
                display.Context.Erase(plate.ais_shape, True)

            # Hide exclusion zones for this plate
            self._hide_exclusion_zones(plate, display)

    def update_all_plates(self, display):
        """
        Update all plate geometries and exclusion zones (e.g., after layout change).

        Args:
            display: The OCC display context
        """
        for plate in self.plates:
            self.update_single_plate(plate, display)

        display.Context.UpdateCurrentViewer()

    def update_single_plate(self, plate, display):
        """
        Update a specific plate geometry and exclusion zones.

        Args:
            display: The OCC display context.
            plate: The Plate object to be updated.
        """
        # Clear old geometry
        if plate.ais_shape is not None:
            display.Context.Erase(plate.ais_shape, False)
            plate.ais_shape = None

        # Hide old exclusion zones
        self._hide_exclusion_zones(plate, display)

        # Create new geometry
        self._create_plate_geometry(plate)

        if plate.ais_shape is not None:
            display.Context.Display(plate.ais_shape, False)

        # Show updated exclusion zones
        self._show_exclusion_zones(plate, display)

    def _style_plate(self, plate):
        """
        Apply style to a plate's AIS_Shape.

        Args:
            plate: The Plate to style.
        """
        # Style the plate - semi-transparent gray with slight color variation
        base_intensity = 0.25 + (plate.id % 3) * 0.05
        plate_color = Quantity_Color(
            base_intensity, base_intensity, base_intensity + 0.05, Quantity_TOC_RGB
        )
        plate.ais_shape.SetColor(plate_color)
        plate.ais_shape.SetTransparency(0.7)  # Semi-transparent

        # Set material to make it look like a flat surface
        material = Graphic3d_MaterialAspect(Graphic3d_NOM_PLASTIC)
        plate.ais_shape.SetMaterial(material)

    def _create_plate_geometry(self, plate: Plate):
        """
        Create the visual geometry for a plate.

        Args:
            plate: The Plate to create geometry for
        """
        # Create a rectangular face at Z=0 with the plate's offset
        p1 = gp_Pnt(plate.x_offset, plate.y_offset, 0)
        p2 = gp_Pnt(plate.x_offset + plate.width_mm, plate.y_offset, 0)
        p3 = gp_Pnt(
            plate.x_offset + plate.width_mm, plate.y_offset + plate.height_mm, 0
        )
        p4 = gp_Pnt(plate.x_offset, plate.y_offset + plate.height_mm, 0)

        # Create the plate face using a polygon wire
        wire_builder = BRepBuilderAPI_MakePolygon()
        wire_builder.Add(p1)
        wire_builder.Add(p2)
        wire_builder.Add(p3)
        wire_builder.Add(p4)
        wire_builder.Close()
        wire = wire_builder.Wire()

        face_builder = BRepBuilderAPI_MakeFace(wire)
        plate_face = face_builder.Face()

        # Create AIS_Shape for visualization
        plate.ais_shape = AIS_Shape(plate_face)

        # Apply styling to the plate
        self._style_plate(plate)

    def get_total_grid_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get the total bounding box of all plates in the grid.

        Returns:
            Tuple of (xmin, ymin, xmax, ymax)
        """
        if not self.plates:
            return (0, 0, 0, 0)

        xmin = min(plate.x_offset for plate in self.plates)
        ymin = min(plate.y_offset for plate in self.plates)
        xmax = max(plate.x_offset + plate.width_mm for plate in self.plates)
        ymax = max(plate.y_offset + plate.height_mm for plate in self.plates)

        return (xmin, ymin, xmax, ymax)

    def _show_exclusion_zones(self, plate: Plate, display):
        """
        Show all exclusion zones for a plate.

        Args:
            plate: The Plate whose exclusion zones to show
            display: The OCC display context
        """
        for zone in plate.exclusion_zones:
            if zone.ais_shape is None:
                self._create_exclusion_zone_geometry(zone, plate)

            if zone.ais_shape is not None:
                display.Context.Display(zone.ais_shape, False)

    def _hide_exclusion_zones(self, plate: Plate, display):
        """
        Hide all exclusion zones for a plate.

        Args:
            plate: The Plate whose exclusion zones to hide
            display: The OCC display context
        """
        for zone in plate.exclusion_zones:
            if zone.ais_shape is not None:
                display.Context.Erase(zone.ais_shape, False)
                zone.ais_shape = None

    def _create_exclusion_zone_geometry(self, zone: ExclusionZone, plate: Plate):
        """
        Create the visual geometry for an exclusion zone.

        Args:
            zone: The ExclusionZone to create geometry for
            plate: The parent Plate (for global offset calculation)
        """
        # Calculate global coordinates (zone coords are relative to plate)
        global_x = plate.x_offset + zone.x
        global_y = plate.y_offset + zone.y

        # Create a rectangular face at Z=0.1 (slightly above plate to be visible)
        z = 0.1
        p1 = gp_Pnt(global_x, global_y, z)
        p2 = gp_Pnt(global_x + zone.width, global_y, z)
        p3 = gp_Pnt(global_x + zone.width, global_y + zone.height, z)
        p4 = gp_Pnt(global_x, global_y + zone.height, z)

        # Create the exclusion zone face using a polygon wire
        wire_builder = BRepBuilderAPI_MakePolygon()
        wire_builder.Add(p1)
        wire_builder.Add(p2)
        wire_builder.Add(p3)
        wire_builder.Add(p4)
        wire_builder.Close()
        wire = wire_builder.Wire()

        face_builder = BRepBuilderAPI_MakeFace(wire)
        zone_face = face_builder.Face()

        # Create AIS_Shape for visualization
        zone.ais_shape = AIS_Shape(zone_face)

        # Style the exclusion zone - semi-transparent red
        red_color = Quantity_Color(0.9, 0.2, 0.2, Quantity_TOC_RGB)
        zone.ais_shape.SetColor(red_color)
        zone.ais_shape.SetTransparency(0.5)  # Semi-transparent

        # Set material
        material = Graphic3d_MaterialAspect(Graphic3d_NOM_PLASTIC)
        zone.ais_shape.SetMaterial(material)

    def update_exclusion_zones(self, plate_id: int, display):
        """
        Update exclusion zones for a specific plate (recreate geometry).

        Args:
            plate_id: ID of the plate to update exclusion zones for
            display: The OCC display context
        """
        plate = self.get_plate_by_id(plate_id)
        if plate:
            self._hide_exclusion_zones(plate, display)
            self._show_exclusion_zones(plate, display)
            display.Context.UpdateCurrentViewer()
