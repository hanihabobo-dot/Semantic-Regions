"""Phase 3-B bridge policy: our Policy subclass plugged into TAMPURA's rollout.

ITEM 12 (GOAL 2): on the first rollout step, BoxelPolicy builds the FindDiceAdapter
over their live world, runs OUR PDDLStream planner on the find_dice domain variant
(relaxed pick, streamless), and EXECUTES the planned (modified) pick in their world
via the simplified pose-set/weld (ITEM 11).  It then no-ops for the rest of the
rollout.  rollout() special-cases action.name == "no-op" (policy.py:125): it skips
env.step, so the pick we performed directly in their world is not double-driven by
their pick controller.
"""
import logging
import os
from typing import Dict, Tuple

from tampura.policies.policy import Policy
from tampura.structs import AliasStore, Belief
from tampura.symbolic import Action

from pddlstream.algorithms.meta import solve
from pddlstream.language.constants import PDDLProblem

from tampura_bridge.perception_adapter import FindDiceAdapter
from tampura_bridge.execution_bridge import execute_faithful_pick
from tampura_bridge.boxelize import capture

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_domain(name="domain_find_dice.pddl"):
    with open(os.path.join(_REPO, "pddl", name)) as f:
        return f.read()


def plan_pick_goal(target_name="cup_0"):
    """Run OUR planner on the find_dice variant for a single-pick goal; return the
    pick Action or None.  Streamless: the relaxed pick grounds from known-pose
    facts (ITEM 10)."""
    domain = _read_domain()
    boxel = "boxel_{}".format(target_name)
    init = [
        ("Obj", target_name), ("Boxel", boxel),
        ("handempty",), ("clear", target_name),
        ("obj_at_boxel_KIF", target_name, boxel),
        ("obj_at_boxel", target_name, boxel),
        ("at_sense_config",),
    ]
    goal = ("holding", target_name)
    problem = PDDLProblem(domain, {}, None, {}, init, goal)
    try:
        solution = solve(problem, unit_costs=True)
    except TypeError:
        solution = solve(problem)
    plan = solution[0]
    if not plan:
        return None
    return next((a for a in plan if a.name == "pick"), None)


def plan_solve(adapter, domain_name="domain_find_dice.pddl"):
    """Run OUR planner on the find_dice variant for the FULL holding-die solve.
    Returns the plan: relocate the hiding cup -> sense the die -> pick the die ->
    go home.  Streamless: relaxed pick/place ground from the symbolic init.
    Seed-generic: cups/die + the hiding cup are derived from the adapter."""
    domain = _read_domain(domain_name)
    objs = list(adapter.objects.values())
    cups = [o for o in objs if o.is_occluder]
    die = next(o for o in objs if not o.is_occluder)
    # find_dice hides the die under ONE cup (containment): the cup nearest in XY.
    hiding = min(cups, key=lambda c: (c.position[0] - die.position[0]) ** 2
                 + (c.position[1] - die.position[1]) ** 2)
    cup_b, region, free = "boxel_" + hiding.name, "region_" + die.name, "free_dest"
    init = [
        ("Obj", hiding.name), ("Obj", die.name),
        ("Boxel", cup_b), ("Boxel", region), ("Boxel", free),
        ("handempty",),
        ("clear", hiding.name), ("clear", die.name),
        ("obj_at_boxel", hiding.name, cup_b), ("obj_at_boxel_KIF", hiding.name, cup_b),
        ("on_table", hiding.name),
        ("is_shadow", region),
        ("is_free_space", free), ("on_surface", free),
        ("blocks_view_at", hiding.name, cup_b, region),
        ("at_sense_config",),
    ]
    goal = ("and", ("holding", die.name), ("at_home",))
    problem = PDDLProblem(domain, {}, None, {}, init, goal)
    try:
        solution = solve(problem, unit_costs=True)
    except TypeError:
        solution = solve(problem)
    return solution[0] or []


class BoxelPolicy(Policy):
    """Drives TAMPURA's rollout with our planner.  ITEM 12: plan + execute one
    pick on the first step, then no-op."""

    def __init__(self, config, problem_spec, **kwargs):
        super().__init__(config, problem_spec, **kwargs)
        self.env = kwargs.get("env")
        self._picked = False
        self._held_constraint = None

    def get_action(self, belief: Belief, store: AliasStore
                   ) -> Tuple[Action, Dict, AliasStore]:
        if self._picked or self.env is None:
            return Action(name="no-op"), {}, store

        adapter = FindDiceAdapter(self.env.world)
        pick = plan_pick_goal(target_name="cup_0")
        if pick is None:
            logging.info("[BoxelPolicy] planner returned no pick; no-op")
            return Action(name="no-op"), {}, store

        obj_name = pick.args[0] if getattr(pick, "args", None) else "cup_0"
        body = adapter.objects[obj_name].object_id
        cid, (tx, ty, tz) = execute_faithful_pick(self.env.world, body)
        self._held_constraint = cid
        self._picked = True
        out = os.path.join(_REPO, "tampura_bridge", "captures", "item12_planner_faithful_pick.png")
        capture(self.env.world.client, out,
                [tx + 0.6, ty - 0.6, tz + 0.2], [tx, ty, tz - 0.1])
        info = {"planned_action": str(pick), "executed_pick": obj_name,
                "constraint": cid, "capture": out}
        logging.info("[BoxelPolicy] planner emitted %s; executed faithful pick of "
                     "%s (constraint %s); capture -> %s", pick, obj_name, cid, out)
        return Action(name="no-op"), info, store
