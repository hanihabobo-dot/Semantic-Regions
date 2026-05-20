#!/usr/bin/env python3
"""Preliminary aggregation + plots for the in-progress 'sweep_anytime' eval.

PARTIAL-DATA PREVIEW ONLY. The sweep is ~82% complete (stack/uniform never ran,
stack/semantic occ4 barely started). Numbers and plots here are provisional and
must be regenerated once the full sweep finishes. Outputs go to plots_preliminary/
so nothing existing is overwritten.

Run:  C:\\Python312\\python.exe eval_results\\sweep_anytime\\preview_plots.py
"""
import csv
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(HERE, "cells")
OUT = os.path.join(HERE, "plots_preliminary")
os.makedirs(OUT, exist_ok=True)

GOALS = ["holding", "find-and-tray-stack", "stack"]
VARIANTS = ["semantic", "semantic+mbs0.05", "uniform"]
VCOLOR = {"semantic": "#1f77b4", "semantic+mbs0.05": "#ff7f0e", "uniform": "#7f7f7f"}
EXIT_COLOR = {
    "success": "#2ca02c",
    "planner_failed": "#d62728",
    "timeout": "#7f0000",
    "replan_limit": "#ff7f0e",
    "no_summary": "#8c564b",
    "physics_mismatch": "#9467bd",
    "drop_failed": "#e377c2",
    "all_searched": "#17becf",
    "unknown": "#999999",
}


def variant_of(name):
    if name.endswith("_mbs0.05"):
        return "semantic+mbs0.05"
    if name.endswith("_uniform"):
        return "uniform"
    return "semantic"


def load():
    rows = []
    n_dirs = empty = bad = 0
    for d in sorted(os.listdir(CELLS)):
        cd = os.path.join(CELLS, d)
        if not os.path.isdir(cd):
            continue
        n_dirs += 1
        jp = os.path.join(cd, "timing_summary.json")
        if not os.path.isfile(jp):
            empty += 1
            continue
        try:
            with open(jp, encoding="utf-8") as f:
                j = json.load(f)
        except Exception as e:  # noqa: BLE001
            bad += 1
            print("  BAD JSON:", d, e)
            continue
        rc = j.get("run_config") or {}

        def get(k):
            return rc.get(k, j.get(k))

        obj, sh, fs = j.get("n_object_boxels"), j.get("n_shadow_boxels"), j.get("n_free_space_boxels")
        tot = (obj + sh + fs) if None not in (obj, sh, fs) else None
        rows.append(dict(
            cell=d, variant=variant_of(d), full_schema=bool(rc),
            goal=get("goal"), scene=get("scene"),
            n_occluders=get("n_occluders"), seed=get("seed"),
            success=bool(j.get("success")),
            exit_reason=(j.get("exit_reason") or ("success" if j.get("success") else "unknown")),
            plan_count=j.get("plan_count"), n_sense=j.get("n_sense_actions"),
            plan_time_s=j.get("total_planning_time_s"), wall_s=j.get("wall_clock_s"),
            n_object_boxels=obj, n_shadow_boxels=sh, n_free_space_boxels=fs, n_boxels=tot,
            n_init_state_facts=j.get("n_init_state_facts"),
        ))
    print(f"dirs={n_dirs}  parsed_json={len(rows)}  empty_dirs={empty}  bad_json={bad}")
    return rows


def grp(rows, v, g):
    return [r for r in rows if r["variant"] == v and r["goal"] == g]


def save(fig, name):
    fig.tight_layout()
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=130)
    plt.close(fig)
    print("  wrote", os.path.relpath(p, HERE))


