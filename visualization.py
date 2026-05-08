"""
Boxel Visualization utilities.

This module handles rendering of boxels in the PyBullet GUI
using debug lines and semi-transparent phantom objects.

Audit #35 (2026-04-17): unified to consume :class:`boxel_data.BoxelData`
directly.  The previous shim that converted BoxelData → boxel_types.Boxel
inside :meth:`BoxelVisualizer.draw_registry` and :meth:`draw_boxel_data`
has been removed.
"""

import numpy as np
import pybullet as p
from typing import Dict, List, Optional, Set

from boxel_data import BoxelData, BoxelType


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


def _color_for_boxel(bd: BoxelData) -> List[float]:
    """
    Color a boxel based on its semantic type and role.

    SHADOW   → gray
    FREE     → cyan  (matches the pre-#35 visual; the pre-merge "green
               for merged" branch in the old bridge was dead code because
               free boxels never had ``object_name`` set, so every free
               cell fell through to cyan in practice)
    OBJECT + is_occluder → red
    OBJECT (non-occluder) → blue
    Anything else → green fallback
    """
    if bd.boxel_type == BoxelType.SHADOW:
        return [0.5, 0.5, 0.5]
    if bd.boxel_type == BoxelType.FREE_SPACE:
        return [0.0, 1.0, 1.0]
    if bd.boxel_type == BoxelType.OBJECT:
        return [1.0, 0.0, 0.0] if bd.is_occluder else [0.0, 0.0, 1.0]
    return [0.0, 1.0, 0.0]


def _label_for_boxel(bd: BoxelData) -> str:
    """Human-readable label drawn above each boxel."""
    if bd.boxel_type == BoxelType.OBJECT:
        return bd.object_name or bd.id
    if bd.boxel_type == BoxelType.SHADOW:
        if bd.created_by_object:
            return f"shadow_of_{bd.created_by_object}"
        return bd.id
    return bd.id


