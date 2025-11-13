"""
No-Fit Polygon (NFP) geometry utilities.

Based on the SVGnest algorithm by Jack000:
https://github.com/Jack000/SVGnest

This implements a simplified orbiting method for computing no-fit polygons,
which enables efficient packing of irregular shapes with concave features,
holes, and finger joints.
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass, field
import math
from ..managers.log_manager import logger


# Tolerance for floating point comparisons
TOLERANCE = 1e-6


@dataclass
class Point2D:
    """2D point representation."""

    x: float
    y: float

    def __add__(self, other: "Point2D") -> "Point2D":
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point2D") -> "Point2D":
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point2D":
        return Point2D(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Point2D":
        return Point2D(self.x / scalar, self.y / scalar)

    def __eq__(self, other: "Point2D") -> bool:
        return (
            abs(self.x - other.x) < TOLERANCE and abs(self.y - other.y) < TOLERANCE
        )

    def __hash__(self) -> int:
        return hash((round(self.x, 6), round(self.y, 6)))

    def dot(self, other: "Point2D") -> float:
        """Dot product."""
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Point2D") -> float:
        """Cross product (returns scalar for 2D)."""
        return self.x * other.y - self.y * other.x

    def magnitude(self) -> float:
        """Vector magnitude."""
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self) -> "Point2D":
        """Return normalized vector."""
        mag = self.magnitude()
        if mag < TOLERANCE:
            return Point2D(0, 0)
        return Point2D(self.x / mag, self.y / mag)

    def distance_to(self, other: "Point2D") -> float:
        """Distance to another point."""
        return (self - other).magnitude()


@dataclass
class Polygon2D:
    """2D polygon representation."""

    points: List[Point2D]
    holes: List[List[Point2D]] = field(default_factory=list)

    def __post_init__(self):
        """Ensure counter-clockwise orientation for exterior, clockwise for holes."""
        if len(self.points) > 2:
            if self._is_clockwise(self.points):
                self.points = list(reversed(self.points))

        for i, hole in enumerate(self.holes):
            if not self._is_clockwise(hole):
                self.holes[i] = list(reversed(hole))

    @staticmethod
    def _is_clockwise(points: List[Point2D]) -> bool:
        """Check if polygon points are in clockwise order."""
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += (points[j].x - points[i].x) * (points[j].y + points[i].y)
        return area > 0

    def area(self) -> float:
        """Calculate polygon area using shoelace formula."""
        if len(self.points) < 3:
            return 0.0

        area = 0.0
        n = len(self.points)
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y

        area = abs(area) / 2.0

        # Subtract hole areas
        for hole in self.holes:
            hole_area = 0.0
            n = len(hole)
            for i in range(n):
                j = (i + 1) % n
                hole_area += hole[i].x * hole[j].y
                hole_area -= hole[j].x * hole[i].y
            area -= abs(hole_area) / 2.0

        return area

    def bounding_box(self) -> Tuple[float, float, float, float]:
        """Get bounding box (min_x, min_y, max_x, max_y)."""
        if not self.points:
            return (0, 0, 0, 0)

        min_x = min(p.x for p in self.points)
        max_x = max(p.x for p in self.points)
        min_y = min(p.y for p in self.points)
        max_y = max(p.y for p in self.points)

        return (min_x, min_y, max_x, max_y)

    def translate(self, offset: Point2D) -> "Polygon2D":
        """Return translated polygon."""
        return Polygon2D(
            [p + offset for p in self.points],
            [[p + offset for p in hole] for hole in self.holes],
        )

    def centroid(self) -> Point2D:
        """Calculate polygon centroid."""
        if not self.points:
            return Point2D(0, 0)

        n = len(self.points)
        cx = sum(p.x for p in self.points) / n
        cy = sum(p.y for p in self.points) / n
        return Point2D(cx, cy)


class NFPGeometry:
    """
    No-Fit Polygon (NFP) calculation using the orbiting method.

    Based on SVGnest implementation.
    """

    @staticmethod
    def compute_nfp(
        polygon_a: Polygon2D, polygon_b: Polygon2D, inside: bool = False
    ) -> Optional[Polygon2D]:
        """
        Compute the No-Fit Polygon of B relative to A.

        The NFP represents all positions where a reference point of B can be placed
        such that B touches but does not overlap A.

        Args:
            polygon_a: Stationary polygon
            polygon_b: Orbiting polygon
            inside: If True, compute Inner-Fit Polygon (for placement inside A)

        Returns:
            NFP polygon, or None if computation fails
        """
        if len(polygon_a.points) < 3 or len(polygon_b.points) < 3:
            logger.warning("NFP: Polygons must have at least 3 vertices")
            return None

        try:
            # Find starting point (rightmost point of A, leftmost point of B)
            start_a = NFPGeometry._get_rightmost_point(polygon_a.points)
            start_b = NFPGeometry._get_leftmost_point(polygon_b.points)

            # Initial NFP point
            nfp_points = [polygon_a.points[start_a] - polygon_b.points[start_b]]

            # Orbit B around A
            prev_vector = None
            current_a = start_a
            current_b = start_b

            max_iterations = 2 * (len(polygon_a.points) + len(polygon_b.points))
            iterations = 0

            while iterations < max_iterations:
                iterations += 1

                # Get edges
                edge_a = NFPGeometry._get_edge_vector(polygon_a.points, current_a)
                edge_b = NFPGeometry._get_edge_vector(polygon_b.points, current_b)

                # Choose translation vector
                if inside:
                    # For IFP, prefer edge from A
                    if NFPGeometry._cross_product(edge_a, edge_b) >= 0:
                        translation = edge_a
                        current_a = (current_a + 1) % len(polygon_a.points)
                    else:
                        translation = edge_b * -1
                        current_b = (current_b + 1) % len(polygon_b.points)
                else:
                    # For NFP, prefer edge from B
                    if NFPGeometry._cross_product(edge_a, edge_b) <= 0:
                        translation = edge_a
                        current_a = (current_a + 1) % len(polygon_a.points)
                    else:
                        translation = edge_b * -1
                        current_b = (current_b + 1) % len(polygon_b.points)

                # Add NFP point if direction changed
                if prev_vector is None or not NFPGeometry._almost_equal_vector(
                    translation, prev_vector
                ):
                    if len(nfp_points) > 0:
                        nfp_points.append(nfp_points[-1] + translation)
                else:
                    # Continue in same direction
                    nfp_points[-1] = nfp_points[-1] + translation

                prev_vector = translation

                # Check if we've returned to start
                if (
                    current_a == start_a
                    and current_b == start_b
                    and len(nfp_points) > 2
                ):
                    # Remove last point if it's same as first
                    if (nfp_points[-1] - nfp_points[0]).magnitude() < TOLERANCE:
                        nfp_points.pop()
                    break

            if len(nfp_points) < 3:
                logger.warning(
                    f"NFP: Failed to compute valid polygon (only {len(nfp_points)} points)"
                )
                return None

            return Polygon2D(nfp_points)

        except Exception as e:
            logger.error(f"NFP computation error: {e}")
            return None

    @staticmethod
    def _get_rightmost_point(points: List[Point2D]) -> int:
        """Get index of rightmost point (highest x, then highest y)."""
        max_idx = 0
        for i in range(1, len(points)):
            if (
                points[i].x > points[max_idx].x + TOLERANCE
                or (
                    abs(points[i].x - points[max_idx].x) < TOLERANCE
                    and points[i].y > points[max_idx].y
                )
            ):
                max_idx = i
        return max_idx

    @staticmethod
    def _get_leftmost_point(points: List[Point2D]) -> int:
        """Get index of leftmost point (lowest x, then lowest y)."""
        min_idx = 0
        for i in range(1, len(points)):
            if (
                points[i].x < points[min_idx].x - TOLERANCE
                or (
                    abs(points[i].x - points[min_idx].x) < TOLERANCE
                    and points[i].y < points[min_idx].y
                )
            ):
                min_idx = i
        return min_idx

    @staticmethod
    def _get_edge_vector(points: List[Point2D], index: int) -> Point2D:
        """Get edge vector from point at index to next point."""
        next_idx = (index + 1) % len(points)
        return points[next_idx] - points[index]

    @staticmethod
    def _cross_product(v1: Point2D, v2: Point2D) -> float:
        """2D cross product."""
        return v1.x * v2.y - v1.y * v2.x

    @staticmethod
    def _almost_equal_vector(v1: Point2D, v2: Point2D) -> bool:
        """Check if two vectors are almost equal in direction."""
        # Normalize and compare
        n1 = v1.normalize()
        n2 = v2.normalize()
        return (abs(n1.x - n2.x) < TOLERANCE and abs(n1.y - n2.y) < TOLERANCE) or (
            abs(n1.x + n2.x) < TOLERANCE and abs(n1.y + n2.y) < TOLERANCE
        )

    @staticmethod
    def point_in_polygon(point: Point2D, polygon: Polygon2D) -> bool:
        """
        Check if a point is inside a polygon using ray casting.

        Args:
            point: Point to test
            polygon: Polygon to test against

        Returns:
            True if point is inside polygon
        """
        inside = False
        points = polygon.points
        n = len(points)

        p1 = points[0]
        for i in range(1, n + 1):
            p2 = points[i % n]

            if point.y > min(p1.y, p2.y):
                if point.y <= max(p1.y, p2.y):
                    if point.x <= max(p1.x, p2.x):
                        if abs(p1.y - p2.y) > TOLERANCE:
                            x_intersect = (point.y - p1.y) * (p2.x - p1.x) / (
                                p2.y - p1.y
                            ) + p1.x

                        if abs(p1.x - p2.x) < TOLERANCE or point.x <= x_intersect:
                            inside = not inside
            p1 = p2

        # Check holes (if point is in a hole, it's not in the polygon)
        for hole in polygon.holes:
            if NFPGeometry._point_in_simple_polygon(point, hole):
                inside = False

        return inside

    @staticmethod
    def _point_in_simple_polygon(point: Point2D, points: List[Point2D]) -> bool:
        """Point in polygon test without holes."""
        inside = False
        n = len(points)

        p1 = points[0]
        for i in range(1, n + 1):
            p2 = points[i % n]

            if point.y > min(p1.y, p2.y):
                if point.y <= max(p1.y, p2.y):
                    if point.x <= max(p1.x, p2.x):
                        if abs(p1.y - p2.y) > TOLERANCE:
                            x_intersect = (point.y - p1.y) * (p2.x - p1.x) / (
                                p2.y - p1.y
                            ) + p1.x

                        if abs(p1.x - p2.x) < TOLERANCE or point.x <= x_intersect:
                            inside = not inside
            p1 = p2

        return inside

    @staticmethod
    def polygons_intersect(poly_a: Polygon2D, poly_b: Polygon2D) -> bool:
        """
        Check if two polygons intersect.

        Args:
            poly_a: First polygon
            poly_b: Second polygon

        Returns:
            True if polygons overlap
        """
        # Quick bounding box check first
        bbox_a = poly_a.bounding_box()
        bbox_b = poly_b.bounding_box()

        if (
            bbox_a[2] < bbox_b[0]
            or bbox_a[0] > bbox_b[2]
            or bbox_a[3] < bbox_b[1]
            or bbox_a[1] > bbox_b[3]
        ):
            return False

        # Check if any vertex of poly_a is inside poly_b
        for point in poly_a.points:
            if NFPGeometry.point_in_polygon(point, poly_b):
                return True

        # Check if any vertex of poly_b is inside poly_a
        for point in poly_b.points:
            if NFPGeometry.point_in_polygon(point, poly_a):
                return True

        # Check for edge intersections
        for i in range(len(poly_a.points)):
            edge_a_start = poly_a.points[i]
            edge_a_end = poly_a.points[(i + 1) % len(poly_a.points)]

            for j in range(len(poly_b.points)):
                edge_b_start = poly_b.points[j]
                edge_b_end = poly_b.points[(j + 1) % len(poly_b.points)]

                if NFPGeometry._segments_intersect(
                    edge_a_start, edge_a_end, edge_b_start, edge_b_end
                ):
                    return True

        return False

    @staticmethod
    def _segments_intersect(
        a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D
    ) -> bool:
        """Check if two line segments intersect."""
        d = (b2.y - b1.y) * (a2.x - a1.x) - (b2.x - b1.x) * (a2.y - a1.y)

        if abs(d) < TOLERANCE:
            # Parallel or collinear
            return False

        ua = ((b2.x - b1.x) * (a1.y - b1.y) - (b2.y - b1.y) * (a1.x - b1.x)) / d
        ub = ((a2.x - a1.x) * (a1.y - b1.y) - (a2.y - a1.y) * (a1.x - b1.x)) / d

        return 0 <= ua <= 1 and 0 <= ub <= 1
