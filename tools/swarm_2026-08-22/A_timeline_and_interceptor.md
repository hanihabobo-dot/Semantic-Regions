# Agent A — Timeline + Interceptor Identification

Run under investigation: `logs/run_2026-08-22_17-14-10/` (GUI, seed 0,
scene `random-pairs`, 3 occluders, goal `holding` blue_object, ORACLE hides
blue in `shadow_of_red_object`). Failed after 8 plans, class `F7`
(binding-death: PDDLStream found a skeleton but stream binding delivered no
values). Sources: `run_2026-08-22_17-14-10.log` (line numbers below are
1-indexed `Read`-tool line numbers), `timing_summary.json`,
`boxel_data.json`, `problem_initial.pddl`, and two probes run against the
current (uncommitted) working tree:
`tools/swarm_2026-08-22/probe_A_interceptor.py` →
`tools/swarm_2026-08-22/probe_A_dump.txt` /
`tools/swarm_2026-08-22/probe_A_stdout.txt`.

All findings below are marked **CONFIRMED** (verified by reading the log/code
or by a probe's printed output) or **HYPOTHESIS** (reasoning that could not
be directly reproduced).

---

## Part 1 — Full timeline

### Run configuration (log:8–26, `boxel_data.json:2–21`)

scene=random-pairs, n_occluders=3, n_targets=1, n_hidden=1, seed=0,
goal=holding, uniform_cell_size=0.05, effective_min_boxel_size=0.146 m
(log:34). Camera position `[0.1,-0.8,0.7]`, target `[0.1,0.0,0.5]` (log:29–30).
Target=blue_object; ORACLE says blue is hidden in `shadow_of_red_object`
(log:52–53). Initial shadow blockers (log:56–58, `Phase 4`):
`shadow_of_green_object←[green_object]`, `shadow_of_orange_object←[orange_object]`,
`shadow_of_red_object←[red_object]`.

### Chronological table

