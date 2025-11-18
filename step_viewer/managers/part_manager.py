"""
Manager for operations of individual parts.
"""

from typing import NamedTuple, List, Optional, Dict, Set
from .log_manager import logger
from .units_manager import UnitSystem

from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.AIS import AIS_ColoredShape
from OCC.Core.Quantity import Quantity_Color


class Part(NamedTuple):
    """Represents a single part in the assembly."""
    shape: TopoDS_Shape | None
    pallete: tuple[float, float, float]
    ais_colored_shape: AIS_ColoredShape


class PartManager:
    """
    Manages all part-related state and operations.
    
    This manager consolidates part tracking, visibility management,
    and provides utilities for working with parts in the assembly.
    """

    def __init__(self):
        """Initialize the part manager."""
        self._parts: List[Part] = []
        self._visible_parts: Set[int] = set()  # Indices of visible parts
        self._hidden_parts: Set[int] = set()   # Indices of hidden parts
        self._part_colors: Dict[int, Quantity_Color] = {}  # Original colors by index
        
    def set_parts(self, parts: List[Part]) -> None:
        """
        Set the list of parts to manage.
        
        Args:
            parts: List of Part namedtuples
        """
        self._parts = parts
        # Initialize all parts as visible
        self._visible_parts = set(range(len(parts)))
        self._hidden_parts.clear()
        logger.info(f"PartManager initialized with {len(parts)} parts")
        
    def get_parts(self) -> List[Part]:
        """Get the list of all parts."""
        return self._parts
    
    def get_part(self, index: int) -> Optional[Part]:
        """
        Get a specific part by index.
        
        Args:
            index: Part index
            
        Returns:
            Part at the given index or None if invalid index
        """
        if 0 <= index < len(self._parts):
            return self._parts[index]
        return None
    
    def get_part_count(self) -> int:
        """Get the total number of parts."""
        return len(self._parts)
    
    def is_visible(self, index: int) -> bool:
        """
        Check if a part is visible.
        
        Args:
            index: Part index
            
        Returns:
            True if part is visible, False otherwise
        """
        return index in self._visible_parts
    
    def set_visibility(self, index: int, visible: bool) -> None:
        """
        Set the visibility of a part.
        
        Args:
            index: Part index
            visible: True to show, False to hide
        """
        if not 0 <= index < len(self._parts):
            return
            
        if visible:
            self._visible_parts.add(index)
            self._hidden_parts.discard(index)
        else:
            self._visible_parts.discard(index)
            self._hidden_parts.add(index)
    
    def get_visible_parts(self) -> List[int]:
        """Get list of visible part indices."""
        return sorted(list(self._visible_parts))
    
    def get_hidden_parts(self) -> List[int]:
        """Get list of hidden part indices."""
        return sorted(list(self._hidden_parts))
    
    def hide_all(self) -> None:
        """Hide all parts."""
        self._hidden_parts = set(range(len(self._parts)))
        self._visible_parts.clear()
        
    def show_all(self) -> None:
        """Show all parts."""
        self._visible_parts = set(range(len(self._parts)))
        self._hidden_parts.clear()
    
    def register_part_color(self, index: int, color: Quantity_Color) -> None:
        """
        Register the original color for a part.
        
        Args:
            index: Part index
            color: The Quantity_Color for the part
        """
        self._part_colors[index] = color
        
    def get_part_color(self, index: int) -> Optional[Quantity_Color]:
        """
        Get the registered color for a part.
        
        Args:
            index: Part index
            
        Returns:
            Quantity_Color or None if not registered
        """
        return self._part_colors.get(index)
    
    def get_ais_colored_shapes(self) -> List[AIS_ColoredShape]:
        """Get list of all AIS_ColoredShape objects."""
        return [part.ais_colored_shape for part in self._parts]
    
    def get_solids(self) -> List[TopoDS_Shape]:
        """Get list of all solid shapes."""
        return [part.shape for part in self._parts if part.shape is not None]
    
    def clear(self) -> None:
        """Clear all parts and reset state."""
        self._parts.clear()
        self._visible_parts.clear()
        self._hidden_parts.clear()
        self._part_colors.clear()
        logger.info("PartManager cleared")