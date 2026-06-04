"""Regenerate the failure-modes figure with ONLY the semantic and uniform
variants (drops semantic+mbs0.05), for thesis audit #282 / author request.

The standard eval_plotter run emits a 3-variant failure_modes.png
(semantic, semantic+mbs0.05, uniform). This one-off reuses the same
grouping/plotting code on a variant-filtered row set so the thesis can
show the cleaner two-variant comparison without altering the 3-variant
figure that the rest of the pipeline produces.

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

rows = ep.load_rows(CSV)
rows = [r for r in rows if r.get("_variant") in ("semantic", "uniform")]
ep.plot_failure_modes(
    ep.group_failure_modes(rows),
    "Failure-mode breakdown by (goal, variant)",
    OUT,
)
print(f"wrote {OUT} from {len(rows)} semantic/uniform rows")
