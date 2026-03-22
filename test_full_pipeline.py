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

PDDLStream path is added to sys.path via the hardcoded PDDLSTREAM_PATH constant below.
"""

import sys
import os
import argparse
import random

# PDDLStream is an external library (not pip-installable) that lives in a
# sibling directory.  We inject it into sys.path so its modules can be
# imported like normal packages by our planner wrapper.
PDDLSTREAM_PATH = os.environ.get(
    'PDDLSTREAM_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pddlstream_lib')
)
if os.path.exists(PDDLSTREAM_PATH):
    sys.path.insert(0, PDDLSTREAM_PATH)

import numpy as np
import pybullet as p
import pybullet_data

# --- Semantic Boxels modules ---
# boxel_env: PyBullet world setup, camera, scene configs
# boxel_data: Boxel types (OBJECT, SHADOW, FREE_SPACE) and registry
# cell_merger: Merges adjacent free-space cells to reduce planner branching
# pddlstream_planner: Wraps PDDLStream with our domain/problem definitions
# streams: Data classes shared between planner and executor (RobotConfig, etc.)
# robot_utils: Low-level Panda arm control (IK, gripper, smooth motion)
# run_logger: Per-run artefact capture for reproducibility
from boxel_env import (BoxelTestEnv, SceneConfig,
                       default_scene, mixed_shapes_scene, scalability_scene)
from boxel_data import BoxelRegistry, BoxelType, create_boxel_registry_from_boxels
from cell_merger import merge_free_space_cells
from pddlstream_planner import PDDLStreamPlanner
from streams import RobotConfig
from robot_utils import (END_EFFECTOR_LINK, RenderingLock, solve_ik,
                         move_robot_smooth, open_gripper, close_gripper)
from run_logger import RunLogger


class BeliefState:
    """
    Epistemic model of the robot's partial observability.

    The robot cannot see through occluders, so it doesn't know which shadow
    hides the target.  This class tracks what has been learned through
    sensing actions, enabling the replanning loop to avoid re-exploring
    already-checked shadows.

    Lifecycle per shadow:
      unknown  ─── sense ───► not_here  (target absent → eliminate)
                         └──► found     (target present → goal reached)

    ``occluders_moved`` records physical relocations so the planner can
    emit correct ``obj_at_boxel`` facts for objects that are no longer at
    their original positions.
    """
    def __init__(self, shadows: list, target: str):
        self.target = target
        self.shadow_status = {s: 'unknown' for s in shadows}
        self.target_found_in = None
        self.occluders_moved = {}  # {occluder_id: destination_boxel_id}
    
    def mark_sensed(self, shadow_id: str, found: bool):
        """Update belief after sensing a shadow."""
        if found:
            self.shadow_status[shadow_id] = 'found'
            self.target_found_in = shadow_id
        else:
            self.shadow_status[shadow_id] = 'not_here'
    
    def mark_occluder_moved(self, occluder_id: str, destination: str):
        """
        Mark that an occluder has been pushed to a new location.

        Args:
            occluder_id: Boxel ID of the occluder that was pushed
            destination: Symbolic boxel ID for the push destination (used
                by the planner to emit obj_at_boxel for the new location)
        """
        self.occluders_moved[occluder_id] = destination

    def get_unknown_shadows(self):
        """Get list of shadows we haven't checked yet."""
        return [s for s, status in self.shadow_status.items() if status == 'unknown']
    
    def get_known_empty_shadows(self):
        """Get list of shadows we've checked and found empty."""
        return [s for s, status in self.shadow_status.items() if status == 'not_here']
    
    def is_target_found(self):
        """Check if we've found the target."""
        return self.target_found_in is not None


