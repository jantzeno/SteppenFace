"""
Planar alignment manager for laying parts flat on a surface.
"""

from typing import List, Tuple, Optional
import numpy as np
import math

from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

from step_viewer.managers.plate_manager import PlateManager

from .log_manager import logger
from .part_manager import Part, PartManager


class PlanarAlignmentManager:
    """Manages planar alignment - laying parts flat on a surface."""

    def __init__(self, part_manager: PartManager, plate_manager: PlateManager):
        # PartManager will be provided by ApplicationManager and is the canonical source
        self.part_manager = part_manager
        self.plate_manager = plate_manager
        self.is_aligned = False
        self.original_transformations = []  # Store original transforms for reset
        self.planar_rotation_transformations = (
            []
        )  # Store planar-only rotation transforms
        self.selected_faces_per_part = (
            {}
        )  # Maps part index to selected face for orientation

    def initialize_parts(self):
        self.parts_list = self.part_manager.get_parts()

    def set_selected_faces(self, selected_faces_map: dict):
        """
        Set selected faces for each part to use for orientation in planar alignment.

        Args:
            selected_faces_map: Dict mapping part index to selected face
        """
        self.selected_faces_per_part = selected_faces_map

    def toggle_planar_alignment(self, display, root):
        """Toggle planar alignment on/off."""
        self.is_aligned = not self.is_aligned

        if self.is_aligned:
            self._apply_planar_alignment(display, root)
        else:
            self._reset_alignment(display, root)

        return self.is_aligned

    def _apply_planar_alignment(self, display, root):
        """Apply planar alignment to all parts - lay flat and arrange in grid.

        The routine does two passes:
        1) Rotate each part so its chosen planar face faces +Z and record its
           rotated bounding box.
        2) Arrange the rotated parts in a simple grid on Z=0 and apply the
           combined rotation+translation to the AIS object for display.
        """
        if not self.parts_list:
            logger.warning("PlanarAlignmentManager: No parts available for alignment")
            return

        self.original_transformations = []
        self.planar_rotation_transformations = []

        # First pass: compute rotation per part to make a chosen planar face point +Z
        part_transforms: List[dict] = []

        for part_idx, part in enumerate(self.parts_list):
            solid = part.shape
            ais_shape = part.ais_colored_shape

            # Store original transformation for later reset
            if ais_shape.HasTransformation():
                self.original_transformations.append(ais_shape.LocalTransformation())
            else:
                self.original_transformations.append(None)

            # Choose face: user-selected face or largest planar face
            if part_idx in self.selected_faces_per_part:
                selected_face = self.selected_faces_per_part[part_idx]
                largest_face_info = self._get_face_info(selected_face)
            else:
                largest_face_info = self._find_largest_planar_face(part_idx)

            if largest_face_info:
                face, area, normal, center = largest_face_info

                # Align face normal to +Z
                z_axis = gp_Dir(0, 0, 1)
                normal_dir = gp_Dir(normal[0], normal[1], normal[2])
                if normal_dir.Z() < 0:
                    normal_dir.Reverse()

                rotation_trsf = gp_Trsf()
                if abs(normal_dir.Z() - 1.0) > 0.001:
                    rotation_axis = gp_Vec(normal_dir.XYZ()).Crossed(
                        gp_Vec(z_axis.XYZ())
                    )
                    if rotation_axis.Magnitude() > 0.001:
                        rotation_axis.Normalize()
                        axis = gp_Ax1(
                            gp_Pnt(center[0], center[1], center[2]),
                            gp_Dir(rotation_axis.XYZ()),
                        )
                        angle = np.arccos(np.clip(normal_dir.Dot(z_axis), -1.0, 1.0))
                        rotation_trsf.SetRotation(axis, angle)

                # Check and flip so the face ends up on the top side
                transformed_shape = BRepBuilderAPI_Transform(
                    solid, rotation_trsf, False
                ).Shape()
                bbox = Bnd_Box()
                brepbndlib.Add(transformed_shape, bbox)
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                face_center_pnt = gp_Pnt(center[0], center[1], center[2])
                face_center_pnt.Transform(rotation_trsf)
                face_z = face_center_pnt.Z()
                part_center_z = (zmin + zmax) / 2.0
                if face_z < part_center_z:
                    # flip 180deg around X to move face to top
                    flip_trsf = gp_Trsf()
                    flip_center = gp_Pnt(
                        (xmin + xmax) / 2, (ymin + ymax) / 2, part_center_z
                    )
                    flip_trsf.SetRotation(gp_Ax1(flip_center, gp_Dir(1, 0, 0)), np.pi)
                    rotation_trsf = flip_trsf.Multiplied(rotation_trsf)

                # Record transform and rotated bbox
                transformed_shape = BRepBuilderAPI_Transform(
                    solid, rotation_trsf, False
                ).Shape()
                bbox = Bnd_Box()
                brepbndlib.Add(transformed_shape, bbox)
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                part_transforms.append(
                    {
                        "rotation_trsf": rotation_trsf,
                        "bbox": (xmin, ymin, zmin, xmax, ymax, zmax),
                        "width": xmax - xmin,
                        "height": ymax - ymin,
                        "depth": zmax - zmin,
                        "ais_shape": ais_shape,
                    }
                )
                self.planar_rotation_transformations.append(rotation_trsf)
            else:
                # No planar face found -> identity
                part_transforms.append(
                    {
                        "rotation_trsf": gp_Trsf(),
                        "bbox": (0, 0, 0, 0, 0, 0),
                        "width": 0,
                        "height": 0,
                        "depth": 0,
                        "ais_shape": ais_shape,
                    }
                )
                self.planar_rotation_transformations.append(gp_Trsf())

        # Second pass: arrange parts in a grid on Z=0
        grid_cols = math.ceil(math.sqrt(len(part_transforms))) if part_transforms else 1
        row_heights: List[float] = []
        col_widths: List[float] = [0.0] * grid_cols

        # compute column widths and row heights
        for i, pt in enumerate(part_transforms):
            col = i % grid_cols
            row = i // grid_cols
            if row >= len(row_heights):
                row_heights.append(0.0)
            row_heights[row] = max(row_heights[row], pt["height"])
            col_widths[col] = max(col_widths[col], pt["width"])

        # spacing and placement
        avg_width = sum(col_widths) / len(col_widths) if col_widths else 10.0
        spacing = avg_width * 0.2

        for i, pt in enumerate(part_transforms):
            col = i % grid_cols
            row = i // grid_cols

            x_offset = sum(col_widths[:col]) + spacing * col
            y_offset = sum(row_heights[:row]) + spacing * row

            xmin, ymin, zmin, xmax, ymax, zmax = pt["bbox"]

            translation_trsf = gp_Trsf()
            translation_trsf.SetTranslation(
                gp_Vec(x_offset - xmin, y_offset - ymin, -zmin)
            )

            final_trsf = translation_trsf
            final_trsf.Multiply(pt["rotation_trsf"])

            pt["ais_shape"].SetLocalTransformation(final_trsf)
            display.Context.Redisplay(pt["ais_shape"], True)

        # Show plates (if any)
        if self.plate_manager:
            self.plate_manager.show_all_plates(display)

        display.Context.UpdateCurrentViewer()
        display.FitAll()
        root.update_idletasks()

        logger.info(f"Parts aligned to lay flat in {grid_cols}-column grid")

    def _reset_alignment(self, display, root):
        """Reset parts to their original orientations."""
        for i, part in enumerate(self.parts_list):
            ais_shape = part.ais_colored_shape

            if i < len(self.original_transformations):
                original_trsf = self.original_transformations[i]
                if original_trsf:
                    ais_shape.SetLocalTransformation(original_trsf)
                else:
                    # Clear transformation
                    ais_shape.SetLocalTransformation(gp_Trsf())

                display.Context.Redisplay(ais_shape, True)

        # Hide plates
        if self.plate_manager:
            self.plate_manager.hide_all_plates(display)

        # Refresh display and fit view
        display.Context.UpdateCurrentViewer()
        display.FitAll()
        root.update_idletasks()

        self.original_transformations = []
        logger.info("Parts reset to original orientation")

    def _get_face_info(self, face) -> Optional[Tuple]:
        """
        Get information about a face (face namedtuple, area, normal, center).

        Args:
            face: Either a Face namedtuple or a TopoDS_Face

        Returns:
            Tuple of (face, area, normal, center) or None if face info cannot be determined
        """
        try:
            from step_viewer.managers.part_manager import Face

            # Check if it's already a Face namedtuple
            if isinstance(face, Face):
                # Extract info directly from Face namedtuple
                return (face.shape, face.area, face.normal, face.centroid)

            # Otherwise treat as TopoDS_Face and compute properties
            props = GProp_GProps()
            brepgprop.SurfaceProperties(face, props)
            area = props.Mass()

            # Get face center
            center = props.CentreOfMass()
            center_tuple = (center.X(), center.Y(), center.Z())

            # Get face normal at center
            surface = BRepAdaptor_Surface(face)
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
            normal_vec = vec_u.Crossed(vec_v)
            if normal_vec.Magnitude() < 1e-7:
                return None

            normal_vec.Normalize()
            normal_tuple = (normal_vec.X(), normal_vec.Y(), normal_vec.Z())

            return (face, area, normal_tuple, center_tuple)
        except:
            return None

    def _find_largest_planar_face(self, part_idx: int) -> Optional[Tuple]:
        """
        Find the largest planar face in a part from PartManager.

        Args:
            part_idx: Index of the part

        Returns:
            Tuple of (face, area, normal, center) or None if no planar face found
        """
        largest_area = 0.0
        largest_face = None
        largest_normal = None
        largest_center = None

        # Get faces for this part from PartManager
        faces = self.part_manager.get_faces_for_part(part_idx)

        for face in faces:
            # Check if face is planar
            if face.is_planar:
                if face.area > largest_area:
                    largest_area = face.area
                    largest_face = face.shape
                    largest_normal = face.normal
                    largest_center = face.centroid

        if largest_face:
            return (largest_face, largest_area, largest_normal, largest_center)

        return None

    def is_alignment_active(self) -> bool:
        """Check if planar alignment is currently active."""
        return self.is_aligned
