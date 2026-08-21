"""
perception.py — shared sense-grid geometry (seed of the #P1 step-(2)
perception module).

Single source of truth for WHERE the sense action's rays terminate
inside a shadow fragment.  Both the physical sense
(execution.sense_shadow_raycasting), the scheduler's blocker census
(execution.compute_shadow_blockers) and the spawn-time findability
guarantee (F5 pre-flight / Phase-4 classification, via grid_would_hit)
build their geometry from sense_ray_slices(), so "the harness promised
the target is findable", "the planner's view-blocked facts" and "the
rays the sense actually casts" can never disagree (audit F5: the
spawn-time hidden classification used to promise findability that the
sense grid geometrically could not deliver for the post-resize 3-4 cm
targets — every ray endpoint sat at fragment_base + 0.04 m, above the
targets' tops).

Pure numpy — no pybullet import, so the module is usable from every
layer (env construction, execution, DIRECT pre-flight probes) without
import cycles.
"""

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

# Marginal-clip tolerance shared by the sense classifier AND the
# blocker census (F5): a slice with at most this fraction of blocked
# rays is classified by its remaining rays, and an object whose removal
# is not needed to bring every slice under this fraction is NOT listed
# as a blocker.  One constant, or the census would demand relocations
# (blocks_view_at pins the shadow blocked) that the sense itself would
# have tolerated — observed on seed 0: green at free_010 grazed 1/674
# rays, stayed listed as a blocker of its old shadow, and the forced
# relocate-again plan walked into the re-pick stream-binding failure.
SENSE_MARGINAL_BLOCKED_FRACTION = 0.05

# Lowest slice sits this far above the fragment base.  Targets rest on
# the fragment base (table or, for z-split fragments, an obstacle top);
# the smallest target half-extent is 0.015 m (scalability_scene), so a
# 0.02 m endpoint lies strictly INSIDE any target body whose footprint
# contains it — a ray terminating there must have entered the body.
# 0.02 m also keeps 2 cm clearance above the support surface: rays
# descend monotonically from the camera and bottom out AT the endpoint,
# so they cannot graze the table on the way (verified empirically in
# tools/_diag_f5_seed0.py: zero table hits).
SENSE_LOW_SLICE_OFFSET = 0.02

# XY endpoint spacing on the dense low slice.  The smallest target
# footprint is 0.03 m; at 0.012 m spacing every axis-interval of width
# >= 0.015 m contains a grid point, so any target whose centre lies
# inside the fragment presents at least one endpoint inside its
# footprint (12 mm < 15 mm leaves margin for boundary-straddling and
# fragments narrower than the cube).
SENSE_DENSE_SPACING = 0.012

# Per-axis endpoint count on the two coarse upper slices (unchanged
# from the historical 7x7 grid — they classify blockage by tall
# occluders / the arm, not small-target presence).
SENSE_COARSE_N = 7

# Per-axis cap on the dense slice.  Binds only for fragment extents
# > 0.75 m (wider than the table window — practically unreachable) and
# is LOGGED by the caller when it binds, so coverage is never silently
# reduced.  64x64 + 2x49 rays stays far below pybullet's 16384-ray
# batch limit.
SENSE_MAX_N_PER_AXIS = 64

# Two slices closer than this in z collapse into one (thin elevated
# sliver fragments, down to 4 mm tall, would otherwise cast three
# near-identical ray batches).
_SLICE_DEDUPE_Z = 0.004


@dataclass
class SenseSlice:
    """One horizontal endpoint layer of the sense ray grid."""
    z: float
    points: np.ndarray        # (n_x * n_y, 3) ray endpoints
    spacing_x: float          # endpoint spacing along x (0 for n_x == 1)
    spacing_y: float
    pad_z_down: float         # unobserved gap below this slice
    pad_z_up: float           # unobserved gap above this slice
    dense: bool               # True for the low guaranteed-hit slice


