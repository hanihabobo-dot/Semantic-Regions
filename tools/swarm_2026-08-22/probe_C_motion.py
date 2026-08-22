#!/usr/bin/env python3
"""Agent C probe (read-only, forensics swarm 2026-08-22): motion-execution
deltas for the failing orange_object transit in
logs/run_2026-08-22_17-14-10/ (seed 0, goal=holding, random-pairs scene,
3 occluders).

Reproduces the SAME transit the run's dispatcher actually executed:
  post_pick_contact_runtime -> q_kin_orange_object_3, orange held
  (log lines 138-140: endpoint_ignored=[0,1,5], held=[5],
   "direct path blocked -> RRT-Connect", "RRT path 8 wps -> smoothed 3 wps")
by physically running execute_pick() on orange (same code path
test_full_pipeline.py's dispatcher uses) to get the REAL post-pick joint
state, then calling BoxelStreams._rrt_connect / _smooth_path directly
(the exact internal calls streams.plan_motion makes at streams.py:879-897)
across >=5 RNG realizations.

Also reproduces ONE docile linear transit (q_home -> q_kin_orange_object_2,
log lines 107-108, "direct path clear") for contrast, and parses the run
log for every other move's waypoint count to scale the runtime-impact
estimate.

No GUI, no pddlstream, no FastDownward.  Pure pybullet DIRECT.
Run:
  wsl -e bash -c 'cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels && \
    wsl_env/bin/python tools/swarm_2026-08-22/probe_C_motion.py'
"""
import json
import math
import os
import random
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import numpy as np
import pybullet as p

from boxel_env import BoxelTestEnv, random_pairs_scene
from boxel_data import BoxelRegistry
from cell_merger import merge_free_space_cells
from streams import BoxelStreams, Grasp, RobotConfig
from robot_utils import (JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH, ARM_JOINT_INDICES,
                         REST_POSES, move_robot_smooth)
from execution import execute_pick

SIM_DT = 1.0 / 240.0          # confirmed: no setTimeStep/setPhysicsEngineParameter
                               # call anywhere in the repo -> pybullet default 240 Hz
EXECUTOR_STEPS = 30            # test_full_pipeline.py:1348-1350 (hardcoded call-site arg)
MOVE_ROBOT_SMOOTH_DEFAULT_STEPS = 60  # robot_utils.py:579 signature default (UNUSED
                               # at the transit call site -- overridden to 30)

LOG_PATH = os.path.join(REPO_ROOT, "logs", "run_2026-08-22_17-14-10",
                        "run_2026-08-22_17-14-10.log")

N_TRIALS = 7  # >= 5 required by the task


def build_scene(seed=0):
    """Mirrors test_full_pipeline.py Phase 1-3 (env setup, boxel calc,
    registry) closely enough to reproduce free_005 with the SAME id
    assignment order (all_known first, then merged free-space cells,
    both added via registry.add_boxel in that order)."""
    cfg = random_pairs_scene(n_occluders=3, extra_distractors=0, seed=seed)
    env = BoxelTestEnv(gui=False, scene_config=cfg)
    for _ in range(50):
        env.step_simulation()
    env.update_object_positions()

    obs = env.get_camera_observation()
    all_known = obs.boxels
    free_boxels = env.generate_free_space(all_known, visualize=False)
    merged_free = merge_free_space_cells(free_boxels)
    env.annotate_free_space_surface(merged_free)
    all_boxels = all_known + merged_free

    registry = BoxelRegistry()
    for bd in all_boxels:
        registry.add_boxel(bd)

    # Plan-side object_body_ids / support ids, exactly as
    # test_full_pipeline.py:883-901 builds them for BoxelStreams.
    object_body_ids = {}
    for name, obj_info in env.objects.items():
        if name not in ("plane", "table", "robot"):
            object_body_ids[name] = env.plan_body_id(obj_info.object_id)
    for boxel in registry.boxels.values():
        if boxel.object_name and boxel.object_name in object_body_ids:
            object_body_ids[boxel.id] = object_body_ids[boxel.object_name]

    planner_support_body_ids = frozenset({
        env.plan_body_id(env.objects["plane"].object_id),
        env.plan_body_id(env.objects["table"].object_id),
    })

    return env, registry, object_body_ids, planner_support_body_ids


