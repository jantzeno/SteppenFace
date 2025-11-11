"""
Shape deduplication manager for filtering identical parts.
"""

from typing import List, Tuple, Dict
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer

from ..logger import logger


class DeduplicationManager:
    """Manages identification and filtering of duplicate parts based on geometry."""

    def __init__(self):
        self.show_duplicates = True
        self.hidden_indices = set()  # Indices of parts that are hidden as duplicates

    def toggle_duplicates(self) -> bool:
        """Toggle whether to show duplicate parts. Returns new state."""
        self.show_duplicates = not self.show_duplicates
        return self.show_duplicates

    def is_part_hidden(self, index: int) -> bool:
        """Check if a part at the given index is currently hidden as a duplicate."""
        return index in self.hidden_indices

    def get_unique_parts(self, parts_list: List) -> Tuple[List, Dict[int, List[int]]]:
        """
        Filter parts to show only unique geometries.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples

        Returns:
            Tuple of (filtered_parts_list, duplicate_groups)
            - filtered_parts_list: List with only unique parts
            - duplicate_groups: Dict mapping unique part index to list of duplicate indices
        """
        if self.show_duplicates:
            self.hidden_indices.clear()
            return parts_list, {}

        unique_parts = []
        duplicate_groups = {}
        shape_signatures = []
        self.hidden_indices.clear()

        for i, (solid, color, ais_shape) in enumerate(parts_list):
            signature = self._compute_shape_signature(solid)

            # Check if this signature matches any existing unique part
            match_found = False
            for j, existing_sig in enumerate(shape_signatures):
                if self._signatures_match(signature, existing_sig):
                    # This is a duplicate
                    if j not in duplicate_groups:
                        duplicate_groups[j] = []
                    duplicate_groups[j].append(i)
                    self.hidden_indices.add(i)
                    match_found = True
                    break

            if not match_found:
                # This is a unique part
                unique_parts.append((solid, color, ais_shape))
                shape_signatures.append(signature)

        logger.info(f"\nDeduplication: Found {len(unique_parts)} unique parts out of {len(parts_list)} total")
        if duplicate_groups:
            logger.info(f"  {sum(len(dups) for dups in duplicate_groups.values())} duplicates hidden")

        return unique_parts, duplicate_groups

    def _compute_shape_signature(self, solid) -> Dict:
        """
        Compute a signature for a solid based on its geometric properties.

        Returns a dictionary with:
        - volume: Volume of the solid
        - surface_area: Surface area of the solid
        - face_count: Number of faces
        - edge_count: Number of edges
        """
        # Calculate volume and surface area
        props = GProp_GProps()
        brepgprop.VolumeProperties(solid, props)
        volume = props.Mass()

        surface_props = GProp_GProps()
        brepgprop.SurfaceProperties(solid, surface_props)
        surface_area = surface_props.Mass()

        # Count faces and edges
        face_count = 0
        explorer = TopExp_Explorer(solid, TopAbs_FACE)
        while explorer.More():
            face_count += 1
            explorer.Next()

        edge_count = 0
        explorer = TopExp_Explorer(solid, TopAbs_EDGE)
        while explorer.More():
            edge_count += 1
            explorer.Next()

        return {
            'volume': volume,
            'surface_area': surface_area,
            'face_count': face_count,
            'edge_count': edge_count
        }

    def _signatures_match(self, sig1: Dict, sig2: Dict, tolerance: float = 1e-6) -> bool:
        """
        Check if two shape signatures match within tolerance.

        Args:
            sig1: First signature
            sig2: Second signature
            tolerance: Relative tolerance for floating point comparisons

        Returns:
            True if signatures match, False otherwise
        """
        # First check topology counts (must match exactly)
        if sig1['face_count'] != sig2['face_count']:
            return False
        if sig1['edge_count'] != sig2['edge_count']:
            return False

        # Check geometric properties with tolerance
        if not self._values_close(sig1['volume'], sig2['volume'], tolerance):
            return False
        if not self._values_close(sig1['surface_area'], sig2['surface_area'], tolerance):
            return False

        return True

    def _values_close(self, val1: float, val2: float, tolerance: float) -> bool:
        """Check if two values are close within relative tolerance."""
        if abs(val1) < 1e-10 and abs(val2) < 1e-10:
            return True
        if abs(val1) < 1e-10 or abs(val2) < 1e-10:
            return False
        return abs(val1 - val2) / max(abs(val1), abs(val2)) < tolerance
