#!/usr/bin/env python3
"""
Batch evaluation runner for the Semantic Boxels pipeline (audit #9).

Walks a configuration matrix (n_occluders × n_targets × seed × goal × ...),
launches test_full_pipeline.py once per cell as a subprocess, collects each
cell's timing_summary.json, and writes an aggregated CSV/JSONL for the
plotter (eval_plotter.py).

Subprocess-per-cell: RunLogger replaces sys.stdout, SmartConsoleFilter is
process-global, and PyBullet GUI/DIRECT clients don't always tear down
cleanly.  A fresh process per cell keeps state isolation cheap and lets
one bad cell not poison the rest of the sweep.

Usage:
    python eval_runner.py --matrix scalability \\
        --output eval_results/sweep_2026-05-08
    python eval_runner.py --matrix smoke --output eval_results/smoke
    python eval_runner.py --matrix scalability --skip-existing --timeout 300
    python eval_runner.py --matrix scalability --dry-run

Exit code 0 if every cell produced a timing_summary.json (success or fail);
non-zero if any cell crashed/timed out (or above --max-failures).
"""

import argparse
import csv
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional


# ---------------------------------------------------------------------------
# Matrix presets
# ---------------------------------------------------------------------------

# Scalability evaluation matrix (audit #9, absorbing #12).
# n_occluders ∈ 1..6 × n_targets ∈ 1..3 × 5 seeds × baseline {sem,uni}
# = 180 cells.  --goal holding only — find-and-tray-stack adds a third
# data series later.  n_hidden = min(n_targets, n_occluders) so every
# cell has the deepest search this scene size can support without
# overconstraining placement.  baseline axis (audit #10) drives the
# uniform-vs-semantic free-space comparison plotted by eval_plotter via
# the --baseline-csv overlay hook.
SCALABILITY_MATRIX = {
    "n_occluders": [1, 2, 3, 4, 5, 6],
    "n_targets":   [1, 2, 3],
    "seed":        list(range(5)),
    "goal":        ["holding"],
    "unit_costs":  [False],
    "scene":       ["scalability"],
    "baseline":    ["semantic", "uniform"],
    "_n_hidden_strategy": "all_or_max",
}

# 1-cell smoke test for runner sanity checks.
SMOKE_MATRIX = {
    "n_occluders": [1],
    "n_targets":   [1],
    "seed":        [0],
    "goal":        ["holding"],
    "unit_costs":  [False],
    "scene":       ["scalability"],
    "baseline":    ["semantic"],
    "_n_hidden_strategy": "all_or_max",
}

# "default" matrix — semantic-vs-uniform comparison across goal types
# on canonical default scenes (vs. SCALABILITY_MATRIX, which sweeps
# n_occluders / n_targets on the random scalability scene).  3 (scene,
# goal) pairs × 10 seeds × 2 baselines = 60 cells.
#
# Per-seed variation:
#   - 'default' scene has fixed object positions, so --seed only varies
#     planner-level RNG (Phase 4 random.choice() target pick + PDDLStream
#     stream sampling).  Same scene geometry across all 10 seeds for
#     holding and find-and-tray-stack.
#   - 'stack' scene has random per-seed cube placement
#     (constrain_to_reach=True), so layout varies across seeds.
#
# (default, stack) is intentionally skipped because run_logger
# auto-promotes it to (stack, stack).  (stack, holding) and
# (stack, find-and-tray-stack) are skipped because no occluders means
# 0 hidden — degenerate for both goals.
DEFAULT_MATRIX = [
    {
        "scene":              [scene],
        "goal":               [goal],
        "seed":               list(range(10)),
        "baseline":           ["semantic", "uniform"],
        "unit_costs":         [False],
        "n_occluders":        [3],
        "n_targets":          [4],
        "_n_hidden_strategy": "none",
    }
    for scene, goal in [
        ("default", "holding"),
        ("stack",   "stack"),
        ("default", "find-and-tray-stack"),
    ]
]

