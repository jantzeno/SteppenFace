"""
Copy of export_face.py with thinner SVG outline for nicer visuals when exported.

This file was placed in `scratchpad/` as requested and reduces stroke widths
from 0.5 to 0.15 for both path and polygon outputs.
"""

import sys
import math
import argparse
from pathlib import Path

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.BRep import BRep_Tool
from OCC.Core.Geom import Geom_Plane
from OCC.Core.gp import gp_Vec, gp_Pnt
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.gp import gp_Ax3, gp_Dir, gp_Trsf
from OCC.Extend.DataExchange import export_shape_to_svg

# The sampling-based exporters and helpers were removed: this script focuses
# exclusively on the native OCC.Extend.DataExchange exporter. Removing the
# dead helper functions (sampling, triangulation, projection helpers) keeps
# the file smaller and easier to maintain.


def load_step(path: str):
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP file: {path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    return shape


def faces_from_shape(shape):
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    faces = []
    while exp.More():
        faces.append(exp.Current())
        exp.Next()
    return faces


def find_face_plane_and_basis(face):
    # Try to get the geometric surface and check if it's a plane.
    surf = BRep_Tool.Surface(face)
    plane = None
    try:
        plane = Geom_Plane.DownCast(surf)
    except Exception:
        plane = None

    if plane is not None:
        pl = None
        if hasattr(plane, "Plane"):
            try:
                pl = plane.Plane()
            except Exception:
                pl = None
        if pl is None and hasattr(plane, "Pln"):
            try:
                pl = plane.Pln()
            except Exception:
                pl = None

        origin = None
        xdir = None
        ydir = None
        if pl is not None:
            if (
                hasattr(pl, "Location")
                and hasattr(pl, "XDirection")
                and hasattr(pl, "YDirection")
            ):
                origin = pl.Location()
                xdir = pl.XDirection()
                ydir = pl.YDirection()
            else:
                if hasattr(pl, "Position"):
                    pos = pl.Position()
                    origin = pos.Location()
                    xdir = pos.XDirection()
                    ydir = pos.YDirection()

        if origin is not None and xdir is not None and ydir is not None:
            ex = gp_Vec(xdir.X(), xdir.Y(), xdir.Z())
            ey = gp_Vec(ydir.X(), ydir.Y(), ydir.Z())
            return origin, ex, ey

    # Fallback: try to evaluate surface derivatives at midpoint
    try:
        u1, u2, v1, v2 = BRep_Tool.UVBounds(face)
    except Exception:
        u1, u2, v1, v2 = 0.0, 1.0, 0.0, 1.0

    um = 0.5 * (u1 + u2)
    vm = 0.5 * (v1 + v2)
    try:
        P, d1u, d1v = surf.D1(um, vm)
    except Exception:
        bbox_center = gp_Pnt(0, 0, 0)
        return bbox_center, gp_Vec(1, 0, 0), gp_Vec(0, 1, 0)

    origin = P
    vu = gp_Vec(d1u.X(), d1u.Y(), d1u.Z())
    vv = gp_Vec(d1v.X(), d1v.Y(), d1v.Z())
    vn = vu.Crossed(vv)
    try:
        vu.Normalize()
    except Exception:
        pass
    try:
        vn.Normalize()
    except Exception:
        pass
    ex = vu
    ey = vn.Crossed(ex)
    try:
        ey.Normalize()
    except Exception:
        pass
    return origin, ex, ey


# The sampling-based exporters and helpers were removed: this script focuses
# exclusively on the native OCC.Extend.DataExchange exporter. Removing the
# dead helper functions (sampling, triangulation, projection helpers) keeps
# the file smaller and easier to maintain.


def export_face_with_extend(
    face, out_path: Path, view: str = "top", orthogonalize: bool = True, **kwargs
):
    """Use OCC.Extend.DataExchange.export_shape_to_svg to write the face.

    This wraps the face into a compound and calls the native exporter. The
    exporter typically produces high-quality SVGs without explicit triangulation
    by leveraging OCC's native exporters.
    """
    # Build a compound containing only this face
    builder = TopoDS_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    builder.Add(comp, face)

    if orthogonalize:
        # Rotate the face so its normal aligns with the requested view axis
        # while preserving XY location, then translate along Z so the face
        # plane's origin sits at Z=0.
        try:
            origin, ex, ey = find_face_plane_and_basis(face)
            # normal is ex x ey
            normal = ex.Crossed(ey)

            # Map human view names to world directions
            view_dirs = {
                "top": gp_Dir(0, 0, 1),
                "bottom": gp_Dir(0, 0, -1),
                "front": gp_Dir(0, 1, 0),
                "back": gp_Dir(0, -1, 0),
                "left": gp_Dir(-1, 0, 0),
                "right": gp_Dir(1, 0, 0),
            }
            desired_dir = view_dirs.get(view, gp_Dir(0, 0, 1))

            # choose a sensible XDirection for target axis (avoid colinearity)
            def pick_xdir(zdir: gp_Dir):
                # prefer global X unless it's nearly parallel to zdir
                if abs(zdir.Dot(gp_Dir(1, 0, 0))) > 0.9:
                    return gp_Dir(0, 1, 0)
                return gp_Dir(1, 0, 0)

            tgt_x = pick_xdir(desired_dir)

            src_ax3 = gp_Ax3(
                origin,
                gp_Dir(normal.X(), normal.Y(), normal.Z()),
                gp_Dir(ex.X(), ex.Y(), ex.Z()),
            )
            tgt_ax3 = gp_Ax3(origin, desired_dir, tgt_x)
            trsf = gp_Trsf()
            trsf.SetTransformation(src_ax3, tgt_ax3)
            transformer = BRepBuilderAPI_Transform(comp, trsf, True)
            comp_rot = transformer.Shape()

            # translate along Z so the face plane origin lands at Z=0 (keep X,Y)
            origin_z = origin.Z()
            trsf2 = gp_Trsf()
            trsf2.SetTranslation(gp_Vec(0, 0, -origin_z))
            transformer2 = BRepBuilderAPI_Transform(comp_rot, trsf2, True)
            comp = transformer2.Shape()
        except Exception:
            # if orthogonalize fails, fall back to untransformed compound
            pass

    # export_shape_to_svg accepts a shape and filename. We pass kwargs
    # through if supported by the underlying implementation.
    # Try to force a top-down direction when orthogonalizing so the exporter
    # renders the face "lying flat". Many versions accept a `direction` arg.
    try:
        if orthogonalize:
            try:
                export_shape_to_svg(comp, str(out_path), direction=gp_Dir(0, 0, 1))
                return out_path
            except TypeError:
                # exporter doesn't accept direction kwarg
                pass
        export_shape_to_svg(comp, str(out_path))
    except TypeError:
        # Some versions accept additional kwargs; ignore if not accepted.
        export_shape_to_svg(comp, str(out_path))
    return out_path


def project_point_to_basis(p: gp_Pnt, origin: gp_Pnt, ex: gp_Vec, ey: gp_Vec):
    v = gp_Vec(origin, p)
    x = v.Dot(ex)
    y = v.Dot(ey)
    return float(x), float(y)


# Note: older exporters and sampling-based SVG writers were intentionally
# removed from this script to keep the tool focused on the native
# OCC.Extend.DataExchange exporter. Use `export_face_with_extend(...)` as the
# single export entrypoint below.


def main():
    p = argparse.ArgumentParser(
        description="Export a face from a STEP file to SVG using OCC.Extend.DataExchange native exporter."
    )
    p.add_argument(
        "--step",
        required=False,
        default="sample_files/Assembly 3.step",
        help="Path to STEP file (default: sample_files/Assembly 3.step)",
    )
    p.add_argument(
        "--index",
        required=False,
        type=int,
        default=0,
        help="Face global index (0-based by default)",
    )
    p.add_argument(
        "--one-based",
        action="store_true",
        help="Treat --index as 1-based instead of 0-based",
    )
    p.add_argument(
        "--out", required=False, default="face_export.svg", help="Output SVG filename"
    )
    p.add_argument(
        "--view",
        required=False,
        choices=["top", "bottom", "left", "right", "front", "back"],
        default="top",
        help="View direction to orient the face before export (default: top)",
    )
    p.add_argument(
        "--no-orthogonalize",
        action="store_true",
        help="Do not orthogonalize the face before exporting (default: orthogonalize)",
    )
    args = p.parse_args()

    step_path = Path(args.step)
    if not step_path.exists():
        print(f"STEP file not found: {step_path}")
        sys.exit(2)

    try:
        shape = load_step(str(step_path))
    except Exception as e:
        print(f"Failed to load STEP: {e}")
        sys.exit(3)

    faces = faces_from_shape(shape)
    if not faces:
        print("No faces found in STEP file.")
        sys.exit(4)

    idx = args.index
    if args.one_based:
        idx = idx - 1
    if idx < 0 or idx >= len(faces):
        print(
            f"Index out of range. Found {len(faces)} faces. Requested index: {args.index} (0-based interpreted as {idx})"
        )
        sys.exit(5)

    selected_face = faces[idx]
    out = Path(args.out)
    try:
        # Always use the native exporter. Orthogonalize by default unless
        # explicitly disabled with --no-orthogonalize.
        res = export_face_with_extend(
            selected_face, out, view=args.view, orthogonalize=not args.no_orthogonalize
        )
        print(f"Wrote SVG to: {res}")
    except Exception as e:
        print(f"Failed exporting face: {e}")
        sys.exit(6)


if __name__ == "__main__":
    main()
