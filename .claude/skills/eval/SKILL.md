---
name: eval
description: Seed-for-seed A/B evaluation of the Semantic Boxels pipeline between the CURRENT code state and one or more past git states (session start, pre-paper baseline, experiment branches, or any user-named ref). Use when the user says "eval", "run the eval", "compare against before", "did my changes regress", "A/B this", or after a batch of changes lands and they want numbers. Suggests relevant comparison points first, then runs serialized headless episodes per arm and reports success rate, planning time, per-seed diffs, and follow-up suggestions.
---

# /eval — pipeline A/B between code states

Compare how the pipeline performs NOW versus one or more earlier git states,
seed-for-seed, and turn the diff into a ranked list of suggestions.  Modeled on
the F6 sense-gate A/B of 2026-08-22 (six arms; method and results recorded in
PAPER_AUDIT.txt under F6, raw data in `eval_results/ab_sensable_2026-08-22/`).

## Argument (optional)

Free text naming the comparison target(s) and/or eval shape, e.g.
`/eval vs session start`, `/eval vs 4b3aaca seeds 100-119`,
`/eval stack goal vs pre-paper`.  With no argument: suggest points (step 2).

## Hard safety rules (this machine, this repo)

- PowerShell tool only; NEVER the Bash tool or Monitor (both hit MSYS2 bash).
  WSL via `wsl -e bash -c '...'`.  git ALWAYS foreground (hook-enforced).
- `wsl -e bash -c 'pgrep -af test_full_pipeline'` before ANY run — the user
  launches GUI runs spontaneously; never two pipeline processes (pddlstream
  temp/ race).  While arms run, tell the user not to start GUI runs.
- Long runs = tool-managed background commands (`run_in_background: true`,
  they survive past the 10-min timeout).  NEVER nohup-detach inside WSL: the
  WSL instance idle-terminates between tool calls and kills the process.
- NO git worktrees (user directive).  Arms run by checking out refs in the
  MAIN checkout, sequentially.
- Before any checkout: `git status --porcelain`, confirm no TRACKED *code*
  file is dirty (the user's standing thesis/notes/viewer entries are fine —
  they never collide with code checkouts).  Dirty code -> stop and ask.
- Record `git branch --show-current` FIRST and always return to it at the
  end, including on failure.  Old refs check out DETACHED — that is fine.

## Steps

### 1. State check

`git branch --show-current`, `git log --oneline -8`, dirty-tracked-files
check, pgrep.  Record the branch to restore.

### 2. Choose comparison points — suggest, then confirm

Arm 0 is always the current HEAD.  Compute these candidates, present them
with hash + one-line rationale, and let the user pick (default: session
start; skip the dialog when the argument already names refs):

- **Session start** — the code before the user's current work session:
  newest commit older than the session's first change.  Heuristic:
  `git log --oneline --before="<today 00:00>" -1` (adjust if the user says
  when the session started).  The default and usually most relevant point.
- **Pre-paper baseline** — the code before ICAPS-paper preparation began:
  the parent of the commit that created PAPER_AUDIT.txt
  (`git log --diff-filter=A --format=%h -- PAPER_AUDIT.txt` -> `<sha>^`),
  and/or the branch fork `git merge-base HEAD main`.  The user wants this
  offered EVERY time.  CAVEAT to state whenever it is used: it crosses the
  oracle/weld boundary (pre-#P1 the pipeline used ground-truth detection
  and weld grasps) AND the spawn-spacing change (f6c00eb) — same seed means
  a different scene, and the numbers measure TOTAL SYSTEM DRIFT, not a
  like-for-like regression.
- **Experiment branches / notable commits** relevant to the question — read
  PAPER_AUDIT.txt's open findings for candidates.  Standing examples:
  `p1-sensable-gate` strict gate = 4b3aaca, necessary-only variant =
  90df94a (F6, parked as the LAST work item); F11 honest-margin variant =
  335ddc1 (reverted).
- **Any user-named ref.**

### 3. Harness

