#!/usr/bin/env python3
"""Agent D (F12/I4) marginal-band evidence sweep.

READ-ONLY: parses existing log text under logs/ and eval_results/. Does not
run pybullet, pddlstream, or FastDownward. Does not modify any repo file
other than writing its own JSON output under tools/swarm_2026-08-22/.

For every `place` action confirmed with "*** X PLACED at Y! ***", checks
whether the immediately-preceding "Shadow blockers (audit #78):" census
block (compute_shadow_blockers, SENSE_MARGINAL_BLOCKED_FRACTION = 0.05)
already lists the just-placed object X as a blocker of some shadow. That is
the observable signature of the F11 residual: a placement that cleared
whatever prospective gate was active gets immediately re-flagged by the
post-place census.
"""
import json
import re
import os
from pathlib import Path

REPO = Path("/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels")
OUT_DIR = REPO / "tools" / "swarm_2026-08-22"

HEADER_RE = re.compile(r"^\s*(\w[\w_]*)\s*=\s*(.+?)\s*$")
CENSUS_HEADER_RE = re.compile(r"Shadow blockers \(audit #78\):")
CENSUS_LINE_RE = re.compile(r"^\s*(\S+) blocked by: \[(.*)\]\s*$")
PLACED_RE = re.compile(r"\*\*\*\s+(\S+)\s+PLACED at (\S+)!\s+\*\*\*")
TARGET_RE = re.compile(r"^\s*Target:\s*(\S+)")
ORACLE_RE = re.compile(r"ORACLE: Actually hidden in (\S+)")
FAILED_RE = re.compile(r"^FAILED: (.+)$")
SUCCESS_RE = re.compile(r"^SUCCESS!\s*$")
RUN_STARTED_RE = re.compile(r"Run started\s*:\s*(\S+)")
PLAN_START_RE = re.compile(r"\[timing\] planner\.plan\(\) #(\d+):")
RELOCATE_HINT_RE = re.compile(
    r"relocate|re-pick|F7|binding death|not_here|not-here|"
    r"blocked-unresolved|giving up", re.IGNORECASE)

# F11 code-regime boundaries observed in git log (2026-08-22, all times
# same day, from `git log --pretty=%ad %s --date=format:%H:%M:%S`):
#   < 12:22:42            regime A: no per-object egregious volume test at
#                          all (only the free-CELL AABB pair test @ 0.05).
#   12:22:42 - 12:42:53   regime B: FIRST F11 impl (335ddc1) - per-object
#                          volume tested at the STRICT 0.05 census margin.
#   12:42:53 - ~15:40:09  regime C: reverted back to regime A.
#   >= ~15:40:09 (c0fb6ec, "F11: per-object egregious ... at 0.15")
#                          regime D: final fix - egregious test @ 0.15,
#                          the literal 5-15% band this sweep targets.
# NOTE: run 15-25-35 predates the c0fb6ec commit timestamp by ~15 min but
# PAPER_AUDIT.txt F11 cites it as the fix's own smoke/repro (working-tree
# code, committed after the smoke passed) - flagged individually below
# rather than trusted to the timestamp cut alone.
REGIME_D_CUTOFF_SEC = 15 * 3600 + 40 * 60 + 9  # 15:40:09


def _hhmmss_to_sec(hhmmss: str):
    # run dir names use HH-MM-SS; be defensive about non-matching ids
    # (e.g. secondary corpus cell names carry no timestamp at all).
    parts = hhmmss.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s


def classify_regime(run_time_hhmmss: str) -> str:
    sec = _hhmmss_to_sec(run_time_hhmmss)
    if sec is None:
        return "N/A(no timestamp, e.g. secondary corpus)"
    return ("D(current,0.15-gate)" if sec >= REGIME_D_CUTOFF_SEC
            else "A/B/C(pre-fix or first-impl)")


