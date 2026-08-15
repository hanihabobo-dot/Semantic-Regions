#!/usr/bin/env python3
"""Smoke test (audit #120): run OUR streams on TAMPURA's Panda.

Constructs BoxelStreams (tampura_bridge/streams_boxel.py) over the live find_dice
world with the their-Panda RobotModel, then exercises the full geometric stream
chain on a VISIBLE cup: sample_grasp -> compute_kin_solution (IK on their robot)
-> plan_motion (collision-checked RRT on their robot).  First proof that OUR
streams produce real grasps / configs / collision-free trajectories on their
robot -- the foundation for un-relaxing pick/place to ground through them.
"""
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tampura_bridge.perception_adapter import FindDiceAdapter
from tampura_bridge.boxelize import boxelize_scene
from tampura_bridge.tampura_robot import build_robot_model
from tampura_bridge.streams_boxel import BoxelStreams


def build_streams(world):
    """FindDiceAdapter + boxelization + their-Panda model -> a BoxelStreams over
    their live world (reused by the smoke test and, later, the policy)."""
    adapter = FindDiceAdapter(world)
    visible = adapter.segment_visible()
    registry, _auto_cell = boxelize_scene(adapter, visible_names=visible)
    model = build_robot_model(world)
    object_body_ids = {n: o.object_id for n, o in adapter.objects.items()}
    support_body_ids = frozenset({world.floor})
    streams = BoxelStreams(
        registry, robot_id=world.robot.body,
        physics_client=adapter.client_id,
        object_body_ids=object_body_ids,
        support_body_ids=support_body_ids,
        robot=model)
    return adapter, registry, model, streams, visible


def _main():
    import argparse
    import random

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 -- registers the find_dice env

    pr = argparse.ArgumentParser(description="audit #120: OUR streams on their Panda")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int, default=0)
    pr.add_argument("--vis", type=int, default=0)
    pr.add_argument("--save-dir", default="/tmp/boxel_streams_smoke")
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])

    env = tconfig.get_env(config["task"])(config=config)
    env.initialize()

    adapter, registry, model, streams, visible = build_streams(env.world)
    print("=== OUR streams on their Panda (seed 0) ===")
    print("visible:", visible)

    obj_boxels = [b for b in registry.get_object_boxels()
                  if b.object_name and b.object_name.startswith("cup")]
    if not obj_boxels:
        print("no visible cup to test -- abort")
        return
    cup_boxel = obj_boxels[0]
    cup_name = cup_boxel.object_name
    print("target cup:", cup_name, " boxel:", cup_boxel.id,
          " center:", np.round(cup_boxel.center, 4).tolist())

    grasps = list(streams.sample_grasp(cup_name))
    print("sample_grasp ->", len(grasps), "grasp(s)")
    if not grasps:
        print("FAIL: no grasp")
        return
    grasp = grasps[0][0]

    configs = list(streams.compute_kin_solution(cup_name, cup_boxel.id, grasp))
    print("compute_kin_solution ->", len(configs), "IK config(s)")
    if not configs:
        print("FAIL: no IK on their robot (EE link / reach / orientation?)")
        return
    q_pick = configs[0][0]
    print("  q_pick:", np.round(q_pick.joint_positions, 3).tolist())

    trajs = list(streams.plan_motion(streams.home_config, q_pick))
    print("plan_motion(home -> q_pick) ->", len(trajs), "trajectory(ies)")
    if not trajs:
        print("FAIL: no collision-free path on their robot")
        return
    traj = trajs[0][0]
    print("  trajectory waypoints:", len(traj.waypoints))
    print("PASS: grasp + IK + collision-free motion on their Panda")


if __name__ == "__main__":
    _main()
