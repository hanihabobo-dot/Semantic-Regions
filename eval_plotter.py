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


def _is_default_matrix(rows: List[dict]) -> bool:
    """Detect a default-style matrix shape: constant n_occluders with
    multiple (scene, goal) pairs.  This shape doesn't fit the
    line-plot-vs-n_occluders layout — the new ``plot_grouped_bars``
    path renders it as one bar group per (scene, goal) instead.
    """
    occs = {r.get("n_occluders") for r in rows
            if r.get("n_occluders") not in (None, "")}
    pairs = {(r.get("scene"), r.get("goal")) for r in rows}
    return len(occs) <= 1 and len(pairs) >= 2


def _is_random_pairs_matrix(rows: List[dict]) -> bool:
    """Detect a random-pairs sweep: every row has scene='random-pairs'.

    random_pairs_scene draws n_hidden/n_targets per seed, so n_targets
    is not a meaningful series axis here — the user-controlled axes are
    n_occluders and goal.  Plot with goal as the series instead.
    """
    scenes = {r.get("scene") for r in rows}
    return scenes == {"random-pairs"}


def group_by_scene_goal_baseline(
    rows: List[dict],
    metric: Optional[str] = None,
    success_only: bool = True,
) -> Dict[tuple, Dict[str, List[float]]]:
    """Returns ``{(scene, goal): {baseline: [samples]}}``.

    ``metric=None`` -> samples are 1.0/0.0 success flags (for success
    rate plots).  Otherwise samples are the per-cell metric value;
    ``success_only`` drops failed cells.
    """
    out: Dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        scene = r.get("scene")
        goal = r.get("goal")
        baseline = r.get("baseline") or "semantic"
        if metric is None:
            out[(scene, goal)][baseline].append(
                1.0 if r.get("success") else 0.0
            )
            continue
        if success_only and not r.get("success"):
            continue
        v = r.get(metric)
        if v in (None, ""):
            continue
        try:
            out[(scene, goal)][baseline].append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _print_grouped_bars_text(grouped, title: str) -> None:
    print(f"\n=== {title} (matplotlib not available) ===")
    for pair in sorted(grouped.keys()):
        for b in sorted(grouped[pair].keys()):
            samples = grouped[pair][b]
            if not samples:
                continue
            m = mean(samples)
            sd = pstdev(samples) if len(samples) > 1 else 0.0
            print(f"  {pair[0]}/{pair[1]}/{b}: mean={m:.3f} "
                  f"std={sd:.3f} n={len(samples)}")


