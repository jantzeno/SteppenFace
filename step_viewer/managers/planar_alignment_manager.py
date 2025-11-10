"""
Planar alignment manager for laying parts flat on a surface.
"""

from typing import List, Tuple, Optional
import numpy as np
import math

from OCC.Core.gp import gp_Trsf, gp_Vec, gp_Ax1, gp_Pnt, gp_Dir, gp_Ax3
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform


class PlanarAlignmentManager:
    """Manages planar alignment - laying parts flat on a surface."""

    def __init__(self):
        self.parts_data = []
        self.is_aligned = False
        self.original_transformations = []  # Store original transforms for reset
        self.selected_faces_per_part = {}  # Maps part index to selected face for orientation

    def initialize_parts(self, parts_list: List):
        """
        Initialize parts data.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
        """
        self.parts_data = []
        for solid, color, ais_shape in parts_list:
            self.parts_data.append({
                'solid': solid,
                'color': color,
                'ais_shape': ais_shape
            })

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
        """Apply planar alignment to all parts - lay flat and arrange in grid."""
        self.original_transformations = []

        # First pass: rotate parts to lay flat and calculate their bounding boxes
        part_transforms = []

        for part_idx, part_data in enumerate(self.parts_data):
            solid = part_data['solid']
            ais_shape = part_data['ais_shape']

            # Store original transformation
            if ais_shape.HasTransformation():
                self.original_transformations.append(ais_shape.LocalTransformation())
            else:
                self.original_transformations.append(None)

            # Use selected face if available, otherwise find the largest planar face
            if part_idx in self.selected_faces_per_part:
                selected_face = self.selected_faces_per_part[part_idx]
                largest_face_info = self._get_face_info(selected_face)
            else:
                largest_face_info = self._find_largest_planar_face(solid)

            if largest_face_info:
                face, area, normal, center = largest_face_info

                # Create transformation to align face with XY plane
                z_axis = gp_Dir(0, 0, 1)

                # Create direction from normal
                normal_dir = gp_Dir(normal[0], normal[1], normal[2])

                # For selected faces, we want them to point upward (+Z) after transformation
                # Face normals can be arbitrary, so we need to check which way to flip
                # If the normal already points generally upward (Z > 0), keep it
                # If it points downward (Z < 0), reverse it so it will point upward
                if normal_dir.Z() < 0:
                    normal_dir.Reverse()

                # Create rotation to align normal with Z axis
                rotation_trsf = gp_Trsf()

                # Only rotate if not already aligned
                if abs(normal_dir.Z() - 1.0) > 0.001:
                    rotation_axis = gp_Vec(normal_dir.XYZ()).Crossed(gp_Vec(z_axis.XYZ()))
                    if rotation_axis.Magnitude() > 0.001:
                        rotation_axis.Normalize()
                        axis = gp_Ax1(gp_Pnt(center[0], center[1], center[2]),
                                     gp_Dir(rotation_axis.XYZ()))
                        angle = np.arccos(np.clip(normal_dir.Dot(z_axis), -1.0, 1.0))
                        rotation_trsf.SetRotation(axis, angle)

                # Calculate bounding box after rotation
                transformed_shape = BRepBuilderAPI_Transform(solid, rotation_trsf, False).Shape()
                bbox = Bnd_Box()
                brepbndlib.Add(transformed_shape, bbox)
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                # Check if the selected face ended up on top or bottom
                # Transform the face center to see where it is in the rotated part
                face_center_pnt = gp_Pnt(center[0], center[1], center[2])
                face_center_pnt.Transform(rotation_trsf)
                face_z = face_center_pnt.Z()

                # The face should be near the top (zmax) or bottom (zmin) of the bounding box
                # If it's near the bottom, flip the part 180° around X axis
                part_center_z = (zmin + zmax) / 2.0
                is_on_bottom = face_z < part_center_z

                if is_on_bottom:
                    # Rotate 180° around X axis at the part center to flip top/bottom
                    flip_trsf = gp_Trsf()
                    flip_center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, part_center_z)
                    flip_trsf.SetRotation(gp_Ax1(flip_center, gp_Dir(1, 0, 0)), np.pi)
                    rotation_trsf = flip_trsf.Multiplied(rotation_trsf)

                    # Recalculate bounding box after flip
                    transformed_shape = BRepBuilderAPI_Transform(solid, rotation_trsf, False).Shape()
                    bbox = Bnd_Box()
                    brepbndlib.Add(transformed_shape, bbox)
                    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

                part_transforms.append({
                    'rotation_trsf': rotation_trsf,
                    'bbox': (xmin, ymin, zmin, xmax, ymax, zmax),
                    'width': xmax - xmin,
                    'height': ymax - ymin,
                    'depth': zmax - zmin,
                    'ais_shape': ais_shape
                })
            else:
                # No planar face found, store identity transform
                part_transforms.append({
                    'rotation_trsf': gp_Trsf(),
                    'bbox': (0, 0, 0, 0, 0, 0),
                    'width': 0,
                    'height': 0,
                    'depth': 0,
                    'ais_shape': ais_shape
                })

        # Second pass: arrange parts in a grid layout
        grid_cols = math.ceil(math.sqrt(len(part_transforms)))
        current_row = 0
        current_col = 0
        row_heights = []
        col_widths = [0] * grid_cols

        # Calculate grid dimensions
        for i, pt in enumerate(part_transforms):
            col = i % grid_cols
            row = i // grid_cols

            if row >= len(row_heights):
                row_heights.append(0)

            row_heights[row] = max(row_heights[row], pt['height'])
            col_widths[col] = max(col_widths[col], pt['width'])

        # Add spacing between parts (10% of average size)
        avg_width = sum(col_widths) / len(col_widths) if col_widths else 10
        spacing = avg_width * 0.2

        # Place parts in grid
        for i, pt in enumerate(part_transforms):
            col = i % grid_cols
            row = i // grid_cols

            # Calculate position based on grid
            x_offset = sum(col_widths[:col]) + spacing * col
            y_offset = sum(row_heights[:row]) + spacing * row

            # Get bbox info
            xmin, ymin, zmin, xmax, ymax, zmax = pt['bbox']

            # Create translation to move part to grid position and Z=0
            translation_trsf = gp_Trsf()
            translation_trsf.SetTranslation(gp_Vec(
                x_offset - xmin,
                y_offset - ymin,
                -zmin  # Move to Z=0
            ))

            # Combine transformations: translation * rotation (apply rotation first, then translation)
            final_trsf = translation_trsf
            final_trsf.Multiply(pt['rotation_trsf'])

            # Apply transformation
            pt['ais_shape'].SetLocalTransformation(final_trsf)
            display.Context.Redisplay(pt['ais_shape'], True)

        # Refresh display and fit view
        display.Context.UpdateCurrentViewer()
        display.FitAll()
        root.update_idletasks()

        print(f"Parts aligned to lay flat in {grid_cols}-column grid")

    def _reset_alignment(self, display, root):
        """Reset parts to their original orientations."""
        for i, part_data in enumerate(self.parts_data):
            ais_shape = part_data['ais_shape']

            if i < len(self.original_transformations):
                original_trsf = self.original_transformations[i]
                if original_trsf:
                    ais_shape.SetLocalTransformation(original_trsf)
                else:
                    # Clear transformation
                    ais_shape.SetLocalTransformation(gp_Trsf())

                display.Context.Redisplay(ais_shape, True)

        # Refresh display and fit view
        display.Context.UpdateCurrentViewer()
        display.FitAll()
        root.update_idletasks()

        self.original_transformations = []
        print("Parts reset to original orientation")

    def _get_face_info(self, face) -> Optional[Tuple]:
        """
        Get information about a face (area, normal, center).

        Returns:
            Tuple of (face, area, normal, center) or None if face info cannot be determined
        """
        try:
            # Calculate face area
            props = GProp_GProps()
            brepgprop.SurfaceProperties(face, props)
            area = props.Mass()

            # Get face center
            center = props.CentreOfMass()
            center_tuple = (center.X(), center.Y(), center.Z())

            # Get face normal at center
            surface = BRepAdaptor_Surface(face)
            u_min, u_max, v_min, v_max = surface.FirstUParameter(), surface.LastUParameter(), \
                                          surface.FirstVParameter(), surface.LastVParameter()
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

    def _find_largest_planar_face(self, solid) -> Optional[Tuple]:
        """
        Find the largest planar face of a solid.

        Returns:
            Tuple of (face, area, normal, center) or None if no planar face found
        """
        largest_area = 0.0
        largest_face = None
        largest_normal = None
        largest_center = None

        explorer = TopExp_Explorer(solid, TopAbs_FACE)

        while explorer.More():
            face = explorer.Current()

            # Check if face is planar
            surface = BRepAdaptor_Surface(face)
            if surface.GetType() == GeomAbs_Plane:
                # Calculate face area
                props = GProp_GProps()
                brepgprop.SurfaceProperties(face, props)
                area = props.Mass()

                if area > largest_area:
                    largest_area = area
                    largest_face = face

                    # Get plane normal
                    plane = surface.Plane()
                    axis = plane.Axis()
                    normal_dir = axis.Direction()
                    largest_normal = (normal_dir.X(), normal_dir.Y(), normal_dir.Z())

                    # Get face center
                    center = props.CentreOfMass()
                    largest_center = (center.X(), center.Y(), center.Z())

            explorer.Next()

        if largest_face:
            return (largest_face, largest_area, largest_normal, largest_center)

        return None

    def is_alignment_active(self) -> bool:
        """Check if planar alignment is currently active."""
        return self.is_aligned
