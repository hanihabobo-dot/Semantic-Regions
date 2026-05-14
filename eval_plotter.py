#!/usr/bin/env python3
"""
Plot Results-chapter figures from an eval_runner sweep (audit #9).

Reads aggregated.csv produced by eval_runner.py and writes:
  - planning_time_vs_n_occluders[__<goal>].png
  - success_rate_vs_n_occluders[__<goal>].png
  - plan_count_vs_n_occluders[__<goal>].png

For random-pairs sweeps, the per-goal suffix is added so each goal
(e.g. find-and-tray-stack, holding) gets its own figure.  Non-random-
pairs sweeps emit the plain filenames (single figure with n_targets
as the series).

If matplotlib is not installed, prints summary tables to stdout so the
sweep still produces a usable artifact on a fresh checkout.

Usage:
    python eval_plotter.py eval_results/sweep_<ts>_scalability/aggregated.csv
    python eval_plotter.py <csv> --baseline-csv <other csv>     # issue #10 stub
"""

import argparse
import csv
import json
import math
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
                      "plan_count",
                      "n_object_boxels", "n_shadow_boxels",
                      "n_free_space_boxels", "n_init_state_facts"):
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


def load_jsonl_rows(jsonl_path: Path) -> List[dict]:
    """Load aggregated.jsonl which preserves list/dict-valued columns
    that aggregated.csv drops via the LIST_VALUED gate in
    eval_runner.py (per-call timings, per-boxel volumes,
    n_facts_by_predicate).
    """
    rows: List[dict] = []
    if not jsonl_path.exists():
        return rows
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
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
    """Detect a random-pairs sweep — pure or mixed-scene.

    random_pairs_scene draws n_hidden/n_targets per seed, so n_targets
    is not a meaningful series axis here — the user-controlled axes are
    n_occluders and goal.  Plot with goal as the series instead.

    Audit #73 step 1(d) widened RANDOM_PAIRS_MATRIX to a list-of-sub-
    matrices that adds a stack-scene sub-tier for the 3rd goal.  Accept
    a sweep whose scenes are {random-pairs} OR {random-pairs, stack};
    reject anything else (so the default-matrix path still wins for the
    'default' sweep's mixed scenes).
    """
    scenes = {r.get("scene") for r in rows}
    return ("random-pairs" in scenes
            and not (scenes - {"random-pairs", "stack"}))


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


def group_boxel_counts(rows: List[dict],
                       goal: Optional[str] = None
                       ) -> Dict[str, Dict[int, Dict[str, List[int]]]]:
    """``{baseline: {n_occluders: {type_key: [samples]}}}``.

    Audit #73 TIER A plot 1 data prep.  ``type_key`` ∈ {"object",
    "shadow", "free_space"}.

    Includes failed runs — boxel counts are end-of-run registry snapshots,
    valid regardless of whether the plan succeeded.  Filtering on success
    would hide compactness data for baselines that fail more often (e.g.
    uniform's 0/15 success on find-and-tray-stack in the 2026-05-12 sweep),
    which is exactly the comparison the plot is meant to surface.  Cells
    that crashed before report_run_outcome (no_summary / timeout stubs)
    are skipped naturally — they have no boxel-count columns.
    """
    out: Dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    type_cols = {
        "object":     "n_object_boxels",
        "shadow":     "n_shadow_boxels",
        "free_space": "n_free_space_boxels",
    }
    for r in rows:
        if goal is not None and r.get("goal") != goal:
            continue
        try:
            x = int(r["n_occluders"])
        except (KeyError, TypeError, ValueError):
            continue
        baseline = r.get("baseline") or "semantic"
        for k, col in type_cols.items():
            v = r.get(col)
            if v in (None, ""):
                continue
            try:
                out[baseline][x][k].append(int(v))
            except (TypeError, ValueError):
                continue
    return out


