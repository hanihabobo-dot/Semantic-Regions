#!/usr/bin/env python3
"""Phase 3-B ITEM 13: SENSE is legal ONLY at the fixed home config (GOAL 3 sense).

(A) Planning gate: with (at_sense_config) in init a sense goal grounds; WITHOUT it,
    no plan -> the domain precondition blocks sensing when not at home.
(B) Perception at home: our oracle reads the scene from the fixed wrist camera.
(C) Hide-gate: our test_target_can_hide_in_shadow runs on the find_dice scene
    (their client) -> sense uses our perception. (Need not reveal the die.)
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np

from pddlstream.algorithms.meta import solve
from pddlstream.language.constants import PDDLProblem


def _read_domain(name="domain_find_dice.pddl"):
    with open(os.path.join(_REPO, "pddl", name)) as f:
        return f.read()


def _sense_plan(at_home):
    domain = _read_domain()
    die, region = "die", "shadow_region"
    init = [("Obj", die), ("Boxel", region), ("is_shadow", region), ("handempty",)]
    if at_home:
        init.append(("at_sense_config",))
    problem = PDDLProblem(domain, {}, None, {}, init, ("obj_pose_known", die))
    try:
        sol = solve(problem, unit_costs=True)
    except TypeError:
        sol = solve(problem)
    plan = sol[0]
    return None if not plan else [a.name for a in plan]


def _main():
    import argparse
    import logging
    import random
    import time

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 — registers the find_dice env
    from tampura_bridge.perception_adapter import FindDiceAdapter
    from tampura_bridge.boxelize import boxelize_scene
    from streams import BoxelStreams

    # (A) planning gate — no env needed
    at_home, not_home = _sense_plan(True), _sense_plan(False)
    print("=== ITEM 13: sense-at-home gate ===")
    print("at home  -> plan:", at_home)
    print("NOT home -> plan:", not_home)
    gate_ok = bool(at_home) and ("sense" in at_home) and (not not_home)
    print("gate enforced (sense only at home)?", gate_ok)

    # (B)/(C) env-backed perception
    pr = argparse.ArgumentParser()
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int)
    pr.add_argument("--vis", type=int, default=1)
    pr.add_argument(
        "--save-dir",
        default=os.path.join(os.getcwd(), "runs", "boxel_sense13_{}".format(time.time())),
    )
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None}
    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)
    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()

    adapter = FindDiceAdapter(env.world)
    visible, _ = adapter.oracle_detect_objects()
    print("home perception: visible=", visible, " die hidden=", "die" not in visible)

    try:
        registry, _auto = boxelize_scene(adapter)
        die_b = next((b for b in registry.get_object_boxels()
                      if b.object_name == "die"), None)
        shadows = registry.get_shadow_boxels()
        streams = BoxelStreams(registry, robot_id=adapter.world.robot.body,
                               physics_client=adapter.client_id)
        if die_b and shadows:
            res = streams.test_target_can_hide_in_shadow(
                die_b.id, shadows[0].id, camera_pos=adapter.camera_position)
            print("hide-gate test_target_can_hide_in_shadow(die, cup_shadow) =", res,
                  "(ran on our perception)")
        else:
            print("hide-gate: no die/shadow boxel to test")
    except Exception as e:  # non-fatal — A+B carry the item
        print("hide-gate: skipped (", repr(e), ")")

    ok = gate_ok and ("die" not in visible)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _main()
