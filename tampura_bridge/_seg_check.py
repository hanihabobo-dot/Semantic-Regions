#!/usr/bin/env python3
"""Phase 3-C de-cheat: test RENDERED-IMAGE segmentation as a reliable visibility
check from a fixed external camera (vs the crude AABB-corner oracle).  Reports
which objects a rendered external view actually sees, before/after uncovering the
die.  Headless (ER_TINY_RENDERER)."""
import argparse
import logging
import os
import random
import time

import numpy as np
import pybullet as p
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from tampura_bridge.perception_adapter import FindDiceAdapter

p_ = argparse.ArgumentParser()
p_.add_argument("--config", default="./env_configs/find_dice.yml")
p_.add_argument("--global-seed", type=int)
p_.add_argument("--vis", type=int, default=0)
p_.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "seg_{}".format(time.time())))
args = p_.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
ad = FindDiceAdapter(env.world)
cid = ad.client_id
cx, cy, cz = [float(v) for v in ad.camera_target]
id2name = {o.object_id: n for n, o in ad.objects.items()}
cups = [o for n, o in ad.objects.items() if o.is_occluder]
die = ad.objects["die"]
hiding = min(cups, key=lambda c: (c.position[0] - die.position[0]) ** 2
             + (c.position[1] - die.position[1]) ** 2)


def seen(eye, w=320, h=240):
    view = p.computeViewMatrix(eye, [cx, cy, cz], [0, 0, 1], physicsClientId=cid)
    proj = p.computeProjectionMatrixFOV(60.0, w / float(h), 0.01, 5.0, physicsClientId=cid)
    img = p.getCameraImage(w, h, viewMatrix=view, projectionMatrix=proj,
                           renderer=p.ER_TINY_RENDERER, physicsClientId=cid)
    seg = np.array(img[4]).reshape(h, w)
    ids = set(int(v) & ((1 << 24) - 1) for v in np.unique(seg) if v >= 0)
    return sorted(id2name[i] for i in ids if i in id2name)


eyes = {"overhead": [cx, cy, cz + 1.0], "high_obl": [cx, cy - 0.3, cz + 0.9],
        "mid_obl": [cx, cy - 0.5, cz + 0.7]}
print("scene cups:", len(cups))
for name, eye in eyes.items():
    print("  {:9s} sees: {}".format(name, seen(eye)))
ad.client.resetBasePositionAndOrientation(hiding.object_id, [5, 5, 5], [0, 0, 0, 1])
print("-- after removing the covering cup --")
for name, eye in eyes.items():
    s = seen(eye)
    print("  {:9s} sees: {}  die_revealed={}".format(name, s, "die" in s))
