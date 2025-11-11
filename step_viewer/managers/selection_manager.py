"""
Face selection state management.
"""

from typing import Dict, List, Tuple

from OCC.Core.AIS import AIS_Shape
from OCC.Core.Aspect import Aspect_TypeOfLine
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Lin, gp_Ax1, gp_Trsf
from OCC.Core.BRepIntCurveSurface import BRepIntCurveSurface_Inter

from ..config import ViewerConfig
from .color_manager import ColorManager
from .log_manager import logger


class SelectionManager:
    """Manages face selection state and highlighting."""

    def __init__(self, display, color_manager: ColorManager, config: ViewerConfig):
        self.display = display
        self.color_manager = color_manager
        self.config = config
        self.is_selection_mode = False
        self.highlighted_faces: Dict[int, AIS_Shape] = {}
        self.face_parent_map: Dict[int, AIS_Shape] = (
            {}
        )  # Maps face hash to parent AIS_Shape
        self.face_to_part_map: Dict[int, int] = {}  # Maps face hash to part index
        self.part_selected_faces: Dict[int, any] = (
            {}
        )  # Maps part index to selected face object
        self.selection_label = None
        self.planar_alignment_manager = None  # Reference to planar alignment manager

    def set_selection_label(self, label):
        """Set reference to the selection count label."""
        self.selection_label = label

    def set_planar_alignment_manager(self, manager):
        """Set reference to planar alignment manager."""
        self.planar_alignment_manager = manager

    def update_face_transformations(self):
        """Update transformations of all highlighted faces to match their parent parts."""
        for face_hash, ais_highlight in self.highlighted_faces.items():
            if face_hash in self.face_parent_map:
                parent_ais_shape = self.face_parent_map[face_hash]
                if parent_ais_shape.HasTransformation():
                    ais_highlight.SetLocalTransformation(
                        parent_ais_shape.LocalTransformation()
                    )
                else:
                    # Parent has no transformation, clear the face highlight transformation too
                    ais_highlight.SetLocalTransformation(gp_Trsf())

                # Redisplay to ensure transformation is applied
                self.display.Context.Redisplay(ais_highlight, False)

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def toggle_mode(self) -> bool:
        """Toggle between navigation and selection mode. Returns new mode state."""
        self.is_selection_mode = not self.is_selection_mode
        return self.is_selection_mode

    def select_face_at_position(self, x: int, y: int, view, root) -> bool:
        """
        Select or deselect a face at the given screen position.

        Returns:
            True if a face was selected/deselected, False otherwise
        """
        try:
            self.display.Context.MoveTo(x, y, view, True)

            if not self.display.Context.HasDetected():
                return False

            detected_shape = self.display.Context.DetectedShape()
            if detected_shape.IsNull():
                return False

            # Get the parent interactive object (AIS_Shape) that was clicked
            detected_interactive = self.display.Context.DetectedInteractive()

            face_hash = detected_shape.__hash__()

            if face_hash in self.highlighted_faces:
                # Deselect
                ais_highlight = self.highlighted_faces[face_hash]
                self.display.Context.Remove(ais_highlight, True)
                del self.highlighted_faces[face_hash]
                if face_hash in self.face_parent_map:
                    del self.face_parent_map[face_hash]
                action = "Deselected"
            else:
                # Select
                ais_highlight = AIS_Shape(detected_shape)
                ais_highlight.SetColor(self.color_manager.get_fill_quantity_color())
                ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)

                # Set display mode to shaded (1) to show the face properly
                ais_highlight.SetDisplayMode(1)

                # Copy transformation from parent object if it has one
                if detected_interactive is not None:
                    parent_ais = AIS_Shape.DownCast(detected_interactive)
                    if parent_ais is not None:
                        # Store the parent for later transformation updates
                        self.face_parent_map[face_hash] = parent_ais
                        if parent_ais.HasTransformation():
                            ais_highlight.SetLocalTransformation(
                                parent_ais.LocalTransformation()
                            )

                drawer = ais_highlight.Attributes()
                drawer.SetFaceBoundaryDraw(True)
                drawer.FaceBoundaryAspect().SetColor(
                    self.color_manager.get_outline_quantity_color()
                )
                drawer.FaceBoundaryAspect().SetWidth(
                    self.config.SELECTION_OUTLINE_WIDTH
                )
                drawer.FaceBoundaryAspect().SetTypeOfLine(
                    Aspect_TypeOfLine.Aspect_TOL_SOLID
                )

                self.display.Context.Display(ais_highlight, True)
                self.highlighted_faces[face_hash] = ais_highlight
                action = "Selected"

            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()
            root.update_idletasks()
            root.update()

            count = len(self.highlighted_faces)
            if self.selection_label:
                self.selection_label.config(
                    text=f"Selected: {count} face{'s' if count != 1 else ''}"
                )

            logger.info(f"{action} face (total: {count})")
            return True

        except Exception as e:
            logger.error(f"Error selecting face: {e}")
            return False

    def clear_all(self, root):
        """Clear all selected faces."""
        for ais_highlight in self.highlighted_faces.values():
            self.display.Context.Remove(ais_highlight, True)

        self.highlighted_faces.clear()
        self.face_parent_map.clear()
        self.face_to_part_map.clear()
        self.part_selected_faces.clear()

        # Clear selected faces in planar alignment manager
        if self.planar_alignment_manager:
            self.planar_alignment_manager.set_selected_faces({})

        self.display.Context.ClearSelected(True)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        if self.selection_label:
            self.selection_label.config(text="Selected: 0 faces")

        logger.info("Cleared all selections")

    def update_all_colors(self, root):
        """Update colors of all currently selected faces."""
        fill_color = self.color_manager.get_fill_quantity_color()
        outline_color = self.color_manager.get_outline_quantity_color()

        for ais_highlight in self.highlighted_faces.values():
            ais_highlight.SetColor(fill_color)
            ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)

            drawer = ais_highlight.Attributes()
            drawer.SetFaceBoundaryDraw(True)
            drawer.FaceBoundaryAspect().SetColor(outline_color)
            drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
            drawer.FaceBoundaryAspect().SetTypeOfLine(
                Aspect_TypeOfLine.Aspect_TOL_SOLID
            )

            self.display.Context.Redisplay(ais_highlight, True)

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        fill_rgb, fill_name = self.color_manager.get_current_fill_color()
        outline_rgb, outline_name = self.color_manager.get_current_outline_color()
        logger.info(f"\nSelection colors updated:")
        logger.info(f"  Fill: {fill_name} RGB{fill_rgb}")
        logger.info(f"  Outline: {outline_name} RGB{outline_rgb}\n")

    def get_selection_count(self) -> int:
        """Get number of currently selected faces."""
        return len(self.highlighted_faces)

    def update_all_transformations(self, root):
        """Update transformations of all selected faces to match their parent parts."""
        for face_hash, ais_highlight in self.highlighted_faces.items():
            if face_hash in self.face_parent_map:
                parent_ais = self.face_parent_map[face_hash]
                if parent_ais.HasTransformation():
                    ais_highlight.SetLocalTransformation(
                        parent_ais.LocalTransformation()
                    )
                else:
                    # Clear transformation if parent has none
                    ais_highlight.SetLocalTransformation(
                        parent_ais.LocalTransformation()
                    )
                self.display.Context.Redisplay(ais_highlight, True)

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

    def hide_selections_for_parts(self, ais_shapes_to_hide, root):
        """
        Hide selections for specific parts (when parts are hidden).
        Returns a dict of hidden selections for later restoration.
        """
        hidden_selections = {}
        faces_to_remove = []

        for face_hash, ais_highlight in list(self.highlighted_faces.items()):
            if face_hash in self.face_parent_map:
                parent_ais = self.face_parent_map[face_hash]
                if parent_ais in ais_shapes_to_hide:
                    # Store for later restoration
                    hidden_selections[face_hash] = {
                        "ais_highlight": ais_highlight,
                        "parent_ais": parent_ais,
                    }
                    # Hide the selection
                    self.display.Context.Remove(ais_highlight, False)
                    faces_to_remove.append(face_hash)

        # Remove from active selections
        for face_hash in faces_to_remove:
            del self.highlighted_faces[face_hash]

        # Update selection count label
        count = len(self.highlighted_faces)
        if self.selection_label:
            self.selection_label.config(
                text=f"Selected: {count} face{'s' if count != 1 else ''}"
            )

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()

        return hidden_selections

    def restore_hidden_selections(self, hidden_selections, root):
        """Restore previously hidden selections when parts become visible again."""
        for face_hash, selection_data in hidden_selections.items():
            ais_highlight = selection_data["ais_highlight"]
            # Restore the selection
            self.display.Context.Display(ais_highlight, False)
            self.highlighted_faces[face_hash] = ais_highlight

        # Update selection count label
        count = len(self.highlighted_faces)
        if self.selection_label:
            self.selection_label.config(
                text=f"Selected: {count} face{'s' if count != 1 else ''}"
            )

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()

    def select_largest_external_faces(self, parts_list: List[Tuple], root):
        """
        Select the largest correctly-oriented face of each part for CNC cutting.

        For laser-cut parts, selects the largest face that points away from the
        assembly center (external-facing for outer parts, internal-facing for inner parts).

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
            root: Tkinter root for UI updates
        """
        if not self.is_selection_mode:
            logger.warning(
                "Not in selection mode. Press 's' to enter selection mode first."
            )
            return

        # Clear existing selections first
        self.clear_all(root)

        selected_count = 0

        # Calculate assembly center for inside/outside determination
        assembly_origin = self._calculate_assembly_center(parts_list)

        # Get all solids for occlusion checking (entire assembly)
        all_solids = [s for s, _, _ in parts_list]

        for idx, (solid, color, ais_shape) in enumerate(parts_list):
            # Find all faces and their areas
            face_areas = []
            explorer = TopExp_Explorer(solid, TopAbs_FACE)

            while explorer.More():
                face = explorer.Current()
                props = GProp_GProps()
                brepgprop.SurfaceProperties(face, props)
                area = props.Mass()
                face_areas.append((area, face))
                explorer.Next()

            # Sort by area and take the two largest faces
            face_areas.sort(reverse=True, key=lambda x: x[0])

            if not face_areas:
                continue

            # Debug info
            logger.debug(
                f"  Part {idx+1}: {len(face_areas)} faces, top 2 by area: {[f'{a:.2f}' for a, _ in face_areas[:2]]}"
            )

            # Check the two largest faces to determine which is external
            selected_face = None
            selected_area = 0.0

            # Get part center for orientation checking
            part_props = GProp_GProps()
            brepgprop.VolumeProperties(solid, part_props)
            part_center = part_props.CentreOfMass()

            # We'll test up to 2 largest faces and score them
            best_score = -1.0
            face_candidates = []

            for face_idx, (area, face) in enumerate(face_areas[:2]):
                # Check if this face is external relative to the entire assembly
                is_external, debug_info, clear_count = (
                    self._is_face_external_to_assembly(face, all_solids)
                )

                if is_external:
                    # Calculate outward score: how well does the face point away from origin?
                    face_props = GProp_GProps()
                    brepgprop.SurfaceProperties(face, face_props)
                    face_center = face_props.CentreOfMass()

                    # Get face normal
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
                    normal = vec_u.Crossed(vec_v)

                    outward_score = 0.0
                    if normal.Magnitude() > 1e-7:
                        normal.Normalize()
                        # Vector from origin to face center
                        to_face = gp_Vec(assembly_origin, face_center)
                        if to_face.Magnitude() > 1e-7:
                            to_face.Normalize()
                            # Positive dot product means normal points away from origin (outward)
                            # Use max of normal and -normal to handle arbitrary normal direction
                            outward_score = max(
                                normal.Dot(to_face), -normal.Dot(to_face)
                            )

                    # Composite score: clearness (2 or 1) * 1000 + outward_score (0-1) * 100
                    # This prioritizes clearness first, then outward direction as tiebreaker
                    composite_score = clear_count * 1000 + outward_score * 100

                    face_candidates.append(
                        (
                            face,
                            area,
                            clear_count,
                            outward_score,
                            composite_score,
                            face_idx,
                            debug_info,
                        )
                    )
                    logger.debug(
                        f"    Face #{face_idx+1}: area={area:.2f} clearness={clear_count} outward={outward_score:.2f} score={composite_score:.1f} {debug_info}"
                    )
                else:
                    logger.debug(
                        f"    ✗ Skipped face #{face_idx+1}: area={area:.2f} (internal) {debug_info}"
                    )

            # Select the face with best composite score
            if face_candidates:
                # Sort by composite score (highest first)
                face_candidates.sort(key=lambda x: x[4], reverse=True)
                (
                    selected_face,
                    selected_area,
                    clearness,
                    outward,
                    score,
                    selected_idx,
                    selected_debug,
                ) = face_candidates[0]
                logger.debug(
                    f"    ✓ Selected face #{selected_idx+1}: area={selected_area:.2f} clearness={clearness} outward={outward:.2f} {selected_debug}"
                )

            # If neither of the two largest faces is external, fall back to largest
            if selected_face is None and face_areas:
                selected_area, selected_face = face_areas[0]
                logger.debug(
                    f"    Fallback: selected largest face area={selected_area:.2f}"
                )

            # Add the selected face to highlights
            if selected_face is not None:
                face_hash = selected_face.__hash__()

                # Only add if not already selected
                if face_hash not in self.highlighted_faces:
                    ais_highlight = AIS_Shape(selected_face)
                    ais_highlight.SetColor(self.color_manager.get_fill_quantity_color())
                    ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)
                    ais_highlight.SetDisplayMode(1)  # Shaded mode

                    # Copy transformation from parent if it has one
                    if ais_shape.HasTransformation():
                        ais_highlight.SetLocalTransformation(
                            ais_shape.LocalTransformation()
                        )

                    # Store the parent for transformation updates
                    self.face_parent_map[face_hash] = ais_shape

                    # Store face to part mapping and part's selected face
                    self.face_to_part_map[face_hash] = idx
                    self.part_selected_faces[idx] = selected_face

                    # Apply outline
                    drawer = ais_highlight.Attributes()
                    drawer.SetFaceBoundaryDraw(True)
                    drawer.FaceBoundaryAspect().SetColor(
                        self.color_manager.get_outline_quantity_color()
                    )
                    drawer.FaceBoundaryAspect().SetWidth(
                        self.config.SELECTION_OUTLINE_WIDTH
                    )
                    drawer.FaceBoundaryAspect().SetTypeOfLine(
                        Aspect_TypeOfLine.Aspect_TOL_SOLID
                    )

                    self.display.Context.Display(ais_highlight, True)
                    self.highlighted_faces[face_hash] = ais_highlight
                    selected_count += 1

        # Update display
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        # Update selection count label
        count = len(self.highlighted_faces)
        if self.selection_label:
            self.selection_label.config(
                text=f"Selected: {count} face{'s' if count != 1 else ''}"
            )

        # Update planar alignment manager with selected faces
        if self.planar_alignment_manager:
            self.planar_alignment_manager.set_selected_faces(self.part_selected_faces)

        logger.info(f"Selected {count} largest external faces (one per part)")

    def _calculate_assembly_center(self, parts_list: List[Tuple]) -> gp_Pnt:
        """Calculate the center point of the entire assembly."""
        total_x = 0.0
        total_y = 0.0
        total_z = 0.0
        count = 0

        for solid, _, _ in parts_list:
            props = GProp_GProps()
            brepgprop.VolumeProperties(solid, props)
            center = props.CentreOfMass()
            total_x += center.X()
            total_y += center.Y()
            total_z += center.Z()
            count += 1

        if count > 0:
            return gp_Pnt(total_x / count, total_y / count, total_z / count)
        return gp_Pnt(0, 0, 0)

    def _is_face_external_to_assembly(self, face, all_solids: List):
        """
        Check if a face is external to the assembly using raycast in both directions.

        Since face normal direction is arbitrary, we check both directions
        and return True if at least one direction is clear (external to the model).

        Args:
            face: The face to check
            all_solids: List of all solids in the assembly to check against

        Returns:
            Tuple of (is_external: bool, debug_info: str, clear_direction_count: int)
            - is_external: True if at least one direction is clear
            - debug_info: String describing raycast results
            - clear_direction_count: 0, 1, or 2 - number of clear directions (2 is best)
        """
        if not all_solids:
            return True, "", 2

        try:
            # Get face properties
            props = GProp_GProps()
            brepgprop.SurfaceProperties(face, props)
            face_center = props.CentreOfMass()

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

            # Get point and normal at middle of face
            pnt = gp_Pnt()
            vec_u = gp_Vec()
            vec_v = gp_Vec()
            surface.D1(u_mid, v_mid, pnt, vec_u, vec_v)

            # Calculate normal (cross product of tangent vectors)
            normal = vec_u.Crossed(vec_v)
            if normal.Magnitude() < 1e-7:
                return True, "", 2  # Can't determine, assume external

            normal.Normalize()

            # Check both directions (normal and -normal)
            # Use a dynamic threshold: at least 2.5x the material thickness, with a minimum of 5mm
            # This ensures we skip the opposite face of thin parts
            threshold = max(self.config.MATERIAL_THICKNESS_MM * 2.5, 5.0)
            hits_info = []
            clear_count = 0

            # Check BOTH directions fully (don't early return)
            for direction_multiplier in [1.0, -1.0]:
                ray_dir = gp_Dir(
                    normal.X() * direction_multiplier,
                    normal.Y() * direction_multiplier,
                    normal.Z() * direction_multiplier,
                )
                ray = gp_Lin(gp_Ax1(face_center, ray_dir))

                # Cast ray against all solids in assembly
                has_hit = False
                closest_hit_dist = None

                for solid in all_solids:
                    inter = BRepIntCurveSurface_Inter()
                    inter.Init(solid, ray, 1e-7)

                    # Check if there's any intersection in front
                    while inter.More():
                        w_param = inter.W()
                        # Skip intersections within material thickness to avoid detecting
                        # the opposite face of thin parts. Use 2x thickness for safety.
                        if w_param > threshold:
                            has_hit = True
                            if closest_hit_dist is None or w_param < closest_hit_dist:
                                closest_hit_dist = w_param
                        inter.Next()

                    if has_hit:
                        break

                dir_name = "+normal" if direction_multiplier > 0 else "-normal"
                if has_hit:
                    hits_info.append(f"{dir_name}:hit@{closest_hit_dist:.1f}mm")
                else:
                    hits_info.append(f"{dir_name}:clear")
                    clear_count += 1

            # Face is external if at least one direction is clear
            is_external = clear_count > 0
            return is_external, f"[{', '.join(hits_info)}]", clear_count

        except Exception as e:
            # If we can't determine, assume it's external (conservative approach)
            # print(f"Warning: Could not determine if face is external: {e}")
            return True, f"[error: {e}]", 2
