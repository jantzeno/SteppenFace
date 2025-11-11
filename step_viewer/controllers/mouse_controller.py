from ..managers.selection_manager import SelectionManager


class MouseController:
    """Handles main application mouse events for navigation and face selection."""

    def __init__(self, view, display, selection_manager: SelectionManager, root):
        self.view = view
        self.display = display
        self.selection_manager = selection_manager
        self.root = root
        self.start_x = 0
        self.start_y = 0
        self.button = None

    def on_left_press(self, event):
        """Handle left mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 1

        if not self.selection_manager.is_selection_mode:
            self.view.StartRotation(event.x, event.y)

    def on_left_motion(self, event):
        """Handle left mouse button drag."""
        if self.button == 1 and not self.selection_manager.is_selection_mode:
            self.view.Rotation(event.x, event.y)
            self.display.Context.UpdateCurrentViewer()
            self.root.update_idletasks()

    def on_right_press(self, event):
        """Handle right mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 3

    def on_right_motion(self, event):
        """Handle right mouse button drag."""
        if self.button == 3:
            dx = event.x - self.start_x
            dy = self.start_y - event.y
            self.view.Pan(dx, dy)
            self.display.Context.UpdateCurrentViewer()
            self.root.update_idletasks()
            self.start_x = event.x
            self.start_y = event.y

    def on_release(self, event):
        """Handle mouse button release."""
        # Check if this was a click (not a drag) in selection mode
        if self.button == 1 and self.selection_manager.is_selection_mode:
            dx = abs(event.x - self.start_x)
            dy = abs(event.y - self.start_y)
            if dx < 5 and dy < 5:
                self.selection_manager.select_face_at_position(
                    event.x, event.y, self.view, self.root
                )

        self.button = None

    def on_wheel(self, event):
        """Handle mouse wheel zoom."""
        if event.delta > 0 or event.num == 4:
            self.display.ZoomFactor(1.1)
        elif event.delta < 0 or event.num == 5:
            self.display.ZoomFactor(0.9)
