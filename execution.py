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

The orchestration loop in test_full_pipeline.py composes these — it owns
the BeliefState, the registry, and the high-level decision logic, while
this module owns the geometry/physics primitives.
"""

from typing import Optional, Set, Tuple

import numpy as np
import pybullet as p

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

    z_levels = [
        min_c[2] + 0.04,
        min_c[2] + (max_c[2] - min_c[2]) * 0.33,
        min_c[2] + (max_c[2] - min_c[2]) * 0.67,
    ]

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


def execute_pick(robot_id, env, obj_name, obj_pos, grasp, config, gui
                 ) -> Tuple[Optional[int], Optional[RobotConfig]]:
    """
    Execute pick action using the plan's grasp pose.

    Assumes the planned `move` action has already delivered the arm to
    the compute_kin_solution config (boxel.center + grasp.position,
    2 cm above the object after audit #37/#38).  This routine only
    handles the final lower-and-grasp:

      IK (seeded from `config`) + lower to contact  →  close gripper
      →  weld via createConstraint with the live EE-to-object transform.

    The contact waypoint is computed from the object's actual AABB so
    the Panda's finger pads physically wrap around the object.

    The constraint-based attachment (p.createConstraint) is an accepted
    simulation simplification — see audit #7 part B.

    Lifting after the grasp is intentionally NOT done here (refactor
    step 1).  The pick ends at the contact configuration with the
    object welded to the EE; any subsequent `move` action's plan-motion
    trajectory will lift the arm naturally through free space.  This
    keeps execution one-to-one with PDDL actions — no hidden arm
    motion that the planner does not see.

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
    # grasp.position[2] is 0.02 m (audit #37/#38: a thin clearance above
    # the object centre; the planner reaches it via `move`, execution
    # lowers the remaining 2 cm seeded from `config`).
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
    # grasp.position (now 2 cm above object, audit #37/#38).  We seed
    # the contact-pose IK with `config.joint_positions` so the solver
    # stays in the same IK branch the planner already validated; the
    # contact pose is just 2 cm below `config`, so a small in-branch
    # joint step suffices.
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

    # No lift here (refactor step 1).  The arm stays at the contact
    # config holding the object; the next planned `move` action will
    # lift via plan_motion's collision-free trajectory.  Read the actual
    # joint state — position control may not reach the exact IK target.
    # Tracking the true state prevents PDDL state drift from compounding
    # across chained actions within a plan (audit #86).
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
    2 cm above the destination after audit #37/#38).  This routine
    only handles the final lower-and-release:

      IK (seeded from `config`) + lower to release height  →
      open gripper  →  removeConstraint  →  settle.

    The release height is computed so the held object's bottom rests on
    the table surface, using the live EE-to-object offset from the
    constraint (established at pick time).

    Retreating after the release is intentionally NOT done here
    (refactor step 1, mirror of execute_pick): the next planned `move`
    action lifts via plan-motion's collision-free trajectory.

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
    # grasp.position (now 2 cm above destination, audit #37/#38).  We
    # seed the contact-pose IK with `config.joint_positions` so the
    # solver stays in the same IK branch the planner already validated.
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

    The contact-pose IK is seeded with the planner's ``config`` (audit
    #37/#38) so the solver stays in the same IK branch the planner
    already validated — the lower is just ~2 cm in joint space.

    Args:
        robot_id: PyBullet body ID of the robot.
        env: BoxelTestEnv (for env.objects lookup and client_id).
        obj_name: Held object's name (logging).
        on_obj_name: Support object's name (must be in env.objects).
        grasp: Grasp from the planner (provides EE→object offset).
        config: RobotConfig from the planner's compute_stack_kin (the
            approach pose 2 cm above the support top).  Used as the
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

    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name=f"post_stack_{obj_name}_on_{on_obj_name}")


# compute_push_displacement() removed (#53): push superseded by pick-and-place.
# The function teleported occluders via p.resetBasePositionAndOrientation without
# involving the robot arm. Occluder relocation now uses pick â move â place.