def plot_grouped_bars(
    grouped: Dict[tuple, Dict[str, List[float]]],
    title: str,
    ylabel: str,
    out_path: Path,
    ylim: Optional[tuple] = None,
    log_y: bool = False,
    annotate_means: bool = True,
) -> Optional[Path]:
    """One bar group per (scene, goal), one bar per baseline."""
    if not HAVE_MPL:
        _print_grouped_bars_text(grouped, title)
        return None

    pairs = sorted(grouped.keys())
    baselines = sorted({b for v in grouped.values() for b in v.keys()})
    labels = [f"{s}\n{g}" for s, g in pairs]
    n_groups = len(pairs)
    n_bars = max(len(baselines), 1)
    bar_w = 0.8 / n_bars
    xs = list(range(n_groups))

    fig, ax = plt.subplots(figsize=(max(6, 1.8 * n_groups), 5))
    for i, b in enumerate(baselines):
        means, stds, ns = [], [], []
        for p in pairs:
            samples = grouped[p].get(b, [])
            ns.append(len(samples))
            means.append(mean(samples) if samples else 0.0)
            stds.append(pstdev(samples) if len(samples) > 1 else 0.0)
        offsets = [x + (i - (n_bars - 1) / 2) * bar_w for x in xs]
        ax.bar(offsets, means, bar_w, yerr=stds, capsize=3, label=b)
        if annotate_means:
            for off, m, s, n in zip(offsets, means, stds, ns):
                if n == 0:
                    continue
                top = m + (s if s else 0)
                ax.text(off, top, f"{m:.2g}",
                        ha="center", va="bottom", fontsize=8)

    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_xlabel("(scene, goal)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(*ylim)
    if log_y:
        ax.set_yscale("log")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(title="baseline")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def _coerce_series(val):
    """Return a hashable, plot-friendly series key.

    Integer-looking values are int-converted (so ``"3"`` and ``3`` share
    a series); everything else passes through as-is.  Without this the
    line plots would split numeric series across two keys when the CSV
    loader emits one value as str and another as int.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return int(val) if float(val).is_integer() else val
    try:
        return int(val)
    except (TypeError, ValueError):
        return val


def group_metric(rows: List[dict],
                 axis_x: str = "n_occluders",
                 series: str = "n_targets",
                 metric: str = "total_planning_time_s",
                 success_only: bool = True) -> Dict[object, Dict[int, List[float]]]:
    """Returns ``{series_value: {x_value: [metric_samples]}}``.

    ``series`` may name a numeric column (e.g. ``n_targets``) or a
    string-valued column (e.g. ``goal``).  String series stay as-is;
    numeric strings are coerced via ``_coerce_series``.
    """
    out: Dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if success_only and not r.get("success"):
            continue
        try:
            x = int(r[axis_x])
            v = float(r[metric])
        except (KeyError, TypeError, ValueError):
            continue
        s = r.get(series)
        if s in (None, ""):
            continue
        out[_coerce_series(s)][x].append(v)
    return out


def group_success_rate(rows: List[dict],
                       axis_x: str = "n_occluders",
                       series: str = "n_targets") -> Dict[object, Dict[int, List[float]]]:
    out: Dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        try:
            x = int(r[axis_x])
        except (KeyError, ValueError, TypeError):
            continue
        s = r.get(series)
        if s in (None, ""):
            continue
        out[_coerce_series(s)][x].append(1.0 if r.get("success") else 0.0)
    return out


def _print_text_table(grouped, title: str) -> None:
    print(f"\n=== {title} (matplotlib not available) ===")
    for s_val, xy in sorted(grouped.items(), key=lambda kv: str(kv[0])):
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
        for s_val, xy in sorted(grp.items(), key=lambda kv: str(kv[0])):
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

    out_dir = args.csv_path.parent

    # Dispatch on matrix shape.  Default-style matrix (constant
    # n_occluders, multiple (scene, goal) pairs) doesn't fit the
    # line-plot-vs-n_occluders layout — render grouped bars instead.
    # Scalability-style matrices fall through to the legacy line-plot
    # path below.
    if _is_default_matrix(rows):
        plot_grouped_bars(
            group_by_scene_goal_baseline(rows, metric=None),
            title="Success rate per (scene, goal)",
            ylabel="success rate (over seeds)",
            out_path=out_dir / "success_rate_per_scene_goal.png",
            ylim=(0.0, 1.05),
        )
        plot_grouped_bars(
            group_by_scene_goal_baseline(
                rows, metric="total_planning_time_s", success_only=True),
            title="Mean planning time per (scene, goal) (success-only)",
            ylabel="mean total planning time (s)",
            out_path=out_dir / "planning_time_per_scene_goal.png",
            log_y=True,
        )
        plot_grouped_bars(
            group_by_scene_goal_baseline(
                rows, metric="plan_count", success_only=True),
            title="Mean plan count per (scene, goal) (success-only)",
            ylabel="mean plan_count",
            out_path=out_dir / "plan_count_per_scene_goal.png",
        )
        return 0

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

    # random-pairs draws (n_hidden, n_targets) per seed, so n_targets is
    # not a meaningful series axis here.  Use goal as the series so the
    # line plot becomes one line per goal (with baseline as the dashed
    # overlay if both are present).
    if _is_random_pairs_matrix(rows + (baseline_rows or [])):
        series_key = "goal"
        series_label = "goal"
    else:
        series_key = "n_targets"
        series_label = "n_targets"

    plot_metric(
        group_metric(rows, series=series_key,
                     metric="total_planning_time_s",
                     success_only=True),
        title="Planning time vs scene size (success-only)",
        ylabel="mean total planning time (s)",
        out_path=out_dir / "planning_time_vs_n_occluders.png",
        baseline_grouped=(group_metric(baseline_rows, series=series_key,
                                       metric="total_planning_time_s",
                                       success_only=True)
                          if baseline_rows else None),
        series_label=series_label,
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    plot_metric(
        group_success_rate(rows, series=series_key),
        title="Success rate vs scene size",
        ylabel="success rate (over seeds)",
        out_path=out_dir / "success_rate_vs_n_occluders.png",
        ylim=(0.0, 1.05),
        baseline_grouped=(group_success_rate(baseline_rows, series=series_key)
                          if baseline_rows else None),
        series_label=series_label,
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    plot_metric(
        group_metric(rows, series=series_key,
                     metric="plan_count", success_only=True),
        title="Plan count (replans) vs scene size (success-only)",
        ylabel="mean plan_count",
        out_path=out_dir / "plan_count_vs_n_occluders.png",
        baseline_grouped=(group_metric(baseline_rows, series=series_key,
                                       metric="plan_count",
                                       success_only=True)
                          if baseline_rows else None),
        series_label=series_label,
        main_label_suffix=main_label_suffix,
        baseline_label_suffix=baseline_label_suffix,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
