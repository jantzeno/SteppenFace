"""
Polygon extraction from OCC (Open CASCADE) shapes.

Converts 3D face geometries to 2D polygons for NFP-based packing.
"""

from typing import List, Tuple, Optional
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCC.Core.TopoDS import topods, TopoDS_Face
from OCC.Core.BRep import BRep_Tool
from OCC.Core.ShapeAnalysis import ShapeAnalysis_Wire
from OCC.Core.gp import gp_Pnt

from .nfp_geometry import Point2D, Polygon2D
from ..managers.log_manager import logger


class PolygonExtractor:
    """Extract 2D polygons from OCC faces for packing."""

    @staticmethod
    def extract_from_face(
        face: TopoDS_Face, deflection: float = 0.5
    ) -> Optional[Polygon2D]:
        """
        Extract a 2D polygon from a planar face.

        Args:
            face: OCC TopoDS_Face to extract from
            deflection: Discretization tolerance in mm (smaller = more points)

        Returns:
            Polygon2D with exterior boundary and holes, or None if extraction fails
        """
        try:
            # Get face orientation
            is_reversed = face.Orientation() == 1  # TopAbs_REVERSED

            # Extract all wires from the face
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            wires = []
            while wire_explorer.More():
                wire = topods.Wire(wire_explorer.Current())
                wires.append(wire)
                wire_explorer.Next()

            if not wires:
                logger.warning("No wires found in face")
                return None

            # The first wire is typically the outer wire
            # For a more robust solution, we'd find the wire with largest bounding box
            outer_wire = wires[0]

            # Extract points from outer wire
            exterior_points = PolygonExtractor._extract_wire_points(
                outer_wire, deflection
            )
            if not exterior_points or len(exterior_points) < 3:
                logger.warning(
                    f"Insufficient points in outer wire: {len(exterior_points) if exterior_points else 0}"
                )
                return None

            # Reverse if needed for correct orientation
            if is_reversed:
                exterior_points = list(reversed(exterior_points))

            # Extract holes (remaining wires)
            holes = []
            for i, wire in enumerate(wires):
                if i == 0:  # Skip outer wire
                    continue

                hole_points = PolygonExtractor._extract_wire_points(wire, deflection)
                if hole_points and len(hole_points) >= 3:
                    # Holes should be opposite orientation
                    if not is_reversed:
                        hole_points = list(reversed(hole_points))
                    holes.append(hole_points)

            # Create polygon (constructor will ensure correct orientation)
            polygon = Polygon2D(exterior_points, holes)

            logger.debug(
                f"Extracted polygon: {len(exterior_points)} exterior points, {len(holes)} holes"
            )

            return polygon

        except Exception as e:
            logger.error(f"Error extracting polygon from face: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def _extract_wire_points(
        wire, deflection: float = 0.5
    ) -> Optional[List[Point2D]]:
        """
        Extract discretized points from a wire.

        Args:
            wire: OCC TopoDS_Wire
            deflection: Discretization tolerance

        Returns:
            List of 2D points representing the wire geometry
        """
        points = []
        edge_count = 0

        try:
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)

            while edge_explorer.More():
                edge = topods.Edge(edge_explorer.Current())
                edge_count += 1
                edge_points_before = len(points)

                # Get edge curve
                curve_adaptor = BRepAdaptor_Curve(edge)
                curve_type = curve_adaptor.GetType()  # Get curve type for debugging

                # For a closed wire, we only need the START point of each edge
                # (the end point is the start of the next edge)
                # For curves, we may want intermediate points too

                try:
                    from OCC.Core.GeomAbs import GeomAbs_C0
                    discretizer = GCPnts_QuasiUniformDeflection(
                        curve_adaptor, deflection, GeomAbs_C0  # Correct 3-arg constructor
                    )

                    if not discretizer.IsDone():
                        logger.debug(f"Edge {edge_count}: Curve discretization failed (type={curve_type}), trying with smaller deflection")
                        # Try with smaller deflection
                        discretizer = GCPnts_QuasiUniformDeflection(
                            curve_adaptor, deflection / 2, GeomAbs_C0
                        )

                    if discretizer.IsDone():
                        n_points = discretizer.NbPoints()
                        logger.info(f"Edge {edge_count}: Discretized to {n_points} points (curve type={curve_type})")

                        # For a closed wire, we take start point of each edge
                        # If there are intermediate points (curved edge), take those too
                        if n_points == 2:
                            # Straight line: just take the start point
                            logger.info(f"Edge {edge_count}: Taking ONLY start point (straight line)")
                            pnt = discretizer.Value(1)  # First point (1-indexed)
                            points.append(Point2D(pnt.X(), pnt.Y()))
                        elif n_points > 2:
                            logger.info(f"Edge {edge_count}: Taking {n_points-1} points (excluding last)")
                            # Curved edge: take all points except the last one
                            # (last point is the start of the next edge)
                            for i in range(1, n_points):  # Exclude last point
                                pnt = discretizer.Value(i)
                                points.append(Point2D(pnt.X(), pnt.Y()))
                        else:
                            # Only 1 point? This shouldn't happen, but handle it
                            logger.warning(f"Edge {edge_count}: Only {n_points} point(s) in discretization")
                            if n_points >= 1:
                                pnt = discretizer.Value(1)
                                points.append(Point2D(pnt.X(), pnt.Y()))

                    else:
                        # Fallback: just use start point (end point is next edge's start)
                        logger.debug(f"Edge {edge_count}: Discretization failed, using start point (curve type={curve_type})")
                        p1 = curve_adaptor.Value(curve_adaptor.FirstParameter())
                        points.append(Point2D(p1.X(), p1.Y()))

                except Exception as e:
                    logger.debug(f"Edge {edge_count}: Discretization error: {e}, using edge start point")
                    # Fallback: use edge start point only
                    try:
                        p1 = curve_adaptor.Value(curve_adaptor.FirstParameter())
                        points.append(Point2D(p1.X(), p1.Y()))
                    except:
                        logger.warning(f"Edge {edge_count}: Failed to extract any points!")

                edge_points_added = len(points) - edge_points_before
                logger.debug(f"Edge {edge_count}: Added {edge_points_added} points (total now: {len(points)})")

                edge_explorer.Next()

            logger.debug(f"Wire had {edge_count} edges, extracted {len(points)} raw points before cleanup")

            # For closed wires, we should have approximately one point per edge
            # Remove any remaining duplicate consecutive points
            if len(points) > 1:
                cleaned_points = [points[0]]
                tolerance = 0.01  # 0.01mm tolerance (increased from 0.001)
                duplicates_removed = 0

                for i in range(1, len(points)):
                    # Check if point is different from last added point
                    dx = abs(points[i].x - cleaned_points[-1].x)
                    dy = abs(points[i].y - cleaned_points[-1].y)
                    if dx > tolerance or dy > tolerance:
                        cleaned_points.append(points[i])
                    else:
                        duplicates_removed += 1

                # Check if last point is same as first (shouldn't happen with our new logic)
                if len(cleaned_points) > 2:
                    dx = abs(cleaned_points[-1].x - cleaned_points[0].x)
                    dy = abs(cleaned_points[-1].y - cleaned_points[0].y)
                    if dx < tolerance and dy < tolerance:
                        cleaned_points.pop()
                        duplicates_removed += 1

                logger.debug(f"Removed {duplicates_removed} duplicate points, final count: {len(cleaned_points)}")
                logger.debug(f"Expected ~{edge_count} points (one per edge), got {len(cleaned_points)}")

                if len(cleaned_points) < 3:
                    logger.warning(f"Wire produced only {len(cleaned_points)} unique points after cleanup (edge_count={edge_count})")
                    logger.warning(f"First 5 raw points: {points[:5]}")
                    logger.warning(f"Cleaned points: {cleaned_points}")
                elif len(cleaned_points) < edge_count * 0.5:
                    logger.warning(f"Wire has {edge_count} edges but only {len(cleaned_points)} points - possible extraction issue")

                return cleaned_points

            logger.warning(f"Wire extraction produced {len(points)} points (expected > 1)")
            return points

        except Exception as e:
            logger.error(f"Error extracting wire points: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def simplify_polygon(polygon: Polygon2D, tolerance: float = 1.0) -> Polygon2D:
        """
        Simplify polygon by removing unnecessary points using Douglas-Peucker algorithm.

        Args:
            polygon: Polygon to simplify
            tolerance: Maximum deviation allowed (mm)

        Returns:
            Simplified polygon
        """
        simplified_exterior = PolygonExtractor._douglas_peucker(
            polygon.points, tolerance
        )

        simplified_holes = []
        for hole in polygon.holes:
            simplified_hole = PolygonExtractor._douglas_peucker(hole, tolerance)
            if len(simplified_hole) >= 3:
                simplified_holes.append(simplified_hole)

        return Polygon2D(simplified_exterior, simplified_holes)

    @staticmethod
    def _douglas_peucker(points: List[Point2D], tolerance: float) -> List[Point2D]:
        """
        Douglas-Peucker line simplification algorithm.

        Args:
            points: List of points to simplify
            tolerance: Maximum distance from line

        Returns:
            Simplified list of points
        """
        if len(points) < 3:
            return points

        # Find point with maximum distance from line
        max_dist = 0.0
        max_index = 0

        start = points[0]
        end = points[-1]

        for i in range(1, len(points) - 1):
            dist = PolygonExtractor._point_line_distance(points[i], start, end)
            if dist > max_dist:
                max_dist = dist
                max_index = i

        # If max distance exceeds tolerance, recursively simplify
        if max_dist > tolerance:
            # Recursive call on both segments
            left = PolygonExtractor._douglas_peucker(
                points[: max_index + 1], tolerance
            )
            right = PolygonExtractor._douglas_peucker(points[max_index:], tolerance)

            # Combine results (remove duplicate middle point)
            return left[:-1] + right
        else:
            # All points are within tolerance, return just endpoints
            return [start, end]

    @staticmethod
    def _point_line_distance(point: Point2D, line_start: Point2D, line_end: Point2D) -> float:
        """
        Calculate perpendicular distance from point to line segment.

        Args:
            point: Point to measure from
            line_start: Start of line segment
            line_end: End of line segment

        Returns:
            Perpendicular distance
        """
        # Vector from start to end
        line_vec = line_end - line_start
        line_len = line_vec.magnitude()

        if line_len < 1e-6:
            # Degenerate line, return distance to point
            return point.distance_to(line_start)

        # Vector from start to point
        point_vec = point - line_start

        # Project point onto line
        t = point_vec.dot(line_vec) / (line_len * line_len)

        # Clamp to line segment
        t = max(0.0, min(1.0, t))

        # Find closest point on segment
        closest = line_start + line_vec * t

        return point.distance_to(closest)