MATRIX_PRESETS = {
    "scalability": SCALABILITY_MATRIX,
    "smoke":       SMOKE_MATRIX,
    "default":     DEFAULT_MATRIX,
}


# ---------------------------------------------------------------------------
# Cell expansion
# ---------------------------------------------------------------------------

def iterate_matrix(matrix) -> Iterator[Dict]:
    """Expand the matrix into cell dicts.

    A dict value is a single axis-bundle and gets cartesian-product
    expansion.  A list value means union — iterate each sub-matrix in
    turn.  The list form is useful when two axes need to be paired
    (e.g. scene + goal in the "default" matrix), not crossed.

    Keys starting with ``_`` are policies, not axes — they don't multiply
    the product but instead derive fields from other axes.  Currently
    supported: ``_n_hidden_strategy`` ∈ {"all_or_max", "none"}.
    """
    if isinstance(matrix, list):
        for sub in matrix:
            yield from iterate_matrix(sub)
        return
    axis_keys = [k for k in matrix.keys() if not k.startswith("_")]
    axis_vals = [matrix[k] for k in axis_keys]
    n_hidden_strategy = matrix.get("_n_hidden_strategy", "none")
    for combo in itertools.product(*axis_vals):
        cell = dict(zip(axis_keys, combo))
        if n_hidden_strategy == "all_or_max":
            cell["n_hidden"] = min(int(cell["n_targets"]),
                                   int(cell["n_occluders"]))
        else:
            cell["n_hidden"] = 0
        yield cell


def cell_tag(cell: Dict) -> str:
    """Deterministic short label used as the cell directory name."""
    return (f"occ{cell['n_occluders']}_tgt{cell['n_targets']}"
            f"_hid{cell['n_hidden']}_seed{cell['seed']}"
            f"_{cell['goal']}_uc{int(cell['unit_costs'])}"
            f"_{cell.get('baseline', 'semantic')}")


def cell_to_argv(cell: Dict, extra_args: List[str]) -> List[str]:
    """Build ``python test_full_pipeline.py ...`` argv for one cell."""
    argv = [
        sys.executable, "test_full_pipeline.py",
        "--no-gui",
        "--scene", str(cell["scene"]),
        "--seed", str(cell["seed"]),
        "--goal", str(cell["goal"]),
        "--baseline", str(cell.get("baseline", "semantic")),
        "--log-level", "quiet",
    ]
    # audit #67 follow-up — only emit count knobs when the scene
    # actually consumes them.  run_logger auto-promotes
    # --scene default --goal holding to --scene scalability whenever
    # --n-occluders / --n-targets / --n-hidden is on the CLI, so passing
    # them unconditionally turned every (default, holding) cell into a
    # scalability run.
    if cell["scene"] == "scalability":
        argv.extend([
            "--n-occluders", str(cell["n_occluders"]),
            "--n-targets",   str(cell["n_targets"]),
            "--n-hidden",    str(cell["n_hidden"]),
        ])
    if cell["unit_costs"]:
        argv.append("--unit-costs")
    return argv + list(extra_args)


# ---------------------------------------------------------------------------
# Per-cell execution
# ---------------------------------------------------------------------------

