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

Architecture (post-#26 refactor, 2026-04-19; sense-handler split 2026-05-05):
    belief.py       BeliefState — partial-observability bookkeeping.
    execution.py    execute_pick / execute_place / execute_stack /
                    sense_shadow_raycasting / compute_shadow_blockers /
                    release_held_object_in_place / handle_sense_action.
                    handle_sense_action is the dispatch-loop wrapper that
                    owns post-sense bookkeeping; see its docstring for the
                    break/release contract (audit S-01).
    reboxelize.py   reboxelize_free_space — octree+merge diff after mutations.
    THIS FILE       Phase 1-6 orchestration + CLI.  Reads top-down: setup,
                    boxel calc, registry, scenario selection, replan loop,
                    results.  Move/pick/place/stack handlers remain inline
                    because they share rebound locals (current_config,
                    held_body_id, grasp_constraint_id, shadow_occluder_map)
                    with the loop; sense was extracted because it owns no
                    rebound locals — only mutates containers.
"""

import sys
import os
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
                       scalability_scene, stack_scene,
                       random_pairs_scene)
from boxel_data import BoxelRegistry, BoxelType
from cell_merger import merge_free_space_cells
from free_space import split_free_boxel  # noqa: F401  (kept for future use)
from pddlstream_planner import PDDLStreamPlanner
from streams import RobotConfig
from robot_utils import (move_robot_smooth,
                         detect_execution_collisions)
from run_logger import RunLogger, parse_pipeline_args, report_run_outcome
from visualization import BoxelVisualizer

from belief import BeliefState
from reboxelize import reboxelize_free_space
from execution import (compute_shadow_blockers,
                       release_held_object_in_place,
                       execute_pick, execute_place, execute_stack,
                       handle_sense_action)


def goal_satisfied(goal, on_relations=None, target_found=False) -> bool:
    """
    Generic goal-predicate evaluator for the orchestration loop (audit #30).

    Decoupled from BeliefState because stack goals don't need a belief
    state at all — there are no shadows.  Heads we support:

      ('holding', obj)    — delegates to ``target_found`` (set by the
                            pick handler / sense outcome).
      ('on', a, b)        — checked against ``on_relations``, the
                            planner-side picture of the live stack
                            maintained by the stack action handler.
      ('on_table', obj)   — true iff ``obj`` is not a key in
                            ``on_relations`` (audit #41).  Consulted
                            only at replan boundaries where (handempty)
                            holds, so held cubes never confound this.
      ('and', g1, g2,..)  — conjunction; recurses.

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
    if head == 'on_table':
        # audit #41 — symbolic mirror.  An object is "on the table" iff
        # it is not stacked on another cube.  Held objects are absent
        # from on_relations as keys but goal_satisfied is only consulted
        # at replan boundaries (handempty), so this is sound.
        return str(goal[1]) not in on_relations
    return False


def _verify_cube_on(env, obj_name, support_name, eps_z=0.005):
    """
    Physics check that ``obj_name`` rests on ``support_name``
    (audit #40; tray-aware extension audit #49).  Used both
    per-action (gate the on_relations write after execute_stack) and
    at end-of-run (walk the goal AST).

    Two support shapes:
      - cube-on-cube: the cube's bottom face must match the support's
        top face within ε; XY centre inside the support's AABB.
      - cube-on-tray (``support_info.is_tray``): the cube settles
        INSIDE the tray cavity instead of touching the wall-top, so
        the bottom-z match is replaced by a z-range check (cube's
        bottom anywhere within the tray's full z extent ± ε).  The
        XY centre check is unchanged — the cube must still land
        within the tray's footprint.

    Tolerance ε = 5 mm is the audit's chosen default for 40-mm cubes.
    XY-centre check uses the support's plain AABB; tightening to a
    safe-inset (centre minus half cube footprint) is a FOR LATER
    refinement.

    Returns:
        (ok, reason) — reason is "" on success, a short
        diagnostic on failure.
    """
    if obj_name not in env.objects or support_name not in env.objects:
        return False, (f"missing body ('{obj_name}' or "
                       f"'{support_name}' not in env.objects)")
    o_min, o_max = p.getAABB(env.objects[obj_name].object_id)
    s_min, s_max = p.getAABB(env.objects[support_name].object_id)

    support_info = env.objects.get(support_name)
    is_tray_support = bool(getattr(support_info, 'is_tray', False))
    if is_tray_support:
        if not (s_min[2] - eps_z <= o_min[2] <= s_max[2] + eps_z):
            return False, (f"bottom_z={o_min[2]:.4f} not within tray z "
                           f"range [{s_min[2]:.4f}, {s_max[2]:.4f}] "
                           f"(ε={eps_z})")
    else:
        dz = abs(o_min[2] - s_max[2])
        if dz > eps_z:
            return False, (f"bottom_z={o_min[2]:.4f} not ≈ top_z="
                           f"{s_max[2]:.4f} (Δ={dz:.4f} > ε={eps_z})")

    o_cx = (o_min[0] + o_max[0]) / 2.0
    o_cy = (o_min[1] + o_max[1]) / 2.0
    if not (s_min[0] <= o_cx <= s_max[0]
            and s_min[1] <= o_cy <= s_max[1]):
        return False, (f"centre ({o_cx:.3f},{o_cy:.3f}) not within "
                       f"support XY AABB "
                       f"({s_min[0]:.3f}..{s_max[0]:.3f}, "
                       f"{s_min[1]:.3f}..{s_max[1]:.3f})")
    return True, ""


def _verify_on_table(env, obj_name, eps_z=0.005):
    """
    Physics check that ``obj_name`` rests on the table top
    (audit #41).  Counterpart to ``_verify_cube_on``: the cube's
    bottom z must match ``env.table_surface_height`` within ε.

    Returns:
        (ok, reason) — reason is "" on success, a short
        diagnostic on failure.
    """
    if obj_name not in env.objects:
        return False, f"missing body ('{obj_name}' not in env.objects)"
    o_min, _ = p.getAABB(env.objects[obj_name].object_id)
    table_z = env.table_surface_height
    dz = abs(o_min[2] - table_z)
    if dz > eps_z:
        return False, (f"bottom_z={o_min[2]:.4f} not ≈ table top_z="
                       f"{table_z:.4f} (Δ={dz:.4f} > ε={eps_z})")
    return True, ""


def _verify_holding(env, target_name, grasp_constraint_id):
    """
    Physics check that ``target_name`` is currently welded to the
    end-effector (audit S-18 — the holding-goal twin of
    ``_verify_cube_on``).

    The pre-fix holding-goal success was driven entirely by
    ``belief.is_target_found()``, which flips on a successful
    ``sense`` *or* a successful ``pick`` of the target name.  A
    sense-then-failed-pick run therefore reported SUCCESS while the
    gripper was empty (or holding the wrong body).  This helper
    closes that gap by querying PyBullet directly:

      1. There is an active grasp constraint.
      2. The constraint's child body (``bodyB``, info index 2 — same
         convention used in ``execute_place``) is the target body.

    Both checks together are a hard physics guarantee: a
    ``JOINT_FIXED`` constraint linking the EE link to the target
    body welds them rigidly until ``removeConstraint`` is called,
    so any active constraint with ``bodyB == target_body`` means
    the gripper is genuinely holding the target.

    NOTE on the dropped lift-above-table check (audit #36): an
    earlier revision also required ``target.AABB_min.z > table_z +
    5 mm``.  That contradicts the post-2026-04-22 execute_pick
    refactor, which intentionally terminates at the contact pose
    with the cube hovering at table height — the lift is supposed
    to come from the next planned ``move`` action's plan_motion.
    When ``pick`` is the LAST action of the plan (the typical
    terminal ``(holding ?o)`` goal) there is no follow-on move, so
    the cube legitimately sits at ``table_z`` and the old check
    false-failed every terminal-pick run.  See
    ``CODEBASE_AUDIT.txt#36`` for the design rationale; the
    optional cosmetic post-pick lift listed there (#36(d)) would
    paper over the visual weirdness but is not required for
    correctness.

    Returns:
        (ok, reason) — reason is "" on success, a short
        diagnostic on failure.
    """
    if grasp_constraint_id is None:
        return False, "no active grasp constraint (gripper is empty)"
    if target_name is None or target_name not in env.objects:
        return False, (f"target '{target_name}' not in env.objects "
                       f"(cannot resolve PyBullet body)")
    target_body = env.objects[target_name].object_id
    c_info = p.getConstraintInfo(grasp_constraint_id)
    cstr_body = c_info[2]
    if cstr_body != target_body:
        return False, (f"grasp constraint bodyB={cstr_body} ≠ "
                       f"target body={target_body} ('{target_name}')")
    return True, ""


def _verify_goal_physics(goal, env, grasp_constraint_id=None):
    """
    Walk a goal AST and physics-check each leaf clause
    (audits #40 + S-18).

    Heads currently handled:
      - ``and``       — recurse into sub-clauses
      - ``on``        — AABB stack check via ``_verify_cube_on``
      - ``on_table``  — AABB table-rest check via ``_verify_on_table``
                        (audit #41)
      - ``holding``   — gripper-constraint check via
                        ``_verify_holding`` (requires
                        ``grasp_constraint_id``)

    Other heads (e.g. future predicates like ``at_config``)
    trigger a one-line warning so coverage gaps surface in the run
    log instead of silently passing.

    Returns:
        list[str] — human-readable failure descriptions, empty on
        full pass.  Logged into timing_summary.json so eval tooling
        (#9) can filter false-positive successes.
    """
    failures = []
    # Defensive: PDDLStream goal ASTs are always tuples; a bare
    # string atom or None would crash on goal[0].  Return clean
    # instead so the verifier never bricks a run.
    if not isinstance(goal, tuple):
        return failures
    head = goal[0]  # predicate name; remaining tuple elements are args
    if head == 'and':
        # Conjunction: ('and', clause1, clause2, ...).  Recurse into
        # each subgoal and flatten failure lists with extend (not
        # append) so the caller sees a single flat list, not a list
        # of lists.
        for sub in goal[1:]:
            failures.extend(
                _verify_goal_physics(sub, env, grasp_constraint_id))
    elif head == 'on':
        a, b = str(goal[1]), str(goal[2])
        ok, reason = _verify_cube_on(env, a, b)
        if not ok:
            failures.append(f"(on {a} {b}) — {reason}")
    elif head == 'on_table':
        x = str(goal[1])
        ok, reason = _verify_on_table(env, x)
        if not ok:
            failures.append(f"(on_table {x}) — {reason}")
    elif head == 'holding':
        x = str(goal[1])
        ok, reason = _verify_holding(env, x, grasp_constraint_id)
        if not ok:
            failures.append(f"(holding {x}) — {reason}")
    else:
        # Unknown predicate — verifier coverage gap.  Surface it in
        # the log so a new goal predicate without a verifier doesn't
        # quietly pass.
        print(f"  WARNING: _verify_goal_physics: unhandled goal "
              f"head '{head}' — clause not physics-verified")
    return failures


def build_stack_goal(stackable_objects, stack_height, rng=None):
    """
    Pick ``stack_height`` distinct objects from ``stackable_objects`` and
    return a goal for a tower of that height (audit #30).

    For height H the goal is::

        ('and', ('on', t_1, t_2), ..., ('on', t_{H-1}, t_H),
                ('on_table', t_H))

    where ``t_1`` is the top and ``t_H`` is the base.  The
    ``on_table`` clause (audit #41) makes the table-resting base
    explicit so the verifier can rule out floating-tower
    interpretations.

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
    base = chosen[-1]                        # t_H — the cube at the bottom
    clauses = pairs + [('on_table', base)]   # audit #41 — ground the tower
    return ('and',) + tuple(clauses)


def build_tray_stack_goal(targets, tray_name, rng=None):
    """
    Goal builder for --goal find-and-tray-stack (audit #49).

    For ``targets = [c_0, ..., c_{H-1}]`` (after a shuffle) and tray
    ``T`` the goal is::

        ('and', ('on', c_0, T),
                ('on', c_1, c_0),
                ('on', c_2, c_1),
                ...
                ('on', c_{H-1}, c_{H-2}))

    ``c_0`` is the BASE that anchors the tower onto the tray.  This
    inverts ``build_stack_goal``'s top-down convention because the tray
    plays the role of the table-anchor that ``(on_table base)`` plays
    for cube-stack goals.  No ``(on_table tray)`` clause is emitted —
    the tray is fixed-base and not picked, so the planner-side init
    fact is sufficient and the verifier need not check it.

    A 1-target call collapses to ``('and', ('on', c_0, T))`` — a
    single-clause conjunction that ``_verify_goal_physics`` and
    ``goal_satisfied`` already handle.

    Args:
        targets: discovered/visible cube names to include in the
            tower.  All of them end up on the tray; ``--stack-height``
            is not consulted for this goal.
        tray_name: ObjectInfo name of the tray (commonly "tray").
        rng: ``random.Random`` for reproducible shuffling; defaults to
            the module ``random``.
    """
    if not targets:
        raise ValueError(
            "--goal find-and-tray-stack needs at least 1 target. "
            "Increase --n-targets or pick a scene that spawns cubes."
        )
    rng = rng or random
    chosen = list(targets)
    rng.shuffle(chosen)
    base_clause = ('on', chosen[0], tray_name)
    pairs = [('on', chosen[i + 1], chosen[i])
             for i in range(len(chosen) - 1)]
    return ('and',) + tuple([base_clause] + pairs)


def main(gui=True, run_logger=None, scene_config=None,
         draw_boxel_overlays=True, show_free=False,
         goal_kind='holding', stack_height=2,
         unit_costs=False,
         baseline: str = 'semantic',
         uniform_cell_size: float = 0.05,
         run_config: Optional[Dict[str, Any]] = None):
    print("=" * 60)
    print("FULL PIPELINE: PDDLStream + Replanning")
    print("=" * 60)

    # Echo the run configuration so saved logs are self-documenting:
    # later baseline-vs-feature comparisons (e.g. eval runner audit #9)
    # need to know which flags produced these timings.
    if run_config:
        print("\n--- Run configuration ---")
        for k, v in run_config.items():
            print(f"  {k:18s} = {v}")

    # =========================================================
    # PHASE 1: Setup Environment
    # =========================================================
    print("\n--- Phase 1: Environment Setup ---")
    env = BoxelTestEnv(gui=gui, scene_config=scene_config)

    # audit #10 — uniform-grid baseline.  Toggle BoxelTestEnv's
    # free-space dispatch and (re)build the lattice at the requested
    # cell size before any boxel/registry work in Phase 2.  Default
    # path (baseline='semantic') leaves env.use_uniform_grid=False, so
    # generate_free_space falls through to the octree pipeline as before.
    # Audit #66 (Plan A) — auto-tune cell size to fit the largest
    # object AABB.  Default uniform cell 0.05 m is smaller than default
    # occluders (6-7 cm wide, 12-16 cm tall), so under uniform mode
    # every (boxel_fits ?occluder ?cell) atom is unsatisfiable on all
    # 3 axes (streams.py:369), the place precondition can't ground,
    # and PDDLStream loops searching for a plan that cannot exist
    # (logs/run_2026-05-09_10-48-13/: 2480 cells, 2472 boxel_fits,
    # iter-1 Cost: inf).  Largest AABB axis is the OCCLUDER HEIGHT,
    # so auto_cell ~ 0.17 m for the default scene.  Headroom +0.01 m
    # for PyBullet contact margin.  Acts as a SAFETY GUARD: if the
    # user passes --uniform-cell-size already >= auto_cell, keep it;
    # otherwise bump up.
    #
    # Audit #67 follow-up — also propagate the same value to the
    # semantic octree's min_resolution so both baselines have the
    # SAME smallest possible boxel size.  Without this match, the
    # octree subdivides down to its 0.035 m default while uniform
    # uses 0.06-0.17 m cells — the comparison ends up dominated by
    # grounding cost (number of cells), not the underlying
    # discretization strategy.  We compute effective_cell
    # unconditionally and apply it to whichever baseline is active.
    max_extent = 0.0
    for name, info in env.objects.items():
        if name in ("plane", "table", "robot"):
            continue
        if getattr(info, "is_tray", False):
            continue
        if info.size is None:
            continue
        max_extent = max(max_extent, float(np.max(info.size)))
    auto_cell = max_extent + 0.01
    effective_cell = max(uniform_cell_size, auto_cell)
    print(f"  [audit-66/67] Effective minimum boxel size: "
          f"{effective_cell:.3f} m (largest object AABB "
          f"{max_extent:.3f} m + 0.01 m headroom).")

    if baseline == 'uniform':
        env.use_uniform_grid = True
        if abs(effective_cell - 0.05) > 1e-9:
            env.set_uniform_cell_size(effective_cell)
    else:
        # Semantic octree — clamp the minimum leaf size to
        # effective_cell so leaves can't be smaller than uniform's
        # cells.  Larger leaves are still allowed (CellMerger keeps
        # collapsing same-colour neighbours).
        env.free_space_generator.min_resolution = effective_cell

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
    # audit #10 — uniform baseline produces a strict static lattice;
    # CellMerger would collapse adjacent uniform cubes back into
    # variable-sized rectangles, defeating the uniform property.  Skip
    # merging under that mode; semantic mode keeps the merge as before
    # (octree leaves benefit from collapse).
    merged_free = (free_boxels if env.use_uniform_grid
                   else merge_free_space_cells(free_boxels))
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
    # access to.  Hidden detection uses camera-ray occlusion (the same
    # criterion as Phase 1 / oracle_detect_objects — the physically
    # meaningful definition: "robot can't see it from the camera").
    # The robot only discovers this through sensing.
    print("\n--- Phase 4: Hidden Object Scenario ---")

    # audit #49 — also exclude is_tray=True (the fixed-base tray is a
    # support surface, never a pickable target; it would otherwise leak
    # into stack_target_objects under --goal find-and-tray-stack and
    # produce nonsense (on tray <cube>) clauses in the goal AST).
    all_targets = [
        name for name, info in env.objects.items()
        if not info.is_occluder and not info.is_tray
        and name not in ("plane", "table", "robot")
    ]

    # audit #67 — Hidden detection uses camera-ray occlusion, matching
    # Phase 1.  The previous AABB-containment criterion (target's
    # position lies inside a shadow boxel's AABB) is a downstream
    # geometric proxy that disagrees with camera-ray occlusion near
    # shadow-cone edges; using it as the hidden criterion silently
    # aborts ~16% of seeds in the n_occluders=1..3 eval prefix when a
    # target is camera-occluded but lies just outside every shadow
    # AABB.  AABB containment is now a best-effort follow-up that
    # supplies one shadow id per hidden target for the oracle log
    # line; it is allowed to be empty for individual targets without
    # aborting the run.
    visible_now, _ = env.oracle_detect_objects()
    hidden_targets_set = set(all_targets) - set(visible_now)
    target_to_shadow = {}
    for tname in hidden_targets_set:
        tpos = np.array(env.objects[tname].position)
        for shadow_id in shadows:
            sb = registry.get_boxel(shadow_id)
            if sb and np.all(tpos >= sb.min_corner) and np.all(tpos <= sb.max_corner):
                target_to_shadow[tname] = shadow_id
                break

    visible_target_locations = {}
    on_relations: Dict[str, str] = {}      # stacked_obj -> support_obj
    physical_failures: list = []           # audit #40 — per-action verifier log
    stack_target_objects = []              # populated only for --goal stack

    if goal_kind == 'holding':
        if hidden_targets_set:
            hidden_targets_ordered = [t for t in all_targets
                                      if t in hidden_targets_set]
            target_name = random.choice(hidden_targets_ordered)
            oracle_hidden_shadow = target_to_shadow.get(target_name)
            print(f"  Target: {target_name}")
            if oracle_hidden_shadow is not None:
                print(f"  ORACLE: Actually hidden in {oracle_hidden_shadow} "
                      f"(camera-ray occlusion; shadow AABB also contains "
                      f"its centre)")
            else:
                print(f"  ORACLE: Actually hidden by camera-ray occlusion "
                      f"(shadow AABB is an axis-aligned approximation and "
                      f"does not contain its centre — boundary case)")
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
    elif goal_kind == 'find-and-tray-stack':
        # audit #55 — 2-cube tower on tray (smallest goal that exercises
        # sense → pick → stack end-to-end).  One VISIBLE cube placed on
        # the tray, then one HIDDEN cube sensed and stacked on top of
        # the visible one.  Both cubes drawn from all_targets — same
        # physical size; visible/hidden is the only role distinction.
        # Replaces #49's multi-cube goal.
        tray_obj = next((name for name, info in env.objects.items()
                         if info.is_tray), None)
        if tray_obj is None:
            env.close()
            raise RuntimeError(
                "--goal find-and-tray-stack requires a tray in the scene. "
                "The CLI auto-enables it; if you constructed the SceneConfig "
                "manually, set enable_tray=True."
            )
        # audit #67 — classify by camera-ray occlusion (matches Phase 1
        # and the holding-goal path above), not AABB containment.
        visible_targets = [t for t in all_targets
                           if t not in hidden_targets_set]
        hidden_targets = [t for t in all_targets
                          if t in hidden_targets_set]
        if not visible_targets or not hidden_targets:
            env.close()
            raise RuntimeError(
                f"find-and-tray-stack needs at least 1 visible AND 1 "
                f"hidden target.  Got {len(visible_targets)} visible / "
                f"{len(hidden_targets)} hidden.  Adjust --seed or "
                f"--n-hidden so both roles are populated."
            )
        chosen_visible = random.choice(visible_targets)
        chosen_hidden = random.choice(hidden_targets)
        stack_target_objects = [chosen_visible, chosen_hidden]
        print(f"  2-cube tray tower: {chosen_visible} (on tray) + "
              f"{chosen_hidden} (on {chosen_visible})")
        # Visible cube → emit obj_at_boxel; hidden cube stays unknown
        # until the sense action uncovers it.
        for boxel in registry.boxels.values():
            if boxel.object_name == chosen_visible:
                visible_target_locations[chosen_visible] = boxel.id
                break
        goal = ('and', ('on', chosen_visible, tray_obj),
                       ('on', chosen_hidden, chosen_visible))
        target_name = chosen_hidden  # belief / sense logging
        print(f"  Find-and-tray-stack goal: {goal}")
        print(f"  Tray: {tray_obj}")
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
    # compute_shadow_blockers now applies the parent-relationship fallback
    # internally for any shadow whose ray-grid produced no blockers, so
    # there's nothing to do here per shadow EXCEPT warn when even the
    # parent linkage is missing — those shadows are unreachable by the
    # planner and would silently be treated as view_clear.
    for shadow_id in shadows:
        if not shadow_occluder_map.get(shadow_id):
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
    #
    # Audit #46: streams operate on env.plan_client_id (a separate DIRECT-
    # mode PyBullet world) so that the visible GUI arm is never teleported
    # during planning.  Body ids do NOT match between clients — we translate
    # GUI ids to plan ids via env.plan_body_id() at the planner boundary.
    # Execution-side code (execute_pick / detect_execution_collisions /
    # compute_shadow_blockers) keeps using GUI ids unchanged.
    object_body_ids = {}        # plan-side, consumed by BoxelStreams
    for name, obj_info in env.objects.items():
        if name not in ("plane", "table", "robot"):
            object_body_ids[name] = env.plan_body_id(obj_info.object_id)
    for boxel in registry.boxels.values():
        if boxel.object_name and boxel.object_name in object_body_ids:
            object_body_ids[boxel.id] = object_body_ids[boxel.object_name]

    # Two parallel support-id sets: planner needs plan-side ids (its
    # collision checks run on plan_client_id); execution needs the GUI ids
    # (detect_execution_collisions runs on client_id).
    planner_support_body_ids = frozenset({
        env.plan_body_id(env.objects["plane"].object_id),
        env.plan_body_id(env.objects["table"].object_id),
    })
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
    tray_name = next((name for name, info in env.objects.items()
                      if info.is_tray), None)
    planner = PDDLStreamPlanner(registry, robot_id=env.plan_robot_id,
                                shadow_occluder_map=shadow_occluder_map,
                                physics_client=env.plan_client_id,
                                object_body_ids=object_body_ids,
                                support_body_ids=planner_support_body_ids,
                                camera_pos=env.camera_position,
                                tray_name=tray_name)

    # The planner needs to reason about every object that may participate
    # in the goal.  For 'holding' that's just the chosen target; for
    # 'stack' it's every cube in the requested tower.
    planner_target_objects = (
        stack_target_objects
        if goal_kind in ('stack', 'find-and-tray-stack')
        else [target_name]
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
    # Per-call planner.plan() durations.  Captured originally for
    # audit #30 baseline timing; now consumed by the eval runner
    # (audit #9) for scalability plots.
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
    elif goal_kind == 'find-and-tray-stack':
        # audit #49 — sense (up to 4 attempts/shadow) + pick+stack
        # (2 actions/cube) + slack.
        max_replans = 4 * len(shadows) + 2 * len(stack_target_objects) + 3
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
    # Audit #21: shadows we gave up on after 3 still_blocked outcomes
    # are NOT observed empty — the loop only LIES about them being
    # not_here so the planner stops re-attempting them.  Track the IDs
    # so the run report can distinguish observed-empty shadows from
    # blocked-unresolved ones (no false "Searched all" claim).  The
    # real fix (re-ground blocker atoms) is audit #47, deferred out of
    # scope 2026-05-06.
    blocked_giveup_shadows: set = set()

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
        if goal_kind == 'find-and-tray-stack':
            print(f"Tray-stack progress: {on_relations} "
                  f"(unknown shadows: {len(unknown_shadows)})")
        elif goal_kind == 'holding':
            print(f"Unknown shadows remaining: {len(unknown_shadows)}")
            if not unknown_shadows:
                # Audit #21: 'all_searched' is the loop-termination tag,
                # but with the still_blocked 3-strike give-up some of
                # the shadows below were never observed empty.  The
                # final FAILED message classifies on blocked_giveup_shadows.
                exit_reason = "all_searched"
                if blocked_giveup_shadows:
                    print(f"ERROR: No unknown shadows remain — but "
                          f"{len(blocked_giveup_shadows)} of "
                          f"{len(shadows)} were given up after repeated "
                          f"still_blocked outcomes (audit #21), not "
                          f"observed empty.  Target may still be hiding "
                          f"in: {sorted(blocked_giveup_shadows)}")
                else:
                    print("ERROR: Searched all shadows but target not found!")
                break
        else:
            print(f"Stack progress: {on_relations} (goal {goal})")

        # --- Held-object handling (audit #58) -----------------------------
        # Pre-#58: any held object was unconditionally dropped here so the
        # planner's _build_init could rely on (handempty).  That cost ~4
        # wasted actions per re-grasp cycle whenever the action loop broke
        # while holding (e.g. sense returned empty after pick).
        # Post-#58: pass held_obj=name into planner.plan() so init emits
        # (holding ?o) and the next plan continues mid-grasp.  release_held_-
        # object_in_place stays as a SAFETY NET for the case where the
        # held cube blocks all plans (planner returns None below — see
        # the safety-net branch after planner.plan).
        held_obj_name: Optional[str] = None
        if held_body_id is not None:
            held_obj_name = body_id_to_name.get(held_body_id)

        # Ensure the free-space partition is consistent before the planner
        # reads the registry (audit #25).  After a place action,
        # update_after_place sets registry.dirty because the consumed
        # free boxel is gone but no replacement exists yet.  If a sense
        # action already triggered reboxelization (clearing the flag),
        # this is a no-op — avoiding the double octree+merge cost.
        if registry.dirty:
            reboxelize_free_space(registry, env, boxel_centers, viz, show_free)

        # Audit #46: mirror the live GUI scene into the plan client and let
        # planner.plan() run unwrapped.  All IK/RRT/collision-check calls
        # inside the streams target env.plan_client_id (a DIRECT-mode world),
        # so the visible arm is no longer teleported and the OpenGL window
        # stays interactive throughout planning.  The old outer
        # `with RenderingLock(env.client_id):` block was the source of the
        # GUI freeze — it's no longer needed.
        env.sync_to_plan_client(held_body_id=held_body_id)
        plan_t0 = time.perf_counter()
        plan = planner.plan(
            target_objects=planner_target_objects,
            goal=goal,
            current_config=current_config,
            known_empty_shadows=known_empty,
            moved_occluders=dict(belief.occluders_moved),
            max_time=1800.0,  # audit #54 follow-up — bumped from 120 s; the
                              # find-and-tray-stack 1-cube hidden run gave up at
                              # 45 s on adaptive-search exhaustion under the
                              # 120 s cap, so more rope lets the sampler retry
                              # more skeletons / stream samples.
            verbose=False,
            visible_target_locations=visible_target_locations,
            # on/clear facts only emitted into init when stackable
            # objects is supplied — holding-goal runs pay nothing.
            # find-and-tray-stack (audit #49) reuses the same plumbing
            # because its goal AST is built from (on ?o ?x) clauses.
            on_relations=(on_relations
                          if goal_kind in ('stack', 'find-and-tray-stack')
                          else None),
            stackable_objects=(stack_target_objects
                               if goal_kind in ('stack',
                                                'find-and-tray-stack')
                               else None),
            unit_costs=unit_costs,
            held_obj=held_obj_name,  # audit #58 — preserve grasp across replans
        )
        plan_dt = time.perf_counter() - plan_t0

        # audit #58 SAFETY NET — if the held cube blocked all plans (e.g.
        # collides with everything from its current pose), drop it and
        # try once more from (handempty).  Mirrors the pre-#58 behaviour
        # for this single edge case.
        if plan is None and held_obj_name is not None:
            print(f"  audit #58: planner found no plan with {held_obj_name} "
                  f"held — falling back to release-and-replan.")
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
            held_obj_name = None
            if drop_state.get("shadow_occluder_map") is not None:
                shadow_occluder_map = drop_state["shadow_occluder_map"]
            if drop_state.get("current_config") is not None:
                current_config = drop_state["current_config"]
            if not drop_ok:
                exit_reason = "drop_failed"
                print("ERROR: Could not release held object after retries — "
                      "aborting to avoid double-grasp.")
                break
            env.sync_to_plan_client(held_body_id=None)
            plan_t1 = time.perf_counter()
            plan = planner.plan(
                target_objects=planner_target_objects,
                goal=goal,
                current_config=current_config,
                known_empty_shadows=known_empty,
                moved_occluders=dict(belief.occluders_moved),
                max_time=1800.0,
                verbose=False,
                visible_target_locations=visible_target_locations,
                on_relations=(on_relations
                              if goal_kind in ('stack', 'find-and-tray-stack')
                              else None),
                stackable_objects=(stack_target_objects
                                   if goal_kind in ('stack',
                                                    'find-and-tray-stack')
                                   else None),
                unit_costs=unit_costs,
                held_obj=None,
            )
            plan_dt += time.perf_counter() - plan_t1
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
                # audit #60 fix (i) — if current_config (post-lift, post-action
                # arm pose) differs from traj.waypoints[0] (the planner's q1 =
                # compute_kin contact pose), the planner-baked trajectory would
                # drop the arm BACK to contact altitude before traversing.
                # Re-invoke plan_motion at execution time so the trajectory
                # starts from the actual lifted arm pose and uses the up-to-
                # date plan_client cube layout (synced by fix (ii) at the end
                # of execute_place / execute_stack).  Carries q1's collision-
                # check metadata (ignored_body_ids, held_body_ids,
                # grasp_ee_offset) so plan_motion's held-body tracking and
                # is_pick_place detection behave as the planner originally
                # invoked it.  On replan failure, break the dispatch loop and
                # let the outer replan recover from current_config — same
                # path as IK failures during pick/place.
                if current_config is not None and len(traj.waypoints) > 0:
                    diff = float(np.linalg.norm(
                        np.asarray(current_config.joint_positions)
                        - np.asarray(traj.waypoints[0].joint_positions)))
                    if diff > 1e-2:
                        q1_runtime = RobotConfig(
                            joint_positions=np.asarray(current_config.joint_positions),
                            name=f"{current_config.name}_runtime",
                            ignored_body_ids=q1.ignored_body_ids,
                            held_body_ids=q1.held_body_ids,
                            grasp_ee_offset=q1.grasp_ee_offset,
                        )
                        try:
                            (new_traj,) = next(planner.streams.plan_motion(q1_runtime, q2))
                            # print(f"    [#60-fix(i)] replanned motion from runtime pose "
                            #       f"(prior diff={diff:.4f} rad, "
                            #       f"{len(new_traj.waypoints)} waypoints)")
                            traj = new_traj
                        except StopIteration:
                            # print(f"    [#60-fix(i)] plan_motion could not replan from "
                            #       f"runtime pose (diff={diff:.4f}) — breaking dispatch "
                            #       f"loop to trigger outer replan")
                            break

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
                # See pipeline_actions.handle_sense_action for the full
                # body.  When result.continue_ is False the dispatch
                # loop breaks → outer replan loop drops any held object
                # before the next planner.plan() (audit S-01 contract).
                sense_result = handle_sense_action(
                    action_params=params,
                    env=env,
                    registry=registry,
                    belief=belief,
                    viz=viz,
                    target_name=target_name,
                    robot_id=robot_id,
                    support_body_ids=support_body_ids,
                    shadows=shadows,
                    occluders=occluders,
                    shadow_occluder_map=shadow_occluder_map,
                    blocked_counts=blocked_counts,
                    blocked_giveup_shadows=blocked_giveup_shadows,
                    boxel_centers=boxel_centers,
                    boxel_to_pybullet=boxel_to_pybullet,
                    object_body_ids=object_body_ids,
                    body_id_to_name=body_id_to_name,
                    show_free=show_free,
                )
                if not sense_result.continue_:
                    break

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
                # Audit #48: clear the symbolic stack relation so the next
                # _build_init does not re-emit a stale (on obj_str ?x) fact
                # while also asserting (holding obj_str).  Mirrors the PDDL
                # pick conditional effect (forall ?x: when (on ?o ?x) then
                # not (on ?o ?x)).  No-op when obj_str was on the table.
                on_relations.pop(obj_str, None)
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

                # Audit #40: gate the on_relations write on a physics
                # check.  execute_stack's 60-step settle can leave a
                # cube wobbling or already on the floor; writing the
                # relation in that case would lie to goal_satisfied(),
                # the next _build_init, AND the end-of-run summary.
                stack_ok, stack_reason = _verify_cube_on(
                    env, obj_str, on_obj_str)
                if not stack_ok:
                    print(f"    PHYSICAL_FAILURE: stack {obj_str} on "
                          f"{on_obj_str} — {stack_reason}")
                    physical_failures.append({
                        "action": "stack",
                        "obj": obj_str,
                        "on": on_obj_str,
                        "reason": stack_reason,
                        "plan": plan_count,
                    })
                    break  # replan — on_relations stays as-is
                # Replace any prior support of obj_str (re-stacking) —
                # the conditional pick effect in the domain already
                # cleared the old support symbolically.
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
    # Classify outcome (the exit_reason set during the loop tells us
    # exactly why we stopped) and hand off to report_run_outcome for
    # printing + timing_summary.json write.
    physics_failures: list = []
    if goal_kind == 'holding':
        # Audit S-18: belief.is_target_found() flips on a successful
        # sense OR a successful pick — neither implies the gripper
        # is currently welded to the target body.  A sense-then-
        # failed-pick run (or a slip after a successful pick) leaves
        # the belief flag True but the gripper empty / holding the
        # wrong body.  Gate the success on a physics check so the
        # holding-goal path matches the stack-goal path's audit-#40
        # rigour.
        symbolic_ok = belief.is_target_found()
        if symbolic_ok:
            ok, reason = _verify_holding(env, target_name, grasp_constraint_id)
            if not ok:
                physics_failures.append(f"(holding {target_name}) — {reason}")
                print(f"  PHYSICAL_FAILURE (goal): "
                      f"(holding {target_name}) — {reason}")
                # Reclassify the exit reason so the FAILED summary
                # in report_run_outcome doesn't print the misleading
                # "Replan limit reached" default — the loop exited
                # cleanly on belief, the failure is a physics
                # mismatch with that belief.
                if exit_reason is None:
                    exit_reason = "physics_mismatch"
        success = symbolic_ok and not physics_failures
    else:
        symbolic_ok = goal_satisfied(goal, on_relations)
        if symbolic_ok:
            # Audit #40: verify each (on a b) goal clause against
            # PyBullet AABBs before declaring success.  Catches
            # post-stack collapses that slipped past the per-action
            # gate (e.g. a tower falling later under a subsequent
            # action's vibration).
            physics_failures = _verify_goal_physics(
                goal, env, grasp_constraint_id=grasp_constraint_id)
            for pf in physics_failures:
                print(f"  PHYSICAL_FAILURE (goal): {pf}")
        success = symbolic_ok and not physics_failures

    report_run_outcome(
        success=success,
        exit_reason=exit_reason,
        goal_kind=goal_kind,
        goal=goal,
        target_name=target_name,
        on_relations=on_relations,
        belief=belief,
        plan_count=plan_count,
        shadows=shadows,
        blocked_giveup_shadows=blocked_giveup_shadows,
        max_replans=max_replans,
        plan_times=plan_times,
        total_plan_time=total_plan_time,
        physical_failures=physical_failures,
        physics_failures=physics_failures,
        run_config=run_config,
        run_logger=run_logger,
    )

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
    # CLI interface supporting four scene presets:
    #   default     — hand-crafted scene with cubes (deterministic)
    #   mixed       — diverse shapes, seeded for reproducibility
    #   scalability — random placement with configurable counts,
    #                 used for batch evaluation across many seeds
    #   stack       — N identical cubes, no occluders (audit #30)
    # Argparse + post-parse validation lives in run_logger.py.
    args = parse_pipeline_args()

    # Audit #9: seed every process-global RNG from --seed so two runs
    # with the same seed are bit-identical end-to-end (target choice,
    # PDDL init shuffle, IK joint sampling, RRT goal bias, path-smoothing
    # pivots, placement-offset shuffle).  Scene placement uses local
    # np.random.RandomState(seed) and is unaffected; this hook only
    # tames the *global* random / np.random calls.  FastDownward's
    # internal tie-breaking RNG (random_seed=-1 in the vendored
    # PDDLStream) is NOT overridden — same noise affects every approach
    # at the same seed, so approach-vs-baseline averaging stays valid.
    random.seed(args.seed)
    np.random.seed(args.seed)

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
        'random-pairs': lambda: random_pairs_scene(
            n_occluders=args.n_occluders,
            extra_distractors=args.n_extra_distractors,
            seed=args.seed,
        ),
    }
    scene_cfg = scene_builders[args.scene]()

    # audit #49 — find-and-tray-stack is the only goal that needs the
    # tray entity; enable it on whatever scene was selected (default,
    # scalability, etc.) so the user does not have to construct a custom
    # SceneConfig just to opt the tray in.
    if args.goal == 'find-and-tray-stack':
        scene_cfg.enable_tray = True

    # Snapshot of effective CLI flags echoed into the per-run log and the
    # JSON timing summary so cross-run comparisons can group by config
    # (consumed by eval runner audit #9).  Booleans match the kwargs we
    # hand to main() rather than the inverted no_* arg names for readability.
    # For ``random-pairs`` the per-axis counts (occluders/targets/hidden)
    # are derived from the randomized pair draw inside the scene builder,
    # so we report the ACTUALLY-SPAWNED counts here rather than the unused
    # CLI defaults — otherwise the banner contradicts the scene that was
    # built (was a debugging trap when placement failed).
    effective_n_occluders = len(scene_cfg.occluders)
    effective_n_targets = len(scene_cfg.targets)
    effective_n_hidden = scene_cfg.n_hidden_targets
    run_config = {
        "scene":        args.scene,
        "n_occluders":  effective_n_occluders,
        "n_targets":    effective_n_targets,
        "n_hidden":     effective_n_hidden,
        "n_extra_distractors": args.n_extra_distractors,
        "n_objects":    args.n_objects,
        "seed":         args.seed,
        "goal":         args.goal,
        "stack_height": args.stack_height,
        "unit_costs":   args.unit_costs,
        "baseline":     args.baseline,
        "uniform_cell_size": args.uniform_cell_size,
        "gui":          not args.no_gui,
        "boxel_viz":    not args.no_boxel_viz,
        "show_free":    args.show_free,
        "log_level":    args.log_level,
    }

    # RunLogger captures all artefacts (PDDL files, boxel data, logs)
    # regardless of console verbosity for post-mortem analysis.
    # Placement pre-flight (audit #68 follow-up).  ``random-pairs`` with
    # no explicit ``--seed`` auto-rolls a fresh seed (run_logger sets
    # ``args.seed_auto=True``); at unlucky seeds the hidden-target placer
    # exhausts its budget because each occluder hosts only ~1 hidden
    # target (lateral jitter ≈ occ_half − target_half ≈ 0) and the
    # back-of-table occluders project shadows off the safe-window edge.
    # We probe scene construction headlessly (DIRECT mode) and re-roll
    # the seed on failure BEFORE the GUI is opened — otherwise every
    # retry flashes a new PyBullet window open and closed and the user
    # only sees the final scene appear after several aborted ones (real
    # bug report).  Up to 10 retries when ``seed_auto``; an explicit
    # ``--seed`` is checked once and must succeed or fail loud so
    # reproducibility is preserved.  Scene construction is deterministic
    # in scene_cfg.seed, so the pre-flight verifies the EXACT scene that
    # the real run will build a moment later.
    seed_auto = getattr(args, 'seed_auto', False)
    max_attempts = 11 if seed_auto else 1
    for attempt in range(max_attempts):
        try:
            probe_env = BoxelTestEnv(gui=False, scene_config=scene_cfg)
            probe_env.close()
            break
        except RuntimeError as e:
            if "Could not place" not in str(e) or attempt + 1 >= max_attempts:
                raise
            args.seed = random.randint(0, 2**31 - 1)
            random.seed(args.seed)
            np.random.seed(args.seed)
            scene_cfg = scene_builders[args.scene]()
            if args.goal == 'find-and-tray-stack':
                scene_cfg.enable_tray = True
            run_config["seed"] = args.seed
            run_config["n_occluders"] = len(scene_cfg.occluders)
            run_config["n_targets"] = len(scene_cfg.targets)
            run_config["n_hidden"] = scene_cfg.n_hidden_targets
            print(f"[retry {attempt + 1}/{max_attempts - 1}] "
                  f"placement failed ({e}); rerolling to "
                  f"seed={args.seed}",
                  file=sys.stderr)

    # Single real-pipeline run with the validated scene_cfg.
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
            unit_costs=args.unit_costs,
            baseline=args.baseline,
            uniform_cell_size=args.uniform_cell_size,
            run_config=run_config,
        )
    finally:
        logger.close()
    sys.exit(0 if success else 1)