Use `tools/_eval_ab.py` (UNTRACKED on purpose — a tracked harness would be
deleted by `git checkout <old-sha>` mid-eval).  If missing, regenerate it
from the listing at the bottom of this skill.  Usage:

    wsl -e bash -c 'cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels &&
      wsl_env/bin/python tools/_eval_ab.py --tag <arm> [--seeds 0-19]
      [--scene random-pairs] [--goal holding] [--pipeline-args "--seed-retry"]'

Resumable per tag (incremental JSON in `eval_results/ab_eval/`); a killed
arm continues where it stopped.  Default shape: 20 seeds, holding,
random-pairs — the search-heavy goal where planning changes show.  Use
FRESH seeds (e.g. 100-119) when the change being tested was itself tuned on
0-19.  Name tags `<what>_<shortsha>`.

### 4. Run the arms, sequentially

For each arm: checkout the ref (foreground git; arm 0 needs no checkout),
`py_compile` the key modules as a sanity check, then run the harness as a
tool-managed background command and wait on it.  Two ref-specific checks:

- **Flag drift**: old refs may not support current CLI flags
  (`--seed-retry` only exists since 2026-08-21).  Check the ref's argparse
  (`git show <ref>:run_logger.py` or where the parser lives) and trim
  `--pipeline-args` accordingly.
- **Parse drift**: after the FIRST episode of each arm, confirm
  `plans_executed` and `planning_time_s` parsed non-null; if the ref's
  console format differs, adapt the harness regexes before burning the arm.

Restore the original branch afterwards.

### 5. Report

A compact table (success x/N, mean and median planning time, mean
plans/episode, re-rolls, timeouts) plus a seed-for-seed diff that NAMES the
seeds that flipped in either direction with their failure reasons.  Then a
**Suggestions** list — the deliverable the user asked this skill for:

- For each regressed seed: classify from the logs (planning no-plan vs
  physical failure vs timeout; logs live in `logs/run_<timestamp>/`) and
  propose the next diagnostic or fix, referencing open audit findings when
  the signature matches (F7 silent binding death, F10 held-cargo sweep,
  physical giveups...).
- For improvements: name which landed change plausibly earned them.
- Statistical honesty, always stated: at n=20 a difference of +-2-3 seeds
  is NOISE (measured 2026-08-22: six same-quality configs spread 11-17/20);
  trajectories are tie-break-sensitive (mm-level geometry and wall-clock
  budgets flip equal-cost plans), so judge mechanism over headline; time
  comparisons need arms run back-to-back on an otherwise idle machine.
- If the verdict would change a decision (merge/revert/land), recommend a
  fresh-seed confirmation arm before acting.

### 6. Bookkeeping (repo policy)

Any NEW finding the eval surfaces gets appended to PAPER_AUDIT.txt the same
session; evals that inform an open finding get a dated note under it.
Commit audit edits individually, push BOTH remotes (origin + github).
Leave the raw JSONs in `eval_results/` untracked unless the user says
otherwise; never overwrite a previous eval's files (new out-dir or tags).

## Harness listing (regenerate tools/_eval_ab.py from this if missing)

