#!/usr/bin/env python3
"""find_dice executor (audit #120): real motion planning + collision
checking + physics on TAMPURA's Panda, via OUR streams (tampura_bridge/
streams_boxel.py) + robot_utils_boxel primitives.

Replaces the kinematic execution_bridge.execute_faithful_pick (IK pose-set +
teleport).  Every arm motion here is a TRAJECTORY from OUR plan_motion
(collision-checked RRT / linear), replayed with smooth position-control
interpolation (move_robot_smooth) exactly as our pipeline executes a `move`
action -- there is no hand-scripted joint move.  A pick is:

    sample_grasp -> chained FK-verified IK (approach / contact / lift)
    -> plan_motion + follow (transit to approach, then descend to contact)
    -> close the gripper and VERIFY both finger pads actually contact the object
    -> attach with a JOINT_FIXED constraint at the live EE->object transform
    -> plan_motion + follow the lift (object now in the collision model).

The grasp is genuine: if the fingers do not make contact the pick fails honestly
("no_grasp_contact") -- the object is never teleported into the hand.  The fixed
constraint is the standard post-grasp hold of OUR pipeline (execution.execute_pick,
audit #98), added only AFTER contact is verified, and justified on its own merits
-- NOT by appeal to TAMPURA: their find_dice is look-only (it never picks), their
vendored panda_utils.pb_utils.add_fixed_constraint is unused dead code, and where
TAMPURA does hold a grasp it does so KINEMATICALLY (panda_utils Attachment.assign
re-applies set_pose each sim step), not via a constraint.  The executor can
GENUINELY FAIL (no grasp / no IK / no
collision-free path / no contact / no drop) -- the honest behaviour #120 needs.

Two adaptations are needed for TAMPURA's look-only find_dice scene (both flagged
in CODEBASE_AUDIT #120): (1) their cups/dice are STATIC obstacles (mass <= 0) --
to physically pick/relocate one we make it dynamic first, else attaching the arm
to a static body anchors the arm to the world; (2) their hand frames have no
inertial data so PyBullet gives each mass=1 (~5 kg phantom hand) -- we zero those
so position control is physical.

The low-level primitives drive PyBullet's default client (0).  TAMPURA's
find_dice GUI world is connection 0 (it is the first setup_robot), so the
executor asserts streams.physics_client == 0 to fail loudly if that changes.
"""
import os
import sys
import time

import numpy as np
import pybullet as p

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tampura_environments.panda_utils import pb_utils as pbu

from tampura_bridge.robot_utils_boxel import (close_gripper, move_robot_smooth,
                                              open_gripper)
from tampura_bridge.streams_boxel import RobotConfig


def fix_phantom_masses(client, rb, small=0.01):
    """Correct a TAMPURA-URDF artifact: their hand frames (panda_hand / handv /
    tool_tip / camera_frame) carry no inertial data, so PyBullet assigns each
    mass=1 -> ~5 kg of phantom hand.  That makes torque-controlled motion
    unphysical: the heavy hand needs huge forces and won't settle onto IK
    targets.  Zero those phantom masses so the dynamics are physical; arm/finger
    links (which DO have inertial data, mass != 1) are untouched.  Runtime-only
    -- their URDF files are not modified.  Call once after the world is built."""
    fixed = []
    for link in range(client.getNumJoints(rb)):
        if abs(client.getDynamicsInfo(rb, link)[0] - 1.0) < 1e-9:
            client.changeDynamics(rb, link, mass=small)
            fixed.append(link)
    return fixed


def _current_config(client, rb, model, name):
    """The arm's actual joint config (read back after position control)."""
    return RobotConfig(
        joint_positions=np.array([client.getJointState(rb, j)[0]
                                  for j in model.arm_joints]),
        name=name)


def _held_offset(client, rb, ee_link, obj_body):
    """Live EE->object offset in the frame is_config_collision_free expects (it
    places the held body at multiplyTransforms(ee_pose, -offset)).  Used so the
    grasped object is in the right place for the collision checks of the lift /
    transport / go-home trajectories."""
    ee_pos, ee_orn = client.getLinkState(rb, ee_link)[:2]
    obj_pos = client.getBasePositionAndOrientation(obj_body)[0]
    inv = client.invertTransform(ee_pos, ee_orn)
    rel = client.multiplyTransforms(inv[0], inv[1], obj_pos, [0, 0, 0, 1])[0]
    return np.array([-rel[0], -rel[1], -rel[2]])


