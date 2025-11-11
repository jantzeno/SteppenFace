"""
STEP file loader.
"""

from pathlib import Path
from typing import List

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE

from step_viewer.managers.log_manager import logger


class StepLoader:
    """Loads STEP files and extracts geometry."""

    @staticmethod
    def load_file(filename: str):
        """
        Load a STEP file and return the shape.

        Returns:
            The loaded shape or None if loading failed
        """
        if not Path(filename).exists():
            logger.error(f"File '{filename}' not found.")
            return None

        step_reader = STEPControl_Reader()
        status = step_reader.ReadFile(filename)

        if status != IFSelect_RetDone:
            logger.error(f"Failed to read STEP file '{filename}'")
            return None

        step_reader.TransferRoots()
        shape = step_reader.OneShape()

        logger.info(f"Successfully loaded: {filename}")

        # Report entities
        explorer_solid = TopExp_Explorer(shape, TopAbs_SOLID)
        solid_count = sum(
            1
            for _ in iter(
                lambda: explorer_solid.More() and not explorer_solid.Next(), False
            )
        )

        explorer_face = TopExp_Explorer(shape, TopAbs_FACE)
        face_count = sum(
            1
            for _ in iter(
                lambda: explorer_face.More() and not explorer_face.Next(), False
            )
        )

        logger.info(f"  Solids: {solid_count}")
        logger.info(f"  Faces: {face_count}")

        return shape

    @staticmethod
    def extract_solids(shape) -> List:
        """Extract all solids from a shape."""
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        solids = []
        while explorer.More():
            solids.append(explorer.Current())
            explorer.Next()
        return solids
