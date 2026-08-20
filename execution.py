"""
Physical action execution for the Semantic Boxels pipeline.

Extracted from test_full_pipeline.py during the audit #26 refactor.
This module hosts the routines that translate planned PDDL actions
into PyBullet motions, plus the perception/bookkeeping helpers that
run between actions:

  - sense_shadow_raycasting: ray-cast a shadow volume to classify it as
    found_target / clear_but_empty / contains_nontarget / still_blocked.
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
  - handle_sense_action: dispatch-loop wrapper around sense_shadow_raycasting
    that owns the post-sense bookkeeping (belief, registry, viz, occluder
    map, blocked counts).  Returns an ActionResult; see its docstring for
    the break/release contract (audit S-01).

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


def sense_shadow_raycasting(camera_pos, shadow_boxel, target_pybullet_id,
                            occluder_pybullet_ids=None, robot_id=None,
                            support_body_ids=None) -> Tuple[str, float, Set[int]]:
    """
    Sense a shadow region using PyBullet ray-casting from the fixed camera.

    Returns one of four outcomes:
      - found_target: at least one ray hits the target
      - still_blocked: no ray hits target and at least one ray hits occluder
        or robot arm
      - contains_nontarget: view is clear but rays hit non-target dynamic
        objects inside the shadow (e.g. another occluder that drifted in)
      - clear_but_empty: no ray hits any dynamic object

    Args:
        camera_pos: Fixed camera position [x, y, z]
        shadow_boxel: BoxelData for the shadow region to sense
        target_pybullet_id: PyBullet body ID of the target object
        occluder_pybullet_ids: Optional set/list of PyBullet body IDs for ALL
            objects that may block camera view to this shadow.
        robot_id: Optional PyBullet body ID of the robot.
        support_body_ids: Optional frozenset of static body IDs (plane, table)
            to ignore when collecting detected bodies.

    Returns:
        Tuple[str, float, Set[int]]:
          - outcome string
          - blocked_fraction (0 when not blocked)
          - set of non-target, non-occluder dynamic body IDs detected inside
            the shadow (empty for found_target and still_blocked)
    """
    ray_origin = np.array(camera_pos)
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

    # Three z-slices through the shadow volume so a target at any height
    # has a chance of being hit.  +0.04 m on the lowest slice keeps it
    # clear of the shadow base (which sits at the table surface — rays
    # exactly at table_z would terminate on the table before reaching
    # anything inside the shadow); 1/3 and 2/3 fractions space the
    # upper two slices through the remaining volume.
    z_levels = [
        min_c[2] + 0.04,
        min_c[2] + (max_c[2] - min_c[2]) * 0.33,
        min_c[2] + (max_c[2] - min_c[2]) * 0.67,
    ]

    # 7x7 grid per z-slice — finer than compute_shadow_blockers' 5x5
    # because here we need to detect whether the TARGET is visible
    # (precision matters), not just identify which objects block the
    # corridor.
    n = 7
    ray_froms = []
    ray_tos = []
    for z_target in z_levels:
        for xi in np.linspace(min_c[0], max_c[0], n):
            for yi in np.linspace(min_c[1], max_c[1], n):
                ray_froms.append(ray_origin.tolist())
                ray_tos.append([float(xi), float(yi), float(z_target)])

    # rayTestBatch numThreads=0: let Bullet pick max threads (audit #69).
    # Largest single batch on the planner hot path (147 rays per sense).
    # Safe — sense action is sequential w.r.t. stepSimulation.
    results = p.rayTestBatch(ray_froms, ray_tos, numThreads=0)
    occluder_hits = 0
    robot_hits = 0
    detected_bodies: Set[int] = set()
    total_rays = len(results)

    for hit_obj_id, _link, _frac, _pos, _normal in results:
        if hit_obj_id == target_pybullet_id:
            return "found_target", 0.0, set()
        if occluder_pybullet_ids and (hit_obj_id in occluder_pybullet_ids):
            occluder_hits += 1
        elif (robot_id is not None) and (hit_obj_id == robot_id):
            robot_hits += 1
        elif hit_obj_id not in ignore_ids:
            detected_bodies.add(hit_obj_id)

    blocked_total = occluder_hits + robot_hits
    if blocked_total > 0:
        blocked_fraction = blocked_total / total_rays if total_rays > 0 else 0.0
        if robot_hits > 0 and occluder_hits == 0:
            print(f"    NOTE: {robot_hits}/{total_rays} rays blocked by "
                  f"robot arm (not occluder)")
        return "still_blocked", blocked_fraction, set()

    if detected_bodies:
        return "contains_nontarget", 0.0, detected_bodies

    return "clear_but_empty", 0.0, set()


def compute_shadow_blockers(camera_pos, registry, shadow_ids, object_ids, env):
    """
    For each shadow, find ALL object boxels that block the camera's view.

    Casts a coarse ray grid from the camera through each shadow volume.
    Any object whose PyBullet body intercepts at least one ray is recorded
    as a blocker for that shadow.  This replaces the old one-to-one
    shadow_occluder_map that only tracked the creating occluder (audit #78).

    Why not just use the parent relationship?  Because after objects are
    relocated, a DIFFERENT object may now block the camera's view of a
    shadow that was originally created by something else.

    Why we ALSO consult the parent relationship as a fallback: the 5x5
    z-slice ray grid is geometrically incomplete — for shadows that
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

    ray_origin = camera_pos.tolist()
    blockers = {}

    for shadow_id in shadow_ids:
        sb = registry.get_boxel(shadow_id)
        if sb is None:
            continue

        blocker_set = set()
        min_c, max_c = sb.min_corner, sb.max_corner
        # Single Z slice at the shadow midpoint — coarser than
        # sense_shadow_raycasting because we only need to identify
        # WHICH objects block, not whether the target is visible.
        z_mid = (min_c[2] + max_c[2]) / 2.0
        n = 5

        ray_froms = []
        ray_tos = []
        for xi in np.linspace(min_c[0], max_c[0], n):
            for yi in np.linspace(min_c[1], max_c[1], n):
                ray_froms.append(ray_origin)
                ray_tos.append([float(xi), float(yi), float(z_mid)])

        # rayTestBatch numThreads=0: let Bullet pick max threads (audit #69).
        # Safe — registry rebuild is sequential w.r.t. stepSimulation.
        results = p.rayTestBatch(ray_froms, ray_tos, numThreads=0)
        for hit_id, _link, _frac, _pos, _normal in results:
            if hit_id in pybullet_to_boxel:
                blocker_set.add(pybullet_to_boxel[hit_id])

        # Parent-relationship fallback: if raycasting found nothing for
        # this shadow but we know the creating occluder, add it.  The
        # creator is by construction the geometry that cast the shadow,
        # so it remains a valid blocker until either (a) it is moved or
        # (b) the shadow itself is removed.  We re-confirm it is still
        # an OBJECT in the registry to avoid resurrecting stale links.
        if not blocker_set and sb.created_by_boxel_id:
            creator = registry.get_boxel(sb.created_by_boxel_id)
            if creator is not None:
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
            placement; only when ``expected_support_z`` is provided,
            so the emergency-drop path tolerates sideways landings).
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
        # topple (~90°).  Only for callers that predict a support
        # height (place/stack); the emergency-drop path passes
        # expected_support_z=None and may legitimately land a cube on
        # its side — failing THAT would abort the whole run.
        if expected_support_z is not None:
            tilt_ok = cube_tilt_deg <= 20.0
        else:
            tilt_ok = True

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
    retire_shadows_ok: bool = False,
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
        retire_shadows_ok: #P1 F4 — when True (caller gates on "no
            active search": stack goal, or target already found), the
            dropped object's stale cast shadows are retired like the
            place/stack handlers do.  Default False keeps unsensed
            knowledge regions alive during a search.

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

    # #P1 F4 shadow hygiene, emergency-drop edition (caller gates on
    # "no active search" — see the parameter docstring).  Retire BEFORE
    # the blocker recompute below so the rebuilt map excludes the
    # retired ids.
    if retire_shadows_ok:
        caster_id = (held_object_boxel_id
                     if held_object_boxel_id is not None
                     else dropped_name)
        retire_cast_shadows(registry, caster_id, shadows,
                            shadow_occluder_map=planner.shadow_occluder_map
                            if planner.shadow_occluder_map is not None
                            else {},
                            boxel_centers=boxel_centers, viz=viz)

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