def main(gui=True, run_logger=None, scene_config=None):
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
    registry = create_boxel_registry_from_boxels(all_boxels, env.table_surface_height)
    registry.save_to_json("boxel_data.json")
    if run_logger:
        run_logger.save_artefact("boxel_data.json")
    
    # Extract the two categories the planner cares about:
    # - shadows: regions that might hide the target (must be sensed)
    # - occluders: objects blocking those shadows (must be relocated first)
    shadows = [b.id for b in registry.boxels.values() if b.boxel_type == BoxelType.SHADOW]
    occluders = [b.id for b in registry.boxels.values() if b.boxel_type == BoxelType.OBJECT]
    print(f"  {len(registry.boxels)} boxels, {len(shadows)} shadows, {len(occluders)} occluders")
    
    # Visualize all boxels at once (after calculations complete)
    # if gui:
    #     p.resetDebugVisualizerCamera(
    #         cameraDistance=1.5, cameraYaw=45, cameraPitch=-30,
    #         cameraTargetPosition=[0.5, 0.0, env.table_surface_height]
    #     )
    #     env.draw_boxels(all_boxels, duration=0)
    
    # =========================================================
    # PHASE 4: Hidden Object Scenario (ORACLE ONLY)
    # =========================================================
    # This phase establishes ground truth that the ROBOT does NOT have
    # access to.  We use AABB containment (is the target inside a shadow
    # volume?) to verify the scene is valid — at least one target must be
    # genuinely occluded.  The robot only discovers this through sensing.
    print("\n--- Phase 4: Hidden Object Scenario ---")
    
    all_targets = [name for name in env.objects.keys() if name.startswith("target")]
    
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
    
    if not target_to_shadow:
        print(f"  ERROR: No target is geometrically inside any shadow region.")
        print(f"  Cannot run hidden-object scenario.")
        env.close()
        return False
    
    # When multiple targets are hidden, pick one at random so evaluation
    # runs aren't biased toward a particular spatial arrangement.
    target_name = random.choice(list(target_to_shadow.keys()))
    target_info = env.objects[target_name]
    oracle_hidden_shadow = target_to_shadow[target_name]
    
    print(f"  Target: {target_name}")
    print(f"  ORACLE: Actually hidden in {oracle_hidden_shadow} (ground-truth AABB containment)")
    print(f"  Robot must search to find it!")
    
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
    # PyBullet body IDs and names like "occluder_1".  This mapping lets the
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
    # Both human-readable names ("occluder_1") and boxel IDs ("obj_000")
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
                                 support_body_ids=support_body_ids)
    
    # Export the initial PDDL problem for debugging / reproducibility.
    problem_path = planner.export_problem_pddl(
        target_objects=[target_name],
        goal=('holding', target_name)
    )
    print(f"  Exported initial problem to {problem_path}")
    if run_logger:
        run_logger.save_artefact(problem_path, "problem_initial.pddl")
    
    # Get boxel centers for robot motion targets
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
        
        # Disable rendering for the entire planning phase (audit #60).
        # All IK and collision-check calls inside planner.plan() nest
        # harmlessly via RenderingLock's reference count.
        with RenderingLock(env.client_id):
            plan = planner.plan(
                target_objects=[target_name],
                goal=('holding', target_name),
                current_config=current_config,
                known_empty_shadows=known_empty,
                moved_occluders=dict(belief.occluders_moved),
                max_time=120.0,
                verbose=False
            )
        
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
                # line of sight to the shadow region (audit #79).
                home_joints = planner.home_config.joint_positions
                move_robot_smooth(robot_id, home_joints, gui, steps=40)
                current_config = planner.home_config

                shadow_boxel = registry.get_boxel(str(shadow_id))
                if shadow_boxel is None:
                    print(f"    WARNING: Shadow '{shadow_id}' not found in registry. Replanning...")
                    break

                target_pybullet_id = env.objects[target_name].object_id
                occluder_pybullet_ids = set()
                for blocker_bid in shadow_occluder_map.get(str(shadow_id), []):
                    if blocker_bid in boxel_to_pybullet:
                        occluder_pybullet_ids.add(boxel_to_pybullet[blocker_bid]['pybullet_id'])
                shadow_occluder_id = shadow_boxel.created_by_boxel_id

                sense_outcome, blocked_fraction = sense_shadow_raycasting(
                    env.camera_position,
                    shadow_boxel,
                    target_pybullet_id,
                    occluder_pybullet_ids,
                    robot_id=robot_id
                )

                # --- Interpret sensing result ---
                if sense_outcome == "found_target":
                    # Success: remaining plan actions will pick the target.
                    belief.mark_sensed(str(shadow_id), found=True)
                    print(f"    *** TARGET FOUND in {shadow_id}! (ray-cast) ***")
                elif sense_outcome == "clear_but_empty":
                    # Shadow is visible but target isn't there — eliminate
                    # this shadow and replan to try the next one.
                    belief.mark_sensed(str(shadow_id), found=False)
                    print(f"    Target NOT in {shadow_id} (ray-cast: view clear but no target hit)")
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
                print(f"    *** {pick_obj_name} PICKED UP! ***")

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

                # Refresh positions after the physics settle step inside
                # execute_place — objects may have shifted slightly.
                env.update_object_positions()
                for bid, binfo in boxel_to_pybullet.items():
                    bname = binfo['name']
                    if bname in env.objects:
                        binfo['position'] = np.array(env.objects[bname].position)

                # Rebuild shadow_occluder_map from current physics state so
                # blocks_view_at facts reflect the relocated occluder's new
                # position on the next replan (audit #73).
                shadow_occluder_map = compute_shadow_blockers(
                    env.camera_position, registry, shadows, occluders, env
                )
                planner.shadow_occluder_map = shadow_occluder_map

                # Record the relocation in belief state so the planner
                # knows this occluder is no longer blocking its original
                # shadow — it will emit the correct obj_at_boxel facts.
                #
                # NOTE (audit #44 — accepted simplification): the BoxelRegistry
                # is NOT recomputed here.  Shadow AABBs still describe the
                # pre-relocation geometry.  This is functionally safe because:
                # (a) sense_shadow_raycasting detects the target by PyBullet
                #     body ID — any ray that hits the target works regardless
                #     of whether the AABB is perfectly aligned.
                # (b) The occluder has been physically removed from the shadow
                #     region (picked up and placed elsewhere), so rays through
                #     the old AABB pass through empty space.
                # (c) shadow_occluder_map is refreshed after every place action
                #     (audit #73 DONE), so blocks_view_at facts reflect the
                #     current blocker positions on replan.
                # Full shadow recomputation would require re-running the camera
                # observation + free-space generation + cell merger pipeline,
                # which is a significant cost for marginal accuracy gain.
                if obj_str in boxel_to_pybullet:
                    placed_obj_name = boxel_to_pybullet[obj_str]['name']
                    belief.mark_occluder_moved(obj_str, boxel_id_str)
                    print(f"    *** {placed_obj_name} PLACED at {boxel_id_str}! ***")
                else:
                    print(f"    *** {obj_str} PLACED at {boxel_id_str}! ***")
    
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


