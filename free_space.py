"""
Free Space Discretization using Octree and Post-Placement Splitting.

This module handles the discretization of free space above the table surface
using an octree-based breadth-first subdivision algorithm, and provides
AABB-subtraction splitting for free-space boxels after object placement.
"""

import numpy as np
import pybullet as p
import time
from typing import List, Optional
from boxel_types import OctreeNode
from boxel_data import BoxelData, BoxelType
from visualization import wireframe_corners_and_edges


class FreeSpaceGenerator:
    """
    Generates free space boxels using octree subdivision.
    
    The algorithm starts with a large bounding box covering the workspace
    and recursively subdivides regions that intersect with known objects
    until reaching a minimum resolution.
    """
    
    def __init__(self, table_surface_height: float, min_resolution: float = 0.035,
                 table_x_range: tuple = (0.0, 1.0),
                 table_y_range: tuple = (-0.5, 0.5)):
        """
        Initialize the free space generator.
        
        Args:
            table_surface_height: Z height of the table surface
            min_resolution: Minimum boxel size in meters.  0.035 m (3.5 cm) is
                half the target object size (0.08 m) — fine enough to place
                targets between objects, coarse enough to keep the octree small.
            table_x_range: (min, max) X bounds of the table surface
            table_y_range: (min, max) Y bounds of the table surface
        """
        self.table_surface_height = table_surface_height
        self.min_resolution = min_resolution
        
        # Workspace volume above table.  0.5 m height covers the tallest
        # objects (occluders at 0.15 m) with ample margin for the arm to
        # manoeuvre above them.
        self.ws_min = np.array([table_x_range[0], table_y_range[0], table_surface_height])
        self.ws_max = np.array([table_x_range[1], table_y_range[1], table_surface_height + 0.5])
        
        # Debug drawing state
        self.debug_items = []
        self.candidate_debug_items = []
    
    def generate(self, known_boxels: List[BoxelData],
                 visualize: bool = False) -> List[BoxelData]:
        """
        Discretize the free space using an Octree (Breadth-First Search).

        Args:
            known_boxels: List of OBJECT + SHADOW BoxelData (the obstacles
                that carve free space).
            visualize: If True, animates the generation process (1s per depth layer)

        Returns:
            List of FREE_SPACE BoxelData fragments with empty IDs (the
            consumer registers them via ``BoxelRegistry.add_boxel``, which
            assigns sequential IDs).
        """
        root_center = (self.ws_min + self.ws_max) / 2.0
        root_extent = (self.ws_max - self.ws_min) / 2.0
        
        root = OctreeNode(root_center, root_extent)
        free_boxels: List[BoxelData] = []

        # Pre-compute bounds for known boxels.  BoxelData stores corners
        # directly, so no center/extent arithmetic is needed here.
        known_bounds = [(b.min_corner, b.max_corner) for b in known_boxels]
        
        # BFS Queue
        current_layer = [root]
        drawn_free_boxels = set()
        
        while current_layer:
            next_layer = []
            
            for node in current_layer:
                node_min = node.min_bound
                node_max = node.max_bound
                
                is_mixed = False
                for b_min, b_max in known_bounds:
                    if (np.all(node_max >= b_min) and np.all(node_min <= b_max)):
                        is_mixed = True
                        break
                
                if not is_mixed:
                    # FREE
                    node.state = 'FREE'
                    free_boxels.append(BoxelData.from_center_extent(
                        node.center, node.extent,
                        boxel_type=BoxelType.FREE_SPACE,
                    ))
                    
                    # Visualization
                    boxel_key = (tuple(node.center), tuple(node.extent))
                    if visualize and boxel_key not in drawn_free_boxels:
                        drawn_free_boxels.add(boxel_key)
                        self._draw_boxel_wireframe(node.center, node.extent, [0, 1, 1])
                    
                    continue
                
                # Check size
                max_dim = np.max(node.extent * 2)
                if max_dim <= self.min_resolution:
                    node.state = 'OCCUPIED'
                    continue
                
                # Split
                node.is_leaf = False
                node.state = 'MIXED'
                
                offsets = [
                    [-1, -1, -1], [-1, -1, 1], [-1, 1, -1], [-1, 1, 1],
                    [1, -1, -1], [1, -1, 1], [1, 1, -1], [1, 1, 1]
                ]
                child_extent = node.extent / 2.0
                
                for off in offsets:
                    child_center = node.center + np.array(off) * child_extent
                    child = OctreeNode(child_center, child_extent)
                    node.children.append(child)
                    next_layer.append(child)
            
            # Visualization Step
            if visualize:
                # Clear previous yellow candidates
                for item_id in self.candidate_debug_items:
                    p.removeUserDebugItem(item_id)
                self.candidate_debug_items = []
                
                # Draw current candidates (yellow)
                for node in next_layer:
                    self._draw_boxel_wireframe(node.center, node.extent, [1, 1, 0], 
                                               track_as_candidate=True)
                
                time.sleep(1.0)
            
            current_layer = next_layer

        return free_boxels
    
    def _draw_boxel_wireframe(self, center, extent, color, track_as_candidate=False):
        """Draw a wireframe box using PyBullet debug lines."""
        corners, edges = wireframe_corners_and_edges(center, extent)
        for start_idx, end_idx in edges:
            line_id = p.addUserDebugLine(
                lineFromXYZ=corners[start_idx],
                lineToXYZ=corners[end_idx],
                lineColorRGB=color,
                lineWidth=1.0,
                lifeTime=0
            )
            if track_as_candidate:
                self.candidate_debug_items.append(line_id)
            else:
                self.debug_items.append(line_id)
    
    def clear_debug_items(self):
        """Clear all debug visualization items."""
        for item_id in self.debug_items:
            p.removeUserDebugItem(item_id)
        self.debug_items = []
        
        for item_id in self.candidate_debug_items:
            p.removeUserDebugItem(item_id)
        self.candidate_debug_items = []


