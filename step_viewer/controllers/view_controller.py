"""
View controller for managing standard orthographic view presets.

Provides methods to set the camera to standard views:
- Top, Bottom
- Front, Back
- Right, Left
"""

from OCC.Core.V3d import V3d_XnegYnegZpos, V3d_XposYnegZpos


class ViewController:
    """Controller for managing camera view presets."""

    def __init__(self, view):
        """
        Initialize view controller.

        Args:
            view: OCC.Display.View object
        """
        self.view = view

    def set_top_view(self):
        """Set camera to top view (looking down -Z)."""
        self.view.SetProj(0, 0, -1)  # Look down negative Z
        self.view.SetUp(0, 1, 0)     # Y is up
        self.view.FitAll()

    def set_bottom_view(self):
        """Set camera to bottom view (looking up +Z)."""
        self.view.SetProj(0, 0, 1)   # Look up positive Z
        self.view.SetUp(0, 1, 0)     # Y is up
        self.view.FitAll()

    def set_front_view(self):
        """Set camera to front view (looking along -Y)."""
        self.view.SetProj(0, -1, 0)  # Look along negative Y
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()

    def set_back_view(self):
        """Set camera to back view (looking along +Y)."""
        self.view.SetProj(0, 1, 0)   # Look along positive Y
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()

    def set_right_view(self):
        """Set camera to right view (looking along -X)."""
        self.view.SetProj(-1, 0, 0)  # Look along negative X
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()

    def set_left_view(self):
        """Set camera to left view (looking along +X)."""
        self.view.SetProj(1, 0, 0)   # Look along positive X
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()

    def set_isometric_view(self):
        """Set camera to isometric view."""
        # Standard isometric projection (35.264° and 45°)
        self.view.SetProj(1, -1, 1)  # Isometric direction
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()