def execute_pick(robot_id, env, obj_name, obj_pos, grasp, config, gui
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
    cube_hw = min(aabb_max[0] - aabb_min[0],
                   aabb_max[1] - aabb_min[1]) / 2.0

    _GRASP_MARGIN_FROM_TOP = 0.005  # 5 mm below cube top
    _FINGER_TIP_DEPTH = 0.035
    table_z = env.table_surface_height
    min_contact_z = table_z + _FINGER_TIP_DEPTH
    contact_z = max(cube_top_z - _GRASP_MARGIN_FROM_TOP, min_contact_z)

    contact_ee = np.array([
        obj_pos[0] + grasp.position[0],
        obj_pos[1] + grasp.position[1],
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
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc,
                              seed=config.joint_positions)

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
              f"Opening gripper and replanning.")
        open_gripper(robot_id, gui)
        return None, None
    # #P1 F1(d) aperture plausibility: link identity alone cannot
    # distinguish a pinch from both fingertips STANDING ON the object
    # top (the phantom first pick read both pads "in contact" with the
    # fingers at ~0.000 m).  A genuine pinch parks each finger at the
    # object's half-width (close target is cube_hw − 3 mm; the pads
    # stop at the surface).  6 mm tolerance covers off-centre grasps
    # and the min-vs-actual footprint axis mismatch on non-square
    # objects (≤ 5 mm in the resized scenes).
    finger_pos = [p.getJointState(robot_id, fj)[0] for fj in FINGER_JOINTS]
    aperture_err = max(abs(fp - cube_hw) for fp in finger_pos)
    if aperture_err > 0.006:
        print(f"    ERROR: grip aperture implausible for {obj_name} — "
              f"finger_pos=[{finger_pos[0]:.4f},{finger_pos[1]:.4f}] vs "
              f"cube_hw={cube_hw:.4f} (err={aperture_err * 1000:.1f}mm "
              f"> 6mm; standing-on-top phantom or partial pinch). "
              f"Opening gripper and replanning (#P1 F1).")
        open_gripper(robot_id, gui)
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
                                         expected_support_z=table_z):
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
                                     expected_support_z=verify_support_z):
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


