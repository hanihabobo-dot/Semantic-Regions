"""Audit #98: summarise the coarse-end resolution sweep.

Per (goal, min_boxel_size) success rate + median plan time + median
boxel/fact counts, so the resolution-vs-success curve above auto_cell
can be read against the #93 auto_cell baseline.
"""
import csv
from collections import defaultdict

CSV = ("eval_results/sweep_2026-05-20_13-38-28_scalability-vs-resolution/"
       "aggregated.csv")
rows = list(csv.DictReader(open(CSV)))
print(f"total rows: {len(rows)}")

g = defaultdict(lambda: {"n": 0, "succ": 0, "t": [], "box": [], "fact": []})
for r in rows:
    mbs = r.get("min_boxel_size", "") or "?"
    key = (r["goal"], mbs)
    g[key]["n"] += 1
    if r["success"].lower() == "true":
        g[key]["succ"] += 1
        try:
            g[key]["t"].append(float(r["total_planning_time_s"]))
        except Exception:
            pass
    try:
        nb = int(r.get("n_object_boxels", "") or 0)
        ns = int(r.get("n_shadow_boxels", "") or 0)
        nf = int(r.get("n_free_space_boxels", "") or 0)
        g[key]["box"].append(nb + ns + nf)
    except Exception:
        pass
    try:
        g[key]["fact"].append(int(r.get("n_init_state_facts", "") or 0))
    except Exception:
        pass


def med(xs):
    return sorted(xs)[len(xs) // 2] if xs else None


# auto_cell baseline from #93 (the SCALABILITY_VS_TIME min_boxel_size=None arm)
BASELINE = {
    "holding": (42.3, "auto~9cm"),
    "find-and-tray-stack": (39.8, "auto~9cm"),
    "stack": (61.3, "auto~6cm"),
}

print(f"\n{'goal':22s} | {'mbs (m)':8s} | {'success':>9s} | {'rate':>6s} | "
      f"{'med plan':>9s} | {'med box':>7s} | {'med facts':>9s}")
print("-" * 86)
for goal in ["holding", "find-and-tray-stack", "stack"]:
    base_rate, base_label = BASELINE[goal]
    print(f"{goal:22s} | {base_label:8s} | {'(#93)':>9s} | "
          f"{base_rate:5.1f}% |    (auto) |       — |         —")
    keys = sorted(k for k in g if k[0] == goal)
    for (_, mbs) in keys:
        v = g[(goal, mbs)]
        rate = 100.0 * v["succ"] / v["n"] if v["n"] else 0
        mt = med(v["t"])
        mt_s = f"{mt:.2f}s" if mt is not None else "-"
        print(f"{goal:22s} | {mbs:8s} | {v['succ']:3d}/{v['n']:<4d} | "
              f"{rate:5.1f}% | {mt_s:>9s} | {med(v['box']) or 0:7d} | "
              f"{med(v['fact']) or 0:9d}")
    print()
