#!/usr/bin/env python3
"""Faithful find_dice executor (audit #120): real motion planning + collision
checking + physics on TAMPURA's Panda, via OUR streams (tampura_bridge/
streams_boxel.py) + robot_utils_boxel primitives.

Replaces the kinematic execution_bridge.execute_faithful_pick (IK pose-set +
rigid weld + teleport).  Here a pick is: sample_grasp -> solve_pose_ik
(FK-verified IK) -> plan_motion (collision-checked RRT) -> follow the path with
stepSimulation -> lower to contact -> close + weld -> settle -> lift.  It can
GENUINELY FAIL (no grasp / no IK / no collision-free path) -- the honest
behaviour #120 requires.

Two adaptations are needed for TAMPURA's look-only find_dice scene (both flagged
in CODEBASE_AUDIT #120): (1) their cups/dice are STATIC obstacles (mass <= 0) --
to physically pick/relocate one we make it dynamic first, else welding the arm
to a static body anchors the arm to the world; (2) their hand frames have no
inertial data so PyBullet gives each mass=1 (~5 kg phantom hand) -- we zero
those so position control is physical.

The low-level move/gripper primitives drive PyBullet's default client (0).
TAMPURA's find_dice GUI world is connection 0 (it is the first setup_robot), so
the executor asserts streams.physics_client == 0 to fail loudly if that ever
changes.
"""
import os
import sys

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


def _weld(client, rb, ee_link, obj_body):
    """JOINT_FIXED constraint pinning obj_body to the EE at the CURRENT relative
    pose (no snap impulse -- mirrors execution.execute_pick, audit #98)."""
    ep, eo = client.getLinkState(rb, ee_link)[:2]
    op, oo = client.getBasePositionAndOrientation(obj_body)
    inv = client.invertTransform(ep, eo)
    rel_pos, rel_orn = client.multiplyTransforms(inv[0], inv[1], op, oo)
    return client.createConstraint(
        rb, ee_link, obj_body, -1, p.JOINT_FIXED, [0, 0, 0],
        list(rel_pos), [0, 0, 0], parentFrameOrientation=list(rel_orn))


def follow_trajectory(rb, model, traj, gui, steps_per_wp=10):
    """Drive the arm through a planned trajectory's waypoints with physics
    stepping.  A grasped object rides via its JOINT_FIXED constraint."""
    for wp in traj.waypoints:
        move_robot_smooth(rb, wp.joint_positions, gui,
                          steps=steps_per_wp, robot=model)


def _drive_to(rb, model, q, gui, force=240.0, tol=0.005, max_settle=600):
    """Position-control the arm to config q: command the full target every step
    until the joints converge within `tol` (rad) or max_settle steps.

    A bare move_robot_smooth only ramps the target over a few steps and never
    holds it, so the arm is left mid-motion and never settles onto the IK target
    (worse on their robot until fix_phantom_masses lightens the hand).  Holding
    to convergence makes the contact / lift poses physical.

    Force is the Panda's ~240 N datasheet peak joint torque (== move_robot_smooth,
    robot_utils_boxel).  Earlier this used 1500 N to overpower the ~5 kg phantom
    hand; with fix_phantom_masses zeroing those frames the physical 240 N now
    converges, and the lower force no longer masks control bugs (audit #120
    re-exam)."""
    import time
    qa = np.asarray(q, dtype=float)
    for _ in range(max_settle):
        cur = np.array([p.getJointState(rb, j)[0] for j in model.arm_joints])
        if np.max(np.abs(cur - qa)) < tol:
            break
        for idx, j in enumerate(model.arm_joints):
            p.setJointMotorControl2(rb, j, p.POSITION_CONTROL,
                                    targetPosition=float(qa[idx]), force=force)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 240)