def refresh_object_aabbs(env, registry, viz=None):
    """Refresh every OBJECT boxel's AABB from live PyBullet (audit #71).

    Called at the end of each handle_sense_action outcome branch so the
    next replan reads the registry over current geometry instead of the
    spawn-time AABB.  Closes the OBJECT-side staleness gap left by
    pick/place/stack/settle.  SHADOW boxels are NOT recomputed here —
    accepted thesis gap per user-explicit scope cut; the SHADOW keyed
    to a refreshed OBJECT may now be slightly mis-aligned with the live
    silhouette.  Cost is ~0.1 ms for a 10-object scene.

    Per-object early-out: if the new AABB matches the registry value
    within _aabb_tol (0.1 mm — same FP-noise budget reboxelize uses),
    skip the write AND the viz remove/redraw.  Without this, every
    sense redraws every OBJECT wireframe even when nothing moved.
    """
    _aabb_tol = 1e-4
    for obj_boxel in registry.get_boxels_by_type(BoxelType.OBJECT):
        obj_info = env.objects.get(obj_boxel.id)
        if obj_info is None:
            continue
        aabb_min, aabb_max = p.getAABB(obj_info.object_id)
        new_min = np.array(aabb_min)
        new_max = np.array(aabb_max)
        if (np.allclose(new_min, obj_boxel.min_corner, atol=_aabb_tol) and
                np.allclose(new_max, obj_boxel.max_corner, atol=_aabb_tol)):
            continue
        obj_boxel.min_corner = new_min
        obj_boxel.max_corner = new_max
        if viz is not None and viz.tracks_boxel(obj_boxel.id):
            viz.remove_boxel_viz(obj_boxel.id)
            viz.draw_boxel_data(obj_boxel)


