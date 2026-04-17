"""
Boxel Visualization utilities.

This module handles rendering of boxels in the PyBullet GUI
using debug lines and semi-transparent phantom objects.
"""

import numpy as np
import pybullet as p
from typing import Dict, List, Optional
from boxel_types import Boxel


_EDGE_INDICES = [
    (0, 1), (0, 2), (0, 4), (1, 3), (1, 5),
    (2, 3), (2, 6), (3, 7), (4, 5), (4, 6),
    (5, 7), (6, 7),
]

_SIGN_COMBOS = np.array([
    [-1, -1, -1], [ 1, -1, -1], [-1,  1, -1], [ 1,  1, -1],
    [-1, -1,  1], [ 1, -1,  1], [-1,  1,  1], [ 1,  1,  1],
], dtype=float)


def wireframe_corners_and_edges(center, extent):
    """Return (corners, edges) for an axis-aligned box wireframe.

    corners: list of 8 numpy arrays (the AABB vertices).
    edges:   list of 12 (i, j) index pairs into *corners*.
    """
    corners = [center + extent * s for s in _SIGN_COMBOS]
    return corners, _EDGE_INDICES


class BoxelVisualizer:
    """
    Visualizes boxels in PyBullet using debug lines and phantom objects.
    
    Color coding:
    - Red = Occluder (Obstacle)
    - Blue = Target (Goal)
    - Gray = Shadow (Unknown/Occluded Region)
    - Cyan = Free Space
    - Yellow = Candidate (Processing)
    - Green = Other
    """
    
    def __init__(self):
        """Initialize the visualizer."""
        self.debug_items = []
        self.shadow_bodies = []
        self._items_by_id: Dict[str, List[int]] = {}
        self._bodies_by_id: Dict[str, List[int]] = {}
    
    def draw_boxels(self, boxels: List[Boxel], duration: float = 0, clear_previous: bool = True,
                    fill_opacity: float = 0.05, show_labels: bool = False,
                    label_size: float = 1.0):
        """
        Visualize Semantic Boxels in the PyBullet GUI using debug lines.
        
        Args:
            boxels: List of Boxel objects to visualize
            duration: How long lines remain visible (0 = forever)
            clear_previous: If True, clears previous debug items before drawing
            fill_opacity: Opacity for filled boxel phantoms (0.0 = invisible, 1.0 = solid)
            show_labels: If True, draw a text label on top of each boxel.
                Uses ``boxel.label`` if set, otherwise ``boxel.object_name``.
            label_size: Text size for labels (PyBullet default units).
        """
        # Remove existing shadow bodies
        for body_id in self.shadow_bodies:
            p.removeBody(body_id)
        self.shadow_bodies = []
        
        # Optionally remove existing debug lines
        if clear_previous:
            for item_id in self.debug_items:
                p.removeUserDebugItem(item_id)
            self.debug_items = []
        
        for boxel in boxels:
            c = boxel.center
            e = boxel.extent
            reg_id: Optional[str] = getattr(boxel, '_registry_id', None)
            boxel_item_ids: List[int] = []
            boxel_body_ids: List[int] = []
            
            corners, edges = wireframe_corners_and_edges(c, e)
            
            # Determine color
            color = self._get_boxel_color(boxel)
            
            # Determine line width
            is_thin = boxel.is_shadow or boxel.is_free or boxel.is_candidate
            
            # Draw wireframe
            for start_idx, end_idx in edges:
                line_id = p.addUserDebugLine(
                    lineFromXYZ=corners[start_idx],
                    lineToXYZ=corners[end_idx],
                    lineColorRGB=color,
                    lineWidth=1.0 if is_thin else 2.0, 
                    lifeTime=duration
                )
                self.debug_items.append(line_id)
                boxel_item_ids.append(line_id)
            
            # Draw filled phantom for all boxels
            body_id = self._draw_boxel_phantom(c, e, color, fill_opacity)
            if body_id is not None:
                boxel_body_ids.append(body_id)

            # Draw text label just above the top face
            if show_labels:
                text = boxel.label or boxel.object_name
                if text:
                    label_pos = [c[0], c[1], c[2] + e[2] + 0.01]
                    text_id = p.addUserDebugText(
                        text=text,
                        textPosition=label_pos,
                        textColorRGB=color,
                        textSize=label_size,
                        lifeTime=duration,
                    )
                    self.debug_items.append(text_id)
                    boxel_item_ids.append(text_id)

            if reg_id is not None:
                self._items_by_id[reg_id] = boxel_item_ids
                self._bodies_by_id[reg_id] = boxel_body_ids
    
    def _get_boxel_color(self, boxel: Boxel) -> List[float]:
        """Get the color for a boxel based on its type."""
        if boxel.is_candidate:
            return [1, 1, 0]  # Yellow - being processed
        elif boxel.is_shadow:
            return [0.5, 0.5, 0.5]  # Gray - shadow/occluded region
        elif boxel.is_free:
            return [0, 1, 1]  # Cyan - free space (before merge)
        elif boxel.object_name and boxel.object_name.startswith("free_space"):
            return [0, 1, 0]  # Green - merged free space
        elif boxel.is_occluder:
            return [1, 0, 0]  # Red - object that casts shadows (occluding something)
        elif boxel.object_name:
            return [0, 0, 1]  # Blue - object that doesn't occlude anything
        else:
            return [0, 1, 0]  # Green - fallback
    
    def _draw_boxel_phantom(self, center, extent, color, opacity) -> int:
        """Draw a semi-transparent phantom object for boxel visualization."""
        visual_shape_id = p.createVisualShape(
            shapeType=p.GEOM_BOX,
            halfExtents=extent,
            rgbaColor=[color[0], color[1], color[2], opacity],
            specularColor=[0, 0, 0]
        )
        
        body_id = p.createMultiBody(
            baseMass=0,
            baseVisualShapeIndex=visual_shape_id,
            basePosition=center,
            baseOrientation=[0, 0, 0, 1]
        )
        
        self.shadow_bodies.append(body_id)
        return body_id
    
    def draw_registry(self, registry, duration: float = 0,
                      fill_opacity: float = 0.05, label_size: float = 1.0,
                      skip_free: bool = True):
        """
        Draw all boxels from a BoxelRegistry with their registry IDs as labels.

        Args:
            registry: A BoxelRegistry instance (from boxel_data.py).
            duration: How long lines remain visible (0 = forever).
            fill_opacity: Opacity for filled boxel phantoms.
            label_size: Text size for labels.
            skip_free: If True, skip free-space boxels to reduce clutter.
        """
        from boxel_data import BoxelType

        boxels: List[Boxel] = []
        for bd in registry.boxels.values():
            if skip_free and bd.boxel_type == BoxelType.FREE_SPACE:
                continue
            if bd.boxel_type == BoxelType.OBJECT:
                label = bd.object_name or bd.id
            elif bd.boxel_type == BoxelType.SHADOW:
                label = (f"shadow_of_{bd.created_by_object}"
                         if bd.created_by_object else bd.id)
            else:
                label = bd.id
            b = Boxel(
                center=bd.center.copy(),
                extent=bd.extent.copy(),
                object_name=bd.object_name,
                label=label,
                is_shadow=(bd.boxel_type == BoxelType.SHADOW),
                is_occluder=bd.is_occluder,
                is_free=(bd.boxel_type == BoxelType.FREE_SPACE),
            )
            b._registry_id = bd.id  # stash for per-ID tracking
            boxels.append(b)

        self.draw_boxels(boxels, duration=duration, clear_previous=True,
                         fill_opacity=fill_opacity, show_labels=True,
                         label_size=label_size)

    def remove_boxel_viz(self, boxel_id: str) -> None:
        """Remove all debug lines, labels, and phantom bodies for one boxel."""
        for item_id in self._items_by_id.pop(boxel_id, []):
            p.removeUserDebugItem(item_id)
            if item_id in self.debug_items:
                self.debug_items.remove(item_id)
        for body_id in self._bodies_by_id.pop(boxel_id, []):
            p.removeBody(body_id)
            if body_id in self.shadow_bodies:
                self.shadow_bodies.remove(body_id)

    def draw_boxel_data(self, bd, duration: float = 0,
                        fill_opacity: float = 0.05,
                        label_size: float = 1.0) -> None:
        """
        Draw a single BoxelData entry and track its visuals by ID.

        Args:
            bd: A BoxelData instance (from boxel_data.py).
            duration: How long lines remain visible (0 = forever).
            fill_opacity: Opacity for filled phantom.
            label_size: Text size for label.
        """
        from boxel_data import BoxelType

        if bd.boxel_type == BoxelType.OBJECT:
            label = bd.object_name or bd.id
        elif bd.boxel_type == BoxelType.SHADOW:
            label = (f"shadow_of_{bd.created_by_object}"
                     if bd.created_by_object else bd.id)
        else:
            label = bd.id

        b = Boxel(
            center=bd.center.copy(),
            extent=bd.extent.copy(),
            object_name=bd.object_name,
            label=label,
            is_shadow=(bd.boxel_type == BoxelType.SHADOW),
            is_occluder=bd.is_occluder,
            is_free=(bd.boxel_type == BoxelType.FREE_SPACE),
        )

        c, e = b.center, b.extent
        color = self._get_boxel_color(b)
        is_thin = b.is_shadow or b.is_free or b.is_candidate

        item_ids: List[int] = []
        corners, edges = wireframe_corners_and_edges(c, e)
        for si, ei in edges:
            lid = p.addUserDebugLine(
                lineFromXYZ=corners[si], lineToXYZ=corners[ei],
                lineColorRGB=color,
                lineWidth=1.0 if is_thin else 2.0,
                lifeTime=duration,
            )
            self.debug_items.append(lid)
            item_ids.append(lid)

        tid = p.addUserDebugText(
            text=label,
            textPosition=[c[0], c[1], c[2] + e[2] + 0.01],
            textColorRGB=color,
            textSize=label_size,
            lifeTime=duration,
        )
        self.debug_items.append(tid)
        item_ids.append(tid)

        self._items_by_id[bd.id] = item_ids

        vis = p.createVisualShape(
            shapeType=p.GEOM_BOX, halfExtents=e,
            rgbaColor=[color[0], color[1], color[2], fill_opacity],
            specularColor=[0, 0, 0],
        )
        body = p.createMultiBody(
            baseMass=0, baseVisualShapeIndex=vis,
            basePosition=c, baseOrientation=[0, 0, 0, 1],
        )
        self.shadow_bodies.append(body)
        self._bodies_by_id[bd.id] = [body]

    def clear_all(self):
        """Clear all debug items and shadow bodies."""
        for body_id in self.shadow_bodies:
            p.removeBody(body_id)
        self.shadow_bodies = []
        
        for item_id in self.debug_items:
            p.removeUserDebugItem(item_id)
        self.debug_items = []
