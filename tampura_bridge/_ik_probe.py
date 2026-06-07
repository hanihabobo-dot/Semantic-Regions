#!/usr/bin/env python3
"""Step 2: IK reachability probe — can our IK approach put panda_grasptarget
(their link 14) at a top grasp of the cup on their Panda?  Validates reachability
BEFORE we parameterize/refactor our streams."""
import math
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np

from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from tampura_environments.panda_utils import pb_utils as pbu
from tampura_bridge.perception_adapter import FindDiceAdapter

GRASP_TARGET = "panda_grasptarget"
ARM = [0, 1, 2, 3, 4, 5, 6]


def main():
    arg_dict = {"config": "./env_configs/find_dice.yml", "vis": 0, "global_seed": 0,
                "save_dir": os.path.join(os.getcwd(), "runs", "ik_probe_{}".format(time.time()))}
    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    import random
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()
    world = env.world
    client = world.client
    rb = world.robot.body

    ee = pbu.link_from_name(rb, GRASP_TARGET, client=client)
    print("panda_grasptarget link idx:", ee)

    ad = FindDiceAdapter(world)
    cup = ad.objects["cup_0"]
    aabb = pbu.get_aabb(cup.object_id, client=client)
    cx = float((aabb.lower[0] + aabb.upper[0]) / 2)
    cy = float((aabb.lower[1] + aabb.upper[1]) / 2)
    ztop = float(aabb.upper[2])
    down = client.getQuaternionFromEuler([math.pi, 0, 0])

    err = None
    for label, tgt in [("pre-grasp(+10cm)", [cx, cy, ztop + 0.10]),
                       ("grasp(+1cm)", [cx, cy, ztop + 0.01])]:
        jp = client.calculateInverseKinematics(rb, ee, tgt, down,
                                               maxNumIterations=200,
                                               residualThreshold=1e-4)
        for i, a in zip(ARM, jp[:7]):
            client.resetJointState(rb, i, a)
        got = client.getLinkState(rb, ee)[0]
        err = float(np.linalg.norm(np.array(got) - np.array(tgt)))
        print("{:18s} target={} reached={} err={:.4f} m".format(
            label, [round(v, 4) for v in tgt], [round(v, 4) for v in got], err))

    print("cup top z={:.4f}  arm config (grasp) = {}".format(
        ztop, [round(client.getJointState(rb, i)[0], 3) for i in ARM]))
    print("RESULT:", "REACHABLE (err<2cm)" if (err is not None and err < 0.02)
          else "POOR REACH (err>=2cm) — IK may need tuning")


if __name__ == "__main__":
    main()