def _weld(client, rb, ee_link, obj_body):
    """JOINT_FIXED constraint pinning obj_body to the EE at the CURRENT relative
    pose -- the standard post-grasp hold of our execution.execute_pick (audit
    #98).  Computed from the live EE->object transform so there is no snap
    impulse.  Added by execute_pick ONLY after finger-contact has been verified.
    (NOT a TAMPURA mechanism: their vendored add_fixed_constraint is unused dead
    code; their actual grasp hold is kinematic -- Attachment.assign set_pose.)"""
    ep, eo = client.getLinkState(rb, ee_link)[:2]
    op, oo = client.getBasePositionAndOrientation(obj_body)
    inv = client.invertTransform(ep, eo)
    rel_pos, rel_orn = client.multiplyTransforms(inv[0], inv[1], op, oo)
    return client.createConstraint(
        rb, ee_link, obj_body, -1, p.JOINT_FIXED, [0, 0, 0],
        list(rel_pos), [0, 0, 0], parentFrameOrientation=list(rel_orn))


def follow_trajectory(rb, model, traj, gui, steps=30):
    """Replay a planned trajectory's waypoints with smooth interpolation -- the
    same way our pipeline executes a `move` action (test_full_pipeline move
    dispatch): for each waypoint after the start, move_robot_smooth linearly
    interpolates the arm to it over ``steps`` substeps under POSITION_CONTROL
    (force 240 N, the Panda's peak joint torque), stepping physics each tick.
    EVERY target is a PLANNED waypoint from plan_motion -- there is no hand-
    scripted motion.  Streaming the waypoints this way (no decelerate-and-settle
    at each one, no velocity cap) gives continuous motion instead of the discrete
    step-pause-step of a converge-at-each-waypoint follower.

    A streamed move can undershoot the FINAL waypoint by a few mm -- harmless for
    transit, but it makes a descent stop short of a small object's grasp pose
    (the die's fingers would close on air).  So after streaming, briefly hold the
    endpoint target until the arm converges onto it (or a short cap): the planned
    contact / release pose is then actually reached before the gripper acts.
    This settle is near-instant for transit (already on target) -- the only
    visible convergence is the arm pressing the last mm into the grasp pose.  A
    grasped object rides via its JOINT_FIXED constraint."""
    wps = traj.waypoints
    if not wps:
        return
    for wp in wps[1:]:
        move_robot_smooth(rb, wp.joint_positions, gui, steps=steps, robot=model)
    final = np.asarray(wps[-1].joint_positions, dtype=float)
    for _ in range(120):
        cur = np.array([p.getJointState(rb, j)[0] for j in model.arm_joints])
        if np.max(np.abs(cur - final)) < 0.004:
            break
        for idx, j in enumerate(model.arm_joints):
            p.setJointMotorControl2(rb, j, p.POSITION_CONTROL,
                                    targetPosition=float(final[idx]), force=240.0)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 240)


def _plan_follow(streams, rb, model, q_from, q_to, gui):
    """plan_motion(q_from -> q_to) and follow the trajectory.  Returns True on a
    found+executed path, False (honest no-path) otherwise.  q_from/q_to are
    RobotConfigs carrying ignored / held body ids + grasp offset so the planner
    checks collisions correctly (target object ignored at pick, held object
    carried at lift / transport)."""
    mp = list(streams.plan_motion(q_from, q_to))
    if not mp:
        return False
    follow_trajectory(rb, model, mp[0][0], gui)
    return True


