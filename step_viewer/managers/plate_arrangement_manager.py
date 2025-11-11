"""
Plate arrangement manager for packing parts on plates with nesting optimization.
Implements 2D bin packing algorithms with spacing, rotation, and exclusion zone support.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import math

from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Pnt
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

from .log_manager import logger
from ..config import ViewerConfig


@dataclass
class Rectangle:
    """Represents a 2D rectangle for packing."""

    width: float
    height: float
    part_idx: int
    rotation: float = 0.0  # Rotation angle in radians (0 or �/2)
    x: float = 0.0  # Placement position
    y: float = 0.0  # Placement position

    def get_rotated_dimensions(self) -> Tuple[float, float]:
        """Get width and height accounting for rotation."""
        if abs(self.rotation) < 0.01:  # No rotation
            return self.width, self.height
        else:  # 90-degree rotation
            return self.height, self.width

    def area(self) -> float:
        """Get rectangle area."""
        return self.width * self.height


@dataclass
class PackingResult:
    """Result of packing operation for a single part."""

    part_idx: int
    plate_id: int
    x: float  # Position relative to plate origin
    y: float  # Position relative to plate origin
    rotation: float  # Rotation angle in radians
    width: float  # Width after rotation
    height: float  # Height after rotation


class PlateArrangementManager:
    """Manages automatic arrangement of parts on plates using bin packing algorithms."""

    def __init__(self, plate_manager):
        """
        Initialize the arrangement manager.

        Args:
            plate_manager: Reference to the PlateManager instance
        """
        self.plate_manager = plate_manager
        self.spacing_mm = ViewerConfig.DEFAULT_PART_SPACING_MM
        self.margin_mm = ViewerConfig.DEFAULT_PLATE_MARGIN_MM
        self.allow_rotation = ViewerConfig.DEFAULT_ALLOW_ROTATION

    def set_spacing(self, spacing_mm: float):
        """
        Set the spacing between parts.

        Args:
            spacing_mm: Spacing in millimeters
        """
        self.spacing_mm = max(0.0, spacing_mm)
        logger.info(f"Part spacing set to {self.spacing_mm:.1f}mm")

    def set_margin(self, margin_mm: float):
        """
        Set the margin from plate edges and exclusion zones.

        Args:
            margin_mm: Margin in millimeters
        """
        self.margin_mm = max(0.0, margin_mm)
        logger.info(f"Plate/exclusion margin set to {self.margin_mm:.1f}mm")

    def set_rotation_enabled(self, enabled: bool):
        """
        Enable or disable rotation of parts during packing.

        Args:
            enabled: True to allow 90-degree rotation, False otherwise
        """
        self.allow_rotation = enabled
        logger.info(f"Part rotation {'enabled' if enabled else 'disabled'}")

    def set_packing_strategy(self, strategy: str):
        """
        Set the packing strategy.

        Args:
            strategy: One of "best_fit", "first_fit", "bottom_left"
        """
        if strategy in ["best_fit", "first_fit", "bottom_left"]:
            self.packing_strategy = strategy
            logger.info(f"Packing strategy set to '{strategy}'")
        else:
            logger.warning(
                f"Unknown packing strategy '{strategy}', keeping '{self.packing_strategy}'"
            )

    def arrange_parts_on_plates(
        self, parts_list: List, display=None
    ) -> List[PackingResult]:
        """
        Arrange all parts on plates using bin packing algorithm.
        Creates new plates as needed when current plates are full.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            display: Optional display context for getting transformations

        Returns:
            List of PackingResult objects showing where each part was placed
        """
        if not parts_list:
            logger.warning("No parts to arrange")
            return []

        logger.info(f"Starting arrangement of {len(parts_list)} parts...")
        logger.info(
            f"Settings: spacing={self.spacing_mm}mm, rotation={'enabled' if self.allow_rotation else 'disabled'}"
        )

        # Temporarily enable debug logging for arrangement
        import logging

        old_level = logger.level
        logger.setLevel(logging.DEBUG)

        # Extract part bounding boxes
        rectangles = self._extract_part_rectangles(parts_list, display)

        if not rectangles:
            logger.error("Failed to extract part dimensions")
            return []

        # Sort rectangles by area (largest first) for better packing
        rectangles.sort(key=lambda r: r.area(), reverse=True)

        # Get plate dimensions from plate manager (not hardcoded)
        if not self.plate_manager.plates:
            logger.error("No plates available in plate manager")
            return []

        # Use first plate as reference for size (assuming all plates are same size)
        reference_plate = self.plate_manager.plates[0]
        plate_width = reference_plate.width_mm
        plate_height = reference_plate.height_mm

        logger.info(f"Using plate dimensions: {plate_width:.1f}x{plate_height:.1f}mm")

        # Check if any parts are too large for the plate
        oversized_parts = []
        for rect in rectangles:
            # Check both orientations
            fits_normal = rect.width <= plate_width and rect.height <= plate_height
            fits_rotated = rect.height <= plate_width and rect.width <= plate_height

            if not fits_normal and not fits_rotated:
                oversized_parts.append(
                    f"Part {rect.part_idx}: {rect.width:.1f}x{rect.height:.1f}mm"
                )

        if oversized_parts:
            logger.error(
                f"Cannot arrange: {len(oversized_parts)} part(s) too large for plate ({plate_width:.1f}x{plate_height:.1f}mm):"
            )
            for msg in oversized_parts:
                logger.error(f"  {msg}")
            return []

        # Clear existing part associations
        for plate in self.plate_manager.plates:
            plate.part_indices.clear()

        # Pack parts onto plates
        packing_results = []

        for idx, rect in enumerate(rectangles):
            placed = False
            logger.info(
                f"Packing part {rect.part_idx} ({idx+1}/{len(rectangles)}): {rect.width:.1f}x{rect.height:.1f}mm"
            )

            # Try to place on ALL existing plates first (not just from current_plate_idx)
            for plate in self.plate_manager.plates:
                placement = self._find_placement_on_plate(rect, plate, packing_results)

                if placement:
                    # Successfully placed
                    x, y, rotation = placement
                    # Get dimensions based on actual rotation applied
                    if abs(rotation) < 0.01:  # No rotation
                        placed_width, placed_height = rect.width, rect.height
                    else:  # 90-degree rotation
                        placed_width, placed_height = rect.height, rect.width

                    result = PackingResult(
                        part_idx=rect.part_idx,
                        plate_id=plate.id,
                        x=x,
                        y=y,
                        rotation=rotation,
                        width=placed_width,
                        height=placed_height,
                    )
                    packing_results.append(result)
                    plate.part_indices.add(rect.part_idx)
                    placed = True
                    logger.info(
                        f"  -> Placed on {plate.name} at ({x:.1f}, {y:.1f}), rotation={rotation:.2f}rad, size=({placed_width:.1f}x{placed_height:.1f}mm)"
                    )
                    logger.info(
                        f"      Occupies: X=[{x:.1f}, {x+placed_width:.1f}], Y=[{y:.1f}, {y+placed_height:.1f}]"
                    )
                    break

            # If not placed on any existing plate, create a new one
            if not placed:
                new_plate = self.plate_manager.add_plate(
                    f"Plate {self.plate_manager.next_plate_id}"
                )
                logger.info(f"  -> All existing plates full, created {new_plate.name}")

                # Try to place on new plate
                placement = self._find_placement_on_plate(
                    rect, new_plate, packing_results
                )

                if placement:
                    x, y, rotation = placement
                    # Get dimensions based on actual rotation applied
                    if abs(rotation) < 0.01:  # No rotation
                        placed_width, placed_height = rect.width, rect.height
                    else:  # 90-degree rotation
                        placed_width, placed_height = rect.height, rect.width

                    packing_results.append(
                        PackingResult(
                            part_idx=rect.part_idx,
                            plate_id=new_plate.id,
                            x=x,
                            y=y,
                            rotation=rotation,
                            width=placed_width,
                            height=placed_height,
                        )
                    )
                    new_plate.part_indices.add(rect.part_idx)
                    logger.info(
                        f"  -> Placed on {new_plate.name} at ({x:.1f}, {y:.1f}), rotation={rotation:.2f}rad"
                    )
                else:
                    logger.error(
                        f"Could not place part {rect.part_idx} even on new plate (should not happen - oversized check failed?)"
                    )

        logger.info(
            f"Arrangement complete: {len(packing_results)} parts placed on {len(self.plate_manager.plates)} plate(s)"
        )

        # Log statistics per plate
        for plate in self.plate_manager.plates:
            if plate.part_indices:
                utilization = self._calculate_plate_utilization(plate, packing_results)
                logger.info(
                    f"  {plate.name}: {len(plate.part_indices)} parts, {utilization:.1f}% utilization"
                )

        # Restore logger level
        logger.setLevel(old_level)

        return packing_results

    def _extract_part_rectangles(
        self, parts_list: List, display=None
    ) -> List[Rectangle]:
        """
        Extract 2D bounding rectangles from parts in their current orientation.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            display: Optional display context for getting transformations

        Returns:
            List of Rectangle objects
        """
        rectangles = []

        for part_idx, (solid, color, ais_shape) in enumerate(parts_list):
            try:
                # Get bounding box
                bbox = Bnd_Box()
                brepbndlib.Add(solid, bbox, True)

                if bbox.IsVoid():
                    logger.warning(f"Part {part_idx} has empty bounding box, skipping")
                    continue

                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                # Apply transformation if present
                if ais_shape.HasTransformation():
                    trsf = ais_shape.LocalTransformation()

                    # Transform all 8 corners of the bounding box
                    corners = [
                        gp_Pnt(xmin, ymin, zmin),
                        gp_Pnt(xmax, ymin, zmin),
                        gp_Pnt(xmin, ymax, zmin),
                        gp_Pnt(xmax, ymax, zmin),
                        gp_Pnt(xmin, ymin, zmax),
                        gp_Pnt(xmax, ymin, zmax),
                        gp_Pnt(xmin, ymax, zmax),
                        gp_Pnt(xmax, ymax, zmax),
                    ]

                    transformed_corners = []
                    for corner in corners:
                        corner.Transform(trsf)
                        transformed_corners.append(corner)

                    # Find new bounding box from transformed corners
                    xmin = min(p.X() for p in transformed_corners)
                    xmax = max(p.X() for p in transformed_corners)
                    ymin = min(p.Y() for p in transformed_corners)
                    ymax = max(p.Y() for p in transformed_corners)

                # Calculate 2D dimensions (X-Y plane)
                width = xmax - xmin
                height = ymax - ymin

                logger.debug(
                    f"Part {part_idx}: bbox after transform: X=[{xmin:.1f}, {xmax:.1f}], Y=[{ymin:.1f}, {ymax:.1f}] -> {width:.1f}x{height:.1f}mm"
                )

                if width > 0 and height > 0:
                    rectangles.append(
                        Rectangle(width=width, height=height, part_idx=part_idx)
                    )
                else:
                    logger.warning(
                        f"Part {part_idx} has invalid dimensions ({width}x{height}), skipping"
                    )

            except Exception as e:
                logger.error(f"Failed to extract rectangle for part {part_idx}: {e}")
                continue

        return rectangles

    def _find_placement_on_plate(
        self, rect: Rectangle, plate, existing_placements: List[PackingResult]
    ) -> Optional[Tuple[float, float, float]]:
        """
        Find a valid placement for a rectangle on a plate.

        Args:
            rect: Rectangle to place
            plate: Plate to place on
            existing_placements: List of already placed rectangles (all plates)

        Returns:
            Tuple of (x, y, rotation) if placement found, None otherwise
        """
        # CRITICAL: Get placements on THIS plate only!
        plate_placements = [p for p in existing_placements if p.plate_id == plate.id]

        logger.debug(
            f"Trying to place part {rect.part_idx} ({rect.width:.1f}x{rect.height:.1f}mm) on plate {plate.id}"
        )
        logger.debug(f"  Plate size: {plate.width_mm:.1f}x{plate.height_mm:.1f}mm")
        logger.debug(f"  Existing parts on this plate: {len(plate_placements)}")

        # Try both orientations if rotation is allowed
        orientations = [(rect.width, rect.height, 0.0)]
        if (
            self.allow_rotation and abs(rect.width - rect.height) > 0.1
        ):  # Don't rotate squares
            orientations.append((rect.height, rect.width, math.pi / 2))

        best_placement = None
        best_score = float("inf")

        for width, height, rotation in orientations:
            # Use best_fit strategy
            placement = self._find_best_fit_placement(
                width, height, rotation, plate, plate_placements
            )

            if placement:
                x, y, rot = placement
                # Score based on how far from origin (prefer bottom-left)
                score = x + y
                if score < best_score:
                    best_score = score
                    best_placement = placement
                    logger.debug(
                        f"  Found placement: ({x:.1f}, {y:.1f}) rotation={rotation:.2f}, score={score:.1f}"
                    )

        if not best_placement:
            logger.debug(f"  No valid placement found on plate {plate.id}")

        return best_placement

    def _find_best_fit_placement(
        self,
        width: float,
        height: float,
        rotation: float,
        plate,
        placements: List[PackingResult],
    ) -> Optional[Tuple[float, float, float]]:
        """
        Find placement using best-fit strategy (minimize wasted space).

        Args:
            width: Rectangle width (accounting for rotation)
            height: Rectangle height (accounting for rotation)
            rotation: Rotation angle
            plate: Plate to place on
            placements: Existing placements on this plate

        Returns:
            Tuple of (x, y, rotation) if valid placement found, None otherwise
        """
        # Generate candidate positions at strategic locations
        candidates = [
            (self.margin_mm, self.margin_mm)
        ]  # Start with margin-aware origin

        # Add positions around existing placed parts
        for p in placements:
            px, py, pw, ph = self._get_placed_rectangle_dimensions(p)
            # Four positions around each placed rectangle
            candidates.append((px + pw + self.spacing_mm, py))  # Right
            candidates.append((px, py + ph + self.spacing_mm))  # Top
            candidates.append(
                (px + pw + self.spacing_mm, py + ph + self.spacing_mm)
            )  # Top-right

        # Add positions around exclusion zones (with margin)
        for zone in plate.exclusion_zones:
            # Positions around the exclusion zone (outside the margin)
            zone_left = zone.x - self.margin_mm
            zone_right = zone.x + zone.width + self.margin_mm
            zone_bottom = zone.y - self.margin_mm
            zone_top = zone.y + zone.height + self.margin_mm

            # Try all four sides of the exclusion zone
            candidates.append(
                (zone_right + self.spacing_mm, max(self.margin_mm, zone_bottom))
            )  # Right of zone
            candidates.append(
                (
                    max(self.margin_mm, zone_left - width - self.spacing_mm),
                    max(self.margin_mm, zone_bottom),
                )
            )  # Left of zone
            candidates.append(
                (max(self.margin_mm, zone_left), zone_top + self.spacing_mm)
            )  # Above zone
            candidates.append(
                (
                    max(self.margin_mm, zone_left),
                    max(self.margin_mm, zone_bottom - height - self.spacing_mm),
                )
            )  # Below zone

        # Remove duplicates and sort
        candidates = list(set(candidates))
        candidates.sort(key=lambda pos: (pos[1], pos[0]))

        # Try each candidate and score it
        best_placement = None
        best_waste = float("inf")

        for x, y in candidates:
            if self._is_valid_placement(x, y, width, height, plate, placements):
                # Calculate "waste" - how much space is wasted to the left and below
                waste = x + y  # Simple heuristic: prefer bottom-left

                if waste < best_waste:
                    best_waste = waste
                    best_placement = (x, y, rotation)

        return best_placement

    def _is_valid_placement(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        plate,
        placements: List[PackingResult],
    ) -> bool:
        """
        Check if a placement is valid (within plate bounds, no overlaps, avoids exclusion zones).

        Args:
            x: X position (relative to plate origin)
            y: Y position (relative to plate origin)
            width: Rectangle width
            height: Rectangle height
            plate: Plate to place on
            placements: Existing placements on this plate (should be filtered by plate_id)

        Returns:
            True if placement is valid, False otherwise
        """
        # Check plate bounds with margin
        if (
            x < self.margin_mm
            or y < self.margin_mm
            or x + width > plate.width_mm - self.margin_mm
            or y + height > plate.height_mm - self.margin_mm
        ):
            logger.debug(
                f"    Rejected: Out of bounds with margin ({x:.1f}, {y:.1f}) + ({width:.1f}x{height:.1f}) > plate ({plate.width_mm:.1f}x{plate.height_mm:.1f}) with {self.margin_mm:.1f}mm margin"
            )
            return False

        # Check exclusion zones with margin
        # Parts must maintain margin distance from exclusion zones
        for zone in plate.exclusion_zones:
            # Expand the exclusion zone by the margin
            zone_x = zone.x - self.margin_mm
            zone_y = zone.y - self.margin_mm
            zone_w = zone.width + 2 * self.margin_mm
            zone_h = zone.height + 2 * self.margin_mm

            # Check if part overlaps with expanded exclusion zone
            no_overlap = (
                x + width <= zone_x
                or x >= zone_x + zone_w
                or y + height <= zone_y
                or y >= zone_y + zone_h
            )

            if not no_overlap:
                logger.debug(
                    f"    Rejected: Within {self.margin_mm:.1f}mm margin of exclusion zone at ({zone.x:.1f}, {zone.y:.1f})"
                )
                return False

        # Check for overlaps with existing placements
        for p in placements:
            px, py, pw, ph = self._get_placed_rectangle_dimensions(p)

            # Add spacing to the placed rectangle
            px_with_spacing = px - self.spacing_mm / 2
            py_with_spacing = py - self.spacing_mm / 2
            pw_with_spacing = pw + self.spacing_mm
            ph_with_spacing = ph + self.spacing_mm

            # Check for overlap (AABB collision)
            # Two rectangles DON'T overlap if one is completely to the left, right, above, or below the other
            no_overlap = (
                x + width <= px_with_spacing  # New rect is completely to the left
                or x
                >= px_with_spacing
                + pw_with_spacing  # New rect is completely to the right
                or y + height <= py_with_spacing  # New rect is completely below
                or y >= py_with_spacing + ph_with_spacing
            )  # New rect is completely above

            if not no_overlap:
                logger.debug(f"    Rejected: Overlaps with part {p.part_idx}")
                logger.debug(
                    f"      New rect: [{x:.1f}, {x+width:.1f}] x [{y:.1f}, {y+height:.1f}]"
                )
                logger.debug(
                    f"      Existing: [{px_with_spacing:.1f}, {px_with_spacing+pw_with_spacing:.1f}] x [{py_with_spacing:.1f}, {py_with_spacing+ph_with_spacing:.1f}]"
                )
                return False

        return True

    def _get_placed_rectangle_dimensions(
        self, placement: PackingResult
    ) -> Tuple[float, float, float, float]:
        """
        Get the dimensions and position of a placed rectangle.

        Args:
            placement: PackingResult to get dimensions for

        Returns:
            Tuple of (x, y, width, height)
        """
        return (placement.x, placement.y, placement.width, placement.height)

    def _calculate_plate_utilization(
        self, plate, placements: List[PackingResult]
    ) -> float:
        """
        Calculate the percentage of plate area used by parts.

        Args:
            plate: Plate to calculate utilization for
            placements: All placements

        Returns:
            Utilization percentage (0-100)
        """
        plate_area = plate.width_mm * plate.height_mm
        if plate_area <= 0:
            return 0.0

        # Calculate total area of parts on this plate
        used_area = 0.0
        for p in placements:
            if p.plate_id == plate.id:
                used_area += p.width * p.height

        return (used_area / plate_area) * 100.0

    def apply_arrangement(
        self, parts_list: List, packing_results: List[PackingResult], display
    ):
        """
        Apply the packing results by transforming the parts to their arranged positions.
        Parts must already be in planar alignment mode (flattened on Z=0).

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            packing_results: List of PackingResult objects from arrange_parts_on_plates
            display: Display context for updating the view
        """
        if not packing_results:
            logger.warning("No packing results to apply")
            return

        logger.info("Applying arrangement to parts...")

        from OCC.Core.gp import gp_Ax1, gp_Dir

        for result in packing_results:
            if result.part_idx >= len(parts_list):
                continue

            solid, color, ais_shape = parts_list[result.part_idx]
            plate = self.plate_manager.get_plate_by_id(result.plate_id)

            if not plate:
                logger.warning(
                    f"Plate {result.plate_id} not found for part {result.part_idx}"
                )
                continue

            # Get current transformation (from planar alignment)
            current_trsf = (
                ais_shape.LocalTransformation()
                if ais_shape.HasTransformation()
                else gp_Trsf()
            )

            # Get the TRANSFORMED bounding box (shape in current position)
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

            transformed_solid = BRepBuilderAPI_Transform(
                solid, current_trsf, False
            ).Shape()
            bbox = Bnd_Box()
            brepbndlib.Add(transformed_solid, bbox, True)

            if bbox.IsVoid():
                logger.warning(f"Part {result.part_idx} has void bounding box")
                continue

            # Get current bbox (already in world coordinates)
            (
                current_xmin,
                current_ymin,
                current_zmin,
                current_xmax,
                current_ymax,
                current_zmax,
            ) = bbox.Get()

            # Current position is the min corner
            current_x = current_xmin
            current_y = current_ymin
            current_z = current_zmin

            # Current dimensions
            current_width = current_xmax - current_xmin
            current_height = current_ymax - current_ymin

            # Calculate target position (plate offset + placement position)
            target_x = plate.x_offset + result.x
            target_y = plate.y_offset + result.y

            logger.info(
                f"Part {result.part_idx}: current=({current_x:.1f}, {current_y:.1f}), size=({current_width:.1f}x{current_height:.1f}mm)"
            )
            logger.info(
                f"Part {result.part_idx}: plate_offset=({plate.x_offset:.1f}, {plate.y_offset:.1f}), placement=({result.x:.1f}, {result.y:.1f})"
            )
            logger.info(
                f"Part {result.part_idx}: target=({target_x:.1f}, {target_y:.1f}), needs rotation={abs(result.rotation) > 0.01}"
            )

            # Start with current transformation
            working_trsf = current_trsf

            # Apply 90-degree Z-axis rotation if needed (in XY plane)
            if abs(result.rotation) > 0.01:
                logger.info(
                    f"  Applying 90° rotation (rotation={result.rotation:.2f}rad)"
                )

                # Get the center of the part in current position
                center_x = (current_xmin + current_xmax) / 2
                center_y = (current_ymin + current_ymax) / 2

                # Create rotation around Z-axis at current center
                rotation_trsf = gp_Trsf()
                rotation_trsf.SetRotation(
                    gp_Ax1(gp_Pnt(center_x, center_y, current_z), gp_Dir(0, 0, 1)),
                    result.rotation,
                )

                # Apply rotation to current transformation
                working_trsf = rotation_trsf.Multiplied(current_trsf)

                # Recalculate bounding box after rotation
                rotated_solid = BRepBuilderAPI_Transform(
                    solid, working_trsf, False
                ).Shape()
                rotated_bbox = Bnd_Box()
                brepbndlib.Add(rotated_solid, rotated_bbox, True)

                (
                    rotated_xmin,
                    rotated_ymin,
                    rotated_zmin,
                    rotated_xmax,
                    rotated_ymax,
                    rotated_zmax,
                ) = rotated_bbox.Get()

                # Update current position and dimensions after rotation
                current_x = rotated_xmin
                current_y = rotated_ymin
                current_width = rotated_xmax - rotated_xmin
                current_height = rotated_ymax - rotated_ymin

                logger.info(
                    f"  After rotation: position=({current_x:.1f}, {current_y:.1f}), size=({current_width:.1f}x{current_height:.1f}mm)"
                )

            # Calculate the translation needed (in XY plane only - keep Z constant)
            delta_x = target_x - current_x
            delta_y = target_y - current_y

            # Create translation transformation (XY only, preserve Z)
            translation_trsf = gp_Trsf()
            translation_trsf.SetTranslation(gp_Vec(delta_x, delta_y, 0))

            # Apply translation to working transformation
            final_trsf = translation_trsf.Multiplied(working_trsf)

            # Apply final transformation
            ais_shape.SetLocalTransformation(final_trsf)
            display.Context.Redisplay(ais_shape, False)

            # Verify final position
            final_transformed_solid = BRepBuilderAPI_Transform(
                solid, final_trsf, False
            ).Shape()
            final_bbox = Bnd_Box()
            brepbndlib.Add(final_transformed_solid, final_bbox, True)
            final_xmin, final_ymin, final_zmin, final_xmax, final_ymax, final_zmax = (
                final_bbox.Get()
            )

            final_x = final_xmin
            final_y = final_ymin
            final_width = final_xmax - final_xmin
            final_height = final_ymax - final_ymin

            logger.info(
                f"  Part {result.part_idx} VERIFY: actual position=({final_x:.1f}, {final_y:.1f}), size=({final_width:.1f}x{final_height:.1f}mm)"
            )
            if abs(final_x - target_x) > 0.5 or abs(final_y - target_y) > 0.5:
                logger.warning(
                    f"  Part {result.part_idx} MISMATCH: target was ({target_x:.1f}, {target_y:.1f}) but ended at ({final_x:.1f}, {final_y:.1f})"
                )

            logger.info(f"  Part {result.part_idx} arranged successfully")

        display.Context.UpdateCurrentViewer()
        logger.info("Arrangement applied successfully")
