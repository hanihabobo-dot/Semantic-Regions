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
from tampura_bridge.execution_bridge import (execute_faithful_pick,
                                             execute_faithful_place,
                                             execute_go_home)
from tampura_bridge.boxelize import capture, draw_overlay
import tampura_bridge.belief_bridge as bb

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
    """Phase 3-C: drives TAMPURA's find_dice rollout to a PASSING holding-die
    episode with OUR pipeline.  On the first step it plans the full solve with
    plan_solve (relocate cup -> sense -> pick die -> go home) and draws OUR
    boxelization (POMDP voxels cleared); thereafter it executes ONE planned step
    per rollout step via our faithful IK execution on their Panda, writing the
    symbolic result into their SceneBelief (belief_bridge) so their reward fires.
    Each get_action returns no-op so rollout skips env.step (we drive their world
    directly); the no-op deepcopy carries our belief writes forward (policy.py:125)."""

    def __init__(self, config, problem_spec, **kwargs):
        super().__init__(config, problem_spec, **kwargs)
        self.env = kwargs.get("env")
        self._plan = None
        self._step = 0
        self._adapter = None
        self._registry = None
        self._overlay = None
        self._bodies = {}
        self._die_name = None
        self._cup_constraint = None
        self._die_body = None

    def _refresh_overlay(self, sense_at_home=False):
        self._adapter, self._registry, self._overlay = draw_overlay(
            self.env.world, sense_at_home=sense_at_home, prev=self._overlay)

    def _capture(self, fname):
        cen = self._adapter.camera_target
        eye = [float(cen[0]) + 0.45, float(cen[1]) - 0.45, float(cen[2]) + 0.5]
        out = os.path.join(_REPO, "tampura_bridge", "captures", fname)
        return capture(self.env.world.client, out, eye,
                       [float(cen[0]), float(cen[1]), float(cen[2])])

    def _capture_at(self, fname, target_xyz, off=(0.5, -0.6, 0.35)):
        t = [float(target_xyz[0]), float(target_xyz[1]), float(target_xyz[2])]
        eye = [t[0] + off[0], t[1] + off[1], t[2] + off[2]]
        out = os.path.join(_REPO, "tampura_bridge", "captures", fname)
        return capture(self.env.world.client, out, eye, t)

    def _place_xy(self, die_pos):
        """A known-free table point to relocate the cup to, farthest from the die
        (uses OUR free-space boxels; seed-generic)."""
        frees = self._registry.get_free_space_boxels()
        if frees:
            b = max(frees, key=lambda f: (f.center[0] - die_pos[0]) ** 2
                    + (f.center[1] - die_pos[1]) ** 2)
            return (float(b.center[0]), float(b.center[1]))
        return (float(die_pos[0]), float(die_pos[1]) - 0.18)

    def get_action(self, belief, store):
        if self.env is None:
            return Action(name="no-op"), {}, store
        world = self.env.world

        if self._plan is None:
            execute_go_home(world)                              # start from home (animated; no teleport)
            self._refresh_overlay(sense_at_home=False)          # initial boxels; voxels cleared
            self._plan = plan_solve(self._adapter)
            self._bodies = {n: o.object_id for n, o in self._adapter.objects.items()}
            self._die_name = next(n for n, o in self._adapter.objects.items()
                                  if not o.is_occluder)
            self._die_body = self._bodies[self._die_name]
            bb.mark_away(belief)                                 # arm about to leave home
            logging.info("[BoxelPolicy] plan: %s", [str(a) for a in self._plan])
            self._capture("phase3c_initial_boxels.png")

        if not self._plan or self._step >= len(self._plan):
            return Action(name="no-op"), {}, store

        act = self._plan[self._step]
        obj_name = act.args[0] if act.args else None
        info = {"planned_action": str(act), "step": self._step}

        if act.name == "pick" and obj_name != self._die_name:
            self._cup_constraint, _ = execute_faithful_pick(world, self._bodies[obj_name])
            info["executed"] = "faithful pick (cup) " + obj_name
        elif act.name == "place":
            die_pos = self._adapter.objects[self._die_name].position
            place_xy = self._place_xy(die_pos)
            execute_faithful_place(world, self._bodies[obj_name], self._cup_constraint,
                                   place_xy, self._adapter.table_surface_height)
            bb.mark_moved(belief, bb.cup_aliases(belief)[int(obj_name.split("_")[-1])])
            info["executed"] = "faithful place (cup) -> " + str(
                tuple(round(v, 3) for v in place_xy))
        elif act.name == "sense":
            execute_go_home(world)                              # animate to home to sense (no teleport)
            self._refresh_overlay(sense_at_home=False)          # redraw from home (cup moved, die revealed)
            visible, _ = self._adapter.oracle_detect_objects()
            info["executed"] = "sense @ home; visible=" + str(visible)
            logging.info("[BoxelPolicy] sense from home: die visible? %s "
                         "(optimistic-sense + replan; converges immediately for a "
                         "single-occluder scene)", self._die_name in visible)
        elif act.name == "pick" and obj_name == self._die_name:
            execute_faithful_pick(world, self._die_body)
            bb.mark_holding(belief, bb.die_alias(belief))
            info["executed"] = "faithful pick (die) " + obj_name
        elif act.name == "go_home":
            execute_go_home(world, held_body=self._die_body)
            bb.mark_at_home(belief)
            self._refresh_overlay(sense_at_home=False)
            info["executed"] = "faithful go-home (holding die)"
            die_xyz = world.client.getBasePositionAndOrientation(self._die_body)[0]
            self._capture_at("phase3c_die_at_home.png", die_xyz)

        logging.info("[BoxelPolicy] step %d: %s -> %s", self._step, str(act),
                     info.get("executed", ""))
        self._step += 1
        return Action(name="no-op"), info, store
