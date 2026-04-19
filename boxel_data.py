"""
Boxel Data Structure and Serialization for PDDLStream Integration.

This module provides:
- BoxelData: Rich data structure for semantic boxels
- BoxelRegistry: Container for all boxels with relationship tracking
- Serialization to JSON for persistence
- PDDL fact generation for PDDLStream integration
"""

import json
import numpy as np
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class BoxelType(Enum):
    """Semantic type of a boxel."""
    OBJECT = "object"           # Bounding box around a detected object
    SHADOW = "shadow"           # Occluded region cast by an object
    FREE_SPACE = "free_space"   # Known free space (merged)


@dataclass(kw_only=True)
class BoxelData:
    """
    Complete data structure for a Semantic Boxel.

    Designed for PDDLStream integration with all necessary fields for:
    - Geometric queries (motion planning)
    - Spatial relationships (neighbors, occlusion)
    - Manipulation planning (reachability, placement)

    Constructed via keyword arguments only (``kw_only=True``).  Producers
    that don't yet have a stable ID (``FreeSpaceGenerator``, ``CellMerger``,
    ``ShadowCalculator`` for transient fragments) leave ``id=""``;
    ``BoxelRegistry.add_boxel`` then assigns a sequential ID with a
    type-appropriate prefix.
    """

    # === IDENTITY ===
    id: str = ""                                # Empty → registry assigns on add_boxel
    boxel_type: BoxelType = BoxelType.FREE_SPACE

    # === GEOMETRY (AABB) ===
    min_corner: np.ndarray = field(default_factory=lambda: np.zeros(3))
    max_corner: np.ndarray = field(default_factory=lambda: np.zeros(3))

    # === OBJECT BOXEL FIELDS ===
    object_name: Optional[str] = None           # Physical object name (for type=OBJECT)
    is_occluder: bool = False                   # Does this cast shadows?
    shadow_boxel_ids: List[str] = field(default_factory=list)  # IDs of shadows this creates

    # === SHADOW BOXEL FIELDS ===
    created_by_boxel_id: Optional[str] = None   # Which object boxel creates this shadow
    created_by_object: Optional[str] = None     # Object name that creates this shadow

    # === SPATIAL RELATIONSHIPS ===
    neighbor_ids: Dict[str, List[str]] = field(default_factory=lambda: {
        "x_pos": [], "x_neg": [], "y_pos": [], "y_neg": [], "z_pos": [], "z_neg": []
    })
    on_surface: Optional[str] = None            # Which support surface (e.g., "table")
    surface_z: Optional[float] = None           # Z height of support surface

    # Note: blocking_boxels removed - use created_by_boxel_id for shadows
    # Note: belief-state fields (possibly_contains, confirmed_contains,
    # confirmed_empty, observed, last_observation_time) removed — they were
    # always default values and never managed by any code path. Belief
    # tracking is handled by BeliefState in the execution layer.

    @classmethod
    def from_center_extent(
        cls,
        center,
        extent,
        boxel_type: BoxelType = BoxelType.FREE_SPACE,
        **kwargs,
    ) -> 'BoxelData':
        """
        Build a BoxelData from a (center, half-extent) pair.

        Convenience for stateless geometry generators that think in
        center/extent rather than min/max corners (FreeSpaceGenerator,
        CellMerger, ShadowCalculator).  Pass ``id=""`` (the default)
        to defer ID assignment to ``BoxelRegistry.add_boxel``.
        """
        c = np.asarray(center, dtype=float)
        e = np.asarray(extent, dtype=float)
        return cls(
            boxel_type=boxel_type,
            min_corner=c - e,
            max_corner=c + e,
            **kwargs,
        )

    @property
    def center(self) -> np.ndarray:
        """Compute center from corners."""
        return (self.min_corner + self.max_corner) / 2.0

    @property
    def extent(self) -> np.ndarray:
        """Compute half-extents from corners."""
        return (self.max_corner - self.min_corner) / 2.0
    
    @property
    def volume(self) -> float:
        """Compute volume in cubic meters."""
        dims = self.max_corner - self.min_corner
        return float(np.prod(dims))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "boxel_type": self.boxel_type.value,
            "min_corner": self.min_corner.tolist(),
            "max_corner": self.max_corner.tolist(),
            "center": self.center.tolist(),
            "extent": self.extent.tolist(),
            "volume": self.volume,
            "object_name": self.object_name,
            "is_occluder": self.is_occluder,
            "shadow_boxel_ids": self.shadow_boxel_ids,
            "created_by_boxel_id": self.created_by_boxel_id,
            "created_by_object": self.created_by_object,
            "neighbor_ids": self.neighbor_ids,
            "on_surface": self.on_surface,
            "surface_z": self.surface_z,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BoxelData':
        """Create BoxelData from dictionary."""
        return cls(
            id=data["id"],
            boxel_type=BoxelType(data["boxel_type"]),
            min_corner=np.array(data["min_corner"]),
            max_corner=np.array(data["max_corner"]),
            object_name=data.get("object_name"),
            is_occluder=data.get("is_occluder", False),
            shadow_boxel_ids=data.get("shadow_boxel_ids", []),
            created_by_boxel_id=data.get("created_by_boxel_id"),
            created_by_object=data.get("created_by_object"),
            neighbor_ids=data.get("neighbor_ids", {}),
            on_surface=data.get("on_surface"),
            surface_z=data.get("surface_z"),
        )