def joint_step_metrics(q_a, q_b, steps):
    """Per-joint delta between two waypoints, and the per-STEP delta /
    implied velocity if that pair is executed in a fixed *steps* count
    (mirrors move_robot_smooth's linear interpolation, robot_utils.py:600-609)."""
    delta = np.asarray(q_b, dtype=float) - np.asarray(q_a, dtype=float)
    max_delta = float(np.max(np.abs(delta)))
    per_step = delta / steps
    max_per_step = float(np.max(np.abs(per_step)))
    velocity = max_per_step / SIM_DT
    return {
        "delta_per_joint": delta.tolist(),
        "max_abs_delta_rad": max_delta,
        "steps": steps,
        "max_per_step_delta_rad": max_per_step,
        "implied_velocity_rad_s": velocity,
    }


def path_metrics(path, steps=EXECUTOR_STEPS):
    pairs = []
    for i in range(len(path) - 1):
        pairs.append(joint_step_metrics(path[i], path[i + 1], steps))
    worst_pair = max(pairs, key=lambda m: m["max_abs_delta_rad"]) if pairs else None
    worst_step = max(pairs, key=lambda m: m["max_per_step_delta_rad"]) if pairs else None
    return {
        "n_waypoints": len(path),
        "n_pairs": len(pairs),
        "pairs": pairs,
        "worst_pair_max_delta_rad": worst_pair["max_abs_delta_rad"] if worst_pair else 0.0,
        "worst_per_step_delta_rad": worst_step["max_per_step_delta_rad"] if worst_step else 0.0,
        "worst_implied_velocity_rad_s": worst_step["implied_velocity_rad_s"] if worst_step else 0.0,
    }


def steps_at_cap(path, cap):
    """Velocity-bounded interpolation: steps scaled per-pair so
    max|delta|/steps <= cap.  Returns (total_steps, per_pair_steps)."""
    per_pair = []
    for i in range(len(path) - 1):
        d = np.asarray(path[i + 1], dtype=float) - np.asarray(path[i], dtype=float)
        max_d = float(np.max(np.abs(d)))
        n = max(1, math.ceil(max_d / cap)) if max_d > 0 else 1
        per_pair.append(n)
    return sum(per_pair), per_pair


def parse_log_moves(log_path):
    """Extract every 'Moving to X (N waypoints)' dispatch print and every
    'RRT path N wps -> smoothed M wps' stream log line, in file order."""
    moves = []
    rrt_lines = []
    if not os.path.exists(log_path):
        return moves, rrt_lines
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.search(r"Moving to (\S+) \((\d+) waypoints\)", line)
            if m:
                moves.append((m.group(1), int(m.group(2))))
            m2 = re.search(r"RRT path (\d+) wps -> smoothed (\d+) wps", line)
            if m2:
                rrt_lines.append((int(m2.group(1)), int(m2.group(2))))
    return moves, rrt_lines


