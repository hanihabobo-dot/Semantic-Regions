#!/usr/bin/env python3
"""Phase 3-B ITEM 11: SIMPLIFIED pick execution in TAMPURA's world (option b).

Our execution.py drives our BoxelTestEnv and cannot move their robot, so for this
phase a "pick" is a pose-set + weld in their pybullet: teleport the target object
into the gripper and fix it there with a constraint (no motion planning). Proves
the loop; faithful pick/place controllers are a LATER upgrade.
"""
import os
import sys

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
        default=os.path.join(_REPO, "tampura_bridge", "captures", "item11_pick_held.png"),
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
    cid, (tx, ty, tz) = execute_simplified_pick(world, cup.object_id)
    after = pbu.get_pose(cup.object_id, client=world.client)[0]
    print("=== ITEM 11: simplified pick (cup_0) in their world ===")
    print("cup before:", np.round(before, 4).tolist())
    print("cup after :", np.round(after, 4).tolist(),
          " lifted dz: {:+.4f}".format(after[2] - before[2]), " constraint:", cid)
    saved = capture(world.client, args.out,
                    [tx + 0.6, ty - 0.6, tz + 0.2], [tx, ty, tz - 0.1])
    print("pick capture saved ->", saved)


if __name__ == "__main__":
    _main()
