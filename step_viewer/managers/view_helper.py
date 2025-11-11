"""
View helper for managing camera view presets.
"""


class ViewHelper:
    """Controller for managing camera view presets."""

    def __init__(self, view):
        """
        Initialize view controller.

        Args:
            view: OCC.Display.View object
        """
        self.view = view

    def set_top_view(self):
        """Set camera to top view (looking down from +Z)."""
        self.view.SetProj(0, 0, 1)   # Camera at +Z looking down
        self.view.SetUp(0, 1, 0)     # +Y is up in screen space
        self.view.FitAll()

    def set_bottom_view(self):
        """Set camera to bottom view (looking up from -Z)."""
        self.view.SetProj(0, 0, -1)  # Camera at -Z looking up
        self.view.SetUp(0, 1, 0)     # +Y is up in screen space
        self.view.FitAll()

    def set_front_view(self):
        """Set camera to front view (looking from -Y towards +Y)."""
        self.view.SetProj(0, -1, 0)  # Camera at -Y (behind) looking forward
        self.view.SetUp(0, 0, 1)     # +Z is up in screen space
        self.view.FitAll()

    def set_back_view(self):
        """Set camera to back view (looking from +Y towards -Y)."""
        self.view.SetProj(0, 1, 0)   # Camera at +Y (front) looking backward
        self.view.SetUp(0, 0, 1)     # +Z is up in screen space
        self.view.FitAll()

    def set_right_view(self):
        """Set camera to right view (looking from +X towards -X)."""
        self.view.SetProj(1, 0, 0)   # Camera at +X (right) looking left
        self.view.SetUp(0, 0, 1)     # +Z is up in screen space
        self.view.FitAll()

    def set_left_view(self):
        """Set camera to left view (looking from -X towards +X)."""
        self.view.SetProj(-1, 0, 0)  # Camera at -X (left) looking right
        self.view.SetUp(0, 0, 1)     # +Z is up in screen space
        self.view.FitAll()

    def set_isometric_view(self):
        """Set camera to isometric view."""
        # Standard isometric projection (35.264° and 45°)
        self.view.SetProj(1, -1, 1)  # Isometric direction
        self.view.SetUp(0, 0, 1)     # Z is up
        self.view.FitAll()
