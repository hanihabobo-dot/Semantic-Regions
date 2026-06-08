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

from tampura_bridge.robot_utils_boxel import close_gripper, move_robot_smooth
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
                  lift_height=0.20):
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
    approach_ee = np.array([cx, cy, top_z + approach_clearance])
    contact_ee = np.array([cx, cy, top_z - 0.005])
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
        _REPO, "tampura_bridge", "captures", "faithful_pick_streams.png"))
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

    cen = adapter.camera_target
    saved = capture(world.client, args.out,
                    [float(cen[0]) + 0.5, float(cen[1]) - 0.6, float(cen[2]) + 0.4],
                    [float(cen[0]), float(cen[1]), float(cen[2])])
    print("capture ->", saved)


if __name__ == "__main__":
    _main()
