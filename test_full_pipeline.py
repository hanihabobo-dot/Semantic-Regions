#!/usr/bin/env python3
"""
Full Pipeline Test: PDDLStream Planning + PyBullet Execution with REPLANNING

This uses the REAL PDDLStream planner with proper partial observability:
1. Robot doesn't know where target is (hidden in a shadow)
2. Must push occluder aside to reveal shadow
3. Sense shadow to check for object
4. If not found: REPLAN with updated belief
5. Repeat until found, then pick

Run from WSL:
    source wsl_env/bin/activate
    export DISPLAY=:0
    export LIBGL_ALWAYS_SOFTWARE=1
    export PYTHONPATH=/path/to/pddlstream_lib
    python3 test_full_pipeline.py

Or with no GUI (for testing):
    python3 test_full_pipeline.py --no-gui

GUI on but no boxel wireframes/labels (PyBullet only):
    python3 test_full_pipeline.py --no-boxel-viz

PDDLStream path is added to sys.path via the hardcoded PDDLSTREAM_PATH constant below.

Architecture (post-#26 refactor, 2026-04-19):
    belief.py       BeliefState — partial-observability bookkeeping.
    execution.py    execute_pick / execute_place / sense_shadow_raycasting /
                    compute_shadow_blockers / release_held_object_in_place.
    reboxelize.py   reboxelize_free_space — octree+merge diff after mutations.
    THIS FILE       Phase 1-6 orchestration + CLI.  Reads top-down: setup,
                    boxel calc, registry, scenario selection, replan loop,
                    results.  Action handlers live next to the loop because
                    they own the cross-cutting bookkeeping (registry, viz,
                    belief, planner state).
"""

import sys
import os
import argparse
import json
import random
import time
from typing import Any, Dict, Optional

PDDLSTREAM_PATH = os.environ.get(
    'PDDLSTREAM_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pddlstream_lib')
)
if os.path.exists(PDDLSTREAM_PATH):
    sys.path.insert(0, PDDLSTREAM_PATH)

import numpy as np
import pybullet as p

from boxel_env import (BoxelTestEnv, SceneConfig,
                       default_scene, mixed_shapes_scene,
                       scalability_scene, stack_scene)
from boxel_data import BoxelData, BoxelRegistry, BoxelType
from cell_merger import merge_free_space_cells
from free_space import split_free_boxel  # noqa: F401  (kept for future use)
from pddlstream_planner import PDDLStreamPlanner
from streams import RobotConfig
from robot_utils import (RenderingLock, move_robot_smooth,
                         detect_execution_collisions)
from run_logger import RunLogger
from visualization import BoxelVisualizer

from belief import BeliefState
from reboxelize import reboxelize_free_space
from execution import (sense_shadow_raycasting, compute_shadow_blockers,
                       release_held_object_in_place,
                       execute_pick, execute_place, execute_stack)


def goal_satisfied(goal, on_relations=None, target_found=False) -> bool:
    """
    Generic goal-predicate evaluator for the orchestration loop (audit #30).

    Decoupled from BeliefState because stack goals don't need a belief
    state at all — there are no shadows.  The two flavours we support:

      ('holding', obj)   — delegates to ``target_found`` (set by the
                           pick handler / sense outcome).
      ('on', a, b)       — checked against ``on_relations``, the
                           planner-side picture of the live stack
                           maintained by the stack action handler.
      ('and', g1, g2,..) — conjunction; recurses.

    Reading from ``on_relations`` rather than re-deriving from PyBullet
    AABBs each tick avoids races with in-flight settling — by the time
    the loop polls, execute_stack has already let physics settle and
    written the canonical relation.
    """
    on_relations = on_relations or {}
    if not isinstance(goal, tuple):
        return False
    head = goal[0]
    if head == 'and':
        return all(goal_satisfied(sub, on_relations, target_found)
                   for sub in goal[1:])
    if head == 'holding':
        return target_found
    if head == 'on':
        a, b = str(goal[1]), str(goal[2])
        return on_relations.get(a) == b
    return False


def build_stack_goal(stackable_objects, stack_height, rng=None):
    """
    Pick ``stack_height`` distinct objects from ``stackable_objects`` and
    return a goal for a tower of that height (audit #30).

    For height H the goal is::

        ('and', ('on', t_1, t_2), ..., ('on', t_{H-1}, t_H))

    where ``t_1`` is the top and ``t_H`` is the base resting on the
    table.  The base is implicitly table-resting — the domain doesn't
    represent the table as an object.

    Args:
        stackable_objects: Object IDs the planner may use as cubes.
        stack_height: Total cubes in the stack (>= 2).  Height 1 is
            rejected because it collapses to (clear t), which the
            planner trivially satisfies — use --goal holding instead.
        rng: ``random.Random`` for reproducible shuffling.  Defaults to
            module ``random`` so the existing --seed plumbing keeps
            working unchanged.
    """
    if stack_height < 2:
        raise ValueError(
            f"--stack-height must be >= 2 for a meaningful goal "
            f"(got {stack_height}).  Use --goal holding for a single object."
        )
    if len(stackable_objects) < stack_height:
        raise ValueError(
            f"Need at least {stack_height} stackable objects for "
            f"--stack-height={stack_height}, have {len(stackable_objects)}. "
            f"Increase --n-objects."
        )

    rng = rng or random
    chosen = list(stackable_objects)
    rng.shuffle(chosen)
    chosen = chosen[:stack_height]

    pairs = [('on', chosen[i], chosen[i + 1])
             for i in range(stack_height - 1)]
    if len(pairs) == 1:
        return pairs[0]
    return ('and',) + tuple(pairs)