def execute_pick(streams, world, model, obj_name, obj_boxel_id, q_start, gui,
                  approach_clearance=0.10, lift_height=0.06):
    """Real reach -> grasp -> lift of obj_name on their robot, via OUR streams.

    Both the transit-to-approach and the descent-to-contact are motion-planned
    and followed; the grasp closes on the object's half-width and is attached
    ONLY after both finger pads are verified in contact; the lift is motion-
    planned with the held object in the collision model.  Returns
    (q_final, constraint_id, status); status "ok", else an honest failure:
    "no_grasp" / "no_approach_ik" / "no_contact_ik" / "no_path" /
    "no_grasp_contact".  (obj_boxel_id is accepted for API symmetry; geometry is
    read live from the object's AABB.)"""
    assert streams.physics_client == 0, (
        "executor drives default client 0; their GUI world must be connection 0 "
        "(got physics_client=%r)" % streams.physics_client)
    client, rb = world.client, world.robot.body
    obj_body = streams.object_body_ids[obj_name]

    # Their find_dice cups/dice are STATIC obstacles (mass <= 0): TAMPURA only
    # looks behind the cups, never picks them.  To physically pick/relocate one
    # we make it dynamic (light, so a real grasp holds it); otherwise attaching
    # the arm to a static body anchors the arm to the world against the lift.
    if client.getDynamicsInfo(obj_body, -1)[0] <= 0:
        client.changeDynamics(obj_body, -1, mass=0.05)

    grasps = list(streams.sample_grasp(obj_name))
    if not grasps:
        return None, None, "no_grasp"
    grasp = grasps[0][0]
    orn = grasp.orientation

    aabb = pbu.get_aabb(obj_body, client=client)
    cx = float((aabb.lower[0] + aabb.upper[0]) / 2)
    cy = float((aabb.lower[1] + aabb.upper[1]) / 2)
    top_z = float(aabb.upper[2])
    # Grasp at the object's LIVE AABB centre so the finger pads straddle it
    # wherever it actually is.
    contact_z = float((aabb.lower[2] + aabb.upper[2]) / 2)

    # Chained, FK-verified IK in ONE branch: approach above the object, contact
    # at the centre, lift straight up.  contact is seeded from approach and lift
    # from contact so the arm stays in one IK branch (no mid-pick swing).
    approach_ee = np.array([cx, cy, top_z + approach_clearance])
    contact_ee = np.array([cx, cy, contact_z])
    q_app = streams.solve_pose_ik(approach_ee, orn, seed=q_start.joint_positions)
    if q_app is None:
        return None, None, "no_approach_ik"
    q_con = streams.solve_pose_ik(contact_ee, orn, seed=q_app)
    if q_con is None:
        return None, None, "no_contact_ik"
    # lift_height must raise the held cup clear of whatever it occludes before
    # the transport (find_dice hides the die UNDER the cup), so it is sized to
    # the scene, not the cosmetic ~0.10 m headroom of our execute_pick: the cup
    # bottom (~table) must clear the die top (~5 cm above the cup bottom here),
    # hence 0.06 m.  A smaller lift leaves the cup overlapping the die and the
    # transport would bulldoze it sideways instead of revealing it in place.
    q_lift = streams.solve_pose_ik(contact_ee + np.array([0.0, 0.0, lift_height]),
                                   orn, seed=q_con)

    ign = frozenset({obj_body})
    q_app_cfg = RobotConfig(joint_positions=q_app, name="q_pick_approach",
                            ignored_body_ids=ign, grasp_ee_offset=grasp.position)
    q_con_cfg = RobotConfig(joint_positions=q_con, name="q_pick_contact",
                            ignored_body_ids=ign, grasp_ee_offset=grasp.position)
    # Transit to the approach, then descend to contact -- BOTH motion-planned.
    if not _plan_follow(streams, rb, model, q_start, q_app_cfg, gui):
        return None, None, "no_path"
    if not _plan_follow(streams, rb, model, q_app_cfg, q_con_cfg, gui):
        return None, None, "no_path"

    # Genuine grasp: boost contact friction, then command a firm full close so
    # the pads clamp onto the object (the object stops them) and register contact
    # -- a gentle close lets a tiny light object (the die) squirt out before
    # contact registers.  Then VERIFY both finger pads actually touch it; no
    # contact -> reopen and fail honestly (the object is never teleported into
    # the hand).  The constraint added next, not the squeeze, holds it in transit.
    client.changeDynamics(obj_body, -1, lateralFriction=4.0)
    for fj in model.finger_joints:
        client.changeDynamics(rb, fj, lateralFriction=4.0)
    close_gripper(rb, gui, target_finger_pos=0.0, force=200.0, robot=model)
    for _ in range(20):
        p.stepSimulation()
    contacts = [len(client.getContactPoints(bodyA=rb, linkIndexA=fj,
                                            bodyB=obj_body))
                for fj in model.finger_joints]
    if not all(c > 0 for c in contacts):
        open_gripper(rb, gui, robot=model)
        return None, None, "no_grasp_contact"

    # Attach: fixed constraint at the live EE->object transform (standard
    # post-grasp hold), added only now that contact is confirmed.
    cid = _weld(client, rb, model.ee_link, obj_body)

    # Lift -- motion-planned, with the now-held object in the collision model.
    if q_lift is not None:
        held = frozenset({obj_body})
        off = _held_offset(client, rb, model.ee_link, obj_body)
        q_con_held = RobotConfig(joint_positions=q_con, name="q_pick_contact_h",
                                 ignored_body_ids=held, held_body_ids=held,
                                 grasp_ee_offset=off)
        q_lift_cfg = RobotConfig(joint_positions=q_lift, name="q_pick_lift",
                                 ignored_body_ids=held, held_body_ids=held,
                                 grasp_ee_offset=off)
        _plan_follow(streams, rb, model, q_con_held, q_lift_cfg, gui)

    return _current_config(client, rb, model, "post_pick"), cid, "ok"


