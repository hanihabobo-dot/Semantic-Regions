#!/usr/bin/env python3
"""
Real PDDLStream Planner Integration for Semantic Boxel TAMP.

This module provides the interface between our Boxel TAMP system and
the actual PDDLStream solver with FastDownward backend.

Usage (from WSL):
    source wsl_env/bin/activate
    export PYTHONPATH=/path/to/pddlstream_lib
    python3 pddlstream_planner.py

PDDLStream path is added to sys.path via the hardcoded PDDLSTREAM_PATH constant below.
"""

import sys
import os
import time

# Add pddlstream to path (for WSL)
PDDLSTREAM_PATH = os.environ.get(
    'PDDLSTREAM_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pddlstream_lib')
)
if PDDLSTREAM_PATH not in sys.path:
    sys.path.insert(0, PDDLSTREAM_PATH)

import random
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Union

from pddlstream.algorithms.meta import solve
from pddlstream.language.constants import PDDLProblem, print_solution
from pddlstream.language.generator import from_gen_fn, from_fn
from pddlstream.utils import read

from boxel_data import BoxelRegistry, BoxelType
from streams import BoxelStreams, RobotConfig, Trajectory, Grasp
from robot_utils import REST_POSES


def read_pddl_file(filename: str) -> str:
    """Read PDDL file content."""
    pddl_dir = os.path.join(os.path.dirname(__file__), 'pddl')
    filepath = os.path.join(pddl_dir, filename)
    with open(filepath, 'r') as f:
        return f.read()