class BoxelVisualizer:
    """
    Visualizes boxels in PyBullet using debug lines and phantom objects.

    Color coding (see :func:`_color_for_boxel`):
    - Red  = Occluder (OBJECT with is_occluder=True)
    - Blue = Visible non-occluding object
    - Gray = SHADOW
    - Cyan = FREE_SPACE (merged)

    uniform_mode (audit #64 — TAMPURA-faithful, Curtis et al. 2024):
        When True, OBJECT and SHADOW BoxelData are suppressed from
        the overlay so only the FREE lattice renders.  Mirrors
        TAMPURA's VoxelGrid (binary {free, occupied}; occupied is
        implicit, never drawn).  PyBullet's own object rendering
        provides the physical scene underneath.  OBJECT/SHADOW
        records remain in the BoxelRegistry — they are the planner's
        per-object handles (TAMPURA's `object_poses` equivalent),
        only their viz is hidden.  Default False = semantic mode.
    """

    def __init__(self, *, uniform_mode: bool = False):
        """Initialize the visualizer.

        Args:
            uniform_mode: If True, skip OBJECT and SHADOW boxels in
                every draw call.  Set this when running under
                ``--baseline uniform`` so the GUI matches the
                TAMPURA-faithful framing (audit #64).
        """
        # Sets (audit #33): remove_boxel_viz() needs O(1) membership and
        # removal because reboxelization can churn many entries per replan.
        self.debug_items: Set[int] = set()
        self.shadow_bodies: Set[int] = set()
        self._items_by_id: Dict[str, List[int]] = {}
        self._bodies_by_id: Dict[str, List[int]] = {}
        self.uniform_mode = uniform_mode

    def _should_draw(self, bd: BoxelData) -> bool:
        """Whether ``bd`` survives the active draw filter.

        Under :attr:`uniform_mode`, OBJECT and SHADOW are suppressed
        so the GUI shows only the FREE lattice (audit #64).  All
        other types — including FREE_SPACE — pass through.
        """
        if self.uniform_mode and bd.boxel_type in (
                BoxelType.OBJECT, BoxelType.SHADOW):
            return False
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw_boxel_phantom(self, center, extent, color, opacity) -> int:
        """Draw a semi-transparent phantom AABB and return its body id."""
        visual_shape_id = p.createVisualShape(
            shapeType=p.GEOM_BOX,
            halfExtents=extent,
            rgbaColor=[color[0], color[1], color[2], opacity],
            specularColor=[0, 0, 0],
        )
        body_id = p.createMultiBody(
            baseMass=0,
            baseVisualShapeIndex=visual_shape_id,
            basePosition=center,
            baseOrientation=[0, 0, 0, 1],
        )
        self.shadow_bodies.add(body_id)
        return body_id

    def _draw_one_boxel(self, bd: BoxelData, *, duration: float,
                        fill_opacity: float, show_labels: bool,
                        label_size: float) -> tuple[List[int], List[int]]:
        """Draw a single BoxelData; return (debug_item_ids, body_ids)."""
        c = bd.center
        e = bd.extent
        color = _color_for_boxel(bd)
        # SHADOW and FREE_SPACE are visually quieter (thinner edges) so
        # OBJECT boxels stand out against the background partition.
        is_thin = bd.boxel_type in (BoxelType.SHADOW, BoxelType.FREE_SPACE)

        item_ids: List[int] = []
        body_ids: List[int] = []

        corners, edges = wireframe_corners_and_edges(c, e)
        for start_idx, end_idx in edges:
            line_id = p.addUserDebugLine(
                lineFromXYZ=corners[start_idx],
                lineToXYZ=corners[end_idx],
                lineColorRGB=color,
                lineWidth=1.0 if is_thin else 2.0,
                lifeTime=duration,
            )
            self.debug_items.add(line_id)
            item_ids.append(line_id)

        body_id = self._draw_boxel_phantom(c, e, color, fill_opacity)
        body_ids.append(body_id)

        if show_labels:
            text = _label_for_boxel(bd)
            if text:
                label_pos = [c[0], c[1], c[2] + e[2] + 0.01]
                text_id = p.addUserDebugText(
                    text=text,
                    textPosition=label_pos,
                    textColorRGB=color,
                    textSize=label_size,
                    lifeTime=duration,
                )
                self.debug_items.add(text_id)
                item_ids.append(text_id)

        return item_ids, body_ids

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw_boxels(self, boxels: List[BoxelData], duration: float = 0,
                    clear_previous: bool = True,
                    fill_opacity: float = 0.05,
                    show_labels: bool = False,
                    label_size: float = 1.0):
        """
        Visualize a list of BoxelData in the PyBullet GUI.

        Args:
            boxels: BoxelData entries to draw.
            duration: How long lines remain visible (0 = forever).
            clear_previous: If True, clears previous debug items before drawing.
            fill_opacity: Opacity for filled boxel phantoms (0 = invisible).
            show_labels: If True, draw a text label on top of each boxel
                using :func:`_label_for_boxel`.
            label_size: Text size for labels (PyBullet default units).
        """
        for body_id in self.shadow_bodies:
            p.removeBody(body_id)
        self.shadow_bodies.clear()

        if clear_previous:
            for item_id in self.debug_items:
                p.removeUserDebugItem(item_id)
            self.debug_items.clear()
            self._items_by_id.clear()
            self._bodies_by_id.clear()

        for bd in boxels:
            if not self._should_draw(bd):
                continue
            item_ids, body_ids = self._draw_one_boxel(
                bd, duration=duration, fill_opacity=fill_opacity,
                show_labels=show_labels, label_size=label_size,
            )
            if bd.id:
                self._items_by_id[bd.id] = item_ids
                self._bodies_by_id[bd.id] = body_ids

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
            skip_free: If True, skip FREE_SPACE boxels to reduce clutter.
        """
        boxels = [
            bd for bd in registry.boxels.values()
            if not (skip_free and bd.boxel_type == BoxelType.FREE_SPACE)
        ]
        self.draw_boxels(
            boxels, duration=duration, clear_previous=True,
            fill_opacity=fill_opacity, show_labels=True,
            label_size=label_size,
        )

    def draw_boxel_data(self, bd: BoxelData, duration: float = 0,
                        fill_opacity: float = 0.05,
                        label_size: float = 1.0) -> None:
        """
        Draw a single BoxelData entry and track its visuals by ID.

        Used by the execution loop to incrementally update the overlay
        when new objects/shadows are discovered or fragments are
        added by reboxelization (see test_full_pipeline.py).

        Under :attr:`uniform_mode` (audit #64), OBJECT and SHADOW
        BoxelData are silently dropped here too — discovery in
        execution.py registers the BoxelData unconditionally so the
        planner sees it; the overlay just hides it.
        """
        if not self._should_draw(bd):
            return
        item_ids, body_ids = self._draw_one_boxel(
            bd, duration=duration, fill_opacity=fill_opacity,
            show_labels=True, label_size=label_size,
        )
        if bd.id:
            self._items_by_id[bd.id] = item_ids
            self._bodies_by_id[bd.id] = body_ids

    def remove_boxel_viz(self, boxel_id: str) -> None:
        """Remove all debug lines, labels, and phantom bodies for one boxel."""
        for item_id in self._items_by_id.pop(boxel_id, []):
            p.removeUserDebugItem(item_id)
            self.debug_items.discard(item_id)
        for body_id in self._bodies_by_id.pop(boxel_id, []):
            p.removeBody(body_id)
            self.shadow_bodies.discard(body_id)

    def clear_all(self):
        """Clear all debug items and shadow bodies."""
        for body_id in self.shadow_bodies:
            p.removeBody(body_id)
        self.shadow_bodies.clear()

        for item_id in self.debug_items:
            p.removeUserDebugItem(item_id)
        self.debug_items.clear()
        self._items_by_id.clear()
        self._bodies_by_id.clear()