def faithful_pick(streams, world, model, obj_name, obj_boxel_id, q_start, gui,
                  grasp_finger_pos=None, approach_clearance=0.10,
                  lift_height=0.20, table_z=None):
    """Real reach -> grasp -> lift of obj_name on their robot, via OUR streams.

    sample_grasp -> solve_pose_ik (approach / contact / lift, all solved UP
    FRONT) -> plan_motion (collision-checked path) -> follow -> contact ->
    close + weld -> settle -> lift.  All IK is solved before any physics so the
    post-grasp moves never resetJointState-jitter the welded arm (which
    corrupts the grasp).  Returns (q_final, constraint_id, status); status
    "ok", else an honest failure: "no_grasp" / "no_approach_ik" /
    "no_contact_ik" / "no_path".  (obj_boxel_id is accepted for API symmetry;
    geometry is read live from the object's AABB.)"""
    assert streams.physics_client == 0, (
        "executor drives default client 0; their GUI world must be connection 0 "
        "(got physics_client=%r)" % streams.physics_client)
    client, rb = world.client, world.robot.body
    obj_body = streams.object_body_ids[obj_name]

    # Their find_dice cups/dice are STATIC obstacles (mass <= 0): TAMPURA only
    # looks behind the cups, never picks them.  To physically relocate / pick an
    # object we make it dynamic first -- otherwise welding the arm to a static
    # body anchors the arm to the world and locks it against the lift (#120).
    if client.getDynamicsInfo(obj_body, -1)[0] <= 0:
        client.changeDynamics(obj_body, -1, mass=0.1)

    grasps = list(streams.sample_grasp(obj_name))
    if not grasps:
        return None, None, "no_grasp"
    grasp = grasps[0][0]
    orn = grasp.orientation

    aabb = pbu.get_aabb(obj_body, client=client)
    cx = float((aabb.lower[0] + aabb.upper[0]) / 2)
    cy = float((aabb.lower[1] + aabb.upper[1]) / 2)
    top_z = float(aabb.upper[2])
    # Close target = object half-width along the finger-closing axis (smaller of
    # the XY half-widths) so the pads settle ON the surface under the gentle 10 N
    # budget instead of driving INTO it -- mirrors execution.execute_pick's
    # max(0.005, cube_hw) (audit #81 anti-smash).  A fixed deep target (the old
    # 0.015) pushed the pads inside the cup wall and kept the motor grinding
    # against the contact stop.  An explicit grasp_finger_pos still overrides.
    obj_hw = min(aabb.upper[0] - aabb.lower[0],
                 aabb.upper[1] - aabb.lower[1]) / 2.0
    finger_target = (grasp_finger_pos if grasp_finger_pos is not None
                     else max(0.005, obj_hw))

    # All IK up front (before physics): a post-grasp solve_pose_ik would
    # resetJointState-jitter the arm while welded and corrupt the grasp.
    # Chain the solves so the whole pick stays in ONE IK branch -- approach
    # seeded from the start config, contact from approach, lift from contact
    # (mirrors execution.execute_pick's seeded contact IK, audit #37/#38).
    # Unchained, each pose lands in an independent min-FK-error branch and the
    # base joint swings ~144deg between approach and contact for a 10 cm descent
    # -- the non-physical motion the #120 re-exam caught.
    contact_z = top_z - 0.005
    if table_z is not None:
        # Don't drive the finger tips (~3.5 cm below grasptarget) into the table
        # when picking a SHORT object (e.g. the die) -- mirrors execute_pick's
        # min_contact_z = table_z + 0.035 floor (audit #81).
        contact_z = max(contact_z, table_z + 0.035)
    approach_ee = np.array([cx, cy, top_z + approach_clearance])
    contact_ee = np.array([cx, cy, contact_z])
    q_app = streams.solve_pose_ik(approach_ee, orn, seed=q_start.joint_positions)
    if q_app is None:
        return None, None, "no_approach_ik"
    q_con = streams.solve_pose_ik(contact_ee, orn, seed=q_app)
    if q_con is None:
        return None, None, "no_contact_ik"
    q_lift = streams.solve_pose_ik(contact_ee + np.array([0.0, 0.0, lift_height]),
                                   orn, seed=q_con)

    q_app_cfg = RobotConfig(joint_positions=q_app, name="q_pick_approach",
                            ignored_body_ids=frozenset({obj_body}),
                            grasp_ee_offset=grasp.position)
    mp = list(streams.plan_motion(q_start, q_app_cfg))
    if not mp:
        return None, None, "no_path"

    # Reach (collision-checked path) -> contact -> grasp -> settle -> lift.
    follow_trajectory(rb, model, mp[0][0], gui)
    _drive_to(rb, model, q_app, gui)
    _drive_to(rb, model, q_con, gui)
    close_gripper(rb, gui, target_finger_pos=finger_target, robot=model)
    cid = _weld(client, rb, model.ee_link, obj_body)
    for _ in range(20):                       # let the weld settle before lifting
        p.stepSimulation()
    if q_lift is not None:
        _drive_to(rb, model, q_lift, gui)
    return _current_config(client, rb, model, "post_pick"), cid, "ok"


