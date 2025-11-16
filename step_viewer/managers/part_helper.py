"""
Functions for operations of individual parts.
"""

from typing import NamedTuple
from .log_manager import logger
from .units_manager import UnitSystem

from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON
from OCC.Core.AIS import AIS_Shape

from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box, Bnd_OBB
from OCC.Core.gp import (
    gp_Vec,
    gp_Pnt,
    gp_Ax2,
    gp_Dir,
    gp_XYZ,
    gp_Lin,
)
import os
import csv
import math
from datetime import datetime
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.BRepLProp import BRepLProp_SLProps
from OCC.Core.BRepClass import BRepClass_FaceClassifier


class Part(NamedTuple):
    shape: TopoDS_Shape | None
    pallete: tuple[float, float, float]
    ais_shape: AIS_Shape

def get_largest_xy_plane_face(part, z_tolerance=1e-6, normal_tolerance=1e-3):
    """
    Get the largest face of a part that is planar to the XY plane and has the highest Z coordinate.

    This is useful for laser cutting - gets the top face to be cut from a sheet.

    Parameters
    ----------
    part : Part
        The part to analyze
    z_tolerance : float
        Tolerance for Z coordinate comparison (default 1e-6)
    normal_tolerance : float
        Tolerance for checking if normal is perpendicular to XY plane (default 1e-6)

    Returns
    -------
    TopoDS_Face or None
        The largest face that is planar and parallel to XY plane with highest Z,
        or None if no suitable face found
    """
    largest_face = None
    largest_area = 0.0
    highest_z = float('-inf')

    explorer = TopExp_Explorer(part.shape, TopAbs_FACE)
    face_idx = 0
    diagnostics_records: list[dict] = []

    selected_face_idx = None
    # Compute ray origin (plate Z) and line through the part center
    try:
        xmin, ymin, zmin, xmax, ymax, zmax = get_boundingbox(part.shape, 1e-6)
        plate_z = float(zmin)
    except Exception:
        plate_z = 0.0

    try:
        center_pnt, _, _ = get_aligned_boundingbox(part.shape)
        cx = center_pnt.X()
        cy = center_pnt.Y()
    except Exception:
        # fallback to origin
        cx = 0.0
        cy = 0.0

    ray_start_z = plate_z - max(1.0, abs(plate_z) + 1.0)
    # prepare Geom line for intersection tests
    try:
        from OCC.Core.Geom import Geom_Line
        from OCC.Core.GeomAPI import GeomAPI_IntCS

        gline = Geom_Line(gp_Lin(gp_Pnt(cx, cy, ray_start_z), gp_Dir(0, 0, 1)))
        have_geom_intersector = True
    except Exception:
        have_geom_intersector = False

    # collect faces intersected by the ray: tuples of (face, hit_z, area, face_idx)
    ray_hits: list[tuple] = []
    face_records: list[tuple] = []
    while explorer.More():
        face = explorer.Current()

        # Check if face is planar with normal perpendicular to XY plane
        try:
            adapter = BRepAdaptor_Surface(face)

            # compute area and centroid early (used for diagnostics and tie-break)
            props = GProp_GProps()
            brepgprop.SurfaceProperties(face, props)
            area = props.Mass()
            centroid = props.CentreOfMass()
            z_coord = centroid.Z()

            # Attempt ray-face intersection (prefer exact surface intersection)
            hit_z = None
            try:
                if have_geom_intersector:
                    surf = adapter.Surface()
                    inter = GeomAPI_IntCS(gline, surf)
                    npts = inter.NbPoints()
                    if npts and npts > 0:
                        # pick the highest intersection Z (furthest along +Z)
                        for ii in range(1, npts + 1):
                            p = inter.Point(ii)
                            # skip intersection points that are below the plate
                            if p.Z() < plate_z - 1e-9:
                                continue
                            # ensure the intersection point lies within the trimmed face
                            try:
                                classifier = BRepClass_FaceClassifier(face, p, 1e-7)
                                st = classifier.State()
                                if st not in (TopAbs_IN, TopAbs_ON):
                                    # point lies outside the trimmed face (e.g., in a hole)
                                    continue
                            except Exception:
                                # if classification fails, be conservative and skip this point
                                continue
                            if hit_z is None or p.Z() > hit_z:
                                hit_z = p.Z()
                else:
                    # couldn't create intersector; leave hit_z as None
                    hit_z = None
            except Exception:
                hit_z = None

            # record a diagnostic entry (normal info will be filled if available)
            # attempt to compute a stable normal vector if possible
            normal_source = None
            nvec = None
            mag = None
            try:
                is_planar_surface = adapter.GetType() == GeomAbs_Plane
                if is_planar_surface:
                    u_min = adapter.FirstUParameter()
                    u_max = adapter.LastUParameter()
                    v_min = adapter.FirstVParameter()
                    v_max = adapter.LastVParameter()
                    u_mid = (u_min + u_max) / 2.0
                    v_mid = (v_min + v_max) / 2.0
                    props_sl = BRepLProp_SLProps(adapter, 1, 1e-7)
                    props_sl.SetParameters(u_mid, v_mid)
                    normal = props_sl.Normal()
                    normal_source = "surface"
                else:
                    # try mesh fallback to get approx normal
                    try:
                        mesh_deflection = 0.1
                        BRepMesh_IncrementalMesh(face, mesh_deflection)
                        loc = TopLoc_Location()
                        tri = BRep_Tool.Triangulation(face, loc)
                        if tri is not None:
                            tris = tri.Triangles()
                            nb_tris = tri.NbTriangles()
                            nb_nodes = tri.NbNodes()
                            nodes = [tri.Node(i) for i in range(1, nb_nodes + 1)]
                            acc_n = gp_Vec(0, 0, 0)
                            for ti in range(1, nb_tris + 1):
                                t = tris.Value(ti)
                                n1, n2, n3 = t.Get()
                                p1 = nodes[n1 - 1]
                                p2 = nodes[n2 - 1]
                                p3 = nodes[n3 - 1]
                                v1 = gp_Vec(p1.XYZ())
                                v2 = gp_Vec(p2.XYZ())
                                v3 = gp_Vec(p3.XYZ())
                                e1 = v2.Subtracted(v1)
                                e2 = v3.Subtracted(v1)
                                tri_n = e1.Crossed(e2)
                                acc_n = acc_n.Added(tri_n)
                            if acc_n.Magnitude() > 1e-12:
                                acc_n.Normalize()
                                normal = acc_n
                                normal_source = "mesh"
                            else:
                                normal = None
                    except Exception:
                        normal = None

                if normal is not None:
                    nvec = gp_Vec(normal.X(), normal.Y(), normal.Z())
                    mag = nvec.Magnitude()
                    if mag > 1e-12:
                        nvec.Normalize()
            except Exception:
                # ignore normal computation failures
                normal = None

            diagnostics_records.append(
                {
                    "face_idx": face_idx,
                    "is_planar_surface": adapter.GetType() == GeomAbs_Plane,
                    "normal_source": normal_source,
                    "normal_x": float(nvec.X()) if nvec is not None else None,
                    "normal_y": float(nvec.Y()) if nvec is not None else None,
                    "normal_z": float(nvec.Z()) if nvec is not None else None,
                    "normal_mag": float(mag) if mag is not None else None,
                    "nx": float(abs(nvec.X())) if nvec is not None else None,
                    "ny": float(abs(nvec.Y())) if nvec is not None else None,
                    "area": float(area),
                    "centroid_z": float(z_coord),
                }
            )

            # Determine if this face should be considered planar-to-XY
            planar_ok = False
            try:
                if adapter.GetType() == GeomAbs_Plane:
                    planar_ok = True
                elif nvec is not None:
                    nx = abs(nvec.X())
                    ny = abs(nvec.Y())
                    if nx <= normal_tolerance and ny <= normal_tolerance:
                        planar_ok = True
            except Exception:
                planar_ok = False

            # only consider faces that are planar (or near-planar) with respect to XY
            if planar_ok:
                # keep a lightweight record of this face for centroid-based fallback
                face_records.append((face, float(z_coord), float(area), face_idx))

                # If ray hit this face, record it
                if hit_z is not None:
                    ray_hits.append((face, hit_z, area, face_idx))
        except Exception as e:
            logger.error(f"Error analyzing face: '{e}'")

        explorer.Next()
        face_idx += 1

    # Optional: write diagnostics CSV when TOPFACE_DIAG environment variable set
    diag_path = os.getenv("TOPFACE_DIAG")
    if diag_path:
        try:
            write_header = not os.path.exists(diag_path)
            with open(diag_path, "a", newline="") as csvfile:
                fieldnames = [
                    "timestamp",
                    "face_idx",
                    "is_planar_surface",
                    "normal_source",
                    "normal_x",
                    "normal_y",
                    "normal_z",
                    "normal_mag",
                    "nx",
                    "ny",
                    "area",
                    "centroid_z",
                    "selected",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                for rec in diagnostics_records:
                    out = {
                        "timestamp": datetime.utcnow().isoformat(),
                        **rec,
                        "selected": rec.get("face_idx") == selected_face_idx,
                    }
                    writer.writerow(out)
        except Exception:
            logger.exception("Failed to write TOPFACE_DIAG CSV")

    # Choose selection so that a top face with a hole is still selected.
    # Strategy:
    # - compute the highest Z that any ray actually hit (max_hit_z)
    # - compute the face with the largest centroid Z (best_centroid)
    # - if best_centroid.Z is >= max_hit_z - z_tolerance, prefer best_centroid
    #   (this ensures a face whose trimmed area doesn't include the ray path
    #    but is physically the highest face is selected)
    max_hit_z = max((t[1] for t in ray_hits), default=float("-inf"))
    best_centroid = None
    if len(face_records) > 0:
        best_centroid = max(face_records, key=lambda t: (t[1], t[2]))

    if best_centroid is not None and best_centroid[1] >= max_hit_z - z_tolerance:
        largest_face, best_z, largest_area, selected_face_idx = best_centroid
    elif len(ray_hits) > 0:
        # pick the hit with the largest Z, tie-break on area
        best = max(ray_hits, key=lambda t: (t[1], t[2]))
        largest_face, best_z, largest_area, selected_face_idx = best
    elif best_centroid is not None:
        largest_face, best_z, largest_area, selected_face_idx = best_centroid
    else:
        largest_face = None

    return largest_face

def get_aligned_boundingbox(shape, tol=1e-6, optimal_BB=True):
    """return the bounding box of the TopoDS_Shape `shape`

    Parameters
    ----------

    shape : TopoDS_Shape or a subclass such as TopoDS_Face
        the shape to compute the bounding box from

    tol: float
        tolerance of the computed boundingbox

    use_triangulation : bool, True by default
        This makes the computation more accurate

    Returns
    -------
        if `as_pnt` is True, return a tuple of gp_Pnt instances
         for the lower and another for the upper X,Y,Z values representing the bounding box

        if `as_pnt` is False, return a tuple of lower and then upper X,Y,Z values
         representing the bounding box
    """
    bbox = Bnd_Box()
    bbox.SetGap(tol)

    # note: useTriangulation is True by default, we set it explicitly, but t's not necessary
    if optimal_BB:
        use_triangulation = True
        use_shapetolerance = True
        brepbndlib.AddOptimal(shape, bbox, use_triangulation, use_shapetolerance)
    else:
        brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    corner1 = gp_Pnt(xmin, ymin, zmin)
    corner2 = gp_Pnt(xmax, ymax, zmax)
    center = midpoint(corner1, corner2)
    dx = xmax - xmin
    dy = ymax - ymin
    dz = zmax - zmin
    box_shp = BRepPrimAPI_MakeBox(corner1, corner2).Shape()
    return center, [dx, dy, dz], box_shp


def get_oriented_boundingbox(shape, optimal_OBB=True):
    """return the oriented bounding box of the TopoDS_Shape `shape`

    Parameters
    ----------

    shape : TopoDS_Shape or a subclass such as TopoDS_Face
        the shape to compute the bounding box from
    optimal_OBB : bool, True by default. If set to True, compute the
        optimal (i.e. the smallest oriented bounding box). Optimal OBB is
        a bit longer.
    Returns
    -------
        a list with center, x, y and z sizes

        a shape
    """
    obb = Bnd_OBB()
    if optimal_OBB:
        is_triangulation_used = True
        is_optimal = True
        is_shape_tolerance_used = False
        brepbndlib.AddOBB(
            shape, obb, is_triangulation_used, is_optimal, is_shape_tolerance_used
        )
    else:
        brepbndlib.AddOBB(shape, obb)

    # converts the bounding box to a shape
    bary_center = obb.Center()
    x_direction = obb.XDirection()
    y_direction = obb.YDirection()
    z_direction = obb.ZDirection()
    a_half_x = obb.XHSize()
    a_half_y = obb.YHSize()
    a_half_z = obb.ZHSize()

    ax = gp_XYZ(x_direction.X(), x_direction.Y(), x_direction.Z())
    ay = gp_XYZ(y_direction.X(), y_direction.Y(), y_direction.Z())
    az = gp_XYZ(z_direction.X(), z_direction.Y(), z_direction.Z())
    p = gp_Pnt(bary_center.X(), bary_center.Y(), bary_center.Z())
    an_axe = gp_Ax2(p, gp_Dir(z_direction), gp_Dir(x_direction))
    an_axe.SetLocation(gp_Pnt(gp_XYZ() - ax * a_half_x - ay * a_half_y - az * a_half_z))
    a_box = BRepPrimAPI_MakeBox(
        an_axe, 2.0 * a_half_x, 2.0 * a_half_y, 2.0 * a_half_z
    ).Shape()
    return bary_center, [a_half_x, a_half_y, a_half_z], a_box


def midpoint(point_A, point_B):
    """computes the point that lies in the middle between pntA and pntB

    Parameters
    ----------

    pntA, pntB : gp_Pnt

    Returns
    -------

    gp_Pnt

    """
    vec_1 = gp_Vec(point_A.XYZ())
    vec_2 = gp_Vec(point_B.XYZ())
    mid = (vec_1 + vec_2) * 0.5
    return gp_Pnt(mid.XYZ())


def center_boundingbox(shape):
    """compute the center point of a TopoDS_Shape, based on its bounding box

    Parameters
    ----------

    shape : TopoDS_Shape instance or a subclass like TopoDS_Face

    Returns
    -------

    gp_Pnt

    """
    xmin, ymin, zmin, xmax, ymax, zmax = get_boundingbox(shape, 1e-6)
    return midpoint(gp_Pnt(xmin, ymin, zmin), gp_Pnt(xmax, ymax, zmax))


def get_boundingbox(shape, tol=1e-6, use_mesh=True):
    """return the bounding box of the TopoDS_Shape `shape`
    Parameters
    ----------
    shape : TopoDS_Shape or a subclass such as TopoDS_Face
        the shape to compute the bounding box from
    tol: float
        tolerance of the computed boundingbox
    use_mesh : bool
        a flag that tells whether or not the shape has first to be meshed before the bbox
        computation. This produces more accurate results
    """
    bbox = Bnd_Box()
    bbox.SetGap(tol)
    if use_mesh:
        mesh = BRepMesh_IncrementalMesh()
        mesh.SetParallelDefault(True)
        mesh.SetShape(shape)
        mesh.Perform()
        if not mesh.IsDone():
            raise AssertionError("Mesh not done.")
    brepbndlib.Add(shape, bbox, use_mesh)

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return xmin, ymin, zmin, xmax, ymax, zmax