| Wall-clock | Plan # | Action(s) executed | Physical outcome | Belief / registry / census change |
|---|---|---|---|---|
| 17:14:10–17:14:28 | setup | Phase 1–5: env spawn, boxelize (16 boxels), register, export `problem_initial.pddl` | — | Initial `obj_at_boxel`: green→`green_object`, orange→`orange_object`, red→`red_object` (log:73) |
| 17:14:28–17:14:32 | **#1** (4.289 s, log:99–116) | Skeleton: **pick orange → place at free_005 → sense `shadow_of_orange_object`** for blue. `move`→`pick orange_object` succeeds, `pad_normal_force=112.25N` (log:132–134, **CONFIRMED**). `move` to free_005 needs RRT-Connect (direct path blocked; 8 wps→3 smoothed, log:138–141). | **`place` FAILS at entry: `pad_normal_force=0.00N`, pad contacts=none (log:145)** — orange slipped out of the friction grip somewhere during the RRT transit, i.e. it was physically flung/dropped, landing at an unlogged location. "clearing held state and replanning" (log:146); `transit loss 1/3 for orange_object` (log:147). | First `[perception] 1 object(s) not visible in the refresh render — keeping last estimate: ['orange_object']` (log:148, **CONFIRMED, first of 7**). Registry keeps orange's OBJECT boxel at its spawn AABB — never updated for the rest of the run. |
| 17:14:32–17:14:46 | **#2** (3.174 s, log:184–200) | Skeleton: pick green → place at free_003 → sense `shadow_of_green_object`. `pick green_object` succeeds (109.19N, log:217). `place` at free_003 **succeeds** (log:227–229, tilt 0.33°, err ‑0.0 mm). | Green physically relocated to `[0.2051,-0.1545,0.3913]` (log:228). | Census (audit #78) recomputes: `shadow_of_orange_object←[orange_object]`, `shadow_of_red_object←[red_object]` printed (log:231–232); **`shadow_of_green_object` is absent from the print → its blocker set is now empty (green moved off its own casting position)**. `obj_at_boxel`: orange **still `['orange_object']`** (plan #2 diag, log:158, unchanged from plan #1). Sense of `shadow_of_green_object`: `contains something the render cannot localize … [attempt 1]` (log:243). 2nd `[perception] … keeping last estimate: ['orange_object']` (log:244). |
| 17:14:46–17:15:08 | **#3** (1.605 s, log:283–291) | Re-boxelize (80→12 boxels, log:248–253). Skeleton: move → sense `shadow_of_green_object` (no pick/place needed). | Sense attempt 2: `contains something the render cannot localize … [attempt 2]` (log:302–303). | `obj_at_boxel` orange still `['orange_object']` (log:260, green now `['free_003']`). 3rd `keeping last estimate: ['orange_object']` (log:304). |
| 17:15:08–17:15:14 | **#4** (1.365 s, log:337–345) | move → sense `shadow_of_green_object` again. | Sense attempt 3: `contains something the render cannot localize … [attempt 3]` → **`ERROR: shadow_of_green_object unlocalizable-content 3 times — giving up … Marked not_here`** (log:357–358). | `blocked_giveup_shadows` gets `shadow_of_green_object`; `belief.mark_sensed(..., found=False)`. `obj_at_boxel` orange still `['orange_object']` (log:314). 4th `keeping last estimate: ['orange_object']` (log:359). |
| 17:15:14–17:15:22 | **#5** (6.754 s, log:394–422) | Skeleton: pick red → place at free_011 → sense `shadow_of_red_object`. `pick red_object` succeeds (119.81N, log:441). `place` at free_011 **succeeds** (`pos=[0.2039,-0.0019,0.3951]`, log:452, tilt 0.24°). | Red physically relocated to free_011. | Census reprint (log:454–455): **`shadow_of_orange_object blocked by: ['red_object']`** — this is the exact line the task asked me to quote: the same predicate that read `['orange_object']` at log:57 (initial Phase 4) and again at log:231 (after plan #2) now reads `['red_object']`, because compute_shadow_blockers re-renders and finds RED's *new* position (free_011) intercepting `shadow_of_orange_object`'s grid on >5 % of a slice — orange's *old* position is no longer where anything actually blocks that shadow from the camera, but the planner's own belief for orange itself never changed. `shadow_of_red_object` is now absent from the print → its own blocker set (previously `['red_object']`) is now empty too (red moved off its own casting position). Sense of `shadow_of_red_object` attempt 1: `NOTE: 4/388 endpoints hidden by robot arm (not occluder)` → `View to shadow_of_red_object still blocked (8% of the worst slice's rays hit occluder). [attempt 1]` → shrunk `10.4x33.2x13.6 → 4.3x8.3x9.1 cm` (log:466–468) → `REPLANNING without marking shadow empty`. `obj_at_boxel` orange still `['orange_object']` (log:369, unchanged). 5th `keeping last estimate: ['orange_object']` (log:470). |
| 17:15:22–17:15:49 | **#6** (1.453 s, log:509–517) | Re-boxelize (58→12, log:474–479). move → sense shrunk `shadow_of_red_object`. | Sense attempt 2: `contains something the render cannot localize … [attempt 2]` (log:528–529). | `obj_at_boxel`: green `['free_003']`, red `['free_011']`, orange **still `['orange_object']`** (log:486). 6th `keeping last estimate: ['orange_object']` (log:530). |
| 17:15:49–17:15:56 | **#7** (1.504 s, log:562–571) | move → sense shrunk `shadow_of_red_object` again. | Sense attempt 3: `contains something the render cannot localize … [attempt 3]` → **`ERROR: shadow_of_red_object unlocalizable-content 3 times — giving up … Marked not_here`** (log:583–584). | `blocked_giveup_shadows` now has both `shadow_of_green_object` and `shadow_of_red_object` (the ORACLE-correct one). 7th (final) `keeping last estimate: ['orange_object']` (log:585). Only `shadow_of_orange_object` remains unsearched (`Unknown shadows remaining: 1`, log:588). |
| 17:15:56–17:16:10 | **#8** (4.678 s, log:619–637) | Only remaining skeleton: pick red off free_011 → place at free_014 → move to `shadow_of_orange_object` → sense → pick blue. IK for `red_object at free_010`/`free_011` rejects (8 seeds fail, log:399–403); complexity climbs to 4; **stream binding never delivers values for the one found skeleton** (`sample_time=0.002s`, log:632–635). | No physical action executed (planning-only failure). | `Action plan: False` (log:630). `exit_reason: "no_plan_binding_death"` (`timing_summary.json:23`). Run ends: **8 plans, 24.822 s cumulative planning, `success: false`** (log:639–648, `timing_summary.json`). |

### Orange's belief vs. physical reality, made explicit

