#!/usr/bin/env python3
"""Inspect a run's world-eye snapshots (eye.jsonl written by world_eye.py).

Pick a moment and see where every object really was, where the robot
believed it was, what the camera saw, and what the belief / planner init
said — without a GUI.

  wsl_env/bin/python tools/eye.py logs/run_2026-09-18_17-02-11 --list
  wsl_env/bin/python tools/eye.py logs/<run> --index 7
  wsl_env/bin/python tools/eye.py logs/<run> --plan 3          # first snapshot of plan 3
  wsl_env/bin/python tools/eye.py logs/<run> --step 4030       # nearest sim step
  wsl_env/bin/python tools/eye.py logs/<run> --wall 42.5       # nearest wall-clock second
  wsl_env/bin/python tools/eye.py logs/<run> --tag "sense"     # every snapshot whose tag contains it
  wsl_env/bin/python tools/eye.py logs/<run> --diff 3 9        # what moved / changed between two
  wsl_env/bin/python tools/eye.py logs/<run> --audit           # redundant relocations, placements
                                                               # that hid a body, who hides whom,
                                                               # which bodies the planner ever had
                                                               # a reason to move
  add --no-view / --no-facts / --free to trim or extend the block; --all dumps everything.

Give the run directory, or just a timestamp fragment ("17-02-11") to find
it under logs/.
"""
import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from world_eye import render_snapshot  # noqa: E402


def resolve_run(arg):
    if os.path.isdir(arg):
        return arg
    hits = sorted(glob.glob(os.path.join(ROOT, "logs", f"*{arg}*")))
    if not hits:
        sys.exit(f"no run directory matches '{arg}'")
    return hits[-1]


def load(run_dir):
    path = os.path.join(run_dir, "eye.jsonl")
    if not os.path.exists(path):
        sys.exit(f"{path} not found (run predates world_eye, or the eye was off)")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def one_line(r):
    objs = " ".join(
        f"{o['name']}@({o['true_pos'][0]:.2f},{o['true_pos'][1]:.2f})"
        + ("" if o.get("believed_aabb") is not None else "[NO BOXEL]")
        for o in r.get("objects", []))
    b = r.get("belief") or {}
    img = " [img]" if r.get("images") else ""
    return (f"#{r['k']:<3} plan={str(r.get('plan')):<4} wall={r.get('t_wall'):>7}s "
            f"step={str(r.get('sim_step')):<6} held={r.get('held') or '-':<12} "
            f"unknown={len(b.get('unknown', [])) if b else '-':<3} {r['tag']:<48}{img} {objs}")


def nearest(recs, key, value):
    best, bd = None, None
    for r in recs:
        v = r.get(key)
        if v is None:
            continue
        d = abs(float(v) - float(value))
        if bd is None or d < bd:
            best, bd = r, d
    return best


def diff(a, b):
    out = [f"diff eye #{a['k']} ({a['tag']}) -> #{b['k']} ({b['tag']})"]
    oa = {o["name"]: o for o in a.get("objects", [])}
    ob = {o["name"]: o for o in b.get("objects", [])}
    for name in sorted(set(oa) | set(ob)):
        x, y = oa.get(name), ob.get(name)
        if x is None or y is None:
            out.append(f"  {name}: {'appeared' if x is None else 'vanished'}")
            continue
        dx = [y["true_pos"][i] - x["true_pos"][i] for i in range(3)]
        moved = (sum(d * d for d in dx)) ** 0.5 * 1000.0
        reg = ("registered" if x.get("believed_aabb") is None
               and y.get("believed_aabb") is not None else
               "UNREGISTERED" if x.get("believed_aabb") is not None
               and y.get("believed_aabb") is None else "")
        if moved > 5.0 or reg:
            out.append(f"  {name}: moved {moved:.0f} mm "
                       f"({x['true_pos'][0]:.3f},{x['true_pos'][1]:.3f},{x['true_pos'][2]:.3f}) -> "
                       f"({y['true_pos'][0]:.3f},{y['true_pos'][1]:.3f},{y['true_pos'][2]:.3f}) {reg}")
    sa = {s["id"]: s for s in a.get("shadows", [])}
    sb = {s["id"]: s for s in b.get("shadows", [])}
    for sid in sorted(set(sa) | set(sb)):
        if sid not in sb:
            out.append(f"  shadow {sid}: removed (was {sa[sid].get('status')})")
        elif sid not in sa:
            out.append(f"  shadow {sid}: created ({sb[sid].get('status')})")
        elif sa[sid].get("status") != sb[sid].get("status"):
            out.append(f"  shadow {sid}: {sa[sid].get('status')} -> {sb[sid].get('status')}")
    ba, bb = a.get("belief") or {}, b.get("belief") or {}
    if ba.get("target_found_in") != bb.get("target_found_in"):
        out.append(f"  target_found_in: {ba.get('target_found_in')} -> {bb.get('target_found_in')}")
    if a.get("held") != b.get("held"):
        out.append(f"  held: {a.get('held')} -> {b.get('held')}")
    return "\n".join(out)


