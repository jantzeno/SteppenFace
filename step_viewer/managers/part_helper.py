"""
Functions for operations of individual parts.
"""

from typing import NamedTuple
from .log_manager import logger
from .units_manager import UnitSystem

from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.AIS import AIS_Shape



class Part(NamedTuple):
    shape: TopoDS_Shape | None
    pallete: tuple[float, float, float]
    ais_shape: AIS_Shape