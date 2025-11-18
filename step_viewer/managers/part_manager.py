"""
Manager for operations of individual parts.
"""

from typing import NamedTuple, List, Optional, Dict, Set, Tuple
from .log_manager import logger
from .units_manager import UnitSystem

from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.gp import gp_Pnt, gp_Vec
import hashlib
from OCC.Core.AIS import AIS_ColoredShape
from OCC.Core.Quantity import Quantity_Color


class Face(NamedTuple):
    """Represents a single face of a part."""

    shape: TopoDS_Face
    global_index: int  # 1-based sequential across all parts
    part_index: int  # 0-based index of owning part
    fingerprint: str  # Stable 64-bit geometry hash
    area: float
    centroid: Tuple[float, float, float]  # (x, y, z)
    normal: Tuple[float, float, float]  # Face normal vector
    is_planar: bool
    is_external: bool


class Part(NamedTuple):
    """Represents a single part in the assembly."""

    shape: TopoDS_Shape | None
    pallete: tuple[float, float, float]
    ais_colored_shape: AIS_ColoredShape
    faces: Tuple[Face, ...] = ()  # Tuple of faces in this part


class PartManager:
    """
    Manages all part-related state and operations.

    This manager consolidates part tracking, visibility management,
    and provides utilities for working with parts in the assembly.
    """

    def __init__(self):
        """Initialize the part manager."""
        self._parts: List[Part] = []
        self._visible_parts: Set[int] = set()  # Indices of visible parts
        self._hidden_parts: Set[int] = set()  # Indices of hidden parts
        self._part_colors: Dict[int, Quantity_Color] = {}  # Original colors by index
        # Map from face hash to Face namedtuple for quick lookup
        self._face_map: Dict[int, Face] = {}
        # Map from fingerprint string to Face namedtuple
        self._face_by_fingerprint: Dict[str, Face] = {}

    def set_parts(self, parts: List[Part]) -> None:
        """
        Set the list of parts to manage.

        Args:
            parts: List of Part namedtuples
        """
        self._face_map.clear()
        self._face_by_fingerprint.clear()

        # Build all faces for each part
        parts_with_faces = []
        global_face_idx = 1

        for part_idx, part in enumerate(parts):
            faces = []

            if part.shape:
                exp = TopExp_Explorer(part.shape, TopAbs_FACE)
                while exp.More():
                    face_shape = exp.Current()
                    face_props = self._compute_face_properties(face_shape, part_idx, global_face_idx)
                    faces.append(face_props)

                    # Store in lookup maps
                    face_key = face_shape.__hash__()
                    self._face_map[face_key] = face_props
                    self._face_by_fingerprint[face_props.fingerprint] = face_props

                    global_face_idx += 1
                    exp.Next()

            # Create new Part with faces tuple
            part_with_faces = Part(
                shape=part.shape,
                pallete=part.pallete,
                ais_colored_shape=part.ais_colored_shape,
                faces=tuple(faces)
            )
            parts_with_faces.append(part_with_faces)

        self._parts = parts_with_faces
        # Initialize all parts as visible
        self._visible_parts = set(range(len(parts_with_faces)))
        self._hidden_parts.clear()
        logger.info(f"PartManager initialized with {len(parts_with_faces)} parts")
        total_faces = sum(len(part.faces) for part in self._parts)
        logger.info(f"Total faces: {total_faces}")

    def get_face_key(self, face) -> int:
        return face.__hash__()

    def _compute_face_properties(self, face_shape: TopoDS_Face, part_index: int, global_index: int) -> Face:
        """
        Compute all properties for a face and return a Face namedtuple.

        Args:
            face_shape: The TopoDS_Face to analyze
            part_index: The index of the owning part
            global_index: The global 1-based face index

        Returns:
            Face namedtuple with all properties computed
        """
        # Compute area and centroid
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face_shape, props)
        area = float(props.Mass())
        centroid_pt = props.CentreOfMass()
        centroid = (float(centroid_pt.X()), float(centroid_pt.Y()), float(centroid_pt.Z()))

        # Compute fingerprint
        fingerprint = self._compute_fingerprint(face_shape)

        # Compute normal vector at face center
        normal = self._compute_face_normal(face_shape, centroid_pt)

        # Check if planar (all edges have same normal)
        is_planar = self._is_face_planar(face_shape)

        # is_external will be set to False by default, can be computed separately if needed
        is_external = False

        return Face(
            shape=face_shape,
            global_index=global_index,
            part_index=part_index,
            fingerprint=fingerprint,
            area=area,
            centroid=centroid,
            normal=normal,
            is_planar=is_planar,
            is_external=is_external
        )

    def _compute_face_normal(self, face_shape: TopoDS_Face, point) -> Tuple[float, float, float]:
        """
        Compute the normal vector at the center of the face using surface parameters.

        Args:
            face_shape: The TopoDS_Face
            point: gp_Pnt (centroid, used for reference only)

        Returns:
            Tuple of (nx, ny, nz) as floats
        """
        try:
            surface = BRepAdaptor_Surface(face_shape)
            u_min, u_max, v_min, v_max = (
                surface.FirstUParameter(),
                surface.LastUParameter(),
                surface.FirstVParameter(),
                surface.LastVParameter(),
            )
            u_mid = (u_min + u_max) / 2.0
            v_mid = (v_min + v_max) / 2.0

            pnt = gp_Pnt()
            vec_u = gp_Vec()
            vec_v = gp_Vec()
            surface.D1(u_mid, v_mid, pnt, vec_u, vec_v)

            # Calculate normal (cross product of tangent vectors)
            normal = vec_u.Crossed(vec_v)
            if normal.Magnitude() < 1e-7:
                return (0.0, 0.0, 1.0)

            normal.Normalize()
            return (float(normal.X()), float(normal.Y()), float(normal.Z()))
        except Exception:
            # Fallback: return z-normal
            return (0.0, 0.0, 1.0)

    def _is_face_planar(self, face_shape: TopoDS_Face) -> bool:
        """
        Check if a face is planar.

        Args:
            face_shape: The TopoDS_Face to check

        Returns:
            True if the face is planar, False otherwise
        """
        from OCC.Core.GeomAbs import GeomAbs_Plane
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface

        adaptor = BRepAdaptor_Surface(face_shape)
        return adaptor.GetType() == GeomAbs_Plane

    def get_face_by_fingerprint(self, fingerprint: str) -> Optional[Face]:
        """
        Get a Face by its fingerprint.

        Args:
            fingerprint: The 64-bit fingerprint string

        Returns:
            Face namedtuple or None if not found
        """
        return self._face_by_fingerprint.get(fingerprint)

    def get_face_by_global_index(self, global_index: int) -> Optional[Face]:
        """
        Get a Face by its global index.

        Args:
            global_index: 1-based global face index

        Returns:
            Face namedtuple or None if not found
        """
        for face in self._face_map.values():
            if face.global_index == global_index:
                return face
        return None

    def get_faces_for_part(self, part_index: int) -> Tuple[Face, ...]:
        """
        Get all faces for a specific part.

        Args:
            part_index: 0-based part index

        Returns:
            Tuple of Face namedtuples for this part
        """
        if 0 <= part_index < len(self._parts):
            return self._parts[part_index].faces
        return ()

    def find_face(self, face_shape: TopoDS_Face) -> Optional[Face]:
        """
        Find a Face namedtuple by its TopoDS_Face shape.

        Args:
            face_shape: The TopoDS_Face to search for

        Returns:
            Face namedtuple or None if not found
        """
        face_key = face_shape.__hash__()
        return self._face_map.get(face_key)

    def _compute_fingerprint(self, face) -> str:
        """
        Compute stable 64-bit fingerprint from face geometry.
        Derived from: area, centroid coordinates, number of wires and edges.
        """
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = float(props.Mass())
        c = props.CentreOfMass()
        cx, cy, cz = float(c.X()), float(c.Y()), float(c.Z())

        # count wires and edges
        wires = 0
        edges = 0
        wexp = TopExp_Explorer(face, TopAbs_WIRE)
        while wexp.More():
            wires += 1
            eexp = TopExp_Explorer(wexp.Current(), TopAbs_EDGE)
            while eexp.More():
                edges += 1
                eexp.Next()
            wexp.Next()

        s = f"area={area:.6f};centroid={cx:.6f},{cy:.6f},{cz:.6f};wires={wires};edges={edges}"
        h = hashlib.sha1(s.encode("utf8")).digest()[:8]
        val = int.from_bytes(h, byteorder="big", signed=False)
        return str(val)

    def get_parts(self) -> List[Part]:
        """Get the list of all parts."""
        return self._parts

    def get_part(self, index: int) -> Optional[Part]:
        """
        Get a specific part by index.

        Args:
            index: Part index

        Returns:
            Part at the given index or None if invalid index
        """
        if 0 <= index < len(self._parts):
            return self._parts[index]
        return None

    def get_part_count(self) -> int:
        """Get the total number of parts."""
        return len(self._parts)

    def is_visible(self, index: int) -> bool:
        """
        Check if a part is visible.

        Args:
            index: Part index

        Returns:
            True if part is visible, False otherwise
        """
        return index in self._visible_parts

    def set_visibility(self, index: int, visible: bool) -> None:
        """
        Set the visibility of a part.

        Args:
            index: Part index
            visible: True to show, False to hide
        """
        if not 0 <= index < len(self._parts):
            return

        if visible:
            self._visible_parts.add(index)
            self._hidden_parts.discard(index)
        else:
            self._visible_parts.discard(index)
            self._hidden_parts.add(index)

    def get_visible_parts(self) -> List[int]:
        """Get list of visible part indices."""
        return sorted(list(self._visible_parts))

    def get_hidden_parts(self) -> List[int]:
        """Get list of hidden part indices."""
        return sorted(list(self._hidden_parts))

    def hide_all(self) -> None:
        """Hide all parts."""
        self._hidden_parts = set(range(len(self._parts)))
        self._visible_parts.clear()

    def show_all(self) -> None:
        """Show all parts."""
        self._visible_parts = set(range(len(self._parts)))
        self._hidden_parts.clear()

    def register_part_color(self, index: int, color: Quantity_Color) -> None:
        """
        Register the original color for a part.

        Args:
            index: Part index
            color: The Quantity_Color for the part
        """
        self._part_colors[index] = color

    def get_part_color(self, index: int) -> Optional[Quantity_Color]:
        """
        Get the registered color for a part.

        Args:
            index: Part index

        Returns:
            Quantity_Color or None if not registered
        """
        return self._part_colors.get(index)

    def get_ais_colored_shapes(self) -> List[AIS_ColoredShape]:
        """Get list of all AIS_ColoredShape objects."""
        return [part.ais_colored_shape for part in self._parts]

    def get_solids(self) -> List[TopoDS_Shape]:
        """Get list of all solid shapes."""
        return [part.shape for part in self._parts if part.shape is not None]

    def clear(self) -> None:
        """Clear all parts and reset state."""
        self._parts.clear()
        self._visible_parts.clear()
        self._hidden_parts.clear()
        self._part_colors.clear()
        self._face_map.clear()
        self._face_by_fingerprint.clear()
        logger.info("PartManager cleared")
