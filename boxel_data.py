"""
Boxel Data Structure and Serialization for PDDLStream Integration.

This module provides:
- BoxelData: Rich data structure for semantic boxels
- BoxelRegistry: Container for all boxels with relationship tracking
- Serialization to JSON for persistence
- Type tags consumed by pddlstream_planner for PDDL fact emission
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
    """Boxel record."""
    id: str = ""
    boxel_type: BoxelType = BoxelType.FREE_SPACE
    min_corner: np.ndarray = field(default_factory=lambda: np.zeros(3))
    max_corner: np.ndarray = field(default_factory=lambda: np.zeros(3))
    object_name: Optional[str] = None
    is_occluder: bool = False
    shadow_boxel_ids: List[str] = field(default_factory=list)
    created_by_boxel_id: Optional[str] = None
    created_by_object: Optional[str] = None
    neighbor_ids: Dict[str, List[str]] = field(default_factory=lambda: {
        "x_pos": [], "x_neg": [], "y_pos": [], "y_neg": [], "z_pos": [], "z_neg": []
    })
    on_surface: Optional[str] = None
    surface_z: Optional[float] = None

    @classmethod
    def from_center_extent(cls, center, extent,
                           boxel_type: BoxelType = BoxelType.FREE_SPACE,
                           **kwargs) -> 'BoxelData':
        c = np.asarray(center, dtype=float)
        e = np.asarray(extent, dtype=float)
        return cls(boxel_type=boxel_type, min_corner=c - e, max_corner=c + e, **kwargs)

    @property
    def center(self) -> np.ndarray:
        return (self.min_corner + self.max_corner) / 2.0

    @property
    def extent(self) -> np.ndarray:
        return (self.max_corner - self.min_corner) / 2.0

    @property
    def volume(self) -> float:
        dims = self.max_corner - self.min_corner
        return float(np.prod(dims))

    def to_dict(self) -> Dict[str, Any]:
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
    """Registry of boxels."""

    def __init__(self):
        self.boxels: Dict[str, BoxelData] = {}
        self._next_id = 0
        self._dirty: bool = False

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    _PREFIX_FOR_TYPE = {
        BoxelType.FREE_SPACE: "free",
        BoxelType.OBJECT: "obj",
        BoxelType.SHADOW: "shadow",
    }

    def generate_id(self, prefix: str = "boxel") -> str:
        boxel_id = f"{prefix}_{self._next_id:03d}"
        self._next_id += 1
        return boxel_id

    def add_boxel(self, boxel: BoxelData) -> str:
        if not boxel.id:
            prefix = self._PREFIX_FOR_TYPE.get(boxel.boxel_type, "boxel")
            boxel.id = self.generate_id(prefix)
        if (boxel.boxel_type == BoxelType.OBJECT
                and boxel.object_name is not None):
            for existing in self.boxels.values():
                if (existing.boxel_type == BoxelType.OBJECT
                        and existing.object_name == boxel.object_name
                        and existing.id != boxel.id):
                    raise ValueError(
                        f"Refusing to add OBJECT boxel id={boxel.id!r} for "
                        f"object_name={boxel.object_name!r}: a different "
                        f"OBJECT boxel id={existing.id!r} already claims that name."
                    )
        self.boxels[boxel.id] = boxel
        return boxel.id

    def get_boxel(self, boxel_id: str) -> Optional[BoxelData]:
        return self.boxels.get(boxel_id)

    def get_boxels_by_type(self, boxel_type: BoxelType) -> List[BoxelData]:
        return [b for b in self.boxels.values() if b.boxel_type == boxel_type]

    def get_object_boxels(self) -> List[BoxelData]:
        return self.get_boxels_by_type(BoxelType.OBJECT)

    def get_shadow_boxels(self) -> List[BoxelData]:
        return self.get_boxels_by_type(BoxelType.SHADOW)

    def get_free_space_boxels(self) -> List[BoxelData]:
        return self.get_boxels_by_type(BoxelType.FREE_SPACE)

    def remove_boxel(self, boxel_id: str) -> Optional[BoxelData]:
        return self.boxels.pop(boxel_id, None)

    def get_adjacent_free_boxels(self, region_min, region_max,
                                  exclude_ids=None, tolerance: float = 0.01):
        exclude = exclude_ids or set()
        result = []
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

    def update_after_place(self, free_boxel_id: str, object_boxel_id: str,
                           placed_min, placed_max, table_surface_height: float) -> None:
        self.remove_boxel(free_boxel_id)
        obj_boxel = self.get_boxel(object_boxel_id)
        if obj_boxel is not None:
            obj_boxel.min_corner = np.asarray(placed_min, dtype=float)
            obj_boxel.max_corner = np.asarray(placed_max, dtype=float)
            # 0.01 m (1 cm) tolerance accommodates PyBullet contact
            # margin + AABB rounding — same convention used in
            # execution.release_held_object_in_place and
            # boxel_env.annotate_free_space_surface.
            obj_boxel.on_surface = (
                "table" if placed_min[2] <= table_surface_height + 0.01 else None
            )
        self._dirty = True

    def to_dict(self) -> Dict[str, Any]:
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
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Saved {len(self.boxels)} boxels to {filepath}")

    @classmethod
    def load_from_json(cls, filepath: str) -> 'BoxelRegistry':
        with open(filepath, 'r') as f:
            data = json.load(f)
        registry = cls()
        for boxel_data in data["boxels"]:
            boxel = BoxelData.from_dict(boxel_data)
            registry.add_boxel(boxel)
        return registry