def _action_obj(action_str):
    """'place red_object free_005' -> ('place', 'red_object', 'free_005')."""
    parts = action_str.split()
    return (parts[0], parts[1] if len(parts) > 1 else None,
            parts[2] if len(parts) > 2 else None)


def audit(recs):
    """Derived judgements a reader would otherwise have to script:
    placements that hid other bodies, plans that shuffle one object twice,
    bodies the planner never had a reason to move, and who hides whom."""
    out = []
    rendered = [r for r in recs if any("visible_px" in o for o in r.get("objects", []))]

    # 1. Redundant plan actions: the same object placed/stacked twice in
    #    one plan, or picked from where it was just put down.
    out.append("== plans with a redundant relocation ==")
    hit = False
    for r in recs:
        acts = r.get("plan_actions") or []
        placed = {}
        for a in acts:
            verb, obj, dest = _action_obj(a)
            if verb in ("place", "place_hiding", "stack") and obj:
                placed.setdefault(obj, []).append(dest)
        for obj, dests in placed.items():
            if len(dests) > 1:
                hit = True
                out.append(f"  #{r['k']} {r['tag']}: {obj} is put down {len(dests)} times "
                           f"({' -> '.join(str(d) for d in dests)}) in one plan "
                           f"— only the last placement can matter to the goal")
    if not hit:
        out.append("  none")

    # 2. Placements that hid something: compare the last render before a
    #    place/stack with the first render after it.
    out.append("== placements that changed what the camera sees ==")
    hit = False
    for i, r in enumerate(recs):
        tag = r.get("tag", "")
        if "before action" not in tag or not (" place(" in tag or " place_hiding(" in tag
                                              or " stack(" in tag):
            continue
        verb = ("place" if " place(" in tag
                else "place_hiding" if " place_hiding(" in tag else "stack")
        inner = tag.split(f" {verb}(", 1)[1].rstrip(")")
        obj = inner.split(",")[0].strip()
        dest = inner.split(",")[1].strip() if "," in inner else "?"
        before = next((x for x in reversed(recs[:i]) if x in rendered), None)
        after = next((x for x in recs[i + 1:] if x in rendered), None)
        if before is None or after is None:
            continue
        pb = {o["name"]: o for o in before["objects"]}
        pa = {o["name"]: o for o in after["objects"]}
        for name, oa in pa.items():
            if name == obj:
                continue
            ob = pb.get(name)
            if ob is None:
                continue
            b_px, a_px = ob.get("visible_px"), oa.get("visible_px")
            hb = oa.get("hidden_by")
            if b_px is None or a_px is None:
                continue
            if (b_px > 0 and a_px < 0.6 * b_px) or (hb == obj):
                hit = True
                role = oa.get("role", "?")
                out.append(f"  #{r['k']} {verb}({obj} -> {dest}): {name} ({role}) "
                           f"went from {b_px} px to {a_px} px"
                           + (f", camera now sees {hb} at its centre" if hb else "")
                           + (f"  [seen at #{after['k']}]"))
    if not hit:
        out.append("  none detected (needs a render before and after the placement)")

    # 3. Who hides whom, per rendered snapshot.
    out.append("== hidden-by (per observation) ==")
    for r in rendered:
        hs = [f"{o['name']} by {o['hidden_by']}" for o in r["objects"] if o.get("hidden_by")]
        px = " ".join(f"{o['name'][:6]}={o.get('visible_px')}" for o in r["objects"])
        out.append(f"  #{r['k']:<3} {r['tag'][:44]:<44} {px}"
                   + (f"  | HIDDEN: {'; '.join(hs)}" if hs else ""))

    # 4. Per object: was it ever a blocker of an unknown fragment, ever in
    #    a plan, ever moved?  A body that never blocked anything gave the
    #    planner no reason to relocate it; a body that DID block an unknown
    #    fragment and still never entered a plan is the search never
    #    getting to that branch (equal-cost tie-breaks, then an F7
    #    binding death before the next replan could pick it).
    out.append("== per-object planner relevance ==")
    names = sorted({o["name"] for r in recs for o in r.get("objects", [])})
    never_planned_blockers = []
    for n in names:
        blocked = set()
        for r in recs:
            for s in r.get("shadows", []):
                if s.get("status") == "unknown" and n in (s.get("blockers") or []):
                    blocked.add(s["id"])
        in_plans = sum(1 for r in recs if any(n in a for a in (r.get("plan_actions") or [])))
        moved = any(n in (r.get("belief") or {}).get("occluders_moved", {}) for r in recs)
        registered_at = next((r["k"] for r in recs
                              if any(o["name"] == n and o.get("believed_aabb") is not None
                                     for o in r.get("objects", []))), None)
        roles = {o.get("role") for r in recs for o in r.get("objects", []) if o["name"] == n}
        out.append(f"  {n:<15} role={'/'.join(sorted(x for x in roles if x)):<9} "
                   f"registered_at=#{registered_at} moved={moved} in_plans={in_plans} "
                   f"blocker_of_unknown={sorted(blocked) or 'never'}")
        if blocked and in_plans == 0:
            never_planned_blockers.append((n, sorted(blocked)))
    out.append("== blockers of unknown fragments that never entered a plan ==")
    if never_planned_blockers:
        last = recs[-1]
        still = {s["id"] for s in last.get("shadows", []) if s.get("status") == "unknown"}
        for n, frags in never_planned_blockers:
            open_frags = [f for f in frags if f in still]
            out.append(f"  {n}: blocked {frags}; still unknown at the end: "
                       f"{open_frags or 'none'} — the planner never planned to "
                       f"relocate it (equal-cost alternatives were tried first, "
                       f"or the run ended before its turn)")
    else:
        out.append("  none")
    out.append("== images ==")
    imgs = [(r["k"], r["tag"], r.get("images")) for r in recs if r.get("images")]
    if imgs:
        for k, tag, names_ in imgs:
            out.append(f"  #{k:<3} {tag[:50]:<50} {', '.join(names_)}")
    else:
        out.append("  none (run predates image saving)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="run directory or a fragment of its timestamp")
    ap.add_argument("--list", action="store_true", help="one line per snapshot")
    ap.add_argument("--audit", action="store_true",
                    help="derived judgements: redundant relocations, placements that hid "
                         "other bodies, who hides whom, per-object planner relevance")
    ap.add_argument("--all", action="store_true", help="dump every snapshot in full")
    ap.add_argument("--index", type=int, help="snapshot number (the #k)")
    ap.add_argument("--plan", type=int, help="first snapshot of this plan")
    ap.add_argument("--step", type=int, help="nearest simulation step")
    ap.add_argument("--wall", type=float, help="nearest wall-clock second since the eye opened")
    ap.add_argument("--tag", help="every snapshot whose tag contains this text")
    ap.add_argument("--diff", nargs=2, type=int, metavar=("A", "B"),
                    help="what changed between snapshots #A and #B")
    ap.add_argument("--no-view", action="store_true")
    ap.add_argument("--no-facts", action="store_true")
    ap.add_argument("--free", action="store_true", help="also list free cells")
    args = ap.parse_args()

    run_dir = resolve_run(args.run)
    recs = load(run_dir)
    print(f"{run_dir}: {len(recs)} snapshot(s)")
    if args.audit:
        print(audit(recs))
        return
    if args.list or not any([args.all, args.index, args.plan, args.step is not None,
                             args.wall is not None, args.tag, args.diff]):
        for r in recs:
            print(one_line(r))
        return
    kw = dict(view=not args.no_view, facts=not args.no_facts, free=args.free)
    if args.diff:
        by = {r["k"]: r for r in recs}
        print(diff(by[args.diff[0]], by[args.diff[1]]))
        return
    chosen = []
    if args.all:
        chosen = recs
    elif args.index is not None:
        chosen = [r for r in recs if r["k"] == args.index]
    elif args.plan is not None:
        chosen = [r for r in recs if r.get("plan") == args.plan][:1]
    elif args.step is not None:
        chosen = [nearest(recs, "sim_step", args.step)]
    elif args.wall is not None:
        chosen = [nearest(recs, "t_wall", args.wall)]
    elif args.tag:
        chosen = [r for r in recs if args.tag.lower() in r["tag"].lower()]
    chosen = [c for c in chosen if c is not None]
    if not chosen:
        sys.exit("no snapshot matches")
    for r in chosen:
        print(render_snapshot(r, **kw))
        print()


if __name__ == "__main__":
    main()