def plot_boxel_count_breakdown(
    grouped: Dict[str, Dict[int, Dict[str, List[int]]]],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """Stacked bars OBJECT / SHADOW / FREE_SPACE by n_occluders;
    semantic and uniform shown side-by-side per X position.

    Audit #73 TIER A plot 1 — the compactness pillar's headline figure.
    Uniform's bar grows with n_occluders × workspace_vol / cell_size^3;
    semantic's grows linearly with (OBJECT + SHADOW) counts.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for baseline in sorted(grouped):
            for x in sorted(grouped[baseline]):
                parts = grouped[baseline][x]
                summary = ", ".join(
                    f"{k}={mean(parts[k]):.1f}" if parts.get(k) else f"{k}=-"
                    for k in ("object", "shadow", "free_space"))
                print(f"  {baseline}/n_occluders={x}: {summary}")
        return None

    baselines = sorted(grouped.keys())
    xs_all = sorted({x for b in baselines for x in grouped[b]})
    if not xs_all:
        print(f"[plotter] no data for {title}")
        return None
    n_baselines = max(len(baselines), 1)
    bar_w = 0.8 / n_baselines
    type_keys = ["object", "shadow", "free_space"]
    type_colors = {"object": "#1f77b4",
                   "shadow": "#ff7f0e",
                   "free_space": "#2ca02c"}
    type_labels = {"object": "OBJECT",
                   "shadow": "SHADOW",
                   "free_space": "FREE_SPACE"}

    fig, ax = plt.subplots(figsize=(max(6, 1.8 * len(xs_all)), 5))
    for i, baseline in enumerate(baselines):
        offsets = [x + (i - (n_baselines - 1) / 2) * bar_w for x in xs_all]
        bottoms = [0.0] * len(xs_all)
        for tk in type_keys:
            means = []
            for x in xs_all:
                samples = grouped[baseline].get(x, {}).get(tk, [])
                means.append(mean(samples) if samples else 0.0)
            ax.bar(offsets, means, bar_w, bottom=bottoms,
                   color=type_colors[tk],
                   alpha=1.0 if baseline == "semantic" else 0.55,
                   edgecolor="black", linewidth=0.5)
            bottoms = [b + m for b, m in zip(bottoms, means)]

    ax.set_ylabel("boxel count (mean over seeds)")
    ax.set_title(title)
    if len(xs_all) > 1:
        ax.set_xlabel("n_occluders")
        ax.set_xticks(xs_all)
    else:
        # Single-X (stack subtier): n_occluders=0 tick is meaningless;
        # the scene context is already in the title.
        ax.set_xticks([])
        ax.set_xlabel("")
    ax.grid(True, axis="y", alpha=0.3)
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=type_colors[tk], label=type_labels[tk])
               for tk in type_keys]
    if len(baselines) > 1:
        handles += [
            Patch(facecolor="lightgrey", edgecolor="black",
                  label="semantic (solid)"),
            Patch(facecolor="lightgrey", edgecolor="black",
                  alpha=0.55, label="uniform (faded)"),
        ]
    ax.legend(handles=handles, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def group_boxel_volumes(rows: List[dict],
                        goal: Optional[str] = None
                        ) -> Dict[str, Dict[str, List[float]]]:
    """``{baseline: {type_key: [all volumes pooled across cells]}}``.

    Audit #73 TIER A plot 3 data prep.  Pools volumes across cells
    within a (baseline, goal) bucket — the histogram shows the
    DISTRIBUTION of boxel sizes the planner sees, regardless of
    which cell produced any particular sample.  ``type_key`` ∈
    {"object", "shadow", "free_space"}.
    """
    out: Dict = defaultdict(lambda: defaultdict(list))
    vol_cols = {
        "object":     "boxel_volumes_object",
        "shadow":     "boxel_volumes_shadow",
        "free_space": "boxel_volumes_free_space",
    }
    for r in rows:
        if goal is not None and r.get("goal") != goal:
            continue
        baseline = r.get("baseline") or "semantic"
        for k, col in vol_cols.items():
            vs = r.get(col)
            if not vs:
                continue
            try:
                out[baseline][k].extend(float(v) for v in vs)
            except (TypeError, ValueError):
                continue
    return out


def plot_boxel_volume_histogram(
    grouped: Dict[str, Dict[str, List[float]]],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """Side-by-side histograms (semantic | uniform) of boxel
    volumes, overlaid by type.  Log-x because volumes span 3-4
    decades (OBJECT ~1e-5 m³ vs FREE_SPACE ~1e-2 m³).

    Audit #73 TIER A plot 3 — heterogeneity proof.  Semantic should
    show a wide spread (a few big FREE_SPACE + many small OBJECT/
    SHADOW); uniform by construction shows a narrow spike at
    cell_size³.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for baseline in sorted(grouped):
            for tk, vs in grouped[baseline].items():
                if not vs:
                    continue
                print(f"  {baseline}/{tk}: n={len(vs)}, "
                      f"min={min(vs):.6f}, max={max(vs):.6f}, "
                      f"mean={mean(vs):.6f}")
        return None

    baselines = sorted(grouped.keys())
    if not baselines:
        print(f"[plotter] no data for {title}")
        return None

    type_keys = ["object", "shadow", "free_space"]
    type_colors = {"object": "#1f77b4",
                   "shadow": "#ff7f0e",
                   "free_space": "#2ca02c"}
    type_labels = {"object": "OBJECT",
                   "shadow": "SHADOW",
                   "free_space": "FREE_SPACE"}

    all_vols = [v for b in baselines for tk in type_keys
                for v in grouped[b].get(tk, []) if v > 0]
    if not all_vols:
        print(f"[plotter] no positive volumes for {title}")
        return None
    lo = math.log10(max(min(all_vols), 1e-8))
    hi = math.log10(max(all_vols))
    if hi <= lo:
        hi = lo + 1.0
    bins = [10 ** (lo + (hi - lo) * i / 30) for i in range(31)]

    fig, axes = plt.subplots(1, len(baselines),
                             figsize=(5 * len(baselines), 4.5),
                             sharey=True, sharex=True)
    if len(baselines) == 1:
        axes = [axes]
    for ax, baseline in zip(axes, baselines):
        for tk in type_keys:
            vs = [v for v in grouped[baseline].get(tk, []) if v > 0]
            if not vs:
                continue
            ax.hist(vs, bins=bins, color=type_colors[tk],
                    alpha=0.55, edgecolor="black", linewidth=0.3,
                    label=f"{type_labels[tk]} (n={len(vs)})")
        ax.set_xscale("log")
        ax.set_xlabel("boxel volume (m³)")
        ax.set_title(baseline)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)
    axes[0].set_ylabel("count")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def group_failure_modes(rows: List[dict]
                        ) -> Dict[tuple, Dict[str, int]]:
    """``{(goal, baseline): {exit_reason: count}}``.

    Audit #73 TIER B plot 6 data prep.  Counts ALL cells (successful
    runs go into the "success" bucket).  Bar height per (goal, baseline)
    thus equals total cells in that group — gives the reader an implicit
    failure-rate reference.
    """
    out: Dict = defaultdict(lambda: defaultdict(int))
    for r in rows:
        goal = r.get("goal")
        baseline = r.get("baseline") or "semantic"
        if r.get("success"):
            key = "success"
        else:
            key = r.get("exit_reason") or "unknown"
        out[(goal, baseline)][key] += 1
    return out


