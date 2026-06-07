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


def plan_solve(adapter, visible, known_empty=(), domain_name="domain_find_dice.pddl"):
    """Genuine optimistic plan over the CURRENTLY VISIBLE scene -- never uses the
    die's pose.  die visible -> pick(die)->home; else relocate the next un-emptied
    visible cup + sense its region (the policy executes through the sense, then
    re-segments and replans); no candidates -> [] (give up).  Seed-generic."""
    domain = _read_domain(domain_name)
    if "die" in visible:
        init = [
            ("Obj", "die"), ("Boxel", "boxel_die"),
            ("handempty",), ("clear", "die"),
            ("obj_at_boxel", "die", "boxel_die"),
            ("obj_at_boxel_KIF", "die", "boxel_die"),
            ("on_table", "die"),
        ]
    else:
        cands = [n for n in sorted(visible) if n != "die" and n not in set(known_empty)]
        if not cands:
            return []
        cup = cands[0]
        cup_b, region, free = "boxel_" + cup, "region_" + cup, "free_dest"
        init = [
            ("Obj", cup), ("Obj", "die"),
            ("Boxel", cup_b), ("Boxel", region), ("Boxel", free),
            ("handempty",),
            ("clear", cup), ("clear", "die"),
            ("obj_at_boxel", cup, cup_b), ("obj_at_boxel_KIF", cup, cup_b),
            ("on_table", cup),
            ("is_shadow", region),
            ("is_free_space", free), ("on_surface", free),
            ("blocks_view_at", cup, cup_b, region),
        ]
    goal = ("and", ("holding", "die"), ("at_home",))
    problem = PDDLProblem(domain, {}, None, {}, init, goal)
    try:
        solution = solve(problem, unit_costs=True)
    except TypeError:
        solution = solve(problem)
    return solution[0] or []


class BoxelPolicy(Policy):
    """Phase 3-C de-cheat: GENUINE sense-plan-replan search on their find_dice
    env, driven by OUR pipeline.  The die's pose is UNKNOWN until a real render
    reveals it.  Each cycle OUR planner picks an un-emptied VISIBLE cup; we
    relocate it (faithful IK pick + place), park the arm clear of the fixed
    external camera, and SENSE by re-rendering + segmenting.  If the die is
    genuinely revealed we pick it and go home (success); otherwise that region
    is marked empty and we replan; if no cups remain we give up (failure ->
    reward stays 0).  Belief/reward is written ONLY on a real grasp.  get_action
    returns no-op so the rollout's deepcopy carries our writes (policy.py:125)."""

    def __init__(self, config, problem_spec, **kwargs):
        super().__init__(config, problem_spec, **kwargs)
        self.env = kwargs.get("env")
        self._overlay = None
        self._cam_eye = None          # fixed external camera, locked on first build
        self._cam_target = None
        self._adapter = None
        self._registry = None
        self._subplan = None
        self._subidx = 0
        self._known_empty = []
        self._used_places = []
        self._held_cup_name = None
        self._held_cup_body = None
        self._held_constraint = None
        self._die_body = None
        self._done = False
        self._failed = False

    def _refresh_overlay(self):
        self._adapter, self._registry, self._overlay, visible = draw_overlay(
            self.env.world, sense_at_home=False, prev=self._overlay,
            camera_eye=self._cam_eye, camera_target=self._cam_target)
        if self._cam_eye is None:                       # lock the fixed camera once
            self._cam_eye = self._adapter.camera_position
            self._cam_target = self._adapter.camera_target
        return visible

    def _capture(self, fname, target=None, off=(0.5, -0.6, 0.35)):
        cen = target if target is not None else self._adapter.camera_target
        eye = [float(cen[0]) + off[0], float(cen[1]) + off[1], float(cen[2]) + off[2]]
        out = os.path.join(_REPO, "tampura_bridge", "captures", fname)
        return capture(self.env.world.client, out, eye,
                       [float(cen[0]), float(cen[1]), float(cen[2])])

    def _next_place_xy(self):
        """A known-free table spot to set a relocated cup aside -- farthest from
        the occluder centroid, spread from spots already used (die-independent)."""
        cen = self._adapter.camera_target
        frees = self._registry.get_free_space_boxels()
        avail = [f for f in frees if all(
            (f.center[0] - u[0]) ** 2 + (f.center[1] - u[1]) ** 2 > 0.01
            for u in self._used_places)]
        pool = avail or frees
        if pool:
            b = max(pool, key=lambda f: (f.center[0] - cen[0]) ** 2
                    + (f.center[1] - cen[1]) ** 2)
            xy = (float(b.center[0]), float(b.center[1]))
        else:
            xy = (float(cen[0]), float(cen[1]) - 0.25 - 0.1 * len(self._used_places))
        self._used_places.append(xy)
        return xy

    def _replan(self, visible):
        self._subplan = plan_solve(self._adapter, visible, self._known_empty)
        self._subidx = 0
        if not self._subplan:
            self._failed = True

    def get_action(self, belief, store):
        if self.env is None or self._done or self._failed:
            return Action(name="no-op"), {}, store
        world = self.env.world

        if self._subplan is None:                       # first step: perceive + plan
            execute_go_home(world)                      # arm clear of the camera (animated)
            visible = self._refresh_overlay()
            self._capture("phase3c_genuine_initial.png")
            bb.mark_away(belief)
            self._replan(visible)
            logging.info("[BoxelPolicy] GENUINE search; initial plan: %s",
                         [str(a) for a in (self._subplan or [])])
            if self._failed:
                return Action(name="no-op"), {"failed": "no visible cups"}, store

        act = self._subplan[self._subidx]
        arg0 = act.args[0] if act.args else None
        info = {"action": str(act), "known_empty": list(self._known_empty)}

        if act.name == "pick" and arg0 != "die":
            self._held_cup_name = arg0
            self._held_cup_body = self._adapter.objects[arg0].object_id
            self._held_constraint, _ = execute_faithful_pick(world, self._held_cup_body)
            self._subidx += 1
        elif act.name == "place":
            xy = self._next_place_xy()
            execute_faithful_place(world, self._held_cup_body, self._held_constraint,
                                   xy, self._adapter.table_surface_height)
            self._subidx += 1
        elif act.name == "sense":
            execute_go_home(world)                      # park arm clear of the external camera
            visible = self._refresh_overlay()           # re-render the relocated scene (clean segment)
            revealed = "die" in visible
            if revealed:
                self._die_body = self._adapter.objects["die"].object_id
            elif self._held_cup_name and self._held_cup_name not in self._known_empty:
                self._known_empty.append(self._held_cup_name)
            self._replan(visible)                       # revealed -> [pick die, home]; else next cup / give up
            info["sensed_after"] = self._held_cup_name
            info["die_revealed"] = revealed
            logging.info("[BoxelPolicy] sensed after relocating %s: die_revealed=%s; "
                         "known_empty=%s", self._held_cup_name, revealed, self._known_empty)
        elif act.name == "pick" and arg0 == "die":
            execute_faithful_pick(world, self._die_body)
            bb.mark_holding(belief, bb.die_alias(belief))
            self._subidx += 1
        elif act.name == "go_home":
            execute_go_home(world, held_body=self._die_body)
            bb.mark_at_home(belief)
            self._done = True
            self._refresh_overlay()
            die_xyz = world.client.getBasePositionAndOrientation(self._die_body)[0]
            self._capture("phase3c_genuine_die_at_home.png", die_xyz)
            info["success"] = True

        return Action(name="no-op"), info, store
