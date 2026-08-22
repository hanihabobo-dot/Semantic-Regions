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

from boxel_data import BoxelData, BoxelType
from perception import (SENSE_MARGINAL_BLOCKED_FRACTION,
                        first_surface_interceptors, sense_ray_slices)
from reboxelize import reboxelize_free_space
from streams import RobotConfig
from robot_utils import (END_EFFECTOR_LINK, FINGER_JOINTS, solve_ik,
                         move_robot_smooth, open_gripper, close_gripper)


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
        Tuple[str, float, Set[int], Optional[Tuple[np.ndarray, np.ndarray]]]:
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
        if hit_obj_id == target_pybullet_id:
            return "found_target", 0.0, set(), None
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
            return "still_blocked", blocked_fraction, set(), (b_min, b_max)
        print(f"    NOTE: tolerating {blocked_total}/{len(ray_tos)} "
              f"marginally hidden endpoints (worst slice "
              f"{blocked_fraction:.0%} <= 5%) — classifying by the "
              f"remaining endpoints")

    if detected_bodies:
        return "contains_nontarget", 0.0, detected_bodies, None

    return "clear_but_empty", 0.0, set(), None


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
    contact check to a 4-signal check.  The earlier check accepted false
    positives: a cube touching the table for one frame while still
    friction-pinned to a finger pad produced "released" with the cube
    still attached to the EE — the PDDL fact (obj_at_boxel ?o ?b) then
    diverged from physical reality and every subsequent plan was
    grounded on a fiction.  Now require ALL of:
      (i)   fingers physically reached max open (≥ 0.038 per finger —
            the #P1 friction-grasp analog of the old "constraint gone"
            probe: with the weld removed, a pad that failed to withdraw
            is the only thing that can still bind the object to the EE),
      (ii)  cube bottom within 2 cm of ``expected_support_z`` (when
            provided; callers that can't predict it — e.g. the
            emergency-drop path — pass None and the gate is skipped),
      (iii) cube COM stationary across an extra 20 settle steps
            (<1 mm lateral drift — catches cubes pinned to a finger
            that move with the arm on the next step),
      (iv)  zero contact between held_body_id and any robot link,
      (v)   cube tilt ≤ 20° (#P1 F2 — a topple-on-release is a failed
            placement; opt-in via ``enforce_tilt``, set by the planned
            place/stack paths INCLUDING tray stacks, while the
            emergency-drop path leaves it off and tolerates sideways
            landings.  Decoupled from ``expected_support_z`` because
            tray stacks skip the height gate but still need the tilt
            gate — review fix 2026-08-20).
    Diagnostic info is logged on every attempt (pass or fail) so a
    future false-positive regression is immediately visible in the run
    log.

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
    print(f"    [#84-diag] pre-release {dropped_name}: "
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

        # (ii) cube bottom near the expected support surface.
        aabb_min, _ = p.getAABB(held_body_id)
        cube_bottom_z = float(aabb_min[2])
        if expected_support_z is not None:
            height_err = cube_bottom_z - expected_support_z
            height_ok = abs(height_err) <= 0.02  # 2 cm tolerance
        else:
            height_err = None
            height_ok = True  # caller didn't request this gate

        # (iii) cube COM stationary across 20 extra settle steps.  A
        # cube pinned to a finger pad moves with the arm; a settled
        # cube doesn't.  Costs ~83 ms at 240 Hz — same order as the
        # existing base_settle_steps.
        pos_before, _ = p.getBasePositionAndOrientation(held_body_id)
        for _ in range(20):
            env.step_simulation()
        pos_after, held_orn = p.getBasePositionAndOrientation(held_body_id)
        lateral_drift = float(np.hypot(pos_after[0] - pos_before[0],
                                        pos_after[1] - pos_before[1]))
        stationary = lateral_drift <= 1e-3  # 1 mm

        # Audit #82: cube tilt at release time.  Anything >5° suggests an
        # off-axis grip from close_gripper — the audit #40 _verify_cube_on
        # z-range check may then pass visually while the cube sits at a
        # non-physical angle.
        held_euler = p.getEulerFromQuaternion(held_orn)
        cube_tilt_deg = max(abs(np.degrees(held_euler[0])),
                             abs(np.degrees(held_euler[1])))
        # #P1 F2(1c): gate on the tilt for PLANNED releases.  A 90°
        # topple-on-release used to pass "verify ok" because the tilt
        # was computed but never checked (field report pick_giveup.md
        # §B3: red_object released lying on its side, verify ok).  20°
        # sits far above genuine landings (≤ ~2°) and far below a
        # topple (~90°).  Opt-in via enforce_tilt: place and stack set
        # it (INCLUDING tray stacks, which skip the height gate); the
        # emergency-drop path leaves it off — a sideways landing there
        # is tolerable and failing it would abort the whole run.
        tilt_ok = (cube_tilt_deg <= 20.0) if enforce_tilt else True

        height_str = (
            f"bottom_z={cube_bottom_z:.4f} "
            f"expected={expected_support_z:.4f} "
            f"err={height_err * 1000:.1f}mm"
            if expected_support_z is not None
            else f"bottom_z={cube_bottom_z:.4f} (no_expected)"
        )
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
                f"non_robot_contacts={sorted(non_robot) or 'none'} "
                f"{height_str} "
                f"lateral_drift={lateral_drift * 1000:.2f}mm "
                f"cube_tilt_deg={cube_tilt_deg:.2f} "
                f"finger_pos=[{finger_pos[0]:.4f},{finger_pos[1]:.4f}]")

        ok = (fingers_open
              and not robot_contacts
              and bool(non_robot)
              and height_ok
              and stationary
              and tilt_ok)
        if ok:
            print(f"    -> Released {dropped_name} (audit #80 verify ok; "
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

    aabb_min, aabb_max = p.getAABB(held_body_id)
    aabb_min = np.array(aabb_min)
    aabb_max = np.array(aabb_max)
    if (held_object_boxel_id is not None
            and registry.get_boxel(held_object_boxel_id) is not None):
        obj_bd = registry.get_boxel(held_object_boxel_id)
        obj_bd.min_corner = aabb_min
        obj_bd.max_corner = aabb_max
        obj_bd.on_surface = (
            "table"
            if aabb_min[2] <= env.table_surface_height + 0.01
            else None
        )
        boxel_centers[held_object_boxel_id] = obj_bd.center
        if held_object_boxel_id in boxel_to_pybullet:
            boxel_to_pybullet[held_object_boxel_id]['position'] = \
                np.array(env.objects[dropped_name].position)
        if viz is not None:
            viz.remove_boxel_viz(held_object_boxel_id)
            viz.draw_boxel_data(obj_bd)

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
    print(f"    -> Dropped {dropped_name} at "
          f"{tuple(round(v, 3) for v in env.objects[dropped_name].position)}")

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
                 _retry: bool = False
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

    The contact waypoint is computed from the object's actual AABB so
    the Panda's finger pads physically wrap around the object.

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
        obj_pos: Current object position [x, y, z] (from PyBullet)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        gui: Whether GUI is active (for step_simulation timing)

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
    # the grip.  Now we measure cube top from getAABB and offset
    # down by a fixed 5 mm so the % grip height is invariant in
    # cube size — small cubes match the previous "clamped to
    # table_z + 0.035" behaviour, large cubes get a proportionally
    # higher grasp.  cube_hw (smaller of XY half-widths) is reused
    # for the close_gripper target below.
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
    aabb_min, aabb_max = p.getAABB(obj_id)
    cube_top_z = float(aabb_max[2])
    x_half = (aabb_max[0] - aabb_min[0]) / 2.0
    y_half = (aabb_max[1] - aabb_min[1]) / 2.0
    cube_hw = min(x_half, y_half)

    _GRASP_MARGIN_FROM_TOP = 0.005  # 5 mm below cube top
    _FINGER_TIP_DEPTH = 0.035
    table_z = env.table_surface_height
    min_contact_z = table_z + _FINGER_TIP_DEPTH
    contact_z = max(cube_top_z - _GRASP_MARGIN_FROM_TOP, min_contact_z)

    # #P1 pick re-aim (2026-08-21, investigation synthesis): the
    # dispatcher's obj_pos can be STALE by the time the descent starts —
    # transit finger sweeps shove objects 10-28 mm between the position
    # read and the pick (GUI field runs 10-53-50 / 10-55-47: 7 of 9
    # picks failed with single-pad grips at exactly that misalignment).
    # Aim the final descent at the object's LIVE pose; the AABB-derived
    # contact_z above is already live.
    obj_pos_live = p.getBasePositionAndOrientation(obj_id)[0]
    reaim_xy = float(np.hypot(obj_pos_live[0] - obj_pos[0],
                              obj_pos_live[1] - obj_pos[1]))
    if reaim_xy > 0.002:
        print(f"    [#P1-diag] pick re-aim {obj_name}: live pose "
              f"{reaim_xy * 1000:.1f}mm from the dispatcher's position")
    contact_ee = np.array([
        obj_pos_live[0] + grasp.position[0],
        obj_pos_live[1] + grasp.position[1],
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
    pregrasp_aperture = min(0.04, max(x_half, y_half) + 0.008)
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
    # during both the align and the descent.  The pinch axis can be
    # either horizontal AABB axis (yaw-less grasp), so the aperture is
    # sized on the LARGER half-extent, +8 mm clearance per finger.

    # settle=True: the contact descent is precision-critical (#P1) —
    # the friction grasp needs lateral centering within the descent
    # clearance, so hold the endpoint until the arm converges.
    move_robot_smooth(robot_id, contact_joints, gui, settle=True)

    # #P1 pick-arrival diagnostic (mirrors the audit-#84 stack diag).
    # With the weld gone, a lateral arrival error beyond the descent
    # clearance is the prime suspect when grip verification below
    # reports a miss — log EE-vs-target and EE-vs-object XY offsets so
    # failed grips are attributable from headless logs.  Print-only:
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

    # Close target = 3 mm INSIDE the cube surface along the finger-
    # closing axis (use the smaller of XY half-widths as a conservative
    # bound since the grasp orientation may yaw the gripper).  The pads
    # stop at the surface; the unreachable target keeps the motors
    # pressing at close_gripper's force budget, and that normal force ×
    # pad friction is the grip — there is no constraint weld any more
    # (#P1, deferred #59).  Floor at 2 mm so a degenerate cube_hw can't
    # drive the target to zero or negative.
    close_gripper(robot_id, gui,
                  target_finger_pos=max(0.002, cube_hw - 0.003))

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
                                config, gui, _retry=True)
        return None, None
    # #P1 F1(d) aperture plausibility: link identity alone cannot
    # distinguish a pinch from both fingertips STANDING ON the object
    # top (the phantom first pick read both pads "in contact" with the
    # fingers at ~0.000 m).  A genuine pinch parks each finger at the
    # object's half-extent ALONG THE PINCH AXIS — which, with the
    # yaw-less grasp, may be either horizontal AABB axis of a
    # non-square footprint (a toppled 4x6 cm box pinched across its
    # 6 cm side is a real grasp at finger_pos 0.03 while min-half is
    # 0.02).  Accept an aperture within 6 mm of EITHER horizontal
    # half-extent; a phantom reads ~0.000-0.005, far below the
    # >= 0.015 m half-extents of every scene object, so the
    # standing-on-top signature is still caught.
    # x_half / y_half hoisted to the AABB read at the top of the
    # function (also sizes the pre-grasp aperture).
    finger_pos = [p.getJointState(robot_id, fj)[0] for fj in FINGER_JOINTS]
    aperture_err = min(
        max(abs(fp - h) for fp in finger_pos)
        for h in (x_half, y_half)
    )
    if aperture_err > 0.006:
        print(f"    ERROR: grip aperture implausible for {obj_name} — "
              f"finger_pos=[{finger_pos[0]:.4f},{finger_pos[1]:.4f}] vs "
              f"half_extents=[{x_half:.4f},{y_half:.4f}] "
              f"(err={aperture_err * 1000:.1f}mm > 6mm; standing-on-top "
              f"phantom or partial pinch). Opening gripper (#P1 F1).")
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
                                config, gui, _retry=True)
        return None, None
    print(f"    Grip verified for {obj_name}: both pads in contact, "
          f"pad_normal_force={grip_nf:.2f}N, "
          f"aperture_err={aperture_err * 1000:.1f}mm")

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


def execute_place(robot_id, env, obj_name, place_pos, grasp, config,
                  held_body_id, gui) -> Optional[RobotConfig]:
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
    if held_body_id is not None:
        # #P1 F1(c): held-contact entry assert — raises EmptyHandError
        # (dedicated dispatcher path) when the object was lost in
        # transport or the hold was phantom all along.
        _assert_held_contact(robot_id, held_body_id, obj_name, gui,
                             action="place")
        held_aabb_min, held_aabb_max = p.getAABB(held_body_id)
        obj_half_height = (held_aabb_max[2] - held_aabb_min[2]) / 2.0

        ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK)
        ee_z = ee_state[0][2]
        obj_cur_z = p.getBasePositionAndOrientation(held_body_id)[0][2]
        ee_to_obj_z = obj_cur_z - ee_z

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
        # audit #80: pass expected support Z so the verify gate can
        # reject cubes pinned mid-air or floating above the table.
        # execute_place IKs the cube to land at table_z + obj_half_height
        # (lines 642-647 above), so the cube's bottom should sit at table_z.
        if not _release_and_verify_drop(env, robot_id, gui,
                                         held_body_id, obj_name,
                                         expected_support_z=table_z,
                                         enforce_tilt=True):
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

    # Hardcoded post-place lift (audit #36, THESIS_NOTES §19): give the
    # next plan_motion ~10 cm of safe headroom over the just-placed cube.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # audit #60 fix (ii) — mirror the placed cube's runtime pose into
    # plan_client so subsequent plan_motion calls see the correct obstacle
    # layout.  sync_to_plan_client only fires at replan boundaries
    # (test_full_pipeline.py:882), so without this the placed cube remains
    # at its pre-place pose in plan_client and plan_motion certifies
    # trajectories through where it actually sits at runtime.
    if held_body_id is not None and held_body_id in env._gui_to_plan:
        plan_body = env._gui_to_plan[held_body_id]
        gui_pos, gui_orn = p.getBasePositionAndOrientation(
            held_body_id, physicsClientId=env.client_id)
        p.resetBasePositionAndOrientation(
            plan_body, gui_pos, gui_orn,
            physicsClientId=env.plan_client_id)

    # Read actual joint state to prevent drift accumulation (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name="post_place_contact")