def execute_place(streams, world, model, obj_name, obj_body, cid, place_pos,
                   q_start, gui, table_z, approach_clearance=0.10):
    """Real transport -> lower -> release -> settle -> retract of the HELD
    obj_name to place_pos, via OUR streams on their robot.  Mirrors
    execution.execute_place: release height from the held object's live geometry
    (land its bottom on the table), motion-planned transport + descent with the
    held object in the collision model, gentle release (open + removeConstraint),
    drop verification, motion-planned retract.  Returns (q_final, status);
    status "ok", else an honest failure: "no_approach_ik" / "no_release_ik" /
    "no_path" / "drop_failed".  place_pos is an (x, y) table spot (a known-free
    boxel centre)."""
    client, rb = world.client, world.robot.body
    grasp = list(streams.sample_grasp(obj_name))[0][0]
    orn = grasp.orientation

    # Release height from the held object's live geometry: lower the EE so the
    # object's bottom lands on the table (account for the live EE->object Z).
    haabb = pbu.get_aabb(obj_body, client=client)
    obj_half_h = float(haabb.upper[2] - haabb.lower[2]) / 2.0
    obj_z = client.getBasePositionAndOrientation(obj_body)[0][2]
    ee_z = client.getLinkState(rb, model.ee_link)[0][2]
    ee_to_obj_z = obj_z - ee_z
    release_z = (table_z + obj_half_h) - ee_to_obj_z

    px, py = float(place_pos[0]), float(place_pos[1])
    approach_ee = np.array([px, py, release_z + approach_clearance])
    release_ee = np.array([px, py, release_z])

    # Chained, FK-verified IK in one branch (approach above the spot, release at
    # the spot, retract back up).
    q_app = streams.solve_pose_ik(approach_ee, orn, seed=q_start.joint_positions)
    if q_app is None:
        return None, "no_approach_ik"
    q_rel = streams.solve_pose_ik(release_ee, orn, seed=q_app)
    if q_rel is None:
        return None, "no_release_ik"
    q_ret = streams.solve_pose_ik(approach_ee, orn, seed=q_rel)  # retract back up

    # Transport + descent with the held object in the collision model -- BOTH
    # motion-planned and followed.
    held = frozenset({obj_body})
    off = _held_offset(client, rb, model.ee_link, obj_body)
    q_app_cfg = RobotConfig(joint_positions=q_app, name="q_place_approach",
                            ignored_body_ids=held, held_body_ids=held,
                            grasp_ee_offset=off)
    q_rel_cfg = RobotConfig(joint_positions=q_rel, name="q_place_release",
                            ignored_body_ids=held, held_body_ids=held,
                            grasp_ee_offset=off)
    if not _plan_follow(streams, rb, model, q_start, q_app_cfg, gui):
        return None, "no_path"
    if not _plan_follow(streams, rb, model, q_app_cfg, q_rel_cfg, gui):
        return None, "no_path"

    # Release: open the gripper, remove the constraint, let the object settle
    # under gravity (mirrors execute_place's open + removeConstraint + settle).
    open_gripper(rb, gui, robot=model)
    if cid is not None:
        client.removeConstraint(cid)
    for _ in range(120):
        p.stepSimulation()
        if gui:
            time.sleep(1 / 240)

    # Honest drop verification: the object's bottom must come to rest on the table.
    obj_bottom = float(pbu.get_aabb(obj_body, client=client).lower[2])
    status = "ok" if abs(obj_bottom - table_z) < 0.03 else "drop_failed"

    # Retract straight up for headroom.  Driven DIRECTLY along a linear joint-
    # space path (no plan_motion), mirroring our execute_place post-place lift
    # (_apply_post_action_lift -> move_robot_smooth): at the release pose the
    # just-opened finger pads still graze the placed object, so a plan_motion
    # start-config check rejects the pose -- but this is a short, purely-vertical
    # lift (q_ret is release_xy at +approach_clearance) well within the IK
    # neighbourhood, so it needs no collision-planned path.  Clearing the object
    # here is exactly what lets the next (motion-planned) go_home start from a
    # collision-free pose.  Followed smoothly via follow_trajectory.
    if q_ret is not None:
        q_rel_now = _current_config(client, rb, model, "q_place_at_release")
        q_ret_cfg = RobotConfig(joint_positions=q_ret, name="q_place_retract")
        follow_trajectory(rb, model,
                          streams._linear_trajectory(q_rel_now, q_ret_cfg), gui)
    return _current_config(client, rb, model, "post_place"), status


