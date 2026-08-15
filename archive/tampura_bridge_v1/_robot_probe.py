#!/usr/bin/env python3
"""Feasibility probe (faithful pick): dump their find_dice Panda's joint/link
layout and compare to our hardcoded robot_utils indices, to see whether our IK
(ARM_JOINT_INDICES=[0..6], END_EFFECTOR_LINK=11) targets their robot correctly."""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import time

from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from robot_utils import ARM_JOINT_INDICES, END_EFFECTOR_LINK, FINGER_JOINTS, REST_POSES


def main():
    arg_dict = {
        "config": "./env_configs/find_dice.yml",
        "vis": 0,
        "global_seed": 0,
        "save_dir": os.path.join(os.getcwd(), "runs", "robot_probe_{}".format(time.time())),
    }
    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()
    world = env.world
    rb = world.robot.body
    client = world.client

    n = client.getNumJoints(rb)
    print("=== THEIR find_dice Panda ===")
    print("robot body id:", rb, " numJoints:", n)
    for j in range(n):
        info = client.getJointInfo(rb, j)
        jname = info[1].decode("utf-8", "replace")
        jtype = info[2]  # 0=revolute,1=prismatic,4=fixed
        lname = info[12].decode("utf-8", "replace")
        print("  idx {:2d}  joint={:24s} type={}  childLink={}".format(j, jname, jtype, lname))

    print("\n=== OUR hardcoded robot_utils (built for our Panda) ===")
    print("ARM_JOINT_INDICES :", ARM_JOINT_INDICES)
    print("FINGER_JOINTS     :", FINGER_JOINTS)
    print("END_EFFECTOR_LINK :", END_EFFECTOR_LINK, "(panda_grasptarget on our load)")
    print("REST_POSES        :", REST_POSES)

    # name -> index lookup on their robot
    name_to_idx = {}
    for j in range(n):
        info = client.getJointInfo(rb, j)
        name_to_idx[info[12].decode("utf-8", "replace")] = j  # childLink name -> joint idx
    print("\n=== key links on their robot (by name) ===")
    for ln in ["panda_grasptarget", "panda_tool_tip", "panda_hand", "panda_handv",
               "camera_frame", "panda_link7", "panda_link8"]:
        print("  {:20s} -> link idx {}".format(ln, name_to_idx.get(ln, "ABSENT")))


if __name__ == "__main__":
    main()