def main(gui=True, run_logger=None, scene_config=None,
         draw_boxel_overlays=True, show_free=False,
         goal_kind='holding', stack_height=2,
         run_config: Optional[Dict[str, Any]] = None):
    print("=" * 60)
    print("FULL PIPELINE: PDDLStream + Replanning")
    print("=" * 60)

    # Echo the run configuration so saved logs are self-documenting:
    # later baseline-vs-feature comparisons (audit #30 keep/kill) need
    # to know which flags produced these timings.
    if run_config:
        print("\n--- Run configuration ---")
        for k, v in run_config.items():
            print(f"  {k:18s} = {v}")

    # =========================================================
    # PHASE 1: Setup Environment
    # =========================================================
    print("\n--- Phase 1: Environment Setup ---")
    env = BoxelTestEnv(gui=gui, scene_config=scene_config)

    # Let settle: 50 steps at 240 Hz ≈ 0.2 s.  Enough for the loaded
    # Panda + cubes to reach static equilibrium after spawning.
    for _ in range(50):
        env.step_simulation()
    env.update_object_positions()

    # Audit #29: single-shot sanity log.  Placement in
    # ``_hidden_xy_positions`` already uses 8-corner raycasts against
    # the spawned occluders, so if the scene loaded at all the hidden
    # targets were raycast-verified occluded at spawn time.  We still
    # run one ``oracle_detect_objects`` pass AFTER physics settle to
    # catch any drift, but we do NOT retry — a mismatch here is either
    # a placement-vs-oracle logic bug worth investigating, or sub-mm
    # settling drift that does not affect downstream behaviour.
    required_hidden = int(getattr(scene_config, 'n_hidden_targets', 0) or 0)
    if required_hidden > 0:
        visible, _ = env.oracle_detect_objects()
        target_names = [
            name for name, info in env.objects.items()
            if not info.is_occluder
            and name not in ("plane", "table", "robot")
        ]
        hidden_now = sum(1 for t in target_names if t not in visible)
        if hidden_now >= required_hidden:
            print(f"  Hidden-target guarantee OK: {hidden_now}/"
                  f"{len(target_names)} hidden "
                  f"(requested >= {required_hidden}, "
                  f"seed={scene_config.seed}).")
        else:
            print(f"  [warn] Hidden-target post-spawn check: "
                  f"{hidden_now}/{required_hidden} hidden "
                  f"(placement was raycast-verified; mismatch likely "
                  f"from physics settling drift). Continuing without "
                  f"retry.", file=sys.stderr)

    robot_id = env.objects["robot"].object_id
    print(f"Robot ID: {robot_id}")

    # =========================================================
    # PHASE 2: Boxel Calculation (fast, no visualization)
    # =========================================================
    # Perception pipeline:
    #   1. Camera observation → occupied boxels (objects + shadows they cast)
    #   2. Free-space generation → fills unoccupied table surface with boxels
    #   3. Cell merging → collapses adjacent free-space cells into fewer,
    #      larger boxels so the planner's search space stays tractable
    # The combined set gives the planner a complete spatial model of the
    # table surface: where objects are, where shadows are, and where
    # the robot can safely place things.
    print("\n--- Phase 2: Calculating Boxels ---")
    obs = env.get_camera_observation()
    all_known = obs.boxels
    free_boxels = env.generate_free_space(all_known, visualize=False)
    merged_free = merge_free_space_cells(free_boxels)
    # Free-space geometry is stateless until here; tag table-contact info
    # so the planner can emit (on_surface ?b) for place actions (audit #35).
    env.annotate_free_space_surface(merged_free)
    all_boxels = all_known + merged_free
    print(f"  Calculated {len(all_boxels)} boxels")

    # =========================================================
    # PHASE 3: Create Registry
    # =========================================================
    # The registry is the single source of truth for spatial reasoning.
    # It assigns stable IDs, classifies boxels by type, and records
    # parent relationships (which occluder created which shadow).
    # Both the PDDL planner and the execution layer reference the same
    # registry, ensuring symbolic names map to consistent geometry.
    print("\n--- Phase 3: Creating BoxelRegistry ---")
    # Post-#35: producers emit BoxelData with semantic IDs (object name for
    # OBJECT, "shadow_of_<name>" for SHADOW) and parent linkage already set.
    # Free-space cells arrive with empty IDs; add_boxel assigns "free_NNN".
    registry = BoxelRegistry()
    for bd in all_boxels:
        registry.add_boxel(bd)
    registry.save_to_json("boxel_data.json")
    if run_logger:
        run_logger.save_artefact("boxel_data.json")

    # Extract the two categories the planner cares about:
    # - shadows: regions that might hide the target (must be sensed)
    # - occluders: objects blocking those shadows (must be relocated first)
    shadows = [b.id for b in registry.boxels.values() if b.boxel_type == BoxelType.SHADOW]
    occluders = [b.id for b in registry.boxels.values() if b.boxel_type == BoxelType.OBJECT]
    print(f"  {len(registry.boxels)} boxels, {len(shadows)} shadows, {len(occluders)} occluders")

    viz = None
    if gui and draw_boxel_overlays:
        viz = BoxelVisualizer()
        viz.draw_registry(registry, duration=0, label_size=1.0,
                          skip_free=not show_free)

    # =========================================================
    # PHASE 4: Hidden Object Scenario (ORACLE ONLY)
    # =========================================================
    # This phase establishes ground truth that the ROBOT does NOT have
    # access to.  We use AABB containment (is the target inside a shadow
    # volume?) to verify the scene is valid — at least one target must be
    # genuinely occluded.  The robot only discovers this through sensing.
    print("\n--- Phase 4: Hidden Object Scenario ---")

    all_targets = [
        name for name, info in env.objects.items()
        if not info.is_occluder and name not in ("plane", "table", "robot")
    ]

    # AABB containment test: a target is "in" a shadow if its position
    # falls within the shadow boxel's axis-aligned bounding box.
    # This is an oracle check — it uses the simulator's ground-truth
    # positions that the robot cannot directly observe.
    target_to_shadow = {}
    for tname in all_targets:
        tpos = np.array(env.objects[tname].position)
        for shadow_id in shadows:
            sb = registry.get_boxel(shadow_id)
            if sb and np.all(tpos >= sb.min_corner) and np.all(tpos <= sb.max_corner):
                target_to_shadow[tname] = shadow_id
                break

    visible_target_locations = {}
    on_relations: Dict[str, str] = {}      # stacked_obj -> support_obj
    stack_target_objects = []              # populated only for --goal stack

    if goal_kind == 'holding':
        if target_to_shadow:
            target_name = random.choice(list(target_to_shadow.keys()))
            oracle_hidden_shadow = target_to_shadow[target_name]
            print(f"  Target: {target_name}")
            print(f"  ORACLE: Actually hidden in {oracle_hidden_shadow} (ground-truth AABB containment)")
            print(f"  Robot must search to find it!")
        else:
            # No target is hidden — all are visible from the camera.
            # Pick a random visible target and resolve its boxel ID so the
            # planner can generate a direct move→pick plan without sensing.
            print(f"  No targets hidden — all visible from camera.")
            target_name = random.choice(all_targets)
            for boxel in registry.boxels.values():
                if boxel.object_name == target_name:
                    visible_target_locations[target_name] = boxel.id
                    break
            if target_name in visible_target_locations:
                print(f"  Target: {target_name} at boxel "
                      f"{visible_target_locations[target_name]} (direct pick)")
            else:
                print(f"  WARNING: Target {target_name} has no boxel in registry")
                env.close()
                return False
        goal = ('holding', target_name)
    elif goal_kind == 'stack':
        # stack_scene has no occluders → no shadows → no sensing needed.
        # Every cube is its own visible target so the planner can pick
        # any of them without a search loop.
        stack_target_objects = list(all_targets)
        for tname in stack_target_objects:
            for boxel in registry.boxels.values():
                if boxel.object_name == tname:
                    visible_target_locations[tname] = boxel.id
                    break
        goal = build_stack_goal(stack_target_objects, stack_height)
        # ``target_name`` is still referenced in the holding-style log
        # paths (planner export, replan loop banner).  Pick the top of
        # the requested tower as a representative — it matches the
        # holding semantics ("the object the user cares about").
        if isinstance(goal, tuple) and goal[0] == 'and':
            target_name = str(goal[1][1])
        else:
            target_name = str(goal[1])
        print(f"  Stack goal: {goal}")
        print(f"  Stackable cubes: {stack_target_objects}")
    else:
        raise ValueError(f"Unsupported --goal '{goal_kind}'. "
                         "Add a builder before passing it through.")

    # Build shadow → [blocker_ids] mapping via raycasting (audit #78).
    # A shadow can be blocked by MORE than just the object that created it
    # (e.g. a second occluder drifts into the line of sight after spawning).
    # Raycasting from the camera through each shadow volume catches all
    # actual blockers, not just the geometrically-derived creator.
    shadow_occluder_map = compute_shadow_blockers(
        env.camera_position, registry, shadows, occluders, env
    )
    # Fallback: if raycasting found no blockers for a shadow (can happen
    # when the occluder sits exactly at a ray grid boundary), use the
    # parent relationship recorded during boxel creation.
    for shadow_id in shadows:
        if shadow_id not in shadow_occluder_map or not shadow_occluder_map[shadow_id]:
            shadow_boxel = registry.get_boxel(shadow_id)
            if shadow_boxel and shadow_boxel.created_by_boxel_id:
                shadow_occluder_map.setdefault(shadow_id, []).append(
                    shadow_boxel.created_by_boxel_id
                )
            else:
                print(f"  WARNING: Shadow {shadow_id} has no linked occluder — skipping")

    # Bridge between the symbolic (PDDL) and physical (PyBullet) worlds.
    # The planner reasons about boxel IDs like "obj_000"; execution needs
    # PyBullet body IDs and names like "red_object".  This mapping lets the
    # action dispatcher translate plan parameters into simulator calls.
    boxel_to_pybullet = {}
    for boxel in registry.boxels.values():
        if boxel.object_name and boxel.object_name in env.objects:
            boxel_to_pybullet[boxel.id] = {
                'name': boxel.object_name,
                'pybullet_id': env.objects[boxel.object_name].object_id,
                'position': np.array(env.objects[boxel.object_name].position)
            }

    print(f"  Boxel->PyBullet mapping: {len(boxel_to_pybullet)} objects")

    # =========================================================
    # PHASE 5: Planning with Replanning Loop
    # =========================================================
    # Core idea: plan optimistically (assume target is in the first shadow),
    # execute until a sense action reveals new information, then replan with
    # updated beliefs.  This is a sense-plan-act loop with lazy replanning.
    print("\n--- Phase 5: Planning with Replanning ---")

    # Collision-aware planning needs to know which PyBullet bodies are
    # movable objects (to exclude the grasped object from self-collision)
    # vs. immovable support surfaces (always present in collision checks).
    # Both human-readable names ("red_object") and boxel IDs ("obj_000")
    # map to the same body ID, so streams can look up either form.
    object_body_ids = {}
    for name, obj_info in env.objects.items():
        if name not in ("plane", "table", "robot"):
            object_body_ids[name] = obj_info.object_id
    for boxel in registry.boxels.values():
        if boxel.object_name and boxel.object_name in object_body_ids:
            object_body_ids[boxel.id] = object_body_ids[boxel.object_name]

    support_body_ids = frozenset({
        env.objects["plane"].object_id,
        env.objects["table"].object_id,
    })

    body_id_to_name = {info.object_id: name
                       for name, info in env.objects.items()}

    # Initialise belief (all shadows unknown) and the planner.
    # The planner is stateless between calls — all context it needs
    # (known-empty shadows, moved occluders, current config) is passed
    # in each plan() call so replanning always starts from scratch with
    # the latest world state.
    belief = BeliefState(shadows, target_name)
    planner = PDDLStreamPlanner(registry, robot_id=robot_id,
                                shadow_occluder_map=shadow_occluder_map,
                                physics_client=env.client_id,
                                object_body_ids=object_body_ids,
                                support_body_ids=support_body_ids,
                                camera_pos=env.camera_position)

    # The planner needs to reason about every object that may participate
    # in the goal.  For 'holding' that's just the chosen target; for
    # 'stack' it's every cube in the requested tower.
    planner_target_objects = (
        stack_target_objects if goal_kind == 'stack' else [target_name]
    )

    problem_path = planner.export_problem_pddl(
        target_objects=planner_target_objects,
        goal=goal,
        visible_target_locations=visible_target_locations,
    )
    print(f"  Exported initial problem to {problem_path}")
    if run_logger:
        run_logger.save_artefact(problem_path, "problem_initial.pddl")

    boxel_centers = {b.id: b.center for b in registry.boxels.values()}

    plan_count = 0
    # Per-call planner.plan() durations (audit #30 baseline timing).
    # The cumulative total is what matters for keep/kill on stack-goal.
    total_plan_time = 0.0
    plan_times = []
    # --- Reactive replanning loop ---
    # Design: the PDDL sense action is OPTIMISTIC — it assumes the
    # target will be found.  When execution reveals otherwise (empty or
    # still-blocked), we break out of the current plan and replan with
    # the updated belief.  This is cheaper than encoding every possible
    # sensing outcome in PDDL.
    #
    # Termination: each replan eliminates at least one shadow (or retries
    # a blocked one up to 3 times), so worst case is bounded.  Budget:
    # 4 attempts per shadow + 1 final pick.  Stack has no shadows; size
    # the budget by stack height instead — 2 PDDL actions per cube
    # (pick + stack) plus a small slack for retries (audit #30).
    if goal_kind == 'stack':
        max_replans = 2 * stack_height + 3
    else:
        max_replans = 4 * len(shadows) + 1
    grasp_constraint_id = None       # set during pick, cleared after place
    held_body_id = None              # PyBullet body ID of the held object
    held_object_boxel_id = None      # registry boxel ID of the held object
    exit_reason = None               # tracks why the loop ended for Phase 6
    current_config = planner.home_config  # robot's last known joint config
    # Detect infinite-replan loops: if sensing the same shadow stays
    # "still_blocked" 3+ times, give up on it (audit #78c).
    blocked_counts = {}  # shadow_id → consecutive-block count

    def _loop_done() -> bool:
        # Holding goals stop when belief.target_found flips; stack goals
        # stop when every (on a b) clause is satisfied (audit #30).
        if goal_kind == 'holding':
            return belief.is_target_found()
        return goal_satisfied(goal, on_relations)

    while not _loop_done() and plan_count < max_replans:
        plan_count += 1
        unknown_shadows = belief.get_unknown_shadows()
        known_empty = belief.get_known_empty_shadows()

        print(f"\n=== PLAN #{plan_count} ===")
        if goal_kind == 'holding':
            print(f"Unknown shadows remaining: {len(unknown_shadows)}")
            if not unknown_shadows:
                exit_reason = "all_searched"
                print("ERROR: Searched all shadows but target not found!")
                break
        else:
            print(f"Stack progress: {on_relations} (goal {goal})")

        # --- Drop any object still in the gripper before replanning -------
        # The action loop can `break` mid-plan (sense failed, IK failed,
        # missing shadow, etc.) before reaching the planned `place`.  When
        # that happens the constraint from the prior `pick` is still
        # attached, but the planner's _build_init unconditionally emits
        # ('handempty',) and will happily plan another `pick` — leading to
        # two objects dangling from the EE.  Release the held object in
        # place so reality matches the planner's assumption.  Retry on
        # failure (object stuck between fingers, constraint not removed,
        # etc.); after exhausting retries, abort the run rather than carry
        # on with an inconsistent world state.
        if held_body_id is not None:
            drop_ok, drop_state = release_held_object_in_place(
                env=env,
                robot_id=robot_id,
                gui=gui,
                grasp_constraint_id=grasp_constraint_id,
                held_body_id=held_body_id,
                held_object_boxel_id=held_object_boxel_id,
                registry=registry,
                boxel_centers=boxel_centers,
                boxel_to_pybullet=boxel_to_pybullet,
                body_id_to_name=body_id_to_name,
                viz=viz,
                shadows=shadows,
                occluders=occluders,
                planner=planner,
                max_attempts=3,
            )
            grasp_constraint_id = None
            held_body_id = None
            held_object_boxel_id = None
            if drop_state.get("shadow_occluder_map") is not None:
                shadow_occluder_map = drop_state["shadow_occluder_map"]
            if drop_state.get("current_config") is not None:
                current_config = drop_state["current_config"]
            if not drop_ok:
                exit_reason = "drop_failed"
                print("ERROR: Could not release held object after retries — "
                      "aborting to avoid double-grasp.")
                break

        # Ensure the free-space partition is consistent before the planner
        # reads the registry (audit #25).  After a place action,
        # update_after_place sets registry.dirty because the consumed
        # free boxel is gone but no replacement exists yet.  If a sense
        # action already triggered reboxelization (clearing the flag),
        # this is a no-op — avoiding the double octree+merge cost.
        if registry.dirty:
            reboxelize_free_space(registry, env, boxel_centers, viz, show_free)

        # Disable rendering for the entire planning phase (audit #60).
        # All IK and collision-check calls inside planner.plan() nest
        # harmlessly via RenderingLock's reference count.
        with RenderingLock(env.client_id):
            plan_t0 = time.perf_counter()
            plan = planner.plan(
                target_objects=planner_target_objects,
                goal=goal,
                current_config=current_config,
                known_empty_shadows=known_empty,
                moved_occluders=dict(belief.occluders_moved),
                max_time=120.0,
                verbose=False,
                visible_target_locations=visible_target_locations,
                # on/clear facts only emitted into init when stackable
                # objects is supplied — holding-goal runs pay nothing.
                on_relations=(on_relations if goal_kind == 'stack'
                              else None),
                stackable_objects=(stack_target_objects
                                   if goal_kind == 'stack' else None),
            )
            plan_dt = time.perf_counter() - plan_t0
        total_plan_time += plan_dt
        plan_times.append(plan_dt)
        print(f"  [timing] planner.plan() #{plan_count}: {plan_dt:.3f}s "
              f"(cumulative {total_plan_time:.3f}s)")

        if gui:
            env.refresh_debug_camera_views()

        if plan is None:
            exit_reason = "planner_failed"
            print("ERROR: No plan found!")
            break

        print(f"Plan: {len(plan)} actions")
        for i, action in enumerate(plan):
            print(f"  {i+1}. {action[0]}")

        # Safety gate: during planning, streams may emit "heuristic"
        # configs (e.g. boxel-center approximations) when no robot_id is
        # available.  These are geometrically reasonable but not IK-valid,
        # so executing them would drive the real arm to arbitrary poses.
        for action in plan:
            for param in action[1:]:
                if isinstance(param, RobotConfig) and param.is_heuristic:
                    raise RuntimeError(
                        f"Plan contains heuristic config '{param.name}' — "
                        f"cannot execute kinematically invalid configurations. "
                        f"Ensure BoxelStreams has a valid robot_id."
                    )

        # --- Action dispatcher ---
        # Each PDDL action maps to a physical execution routine.  The
        # loop breaks early on two conditions:
        #   • sense reveals new info → replan with updated belief
        #   • IK failure → replan from current config
        for i, action in enumerate(plan):
            action_name = action[0]
            params = action[1:]

            print(f"\n  Executing: {action_name}")

            if action_name == 'move':
                # MOVE: follow a collision-free trajectory from q1 to q2.
                # The trajectory was computed by the plan_motion stream
                # using RRT; we replay its waypoints with smooth
                # interpolation for visual fidelity and physics stability.
                q1, q2, dest_boxel_id, traj = params
                print(f"    Moving to {dest_boxel_id} ({len(traj.waypoints)} waypoints)...")

                for wp in traj.waypoints[1:]:
                    move_robot_smooth(robot_id, wp.joint_positions,
                                      gui, steps=30)
                # Read the arm's true joint state after motion completes.
                # Position control can undershoot the IK target; if we
                # used the planned q2 directly, errors would accumulate
                # across chained actions and confuse the next replan
                # (audit #86).
                actual_joints = np.array(
                    [p.getJointState(robot_id, i)[0] for i in range(7)]
                )
                current_config = RobotConfig(
                    joint_positions=actual_joints,
                    name=q2.name
                )
                detect_execution_collisions(
                    robot_id, env.client_id,
                    held_body_id=held_body_id,
                    support_body_ids=support_body_ids,
                    label=f"move to {dest_boxel_id}",
                    body_names=body_id_to_name)
                print(f"    -> Arrived at {dest_boxel_id}")

            elif action_name == 'sense':
                # SENSE: cast rays from the fixed camera through the
                # shadow volume to determine what's inside.
                # Three possible outcomes drive the control flow:
                #   found_target  → belief updated, plan continues to pick
                #   clear_but_empty → shadow eliminated, break to replan
                #   still_blocked → occluder not fully cleared, break to replan
                obj, shadow_id = params
                print(f"    Sensing {shadow_id} (fixed camera)...")

                # Retract arm to home so it doesn't block the camera's
                # line of sight to the shadow region (audit #79, #3 deferred).
                # home_joints = planner.home_config.joint_positions
                # move_robot_smooth(robot_id, home_joints, gui, steps=40)
                # current_config = planner.home_config

                shadow_boxel = registry.get_boxel(str(shadow_id))
                if shadow_boxel is None:
                    print(f"    WARNING: Shadow '{shadow_id}' not found in registry. Replanning...")
                    break

                target_pybullet_id = env.objects[target_name].object_id
                occluder_pybullet_ids = set()
                for blocker_bid in shadow_occluder_map.get(str(shadow_id), []):
                    if blocker_bid in boxel_to_pybullet:
                        occluder_pybullet_ids.add(boxel_to_pybullet[blocker_bid]['pybullet_id'])

                sense_outcome, blocked_fraction, detected_bodies = sense_shadow_raycasting(
                    env.camera_position,
                    shadow_boxel,
                    target_pybullet_id,
                    occluder_pybullet_ids,
                    robot_id=robot_id,
                    support_body_ids=support_body_ids,
                )

                if sense_outcome == "found_target":
                    belief.mark_sensed(str(shadow_id), found=True)
                    print(f"    *** TARGET FOUND in {shadow_id}! (ray-cast) ***")
                elif sense_outcome in ("clear_but_empty", "contains_nontarget"):
                    sid_str = str(shadow_id)
                    belief.mark_sensed(sid_str, found=False)

                    registry.remove_boxel(sid_str)
                    if sid_str in shadows:
                        shadows.remove(sid_str)
                    shadow_occluder_map.pop(sid_str, None)

                    if sense_outcome == "contains_nontarget":
                        # Non-target objects discovered inside the shadow.
                        # Create OBJECT + SHADOW boxels for each one so the
                        # planner knows about them on the next replan.
                        discovered_names = [
                            body_id_to_name[bid]
                            for bid in detected_bodies
                            if bid in body_id_to_name
                        ]
                        print(f"    Shadow {shadow_id} contains non-target "
                              f"object(s): {discovered_names}")

                        for obj_name in discovered_names:
                            obj_info = env.objects.get(obj_name)
                            if obj_info is None:
                                continue
                            bid = obj_info.object_id
                            aabb_min, aabb_max = p.getAABB(bid)
                            aabb_min = np.array(aabb_min)
                            aabb_max = np.array(aabb_max)

                            obj_bd = BoxelData(
                                id=obj_name,
                                boxel_type=BoxelType.OBJECT,
                                min_corner=aabb_min,
                                max_corner=aabb_max,
                                object_name=obj_name,
                                is_occluder=False,
                                on_surface=(
                                    "table"
                                    if aabb_min[2] <= env.table_surface_height + 0.01
                                    else None
                                ),
                                surface_z=env.table_surface_height,
                            )
                            registry.add_boxel(obj_bd)
                            boxel_centers[obj_name] = obj_bd.center
                            object_body_ids[obj_name] = bid
                            boxel_to_pybullet[obj_name] = {
                                'name': obj_name,
                                'pybullet_id': bid,
                                'position': np.array(obj_info.position),
                            }

                            # Compute shadow for this newly visible object.
                            # ShadowCalculator now accepts BoxelData directly,
                            # so we can pass obj_bd and the OBJECT registry
                            # entries with no conversion (audit #35).
                            other_solids = [
                                bd for bd in registry.boxels.values()
                                if (bd.boxel_type == BoxelType.OBJECT
                                    and bd.id != obj_name)
                            ]
                            shadow_parts = env.shadow_calculator.calculate_shadow_boxel(
                                obj_bd, other_solids)

                            if shadow_parts:
                                obj_bd.is_occluder = True
                                table_z = env.table_surface_height
                                for sp in shadow_parts:
                                    sp.created_by_boxel_id = obj_name
                                    sp.created_by_object = obj_name
                                    sp.on_surface = (
                                        "table"
                                        if sp.min_corner[2] <= table_z + 0.01
                                        else None
                                    )
                                    sp.surface_z = table_z
                                    s_id = registry.add_boxel(sp)  # auto-assigns "shadow_NNN"
                                    obj_bd.shadow_boxel_ids.append(s_id)
                                    shadows.append(s_id)
                                    shadow_occluder_map[s_id] = [obj_name]
                                    boxel_centers[s_id] = sp.center

                            if viz is not None:
                                viz.draw_boxel_data(obj_bd)
                                for s_id in obj_bd.shadow_boxel_ids:
                                    s_bd = registry.get_boxel(s_id)
                                    if s_bd is not None:
                                        viz.draw_boxel_data(s_bd)

                            print(f"      -> {obj_name}: object boxel + "
                                  f"{len(shadow_parts)} shadow(s)")
                    else:
                        print(f"    Target NOT in {shadow_id} "
                              f"(ray-cast: view clear but no target hit)")

                    # Re-run octree + merge now that the shadow is gone
                    # (and possibly new object/shadow boxels were added).
                    if viz is not None:
                        viz.remove_boxel_viz(sid_str)
                    reboxelize_free_space(
                        registry, env, boxel_centers, viz, show_free)

                    print(f"    -> REPLANNING with updated belief...")
                    break

                else:
                    # Occluder (or robot arm) still blocks the view.
                    # Track repeated failures; after 3 attempts, assume
                    # the shadow is unreachable and give up on it.
                    sid_str = str(shadow_id)
                    blocked_counts[sid_str] = blocked_counts.get(sid_str, 0) + 1
                    print(f"    View to {shadow_id} still blocked "
                          f"({blocked_fraction:.0%} rays hit occluder). "
                          f"[attempt {blocked_counts[sid_str]}]")
                    if blocked_counts[sid_str] >= 3:
                        print(f"    ERROR: {shadow_id} blocked {blocked_counts[sid_str]} "
                              f"times — giving up on this shadow (audit #78c)")
                        belief.mark_sensed(sid_str, found=False)
                    else:
                        print(f"    -> REPLANNING without marking shadow empty...")
                    break  # Exit action loop to replan

            elif action_name == 'pick':
                # PICK: approach → open gripper → lower to contact →
                # close gripper → attach via constraint → lift.
                # Uses the object's CURRENT simulator position (not the
                # boxel center from planning) to handle any drift.
                obj, boxel_id, grasp, config = params
                obj_str = str(obj)
                print(f"    Picking {obj_str} from {boxel_id}...")

                # Defensive: refuse to pick when the gripper is already
                # holding something.  The pre-replan release step should
                # have cleared this, but a fresh planner skeleton can in
                # principle chain pick→pick without an intervening place;
                # double-grasping would silently attach two bodies.
                if held_body_id is not None or grasp_constraint_id is not None:
                    held_name = body_id_to_name.get(held_body_id, str(held_body_id))
                    print(f"    ERROR: Cannot pick {obj_str} — gripper already "
                          f"holds {held_name}. Replanning.")
                    break

                # Resolve symbolic name → PyBullet object.  The target
                # isn't in boxel_to_pybullet (it's hidden), so we
                # handle it as a special case.
                if obj_str in boxel_to_pybullet:
                    pick_obj_name = boxel_to_pybullet[obj_str]['name']
                    pick_pos = np.array(env.objects[pick_obj_name].position)
                elif obj_str == target_name:
                    pick_obj_name = target_name
                    pick_pos = np.array(env.objects[target_name].position)
                else:
                    print(f"    ERROR: Cannot resolve PyBullet object for '{obj_str}'")
                    break

                result = execute_pick(
                    robot_id, env, pick_obj_name, pick_pos,
                    grasp, config, gui)
                if result[0] is None:
                    print(f"    IK failure during pick — replanning (audit #82)")
                    break
                grasp_constraint_id, current_config = result
                held_body_id = env.objects[pick_obj_name].object_id
                # Track the registry boxel ID corresponding to the held
                # body so the emergency-drop path can relocate the right
                # OBJECT boxel if we have to release mid-plan.
                held_object_boxel_id = obj_str if obj_str in boxel_to_pybullet else None
                detect_execution_collisions(
                    robot_id, env.client_id,
                    held_body_id=held_body_id,
                    support_body_ids=support_body_ids,
                    label=f"after pick {pick_obj_name}",
                    body_names=body_id_to_name)
                print(f"    *** {pick_obj_name} PICKED UP! ***")
                if pick_obj_name == target_name:
                    belief.target_found_in = visible_target_locations.get(
                        target_name, "picked")

            elif action_name == 'place':
                # PLACE: approach above destination → lower to contact →
                # open gripper → release constraint → settle → retreat.
                # After placing, we refresh all object positions from the
                # simulator so subsequent actions and replans use up-to-date
                # geometry.
                obj, boxel_id, grasp, config = params
                obj_str = str(obj)
                boxel_id_str = str(boxel_id)
                print(f"    Placing {obj_str} at {boxel_id_str}...")

                # Resolve destination: prefer boxel center (for free-space
                # targets); fall back to the object's recorded position
                # (for placing onto another object's boxel).
                if boxel_id_str in boxel_centers:
                    place_pos = boxel_centers[boxel_id_str]
                elif boxel_id_str in boxel_to_pybullet:
                    place_pos = boxel_to_pybullet[boxel_id_str]['position']
                else:
                    print(f"    ERROR: Cannot resolve position for boxel '{boxel_id_str}'")
                    break

                place_result = execute_place(
                    robot_id, env, obj_str, place_pos, grasp, config,
                    grasp_constraint_id, gui)
                if place_result is None:
                    print(f"    IK failure during place — replanning (audit #82)")
                    break
                current_config = place_result
                grasp_constraint_id = None
                held_body_id = None
                held_object_boxel_id = None

                # Refresh positions after the physics settle step inside
                # execute_place — objects may have shifted slightly.
                env.update_object_positions()
                for bid, binfo in boxel_to_pybullet.items():
                    bname = binfo['name']
                    if bname in env.objects:
                        binfo['position'] = np.array(env.objects[bname].position)

                # --- Re-boxelize free space after placement ---
                # Re-run the full octree + merge pipeline (same as the
                # initial scan in Phase 2) using the current obstacles.
                # The previous approach of splitting the consumed boxel and
                # trying to merge fragments failed because the CellMerger
                # requires exact face alignment — split fragments have edges
                # shaped by the object AABB which never align with the
                # octree-grid edges of existing free boxels.  Re-running
                # the octree produces fine cells that merge naturally.
                consumed_free = registry.get_boxel(boxel_id_str)
                if (consumed_free is not None
                        and consumed_free.boxel_type == BoxelType.FREE_SPACE):
                    placed_name = (boxel_to_pybullet[obj_str]['name']
                                   if obj_str in boxel_to_pybullet
                                   else obj_str)
                    if placed_name in env.objects:
                        body_id = env.objects[placed_name].object_id
                        aabb_min, aabb_max = p.getAABB(body_id)
                        aabb_min = np.array(aabb_min)
                        aabb_max = np.array(aabb_max)

                        registry.update_after_place(
                            free_boxel_id=boxel_id_str,
                            object_boxel_id=obj_str,
                            placed_min=aabb_min,
                            placed_max=aabb_max,
                            table_surface_height=env.table_surface_height,
                        )

                        if viz is not None:
                            viz.remove_boxel_viz(boxel_id_str)
                            moved_bd = registry.get_boxel(obj_str)
                            if moved_bd is not None:
                                viz.remove_boxel_viz(obj_str)
                                viz.draw_boxel_data(moved_bd)

                # Rebuild shadow_occluder_map from current physics state so
                # blocks_view_at facts reflect the relocated occluder's new
                # position on the next replan (audit #73, #24 fixed).
                shadow_occluder_map = compute_shadow_blockers(
                    env.camera_position, registry, shadows, occluders, env
                )
                planner.shadow_occluder_map = shadow_occluder_map

                # Record the relocation in belief state so the planner
                # knows this occluder is no longer blocking its original
                # shadow — it will emit the correct obj_at_boxel facts.
                #
                # NOTE (audit #44 — accepted simplification): Free-space
                # boxels are now split after placement (above), but shadow
                # AABBs still describe the pre-relocation geometry.  This
                # is functionally safe because:
                # (a) sense_shadow_raycasting detects the target by PyBullet
                #     body ID — any ray that hits the target works regardless
                #     of whether the AABB is perfectly aligned.
                # (b) The occluder has been physically removed from the shadow
                #     region (picked up and placed elsewhere), so rays through
                #     the old AABB pass through empty space.
                # (c) shadow_occluder_map is refreshed after every place action
                #     (audit #73; #24 fixed) so blocks_view_at facts are current.
                # Full shadow recomputation would require re-running the camera
                # observation pipeline, which is a separate concern (audit #4).
                if obj_str in boxel_to_pybullet:
                    placed_obj_name = boxel_to_pybullet[obj_str]['name']
                    belief.mark_occluder_moved(obj_str, boxel_id_str)
                    print(f"    *** {placed_obj_name} PLACED at {boxel_id_str}! ***")
                else:
                    print(f"    *** {obj_str} PLACED at {boxel_id_str}! ***")

            elif action_name == 'stack':
                # STACK: drop the held object on top of ?on_obj.  Mirrors
                # `place` but the destination is computed from the
                # support's CURRENT AABB inside execute_stack — no
                # boxel-center lookup, no free-space consumption.  We
                # refresh the OBJECT boxel for the stacked cube to its
                # post-settle AABB so the next planner.plan() sees the
                # new stack height (audit #30).
                obj, on_obj, grasp, config = params
                obj_str = str(obj)
                on_obj_str = str(on_obj)
                print(f"    Stacking {obj_str} on {on_obj_str}...")

                stack_result = execute_stack(
                    robot_id, env, obj_str, on_obj_str, grasp, config,
                    grasp_constraint_id, gui)
                if stack_result is None:
                    print(f"    IK failure during stack — replanning (audit #30)")
                    break
                current_config = stack_result
                grasp_constraint_id = None
                held_body_id = None
                held_object_boxel_id = None

                env.update_object_positions()
                for bid, binfo in boxel_to_pybullet.items():
                    bname = binfo['name']
                    if bname in env.objects:
                        binfo['position'] = np.array(env.objects[bname].position)

                # Refresh the stacked object's OBJECT boxel from its new
                # AABB so _build_init's next pass sees it above the
                # support and (clear ?obj_str) is emitted for the new
                # stack top (the support is no longer clear, which the
                # planner picks up via on_relations below).
                if obj_str in env.objects:
                    body_id = env.objects[obj_str].object_id
                    a_min, a_max = p.getAABB(body_id)
                    a_min = np.array(a_min)
                    a_max = np.array(a_max)
                    bd = registry.get_boxel(obj_str)
                    if bd is not None:
                        bd.min_corner = a_min
                        bd.max_corner = a_max
                        bd.on_surface = None
                        boxel_centers[obj_str] = bd.center
                        if viz is not None:
                            viz.remove_boxel_viz(obj_str)
                            viz.draw_boxel_data(bd)

                # Track the relation so goal_satisfied() / next replan
                # see the live stack.  Replace any prior support of
                # obj_str (re-stacking) — the conditional pick effect in
                # the domain already cleared the old support symbolically.
                on_relations[obj_str] = on_obj_str
                # Stacking does NOT consume free space (we placed onto
                # an OBJECT, not a FREE_SPACE), so reboxelize_free_space
                # is unnecessary here.  Any registry.dirty flag set by
                # the AABB update will be picked up at the top of the
                # next plan iteration via the existing dirty-flag check.
                print(f"    *** {obj_str} STACKED on {on_obj_str}! ***")

            if gui:
                env.refresh_debug_camera_views()

    # =========================================================
    # PHASE 6: Results & Cleanup
    # =========================================================
    # Classify outcome and report metrics.  The exit_reason set during
    # the loop tells us exactly why we stopped: target found, all shadows
    # exhausted, planner failure, or replan budget exceeded.
    print("\n" + "=" * 60)
    if goal_kind == 'holding':
        success = belief.is_target_found()
    else:
        success = goal_satisfied(goal, on_relations)
    if success:
        print(f"SUCCESS!")
        if goal_kind == 'holding':
            print(f"  Target: {target_name}")
            print(f"  Found in: {belief.target_found_in}")
            print(f"  Plans executed: {plan_count}")
            print(f"  Shadows searched: {len(shadows) - len(belief.get_unknown_shadows())}")
        else:
            print(f"  Stack goal: {goal}")
            print(f"  Final on-relations: {on_relations}")
            print(f"  Plans executed: {plan_count}")
    else:
        remaining = belief.get_unknown_shadows()
        if exit_reason is None:
            exit_reason = "replan_limit"
        if exit_reason == "all_searched":
            print(f"FAILED: All {len(shadows)} shadows searched — target not found")
        elif exit_reason == "planner_failed":
            print(f"FAILED: Planner returned no plan "
                  f"({len(remaining)} unsearched shadows remaining)")
        elif exit_reason == "drop_failed":
            print(f"FAILED: Could not release held object after retries — "
                  f"aborted to avoid double-grasp "
                  f"({len(remaining)} unsearched shadows remaining)")
        elif goal_kind == 'stack':
            print(f"FAILED: Stack goal not reached after {plan_count} plans "
                  f"(goal {goal}, achieved {on_relations})")
        else:
            print(f"FAILED: Replan limit reached ({max_replans}) with "
                  f"{len(remaining)} unsearched shadows remaining")
        print(f"  Plans executed: {plan_count}")

    print(f"\n--- Planning timing summary ---")
    print(f"  Total plan() calls       : {len(plan_times)}")
    print(f"  Cumulative planning time : {total_plan_time:.3f}s")
    if plan_times:
        avg = total_plan_time / len(plan_times)
        print(f"  Average per call         : {avg:.3f}s")
        per_call_str = ', '.join(f'{t:.3f}' for t in plan_times)
        print(f"  Per-call (s)             : [{per_call_str}]")

    # Machine-readable summary alongside the full text log so multi-run
    # comparisons (baseline vs. stack feature, GUI vs. no-GUI, etc.)
    # don't require parsing the prose log.
    if run_logger is not None:
        summary_path = run_logger.run_dir / "timing_summary.json"
        try:
            summary_path.write_text(json.dumps({
                "run_config": run_config or {},
                "success": bool(success),
                "exit_reason": exit_reason,
                "plan_count": plan_count,
                "total_planning_time_s": round(total_plan_time, 3),
                "per_call_planning_time_s": [round(t, 3) for t in plan_times],
            }, indent=2))
            print(f"  Timing summary written to {summary_path}")
        except Exception as e:
            print(f"  WARNING: could not write timing_summary.json: {e}")
    print("=" * 60)

    # Keep the GUI visible briefly so the user can inspect the final
    # state, then tear down the simulation cleanly.
    if gui:
        print("\nWindow closing in 4 seconds...")
        end_time = time.time() + 4
        while time.time() < end_time:
            env.step_simulation()
            time.sleep(1.0 / 240.0)

    if grasp_constraint_id is not None:
        p.removeConstraint(grasp_constraint_id)

    env.close()
    return success