- **Physically**: orange_object is picked at 17:14:32 (log:130–134,
  `pad_normal_force=112.25N`) and is confirmed gone from the gripper by
  17:14:38 — the place-entry assert at free_005 reads `pad_normal_force=0.00N`
  (log:145) after an RRT-Connect transit (log:138–141). It is never picked,
  placed, sensed, or otherwise physically referenced again in the log.
- **In the planner's belief** (`obj_at_boxel` fact for orange_object, printed
  in every plan's `[#76-diag]` block): `['orange_object']` at plan #1
  (log:73), #2 (log:158), #3 (log:260), #4 (log:314), #5 (log:369), #6
  (log:486), #7 (log:540), #8 (log:595) — **identical, unchanged, across all
  8 plans**. Green's and red's `obj_at_boxel` facts DO update the instant
  their `place` succeeds (green: `['green_object']`→`['free_003']` between
  plan #2 and #3; red: `['red_object']`→`['free_011']` between plan #5 and
  #6) — orange is the only one of the three occluders whose belief never
  moves, because it was never successfully re-placed (its `place` failed,
  so no code path ever writes a new boxel for it).
- **The shadow census (audit #78, `compute_shadow_blockers`,
  execution.py:283) is observation-driven and did update**, independent of
  orange's frozen `obj_at_boxel` fact: `shadow_of_orange_object blocked by:
  ['orange_object']` (log:57, Phase 4) → unchanged after green's placement
  (log:231, since neither orange nor green's new position affects that
  shadow) → **`shadow_of_orange_object blocked by: ['red_object']`** (log:455,
  after red's placement at free_011) — red's new position geometrically
  intercepts `shadow_of_orange_object`'s sense grid, so the *shadow*-level
  census correctly re-attributes the blocker, while the *object*-level
  belief for orange itself stays stuck. This is an asymmetry in what gets
  refreshed from observation: shadow-blocker facts (`blocks_view_at`) are
  recomputed from a fresh render every place action; the moved/lost
  object's own `obj_at_boxel` fact is not, because nothing ever observes
  orange again to correct it (see Part 2/3 below for why).
- `n_sense_actions: 6` (`timing_summary.json:25`) matches the 6 `sense`
  actions executed (plans #2–#4 on `shadow_of_green_object`, #5–#7 on
  `shadow_of_red_object`); the `[perception] … keeping last estimate:
  ['orange_object']` line fires 7 times total (log:148,244,304,359,470,530,585)
  — once per sense action (6) plus once after the plan #1 place failure (1),
  since `refresh_object_aabbs` is also called from the place-failure cleanup
  path.

---

## Part 2 — Which body was the sub-detection-minimum interceptor?

### Working-tree note (important, affects reproducibility)

`git status --porcelain execution.py` → `" M execution.py"` (41 insertions /
8 deletions vs `HEAD=2056f04`, **CONFIRMED**, not made by this probe — rule
#3 forbids that). The working tree already carries an **uncommitted #P1 F15
diagnostic**: `sense_shadow_from_render` (execution.py:71) now returns a 5th
element, `interceptor_counts` (`{seg id → endpoints intercepted}`,
execution.py:129–134, 183, 201–202), and `handle_sense_action`
(execution.py:1799) prints an `[F15-diag] discoveries: …` line
(execution.py:2003–2006) naming exactly the body this task asks about,
whenever the "cannot localize" guard fires. **This fix postdates the
investigated run** — `run_2026-08-22_17-14-10.log` has no `[F15-diag]` lines
anywhere, so the run itself never got to name its own interceptor; the
diagnostic exists now but wasn't there when the failure happened. My probe
calls the *current* `execution.sense_shadow_from_render` directly (not a
reimplementation) to get the authoritative classification for reconstructed
states.

### Guard mechanism (execution.py:1977–2024, CONFIRMED by reading)

`sense_shadow_from_render` computes `detected_bodies` = seg ids that
intercept a shadow's sense-grid endpoint and are **not** the target, not the
robot, not a support (plane/table/tray), and not in `occluder_pybullet_ids`
(the shadow's *currently registered* census blockers, execution.py:1861–1864,
sourced from `shadow_occluder_map`). If `sense_outcome == "contains_nontarget"`
and **none** of `detected_bodies` appear in `sense_detections` (i.e. all have
global segmentation pixel count `< DETECTION_MIN_PIXELS = 6`,
perception.py:320) — `handle_sense_action` prints "contains something the
render cannot localize" (execution.py:1984–1987) and burns a strike
(execution.py:1969, 2007) instead of registering a discovery.

### Which shadows had which occluder set at sense time (CONFIRMED from the log)

- `shadow_of_green_object` at plans #2/#3/#4: occluder set **empty**
  (log:231–232 lists it as absent → 0 blockers; diag confirms
  `shadow_of_green_object(blockers=0)`, log:258).
- `shadow_of_red_object` at plans #5/#6/#7: occluder set **empty**
  (log:454–455 lists it as absent after red's placement; diag confirms
  `shadow_of_red_object(blockers=0)`, log:484).

So for both guard-triggering shadows, `ignore_ids` reduces to
`{-1, robot_id, plane, table, target(blue)}` — meaning **red_object,
green_object, and orange_object were all eligible** to be classified as
`detected_bodies`; nothing hard-excluded them by name.

### Elimination of green_object and red_object (CONFIRMED by probe)

`probe_A_interceptor.py` PART 2 calls the real `execution.sense_shadow_from_render`
with the corrected (empty) occluder sets, green at its real post-place
position and red at both its pre-move (original) and post-place (free_011)
positions:

```
[REAL sense_shadow_from_render / green-shadow / orange hidden far away] outcome=clear_but_empty  detected_bodies=[]
[REAL sense_shadow_from_render / red-shadow(orig)  / orange hidden far away] outcome=found_target  detected_bodies=[]  interceptor_counts={6: 1}   (blue itself, 643 px — expected, this is blue's true hiding spot)
[REAL sense_shadow_from_render / red-shadow(shrunk)/ orange hidden far away] — not tested directly, but S2a/S2b variants below show clear_but_empty
```

With orange present at either candidate position (see next section) the
outcome for green's shadow stays `clear_but_empty` and for red's
shadow stays `found_target` (original AABB, since our reconstruction has no
robot arm blocking blue) or `clear_but_empty` (shrunk AABB) — **green_object
and red_object never once appear in `detected_bodies` in any tested state**;
they are geometrically nowhere near the relevant camera-ray projections.
Independently, both have global pixel counts of 1000+ in every state
(S1 red=4199, green=1315→3175; S3 red=1242, green=3175 — probe_A_stdout.txt
lines 24–29, 40–44, 65–71) — far above `DETECTION_MIN_PIXELS=6`, so *even if*
either intercepted an endpoint it would be `sense_detections`-localized and
would NOT trigger the "cannot localize" branch (it would instead register as
a normal `contains_nontarget` discovery, which never happened in the log).
**Blue_object is categorically excluded by construction**: any endpoint hit
on `target_pybullet_id` returns `"found_target"` immediately
(execution.py:203–204), before the localizability branch is ever reached;
its S3 pixel count (643, probe_A_stdout.txt:71/122) is reported only for
completeness.

**By elimination: orange_object is the only body that can be the
sub-detection-minimum interceptor** (**CONFIRMED** as the only remaining
candidate; its *exact* pose is **HYPOTHESIS**, see below).

### Reproducing orange's actual pose — not achieved (HYPOTHESIS, disclosed negative result)

Per the task's two plausible endings, plus a 339-pose grid sweep over two
regions and 4 hand-picked "wedge" poses (probe_A_interceptor.py
`S2-SWEEP`/`S2-WEDGE`, full numbers in probe_A_dump.txt and
probe_A_stdout.txt):

| Candidate orange pose | Global seg px | Intercepts `shadow_of_green` endpoints? | Intercepts `shadow_of_red` endpoints? |
|---|---|---|---|
| S2a: floor beside table `(0.0,-0.55,0.0341)` | 0 | No (0/674) | No (0/388, both AABBs) |
| S2b: on-table frame-edge `(-0.08,-0.38,0.359)` | 6372 | No (0/674) | No (0/388, both AABBs) |
| 339-pose grid sweep (floor region + 2 table-edge strips) | 700–6557 whenever intercepting at all | 10/339 poses intercept, **all with ≥700 px** | not swept |
| 4 wedge poses (behind red, table corners) | 41–6557 | 0/4 intercept | not swept |

**Zero of ~347 tested poses simultaneously satisfy `<6 global px` AND
`≥1 shadow endpoint intercepted`.** The geometric pattern is consistent:
whenever orange sits somewhere its projection lands on a `shadow_of_green`/
`shadow_of_red` grid endpoint, it is also large/close enough on-screen to be
solidly visible (hundreds to thousands of px); whenever it's nearly invisible
(0 px, off-frame or fully occluded), it also doesn't intercept anything.
Hitting both conditions at once needs orange to be almost entirely hidden
behind some *other* body (the robot arm, red, green, or the table edge) with
only a 1–5-pixel sliver surviving that happens to land on exactly one shadow
endpoint's projected pixel — a low-probability coincidence for a coarse pose
sweep, but physically plausible for the actual event: orange was flung off
the gripper mid-RRT-transit (log:138–145), an unrepeatable, chaotic physical
event this probe was explicitly told not to replay (orchestrator hard rule:
teleport states only, "do NOT try to replay the arm"). **Conclusion: orange
is the interceptor by elimination (CONFIRMED), but its precise resting
pose — and therefore the precise 1–5px reading the real run's F15 diagnostic
would have printed — could not be recovered without an arm-trajectory
replay, which is out of this probe's scope.**

### Bonus finding: why orange never gets marked "lost" instead of "stale" (HYPOTHESIS)

`refresh_object_aabbs(check_lost=True)` (execution.py:1597) tests whether a
stale object's *believed* AABB (for orange, still its original spawn box,
`min=[0.133,0.138,0.325]`, `max=[0.187,0.192,0.458]` — never updated, since
orange's registry entry is untouched, matching the frozen `obj_at_boxel`
fact) renders **fully empty** on every sense-grid slice
(`first_surface_interceptors` called there with **no `ignore_ids` at all** —
unlike `sense_shadow_from_render`, nothing is excluded, execution.py:1691–1700).
If empty, the object is retired as `LOST` (never happened in this log — only
the "keeping last estimate" / stale branch fires, 7 times). Probe PART 3
reconstructs orange's own original box in the two relevant occluder
configurations (green@free_003/red@original for plans #2–#4, and
green@free_003/red@free_011 for plans #6–#7) with orange itself removed from
the scene, and finds `observed_empty=True` in **both** cases
(probe_A_stdout.txt, PART 3 block) — i.e., with no robot arm in the frame,
orange's old spot renders completely clear. Since the real run never
reported it LOST, **something not modeled by this teleport-only probe — most
likely the robot arm's transient pose during the refresh renders that follow
each place/sense action — must be occluding orange's old spot just enough
(>5% of one slice) to keep it "stale" instead of "lost," every single time**.
This is plausible but unverified (arm replay out of scope) and is flagged as
HYPOTHESIS.

---

## Answers to the structured-output fields

- **`interceptor_body`**: `orange_object` (pybullet body id 5 in the probe's
  reconstruction) — identified by elimination (CONFIRMED); its exact
  intercepted-endpoint count could not be reproduced (no tested pose
  reproduces the log's exact interaction), so `interceptor_pixels` is
  reported as the best-supported estimate: **0**, matching the S2a
  ("flung off the table, resting on the floor beside it, out of camera
  view") reconstruction — the only tested ending under 6 px globally
  (probe_A_stdout.txt: `orange_object global_seg_px=0`). This specific
  pose does not itself intercept any grid endpoint in the probe (0
  reproduces the pixel-count condition but not the interception condition;
  see the disclosed negative result above) — treat the pixel figure as the
  closest measured proxy, not a full reproduction.
- **`blue_pixels_S3`**: 643 (probe_A_stdout.txt:71/122, body id 6, final S3
  render — blue is visible/unoccluded from the camera the whole time; it is
  ruled out as the interceptor by construction, not by pixel count).
- **`orange_resting_place`**: unreproduced. Best-supported HYPOTHESIS:
  knocked off the table during the plan #1 RRT-Connect transit to free_005
  and out of the camera's view entirely (0 global px in every "off-table"
  reconstruction tried) — but the exact pose that also grazes a
  `shadow_of_green_object`/`shadow_of_red_object` sense endpoint was not
  found by an exhaustive teleport search and would require replaying the
  arm's actual throw physics (out of scope).

## Files produced

- `tools/swarm_2026-08-22/A_timeline_and_interceptor.md` — this report.
- `tools/swarm_2026-08-22/probe_A_interceptor.py` — probe source (extended
  with PART 2 authoritative `sense_shadow_from_render` replay and PART 3
  lost-check replay; original S1/S2/S3/sweep/wedge sections preserved).
- `tools/swarm_2026-08-22/probe_A_dump.txt` — full per-endpoint dump
  (written by the probe's own `DUMP_PATH` writer).
- `tools/swarm_2026-08-22/probe_A_stdout.txt` — full captured stdout of the
  latest probe run (160 lines), source of every pixel-count/outcome number
  quoted above.