def execute_go_home(streams, world, model, q_start, gui, held_body=None):
    """Collision-checked return to the rest config (DEFAULT_ARM_POS), via OUR
    streams -- our pipeline's go_home is plan_motion(current -> rest) + follow.
    A held object rides along: held_body_ids repositions it (at its live EE-frame
    offset) for the path collision checks, and its JOINT_FIXED constraint
    physically carries it during the follow.  Returns (q_final, status); status
    "ok", else honest "no_path"."""
    client, rb = world.client, world.robot.body
    held = frozenset({held_body}) if held_body is not None else frozenset()
    off = (_held_offset(client, rb, model.ee_link, held_body)
           if held_body is not None else None)
    q0 = RobotConfig(joint_positions=q_start.joint_positions, name="q_prehome",
                     ignored_body_ids=held, held_body_ids=held,
                     grasp_ee_offset=off)
    home = RobotConfig(joint_positions=np.array(model.rest_poses), name="q_home",
                       ignored_body_ids=held, held_body_ids=held,
                       grasp_ee_offset=off)
    if not _plan_follow(streams, rb, model, q0, home, gui):
        # Return the (unchanged) live config rather than None so callers never
        # poison their threaded q_current; status tells them it did not move.
        return _current_config(client, rb, model, "post_home"), "no_path"
    return _current_config(client, rb, model, "post_home"), "ok"


def _main():
    import argparse
    import random

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 -- registers the find_dice env
    from tampura_bridge._streams_smoke import build_streams
    from tampura_bridge.boxelize import capture, suppress_tampura_visibility_voxels

    pr = argparse.ArgumentParser(description="audit #120: pick on their Panda via our streams")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int, default=0)
    pr.add_argument("--vis", type=int, default=1)
    pr.add_argument("--save-dir", default="/tmp/boxel_pick")
    pr.add_argument("--out", default=os.path.join(
        _REPO, "tampura_bridge", "captures", "pick_place_streams.png"))
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None and k != "out"}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])

    suppress_tampura_visibility_voxels()  # no blue POMDP voxel grid in the GUI
    env = tconfig.get_env(config["task"])(config=config)
    env.initialize()
    world = env.world

    adapter, registry, model, streams, visible = build_streams(world)
    fixed = fix_phantom_masses(world.client, world.robot.body)
    print("zeroed phantom hand-frame masses on links:", fixed)
    cup = next(b for b in registry.get_object_boxels()
               if b.object_name and b.object_name.startswith("cup"))
    obj_body = streams.object_body_ids[cup.object_name]
    z0 = world.client.getBasePositionAndOrientation(obj_body)[0][2]

    q_final, cid, status = execute_pick(
        streams, world, model, cup.object_name, cup.id,
        streams.home_config, gui=bool(args.vis))
    z1 = world.client.getBasePositionAndOrientation(obj_body)[0][2]
    print("=== pick (streams) on their Panda ===")
    ee_z = world.client.getLinkState(world.robot.body, model.ee_link)[0][2]
    print("cup:", cup.object_name, " status:", status, " constraint:", cid)
    print("cup z: %.4f -> %.4f  (lifted %+.4f)  final EE_z: %.4f"
          % (z0, z1, z1 - z0, ee_z))

    if status == "ok":
        cen = adapter.camera_target
        frees = registry.get_free_space_boxels()
        place_b = max(frees, key=lambda f: (f.center[0] - cen[0]) ** 2
                      + (f.center[1] - cen[1]) ** 2)
        place_xy = (float(place_b.center[0]), float(place_b.center[1]))
        q_after, pstatus = execute_place(
            streams, world, model, cup.object_name, obj_body, cid, place_xy,
            q_final, gui=bool(args.vis), table_z=adapter.table_surface_height)
        z2 = world.client.getBasePositionAndOrientation(obj_body)[0][2]
        print("=== place (streams) on their Panda ===")
        print("place_xy:", tuple(round(v, 3) for v in place_xy),
              " status:", pstatus)
        print("cup z: %.4f (held) -> %.4f (placed)" % (z1, z2))

        qh, hstatus = execute_go_home(streams, world, model, q_after,
                                      gui=bool(args.vis))
        print("=== go_home (streams) ===  status:", hstatus)

    cen = adapter.camera_target
    saved = capture(world.client, args.out,
                    [float(cen[0]) + 0.5, float(cen[1]) - 0.6, float(cen[2]) + 0.4],
                    [float(cen[0]), float(cen[1]), float(cen[2])])
    print("capture ->", saved)


if __name__ == "__main__":
    _main()