def faithful_place(streams, world, model, obj_name, obj_body, cid, place_pos,
                   q_start, gui, table_z, approach_clearance=0.10):
    """Real transport -> lower -> release -> settle -> retract of the HELD
    obj_name to place_pos, via OUR streams on their robot.  Mirrors
    execution.execute_place: release height from the held object's live
    geometry (land its bottom on the table), collision-checked transport with
    the held object attached, gentle release, drop verification.  All IK is
    chained (approach seeded from start, release from approach, retract from
    release) and solved UP FRONT so the welded arm never resetJointState-jitters
    mid-transport.  Returns (q_final, status); status "ok", else an honest
    failure: "no_approach_ik" / "no_release_ik" / "no_path" / "drop_failed".
    place_pos is an (x, y) table spot (a known-free boxel centre)."""
    import time
    client, rb = world.client, world.robot.body
    grasp = list(streams.sample_grasp(obj_name))[0][0]
    orn = grasp.orientation

    # Release height from the held object's live geometry (mirrors
    # execute_place): lower the EE so the object's bottom lands on the table.
    haabb = pbu.get_aabb(obj_body, client=client)
    obj_half_h = float(haabb.upper[2] - haabb.lower[2]) / 2.0
    obj_z = client.getBasePositionAndOrientation(obj_body)[0][2]
    ee_z = client.getLinkState(rb, model.ee_link)[0][2]
    ee_to_obj_z = obj_z - ee_z
    release_z = (table_z + obj_half_h) - ee_to_obj_z

    px, py = float(place_pos[0]), float(place_pos[1])
    approach_ee = np.array([px, py, release_z + approach_clearance])
    release_ee = np.array([px, py, release_z])

    # All IK up front, chained -> one branch (see faithful_pick).
    q_app = streams.solve_pose_ik(approach_ee, orn, seed=q_start.joint_positions)
    if q_app is None:
        return None, "no_approach_ik"
    q_rel = streams.solve_pose_ik(release_ee, orn, seed=q_app)
    if q_rel is None:
        return None, "no_release_ik"
    q_ret = streams.solve_pose_ik(approach_ee, orn, seed=q_rel)  # retract back up

    # Collision-checked transport of the HELD object to the approach pose
    # (held_body_ids -> the object is repositioned along the path and checked
    # for environment collisions; grasp_ee_offset places it below the EE).
    q_app_cfg = RobotConfig(joint_positions=q_app, name="q_place_approach",
                            ignored_body_ids=frozenset({obj_body}),
                            held_body_ids=frozenset({obj_body}),
                            grasp_ee_offset=grasp.position)
    mp = list(streams.plan_motion(q_start, q_app_cfg))
    if not mp:
        return None, "no_path"

    # Transport -> approach -> lower to release.
    follow_trajectory(rb, model, mp[0][0], gui)
    _drive_to(rb, model, q_app, gui)
    _drive_to(rb, model, q_rel, gui)

    # Release: open the gripper, remove the weld, let the object settle
    # (mirrors execute_place's open + removeConstraint + settle).
    open_gripper(rb, gui, robot=model)
    client.removeConstraint(cid)
    for _ in range(60):
        p.stepSimulation()
        if gui:
            time.sleep(1 / 240)

    # Honest drop verification: the object's bottom must rest on the table.
    obj_bottom = float(pbu.get_aabb(obj_body, client=client).lower[2])
    status = "ok" if abs(obj_bottom - table_z) < 0.02 else "drop_failed"

    # Retract straight up for headroom (post-place lift).
    if q_ret is not None:
        _drive_to(rb, model, q_ret, gui)
    return _current_config(client, rb, model, "post_place"), status


