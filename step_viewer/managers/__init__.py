"""
Manager classes for handling state and business logic.
"""

from .color_manager import ColorManager
from .selection_manager import SelectionManager
from .explode_manager import ExplodeManager
from .deduplication_manager import DeduplicationManager
from .planar_alignment_manager import PlanarAlignmentManager
from .plate_manager import PlateManager, Plate

__all__ = ['ColorManager', 'SelectionManager', 'ExplodeManager', 'DeduplicationManager', 'PlanarAlignmentManager', 'PlateManager', 'Plate']
