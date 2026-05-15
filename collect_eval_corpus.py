#!/usr/bin/env python3
"""
collect_eval_corpus.py — Pre-vetted seed corpus for audit #77.

Iterates candidate seeds and headless-probes scene construction across
every (scene, n_occluders, stack_height, tray) configuration the
audit-77 anytime-compactness sweep will use.  Keeps ALL seeds that
pass every config (no truncation to --n-corpus — that flag is a
soft progress target for logging only).  Persists the vetted seeds
to eval_corpus.json (committed to the repo so future inter-
algorithm comparisons share the corpus).

Probes run in parallel via ProcessPoolExecutor — each probe is a
self-contained BoxelTestEnv(gui=False) construction.  PyBullet DIRECT
clients are process-local, so workers don't share state.

Supervisor methodology (audit #77, 2026-05-14): cross-algorithm
comparisons require a shared scene corpus, not per-cell randomized
seeds.  Without one, baselines run on different problem distributions
and the comparison claim collapses.

Usage:
    python collect_eval_corpus.py
    python collect_eval_corpus.py --n-corpus 100 --workers 8
    python collect_eval_corpus.py --start-seed 1000 --max-candidates 500
"""

import argparse
import concurrent.futures
import contextlib
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

from boxel_env import BoxelTestEnv, random_pairs_scene, stack_scene


# Configurations the audit-77 sweep exercises (audit #77 Step 3).
# Each entry must mirror what test_full_pipeline.main() / run_logger
# would construct for the (scene, goal, n_occluders, stack_height) tuple.
#
#   random-pairs + holding              -> extra_distractors=0, tray off
#   random-pairs + find-and-tray-stack  -> extra_distractors=1, tray on
#                                          (run_logger.py:597 auto-bump)
#   stack + stack                       -> stack_scene(n_objects=H) where
#                                          H is the sweep stack_height
#                                          (heights {2,3,4,5} dedup to
#                                          n_objects {3,4,5} since
#                                          test_full_pipeline computes
#                                          n_objects = max(default=3, H))
PROBE_CONFIGS = [
    # random-pairs x goal {holding}
    ("random-pairs", {"n_occluders": 2, "extra_distractors": 0, "enable_tray": False}),
    ("random-pairs", {"n_occluders": 3, "extra_distractors": 0, "enable_tray": False}),
    ("random-pairs", {"n_occluders": 4, "extra_distractors": 0, "enable_tray": False}),
    # random-pairs x goal {find-and-tray-stack}
    ("random-pairs", {"n_occluders": 2, "extra_distractors": 1, "enable_tray": True}),
    ("random-pairs", {"n_occluders": 3, "extra_distractors": 1, "enable_tray": True}),
    ("random-pairs", {"n_occluders": 4, "extra_distractors": 1, "enable_tray": True}),
    # stack x goal {stack} at multiple heights
    ("stack",        {"n_objects": 3, "enable_tray": False}),
    ("stack",        {"n_objects": 4, "enable_tray": False}),
    ("stack",        {"n_objects": 5, "enable_tray": False}),
]


def _build_scene(scene_name: str, seed: int, params: dict):
    # Seed BEFORE the builder, matching test_full_pipeline.main():1575-76.
    # Scene builders consume global random / np.random for placement.
    random.seed(seed)
    np.random.seed(seed)
    if scene_name == "random-pairs":
        cfg = random_pairs_scene(
            n_occluders=params["n_occluders"],
            extra_distractors=params["extra_distractors"],
            seed=seed,
        )
    elif scene_name == "stack":
        cfg = stack_scene(n_objects=params["n_objects"], seed=seed)
    else:
        raise ValueError(f"Unknown scene: {scene_name}")
    if params.get("enable_tray"):
        cfg.enable_tray = True
    return cfg