def sense_shadow_raycasting(camera_pos, shadow_boxel, target_pybullet_id,
                            occluder_pybullet_ids=None, robot_id=None):
    """
    Sense a shadow region using PyBullet ray-casting from the fixed camera.

    Returns one of three outcomes:
      - found_target: at least one ray hits the target
      - clear_but_empty: no ray hits target and no ray hits the occluder
        or robot arm
      - still_blocked: no ray hits target and at least one ray hits occluder
        or robot arm

    This keeps visibility verification inside the sensing action (Phase 3):
    blocked sensing must not be treated as "target absent".

    Args:
        camera_pos: Fixed camera position [x, y, z]
        shadow_boxel: BoxelData for the shadow region to sense
        target_pybullet_id: PyBullet body ID of the target object
        occluder_pybullet_ids: Optional set/list of PyBullet body IDs for ALL
            objects that may block camera view to this shadow (audit #99).
            Previously only the creating occluder was checked; now all
            blockers from compute_shadow_blockers are accepted.
        robot_id: Optional PyBullet body ID of the robot.  If provided, rays
            hitting the robot arm are counted as blocked (audit #83).

    Returns:
        Tuple[str, float]:
          - outcome string in {"found_target", "clear_but_empty", "still_blocked"}
          - blocked_fraction (fraction of rays blocked by occluder or robot;
            0 when not blocked)
    """
    ray_origin = np.array(camera_pos)

    min_c = shadow_boxel.min_corner
    max_c = shadow_boxel.max_corner

    # Three Z slices through the shadow volume:
    # - Bottom slice at +0.04 m above min (half the target height 0.08 m,
    #   avoids hitting the table surface at min_z);
    # - Two interior slices at 33% and 67% of the shadow height.
    z_levels = [
        min_c[2] + 0.04,
        min_c[2] + (max_c[2] - min_c[2]) * 0.33,
        min_c[2] + (max_c[2] - min_c[2]) * 0.67,
    ]

    # 7×7 grid per Z slice = 147 total rays.  Empirically chosen:
    # 5×5 missed small targets at shadow edges; 9×9 doubled ray count
    # with negligible detection improvement.
    n = 7
    ray_froms = []
    ray_tos = []
    for z_target in z_levels:
        for xi in np.linspace(min_c[0], max_c[0], n):
            for yi in np.linspace(min_c[1], max_c[1], n):
                ray_froms.append(ray_origin.tolist())
                ray_tos.append([float(xi), float(yi), float(z_target)])

    results = p.rayTestBatch(ray_froms, ray_tos)
    occluder_hits = 0
    robot_hits = 0
    total_rays = len(results)

    for hit_obj_id, _link, _frac, _pos, _normal in results:
        if hit_obj_id == target_pybullet_id:
            return "found_target", 0.0
        if occluder_pybullet_ids and (hit_obj_id in occluder_pybullet_ids):
            occluder_hits += 1
        elif (robot_id is not None) and (hit_obj_id == robot_id):
            robot_hits += 1

    blocked_total = occluder_hits + robot_hits
    if blocked_total > 0:
        blocked_fraction = blocked_total / total_rays if total_rays > 0 else 0.0
        if robot_hits > 0 and occluder_hits == 0:
            print(f"    NOTE: {robot_hits}/{total_rays} rays blocked by "
                  f"robot arm (not occluder)")
        return "still_blocked", blocked_fraction

    return "clear_but_empty", 0.0