def main():
    print("=" * 78)
    print("Agent C: motion-execution delta probe")
    print("=" * 78)

    env, registry, object_body_ids, planner_support_body_ids = build_scene(seed=0)

    streams = BoxelStreams(registry, robot_id=env.plan_robot_id,
                           physics_client=env.plan_client_id,
                           object_body_ids=object_body_ids,
                           support_body_ids=planner_support_body_ids)

    orn = np.array(p.getQuaternionFromEuler([0, np.pi, 0]))
    grasp = Grasp(position=np.array([0.0, 0.0, 0.10]), orientation=orn,
                  name="grasp_orange_probe")

    # --- q1: q_home -> q_kin_orange_object_2 (planned pick-approach pose) ---
    q_home = streams.home_config
    q_pick_list = list(streams.compute_kin_solution("orange_object",
                                                     "orange_object", grasp))
    if not q_pick_list:
        print("FATAL: compute_kin_solution found no IK for orange pick approach")
        return 1
    (q_pick,) = q_pick_list[0]
    print(f"q_pick (approach): {q_pick.joint_positions.tolist()} "
          f"ignored={sorted(q_pick.ignored_body_ids)}")

    # Contrast case: the docile "direct path clear" linear move actually
    # executed for this leg of the plan (log lines 107-108, 10 waypoints).
    (linear_traj,) = next(streams.plan_motion(q_home, q_pick))
    linear_path = [wp.joint_positions for wp in linear_traj.waypoints]
    linear_metrics = path_metrics(linear_path, steps=EXECUTOR_STEPS)
    print(f"\n[contrast] q_home -> q_pick: direct linear, "
          f"{linear_metrics['n_waypoints']} waypoints, "
          f"worst_pair_delta={linear_metrics['worst_pair_max_delta_rad']:.5f} rad, "
          f"worst_per_step={linear_metrics['worst_per_step_delta_rad']:.5f} rad "
          f"({linear_metrics['worst_implied_velocity_rad_s']:.3f} rad/s)")

    # --- Physically execute the pick to get the REAL post-pick joint state ---
    exec_robot_id = env.objects["robot"].object_id
    orange_pos = np.array(env.objects["orange_object"].position)
    # Move the execution-side (GUI-client==0) arm to the approach pose first,
    # same as the dispatcher's preceding 'move' action.
    move_robot_smooth(exec_robot_id, q_pick.joint_positions, gui=False,
                      steps=EXECUTOR_STEPS, settle=True)
    held_body_id, post_pick_config = execute_pick(
        exec_robot_id, env, "orange_object", orange_pos, grasp, q_pick, gui=False)
    if held_body_id is None:
        print("FATAL: execute_pick failed to grasp orange_object in the probe")
        return 1
    print(f"\npost_pick_contact (REAL, physically executed): "
          f"{post_pick_config.joint_positions.tolist()}")

    # Mirror test_full_pipeline.py:1321-1327's runtime-replan config exactly.
    q1_runtime = RobotConfig(
        joint_positions=np.asarray(post_pick_config.joint_positions),
        name="post_pick_contact_runtime",
        ignored_body_ids=q_pick.ignored_body_ids,
        held_body_ids=q_pick.held_body_ids,
        grasp_ee_offset=q_pick.grasp_ee_offset,
    )

    # --- q2: q_kin_orange_object_3 (place at free_005) ---
    q_place_list = list(streams.compute_kin_solution("orange_object",
                                                      "free_005", grasp))
    used_free_id = "free_005"
    if not q_place_list:
        # Fall back to nearest free boxel by target ee position if id
        # numbering drifted from the original run (documented below).
        print("  [warn] no IK for literal 'free_005' -- searching nearest "
              "free boxel by target position")
        target_xy = np.array([0.0, -0.35])
        best = None
        for b in registry.boxels.values():
            if not b.id.startswith("free_"):
                continue
            d = float(np.linalg.norm(np.asarray(b.center[:2]) - target_xy))
            if best is None or d < best[0]:
                best = (d, b.id)
        if best is not None:
            used_free_id = best[1]
            q_place_list = list(streams.compute_kin_solution(
                "orange_object", used_free_id, grasp))
    if not q_place_list:
        print("FATAL: compute_kin_solution found no IK for the place boxel")
        return 1
    (q_place,) = q_place_list[0]
    print(f"q_place (at {used_free_id}, log target='free_005'): "
          f"{q_place.joint_positions.tolist()} "
          f"[id_match={'YES' if used_free_id == 'free_005' else 'NO -- see warn above'}]")

    # --- Replicate plan_motion's ignore/held-set derivation (streams.py:773-821) ---
    base_ignored = q1_runtime.ignored_body_ids | q_place.ignored_body_ids
    is_pick_place = bool(q1_runtime.ignored_body_ids or q_place.ignored_body_ids)
    if q1_runtime.held_body_ids or q_place.held_body_ids:
        held_body_ids = q1_runtime.held_body_ids | q_place.held_body_ids
    else:
        held_body_ids = q1_runtime.ignored_body_ids & q_place.ignored_body_ids
    held_body_ee_offset = None
    if held_body_ids:
        for q in (q1_runtime, q_place):
            if q.grasp_ee_offset is not None:
                held_body_ee_offset = q.grasp_ee_offset
                break
    path_ignored = (base_ignored | streams.support_body_ids
                    if is_pick_place else base_ignored)
    print(f"\nderived: is_pick_place={is_pick_place} held_body_ids="
          f"{sorted(held_body_ids)} path_ignored={sorted(path_ignored)} "
          f"(log line 138: endpoint_ignored=[0, 1, 5] held=[5])")

    # Sanity: confirm this transit is indeed RRT territory (matches
    # log lines 139-140 "direct path blocked -> RRT-Connect").
    from robot_utils import is_path_collision_free
    direct_ok = is_path_collision_free(
        streams.robot_id, q1_runtime.joint_positions, q_place.joint_positions,
        streams.physics_client, n_checks=streams.RRT_EDGE_CHECKS,
        ignored_bodies=path_ignored, allow_gripper_collisions=is_pick_place,
        held_body_ids=held_body_ids, held_body_ee_offset=held_body_ee_offset,
        strict_gripper_interior=is_pick_place)
    print(f"direct path collision-free? {direct_ok}  "
          f"(log says blocked -> should be False)")

    # --- Repeat the RRT + shortcut-smooth over N_TRIALS RNG realizations ---
    trials = []
    for trial in range(N_TRIALS):
        seed = 1000 + trial
        random.seed(seed)
        np.random.seed(seed)
        raw_path = streams._rrt_connect(
            q1_runtime.joint_positions, q_place.joint_positions,
            path_ignored, allow_gripper_collisions=is_pick_place,
            held_body_ids=held_body_ids, held_body_ee_offset=held_body_ee_offset)
        if raw_path is None:
            print(f"  trial seed={seed}: RRT-Connect FAILED to find a path")
            continue
        smoothed_path = streams._smooth_path(
            raw_path, path_ignored, allow_gripper_collisions=is_pick_place,
            held_body_ids=held_body_ids, held_body_ee_offset=held_body_ee_offset)

        raw_m = path_metrics(raw_path, steps=EXECUTOR_STEPS)
        smooth_m = path_metrics(smoothed_path, steps=EXECUTOR_STEPS)
        trials.append({"seed": seed, "raw": raw_m, "smoothed": smooth_m,
                       "raw_path": [q.tolist() for q in raw_path],
                       "smoothed_path": [q.tolist() for q in smoothed_path]})
        print(f"\n  trial seed={seed}: raw {raw_m['n_waypoints']} wps "
              f"-> smoothed {smooth_m['n_waypoints']} wps")
        print(f"    RAW      worst_pair_delta={raw_m['worst_pair_max_delta_rad']:.5f} rad  "
              f"worst_per_step(@{EXECUTOR_STEPS})={raw_m['worst_per_step_delta_rad']:.5f} rad  "
              f"({raw_m['worst_implied_velocity_rad_s']:.3f} rad/s)")
        print(f"    SMOOTHED worst_pair_delta={smooth_m['worst_pair_max_delta_rad']:.5f} rad  "
              f"worst_per_step(@{EXECUTOR_STEPS})={smooth_m['worst_per_step_delta_rad']:.5f} rad  "
              f"({smooth_m['worst_implied_velocity_rad_s']:.3f} rad/s)")

    if not trials:
        print("FATAL: every RRT trial failed -- cannot report deltas")
        return 1

    # Aggregate worst case across all trials (smoothed = what's executed).
    worst_overall = max(trials, key=lambda t: t["smoothed"]["worst_per_step_delta_rad"])
    worst_smoothed = worst_overall["smoothed"]
    print("\n" + "=" * 78)
    print(f"WORST-CASE across {len(trials)} trials (SMOOTHED path, "
          f"as actually executed at steps={EXECUTOR_STEPS}):")
    print(f"  seed={worst_overall['seed']}  "
          f"worst_pair_max_delta={worst_smoothed['worst_pair_max_delta_rad']:.5f} rad  "
          f"worst_per_step_delta={worst_smoothed['worst_per_step_delta_rad']:.5f} rad  "
          f"implied_velocity={worst_smoothed['worst_implied_velocity_rad_s']:.3f} rad/s")

    median_smoothed_per_step = float(np.median(
        [t["smoothed"]["worst_per_step_delta_rad"] for t in trials]))
    median_smoothed_delta = float(np.median(
        [t["smoothed"]["worst_pair_max_delta_rad"] for t in trials]))
    print(f"  median worst_pair_max_delta={median_smoothed_delta:.5f} rad  "
          f"median worst_per_step_delta={median_smoothed_per_step:.5f} rad")

    # --- Step 4: velocity-bounded interpolation cost, for this transit ---
    caps = [0.02, 0.05, 0.10]
    print("\nVelocity-cap step counts (this transit's SMOOTHED path, per trial):")
    cap_summaries = {}
    for cap in caps:
        totals = []
        for t in trials:
            total, per_pair = steps_at_cap(
                [np.asarray(q) for q in t["smoothed_path"]], cap)
            totals.append(total)
        cap_summaries[cap] = {
            "min_steps": min(totals), "max_steps": max(totals),
            "median_steps": float(np.median(totals)),
        }
        fixed_steps = (len(worst_overall["smoothed_path"]) - 1) * EXECUTOR_STEPS
        print(f"  cap={cap:.2f} rad/step: total steps min/median/max = "
              f"{min(totals)}/{np.median(totals):.0f}/{max(totals)} "
              f"(current fixed schedule: {fixed_steps} steps @ "
              f"{EXECUTOR_STEPS}/pair)")

    # --- Parse the whole run log for every other move's waypoint count ---
    moves, rrt_lines = parse_log_moves(LOG_PATH)
    print(f"\nRun-wide move census (parsed from {LOG_PATH}):")
    print(f"  total 'move' dispatch prints: {len(moves)}")
    linear_moves = [m for m in moves if m[1] != 3]
    smoothed_moves = [m for m in moves if m[1] == 3]
    print(f"  10-waypoint linear moves (direct path clear): {len(linear_moves)} "
          f"-> {[m[0] for m in linear_moves]}")
    print(f"  3-waypoint SMOOTHED-RRT moves: {len(smoothed_moves)} "
          f"-> {[m[0] for m in smoothed_moves]}")
    print(f"  'RRT path N -> smoothed M' stream log lines: {rrt_lines} "
          f"(2 lines = 1 planning-time call + 1 runtime-replan call for the "
          f"SAME orange->free_005 transit; every other transit in the whole "
          f"run was 'direct path clear')")

    # Current fixed-schedule total steps across the whole run (measured
    # exactly for linear moves: 9 segments/move * 30 steps; measured
    # exactly for the one smoothed move via this probe's trials).
    linear_pair_count = sum(max(0, n - 1) for _, n in linear_moves)
    smoothed_pair_count = sum(max(0, n - 1) for _, n in smoothed_moves)
    fixed_total_steps = ((linear_pair_count + smoothed_pair_count)
                         * EXECUTOR_STEPS)
    print(f"\n  Fixed-schedule total steps for the whole run: "
          f"{linear_pair_count} linear pairs + {smoothed_pair_count} "
          f"smoothed pairs, all @ {EXECUTOR_STEPS} steps = {fixed_total_steps} "
          f"steps = {fixed_total_steps * SIM_DT:.2f} s of stepSimulation "
          f"(HYPOTHESIS: assumes every linear move's 9 segments run at the "
          f"SAME 30-step schedule as observed -- confirmed by code at "
          f"test_full_pipeline.py:1346-1350, which applies steps=30 "
          f"uniformly to EVERY waypoint pair regardless of source).")

    # Only the smoothed move's pairs are cap-scaled with MEASURED deltas
    # (2 pairs, this probe).  Linear moves' pairs are not reproduced here
    # (out of scope -- would require replaying all 7 other object states);
    # flagged HYPOTHESIS if extrapolated using the smoothed move's per-pair
    # profile, so we report the SMOOTHED-only run-wide delta explicitly
    # instead of guessing at the linear movements' deltas.
    print("\n  Cap-scaled total steps for JUST the smoothed-RRT move "
          "(2 executed pairs, this probe's trials):")
    for cap in caps:
        s = cap_summaries[cap]
        print(f"    cap={cap:.2f}: median {s['median_steps']:.0f} steps "
              f"({s['median_steps'] * SIM_DT:.3f} s) vs fixed "
              f"{smoothed_pair_count * EXECUTOR_STEPS} steps "
              f"({smoothed_pair_count * EXECUTOR_STEPS * SIM_DT:.3f} s)")

    # --- Dump full data for the report ---
    out = {
        "sim_dt": SIM_DT,
        "executor_steps_fixed": EXECUTOR_STEPS,
        "move_robot_smooth_default_steps_UNUSED": MOVE_ROBOT_SMOOTH_DEFAULT_STEPS,
        "used_free_boxel_id": used_free_id,
        "id_matches_log": used_free_id == "free_005",
        "linear_contrast": linear_metrics,
        "held_body_ids": sorted(held_body_ids),
        "path_ignored": sorted(path_ignored),
        "direct_path_collision_free": bool(direct_ok),
        "n_trials": len(trials),
        "trials_summary": [
            {"seed": t["seed"],
             "raw_n_waypoints": t["raw"]["n_waypoints"],
             "smoothed_n_waypoints": t["smoothed"]["n_waypoints"],
             "raw_worst_pair_delta_rad": t["raw"]["worst_pair_max_delta_rad"],
             "raw_worst_per_step_delta_rad": t["raw"]["worst_per_step_delta_rad"],
             "raw_worst_velocity_rad_s": t["raw"]["worst_implied_velocity_rad_s"],
             "smoothed_worst_pair_delta_rad": t["smoothed"]["worst_pair_max_delta_rad"],
             "smoothed_worst_per_step_delta_rad": t["smoothed"]["worst_per_step_delta_rad"],
             "smoothed_worst_velocity_rad_s": t["smoothed"]["worst_implied_velocity_rad_s"],
             }
            for t in trials
        ],
        "worst_overall_seed": worst_overall["seed"],
        "worst_overall_smoothed": worst_smoothed,
        "median_smoothed_worst_pair_delta_rad": median_smoothed_delta,
        "median_smoothed_worst_per_step_delta_rad": median_smoothed_per_step,
        "cap_summaries": cap_summaries,
        "log_moves": moves,
        "log_rrt_lines": rrt_lines,
        "linear_pair_count_run_wide": linear_pair_count,
        "smoothed_pair_count_run_wide": smoothed_pair_count,
        "fixed_total_steps_run_wide": fixed_total_steps,
        "full_trials": trials,
    }
    out_path = os.path.join(REPO_ROOT, "tools", "swarm_2026-08-22",
                            "probe_C_motion_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nFull data dumped to {out_path}")

    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
