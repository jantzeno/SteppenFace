"""
Manager classes for handling state and business logic.
"""

from .color_manager import ColorManager
from .selection_manager import SelectionManager
from .explode_manager import ExplodeManager
from .deduplication_manager import DeduplicationManager

__all__ = ['ColorManager', 'SelectionManager', 'ExplodeManager', 'DeduplicationManager']