def sense_ray_slices(min_corner, max_corner) -> Tuple[List[SenseSlice], bool]:
    """Build the sense ray-endpoint slices for a fragment AABB.

    Returns (slices sorted by z, capped) where ``capped`` is True when
    the dense slice hit SENSE_MAX_N_PER_AXIS and its spacing therefore
    exceeds SENSE_DENSE_SPACING (caller must log this — no silent
    coverage reduction).

    Slice layout: one dense slice near the fragment base (guaranteed to
    hit any >= 3 cm target whose centre is inside the fragment) plus the
    two historical coarse slices at 0.33/0.67 of the fragment height.
    All slice heights are clamped INSIDE the fragment's z-range and
    deduplicated, so thin elevated slivers (a few mm tall) get one
    mid-height slice instead of three vacuous ones above their top —
    the pre-F5 grid sampled nothing of such fragments.
    """
    min_c = np.asarray(min_corner, dtype=float)
    max_c = np.asarray(max_corner, dtype=float)
    height = float(max_c[2] - min_c[2])

    # Candidate heights: dense low slice first so dedup keeps it.
    z_low = float(min_c[2] + min(SENSE_LOW_SLICE_OFFSET, 0.5 * height))
    candidates = [(z_low, True),
                  (float(min_c[2] + height * 0.33), False),
                  (float(min_c[2] + height * 0.67), False)]
    kept: List[Tuple[float, bool]] = []
    for z, dense in candidates:
        if all(abs(z - kz) >= _SLICE_DEDUPE_Z for kz, _ in kept):
            kept.append((z, dense))
    kept.sort(key=lambda t: t[0])

    ext_x = float(max_c[0] - min_c[0])
    ext_y = float(max_c[1] - min_c[1])
    capped = False
    slices: List[SenseSlice] = []
    for i, (z, dense) in enumerate(kept):
        if dense:
            nx = max(2, int(np.ceil(ext_x / SENSE_DENSE_SPACING)) + 1)
            ny = max(2, int(np.ceil(ext_y / SENSE_DENSE_SPACING)) + 1)
            if nx > SENSE_MAX_N_PER_AXIS or ny > SENSE_MAX_N_PER_AXIS:
                capped = True
                nx = min(nx, SENSE_MAX_N_PER_AXIS)
                ny = min(ny, SENSE_MAX_N_PER_AXIS)
        else:
            nx = ny = SENSE_COARSE_N
        xs = np.linspace(min_c[0], max_c[0], nx)
        ys = np.linspace(min_c[1], max_c[1], ny)
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        pts = np.column_stack([gx.ravel(), gy.ravel(),
                               np.full(gx.size, z)])
        pad_down = z - (kept[i - 1][0] if i > 0 else float(min_c[2]))
        pad_up = (kept[i + 1][0] if i + 1 < len(kept)
                  else float(max_c[2])) - z
        slices.append(SenseSlice(
            z=z, points=pts,
            spacing_x=ext_x / (nx - 1) if nx > 1 else 0.0,
            spacing_y=ext_y / (ny - 1) if ny > 1 else 0.0,
            pad_z_down=pad_down, pad_z_up=pad_up, dense=dense))
    return slices, capped


def _segments_intersect_aabb(origin: np.ndarray, endpoints: np.ndarray,
                             bmin: np.ndarray, bmax: np.ndarray) -> bool:
    """True if any segment origin->endpoint intersects the AABB.

    Slab test restricted to t in [0, 1] — rays TERMINATE at their
    endpoint (matching pybullet rayTestBatch), so a body beyond the
    endpoint does not count.
    """
    d = endpoints - origin[None, :]
    t_lo = np.zeros(len(endpoints))
    t_hi = np.ones(len(endpoints))
    for a in range(3):
        da = d[:, a]
        parallel = np.abs(da) < 1e-12
        with np.errstate(divide="ignore", invalid="ignore"):
            ta = (bmin[a] - origin[a]) / da
            tb = (bmax[a] - origin[a]) / da
        lo = np.minimum(ta, tb)
        hi = np.maximum(ta, tb)
        inside = bool(bmin[a] <= origin[a] <= bmax[a])
        lo = np.where(parallel, -np.inf if inside else np.inf, lo)
        hi = np.where(parallel, np.inf if inside else -np.inf, hi)
        t_lo = np.maximum(t_lo, lo)
        t_hi = np.minimum(t_hi, hi)
    return bool(np.any(t_lo <= t_hi))


def grid_would_hit(camera_pos, frag_min, frag_max,
                   target_min, target_max) -> bool:
    """Would the sense ray grid for this fragment hit the target body?

    Pure geometry (no physics client): generates the IDENTICAL endpoint
    list the live sense casts and segment-tests it against the target's
    AABB.  The target box is shrunk by 1 mm per side so a corner-graze
    does not count as findable — the guarantee stays conservative
    (same EPS idea as _hidden_xy_positions' corner shrink).
    """
    slices, _ = sense_ray_slices(frag_min, frag_max)
    if not slices:
        return False
    endpoints = np.vstack([s.points for s in slices])
    bmin = np.asarray(target_min, dtype=float) + 1e-3
    bmax = np.asarray(target_max, dtype=float) - 1e-3
    if np.any(bmin >= bmax):        # degenerate after shrink
        centre = (np.asarray(target_min, dtype=float)
                  + np.asarray(target_max, dtype=float)) / 2.0
        bmin = np.minimum(bmin, centre - 1e-6)
        bmax = np.maximum(bmax, centre + 1e-6)
    return _segments_intersect_aabb(
        np.asarray(camera_pos, dtype=float), endpoints, bmin, bmax)
