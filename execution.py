"""
Physical action execution for the Semantic Boxels pipeline.

Extracted from test_full_pipeline.py during the audit #26 refactor.
This module hosts the routines that translate planned PDDL actions
into PyBullet motions, plus the perception/bookkeeping helpers that
run between actions:

  - sense_shadow_from_render: classify a shadow volume against the fixed
    camera's rendered depth + segmentation (#P1 step 3; the pre-step-3
    rayTestBatch version lives in git history) as found_target /
    clear_but_empty / contains_nontarget / still_blocked.
  - compute_shadow_blockers: rebuild shadow → [blocker] map after objects
    are relocated (audit #78).
  - execute_pick / execute_place: arm trajectories with friction-based
    grasping (finger-motor squeeze, #P1 — the former constraint weld is
    gone) and geometry-derived contact heights (audit #1, #98).
  - execute_stack: place the held object on top of another object's live
    AABB top — destination computed from the live PyBullet pose so
    incremental stacks tolerate per-step settling (audit #30).
  - release_held_object_in_place: emergency drop with verification when
    the planner needs to be invoked while still holding an object.
  - handle_sense_action: dispatch-loop wrapper around
    sense_shadow_from_render that owns the post-sense bookkeeping
    (belief, registry, viz, occluder map, blocked counts).  Returns an
    ActionResult; see its docstring for the break/release contract
    (audit S-01).

The orchestration loop in test_full_pipeline.py composes these — it owns
the BeliefState, the registry, and the high-level decision logic, while
this module owns the geometry/physics primitives plus the sense action
handler.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional, Set, Tuple

import numpy as np
import pybullet as p

import telemetry          # #P1 F17 world telemetry (no-op unless armed)
import world_eye          # textual world/belief/camera snapshots (no-op unless armed)
from boxel_data import BoxelData, BoxelType
from perception import (DETECTION_MIN_PIXELS, DETECTION_SUPPORT_SNAP,
                        SENSE_MARGINAL_BLOCKED_FRACTION, ObjectDetection,
                        detect_objects_from_render,
                        first_surface_interceptors, sense_ray_slices)
from reboxelize import reboxelize_free_space
from streams import NOMINAL_HIDDEN_EXTENTS, RobotConfig
from robot_utils import (END_EFFECTOR_LINK, FINGER_JOINTS, solve_ik,
                         move_robot_smooth, open_gripper, close_gripper,
                         close_gripper_until_contact, pinch_axis)


def _capture_freeze(label: str) -> None:
    """Figure-capture aid (thesis/audit). If the env var BOXEL_CAPTURE_FREEZE is
    set to a number of seconds, hold the GUI on this event so it can be
    screenshotted (Win+Shift+S -> Window snip). Default OFF: when the var is
    unset this is a no-op, so normal runs and the eval sweep are unaffected."""
    secs = os.environ.get("BOXEL_CAPTURE_FREEZE")
    if not secs:
        return
    try:
        secs = float(secs)
    except ValueError:
        return
    print(f"    [CAPTURE] {label} -- GUI frozen {secs:.0f}s; screenshot the "
          f"window now (terminal for the log line).", flush=True)
    time.sleep(secs)


def sense_shadow_from_render(shadow_boxel, target_pybullet_id,
                             depth_image_m, seg_mask,
                             view_matrix, projection_matrix,
                             occluder_pybullet_ids=None, robot_id=None,
                             support_body_ids=None):
    """
    Sense a shadow region against ONE rendered observation (#P1 step 3).

    The classification grid is the shared sense-grid geometry
    (perception.sense_ray_slices), but instead of privileged
    pybullet.rayTestBatch body-id casts, each grid endpoint is tested
    against the fixed camera's rendered depth + instance segmentation
    (perception.first_surface_interceptors): a rendered surface strictly
    in front of an endpoint means the camera cannot see that endpoint,
    and the seg mask names the interceptor — the accepted sim-grade
    identity map standing in for a recognition model.  Ray-vs-render
    agreement measured 98 % per endpoint over the 20 A/B eval seeds
    with ZERO found-chain differences (tools/_probe_render_sense.py);
    the residual disagreements are boundary grazes in both directions.

    Returns one of four outcomes:
      - found_target: the target's surface intercepts some endpoint
      - still_blocked: no endpoint shows the target and some slice has
        more than the marginal fraction of its endpoints hidden behind
        an occluder or the robot arm
      - contains_nontarget: view is clear but non-target dynamic
        objects intercept endpoints inside the shadow
      - clear_but_empty: every endpoint is visible (or only support
        surfaces stand beyond it)

    Args:
        shadow_boxel: BoxelData for the shadow region to sense
        target_pybullet_id: seg-mask id of the target object
        depth_image_m: rendered depth in METERS (H, W), view-axis
        seg_mask: rendered instance segmentation (H, W)
        view_matrix / projection_matrix: the render's camera matrices
            (pybullet column-major 16-tuples) — the observation defines
            the viewpoint; no separate camera position is taken.
        occluder_pybullet_ids: Optional set/list of seg ids for ALL
            objects that may block camera view to this shadow.
        robot_id: Optional seg id of the robot.
        support_body_ids: Optional frozenset of static ids (plane,
            table, tray walls) never counted as interceptors.

    Returns:
        Tuple[str, float, Set[int], Optional[Tuple[np.ndarray, np.ndarray]]],
        Dict[int, int]:
          - outcome string
          - blocked_fraction (0 when not blocked)
          - set of non-target, non-occluder dynamic body IDs detected inside
            the shadow (empty for found_target and still_blocked)
          - for still_blocked: (min, max) AABB of the BLOCKED grid
            endpoints, padded per endpoint by half ITS slice's X/Y
            spacing and by the gap to the neighbouring slice in Z,
            clamped to the fragment — the sub-region that remains
            UNOBSERVED.  The visible endpoints observed the rest of the
            fragment empty, so the caller may SHRINK the shadow to this
            box (partial-reveal shrink, 2026-08-21, user-directed).
            None for the other outcomes.
          - interceptor_counts: {seg id -> how many grid endpoints that
            body stood in front of}, covering EVERY intercepting body
            (target, occluders, robot, supports and discoveries alike).
            Purely diagnostic — no branch reads it — but without it the
            "contains something the render cannot localize" refusal
            cannot name what it saw (#P1 F15).
    """
    ignore_ids = {-1}
    if robot_id is not None:
        ignore_ids.add(robot_id)
    if support_body_ids:
        ignore_ids |= set(support_body_ids)
    if occluder_pybullet_ids:
        ignore_ids |= set(occluder_pybullet_ids)
    ignore_ids.add(target_pybullet_id)

    min_c = shadow_boxel.min_corner
    max_c = shadow_boxel.max_corner

    # Shared sense-grid geometry (F5, 2026-08-21): one dense low slice
    # near the fragment base (12 mm spacing — an endpoint 2 cm above the
    # base lies INSIDE any >= 3 cm target body whose footprint contains
    # it, so its pixel must show the body's surface in front) plus the
    # two historical coarse 7x7 slices at 0.33/0.67 of the fragment
    # height.  The pre-F5 grid's lowest endpoints sat at base + 0.04 m —
    # ABOVE the tops of the post-resize 3-4 cm targets, so every
    # holding-goal target was structurally undetectable and its fragment
    # got removed as "observed empty".  perception.sense_ray_slices is
    # the single source of this geometry; the spawn-time findability
    # guarantee (perception.grid_would_hit) consumes the identical
    # endpoint list, so the spawn promise and the physical sense cannot
    # disagree (probe-verified under the render criterion: zero
    # found-chain differences across the eval seeds).
    slices, capped = sense_ray_slices(min_c, max_c)
    if capped:
        print(f"    NOTE: dense sense slice capped — endpoint spacing "
              f"exceeds the guaranteed-hit bound on this oversized "
              f"fragment ({float(max_c[0]-min_c[0]):.2f} x "
              f"{float(max_c[1]-min_c[1]):.2f} m)")
    ray_tos = []
    ray_slice = []            # slice index per endpoint (stats/pads)
    for si, sl in enumerate(slices):
        for pt in sl.points:
            ray_tos.append([float(pt[0]), float(pt[1]), float(pt[2])])
            ray_slice.append(si)

    intercepted, hit_ids, in_view = first_surface_interceptors(
        ray_tos, depth_image_m, seg_mask, view_matrix, projection_matrix)

    occluder_hits = 0
    robot_hits = 0
    detected_bodies: Set[int] = set()
    # Diagnostic only (#P1 F15): every intercepting seg id and how many
    # endpoints it covered, so the caller can name what it saw.
    interceptor_counts: dict = {}
    # Blocked endpoints as (endpoint, slice index) — the sub-region that
    # stays unobserved.  Feeds the partial-reveal shrink (see Returns).
    blocked_targets = []
    blocked_per_slice = [0] * len(slices)

    occ_set = set(occluder_pybullet_ids) if occluder_pybullet_ids else set()
    for i in range(len(ray_tos)):
        if not in_view[i]:
            # An endpoint outside the image frame was never observed —
            # count it blocked (conservative; zero occurrences on the
            # table scenes, probe-verified).
            blocked_targets.append((ray_tos[i], ray_slice[i]))
            blocked_per_slice[ray_slice[i]] += 1
            continue
        if not intercepted[i]:
            continue
        hit_obj_id = int(hit_ids[i])
        interceptor_counts[hit_obj_id] = \
            interceptor_counts.get(hit_obj_id, 0) + 1
        if hit_obj_id == target_pybullet_id:
            return "found_target", 0.0, set(), None, interceptor_counts
        if hit_obj_id in occ_set:
            occluder_hits += 1
            blocked_targets.append((ray_tos[i], ray_slice[i]))
            blocked_per_slice[ray_slice[i]] += 1
        elif (robot_id is not None) and (hit_obj_id == robot_id):
            robot_hits += 1
            blocked_targets.append((ray_tos[i], ray_slice[i]))
            blocked_per_slice[ray_slice[i]] += 1
        elif hit_obj_id not in ignore_ids:
            detected_bodies.add(hit_obj_id)

    blocked_total = occluder_hits + robot_hits
    if blocked_total > 0:
        # Per-slice blocked fractions (F5): the dense low slice carries
        # an order of magnitude more rays than a coarse 7x7 slice, so a
        # single blocked_count/total_rays fraction would DILUTE a
        # genuinely blocked upper region below the tolerance and let
        # the fragment be removed with its upper volume never observed.
        # Classify by the WORST slice instead — each slice is judged
        # against its own ray count, which keeps the 5 % marginal-clip
        # tolerance (2026-08-21, user-directed: "sense used to remove
        # the shadow before P1") at its original calibration: P1's tall
        # occluders and F3's full-size fragments make 1-3 % of a
        # slice's rays routinely graze an occluder corner or the arm —
        # and ANY hit used to veto the whole observation, so the
        # clear_but_empty removal path never fired and shadows looked
        # permanent in the GUI (runs 09-09-27 / 10-19-02: senses stuck
        # at 1 % and 3 % blocked).  Genuine blockages measure 12-100 %
        # on their slice.  Disclosed cost: a target hiding exactly
        # behind the tolerated rays is missed by THIS sense.
        slice_fractions = [
            blocked_per_slice[si] / len(sl.points)
            for si, sl in enumerate(slices)
        ]
        blocked_fraction = max(slice_fractions)
        if blocked_fraction > SENSE_MARGINAL_BLOCKED_FRACTION:
            if robot_hits > 0 and occluder_hits == 0:
                print(f"    NOTE: {robot_hits}/{len(ray_tos)} endpoints "
                      f"hidden by robot arm (not occluder)")
            # Partial-reveal bounds: union of per-ray pad boxes, clamped
            # to the fragment.  Each blocked endpoint is padded by half
            # ITS slice's spacing in X/Y (the dense slice earned a small
            # pad, the coarse slices need a large one — one global pad
            # cannot represent the mixed-density grid) and by the actual
            # gap to the neighbouring slice or fragment boundary in Z,
            # so unsampled volume between slices is never claimed
            # observed.  2026-08-21 user report: a tall occluder blocked
            # only the TOP of a fragment while the rest was visibly
            # clear — the old full-height bbox threw that vertical
            # information away.
            lo_list = []
            hi_list = []
            for pt, si in blocked_targets:
                sl = slices[si]
                pt_arr = np.asarray(pt, dtype=float)
                lo_list.append(pt_arr - np.array([
                    sl.spacing_x / 2.0, sl.spacing_y / 2.0, sl.pad_z_down]))
                hi_list.append(pt_arr + np.array([
                    sl.spacing_x / 2.0, sl.spacing_y / 2.0, sl.pad_z_up]))
            b_min = np.maximum(np.min(np.asarray(lo_list), axis=0),
                               np.asarray(min_c, dtype=float))
            b_max = np.minimum(np.max(np.asarray(hi_list), axis=0),
                               np.asarray(max_c, dtype=float))
            return ("still_blocked", blocked_fraction, set(),
                    (b_min, b_max), interceptor_counts)
        print(f"    NOTE: tolerating {blocked_total}/{len(ray_tos)} "
              f"marginally hidden endpoints (worst slice "
              f"{blocked_fraction:.0%} <= 5%) — classifying by the "
              f"remaining endpoints")

    if detected_bodies:
        return ("contains_nontarget", 0.0, detected_bodies, None,
                interceptor_counts)

    return "clear_but_empty", 0.0, set(), None, interceptor_counts


def compute_shadow_blockers(camera_pos, registry, shadow_ids, object_ids, env):
    """
    For each shadow, find ALL object boxels that block the camera's view.

    Classifies the SAME shared sense grid as sense_shadow_from_render
    (perception.sense_ray_slices geometry, F5) against ONE rendered
    observation of the fixed camera (#P1 step 3 — the pre-step-3
    rayTestBatch version lives in git history; ``camera_pos`` is kept
    for signature stability but the render defines the viewpoint).
    Any object whose rendered surface hides grid endpoints beyond the
    shared marginal tolerance is recorded as a blocker for that shadow.
    This replaces the old one-to-one shadow_occluder_map that only
    tracked the creating occluder (audit #78).

    Why not just use the parent relationship?  Because after objects are
    relocated, a DIFFERENT object may now block the camera's view of a
    shadow that was originally created by something else.

    Why we ALSO consult the parent relationship as a fallback: any
    finite ray grid is geometrically incomplete — for shadows that
    share a face with their occluder and extend past the occluder under
    perspective skew (e.g. yellow ↔ shadow_of_yellow_object), the rays
    can graze the occluder's AABB along the shared face and miss it
    entirely.  Without a fallback those shadows would be reported with
    an empty blocker list, the planner would treat them as view_clear,
    and `(move, sense, pick)` plans would target a region whose
    occluder is still in front — sensing then re-discovers the same
    occluder, a fresh shadow boxel materialises in the same place, and
    nothing has changed.  We guard against that by ensuring every
    shadow's `created_by_boxel_id` (when known and still in the
    registry) is at least listed as a blocker — the post-place refresh
    no longer relies on a separate caller-side fallback the way the
    initial setup did.

    Args:
        camera_pos: Camera position [x, y, z].
        registry: BoxelRegistry with all boxels.
        shadow_ids: List of shadow boxel IDs.
        object_ids: List of object boxel IDs.
        env: BoxelTestEnv for resolving PyBullet body IDs.

    Returns:
        Dict mapping shadow_id → list of blocker object boxel IDs.
    """
    pybullet_to_boxel = {}
    for obj_bid in object_ids:
        obj_boxel = registry.get_boxel(obj_bid)
        if obj_boxel and obj_boxel.object_name and obj_boxel.object_name in env.objects:
            body_id = env.objects[obj_boxel.object_name].object_id
            pybullet_to_boxel[body_id] = obj_bid

    # #P1 step (3): the census reads ONE rendered observation of the
    # fixed camera, like the sense — grid endpoints are classified by
    # perception.first_surface_interceptors against the render's depth
    # + segmentation instead of rayTestBatch body-id casts, so the
    # planner's blocks_view_at facts and the physical sense agree on
    # the SAME observation channel as well as the same grid geometry.
    _, _, _census_depth_buf, census_seg = env.detect_objects()
    census_depth_m = env._depth_buffer_to_meters(_census_depth_buf)
    census_view, census_proj = env._view_and_projection_matrices()

    blockers = {}

    for shadow_id in shadow_ids:
        sb = registry.get_boxel(shadow_id)
        if sb is None:
            continue

        blocker_set = set()
        min_c, max_c = sb.min_corner, sb.max_corner
        # SAME grid as sense_shadow_from_render (F5, 2026-08-21): the
        # census used to cast a single 5x5 slice at the shadow
        # midpoint, which never saw a SHORT (3-4 cm) body standing in
        # front of a fragment's low region — the denser sense would
        # then hit that body without it ever appearing in the blocker
        # facts, misclassifying it as contains_nontarget and churning
        # discovery/replans.  Sharing perception.sense_ray_slices keeps
        # the planner's blocks_view_at facts and the physical sense
        # agreeing endpoint-for-endpoint on WHO blocks WHAT.
        slices, _capped = sense_ray_slices(min_c, max_c)
        ray_tos = []
        ray_slice = []
        for si, sl in enumerate(slices):
            for pt in sl.points:
                ray_tos.append([float(pt[0]), float(pt[1]), float(pt[2])])
                ray_slice.append(si)

        intercepted, hit_ids, _in_view = first_surface_interceptors(
            ray_tos, census_depth_m, census_seg,
            census_view, census_proj)
        # Tolerance-aligned blocker selection (F5): mirror the sense's
        # per-slice classifier.  An object is listed as a blocker only
        # if removing it is NEEDED to bring every slice's blocked
        # fraction under the shared SENSE_MARGINAL_BLOCKED_FRACTION —
        # exactly the condition under which the sense would classify
        # still_blocked because of it.  Any-hit listing would pin a
        # shadow blocked (blocks_view_at is keyed to the blocker's
        # CURRENT boxel) over single grazing rays the sense itself
        # tolerates — observed on seed 0: green at free_010 grazed
        # 1/674 rays of its old shadow, stayed a blocker, and the
        # forced relocate-again plan died in the re-pick
        # stream-binding failure.
        per_slice_obj_hits = [dict() for _ in slices]
        for i in range(len(ray_tos)):
            if not intercepted[i]:
                continue
            hit_id = int(hit_ids[i])
            if hit_id in pybullet_to_boxel:
                counts = per_slice_obj_hits[ray_slice[i]]
                counts[hit_id] = counts.get(hit_id, 0) + 1
        for si, sl in enumerate(slices):
            counts = per_slice_obj_hits[si]
            remaining = sum(counts.values())
            n_slice = len(sl.points)
            if remaining / n_slice <= SENSE_MARGINAL_BLOCKED_FRACTION:
                continue
            for hit_id, cnt in sorted(counts.items(),
                                      key=lambda kv: -kv[1]):
                blocker_set.add(pybullet_to_boxel[hit_id])
                remaining -= cnt
                if remaining / n_slice <= SENSE_MARGINAL_BLOCKED_FRACTION:
                    break

        # Parent-relationship fallback: if raycasting found nothing for
        # this shadow but we know the creating occluder, add it.  The
        # creator is by construction the geometry that cast the shadow,
        # so it remains a valid blocker while it still stands where it
        # cast it.  Gated on face-adjacency (F5): the fallback exists
        # for the shared-face graze case — rays skimming along the
        # occluder/shadow contact face can miss the body entirely — and
        # that case only exists while the creator's AABB still touches
        # the fragment.  A relocated creator (or one whose residual
        # grazes the tolerance pass above deemed marginal) must NOT be
        # re-pinned: blocks_view_at keys to its CURRENT boxel and would
        # freeze the shadow blocked forever.  We re-confirm it is still
        # an OBJECT in the registry to avoid resurrecting stale links.
        if not blocker_set and sb.created_by_boxel_id:
            creator = registry.get_boxel(sb.created_by_boxel_id)
            if creator is not None:
                adj = 0.01
                touches = bool(
                    np.all(np.asarray(creator.min_corner)
                           <= np.asarray(max_c) + adj)
                    and np.all(np.asarray(creator.max_corner)
                               >= np.asarray(min_c) - adj))
                if touches:
                    blocker_set.add(sb.created_by_boxel_id)

        blockers[shadow_id] = list(blocker_set)

    print(f"  Shadow blockers (audit #78):")
    for sid, bids in blockers.items():
        if bids:
            print(f"    {sid} blocked by: {bids}")

    return blockers


def audit_robot_held_state(env, robot_id, expected_held_body_id=None,
                            tag: str = ""):
    """List non-static bodies in contact with the robot; log anomalies.

    Audit #82 diagnostic.  Surfaces the "robot holding two cubes"
    divergence between PDDL (handempty) and physics when a release
    failure leaves a cube friction-pinned to the EE after the dispatcher's
    audit-#79 state-clear has already set (handempty) symbolically.

    Static bodies (plane, table, robot, trays) are filtered out so the
    return list contains only dynamic objects (cubes / occluders).

    Anomaly cases (each prints "!!! HELD-STATE ANOMALY"):
      (a) expected_held_body_id is None and any body is in contact;
      (b) expected_held_body_id is X and a body other than X is in
          contact, OR more than one body is in contact.
    Success cases stay quiet (empty contacts on either expected mode;
    exactly the expected body on expected=X).

    Returns the sorted list of dynamic body ids found so callers may
    branch on it later.
    """
    static_ids = {-1, robot_id}
    for name, info in env.objects.items():
        if name in ("plane", "table", "robot"):
            static_ids.add(info.object_id)
            continue
        if getattr(info, "is_tray", False):
            static_ids.add(info.object_id)

    contacts = p.getContactPoints(bodyA=robot_id)
    bodies = sorted({c[2] for c in contacts} - static_ids)

    if not bodies:
        return bodies  # quiet success — empty contacts on either mode

    if expected_held_body_id is None:
        print(f"    !!! HELD-STATE ANOMALY ({tag}): expected handempty, "
              f"robot in contact with bodies={bodies}")
    elif len(bodies) > 1 or expected_held_body_id not in bodies:
        print(f"    !!! HELD-STATE ANOMALY ({tag}): expected only "
              f"body={expected_held_body_id}, robot in contact with "
              f"bodies={bodies}")

    return bodies


class EmptyHandError(Exception):
    """#P1 F1(c): place/stack entered with no object between the pads.

    Raised by the held-contact entry assert in execute_place /
    execute_stack.  Needs its OWN dispatcher path: the audit-#79
    fingers_open classifier would misfile this case as "IK failure,
    grip intact" (the fingers are CLOSED — on nothing) and leave stale
    held state for the next planner.plan().  The dispatcher's handler
    clears held state, refreshes OBJECT boxels from live PyBullet, and
    replans.  The gripper is opened before raising so the next pick
    descent starts from the open baseline.
    """


def _assert_held_contact(robot_id, held_body_id, obj_name, gui, action):
    """#P1 F1(c) entry gate for place/stack: the held object must still
    be pinched between BOTH finger pads when the action starts.  The
    friction grasp can lose the object in transport (or never have had
    it — a phantom hold that slipped past the pick-side gates); the
    drop verifier's height gate (ii) is blind for table-height places,
    so without this assert a lost cube can be "PLACED" without ever
    moving.  On failure: open the gripper (the fingers are closed on
    air) and raise EmptyHandError for the dispatcher's dedicated path.
    """
    contacts = p.getContactPoints(bodyA=robot_id, bodyB=held_body_id)
    pad_links = {c[3] for c in contacts if c[3] in FINGER_JOINTS}
    if pad_links != set(FINGER_JOINTS):
        nf = sum(c[9] for c in contacts if c[3] in FINGER_JOINTS)
        print(f"    ERROR: {action} entry assert failed for {obj_name} — "
              f"held object not in the gripper (pad contacts="
              f"{sorted(pad_links) or 'none'}, need both {FINGER_JOINTS}, "
              f"pad_normal_force={nf:.2f}N).  Opening gripper (#P1 F1).")
        open_gripper(robot_id, gui)
        raise EmptyHandError(
            f"{action} {obj_name}: no held-object pad contact at entry")


def _release_and_verify_drop(
    env,
    robot_id,
    gui,
    held_body_id,
    dropped_name,
    max_attempts: int = 3,
    base_settle_steps: int = 30,
    expected_support_z: Optional[float] = None,
    enforce_tilt: bool = False,
) -> bool:
    """
    Open the gripper through the finger motors and verify the held
    object actually fell free of the end-effector.  Retries with longer
    settle steps on failure.

    Shared inner block of release_held_object_in_place (replan-break
    safety net, audit #58) and execute_place / execute_stack (action
    paths, audit #75).

    Audit #80 hardened the verify gate from a single-frame non-robot-
    contact check to a multi-signal check.  The earlier check accepted
    false positives: a cube touching the table for one frame while still
    friction-pinned to a finger pad produced "released" with the cube
    still attached to the EE — the PDDL fact (obj_at_boxel ?o ?b) then
    diverged from physical reality and every subsequent plan was
    grounded on a fiction.

    #P1 WP2b (2026-09-19): this function is now the TACTILE half of the
    verification — what the robot senses through its own joints and
    links:
      (i)   fingers physically reached max open (≥ 0.038 per finger —
            the #P1 friction-grasp analog of the old "constraint gone"
            probe: with the weld removed, a pad that failed to withdraw
            is the only thing that can still bind the object to the EE),
      (iv)  zero contact between the released body and any robot link.
    The former simulator-read gates — (ii) bottom within 2 cm of the
    support, (iii) COM stationary over 20 steps, (v) tilt ≤ 20° — are
    now OBSERVED after the post-action lift by _observe_release (the
    camera sees the released object's top and footprint once the hand
    is out of the way); ``expected_support_z`` / ``enforce_tilt`` are
    accepted for call compatibility and forwarded nowhere.  A released
    object that hangs on a pad still moves with the arm — that is
    contact (iv), which the retries are for.  The [#84-gt-diag] lines
    are print-only ground-truth diagnostics for the run log.

    Failure modes covered:
      • Fingers stall short of max open (motor loses a force fight).
      • Fingers re-close on the object due to position-control overshoot.
      • Object snags on a finger pad and stays at gripper height.

    Returns True on a verified drop; False after exhausting max_attempts.
    """
    if dropped_name is None or dropped_name not in env.objects:
        # Without a name we can't read the object's pose to verify —
        # best effort: open the fingers and let whatever sits between
        # them fall, then settle briefly.
        open_gripper(robot_id, gui)
        for _ in range(base_settle_steps):
            env.step_simulation()
        return True

    # Audit #84 pre-release diag - bracket entry-to-loop so a cube that
    # is already on the floor BEFORE open_gripper fires is distinguishable
    # from one that falls during the release loop.  Pairs with the in-
    # loop diag below; tilt-at-grip vs tilt-at-release split visible
    # across consecutive lines.  Fires for execute_place / execute_stack /
    # release_held_object_in_place - extra signal welcome on all three.
    pre_pos, pre_orn = p.getBasePositionAndOrientation(held_body_id)
    pre_aabb_min, pre_aabb_max = p.getAABB(held_body_id)
    pre_euler = p.getEulerFromQuaternion(pre_orn)
    pre_tilt_deg = max(abs(np.degrees(pre_euler[0])),
                        abs(np.degrees(pre_euler[1])))
    print(f"    [#84-gt-diag] pre-release {dropped_name}: "
          f"pos=[{pre_pos[0]:.4f},{pre_pos[1]:.4f},{pre_pos[2]:.4f}] "
          f"aabb=[{pre_aabb_min[0]:.4f},{pre_aabb_min[1]:.4f},"
          f"{pre_aabb_min[2]:.4f}]-[{pre_aabb_max[0]:.4f},"
          f"{pre_aabb_max[1]:.4f},{pre_aabb_max[2]:.4f}] "
          f"tilt_deg={pre_tilt_deg:.2f}")

    for attempt in range(1, max_attempts + 1):
        open_gripper(robot_id, gui)
        # Longer settle on retries so a snagged object has more time to
        # slip free under gravity.
        for _ in range(base_settle_steps + 30 * (attempt - 1)):
            env.step_simulation()
        env.update_object_positions()

        # Audit #80 multi-signal verify gate (see function docstring).

        # (i) fingers physically reached max open (#P1 friction grasp —
        # the analog of the old getConstraintInfo probe; open_gripper
        # already warned if the motors stalled, this gates on it).
        finger_pos = [p.getJointState(robot_id, fj)[0]
                       for fj in FINGER_JOINTS]
        fingers_open = min(finger_pos) >= 0.038

        # (iv) robot-link contacts; also collect non-robot contacts (a
        # released cube must touch at least one non-robot body).
        # Audit #82: per-link breakdown (link id, min penetration distance,
        # summed normal force) so a stuck-on-release ghost surfaces WHICH
        # link is welding the cube — pads (9,10), hand (8), wrist (7), etc.
        contacts = p.getContactPoints(bodyA=held_body_id)
        contact_bodies = {c[2] for c in contacts}
        robot_contacts = contact_bodies & {robot_id}
        non_robot = contact_bodies - {robot_id, -1}
        robot_link_contacts: dict = {}
        for c in contacts:
            if c[2] != robot_id:
                continue
            link_b, dist, nf = c[4], c[8], c[9]
            cur_d, cur_f = robot_link_contacts.get(link_b, (dist, 0.0))
            robot_link_contacts[link_b] = (min(cur_d, dist), cur_f + nf)

        # Ground-truth diagnostic only (print): bottom height and tilt
        # of the released body, so the run log still shows the physics
        # next to the robot's own verdict.  The robot's checks of these
        # quantities are the observation in _observe_release.
        for _ in range(20):
            env.step_simulation()
        _gt_aabb_min, _ = p.getAABB(held_body_id)
        _, _gt_orn = p.getBasePositionAndOrientation(held_body_id)
        _gt_euler = p.getEulerFromQuaternion(_gt_orn)
        _gt_tilt_deg = max(abs(np.degrees(_gt_euler[0])),
                           abs(np.degrees(_gt_euler[1])))

        # finger_pos already read for gate (i) above — reused in diag.
        if robot_link_contacts:
            link_breakdown = "; ".join(
                f"link{k}: d={d * 1000:.2f}mm, F={f:.2f}N"
                for k, (d, f) in sorted(robot_link_contacts.items())
            )
        else:
            link_breakdown = "none"
        diag = (f"fingers_open={fingers_open} "
                f"robot_link_contacts={{{link_breakdown}}} "
                f"finger_pos=[{finger_pos[0]:.4f},{finger_pos[1]:.4f}] "
                f"| gt-diag: bottom_z={float(_gt_aabb_min[2]):.4f} "
                f"tilt_deg={_gt_tilt_deg:.2f} "
                f"non_robot_contacts={sorted(non_robot) or 'none'}")

        ok = fingers_open and not robot_contacts
        if ok:
            print(f"    -> Released {dropped_name} (tactile verify ok; "
                  f"{diag})")
            audit_robot_held_state(
                env, robot_id, expected_held_body_id=None,
                tag=f"post-release:{dropped_name}:attempt-{attempt}-ok")
            return True
        print(f"    Drop verification failed for {dropped_name}: "
              f"{diag} — retry {attempt}/{max_attempts}.")
        audit_robot_held_state(
            env, robot_id, expected_held_body_id=None,
            tag=f"post-release:{dropped_name}:attempt-{attempt}-fail")

    return False


def _observe_release(env, dropped_name, expected_top_z=None, rigid_ext=None,
                     enforce_tilt=False, settle_steps=20):
    """Verify a release by OBSERVATION after the post-action lift (#P1
    WP2b, 2026-09-19): the camera half of the drop verification.

    Two renders ``settle_steps`` apart (env.detect_objects).  On the
    released object's detection:
      top      — its estimated top within 2 cm of ``expected_top_z``
                 (support top + the object's rigid height; None skips
                 the check, e.g. a tray whose floor is not a modelled
                 support);
      upright  — with ``enforce_tilt``, the horizontal extents no wider
                 than the rigid size + 1.5 cm and the top no higher than
                 expected + 1.5 cm (a toppled box grows sideways and
                 shrinks in height; a hanging one is too high);
      still    — the centre moved no more than 3 mm between the renders
                 (a body riding on the retreating arm moves).
    The tops of resting bodies are the best-observed surface of this
    camera (probe: +0.1 cm), so 2 cm is generous.  An object the render
    does not show at all (hidden by the arm or another body) cannot be
    judged by sight: the release is accepted on the tactile checks and
    the run log says so; the dispatcher's post-action refresh keeps
    correcting the belief.  Returns (ok, diag, observed_centre) — the
    centre is None when the object was not observed or the check failed.
    """
    dets_a = env.detect_objects()[0]
    for _ in range(settle_steps):
        env.step_simulation()
    dets_b = env.detect_objects()[0]
    da, db = dets_a.get(dropped_name), dets_b.get(dropped_name)
    if da is None or db is None or db.pixel_count < DETECTION_MIN_PIXELS:
        return True, (f"unobserved after the lift "
                      f"({'no detection' if db is None else f'{db.pixel_count} px'}) — "
                      f"accepted on the tactile checks"), None
    top = float(db.est_max[2])
    ext = db.est_max - db.est_min
    shift = float(np.hypot(*((db.est_center - da.est_center)[:2])))
    problems = []
    if expected_top_z is not None and abs(top - expected_top_z) > 0.02:
        problems.append(f"top {top:.4f} is {(top - expected_top_z) * 1000:+.0f} mm "
                        f"from the expected {expected_top_z:.4f}")
    if enforce_tilt and rigid_ext is not None:
        if (ext[0] > rigid_ext[0] + 0.015) or (ext[1] > rigid_ext[1] + 0.015):
            problems.append(f"footprint {ext[0] * 100:.1f} x {ext[1] * 100:.1f} cm "
                            f"exceeds the rigid {rigid_ext[0] * 100:.1f} x "
                            f"{rigid_ext[1] * 100:.1f} cm — toppled")
        if expected_top_z is not None and top > expected_top_z + 0.015:
            problems.append("top above the expected top — tilted or hanging")
    if shift > 0.003:
        problems.append(f"moved {shift * 1000:.1f} mm between two renders")
    diag = (f"observed {db.pixel_count} px, top {top:.4f}"
            f"{'' if expected_top_z is None else f' (expected {expected_top_z:.4f})'}, "
            f"footprint {ext[0] * 100:.1f} x {ext[1] * 100:.1f} cm, "
            f"shift {shift * 1000:.1f} mm")
    if problems:
        return False, diag + " — " + "; ".join(problems), None
    return True, diag, np.asarray(db.est_center, dtype=float)


def release_held_object_in_place(
    env,
    robot_id,
    gui,
    held_body_id,
    held_object_boxel_id,
    registry,
    boxel_centers,
    boxel_to_pybullet,
    body_id_to_name,
    viz,
    shadows,
    occluders,
    planner,
    max_attempts: int = 3,
):
    """
    Open the gripper through the finger motors and verify the object
    actually fell/separated from the end-effector.  Retries on failure.

    A drop is considered successful when, after settling:
      • The object's COM is reasonably far from the EE (no longer pinched).
      • The object's linear speed is near zero (came to rest, not floating).

    Failure modes covered:
      • Fingers stall short of max open (motor loses a force fight).
      • Fingers re-close on the object due to position-control overshoot.
      • Object snags on a finger pad and stays at gripper height.

    Args:
        env: BoxelTestEnv.
        robot_id: PyBullet body ID of the robot.
        gui: Whether GUI is active.
        held_body_id: PyBullet body ID of the held object.
        held_object_boxel_id: Registry boxel ID for the held object (may be None).
        registry, boxel_centers, boxel_to_pybullet, body_id_to_name, viz:
            Bookkeeping caches that need to be updated with the dropped pose.
        shadows, occluders, planner: Inputs for refreshing shadow_occluder_map.
        max_attempts: How many open-and-settle cycles to try before giving up.

    Returns:
        Tuple[bool, Dict]: (success, state_updates).  state_updates may
        contain 'shadow_occluder_map' and 'current_config' for the caller
        to apply.  When success is False, the caller should abort the run.
    """
    state_updates: dict = {
        "shadow_occluder_map": None,
        "current_config": None,
    }

    dropped_name = body_id_to_name.get(held_body_id)
    print(f"  Replanning while holding {dropped_name or '?'} — releasing.")
    if not _release_and_verify_drop(env, robot_id, gui,
                                     held_body_id, dropped_name,
                                     max_attempts=max_attempts):
        return False, state_updates
    if dropped_name is None or dropped_name not in env.objects:
        # Helper succeeded via best-effort path; nothing to refresh.
        return True, state_updates

    # #P1 WP2c (2026-09-19): the dropped object's boxel is re-posed from
    # an OBSERVATION (the rigid-size refresh) instead of p.getAABB; when
    # the arm hides it, the boxel goes where the hand is (proprioception)
    # with its bottom on the table, and the next observation corrects it.
    if (held_object_boxel_id is not None
            and registry.get_boxel(held_object_boxel_id) is not None):
        obj_bd = registry.get_boxel(held_object_boxel_id)
        dets = env.detect_objects()[0]
        det = dets.get(dropped_name)
        if det is not None and det.pixel_count >= DETECTION_MIN_PIXELS:
            refresh_object_aabbs(env, registry, viz=viz, detections=dets)
        else:
            ee = p.getLinkState(robot_id, END_EFFECTOR_LINK)[0]
            ext = (np.asarray(obj_bd.max_corner, dtype=float)
                   - np.asarray(obj_bd.min_corner, dtype=float))
            obj_bd.min_corner = np.array([ee[0] - ext[0] / 2.0,
                                          ee[1] - ext[1] / 2.0,
                                          env.table_surface_height])
            obj_bd.max_corner = obj_bd.min_corner + ext
            print(f"    [WP2c] {dropped_name} not visible after the emergency "
                  f"drop — its boxel is placed under the hand")
            if viz is not None:
                viz.remove_boxel_viz(held_object_boxel_id)
                viz.draw_boxel_data(obj_bd)
        obj_bd.on_surface = (
            "table"
            if obj_bd.min_corner[2] <= env.table_surface_height + 0.01
            else None
        )
        boxel_centers[held_object_boxel_id] = obj_bd.center

    # Free space and shadows must be refreshed: the dropped object now
    # occupies new ground and may block different camera lines of sight.
    setattr(registry, "_dirty", True)
    state_updates["shadow_occluder_map"] = compute_shadow_blockers(
        env.camera_position, registry, shadows, occluders, env
    )
    planner.shadow_occluder_map = state_updates["shadow_occluder_map"]

    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    state_updates["current_config"] = RobotConfig(
        joint_positions=actual_joints,
        name="post_emergency_drop"
    )
    _bd = (registry.get_boxel(held_object_boxel_id)
           if held_object_boxel_id is not None else None)
    print(f"    -> Dropped {dropped_name}; believed at "
          f"{tuple(round(float(v), 3) for v in _bd.center) if _bd is not None else '?'}")

    return True, state_updates


def _apply_post_action_lift(robot_id, contact_ee, orientation, contact_joints,
                             pc, gui, lift_height: float = 0.10):
    """Lift the EE straight up by ``lift_height`` after a contact pose.

    Hardcoded post-action workaround for motion-planning fragility — see
    audit #36 / THESIS_NOTES.md §19.  The lift is invisible to the planner;
    ``final_config`` (read by the caller after this returns) carries the
    lifted pose forward as the next ``move`` action's plan_motion seed.
    Falls through silently to the contact configuration if the lift IK
    cannot be solved — never aborts the surrounding pick / place / stack.
    """
    lift_ee = contact_ee + np.array([0.0, 0.0, lift_height])
    lift_joints = solve_ik(robot_id, lift_ee, orientation, pc,
                           seed=contact_joints)
    # audit #60 diagnostic — confirm lift IK and physical execution
    if lift_joints is None:
        print(f"    [#60-diag] lift IK FAILED for target_z={lift_ee[2]:.3f} "
              f"(contact_z={contact_ee[2]:.3f}, +{lift_height:.3f}) — "
              f"final_config will be CONTACT pose (candidate iii)")
        return
    move_robot_smooth(robot_id, lift_joints, gui)


def execute_pick(robot_id, env, obj_name, obj_pos, grasp, config, gui,
                 obj_aabb=None, _retry: bool = False
                 ) -> Tuple[Optional[int], Optional[RobotConfig]]:
    """
    Execute pick action using the plan's grasp pose.

    Assumes the planned `move` action has already delivered the arm to
    the compute_kin_solution config (boxel.center + grasp.position,
    10 cm above the object).  This routine only handles the final
    lower-and-grasp:

      IK (seeded from `config`, audit #37/#38) + lower to contact  →
      close gripper (friction squeeze)  →  verify both pads contact
      the object.

    The contact waypoint is computed from the object's ESTIMATED box
    (``obj_aabb``, the registry estimate the dispatcher passes; #P1
    F24, 2026-09-18) re-observed once before the descent, so the
    Panda's finger pads wrap around the object the robot believes is
    there.  The close is tactile (close_gripper_until_contact): the
    fingers advance until both pads touch, and the finger position at
    contact is the measured half-width the squeeze is set from.  The
    simulator's pose and AABB are read here only for print-only
    diagnostics and for the body-identity contact query.

    #P1 friction grasp (2026-08-20): the JOINT_FIXED constraint weld
    (the audit-#7-part-B "accepted simulation simplification") is
    removed.  The hold is now pad friction alone: close_gripper drives
    the fingers toward a target 3 mm inside the object surface, the
    motors keep pressing at the close force budget, and μ 1.2 pad
    friction carries the object through transport (deferred #59 fix,
    unblocked by the deferred-#77 resize).  A grasp that misses (pads
    not both in contact) aborts into a replan instead of being papered
    over by a telekinetic attachment.

    A small (~5 cm) hardcoded post-pick lift runs after the verified
    grasp — see audit #36 / THESIS_NOTES.md §19 for the rationale
    (motion-planning fragility workaround); the lift is invisible to
    the planner because ``final_config`` (read after the lift) carries
    the lifted pose forward as the next ``move`` action's plan_motion
    seed.  (Explicitly exempted in #P1: "the hardcoded lift after a
    pick or place action may stay".)

    Args:
        robot_id: PyBullet body ID of the robot
        env: BoxelTestEnv instance
        obj_name: Name key in env.objects (e.g. "blue_object", "red_object")
        obj_pos: Believed object position [x, y, z] (the registry
            estimate's centre; kept for logging, the aim is obj_aabb)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        gui: Whether GUI is active (for step_simulation timing)
        obj_aabb: (min_corner, max_corner) of the object's estimated
            box — required; the pick aborts without it.

    Returns:
        Tuple[int, RobotConfig]: PyBullet body ID of the held object
        (the dispatcher threads it through place/stack/release), and a
        RobotConfig representing the robot's actual final joint
        configuration (contact position with object held).  (None,
        None) on IK failure or failed grip verification — caller
        replans.
    """
    # --- Contact height from cube TOP, not cube centre (audit #81 refine) ---
    # panda_grasptarget (link 11) sits at the centre of the finger-
    # pad closing area; pads extend ~3.5 cm below the grasptarget.
    # Pre-refine we used obj_pos[2] (cube centre) clamped to
    # table_z + 0.035 — for 4 cm cubes this happened to land 5 mm
    # below the cube top (good wrap-around), but for larger cubes
    # the grasptarget sat at the cube CENTRE, leaving pads to wrap
    # only the lower half so the cube could rotate forward out of
    # the grip.  Now we take the top of the ESTIMATED box and offset
    # down by a fixed 5 mm so the % grip height is invariant in
    # cube size — small cubes match the previous "clamped to
    # table_z + 0.035" behaviour, large cubes get a proportionally
    # higher grasp.
    #
    # User direction 2026-05-15: "when the gripper is targeting a
    # big object, the centre it's targeting should be higher.  make
    # it as high percentage wise as it is when the object is small."
    obj_id = env.objects[obj_name].object_id
    # Audit #82: assert (handempty) BEFORE closing on a new object.  If
    # the robot is already in contact with a non-static body, we're about
    # to pick while still physically holding the previous one — surfaces
    # the dispatcher's audit-#79 state-clear divergence (PDDL says
    # handempty, physics says we're friction-pinned to a ghost).
    audit_robot_held_state(env, robot_id, expected_held_body_id=None,
                            tag=f"pre-pick:{obj_name}")
    # #P1 F24 / step (4) (2026-09-18): the object's geometry is the
    # ESTIMATE the dispatcher passes (the registry box perception
    # registered and has re-posed at every observation since), never
    # p.getAABB.  Before the descent the scene is observed once more —
    # the planned move parked the arm at the approach altitude, so the
    # object is usually still in view — and the box is re-posed on that
    # detection when it is consistent with the known size (XY centred on
    # the fresh estimate, rigid extents, top where the fresh render sees
    # it).  A transit sweep that shoved the object 10-28 mm (GUI field
    # runs 10-53-50 / 10-55-47) is caught here the honest way; an
    # occluded or inconsistent detection keeps the registry box, and
    # the F2 strike counter absorbs the residual.
    if obj_aabb is None:
        print(f"    ERROR: execute_pick({obj_name}) needs the object's "
              f"estimated box (#P1 F24) — none passed; aborting")
        return None, None
    est_min = np.asarray(obj_aabb[0], dtype=float).copy()
    est_max = np.asarray(obj_aabb[1], dtype=float).copy()
    rigid_ext = est_max - est_min
    fresh = env.detect_objects()[0].get(obj_name)
    if fresh is None:
        _why = "no detection"
    elif fresh.pixel_count < DETECTION_MIN_PIXELS:
        _why = f"{fresh.pixel_count} px"
    elif abs(float(fresh.est_max[2]) - float(est_max[2])) > 0.01:
        _why = (f"top {abs(float(fresh.est_max[2]) - float(est_max[2])) * 1000:.0f} mm "
                f"from the known top — partly hidden")
    else:
        _why = None
    if _why is None:
        _cxy = (fresh.est_min[:2] + fresh.est_max[:2]) / 2.0
        _new_max = np.array([_cxy[0] + rigid_ext[0] / 2.0,
                             _cxy[1] + rigid_ext[1] / 2.0,
                             float(fresh.est_max[2])])
        _new_min = _new_max - rigid_ext
        _old_c = (est_min + est_max) / 2.0
        reaim_xy = float(np.hypot(_cxy[0] - _old_c[0], _cxy[1] - _old_c[1]))
        if reaim_xy > 0.002:
            print(f"    [F24] pick re-aim {obj_name}: the pre-descent "
                  f"observation puts it {reaim_xy * 1000:.1f} mm from the "
                  f"registry estimate ({fresh.pixel_count} px)")
        est_min, est_max = _new_min, _new_max
    else:
        print(f"    [F24] {obj_name} not re-observed before the descent "
              f"({_why}) — aiming at the registry estimate")
    est_centre = (est_min + est_max) / 2.0
    cube_top_z = float(est_max[2])
    x_half = float(rigid_ext[0]) / 2.0
    y_half = float(rigid_ext[1]) / 2.0
    # The grasp's yaw fixes the pinch axis (robot_utils.pinch_axis); the
    # aperture and the width plausibility are sized on THAT extent.
    _pinch = pinch_axis(grasp.orientation)
    pinch_half = (x_half, y_half)[_pinch]

    _GRASP_MARGIN_FROM_TOP = 0.005  # 5 mm below cube top
    _FINGER_TIP_DEPTH = 0.035
    table_z = env.table_surface_height
    min_contact_z = table_z + _FINGER_TIP_DEPTH
    contact_z = max(cube_top_z - _GRASP_MARGIN_FROM_TOP, min_contact_z)

    # The descent aims at the (re-observed) estimate centre; contact_z
    # above comes from the same box.  (The 2026-08-21 live-pose re-aim
    # read p.getBasePositionAndOrientation here; the pre-descent
    # observation above replaces it.)
    contact_ee = np.array([
        est_centre[0] + grasp.position[0],
        est_centre[1] + grasp.position[1],
        contact_z,
    ])

    # No pre-contact approach motion (refactor step 2).  The prior
    # planned `move` action already delivered the arm to `config`, the
    # compute_kin_solution config — which targets boxel.center +
    # grasp.position (10 cm above object).  We seed the contact-pose
    # IK with `config.joint_positions` so the solver stays in the same
    # IK branch the planner already validated (audit #37/#38).  10 cm
    # is a Cartesian distance well within IK's 100-iteration limit
    # given the seed, and it keeps the wrist out of the camera's view
    # so move→sense sequences aren't blocked by the arm itself.
    pc = env.client_id

    # #P1 top-down descent (2026-08-21, user report: "it first
    # collided... its not top down enough").  The planned move parks
    # the arm above the PLAN-TIME target; since the live-pose re-aim,
    # the contact point is the LIVE pose — a single interpolated lower
    # therefore swipes sideways-and-down and the fingers clip the
    # block's edge on the way, knocking it and loosening the grip.
    # Split the lower: (1) horizontal re-aim at the approach altitude
    # to directly above the live object (fingertips stay well clear of
    # the block top), then (2) a strictly vertical descent.  The
    # vertical stage is seeded from the align solution so the IK stays
    # in the same branch.
    # Pre-grasp aperture first (see the comment further down) so the
    # horizontal align above the block also sweeps with narrowed
    # fingers, not the full-open 0.04 m.
    pregrasp_aperture = min(0.04, pinch_half + 0.008)
    close_gripper(robot_id, gui, target_finger_pos=pregrasp_aperture)

    live_ee_now = p.getLinkState(robot_id, END_EFFECTOR_LINK)[0]
    above_ee = np.array([contact_ee[0], contact_ee[1],
                         max(float(live_ee_now[2]), contact_z + 0.05)])
    above_joints = solve_ik(robot_id, above_ee, grasp.orientation, pc,
                            seed=config.joint_positions)
    contact_seed = config.joint_positions
    if above_joints is not None:
        move_robot_smooth(robot_id, above_joints, gui, settle=True)
        contact_seed = above_joints
    else:
        print(f"    WARNING: horizontal re-aim IK failed for {obj_name} — "
              f"falling back to the single-stage lower (#P1 top-down "
              f"descent)")

    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc,
                              seed=contact_seed)

    # Contact IK is mandatory (can't pick without reaching the object).
    # Aborting on failure triggers a replan rather than driving the arm
    # to an arbitrary configuration (audit #82).
    if contact_joints is None:
        print(f"    ERROR: IK failed for pick contact of {obj_name} — aborting")
        return None, None

    # Defensive open_gripper removed (audit #37/#38).  Gripper state is
    # implicit in the PDDL predicate (holding ?o) — init = open, only
    # pick/place/stack change it.  No drift channel for this safety net
    # to defend against; the dispatcher already refuses pick-on-pick.
    # #P1 F1: "init = open" is now enforced in PHYSICS too — _setup_scene
    # resets the fingers to 0.04 after robot load (they spawn closed;
    # the #37/#38 removal rested on a false "loadURDF = open" assumption
    # that produced the phantom-first-pick field bug).
    # #P1 pre-grasp aperture (2026-08-21, investigation synthesis):
    # the fingers are sized to the object BEFORE the horizontal align
    # above (see there) — the narrower sweep keeps the pads from
    # clipping neighbours (or the object itself on a marginal arrival)
    # during both the align and the descent.  The grasp's yaw names the
    # pinch axis (#P1 step (4)), so the aperture is sized on the
    # estimate's half-extent along it, +8 mm clearance per finger.

    # settle=True: the contact descent is precision-critical (#P1) —
    # the friction grasp needs lateral centering within the descent
    # clearance, so hold the endpoint until the arm converges.
    move_robot_smooth(robot_id, contact_joints, gui, settle=True)

    # #P1 pick-arrival diagnostic (mirrors the audit-#84 stack diag).
    # With the weld gone, a lateral arrival error beyond the descent
    # clearance is the prime suspect when grip verification below
    # reports a miss — log EE-vs-target and EE-vs-object XY offsets so
    # failed grips are attributable from headless logs.  Print-only
    # GROUND-TRUTH diagnostic (p.getBasePositionAndOrientation):
    # nothing here feeds control.
    live_ee_pos = p.getLinkState(robot_id, END_EFFECTOR_LINK)[0]
    ee_xy_err = float(np.hypot(live_ee_pos[0] - contact_ee[0],
                                live_ee_pos[1] - contact_ee[1]))
    obj_live_pos = p.getBasePositionAndOrientation(obj_id)[0]
    ee_vs_obj_xy = float(np.hypot(live_ee_pos[0] - obj_live_pos[0],
                                   live_ee_pos[1] - obj_live_pos[1]))
    print(f"    [#P1-diag] pick arrival {obj_name}: "
          f"ee_xy_err={ee_xy_err * 1000:.2f}mm "
          f"ee_vs_obj_xy={ee_vs_obj_xy * 1000:.2f}mm "
          f"ee_z={live_ee_pos[2]:.4f} contact_z={contact_z:.4f}")

    # Tactile close (#P1 step (4), 2026-09-18): the fingers advance until
    # both pads touch, the finger position at contact is the object's
    # measured half-width along the pinch axis, and the motors then hold
    # 3 mm inside it — the pads stop at the surface, the unreachable
    # target keeps them pressing at the close force budget, and that
    # normal force × pad friction is the grip (no constraint weld, #P1,
    # deferred #59).  close_gripper used to place the same 3 mm target
    # from a p.getAABB width; the measured width needs no oracle and is
    # right for an estimate that over-approximates the object.  The
    # table and the ground are the only bodies the pads may brush
    # without it counting as contact.
    _static_ids = frozenset(env.objects[n].object_id
                            for n in ("table", "plane") if n in env.objects)
    measured_half = close_gripper_until_contact(
        robot_id, gui, force=60.0, squeeze=0.003, ignore_body_ids=_static_ids)
    if measured_half is None:
        print(f"    [step 4] {obj_name}: the fingers closed without both "
              f"pads touching anything")

    # Grip verification (#P1): a friction grasp only exists if BOTH
    # finger pads are in contact with the object after the close.  A
    # miss (object drifted, lateral IK error beyond the descent
    # clearance) must abort into a replan rather than continue with an
    # empty or one-sided pinch — the weld used to paper over exactly
    # this failure class by attaching whatever the planner believed
    # was there (deferred #59: "it can hold objects that don't fit in
    # the gripper").  obj_id already resolved at the top of
    # execute_pick (for the AABB read that drives contact_z and the
    # close_gripper target).
    grip_contacts = p.getContactPoints(bodyA=robot_id, bodyB=obj_id)
    pad_links = {c[3] for c in grip_contacts
                 if c[3] in FINGER_JOINTS}
    grip_nf = sum(c[9] for c in grip_contacts if c[3] in FINGER_JOINTS)
    if pad_links != set(FINGER_JOINTS):
        print(f"    ERROR: grip verification failed for {obj_name} — "
              f"pad contacts={sorted(pad_links) or 'none'} (need both "
              f"{FINGER_JOINTS}), pad_normal_force={grip_nf:.2f}N. "
              f"Opening gripper.")
        open_gripper(robot_id, gui)
        if not _retry:
            # #P1 grasp resample (2026-08-21, user step 2): the failed
            # descent/close may itself have shoved the block, so a full
            # replan would regenerate the same grasp against stale
            # geometry.  Retreat to the approach altitude and re-run
            # the whole pick ONCE against the fresh live pose (new
            # AABB, re-aim, aperture, vertical descent).
            print(f"    -> resampling the grasp against the live pose "
                  f"(one retry, #P1 step 2)")
            retreat = (above_joints if above_joints is not None
                       else config.joint_positions)
            move_robot_smooth(robot_id, retreat, gui, settle=True)
            return execute_pick(robot_id, env, obj_name, obj_pos, grasp,
                                config, gui, obj_aabb=obj_aabb, _retry=True)
        return None, None
    # #P1 F1(d) width plausibility: link identity alone cannot
    # distinguish a pinch from both fingertips STANDING ON the object
    # top (the phantom first pick read both pads "in contact" with the
    # fingers at ~0.000 m).  A genuine pinch parks each finger at the
    # object's half-extent ALONG THE PINCH AXIS; the grasp's yaw names
    # that axis now (#P1 step (4)), so the measured half-width must lie
    # between 5 mm (a phantom reads ~0.000-0.005, far below the
    # >= 0.015 m half-extents of every scene object) and the estimate's
    # pinch half-extent + 8 mm (the estimate over-approximates by at
    # most a few mm; wider means the pads closed on something else or
    # across the wrong axis).
    finger_pos = [p.getJointState(robot_id, fj)[0] for fj in FINGER_JOINTS]
    width = (measured_half if measured_half is not None
             else float(np.mean(finger_pos)))
    width_lo, width_hi = 0.005, pinch_half + 0.008
    aperture_err = 0.0 if width_lo <= width <= width_hi else \
        min(abs(width - width_lo), abs(width - width_hi))
    if aperture_err > 0.0:
        print(f"    ERROR: grip width implausible for {obj_name} — "
              f"measured half-width {width * 1000:.1f} mm "
              f"(finger_pos=[{finger_pos[0]:.4f},{finger_pos[1]:.4f}]) "
              f"outside [{width_lo * 1000:.0f}, {width_hi * 1000:.0f}] mm for "
              f"the estimate's pinch half-extent {pinch_half * 1000:.1f} mm "
              f"(standing-on-top phantom, partial pinch or wrong axis). "
              f"Opening gripper (#P1 F1).")
        open_gripper(robot_id, gui)
        if not _retry:
            # #P1 grasp resample — same one-shot retry as the pad-contact
            # failure above (the block may have been nudged by this very
            # attempt).
            print(f"    -> resampling the grasp against the live pose "
                  f"(one retry, #P1 step 2)")
            retreat = (above_joints if above_joints is not None
                       else config.joint_positions)
            move_robot_smooth(robot_id, retreat, gui, settle=True)
            return execute_pick(robot_id, env, obj_name, obj_pos, grasp,
                                config, gui, obj_aabb=obj_aabb, _retry=True)
        return None, None
    print(f"    Grip verified for {obj_name}: both pads in contact, "
          f"pad_normal_force={grip_nf:.2f}N, measured half-width "
          f"{width * 1000:.1f} mm vs estimate {pinch_half * 1000:.1f} mm")

    # Audit #82: post-pick assertion — only the newly grasped cube should
    # be in contact with the robot.  Anything else surfaces a ghost from
    # a prior release that did not actually drop.
    audit_robot_held_state(env, robot_id, expected_held_body_id=obj_id,
                            tag=f"post-pick:{obj_name}")

    # Hardcoded post-pick lift (audit #36, THESIS_NOTES §19): smaller
    # than place/stack (~5 cm) — cosmetic only for the holding-goal
    # terminate-at-contact view; the next plan_motion already runs in
    # free space because the cube now rides in the closed gripper.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # #P1 F1(b) post-lift re-verify: with the weld gone, "verified at
    # close" can never be assumed to mean "still held after the lift".
    # A phantom hold (tips standing on the object top), a close-then-
    # eject, or a slip-on-lift all separate here — the object stays
    # behind while the EE rises.  Re-check both pads against obj_id and
    # abort into the dispatcher's replan path on loss.
    lift_contacts = p.getContactPoints(bodyA=robot_id, bodyB=obj_id)
    lift_pads = {c[3] for c in lift_contacts if c[3] in FINGER_JOINTS}
    if lift_pads != set(FINGER_JOINTS):
        lift_nf = sum(c[9] for c in lift_contacts
                      if c[3] in FINGER_JOINTS)
        obj_z_now = p.getBasePositionAndOrientation(obj_id)[0][2]
        print(f"    ERROR: grip lost after post-pick lift for {obj_name} — "
              f"pad contacts={sorted(lift_pads) or 'none'} (need both "
              f"{FINGER_JOINTS}), pad_normal_force={lift_nf:.2f}N, "
              f"obj_z={obj_z_now:.4f}. Opening gripper and replanning "
              f"(#P1 F1).")
        open_gripper(robot_id, gui)
        return None, None

    # Read the actual joint state — position control may not reach the
    # exact IK target.  Tracking the true state prevents PDDL state
    # drift from compounding across chained actions within a plan
    # (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    final_config = RobotConfig(joint_positions=actual_joints,
                               name="post_pick_contact")
    return obj_id, final_config


def _grasp_ee_to_obj_z(held_aabb, table_z: float) -> float:
    """EE-to-object-centre vertical offset the pick established (#P1
    WP2b, 2026-09-19).  execute_pick descends to max(top - 5 mm,
    table + 35 mm finger-tip depth) and pinches there, so with the
    object's rigid box (the registry estimate it was picked with) the
    offset is known without reading the held body's pose.  Negative:
    the object's centre hangs below the EE.  A vertical slip inside the
    pads is the residual the drop observation catches.
    """
    top = float(held_aabb[1][2])
    bottom = float(held_aabb[0][2])
    half_h = (top - bottom) / 2.0
    contact_z = max(top - 0.005, table_z + 0.035)   # mirrors execute_pick
    return (top - half_h) - contact_z


def execute_place(robot_id, env, obj_name, place_pos, grasp, config,
                  held_body_id, gui, held_aabb=None) -> Optional[RobotConfig]:
    """
    Execute place action using the plan's grasp pose.

    Assumes the planned `move` action has already delivered the arm to
    the compute_kin_solution config (boxel.center + grasp.position,
    10 cm above the destination).  This routine only handles the
    final lower-and-release:

      IK (seeded from `config`, audit #37/#38) + lower to release
      height  →  open gripper through the finger motors  →  settle.

    The release height is computed so the held object's bottom rests on
    the table surface, using the live EE-to-object offset (whatever
    grip height the friction grasp established at pick time).

    A small (~10 cm) hardcoded post-place lift runs after the settle
    so the next ``move`` action's plan_motion has safe headroom over
    the just-placed cube.  See audit #36 / THESIS_NOTES.md §19; the
    lift is invisible to the planner — ``final_config`` carries the
    lifted pose forward.

    Args:
        robot_id: PyBullet body ID of the robot
        env: BoxelTestEnv instance
        obj_name: Name of the object being placed (for logging)
        place_pos: Destination position [x, y, z] (boxel center)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        held_body_id: PyBullet body ID of the held object, from
            execute_pick() (may be None for the defensive no-held path)
        gui: Whether GUI is active (for step_simulation timing)

    Returns:
        RobotConfig: The robot's actual final joint configuration
        (contact position with the object resting on the table below
        the EE).
    """
    # --- Release height from held-object geometry ----------------------------
    # Compute the EE height that places the held object's bottom on the
    # table surface.  The live EE-to-object Z offset accounts for
    # whatever grip height the friction grasp established at pick time.
    table_z = env.table_surface_height
    rigid_ext = None
    if held_body_id is not None:
        # #P1 F1(c): held-contact entry assert — raises EmptyHandError
        # (dedicated dispatcher path) when the object was lost in
        # transport or the hold was phantom all along.
        _assert_held_contact(robot_id, held_body_id, obj_name, gui,
                             action="place")
        # #P1 WP2b (2026-09-19): the held object's height and the
        # EE-to-object offset come from the ESTIMATED box it was picked
        # with (registry, rigid size) and the pick's own contact rule,
        # not from p.getAABB / p.getBasePositionAndOrientation.
        if held_aabb is None:
            print(f"    ERROR: execute_place({obj_name}) needs the held "
                  f"object's estimated box (#P1 WP2b) — none passed; "
                  f"aborting")
            return None
        rigid_ext = (np.asarray(held_aabb[1], dtype=float)
                     - np.asarray(held_aabb[0], dtype=float))
        obj_half_height = float(rigid_ext[2]) / 2.0
        ee_to_obj_z = _grasp_ee_to_obj_z(held_aabb, table_z)

        target_obj_z = table_z + obj_half_height
        contact_z = target_obj_z - ee_to_obj_z
    else:
        contact_z = place_pos[2] + grasp.position[2]

    contact_ee = np.array([
        place_pos[0] + grasp.position[0],
        place_pos[1] + grasp.position[1],
        contact_z,
    ])

    # No pre-contact approach motion (refactor step 2).  The prior
    # planned `move` action already delivered the arm to `config`, the
    # compute_kin_solution config — which targets place_pos +
    # grasp.position (10 cm above destination).  We seed the contact-
    # pose IK with `config.joint_positions` so the solver stays in
    # the same IK branch the planner already validated (audit
    # #37/#38).
    pc = env.client_id
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc,
                              seed=config.joint_positions)

    if contact_joints is None:
        print(f"    ERROR: IK failed for place contact of {obj_name} — aborting")
        return None

    # settle=True: release-height accuracy feeds the audit-#80 drop
    # gate's 2 cm height check (#P1 endpoint hold, precision endpoint).
    move_robot_smooth(robot_id, contact_joints, gui, settle=True)

    # Audit #85's 15 mm pre-release lift was removed here (#P1 scope
    # decision, 2026-08-20).  It compensated for a weld-era geometry:
    # the gentle cosmetic close let the cube tilt up to ~11° in the
    # weld's grip, and a tilted corner poked a pad on open.  The
    # friction grasp squeezes the cube flat between both pads (observed
    # pick tilt ≤ ~1.6°), so the wedge geometry that motivated the lift
    # is gone; if drop verification regresses on place, restore the
    # lift with a physical justification and disclose it.

    # Verify the cube actually falls free of the gripper — finger-pad
    # snags / position-control overshoot can leave it pinched even
    # after the motors drive toward open (audit #75).  Helper opens the
    # gripper, settles, and retries on failure.  On a verified drop the
    # caller's post-place lift + plan-client sync run normally; on
    # failure return None and let the dispatcher replan.
    if held_body_id is not None:
        # Tactile half of the drop verification (fingers open, no robot-
        # link contact); the observed half runs after the lift below.
        if not _release_and_verify_drop(env, robot_id, gui,
                                         held_body_id, obj_name):
            print(f"    ERROR: drop verification failed for {obj_name} "
                  f"after place — aborting (audit #75/#80)")
            return None
    else:
        # Defensive fallback: place called without a held object (not
        # reachable from a planner-scheduled action, but the surface
        # API tolerates it).
        open_gripper(robot_id, gui)
        for _ in range(30):
            p.stepSimulation()
            telemetry.tick()

    # Hardcoded post-place lift (audit #36, THESIS_NOTES §19): give the
    # next plan_motion ~10 cm of safe headroom over the just-placed cube.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # Observed half of the drop verification (#P1 WP2b): with the hand
    # out of the way, the camera checks the placed object's top against
    # table + rigid height, its footprint against the rigid size, and
    # that it is not moving.
    _obs_centre = None
    if held_body_id is not None:
        _ok, _diag, _obs_centre = _observe_release(
            env, obj_name, expected_top_z=table_z + float(rigid_ext[2]),
            rigid_ext=rigid_ext, enforce_tilt=True)
        print(f"    [release-obs] {obj_name}: {_diag}")
        if not _ok:
            print(f"    ERROR: drop verification failed for {obj_name} "
                  f"after place — the observation disagrees; aborting "
                  f"(#P1 WP2b)")
            return None

    # audit #60 fix (ii) — mirror the placed cube into plan_client so
    # subsequent plan_motion calls see the correct obstacle layout.
    # sync_to_plan_client only fires at replan boundaries, so without
    # this the placed cube remains at its pre-place pose in plan_client
    # and plan_motion certifies trajectories through where it actually
    # sits.  #P1 WP2c: the mirror is the BELIEF — the release
    # observation's centre when the camera saw the placed object, else
    # the intended destination (cell centre, bottom on the table).
    if held_body_id is not None and held_body_id in env._gui_to_plan:
        _mirror = (_obs_centre if _obs_centre is not None
                   else np.array([place_pos[0], place_pos[1],
                                  table_z + float(rigid_ext[2]) / 2.0]))
        p.resetBasePositionAndOrientation(
            env._gui_to_plan[held_body_id], [float(v) for v in _mirror],
            [0.0, 0.0, 0.0, 1.0], physicsClientId=env.plan_client_id)

    # Read actual joint state to prevent drift accumulation (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name="post_place_contact")


def execute_stack(robot_id, env, obj_name, on_obj_name, grasp, config,
                  held_body_id, gui, held_aabb=None,
                  support_aabb=None) -> Optional[RobotConfig]:
    """
    Drop the held object on top of ``on_obj_name`` (audit #30, --goal stack).

    Mirrors :func:`execute_place` in shape but the destination is read
    LIVE from PyBullet rather than derived from a free-space boxel
    centre:

      EE z = on_obj_top_z + held_half_height - ee_to_obj_z

    ``ee_to_obj_z`` is the current EE→object Z offset (read from the
    held body's live pose just like execute_place), so any drift in
    the grasp pose between pick and stack is accounted for.

    Why live AABBs instead of the planner's symbolic destination:
    in a multi-step stack, by the time the third stack action runs the
    first two cubes have physically settled and may differ slightly from
    the planner's nominal pose.  Reading the support's actual top each
    time keeps the placement geometrically grounded.

    A small (~10 cm) hardcoded post-stack lift runs after the settle so
    the next ``move`` action's plan_motion has safe headroom over the
    freshly stacked column.  See audit #36 / THESIS_NOTES.md §19; the
    lift is invisible to the planner — ``final_config`` carries the
    lifted pose forward.

    The contact-pose IK is seeded with the planner's ``config`` (audit
    #37/#38) so the solver stays in the same IK branch the planner
    already validated — the Cartesian lower is ~10 cm and stays well
    within IK's iteration budget given the seed.

    Args:
        robot_id: PyBullet body ID of the robot.
        env: BoxelTestEnv (for env.objects lookup and client_id).
        obj_name: Held object's name (logging).
        on_obj_name: Support object's name (must be in env.objects).
        grasp: Grasp from the planner (provides EE→object offset).
        config: RobotConfig from the planner's compute_stack_kin (the
            approach pose 10 cm above the support top).  Used as the
            IK seed for the contact-pose lower (audit #37/#38).
        held_body_id: PyBullet body ID of the held object, from the
            prior execute_pick.  Required.
        gui: Whether GUI is active (controls move_robot_smooth pacing).

    Returns:
        RobotConfig at the contact pose after release+settle, or None on
        IK failure (caller replans).
    """
    if on_obj_name not in env.objects:
        print(f"    ERROR: stack support '{on_obj_name}' not in env.objects")
        return None
    if held_body_id is None:
        print(f"    ERROR: stack {obj_name} on {on_obj_name} called without "
              f"a held object.")
        return None

    # #P1 F1(c): held-contact entry assert — raises EmptyHandError
    # (dedicated dispatcher path) when the object was lost in transport
    # or the hold was phantom all along.
    _assert_held_contact(robot_id, held_body_id, obj_name, gui,
                         action="stack")

    # #P1 WP2b (2026-09-19): the destination is the support's ESTIMATED
    # box (registry: re-posed by every observation and by the post-stack
    # refresh, so a settled tower is still followed) and the held
    # object's height and EE offset come from the box it was picked
    # with — no p.getAABB / p.getBasePositionAndOrientation for control.
    if held_aabb is None or support_aabb is None:
        print(f"    ERROR: execute_stack({obj_name} on {on_obj_name}) needs "
              f"the estimated boxes of the held object and the support "
              f"(#P1 WP2b) — missing; aborting")
        return None
    sup_min = np.asarray(support_aabb[0], dtype=float)
    sup_max = np.asarray(support_aabb[1], dtype=float)
    sup_top_z = float(sup_max[2])
    sup_cx = float((sup_min[0] + sup_max[0]) / 2.0)
    sup_cy = float((sup_min[1] + sup_max[1]) / 2.0)

    rigid_ext = (np.asarray(held_aabb[1], dtype=float)
                 - np.asarray(held_aabb[0], dtype=float))
    held_half_height = float(rigid_ext[2]) / 2.0
    ee_to_obj_z = _grasp_ee_to_obj_z(held_aabb, env.table_surface_height)

    target_obj_z = sup_top_z + held_half_height
    contact_z = target_obj_z - ee_to_obj_z

    contact_ee = np.array([
        sup_cx + grasp.position[0],
        sup_cy + grasp.position[1],
        contact_z,
    ])

    # Audit #84 pre-lower diag - bracket the stack approach so a cube
    # that ends up on the plane instead of the support surfaces WHICH
    # input (support pose, grasp tilt, EE-obj Z) was wrong.  The tilt
    # and the true boxes are print-only ground truth.
    held_orn = p.getBasePositionAndOrientation(held_body_id)[1]
    held_euler = p.getEulerFromQuaternion(held_orn)
    held_tilt_deg = max(abs(np.degrees(held_euler[0])),
                         abs(np.degrees(held_euler[1])))
    _gt_sup = p.getAABB(env.objects[on_obj_name].object_id)
    print(f"    [#84-diag] stack {obj_name} on {on_obj_name}: "
          f"contact_ee=[{contact_ee[0]:.4f},{contact_ee[1]:.4f},"
          f"{contact_ee[2]:.4f}] target_obj_z={target_obj_z:.4f} "
          f"sup_top_z={sup_top_z:.4f} ee_to_obj_z={ee_to_obj_z:.4f} "
          f"held_half_height={held_half_height:.4f} "
          f"sup_est=[{sup_min[0]:.4f},{sup_min[1]:.4f},{sup_min[2]:.4f}]"
          f"-[{sup_max[0]:.4f},{sup_max[1]:.4f},{sup_max[2]:.4f}] "
          f"| gt-diag: sup_true_top={float(_gt_sup[1][2]):.4f} "
          f"held_tilt_deg={held_tilt_deg:.2f}")

    pc = env.client_id
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc,
                              seed=config.joint_positions)
    if contact_joints is None:
        # #P1 F4: the planner's config can be STALE by the time a
        # multi-step stack executes (computed against the support's
        # pre-stack pose — field report stale_shadow_drop.md: 29.4 mm
        # FK rejection at the level-4 salvage IK).  Retry once from
        # REST_POSES before aborting: a fresh solve is free to leave
        # the dead IK branch the stale seed pinned it to.
        print(f"    stack contact IK failed from the plan-config seed — "
              f"retrying from REST_POSES (#P1 F4)")
        contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation,
                                  pc)
        # Review fix 2026-08-20: the REST_POSES solve is free to land
        # in a DIFFERENT IK branch than the arm's current (planned,
        # collision-checked) pose — and move_robot_smooth below is
        # plain linear joint interpolation with no collision checking,
        # so a branch jump would sweep the arm, cube in hand, over the
        # very stack it is building.  Accept the retry only if it
        # stays near the current arm state (the true contact pose is a
        # ~10 cm lower from the approach, well under 0.9 rad on every
        # joint); otherwise abort to a replan, which re-derives the
        # kinematics through the refined stream IK anyway.
        if contact_joints is not None:
            _cur = [p.getJointState(robot_id, i)[0] for i in range(7)]
            _max_dj = max(abs(c - t)
                          for c, t in zip(_cur, contact_joints))
            if _max_dj > 0.9:
                print(f"    REST_POSES retry landed in a different IK "
                      f"branch (max joint delta {_max_dj:.2f} rad > "
                      f"0.9) — rejecting the unplanned sweep, aborting "
                      f"to replan (#P1 F4 review fix)")
                contact_joints = None
    if contact_joints is None:
        print(f"    ERROR: IK failed for stack contact of {obj_name} on "
              f"{on_obj_name} - aborting")
        return None

    # settle=True: stack landings need the tightest XY of all actions —
    # the #84 arrival diag measures exactly this endpoint (#P1 hold).
    move_robot_smooth(robot_id, contact_joints, gui, settle=True)

    # Audit #84 post-arrival diag - surfaces motion-control overshoot
    # or grasp-tilt drift between contact_z compute and arm arrival.
    # >5 mm overshoot OR >5 deg tilt drift flips the prefix to
    # "arrival-deviation" for easy greppability.
    live_ee_pos = p.getLinkState(robot_id, END_EFFECTOR_LINK)[0]
    live_obj_pos, live_obj_orn = p.getBasePositionAndOrientation(held_body_id)
    ee_xy_err = float(np.hypot(live_ee_pos[0] - contact_ee[0],
                                live_ee_pos[1] - contact_ee[1]))
    ee_z_err = float(live_ee_pos[2] - contact_ee[2])
    obj_z_err = float(live_obj_pos[2] - target_obj_z)
    live_euler = p.getEulerFromQuaternion(live_obj_orn)
    live_tilt_deg = max(abs(np.degrees(live_euler[0])),
                         abs(np.degrees(live_euler[1])))
    tilt_drift_deg = live_tilt_deg - held_tilt_deg
    overshoot = (max(ee_xy_err, abs(ee_z_err), abs(obj_z_err)) > 0.005
                 or abs(tilt_drift_deg) > 5.0)
    arrival_prefix = ("[#84-diag] arrival-deviation"
                      if overshoot else "[#84-diag] arrival")
    print(f"    {arrival_prefix} {obj_name} on {on_obj_name}: "
          f"live_ee=[{live_ee_pos[0]:.4f},{live_ee_pos[1]:.4f},"
          f"{live_ee_pos[2]:.4f}] ee_xy_err={ee_xy_err*1000:.2f}mm "
          f"ee_z_err={ee_z_err*1000:.2f}mm "
          f"live_obj_z={live_obj_pos[2]:.4f} "
          f"obj_z_err={obj_z_err*1000:.2f}mm "
          f"live_tilt_deg={live_tilt_deg:.2f} "
          f"tilt_drift_deg={tilt_drift_deg:+.2f}")

    # Verify the cube actually falls free of the gripper — finger-pad
    # snags / position-control overshoot can leave it pinched even
    # after the motors drive toward open (audit #75).  Helper opens the
    # gripper, settles 60 steps (matching the prior in-line settle so
    # the post-stack AABB read into the registry doesn't see a
    # micro-bouncing cube), and retries on failure.
    # audit #80: expected support Z is the support's live top.  Cube-on-
    # cube stacks land on the support top, so passing sup_top_z is the
    # tight check.  Tray supports are containers — the cube settles
    # INSIDE the cavity at the tray floor (~ table_z), not on the rim
    # top (sup_max[2]).  Skip the height gate for trays and let the
    # tray-aware geometric check in _verify_cube_on (audit #40,
    # test_full_pipeline.py:127-180) catch geometric stack failures
    # downstream.  The other 3 gate signals (fingers open, no robot
    # contact, cube stationary) still catch a gripper pin regardless
    # of support shape.
    support_info = env.objects.get(on_obj_name)
    support_is_tray = bool(getattr(support_info, 'is_tray', False))

    # Tactile half of the drop verification (fingers open, no robot-
    # link contact); the observed half runs after the lift below.
    if not _release_and_verify_drop(env, robot_id, gui,
                                     held_body_id, obj_name,
                                     base_settle_steps=60):
        print(f"    ERROR: drop verification failed for {obj_name} on "
              f"{on_obj_name} — aborting (audit #75/#80)")
        return None

    # Hardcoded post-stack lift (audit #36, THESIS_NOTES §19): the EE
    # currently sits on top of the freshly stacked column; lift ~10 cm
    # so the next plan_motion has safe headroom over the column.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # Observed half (#P1 WP2b): the stacked object's top should sit at
    # the support's estimated top + its rigid height.  A tray is a
    # container — the cube settles on the tray floor, not on the rim
    # the box top is — so the top check is skipped there and the
    # tray-aware _verify_cube_on (audit #40) remains the geometric
    # gate; upright and still are checked for every support.
    _ok, _diag, _obs_centre = _observe_release(
        env, obj_name,
        expected_top_z=None if support_is_tray else sup_top_z + float(rigid_ext[2]),
        rigid_ext=rigid_ext, enforce_tilt=True)
    print(f"    [release-obs] {obj_name} on {on_obj_name}: {_diag}")
    if not _ok:
        print(f"    ERROR: drop verification failed for {obj_name} on "
              f"{on_obj_name} — the observation disagrees; aborting "
              f"(#P1 WP2b)")
        return None

    # audit #60 fix (ii) — mirror the stacked cube's runtime pose into
    # plan_client (mirror of execute_place's sync; see that function for
    # rationale).  Without this, plan_motion in subsequent plan_motion
    # calls cannot see the stacked cube at its runtime location and may
    # certify trajectories straight through the new tower.
    # #P1 WP2c: the mirror is the BELIEF — the release observation's
    # centre when the camera saw the stacked object, else the intended
    # destination on the support's estimated top.
    if held_body_id in env._gui_to_plan:
        _mirror = (_obs_centre if _obs_centre is not None
                   else np.array([sup_cx, sup_cy, target_obj_z]))
        p.resetBasePositionAndOrientation(
            env._gui_to_plan[held_body_id], [float(v) for v in _mirror],
            [0.0, 0.0, 0.0, 1.0], physicsClientId=env.plan_client_id)

    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name=f"post_stack_{obj_name}_on_{on_obj_name}")


# compute_push_displacement() removed (#53): push superseded by pick-and-place.
# The function teleported occluders via p.resetBasePositionAndOrientation without
# involving the robot arm. Occluder relocation now uses pick â move â place.


# ---------------------------------------------------------------------------
# Action-dispatch handler (extracted from test_full_pipeline.py 2026-05-05)
# ---------------------------------------------------------------------------
# When a handler returns continue_=False, the dispatch loop in
# test_full_pipeline.py breaks and the outer replan loop runs
# release_held_object_in_place BEFORE the next planner.plan().  That
# release is a hidden side-channel — no PDDL action represents it
# (audit S-01) — so the typed return value is what keeps the contract
# visible.  Do not collapse it back to a bare True/False without
# preserving the reason tag for trace auditing.


@dataclass(frozen=True)
class ActionResult:
    """Outcome of a single action handler.

    continue_ = True   action succeeded; dispatch loop runs the next action.
    continue_ = False  action interrupted; dispatch loop breaks and the
                       outer replan loop will drop any held object before
                       re-planning.  ``reason`` tags the cause for
                       debugging/audit traces.
    """
    continue_: bool
    reason: str = ""


INTEGRITY_DISTURB_M = 0.015      # a believed body found this far away was disturbed
INTEGRITY_SUPPORT_TOL_M = 0.02   # a stacked body's bottom this far off its support's top has fallen


def world_integrity_check(*, env, registry, belief, viz, shadows, occluders,
                          shadow_occluder_map, boxel_centers, on_relations,
                          held_name=None, label=""):
    """#P2 (a) world-integrity monitor (2026-09-19): after an executed
    action, observe the scene once and reconcile every registered
    object's belief with what the camera shows.

    Decisions come from perception only (env.detect_objects, the same
    render the sense action uses); the simulator is never read.  Per
    registered OBJECT boxel, except the held one (F26: its region is
    legitimately empty — exclude_ids) and the tray (fixed):
      knocked_off_table — its detection lies wholly below the table
                          surface: retired (retire_lost_objects);
      lost              — no detection and its believed region renders
                          empty on every slice (refresh_object_aabbs'
                          check): retired;
      disturbed         — detected more than INTEGRITY_DISTURB_M from
                          its believed centre: the boxel is re-posed
                          (rigid-size fusion) and the census re-run;
      toppled           — its raw detection is far lower and wider than
                          its rigid box (a box on its side; a cube's
                          topple is not visible in an AABB): re-posed,
                          reported;
      off_support       — it is believed stacked (on_relations) but its
                          bottom is no longer at its support's top: the
                          relation is dropped so the planner re-stacks.
    An object the render does not show and whose region is occluded is
    kept as believed (cannot see, cannot claim).  Telemetry's ground-
    truth DISTURBED / TOPPLE / OFF_SUPPORT events are the validation
    labels for these verdicts in the run log.  Returns (events, dets):
    the event list (dicts with kind, object, label and a measure) and
    the render's detections, which the caller hands to
    register_new_detections so a body this observation shows for the
    first time enters the belief here too (review 2026-09-19: a knocked-
    away occluder can leave the target in plain view, and a run must
    not end "all searched" on it).  Mutates the registry, belief,
    shadows, boxel_centers, on_relations and shadow_occluder_map
    exactly as the sense action's discovery paths do.
    """
    dets, _, depth_buf, seg = env.detect_objects()
    render = (env._depth_buffer_to_meters(depth_buf), seg,
              *env._view_and_projection_matrices())
    table_z = env.table_surface_height
    obj_boxels = [bd for bd in registry.get_boxels_by_type(BoxelType.OBJECT)
                  if bd.id != held_name
                  and not getattr(env.objects.get(bd.id), "is_tray", False)]
    before = {bd.id: (np.asarray(bd.center, dtype=float).copy(),
                      np.asarray(bd.max_corner, dtype=float)
                      - np.asarray(bd.min_corner, dtype=float))
              for bd in obj_boxels}
    events = []
    floor = []
    toppled = []
    for bd in obj_boxels:
        det = dets.get(bd.id)
        if det is None or det.pixel_count < DETECTION_MIN_PIXELS:
            continue
        if float(det.est_max[2]) < table_z - DETECTION_SUPPORT_SNAP:
            floor.append(bd.id)
            events.append({"kind": "knocked_off_table", "object": bd.id,
                           "label": label,
                           "top_below_table_mm": round(
                               (table_z - float(det.est_max[2])) * 1000, 1)})
            continue
        raw_ext = np.asarray(det.est_max - det.est_min, dtype=float)
        rigid = before[bd.id][1]
        if (raw_ext[2] < rigid[2] - 0.03
                and max(raw_ext[0], raw_ext[1]) > max(rigid[0], rigid[1]) + 0.03):
            toppled.append(bd.id)
    exclude = set(floor)
    if held_name is not None:
        exclude.add(held_name)
    lost = refresh_object_aabbs(env, registry, viz, detections=dets,
                                render=render, check_lost=True,
                                exclude_ids=frozenset(exclude))
    for name in lost:
        events.append({"kind": "lost", "object": name, "label": label})
    for bd in obj_boxels:
        if bd.id in floor or bd.id in lost:
            continue
        shift = float(np.hypot(*((np.asarray(bd.center, dtype=float)
                                  - before[bd.id][0])[:2])))
        if bd.id in toppled:
            # Review 2026-09-19: the rigid-size fusion is monotone, so a
            # topple would inflate the box for good (a 4 x 4 x 12 block on
            # its side became a 12 x 4 x 12 box that no grasp spans).  A
            # toppled body is re-initialised from the raw detection: its
            # box IS a new rigid size until it stands again.
            det = dets[bd.id]
            bd.min_corner = np.asarray(det.est_min, dtype=float).copy()
            bd.max_corner = np.asarray(det.est_max, dtype=float).copy()
            if viz is not None and viz.tracks_boxel(bd.id):
                viz.remove_boxel_viz(bd.id)
                viz.draw_boxel_data(bd)
            events.append({"kind": "toppled", "object": bd.id, "label": label,
                           "shift_mm": round(shift * 1000, 1),
                           "box_cm": [round(float(v) * 100, 1)
                                      for v in (bd.max_corner - bd.min_corner)]})
        elif shift > INTEGRITY_DISTURB_M:
            events.append({"kind": "disturbed", "object": bd.id,
                           "label": label, "shift_mm": round(shift * 1000, 1)})
    for obj, sup in list(on_relations.items()):
        if obj in floor or obj in lost or obj == held_name:
            on_relations.pop(obj, None)
            continue
        obd, sbd = registry.get_boxel(obj), registry.get_boxel(sup)
        if obd is None or sbd is None:
            continue
        if getattr(env.objects.get(sup), "is_tray", False):
            continue      # container: the cube rests on the tray floor
        gap = float(obd.min_corner[2]) - float(sbd.max_corner[2])
        if abs(gap) > INTEGRITY_SUPPORT_TOL_M:
            events.append({"kind": "off_support", "object": obj, "support": sup,
                           "label": label, "gap_mm": round(gap * 1000, 1)})
            on_relations.pop(obj, None)
    gone = floor + lost
    if gone:
        retire_lost_objects(gone, registry, viz, shadows, shadow_occluder_map,
                            boxel_centers, occluders, belief, render=render)
    if events:
        setattr(registry, "_dirty", True)
        for bd in registry.get_boxels_by_type(BoxelType.OBJECT):
            boxel_centers[bd.id] = bd.center
        new_map = compute_shadow_blockers(env.camera_position, registry,
                                          shadows, occluders, env)
        shadow_occluder_map.clear()
        shadow_occluder_map.update(new_map)
        for e in events:
            extra = {k: v for k, v in e.items()
                     if k not in ("kind", "object", "label")}
            print(f"    [integrity] {e['kind']}: {e['object']} after {label}"
                  f"{' ' + str(extra) if extra else ''}")
    else:
        n_obs = sum(1 for bd in obj_boxels
                    if bd.id in dets and dets[bd.id].pixel_count >= DETECTION_MIN_PIXELS)
        print(f"    [integrity] after {label}: {n_obs}/{len(obj_boxels)} "
              f"believed bodies observed where believed, none disturbed")
    return events, dets


def refresh_object_aabbs(env, registry, viz=None, detections=None,
                         render=None, check_lost=False,
                         exclude_ids=frozenset()):
    """Refresh every OBJECT boxel's AABB from a fresh OBSERVATION (audit
    #71; rewired to perception estimates by #P1 step (2c), 2026-08-21 —
    this used to be the last per-episode p.getAABB chokepoint feeding
    the planner).

    Called at the end of each handle_sense_action outcome branch and
    after pick/place failures so the next replan reads the registry
    over current geometry instead of the spawn-time AABB.  SHADOW
    boxels are NOT recomputed here — accepted thesis gap per
    user-explicit scope cut.  Cost is one TinyRenderer pass (~190 ms).

    RIGID-SIZE TRACKING: an object's size cannot change, but a refresh
    render often has the ARM partially occluding the just-manipulated
    object, and a naive re-estimate would shrink the boxel to the
    visible sliver (misleading every fits/kin consumer).  So the boxel's
    extents are canonical — per axis the MAX of the current extents and
    the fresh estimate's — and the refresh re-POSES that known-size box:
    XY centred on the fresh estimate, z anchored to the estimate's top
    (the top face is the best-observed surface from this camera).  An
    object with no detection at all (fully behind the arm) keeps its
    last estimate — honest staleness, logged.

    Per-object early-out: if the resulting AABB matches the registry
    value within _aabb_tol (0.1 mm — same FP-noise budget reboxelize
    uses), skip the write AND the viz remove/redraw.

    ``detections`` (#P1 step 3): pass the detection dict of an
    observation the caller already rendered (handle_sense_action's
    single-render contract) to skip the extra TinyRenderer pass; None
    renders fresh, as before.

    LOST-OBJECT CHECK (#P1 step 3c — the step-(2c) follow-on): with
    ``check_lost=True``, every STALE object (no detection this render)
    whose believed region is nonetheless OBSERVED EMPTY — the boxel's
    own sense-grid endpoints are visible through, i.e. the first
    rendered surface lies at/behind them on every slice up to the
    shared marginal tolerance — is reported LOST instead of kept: the
    object is provably not where the belief says (transit slip landed
    it elsewhere, or it was knocked off the table).  A stale object
    whose region is occluded (arm, another body, tray walls) stays
    kept-with-last-estimate as before — cannot see, cannot claim.
    ``render`` is (depth_image_m, seg_mask, view_matrix,
    projection_matrix) from the same observation as ``detections``;
    rendered internally when needed.  ``exclude_ids`` names boxels
    never touched — neither re-posed nor lost-checked (the held object
    mid-manipulation: its region is legitimately empty and its
    detection is in the air).  Returns the list of LOST boxel ids; the
    caller owns the retirement bookkeeping (retire_lost_objects).
    """
    _aabb_tol = 1e-4
    if detections is None or render is None:
        _dets, _, _depth_buf, _seg = env.detect_objects()
        if detections is None:
            detections = _dets
        if render is None:
            render = (env._depth_buffer_to_meters(_depth_buf), _seg,
                      *env._view_and_projection_matrices())
    # Arm-occlusion guard (review 2026-09-19): a body the ARM partly hides
    # renders as a partial cloud whose centre is off — re-posing the
    # rigid box on it would move the belief by centimetres and the #P2
    # monitor would call that "disturbed" after every move the arm ends
    # near a bystander.  A body whose box lattice (3 x 3 x 3) has any
    # point behind the robot in this render keeps its last estimate.
    _robot_id = env.objects["robot"].object_id if "robot" in env.objects else None
    _depth_m, _seg_m, _view_m, _proj_m = render
    stale = []
    for obj_boxel in registry.get_boxels_by_type(BoxelType.OBJECT):
        obj_info = env.objects.get(obj_boxel.id)
        if obj_info is None:
            continue
        if obj_boxel.id in exclude_ids:
            # F26 (2026-09-19): a boxel named here is never touched — the
            # held object mid-manipulation renders in the air, and re-
            # posing its boxel there (with the F22 support completion
            # stretching the cloud down to the table) turned a 12 cm
            # block into a 20 cm one in the first #P2 monitor smoke.
            continue
        det = detections.get(obj_boxel.id)
        if det is None:
            stale.append(obj_boxel.id)
            continue
        if _robot_id is not None:
            _g = [np.linspace(float(obj_boxel.min_corner[k]),
                              float(obj_boxel.max_corner[k]), 3) for k in range(3)]
            _pts = np.array([[x, y, z] for x in _g[0] for y in _g[1] for z in _g[2]])
            _icp, _hids, _ = first_surface_interceptors(
                _pts, _depth_m, _seg_m, _view_m, _proj_m)
            if np.any(_icp & (_hids == _robot_id)):
                print(f"    [perception] {obj_boxel.id} partly behind the arm "
                      f"in this render — keeping its last estimate")
                continue
        cur_ext = np.asarray(obj_boxel.max_corner, dtype=float) \
            - np.asarray(obj_boxel.min_corner, dtype=float)
        est_ext = det.est_max - det.est_min
        canon_ext = np.maximum(cur_ext, est_ext)
        centre_xy = (det.est_min[:2] + det.est_max[:2]) / 2.0
        new_max = np.array([centre_xy[0] + canon_ext[0] / 2.0,
                            centre_xy[1] + canon_ext[1] / 2.0,
                            det.est_max[2]])
        new_min = new_max - canon_ext
        if (np.allclose(new_min, obj_boxel.min_corner, atol=_aabb_tol) and
                np.allclose(new_max, obj_boxel.max_corner, atol=_aabb_tol)):
            continue
        obj_boxel.min_corner = new_min
        obj_boxel.max_corner = new_max
        # Review 2026-09-19: a re-posed body may now overlap FREE cells
        # (a rejected release left the object where the cell still reads
        # free); the dirty flag makes the next replan re-carve free space.
        setattr(registry, "_dirty", True)
        if viz is not None and viz.tracks_boxel(obj_boxel.id):
            viz.remove_boxel_viz(obj_boxel.id)
            viz.draw_boxel_data(obj_boxel)
    # #P1 F20 visibility: name every detection that has NO registry boxel.
    # This refresh only re-poses boxels that already exist; the sense
    # action's observation is what registers new ones (register_new_
    # detections).  Before this line existed, run 13-25-19 carried the
    # target in five consecutive sense detection dicts without a trace.
    _unregistered = sorted(
        n for n in detections
        if registry.get_boxel(n) is None and n in env.objects
        and n not in ("plane", "table", "robot")
        and not getattr(env.objects[n], "is_tray", False))
    if _unregistered:
        print(f"    [perception] detected but UNREGISTERED (no boxel): "
              f"{_unregistered} — only a sense observation registers "
              f"new objects (#P1 F20); this refresh re-poses known "
              f"boxels only")
    lost = []
    if stale and check_lost and render is not None:
        depth_m, seg, view_m, proj_m = render
        for oid in list(stale):
            if oid in exclude_ids:
                continue
            bd = registry.get_boxel(oid)
            if bd is None:
                continue
            slices, _ = sense_ray_slices(bd.min_corner, bd.max_corner)
            observed_empty = bool(slices)
            for sl in slices:
                icp, _hids, in_view = first_surface_interceptors(
                    sl.points, depth_m, seg, view_m, proj_m)
                not_visible = np.count_nonzero(icp | ~in_view)
                if (not_visible / len(sl.points)
                        > SENSE_MARGINAL_BLOCKED_FRACTION):
                    observed_empty = False
                    break
            if observed_empty:
                stale.remove(oid)
                lost.append(oid)
    if lost:
        print(f"    [perception] LOST object(s) — believed region "
              f"renders empty on every slice: {sorted(lost)} "
              f"(#P1 step 3c; caller retires their boxels/shadows)")
    if stale:
        print(f"    [perception] {len(stale)} object(s) not visible in "
              f"the refresh render — keeping last estimate: "
              f"{sorted(stale)}")
    return lost


def _fragment_renders_empty(bd, render) -> bool:
    """Is every sense slice of this fragment visible-through in ``render``
    (depth_m, seg, view, proj) up to the shared marginal tolerance?  The
    same test refresh_object_aabbs applies to a stale object's region."""
    depth_m, seg, view_m, proj_m = render
    slices, _ = sense_ray_slices(bd.min_corner, bd.max_corner)
    if not slices:
        return False
    for sl in slices:
        icp, _hids, in_view = first_surface_interceptors(
            sl.points, depth_m, seg, view_m, proj_m)
        if (np.count_nonzero(icp | ~in_view) / len(sl.points)
                > SENSE_MARGINAL_BLOCKED_FRACTION):
            return False
    return True


def retire_lost_objects(lost_ids, registry, viz, shadows,
                        shadow_occluder_map, boxel_centers, occluders,
                        belief, render=None, env=None):
    """Remove a LOST object's boxel and, where observed empty, its shadow
    fragments (#P1 step 3c).

    A lost object's believed region was OBSERVED empty
    (refresh_object_aabbs check_lost) or its detection lies below the
    table (#P2 knocked_off_table), so its OBJECT boxel is a stale
    fiction.  Its shadow fragments describe occlusion from a pose the
    object no longer occupies, but "the caster is gone" does not by
    itself observe them empty — another body may stand in front (review
    2026-09-19).  With a ``render`` (or an ``env`` to take one), each
    fragment is tested with the sense slices: an observed-empty fragment
    is marked not_here and removed, mirroring clear_but_empty; one that
    is still occluded is KEPT as an unknown region without a caster and
    left to the sense action.  Without either, every fragment is removed
    as before (the pre-review behaviour, now only for callers that have
    no observation at hand).  The object may re-enter later through
    detection or a contains_nontarget discovery.
    """
    if render is None and env is not None:
        _, _, _depth_buf, _seg = env.detect_objects()
        render = (env._depth_buffer_to_meters(_depth_buf), _seg,
                  *env._view_and_projection_matrices())
    for oid in lost_ids:
        bd = registry.get_boxel(oid)
        if bd is None:
            continue
        kept = []
        for sid in list(getattr(bd, "shadow_boxel_ids", [])):
            sbd = registry.get_boxel(sid)
            if sbd is not None and render is not None \
                    and not _fragment_renders_empty(sbd, render):
                kept.append(sid)
                continue
            if sbd is not None:
                belief.mark_sensed(sid, found=False)
                registry.remove_boxel(sid)
            if viz is not None:
                viz.remove_boxel_viz(sid)
            if sid in shadows:
                shadows.remove(sid)
            shadow_occluder_map.pop(sid, None)
            boxel_centers.pop(sid, None)
        registry.remove_boxel(oid)
        if viz is not None:
            viz.remove_boxel_viz(oid)
        boxel_centers.pop(oid, None)
        if oid in occluders:
            occluders.remove(oid)
        print(f"    -> retired LOST {oid}: OBJECT boxel removed; shadow "
              f"fragments {'observed empty and removed' if not kept else 'removed where observed empty, kept (still occluded): ' + str(kept)}")


def _shrink_shadow_fragment(registry, shadow_bd, blocked_min, blocked_max,
                            viz, boxel_centers):
    """#P1 partial-reveal shrink (2026-08-21, user-directed).

    A still_blocked sense is not a null observation: every CLEAR ray
    observed its column of the fragment empty.  Shrink the fragment to
    the blocked rays' padded bounding box (the sub-region that remains
    unobserved) so the belief, the planner's boxel_fits grounding, and
    the GUI wireframe all track what is actually still hidden.  The
    fragment keeps its id, its belief status ('unknown' — the remaining
    region was NOT observed), and its blocked_counts strikes.

    Returns True when the fragment actually shrank.
    """
    new_min = np.maximum(np.asarray(shadow_bd.min_corner, dtype=float),
                         np.asarray(blocked_min, dtype=float))
    new_max = np.minimum(np.asarray(shadow_bd.max_corner, dtype=float),
                         np.asarray(blocked_max, dtype=float))
    # Degenerate guard — never register an inverted/sliver box (mirrors
    # the F3 shadow-construction guards).
    if np.any(new_max - new_min <= 1e-3):
        return False
    old_ext = shadow_bd.max_corner - shadow_bd.min_corner
    new_ext = new_max - new_min
    # Only rewrite geometry for a meaningful reveal (> 2 mm on some
    # axis, Z included — 2026-08-21) — avoids viz churn on repeat
    # identical senses.
    if not np.any(old_ext - new_ext > 0.002):
        return False
    shadow_bd.min_corner = new_min
    shadow_bd.max_corner = new_max
    boxel_centers[shadow_bd.id] = shadow_bd.center
    if viz is not None:
        viz.remove_boxel_viz(shadow_bd.id)
        viz.draw_boxel_data(shadow_bd)
    setattr(registry, "_dirty", True)
    print(f"    -> {shadow_bd.id} shrunk to the still-blocked region "
          f"({old_ext[0] * 100:.1f}x{old_ext[1] * 100:.1f}x"
          f"{old_ext[2] * 100:.1f} -> "
          f"{new_ext[0] * 100:.1f}x{new_ext[1] * 100:.1f}x"
          f"{new_ext[2] * 100:.1f} cm; the revealed part was observed "
          f"empty)")
    return True


def sweep_all_fragments(*, registry, belief, viz, shadows,
                        shadow_occluder_map, boxel_centers,
                        boxel_to_pybullet, target_pybullet_id, robot_id,
                        sense_support_ids, sense_depth_m, sense_seg,
                        sense_view, sense_proj, skip_ids=frozenset()):
    """Classify EVERY registry shadow fragment against one render (#P1 F16).

    The sense action already pays for a full depth+seg render, and that
    ONE observation carries the evidence for every fragment in the
    registry, not just the one the planner named.  Before this, the batch
    pass re-checked only the SAME CASTER's sibling fragments, and only
    when the primary outcome was clear_but_empty — so fragments belonging
    to other casters kept their planned senses even when the render
    already showed them empty, and a sense that ended blocked or
    unresolved (the F15 path) threw the whole observation away.

    Every removal here is observation-backed exactly as the sibling pass
    was: the fragment is deleted only on ``clear_but_empty``, i.e. every
    one of its grid endpoints was seen.  ``still_blocked`` fragments get
    the same partial-reveal shrink a planned sense would give them, and
    ``contains_nontarget`` fragments are left entirely alone for a
    planned sense that can do the discovery bookkeeping.

    A ``found_target`` on some OTHER fragment is reported loudly but NOT
    acted on: promoting it would have to run the audit-#76 registration
    chain from inside a sweep, and that chain is the found-path's
    contract.  Surfacing it lets the next plan plan for it.

    Returns (removed_ids, shrunk_ids, target_seen_ids).
    """
    removed, shrunk, target_seen = [], [], []
    for bd in list(registry.get_shadow_boxels()):
        sid = str(bd.id)
        if sid in skip_ids:
            continue
        occ_ids = set()
        for blocker_bid in shadow_occluder_map.get(sid, []):
            if blocker_bid in boxel_to_pybullet:
                occ_ids.add(boxel_to_pybullet[blocker_bid]['pybullet_id'])
        outcome, _, _, bbox, _ = sense_shadow_from_render(
            bd, target_pybullet_id, sense_depth_m, sense_seg,
            sense_view, sense_proj, occ_ids, robot_id=robot_id,
            support_body_ids=sense_support_ids)
        if outcome == "found_target":
            target_seen.append(sid)
            print(f"    [F16] the sense render also shows the TARGET in "
                  f"{sid} — left for a planned sense to register.")
            continue
        if outcome == "still_blocked":
            if bbox:
                _shrink_shadow_fragment(registry, bd, bbox[0], bbox[1],
                                        viz, boxel_centers)
                shrunk.append(sid)
            continue
        if outcome != "clear_but_empty":
            continue
        belief.mark_sensed(sid, found=False)
        registry.remove_boxel(sid)
        if viz is not None:
            viz.remove_boxel_viz(sid)
        if sid in shadows:
            shadows.remove(sid)
        shadow_occluder_map.pop(sid, None)
        boxel_centers.pop(sid, None)
        caster_id = bd.created_by_boxel_id or bd.created_by_object
        caster_bd = registry.get_boxel(caster_id) if caster_id else None
        if caster_bd is not None and sid in getattr(
                caster_bd, "shadow_boxel_ids", []):
            caster_bd.shadow_boxel_ids.remove(sid)
        removed.append(sid)
        print(f"    -> fragment {sid} observed empty in this render — "
              f"removed (F16 full sweep)")
    return removed, shrunk, target_seen


def register_new_detections(*, env, registry, belief, viz, detections,
                            target_name, shadows, occluders,
                            shadow_occluder_map, boxel_centers,
                            boxel_to_pybullet, object_body_ids,
                            skip_names=frozenset()):
    """Register every detected object that has no registry boxel (#P1 F20).

    The sense action observes the WHOLE workspace: its render detects
    every body the camera can see, not only what stands inside the named
    fragment.  Until 2026-09-18 that whole-frame evidence was thrown
    away — objects entered the registry only through the initial
    observation or when a sense hit them INSIDE the sensed fragment, so a
    target that became plainly visible after its occluders were moved
    (seed 999, run 13-25-19: five consecutive sense detections of the
    target, all discarded) stayed unknown and the episode ended
    "searched everything, not found".

    This is the belief update the thesis's sensor model prescribes for a
    sense observation ("target found, region known-empty, or a new
    occluder revealed"), applied to the full observation: a detected but
    unregistered body becomes an OBJECT boxel at its render estimate,
    exactly like the sense-discovery registration.  A non-target also
    joins ``occluders`` (compute_shadow_blockers maps only listed bodies)
    and casts its shadow fragments against the current solids AND the
    existing fragments (the audit-#68 cross-shadow carve, as the initial
    observation does), and every new fragment is added to the BELIEF as
    unknown so the replan loop cannot declare "all searched" over it.
    The search target itself gets no shadows (it is about to be picked)
    and the belief's found flag stays untouched: the pick sets it, and
    the loop's all-searched exit consults the registry instead.

    ``skip_names``: bodies never to register here (the held object, which
    a sense cannot see resting anywhere).  Returns the registered names.
    """
    registered = []
    table_z = env.table_surface_height
    for name in sorted(detections):
        if name in skip_names or registry.get_boxel(name) is not None:
            continue
        info = env.objects.get(name)
        if (info is None or name in ("plane", "table", "robot")
                or getattr(info, "is_tray", False)):
            continue
        det = detections[name]
        aabb_min = np.array(det.est_min, dtype=float)
        aabb_max = np.array(det.est_max, dtype=float)
        # A body seen BELOW the table surface is on the floor (knocked
        # off, #P2 territory): it is not a workspace object any more and
        # must not get on_table facts or a shadow.  Logged, not
        # registered.
        if aabb_min[2] < table_z - 0.02:
            print(f"    [F20] {name} is visible ({det.pixel_count} px) but "
                  f"lies below the table surface (z_min "
                  f"{aabb_min[2]:.3f} < {table_z:.3f}) — off the table, "
                  f"not registered (#P2 knocked_off_table).")
            continue
        obj_bd = BoxelData(
            id=name,
            boxel_type=BoxelType.OBJECT,
            min_corner=aabb_min,
            max_corner=aabb_max,
            object_name=name,
            is_occluder=False,
            on_surface="table" if aabb_min[2] <= table_z + 0.01 else None,
            surface_z=table_z,
        )
        registry.add_boxel(obj_bd)
        boxel_centers[name] = obj_bd.center
        object_body_ids[name] = env.plan_body_id(info.object_id)
        boxel_to_pybullet[name] = {
            'name': name,
            'pybullet_id': info.object_id,
            'position': np.array(det.est_center),
        }
        # `occluders` is the census's body list (every OBJECT boxel joins
        # it at startup, targets included, test_full_pipeline Phase 3):
        # a body absent from it can never be recorded as a blocker.
        if name not in occluders:
            occluders.append(name)
        belief.redetected.add(name)
        n_shadows = 0
        if name != target_name:
            obstacles = [bd for bd in registry.boxels.values()
                         if bd.boxel_type == BoxelType.OBJECT
                         and bd.id != name]
            obstacles.extend(registry.get_shadow_boxels())
            shadow_parts = env.shadow_calculator.calculate_shadow_boxel(
                obj_bd, obstacles)
            if shadow_parts:
                obj_bd.is_occluder = True
            for sp in shadow_parts:
                sp.created_by_boxel_id = name
                sp.created_by_object = name
                sp.on_surface = ("table"
                                 if sp.min_corner[2] <= table_z + 0.01
                                 else None)
                sp.surface_z = table_z
                s_id = registry.add_boxel(sp)
                obj_bd.shadow_boxel_ids.append(s_id)
                shadows.append(s_id)
                shadow_occluder_map[s_id] = [name]
                boxel_centers[s_id] = sp.center
                belief.add_shadow(s_id)
                n_shadows += 1
        if viz is not None:
            viz.draw_boxel_data(obj_bd)
            for s_id in obj_bd.shadow_boxel_ids:
                s_bd = registry.get_boxel(s_id)
                if s_bd is not None:
                    viz.draw_boxel_data(s_bd)
        # The free-space partition must be re-carved around the new solid
        # before the next plan (the loop's dirty check does it).
        setattr(registry, "_dirty", True)
        c = obj_bd.center
        role = ("the SEARCH TARGET — directly pickable, no sense needed"
                if name == target_name else
                f"non-target, now an occluder with {n_shadows} shadow "
                f"fragment(s) added to the belief as unknown")
        print(f"    [F20] {name} is visible in this observation but had no "
              f"boxel — registered at the render estimate "
              f"[{c[0]:.3f},{c[1]:.3f},{c[2]:.3f}] ({det.pixel_count} px); "
              f"{role}.")
        registered.append(name)
    if registered:
        # A newly registered body may stand between the camera and an
        # EXISTING fragment.  The blocker census only maps listed bodies
        # and is otherwise re-run after a place, so without this the
        # planner would keep deriving view_clear for that fragment, the
        # next sense of it would classify the body as CONTENT
        # (contains_nontarget) and delete the fragment with the target
        # possibly still behind the body (review finding 2026-09-18).
        # One extra render; the map is updated in place so the planner's
        # reference stays current.
        new_map = compute_shadow_blockers(
            env.camera_position, registry, shadows, occluders, env)
        shadow_occluder_map.clear()
        shadow_occluder_map.update(new_map)
        print(f"    [F20] blocker census refreshed for {len(shadows)} "
              f"fragment(s) after registering {registered}")
    return registered


def handle_sense_action(
    *,
    action_params,
    env,
    registry,
    belief,
    viz,
    target_name,
    robot_id,
    support_body_ids,
    shadows,
    occluders,
    shadow_occluder_map,
    blocked_counts,
    blocked_giveup_shadows,
    nontarget_rediscovery_counts=None,
    boxel_centers,
    boxel_to_pybullet,
    object_body_ids,
    body_id_to_name,
    show_free,
):
    """Execute one PDDL ``sense`` action.

    Casts rays from ``env.camera_position`` through the shadow volume;
    branches on the outcome:

      * found_target           → belief updated; continue plan.
      * clear_but_empty
        / contains_nontarget   → registry/viz/shadows cleaned up;
                                  OBJECT+SHADOW boxels created for newly-
                                  discovered bodies (audit S-09:
                                  perception expansion outside PDDL);
                                  free-space re-boxelized; break to replan.
      * still_blocked          → blocked_counts incremented; after 3
                                  strikes the shadow is given up
                                  (audit #21); break to replan.
      * unknown shadow id      → warn and break to replan.
    """
    # SENSE: cast rays from the fixed camera through the
    # shadow volume to determine what's inside.
    # Four sense outcomes are folded into three control-flow branches:
    #   found_target            → belief updated, plan continues to pick
    #   clear_but_empty
    #     / contains_nontarget  → shadow eliminated, break to replan
    #                              (contains_nontarget also registers the
    #                               discovered objects + their new shadows)
    #   still_blocked           → occluder not fully cleared, break to replan
    obj, shadow_id = action_params
    print(f"    Sensing {shadow_id} (fixed camera)...")

    # Retract arm to home so it doesn't block the camera's
    # line of sight to the shadow region (audit #79, #3 deferred).
    # home_joints = planner.home_config.joint_positions
    # move_robot_smooth(robot_id, home_joints, gui, steps=40)
    # current_config = planner.home_config

    shadow_boxel = registry.get_boxel(str(shadow_id))
    if shadow_boxel is None:
        print(f"    WARNING: Shadow '{shadow_id}' not found in registry. Replanning...")
        return ActionResult(continue_=False, reason="sense_missing_shadow")

    target_pybullet_id = env.objects[target_name].object_id
    occluder_pybullet_ids = set()
    for blocker_bid in shadow_occluder_map.get(str(shadow_id), []):
        if blocker_bid in boxel_to_pybullet:
            occluder_pybullet_ids.add(boxel_to_pybullet[blocker_bid]['pybullet_id'])

    # F5 low-slice companion: the dense slice's endpoints sit only 2 cm
    # above the fragment base, low enough that rays near the tray can
    # terminate on its 3 cm walls.  The tray is static support furniture
    # (audit #82 treats it as static too) — fold it into the ignored
    # supports so a wall hit neither blocks the observation nor
    # "discovers" the tray as a non-target object.
    sense_support_ids = frozenset(support_body_ids or ()) | {
        info.object_id for info in env.objects.values()
        if getattr(info, "is_tray", False)}

    # #P1 step (3): ONE rendered observation serves this entire sense
    # action — the main classification, the sibling batch-sense, the
    # discovery estimates and the closing AABB refresh all read the
    # same instant (GUI and headless twins render identical pixels,
    # ER_TINY_RENDERER both modes).
    sense_detections, sense_rgb, _sense_depth_buf, sense_seg = env.detect_objects()
    sense_depth_m = env._depth_buffer_to_meters(_sense_depth_buf)
    sense_view, sense_proj = env._view_and_projection_matrices()

    # #P1 F20: this ONE observation also registers every visible body that
    # has no boxel yet.  Called at the end of each outcome branch, AFTER
    # that branch's own registration (found-target hook, discovery
    # branch) so those keep their bookkeeping (audit #76, F9 strikes) and
    # this only catches what the fragment-scoped paths never looked at.
    def _register_new_detections():
        return register_new_detections(
            env=env, registry=registry, belief=belief, viz=viz,
            detections=sense_detections, target_name=str(target_name),
            shadows=shadows, occluders=occluders,
            shadow_occluder_map=shadow_occluder_map,
            boxel_centers=boxel_centers, boxel_to_pybullet=boxel_to_pybullet,
            object_body_ids=object_body_ids)

    (sense_outcome, blocked_fraction, detected_bodies,
     blocked_bbox, interceptor_counts) = sense_shadow_from_render(
        shadow_boxel,
        target_pybullet_id,
        sense_depth_m, sense_seg, sense_view, sense_proj,
        occluder_pybullet_ids,
        robot_id=robot_id,
        support_body_ids=sense_support_ids,
    )
    # World eye: the observation itself (camera view + detections) plus
    # how this sense classified the named fragment.
    world_eye.snapshot(
        f"sense {shadow_id} -> {sense_outcome}",
        registry=registry, belief=belief, detections=sense_detections,
        render=(sense_depth_m, sense_seg, sense_view, sense_proj),
        rgb=sense_rgb, save_image=True,
        shadow_occluder_map=shadow_occluder_map,
        extra={"outcome": sense_outcome,
               "blocked_fraction": round(float(blocked_fraction), 3),
               "detected_bodies": sorted(
                   body_id_to_name.get(b, str(b)) for b in detected_bodies),
               "interceptors": {body_id_to_name.get(b, str(b)): n
                                for b, n in interceptor_counts.items()}})

    if sense_outcome == "found_target":
        belief.mark_sensed(str(shadow_id), found=True)
        print(f"    *** TARGET FOUND in {shadow_id}! (ray-cast) ***")

        # Audit #76: register an OBJECT boxel for the discovered target.
        # Hidden targets have no OBJECT boxel at startup (they live inside
        # a shadow region).  Without this hook, every subsequent _build_init
        # rebuilds init from registry+belief and finds no (obj_at_boxel
        # target ?) fact for the target — so any plan that breaks mid-
        # execution (audit #40 stack physics failure, IK failure mid-pick)
        # leaves the planner unable to ground a re-pick of the same target.
        # PDDLStream then concludes "Stream plan: False" at complexity 3
        # in ~1 s with sample_time=0 — the audit #76 freeze-mode failure.
        # The contains_nontarget branch below already registers OBJECT
        # boxels for discovered non-targets; this is the symmetric hook
        # for targets.
        target_obj_str = str(obj)
        target_info = env.objects.get(target_obj_str)
        if (target_info is not None
                and registry.get_boxel(target_obj_str) is None):
            t_bid = target_info.object_id
            # #P1 step (3): the registered boxel comes from the SAME
            # rendered observation that just found the target — no
            # p.getAABB.  A target found through a sliver can render
            # below DETECTION_MIN_PIXELS; it then stays unregistered
            # this round (loud log) and the next observation localizes
            # it — the pick that usually follows in the SAME plan uses
            # the execution servo's own live re-aim, not this boxel.
            t_det = sense_detections.get(target_obj_str)
            if t_det is None:
                print(f"      [step3-diag] {target_obj_str} found but "
                      f"renders below the detection minimum — OBJECT "
                      f"boxel NOT registered this round (audit #76 "
                      f"hook deferred to the next observation).")
            else:
                target_bd = BoxelData(
                    id=target_obj_str,
                    boxel_type=BoxelType.OBJECT,
                    min_corner=np.array(t_det.est_min),
                    max_corner=np.array(t_det.est_max),
                    object_name=target_obj_str,
                    is_occluder=False,
                    on_surface=(
                        "table"
                        if t_det.est_min[2]
                        <= env.table_surface_height + 0.01
                        else None
                    ),
                    surface_z=env.table_surface_height,
                )
                registry.add_boxel(target_bd)
                boxel_centers[target_obj_str] = target_bd.center
                object_body_ids[target_obj_str] = env.plan_body_id(t_bid)
                boxel_to_pybullet[target_obj_str] = {
                    'name': target_obj_str,
                    'pybullet_id': t_bid,
                    'position': np.array(t_det.est_center),
                }
                if viz is not None:
                    viz.draw_boxel_data(target_bd)
                print(f"      -> registered OBJECT boxel for "
                      f"{target_obj_str} at the render estimate "
                      f"(audit #76, step 3).")

        _register_new_detections()
        _lost = refresh_object_aabbs(
            env, registry, viz, detections=sense_detections,
            render=(sense_depth_m, sense_seg, sense_view, sense_proj),
            check_lost=True)
        if _lost:
            retire_lost_objects(_lost, registry, viz, shadows,
                                shadow_occluder_map, boxel_centers,
                                occluders, belief,
                                render=(sense_depth_m, sense_seg,
                                        sense_view, sense_proj))
        return ActionResult(continue_=True, reason="sense_found_target")

    # #P1 step (3): a contains_nontarget where NO discovered body is
    # localizable in the render (all below DETECTION_MIN_PIXELS) cannot
    # register anything — removing the fragment would erase a volume we
    # just observed to contain SOMETHING, and proceeding would loop.
    # Treat it like a blocked observation: keep the fragment, burn an
    # audit-#21 strike, give up on the fragment after 3 (marked
    # not_here, disclosed).  Practically this needs a pathological
    # sliver view of the discovered body; the bound keeps it finite.
    if sense_outcome == "contains_nontarget":
        _loc_names = [body_id_to_name[b] for b in detected_bodies
                      if b in body_id_to_name
                      and body_id_to_name[b] in sense_detections]

        # #P1 F15(b): before refusing, LOCALIZE FROM WHAT IS THERE.
        # The endpoints this body intercepted prove it has pixels, and
        # those pixels carry depth — they are simply too few to clear
        # DETECTION_MIN_PIXELS, which is a whole-frame confidence gate,
        # not a statement that the body is unlocatable.  Re-run the same
        # unprojection at min_pixels=1 restricted to the intercepting
        # bodies and, because a 1-5 pixel cloud measures far smaller than
        # the object, GROW the estimate to the NOMINAL class box centred
        # on it.  That mirrors the hidden-object prior the streams already
        # use: the box only ever over-estimates, so downstream
        # "could something hide here / does this fit" reasoning stays
        # conservative.  A body with genuinely zero pixels cannot be
        # localized this way and still burns a strike below.
        if not _loc_names and detected_bodies:
            _cand = {b: body_id_to_name[b] for b in detected_bodies
                     if b in body_id_to_name}
            _sliver = detect_objects_from_render(
                sense_seg, _sense_depth_buf, sense_view, sense_proj,
                _cand, env.camera_position, env.table_surface_height,
                min_pixels=1) if _cand else {}
            for _nm, _det in _sliver.items():
                _c = _det.est_center
                _half = np.maximum(
                    (np.asarray(_det.est_max) - np.asarray(_det.est_min)) / 2.0,
                    NOMINAL_HIDDEN_EXTENTS / 2.0)
                _lo = _c - _half
                _hi = _c + _half
                if _lo[2] <= env.table_surface_height + DETECTION_SUPPORT_SNAP:
                    _lo[2] = env.table_surface_height
                    _hi[2] = max(_hi[2],
                                 env.table_surface_height
                                 + float(NOMINAL_HIDDEN_EXTENTS[2]))
                sense_detections[_nm] = ObjectDetection(
                    name=_nm, body_id=_det.body_id,
                    pixel_count=_det.pixel_count,
                    est_min=_lo, est_max=_hi)
                print(f"    [F15] {_nm} renders {_det.pixel_count} px — under "
                      f"the {DETECTION_MIN_PIXELS} px detection minimum, but "
                      f"its pixels localize it: registering a conservative "
                      f"{NOMINAL_HIDDEN_EXTENTS[0] * 100:.0f} cm class box at "
                      f"[{_c[0]:.3f},{_c[1]:.3f},{_c[2]:.3f}] instead of "
                      f"refusing the observation.")
            _loc_names = [body_id_to_name[b] for b in detected_bodies
                          if b in body_id_to_name
                          and body_id_to_name[b] in sense_detections]

        if not _loc_names:
            sid_str = str(shadow_id)
            # #P1 F15(c): its OWN strike budget.  blocked_counts is keyed
            # by shadow id and is also incremented by the still_blocked
            # branch, so before this the two unrelated failure modes
            # shared one budget — the field run retired blue's actual
            # hiding place on 1 blocked strike + 2 unlocalizable ones,
            # three strikes that were never three of the same
            # observation.  A shared "_unlocalizable" key namespace keeps
            # the counters separate without a signature change.
            _ukey = f"{sid_str}::unlocalizable"
            blocked_counts[_ukey] = blocked_counts.get(_ukey, 0) + 1
            print(f"    Shadow {shadow_id} contains something the render "
                  f"cannot localize (below the detection minimum) — "
                  f"keeping the fragment. [attempt "
                  f"{blocked_counts[_ukey]}]")
            # #P1 F15: NAME what was seen.  Before this the refusal was
            # anonymous — three strikes could retire the fragment the
            # target was actually sitting in and the log never said which
            # body caused it.  For each discovery: how many grid endpoints
            # it stood in front of, how many pixels its seg id covers in
            # the whole frame, and why it missed the detection gate.
            _diag = []
            for _b in sorted(detected_bodies):
                _nm = body_id_to_name.get(_b, f"<seg id {_b}>")
                _px = int(np.count_nonzero(sense_seg == _b))
                # Three distinct reasons a discovery is unresolvable, and
                # they must not share a label: a known object under the
                # pixel gate (BELOW_MIN), versus a seg id that is not a
                # scene object at all (F19 caught the debug overlay's
                # phantom bodies here with 1197 px — nothing about a
                # detection minimum applied).
                if _nm in sense_detections:
                    _why = 'localized'
                elif _b in body_id_to_name:
                    _why = 'BELOW_MIN'
                else:
                    _why = 'NOT_A_SCENE_OBJECT'
                _diag.append(
                    f"{_nm}(id={_b}) endpoints={interceptor_counts.get(_b, 0)} "
                    f"seg_px={_px} {_why}")
            print(f"      [F15-diag] discoveries: {'; '.join(_diag)}"
                  f" | detection minimum {DETECTION_MIN_PIXELS} px"
                  f" | localized this render: "
                  f"{sorted(sense_detections)}")
            if blocked_counts[_ukey] >= 3:
                # #P1 F15(c): PARKED, not eliminated.  The observation
                # backing this giveup is "this volume contains something
                # I could not resolve" — evidence of OCCUPANCY, not of
                # the target's absence — so mark_sensed(found=False)
                # would assert something the robot never saw.  It did
                # exactly that in the field run and retired the fragment
                # the target was physically inside.  Parking stops the
                # planner spending more actions here (the episode would
                # otherwise loop) while the belief stays truthful and the
                # run outcome discloses the fragment as unsearched.
                print(f"    ERROR: {shadow_id} unlocalizable-content "
                      f"{blocked_counts[_ukey]} times — parking it "
                      f"UNRESOLVED (not marked empty: the observation "
                      f"says the volume is OCCUPIED, not that the target "
                      f"is absent).  The content stays unmodelled and "
                      f"the fragment stays in the registry.")
                blocked_giveup_shadows.add(sid_str)
                belief.mark_unresolved(sid_str)
            # #P1 F16: this render is still evidence about every OTHER
            # fragment even though it could not settle this one — the
            # exact loop F15 exposed, where repeated senses of one
            # fragment learned nothing while the observation in hand
            # could have cleared others.
            sweep_all_fragments(
                registry=registry, belief=belief, viz=viz, shadows=shadows,
                shadow_occluder_map=shadow_occluder_map,
                boxel_centers=boxel_centers,
                boxel_to_pybullet=boxel_to_pybullet,
                target_pybullet_id=target_pybullet_id, robot_id=robot_id,
                sense_support_ids=sense_support_ids,
                sense_depth_m=sense_depth_m, sense_seg=sense_seg,
                sense_view=sense_view, sense_proj=sense_proj,
                skip_ids={sid_str})
            _register_new_detections()
            _lost = refresh_object_aabbs(
                env, registry, viz, detections=sense_detections,
                render=(sense_depth_m, sense_seg, sense_view,
                        sense_proj),
                check_lost=True)
            if _lost:
                retire_lost_objects(_lost, registry, viz, shadows,
                                    shadow_occluder_map, boxel_centers,
                                    occluders, belief,
                                    render=(sense_depth_m, sense_seg,
                                            sense_view, sense_proj))
            return ActionResult(continue_=False,
                                reason="sense_contains_unlocalizable")

    if sense_outcome in ("clear_but_empty", "contains_nontarget"):
        sid_str = str(shadow_id)
        belief.mark_sensed(sid_str, found=False)

        registry.remove_boxel(sid_str)
        if viz is not None:
            # Drop wireframe + label for the cleared shadow so
            # the GUI doesn't keep the old SHADOW outline alive
            # alongside whatever the next refresh draws.
            # remove_boxel_viz is a no-op on unknown ids.
            viz.remove_boxel_viz(sid_str)
        if sid_str in shadows:
            shadows.remove(sid_str)
        shadow_occluder_map.pop(sid_str, None)
        boxel_centers.pop(sid_str, None)

        # Sanity check: the registry entry and every GUI overlay (wireframe
        # lines + label + phantom AABB body) for this shadow MUST be gone
        # after a successful sense_empty.  A leftover surfaces as the
        # "sensed shadow still painted on the GUI" bug (user-reported).
        # Loud warning here lets us catch the regression without crashing
        # the run; the planner already updated belief so execution can
        # continue, but the GUI is lying to the user.
        if registry.get_boxel(sid_str) is not None:
            print(f"    WARNING: shadow {sid_str} still in registry after "
                  f"sense_empty — viz/planner state will diverge")
        if viz is not None and viz.tracks_boxel(sid_str):
            print(f"    WARNING: shadow {sid_str} GUI overlay still tracked "
                  f"after remove_boxel_viz — wireframe/phantom likely "
                  f"painted at the stale location")

        # Sibling batch-sense (2026-08-21, user-directed): F3's corrected
        # geometry splits one caster's occlusion into several fragments,
        # so a single sense cleared only ITS fragment and the GUI kept
        # showing the caster's other shadows ("shadow still there after
        # sensing" field report).  Re-run the same ray-grid cast on the
        # caster's remaining fragments now and remove every one that is
        # ALSO observably empty — each removal is backed by a real
        # observation, so the belief stays honest.  Fragments that come
        # back blocked / non-empty stay for a planned sense of their
        # own; a surprise found_target here is deliberately left for the
        # next planned sense rather than plumbed through this replan
        # branch.
        caster_id = (shadow_boxel.created_by_boxel_id
                     or shadow_boxel.created_by_object)
        caster_bd = registry.get_boxel(caster_id) if caster_id else None
        if caster_bd is not None and sid_str in getattr(
                caster_bd, "shadow_boxel_ids", []):
            caster_bd.shadow_boxel_ids.remove(sid_str)
        # #P1 F16: sweep EVERY fragment against this render, not just the
        # caster's siblings.  Same observation, same removal criterion —
        # it simply stops discarding evidence the render already has.
        sweep_all_fragments(
            registry=registry, belief=belief, viz=viz, shadows=shadows,
            shadow_occluder_map=shadow_occluder_map,
            boxel_centers=boxel_centers, boxel_to_pybullet=boxel_to_pybullet,
            target_pybullet_id=target_pybullet_id, robot_id=robot_id,
            sense_support_ids=sense_support_ids, sense_depth_m=sense_depth_m,
            sense_seg=sense_seg, sense_view=sense_view,
            sense_proj=sense_proj, skip_ids={sid_str})

        if sense_outcome == "contains_nontarget":
            # Non-target objects discovered inside the shadow.
            # Create OBJECT + SHADOW boxels for each one so the
            # planner knows about them on the next replan.
            discovered_names = [
                body_id_to_name[bid]
                for bid in detected_bodies
                if bid in body_id_to_name
            ]
            print(f"    Shadow {shadow_id} contains non-target "
                  f"object(s): {discovered_names}")
            _capture_freeze(f"replan trigger: {shadow_id} holds non-target "
                            f"{discovered_names}")

            for obj_name in discovered_names:
                obj_info = env.objects.get(obj_name)
                if obj_info is None:
                    continue
                bid = obj_info.object_id
                # #P1 step (3): the discovered object's boxel comes from
                # the SAME rendered observation that discovered it — no
                # p.getAABB.  A body below the detection minimum stays
                # unregistered this round (the guard above already
                # ensured at least one discovery IS localizable).
                det = sense_detections.get(obj_name)
                if det is None:
                    print(f"      [step3-diag] discovered {obj_name} "
                          f"renders below the detection minimum — not "
                          f"registered this round; a later observation "
                          f"localizes it.")
                    continue
                aabb_min = np.array(det.est_min)
                aabb_max = np.array(det.est_max)

                # Discovery may re-trigger for an object_name we
                # already know about (e.g. previous re-sense pass
                # added it; current sense saw it through a second
                # shadow).  Without this cleanup the registry
                # silently overwrites the OBJECT entry but the old
                # wireframe + ALL prior shadow entries (both registry
                # and viz) survive — that's the "two boxels under
                # one name" trace.  Clean both before recreating
                # so only the accurate (live-AABB) entry stays.
                old_obj = registry.get_boxel(obj_name)
                if old_obj is not None:
                    for old_sid in list(old_obj.shadow_boxel_ids):
                        registry.remove_boxel(old_sid)
                        if viz is not None:
                            viz.remove_boxel_viz(old_sid)
                        if old_sid in shadows:
                            shadows.remove(old_sid)
                        shadow_occluder_map.pop(old_sid, None)
                        boxel_centers.pop(old_sid, None)
                        # #P1 F20 follow-up: the belief must forget the
                        # superseded fragment too, or it stays 'unknown'
                        # forever and blocks the all-searched exit.
                        belief.remove_shadow(old_sid)
                    if viz is not None:
                        viz.remove_boxel_viz(obj_name)

                # #P1 F9: strike counter for REDISCOVERIES — this
                # object was already registered (spawn occluder or a
                # previous discovery) and a sense has hit it inside a
                # fragment again.  Mirrors the audit-#21 3-strike
                # sense giveup; see the counter's declaration in
                # test_full_pipeline for the semantics.
                # #P1 F20 follow-up: a body that entered the registry from
                # a whole-workspace observation is being DISCOVERED inside
                # a fragment for the first time here — that is not the
                # relocate-rediscover cycle F9 bounds.  One exemption, then
                # it counts like any other object.
                if (nontarget_rediscovery_counts is not None
                        and old_obj is not None
                        and obj_name not in belief.redetected):
                    nontarget_rediscovery_counts[obj_name] = \
                        nontarget_rediscovery_counts.get(obj_name, 0) + 1
                    print(f"      -> rediscovery "
                          f"{nontarget_rediscovery_counts[obj_name]}/3 "
                          f"for {obj_name} (#P1 F9 strike counter)")
                belief.redetected.discard(obj_name)

                obj_bd = BoxelData(
                    id=obj_name,
                    boxel_type=BoxelType.OBJECT,
                    min_corner=aabb_min,
                    max_corner=aabb_max,
                    object_name=obj_name,
                    is_occluder=False,
                    on_surface=(
                        "table"
                        if aabb_min[2] <= env.table_surface_height + 0.01
                        else None
                    ),
                    surface_z=env.table_surface_height,
                )
                registry.add_boxel(obj_bd)
                boxel_centers[obj_name] = obj_bd.center
                # object_body_ids is the planner-side mapping
                # (audit #46): translate the GUI body id to the
                # plan client's body id before exposing the new
                # OBJECT to BoxelStreams' compute_kin / plan_motion.
                object_body_ids[obj_name] = env.plan_body_id(bid)
                boxel_to_pybullet[obj_name] = {
                    'name': obj_name,
                    'pybullet_id': bid,
                    'position': np.array(det.est_center),
                }
                # Keep the `occluders` snapshot in sync with the
                # registry: compute_shadow_blockers iterates this
                # list to build its body_id → boxel_id map.  If
                # we don't append the freshly discovered object
                # here, any ray that hits it is silently treated
                # as "not a blocker" and the planner thinks the
                # new shadow region is view_clear — leading to
                # (move, sense, pick) plans against shadows whose
                # occluder is still in front, which sense->reveals
                # the same occluder again with zero progress.
                if obj_name not in occluders:
                    occluders.append(obj_name)

                # Compute shadow for this newly visible object.
                # ShadowCalculator now accepts BoxelData directly,
                # so we can pass obj_bd and the OBJECT registry
                # entries with no conversion (audit #35).
                # #P1 F9: after 3 rediscoveries the object's shadows
                # are no longer re-created — the rediscover-relocate
                # cycle it fed is bounded, like the audit-#21 giveup.
                # The OBJECT boxel above still refreshed (census and
                # collision mirroring stay correct); only the
                # occlusion model goes un-rebuilt, so the belief may
                # end incomplete and the episode ends honestly if the
                # target actually hides behind this object.
                if (nontarget_rediscovery_counts is not None
                        and nontarget_rediscovery_counts.get(
                            obj_name, 0) >= 3):
                    print(f"    ERROR: {obj_name} rediscovered "
                          f"{nontarget_rediscovery_counts[obj_name]} "
                          f"times — giving up re-creating its shadows "
                          f"(#P1 F9 strike counter, mirrors audit "
                          f"#21).  Belief may be incomplete for "
                          f"regions it occludes.")
                    _capture_freeze(f"give-up: {obj_name} rediscovered "
                                    f"3x (F9)")
                    shadow_parts = []
                else:
                    other_solids = [
                        bd for bd in registry.boxels.values()
                        if (bd.boxel_type == BoxelType.OBJECT
                            and bd.id != obj_name)
                    ]
                    shadow_parts = \
                        env.shadow_calculator.calculate_shadow_boxel(
                            obj_bd, other_solids)

                if shadow_parts:
                    obj_bd.is_occluder = True
                    table_z = env.table_surface_height
                    for sp in shadow_parts:
                        sp.created_by_boxel_id = obj_name
                        sp.created_by_object = obj_name
                        sp.on_surface = (
                            "table"
                            if sp.min_corner[2] <= table_z + 0.01
                            else None
                        )
                        sp.surface_z = table_z
                        s_id = registry.add_boxel(sp)  # auto-assigns "shadow_NNN"
                        obj_bd.shadow_boxel_ids.append(s_id)
                        shadows.append(s_id)
                        shadow_occluder_map[s_id] = [obj_name]
                        boxel_centers[s_id] = sp.center
                        # #P1 F20 follow-up: the belief must know the
                        # fragment exists, or get_unknown_shadows() never
                        # lists it and the loop can exit "all searched"
                        # with it unsensed.
                        belief.add_shadow(s_id)

                if viz is not None:
                    viz.draw_boxel_data(obj_bd)
                    for s_id in obj_bd.shadow_boxel_ids:
                        s_bd = registry.get_boxel(s_id)
                        if s_bd is not None:
                            viz.draw_boxel_data(s_bd)

                print(f"      -> {obj_name}: object boxel + "
                      f"{len(shadow_parts)} shadow(s)")
        else:
            print(f"    Target NOT in {shadow_id} "
                  f"(ray-cast: view clear but no target hit)")

        # Re-run octree + merge now that the shadow is gone
        # (and possibly new object/shadow boxels were added).
        if viz is not None:
            viz.remove_boxel_viz(sid_str)
        # audit #71 — refresh OBJECT AABBs from the observation BEFORE
        # reboxelize so the free-space carve uses current geometry,
        # not the spawn-time snapshot.  SHADOW boxels intentionally
        # left stale (scope cut).  Lost objects retire BEFORE the
        # carve so free space reclaims their vacated regions.
        _register_new_detections()
        _lost = refresh_object_aabbs(
            env, registry, viz, detections=sense_detections,
            render=(sense_depth_m, sense_seg, sense_view, sense_proj),
            check_lost=True)
        if _lost:
            retire_lost_objects(_lost, registry, viz, shadows,
                                shadow_occluder_map, boxel_centers,
                                occluders, belief,
                                render=(sense_depth_m, sense_seg,
                                        sense_view, sense_proj))
        reboxelize_free_space(
            registry, env, boxel_centers, viz, show_free)

        print(f"    -> REPLANNING with updated belief...")
        return ActionResult(continue_=False, reason=f"sense_{sense_outcome}")

    # Occluder (or robot arm) still blocks the view.
    # Track repeated failures; after 3 attempts, assume
    # the shadow is unreachable and give up on it.
    sid_str = str(shadow_id)
    blocked_counts[sid_str] = blocked_counts.get(sid_str, 0) + 1
    print(f"    View to {shadow_id} still blocked "
          f"({blocked_fraction:.0%} of the worst slice's rays hit "
          f"occluder). [attempt {blocked_counts[sid_str]}]")
    # #P1 partial-reveal shrink (2026-08-21, user-directed): the clear
    # rays of this failed sense still observed part of the fragment
    # empty — shrink it to the blocked sub-region so belief, planner
    # grounding, and the GUI wireframe track what actually remains
    # hidden.
    if blocked_bbox:
        _shrink_shadow_fragment(registry, shadow_boxel,
                                blocked_bbox[0], blocked_bbox[1],
                                viz, boxel_centers)
    if blocked_counts[sid_str] >= 3:
        # #P1 F15(c): PARKED, not eliminated.  This branch's own message
        # always said "Shadow is NOT observed empty" while nonetheless
        # writing not_here — the planner needs the fragment withheld so
        # it stops re-attempting, but the BELIEF must not claim an
        # absence nobody observed.  mark_unresolved gives the planner the
        # same exclusion and keeps the run outcome honest.  Real remedy
        # for the blockage itself is still audit #47 (re-ground blocker
        # atoms after repeated failure).
        print(f"    ERROR: {shadow_id} blocked "
              f"{blocked_counts[sid_str]} times — parking it "
              f"UNRESOLVED so the planner stops re-attempting it.  The "
              f"shadow is NOT observed empty and is not marked as such; "
              f"it stays disclosed as unsearched.  Real remedy: "
              f"re-ground blocker atoms after repeated failure — "
              f"audit #47 (deferred out of scope 2026-05-06).")
        _capture_freeze(f"give-up: {shadow_id} blocked 3x (still-blocked 3/3)")
        blocked_giveup_shadows.add(sid_str)
        belief.mark_unresolved(sid_str)
    else:
        print(f"    -> REPLANNING without marking shadow empty...")
    # #P1 F16: a blocked sense still rendered the whole table — use it on
    # every other fragment instead of discarding the observation.
    sweep_all_fragments(
        registry=registry, belief=belief, viz=viz, shadows=shadows,
        shadow_occluder_map=shadow_occluder_map,
        boxel_centers=boxel_centers, boxel_to_pybullet=boxel_to_pybullet,
        target_pybullet_id=target_pybullet_id, robot_id=robot_id,
        sense_support_ids=sense_support_ids, sense_depth_m=sense_depth_m,
        sense_seg=sense_seg, sense_view=sense_view, sense_proj=sense_proj,
        skip_ids={sid_str})
    _register_new_detections()
    _lost = refresh_object_aabbs(
        env, registry, viz, detections=sense_detections,
        render=(sense_depth_m, sense_seg, sense_view, sense_proj),
        check_lost=True)
    if _lost:
        retire_lost_objects(_lost, registry, viz, shadows,
                            shadow_occluder_map, boxel_centers,
                            occluders, belief,
                            render=(sense_depth_m, sense_seg,
                                    sense_view, sense_proj))
    return ActionResult(continue_=False, reason="sense_still_blocked")
