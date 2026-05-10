#!/usr/bin/env python3
"""
Plot Results-chapter figures from an eval_runner sweep (audit #9).

Reads aggregated.csv produced by eval_runner.py and writes:
  - planning_time_vs_n_occluders.png
  - success_rate_vs_n_occluders.png
  - plan_count_vs_n_occluders.png

If matplotlib is not installed, prints summary tables to stdout so the
sweep still produces a usable artifact on a fresh checkout.

Usage:
    python eval_plotter.py eval_results/sweep_<ts>_scalability/aggregated.csv
    python eval_plotter.py <csv> --baseline-csv <other csv>     # issue #10 stub
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


def load_rows(csv_path: Path) -> List[dict]:
    rows: List[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            for k in ("n_occluders", "n_targets", "n_hidden", "seed",
                      "plan_count"):
                v = r.get(k)
                if v not in (None, ""):
                    try:
                        r[k] = int(v)
                    except ValueError:
                        pass
            for k in ("total_planning_time_s", "wall_clock_s"):
                v = r.get(k)
                if v not in (None, ""):
                    try:
                        r[k] = float(v)
                    except ValueError:
                        pass
            r["success"] = (str(r.get("success")).strip().lower() == "true")
            rows.append(r)
    return rows


def _split_by_baseline(rows: List[dict]) -> tuple:
    """Split rows by ``baseline`` column when BOTH 'semantic' and 'uniform'
    are present.

    Audit #50/#66 follow-up: ``eval_runner.SCALABILITY_MATRIX`` runs both
    baselines in one sweep, so the produced ``aggregated.csv`` mixes them.
    Without this split ``group_metric`` would compute means over a mixed
    series and the comparison plot would be meaningless.

    Returns:
        (semantic_rows, uniform_rows) when both baselines are present,
        (rows, None) when only one or zero baseline values are present
        (preserves the pre-#50/#66 single-series behaviour).
    """
    semantic = [r for r in rows if r.get("baseline") == "semantic"]
    uniform = [r for r in rows if r.get("baseline") == "uniform"]
    if semantic and uniform:
        return semantic, uniform
    return rows, None


def group_metric(rows: List[dict],
                 axis_x: str = "n_occluders",
                 series: str = "n_targets",
                 metric: str = "total_planning_time_s",
                 success_only: bool = True) -> Dict[int, Dict[int, List[float]]]:
    """Returns ``{series_value: {x_value: [metric_samples]}}``."""
    out: Dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if success_only and not r.get("success"):
            continue
        try:
            x = int(r[axis_x])
            s = int(r[series])
            v = float(r[metric])
        except (KeyError, TypeError, ValueError):
            continue
        out[s][x].append(v)
    return out


def group_success_rate(rows: List[dict],
                       axis_x: str = "n_occluders",
                       series: str = "n_targets") -> Dict[int, Dict[int, List[float]]]:
    out: Dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        try:
            x = int(r[axis_x])
            s = int(r[series])
        except (KeyError, ValueError, TypeError):
            continue
        out[s][x].append(1.0 if r.get("success") else 0.0)
    return out


def _print_text_table(grouped, title: str) -> None:
    print(f"\n=== {title} (matplotlib not available) ===")
    for s_val, xy in sorted(grouped.items()):
        for x in sorted(xy.keys()):
            samples = xy[x]
            if not samples:
                continue
            m = mean(samples)
            sd = pstdev(samples) if len(samples) > 1 else 0.0
            print(f"  series={s_val} x={x}: mean={m:.3f} "
                  f"std={sd:.3f} n={len(samples)}")


def plot_metric(grouped: Dict[int, Dict[int, List[float]]],
                title: str,
                ylabel: str,
                out_path: Path,
                ylim: Optional[tuple] = None,
                series_label: str = "n_targets",
                xlabel: str = "n_occluders",
                baseline_grouped: Optional[Dict] = None,
                main_label_suffix: str = "",
                baseline_label_suffix: str = " (baseline)") -> Optional[Path]:
    if not HAVE_MPL:
        _print_text_table(grouped, title + main_label_suffix)
        if baseline_grouped is not None:
            _print_text_table(baseline_grouped,
                              f"{title}{baseline_label_suffix}")
        return None

    fig, ax = plt.subplots(figsize=(7, 5))

    def _plot(grp, suffix, linestyle):
        for s_val, xy in sorted(grp.items()):
            xs = sorted(xy.keys())
            means = [mean(xy[x]) for x in xs]
            stds = [pstdev(xy[x]) if len(xy[x]) > 1 else 0.0 for x in xs]
            ax.errorbar(xs, means, yerr=stds, marker="o", capsize=3,
                        linestyle=linestyle,
                        label=f"{series_label}={s_val}{suffix}")

    _plot(grouped, main_label_suffix, "-")
    if baseline_grouped is not None:
        _plot(baseline_grouped, baseline_label_suffix, "--")

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("csv_path", type=Path,
                   help="aggregated.csv from eval_runner.py")
    p.add_argument("--baseline-csv", type=Path, default=None,
                   help="Overlay a baseline aggregated.csv (issue #10 hook).")
    args = p.parse_args(argv)

    if not args.csv_path.exists():
        print(f"[plotter] not found: {args.csv_path}", file=sys.stderr)
        return 2

    rows = load_rows(args.csv_path)
    if not rows:
        print(f"[plotter] no rows in {args.csv_path}", file=sys.stderr)
        return 1

    # Audit #50/#66 follow-up — when --baseline-csv is not given but the
    # input CSV contains BOTH 'semantic' and 'uniform' rows (the
    # SCALABILITY_MATRIX default), auto-split by the baseline column so
    # the plot draws semantic vs uniform without manual CSV slicing.
    # Explicit --baseline-csv overrides this and behaves as before.
    main_label_suffix = ""
    baseline_label_suffix = " (baseline)"
    if args.baseline_csv:
        baseline_rows = load_rows(args.baseline_csv)
    else:
        rows, baseline_rows = _split_by_baseline(rows)
        if baseline_rows is not None:
            main_label_suffix = " (semantic)"
            baseline_label_suffix = " (uniform)"
            print(f"[plotter] auto-split by baseline column: "
                  f"semantic={len(rows)} rows, "
                  f"uniform={len(baseline_rows)} rows")

    out_dir = args.csv_path.parent

    plot_metric(
        group_metric(rows, metric="total_planning_time_s",
                     success_only=True),
        title="Planning time vs scene size (success-only)",
        ylabel="mean total planning time (s)",
        out_path=out_dir / "planning_time_vs_n_occluders.png",
        baseline_grouped=(group_metric(baseline_rows,
                                       metric="total_planning_time_s",
                                       success_only=True)
                          if baseline_rows else None),
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    plot_metric(
        group_success_rate(rows),
        title="Success rate vs scene size",
        ylabel="success rate (over seeds)",
        out_path=out_dir / "success_rate_vs_n_occluders.png",
        ylim=(0.0, 1.05),
        baseline_grouped=(group_success_rate(baseline_rows)
                          if baseline_rows else None),
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    plot_metric(
        group_metric(rows, metric="plan_count", success_only=True),
        title="Plan count (replans) vs scene size (success-only)",
        ylabel="mean plan_count",
        out_path=out_dir / "plan_count_vs_n_occluders.png",
        baseline_grouped=(group_metric(baseline_rows, metric="plan_count",
                                       success_only=True)
                          if baseline_rows else None),
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