def print_summary(rows):
    print("\n=== success rate by variant x goal (denominator = all parsed cells) ===")
    tot_s = tot_n = 0
    summary = []
    for g in GOALS:
        for v in VARIANTS:
            sub = grp(rows, v, g)
            if not sub:
                continue
            ns = sum(r["success"] for r in sub)
            tot_s += ns
            tot_n += len(sub)
            full = [r for r in sub if r["full_schema"]]
            pt = [r["plan_time_s"] for r in full if r["success"] and r["plan_time_s"] is not None]
            bx = [r["n_boxels"] for r in full if r["n_boxels"] is not None]
            fct = [r["n_init_state_facts"] for r in full if r["n_init_state_facts"] is not None]
            print(f"  {v:18s} {g:20s} n={len(sub):4d}  success={ns:4d}  "
                  f"rate={ns / len(sub) * 100:5.1f}%  "
                  f"plan_t_med={np.median(pt) if pt else float('nan'):8.2f}s  "
                  f"boxels_mean={np.mean(bx) if bx else float('nan'):7.1f}  "
                  f"facts_mean={np.mean(fct) if fct else float('nan'):8.1f}")
            summary.append(dict(
                variant=v, goal=g, n=len(sub), n_success=ns,
                success_rate_pct=round(ns / len(sub) * 100, 1),
                plan_time_median_s=round(float(np.median(pt)), 3) if pt else "",
                boxels_mean=round(float(np.mean(bx)), 1) if bx else "",
                facts_mean=round(float(np.mean(fct)), 1) if fct else "",
            ))
    print(f"  {'TOTAL':18s} {'':20s} n={tot_n:4d}  success={tot_s:4d}  rate={tot_s / tot_n * 100:5.1f}%")
    by_exit = {}
    for r in rows:
        by_exit[r["exit_reason"]] = by_exit.get(r["exit_reason"], 0) + 1
    print("\n=== exit_reason breakdown (all parsed cells) ===")
    for k, v in sorted(by_exit.items(), key=lambda kv: -kv[1]):
        print(f"  {k:18s} {v:5d}")
    return summary


def plot_success(rows):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(GOALS))
    w = 0.26
    for i, v in enumerate(VARIANTS):
        vals, ns = [], []
        for g in GOALS:
            sub = grp(rows, v, g)
            vals.append(sum(r["success"] for r in sub) / len(sub) * 100 if sub else 0.0)
            ns.append(len(sub))
        bars = ax.bar(x + (i - 1) * w, vals, w, label=v, color=VCOLOR[v])
        for b, val, n in zip(bars, vals, ns):
            if n:
                ax.text(b.get_x() + b.get_width() / 2, val + 1.5, f"{val:.0f}%\nn={n}",
                        ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(GOALS)
    ax.set_ylabel("success rate (%)")
    ax.set_ylim(0, 108)
    ax.set_title("Success rate by planner variant and goal\n"
                 "sweep_anytime (PARTIAL ~82%); denominator = all parsed cells incl. timeout/crash")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    save(fig, "success_rate_by_variant_goal.png")


def plot_plan_time(rows):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(GOALS))
    w = 0.26
    for i, v in enumerate(VARIANTS):
        med, lo, hi, ns = [], [], [], []
        for g in GOALS:
            vals = [r["plan_time_s"] for r in grp(rows, v, g)
                    if r["success"] and r["plan_time_s"] is not None]
            if vals:
                a = np.array(vals, dtype=float)
                m = float(np.median(a))
                med.append(m)
                lo.append(m - float(np.percentile(a, 25)))
                hi.append(float(np.percentile(a, 75)) - m)
                ns.append(len(vals))
            else:
                med.append(np.nan)
                lo.append(0.0)
                hi.append(0.0)
                ns.append(0)
        xs = x + (i - 1) * w
        ax.bar(xs, med, w, yerr=[lo, hi], capsize=3, label=v, color=VCOLOR[v])
        for xi, m, n in zip(xs, med, ns):
            if n:
                ax.text(xi, m, f" n={n}", ha="center", va="bottom", fontsize=7, rotation=90)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(GOALS)
    ax.set_ylabel("planning time to solution (s, log) — median, IQR whiskers")
    ax.set_title("Planning time of SUCCESSFUL runs, by variant and goal\nsweep_anytime (PARTIAL ~82%)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    save(fig, "planning_time_by_variant_goal.png")


def plot_boxels(rows):
    labels, objs, shs, fss = [], [], [], []
    for g in GOALS:
        for v in VARIANTS:
            sub = [r for r in grp(rows, v, g)
                   if r["full_schema"] and r["n_object_boxels"] is not None]
            if not sub:
                continue
            labels.append(f"{g}\n{v}")
            objs.append(np.mean([r["n_object_boxels"] for r in sub]))
            shs.append(np.mean([r["n_shadow_boxels"] for r in sub]))
            fss.append(np.mean([r["n_free_space_boxels"] for r in sub]))
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(labels))
    objs, shs, fss = np.array(objs), np.array(shs), np.array(fss)
    ax.bar(x, objs, label="object boxels", color="#d62728")
    ax.bar(x, shs, bottom=objs, label="shadow boxels", color="#9467bd")
    ax.bar(x, fss, bottom=objs + shs, label="free-space boxels", color="#2ca02c")
    for xi, tot in zip(x, objs + shs + fss):
        ax.text(xi, tot + 4, f"{tot:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("mean boxel count")
    ax.set_title("Boxel-set size by type — semantic partition vs uniform grid\n"
                 "sweep_anytime (PARTIAL ~82%); full-schema cells only")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    save(fig, "boxel_count_breakdown.png")


def plot_facts(rows):
    labels, means = [], []
    colors = []
    for g in GOALS:
        for v in VARIANTS:
            sub = [r["n_init_state_facts"] for r in grp(rows, v, g)
                   if r["full_schema"] and r["n_init_state_facts"] is not None]
            if not sub:
                continue
            labels.append(f"{g}\n{v}")
            means.append(np.mean(sub))
            colors.append(VCOLOR[v])
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(labels))
    bars = ax.bar(x, means, color=colors)
    for b, m in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, m, f"{m:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("mean PDDL init-state fact count")
    ax.set_title("Init-state fact count — semantic partition vs uniform grid\n"
                 "sweep_anytime (PARTIAL ~82%); full-schema cells only")
    ax.grid(axis="y", alpha=0.3)
    save(fig, "init_state_facts_by_variant_goal.png")