```python
#!/usr/bin/env python3
"""Generalized A/B eval harness for the Semantic Boxels pipeline.

Runs headless episodes on a fixed seed list, SERIALIZED (one pipeline
process at a time - pddlstream temp/ race), parses each episode's console
output, and writes one incrementally-persisted, resumable JSON per arm.

DELIBERATELY UNTRACKED (underscore name): a tracked harness would be
deleted by `git checkout <old-sha>` mid-eval.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_seeds(spec):
    seeds = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def run_episode(seed, args):
    cmd = [sys.executable, os.path.join(ROOT, "test_full_pipeline.py"),
           "--no-gui", "--scene", args.scene,
           "--seed", str(seed), "--goal", args.goal]
    cmd += args.pipeline_args.split()
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                              timeout=args.timeout)
        timed_out = False
        rc = proc.returncode
        out = proc.stdout.decode("utf-8", errors="replace") \
            + proc.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        timed_out = True
        rc = None
        out = ((e.stdout or b"").decode("utf-8", errors="replace")
               + (e.stderr or b"").decode("utf-8", errors="replace"))
    wall = time.monotonic() - t0

    def find(pat, cast=str, default=None):
        m = re.search(pat, out, re.MULTILINE)
        return cast(m.group(1)) if m else default

    return {
        "seed": seed,
        "effective_seed": find(r"^\s*seed\s+=?\s*(\d+)\s*$", int,
                               default=seed),
        "rerolls": len(re.findall(r"rerolling to seed=", out)),
        "success": ("SUCCESS" in out) and not timed_out and rc == 0,
        "timed_out": timed_out,
        "exit_code": rc,
        "plans_executed": find(r"[Pp]lans executed\s*:?\s+(\d+)", int),
        "planning_time_s": find(
            r"[Cc]umulative planning time\s*:?\s+([\d.]+)s", float),
        "senses_seen": len(re.findall(r"sense\s+shadow_of", out)),
        "wall_s": round(wall, 1),
        "fail_reason": find(r"FAILED:?\s*(.+)"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True,
                    help="arm name; also the resume key and JSON filename")
    ap.add_argument("--seeds", default="0-19",
                    help='e.g. "0-19", "100-119", "0,5,9"')
    ap.add_argument("--scene", default="random-pairs")
    ap.add_argument("--goal", default="holding")
    ap.add_argument("--pipeline-args", default="--seed-retry",
                    help="extra test_full_pipeline flags; older refs may "
                         "not support --seed-retry - pass '' there")
    ap.add_argument("--timeout", type=int, default=1200,
                    help="per-episode wall-clock cap in seconds")
    ap.add_argument("--out-dir",
                    default=os.path.join(ROOT, "eval_results", "ab_eval"))
    args = ap.parse_args()
    seeds = parse_seeds(args.seeds)
    os.makedirs(args.out_dir, exist_ok=True)

    def git(*a):
        return subprocess.run(("git",) + a, cwd=ROOT,
                              capture_output=True).stdout.decode().strip()

    branch = git("branch", "--show-current") or "(detached)"
    head = git("rev-parse", "--short", "HEAD")
    out_path = os.path.join(args.out_dir, f"{args.tag}.json")
    print(f"[ab] arm={args.tag} branch={branch} head={head} "
          f"scene={args.scene} goal={args.goal} seeds={args.seeds}",
          flush=True)

    results = []
    if os.path.exists(out_path):
        with open(out_path) as f:
            results = json.load(f).get("results", [])
        print(f"[ab] resuming: {len(results)} episode(s) already banked",
              flush=True)
    done = {r["seed"] for r in results}

    for seed in seeds:
        if seed in done:
            continue
        r = run_episode(seed, args)
        results.append(r)
        print(f"[ab] seed {seed:4d} -> eff {r['effective_seed']} "
              f"{'OK ' if r['success'] else 'FAIL'} "
              f"plans={r['plans_executed']} "
              f"plan_t={r['planning_time_s']}s wall={r['wall_s']}s "
              f"{'TIMEOUT' if r['timed_out'] else ''} "
              f"{r['fail_reason'] or ''}", flush=True)
        with open(out_path, "w") as f:
            json.dump({"arm": args.tag, "branch": branch, "head": head,
                       "scene": args.scene, "goal": args.goal,
                       "pipeline_args": args.pipeline_args,
                       "results": results}, f, indent=1)

    n = len(results)
    ok = sum(r["success"] for r in results)
    pts = sorted(r["planning_time_s"] for r in results
                 if r["planning_time_s"] is not None)
    if pts:
        print(f"[ab] DONE {args.tag}: success {ok}/{n}  "
              f"mean plan_t {sum(pts) / len(pts):.1f}s  "
              f"median {pts[len(pts) // 2]:.1f}s", flush=True)
    else:
        print(f"[ab] DONE {args.tag}: success {ok}/{n}  "
              f"(no planning times parsed - CHECK THE PARSE REGEXES "
              f"against this ref's console format)", flush=True)


if __name__ == "__main__":
    main()
```
