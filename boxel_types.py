"""
Data structures for Semantic Boxel representation.

This module contains the core data types used throughout the boxel system:
- ObjectInfo: Stores PyBullet object metadata
- OctreeNode: Helper for spatial subdivision
- CameraObservation: Container for camera capture results

The Boxel dataclass that previously lived here was removed by audit #35
(2026-04-17): the codebase now uses :class:`boxel_data.BoxelData` as the
sole representation everywhere, including in stateless geometry producers
(FreeSpaceGenerator, CellMerger, ShadowCalculator).
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from boxel_data import BoxelData  # forward reference for CameraObservation


@dataclass
class ObjectInfo:
    """Data structure to store information about objects in the scene."""
    object_id: int  # PyBullet object ID
    name: str  # Human-readable name
    position: np.ndarray  # [x, y, z] position
    orientation: np.ndarray  # [x, y, z, w] quaternion
    size: np.ndarray  # [width, height, depth] dimensions
    is_visible: bool  # Whether object is currently visible from camera
    is_occluder: bool  # Whether this object is an occluder (larger cube)


class OctreeNode:
    """Helper class for Octree spatial subdivision."""
    
    def __init__(self, center: np.ndarray, extent: np.ndarray):
        self.center = center
        self.extent = extent
        self.children: List['OctreeNode'] = []
        self.is_leaf = True
        self.state = 'FREE'  # 'FREE', 'OCCUPIED', 'MIXED'

    @property
    def min_bound(self):
        return self.center - self.extent

    @property
    def max_bound(self):
        return self.center + self.extent


@dataclass
class CameraObservation:
    """Data structure for camera observations."""
    visible_objects: List[str]  # List of object names that are visible
    object_poses: Dict[str, Tuple[np.ndarray, np.ndarray]]  # Dict mapping object names to (position, orientation)
    boxels: Optional[List['BoxelData']] = None  # OBJECT + SHADOW BoxelData generated from the observation
    rgb_image: Optional[np.ndarray] = None  # RGB image (H, W, 3) — None when not computed
    depth_image: Optional[np.ndarray] = None  # Depth image (H, W) in meters — None when not computed
    point_cloud: Optional[np.ndarray] = None  # Point cloud (N, 3) in world coords — None when not computed
