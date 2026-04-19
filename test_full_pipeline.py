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
import random

PDDLSTREAM_PATH = os.environ.get(
    'PDDLSTREAM_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pddlstream_lib')
)
if os.path.exists(PDDLSTREAM_PATH):
    sys.path.insert(0, PDDLSTREAM_PATH)

import numpy as np
import pybullet as p

from boxel_env import (BoxelTestEnv, SceneConfig,
                       default_scene, mixed_shapes_scene, scalability_scene)
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
                       execute_pick, execute_place)


def main(gui=True, run_logger=None, scene_config=None,
         draw_boxel_overlays=True, show_free=False,
         goal_kind='holding'):
    print("=" * 60)
    print("FULL PIPELINE: PDDLStream + Replanning")
    print("=" * 60)

    # =========================================================
    # PHASE 1: Setup Environment
    # =========================================================
    print("\n--- Phase 1: Environment Setup ---")
    env = BoxelTestEnv(gui=gui, scene_config=scene_config)
    robot_id = env.objects["robot"].object_id
    print(f"Robot ID: {robot_id}")

    # Let settle: 50 steps at 240 Hz ≈ 0.2 s.  Enough for the loaded
    # Panda + cubes to reach static equilibrium after spawning.
    for _ in range(50):
        env.step_simulation()
    env.update_object_positions()

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

    # The goal kind is decoupled from target selection so future goal
    # types (e.g. ('on', a, b)) can reuse the same target-discovery code.
    # Currently only 'holding' is wired through the planner.
    if goal_kind == 'holding':
        goal = ('holding', target_name)
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

    problem_path = planner.export_problem_pddl(
        target_objects=[target_name],
        goal=goal,
        visible_target_locations=visible_target_locations,
    )
    print(f"  Exported initial problem to {problem_path}")
    if run_logger:
        run_logger.save_artefact(problem_path, "problem_initial.pddl")

    boxel_centers = {b.id: b.center for b in registry.boxels.values()}

    plan_count = 0
    # --- Reactive replanning loop ---
    # Design: the PDDL sense action is OPTIMISTIC — it assumes the
    # target will be found.  When execution reveals otherwise (empty or
    # still-blocked), we break out of the current plan and replan with
    # the updated belief.  This is cheaper than encoding every possible
    # sensing outcome in PDDL.
    #
    # Termination: each replan eliminates at least one shadow (or retries
    # a blocked one up to 3 times), so worst case is bounded.  Budget:
    # 4 attempts per shadow + 1 final pick.
    max_replans = 4 * len(shadows) + 1
    grasp_constraint_id = None       # set during pick, cleared after place
    held_body_id = None              # PyBullet body ID of the held object
    held_object_boxel_id = None      # registry boxel ID of the held object
    exit_reason = None               # tracks why the loop ended for Phase 6
    current_config = planner.home_config  # robot's last known joint config
    # Detect infinite-replan loops: if sensing the same shadow stays
    # "still_blocked" 3+ times, give up on it (audit #78c).
    blocked_counts = {}  # shadow_id → consecutive-block count

    while not belief.is_target_found() and plan_count < max_replans:
        plan_count += 1
        unknown_shadows = belief.get_unknown_shadows()
        known_empty = belief.get_known_empty_shadows()

        print(f"\n=== PLAN #{plan_count} ===")
        print(f"Unknown shadows remaining: {len(unknown_shadows)}")

        if not unknown_shadows:
            exit_reason = "all_searched"
            print("ERROR: Searched all shadows but target not found!")
            break

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
            plan = planner.plan(
                target_objects=[target_name],
                goal=goal,
                current_config=current_config,
                known_empty_shadows=known_empty,
                moved_occluders=dict(belief.occluders_moved),
                max_time=120.0,
                verbose=False,
                visible_target_locations=visible_target_locations,
            )

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

                # Force-refresh every OBJECT boxel + its shadow children
                # from the live PyBullet pose before we sense.  Settling
                # and incidental contact can drift cubes between actions;
                # without this pass the planner keeps reasoning over the
                # AABB the cube had at Phase 2 spawn time.  Mirrors the
                # contains_nontarget branch below — same field setup,
                # same shadow_calculator call, same auxiliary maps.
                #
                # When the shadow part count is unchanged (the common
                # case for translational drift) we update the existing
                # shadow BoxelData in-place so their registry IDs — and
                # the belief entries / sense-empty marks tied to those
                # IDs — remain stable.  Only when topology actually
                # changes do we fall back to remove-and-readd.
                for obj_bd in list(registry.get_object_boxels()):
                    obj_name_r = obj_bd.object_name
                    if obj_name_r is None or obj_name_r not in env.objects:
                        continue
                    bid_r = env.objects[obj_name_r].object_id
                    aabb_min_r, aabb_max_r = p.getAABB(bid_r)
                    aabb_min_r = np.array(aabb_min_r)
                    aabb_max_r = np.array(aabb_max_r)

                    moved = not (
                        np.allclose(obj_bd.min_corner, aabb_min_r, atol=1e-4)
                        and np.allclose(obj_bd.max_corner, aabb_max_r, atol=1e-4)
                    )
                    if not moved:
                        continue

                    obj_bd.min_corner = aabb_min_r
                    obj_bd.max_corner = aabb_max_r
                    boxel_centers[obj_bd.id] = obj_bd.center

                    other_solids_r = [
                        bd for bd in registry.boxels.values()
                        if (bd.boxel_type == BoxelType.OBJECT
                            and bd.id != obj_bd.id)
                    ]
                    new_shadow_parts = env.shadow_calculator.calculate_shadow_boxel(
                        obj_bd, other_solids_r)
                    existing_shadow_ids = list(obj_bd.shadow_boxel_ids)
                    table_z_r = env.table_surface_height

                    if len(new_shadow_parts) == len(existing_shadow_ids):
                        for s_id_r, sp in zip(existing_shadow_ids, new_shadow_parts):
                            s_bd = registry.get_boxel(s_id_r)
                            if s_bd is None:
                                continue
                            s_bd.min_corner = sp.min_corner
                            s_bd.max_corner = sp.max_corner
                            s_bd.on_surface = (
                                "table"
                                if sp.min_corner[2] <= table_z_r + 0.01
                                else None
                            )
                            s_bd.surface_z = table_z_r
                            boxel_centers[s_id_r] = s_bd.center
                            if viz is not None:
                                viz.remove_boxel_viz(s_id_r)
                                viz.draw_boxel_data(s_bd)
                        obj_bd.is_occluder = bool(new_shadow_parts)
                    else:
                        for s_id_old in existing_shadow_ids:
                            registry.remove_boxel(s_id_old)
                            if s_id_old in shadows:
                                shadows.remove(s_id_old)
                            shadow_occluder_map.pop(s_id_old, None)
                            boxel_centers.pop(s_id_old, None)
                            if viz is not None:
                                viz.remove_boxel_viz(s_id_old)
                        obj_bd.shadow_boxel_ids = []
                        obj_bd.is_occluder = False

                        if new_shadow_parts:
                            obj_bd.is_occluder = True
                            for sp in new_shadow_parts:
                                sp.created_by_boxel_id = obj_bd.id
                                sp.created_by_object = obj_name_r
                                sp.on_surface = (
                                    "table"
                                    if sp.min_corner[2] <= table_z_r + 0.01
                                    else None
                                )
                                sp.surface_z = table_z_r
                                s_id_new = registry.add_boxel(sp)
                                obj_bd.shadow_boxel_ids.append(s_id_new)
                                shadows.append(s_id_new)
                                shadow_occluder_map[s_id_new] = [obj_bd.id]
                                boxel_centers[s_id_new] = sp.center
                                if viz is not None:
                                    viz.draw_boxel_data(sp)

                    if viz is not None:
                        viz.remove_boxel_viz(obj_bd.id)
                        viz.draw_boxel_data(obj_bd)

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

            if gui:
                env.refresh_debug_camera_views()

    # =========================================================
    # PHASE 6: Results & Cleanup
    # =========================================================
    # Classify outcome and report metrics.  The exit_reason set during
    # the loop tells us exactly why we stopped: target found, all shadows
    # exhausted, planner failure, or replan budget exceeded.
    print("\n" + "=" * 60)
    if belief.is_target_found():
        print(f"SUCCESS!")
        print(f"  Target: {target_name}")
        print(f"  Found in: {belief.target_found_in}")
        print(f"  Plans executed: {plan_count}")
        print(f"  Shadows searched: {len(shadows) - len(belief.get_unknown_shadows())}")
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
        else:
            print(f"FAILED: Replan limit reached ({max_replans}) with "
                  f"{len(remaining)} unsearched shadows remaining")
        print(f"  Plans executed: {plan_count}")
    print("=" * 60)

    # Keep the GUI visible briefly so the user can inspect the final
    # state, then tear down the simulation cleanly.
    if gui:
        import time
        print("\nWindow closing in 4 seconds...")
        end_time = time.time() + 4
        while time.time() < end_time:
            env.step_simulation()
            time.sleep(1.0 / 240.0)

    if grasp_constraint_id is not None:
        p.removeConstraint(grasp_constraint_id)

    env.close()
    return belief.is_target_found()


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
    parser.add_argument('--scene', choices=['default', 'mixed', 'scalability'],
                        default='default',
                        help='Scene preset: default (original cubes), mixed (diverse '
                             'shapes), scalability (random for evaluation)')
    parser.add_argument('--n-occluders', type=int, default=3,
                        help='Number of occluders (scalability scene only)')
    parser.add_argument('--n-targets', type=int, default=4,
                        help='Number of targets (scalability scene only)')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed (scalability/mixed scenes)')
    parser.add_argument(
        '--goal',
        choices=['holding'],
        default='holding',
        help="Goal kind. 'holding' picks the (hidden or visible) target. "
             "Reserved for future kinds (e.g. stacking) — see audit #30.",
    )
    args = parser.parse_args()

    # Lazy scene construction — each builder captures CLI args and
    # returns a SceneConfig when called, so only the selected scene
    # pays the cost of object placement computation.
    scene_builders = {
        'default': lambda: default_scene(),
        'mixed': lambda: mixed_shapes_scene(seed=args.seed),
        'scalability': lambda: scalability_scene(
            n_occluders=args.n_occluders,
            n_targets=args.n_targets,
            seed=args.seed,
        ),
    }
    scene_cfg = scene_builders[args.scene]()

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
        )
    finally:
        logger.close()
    sys.exit(0 if success else 1)
