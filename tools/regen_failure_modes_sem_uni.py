"""Regenerate the failure-modes figure with ONLY the semantic and uniform
variants (drops semantic+mbs0.05) AND reader-friendly category labels, for
thesis audit #282 / author request.

The standard eval_plotter run emits a 3-variant failure_modes.png whose bands
are the raw exit-reason identifiers (success / planner_failed / timeout). This
one-off reuses the same grouping/plotting code on a variant-filtered row set,
then relabels the bands to plain language (success / plan failed / timed out)
so the thesis figure needs no internal jargon. The 3-variant figure that the
rest of the pipeline produces is left untouched.

Run via WSL with the project venv + PYTHONPATH (see audit #282):
  wsl bash -lc 'cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels && \
    source wsl_env/bin/activate && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python3 tools/regen_failure_modes_sem_uni.py'
"""
from pathlib import Path

import eval_plotter as ep

CSV = Path("eval_results/sweep_full_2026-05-28/aggregated.csv")
OUT = CSV.parent / "failure_modes_sem_uni.png"

# Plain-language band labels (carry the same colours as the raw identifiers).
RENAME = {"planner_failed": "plan failed", "timeout": "timed out"}
for raw, friendly in RENAME.items():
    ep.EXIT_REASON_COLOUR[friendly] = ep.EXIT_REASON_COLOUR[raw]

rows = ep.load_rows(CSV)
rows = [r for r in rows if r.get("_variant") in ("semantic", "uniform")]
grouped = ep.group_failure_modes(rows)
relabeled = {
    key: {RENAME.get(reason, reason): n for reason, n in counts.items()}
    for key, counts in grouped.items()
}

ep.plot_failure_modes(
    relabeled,
    "Failure-mode breakdown by (goal, variant)",
    OUT,
)
print(f"wrote {OUT} from {len(rows)} semantic/uniform rows")
