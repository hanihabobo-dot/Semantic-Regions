"""Regenerate the failure-modes figure for the thesis (semantic + uniform only).

Emits TWO figures from the same sem/uni row set:
  * failure_modes_sem_uni.png           -- 2-category simplified (plan failed /
                                           timed out); folds the give-up reasons.
                                           Kept regenerable (audit #282).
  * failure_modes_sem_uni_detailed.png  -- author request 2026-06-09: the give-up
                                           reasons broken out (no plan found /
                                           searched all regions / manipulation
                                           failed / execution mismatch / timed out)
                                           so the graph matches the failure modes
                                           the §4.6 loop + metrics text name.

The 3-variant failure_modes.png the rest of the pipeline produces is untouched.

Run via WSL with the project venv + PYTHONPATH (see audit #282):
  wsl bash -lc 'cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels && \
    source wsl_env/bin/activate && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python3 tools/regen_failure_modes_sem_uni.py'
"""
from pathlib import Path

import eval_plotter as ep

CSV = Path("eval_results/sweep_full_2026-05-28/aggregated.csv")
OUT_SIMPLE = CSV.parent / "failure_modes_sem_uni.png"
OUT_DETAIL = CSV.parent / "failure_modes_sem_uni_detailed.png"

rows = ep.load_rows(CSV)
rows = [r for r in rows if r.get("_variant") in ("semantic", "uniform")]


def _relabel(grouped, rename):
    """Copy each raw category's colour onto its friendly name, then relabel."""
    for raw, friendly in rename.items():
        if raw in ep.EXIT_REASON_COLOUR:
            ep.EXIT_REASON_COLOUR[friendly] = ep.EXIT_REASON_COLOUR[raw]
    return {
        key: {rename.get(reason, reason): n for reason, n in counts.items()}
        for key, counts in grouped.items()
    }


# --- Simplified 2-category figure (unchanged; folds the give-ups) ---
SIMPLE = {"planner_failed": "plan failed", "timeout": "timed out"}
ep.plot_failure_modes(
    _relabel(ep.group_failure_modes(rows, fold=True), SIMPLE),
    "Failure-mode breakdown by (goal, variant)",
    OUT_SIMPLE,
)

# --- Detailed figure (author request 2026-06-09; give-ups broken out) ---
DETAIL = {
    "planner_failed":   "no plan found",
    "timeout":          "timed out",
    "all_searched":     "blocked from view",
    "drop_failed":      "manipulation failed",
    "physics_mismatch": "execution mismatch",
}
ep.plot_failure_modes(
    _relabel(ep.group_failure_modes(rows, fold=False), DETAIL),
    "Failure-mode breakdown by (goal, variant)",
    OUT_DETAIL,
)
print(f"wrote {OUT_SIMPLE} and {OUT_DETAIL} from {len(rows)} semantic/uniform rows")
