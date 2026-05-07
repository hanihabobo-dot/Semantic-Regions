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
  - execute_pick / execute_place: arm trajectories with constraint-based
    grasping and geometry-derived contact heights (audit #1, #98).
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

from dataclasses import dataclass
from typing import Optional, Set, Tuple

import numpy as np
import pybullet as p

from boxel_data import BoxelData, BoxelType
from reboxelize import reboxelize_free_space
from streams import RobotConfig
from robot_utils import (END_EFFECTOR_LINK, solve_ik, move_robot_smooth,
                         open_gripper, close_gripper)


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

    results = p.rayTestBatch(ray_froms, ray_tos)
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

        results = p.rayTestBatch(ray_froms, ray_tos)
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


def release_held_object_in_place(
    env,
    robot_id,
    gui,
    grasp_constraint_id,
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
    Open the gripper, remove the grasp constraint, and verify the object
    actually fell/separated from the end-effector.  Retries on failure.

    A drop is considered successful when, after settling:
      • The object's COM is reasonably far from the EE (no longer pinched).
      • The object's linear speed is near zero (came to rest, not floating).

    Failure modes covered:
      • removeConstraint raises (already removed, invalid id).
      • Fingers re-close on the object due to position-control overshoot.
      • Object snags on a finger pad and stays at gripper height.

    Args:
        env: BoxelTestEnv.
        robot_id: PyBullet body ID of the robot.
        gui: Whether GUI is active.
        grasp_constraint_id: Constraint to remove (may be None).
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
    if dropped_name is None or dropped_name not in env.objects:
        # Without a name we can't refresh the registry — but the caller
        # still wants the constraint gone.
        try:
            if grasp_constraint_id is not None:
                p.removeConstraint(grasp_constraint_id)
        except Exception:
            pass
        return True, state_updates

    constraint_removed = False
    drop_ok = False

    for attempt in range(1, max_attempts + 1):
        print(f"  Replanning while holding {dropped_name} — release "
              f"attempt {attempt}/{max_attempts}.")

        # Remove the constraint exactly once; subsequent attempts only
        # retry the gripper-open + settle cycle.
        if not constraint_removed and grasp_constraint_id is not None:
            try:
                p.removeConstraint(grasp_constraint_id)
                constraint_removed = True
            except Exception as exc:
                print(f"    WARNING: removeConstraint failed: {exc}")
                # Treat as "already gone" so subsequent retries can proceed.
                constraint_removed = True

        open_gripper(robot_id, gui)
        # Longer settle on retries so a snagged object has more time to
        # slip free under gravity.
        for _ in range(30 + 30 * (attempt - 1)):
            env.step_simulation()
        env.update_object_positions()

        ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK)
        ee_pos = np.array(ee_state[0])
        obj_pos = np.array(env.objects[dropped_name].position)
        ee_to_obj_dist = float(np.linalg.norm(ee_pos - obj_pos))
        lin_vel, _ = p.getBaseVelocity(held_body_id)
        speed = float(np.linalg.norm(lin_vel))

        # Heuristics:
        # • If the object COM sits >= 8 cm from the EE, fingers can't
        #   still be pinching it (Panda finger length ~5.4 cm).
        # • If it's closer but at rest, it may have landed directly under
        #   the gripper — that's still a successful drop.
        far_enough = ee_to_obj_dist >= 0.08
        at_rest = speed < 0.02
        if far_enough and at_rest:
            drop_ok = True
            print(f"    -> Released {dropped_name} "
                  f"(EE→obj {ee_to_obj_dist*100:.1f} cm, speed "
                  f"{speed*100:.1f} cm/s)")
            break
        print(f"    Drop verification failed: EE→obj {ee_to_obj_dist*100:.1f} cm, "
              f"speed {speed*100:.1f} cm/s — retrying.")

    if not drop_ok:
        return False, state_updates

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
    if lift_joints is None:
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
      close gripper  →  weld via createConstraint with the live
      EE-to-object transform.

    The contact waypoint is computed from the object's actual AABB so
    the Panda's finger pads physically wrap around the object.

    The constraint-based attachment (p.createConstraint) is an accepted
    simulation simplification — see audit #7 part B.

    A small (~5 cm) hardcoded post-pick lift runs after the grasp
    constraint is created — cosmetic only.  See audit #36 /
    THESIS_NOTES.md §19 for the rationale (motion-planning fragility
    workaround); the lift is invisible to the planner because
    ``final_config`` (read after the lift) carries the lifted pose
    forward as the next ``move`` action's plan_motion seed.

    Args:
        robot_id: PyBullet body ID of the robot
        env: BoxelTestEnv instance
        obj_name: Name key in env.objects (e.g. "blue_object", "red_object")
        obj_pos: Current object position [x, y, z] (from PyBullet)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        gui: Whether GUI is active (for step_simulation timing)

    Returns:
        Tuple[int, RobotConfig]: PyBullet constraint ID for the grasp
        attachment, and a RobotConfig representing the robot's actual
        final joint configuration (contact position with object held).
    """
    # --- Contact height from object geometry, not the planning offset --------
    # grasp.position[2] is 0.10 m (the planner reaches that approach
    # height via `move`; execution lowers to contact via solve_ik
    # seeded from `config` so the contact pose stays in the same IK
    # branch — audit #37/#38).  10 cm clearance also keeps the wrist
    # out of the camera→shadow ray paths so a subsequent sense action
    # is not blocked by the arm itself.
    # For execution we need the grasptarget at the object, not above it.
    #
    # panda_grasptarget (link 11) sits at the center of the finger-pad
    # closing area.  Finger pads extend ~3.5 cm below the grasptarget.
    # Ideal contact: grasptarget at the object center so fingers wrap
    # symmetrically.  Floor: finger tips must stay above the table.
    _FINGER_TIP_DEPTH = 0.035
    table_z = env.table_surface_height
    min_contact_z = table_z + _FINGER_TIP_DEPTH
    contact_z = max(obj_pos[2], min_contact_z)

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
    move_robot_smooth(robot_id, contact_joints, gui)
    close_gripper(robot_id, gui)

    # Attach the object to the gripper with a fixed constraint.
    # This is a simulation simplification — real grippers use friction,
    # but constraints prevent physics-engine slip during fast motions.
    #
    # Compute the ACTUAL relative transform between EE and object at this
    # instant rather than using the planned grasp.position offset — position-
    # control lag means the true EE pose differs slightly, and using the
    # planned offset causes a corrective snap impulse (audit #98).
    obj_id = env.objects[obj_name].object_id
    ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK)
    ee_world_pos, ee_world_orn = ee_state[0], ee_state[1]
    obj_world_pos, obj_world_orn = p.getBasePositionAndOrientation(obj_id)
    inv_ee_pos, inv_ee_orn = p.invertTransform(ee_world_pos, ee_world_orn)
    parent_frame_pos, parent_frame_orn = p.multiplyTransforms(
        inv_ee_pos, inv_ee_orn, obj_world_pos, obj_world_orn
    )
    grasp_constraint_id = p.createConstraint(
        robot_id, END_EFFECTOR_LINK, obj_id, -1,
        p.JOINT_FIXED, [0, 0, 0],
        list(parent_frame_pos), [0, 0, 0],
        parentFrameOrientation=list(parent_frame_orn)
    )

    # Hardcoded post-pick lift (audit #36, THESIS_NOTES §19): smaller
    # than place/stack (~5 cm) — cosmetic only for the holding-goal
    # terminate-at-contact view; the next plan_motion already runs in
    # free space because the cube is now attached to the EE.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui, lift_height=0.05)

    # Read the actual joint state — position control may not reach the
    # exact IK target.  Tracking the true state prevents PDDL state
    # drift from compounding across chained actions within a plan
    # (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    final_config = RobotConfig(joint_positions=actual_joints,
                               name="post_pick_contact")
    return grasp_constraint_id, final_config


def execute_place(robot_id, env, obj_name, place_pos, grasp, config,
                  grasp_constraint_id, gui) -> Optional[RobotConfig]:
    """
    Execute place action using the plan's grasp pose.

    Assumes the planned `move` action has already delivered the arm to
    the compute_kin_solution config (boxel.center + grasp.position,
    10 cm above the destination).  This routine only handles the
    final lower-and-release:

      IK (seeded from `config`, audit #37/#38) + lower to release
      height  →  open gripper  →  removeConstraint  →  settle.

    The release height is computed so the held object's bottom rests on
    the table surface, using the live EE-to-object offset from the
    constraint (established at pick time).

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
        grasp_constraint_id: PyBullet constraint ID from execute_pick()
        gui: Whether GUI is active (for step_simulation timing)

    Returns:
        RobotConfig: The robot's actual final joint configuration
        (contact position with the object resting on the table below
        the EE).
    """
    # --- Release height from held-object geometry ----------------------------
    # Query the constraint to find the held body, then compute the EE
    # height that places the object's bottom on the table surface.
    # The live EE-to-object Z offset accounts for whatever grasp offset
    # was established at pick time.
    table_z = env.table_surface_height
    if grasp_constraint_id is not None:
        c_info = p.getConstraintInfo(grasp_constraint_id)
        held_body_id = c_info[2]
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

    move_robot_smooth(robot_id, contact_joints, gui)

    open_gripper(robot_id, gui)

    # Remove the fixed constraint so the object responds to gravity
    # and rests on the table surface.
    if grasp_constraint_id is not None:
        p.removeConstraint(grasp_constraint_id)

    # 30 steps ≈ 0.125 s — let the placed object settle before retreating
    # so it reaches a stable resting pose and doesn't tip over.
    for _ in range(30):
        p.stepSimulation()

    # Hardcoded post-place lift (audit #36, THESIS_NOTES §19): give the
    # next plan_motion ~10 cm of safe headroom over the just-placed cube.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

    # Read actual joint state to prevent drift accumulation (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name="post_place_contact")


def execute_stack(robot_id, env, obj_name, on_obj_name, grasp, config,
                  grasp_constraint_id, gui) -> Optional[RobotConfig]:
    """
    Drop the held object on top of ``on_obj_name`` (audit #30, --goal stack).

    Mirrors :func:`execute_place` in shape but the destination is read
    LIVE from PyBullet rather than derived from a free-space boxel
    centre:

      EE z = on_obj_top_z + held_half_height - ee_to_obj_z

    ``ee_to_obj_z`` is the current EE→object Z offset (queried from the
    grasp constraint's body just like execute_place), so any drift in
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
        grasp_constraint_id: Constraint id from the prior pick.  Required —
            execute_stack queries it to find the held body.
        gui: Whether GUI is active (controls move_robot_smooth pacing).

    Returns:
        RobotConfig at the contact pose after release+settle, or None on
        IK failure (caller replans).
    """
    if on_obj_name not in env.objects:
        print(f"    ERROR: stack support '{on_obj_name}' not in env.objects")
        return None
    if grasp_constraint_id is None:
        print(f"    ERROR: stack {obj_name} on {on_obj_name} called without "
              f"a held object (no grasp constraint).")
        return None

    support_id = env.objects[on_obj_name].object_id
    sup_min, sup_max = p.getAABB(support_id)
    sup_top_z = float(sup_max[2])
    sup_cx = (sup_min[0] + sup_max[0]) / 2.0
    sup_cy = (sup_min[1] + sup_max[1]) / 2.0

    c_info = p.getConstraintInfo(grasp_constraint_id)
    held_body_id = c_info[2]
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

    pc = env.client_id
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc,
                              seed=config.joint_positions)
    if contact_joints is None:
        print(f"    ERROR: IK failed for stack contact of {obj_name} on "
              f"{on_obj_name} - aborting")
        return None

    move_robot_smooth(robot_id, contact_joints, gui)

    open_gripper(robot_id, gui)

    p.removeConstraint(grasp_constraint_id)

    # 60 settle steps (vs 30 for place): a stacked cube on a flat support
    # face needs a touch more time to find equilibrium before we read its
    # final pose into the registry.  Picked empirically — long enough to
    # damp visible micro-bouncing, short enough to keep the run snappy.
    for _ in range(60):
        p.stepSimulation()

    # Hardcoded post-stack lift (audit #36, THESIS_NOTES §19): the EE
    # currently sits on top of the freshly stacked column; lift ~10 cm
    # so the next plan_motion has safe headroom over the column.
    _apply_post_action_lift(robot_id, contact_ee, grasp.orientation,
                            contact_joints, pc, gui)

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
        blocked_giveup_shadows.add(sid_str)
        belief.mark_sensed(sid_str, found=False)
    else:
        print(f"    -> REPLANNING without marking shadow empty...")
    return ActionResult(continue_=False, reason="sense_still_blocked")
