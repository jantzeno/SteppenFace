"""
Color management for face selection highlighting.
"""

from typing import Tuple
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
from ..config import ViewerConfig


class ColorManager:
    """Manages selection colors and color cycling."""

    def __init__(self, config: ViewerConfig):
        self.config = config
        self.fill_index = 0
        self.outline_index = 0

    def get_current_fill_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Get current fill color preset."""
        return self.config.SELECTION_COLOR_PRESETS[self.fill_index]

    def get_current_outline_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Get current outline color preset."""
        return self.config.OUTLINE_COLOR_PRESETS[self.outline_index]

    def cycle_fill_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Cycle to next fill color preset."""
        self.fill_index = (self.fill_index + 1) % len(
            self.config.SELECTION_COLOR_PRESETS
        )
        return self.get_current_fill_color()

    def cycle_outline_color(self) -> Tuple[Tuple[float, float, float], str]:
        """Cycle to next outline color preset."""
        self.outline_index = (self.outline_index + 1) % len(
            self.config.OUTLINE_COLOR_PRESETS
        )
        return self.get_current_outline_color()

    def get_fill_quantity_color(self) -> Quantity_Color:
        """Get current fill color as Quantity_Color."""
        rgb, _ = self.get_current_fill_color()
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)

    def get_outline_quantity_color(self) -> Quantity_Color:
        """Get current outline color as Quantity_Color."""
        rgb, _ = self.get_current_outline_color()
        return Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)
