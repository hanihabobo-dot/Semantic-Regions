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
from statistics import mean, median, stdev, quantiles
from typing import Dict, List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


# Audit #94 — explicit colour map for exit_reason categories so the
# stacked-bar legend in plot_failure_modes does not collide on tab10's
# default cycle (where index 2 is green, matching the success colour
# and rendering "success" vs "planner_failed" or whichever lands on
# index 2 visually indistinguishable).
EXIT_REASON_COLOUR = {
    "success":          "#2ca02c",   # green
    "planner_failed":   "#d62728",   # red
    "timeout":          "#7f0000",   # dark red
    "replan_limit":     "#ff7f0e",   # orange
    "no_summary":       "#8c564b",   # brown
    "physics_mismatch": "#9467bd",   # purple
    "drop_failed":      "#e377c2",   # pink
    "all_searched":     "#17becf",   # cyan
    "unknown":          "#999999",   # gray
}


def load_rows(csv_path: Path) -> List[dict]:
    rows: List[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            for k in ("n_occluders", "n_targets", "n_hidden", "seed",
                      "plan_count", "n_sense_actions",
                      "n_object_boxels", "n_shadow_boxels",
                      "n_free_space_boxels", "n_init_state_facts"):
                v = r.get(k)
                if v not in (None, ""):
                    try:
                        r[k] = int(v)
                    except ValueError:
                        pass
            for k in ("total_planning_time_s", "wall_clock_s",
                      "min_boxel_size"):
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
            sd = stdev(samples) if len(samples) > 1 else 0.0
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
            stds.append(stdev(samples) if len(samples) > 1 else 0.0)
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


def group_boxel_evolution_per_replan(
    rows: List[dict],
    goal: Optional[str] = None,
) -> Dict[str, List[List[dict]]]:
    """``{baseline: [per_cell_trajectory, ...]}`` where each trajectory is
    a list of ``{plan_index, n_object_boxels, n_shadow_boxels,
    n_free_space_boxels}`` dicts (one per planner.plan() call).

    Audit #73 TIER A plot 11 data prep.  Reads jsonl rows only — the
    boxel_counts_per_replan column is LIST_VALUED.
    """
    out: Dict = defaultdict(list)
    for r in rows:
        if goal is not None and r.get("goal") != goal:
            continue
        traj = r.get("boxel_counts_per_replan")
        if not traj:
            continue
        baseline = r.get("baseline") or "semantic"
        out[baseline].append(traj)
    return out


def plot_boxel_evolution_per_replan(
    grouped: Dict[str, List[List[dict]]],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """One panel per baseline: per-replan boxel count means with shaded
    +/-1 std bands, one line per type (OBJECT / SHADOW / FREE_SPACE).

    Audit #73 TIER A plot 11 — adaptive-partition evolution.  Visualises
    whether the partition actually mutates as occluders move and shadows
    resolve across replans (semantic should drift; uniform should be
    approximately flat).
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for baseline in sorted(grouped):
            cells = grouped[baseline]
            indices = sorted({s["plan_index"] for c in cells for s in c})
            for pi in indices:
                obj = [s["n_object_boxels"] for c in cells for s in c
                       if s["plan_index"] == pi]
                shd = [s["n_shadow_boxels"] for c in cells for s in c
                       if s["plan_index"] == pi]
                fs = [s["n_free_space_boxels"] for c in cells for s in c
                      if s["plan_index"] == pi]
                if obj:
                    print(f"  {baseline}/plan#{pi}: "
                          f"obj_mean={mean(obj):.1f} "
                          f"shd_mean={mean(shd):.1f} "
                          f"fs_mean={mean(fs):.1f} n={len(obj)}")
        return None

    baselines = sorted(grouped.keys())
    if not baselines or not any(grouped[b] for b in baselines):
        print(f"[plotter] no data for {title}")
        return None

    type_cols = {"object": "n_object_boxels",
                 "shadow": "n_shadow_boxels",
                 "free_space": "n_free_space_boxels"}
    type_colors = {"object": "#1f77b4",
                   "shadow": "#ff7f0e",
                   "free_space": "#2ca02c"}
    type_labels = {"object": "OBJECT",
                   "shadow": "SHADOW",
                   "free_space": "FREE_SPACE"}

    fig, axes = plt.subplots(
        1, len(baselines),
        figsize=(5 * len(baselines), 4),
        sharey=True, squeeze=False,
    )
    axes = axes[0]
    for ax, baseline in zip(axes, baselines):
        cells = grouped[baseline]
        indices = sorted({s["plan_index"] for c in cells for s in c})
        if not indices:
            ax.set_title(f"{baseline} (no data)")
            continue
        for tk, col in type_cols.items():
            means = []
            stds = []
            for pi in indices:
                samples = [s[col] for c in cells for s in c
                           if s["plan_index"] == pi]
                means.append(mean(samples) if samples else 0.0)
                stds.append(stdev(samples) if len(samples) > 1 else 0.0)
            lower = [m - sd for m, sd in zip(means, stds)]
            upper = [m + sd for m, sd in zip(means, stds)]
            ax.plot(indices, means, color=type_colors[tk],
                    label=type_labels[tk], marker="o", markersize=4)
            ax.fill_between(indices, lower, upper,
                            color=type_colors[tk], alpha=0.2)
        ax.set_title(baseline)
        ax.set_xlabel("plan index (replan)")
        ax.set_xticks(indices)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(loc="best", fontsize=8)

    axes[0].set_ylabel("boxel count (mean +/-1 std across cells)")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def group_per_call_planning_time(
    rows: List[dict],
    goal: Optional[str] = None,
) -> Dict[str, List[List[float]]]:
    """``{baseline: [per_cell_list, ...]}`` where each per_cell_list is one
    cell's ``per_call_planning_time_s`` — one entry per planner.plan()
    call.

    Audit #73 TIER C plot 7 data prep.  Reads jsonl rows only — the
    per_call_planning_time_s column is LIST_VALUED in eval_runner.py.
    Includes failed runs: every plan call gets timed regardless of
    overall outcome, and a failure-correlated slowdown is itself a
    finding.
    """
    out: Dict = defaultdict(list)
    for r in rows:
        if goal is not None and r.get("goal") != goal:
            continue
        seq = r.get("per_call_planning_time_s")
        if not seq:
            continue
        baseline = r.get("baseline") or "semantic"
        try:
            out[baseline].append([float(t) for t in seq])
        except (TypeError, ValueError):
            continue
    return out


def plot_per_call_planning_time(
    grouped: Dict[str, List[List[float]]],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """One line per baseline; X = plan index (0 = first plan, 1 = first
    replan, ...); Y = mean per-call planning time with +/-1 std band.

    Audit #73 TIER C plot 7 — per-call planning time vs replan index.
    Quantifies THESIS_NOTES §21.3's framing that PDDLStream "pays
    geometry-sampling cost per plan call" — replans cheaper would
    indicate caching warm-up; flat = no caching benefit; worse = state
    growth pathology.  Sample count thins toward higher plan_index as
    cells terminate at smaller plan_count; legend reports n_cells so
    readers can weight the right-edge means.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for baseline in sorted(grouped):
            seqs = grouped[baseline]
            if not seqs:
                continue
            max_len = max(len(s) for s in seqs)
            for pi in range(max_len):
                samples = [s[pi] for s in seqs if len(s) > pi]
                if samples:
                    sd = stdev(samples) if len(samples) > 1 else 0.0
                    print(f"  {baseline}/plan#{pi}: "
                          f"mean={mean(samples):.3f} "
                          f"std={sd:.3f} n={len(samples)}")
        return None

    baselines = sorted(grouped.keys())
    if not baselines or not any(grouped[b] for b in baselines):
        print(f"[plotter] no data for {title}")
        return None

    fig, ax = plt.subplots(figsize=(7, 5))
    for baseline in baselines:
        seqs = grouped[baseline]
        if not seqs:
            continue
        max_len = max(len(s) for s in seqs)
        if max_len == 0:
            continue
        xs = list(range(max_len))
        means, stds = [], []
        for pi in xs:
            samples = [s[pi] for s in seqs if len(s) > pi]
            means.append(mean(samples) if samples else 0.0)
            stds.append(stdev(samples) if len(samples) > 1 else 0.0)
        line = ax.plot(xs, means, marker="o",
                       label=f"{baseline} (n_cells={len(seqs)})")[0]
        lower = [max(0.0, m - sd) for m, sd in zip(means, stds)]
        upper = [m + sd for m, sd in zip(means, stds)]
        ax.fill_between(xs, lower, upper, alpha=0.2,
                        color=line.get_color())

    ax.set_xlabel("plan index (0 = first plan, 1 = first replan, ...)")
    ax.set_ylabel("mean per-call planning time (s)")
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def group_wallclock_vs_planning(
    rows: List[dict],
    goal: Optional[str] = None,
) -> Dict[str, List[tuple]]:
    """``{baseline: [(planning_time_s, wall_clock_s), ...]}``.

    Audit #73 TIER C plot 8 data prep.  Pairs total_planning_time_s
    with wall_clock_s per cell — both are scalar CSV columns, no jsonl
    read needed.  Includes failed runs: the failure profile surfaces
    naturally as points clustered low on the X axis (no_summary cells
    have no planning time at all; planner_failed cells have small X +
    medium Y; success cells trend along the diagonal at higher X).
    """
    out: Dict = defaultdict(list)
    for r in rows:
        if goal is not None and r.get("goal") != goal:
            continue
        pt = r.get("total_planning_time_s")
        wc = r.get("wall_clock_s")
        if pt in (None, "") or wc in (None, ""):
            continue
        try:
            out[r.get("baseline") or "semantic"].append(
                (float(pt), float(wc)))
        except (TypeError, ValueError):
            continue
    return out


def plot_wallclock_vs_planning(
    grouped: Dict[str, List[tuple]],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """Scatter: X = total_planning_time_s, Y = wall_clock_s, color by
    baseline.  Diagonal y=x marks "pure planning" — wall_clock <
    planning_time is impossible, so points sit on or above the line.

    Audit #73 TIER C plot 8 — wall-clock vs planning decomposition.
    Quantifies "what fraction of wall-clock is planning vs sim /
    execution".  Points well above y=x: long PyBullet step / perception
    / replan-orchestration tail.  Points near y=x: the planner
    dominated wall-clock (the case where #50's planner-perf
    investigation pays off).
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for baseline in sorted(grouped):
            pairs = grouped[baseline]
            if not pairs:
                continue
            pts = [p for p, _ in pairs]
            wcs = [w for _, w in pairs]
            ratios = [p / w for p, w in pairs if w > 0]
            print(f"  {baseline}: n={len(pairs)}, "
                  f"mean_planning_s={mean(pts):.3f}, "
                  f"mean_wall_clock_s={mean(wcs):.3f}, "
                  f"mean_planning_ratio="
                  f"{mean(ratios) if ratios else 0:.3f}")
        return None

    baselines = sorted(grouped.keys())
    if not baselines or not any(grouped[b] for b in baselines):
        print(f"[plotter] no data for {title}")
        return None

    baseline_colors = {"semantic": "#1f77b4", "uniform": "#ff7f0e"}
    fig, ax = plt.subplots(figsize=(7, 5.5))
    all_max = 0.0
    for baseline in baselines:
        pairs = grouped[baseline]
        if not pairs:
            continue
        xs = [p for p, _ in pairs]
        ys = [w for _, w in pairs]
        ax.scatter(xs, ys, s=36, alpha=0.65,
                   c=baseline_colors.get(baseline),
                   edgecolors="black", linewidths=0.4,
                   label=f"{baseline} (n={len(pairs)})")
        all_max = max(all_max, max(xs), max(ys))

    if all_max > 0:
        diag = [0, all_max]
        ax.plot(diag, diag, linestyle="--", color="gray",
                linewidth=1.0, alpha=0.7, label="y = x (pure planning)")

    ax.set_xlabel("total planning time (s)")
    ax.set_ylabel("wall clock (s)")
    ax.set_title(title)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def plot_tampura_wallclock_comparison(
    rows: List[dict],
    title: str,
    out_path: Path,
) -> Optional[Path]:
    """Bar chart: our find-and-tray-stack wall_clock_s (median + IQR
    over seeds, success-only) vs TAMPURA Partial Observability
    (57 ± 38 from arXiv:2403.10454 Table II).

    Audit #73 TIER C plot 9.  Three bars: semantic boxels, uniform
    baseline, TAMPURA Partial Observability.  Our numbers use
    median + IQR (robust to long-tail outliers visible in plot 8);
    TAMPURA reports mean ± std.  Hardware-parity caveat from
    THESIS_NOTES §21.1 lives in the figure caption.
    """
    # TAMPURA Partial Observability — arXiv:2403.10454 Table II,
    # 20 trials, mean ± std.  Hardcoded constants per audit spec;
    # update if the paper revises.
    TAMPURA_MEAN = 57.0
    TAMPURA_STD = 38.0
    TAMPURA_N = 20

    our_data: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        if r.get("goal") != "find-and-tray-stack":
            continue
        if not r.get("success"):
            continue
        wc = r.get("wall_clock_s")
        if wc in (None, ""):
            continue
        try:
            our_data[r.get("baseline") or "semantic"].append(float(wc))
        except (TypeError, ValueError):
            continue

    if not any(our_data.values()):
        print(f"[plotter] no successful find-and-tray-stack cells "
              f"for {title}")
        return None

    bars = []  # (label, central, lo_err, hi_err, n)
    for baseline in sorted(our_data.keys()):
        vs = sorted(our_data[baseline])
        n = len(vs)
        if n == 0:
            continue
        med = median(vs)
        if n >= 4:
            q1, _, q3 = quantiles(vs, n=4)
        else:
            # n < 4: not enough data for quartiles; fall back to
            # min/max range so the bar still gives a magnitude clue.
            q1, q3 = vs[0], vs[-1]
        bars.append((f"Ours\n{baseline}", med, med - q1, q3 - med, n))
    bars.append(("TAMPURA\nPartial Obs.",
                 TAMPURA_MEAN, TAMPURA_STD, TAMPURA_STD, TAMPURA_N))

    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for lab, c, lo, hi, n in bars:
            print(f"  {lab.replace(chr(10), ' ')}: "
                  f"{c:.1f} (-{lo:.1f}/+{hi:.1f}) n={n}")
        return None

    fig, ax = plt.subplots(figsize=(6.5, 5))
    xs = list(range(len(bars)))
    colors = ["#1f77b4", "#ff7f0e", "#d62728"]
    centrals = [b[1] for b in bars]
    yerr_lo = [b[2] for b in bars]
    yerr_hi = [b[3] for b in bars]
    ax.bar(xs, centrals, 0.6, yerr=[yerr_lo, yerr_hi], capsize=5,
           color=colors[:len(bars)], edgecolor="black", linewidth=0.5)
    for x, (_, c, _, hi, n) in zip(xs, bars):
        ax.text(x, c + hi, f"{c:.1f}s\n(n={n})",
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(xs)
    ax.set_xticklabels([b[0] for b in bars])
    ax.set_ylabel("wall clock per episode (s)")
    ax.set_title(title)
    # Audit #94 cosmetic — set_ylim was bottom=0 only, so the
    # "57.0s\n(n=N)" annotations placed at (c + hi) clipped against
    # the matplotlib-auto top.  Pin the top to 25% above the tallest
    # error-bar reach so the annotation has guaranteed headroom.
    _max_top = max(c + hi for _, c, _, hi, _ in bars)
    ax.set_ylim(bottom=0, top=_max_top * 1.25)
    ax.grid(True, axis="y", alpha=0.3)
    fig.text(0.5, 0.02,
             "Ours: median + IQR over seeds, success-only.  "
             "TAMPURA: mean ± std (Table II, 20 trials).\n"
             "Hardware caveat: TAMPURA 20-core Xeon Gold 6248; "
             "ours 8-core consumer CPU (THESIS_NOTES §21.1).",
             ha="center", fontsize=8, style="italic")
    fig.tight_layout(rect=[0, 0.10, 1, 1])
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
        # Audit #94 — use the explicit EXIT_REASON_COLOUR map (top of
        # this module) instead of falling through to cmap(ri % 10),
        # which previously collided "success" and "planner_failed" on
        # the same green when planner_failed landed on tab10 index 2.
        color = EXIT_REASON_COLOUR.get(reason, cmap(ri % 10))
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


# ---------------------------------------------------------------------------
# Audit #94 (#77 step 4) — IPC-style cumulative-solve-vs-wall-clock curve.
# ---------------------------------------------------------------------------

def _has_anytime_axis(rows: List[dict]) -> bool:
    """Detect a SCALABILITY_VS_TIME (audit #77) sweep by the presence
    of a non-null min_boxel_size in the row set.

    The anytime curve is only meaningful when the sweep varies
    min_boxel_size — otherwise it collapses to one line per baseline.
    """
    for r in rows:
        mbs = r.get("min_boxel_size")
        if mbs in (None, ""):
            continue
        try:
            if float(mbs) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def group_solved_vs_time(rows: List[dict]
                         ) -> Dict[tuple, tuple]:
    """``{(goal, baseline, min_boxel_size_or_None): (n_total, [wall_clocks_of_successes])}``.

    Input for the IPC-style cumulative-solve curve (audit #94 /
    #77 step 4).  Denominator is ALL cells in the (goal, variant)
    group so the right-hand asymptote equals that group's success
    rate; the curve plots successful wall_clock_s ascending.
    """
    out_n: Dict[tuple, int] = defaultdict(int)
    out_solved: Dict[tuple, List[float]] = defaultdict(list)
    for r in rows:
        goal = r.get("goal")
        baseline = r.get("baseline") or "semantic"
        mbs = r.get("min_boxel_size")
        if mbs in (None, ""):
            mbs_key: Optional[float] = None
        else:
            try:
                mbs_key = float(mbs)
            except (TypeError, ValueError):
                mbs_key = None
        key = (goal, baseline, mbs_key)
        out_n[key] += 1
        if not r.get("success"):
            continue
        wc = r.get("wall_clock_s")
        if wc in (None, ""):
            continue
        try:
            out_solved[key].append(float(wc))
        except (TypeError, ValueError):
            continue
    return {key: (n, sorted(out_solved[key])) for key, n in out_n.items()}


def plot_solved_vs_time(grouped: Dict[tuple, tuple],
                        title: str,
                        out_path: Path) -> Optional[Path]:
    """IPC-style cumulative-solve-rate-vs-wall-clock-budget curve
    (audit #94 / #77 step 4).  One subplot per goal; one line per
    (baseline, min_boxel_size).

    Y: percentage of cells in the (goal, variant) group solved within
    the wall-clock budget on X.  X: wall-clock budget in seconds, log
    scale.  Denominator is ALL cells (success + failure), so the
    plateau on the right equals the group's overall success rate.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for key in sorted(grouped.keys(),
                          key=lambda k: (k[0] or "", k[1] or "",
                                         k[2] if k[2] is not None else -1.0)):
            n_total, solved = grouped[key]
            print(f"  {key}: solved={len(solved)}/{n_total}")
        return None

    by_goal: Dict[str, Dict[tuple, tuple]] = defaultdict(dict)
    for (goal, baseline, mbs), payload in grouped.items():
        if goal is None:
            continue
        by_goal[goal][(baseline, mbs)] = payload

    goals = sorted(by_goal.keys())
    if not goals:
        print(f"[plotter] no rows with a goal field for {title}")
        return None

    fig, axes = plt.subplots(1, len(goals),
                              figsize=(5 * len(goals), 4.6),
                              sharey=True)
    if len(goals) == 1:
        axes = [axes]

    def _variant_style(baseline: str, mbs: Optional[float]) -> tuple:
        if baseline == "uniform":
            return ("uniform", "#7f7f7f")
        if mbs is None:
            return ("semantic", "#1f77b4")
        return (f"semantic+mbs{mbs}", "#ff7f0e")

    for ax, goal in zip(axes, goals):
        for (baseline, mbs), (n_total, solved) in sorted(
                by_goal[goal].items(),
                key=lambda kv: (kv[0][0],
                                kv[0][1] if kv[0][1] is not None else -1.0)):
            label_base, color = _variant_style(baseline, mbs)
            label = f"{label_base} ({len(solved)}/{n_total})"
            if not solved or n_total == 0:
                ax.plot([], [], color=color, label=label)
                continue
            ys = [(i + 1) / n_total * 100 for i in range(len(solved))]
            ax.step([solved[0]] + solved, [0] + ys, where="post",
                    color=color, label=label)
        ax.set_xscale("log")
        ax.set_xlabel("wall-clock budget (s, log)")
        ax.set_title(goal)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=8)
    axes[0].set_ylabel("instances solved (%)")
    axes[0].set_ylim(0, 100)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[plotter] wrote {out_path}")
    return out_path


def group_plan_count_distribution(rows: List[dict]
                                  ) -> Dict[tuple, List[int]]:
    """``{(goal, baseline): [plan_count, ...]}``.

    Audit #73 TIER B plot 5 data prep.  All cells included; failed
    runs typically sit at max_replans and pile at the right edge of
    the histogram, which is the intended diagnostic (the failure
    tail surfaces alongside the convergence distribution).
    """
    out: Dict = defaultdict(list)
    for r in rows:
        goal = r.get("goal")
        baseline = r.get("baseline") or "semantic"
        pc = r.get("plan_count")
        if pc in (None, ""):
            continue
        try:
            out[(goal, baseline)].append(int(pc))
        except (ValueError, TypeError):
            continue
    return out


def plot_plan_count_distribution(grouped: Dict[tuple, List[int]],
                                 title: str,
                                 out_path: Path) -> Optional[Path]:
    """Histogram of plan_count per (goal, baseline) — one panel per
    cell of the goal x baseline grid.

    Audit #73 TIER B plot 5 — replan-count distribution.  Tests
    whether semantic's partition converges in fewer replans than
    uniform on the same scenes.  All cells included so the failure
    pile (typically at max_replans) is visible at the right edge.
    """
    if not HAVE_MPL:
        print(f"\n=== {title} (matplotlib not available) ===")
        for key, vs in sorted(grouped.items(), key=lambda kv: str(kv[0])):
            if not vs:
                continue
            print(f"  {key}: n={len(vs)}, "
                  f"min={min(vs)}, max={max(vs)}, "
                  f"mean={sum(vs) / len(vs):.2f}")
        return None

    keys = sorted(grouped.keys())
    if not keys:
        print(f"[plotter] no data for {title}")
        return None
    all_counts = [c for vs in grouped.values() for c in vs]
    if not all_counts:
        print(f"[plotter] no plan_count data for {title}")
        return None
    max_pc = max(all_counts)
    bins = list(range(0, max_pc + 2))  # integer bins [0, 1, ..., max+1]

    goals = sorted({g for g, _ in keys})
    baselines = sorted({b for _, b in keys})
    fig, axes = plt.subplots(
        len(goals), len(baselines),
        figsize=(4 * len(baselines), 3 * len(goals)),
        sharey=True, sharex=True, squeeze=False,
    )
    cmap = plt.get_cmap("tab10")
    for gi, goal in enumerate(goals):
        for bi, baseline in enumerate(baselines):
            ax = axes[gi][bi]
            vs = grouped.get((goal, baseline), [])
            if vs:
                ax.hist(vs, bins=bins, color=cmap(bi % 10),
                        alpha=0.75, edgecolor="black", linewidth=0.4,
                        label=f"n={len(vs)}, "
                              f"mean={sum(vs) / len(vs):.1f}")
                ax.legend(loc="upper right", fontsize=8)
            ax.set_title(f"{goal} / {baseline}")
            ax.grid(True, axis="y", alpha=0.3)
            if gi == len(goals) - 1:
                ax.set_xlabel("plan_count")
            if bi == 0:
                ax.set_ylabel("cell count")
    fig.suptitle(title)
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
            sd = stdev(samples) if len(samples) > 1 else 0.0
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
                        sd = stdev(samples) if len(samples) > 1 else 0.0
                        print(f"  {s_val} {tag}: mean={m:.3g} "
                              f"std={sd:.3g} n={len(samples)}")
        return None

    bars = []  # (label, mean, std, n)
    for s_val, xy in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        for samples in xy.values():
            if samples:
                bars.append((f"{s_val}{main_label_suffix}",
                             mean(samples),
                             stdev(samples) if len(samples) > 1 else 0.0,
                             len(samples)))
                break
    if baseline_grouped:
        for s_val, xy in sorted(baseline_grouped.items(),
                                 key=lambda kv: str(kv[0])):
            for samples in xy.values():
                if samples:
                    bars.append((f"{s_val}{baseline_label_suffix}",
                                 mean(samples),
                                 stdev(samples) if len(samples) > 1 else 0.0,
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
            stds = [stdev(xy[x]) if len(xy[x]) > 1 else 0.0 for x in xs]
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
        # Audit #73 TIER B plot 5: replan-count distribution per
        # (goal, baseline).  Sweep-level histogram; all cells included
        # so the failure pile at max_replans is visible.  Reads
        # plan_count from aggregated.csv — no schema change.
        plot_plan_count_distribution(
            group_plan_count_distribution(all_rows),
            title="Replan-count distribution by (goal, baseline)",
            out_path=out_dir / "plan_count_distribution.png",
        )
        # Audit #73 TIER C plot 9: TAMPURA wall-clock comparison
        # for find-and-tray-stack.  Sweep-level; no-op if the sweep
        # has no successful find-and-tray-stack cells.
        plot_tampura_wallclock_comparison(
            all_rows,
            title="TAMPURA wall-clock comparison (find-and-tray-stack)",
            out_path=out_dir / "tampura_wallclock_comparison.png",
        )
        # Audit #94 (#77 step 4): IPC-style anytime curve.  No-op if
        # the sweep does not vary min_boxel_size (SCALABILITY_VS_TIME).
        if _has_anytime_axis(all_rows):
            plot_solved_vs_time(
                group_solved_vs_time(all_rows),
                title="Cumulative solve rate vs wall-clock budget "
                      "(anytime / #77)",
                out_path=out_dir / "solved_vs_time.png",
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
        # Audit #73 TIER B plot 4: sense-action count vs n_occluders.
        # Counts every sense executed (any outcome) across all
        # replans, so include failed runs — they may still have done
        # many senses before exiting (the audit body explicitly notes
        # uniform vs semantic should show ~equal counts if the shadow
        # set is identical; a divergence is itself a finding).  No-op
        # on pre-#73-step-3(c) sweeps (n_sense_actions column absent).
        plot_metric(
            group_metric(g_rows, series=series_key,
                         metric="n_sense_actions",
                         success_only=False),
            title=f"Sense-action count vs scene size{title_suffix}",
            ylabel="mean n_sense_actions",
            out_path=out_dir / f"sense_action_count_vs_n_occluders{suffix}.png",
            baseline_grouped=(group_metric(g_baseline, series=series_key,
                                           metric="n_sense_actions",
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
        # Audit #73 TIER A plot 11: boxel-count evolution across replans.
        # Reads aggregated.jsonl (boxel_counts_per_replan is LIST_VALUED);
        # no-op on pre-#73-step-2(d) sweeps.
        plot_boxel_evolution_per_replan(
            group_boxel_evolution_per_replan(jsonl_rows, goal=goal),
            title=f"Boxel evolution across replans{title_suffix}",
            out_path=out_dir / f"boxel_evolution_per_replan{suffix}.png",
        )
        # Audit #73 TIER C plot 7: per-call planning time vs replan
        # index.  One line per baseline (semantic, uniform); reads
        # aggregated.jsonl (per_call_planning_time_s is LIST_VALUED).
        # No new data — run_logger already writes the list each run.
        plot_per_call_planning_time(
            group_per_call_planning_time(jsonl_rows, goal=goal),
            title=f"Per-call planning time vs replan index{title_suffix}",
            out_path=out_dir / f"per_call_planning_time{suffix}.png",
        )
        # Audit #73 TIER C plot 8: wall-clock vs total_planning_time
        # scatter, color by baseline, with y=x reference.  Both columns
        # are scalar in aggregated.csv (PRIMARY_COLUMNS); no schema
        # change.  Includes failed runs so the no_summary/planner_failed
        # clusters near X=0 are visible.
        plot_wallclock_vs_planning(
            group_wallclock_vs_planning(g_rows + (g_baseline or []),
                                         goal=goal),
            title=f"Wall-clock vs planning time{title_suffix}",
            out_path=out_dir / f"wallclock_vs_planning{suffix}.png",
        )
    # Audit #73 TIER B plot 6: failure-mode breakdown (sweep-level
    # stacked bar per (goal, baseline)).  Counts all cells including
    # successes so bar height = total cells per group.
    plot_failure_modes(
        group_failure_modes(all_rows),
        title="Failure-mode breakdown by (goal, baseline)",
        out_path=out_dir / "failure_modes.png",
    )
    # Audit #73 TIER B plot 5: replan-count distribution per
    # (goal, baseline).  Sweep-level histogram; all cells included
    # so the failure pile at max_replans is visible.  Reads
    # plan_count from aggregated.csv — no schema change.
    plot_plan_count_distribution(
        group_plan_count_distribution(all_rows),
        title="Replan-count distribution by (goal, baseline)",
        out_path=out_dir / "plan_count_distribution.png",
    )
    # Audit #73 TIER C plot 9: TAMPURA wall-clock comparison
    # for find-and-tray-stack.  Sweep-level; no-op if the sweep
    # has no successful find-and-tray-stack cells.
    plot_tampura_wallclock_comparison(
        all_rows,
        title="TAMPURA wall-clock comparison (find-and-tray-stack)",
        out_path=out_dir / "tampura_wallclock_comparison.png",
    )
    # Audit #94 (#77 step 4): IPC-style anytime curve.  No-op if the
    # sweep does not vary min_boxel_size (SCALABILITY_VS_TIME).
    if _has_anytime_axis(all_rows):
        plot_solved_vs_time(
            group_solved_vs_time(all_rows),
            title="Cumulative solve rate vs wall-clock budget "
                  "(anytime / #77)",
            out_path=out_dir / "solved_vs_time.png",
        )
    # Audit #73 — tabular summary alongside the plots (markdown +
    # 2 CSVs).  Aggregate by (goal, baseline) + per-occluder breakdown.
    write_summary_table(all_rows, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
