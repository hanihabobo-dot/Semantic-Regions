#!/usr/bin/env python3
"""Phase 3-C probe: prove the bridge belief-write makes THEIR find_dice reward
fire (holding(die) AND at-home == 1.0) WITHOUT editing their env.  Headless.

RUN:
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/_belief_smoke.py --global-seed 0'
"""
import argparse
import logging
import os
import random
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401 — registers find_dice
import tampura_bridge.belief_bridge as bb

p = argparse.ArgumentParser()
p.add_argument("--config", default="./env_configs/find_dice.yml")
p.add_argument("--global-seed", type=int)
p.add_argument("--vis", type=int, default=0)
p.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "bb_{}".format(time.time())))
args = p.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)

env = tconfig.get_env(config["task"])(config=config)
b0, store = env.initialize()
reward = lambda: env.problem_spec.get_reward(b0.abstract(store), store)

die = bb.die_alias(b0)
r0 = reward()                                  # init: at-home but not holding -> 0
bb.mark_moved(b0, bb.cup_aliases(b0)[0])
bb.mark_away(b0)
r1 = reward()                                  # working, not home -> 0
bb.mark_holding(b0, die)
r2 = reward()                                  # holding die, still away -> 0
bb.mark_at_home(b0)
r3 = reward()                                  # holding die AND home -> 1.0

print("die_alias =", die, " cups =", bb.cup_aliases(b0))
print("rewards: init={} away={} holding_away={} home={}".format(r0, r1, r2, r3))
print("PASS" if (r0 == 0.0 and r1 == 0.0 and r2 == 0.0 and r3 == 1.0) else "FAIL")