def plot_failure_modes(rows):
    cols = [(g, v) for g in GOALS for v in VARIANTS if grp(rows, v, g)]
    reasons = ["success", "planner_failed", "replan_limit", "timeout",
               "no_summary", "physics_mismatch", "drop_failed", "all_searched", "unknown"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(cols))
    bottom = np.zeros(len(cols))
    for reason in reasons:
        counts = []
        for g, v in cols:
            sub = grp(rows, v, g)
            counts.append(sum(1 for r in sub if r["exit_reason"] == reason))
        counts = np.array(counts, dtype=float)
        if counts.sum() == 0:
            continue
        ax.bar(x, counts, bottom=bottom, label=reason, color=EXIT_COLOR.get(reason, "#999999"))
        bottom += counts
    ax.set_xticks(x)
    ax.set_xticklabels([f"{g}\n{v}" for g, v in cols], fontsize=7)
    ax.set_ylabel("cell count")
    ax.set_title("Outcome / failure-mode breakdown by variant and goal\nsweep_anytime (PARTIAL ~82%)")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "failure_modes.png")


def plot_anytime(rows):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, g in zip(axes, GOALS):
        for v in VARIANTS:
            sub = grp(rows, v, g)
            if not sub:
                continue
            n_total = len(sub)
            solved = sorted(r["wall_s"] for r in sub if r["success"] and r["wall_s"] is not None)
            if not solved:
                ax.plot([], [], color=VCOLOR[v], label=f"{v} (0/{n_total})")
                continue
            ys = [(i + 1) / n_total * 100 for i in range(len(solved))]
            ax.step([solved[0]] + solved, [0] + ys, where="post",
                    color=VCOLOR[v], label=f"{v} ({len(solved)}/{n_total})")
        ax.set_xscale("log")
        ax.set_xlabel("wall-clock budget (s, log)")
        ax.set_title(g)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="lower right")
    axes[0].set_ylabel("instances solved (%)")
    axes[0].set_ylim(0, 100)
    fig.suptitle("Anytime curves — cumulative solve rate vs wall-clock budget — "
                 "sweep_anytime (PARTIAL ~82%)")
    save(fig, "anytime_curves.png")


def write_csvs(rows, summary):
    per_cell = os.path.join(OUT, "preliminary_per_cell.csv")
    with open(per_cell, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("  wrote", os.path.relpath(per_cell, HERE))
    summ = os.path.join(OUT, "preliminary_summary.csv")
    with open(summ, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print("  wrote", os.path.relpath(summ, HERE))


def main():
    rows = load()
    if not rows:
        print("no data")
        return
    summary = print_summary(rows)
    print("\n=== plots ===")
    plot_success(rows)
    plot_plan_time(rows)
    plot_boxels(rows)
    plot_facts(rows)
    plot_failure_modes(rows)
    plot_anytime(rows)
    write_csvs(rows, summary)
    print("\ndone -> plots_preliminary/")


if __name__ == "__main__":
    main()
