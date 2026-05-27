"""Throwaway A/B driver: holding / random-pairs / semantic / occ2 over a fixed
seed set.  Runs test_full_pipeline.py once per seed as a subprocess and records
success + exit_reason.  Same script is run for the baseline arm and (after the
domain.pddl sense-constraint edit) the fix arm; the domain file is read at
runtime so no script change is needed between arms.

Usage (inside WSL wsl_env):
    python3 tools/exp_sense_fit.py <out.json>
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SEEDS = [0, 2, 4, 15, 16, 19, 20, 25, 28, 34,
         36, 39, 42, 43, 44, 45, 48, 50, 53, 59]
REPO = Path("/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels")
PER_RUN_TIMEOUT_S = 600

_SUMMARY_RE = re.compile(r"Timing summary written to (\S+timing_summary\.json)")


def _latest_summary(after_ts: float):
    best, best_m = None, -1.0
    logs = REPO / "logs"
    for rd in logs.iterdir():
        s = rd / "timing_summary.json"
        if rd.is_dir() and rd.name.startswith("run_") and s.exists():
            m = s.stat().st_mtime
            if m + 1.0 >= after_ts and m > best_m:
                best_m, best = m, s
    return best


def _run_one(seed: int) -> dict:
    argv = [
        sys.executable, "test_full_pipeline.py",
        "--no-gui", "--scene", "random-pairs",
        "--seed", str(seed), "--goal", "holding",
        "--baseline", "semantic", "--log-level", "quiet",
        "--n-occluders", "2", "--seed-retry",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(argv, cwd=str(REPO), timeout=PER_RUN_TIMEOUT_S,
                              capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return {"seed": seed, "success": False, "exit_reason": "timeout",
                "wall_s": round(time.time() - t0, 1)}
    # Prefer the explicit path the pipeline prints; fall back to newest.
    summ = None
    m = _SUMMARY_RE.search(proc.stdout or "")
    if m:
        cand = REPO / m.group(1)
        if cand.exists():
            summ = cand
    if summ is None:
        summ = _latest_summary(t0)
    if summ is None:
        return {"seed": seed, "success": False, "exit_reason": "no_summary",
                "wall_s": round(time.time() - t0, 1)}
    j = json.loads(summ.read_text())
    return {"seed": seed, "success": bool(j.get("success")),
            "exit_reason": j.get("exit_reason"),
            "plan_count": j.get("plan_count"),
            "wall_s": round(time.time() - t0, 1)}


def main():
    out = Path(sys.argv[1])
    results = []
    for seed in SEEDS:
        r = _run_one(seed)
        results.append(r)
        print(f"seed {seed:>3}: success={r['success']!s:<5} "
              f"exit={r['exit_reason']} ({r['wall_s']}s)", flush=True)
    out.write_text(json.dumps(results, indent=2))
    n = len(results)
    succ = sum(1 for r in results if r["success"])
    pf = sum(1 for r in results if r["exit_reason"] == "planner_failed")
    print(f"\n=== {out.name} ===")
    print(f"SUCCESS: {succ}/{n} = {100*succ/n:.0f}%")
    print(f"planner_failed: {pf}/{n} = {100*pf/n:.0f}%")


if __name__ == "__main__":
    main()
