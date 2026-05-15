#!/usr/bin/env python3
"""
collect_eval_corpus.py — Pre-vetted seed corpus for audit #77.

Iterates candidate seeds and headless-probes scene construction across
every (scene, n_occluders, tray) configuration the audit-77 anytime-
compactness sweep will use.  Keeps only seeds that pass ALL configs.
Persists the first N vetted seeds to eval_corpus_100.json (committed
to the repo so future inter-algorithm comparisons share the corpus).

Supervisor methodology (audit #77, 2026-05-14): cross-algorithm
comparisons require a shared scene corpus, not per-cell randomized
seeds.  Without one, baselines run on different problem distributions
and the comparison claim collapses.

Usage:
    python collect_eval_corpus.py
    python collect_eval_corpus.py --n-corpus 100 --output eval_corpus_100.json
    python collect_eval_corpus.py --start-seed 1000 --max-candidates 5000
"""

import argparse
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
# would construct for the (scene, goal, n_occluders) tuple.
#
#   random-pairs + holding              -> extra_distractors=0, tray off
#   random-pairs + find-and-tray-stack  -> extra_distractors=1, tray on
#                                          (run_logger.py:597 auto-bump)
#   stack + stack                       -> stack_scene(n_objects=3)
PROBE_CONFIGS = [
    ("random-pairs", {"n_occluders": 2, "extra_distractors": 0, "enable_tray": False}),
    ("random-pairs", {"n_occluders": 3, "extra_distractors": 0, "enable_tray": False}),
    ("random-pairs", {"n_occluders": 4, "extra_distractors": 0, "enable_tray": False}),
    ("random-pairs", {"n_occluders": 2, "extra_distractors": 1, "enable_tray": True}),
    ("random-pairs", {"n_occluders": 3, "extra_distractors": 1, "enable_tray": True}),
    ("random-pairs", {"n_occluders": 4, "extra_distractors": 1, "enable_tray": True}),
    ("stack",        {"n_objects": 3, "enable_tray": False}),
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


def probe_seed(seed: int, silence: bool = True) -> tuple:
    """Probe one seed against every PROBE_CONFIG.  Return (passed, reason)."""
    # BoxelTestEnv.__init__ prints ~8 lines per probe; suppress on the
    # success path so the corpus-collection log stays scannable.
    sink = open(os.devnull, "w") if silence else sys.stdout
    try:
        for scene_name, params in PROBE_CONFIGS:
            try:
                with contextlib.redirect_stdout(sink):
                    cfg = _build_scene(scene_name, seed, params)
                    env = BoxelTestEnv(gui=False, scene_config=cfg)
                    env.close()
            except RuntimeError as e:
                return False, f"{scene_name} {params}: {e}"
            except Exception as e:
                return False, (f"{scene_name} {params}: "
                               f"unexpected {type(e).__name__}: {e}")
    finally:
        if silence:
            sink.close()
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Collect a fixed pre-vetted seed corpus for audit #77.",
    )
    ap.add_argument("--n-corpus", type=int, default=100,
                    help="Target corpus size (default 100).")
    ap.add_argument("--start-seed", type=int, default=0,
                    help="First candidate seed (default 0, sequential).")
    ap.add_argument("--max-candidates", type=int, default=5000,
                    help="Give up after probing this many candidates "
                         "(default 5000).")
    ap.add_argument("--output", type=Path,
                    default=Path("eval_corpus_100.json"),
                    help="Output JSON (default eval_corpus_100.json).")
    ap.add_argument("--verbose-probes", action="store_true",
                    help="Don't silence BoxelTestEnv stdout (debug).")
    args = ap.parse_args()

    print(f"[corpus] target n={args.n_corpus}, "
          f"start_seed={args.start_seed}, "
          f"max_candidates={args.max_candidates}", flush=True)
    print(f"[corpus] {len(PROBE_CONFIGS)} probe configs per candidate:",
          flush=True)
    for scene, params in PROBE_CONFIGS:
        print(f"           {scene} {params}", flush=True)

    accepted = []
    rejections = []
    t0 = time.perf_counter()

    candidate = args.start_seed
    n_probed = 0
    while len(accepted) < args.n_corpus and n_probed < args.max_candidates:
        ok, reason = probe_seed(candidate, silence=not args.verbose_probes)
        n_probed += 1
        if ok:
            accepted.append(candidate)
            print(f"[corpus] {len(accepted):3d}/{args.n_corpus} "
                  f"seed={candidate} "
                  f"(probed {n_probed}, rejected {len(rejections)})",
                  flush=True)
        else:
            rejections.append({"seed": candidate, "reason": reason})
            if len(rejections) <= 20 or len(rejections) % 50 == 0:
                print(f"[corpus] reject seed={candidate}: {reason}",
                      flush=True)
        candidate += 1

    wall = time.perf_counter() - t0
    payload = {
        "schema_version": 1,
        "audit_issue": 77,
        "n_corpus": len(accepted),
        "target_n_corpus": args.n_corpus,
        "start_seed": args.start_seed,
        "probe_configs": [{"scene": s, **p} for s, p in PROBE_CONFIGS],
        "seeds": accepted,
        "stats": {
            "n_probed": n_probed,
            "n_rejected": len(rejections),
            "wall_clock_s": round(wall, 2),
        },
        # Trim reject log to first 50 — keeps the artefact small while
        # preserving an audit trail of why early candidates failed.
        "rejections_sample": rejections[:50],
    }
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"[corpus] wrote {args.output} ({len(accepted)} seeds, "
          f"{n_probed} probed, {wall:.1f}s wall)", flush=True)

    if len(accepted) < args.n_corpus:
        print(f"[corpus] WARNING: only {len(accepted)}/{args.n_corpus} "
              f"seeds found within {args.max_candidates} candidates.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
