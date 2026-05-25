#!/usr/bin/env python3
"""
render_thesis_figs.py -- open the Semantic Boxels scene + partition in the
PyBullet GUI and FREEZE the window so you can screenshot it cleanly.

WHY THIS SHAPE
    The boxel wireframes / grid are PyBullet *debug-draw* (addUserDebugLine) and
    the labels are addUserDebugText. Those render ONLY in the live GUI window --
    they never appear in an offscreen getCameraImage (confirmed: an offscreen
    render came back as the bare scene). So to get the real wireframe look we use
    the GUI and YOU screenshot it. This script just mirrors test_full_pipeline.py
    Phases 1-3 (scene -> boxels -> registry -> wireframe overlay), then holds the
    window still for --freeze seconds so you have time to grab it.

HOW TO CAPTURE
    Screenshot the WINDOW with Alt+PrtScn -- NOT full screen. Only the PyBullet
    window's own chrome (title bar / Explorer-Test tabs / RGB-depth insets) is in
    frame, and that gets cropped afterwards. Full-screen drags in the taskbar /
    desktop / any other app, which is what we are trying to avoid.

USAGE (WSL, repo root, wsl_env active, DISPLAY set -- same env as run_boxels)
    # matched partition pair: same seed, semantic then uniform. Screenshot each
    # window while it is frozen.
    python3 tools/render_thesis_figs.py --scene random-pairs \
        --goal find-and-tray-stack --seed 7 --pair --freeze 15

    # a single clean boxelized scene (object + shadow boxels; free cells off):
    python3 tools/render_thesis_figs.py --scene random-pairs --goal holding \
        --n-occluders 3 --seed <a seed that places> --freeze 15

    All the usual run_boxels / test_full_pipeline scene flags are accepted
    (--scene --goal --seed --n-occluders --n-extra-distractors --n-hidden
     --n-targets --n-objects --stack-height --baseline --uniform-cell-size
     --min-boxel-size --show-free) because parse_pipeline_args() is reused
     verbatim. Extra flags handled here (stripped before that parser runs):
       --freeze SECONDS   how long to hold each window (default 12; >= 10 asked)
       --pair             render semantic then uniform at the same seed
       --window-width N / --window-height N   GUI window size (default 1280x720)

    --pair forces free-space cells visible (the comparison IS the cell density).
    A single run leaves them off unless you pass --show-free.

NOTE
    Lives in tools/, imports the repo's own modules, touches no core file. The
    GUI render thread keeps drawing during time.sleep(), so the window stays live
    (you can rotate it) while frozen. If the SECOND window of --pair misbehaves,
    run the two commands separately instead.
"""
from __future__ import annotations

import os
import random
import sys
import time

import numpy as np

# This script lives in <repo>/tools/, but the modules it imports live in <repo>/.
# Running "python3 tools/render_thesis_figs.py" puts tools/ on sys.path[0], NOT
# the repo root, so add the repo root explicitly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pybullet as p  # noqa: E402  (after sys.path fix)

from boxel_env import (BoxelTestEnv,
                       default_scene, mixed_shapes_scene,
                       scalability_scene, stack_scene,
                       random_pairs_scene)
from boxel_data import BoxelRegistry
from cell_merger import merge_free_space_cells
from visualization import BoxelVisualizer
from run_logger import parse_pipeline_args


# ----------------------------------------------------------------------
# Custom flags pulled out of sys.argv BEFORE parse_pipeline_args() runs, so the
# reused scene parser never sees them and scene construction stays identical to
# test_full_pipeline.py.
# ----------------------------------------------------------------------
def _pop_flag(argv, name):
    if name in argv:
        argv.remove(name)
        return True
    return False


def _pop_opt(argv, name, default):
    if name in argv:
        i = argv.index(name)
        if i + 1 >= len(argv):
            raise SystemExit(f"{name} requires a value")
        val = argv[i + 1]
        del argv[i:i + 2]
        return val
    return default


def _build_scene(args):
    """Exactly mirror test_full_pipeline.py's scene_builders dispatch."""
    builders = {
        'default':      lambda: default_scene(),
        'mixed':        lambda: mixed_shapes_scene(seed=args.seed),
        'scalability':  lambda: scalability_scene(
                            n_occluders=args.n_occluders,
                            n_targets=args.n_targets,
                            n_hidden=args.n_hidden,
                            seed=args.seed),
        'stack':        lambda: stack_scene(
                            n_objects=max(args.n_objects, args.stack_height),
                            seed=args.seed),
        'random-pairs': lambda: random_pairs_scene(
                            n_occluders=args.n_occluders,
                            extra_distractors=args.n_extra_distractors,
                            seed=args.seed),
    }
    cfg = builders[args.scene]()
    if args.goal == 'find-and-tray-stack':
        cfg.enable_tray = True
    return cfg


