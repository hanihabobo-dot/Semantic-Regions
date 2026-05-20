"""One-off parse of aggregated.csv for #93 refresh — full-sweep numbers."""
import csv
from collections import defaultdict

rows = list(csv.DictReader(open("eval_results/sweep_anytime/aggregated.csv")))
print(f"total rows: {len(rows)}")

g = defaultdict(lambda: {"n": 0, "succ": 0, "times": [],
                          "boxels": [], "facts": []})
for r in rows:
    if r["baseline"] == "uniform":
        arm = "uniform"
    else:
        mbs = r.get("min_boxel_size", "") or ""
        arm = "semantic+mbs0.05" if mbs == "0.05" else "semantic"
    key = (r["goal"], arm)
    g[key]["n"] += 1
    if r["success"].lower() == "true":
        g[key]["succ"] += 1
        try:
            g[key]["times"].append(float(r["total_planning_time_s"]))
        except Exception:
            pass
    try:
        nb = int(r.get("n_object_boxels", "") or "0")
        ns = int(r.get("n_shadow_boxels", "") or "0")
        nf = int(r.get("n_free_space_boxels", "") or "0")
        g[key]["boxels"].append(nb + ns + nf)
    except Exception:
        pass
    try:
        g[key]["facts"].append(int(r.get("n_init_state_facts", "0") or "0"))
    except Exception:
        pass


def median(xs):
    return sorted(xs)[len(xs) // 2] if xs else None


print(f"{'goal':24s} | {'arm':18s} | {'success':>10s} | {'rate':>6s} | "
      f"{'med plan':>10s} | {'med boxels':>10s} | {'med facts':>10s}")
print("-" * 95)
for goal in ["holding", "find-and-tray-stack", "stack"]:
    for arm in ["semantic", "semantic+mbs0.05", "uniform"]:
        v = g.get((goal, arm))
        if not v:
            continue
        rate = 100.0 * v["succ"] / v["n"] if v["n"] else 0
        mp = median(v["times"])
        mp_s = f"{mp:.2f}s" if mp is not None else "-"
        mb = median(v["boxels"]) or 0
        mf = median(v["facts"]) or 0
        print(f"{goal:24s} | {arm:18s} | "
              f"{v['succ']:3d}/{v['n']:3d}    | {rate:5.1f}% | "
              f"{mp_s:>10s} | {mb:10d} | {mf:10d}")

# Exit-reason failure breakdown
print()
print("Exit-reason counts:")
exit_counts = defaultdict(int)
for r in rows:
    exit_counts[r.get("exit_reason", "") or "(none)"] += 1
for reason, n in sorted(exit_counts.items(), key=lambda kv: -kv[1]):
    print(f"  {reason:20s}: {n}")