def execute_stack(robot_id, env, obj_name, on_obj_name, grasp, config,
                  held_body_id, gui) -> Optional[RobotConfig]:
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

    support_id = env.objects[on_obj_name].object_id
    sup_min, sup_max = p.getAABB(support_id)
    sup_top_z = float(sup_max[2])
    sup_cx = (sup_min[0] + sup_max[0]) / 2.0
    sup_cy = (sup_min[1] + sup_max[1]) / 2.0

    held_aabb_min, held_aabb_max = p.getAABB(held_body_id)
    held_half_height = (held_aabb_max[2] - held_aabb_min[2]) / 2.0

    ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK)
    ee_z = ee_state[0][2]
    obj_cur_z = p.getBasePositionAndOrientation(held_body_id)[0][2]
    ee_to_obj_z = obj_cur_z - ee_z

    target_obj_z = sup_top_z + held_half_height
    contact_z = target_obj_z - ee_to_obj_z

    contact_ee = np.array([
        sup_cx + grasp.position[0],
        sup_cy + grasp.position[1],
        contact_z,
    ])

    # Audit #84 pre-lower diag - bracket the stack approach so a cube
    # that ends up on the plane instead of the support surfaces WHICH
    # input (support pose, grasp tilt, EE-obj Z) was wrong.
    held_orn = p.getBasePositionAndOrientation(held_body_id)[1]
    held_euler = p.getEulerFromQuaternion(held_orn)
    held_tilt_deg = max(abs(np.degrees(held_euler[0])),
                         abs(np.degrees(held_euler[1])))
    print(f"    [#84-diag] stack {obj_name} on {on_obj_name}: "
          f"contact_ee=[{contact_ee[0]:.4f},{contact_ee[1]:.4f},"
          f"{contact_ee[2]:.4f}] target_obj_z={target_obj_z:.4f} "
          f"sup_top_z={sup_top_z:.4f} ee_to_obj_z={ee_to_obj_z:.4f} "
          f"held_half_height={held_half_height:.4f} "
          f"sup_aabb=[{sup_min[0]:.4f},{sup_min[1]:.4f},{sup_min[2]:.4f}]"
          f"-[{sup_max[0]:.4f},{sup_max[1]:.4f},{sup_max[2]:.4f}] "
          f"held_aabb=[{held_aabb_min[0]:.4f},{held_aabb_min[1]:.4f},"
          f"{held_aabb_min[2]:.4f}]-[{held_aabb_max[0]:.4f},"
          f"{held_aabb_max[1]:.4f},{held_aabb_max[2]:.4f}] "
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
    verify_support_z = None if support_is_tray else sup_top_z

    if not _release_and_verify_drop(env, robot_id, gui,
                                     held_body_id, obj_name,
                                     base_settle_steps=60,
                                     expected_support_z=verify_support_z,
                                     enforce_tilt=True):
        print(f"    ERROR: drop verification failed for {obj_name} on "
              f"{on_obj_name} — aborting (audit #75/#80)")
        return None

    # Hardcoded post-stack lift (audit #36, THESIS_NOTES §19): the EE
    # currently sits on top of the freshly stacked column; lift ~10 cm
    # so the next plan_motion has safe headroom over the column.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # audit #60 fix (ii) — mirror the stacked cube's runtime pose into
    # plan_client (mirror of execute_place's sync; see that function for
    # rationale).  Without this, plan_motion in subsequent plan_motion
    # calls cannot see the stacked cube at its runtime location and may
    # certify trajectories straight through the new tower.
    if held_body_id in env._gui_to_plan:
        plan_body = env._gui_to_plan[held_body_id]
        gui_pos, gui_orn = p.getBasePositionAndOrientation(
            held_body_id, physicsClientId=env.client_id)
        p.resetBasePositionAndOrientation(
            plan_body, gui_pos, gui_orn,
            physicsClientId=env.plan_client_id)

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


def refresh_object_aabbs(env, registry, viz=None, detections=None):
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
    """
    _aabb_tol = 1e-4
    if detections is None:
        detections, _, _, _ = env.detect_objects()
    stale = []
    for obj_boxel in registry.get_boxels_by_type(BoxelType.OBJECT):
        obj_info = env.objects.get(obj_boxel.id)
        if obj_info is None:
            continue
        det = detections.get(obj_boxel.id)
        if det is None:
            stale.append(obj_boxel.id)
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
        if viz is not None and viz.tracks_boxel(obj_boxel.id):
            viz.remove_boxel_viz(obj_boxel.id)
            viz.draw_boxel_data(obj_boxel)
    if stale:
        print(f"    [perception] {len(stale)} object(s) not visible in "
              f"the refresh render — keeping last estimate: "
              f"{sorted(stale)}")


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
    sense_detections, _, _sense_depth_buf, sense_seg = env.detect_objects()
    sense_depth_m = env._depth_buffer_to_meters(_sense_depth_buf)
    sense_view, sense_proj = env._view_and_projection_matrices()

    (sense_outcome, blocked_fraction, detected_bodies,
     blocked_bbox) = sense_shadow_from_render(
        shadow_boxel,
        target_pybullet_id,
        sense_depth_m, sense_seg, sense_view, sense_proj,
        occluder_pybullet_ids,
        robot_id=robot_id,
        support_body_ids=sense_support_ids,
    )

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

        refresh_object_aabbs(env, registry, viz,
                             detections=sense_detections)
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
        if not _loc_names:
            sid_str = str(shadow_id)
            blocked_counts[sid_str] = blocked_counts.get(sid_str, 0) + 1
            print(f"    Shadow {shadow_id} contains something the render "
                  f"cannot localize (below the detection minimum) — "
                  f"keeping the fragment. [attempt "
                  f"{blocked_counts[sid_str]}]")
            if blocked_counts[sid_str] >= 3:
                print(f"    ERROR: {shadow_id} unlocalizable-content "
                      f"{blocked_counts[sid_str]} times — giving up "
                      f"(mirrors audit #21).  Marked not_here; the "
                      f"content stays unmodelled.")
                blocked_giveup_shadows.add(sid_str)
                belief.mark_sensed(sid_str, found=False)
            refresh_object_aabbs(env, registry, viz,
                                 detections=sense_detections)
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
        if caster_bd is not None:
            for sib_sid in list(getattr(caster_bd, "shadow_boxel_ids", [])):
                sib_bd = registry.get_boxel(sib_sid)
                if sib_bd is None:
                    continue
                sib_occluder_ids = set()
                for blocker_bid in shadow_occluder_map.get(sib_sid, []):
                    if blocker_bid in boxel_to_pybullet:
                        sib_occluder_ids.add(
                            boxel_to_pybullet[blocker_bid]['pybullet_id'])
                sib_outcome, _, _, sib_bbox = sense_shadow_from_render(
                    sib_bd, target_pybullet_id,
                    sense_depth_m, sense_seg, sense_view, sense_proj,
                    sib_occluder_ids, robot_id=robot_id,
                    support_body_ids=sense_support_ids)
                if sib_outcome != "clear_but_empty":
                    # Partial-reveal shrink for a still-blocked sibling:
                    # its clear rays observed part of it empty even
                    # though the fragment as a whole stays.
                    if sib_outcome == "still_blocked" and sib_bbox:
                        _shrink_shadow_fragment(registry, sib_bd,
                                                sib_bbox[0], sib_bbox[1],
                                                viz, boxel_centers)
                    continue
                belief.mark_sensed(sib_sid, found=False)
                registry.remove_boxel(sib_sid)
                if viz is not None:
                    viz.remove_boxel_viz(sib_sid)
                if sib_sid in shadows:
                    shadows.remove(sib_sid)
                shadow_occluder_map.pop(sib_sid, None)
                boxel_centers.pop(sib_sid, None)
                caster_bd.shadow_boxel_ids.remove(sib_sid)
                print(f"    -> sibling fragment {sib_sid} also observed "
                      f"empty — removed (batch-sense)")

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
                    if viz is not None:
                        viz.remove_boxel_viz(obj_name)

                # #P1 F9: strike counter for REDISCOVERIES — this
                # object was already registered (spawn occluder or a
                # previous discovery) and a sense has hit it inside a
                # fragment again.  Mirrors the audit-#21 3-strike
                # sense giveup; see the counter's declaration in
                # test_full_pipeline for the semantics.
                if (nontarget_rediscovery_counts is not None
                        and old_obj is not None):
                    nontarget_rediscovery_counts[obj_name] = \
                        nontarget_rediscovery_counts.get(obj_name, 0) + 1
                    print(f"      -> rediscovery "
                          f"{nontarget_rediscovery_counts[obj_name]}/3 "
                          f"for {obj_name} (#P1 F9 strike counter)")

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
        # left stale (scope cut).
        refresh_object_aabbs(env, registry, viz,
                             detections=sense_detections)
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
        print(f"    ERROR: {shadow_id} blocked "
              f"{blocked_counts[sid_str]} times — giving "
              f"up (audit #21).  Shadow is NOT observed "
              f"empty; marking not_here so the planner "
              f"stops re-attempting it.  Real remedy: "
              f"re-ground blocker atoms after repeated "
              f"failure — audit #47 (deferred out of scope "
              f"2026-05-06).")
        _capture_freeze(f"give-up: {shadow_id} blocked 3x (still-blocked 3/3)")
        blocked_giveup_shadows.add(sid_str)
        belief.mark_sensed(sid_str, found=False)
    else:
        print(f"    -> REPLANNING without marking shadow empty...")
    refresh_object_aabbs(env, registry, viz,
                         detections=sense_detections)
    return ActionResult(continue_=False, reason="sense_still_blocked")
