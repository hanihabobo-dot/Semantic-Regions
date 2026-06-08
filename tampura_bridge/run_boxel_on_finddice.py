#!/usr/bin/env python3
"""Phase 3-B ITEM 2 — our entry point running OUR BoxelPolicy on TAMPURA's
find_dice env. Mirrors run_planner.py:101-138 but builds BoxelPolicy directly
(no get_planner), so their clone is untouched.

RUN (GUI; user watches):
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/run_boxel_on_finddice.py --global-seed 0 --vis 1'
"""
import argparse
import logging
import os
import random
import sys
import time

import numpy as np

# Self-locate the repo root so our package + root modules import even when this
# script is launched by absolute path (sys.path[0] is the script's own dir).
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tampura.config import config as tconfig
import tampura_environments  # noqa: F401 — import registers the find_dice env

from tampura_bridge.boxel_policy import BoxelPolicy

DEFAULT_CONFIG = "./env_configs/find_dice.yml"  # relative to their env repo (cwd)


def build_parser():
    default_save = os.path.join(os.getcwd(), "runs", "boxel_run_{}".format(time.time()))
    p = argparse.ArgumentParser(description="Run BoxelPolicy on TAMPURA find_dice")
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--global-seed", type=int)
    # type=int (not their buggy type=bool, where bool("0") is True): 1=GUI, 0=headless.
    p.add_argument("--vis", type=int, default=1)
    p.add_argument("--max-steps", type=int)
    p.add_argument("--print-options", type=str)
    p.add_argument("--save-dir", default=default_save)
    return p


def main():
    args = build_parser().parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)

    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)
    logging.info(
        "[BoxelBridge] task=%s vis=%s seed=%s max_steps=%s",
        config["task"], config["vis"], config["global_seed"], config["max_steps"],
    )

    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()

    policy = BoxelPolicy(config, env.problem_spec, env=env)
    history, store = policy.rollout(env, b0, store)
    if policy._done:
        result, reason = "SUCCESS", ""
    elif policy._failed:
        result, reason = "FAILURE", getattr(policy, "_fail_reason", "?") or "?"
    else:
        result, reason = "INCOMPLETE", ""
    logging.info("[BoxelBridge] rollout complete: %d entries", len(history))
    logging.info("[BoxelBridge] seed=%s RESULT=%s %s",
                 config["global_seed"], result, reason)
    print("RESULT seed=%s %s %s" % (config["global_seed"], result, reason))


if __name__ == "__main__":
    main()