def split_free_boxel(free_boxel: BoxelData, object_boxel: BoxelData,
                     min_extent: float = 0.005) -> List[BoxelData]:
    """
    Split a free-space boxel around a placed object using 6-axis AABB subtraction.

    Reuses the slab-cut pattern from ShadowCalculator._subtract_aabb but keeps
    ALL surrounding fragments (no directional filtering).

    Args:
        free_boxel: The free-space BoxelData being consumed by placement.
        object_boxel: The placed object's BoxelData (corners at its new position).
        min_extent: Minimum half-extent on any axis (metres) to keep a fragment.
            Fragments thinner than this are degenerate slivers and are discarded.

    Returns:
        List of FREE_SPACE BoxelData fragments surrounding the placed object
        (with empty IDs — caller registers them).  Empty list if the object
        fully covers the free boxel.
    """
    f_min = free_boxel.min_corner.copy()
    f_max = free_boxel.max_corner.copy()

    # Clip the object AABB to the free-boxel bounds so slight physics
    # drift after settling doesn't produce fragments outside the original
    # free region.
    o_min = np.maximum(object_boxel.min_corner, f_min)
    o_max = np.minimum(object_boxel.max_corner, f_max)

    if np.any(o_min >= o_max):
        return []

    fragments: List[BoxelData] = []

    # --- 6-axis slab cuts (same order as shadow_calculator._subtract_aabb) ---
    # After each cut the "remaining" region (f_min/f_max) is narrowed on
    # that axis so subsequent cuts only carve the residual volume.

    # 1. Left of object (−X slab)
    if f_min[0] < o_min[0]:
        slab_max = f_max.copy()
        slab_max[0] = o_min[0]
        _append_if_valid(fragments, f_min, slab_max, min_extent)
        f_min[0] = o_min[0]

    # 2. Right of object (+X slab)
    if f_max[0] > o_max[0]:
        slab_min = f_min.copy()
        slab_min[0] = o_max[0]
        _append_if_valid(fragments, slab_min, f_max, min_extent)
        f_max[0] = o_max[0]

    # 3. Front of object (−Y slab)
    if f_min[1] < o_min[1]:
        slab_max = f_max.copy()
        slab_max[1] = o_min[1]
        _append_if_valid(fragments, f_min, slab_max, min_extent)
        f_min[1] = o_min[1]

    # 4. Back of object (+Y slab)
    if f_max[1] > o_max[1]:
        slab_min = f_min.copy()
        slab_min[1] = o_max[1]
        _append_if_valid(fragments, slab_min, f_max, min_extent)
        f_max[1] = o_max[1]

    # 5. Bottom of object (−Z slab)
    if f_min[2] < o_min[2]:
        slab_max = f_max.copy()
        slab_max[2] = o_min[2]
        _append_if_valid(fragments, f_min, slab_max, min_extent)
        f_min[2] = o_min[2]

    # 6. Top of object (+Z slab)
    if f_max[2] > o_max[2]:
        slab_min = f_min.copy()
        slab_min[2] = o_max[2]
        _append_if_valid(fragments, slab_min, f_max, min_extent)

    return fragments


def _append_if_valid(fragments: List[BoxelData],
                     slab_min: np.ndarray, slab_max: np.ndarray,
                     min_extent: float) -> None:
    """Create a FREE_SPACE BoxelData from bounds and append if non-degenerate."""
    extent = (slab_max - slab_min) / 2.0
    if np.any(extent < min_extent):
        return
    fragments.append(BoxelData(
        boxel_type=BoxelType.FREE_SPACE,
        min_corner=slab_min.copy(),
        max_corner=slab_max.copy(),
    ))
