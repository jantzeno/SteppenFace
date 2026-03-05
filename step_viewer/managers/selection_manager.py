"""
Face selection state management using AIS_ColoredShape for highlighting.
"""

from typing import Dict, List, Tuple

from OCC.Core.AIS import AIS_ColoredShape, AIS_Shape
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE
from OCC.Core.gp import gp_Pnt, gp_Vec
import hashlib

from ..managers.planar_alignment_manager import PlanarAlignmentManager
from .part_manager import PartManager
from ..config import ViewerConfig
from .color_manager import ColorManager
from .log_manager import logger


class SelectionManager:
    """Manages face selection state and highlighting."""

    def __init__(
        self,
        display,
        color_manager: ColorManager,
        part_manager: PartManager,
        planar_alignment_manager: PlanarAlignmentManager,
        config: ViewerConfig,
    ):
        self.display = display
        self.color_manager = color_manager
        self.planar_alignment_manager = planar_alignment_manager
        self.selection_label = None
        self.config = config
        # Optional PartManager for precomputed face metadata
        self.part_manager = part_manager
        self.is_selection_mode = False

        # Simple selection system: faces are either selected (orange) or unselected (base color)
        # Maps fingerprint to tuple of (parent_AIS_ColoredShape, original_color, Face namedtuple)
        self.selected_faces: Dict[str, Tuple[AIS_ColoredShape, object]] = {}

        # Map fingerprint to the Face namedtuple
        self.face_by_fingerprint: Dict[str, object] = {}

        # Map part_index to selected Face for planar alignment
        self.part_selected_faces: Dict[int, object] = {}
        self.ais_base_colors: Dict = {}

    def set_selection_label(self, label):
        """Set reference to the selection count label."""
        self.selection_label = label

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

            if detected_interactive is None:
                return False

            # Get the parent AIS_ColoredShape
            parent_ais = AIS_ColoredShape.DownCast(detected_interactive)
            if parent_ais is None:
                parent_ais = AIS_Shape.DownCast(detected_interactive)
                if parent_ais is None:
                    return False

            # Find the Face namedtuple from PartManager
            face = self.part_manager.find_face(detected_shape)
            if face is None:
                return False

            fingerprint = face.fingerprint

            # Get original color from base color map
            original_color = self.ais_base_colors.get(parent_ais)
            if original_color is None:
                logger.warning(f"No base color registered for AIS object {parent_ais}")
                from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

                original_color = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)

            logger.debug(f"    selection fingerprint={fingerprint}")

            # Toggle selection: if already selected, deselect; otherwise select
            if fingerprint in self.selected_faces:
                # Deselect: restore original color
                parent_ais.SetCustomColor(detected_shape, original_color)
                del self.selected_faces[fingerprint]
                action = "Deselected"
            else:
                # Select: apply highlight color
                self.selected_faces[fingerprint] = (parent_ais, original_color)
                self.face_by_fingerprint[fingerprint] = face
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
            parts_list: optional list of Part namedtuples to
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

            # Find the Face namedtuple
            face = self.part_manager.find_face(detected_shape)

            # Try to compute a per-part face id if parts_list given
            part_idx = None
            face_id = None
            fp = None
            global_face_number = None

            try:
                if face is not None:
                    part_idx = face.part_index
                    fp = face.fingerprint
                    global_face_number = face.global_index
                    face_id = face.part_face_index

            except Exception:
                part_idx = None
                face_id = None
                fp = None
                global_face_number = None

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
                f"Clicked face -> ui_part: {ui_part_number}, file_part: {file_part_number}, part_face_id: {face_id}, global_face: {global_face_number}, fingerprint: {fp}"
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
        for fingerprint, (parent_ais, original_color) in self.selected_faces.items():
            try:
                face = self.face_by_fingerprint.get(fingerprint)
                if face is not None and parent_ais is not None:
                    parent_ais.SetCustomColor(face.shape, original_color)
                    self.display.Context.Redisplay(parent_ais, True)
            except Exception as e:
                logger.warning(f"Could not restore color for face {fingerprint}: {e}")

        self.selected_faces.clear()
        self.face_by_fingerprint.clear()
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
        for fingerprint, (parent_ais, _) in self.selected_faces.items():
            try:
                face = self.face_by_fingerprint.get(fingerprint)
                if face is not None and parent_ais is not None:
                    parent_ais.SetCustomColor(face.shape, fill_color)
                    # Only redisplay each object once (in case multiple faces on same object)
                    if id(parent_ais) not in redrawn_objects:
                        self.display.Context.Redisplay(parent_ais, True)
                        redrawn_objects.add(id(parent_ais))
            except Exception as e:
                logger.warning(f"Could not update color for face {fingerprint}: {e}")

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
        for fingerprint, (parent_ais, original_color) in list(
            self.selected_faces.items()
        ):
            if parent_ais in ais_shapes_to_hide:
                face = self.face_by_fingerprint.get(fingerprint)
                if face is not None:
                    hidden_selections[fingerprint] = {
                        "parent_ais": parent_ais,
                        "original_color": original_color,
                        "face": face,
                    }
                    # Restore original color to hide the highlight
                    parent_ais.SetCustomColor(face.shape, original_color)
                    self.display.Context.Redisplay(parent_ais, True)
                    faces_to_remove.append(fingerprint)

        # Remove from active selections
        for fingerprint in faces_to_remove:
            del self.selected_faces[fingerprint]

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
        for fingerprint, selection_data in hidden_selections.items():
            parent_ais = selection_data["parent_ais"]
            face = selection_data["face"]
            original_color = selection_data["original_color"]

            try:
                # Restore as selected with highlight color
                self.selected_faces[fingerprint] = (parent_ais, original_color)
                self.face_by_fingerprint[fingerprint] = face
                parent_ais.SetCustomColor(face.shape, self._get_selected_color())
                # Only redisplay each object once (in case multiple faces on same object)
                if id(parent_ais) not in redrawn_objects:
                    self.display.Context.Redisplay(parent_ais, True)
                    redrawn_objects.add(id(parent_ais))
            except Exception as e:
                logger.warning(
                    f"Could not restore selection for face {fingerprint}: {e}"
                )

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
            parts_list: List of Part namedtuples
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

        for idx, part in enumerate(parts_list):
            # Find all faces and their areas from the Face namedtuples
            face_areas = []
            for face in part.faces:
                face_areas.append((face.area, face))

            # Sort by area and take the two largest faces
            face_areas.sort(reverse=True, key=lambda x: x[0])

            if not face_areas:
                continue

            # Debug info
            logger.debug(
                f"  Part {idx+1}: {len(face_areas)} faces, top 2 by area: {[f'{a:.2f}' for a, _ in face_areas[:2]]}"
            )

            selected_face = None
            selected_area = 0.0

            if len(face_areas) == 1:
                # Only one face, select it
                selected_area, selected_face = face_areas[0]
            elif len(face_areas) >= 2:
                area1, face1 = face_areas[0]
                area2, face2 = face_areas[1]

                # For sheet metal: the two largest faces are top/bottom.
                # Pick the one whose normal points more outward from assembly center.
                score1 = self._outward_score(face1, assembly_origin)
                score2 = self._outward_score(face2, assembly_origin)

                # If largest face is significantly bigger (>10% more area), just use it
                if area1 > area2 * 1.1:
                    selected_face = face1
                    selected_area = area1
                    logger.debug(
                        f"    Selected largest face: area={area1:.2f} (>10% bigger than #2)"
                    )
                else:
                    # Areas are close — pick by outward score
                    if score1 >= score2:
                        selected_face = face1
                        selected_area = area1
                    else:
                        selected_face = face2
                        selected_area = area2
                    logger.debug(
                        f"    Selected by outward score: face1={score1:.3f} face2={score2:.3f}, chose {'#1' if score1 >= score2 else '#2'}"
                    )

            # Add the selected face to highlights
            if selected_face is not None:
                # selected_face is now a Face namedtuple
                fingerprint = selected_face.fingerprint
                global_face_number = selected_face.global_index

                logger.info(
                    f"    -> Selected face (per-part): {selected_face.part_index + 1} (part index {idx}), global: {global_face_number}"
                )
                logger.info(f"        fingerprint={fingerprint}")

                # Only add if not already selected
                is_already_selected = fingerprint in self.selected_faces

                if not is_already_selected:
                    # Use SetCustomColor on parent AIS_ColoredShape instead of creating new shape
                    # Get the original color from the base color map
                    original_color = self.ais_base_colors.get(part.ais_colored_shape)
                    if original_color is None:
                        logger.warning(
                            f"No base color registered for AIS object {part.ais_colored_shape}"
                        )
                        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

                        original_color = Quantity_Color(0.5, 0.5, 0.5, Quantity_TOC_RGB)

                    # Apply highlight color to the selected face
                    part.ais_colored_shape.SetCustomColor(
                        selected_face.shape, self._get_selected_color()
                    )
                    # Redisplay to apply the color (deduplicate later if needed)
                    self.display.Context.Redisplay(part.ais_colored_shape, True)

                    # Store the parent and original color in selected faces
                    self.selected_faces[fingerprint] = (
                        part.ais_colored_shape,
                        original_color,
                    )

                    # Store Face namedtuple for later use
                    self.face_by_fingerprint[fingerprint] = selected_face

                    # Store part's selected Face for planar alignment
                    self.part_selected_faces[idx] = selected_face

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
        """Calculate the center point of the entire assembly using cached face centroids."""
        total_x = 0.0
        total_y = 0.0
        total_z = 0.0
        count = 0

        for part in parts_list:
            if part.faces:
                largest = max(part.faces, key=lambda f: f.area)
                total_x += largest.centroid[0]
                total_y += largest.centroid[1]
                total_z += largest.centroid[2]
                count += 1

        if count > 0:
            return gp_Pnt(total_x / count, total_y / count, total_z / count)
        return gp_Pnt(0, 0, 0)

    @staticmethod
    def _outward_score(face_nt, assembly_origin: gp_Pnt) -> float:
        """Score how much a face normal points outward from the assembly center.

        Returns a value in [0, 1] where 1 means the normal is perfectly aligned
        with the vector from assembly center to face centroid.
        """
        nv = gp_Vec(face_nt.normal[0], face_nt.normal[1], face_nt.normal[2])
        if nv.Magnitude() < 1e-7:
            return 0.0
        nv.Normalize()
        fc = gp_Pnt(face_nt.centroid[0], face_nt.centroid[1], face_nt.centroid[2])
        to_face = gp_Vec(assembly_origin, fc)
        if to_face.Magnitude() < 1e-7:
            return 0.0
        to_face.Normalize()
        # Use max of both directions since face normal orientation is arbitrary
        return max(nv.Dot(to_face), -nv.Dot(to_face))
