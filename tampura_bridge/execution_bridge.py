#!/usr/bin/env python3
"""Phase 3-B ITEM 11: SIMPLIFIED pick execution in TAMPURA's world (option b).

Our execution.py drives our BoxelTestEnv and cannot move their robot, so for this
phase a "pick" is a pose-set + weld in their pybullet: teleport the target object
into the gripper and fix it there with a constraint (no motion planning). Proves
the loop; faithful pick/place controllers are a LATER upgrade.
"""
import math
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np
import pybullet as p

from tampura_environments.panda_utils import pb_utils as pbu
from tampura_environments.panda_utils.robot import PANDA_TOOL_TIP
from tampura_bridge.perception_adapter import FindDiceAdapter
from tampura_bridge.boxelize import capture


def execute_simplified_pick(world, obj_body):
    """Teleport obj_body into the gripper and weld it (fixed constraint).
    Returns (constraint_id, grasp_xyz). Simplified — no motion planning."""
    client = world.client
    tool = pbu.link_from_name(world.robot.body, PANDA_TOOL_TIP, client=client)
    (tx, ty, tz), _ = pbu.get_link_pose(world.robot.body, tool, client=client)
    _, obj_orn = pbu.get_pose(obj_body, client=client)
    client.resetBasePositionAndOrientation(obj_body, [tx, ty, tz], list(obj_orn))
    cid = client.createConstraint(
        parentBodyUniqueId=world.robot.body, parentLinkIndex=tool,
        childBodyUniqueId=obj_body, childLinkIndex=-1,
        jointType=p.JOINT_FIXED, jointAxis=[0, 0, 0],
        parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0])
    return cid, (tx, ty, tz)


def _ik(client, rb, ee, pos, orn):
    jp = client.calculateInverseKinematics(
        rb, ee, pos, orn, maxNumIterations=200, residualThreshold=1e-4)
    return list(jp[:7])


def _move_arm(client, rb, arm, target, steps=60, sleep=0.01, attached=None):
    """Kinematically interpolate the arm joints to `target`, animating the GUI.
    If `attached` = (obj_body, ee_link, rel_pose), keep that object fixed in the
    end-effector frame each frame (a grasped object riding with the gripper)."""
    start = [client.getJointState(rb, i)[0] for i in arm]
    for s in range(1, steps + 1):
        a = s / float(steps)
        for idx, q0, q1 in zip(arm, start, target):
            client.resetJointState(rb, idx, q0 + a * (q1 - q0))
        if attached is not None:
            obj, ee, rel = attached
            ep, eo = client.getLinkState(rb, ee)[:2]
            wp, wo = client.multiplyTransforms(ep, eo, rel[0], rel[1])
            client.resetBasePositionAndOrientation(obj, wp, wo)
        time.sleep(sleep)


def _save_wrist_image(world, path):
    """Save the robot's WRIST camera view (robot.get_image) at the current arm
    config — what the robot actually SEES, distinct from the external vantage."""
    from PIL import Image
    from tampura_environments.panda_utils.robot import HEIGHT, WIDTH

    ci = world.robot.get_image(client=world.client)
    rgb = getattr(ci, "rgbPixels", None)
    if rgb is None:
        rgb = ci[0]
    rgb = np.asarray(rgb, dtype=np.uint8)
    if rgb.ndim == 1:
        rgb = rgb.reshape(HEIGHT, WIDTH, 4)
    rgb = rgb[:, :, :3]
    ap = os.path.abspath(path)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    Image.fromarray(rgb).save(ap)
    return ap


def execute_faithful_pick(world, obj_body, wrist_capture=None):
    """Real reach -> grasp -> lift using OUR IK approach on THEIR Panda (bridge-
    only; no shared streams refactor).  Targets panda_grasptarget (link 14), arm
    joints 0-6, fingers 12/13.  Returns (constraint_id, lift_xyz).  If
    wrist_capture is given, save the wrist-camera view at the grasp pose."""
    client, rb = world.client, world.robot.body
    ee = pbu.link_from_name(rb, "panda_grasptarget", client=client)
    arm, fingers = [0, 1, 2, 3, 4, 5, 6], [12, 13]
    aabb = pbu.get_aabb(obj_body, client=client)
    cx = float((aabb.lower[0] + aabb.upper[0]) / 2)
    cy = float((aabb.lower[1] + aabb.upper[1]) / 2)
    ztop = float(aabb.upper[2])
    down = client.getQuaternionFromEuler([math.pi, 0, 0])

    for f in fingers:
        client.resetJointState(rb, f, 0.04)  # open
    _move_arm(client, rb, arm, _ik(client, rb, ee, [cx, cy, ztop + 0.10], down), steps=60)
    _move_arm(client, rb, arm, _ik(client, rb, ee, [cx, cy, ztop + 0.00], down), steps=30)

    if wrist_capture is not None:
        _save_wrist_image(world, wrist_capture)  # what the robot SEES at the grasp

    # grasp: record object pose in the EE frame, close fingers, weld
    ep, eo = client.getLinkState(rb, ee)[:2]
    op, oo = client.getBasePositionAndOrientation(obj_body)
    inv = client.invertTransform(ep, eo)
    rel = client.multiplyTransforms(inv[0], inv[1], op, oo)
    for f in fingers:
        client.resetJointState(rb, f, 0.015)  # close on the cup
    cid = client.createConstraint(rb, ee, obj_body, -1, p.JOINT_FIXED,
                                  [0, 0, 0], [0, 0, 0], [0, 0, 0])
    _move_arm(client, rb, arm, _ik(client, rb, ee, [cx, cy, ztop + 0.20], down),
              steps=40, attached=(obj_body, ee, rel))
    lift = client.getLinkState(rb, ee)[0]
    return cid, (float(lift[0]), float(lift[1]), float(lift[2]))


def _main():
    import argparse
    import logging
    import random
    import time

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 — registers the find_dice env

    pr = argparse.ArgumentParser(description="ITEM 11: simplified pick in their world")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int)
    pr.add_argument("--vis", type=int, default=1)
    pr.add_argument(
        "--save-dir",
        default=os.path.join(os.getcwd(), "runs", "boxel_pick_{}".format(time.time())),
    )
    pr.add_argument(
        "--out",
        default=os.path.join(_REPO, "tampura_bridge", "captures", "faithful_pick_held.png"),
    )
    pr.add_argument(
        "--wrist-out",
        default=os.path.join(_REPO, "tampura_bridge", "captures", "faithful_pick_wrist_view.png"),
    )
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None and k != "out"}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)

    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()
    world = env.world

    adapter = FindDiceAdapter(world)
    cup = adapter.objects["cup_0"]
    before = pbu.get_pose(cup.object_id, client=world.client)[0]
    cid, (tx, ty, tz) = execute_faithful_pick(world, cup.object_id, wrist_capture=args.wrist_out)
    after = pbu.get_pose(cup.object_id, client=world.client)[0]
    print("=== faithful pick (cup_0) on their robot ===")
    print("cup before:", np.round(before, 4).tolist())
    print("cup after :", np.round(after, 4).tolist(),
          " lifted dz: {:+.4f}".format(after[2] - before[2]), " constraint:", cid)
    saved = capture(world.client, args.out,
                    [tx + 0.6, ty - 0.6, tz + 0.2], [tx, ty, tz - 0.1])
    print("pick capture saved ->", saved)


if __name__ == "__main__":
    _main()