def parse_log(path: Path, run_id: str):
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()

    cfg = {}
    target = None
    oracle_shadow = None
    run_time = run_id.split("_")[-1] if "_" in run_id else run_id

    # collect terminal outcome
    final_outcome = None  # "SUCCESS" or the FAILED reason text
    final_line_no = None

    # walk lines, tracking last census block
    last_census = {}  # shadow_id -> [blocker ids]
    in_census = False
    incidents = []
    place_lines = []  # (line_no, obj, boxel)
    plan_starts = []  # line numbers where a new "Plan #" begins (rough replan marker)

    for i, line in enumerate(text, start=1):
        if i <= 30:
            m = HEADER_RE.match(line)
            if m and m.group(1) in (
                "scene", "n_occluders", "n_targets", "n_hidden",
                "n_extra_distractors", "n_objects", "seed", "goal",
                "stack_height", "baseline"):
                cfg[m.group(1)] = m.group(2)

        tm = TARGET_RE.match(line)
        if tm and target is None:
            target = tm.group(1)

        om = ORACLE_RE.search(line)
        if om and oracle_shadow is None:
            oracle_shadow = om.group(1)

        if CENSUS_HEADER_RE.search(line):
            in_census = True
            last_census = {}
            continue
        if in_census:
            cm = CENSUS_LINE_RE.match(line)
            if cm:
                sid = cm.group(1)
                blockers_raw = cm.group(2)
                blockers = [b.strip().strip("'\"") for b in blockers_raw.split(",") if b.strip()]
                last_census[sid] = blockers
                continue
            else:
                in_census = False

        pm = PLACED_RE.search(line)
        if pm:
            obj, boxel = pm.group(1), pm.group(2)
            place_lines.append((i, obj, boxel))
            hit_shadows = [sid for sid, blockers in last_census.items() if obj in blockers]
            if hit_shadows:
                incidents.append({
                    "line": i,
                    "placed_obj": obj,
                    "placed_boxel": boxel,
                    "reblocked_shadows": hit_shadows,
                    "census_snapshot": {sid: last_census[sid] for sid in hit_shadows},
                })

        psm = PLAN_START_RE.match(line)
        if psm:
            plan_starts.append(i)

        fm = FAILED_RE.match(line)
        if fm:
            final_outcome = "FAILED: " + fm.group(1)
            final_line_no = i
        sm = SUCCESS_RE.match(line)
        if sm:
            final_outcome = "SUCCESS"
            final_line_no = i

    # annotate incidents with what happened next
    n_lines = len(text)
    for inc in incidents:
        inc_line = inc["line"]
        target_is_here = (oracle_shadow is not None
                           and oracle_shadow in inc["reblocked_shadows"])
        inc["target_true_hiding_place"] = target_is_here
        inc["oracle_shadow"] = oracle_shadow
        # plans that start after this incident
        later_plans = [p for p in plan_starts if p > inc_line]
        inc["plan_restarts_after"] = len(later_plans)
        # placements after this incident (did the episode keep placing objects?)
        later_places = [p for p in place_lines if p[0] > inc_line]
        inc["placements_after"] = len(later_places)
        # distance (in lines) from incident to the run's terminal outcome line
        inc["lines_to_final_outcome"] = (
            (final_line_no - inc_line) if final_line_no else None)
        inc["run_final_outcome"] = final_outcome
        # crude "ended episode" heuristic: no further planning activity
        # (no new Plan # header) after the incident, and the run FAILED.
        inc["episode_ended_by_this"] = (
            final_outcome is not None
            and final_outcome != "SUCCESS"
            and len(later_plans) == 0
        )

    return {
        "run_id": run_id,
        "path": str(path),
        "run_time_hhmmss": run_time,
        "regime": classify_regime(run_time),
        "config": cfg,
        "target": target,
        "oracle_shadow": oracle_shadow,
        "total_place_actions": len(place_lines),
        "total_plan_restarts": len(plan_starts),
        "final_outcome": final_outcome,
        "incidents": incidents,
    }