def compute_shadow_blockers(camera_pos, registry, shadow_ids, object_ids, env):
    """
    For each shadow, find ALL object boxels that block the camera's view.

    Casts a coarse ray grid from the camera through each shadow volume.
    Any object whose PyBullet body intercepts at least one ray is recorded
    as a blocker for that shadow.  This replaces the old one-to-one
    shadow_occluder_map that only tracked the creating occluder (audit #78).

    Why not just use the parent relationship?  Because after objects are
    relocated, a DIFFERENT object may now block the camera's view of a
    shadow that was originally created by something else.

    Args:
        camera_pos: Camera position [x, y, z].
        registry: BoxelRegistry with all boxels.
        shadow_ids: List of shadow boxel IDs.
        object_ids: List of object boxel IDs.
        env: BoxelTestEnv for resolving PyBullet body IDs.

    Returns:
        Dict mapping shadow_id → list of blocker object boxel IDs.
    """
    # Reverse lookup: PyBullet body ID → boxel ID, so we can identify
    # which symbolic object a ray hit.
    pybullet_to_boxel = {}
    for obj_bid in object_ids:
        obj_boxel = registry.get_boxel(obj_bid)
        if obj_boxel and obj_boxel.object_name and obj_boxel.object_name in env.objects:
            body_id = env.objects[obj_boxel.object_name].object_id
            pybullet_to_boxel[body_id] = obj_bid

    ray_origin = camera_pos.tolist()
    blockers = {}

    for shadow_id in shadow_ids:
        sb = registry.get_boxel(shadow_id)
        if sb is None:
            continue

        blocker_set = set()
        min_c, max_c = sb.min_corner, sb.max_corner
        # Single Z slice at the shadow midpoint — coarser than
        # sense_shadow_raycasting because we only need to identify
        # WHICH objects block, not whether the target is visible.
        z_mid = (min_c[2] + max_c[2]) / 2.0
        n = 5

        ray_froms = []
        ray_tos = []
        for xi in np.linspace(min_c[0], max_c[0], n):
            for yi in np.linspace(min_c[1], max_c[1], n):
                ray_froms.append(ray_origin)
                ray_tos.append([float(xi), float(yi), float(z_mid)])

        results = p.rayTestBatch(ray_froms, ray_tos)
        for hit_id, _link, _frac, _pos, _normal in results:
            if hit_id in pybullet_to_boxel:
                blocker_set.add(pybullet_to_boxel[hit_id])

        blockers[shadow_id] = list(blocker_set)

    print(f"  Shadow blockers (audit #78):")
    for sid, bids in blockers.items():
        if bids:
            print(f"    {sid} blocked by: {bids}")

    return blockers


