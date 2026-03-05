from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax1, gp_Vec

from ..managers.selection_manager import SelectionManager
from ..managers.part_manager import PartManager

ORBIT_SENSITIVITY = 0.003  # radians per pixel
PAN_SCALE = 0.002  # pan speed relative to camera distance


class MouseController:
    """Handles main application mouse events for navigation and face selection."""

    def __init__(
        self,
        view,
        display,
        parts_manager: PartManager,
        selection_manager: SelectionManager,
        root,
    ):
        self.view = view
        self.display = display
        self.part_manager = parts_manager
        self.selection_manager = selection_manager
        self.root = root
        self.start_x = 0
        self.start_y = 0
        self.button = None

    def _orbit(self, dx, dy):
        """Orbit the camera around its center using direct camera manipulation."""
        cam = self.display.View.Camera()
        eye = cam.Eye()
        center = cam.Center()
        up = cam.Up()

        # Horizontal rotation: around the up vector
        if dx != 0:
            ax_yaw = gp_Ax1(center, gp_Dir(up.X(), up.Y(), up.Z()))
            trsf_yaw = gp_Trsf()
            trsf_yaw.SetRotation(ax_yaw, -dx * ORBIT_SENSITIVITY)
            eye = eye.Transformed(trsf_yaw)

        # Compute side (right) vector from direction and up
        dir_vec = gp_Vec(eye, center)
        up_vec = gp_Vec(up.X(), up.Y(), up.Z())
        side = dir_vec.Crossed(up_vec)
        if side.Magnitude() > 1e-10:
            side.Normalize()

            # Vertical rotation: around the side vector
            if dy != 0:
                ax_pitch = gp_Ax1(center, gp_Dir(side))
                trsf_pitch = gp_Trsf()
                trsf_pitch.SetRotation(ax_pitch, -dy * ORBIT_SENSITIVITY)
                eye = eye.Transformed(trsf_pitch)
                up = up.Transformed(trsf_pitch)

        cam.SetEyeAndCenter(eye, center)
        cam.SetUp(up)
        self.display.View.Redraw()

    def _pan(self, dx, dy):
        """Pan the camera using direct camera manipulation."""
        cam = self.display.View.Camera()
        eye = cam.Eye()
        center = cam.Center()
        up = cam.Up()
        distance = cam.Distance()

        # Compute side and up vectors in world space
        dir_vec = gp_Vec(eye, center)
        up_vec = gp_Vec(up.X(), up.Y(), up.Z())
        side = dir_vec.Crossed(up_vec)
        if side.Magnitude() > 1e-10:
            side.Normalize()
        up_vec.Normalize()

        # Scale pan by camera distance so it feels consistent at any zoom level
        scale = distance * PAN_SCALE
        shift = side.Multiplied(-dx * scale)
        shift = shift.Added(up_vec.Multiplied(dy * scale))

        new_eye = gp_Pnt(eye.X() + shift.X(), eye.Y() + shift.Y(), eye.Z() + shift.Z())
        new_center = gp_Pnt(
            center.X() + shift.X(), center.Y() + shift.Y(), center.Z() + shift.Z()
        )
        cam.SetEyeAndCenter(new_eye, new_center)
        self.display.View.Redraw()

    def on_left_press(self, event):
        """Handle left mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 1

    def on_left_motion(self, event):
        """Handle left mouse button drag."""
        if self.button == 1 and not self.selection_manager.is_selection_mode:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            self.start_x = event.x
            self.start_y = event.y
            self._orbit(dx, dy)

    def on_right_press(self, event):
        """Handle right mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        self.button = 3

    def on_right_motion(self, event):
        """Handle right mouse button drag."""
        if self.button == 3:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            self.start_x = event.x
            self.start_y = event.y
            self._pan(dx, dy)

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

        # If this was a click in navigation mode, inspect the face and log info
        if self.button == 1 and not self.selection_manager.is_selection_mode:
            dx = abs(event.x - self.start_x)
            dy = abs(event.y - self.start_y)
            if dx < 5 and dy < 5:
                try:
                    parts_list = self.part_manager.get_parts()
                    self.selection_manager.inspect_face_at_position(
                        event.x, event.y, self.view, parts_list=parts_list
                    )
                except Exception:
                    # ensure navigation behavior is not interrupted by inspect errors
                    pass

        self.button = None

    def on_wheel(self, event):
        """Handle mouse wheel zoom."""
        if event.delta > 0 or event.num == 4:
            self.display.ZoomFactor(1.1)
        elif event.delta < 0 or event.num == 5:
            self.display.ZoomFactor(0.9)