class BoxelRegistry:
    """
    Container for all boxels with relationship tracking and serialization.
    
    Provides methods for:
    - Adding/retrieving boxels
    - Computing spatial relationships (neighbors)
    - Serializing to JSON
    - Generating PDDL facts
    """
    
    def __init__(self):
        self.boxels: Dict[str, BoxelData] = {}
        self._next_id = 0
        self._dirty: bool = False

    @property
    def dirty(self) -> bool:
        """True when the free-space partition has been mutated (e.g. by
        update_after_place) but reboxelize_free_space has not yet run."""
        return self._dirty

    def mark_clean(self) -> None:
        """Clear the dirty flag — called after reboxelization."""
        self._dirty = False
    
    # Default ID prefix per boxel type when a producer leaves ``id=""``.
    _PREFIX_FOR_TYPE = {
        BoxelType.FREE_SPACE: "free",
        BoxelType.OBJECT: "obj",
        BoxelType.SHADOW: "shadow",
    }

    def generate_id(self, prefix: str = "boxel") -> str:
        """Generate a unique boxel ID."""
        boxel_id = f"{prefix}_{self._next_id:03d}"
        self._next_id += 1
        return boxel_id

    def add_boxel(self, boxel: BoxelData) -> str:
        """
        Add a boxel to the registry.

        If ``boxel.id`` is empty, a sequential ID is generated using a
        prefix derived from ``boxel.boxel_type`` (see ``_PREFIX_FOR_TYPE``).
        Returns the final ID under which the boxel was stored.
        """
        if not boxel.id:
            prefix = self._PREFIX_FOR_TYPE.get(boxel.boxel_type, "boxel")
            boxel.id = self.generate_id(prefix)
        self.boxels[boxel.id] = boxel
        return boxel.id
    
    def get_boxel(self, boxel_id: str) -> Optional[BoxelData]:
        """Get a boxel by ID."""
        return self.boxels.get(boxel_id)
    
    def get_boxels_by_type(self, boxel_type: BoxelType) -> List[BoxelData]:
        """Get all boxels of a specific type."""
        return [b for b in self.boxels.values() if b.boxel_type == boxel_type]
    
    def get_object_boxels(self) -> List[BoxelData]:
        """Get all object boxels."""
        return self.get_boxels_by_type(BoxelType.OBJECT)
    
    def get_shadow_boxels(self) -> List[BoxelData]:
        """Get all shadow boxels."""
        return self.get_boxels_by_type(BoxelType.SHADOW)
    
    def get_free_space_boxels(self) -> List[BoxelData]:
        """Get all free space boxels."""
        return self.get_boxels_by_type(BoxelType.FREE_SPACE)

    def remove_boxel(self, boxel_id: str) -> Optional[BoxelData]:
        """Remove a boxel from the registry and return it (None if absent)."""
        return self.boxels.pop(boxel_id, None)

    def get_adjacent_free_boxels(
        self,
        region_min: np.ndarray,
        region_max: np.ndarray,
        exclude_ids: Optional[Set[str]] = None,
        tolerance: float = 0.01,
    ) -> List['BoxelData']:
        """
        Return all FREE_SPACE boxels that share a face with a given AABB region.

        Two AABBs share a face when they touch on one axis (within *tolerance*)
        and overlap on the other two axes by more than *tolerance*.  This is the
        same adjacency criterion used by ``compute_neighbors`` / ``_check_adjacency``.

        Args:
            region_min: [x, y, z] minimum corner of the query region.
            region_max: [x, y, z] maximum corner of the query region.
            exclude_ids: Boxel IDs to skip (e.g. the consumed boxel itself).
            tolerance: Face-touch and overlap tolerance in metres.

        Returns:
            List of adjacent BoxelData entries (type FREE_SPACE only).
        """
        exclude = exclude_ids or set()
        result: List[BoxelData] = []
        for bd in self.boxels.values():
            if bd.boxel_type != BoxelType.FREE_SPACE or bd.id in exclude:
                continue
            b_min, b_max = bd.min_corner, bd.max_corner
            for axis in range(3):
                other = [i for i in range(3) if i != axis]
                overlap_ok = True
                for oa in other:
                    if min(region_max[oa], b_max[oa]) - max(region_min[oa], b_min[oa]) < tolerance:
                        overlap_ok = False
                        break
                if not overlap_ok:
                    continue
                if (abs(region_max[axis] - b_min[axis]) < tolerance or
                        abs(b_max[axis] - region_min[axis]) < tolerance):
                    result.append(bd)
                    break
        return result

    def update_after_place(
        self,
        free_boxel_id: str,
        object_boxel_id: str,
        placed_min: np.ndarray,
        placed_max: np.ndarray,
        table_surface_height: float,
    ) -> None:
        """
        Update the registry after an object is placed into a free-space boxel.

        Removes the consumed free-space entry and moves the object's AABB to
        its new position.  Sets the dirty flag so the replan loop knows to
        re-run ``reboxelize_free_space`` before the next planner.plan() call
        (audit #25).

        Free-space fragments are NOT created here — re-boxelization is handled
        end-to-end by ``reboxelize_free_space`` in test_full_pipeline.py, which
        re-runs the full octree + merge pipeline against the current world.

        Args:
            free_boxel_id: ID of the free-space boxel consumed by placement.
            object_boxel_id: Registry ID of the placed object.
            placed_min: New AABB min corner of the placed object.
            placed_max: New AABB max corner of the placed object.
            table_surface_height: Z height of the table surface.
        """
        self.remove_boxel(free_boxel_id)

        obj_boxel = self.get_boxel(object_boxel_id)
        if obj_boxel is not None:
            obj_boxel.min_corner = np.asarray(placed_min, dtype=float)
            obj_boxel.max_corner = np.asarray(placed_max, dtype=float)
            obj_boxel.on_surface = (
                "table" if placed_min[2] <= table_surface_height + 0.01 else None
            )

        self._dirty = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to JSON-serializable dictionary."""
        return {
            "boxels": [b.to_dict() for b in self.boxels.values()],
            "summary": {
                "total": len(self.boxels),
                "objects": len(self.get_object_boxels()),
                "shadows": len(self.get_shadow_boxels()),
                "free_space": len(self.get_free_space_boxels()),
            }
        }
    
    def save_to_json(self, filepath: str) -> None:
        """Save registry to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Saved {len(self.boxels)} boxels to {filepath}")
    
    @classmethod
    def load_from_json(cls, filepath: str) -> 'BoxelRegistry':
        """Load registry from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        registry = cls()
        for boxel_data in data["boxels"]:
            boxel = BoxelData.from_dict(boxel_data)
            registry.add_boxel(boxel)
        
        return registry


# Note (audit #35, 2026-04-17): create_boxel_registry_from_boxels() was the
# bridge between the old boxel_types.Boxel and the modern BoxelData/Registry
# representation.  Both producers (boxel_env.generate_boxels) and consumers
# (FreeSpaceGenerator, CellMerger, ShadowCalculator, BoxelVisualizer) now use
# BoxelData directly, so the bridge is no longer needed.