class PDDLStreamPlanner:
    """
    Real PDDLStream planner for Semantic Boxel TAMP.
    
    Uses PDDLStream with FastDownward for planning with continuous
    stream sampling for IK and motion planning.
    """
    
    def __init__(self, registry: BoxelRegistry, robot_id: int = None,
                 shadow_occluder_map: Dict[str, str] = None,
                 physics_client: int = None,
                 object_body_ids: Dict[str, int] = None,
                 support_body_ids: frozenset = None,
                 camera_pos: 'np.ndarray' = None,
                 tray_name: Optional[str] = None):
        """
        Initialize the planner.

        Args:
            registry: BoxelRegistry with scene boxels
            robot_id: PyBullet robot body ID (required for IK).
            shadow_occluder_map: Dict mapping shadow_id -> list of blocker
                object boxel IDs.  Includes ALL objects that block the
                camera's LOS to each shadow (audit #78).
            physics_client: PyBullet physics client ID (0 if default)
            object_body_ids: Mapping from object/boxel identifiers to
                PyBullet body IDs.  Passed to BoxelStreams so that
                compute_kin and plan_motion can exclude grasped objects
                from collision checks.
            support_body_ids: Body IDs of support surfaces (table, ground
                plane) ignored during pick/place endpoint checks.
            camera_pos: Fixed camera position [x, y, z].  Used to compute
                blocks_view_at facts for placement positions (audit #5).
            tray_name: Fixed-base tray support name (audit #49), or None.
                When set, _build_init emits (Obj <tray>) + (is_tray
                <tray>); (clear <tray>) and (on_table <tray>) fall out
                of the existing clear / on_table loop.
        """
        self.registry = registry
        self.robot_id = robot_id
        self.shadow_occluder_map = shadow_occluder_map or {}
        self.camera_pos = camera_pos
        self.tray_name = tray_name

        self.streams = BoxelStreams(
            registry, robot_id=robot_id, physics_client=physics_client,
            object_body_ids=object_body_ids,
            support_body_ids=support_body_ids,
        )
        self.home_config = self.streams.home_config
        
        # Load PDDL files (use PDDLStream-compatible untyped domain)
        self.domain_pddl = read_pddl_file('domain_pddlstream.pddl')
        self.stream_pddl = read_pddl_file('stream.pddl')

        # Audit #73 step 1(b): cache the most recent _build_init output
        # so the run logger can dump n_init_state_facts + per-predicate
        # counts at end-of-run.  Updated by create_problem (and
        # export_problem_pddl) on every call.
        self.last_init: Optional[List[Tuple]] = None

    def _get_stream_map(self) -> Dict[str, Any]:
        """
        Create the stream map connecting stream names to BoxelStreams generators.
        
        Each entry wraps a BoxelStreams method via PDDLStream's from_gen_fn.
        The streams produce real geometric objects (RobotConfig, Grasp,
        Trajectory) instead of placeholder strings.

        Returns:
            Dict mapping stream names to generator functions
        """
        return {
            'sample-grasp': from_gen_fn(self.streams.sample_grasp),
            'plan-motion': from_gen_fn(self.streams.plan_motion),
            'compute-kin': from_gen_fn(self.streams.compute_kin_solution),
            'compute-stack-kin': from_gen_fn(self.streams.compute_stack_kin_solution),
        }
    
    def create_problem(self,
                       target_objects: List[str],
                       goal: Tuple,
                       current_config: 'Union[RobotConfig, str]' = None,
                       known_empty_shadows: List[str] = None,
                       moved_occluders: Dict[str, str] = None,
                       observed_clear_regions: Optional[List[str]] = None,
                       visible_target_locations: Optional[Dict[str, str]] = None,
                       on_relations: Optional[Dict[str, str]] = None,
                       stackable_objects: Optional[List[str]] = None,
                       held_obj: Optional[str] = None) -> PDDLProblem:
        """
        Create a PDDLStream problem from current state.
        
        Args:
            target_objects: Objects to reason about
            goal: Goal as a tuple, e.g. ('holding', 'blue_object').
                  Passed directly to PDDLStream — must match domain predicates.
            current_config: Current robot config (RobotConfig preferred;
                string accepted for backward compat, wrapped automatically)
            known_empty_shadows: Shadows we've already checked (not containing target)
            moved_occluders: Dict mapping occluder_id -> destination_boxel_id
            observed_clear_regions: Regions explicitly observed clear; see
                _build_init() docstring (audit #67).
            visible_target_locations: Dict mapping target_name -> boxel_id for
                targets that are visible from the camera and do not require
                sensing.  Adds obj_at_boxel so pick is directly plannable.
            on_relations: Dict mapping stacked_obj -> support_obj for known
                stack relations (audit #30).  Only meaningful when
                ``stackable_objects`` is also supplied — else holding-goal
                runs would still pay the grounding cost of (on)
                facts they never use.
            stackable_objects: List of object/boxel IDs the planner may use
                as cubes for stacking.  When None (the typical holding-goal
                case), no (on ...) facts are emitted into init.  NOTE
                (audit #39): (clear ?o) is now emitted for every Obj
                unconditionally because pick requires it, irrespective
                of stackable_objects.

        Returns:
            PDDLProblem for PDDLStream solver
        """
        if current_config is None:
            current_config = self.home_config
        init = self._build_init(target_objects, current_config,
                                known_empty_shadows, moved_occluders,
                                observed_clear_regions,
                                visible_target_locations,
                                on_relations,
                                stackable_objects,
                                held_obj)
        self.last_init = init

        constant_map = {}
        stream_map = self._get_stream_map()
        
        return PDDLProblem(
            self.domain_pddl,
            constant_map,
            self.stream_pddl,
            stream_map,
            init,
            goal
        )
    
    def export_problem_pddl(self,
                            target_objects: List[str],
                            goal: Tuple,
                            current_config: 'Union[RobotConfig, str]' = None,
                            known_empty_shadows: List[str] = None,
                            moved_occluders: Dict[str, str] = None,
                            filepath: str = "pddl/problem_debug.pddl",
                            visible_target_locations: Optional[Dict[str, str]] = None) -> str:
        """
        Export the programmatically-built problem to a standalone PDDL file.

        Useful for debugging: inspect exactly what init state and goal the
        planner receives, without running PDDLStream. The output file matches
        domain_pddlstream.pddl's untyped format.

        Note: stream-certified predicates (kin_solution, motion, valid_grasp, etc.)
        are populated at runtime by PDDLStream streams and will NOT appear in
        this file. The problem is therefore not solvable by a plain PDDL
        planner — it's a snapshot of the static init state for inspection.

        Args:
            target_objects: Objects to reason about
            goal: Goal as a tuple, e.g. ('holding', 'blue_object')
            current_config: Current robot config (RobotConfig preferred)
            known_empty_shadows: Shadows already checked (empty)
            moved_occluders: Dict mapping occluder_id -> destination_boxel_id
            filepath: Output path (default: pddl/problem_debug.pddl)
            visible_target_locations: Dict mapping target_name -> boxel_id for
                visible targets (see _build_init docstring).

        Returns:
            The filepath written to
        """
        if current_config is None:
            current_config = self.home_config
        known_empty_shadows = known_empty_shadows or []
        moved_occluders = moved_occluders or {}

        init = self._build_init(target_objects, current_config,
                                known_empty_shadows, moved_occluders,
                                visible_target_locations=visible_target_locations)

        objects = set()
        for fact in init:
            for arg in fact[1:]:
                objects.add(str(arg))

        def format_fact(fact):
            if len(fact) == 1:
                return f"    ({fact[0]})"
            return f"    ({' '.join(str(a) for a in fact)})"

        def format_goal(g):
            if isinstance(g, str):
                return f"({g})"
            if g[0] == 'and':
                inner = ' '.join(format_goal(sub) for sub in g[1:])
                return f"(and {inner})"
            return f"({' '.join(str(a) for a in g)})"

        lines = [
            ";; Auto-generated problem file from PDDLStreamPlanner.export_problem_pddl()",
            ";; Static init state only — stream-certified facts are NOT included.",
            "",
            "(define (problem boxel-tamp-debug)",
            "  (:domain boxel-tamp)",
            "",
            "  (:objects",
        ]
        for obj in sorted(objects):
            lines.append(f"    {obj}")
        lines.append("  )")
        lines.append("")
        lines.append("  (:init")
        for fact in sorted(init, key=lambda f: (str(f[0]),) + tuple(str(a) for a in f[1:])):
            lines.append(format_fact(fact))
        lines.append("  )")
        lines.append("")
        lines.append(f"  (:goal {format_goal(goal)})")
        lines.append(")")
        lines.append("")

        output_path = os.path.join(os.path.dirname(__file__), filepath)
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        return output_path

    @staticmethod
    def _ray_aabb_intersects(origin: np.ndarray, endpoint: np.ndarray,
                             aabb_min: np.ndarray, aabb_max: np.ndarray) -> bool:
        """
        Slab-method ray-AABB intersection for the segment origin→endpoint.

        Returns True if the ray passes through [aabb_min, aabb_max] at a
        parameter 0 < t < 1 (i.e. the box is strictly between origin and
        endpoint, not behind origin or beyond endpoint).
        """
        direction = endpoint - origin
        with np.errstate(divide='ignore', invalid='ignore'):
            inv_dir = np.where(
                np.abs(direction) > 1e-10,
                1.0 / direction,
                np.copysign(1e10, direction),
            )
        t1 = (aabb_min - origin) * inv_dir
        t2 = (aabb_max - origin) * inv_dir
        t_enter = np.max(np.minimum(t1, t2))
        t_exit = np.min(np.maximum(t1, t2))
        return bool(t_enter <= t_exit and t_exit > 0.0 and t_enter < 1.0)

    def _compute_placement_view_blocks(self, shadow_ids, free_boxels):
        """
        For each (free_boxel, shadow) pair, test whether the free boxel
        lies in the camera→shadow line of sight.

        Casts a 5x5 ray grid from the camera through each shadow volume
        (same density as compute_shadow_blockers in execution.py)
        and tests each ray against every free boxel's AABB.

        Returns:
            Set of (free_boxel_id, shadow_id) pairs where placement would
            block the camera's view to the shadow.
        """
        cam = self.camera_pos
        blocking = set()
        n = 5

        for shadow_id in shadow_ids:
            sb = self.registry.get_boxel(shadow_id)
            if sb is None:
                continue
            min_c, max_c = sb.min_corner, sb.max_corner
            z_mid = (min_c[2] + max_c[2]) / 2.0

            ray_endpoints = []
            for xi in np.linspace(min_c[0], max_c[0], n):
                for yi in np.linspace(min_c[1], max_c[1], n):
                    ray_endpoints.append(np.array([xi, yi, z_mid]))

            for fb in free_boxels:
                for ep in ray_endpoints:
                    if self._ray_aabb_intersects(cam, ep,
                                                 fb.min_corner, fb.max_corner):
                        blocking.add((fb.id, shadow_id))
                        break

        return blocking

    def _build_init(self,
                    target_objects: List[str],
                    current_config: 'Union[RobotConfig, str]' = None,
                    known_empty_shadows: List[str] = None,
                    moved_occluders: Dict[str, str] = None,
                    observed_clear_regions: Optional[List[str]] = None,
                    visible_target_locations: Optional[Dict[str, str]] = None,
                    on_relations: Optional[Dict[str, str]] = None,
                    stackable_objects: Optional[List[str]] = None,
                    held_obj: Optional[str] = None) -> List[Tuple]:
        """
        Build the init state as a list of fact tuples.

        Shared by create_problem() and export_problem_pddl() to guarantee
        they produce identical init states.

        Args:
            target_objects: Objects to reason about
            current_config: Current robot config (RobotConfig or string)
            known_empty_shadows: Shadows already checked (empty)
            moved_occluders: Dict mapping occluder_id -> destination_boxel_id
                for occluders that have been moved aside
            observed_clear_regions: Boxel IDs that the robot has directly
                observed to NOT contain the target.  If ``None`` (default),
                ALL object and free-space boxels are treated as observed-clear
                — this is correct for the current scenario where a fixed
                overhead camera sees the entire table and any non-hidden
                target would be visible (audit #67).
                Supply an explicit set when extending to scenarios with
                limited sensor coverage where the robot has not yet
                observed all regions.
            visible_target_locations: Dict mapping target_name -> boxel_id for
                targets whose position is already known (camera-visible, no
                sensing required).  Adds ``obj_at_boxel`` and
                ``obj_at_boxel_KIF`` so the pick action's preconditions are
                directly satisfiable without a prior sense action.

        Returns:
            List of fact tuples for the init state
        """
        if current_config is None:
            current_config = self.home_config
        known_empty_shadows = known_empty_shadows or []
        moved_occluders = moved_occluders or {}
        visible_target_locations = visible_target_locations or {}

        init = []
        shadows = []

        for boxel in self.registry.boxels.values():
            init.append(('Boxel', boxel.id))

            if boxel.boxel_type == BoxelType.SHADOW:
                init.append(('is_shadow', boxel.id))
                shadows.append(boxel.id)

                if boxel.id in known_empty_shadows:
                    for obj in target_objects:
                        init.append(('obj_at_boxel_KIF', obj, boxel.id))

            elif boxel.boxel_type == BoxelType.OBJECT:
                init.append(('is_object', boxel.id))
                init.append(('Obj', boxel.id))
                if boxel.id in moved_occluders:
                    dest = moved_occluders[boxel.id]
                    init.append(('Boxel', dest))
                    init.append(('obj_at_boxel', boxel.id, dest))
                    init.append(('obj_at_boxel_KIF', boxel.id, dest))
                else:
                    init.append(('obj_at_boxel', boxel.id, boxel.id))
                    init.append(('obj_at_boxel_KIF', boxel.id, boxel.id))

                # KIF for target objects: only emit "known not here" if this
                # region has been observed clear.  When observed_clear_regions
                # is None, the fixed overhead camera covers the entire table,
                # so all visible boxels are observed (audit #67).
                if observed_clear_regions is None or boxel.id in observed_clear_regions:
                    for obj in target_objects:
                        init.append(('obj_at_boxel_KIF', obj, boxel.id))

            elif boxel.boxel_type == BoxelType.FREE_SPACE:
                init.append(('is_free_space', boxel.id))
                if boxel.on_surface is not None:
                    init.append(('on_surface', boxel.id))
                if observed_clear_regions is None or boxel.id in observed_clear_regions:
                    for obj in target_objects:
                        init.append(('obj_at_boxel_KIF', obj, boxel.id))

        # Static geometric facts: blocks_view_at(occ, occ_boxel, shadow).
        # Always added regardless of moved status — they describe geometry,
        # not current state. The derived predicate blocks_view combines these
        # with obj_at_boxel to determine actual view blockage.
        #
        # shadow_occluder_map is Dict[shadow_id, List[blocker_ids]] — includes
        # ALL objects that block the camera's LOS to each shadow, not just the
        # creating occluder (audit #78).
        if self.shadow_occluder_map:
            for shadow_id, blocker_ids in self.shadow_occluder_map.items():
                if isinstance(blocker_ids, str):
                    blocker_ids = [blocker_ids]
                for occluder_id in blocker_ids:
                    init.append(('blocks_view_at', occluder_id, occluder_id, shadow_id))
        else:
            for shadow_id in shadows:
                shadow_boxel = self.registry.get_boxel(shadow_id)
                if shadow_boxel and shadow_boxel.created_by_boxel_id:
                    occ_id = shadow_boxel.created_by_boxel_id
                    init.append(('blocks_view_at', occ_id, occ_id, shadow_id))

        # Placement-blocking facts (audit #5): for each free-space boxel,
        # check whether it lies in the camera→shadow line of sight.  Emitted
        # as blocks_view_at(obj, free_boxel, shadow) so that the existing
        # derived predicates (blocks_view / view_blocked / view_clear)
        # automatically prevent placements that re-block a cleared corridor.
        if self.camera_pos is not None and shadows:
            free_boxels = [
                b for b in self.registry.boxels.values()
                if b.boxel_type == BoxelType.FREE_SPACE
            ]
            placement_blocks = self._compute_placement_view_blocks(
                shadows, free_boxels
            )
            obj_boxel_ids = [
                b.id for b in self.registry.boxels.values()
                if b.boxel_type == BoxelType.OBJECT
            ]
            for (free_id, shadow_id) in placement_blocks:
                for obj_id in obj_boxel_ids:
                    init.append(('blocks_view_at', obj_id, free_id, shadow_id))

        for obj in target_objects:
            init.append(('Obj', obj))

        # audit #49 — tray as a stackable support.  No obj_at_boxel
        # emitted, so pick's (obj_at_boxel ?o ?b) precondition is
        # unsatisfiable for the tray => implicitly unpickable.
        # (clear tray) and (on_table tray) emerge from the all_obj_ids
        # loop further down.  (Boxel tray) is required so the move
        # action's (Boxel ?b) precondition is satisfied when the
        # destination is the tray (compute-stack-kin certifies
        # (config_for_boxel ?q tray)).
        if self.tray_name is not None:
            init.append(('Obj', self.tray_name))
            init.append(('Boxel', self.tray_name))
            init.append(('is_tray', self.tray_name))

        for tgt, boxel_id in visible_target_locations.items():
            init.append(('obj_at_boxel', tgt, boxel_id))
            init.append(('obj_at_boxel_KIF', tgt, boxel_id))
            init.append(('obj_pose_known', tgt))

        # Static boxel_fits facts (audit #102): do NOT use a PDDLStream test stream.
        # Adaptive search re-invokes test streams heavily across skeletons; a cheap
        # predicate became a bottleneck.  One pass here matches stream semantics.
        obj_ids = []
        for boxel in self.registry.boxels.values():
            if boxel.boxel_type == BoxelType.OBJECT:
                obj_ids.append(boxel.id)
        for obj in target_objects:
            if obj not in obj_ids:
                obj_ids.append(obj)
        # Containment candidates (audit #62): boxel_fits now gates BOTH
        # :action place (free-space destination) and :action sense
        # (shadow region that could hide ?o).  Same predicate, both
        # preconditions.  OBJECT boxels are excluded — not valid place
        # destinations (is_free_space false) and not valid sense regions
        # (view_clear only derives over shadows).
        #
        # SHADOW branch (audit #62 refinement): the AABB extent check
        # would over-emit because shadow_calculator subtracts the
        # occluder only along the dominant axis (audit #72 lateral
        # overhang).  test_target_can_hide_in_shadow adds a camera-ray
        # visibility check + stable-resting-pose check on top of the
        # extent test — only emit if a target placement exists where
        # all 8 of its AABB corners are actually occluded from the
        # camera AND the target rests stably on the table.
        free_ids = [
            b.id for b in self.registry.boxels.values()
            if b.boxel_type == BoxelType.FREE_SPACE
        ]
        shadow_ids = [
            b.id for b in self.registry.boxels.values()
            if b.boxel_type == BoxelType.SHADOW
        ]
        for o in obj_ids:
            for bid in free_ids:
                if self.streams.test_boxel_fits(o, bid):
                    init.append(('boxel_fits', o, bid))
            for bid in shadow_ids:
                if self.streams.test_target_can_hide_in_shadow(
                        o, bid, self.camera_pos):
                    init.append(('boxel_fits', o, bid))

        init.append(('Config', current_config))
        init.append(('at_config', current_config))
        if held_obj is None:
            init.append(('handempty',))
        else:
            # audit #58 — when the action loop broke mid-plan with the
            # gripper still holding ?o, replan from (holding ?o) instead
            # of dropping the cube.  sample-grasp re-fires on (Obj ?o)
            # to certify a fresh (Grasp ?g) + (valid_grasp ?o ?g) for
            # the next place/stack action.
            init.append(('holding', held_obj))

        # Stacking facts (audit #30 + #39).
        #   (clear ?o)  now emitted for EVERY object unconditionally,
        #               because pick requires it (audit #39 — prevents
        #               silent tower collapse when picking a stack-base).
        #               Holding-goal runs pay one atom per Obj of extra
        #               grounding cost, far cheaper than the
        #               :conditional-effects penalty debated in #30.
        #   (on ?o ?x)  still emitted ONLY when the caller supplied
        #               stackable_objects + on_relations (i.e. an
        #               explicit stack run).  Holding goals see no (on).
        on_relations = on_relations or {}
        supports_with_obj_on_top = set(on_relations.values())

        # Clear candidates = every Obj already in init (dedup across the
        # OBJECT-boxel loop above and the target_objects loop).  Using a
        # set to avoid duplicate (clear X) atoms when a target also has
        # an OBJECT boxel registered.  init contains tuples of varying
        # arity (e.g. ('handempty',), ('blocks_view_at', o, b, r)), so
        # we filter by first element length-safely rather than
        # destructuring.
        all_obj_ids = {fact[1] for fact in init
                       if len(fact) == 2 and fact[0] == 'Obj'}
        stacked_objs = set(on_relations.keys())
        for obj_id in all_obj_ids:
            if obj_id not in supports_with_obj_on_top:
                init.append(('clear', obj_id))
            # audit #41: a cube not stacked on another cube is
            # table-resting at planning time.  At a replan boundary
            # (handempty) is true, so no held cube exists here.
            if obj_id not in stacked_objs:
                init.append(('on_table', obj_id))

        if stackable_objects is not None:
            for stacked, support in on_relations.items():
                init.append(('on', stacked, support))

        random.shuffle(init)
        return init

    def plan(self,
             target_objects: List[str],
             goal: Tuple,
             current_config: 'Union[RobotConfig, str]' = None,
             known_empty_shadows: List[str] = None,
             moved_occluders: Dict[str, str] = None,
             max_time: float = 30.0,
             verbose: bool = True,
             observed_clear_regions: Optional[List[str]] = None,
             visible_target_locations: Optional[Dict[str, str]] = None,
             on_relations: Optional[Dict[str, str]] = None,
             stackable_objects: Optional[List[str]] = None,
             unit_costs: bool = False,
             held_obj: Optional[str] = None) -> Optional[List[Tuple]]:
        """
        Generate a plan using PDDLStream.

        Args:
            target_objects: Objects to reason about
            goal: Goal as a tuple, e.g. ('holding', 'blue_object')
            current_config: Current robot config (RobotConfig preferred)
            known_empty_shadows: Shadows already checked (empty)
            moved_occluders: Dict mapping occluder_id -> destination_boxel_id
            max_time: Maximum planning time in seconds
            verbose: Print planning info
            observed_clear_regions: Regions explicitly observed clear; see
                _build_init() docstring (audit #67).
            visible_target_locations: Dict mapping target_name -> boxel_id for
                visible targets (see _build_init docstring).
            on_relations: Known stack relations (see create_problem docstring).
            stackable_objects: Stack participants (see create_problem
                docstring).  Leave None for holding-goal runs.
            unit_costs: If True, override the domain's numeric
                ``(increase (total-cost) ...)`` effects and treat every
                action as cost 1 (PDDLStream solve(unit_costs=...)
                kwarg).  False keeps the domain costs (stack=2,
                others=1; see THESIS_NOTES §17).

        Returns:
            List of action tuples, or None if planning fails
        """
        if current_config is None:
            current_config = self.home_config
        problem = self.create_problem(target_objects, goal, current_config,
                                      known_empty_shadows, moved_occluders,
                                      observed_clear_regions,
                                      visible_target_locations,
                                      on_relations,
                                      stackable_objects,
                                      held_obj=held_obj)

        if verbose:
            print(f"\n--- PDDLStream Planning ---")
            print(f"Goal: {goal}")
            print(f"Max time: {max_time}s")
            print(f"Unit costs: {unit_costs}")

        # Audit #76 diagnostic — summarise init facts by predicate so we
        # can see at a glance which atoms PDDLStream has to work with.
        # Tagged [#76-diag] so the smart_filter passes it through
        # unchanged (matches the existing #60-diag convention).
        init_by_pred: Dict[str, int] = {}
        boxel_fits_by_obj: Dict[str, int] = {}
        view_clear_shadows: List[str] = []
        unknown_shadows: List[str] = []
        for fact in problem.init:
            if isinstance(fact, tuple) and fact:
                pred = str(fact[0])
                if pred == 'boxel_fits' and len(fact) >= 2:
                    boxel_fits_by_obj[str(fact[1])] = \
                        boxel_fits_by_obj.get(str(fact[1]), 0) + 1
            elif isinstance(fact, str):
                pred = fact
            else:
                pred = '<unknown>'
            init_by_pred[pred] = init_by_pred.get(pred, 0) + 1
        # Per-shadow view-clear count: how many of the unknown shadows
        # currently have at least one object blocking them?  A shadow with
        # zero blockers is immediately sense-able; one with many requires
        # relocating blockers first.
        shadow_ids = [str(f[1]) for f in problem.init
                       if isinstance(f, tuple) and len(f) == 2
                       and f[0] == 'is_shadow']
        known_KIF_pairs = {(str(f[1]), str(f[2])) for f in problem.init
                           if isinstance(f, tuple) and len(f) == 3
                           and f[0] == 'obj_at_boxel_KIF'}
        blocked_by_count: Dict[str, int] = {}
        for f in problem.init:
            if isinstance(f, tuple) and len(f) == 4 and f[0] == 'blocks_view_at':
                obj_id, b_id, region = str(f[1]), str(f[2]), str(f[3])
                # Only count if obj is currently AT b_id (i.e. the
                # blocks_view_at would actually fire as blocks_view).
                if (obj_id, b_id) in {(str(f2[1]), str(f2[2]))
                                       for f2 in problem.init
                                       if isinstance(f2, tuple)
                                       and len(f2) == 3
                                       and f2[0] == 'obj_at_boxel'}:
                    blocked_by_count[region] = blocked_by_count.get(region, 0) + 1
        for sid in shadow_ids:
            n_blockers = blocked_by_count.get(sid, 0)
            if n_blockers == 0:
                view_clear_shadows.append(sid)
            unknown_shadows.append(f"{sid}(blockers={n_blockers})")
        ordered = dict(sorted(init_by_pred.items(), key=lambda x: -x[1]))
        print(f"  [#76-diag] init facts: {sum(init_by_pred.values())} total, "
              f"by predicate: {ordered}")
        print(f"  [#76-diag] goal: {goal}")
        print(f"  [#76-diag] held_obj={held_obj}, max_time={max_time}s, "
              f"verbose={verbose}")
        print(f"  [#76-diag] boxel_fits per obj: "
              f"{dict(sorted(boxel_fits_by_obj.items()))}")
        print(f"  [#76-diag] shadows ({len(shadow_ids)} total, "
              f"{len(view_clear_shadows)} view-clear NOW): "
              f"{unknown_shadows}")
        # Per target, count how many view-clear unknown shadows accept it
        # (boxel_fits AND view_clear AND NOT obj_at_boxel_KIF).  If 0, the
        # planner can't ground a sense for that target → infeasibility.
        kif_set = {(str(f[1]), str(f[2])) for f in problem.init
                   if isinstance(f, tuple) and len(f) == 3
                   and f[0] == 'obj_at_boxel_KIF'}
        boxel_fits_pairs = {(str(f[1]), str(f[2])) for f in problem.init
                            if isinstance(f, tuple) and len(f) == 3
                            and f[0] == 'boxel_fits'}
        obj_ids_in_init = sorted({str(f[1]) for f in problem.init
                                   if isinstance(f, tuple) and len(f) == 2
                                   and f[0] == 'Obj'})
        sense_options_per_obj: Dict[str, List[str]] = {}
        obj_at_boxel_per_obj: Dict[str, List[str]] = {}
        for obj in obj_ids_in_init:
            sense_options_per_obj[obj] = [
                s for s in shadow_ids
                if (obj, s) in boxel_fits_pairs
                and s in view_clear_shadows
                and (obj, s) not in kif_set
            ]
            obj_at_boxel_per_obj[obj] = [
                str(f[2]) for f in problem.init
                if isinstance(f, tuple) and len(f) == 3
                and f[0] == 'obj_at_boxel'
                and str(f[1]) == obj
            ]
        print(f"  [#76-diag] sense_options per obj (view-clear AND fits AND "
              f"not-KIF): {sense_options_per_obj}")
        print(f"  [#76-diag] obj_at_boxel per obj: {obj_at_boxel_per_obj}")
        _plan_start_t = time.perf_counter()

        # Call PDDLStream solver
        solution = solve(
            problem,
            algorithm='adaptive',  # Best for TAMP problems
            max_time=max_time,
            unit_costs=unit_costs,
            verbose=verbose
        )

        plan, cost, certificate = solution
        _plan_elapsed = time.perf_counter() - _plan_start_t
        _plan_outcome = 'plan_found' if plan is not None else 'no_plan'
        print(f"  [#76-diag] outcome={_plan_outcome}, "
              f"elapsed={_plan_elapsed:.3f}s, "
              f"plan_len={len(plan) if plan else 0}, cost={cost}")

        if verbose:
            print_solution(solution)
        
        if plan is None:
            return None
        
        # Convert plan to our action format
        actions = []
        for action in plan:
            action_name = action.name
            action_args = action.args
            actions.append((action_name,) + tuple(action_args))
        
        return actions


def test_planner():
    """
    Standalone planner test — requires a PyBullet environment with a loaded
    robot.  Run test_full_pipeline.py instead for the full integration test.

    Heuristic IK fallback has been removed (audit #80); a real robot_id
    is now mandatory for IK-dependent streams.
    """
    print("="*60)
    print("Testing PDDLStream Planner")
    print("="*60)
    print("ERROR: Standalone planner test requires a loaded PyBullet robot.")
    print("       Run test_full_pipeline.py for full integration testing.")
    return False


if __name__ == "__main__":
    success = test_planner()
    sys.exit(0 if success else 1)