def execute_pick(robot_id, env, obj_name, obj_pos, grasp, config, gui):
    """
    Execute pick action using the plan's grasp pose.

    All waypoints are derived from the grasp relative to the object's
    actual current position (obj_pos), not hardcoded offsets.  The
    contact waypoint re-derives IK from ``obj_pos + grasp.position``
    at execution time; if IK fails it falls back to the plan config.
    This handles any drift between the boxel center used during
    planning and the object's actual position.

    The constraint-based attachment (p.createConstraint) is an accepted
    simulation simplification — see audit #7 part B.

    Args:
        robot_id: PyBullet body ID of the robot
        env: BoxelTestEnv instance
        obj_name: Name key in env.objects (e.g. "target_1", "occluder_2")
        obj_pos: Current object position [x, y, z] (from PyBullet)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        gui: Whether GUI is active (for step_simulation timing)

    Returns:
        Tuple[int, RobotConfig]: PyBullet constraint ID for the grasp
        attachment, and a RobotConfig representing the robot's actual
        final joint configuration (lift position).
    """
    # Approach 0.10 m above contact: clears the tallest scene object
    # (occluder 0.15 m cube ≈ 0.075 m half-height) with margin, while
    # staying low enough for reliable IK on the Panda.
    approach_height = 0.10
    # Lift 0.25 m above contact: must clear the occluder height (0.15 m)
    # plus table-edge tolerance so the grasped object doesn't collide
    # with anything during the subsequent move trajectory.
    lift_height = 0.25
    approach_dir = np.array([0.0, 0.0, 1.0])

    # Compute the three end-effector waypoints relative to the object's
    # CURRENT position (not the boxel center used during planning).
    # grasp.position is the EE-to-object offset from the grasp sampler.
    contact_ee = obj_pos + grasp.position
    approach_ee = contact_ee + approach_dir * approach_height
    lift_ee = contact_ee + approach_dir * lift_height

    # Solve IK for all three waypoints independently.  Each call resets
    # the arm to a rest pose seed for deterministic results regardless
    # of current joint state (see robot_utils.solve_ik).
    pc = env.client_id
    approach_joints = solve_ik(robot_id, approach_ee, grasp.orientation, pc)
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc)
    lift_joints = solve_ik(robot_id, lift_ee, grasp.orientation, pc)

    # IK failure triage: contact is mandatory (can't pick without reaching
    # the object); approach and lift are nice-to-have with graceful
    # fallbacks.  Aborting on contact failure triggers a replan rather
    # than driving the arm to an arbitrary configuration (audit #82).
    if contact_joints is None:
        print(f"    ERROR: IK failed for pick contact of {obj_name} — aborting")
        return None, None
    if approach_joints is None:
        print(f"    WARNING: IK failed for pick approach of {obj_name}, "
              f"using contact config directly")
        approach_joints = contact_joints
    if lift_joints is None:
        print(f"    WARNING: IK failed for pick lift of {obj_name}, "
              f"using approach config as fallback")
        lift_joints = approach_joints

    # Execute the pick sequence: approach → open → descend → close → attach → lift
    move_robot_smooth(robot_id, approach_joints, gui)
    open_gripper(robot_id, gui)

    move_robot_smooth(robot_id, contact_joints, gui)
    close_gripper(robot_id, gui)

    # Attach the object to the gripper with a fixed constraint.
    # This is a simulation simplification — real grippers use friction,
    # but constraints prevent physics-engine slip during fast motions.
    #
    # Compute the ACTUAL relative transform between EE and object at this
    # instant rather than using the planned grasp.position offset — position-
    # control lag means the true EE pose differs slightly, and using the
    # planned offset causes a corrective snap impulse (audit #98).
    obj_id = env.objects[obj_name].object_id
    ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK)
    ee_world_pos, ee_world_orn = ee_state[0], ee_state[1]
    obj_world_pos, obj_world_orn = p.getBasePositionAndOrientation(obj_id)
    inv_ee_pos, inv_ee_orn = p.invertTransform(ee_world_pos, ee_world_orn)
    parent_frame_pos, parent_frame_orn = p.multiplyTransforms(
        inv_ee_pos, inv_ee_orn, obj_world_pos, obj_world_orn
    )
    grasp_constraint_id = p.createConstraint(
        robot_id, END_EFFECTOR_LINK, obj_id, -1,
        p.JOINT_FIXED, [0, 0, 0],
        list(parent_frame_pos), [0, 0, 0],
        parentFrameOrientation=list(parent_frame_orn)
    )

    move_robot_smooth(robot_id, lift_joints, gui)

    # Read the actual joint state — position control may not reach the exact
    # IK target.  Tracking the true state prevents PDDL state drift from
    # compounding across chained actions within a plan (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    final_config = RobotConfig(joint_positions=actual_joints,
                               name="post_pick_lift")
    return grasp_constraint_id, final_config


