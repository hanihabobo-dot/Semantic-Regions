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


# ---------------------------------------------------------------------------
# #P1 F19 (2026-08-23): the debug overlay must NEVER appear in the robot's
# observation.
#
# The phantom AABB fills are VISUAL-ONLY multibodies (no collision shape):
# pybullet.rayTestBatch intersects collision shapes, so the pre-step-3
# ray-based sense passed straight through them — but getCameraImage's
# TinyRenderer renders VISUAL shapes, so once step (3) moved sensing onto
# the rendered depth+seg observation, every GUI run handed the classifiers
# an image containing the overlay itself.  A shadow fragment's own
# translucent box stands in front of its own sense-grid endpoints: the
# first surface at those pixels is the phantom (a seg id that is not in
# body_id_to_name), found_target can never fire even with the target
# plainly visible through the overlay, the discovery is "unlocalizable",
# and an OBJECT boxel's phantom hides its own object from the refresh
# render ("not visible — keeping last estimate").  Field evidence: run
# 2026-08-23_11-25-45 ([F15-diag] seg id 12, 1197 px, 118/138 endpoints of
# shadow_of_red intercepted while blue_object was localized in the same
# frame).  Headless runs were never affected — the visualizer only exists
# under the GUI — which is exactly why the regression survived a green
# headless battery.
#
# Fix: every phantom registers its home position here, and the perception
# render (BoxelTestEnv.detect_objects — the single observation chokepoint)
# brackets getCameraImage with conceal/restore.  Concealment teleports the
# phantoms 100 m below the scene for the microseconds of the TinyRenderer
# pass; teleporting is renderer-agnostic (alpha tricks are not — TinyRenderer
# still writes seg/depth for transparent visuals) and the bodies are
# massless and collisionless, so physics cannot notice.  The user-facing
# ExampleBrowser view is drawn by the separate OpenGL renderer and keeps
# its overlays; at worst a single frame flickers during a sense.
# ---------------------------------------------------------------------------

_PHANTOM_HOME: Dict[int, tuple] = {}
_CONCEAL_DROP = 100.0          # metres straight down, far below any camera
_conceal_depth = 0             # re-entrancy guard


def conceal_overlay_for_observation() -> None:
    """Teleport every phantom overlay body out of camera view (#P1 F19)."""
    global _conceal_depth
    _conceal_depth += 1
    if _conceal_depth > 1:
        return
    for body_id, home in list(_PHANTOM_HOME.items()):
        try:
            p.resetBasePositionAndOrientation(
                body_id, [home[0], home[1], home[2] - _CONCEAL_DROP],
                [0, 0, 0, 1])
        except Exception:
            # A body removed between registration and concealment is not
            # an error — it simply no longer needs hiding.
            _PHANTOM_HOME.pop(body_id, None)


def restore_overlay_after_observation() -> None:
    """Return every phantom overlay body to its drawn position (#P1 F19)."""
    global _conceal_depth
    _conceal_depth = max(0, _conceal_depth - 1)
    if _conceal_depth > 0:
        return
    for body_id, home in list(_PHANTOM_HOME.items()):
        try:
            p.resetBasePositionAndOrientation(
                body_id, list(home), [0, 0, 0, 1])
        except Exception:
            _PHANTOM_HOME.pop(body_id, None)


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
    """

    def __init__(self):
        """Initialize the visualizer."""
        # Sets (audit #33): remove_boxel_viz() needs O(1) membership and
        # removal because reboxelization can churn many entries per replan.
        self.debug_items: Set[int] = set()
        self.shadow_bodies: Set[int] = set()
        self._items_by_id: Dict[str, List[int]] = {}
        self._bodies_by_id: Dict[str, List[int]] = {}

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
        _PHANTOM_HOME[body_id] = (float(center[0]), float(center[1]),
                                  float(center[2]))
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
        """
        # Hardening (2026-08-21 review): drawing an id that is already
        # tracked would overwrite the tracking lists and orphan the old
        # wireframe/label on screen until clear_all.  Every current
        # caller removes first, but self-removing here makes the
        # invariant local instead of contractual.
        if bd.id and self.tracks_boxel(bd.id):
            self.remove_boxel_viz(bd.id)
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
            _PHANTOM_HOME.pop(body_id, None)

    def tracks_boxel(self, boxel_id: str) -> bool:
        """Whether any debug item or phantom body is still tracked for ``boxel_id``.

        Used as a sanity check by the execution layer after removing a
        sensed shadow — if this returns True post-``remove_boxel_viz``,
        the GUI overlay was not actually cleared (the shadow wireframe /
        label / phantom box is still drawn on screen).
        """
        return boxel_id in self._items_by_id or boxel_id in self._bodies_by_id

    def clear_all(self):
        """Clear all debug items and shadow bodies."""
        for body_id in self.shadow_bodies:
            p.removeBody(body_id)
            _PHANTOM_HOME.pop(body_id, None)
        self.shadow_bodies.clear()

        for item_id in self.debug_items:
            p.removeUserDebugItem(item_id)
        self.debug_items.clear()
        self._items_by_id.clear()
        self._bodies_by_id.clear()
