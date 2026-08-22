"""
perception.py — shared sense-grid geometry (seed of the #P1 step-(2)
perception module).

Single source of truth for WHERE the sense action's rays terminate
inside a shadow fragment.  Both the physical sense
(execution.sense_shadow_from_render), the scheduler's blocker census
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
from typing import Dict, FrozenSet, List, Tuple

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


def segment_aabb_hit_mask(origin, endpoints, bmin, bmax) -> np.ndarray:
    """Per-segment boolean mask: does origin->endpoint intersect the AABB?

    Slab test restricted to t in [0, 1] — rays TERMINATE at their
    endpoint (matching pybullet rayTestBatch), so a body beyond the
    endpoint does not count.  Vectorized over endpoints so callers can
    COUNT blocked rays per slice (the shared marginal tolerance needs
    fractions, not just any-hit).
    """
    origin = np.asarray(origin, dtype=float)
    endpoints = np.asarray(endpoints, dtype=float)
    bmin = np.asarray(bmin, dtype=float)
    bmax = np.asarray(bmax, dtype=float)
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
    return t_lo <= t_hi


def _segments_intersect_aabb(origin: np.ndarray, endpoints: np.ndarray,
                             bmin: np.ndarray, bmax: np.ndarray) -> bool:
    """True if any segment origin->endpoint intersects the AABB."""
    return bool(np.any(segment_aabb_hit_mask(origin, endpoints, bmin, bmax)))


# #P1 step (3): metric depth slack for the render-based sense.  An
# endpoint is INTERCEPTED when the rendered first surface at its pixel
# lies more than this many metres in front of it (view-axis depth).
# The depth buffer's own quantisation is micrometres here (float32 at
# 0.6-0.9 m with near 0.01 / far 5.0); the real mismatch source is that
# the buffer samples the PIXEL-CENTRE ray while the endpoint projects
# off-centre — worst near grazing surfaces.  3 mm absorbs that without
# masking any real interposition: a body in front of an endpoint
# overlaps it by >= the 1 cm-scale margins the grid guarantees
# (SENSE_LOW_SLICE_OFFSET puts the dense endpoints >= 5 mm inside any
# >= 3 cm target).
SENSE_RENDER_DEPTH_TOL = 0.003


def project_points_to_pixels(points, view_matrix, projection_matrix,
                             width: int, height: int):
    """World points -> (rows, cols, view_depth_m, in_view) for the render.

    Exact inverse of :func:`unproject_depth_pixels`'s pixel convention:
    a point unprojected from pixel centre (r, c) projects back to
    rows[i] == r, cols[i] == c.  ``view_depth_m`` is the distance along
    the camera FORWARD axis (the quantity a metric depth image stores),
    NOT the euclidean ray length.  ``in_view`` marks points that land
    inside the image and in front of the near plane; rows/cols are
    rounded to the nearest pixel and only valid where ``in_view``.
    """
    pts = np.asarray(points, dtype=float)
    proj = np.asarray(projection_matrix, dtype=float).reshape(4, 4, order="F")
    view = np.asarray(view_matrix, dtype=float).reshape(4, 4, order="F")
    ones = np.ones((len(pts), 1))
    homo = np.hstack([pts, ones])
    view_pts = homo @ view.T
    depth_m = -view_pts[:, 2]           # OpenGL camera looks down -Z
    clip = view_pts @ proj.T
    with np.errstate(divide="ignore", invalid="ignore"):
        ndc = clip[:, :3] / clip[:, 3:4]
    cols = np.rint((ndc[:, 0] + 1.0) * width / 2.0 - 0.5).astype(int)
    rows = np.rint((1.0 - ndc[:, 1]) * height / 2.0 - 0.5).astype(int)
    in_view = ((depth_m > 0.0)
               & (rows >= 0) & (rows < height)
               & (cols >= 0) & (cols < width))
    return rows, cols, depth_m, in_view


def first_surface_interceptors(endpoints, depth_image_m, seg_mask,
                               view_matrix, projection_matrix,
                               depth_tol: float = SENSE_RENDER_DEPTH_TOL):
    """Which rendered surface, if any, stands in FRONT of each endpoint?

    The render-based counterpart of a terminating ray cast (#P1 step 3):
    for each world endpoint, look up the rendered first surface at its
    pixel and compare view-axis depths.  Returns (intercepted, hit_ids,
    in_view):

      * intercepted[i] — a surface lies more than ``depth_tol`` metres
        in front of endpoint i, i.e. the camera cannot see the endpoint;
        the sense semantics of "the ray never reached its target".
      * hit_ids[i] — the seg-mask id of that surface (valid only where
        intercepted; the seg mask is the accepted sim-grade identity
        map).
      * in_view[i] — endpoint projects into the image; endpoints outside
        the frame are never claimed observed (callers treat them as
        blocked/unknown, not clear).

    A surface AT or BEYOND the endpoint leaves it un-intercepted: rays
    terminate at their endpoints, so bodies behind the endpoint never
    count — matching pybullet.rayTestBatch semantics.
    """
    endpoints = np.asarray(endpoints, dtype=float)
    depth_image_m = np.asarray(depth_image_m, dtype=float)
    seg = np.asarray(seg_mask)
    h, w = depth_image_m.shape
    rows, cols, depth_m, in_view = project_points_to_pixels(
        endpoints, view_matrix, projection_matrix, w, h)
    intercepted = np.zeros(len(endpoints), dtype=bool)
    hit_ids = np.full(len(endpoints), -1, dtype=int)
    iv = np.nonzero(in_view)[0]
    if iv.size:
        r, c = rows[iv], cols[iv]
        surf = depth_image_m[r, c]
        front = surf < (depth_m[iv] - depth_tol)
        idx = iv[front]
        intercepted[idx] = True
        hit_ids[idx] = seg[rows[idx], cols[idx]]
    return intercepted, hit_ids, in_view


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


# ---------------------------------------------------------------------------
# #P1 step (2): render-based object detection.
#
# Sim-grade "real perception": the fixed scene camera renders RGB + depth +
# instance segmentation (pybullet getCameraImage), each segmented object's
# depth pixels are unprojected to a world-frame point cloud, and the cloud
# yields a per-object AABB/pose ESTIMATE.  Planning consumes these
# estimates; the body-id oracle (BoxelTestEnv.oracle_detect_objects)
# survives only for the eval harness's ground-truth checks (Phase-1 settle
# sanity, Phase-4 hidden/visible split, F5 pre-flight target AABB).
#
# The functions below stay pure numpy (no pybullet import — the module
# contract): the caller renders and passes arrays + the OpenGL matrices.
# ---------------------------------------------------------------------------

# An object is detected when its segmentation id covers at least this many
# pixels.  Below that a cloud is too thin to localize (single-edge slivers);
# the object simply stays unknown to the planner — honest partial
# observability.  The 8-corner ray oracle stays the harness's ground truth
# for the hidden/visible SPLIT, so a disagreement here is a perception
# limitation, not a scene-classification change.
DETECTION_MIN_PIXELS = 6

# When the cloud's lowest point comes within this height of a known support
# surface, the estimated AABB is extended down to rest ON the surface: the
# bottom edge of a resting object is almost always cut by the surface
# itself, never observed.  Objects floating higher (stacked cubes, tray
# contents) keep their observed bottom — no guess.
DETECTION_SUPPORT_SNAP = 0.02


@dataclass
class ObjectDetection:
    """One detected object: segmentation pixels -> world-frame estimate."""
    name: str
    body_id: int
    pixel_count: int
    est_min: np.ndarray       # estimated AABB min corner (world frame)
    est_max: np.ndarray       # estimated AABB max corner (world frame)

    @property
    def est_center(self) -> np.ndarray:
        return (self.est_min + self.est_max) / 2.0


def unproject_depth_pixels(rows, cols, depth_values,
                           view_matrix, projection_matrix,
                           width: int, height: int) -> np.ndarray:
    """Unproject pixel coordinates + RAW depth-buffer values to world points.

    Canonical OpenGL inverse: NDC = (2(u+.5)/W - 1, 1 - 2(v+.5)/H, 2d - 1),
    world = (P·V)^-1 · clip.  ``view_matrix`` / ``projection_matrix`` are
    the column-major 16-tuples pybullet's computeViewMatrix /
    computeProjectionMatrixFOV return; ``depth_values`` are the raw [0,1]
    buffer values (NOT meters).  Row 0 is the TOP image row (pybullet
    convention).
    """
    proj = np.asarray(projection_matrix, dtype=float).reshape(4, 4, order="F")
    view = np.asarray(view_matrix, dtype=float).reshape(4, 4, order="F")
    pix_to_world = np.linalg.inv(proj @ view)
    x = (2.0 * (np.asarray(cols, dtype=float) + 0.5) - width) / width
    y = -((2.0 * (np.asarray(rows, dtype=float) + 0.5) - height) / height)
    z = 2.0 * np.asarray(depth_values, dtype=float) - 1.0
    clip = np.column_stack([x, y, z, np.ones_like(x)])
    world = clip @ pix_to_world.T
    return world[:, :3] / world[:, 3:4]


def detect_objects_from_render(seg_mask: np.ndarray,
                               depth_buffer: np.ndarray,
                               view_matrix, projection_matrix,
                               body_id_to_name: Dict[int, str],
                               camera_xy,
                               support_z: float,
                               min_pixels: int = DETECTION_MIN_PIXELS,
                               no_footprint_completion: FrozenSet[str] = frozenset()
                               ) -> Dict[str, "ObjectDetection"]:
    """Per-object AABB/pose estimates from one rendered observation.

    For each candidate body id present in ``seg_mask`` with at least
    ``min_pixels`` pixels: unproject its depth pixels to a world cloud and
    take the cloud's AABB, then apply two completion priors for the
    surfaces a single fixed camera can never observe:

    1. support snap — a bottom within DETECTION_SUPPORT_SNAP of
       ``support_z`` extends down to it (resting objects' bottoms are cut
       by the surface, not seen);
    2. square-footprint — scene objects are box-like with near-square
       footprints, but the face AWAY from the camera is invisible, so the
       observed footprint is shrunk along the viewing direction.  The
       shorter horizontal axis is extended to match the longer one, on the
       side pointing away from the camera.  Names in
       ``no_footprint_completion`` (the tray — deliberately non-square)
       skip this prior.

    Both priors only ever GROW the box — estimates stay conservative for
    "could something hide behind/inside this" reasoning, and the
    execution layer sizes grippers from its own live sensing, not from
    these estimates.
    """
    seg = np.asarray(seg_mask)
    height, width = seg.shape
    cam_xy = np.asarray(camera_xy, dtype=float)[:2]
    detections: Dict[str, ObjectDetection] = {}
    for body_id, name in body_id_to_name.items():
        rows, cols = np.nonzero(seg == body_id)
        if rows.size < min_pixels:
            continue
        pts = unproject_depth_pixels(
            rows, cols, np.asarray(depth_buffer)[rows, cols],
            view_matrix, projection_matrix, width, height)
        est_min = pts.min(axis=0)
        est_max = pts.max(axis=0)
        if est_min[2] <= support_z + DETECTION_SUPPORT_SNAP:
            est_min[2] = support_z
        if name not in no_footprint_completion:
            away = (est_min[:2] + est_max[:2]) / 2.0 - cam_xy
            ext_x = est_max[0] - est_min[0]
            ext_y = est_max[1] - est_min[1]
            if ext_x + 1e-9 < ext_y:
                if away[0] >= 0.0:
                    est_max[0] += ext_y - ext_x
                else:
                    est_min[0] -= ext_y - ext_x
            elif ext_y + 1e-9 < ext_x:
                if away[1] >= 0.0:
                    est_max[1] += ext_x - ext_y
                else:
                    est_min[1] -= ext_x - ext_y
        detections[name] = ObjectDetection(
            name=name, body_id=int(body_id), pixel_count=int(rows.size),
            est_min=est_min, est_max=est_max)
    return detections