def faithful_go_home(streams, world, model, q_start, gui, held_body=None):
    """Collision-checked return to the rest config (DEFAULT_ARM_POS), via OUR
    streams -- our pipeline's go_home is plan_motion(current -> rest) + follow.
    A held object rides along: held_body_ids repositions it (at its live EE-frame
    offset) for the path collision checks, and the JOINT_FIXED weld physically
    carries it during the follow.  Returns (q_final, status); status "ok", else
    honest "no_path"."""
    client, rb = world.client, world.robot.body
    held = frozenset({held_body}) if held_body is not None else frozenset()
    held_offset = None
    if held_body is not None:
        # Live EE->object offset in the EE frame, in the convention
        # is_config_collision_free expects (it places the held body at
        # multiplyTransforms(ee, -offset)); keeps die-in-hand checks exact.
        ee_pos, ee_orn = client.getLinkState(rb, model.ee_link)[:2]
        obj_pos = client.getBasePositionAndOrientation(held_body)[0]
        inv = client.invertTransform(ee_pos, ee_orn)
        rel = client.multiplyTransforms(inv[0], inv[1], obj_pos, [0, 0, 0, 1])[0]
        held_offset = np.array([-rel[0], -rel[1], -rel[2]])
    q0 = RobotConfig(joint_positions=q_start.joint_positions, name="q_prehome",
                     ignored_body_ids=held, held_body_ids=held,
                     grasp_ee_offset=held_offset)
    home = RobotConfig(joint_positions=np.array(model.rest_poses), name="q_home",
                       ignored_body_ids=held, held_body_ids=held,
                       grasp_ee_offset=held_offset)
    mp = list(streams.plan_motion(q0, home))
    if not mp:
        return None, "no_path"
    follow_trajectory(rb, model, mp[0][0], gui)
    return _current_config(client, rb, model, "post_home"), "ok"


def _main():
    import argparse
    import random

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 -- registers the find_dice env
    from tampura_bridge._streams_smoke import build_streams
    from tampura_bridge.boxelize import capture

    pr = argparse.ArgumentParser(description="audit #120: faithful pick on their Panda")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int, default=0)
    pr.add_argument("--vis", type=int, default=1)
    pr.add_argument("--save-dir", default="/tmp/boxel_faithful_pick")
    pr.add_argument("--out", default=os.path.join(
        _REPO, "tampura_bridge", "captures", "faithful_pick_place_streams.png"))
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None and k != "out"}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])

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

    q_final, cid, status = faithful_pick(
        streams, world, model, cup.object_name, cup.id,
        streams.home_config, gui=bool(args.vis))
    z1 = world.client.getBasePositionAndOrientation(obj_body)[0][2]
    print("=== faithful pick (streams) on their Panda ===")
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
        q_after, pstatus = faithful_place(
            streams, world, model, cup.object_name, obj_body, cid, place_xy,
            q_final, gui=bool(args.vis), table_z=adapter.table_surface_height)
        z2 = world.client.getBasePositionAndOrientation(obj_body)[0][2]
        print("=== faithful place (streams) on their Panda ===")
        print("place_xy:", tuple(round(v, 3) for v in place_xy),
              " status:", pstatus)
        print("cup z: %.4f (held) -> %.4f (placed)" % (z1, z2))

        qh, hstatus = faithful_go_home(streams, world, model, q_after,
                                       gui=bool(args.vis))
        print("=== faithful go_home (streams) ===  status:", hstatus)

    cen = adapter.camera_target
    saved = capture(world.client, args.out,
                    [float(cen[0]) + 0.5, float(cen[1]) - 0.6, float(cen[2]) + 0.4],
                    [float(cen[0]), float(cen[1]), float(cen[2])])
    print("capture ->", saved)


if __name__ == "__main__":
    _main()