if __name__ == "__main__":
    # CLI interface supporting three scene presets:
    #   default     — hand-crafted scene with cubes (deterministic)
    #   mixed       — diverse shapes, seeded for reproducibility
    #   scalability — random placement with configurable counts,
    #                 used for batch evaluation across many seeds
    parser = argparse.ArgumentParser(description='Full PDDLStream Pipeline with Replanning')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI')
    parser.add_argument(
        '--no-boxel-viz',
        action='store_true',
        help='Keep PyBullet GUI but skip drawing boxel AABBs/labels (debug clutter)',
    )
    parser.add_argument(
        '--show-free',
        action='store_true',
        help='Include free-space boxels in the visualisation overlay',
    )
    parser.add_argument('--log-level', choices=['quiet', 'normal', 'verbose'],
                        default='normal',
                        help='Console verbosity (log file always captures everything)')
    parser.add_argument('--scene', choices=['default', 'mixed',
                                            'scalability', 'stack'],
                        default='default',
                        help='Scene preset: default (original cubes), mixed (diverse '
                             'shapes), scalability (random for evaluation), '
                             'stack (N identical cubes, no occluders).')
    parser.add_argument('--n-occluders', type=int, default=3,
                        help='Number of occluders (scalability scene only)')
    parser.add_argument('--n-targets', type=int, default=4,
                        help='Number of targets (scalability scene only)')
    parser.add_argument('--n-hidden', type=int, default=0,
                        help='Number of targets that must be hidden from '
                             'the camera at spawn time (scalability + '
                             'holding only, audit #29). 0 = no guarantee '
                             '(emergent from RNG). Capped at --n-targets. '
                             'Requires --n-occluders >= 1.')
    parser.add_argument('--n-objects', type=int, default=3,
                        help='Number of cubes for the stack scene '
                             '(must be >= --stack-height)')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed (scalability/mixed/stack scenes). '
                             'Note: --n-hidden > 0 may nudge the seed on '
                             'retry if placement fails; the effective seed '
                             'is logged in run_config.')
    parser.add_argument(
        '--goal',
        choices=['holding', 'stack'],
        default='holding',
        help="Goal kind. 'holding' picks the (hidden or visible) target; "
             "'stack' builds a randomised tower of cubes (audit #30).",
    )
    parser.add_argument(
        '--stack-height',
        type=int,
        default=2,
        help='Stack tower height in cubes (>= 2). Only used with '
             '--goal stack. Defaults to 2 (one stacking action).',
    )
    args = parser.parse_args()

    # Audit #29: --n-hidden only makes sense on the scalability scene
    # with --goal holding.  Auto-promote --scene default to scalability
    # when the user passes any of the count knobs under --goal holding
    # (mirrors the --goal stack auto-override below).  Reject clearly
    # wrong combinations early so the user sees a CLI error instead of
    # silently running a scene that cannot satisfy the request.
    _holding_counts_explicit = (
        args.n_hidden > 0
        or '--n-occluders' in sys.argv
        or '--n-targets' in sys.argv
    )
    if (args.goal == 'holding'
            and args.scene == 'default'
            and _holding_counts_explicit):
        args.scene = 'scalability'

    if args.n_hidden > 0:
        if args.scene not in ('scalability',):
            parser.error(
                f"--n-hidden > 0 requires --scene scalability "
                f"(got --scene {args.scene}). Hidden-target guarantee "
                f"only applies to the scalability scene."
            )
        if args.goal != 'holding':
            parser.error(
                f"--n-hidden > 0 is only meaningful with --goal holding "
                f"(got --goal {args.goal}). Stack scenes have no "
                f"occluders."
            )
        if args.n_occluders < 1:
            parser.error(
                "--n-hidden > 0 requires --n-occluders >= 1."
            )
        if args.n_hidden > args.n_targets:
            print(f"[warn] --n-hidden={args.n_hidden} > "
                  f"--n-targets={args.n_targets}; capping to "
                  f"{args.n_targets}.", file=sys.stderr)
            args.n_hidden = args.n_targets

    # When --goal stack is requested without an explicit --scene, fall
    # back to stack_scene so the spawned objects are reach-constrained
    # cubes by default.  Explicit --scene overrides this for A/B tests.
    if args.goal == 'stack' and args.scene == 'default':
        args.scene = 'stack'

    # Lazy scene construction — each builder captures CLI args and
    # returns a SceneConfig when called, so only the selected scene
    # pays the cost of object placement computation.
    scene_builders = {
        'default': lambda: default_scene(),
        'mixed': lambda: mixed_shapes_scene(seed=args.seed),
        'scalability': lambda: scalability_scene(
            n_occluders=args.n_occluders,
            n_targets=args.n_targets,
            n_hidden=args.n_hidden,
            seed=args.seed,
        ),
        'stack': lambda: stack_scene(
            n_objects=max(args.n_objects, args.stack_height),
            seed=args.seed,
        ),
    }
    scene_cfg = scene_builders[args.scene]()

    # Snapshot of effective CLI flags echoed into the per-run log and the
    # JSON timing summary so cross-run comparisons can group by config
    # (audit #30 keep/kill).  Booleans match the kwargs we hand to main()
    # rather than the inverted no_* arg names for readability.
    run_config = {
        "scene":        args.scene,
        "n_occluders":  args.n_occluders,
        "n_targets":    args.n_targets,
        "n_hidden":     args.n_hidden,
        "n_objects":    args.n_objects,
        "seed":         args.seed,
        "goal":         args.goal,
        "stack_height": args.stack_height,
        "gui":          not args.no_gui,
        "boxel_viz":    not args.no_boxel_viz,
        "show_free":    args.show_free,
        "log_level":    args.log_level,
    }

    # RunLogger captures all artefacts (PDDL files, boxel data, logs)
    # regardless of console verbosity for post-mortem analysis.
    logger = RunLogger(verbosity=args.log_level)
    try:
        success = main(
            gui=not args.no_gui,
            run_logger=logger,
            scene_config=scene_cfg,
            draw_boxel_overlays=not args.no_boxel_viz,
            show_free=args.show_free,
            goal_kind=args.goal,
            stack_height=args.stack_height,
            run_config=run_config,
        )
    finally:
        logger.close()
    sys.exit(0 if success else 1)
