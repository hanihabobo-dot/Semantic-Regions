"""Audit #108 part-c / #101: regenerate ONLY the boxel-count-vs-resolution
figure into a sweep's resolution dir.

Calls eval_plotter.plot_boxel_vs_resolution directly rather than the full
eval_plotter.py CLI, so the other PNGs in the directory are left untouched
(plots-ADD policy).

Usage:
    python3 scripts/_audit108c_plot.py <path/to/aggregated.csv>
"""
import sys
from pathlib import Path

import eval_plotter as ep

csv = Path(sys.argv[1] if len(sys.argv) > 1
           else "eval_results/sweep_anytime/resolution/aggregated.csv")
rows = ep.load_rows(csv)
out = csv.parent / "boxel_count_vs_resolution.png"
ep.plot_boxel_vs_resolution(
    ep.group_boxel_vs_resolution(rows),
    "Boxel count vs free-space leaf size",
    out,
)
print("done:", out)
