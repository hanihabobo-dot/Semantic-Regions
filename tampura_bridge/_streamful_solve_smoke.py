#!/usr/bin/env python3
"""Streamful solve smoke (audit #120): prove OUR planner -- driven by the
bridge's streams (TAMPURA's Panda IK / collision / motion) -- produces a
GEOMETRICALLY CERTIFIED find_dice plan, where every grasp, config and trajectory
is sampled by our streams (no streamless hand-built init).  No execution, no GUI.

RUN:
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/_streamful_solve_smoke.py --global-seed 0'
"""
import argparse
import logging
import os
import random
import sys
import time

import numpy as np
from tampura.config import config as tconfig
import tampura_environments  # noqa: F401 -- registers find_dice

from tampura_bridge._streams_smoke import build_streams
from tampura_bridge.execution_boxel import fix_phantom_masses
from tampura_bridge.planner_boxel import BoxelBridgePlanner
from boxel_data import BoxelType

p = argparse.ArgumentParser()
p.add_argument("--config", default="./env_configs/find_dice.yml")
p.add_argument("--global-seed", type=int, default=0)
p.add_argument("--vis", type=int, default=0)
p.add_argument("--save-dir",
               default=os.path.join(os.getcwd(), "runs", "streamful_{}".format(time.time())))
args = p.parse_args()
arg_dict = {k: v for k, v in vars(args).items() if v is not None}
config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
random.seed(config["global_seed"])
np.random.seed(config["global_seed"])
tconfig.setup_logger(config["save_dir"], log_level=logging.WARNING)
if os.environ.get("STRM_DEBUG"):
    _lg = logging.getLogger("tampura_bridge.streams_boxel")
    _lg.setLevel(logging.DEBUG)
    _h = logging.StreamHandler(sys.stdout)
    _h.setLevel(logging.DEBUG)
    _h.setFormatter(logging.Formatter("STRM %(message)s"))
    _lg.addHandler(_h)

env = tconfig.get_env(config["task"])(config=config)
env.initialize()
adapter, registry, model, streams, visible = build_streams(env.world)
fix_phantom_masses(env.world.client, env.world.robot.body)

print("visible:", visible)
for b in registry.boxels.values():
    extra = ""
    if b.boxel_type == BoxelType.SHADOW:
        extra = " created_by=%s" % getattr(b, "created_by_boxel_id", None)
    print("  boxel %-14s %-11s%s" % (b.id, b.boxel_type.name, extra))

# Occluder->shadow map (so blocks_view_at is emitted even if created_by is unset).
shadow_occ = {}
for b in registry.boxels.values():
    if b.boxel_type == BoxelType.SHADOW and getattr(b, "created_by_boxel_id", None):
        shadow_occ.setdefault(b.id, []).append(b.created_by_boxel_id)

planner = BoxelBridgePlanner(streams, registry,
                             shadow_occluder_map=(shadow_occ or None),
                             camera_pos=adapter.camera_position)
goal = ("and", ("holding", "die"), ("at_home",))
t0 = time.perf_counter()
plan = planner.plan(target_objects=["die"], goal=goal,
                    current_config=streams.home_config,
                    max_time=90.0, unit_costs=True, verbose=False)
dt = time.perf_counter() - t0

print("PLAN (%.1fs):" % dt)
if plan:
    for a in plan:
        print("   %-9s %s" % (a[0], tuple(str(x) for x in a[1:])))
names = [a[0] for a in plan] if plan else []
ok = all(n in names for n in ("pick", "place", "sense", "go_home"))
print("PASS" if ok else "FAIL")
