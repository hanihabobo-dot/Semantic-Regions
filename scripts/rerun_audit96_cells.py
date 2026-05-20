#!/usr/bin/env python3
"""Re-run the 5 cells that crashed with ModuleNotFoundError: numpy
(audit #96).  Each cell directory was deleted before this script runs;
run_cell here re-launches test_full_pipeline.py under the wsl_env
interpreter and re-populates the cell dir with a real
timing_summary.json.

Invoke under wsl_env (these need numpy/pybullet that Windows Python
lacks):
    wsl bash /mnt/c/.../scripts/_run_in_wsl.sh scripts/rerun_audit96_cells.py

This script does not touch other cells, so it does not race with a
concurrent eval_runner sweep that is processing the stack/uniform
block.
"""
import sys
from pathlib import Path

# Make the repo root importable when invoked as scripts/rerun_*.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval_runner import run_cell  # noqa: E402

CELLS = [
    {
        "scene": "random-pairs",
        "n_occluders": 2,
        "seed": 16,
        "goal": "find-and-tray-stack",
        "baseline": "semantic",
        "min_boxel_size": 0.05,
        "unit_costs": False,
        "n_hidden": 0,
    },
    {
        "scene": "random-pairs",
        "n_occluders": 2,
        "seed": 88,
        "goal": "find-and-tray-stack",
        "baseline": "semantic",
        "min_boxel_size": 0.05,
        "unit_costs": False,
        "n_hidden": 0,
    },
    {
        "scene": "random-pairs",
        "n_occluders": 2,
        "seed": 99,
        "goal": "find-and-tray-stack",
        "baseline": "semantic",
        "min_boxel_size": 0.05,
        "unit_costs": False,
        "n_hidden": 0,
    },
    {
        "scene": "random-pairs",
        "n_occluders": 2,
        "seed": 69,
        "goal": "find-and-tray-stack",
        "baseline": "semantic",
        "min_boxel_size": 0.05,
        "unit_costs": False,
        "n_hidden": 0,
    },
    {
        "scene": "random-pairs",
        "n_occluders": 2,
        "seed": 69,
        "goal": "find-and-tray-stack",
        "baseline": "semantic",
        "min_boxel_size": None,
        "unit_costs": False,
        "n_hidden": 0,
    },
]

SWEEP_DIR = REPO_ROOT / "eval_results" / "sweep_anytime"
TIMEOUT_S = 1800.0


def main() -> int:
    print(f"[rerun-audit96] sweep_dir={SWEEP_DIR}")
    print(f"[rerun-audit96] interpreter={sys.executable}")
    n_pass = 0
    n_fail = 0
    for i, cell in enumerate(CELLS, 1):
        print(f"\n[rerun-audit96] cell {i}/{len(CELLS)}: {cell}")
        row = run_cell(
            cell,
            SWEEP_DIR,
            timeout_s=TIMEOUT_S,
            extra_args=[],
            skip_existing=False,
        )
        ok = bool(row.get("success"))
        n_pass += int(ok)
        n_fail += int(not ok)
        print(f"[rerun-audit96]   -> success={ok} "
              f"exit_reason={row.get('exit_reason')!r} "
              f"plan_time_s={row.get('total_planning_time_s')} "
              f"wall_clock_s={row.get('wall_clock_s')}")
    print(f"\n[rerun-audit96] done: {n_pass} pass / {n_fail} fail "
          f"out of {len(CELLS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