def _show_scene(args, baseline, freeze, show_free, win_w, win_h):
    """Phase 1-3 (mirrors test_full_pipeline.main), draw the wireframe overlay in
    the GUI, then hold the window still for `freeze` seconds for screenshotting."""
    scene_cfg = _build_scene(args)  # rebuilt per call -> deterministic from seed
    env = BoxelTestEnv(gui=True, scene_config=scene_cfg,
                       window_width=win_w, window_height=win_h)
    try:
        # --- Phase 1: effective cell size + uniform toggle (audit #66/67/77) ---
        max_extent = 0.0
        for name, info in env.objects.items():
            if name in ("plane", "table", "robot"):
                continue
            if getattr(info, "is_tray", False):
                continue
            if getattr(info, "size", None) is None:
                continue
            max_extent = max(max_extent, float(np.max(info.size)))
        auto_cell = max_extent + 0.01
        if baseline == 'uniform':
            effective_cell = max(args.uniform_cell_size, auto_cell)
            env.use_uniform_grid = True
            if abs(effective_cell - 0.05) > 1e-9:
                env.set_uniform_cell_size(effective_cell)
        else:
            effective_cell = (auto_cell if args.min_boxel_size is None
                              else args.min_boxel_size)
            env.free_space_generator.min_resolution = effective_cell

        # settle physics (mirror main: 50 steps, then refresh positions)
        for _ in range(50):
            env.step_simulation()
        env.update_object_positions()

        # --- Phase 2: boxel calculation ---
        obs = env.get_camera_observation()
        all_known = obs.boxels
        free_boxels = env.generate_free_space(all_known, visualize=False)
        merged_free = (free_boxels if env.use_uniform_grid
                       else merge_free_space_cells(free_boxels))
        env.annotate_free_space_surface(merged_free)
        all_boxels = all_known + merged_free

        # --- Phase 3: registry + WIREFRAME overlay (the look we want) ---
        registry = BoxelRegistry()
        for bd in all_boxels:
            registry.add_boxel(bd)
        viz = BoxelVisualizer()
        viz.draw_registry(registry, duration=0, label_size=1.0,
                          skip_free=not show_free)

        # make sure the GUI has drawn the overlay before we freeze
        env.refresh_debug_camera_views()
        env.step_simulation()

        bar = "=" * 64
        print(bar, flush=True)
        print(f"  [{baseline}] {len(registry.boxels)} boxels drawn  "
              f"(effective_cell={effective_cell:.3f} m, show_free={show_free})",
              flush=True)
        print(f"  >>> SCREENSHOT THE WINDOW NOW (Alt+PrtScn). "
              f"Frozen {freeze:.0f}s. <<<", flush=True)
        print(bar, flush=True)
        time.sleep(freeze)
    finally:
        env.close()


def main():
    argv = sys.argv[1:]
    do_pair = _pop_flag(argv, "--pair")
    freeze = float(_pop_opt(argv, "--freeze", "12"))
    win_w = int(_pop_opt(argv, "--window-width", "1280"))
    win_h = int(_pop_opt(argv, "--window-height", "720"))
    sys.argv = [sys.argv[0]] + argv  # parse_pipeline_args reads sys.argv

    args = parse_pipeline_args()

    # Mirror test_full_pipeline's global RNG seeding (scene placement is
    # deterministic from --seed regardless; this just matches the pipeline).
    random.seed(args.seed)
    np.random.seed(args.seed)

    if getattr(args, "no_gui", False):
        print("[capture] note: --no-gui ignored; the wireframe overlay only "
              "exists in the GUI window.", file=sys.stderr)

    if do_pair:
        print("Partition pair (same seed; capture EACH window during its freeze):",
              flush=True)
        _show_scene(args, 'semantic', freeze, True, win_w, win_h)
        _show_scene(args, 'uniform',  freeze, True, win_w, win_h)
    else:
        _show_scene(args, args.baseline, freeze, args.show_free, win_w, win_h)

    print("done.", flush=True)


if __name__ == "__main__":
    main()