def _probe_worker(task):
    """Probe one (seed, scene, params) tuple in a worker process.

    Module-level so ProcessPoolExecutor can pickle it.  BoxelTestEnv
    prints ~8 lines per probe; swallow them to keep the parent log
    scannable.  Errors still bubble through exceptions, not stdout.
    """
    seed, scene_name, params = task
    sink = open(os.devnull, "w")
    try:
        with contextlib.redirect_stdout(sink):
            cfg = _build_scene(scene_name, seed, params)
            env = BoxelTestEnv(gui=False, scene_config=cfg)
            env.close()
        return (seed, scene_name, params, True, "")
    except RuntimeError as e:
        return (seed, scene_name, params, False, str(e))
    except Exception as e:
        return (seed, scene_name, params, False,
                f"unexpected {type(e).__name__}: {e}")
    finally:
        sink.close()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Collect a fixed pre-vetted seed corpus for audit #77.",
    )
    ap.add_argument("--n-corpus", type=int, default=100,
                    help="Soft target corpus size, used for progress "
                         "logging only — ALL seeds that pass every "
                         "probe config are kept (no hard cap).  Defaults "
                         "to 100.")
    ap.add_argument("--start-seed", type=int, default=0,
                    help="First candidate seed (default 0, sequential).")
    ap.add_argument("--max-candidates", type=int, default=500,
                    help="Probe at most this many candidates "
                         "(default 500).  The actual corpus size is "
                         "the number that pass all configs, which is "
                         "<= max-candidates.")
    ap.add_argument("--workers", type=int,
                    default=min(4, max(1, (os.cpu_count() or 4) - 1)),
                    help="Parallel probe workers (default min(4, cpus-1)).")
    ap.add_argument("--output", type=Path,
                    default=Path("eval_corpus.json"),
                    help="Output JSON (default eval_corpus.json).")
    args = ap.parse_args()

    print(f"[corpus] target n={args.n_corpus}, "
          f"start_seed={args.start_seed}, "
          f"max_candidates={args.max_candidates}, "
          f"workers={args.workers}", flush=True)
    print(f"[corpus] {len(PROBE_CONFIGS)} probe configs per candidate:",
          flush=True)
    for scene, params in PROBE_CONFIGS:
        print(f"           {scene} {params}", flush=True)

    n_configs = len(PROBE_CONFIGS)
    candidate_seeds = list(range(args.start_seed,
                                 args.start_seed + args.max_candidates))
    tasks = [(seed, scene_name, params)
             for seed in candidate_seeds
             for scene_name, params in PROBE_CONFIGS]
    total = len(tasks)
    print(f"[corpus] dispatching {total} probes "
          f"({len(candidate_seeds)} candidates x {n_configs} configs)",
          flush=True)

    accepted = []
    rejected_seeds = {}
    seed_results = {seed: [] for seed in candidate_seeds}
    n_done = 0
    last_heartbeat = time.perf_counter()
    t0 = time.perf_counter()

    with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.workers) as ex:
        for result in ex.map(_probe_worker, tasks, chunksize=1):
            seed, scene_name, params, ok, reason = result
            seed_results[seed].append((scene_name, params, ok, reason))
            n_done += 1
            if len(seed_results[seed]) == n_configs:
                fails = [(s, p, r) for s, p, k, r in seed_results[seed]
                         if not k]
                if not fails:
                    accepted.append(seed)
                    print(f"[corpus] {len(accepted):3d}/{args.n_corpus} "
                          f"seed={seed} (done {n_done}/{total})",
                          flush=True)
                else:
                    rejected_seeds[seed] = fails
                    if len(rejected_seeds) <= 20 or len(rejected_seeds) % 50 == 0:
                        s, p, r = fails[0]
                        print(f"[corpus] reject seed={seed}: {s} {p}: {r}",
                              flush=True)
            now = time.perf_counter()
            if now - last_heartbeat > 30.0:
                last_heartbeat = now
                print(f"[corpus] heartbeat: done {n_done}/{total} "
                      f"accepted={len(accepted)}/{args.n_corpus} "
                      f"({(now - t0):.0f}s elapsed)", flush=True)

    wall = time.perf_counter() - t0
    # Keep ALL seeds that passed every config — no truncation to
    # --n-corpus.  The CLI flag is now a soft progress target; the
    # corpus IS however many seeds happened to pass the probe across
    # the candidate range.
    payload = {
        "schema_version": 1,
        "audit_issue": 77,
        "n_corpus": len(accepted),
        "target_n_corpus": args.n_corpus,
        "start_seed": args.start_seed,
        "max_candidates": args.max_candidates,
        "probe_configs": [{"scene": s, **p} for s, p in PROBE_CONFIGS],
        "seeds": accepted,
        "stats": {
            "n_probed_candidates": len(candidate_seeds),
            "n_probes_run": n_done,
            "n_rejected": len(rejected_seeds),
            "wall_clock_s": round(wall, 2),
            "workers": args.workers,
        },
        # Trim reject log to first 50 — keeps the artefact small while
        # preserving an audit trail of why early candidates failed.
        "rejections_sample": [
            {"seed": s, "first_fail": {
                "scene": fails[0][0],
                "params": fails[0][1],
                "reason": fails[0][2],
            }}
            for s, fails in list(rejected_seeds.items())[:50]
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"[corpus] wrote {args.output} ({len(accepted)} seeds, "
          f"{n_done} probes, {wall:.1f}s wall, {args.workers} workers)",
          flush=True)

    if len(accepted) < args.n_corpus:
        print(f"[corpus] WARNING: only {len(accepted)}/{args.n_corpus} "
              f"seeds found in {len(candidate_seeds)} candidates.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
