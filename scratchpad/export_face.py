"""Export a face from STEP to SVG for sheet cutting (scratchpad).

Small tester: flattens a face to Z-up and exports an SVG.
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
from OCC.Core.gp import gp_Vec, gp_Pnt, gp_Ax1, gp_Dir, gp_Trsf
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Extend.DataExchange import export_shape_to_svg

# Uses OCC.Extend.DataExchange exporter only.


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
    """Return (origin, ex, ey) for the face plane or an approximate basis."""
    surf = BRep_Tool.Surface(face)
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

        if pl is not None:
            if hasattr(pl, "Location") and hasattr(pl, "XDirection") and hasattr(pl, "YDirection"):
                origin = pl.Location()
                xdir = pl.XDirection()
                ydir = pl.YDirection()
            elif hasattr(pl, "Position"):
                pos = pl.Position()
                origin = pos.Location()
                xdir = pos.XDirection()
                ydir = pos.YDirection()
            else:
                origin = None
            if origin is not None:
                return origin, gp_Vec(xdir.X(), xdir.Y(), xdir.Z()), gp_Vec(ydir.X(), ydir.Y(), ydir.Z())

    try:
        u1, u2, v1, v2 = BRep_Tool.UVBounds(face)
    except Exception:
        u1, u2, v1, v2 = 0.0, 1.0, 0.0, 1.0

    um = 0.5 * (u1 + u2)
    vm = 0.5 * (v1 + v2)
    try:
        P, d1u, d1v = surf.D1(um, vm)
    except Exception:
        return gp_Pnt(0, 0, 0), gp_Vec(1, 0, 0), gp_Vec(0, 1, 0)

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
    return P, ex, ey


# Uses OCC.Extend.DataExchange exporter only.


def export_face_with_extend(face, out_path: Path, orthogonalize: bool = True):
    """Export `face` to `out_path`. If `orthogonalize`, flatten to Z-up."""
    # Build a compound containing only this face
    builder = TopoDS_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    builder.Add(comp, face)

    if orthogonalize:
        # Rotate the face so it lies flat in XY plane for sheet cutting
        origin, ex, ey = find_face_plane_and_basis(face)
        normal = ex.Crossed(ey)
        normal.Normalize()
        
        # Check if normal is already aligned with Z (face is horizontal)
        z_up = gp_Vec(0, 0, 1)
        dot_up = abs(normal.Dot(z_up))
        
        if dot_up < 0.9:
            # Face is vertical or angled - rotate to make it horizontal
            axis = normal.Crossed(z_up)
            if axis.Magnitude() > 1e-6:
                axis.Normalize()
                angle = math.acos(max(-1.0, min(1.0, normal.Dot(z_up))))
                
                trsf = gp_Trsf()
                trsf.SetRotation(
                    gp_Ax1(origin, gp_Dir(axis.X(), axis.Y(), axis.Z())),
                    angle
                )
                transformer = BRepBuilderAPI_Transform(comp, trsf, True)
                comp = transformer.Shape()

    # Force top-down for sheet export
    if orthogonalize:
        export_shape_to_svg(comp, str(out_path), direction=gp_Dir(0, 0, 1))
    else:
        export_shape_to_svg(comp, str(out_path))
    return out_path


# Entry point


def main():
    p = argparse.ArgumentParser(description="Export a face from a STEP file to SVG.")
    p.add_argument("--step", required=False, default="sample_files/Assembly 3.step", help="STEP file path")
    p.add_argument("--face", required=False, type=int, default=1, help="Face number (1-based)")
    p.add_argument("--out", required=False, default="face_export.svg", help="Output SVG filename")
    p.add_argument("--no-ortho", action="store_true", help="Do not orthogonalize before export")
    args = p.parse_args()

    step_path = Path(args.step)
    if not step_path.exists():
        raise SystemExit(f"STEP file not found: {step_path}")

    shape = load_step(str(step_path))
    faces = faces_from_shape(shape)
    if not faces:
        raise SystemExit("No faces found in STEP file.")

    # CLI uses 1-based face numbering for simplicity
    idx = args.face - 1
    if idx < 0 or idx >= len(faces):
        raise SystemExit(f"Face index out of range. Found {len(faces)} faces. Requested: {args.face}")

    selected_face = faces[idx]
    out = Path(args.out)

    # Export: minimal error handling to keep script simple
    res = export_face_with_extend(selected_face, out, orthogonalize=not args.no_ortho)
    print(f"Wrote SVG to: {res}")


if __name__ == "__main__":
    main()
