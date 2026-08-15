#!/usr/bin/env python3
"""Phase 3-C de-cheat: verify the fixed external camera does NOT reveal a hidden
die (die must stay occluded until its cup is relocated).  Prints one line per
seed: scene size, what the camera sees, and whether the die is (correctly) hidden."""
import argparse
import logging
import os
import random
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401
from tampura_bridge.perception_adapter import FindDiceAdapter

a = argparse.ArgumentParser()
a.add_argument("--config", default="./env_configs/find_dice.yml")
a.add_argument("--global-seed", type=int)
a.add_argument("--vis", type=int, default=0)
a.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "segall_{}".format(time.time())))
args = a.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.ERROR)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
ad = FindDiceAdapter(env.world)  # external camera (default)
vis = ad.segment_visible()
ncup = sum(1 for o in ad.objects.values() if o.is_occluder)
die_hidden = "die" not in vis
print("RESULT seed={} n_obj={} cups_seen={}/{} die_hidden={} {}".format(
    config["global_seed"], len(ad.objects),
    sum(1 for v in vis if v.startswith("cup")), ncup, die_hidden,
    "OK" if die_hidden else "CHEAT(die seen w/o moving cup)"))