def plot_failure_modes(grouped: Dict[tuple, Dict[str, int]],
                       title: str,
                       out_path: Path) -> Optional[Path]:
    """Stacked bar per (goal, baseline) with exit_reason categories.

    Audit #73 TIER B plot 6 — failure-mode breakdown.  Counts include
    "success" so bar height = total cells per group (lets the reader
    see failure rate visually).  Each failure mode gets its own colour;
    "success" is pinned to the bottom layer in green so the eye reads
    "tall green = good".
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for key in sorted(grouped):
            parts = grouped[key]
            summary = ", ".join(f"{k}={v}" for k, v in sorted(parts.items()))
            print(f"  {key}: {summary}")
        return None

    keys = sorted(grouped.keys())  # (goal, baseline) tuples
    all_reasons = sorted({r for v in grouped.values() for r in v.keys()})
    # Pin 'success' to the bottom layer so it forms the visual base of
    # the bar and failures stack above it.
    if "success" in all_reasons:
        all_reasons.remove("success")
        all_reasons = ["success"] + all_reasons

    labels = [f"{g}\n{b}" for g, b in keys]
    xs = list(range(len(keys)))

    fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(keys)), 5))
    cmap = plt.get_cmap("tab10")
    bottoms = [0.0] * len(keys)
    for ri, reason in enumerate(all_reasons):
        counts = [grouped[k].get(reason, 0) for k in keys]
        color = "#2ca02c" if reason == "success" else cmap(ri % 10)
        ax.bar(xs, counts, 0.7, bottom=bottoms,
               color=color, edgecolor="black", linewidth=0.5,
               label=reason)
        bottoms = [b + c for b, c in zip(bottoms, counts)]

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_xlabel("(goal, baseline)")
    ax.set_ylabel("cell count")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=8, title="exit_reason")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


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


def write_summary_table(rows: List[dict], out_dir: Path) -> None:
    """Write success-rate + key-metric summary to <sweep>/summary_table.md
    plus two CSVs (aggregate + per-occluder breakdown).

    Audit #73 — supplementary tabular view of the eval data.  Markdown
    is viewable in any editor with preview; CSVs open in any spreadsheet.
    Also echoed to stdout so the table shows up in the runner log.
    """
    import csv as _csv
    from collections import defaultdict

    def _mean_or_none(group, col, success_only=False):
        vals = []
        for r in group:
            if success_only and not r.get("success"):
                continue
            v = r.get(col)
            if v in (None, ""):
                continue
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        return mean(vals) if vals else None

    def _stats(group):
        n_total = len(group)
        n_success = sum(1 for r in group if r.get("success"))
        mean_obj = _mean_or_none(group, "n_object_boxels")
        mean_shd = _mean_or_none(group, "n_shadow_boxels")
        mean_fs  = _mean_or_none(group, "n_free_space_boxels")
        if any(x is None for x in (mean_obj, mean_shd, mean_fs)):
            mean_total_boxels = None
        else:
            mean_total_boxels = mean_obj + mean_shd + mean_fs
        return {
            "n_cells":           n_total,
            "n_success":         n_success,
            "success_rate":      n_success / n_total if n_total else 0.0,
            "mean_plan_time_s":  _mean_or_none(group, "total_planning_time_s",
                                               success_only=True),
            "mean_plan_count":   _mean_or_none(group, "plan_count",
                                               success_only=True),
            "mean_init_facts":   _mean_or_none(group, "n_init_state_facts"),
            "mean_total_boxels": mean_total_boxels,
        }

    def _fmt(v, spec=".2f"):
        if v is None:
            return "—"
        return format(v, spec) if isinstance(v, float) else str(v)

    by_gb: Dict[tuple, List[dict]] = defaultdict(list)
    for r in rows:
        by_gb[(r.get("goal") or "?",
               r.get("baseline") or "semantic")].append(r)

    by_gbo: Dict[tuple, List[dict]] = defaultdict(list)
    for r in rows:
        try:
            occ = int(r.get("n_occluders"))
        except (TypeError, ValueError):
            occ = None
        by_gbo[(r.get("goal") or "?",
                r.get("baseline") or "semantic", occ)].append(r)

    md = [
        f"# Summary table — {out_dir.name}",
        "",
        "## Aggregate by (goal, baseline)",
        "",
        "| goal | baseline | n_cells | success | success_rate "
        "| mean plan_time (s) | mean plan_count "
        "| mean init_facts | mean total_boxels |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    csv_overview = [["goal", "baseline", "n_cells", "n_success",
                     "success_rate", "mean_plan_time_s", "mean_plan_count",
                     "mean_init_facts", "mean_total_boxels"]]
    for key in sorted(by_gb.keys()):
        s = _stats(by_gb[key])
        goal, baseline = key
        md.append(
            f"| {goal} | {baseline} | {s['n_cells']} | {s['n_success']} | "
            f"{s['success_rate']*100:.1f}% | "
            f"{_fmt(s['mean_plan_time_s'])} | "
            f"{_fmt(s['mean_plan_count'])} | "
            f"{_fmt(s['mean_init_facts'], '.0f')} | "
            f"{_fmt(s['mean_total_boxels'], '.1f')} |"
        )
        csv_overview.append([
            goal, baseline, s["n_cells"], s["n_success"],
            f"{s['success_rate']:.4f}",
            "" if s["mean_plan_time_s"] is None else f"{s['mean_plan_time_s']:.4f}",
            "" if s["mean_plan_count"] is None else f"{s['mean_plan_count']:.4f}",
            "" if s["mean_init_facts"] is None else f"{s['mean_init_facts']:.2f}",
            "" if s["mean_total_boxels"] is None else f"{s['mean_total_boxels']:.4f}",
        ])

    md += [
        "",
        "## Per-occluder breakdown",
        "",
        "Note: stack-scene cells log `n_occluders=0` because stack_scene "
        "has no occluders by construction (the matrix-axis value is tag-"
        "only and is not passed through to the pipeline).",
        "",
        "| goal | baseline | n_occluders | n_cells | success | success_rate "
        "| mean plan_time (s) | mean plan_count "
        "| mean init_facts | mean total_boxels |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    csv_detail = [["goal", "baseline", "n_occluders", "n_cells", "n_success",
                   "success_rate", "mean_plan_time_s", "mean_plan_count",
                   "mean_init_facts", "mean_total_boxels"]]
    for key in sorted(by_gbo.keys(),
                      key=lambda k: (k[0], k[1],
                                     -1 if k[2] is None else k[2])):
        s = _stats(by_gbo[key])
        goal, baseline, occ = key
        occ_str = "—" if occ is None else str(occ)
        md.append(
            f"| {goal} | {baseline} | {occ_str} | {s['n_cells']} | "
            f"{s['n_success']} | {s['success_rate']*100:.1f}% | "
            f"{_fmt(s['mean_plan_time_s'])} | "
            f"{_fmt(s['mean_plan_count'])} | "
            f"{_fmt(s['mean_init_facts'], '.0f')} | "
            f"{_fmt(s['mean_total_boxels'], '.1f')} |"
        )
        csv_detail.append([
            goal, baseline, "" if occ is None else occ,
            s["n_cells"], s["n_success"],
            f"{s['success_rate']:.4f}",
            "" if s["mean_plan_time_s"] is None else f"{s['mean_plan_time_s']:.4f}",
            "" if s["mean_plan_count"] is None else f"{s['mean_plan_count']:.4f}",
            "" if s["mean_init_facts"] is None else f"{s['mean_init_facts']:.2f}",
            "" if s["mean_total_boxels"] is None else f"{s['mean_total_boxels']:.4f}",
        ])

    md_text = "\n".join(md) + "\n"
    (out_dir / "summary_table.md").write_text(md_text, encoding="utf-8")
    print(f"[plotter] wrote {out_dir / 'summary_table.md'}")

    with (out_dir / "summary_table_aggregate.csv").open(
            "w", newline="", encoding="utf-8") as f:
        _csv.writer(f).writerows(csv_overview)
    print(f"[plotter] wrote {out_dir / 'summary_table_aggregate.csv'}")
    with (out_dir / "summary_table_per_occluders.csv").open(
            "w", newline="", encoding="utf-8") as f:
        _csv.writer(f).writerows(csv_detail)
    print(f"[plotter] wrote {out_dir / 'summary_table_per_occluders.csv'}")

    # Echo to stdout so the runner log carries the table verbatim.
    print()
    print(md_text)


def _plot_single_x_summary(grouped, baseline_grouped, title, ylabel, out_path,
                           main_label_suffix, baseline_label_suffix):
    """Side-by-side bar comparison when a metric has only ONE X value.

    Replaces a degenerate 1-point line plot with annotated bars (one bar
    per series, plus the baseline overlay if present).  Used implicitly
    by the stack-subtier of mixed-scene RANDOM_PAIRS_MATRIX (stack_scene
    has no occluders so X collapses to one value).  Each bar shows
    mean +/- 1 std (lower whisker clipped at 0) with the sample count
    annotated above.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (single-X bar) ===")
        for tag, grp in (("(main)" + main_label_suffix, grouped),
                         ("(baseline)" + baseline_label_suffix, baseline_grouped)):
            if not grp:
                continue
            for s_val, xy in sorted(grp.items(), key=lambda kv: str(kv[0])):
                for samples in xy.values():
                    if samples:
                        m = mean(samples)
                        sd = pstdev(samples) if len(samples) > 1 else 0.0
                        print(f"  {s_val} {tag}: mean={m:.3g} "
                              f"std={sd:.3g} n={len(samples)}")
        return None

    bars = []  # (label, mean, std, n)
    for s_val, xy in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        for samples in xy.values():
            if samples:
                bars.append((f"{s_val}{main_label_suffix}",
                             mean(samples),
                             pstdev(samples) if len(samples) > 1 else 0.0,
                             len(samples)))
                break
    if baseline_grouped:
        for s_val, xy in sorted(baseline_grouped.items(),
                                 key=lambda kv: str(kv[0])):
            for samples in xy.values():
                if samples:
                    bars.append((f"{s_val}{baseline_label_suffix}",
                                 mean(samples),
                                 pstdev(samples) if len(samples) > 1 else 0.0,
                                 len(samples)))
                    break

    if not bars:
        print(f"[plotter] no data for {title}")
        return None

    fig, ax = plt.subplots(figsize=(max(5, 1.5 * len(bars)), 5))
    xs = list(range(len(bars)))
    means = [b[1] for b in bars]
    stds  = [b[2] for b in bars]
    yerr_lo = [min(sd, m) for m, sd in zip(means, stds)]  # clip at 0
    ax.bar(xs, means, 0.6, yerr=[yerr_lo, stds], capsize=4,
           edgecolor="black", linewidth=0.5)
    for x, (lab, m, sd, n) in zip(xs, bars):
        ax.text(x, m + (sd or 0), f"{m:.3g}\n(n={n})",
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(xs)
    ax.set_xticklabels([b[0] for b in bars])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


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
    # Detect single-X — a line plot 'vs <axis>' with one X value reads
    # as a stray dot, not a graph.  Render as side-by-side bars instead.
    # Stack-subtier of mixed-scene RANDOM_PAIRS_MATRIX hits this (X=0
    # because cell_to_argv skips --n-occluders for stack scenes).
    xs_all = {x for sxy in grouped.values() for x in sxy.keys()}
    if baseline_grouped:
        xs_all |= {x for sxy in baseline_grouped.values() for x in sxy.keys()}
    if len(xs_all) <= 1:
        return _plot_single_x_summary(
            grouped, baseline_grouped, title, ylabel, out_path,
            main_label_suffix, baseline_label_suffix)

    if not HAVE_MPL:
        _print_text_table(grouped, title + main_label_suffix)
        if baseline_grouped is not None:
            _print_text_table(baseline_grouped,
                              f"{title}{baseline_label_suffix}")
        return None

    fig, ax = plt.subplots(figsize=(7, 5))

    def _plot(grp, suffix, linestyle):
        # Shaded +/-1 std band instead of errorbar whiskers — the
        # whiskers-and-caps form was so dense it read as a mesh of
        # intersecting lines.  Band is clipped to the metric's ylim if
        # given (success_rate stays in [0, 1]; time/count don't dip
        # below 0).
        for s_val, xy in sorted(grp.items(), key=lambda kv: str(kv[0])):
            xs = sorted(xy.keys())
            means = [mean(xy[x]) for x in xs]
            stds = [pstdev(xy[x]) if len(xy[x]) > 1 else 0.0 for x in xs]
            line = ax.plot(xs, means, marker="o", linestyle=linestyle,
                           label=f"{series_label}={s_val}{suffix}")[0]
            lo_clip = ylim[0] if ylim else 0.0
            hi_clip = ylim[1] if ylim else None
            lo = [max(lo_clip, m - s) for m, s in zip(means, stds)]
            hi = [(min(hi_clip, m + s) if hi_clip is not None else m + s)
                  for m, s in zip(means, stds)]
            ax.fill_between(xs, lo, hi, alpha=0.18,
                            color=line.get_color())

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

    # Audit #73 TIER B plot 6: capture the full row set before any
    # auto-split mutates `rows` below — failure-mode breakdown is
    # sweep-level and needs every cell, success and failure.
    all_rows = list(rows)

    out_dir = args.csv_path.parent
    # Audit #73 plot 3: per-boxel volumes are LIST_VALUED, so they
    # live in aggregated.jsonl rather than the flat CSV.  Empty list
    # on pre-#73-step-2(c) sweeps; the histogram helper renders a
    # "no data" stub cleanly.
    jsonl_rows = load_jsonl_rows(out_dir / "aggregated.jsonl")

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
        plot_failure_modes(
            group_failure_modes(all_rows),
            title="Failure-mode breakdown by (goal, baseline)",
            out_path=out_dir / "failure_modes.png",
        )
        write_summary_table(all_rows, out_dir)
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
    # not a meaningful series axis here.  Plot one figure PER goal so
    # find-and-tray-stack and holding do not share axes (user direction
    # 2026-05-12 — both-on-one plot was unreadable).  Non-random-pairs
    # sweeps keep the single-figure layout (n_targets as the series).
    if _is_random_pairs_matrix(rows + (baseline_rows or [])):
        series_key = "goal"
        series_label = "goal"
        all_goals = sorted({r.get("goal") for r in rows + (baseline_rows or [])
                            if r.get("goal")})
        goal_buckets = [
            (g,
             [r for r in rows if r.get("goal") == g],
             ([r for r in baseline_rows if r.get("goal") == g]
              if baseline_rows else None))
            for g in all_goals
        ]
    else:
        series_key = "n_targets"
        series_label = "n_targets"
        goal_buckets = [(None, rows, baseline_rows)]

    for goal, g_rows, g_baseline in goal_buckets:
        suffix = f"__{goal}" if goal else ""
        title_suffix = f" — {goal}" if goal else ""
        plot_metric(
            group_metric(g_rows, series=series_key,
                         metric="total_planning_time_s",
                         success_only=True),
            title=f"Planning time vs scene size (success-only){title_suffix}",
            ylabel="mean total planning time (s)",
            out_path=out_dir / f"planning_time_vs_n_occluders{suffix}.png",
            baseline_grouped=(group_metric(g_baseline, series=series_key,
                                           metric="total_planning_time_s",
                                           success_only=True)
                              if g_baseline else None),
            series_label=series_label,
            main_label_suffix=main_label_suffix,
            baseline_label_suffix=baseline_label_suffix,
        )
        plot_metric(
            group_success_rate(g_rows, series=series_key),
            title=f"Success rate vs scene size{title_suffix}",
            ylabel="success rate (over seeds)",
            out_path=out_dir / f"success_rate_vs_n_occluders{suffix}.png",
            ylim=(0.0, 1.05),
            baseline_grouped=(group_success_rate(g_baseline, series=series_key)
                              if g_baseline else None),
            series_label=series_label,
            main_label_suffix=main_label_suffix,
            baseline_label_suffix=baseline_label_suffix,
        )
        plot_metric(
            group_metric(g_rows, series=series_key,
                         metric="plan_count", success_only=True),
            title=f"Plan count (replans) vs scene size (success-only){title_suffix}",
            ylabel="mean plan_count",
            out_path=out_dir / f"plan_count_vs_n_occluders{suffix}.png",
            baseline_grouped=(group_metric(g_baseline, series=series_key,
                                           metric="plan_count",
                                           success_only=True)
                              if g_baseline else None),
            series_label=series_label,
            main_label_suffix=main_label_suffix,
            baseline_label_suffix=baseline_label_suffix,
        )
        # Audit #73 TIER A plot 1: boxel-count breakdown (OBJECT /
        # SHADOW / FREE_SPACE stacked, semantic-vs-uniform side-by-
        # side).  Compactness pillar's headline figure.  No-op on
        # pre-9918047 CSVs (the new columns are missing; the helper
        # prints '[plotter] no data ...' and skips the figure).
        plot_boxel_count_breakdown(
            group_boxel_counts(g_rows + (g_baseline or []), goal=goal),
            title=f"Boxel count breakdown vs n_occluders{title_suffix}",
            out_path=out_dir / f"boxel_count_breakdown{suffix}.png",
        )
        # Audit #73 TIER A plot 2: PDDL init-state fact count vs
        # n_occluders.  Same X-axis as plot 1 but in the planner's
        # units; THESIS_NOTES §14 cites "init facts dominate planning
        # cost" — this plot quantifies the dependence.  Per-predicate
        # stratification (n_facts_by_predicate, jsonl-only) is the
        # follow-on bonus pass; this MVP just plots the total.
        # Includes failed runs — n_init_state_facts is the grounding-
        # cost number from the planner's last call regardless of plan
        # outcome.  Filtering on success hid uniform completely on
        # find-and-tray-stack (0/15 success), which is exactly the
        # comparison the plot is meant to surface.
        plot_metric(
            group_metric(g_rows, series=series_key,
                         metric="n_init_state_facts",
                         success_only=False),
            title=f"Init-state fact count vs n_occluders{title_suffix}",
            ylabel="mean n_init_state_facts",
            out_path=out_dir / f"init_state_facts_vs_n_occluders{suffix}.png",
            baseline_grouped=(group_metric(g_baseline, series=series_key,
                                           metric="n_init_state_facts",
                                           success_only=False)
                              if g_baseline else None),
            series_label=series_label,
            main_label_suffix=main_label_suffix,
            baseline_label_suffix=baseline_label_suffix,
        )
        # Audit #73 TIER A plot 3: boxel-volume histogram (semantic
        # vs uniform).  Heterogeneity proof — semantic shows a wide
        # spread, uniform a narrow spike near cell_size³.  Reads
        # aggregated.jsonl (per-boxel volume lists are LIST_VALUED,
        # dropped from the flat CSV); no-op on pre-#73-step-2(c)
        # sweeps.
        plot_boxel_volume_histogram(
            group_boxel_volumes(jsonl_rows, goal=goal),
            title=f"Boxel volume histogram{title_suffix}",
            out_path=out_dir / f"boxel_volume_histogram{suffix}.png",
        )
    # Audit #73 TIER B plot 6: failure-mode breakdown (sweep-level
    # stacked bar per (goal, baseline)).  Counts all cells including
    # successes so bar height = total cells per group.
    plot_failure_modes(
        group_failure_modes(all_rows),
        title="Failure-mode breakdown by (goal, baseline)",
        out_path=out_dir / "failure_modes.png",
    )
    # Audit #73 — tabular summary alongside the plots (markdown +
    # 2 CSVs).  Aggregate by (goal, baseline) + per-occluder breakdown.
    write_summary_table(all_rows, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
