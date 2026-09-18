#!/usr/bin/env python3
"""Prune old run directories under logs/ (user policy 2026-09-18).

Debug output per run is deliberately generous (run log, telemetry,
world-eye snapshots: a few MB).  Keep it, but not forever: for every ISO
week older than --older-than-days, keep the newest --keep-per-week runs
and delete the rest.  Runs younger than the threshold are never touched.
Dry-run by default; --apply deletes.

  wsl_env/bin/python tools/prune_runs.py                 # show what would go
  wsl_env/bin/python tools/prune_runs.py --apply
  wsl_env/bin/python tools/prune_runs.py --keep-per-week 2 --older-than-days 14
  wsl_env/bin/python tools/prune_runs.py --protect 2026-09-18_17-02-11 --protect 13-25-19

--protect keeps any run whose name contains the fragment (e.g. runs cited
in PAPER_AUDIT.txt).  Runs referenced by name inside PAPER_AUDIT.txt are
protected automatically.
"""
import argparse
import datetime as dt
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
RUN_RE = re.compile(r"^run_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})$")


def audit_protected():
    path = os.path.join(ROOT, "PAPER_AUDIT.txt")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    frags = set(re.findall(r"run[_ ](\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", text))
    frags |= set(re.findall(r"\brun (\d{2}-\d{2}-\d{2})\b", text))
    return frags


def dir_size(path):
    total = 0
    for dp, _, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep-per-week", type=int, default=2)
    ap.add_argument("--older-than-days", type=int, default=14)
    ap.add_argument("--protect", action="append", default=[],
                    help="name fragment to keep (repeatable)")
    ap.add_argument("--apply", action="store_true", help="actually delete")
    args = ap.parse_args()

    protect = set(args.protect) | audit_protected()
    now = dt.datetime.now()
    cutoff = now - dt.timedelta(days=args.older_than_days)
    runs = []
    for name in sorted(os.listdir(LOGS)) if os.path.isdir(LOGS) else []:
        m = RUN_RE.match(name)
        if not m:
            continue
        stamp = dt.datetime.strptime(m.group(1) + "_" + m.group(2), "%Y-%m-%d_%H-%M-%S")
        runs.append((stamp, name))
    by_week = {}
    for stamp, name in runs:
        by_week.setdefault(stamp.isocalendar()[:2], []).append((stamp, name))

    to_delete, kept, freed = [], [], 0
    for week, items in sorted(by_week.items()):
        items.sort(reverse=True)  # newest first
        keep_n = 0
        for stamp, name in items:
            path = os.path.join(LOGS, name)
            protected = any(frag in name for frag in protect)
            if stamp >= cutoff or protected or keep_n < args.keep_per_week:
                kept.append(name)
                if stamp < cutoff and not protected:
                    keep_n += 1
                continue
            to_delete.append((name, dir_size(path)))
    for name, size in to_delete:
        freed += size
        print(f"{'DELETE' if args.apply else 'would delete'}  {name}  ({size / 1e6:.1f} MB)")
        if args.apply:
            shutil.rmtree(os.path.join(LOGS, name), ignore_errors=True)
    print(f"\n{len(runs)} run(s): keep {len(kept)}, "
          f"{'deleted' if args.apply else 'would delete'} {len(to_delete)} "
          f"({freed / 1e6:.1f} MB); protected fragments: {sorted(protect) or 'none'}")
    if not args.apply and to_delete:
        print("dry run — add --apply to delete")


if __name__ == "__main__":
    main()