def _find_latest_timing_summary(start_ts: float) -> Optional[Path]:
    """Locate the timing_summary.json written by the just-finished cell.

    test_full_pipeline.py creates ``logs/run_<ts>/timing_summary.json``
    via report_run_outcome.  We pick the most recent one whose mtime is
    >= ``start_ts`` (epoch seconds, captured before the subprocess ran).
    """
    logs_dir = Path("logs")
    if not logs_dir.is_dir():
        return None
    candidates = []
    for run_dir in logs_dir.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
            continue
        summary = run_dir / "timing_summary.json"
        if not summary.exists():
            continue
        # 1-second slack absorbs filesystem-mtime granularity differences.
        if summary.stat().st_mtime + 1.0 >= start_ts:
            candidates.append((summary.stat().st_mtime, summary))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def run_cell(
    cell: Dict,
    sweep_dir: Path,
    timeout_s: float,
    extra_args: List[str],
    skip_existing: bool,
) -> Dict:
    """Run one cell in a subprocess and collect its timing_summary.json.

    Returns a dict suitable for aggregation: cell config + metrics, or a
    stub row with ``success=False`` and a diagnostic ``exit_reason`` on
    timeout / crash / missing summary.
    """
    tag = cell_tag(cell)
    cell_dir = sweep_dir / "cells" / tag
    cell_dir.mkdir(parents=True, exist_ok=True)

    summary_path = cell_dir / "timing_summary.json"
    stdout_path = cell_dir / "stdout.log"

    if skip_existing and summary_path.exists():
        try:
            return {**cell, **json.loads(summary_path.read_text())}
        except Exception:
            pass

    argv = cell_to_argv(cell, extra_args)
    print(f"[runner] {tag}: launching")
    t0 = time.perf_counter()
    start_ts = time.time()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=os.getcwd(),
        )
    except subprocess.TimeoutExpired:
        wall = time.perf_counter() - t0
        stub = {
            **cell,
            "success": False,
            "exit_reason": "timeout",
            "wall_clock_s": round(wall, 3),
        }
        summary_path.write_text(json.dumps(stub, indent=2))
        print(f"[runner] {tag}: TIMEOUT after {timeout_s}s")
        return stub

    wall = time.perf_counter() - t0
    stdout_path.write_text(
        (proc.stdout or "") + "\n--- STDERR ---\n" + (proc.stderr or ""),
        encoding="utf-8",
    )

    # test_full_pipeline.py exits 0 on success, 1 on run-level failure
    # (exit_reason set by report_run_outcome).  Anything else = crash.
    if proc.returncode not in (0, 1):
        stub = {
            **cell,
            "success": False,
            "exit_reason": f"crash_exit{proc.returncode}",
            "wall_clock_s": round(wall, 3),
        }
        summary_path.write_text(json.dumps(stub, indent=2))
        print(f"[runner] {tag}: CRASH exit={proc.returncode}")
        return stub

    ts_path = _find_latest_timing_summary(start_ts)
    if ts_path is None:
        stub = {
            **cell,
            "success": False,
            "exit_reason": "no_summary",
            "wall_clock_s": round(wall, 3),
        }
        summary_path.write_text(json.dumps(stub, indent=2))
        print(f"[runner] {tag}: NO timing_summary.json found")
        return stub

    shutil.copy2(ts_path, summary_path)
    (cell_dir / "run_dir.txt").write_text(str(ts_path.parent.absolute()))

    summary = json.loads(summary_path.read_text())
    summary["wall_clock_s"] = round(wall, 3)
    summary_path.write_text(json.dumps(summary, indent=2))

    out_row = {**cell, **summary}
    ok = "OK" if summary.get("success") else "FAIL"
    print(f"[runner] {tag}: {ok} "
          f"plan_count={summary.get('plan_count')} "
          f"plan_time_s={summary.get('total_planning_time_s')}")
    return out_row


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Stable column ordering so the CSV is diffable across sweeps.
PRIMARY_COLUMNS = [
    "scene", "n_occluders", "n_targets", "n_hidden", "seed",
    "goal", "unit_costs",
    "baseline", "uniform_cell_size",
    "success", "exit_reason",
    "plan_count", "total_planning_time_s", "wall_clock_s",
]

# Fields that are list-valued (per-call timings, per-action failures);
# don't fit a flat CSV so we drop them from the aggregated CSV but keep
# them in aggregated.jsonl for downstream tooling.
LIST_VALUED = {
    "per_call_planning_time_s",
    "physical_failures_per_action",
    "physical_failures_at_goal",
}


