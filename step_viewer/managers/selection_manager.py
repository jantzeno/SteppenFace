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

            face_hash = detected_shape.__hash__()

            if face_hash in self.highlighted_faces:
                # Deselect
                ais_highlight = self.highlighted_faces[face_hash]
                self.display.Context.Remove(ais_highlight, True)
                del self.highlighted_faces[face_hash]
                action = "Deselected"
            else:
                # Select
                ais_highlight = AIS_Shape(detected_shape)
                ais_highlight.SetColor(self.color_manager.get_fill_quantity_color())
                ais_highlight.SetTransparency(self.config.SELECTION_TRANSPARENCY)

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
