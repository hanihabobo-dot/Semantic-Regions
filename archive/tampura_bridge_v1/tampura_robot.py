#!/usr/bin/env python3
"""Build a robot_utils_boxel.RobotModel for TAMPURA's find_dice Panda (audit #120).

OUR streams (tampura_bridge/streams_boxel.py) are robot-agnostic via RobotModel.
This factory queries TAMPURA's LIVE Panda -- arm/finger joints, the
panda_grasptarget EE link, per-joint limits, the rest config (DEFAULT_ARM_POS),
the gripper-link cluster, and the structural self-collision pairs -- so OUR IK /
collision / motion run on THEIR robot, which differs from ours (fingers [12,13],
panda_grasptarget link 14, vs our [9,10] / 11).
"""
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tampura_environments.panda_utils import pb_utils as pbu
from tampura_environments.panda_utils.panda_env_utils import (ARM_GROUP,
                                                             GRIPPER_GROUP)
from tampura_environments.panda_utils.robot import DEFAULT_ARM_POS

from tampura_bridge.robot_utils_boxel import RobotModel

# panda_grasptarget is the EE link our top-down grasp/IK targets (link 14 on
# their load).  Their controllers use panda_tool_tip as the tool frame, but the
# existing kinematic bridge already grasps via panda_grasptarget, so we keep it.
_EE_LINK_NAME = "panda_grasptarget"


def _structural_self_pairs(client, rb, arm_joints, n_links, rest, n_extra=5):
    """Link-index pairs in SELF-contact at the rest config + a few small
    perturbations -- structural overlaps (hand/finger cluster) to ignore during
    collision checks.  Augmented with kinematic-chain adjacency (i, i+1).
    Deterministic (local RandomState); restores the arm afterwards."""
    rng = np.random.RandomState(0)
    pairs = set()
    saved = [client.getJointState(rb, j)[0] for j in arm_joints]
    try:
        configs = [list(rest)]
        for _ in range(n_extra):
            configs.append([r + rng.uniform(-0.4, 0.4) for r in rest])
        for cfg in configs:
            for j, a in zip(arm_joints, cfg):
                client.resetJointState(rb, j, a)
            client.performCollisionDetection()
            for c in client.getContactPoints(bodyA=rb, bodyB=rb):
                la, lb = c[3], c[4]
                pairs.add((min(la, lb), max(la, lb)))
    finally:
        for j, a in zip(arm_joints, saved):
            client.resetJointState(rb, j, a)
    for i in range(-1, n_links - 1):          # chain adjacency
        pairs.add((i, i + 1))
    return frozenset(pairs)


def build_robot_model(world, ee_link_name=_EE_LINK_NAME):
    """Query TAMPURA's live Panda -> a RobotModel for OUR streams/collision/IK."""
    client = world.client
    rb = world.robot.body
    arm = tuple(int(j) for j in
                world.robot.get_group_joints(ARM_GROUP, client=client))
    fingers = tuple(int(j) for j in
                    world.robot.get_group_joints(GRIPPER_GROUP, client=client))
    ee_link = int(pbu.link_from_name(rb, ee_link_name, client=client))
    n_links = client.getNumJoints(rb)

    lows, highs = [], []
    for j in arm:
        info = client.getJointInfo(rb, j)
        lows.append(float(info[8]))
        highs.append(float(info[9]))
    joint_low = np.array(lows)
    joint_high = np.array(highs)

    rest = tuple(float(v) for v in DEFAULT_ARM_POS)
    open_finger_pos = float(client.getJointInfo(rb, fingers[0])[9])  # finger upper

    # gripper cluster: every link from the last arm link through the end (their
    # hand / fingers / tool / grasptarget frames sit past the arm), exempted by
    # allow_gripper_collisions when the gripper must enter clutter at pick/place.
    gripper_links = frozenset(range(max(arm), n_links))

    return RobotModel(
        arm_joints=arm,
        finger_joints=fingers,
        ee_link=ee_link,
        joint_low=joint_low,
        joint_high=joint_high,
        joint_ranges=joint_high - joint_low,
        rest_poses=rest,
        ignored_self_pairs=_structural_self_pairs(client, rb, arm, n_links, rest),
        gripper_links=gripper_links,
        open_finger_pos=open_finger_pos,
    )


def _main():
    import argparse
    import random

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 -- registers the find_dice env

    pr = argparse.ArgumentParser(description="audit #120: build their-Panda RobotModel")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int, default=0)
    pr.add_argument("--vis", type=int, default=0)
    pr.add_argument("--save-dir", default="/tmp/boxel_robot_model")
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])

    env = tconfig.get_env(config["task"])(config=config)
    env.initialize()
    m = build_robot_model(env.world)
    print("=== their-Panda RobotModel (seed 0) ===")
    print("arm_joints     :", m.arm_joints)
    print("finger_joints  :", m.finger_joints)
    print("ee_link        :", m.ee_link)
    print("rest_poses     :", tuple(round(v, 4) for v in m.rest_poses))
    print("joint_low      :", np.round(m.joint_low, 3).tolist())
    print("joint_high     :", np.round(m.joint_high, 3).tolist())
    print("open_finger_pos:", round(m.open_finger_pos, 4))
    print("gripper_links  :", sorted(m.gripper_links))
    print("self_pairs (%d):" % len(m.ignored_self_pairs), sorted(m.ignored_self_pairs))


if __name__ == "__main__":
    _main()
