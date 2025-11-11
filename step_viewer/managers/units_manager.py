"""
Units Manager for handling unit conversions between metric and imperial systems.

All internal calculations are performed in millimeters (mm).
"""

from enum import Enum
from typing import Optional


class UnitSystem(Enum):
    """Unit system for measurements."""

    METRIC = "mm"
    IMPERIAL = "in"


class UnitsManager:
    """
    Manager for handling unit conversions and display.

    All internal calculations are performed in millimeters (mm).
    This manager handles conversion to/from user-preferred units.
    """

    MM_PER_INCH = 25.4

    def __init__(self, preferred_unit: UnitSystem = UnitSystem.METRIC):
        """
        Initialize the units manager.

        Args:
            preferred_unit: The preferred unit system for display (default: METRIC)
        """
        self._preferred_unit = preferred_unit

    @property
    def preferred_unit(self) -> UnitSystem:
        """Get the current preferred unit system."""
        return self._preferred_unit

    @preferred_unit.setter
    def preferred_unit(self, unit: UnitSystem):
        """Set the preferred unit system."""
        self._preferred_unit = unit

    def to_internal(
        self, value: float, from_unit: Optional[UnitSystem] = None
    ) -> float:
        """
        Convert a value to internal units (mm).

        Args:
            value: The value to convert
            from_unit: The unit system of the input value (uses preferred if None)

        Returns:
            Value in millimeters
        """
        unit = from_unit if from_unit is not None else self._preferred_unit

        if unit == UnitSystem.METRIC:
            return value
        else:  # IMPERIAL
            return value * self.MM_PER_INCH

    def from_internal(
        self, value: float, to_unit: Optional[UnitSystem] = None
    ) -> float:
        """
        Convert a value from internal units (mm) to display units.

        Args:
            value: The value in millimeters
            to_unit: The target unit system (uses preferred if None)

        Returns:
            Value in the specified unit system
        """
        unit = to_unit if to_unit is not None else self._preferred_unit

        if unit == UnitSystem.METRIC:
            return value
        else:  # IMPERIAL
            return value / self.MM_PER_INCH

    def get_unit_label(self, unit: Optional[UnitSystem] = None) -> str:
        """
        Get the display label for a unit system.

        Args:
            unit: The unit system (uses preferred if None)

        Returns:
            Unit label string (e.g., "mm" or "in")
        """
        unit = unit if unit is not None else self._preferred_unit
        return unit.value

    def format_dimension(
        self, value_mm: float, unit: Optional[UnitSystem] = None, precision: int = 1
    ) -> str:
        """
        Format a dimension value for display with unit label.

        Args:
            value_mm: The value in millimeters
            unit: The target unit system (uses preferred if None)
            precision: Number of decimal places

        Returns:
            Formatted string (e.g., "600.0 mm" or "23.6 in")
        """
        unit = unit if unit is not None else self._preferred_unit
        converted = self.from_internal(value_mm, unit)
        return f"{converted:.{precision}f} {self.get_unit_label(unit)}"

    def parse_dimension(self, text: str) -> Optional[float]:
        """
        Parse a dimension string and convert to internal units (mm).

        Supports formats like:
        - "600" (uses preferred unit)
        - "600 mm"
        - "24 in"
        - "24in"

        Args:
            text: The text to parse

        Returns:
            Value in millimeters, or None if parsing fails
        """
        text = text.strip()
        if not text:
            return None

        try:
            # Try to extract unit from string
            if text.endswith("mm"):
                value = float(text[:-2].strip())
                return self.to_internal(value, UnitSystem.METRIC)
            elif text.endswith("in"):
                value = float(text[:-2].strip())
                return self.to_internal(value, UnitSystem.IMPERIAL)
            else:
                # No unit specified, use preferred
                value = float(text)
                return self.to_internal(value)
        except (ValueError, AttributeError):
            return None
