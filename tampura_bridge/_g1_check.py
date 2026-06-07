#!/usr/bin/env python3
"""Phase 3-C de-cheat G1 probe: confirm boxelize_scene boxelizes only VISIBLE
objects -- a die hidden under a cup is NOT in the object boxels until revealed."""
import argparse
import logging
import os
import random
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from tampura_bridge.perception_adapter import FindDiceAdapter
from tampura_bridge.boxelize import boxelize_scene

p = argparse.ArgumentParser()
p.add_argument("--config", default="./env_configs/find_dice.yml")
p.add_argument("--global-seed", type=int)
p.add_argument("--vis", type=int, default=0)
p.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "g1_{}".format(time.time())))
args = p.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
ad = FindDiceAdapter(env.world)
visible, _ = ad.oracle_detect_objects()
reg, _ = boxelize_scene(ad)
obj_names = sorted(b.object_name for b in reg.get_object_boxels())
print("visible      :", sorted(visible))
print("object_boxels:", obj_names)
print("die boxelized while hidden?", "die" in obj_names, "(expect False)")
print("PASS" if "die" not in obj_names else "FAIL")
