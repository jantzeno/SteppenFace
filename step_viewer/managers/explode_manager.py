"""
Model explosion manager for separating parts visually.
"""

from typing import List
import numpy as np

from OCC.Core.gp import gp_Trsf, gp_Vec
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop


class ExplodeManager:
    """Manages model explosion - separating parts based on their positions."""

    def __init__(self):
        self.parts_data = []
        self.global_center = None
        self.explosion_factor = 0.0
        self.min_part_distance = None
        self.selection_manager = None  # Will be set by viewer

    def initialize_parts(self, parts_list: List):
        """
        Initialize parts data with their centroids and original locations.

        Args:
            parts_list: List of (solid, color, ais_shape) tuples
        """
        self.parts_data = []
        centroids = []

        for solid, color, ais_shape in parts_list:
            # Calculate centroid of the solid
            props = GProp_GProps()
            brepgprop.VolumeProperties(solid, props)
            centroid = props.CentreOfMass()
            centroid_tuple = (centroid.X(), centroid.Y(), centroid.Z())

            self.parts_data.append({
                'solid': solid,
                'color': color,
                'ais_shape': ais_shape,
                'centroid': centroid_tuple
            })

            centroids.append(centroid_tuple)

        # Calculate global center (average of all centroids)
        if centroids:
            centroids_array = np.array(centroids)
            self.global_center = tuple(np.mean(centroids_array, axis=0))
        else:
            self.global_center = (0, 0, 0)

        # Calculate minimum distance between any two parts for scaling
        self.min_part_distance = self._calculate_min_part_distance()

    def set_explosion_factor(self, factor: float, display, root):
        """
        Set the explosion factor and update part positions.

        Sorted radial explosion: Parts are sorted by their distance from the global
        center. Each part is pushed outward from center by an amount proportional to
        its rank in the sorted order, ensuring consistent spacing between all parts
        including nested geometries.

        Args:
            factor: Explosion factor (0.0 = normal, higher values = more exploded)
            display: The OCC display object
            root: Tkinter root for UI updates
        """
        self.explosion_factor = max(0.0, min(5.0, factor))

        if len(self.parts_data) == 0:
            return

        # Calculate the characteristic scale based on the model extent
        base_scale = self.min_part_distance if self.min_part_distance else 10.0
        # Multiply by a larger factor to create more visible separation
        gap_size = base_scale * self.explosion_factor * 3.0

        # Sort parts by distance from center
        parts_with_distance = []
        for part_data in self.parts_data:
            centroid = part_data['centroid']
            dx = centroid[0] - self.global_center[0]
            dy = centroid[1] - self.global_center[1]
            dz = centroid[2] - self.global_center[2]
            distance = np.sqrt(dx*dx + dy*dy + dz*dz)

            if distance > 1e-6:
                unit_direction = (dx / distance, dy / distance, dz / distance)
            else:
                unit_direction = (0, 0, 0)

            parts_with_distance.append({
                'part_data': part_data,
                'distance': distance,
                'unit_direction': unit_direction
            })

        # Sort by distance from center (innermost first)
        parts_with_distance.sort(key=lambda p: p['distance'])

        # Apply displacement based on sorted order
        # Parts closer to center get less displacement, farther parts get more
        # This creates equal spacing between consecutive parts
        for i, item in enumerate(parts_with_distance):
            part_data = item['part_data']
            ais_shape = part_data['ais_shape']
            unit_dir = item['unit_direction']

            # Displacement increases with rank: part i gets i * gap_size displacement
            # This ensures parts are evenly spaced with gap_size between them
            displacement = i * gap_size

            explosion_offset_x = unit_dir[0] * displacement
            explosion_offset_y = unit_dir[1] * displacement
            explosion_offset_z = unit_dir[2] * displacement

            # Create transformation
            trsf = gp_Trsf()
            trsf.SetTranslation(gp_Vec(explosion_offset_x, explosion_offset_y, explosion_offset_z))

            # Apply transformation
            ais_shape.SetLocalTransformation(trsf)

            # Update display
            display.Context.Redisplay(ais_shape, True)

        # Refresh display
        display.Context.UpdateCurrentViewer()
        root.update_idletasks()

        # Update face highlight transformations if selection manager is set
        if self.selection_manager:
            self.selection_manager.update_all_transformations(root)

    def reset(self, display, root):
        """Reset all parts to original positions."""
        self.set_explosion_factor(0.0, display, root)

    def get_explosion_factor(self) -> float:
        """Get current explosion factor."""
        return self.explosion_factor

    def _calculate_min_part_distance(self) -> float:
        """
        Calculate the minimum distance between any two part centroids.
        Returns a characteristic distance for scaling the explosion.
        """
        if len(self.parts_data) < 2:
            return 1.0

        centroids = [part['centroid'] for part in self.parts_data]
        centroids_array = np.array(centroids)

        # Calculate all pairwise distances
        min_dist = float('inf')
        for i in range(len(centroids_array)):
            for j in range(i + 1, len(centroids_array)):
                diff = centroids_array[i] - centroids_array[j]
                dist = np.sqrt(np.sum(diff * diff))
                if dist > 1e-6:  # Ignore coincident centroids
                    min_dist = min(min_dist, dist)

        # If no valid distance found, use average distance from center
        if min_dist == float('inf'):
            total_distance = 0.0
            for centroid in centroids:
                dx = centroid[0] - self.global_center[0]
                dy = centroid[1] - self.global_center[1]
                dz = centroid[2] - self.global_center[2]
                total_distance += np.sqrt(dx*dx + dy*dy + dz*dz)
            return total_distance / len(centroids)

        return min_dist
