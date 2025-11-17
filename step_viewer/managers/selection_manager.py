"""
Face selection state management using AIS_ColoredShape for highlighting.
"""

from typing import Dict, List, Tuple

from OCC.Core.AIS import AIS_ColoredShape, AIS_Shape
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Lin, gp_Ax1
from OCC.Core.BRepIntCurveSurface import BRepIntCurveSurface_Inter
import hashlib

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

        # Simple selection system: faces are either selected (orange) or unselected (base color)
        # Maps face hash to tuple of (parent_AIS_ColoredShape, original_color)
        self.selected_faces: Dict[int, Tuple[AIS_ColoredShape, object]] = {}

        # Map highlighted face hash to the original TopoDS_Face object
        self.face_to_faceobj_map: Dict[int, object] = {}
        # Stable 64-bit fingerprint (decimal string) for each face hash
        self.face_fingerprint_map: Dict[int, str] = {}
        self.face_to_part_map: Dict[int, int] = {}  # Maps face hash to part index
        self.part_selected_faces: Dict[int, any] = (
            {}
        )  # Maps part index to selected face object
        # Map AIS_ColoredShape object itself to its base color (for restoring after selection)
        # Using the object as key instead of id() to avoid Python wrapper issues
        self.ais_base_colors: Dict = {}
        self.selection_label = None
        self.planar_alignment_manager = None  # Reference to planar alignment manager

    def set_selection_label(self, label):
        """Set reference to the selection count label."""
        self.selection_label = label

    def set_planar_alignment_manager(self, manager):
        """Set reference to planar alignment manager."""
        self.planar_alignment_manager = manager

    def register_part_base_color(self, ais_shape, color):
        """
        Register the base color for a part's AIS_ColoredShape.
        Called when parts are initially displayed.

        Args:
            ais_shape: The AIS_ColoredShape object
            color: The Quantity_Color base color
        """
        # Use the AIS object itself as key (more stable than id())
        self.ais_base_colors[ais_shape] = color
        logger.debug(f"Registered base color for AIS object: {ais_shape}")

    def _get_selected_color(self):
        """Get the highlight color for selected faces (orange or changeable via color_manager)."""
        color = self.color_manager.get_fill_quantity_color()
        rgb, name = self.color_manager.get_current_fill_color()
        logger.debug(f"Selection color: {name} RGB{rgb}")
        return color

    def toggle_mode(self) -> bool:
        """Toggle between navigation and selection mode. Returns new mode state.

        Selected faces remain visible and highlighted regardless of mode.
        """
        self.is_selection_mode = not self.is_selection_mode
        return self.is_selection_mode

    def select_face_at_position(self, x: int, y: int, view, root) -> bool:
        """
        Toggle selection of a face at the given screen position.

        Click to select (orange highlight), click again to deselect (base color).

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

            detected_interactive = self.display.Context.DetectedInteractive()
            face_hash = detected_shape.__hash__()

            if detected_interactive is None:
                return False

            # Get the parent AIS_ColoredShape
            parent_ais = AIS_ColoredShape.DownCast(detected_interactive)
            if parent_ais is None:
                parent_ais = AIS_Shape.DownCast(detected_interactive)
                if parent_ais is None:
                    return False

            # Get original color from base color map
            original_color = self.ais_base_colors.get(parent_ais)
            if original_color is None:
                logger.warning(f"No base color registered for AIS object {parent_ais}")
                from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                original_color = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)

            # Store face object if not already stored
            if face_hash not in self.face_to_faceobj_map:
                self.face_to_faceobj_map[face_hash] = detected_shape
                try:
                    fp = self._face_fingerprint(detected_shape)
                    self.face_fingerprint_map[face_hash] = fp
                    logger.debug(f"    selection fingerprint={fp}")
                except Exception:
                    pass

            # Toggle selection: if already selected, deselect; otherwise select
            if face_hash in self.selected_faces:
                # Deselect: restore original color
                parent_ais.SetCustomColor(detected_shape, original_color)
                del self.selected_faces[face_hash]
                action = "Deselected"
            else:
                # Select: apply highlight color
                self.selected_faces[face_hash] = (parent_ais, original_color)
                parent_ais.SetCustomColor(detected_shape, self._get_selected_color())
                action = "Selected"

            # Redisplay the parent object to apply the custom color immediately
            self.display.Context.Redisplay(parent_ais, True)
            # Clear OCCT's automatic highlighting so our custom colors take precedence
            self.display.Context.ClearDetected()
            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()
            root.update_idletasks()
            root.update()

            total_selected = len(self.selected_faces)
            if self.selection_label:
                self.selection_label.config(
                    text=f"Selected: {total_selected} face{'s' if total_selected != 1 else ''}"
                )

            logger.info(f"{action} face (total: {total_selected})")
            return True

        except Exception as e:
            logger.error(f"Error selecting face: {e}")
            return False

    def inspect_face_at_position(self, x: int, y: int, view, parts_list=None) -> bool:
        """
        Inspect (do not select) a face at the given screen position and log
        part index, per-part face id and face hash to the console.

        Args:
            x, y: screen coordinates
            view: the OCC view object
            parts_list: optional list of (solid, color, ais_shape) tuples to
                        resolve part indices locally

        Returns:
            True if a face was detected and logged, False otherwise
        """
        try:
            self.display.Context.MoveTo(x, y, view, True)

            if not self.display.Context.HasDetected():
                return False

            detected_shape = self.display.Context.DetectedShape()
            if detected_shape.IsNull():
                return False

            detected_interactive = self.display.Context.DetectedInteractive()
            if detected_interactive is None:
                return False

            # Get the parent AIS object
            parent_ais = AIS_ColoredShape.DownCast(detected_interactive)
            if parent_ais is None:
                parent_ais = AIS_Shape.DownCast(detected_interactive)
                if parent_ais is None:
                    return False

            # Compute a face hash (stable within run)
            try:
                face_hash = detected_shape.__hash__()
            except Exception:
                face_hash = id(detected_shape)

            # Try to compute a per-part face id if parts_list given
            part_idx = None
            face_id = None
            try:
                if parts_list is not None:
                    # find the part index for this AIS object
                    for idx, (solid, _color, ais_shape) in enumerate(parts_list):
                        if ais_shape == parent_ais:
                            part_idx = idx
                            # enumerate faces within this solid to find per-part index
                            exp = TopExp_Explorer(solid, TopAbs_FACE)
                            num = 0
                            while exp.More():
                                num += 1
                                if exp.Current().IsSame(detected_shape):
                                    face_id = num
                                    break
                                exp.Next()
                            break
                # fallback: check any stored mapping
                if part_idx is None:
                    part_idx = self.face_to_part_map.get(face_hash)

                # Try to get stable fingerprint if available
                fp = self.face_fingerprint_map.get(face_hash)
                if not fp:
                    try:
                        fp = self._face_fingerprint(detected_shape)
                        # do not store here, just peek
                    except Exception:
                        fp = None
                # Also compute a global face number (1-based) across all parts when parts_list provided
                global_face_number = None
                if parts_list is not None:
                    try:
                        global_face_map = {}
                        global_idx = 1
                        for s, _c, _a in parts_list:
                            exp_g = TopExp_Explorer(s, TopAbs_FACE)
                            while exp_g.More():
                                f = exp_g.Current()
                                try:
                                    key = f.__hash__()
                                except Exception:
                                    key = id(f)
                                # Only set if not already set (first occurrence)
                                if key not in global_face_map:
                                    global_face_map[key] = global_idx
                                global_idx += 1
                                exp_g.Next()

                        # lookup by same key method
                        try:
                            detected_key = detected_shape.__hash__()
                        except Exception:
                            detected_key = id(detected_shape)

                        global_face_number = global_face_map.get(detected_key)
                    except Exception:
                        global_face_number = None

            except Exception:
                part_idx = None
                face_id = None
                fp = None

            # Compute UI and file part numbers (1-based) for clearer logging
            ui_part_number = None
            file_part_number = None
            try:
                if part_idx is not None:
                    # UI shows parts as 1-based "Part {i+1}"
                    ui_part_number = part_idx + 1
                    # File part number 0 based
                    file_part_number = part_idx
            except Exception:
                ui_part_number = None
                file_part_number = None

            # Log requested information including both UI and file part numbers
            logger.info(
                f"Clicked face -> ui_part: {ui_part_number}, file_part: {file_part_number}, face_id: {face_id}, global_face: {global_face_number}, face_hash: {face_hash}, fingerprint: {fp}"
            )

            # Clear OCCT detection highlighting
            self.display.Context.ClearDetected()
            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()

            return True

        except Exception as e:
            logger.error(f"Error inspecting face: {e}")
            return False

    def clear_all(self, root):
        """Clear all selected faces by restoring original colors."""
        # Restore original colors for all selected faces
        for face_hash, (parent_ais, original_color) in self.selected_faces.items():
            try:
                face_obj = self.face_to_faceobj_map.get(face_hash)
                if face_obj is not None and parent_ais is not None:
                    parent_ais.SetCustomColor(face_obj, original_color)
                    self.display.Context.Redisplay(parent_ais, True)
            except Exception as e:
                logger.warning(f"Could not restore color for face {face_hash}: {e}")

        self.selected_faces.clear()
        self.face_to_faceobj_map.clear()
        self.face_fingerprint_map.clear()
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
        """Update colors of all selected faces (when cycling through colors via '1' key)."""
        fill_color = self._get_selected_color()

        # Update all selected faces with the new color
        redrawn_objects = set()
        for face_hash, (parent_ais, _) in self.selected_faces.items():
            try:
                face_obj = self.face_to_faceobj_map.get(face_hash)
                if face_obj is not None and parent_ais is not None:
                    parent_ais.SetCustomColor(face_obj, fill_color)
                    # Only redisplay each object once (in case multiple faces on same object)
                    if id(parent_ais) not in redrawn_objects:
                        self.display.Context.Redisplay(parent_ais, True)
                        redrawn_objects.add(id(parent_ais))
            except Exception as e:
                logger.warning(f"Could not update color for face {face_hash}: {e}")

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        fill_rgb, fill_name = self.color_manager.get_current_fill_color()
        logger.info(f"\nSelection color updated: {fill_name} RGB{fill_rgb}\n")

    def get_selection_count(self) -> int:
        """Get number of currently selected faces."""
        return len(self.selected_faces)


    def hide_selections_for_parts(self, ais_shapes_to_hide, root):
        """
        Hide selections for specific parts (when parts are hidden).
        Returns a dict of hidden selections for later restoration.
        """
        hidden_selections = {}
        faces_to_remove = []

        # Hide selected faces that belong to hidden parts
        for face_hash, (parent_ais, original_color) in list(self.selected_faces.items()):
            if parent_ais in ais_shapes_to_hide:
                face_obj = self.face_to_faceobj_map.get(face_hash)
                if face_obj is not None:
                    hidden_selections[face_hash] = {
                        "parent_ais": parent_ais,
                        "original_color": original_color,
                        "face_obj": face_obj,
                    }
                    # Restore original color to hide the highlight
                    parent_ais.SetCustomColor(face_obj, original_color)
                    self.display.Context.Redisplay(parent_ais, True)
                    faces_to_remove.append(face_hash)

        # Remove from active selections
        for face_hash in faces_to_remove:
            del self.selected_faces[face_hash]

        # Update selection count label
        count = len(self.selected_faces)
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
        redrawn_objects = set()
        for face_hash, selection_data in hidden_selections.items():
            parent_ais = selection_data["parent_ais"]
            face_obj = selection_data["face_obj"]
            original_color = selection_data["original_color"]

            try:
                # Restore as selected with highlight color
                self.selected_faces[face_hash] = (parent_ais, original_color)
                parent_ais.SetCustomColor(face_obj, self._get_selected_color())
                # Only redisplay each object once (in case multiple faces on same object)
                if id(parent_ais) not in redrawn_objects:
                    self.display.Context.Redisplay(parent_ais, True)
                    redrawn_objects.add(id(parent_ais))
            except Exception as e:
                logger.warning(f"Could not restore selection for face {face_hash}: {e}")

        # Update selection count label
        count = len(self.selected_faces)
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

        # Build a global face index map (1-based) across the provided parts_list
        # so we can report a global STEP-style face number that matches a full
        # dump of the assembly's faces. We map by the Python hash of the face
        # object (stable within this run) to its global index.
        global_face_map = {}
        global_idx = 1
        for s, _, _ in parts_list:
            exp_g = TopExp_Explorer(s, TopAbs_FACE)
            while exp_g.More():
                f = exp_g.Current()
                try:
                    global_face_map[f.__hash__()] = global_idx
                except Exception:
                    global_face_map[id(f)] = global_idx
                global_idx += 1
                exp_g.Next()

        # Build a global face index map (1-based) across the provided parts_list
        # so we can report a global STEP-style face number that matches a full
        # dump of the assembly's faces. We map by the Python hash of the face
        # object (stable within this run) to its global index.
        global_face_map = {}
        global_idx = 1
        for s, _, _ in parts_list:
            exp_g = TopExp_Explorer(s, TopAbs_FACE)
            while exp_g.More():
                f = exp_g.Current()
                try:
                    global_face_map[f.__hash__()] = global_idx
                except Exception:
                    # fallback to using id() if __hash__ fails
                    global_face_map[id(f)] = global_idx
                global_idx += 1
                exp_g.Next()

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
                # Determine the face index in the STEP/solids ordering for debug
                try:
                    # per-solid index (1-based)
                    step_face_number = None
                    explorer_num = TopExp_Explorer(solid, TopAbs_FACE)
                    num = 0
                    while explorer_num.More():
                        num += 1
                        if explorer_num.Current().IsSame(selected_face):
                            step_face_number = num
                            break
                        explorer_num.Next()
                except Exception:
                    step_face_number = None

                try:
                    try:
                        face_hash = selected_face.__hash__()
                    except Exception:
                        face_hash = id(selected_face)
                    global_face_number = global_face_map.get(face_hash, None)
                except Exception:
                    face_hash = None
                    global_face_number = None

                logger.info(
                    f"    -> Selected STEP face number (per-part): {step_face_number} (part index {idx}), global: {global_face_number}, face_hash: {face_hash}"
                )
                # Compute a stable fingerprint for cross-run correlation and store mapping
                try:
                    fp = self._face_fingerprint(selected_face)
                    try:
                        self.face_fingerprint_map[face_hash] = fp
                        self.face_to_faceobj_map[face_hash] = selected_face
                    except Exception:
                        pass
                    logger.info(f"        fingerprint={fp}")
                except Exception:
                    fp = None
                face_hash = selected_face.__hash__()

                # Only add if not already selected
                is_already_selected = face_hash in self.selected_faces

                if not is_already_selected:
                    # Use SetCustomColor on parent AIS_ColoredShape instead of creating new shape
                    # Get the original color from the base color map
                    original_color = self.ais_base_colors.get(ais_shape)
                    if original_color is None:
                        logger.warning(f"No base color registered for AIS object {ais_shape}")
                        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                        original_color = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)

                    # Apply highlight color to the selected face
                    ais_shape.SetCustomColor(selected_face, self._get_selected_color())
                    # Redisplay to apply the color (deduplicate later if needed)
                    self.display.Context.Redisplay(ais_shape, True)

                    # Store the parent and original color in selected faces
                    self.selected_faces[face_hash] = (ais_shape, original_color)

                    # Store face to part mapping and part's selected face
                    self.face_to_part_map[face_hash] = idx
                    self.part_selected_faces[idx] = selected_face

                    # Store face object for later restoration
                    self.face_to_faceobj_map[face_hash] = selected_face

                    selected_count += 1

        # Update display with clear detected to avoid OCCT's automatic highlighting
        self.display.Context.ClearDetected()
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        # Update selection count label
        count = len(self.selected_faces)
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

    def _face_fingerprint(self, face) -> str:
        """Compute a stable 64-bit fingerprint for a face.

        The fingerprint is derived from: area, centroid coordinates, number of
        wires and edges. The data is hashed with SHA1 and the first 8 bytes
        are interpreted as an unsigned 64-bit integer and returned as a
        decimal string. This is stable across runs (given the same geometry)
        and suitable for correlating dumps and runtime selections.
        """
        try:
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

            # Bundle into a deterministic byte string
            s = f"area={area:.6f};centroid={cx:.6f},{cy:.6f},{cz:.6f};wires={wires};edges={edges}"
            h = hashlib.sha1(s.encode("utf8")).digest()[:8]
            # unsigned 64-bit integer
            val = int.from_bytes(h, byteorder="big", signed=False)
            return str(val)
        except Exception:
            # Fallback to Python hash string (not stable across runs)
            try:
                return str(face.__hash__())
            except Exception:
                return str(id(face))

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
