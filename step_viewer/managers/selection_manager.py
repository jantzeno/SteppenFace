"""
Face selection state management.
"""

from typing import Dict

from OCC.Core.AIS import AIS_Shape
from OCC.Core.Aspect import Aspect_TypeOfLine

from ..config import ViewerConfig
from .color_manager import ColorManager


class SelectionManager:
    """Manages face selection state and highlighting."""

    def __init__(self, display, color_manager: ColorManager, config: ViewerConfig):
        self.display = display
        self.color_manager = color_manager
        self.config = config
        self.is_selection_mode = False
        self.highlighted_faces: Dict[int, AIS_Shape] = {}
        self.face_parent_map: Dict[int, AIS_Shape] = {}  # Maps face hash to parent AIS_Shape
        self.selection_label = None

    def set_selection_label(self, label):
        """Set reference to the selection count label."""
        self.selection_label = label

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
                            ais_highlight.SetLocalTransformation(parent_ais.LocalTransformation())

                drawer = ais_highlight.Attributes()
                drawer.SetFaceBoundaryDraw(True)
                drawer.FaceBoundaryAspect().SetColor(self.color_manager.get_outline_quantity_color())
                drawer.FaceBoundaryAspect().SetWidth(self.config.SELECTION_OUTLINE_WIDTH)
                drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

                self.display.Context.Display(ais_highlight, True)
                self.highlighted_faces[face_hash] = ais_highlight
                action = "Selected"

            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()
            root.update_idletasks()
            root.update()

            count = len(self.highlighted_faces)
            if self.selection_label:
                self.selection_label.config(text=f"Selected: {count} face{'s' if count != 1 else ''}")

            print(f"{action} face (total: {count})")
            return True

        except Exception as e:
            print(f"Error selecting face: {e}")
            return False

    def clear_all(self, root):
        """Clear all selected faces."""
        for ais_highlight in self.highlighted_faces.values():
            self.display.Context.Remove(ais_highlight, True)

        self.highlighted_faces.clear()
        self.display.Context.ClearSelected(True)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        if self.selection_label:
            self.selection_label.config(text="Selected: 0 faces")

        print("Cleared all selections")

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
            drawer.FaceBoundaryAspect().SetTypeOfLine(Aspect_TypeOfLine.Aspect_TOL_SOLID)

            self.display.Context.Redisplay(ais_highlight, True)

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
        root.update()

        fill_rgb, fill_name = self.color_manager.get_current_fill_color()
        outline_rgb, outline_name = self.color_manager.get_current_outline_color()
        print(f"\nSelection colors updated:")
        print(f"  Fill: {fill_name} RGB{fill_rgb}")
        print(f"  Outline: {outline_name} RGB{outline_rgb}\n")

    def get_selection_count(self) -> int:
        """Get number of currently selected faces."""
        return len(self.highlighted_faces)

    def update_all_transformations(self, root):
        """Update transformations of all selected faces to match their parent parts."""
        for face_hash, ais_highlight in self.highlighted_faces.items():
            if face_hash in self.face_parent_map:
                parent_ais = self.face_parent_map[face_hash]
                if parent_ais.HasTransformation():
                    ais_highlight.SetLocalTransformation(parent_ais.LocalTransformation())
                else:
                    # Clear transformation if parent has none
                    ais_highlight.SetLocalTransformation(parent_ais.LocalTransformation())
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
                        'ais_highlight': ais_highlight,
                        'parent_ais': parent_ais
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
            self.selection_label.config(text=f"Selected: {count} face{'s' if count != 1 else ''}")

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()

        return hidden_selections

    def restore_hidden_selections(self, hidden_selections, root):
        """Restore previously hidden selections when parts become visible again."""
        for face_hash, selection_data in hidden_selections.items():
            ais_highlight = selection_data['ais_highlight']
            # Restore the selection
            self.display.Context.Display(ais_highlight, False)
            self.highlighted_faces[face_hash] = ais_highlight

        # Update selection count label
        count = len(self.highlighted_faces)
        if self.selection_label:
            self.selection_label.config(text=f"Selected: {count} face{'s' if count != 1 else ''}")

        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()
        root.update_idletasks()
