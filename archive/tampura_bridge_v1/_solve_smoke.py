#!/usr/bin/env python3
"""Phase 3-C probe: prove OUR planner emits the full find_dice solve sequence
(relocate cup -> sense die -> pick die -> go home) on the relaxed domain.  No GUI.

RUN:
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/_solve_smoke.py --global-seed 0'
"""
import argparse
import logging
import os
import random
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401 — registers find_dice
from tampura_bridge.perception_adapter import FindDiceAdapter
from tampura_bridge.boxel_policy import plan_solve

p = argparse.ArgumentParser()
p.add_argument("--config", default="./env_configs/find_dice.yml")
p.add_argument("--global-seed", type=int)
p.add_argument("--vis", type=int, default=0)
p.add_argument("--save-dir", default=os.path.join(os.getcwd(), "runs", "solve_{}".format(time.time())))
args = p.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
adapter = FindDiceAdapter(env.world)
visible = adapter.segment_visible()
cups = [n for n in visible if n != "die"]
print("visible:", visible)
plan = plan_solve(adapter, visible)
print("plan (die hidden):", [(a.name, a.args) for a in plan])
names = [a.name for a in plan]
ok1 = names == ["pick", "place", "sense", "pick", "go_home"]
giveup = plan_solve(adapter, visible, known_empty=cups)
print("plan (all cups emptied):", [(a.name, a.args) for a in giveup])
ok2 = (giveup == [])
print("PASS" if (ok1 and ok2) else "FAIL")