def retire_cast_shadows(registry, caster_boxel_id, shadows,
                        shadow_occluder_map, boxel_centers, viz):
    """#P1 F4: remove the shadow boxels CAST BY a relocated caster.

    Mirror of the sense discovery-cleanup pattern (handle_sense_action's
    contains_nontarget branch): registry entry, GUI wireframe+label,
    shadows list, shadow_occluder_map, and boxel_centers all drop the
    retired ids, and the registry is marked dirty so the next
    reboxelize frees the region for the free-space partition.

    Shadows are otherwise retired ONLY by sense actions, so stack runs
    accumulated every spawn-time shadow forever, in registry AND viz
    (field report stale_shadow_drop.md).  Removal-only — consistent
    with the documented no-shadow-RECOMPUTE scope cut in
    refresh_object_aabbs.

    CALLER MUST GATE THIS on the shadow being irrelevant to an active
    search (goal_kind == 'stack', or the target already found): an
    unsensed shadow of a merely relocated occluder is the knowledge
    frontier the planner still needs to sense — retiring it would make
    a target hidden there structurally unfindable (the F2 verify
    criterion requires those shadows to survive relocation).

    Returns the number of shadows retired.
    """
    bd = registry.get_boxel(caster_boxel_id)
    if bd is None or not getattr(bd, "shadow_boxel_ids", None):
        return 0
    retired = 0
    for old_sid in list(bd.shadow_boxel_ids):
        registry.remove_boxel(old_sid)
        if viz is not None:
            viz.remove_boxel_viz(old_sid)
        if old_sid in shadows:
            shadows.remove(old_sid)
        shadow_occluder_map.pop(old_sid, None)
        boxel_centers.pop(old_sid, None)
        retired += 1
    bd.shadow_boxel_ids = []
    if retired:
        setattr(registry, "_dirty", True)
        print(f"    -> retired {retired} stale shadow(s) cast by "
              f"{caster_boxel_id} (#P1 F4 shadow hygiene)")
    return retired


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

    sense_outcome, blocked_fraction, detected_bodies = sense_shadow_raycasting(
        env.camera_position,
        shadow_boxel,
        target_pybullet_id,
        occluder_pybullet_ids,
        robot_id=robot_id,
        support_body_ids=support_body_ids,
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
            t_min, t_max = p.getAABB(t_bid)
            t_min = np.array(t_min)
            t_max = np.array(t_max)
            target_bd = BoxelData(
                id=target_obj_str,
                boxel_type=BoxelType.OBJECT,
                min_corner=t_min,
                max_corner=t_max,
                object_name=target_obj_str,
                is_occluder=False,
                on_surface=(
                    "table"
                    if t_min[2] <= env.table_surface_height + 0.01
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
                'position': np.array(target_info.position),
            }
            if viz is not None:
                viz.draw_boxel_data(target_bd)
            print(f"      -> registered OBJECT boxel for {target_obj_str} "
                  f"at live AABB (audit #76).")

        refresh_object_aabbs(env, registry, viz)
        return ActionResult(continue_=True, reason="sense_found_target")

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
                aabb_min, aabb_max = p.getAABB(bid)
                aabb_min = np.array(aabb_min)
                aabb_max = np.array(aabb_max)

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
                    'position': np.array(obj_info.position),
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
                other_solids = [
                    bd for bd in registry.boxels.values()
                    if (bd.boxel_type == BoxelType.OBJECT
                        and bd.id != obj_name)
                ]
                shadow_parts = env.shadow_calculator.calculate_shadow_boxel(
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
        # audit #71 — refresh OBJECT AABBs from live PyBullet BEFORE
        # reboxelize so the free-space carve uses current geometry,
        # not the spawn-time snapshot.  SHADOW boxels intentionally
        # left stale (scope cut).
        refresh_object_aabbs(env, registry, viz)
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
          f"({blocked_fraction:.0%} rays hit occluder). "
          f"[attempt {blocked_counts[sid_str]}]")
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
    refresh_object_aabbs(env, registry, viz)
    return ActionResult(continue_=False, reason="sense_still_blocked")