def main():
    results = []

    # Primary corpus: today's GUI/headless runs.
    run_dirs = sorted((REPO / "logs").glob("run_2026-08-22_*"))
    for d in run_dirs:
        if not d.is_dir():
            continue
        log_path = d / f"{d.name}.log"
        if not log_path.exists():
            continue
        try:
            results.append(parse_log(log_path, d.name))
        except Exception as e:
            results.append({"run_id": d.name, "path": str(log_path), "error": str(e)})

    primary_out = OUT_DIR / "D_primary_sweep_results.json"
    primary_out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Secondary corpus: the pre-existing May sweep (older code, no
    # PLACEMENT_EGREGIOUS_BLOCKED_FRACTION at all -> different regime,
    # kept separate, not mixed into the primary quantification).
    sweep_dir = REPO / "eval_results" / "sweep_full_2026-05-28" / "cells"
    sweep_results = []
    if sweep_dir.exists():
        for cell_dir in sorted(sweep_dir.iterdir()):
            log_path = cell_dir / "stdout.log"
            if not log_path.exists():
                continue
            try:
                sweep_results.append(parse_log(log_path, cell_dir.name))
            except Exception as e:
                sweep_results.append({"run_id": cell_dir.name, "path": str(log_path), "error": str(e)})

    secondary_out = OUT_DIR / "D_secondary_sweep_results.json"
    secondary_out.write_text(json.dumps(sweep_results, indent=2), encoding="utf-8")

    # ---- summary printed to stdout ----
    def summarize(rs, label):
        total_runs = len(rs)
        total_places = sum(r.get("total_place_actions", 0) for r in rs if "error" not in r)
        all_incidents = [inc for r in rs if "error" not in r for inc in r.get("incidents", [])]
        n_incidents = len(all_incidents)
        n_ended = sum(1 for inc in all_incidents if inc["episode_ended_by_this"])
        n_target_here = sum(1 for inc in all_incidents if inc["target_true_hiding_place"])
        n_runs_with_incident = sum(1 for r in rs if "error" not in r and r.get("incidents"))
        print(f"=== {label} ===")
        print(f"  runs parsed: {total_runs}")
        print(f"  total place actions: {total_places}")
        print(f"  runs with >=1 incident: {n_runs_with_incident}")
        print(f"  total incidents (immediate re-block): {n_incidents}")
        print(f"  incidents where episode ended with no further plan restart: {n_ended}")
        print(f"  incidents where reblocked shadow WAS target's true hiding place: {n_target_here}")
        # regime split (primary only makes sense)
        regime_counts = {}
        for r in rs:
            if "error" in r:
                continue
            reg = r.get("regime", "?")
            regime_counts.setdefault(reg, {"runs": 0, "incidents": 0})
            regime_counts[reg]["runs"] += 1
            regime_counts[reg]["incidents"] += len(r.get("incidents", []))
        for reg, c in regime_counts.items():
            print(f"    regime {reg}: {c['runs']} runs, {c['incidents']} incidents")
        print()

    summarize(results, "PRIMARY (logs/run_2026-08-22_*)")
    summarize(sweep_results, "SECONDARY (eval_results/sweep_full_2026-05-28, pre-F11 code)")

    # Dump the incident list in readable form for the report.
    lines = []
    for r in results:
        if "error" in r or not r.get("incidents"):
            continue
        for inc in r["incidents"]:
            lines.append(
                f"{r['run_id']} | goal={r['config'].get('goal')} seed={r['config'].get('seed')} "
                f"scene={r['config'].get('scene')} occ={r['config'].get('n_occluders')} "
                f"regime={r['regime']} | placed {inc['placed_obj']}@{inc['placed_boxel']} "
                f"line={inc['line']} -> reblocks {inc['reblocked_shadows']} "
                f"(target true hiding place={inc['target_true_hiding_place']}, "
                f"oracle_shadow={inc['oracle_shadow']}) | "
                f"plan_restarts_after={inc['plan_restarts_after']} "
                f"placements_after={inc['placements_after']} "
                f"episode_ended_by_this={inc['episode_ended_by_this']} "
                f"final_outcome={inc['run_final_outcome']}"
            )
    incident_txt = OUT_DIR / "D_primary_incidents_readable.txt"
    incident_txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} primary incident rows to {incident_txt}")

    lines2 = []
    for r in sweep_results:
        if "error" in r or not r.get("incidents"):
            continue
        for inc in r["incidents"]:
            lines2.append(
                f"{r['run_id']} | goal={r['config'].get('goal')} seed={r['config'].get('seed')} "
                f"| placed {inc['placed_obj']}@{inc['placed_boxel']} "
                f"line={inc['line']} -> reblocks {inc['reblocked_shadows']} "
                f"(target true hiding place={inc['target_true_hiding_place']}, "
                f"oracle_shadow={inc['oracle_shadow']}) | "
                f"plan_restarts_after={inc['plan_restarts_after']} "
                f"placements_after={inc['placements_after']} "
                f"episode_ended_by_this={inc['episode_ended_by_this']} "
                f"final_outcome={inc['run_final_outcome']}"
            )
    incident_txt2 = OUT_DIR / "D_secondary_incidents_readable.txt"
    incident_txt2.write_text("\n".join(lines2), encoding="utf-8")
    print(f"Wrote {len(lines2)} secondary incident rows to {incident_txt2}")


if __name__ == "__main__":
    main()
