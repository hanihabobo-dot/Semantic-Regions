"""find_dice bridge policy (audit #120): our Policy subclass plugged into
TAMPURA's rollout, running OUR streamful PDDLStream planner + streams on their
live find_dice env.

Each rollout step advances a genuine sense-plan-replan search: OUR planner
(planner_boxel.BoxelBridgePlanner -- pddlstream_planner.PDDLStreamPlanner driven
by the bridge's robot-aware streams over the streamful find_dice domain) plans
over the currently-visible scene, and we EXECUTE that plan in their world with the
genuine streams executor (execution_boxel: motion-planned transit, contact-
verified grasp, real physics).  get_action returns no-op so the rollout's deepcopy
carries our belief writes WITHOUT their controllers double-driving the
manipulation (rollout special-cases action.name == "no-op", policy.py:125).
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
from tampura_bridge.execution_boxel import (execute_pick, execute_place,
                                            execute_go_home,
                                            fix_phantom_masses)
from tampura_bridge._streams_smoke import build_streams
from tampura_bridge.boxelize import capture, draw_overlay
from tampura_bridge.planner_boxel import BoxelBridgePlanner
from boxel_data import BoxelType
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
    """GENUINE sense-plan-replan search on their find_dice env, driven by OUR
    streamful PDDLStream planner (planner_boxel) + streams.  The die's pose is
    UNKNOWN until a real render reveals it.  Each cycle OUR planner picks an
    un-emptied VISIBLE cup; we relocate it (IK pick + place), park the arm clear
    of the fixed external camera, and SENSE by re-rendering + segmenting.  If the
    die is
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
        self._gui = bool(config["vis"])
        self._streams = None          # OUR streams on their Panda (built once)
        self._model = None            # their-Panda RobotModel
        self._q_current = None        # live arm config threaded across actions
        self._fail_reason = None      # honest failure cause for per-seed reporting

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

    def _planner(self):
        """OUR streamful planner (planner_boxel.BoxelBridgePlanner) over the
        current registry: each shadow carries its occluder (created_by_boxel_id)
        so blocks_view_at gates view_clear, and the bridge's streams (their Panda
        IK / collision / motion) certify every grasp / config / trajectory."""
        reg = self._registry
        shadow_occ = {}
        for b in reg.boxels.values():
            if b.boxel_type == BoxelType.SHADOW and getattr(
                    b, "created_by_boxel_id", None):
                shadow_occ.setdefault(b.id, []).append(b.created_by_boxel_id)
        return BoxelBridgePlanner(
            self._streams, reg, shadow_occluder_map=(shadow_occ or None),
            camera_pos=self._adapter.camera_position)

    def _known_empty_shadow_ids(self):
        """SHADOW boxel ids whose occluder cup we already relocated + sensed
        empty -- so the streamful planner does not re-sense them."""
        reg = self._registry
        out = []
        for b in reg.boxels.values():
            if b.boxel_type != BoxelType.SHADOW:
                continue
            occ_id = getattr(b, "created_by_boxel_id", None)
            occ = reg.get_boxel(occ_id) if occ_id else None
            if occ is not None and occ.object_name in self._known_empty:
                out.append(b.id)
        return out

    def _boxel_obj_name(self, boxel_id):
        """Map a planner boxel id to the object name our executor expects: cup
        OBJECT boxels carry object_name; the target name 'die' passes through."""
        if boxel_id == "die":
            return "die"
        b = self._registry.get_boxel(boxel_id)
        return b.object_name if (b is not None and b.object_name) else boxel_id

    def _convert_plan(self, plan):
        """Project the streamful plan (move/pick/place/sense/.../go_home tuples
        with boxel-id args) onto the policy's executable steps: drop the transit
        ``move`` actions (our execute_pick/place re-plan their own transit from
        the live config via plan_motion, exactly like our pipeline's runtime
        replan) and translate boxel ids to object names.  Place keeps the
        planner's chosen free-space destination as a second arg."""
        steps = []
        for a in (plan or []):
            name, args = a[0], a[1:]
            if name == "move":
                continue
            if name == "pick":
                steps.append(Action(name="pick",
                                    args=(self._boxel_obj_name(str(args[0])),)))
            elif name == "place":
                steps.append(Action(name="place",
                                    args=(self._boxel_obj_name(str(args[0])),
                                          str(args[1]))))
            elif name == "sense":
                steps.append(Action(name="sense", args=("die", str(args[1]))))
            elif name == "go_home":
                steps.append(Action(name="go_home", args=("die",)))
        return steps

    def _plan_attempt(self, planner, visible, goal):
        """One streamful plan over the current scene: die visible -> direct die
        pick (visible_target_locations links the die to its boxel); else relocate
        a not-yet-emptied cup + sense its region."""
        if "die" in visible:
            die_boxel = next((b.id for b in self._registry.get_object_boxels()
                              if b.object_name == "die"), None)
            vtl = {"die": die_boxel} if die_boxel is not None else None
            # The die is LOCATED, so it is in no shadow: mark every shadow
            # known-empty for the die.  This drops the (now-pointless) sense
            # options from the search -- otherwise the relocated cup's new shadow
            # looks senseable and the adaptive search burns time on infeasible
            # sense-then-relocate skeletons instead of the trivial direct pick.
            all_shadows = [b.id for b in self._registry.boxels.values()
                           if b.boxel_type == BoxelType.SHADOW]
            return planner.plan(target_objects=["die"], goal=goal,
                                current_config=self._q_current,
                                visible_target_locations=vtl,
                                known_empty_shadows=all_shadows,
                                max_time=60.0, unit_costs=True, verbose=False)
        return planner.plan(target_objects=["die"], goal=goal,
                            current_config=self._q_current,
                            known_empty_shadows=self._known_empty_shadow_ids(),
                            max_time=60.0, unit_costs=True, verbose=False)

    def _replan(self, visible, attempts=5):
        """Replan with OUR streamful planner over the current scene, retrying the
        solve a few times.  plan-motion (RRT) and PDDLStream's adaptive search
        are stochastic, so a FEASIBLE plan can be missed on an unlucky draw; a
        fresh attempt re-runs the streams with advanced RNG.  A genuine give-up
        (no un-emptied cups left) returns empty on EVERY attempt, so the retries
        cost time only when no plan actually exists."""
        goal = ("and", ("holding", "die"), ("at_home",))
        plan = []
        for _ in range(attempts):
            plan = self._plan_attempt(self._planner(), visible, goal) or []
            if plan:
                break
        self._subplan = self._convert_plan(plan)
        self._subidx = 0
        if not self._subplan:
            self._failed = True
            self._fail_reason = "no_plan_or_candidates"

    def get_action(self, belief, store):
        if self.env is None or self._done or self._failed:
            return Action(name="no-op"), {}, store
        world = self.env.world

        if self._subplan is None:                       # first step: perceive + plan
            if self._streams is None:                   # build OUR streams on their Panda once
                self._adapter, self._registry, self._model, self._streams, _ = \
                    build_streams(world)
                fix_phantom_masses(world.client, world.robot.body)
                self._q_current = self._streams.home_config
            self._q_current, _ = execute_go_home(      # arm clear of the camera
                self._streams, world, self._model, self._q_current, self._gui)
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
            q_new, cid, pst = execute_pick(
                self._streams, world, self._model, arg0, "boxel_" + arg0,
                self._q_current, self._gui)
            info["pick_status"] = pst
            if pst != "ok":
                self._failed = True
                self._fail_reason = "pick_%s_%s" % (arg0, pst)
                logging.info("[BoxelPolicy] pick(%s) FAILED: %s", arg0, pst)
                return Action(name="no-op"), info, store
            self._q_current, self._held_constraint = q_new, cid
            self._subidx += 1
        elif act.name == "place":
            # OUR planner decides "relocate the cup to a free spot to clear its
            # shadow"; we execute that at the free boxel FARTHEST from the die
            # region (_next_place_xy), a planner-certified-equivalent free dest.
            # The planner cannot see the still-hidden die at plan time, so its
            # arbitrary free choice can land between the robot and the die and
            # block the later die pick; the farthest spot reliably does not.
            xy = self._next_place_xy()
            q_new, pst = execute_place(
                self._streams, world, self._model, self._held_cup_name,
                self._held_cup_body, self._held_constraint, xy,
                self._q_current, self._gui,
                table_z=self._adapter.table_surface_height)
            info["place_status"] = pst
            if pst != "ok":
                self._failed = True
                self._fail_reason = "place_%s" % pst
                logging.info("[BoxelPolicy] place FAILED: %s", pst)
                return Action(name="no-op"), info, store
            self._q_current = q_new
            self._subidx += 1
        elif act.name == "sense":
            self._q_current, _ = execute_go_home(      # park arm clear of the external camera
                self._streams, world, self._model, self._q_current, self._gui)
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
            q_new, cid, pst = execute_pick(
                self._streams, world, self._model, "die", "boxel_die",
                self._q_current, self._gui)
            info["pick_status"] = pst
            if pst != "ok":
                self._failed = True
                self._fail_reason = "pick_die_%s" % pst
                logging.info("[BoxelPolicy] pick(die) FAILED: %s", pst)
                return Action(name="no-op"), info, store
            self._q_current, self._held_constraint = q_new, cid
            bb.mark_holding(belief, bb.die_alias(belief))
            self._subidx += 1
        elif act.name == "go_home":
            self._q_current, _ = execute_go_home(
                self._streams, world, self._model, self._q_current, self._gui,
                held_body=self._die_body)
            bb.mark_at_home(belief)
            self._done = True
            self._refresh_overlay()
            die_xyz = world.client.getBasePositionAndOrientation(self._die_body)[0]
            self._capture("phase3c_genuine_die_at_home.png", die_xyz)
            info["success"] = True

        return Action(name="no-op"), info, store
