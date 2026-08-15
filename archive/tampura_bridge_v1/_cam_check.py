#!/usr/bin/env python3
"""Phase 3-C de-cheat: pick a fixed EXTERNAL sense camera that (a) sees the cups
and (b) reveals the die once its covering cup is removed.  Headless; tries a few
eyes on the current scene and reports visibility."""
import argparse
import logging
import os
import random
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from tampura_bridge.perception_adapter import FindDiceAdapter

p = argparse.ArgumentParser()
p.add_argument("--config", default="./env_configs/find_dice.yml")
p.add_argument("--global-seed", type=int)
p.add_argument("--vis", type=int, default=0)
p.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "cam_{}".format(time.time())))
args = p.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
ad = FindDiceAdapter(env.world)
cx, cy, cz = [float(v) for v in ad.camera_target]
cups = [o for n, o in ad.objects.items() if o.is_occluder]
die = ad.objects["die"]
hiding = min(cups, key=lambda c: (c.position[0] - die.position[0]) ** 2
             + (c.position[1] - die.position[1]) ** 2)

cands = {
    "overhead":  [cx, cy, cz + 1.0],
    "high_obl":  [cx, cy - 0.3, cz + 0.9],
    "mid_obl":   [cx, cy - 0.5, cz + 0.7],
    "model_obl": [cx, cy - 0.8, cz + 0.5],
}
print("scene cups:", len(cups), " centroid:", [round(cx, 3), round(cy, 3), round(cz, 3)])
for name, eye in cands.items():
    ad.camera_position = np.array(eye, dtype=float)
    vis, _ = ad.oracle_detect_objects()
    ncups = len([v for v in vis if v.startswith("cup")])
    print("  {:9s} eye={} cups_visible={}/{} die_hidden={}".format(
        name, [round(e, 2) for e in eye], ncups, len(cups), "die" not in vis))

# remove the covering cup, re-test die reveal
ad.client.resetBasePositionAndOrientation(hiding.object_id, [5, 5, 5], [0, 0, 0, 1])
print("-- after removing the covering cup --")
for name, eye in cands.items():
    ad.camera_position = np.array(eye, dtype=float)
    vis, _ = ad.oracle_detect_objects()
    print("  {:9s} die_visible={}".format(name, "die" in vis))