def aggregate(sweep_dir: Path) -> Path:
    """Walk sweep_dir/cells/*/timing_summary.json into aggregated.csv +
    aggregated.jsonl."""
    cells_root = sweep_dir / "cells"
    rows: List[dict] = []
    if cells_root.is_dir():
        for tag_dir in sorted(cells_root.iterdir()):
            if not tag_dir.is_dir():
                continue
            ts = tag_dir / "timing_summary.json"
            if not ts.exists():
                continue
            try:
                data = json.loads(ts.read_text())
            except Exception as e:
                print(f"[aggregate] skipping {tag_dir.name}: {e}")
                continue
            rc = data.get("run_config")
            if isinstance(rc, dict):
                for k, v in rc.items():
                    data.setdefault(k, v)
            rows.append(data)

    extra_keys = sorted({k for r in rows for k in r.keys()}
                        - set(PRIMARY_COLUMNS) - LIST_VALUED - {"run_config"})
    columns = PRIMARY_COLUMNS + extra_keys

    csv_path = sweep_dir / "aggregated.csv"
    jsonl_path = sweep_dir / "aggregated.jsonl"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"[aggregate] wrote {csv_path} ({len(rows)} rows)")
    print(f"[aggregate] wrote {jsonl_path}")
    return csv_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_seed_spec(spec: str) -> List[int]:
    """'0:5' -> [0,1,2,3,4]; '0,2,4' -> [0,2,4]; '7' -> [7]."""
    if ":" in spec:
        a, b = spec.split(":", 1)
        return list(range(int(a), int(b)))
    return [int(s) for s in spec.split(",") if s.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--matrix", choices=list(MATRIX_PRESETS.keys()),
                        default="scalability",
                        help="Built-in matrix preset.")
    parser.add_argument("--output", type=Path, default=None,
                        help="Sweep output directory (default: "
                             "eval_results/sweep_<timestamp>_<matrix>).")
    parser.add_argument("--seeds", type=str, default=None,
                        help="Override seed list, e.g. '0:5' or '0,2,4'.")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Per-cell wall-clock timeout in seconds "
                             "(default: 300).")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Reuse existing timing_summary.json in cell dirs "
                             "(resume after crash without re-running).")
    parser.add_argument("--max-failures", type=int, default=-1,
                        help="Abort the sweep after this many crash/timeout "
                             "cells (-1 = never abort).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the cell list and exit.")
    parser.add_argument("--extra-arg", action="append", default=[],
                        metavar="ARG",
                        help="Pass-through argv for test_full_pipeline.py "
                             "(repeatable).")
    args = parser.parse_args(argv)

    matrix_preset = MATRIX_PRESETS[args.matrix]
    seeds_override = (_parse_seed_spec(args.seeds)
                      if args.seeds is not None else None)
    if isinstance(matrix_preset, list):
        if seeds_override is not None:
            matrix = [{**sub, "seed": seeds_override}
                      for sub in matrix_preset]
        else:
            matrix = matrix_preset
    else:
        matrix = dict(matrix_preset)
        if seeds_override is not None:
            matrix["seed"] = seeds_override

    cells = list(iterate_matrix(matrix))
    print(f"[runner] matrix={args.matrix}, {len(cells)} cells")

    if args.dry_run:
        for c in cells:
            print(f"  {cell_tag(c)}")
        return 0

    sweep_dir = args.output or (
        Path("eval_results")
        / f"sweep_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{args.matrix}"
    )
    sweep_dir.mkdir(parents=True, exist_ok=True)
    (sweep_dir / "matrix.json").write_text(
        json.dumps({"preset": args.matrix, "cells": cells}, indent=2)
    )

    n_failures = 0
    for i, cell in enumerate(cells, 1):
        print(f"\n[runner] cell {i}/{len(cells)}")
        row = run_cell(cell, sweep_dir, args.timeout,
                       args.extra_arg, args.skip_existing)
        if not row.get("success"):
            n_failures += 1
            if 0 <= args.max_failures < n_failures:
                print(f"[runner] aborting: {n_failures} failures > "
                      f"--max-failures {args.max_failures}")
                break

    aggregate(sweep_dir)
    print(f"\n[runner] sweep complete: {sweep_dir} "
          f"(failures: {n_failures}/{len(cells)})")
    return 0 if n_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