def execute_place(robot_id, env, obj_name, place_pos, grasp, config,
                   grasp_constraint_id, gui):
    """
    Execute place action using the plan's grasp pose.

    Mirrors execute_pick() in reverse: approach above destination, lower
    to contact, release, retreat.  The contact waypoint re-derives IK
    from ``place_pos + grasp.position`` at execution time; falls back
    to the plan config if IK fails.

    Args:
        robot_id: PyBullet body ID of the robot
        env: BoxelTestEnv instance
        obj_name: Name of the object being placed (for logging)
        place_pos: Destination position [x, y, z] (boxel center)
        grasp: Grasp object from the plan (position, orientation)
        config: RobotConfig from the plan's compute_kin_solution (fallback)
        grasp_constraint_id: PyBullet constraint ID from execute_pick()
        gui: Whether GUI is active (for step_simulation timing)

    Returns:
        RobotConfig: The robot's actual final joint configuration
        (retreat position above the placement).
    """
    # Same clearances as execute_pick — see comments there.
    approach_height = 0.10
    retreat_height = 0.25
    approach_dir = np.array([0.0, 0.0, 1.0])

    # Mirror of execute_pick's waypoint computation, but targeting the
    # destination boxel center instead of the object's current position.
    contact_ee = place_pos + grasp.position
    approach_ee = contact_ee + approach_dir * approach_height
    retreat_ee = contact_ee + approach_dir * retreat_height

    pc = env.client_id
    approach_joints = solve_ik(robot_id, approach_ee, grasp.orientation, pc)
    contact_joints = solve_ik(robot_id, contact_ee, grasp.orientation, pc)
    retreat_joints = solve_ik(robot_id, retreat_ee, grasp.orientation, pc)

    # Same IK failure triage as execute_pick — contact is mandatory,
    # approach/retreat have fallbacks.
    if contact_joints is None:
        print(f"    ERROR: IK failed for place contact of {obj_name} — aborting")
        return None
    if approach_joints is None:
        print(f"    WARNING: IK failed for place approach of {obj_name}, "
              f"using contact config directly")
        approach_joints = contact_joints
    if retreat_joints is None:
        print(f"    WARNING: IK failed for place retreat of {obj_name}, "
              f"using approach config as fallback")
        retreat_joints = approach_joints

    # Execute the place sequence: approach → lower → release → settle → retreat
    move_robot_smooth(robot_id, approach_joints, gui)

    move_robot_smooth(robot_id, contact_joints, gui)

    open_gripper(robot_id, gui)

    # Remove the fixed constraint so the object responds to gravity
    # and rests on the table surface.
    if grasp_constraint_id is not None:
        p.removeConstraint(grasp_constraint_id)

    # 30 steps ≈ 0.125 s — let the placed object settle before retreating
    # so it reaches a stable resting pose and doesn't tip over.
    for _ in range(30):
        p.stepSimulation()

    move_robot_smooth(robot_id, retreat_joints, gui)

    # Read actual joint state to prevent drift accumulation (audit #86).
    actual_joints = np.array(
        [p.getJointState(robot_id, i)[0] for i in range(7)]
    )
    return RobotConfig(joint_positions=actual_joints,
                       name="post_place_retreat")


# compute_push_displacement() removed (#53): push superseded by pick-and-place.
# The function teleported occluders via p.resetBasePositionAndOrientation without
# involving the robot arm. Occluder relocation now uses pick → move → place.


if __name__ == "__main__":
    # CLI interface supporting three scene presets:
    #   default     — hand-crafted scene with cubes (deterministic)
    #   mixed       — diverse shapes, seeded for reproducibility
    #   scalability — random placement with configurable counts,
    #                 used for batch evaluation across many seeds
    parser = argparse.ArgumentParser(description='Full PDDLStream Pipeline with Replanning')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI')
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
        success = main(gui=not args.no_gui, run_logger=logger,
                       scene_config=scene_cfg)
    finally:
        logger.close()
    sys.exit(0 if success else 1)
