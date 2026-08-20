# pick_giveup.md — investigation log

Repo: C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels
Branch: p1-real-grasp-perception
Scope: READ-ONLY diagnosis. No edits, no commits, no simulation runs.

## Task recap
GUI observation (--scene random-pairs --goal holding --seed 0): after a grasp
attempt on an occluder fails, sense keeps reporting still_blocked until the
3-strike giveup (audit #21) fires and the run moves to another shadow. A
toppled tall/narrow occluder becomes permanently unpickable.

## CORRECTION FROM COORDINATOR (mid-task)
Machine clock was 5 days behind until ~20:00 tonight (2026-08-20). The
correct/primary GUI logs for the target run are:
  logs\run_2026-08-20_20-09-59  (stack goal, not the target run)
  logs\run_2026-08-20_20-12-20  <-- THE TARGET RUN (holding, random-pairs, seed=0, gui=True)
  logs\run_2026-08-20_20-19-11  (stack goal, not the target run)
  logs\run_2026-08-20_20-21-49  (not checked in detail — 20-12-20 already gives
                                  full evidence for both problems)
The logs\run_2026-08-15_22-06-46 / 22-07-53 / 22-11-32 dirs are an EARLIER
round of the same GUI checks on the same branch (also carry [#P1-diag]
markers) and are used below as corroborating evidence — the blocks_view_at
bug reproduces identically in both rounds.

PRIMARY RUN: logs\run_2026-08-20_20-12-20\run_2026-08-20_20-12-20.log
  run_config (from the header, no timing_summary.json — process was killed
  mid-run, see below): scene=random-pairs, n_occluders=3, seed=0,
  goal=holding, gui=True, log_level=smart.

CORROBORATING RUN: logs\run_2026-08-15_22-07-53\run_2026-08-15_22-07-53.log
  (timing_summary.json confirms scene=random-pairs, seed=0, goal=holding,
  gui=true; success=false, exit_reason=all_searched, plan_count=12)

---

## PART A — Why sense keeps returning still_blocked / no re-pick of the occluder

### A1. Symptom in both runs

08-15 run (22-07-53), PLAN #1: robot picks `orange_object` (an occluder) from
its own spot, places it at free-space cell `free_005` — pick and place both
SUCCEED (log:174-195, "Grip verified... both pads in contact", "-> Released
orange_object (audit #80 verify ok...)"). Immediately after, `compute_shadow_
blockers()` is re-run and genuinely, physically finds `orange_object` STILL
blocking the very shadows it was supposed to clear:

```
190   Shadow blockers (audit #78):
191     shadow_of_green_object blocked by: ['orange_object', 'green_object']
192     shadow_of_orange_object__00 blocked by: ['orange_object']
193     shadow_of_orange_object__01 blocked by: ['orange_object']
194     shadow_of_red_object blocked by: ['red_object']
```

(#84-diag pre-release position for orange_object, log:188, is
`[0.0694,0.0856,0.3911]` — nearly identical to its ORIGINAL spot
`[0.071,0.084,...]` seen in the grasp ee_target at log:122. The chosen "free"
destination is right next to where the occluder started, so it is still in
the same camera→shadow ray-cone. `compute_shadow_blockers`'s live raycast
correctly detects this.)

Yet the very next planner.plan() call (PLAN #2, log:219) reports:

```
219   [#76-diag] shadows (4 total, 2 view-clear NOW): [...,
        'shadow_of_orange_object__00(blockers=0)', ...,
        'shadow_of_orange_object__01(blockers=0)']
```

`blockers=0` — the SAME shadow the raw compute_shadow_blockers call just
listed `orange_object` as blocking. The planner therefore emits a plain
`(move, sense, pick)` plan straight at `shadow_of_orange_object__01` — no
"relocate the blocker further" step is ever generated, because the model
believes nothing is blocking. Physically the ray-cast at sense time (finer:
7x7 grid x 3 z-slices vs. compute_shadow_blockers' 5x5 x 1 slice) again hits
`orange_object` at its new position:

```
203-206   Sensing shadow_of_orange_object__01 (fixed camera)...
          View to shadow_of_orange_object__01 still blocked (41% rays hit
          occluder). [attempt 1]
          -> REPLANNING without marking shadow empty...
```

This repeats identically for attempts 2 and 3 (log:320, 431) — SAME 41%
figure every time, because nothing about the scene changes between attempts
(no new relocate action is ever planned) — until the 3-strike giveup fires
(execution.py:1531-1542):

```
911  ERROR: shadow_of_red_object blocked 3 times — giving up (audit #21).
     ... Real remedy: re-ground blocker atoms after repeated failure —
     audit #47 (deferred out of scope 2026-05-06).
915  ERROR: No unknown shadows remain — but 3 of 3 were given up ...
918  FAILED: 0 shadow(s) observed empty, 3 blocked-unresolved
```

ALL THREE unresolved shadows in the 08-15 run (`shadow_of_orange_object__00`,
`__01`, `shadow_of_red_object`) fail via this EXACT mechanism — one successful
pick+place of the relevant occluder each time, then 3 identical still_blocked
strikes, then give-up. `shadow_of_green_object` is the only one that resolves
cleanly (sensed empty on attempt 1, log:572-575) — the target genuinely
wasn't behind it.

08-20 run (20-12-20) reproduces the identical pattern for BOTH orange
shadows (log:159, 219, 274, 329, 384-385 giveup on __01; 438-439 giveup on
__00) before the run moves on to green_object (see Part B).

### A2. Root cause — confirmed in code, not just inferred from logs

`compute_shadow_blockers` (execution.py:166-260) is doing its job correctly:
it re-raycasts against LIVE PyBullet geometry after every `place` action
(called from test_full_pipeline.py:1464, inside the place-action handler,
right after `registry.update_after_place`) and correctly identifies that the
relocated occluder is still in the ray path. Its "parent-relationship
fallback" (execution.py:242-251, the mechanism named in the task brief) is
NOT what fires here — the real ray-cast hits the occluder directly, so the
fallback path is never exercised for these shadows. **The `compute_shadow_
blockers` diagnosis for this scene is correct.**

The bug is in how that correct information is translated into PDDL facts.
`PDDLStreamPlanner._build_init` (pddlstream_planner.py:343-585):

```python
# pddlstream_planner.py:439-444
if self.shadow_occluder_map:
    for shadow_id, blocker_ids in self.shadow_occluder_map.items():
        if isinstance(blocker_ids, str):
            blocker_ids = [blocker_ids]
        for occluder_id in blocker_ids:
            init.append(('blocks_view_at', occluder_id, occluder_id, shadow_id))
```

This emits `blocks_view_at(occluder_id, occluder_id, shadow_id)` — the
occluder's OWN boxel id is hardcoded as BOTH the object arg and the
location arg, i.e. "X blocks shadow S only from X's own original spot."
Compare to the OBJECT-boxel loop just above it (pddlstream_planner.py:
403-413):

```python
elif boxel.boxel_type == BoxelType.OBJECT:
    ...
    if boxel.id in moved_occluders:
        dest = moved_occluders[boxel.id]
        init.append(('obj_at_boxel', boxel.id, dest))       # obj_at_boxel(X, free_005)
        init.append(('obj_at_boxel_KIF', boxel.id, dest))
    else:
        init.append(('obj_at_boxel', boxel.id, boxel.id))   # obj_at_boxel(X, X)  -- only if NOT moved
```

Once an occluder is picked up and placed ANYWHERE (i.e. it's a key in
`moved_occluders`), `obj_at_boxel(X, X)` is never emitted again — only
`obj_at_boxel(X, free_005)`. The domain's derived predicate
(pddl/domain_pddlstream.pddl:99-102):

```lisp
(:derived (blocks_view ?obj ?region)
  (exists (?b)
    (and (obj_at_boxel ?obj ?b)
         (blocks_view_at ?obj ?b ?region))))
```

requires the SAME `?b` in both facts. Since `blocks_view_at` is permanently
keyed to the occluder's own boxel id (never re-grounded to `free_005`), and
`obj_at_boxel(X, X)` disappears the instant the occluder is recorded as
moved, `blocks_view(occluder, shadow)` becomes UNDERIVABLE forever after one
relocation — **regardless of whether the destination the occluder was placed
at actually clears the sightline**. `_build_init`'s own diagnostic code
(pddlstream_planner.py:673-684, `blocked_by_count`) implements this same
(occluder_id, occluder_id) pairing check, which is exactly why the "blockers="
diagnostic printed `0` right after `compute_shadow_blockers` printed the
correct nonzero blocker.

There IS a second, independent mechanism meant to catch exactly this class of
problem — "placement-blocking facts" (pddlstream_planner.py:452-471, using
`_compute_placement_view_blocks` at :305-341) which pre-checks whether ANY
free-space boxel's full AABB intersects a shadow's camera ray-cone and, if
so, emits `blocks_view_at(obj, free_id, shadow_id)` for every object so a
future placement there is correctly flagged. In this scene it evidently
misses the free_005/shadow_of_orange_object__01 pair (same 5x5 single-slice
resolution as `compute_shadow_blockers`, and free_005's registered boxel
extents vs. the small object's real settled footprint may not coincide) —
but this is a secondary, redundant safety net; the PRIMARY, load-bearing
defect is the self-referential `blocks_view_at(occ, occ, shadow)` binding
above, which by construction can NEVER represent "occluder now blocks from
its NEW location" even when the placement-blocking check works correctly.

### A3. Consequence for "does it ever re-pick the occluder?"

No. Because the symbolic model believes the shadow is unblocked the moment
ANY relocation happens, PDDLStream never has a reason to plan a second
`pick(occluder, ...)` / `place(occluder, elsewhere, ...)` step. The plan is
always the minimal-cost `(move, sense, pick)` straight at the shadow. This
matches the user's framing ("does NOT retry picking that block") even though
the underlying trigger is not a failed grasp — in both captured runs the
occluder relocation pick/place SUCCEEDED; it's the destination-selection +
belief-update pairing that's broken, not the grasp itself, for this part of
the bug.

---

## PART B — Toppled block / never pickable again

### B1. First-hand evidence, 08-20 run (20-12-20) — the money sequence

After giving up on both orange shadows (Part A), the plan picks up
`green_object`, places `free_003` clear (`orange_object` was earlier placed
there), then at PLAN #9 (log:614-615) elects to STACK `green_object` on top
of `orange_object` as part of a place/sense sequence:

```
775-785  Executing: place ... "*** red_object PLACED at free_013! ***"
         (red_object toppled here too — see B2)
...
781-785  Executing: stack green_object on orange_object
         [#84-diag] pre-release green_object: pos=[0.0702,0.0873,0.5219]
           tilt_deg=0.08
         -> Released green_object (audit #80 verify ok; ... cube_tilt_deg=0.01)
         *** green_object STACKED on orange_object! ***
```

Green_object is now perched on top of orange_object (elevated, contact_z
should be ~0.58 for a normal top-down grasp there). The very next action is
a `pick` of `green_object` back off the stack:

```
793-797  Executing: pick
         Picking green_object from green_object...
         [#P1-diag] pick arrival green_object: ee_xy_err=3.04mm
           ee_vs_obj_xy=44.03mm ee_z=0.5781 contact_z=0.5795
         ERROR: grip verification failed for green_object — pad contacts=none
           (need both [9, 10]), pad_normal_force=0.00N. Opening gripper and
           replanning.
         IK or grip failure during pick — replanning (audit #82 / #P1 grip
           verification)
```

**This is the genuine grasp MISS from the user's premise**: `ee_vs_obj_xy=
44.03mm` — the gripper closed 4.4cm off-target (more than half the ~8cm
finger opening), both pads miss, force=0. Immediately following (contact_z
in the NEXT attempt, log:893, drops to `0.3760` — down from `0.5795` for the
elevated stack pick and `0.4472`/`0.4480` for green_object's normal
standing-on-table pick earlier in the same run, log:652/562 in the two runs
respectively):

```
891-895  Executing: pick
         [#P1-diag] pick arrival green_object: ee_xy_err=4.72mm
           ee_vs_obj_xy=2.21mm ee_z=0.3789 contact_z=0.3760
         ERROR: grip verification failed for green_object — pad contacts=[10]
           (need both [9, 10]), pad_normal_force=393.98N. ...
```

The 44mm-off first swipe evidently knocked `green_object` clean off the top
of `orange_object`; it fell back to table height and landed in a LOW,
non-upright pose (contact_z ~0.376 vs. the object's normal standing
contact_z ~0.447-0.448 — an ~7cm drop in grip height, consistent with the
box now lying on its side, matching the "contact_z ~0.376-0.380 indicates a
lying block" signature named in the task brief). Confirms `test_full_
pipeline.py:1316-1324`'s own in-code comment, which documents this EXACT
failure class as already known:

```python
# test_full_pipeline.py:1316-1324
# #P1: a failed grasp attempt can shove or topple
# the object (the descent or close physically
# touched it).  Refresh every OBJECT boxel from
# live PyBullet before replanning — otherwise the
# planner re-targets the stale pose and the same
# miss repeats until timeout (audit #83's
# stale-boxel loop, pick edition; observed on
# random-pairs seed 3: ee_vs_obj_xy ~130 mm on
# every retry against a toppled occluder).
env.update_object_positions()
refresh_object_aabbs(env, registry, viz=viz)
break
```

### B2. The position refresh works; the ORIENTATION never adapts — infinite loop

The `env.update_object_positions()` + `refresh_object_aabbs()` call after
each pick failure DOES correct the XY targeting over the next few attempts —
`ee_vs_obj_xy` shrinks from 44.03mm -> 2.21mm (log:893) -> 2.91mm (log:991)
-> 10.63mm (log:1077) -> 0.70mm (log:1173 onward), and the grip alternates
between hitting only pad [10] or only pad [9] (log:894, 992, 1078) — i.e. the
gripper is now well-centered over the object's centroid but the pads still
can't BOTH close on it. From log:1173 onward the retries become perfectly,
bit-for-bit IDENTICAL:

```
1173/1271/1367/1465/1550/1647/1745/1843:
  [#P1-diag] pick arrival green_object: ee_xy_err=0.70mm ee_vs_obj_xy=0.70mm
    ee_z=0.3771 contact_z=0.3760
  ERROR: grip verification failed for green_object — pad contacts=none
    (need both [9, 10]), pad_normal_force=0.00N. Opening gripper and
    replanning.
```

Same numbers, 8 times in a row (PLAN #14 through PLAN #21, log:1177-1847).
This is the smoking gun for the orientation gap: `sample_grasp` (streams.py:
561-610) yields exactly ONE grasp per call — fixed top-down orientation
`p.getQuaternionFromEuler([0, pi, 0])` (streams.py:591, no yaw term at all)
at a single hardcoded z-offset `_GRASP_Z_OFFSETS = [0.10]` (streams.py:561).
Given an identical object pose, every regenerated grasp/IK/contact pose is
byte-for-byte deterministic, so once the toppled object's true footprint no
longer fits under this fixed-axis pinch, NO amount of replanning can ever
produce a different (successful) attempt — it is a structurally
unrecoverable loop, not a transient failure.

**Unlike the `sense` action's 3-strike giveup (execution.py:1523-1546,
`blocked_counts` / `blocked_giveup_shadows`), there is NO strike counter or
give-up path for repeated PICK failures.** The loop only terminates when an
external wall-clock/process limit intervenes. In this run it terminated
because the LOG ITSELF STOPS MID-PLANNING-CALL:

```
1893  Iteration: 5 | ... | Attempt: 1 | Results: 109 | Depth: 1 | Success:
        False | Time: 0.600
1895  20:18:36 [INFO] root: Run finished : 2026-08-20_20-18-36
```

No `SUCCESS!` / `FAILED:` block was ever printed (report_run_outcome never
ran) — the process was killed externally (GUI window closed / Ctrl-C) after
21 replans and ~6 minutes (20:12:20 -> 20:18:36) of watching the arm swipe at
the same toppled green_object with zero progress. This is a direct,
first-hand match for "the user watched the robot fail to pick, over and
over, and gave up manually" — the GUI observation this task investigates.

### B3. Corroborating toppling event, 08-15 run — different mechanism, same signature

In the 08-15 run, `red_object` topples not from a failed grasp but during a
SUCCESSFUL place's release (audit #80's verify gate has no orientation
check):

```
776-779  Executing: place
         Placing red_object at free_013...
         [#84-diag] pre-release red_object: pos=[0.0470,-0.3400,0.3527]
           aabb=[0.0162,-0.4091,0.3250]-[0.0779,-0.2709,0.3805]
           tilt_deg=90.00
         -> Released red_object (audit #80 verify ok; fingers_open=True
           robot_link_contacts={none} non_robot_contacts=[1] bottom_z=0.3250
           expected=0.3250 err=-0.0mm lateral_drift=0.00mm
           cube_tilt_deg=90.00 finger_pos=[0.0400,0.0400])
```

`tilt_deg=90.00`, and the AABB extent is 6.2cm (x) x 13.8cm (y) x 5.5cm (z)
— a tall/narrow occluder now lying on its long side — yet `_release_and_
verify_drop` (execution.py:310-460) reports `verify ok`. The 4-signal gate
(execution.py:395-439: fingers_open, cube-bottom height, lateral-drift
stationarity, zero robot contact) never checks `cube_tilt_deg` — it's
computed and printed (execution.py:441-447, "Audit #82: cube tilt at
release... Anything >5 deg suggests an off-axis grip") purely as a
diagnostic, not a pass/fail criterion. A 90-degree toppled release is
therefore silently accepted as a normal, successful place. In this run the
overall episode gave up on `shadow_of_red_object` (3-strike, Part A
mechanism) before any subsequent action needed to re-pick the now-toppled
`red_object`, so this run doesn't show a failed re-pick directly — but B1/B2
above shows exactly what happens when a toppled object DOES need to be
picked again: an unrecoverable identical-failure loop.

---

## SUMMARY — causal chain

1. Occluder-relocation `pick`+`place` SUCCEEDS. Destination boxel is chosen
   purely by IK reachability (`compute-kin` stream), with no notion of
   "does this clear the shadow" baked into the grasp/placement choice
   itself — a second, independent "placement-blocking" pre-check exists
   (pddlstream_planner.py:305-341, 452-471) but is coarse (5x5 single
   z-slice ray grid) and misses this geometry.
2. `compute_shadow_blockers` (execution.py:166-260), re-run after every
   `place` (test_full_pipeline.py:1464), CORRECTLY re-detects via live
   raycast that the occluder still blocks the shadow from its NEW position.
3. `_build_init` (pddlstream_planner.py:439-444) discards the "new position"
   part of that information: it always emits `blocks_view_at(occluder,
   occluder, shadow)` — hardcoded to the occluder's OWN original boxel id.
   Combined with `obj_at_boxel(occluder, occluder)` disappearing the moment
   the occluder is recorded in `moved_occluders` (pddlstream_planner.py:
   406-413), the domain's derived `blocks_view` predicate (pddl/domain_
   pddlstream.pddl:99-102) becomes permanently false for this occluder/
   shadow pair — regardless of physical reality.
4. The planner therefore emits a plain `(move, sense, pick)` plan straight
   at the shadow — it never considers relocating the same blocker again,
   because symbolically nothing blocks it any more.
5. The real `sense_shadow_raycasting` call (finer 7x7 x 3-slice grid,
   execution.py:64-163) still hits the occluder at its true position and
   returns `still_blocked`, unchanged, on every attempt (nothing in the
   scene differs between attempts). After 3 identical strikes, audit #21's
   give-up (execution.py:1531-1542) marks the shadow `not_here` even though
   it was never actually observed empty — exactly the symptom reported
   ("sense keeps reporting still_blocked... 3-strike giveup... moves to
   another block").
6. SEPARATELY: a grasp MISS (fixed single top-down grasp, streams.py:561,
   591 — no yaw, one z-offset) that lands off-center by several cm can
   physically knock a tall/narrow object off a perch or its base, toppling
   it (confirmed via `cube_tilt_deg`/`tilt_deg` diagnostics in both runs:
   90.00 deg release-time topple in the 08-15 run; a knocked-off-stack
   topple inferred from the ~7cm contact_z drop in the 08-20 run). The
   position-refresh added for audit #83 (test_full_pipeline.py:1325-1326)
   fixes XY re-targeting on subsequent attempts, but `sample_grasp` never
   varies ORIENTATION — so once the object's short axis no longer aligns
   with the gripper's fixed world-frame pinch axis, EVERY subsequent
   attempt is deterministically identical and fails identically. Unlike
   `sense`, `pick` failures have no strike-counter/give-up path
   (execution.py:1310-1327 in the pick-failure branch just breaks to
   replan, forever) — the loop only ends via an external wall-clock cutoff
   or (as directly observed in run 20-12-20) the user killing the GUI
   process after 21 replans / ~6 minutes of identical failures.

---

## PROPOSED FIX — two tiers

### Tier 1 — minimal near-term mitigation (both problems)

**(1a) Fix the `blocks_view_at` fact keying (Part A root cause).**
This is a small, surgical, ROOT-CAUSE fix, not a workaround — `compute_
shadow_blockers` is already computing the right answer; only its
translation into PDDL facts is wrong.

  File: `pddlstream_planner.py`, `_build_init`, lines 439-444.
  Change the self-referential pairing to use the occluder's CURRENT boxel
  (from the `moved_occluders` dict already threaded into `_build_init`,
  see its signature at line 347) instead of hardcoding the occluder's own
  id:

  ```python
  if self.shadow_occluder_map:
      for shadow_id, blocker_ids in self.shadow_occluder_map.items():
          if isinstance(blocker_ids, str):
              blocker_ids = [blocker_ids]
          for occluder_id in blocker_ids:
              current_boxel = moved_occluders.get(occluder_id, occluder_id)
              init.append(('blocks_view_at', occluder_id, current_boxel, shadow_id))
  ```

  This makes `blocks_view_at` track wherever `compute_shadow_blockers`
  (ground truth, live raycast) says the occluder actually is, so `blocks_
  view` derives correctly whether the occluder is at its original spot or
  its relocated one. The `_build_init` diagnostic at lines 673-684 should
  get the same `moved_occluders`-aware pairing so the "[#76-diag] shadows
  (blockers=N)" printout stops lying to the log. With this fix, a
  still-blocking relocation naturally produces a plan that moves the SAME
  occluder again (to a DIFFERENT free cell) instead of walking straight
  into a doomed sense — no giveup-counter workaround needed, because the
  model would never have believed the shadow was clear in the first place.
  (Residual risk: if EVERY reachable free cell keeps re-blocking the same
  shadow, the planner could still loop across different destinations
  forever; a per-shadow relocation-attempt cap alongside this fix, mirroring
  the existing `blocked_counts` pattern in execution.py:1523-1546, is a
  cheap belt-and-suspenders addition — but strictly secondary to 1a.)

**(1b) Give `pick` failures a strike counter / give-up path (Part B
symptom).** `sense` already has one (execution.py:1523-1546,
`blocked_counts` / `blocked_giveup_shadows` / audit #21); `pick` has none
(test_full_pipeline.py:1310-1327 just breaks to replan unconditionally on
`result[0] is None`). Add an analogous per-object failed-pick counter
(e.g. `pick_fail_counts[obj_str]`) incremented in that branch; after N
(3, mirroring audit #21) IDENTICAL-looking failures for the same object
(compare `ee_vs_obj_xy` / `pad contacts` signature, or simply count
attempts regardless), mark that object's target/goal as ungraspable-for-now
(symbolically: emit an `obj_at_boxel_KIF`-style "known stuck" fact, or drop
it from `boxel_fits` for one replan cycle) so the planner is forced onto a
different branch instead of silently regenerating the same doomed
`(move, pick)` step. This does not fix the underlying grasp limitation
(that's Tier 2) but converts an infinite silent loop into a visible,
bounded failure the run/eval harness can report and a human/eval script can
act on — parallel in spirit to how audit #21 already bounds `sense`.

**(1c) Optional, cheap: make the audit-#80 release-verify gate flag large
tilt.** `_release_and_verify_drop` (execution.py:310-460) already computes
`cube_tilt_deg` (line 446-447) but only prints it. Adding a `tilt_ok =
cube_tilt_deg <= threshold` (e.g. 15-20 deg) to the same gate that already
checks `fingers_open`/`height_ok`/`stationary` would at minimum SURFACE a
topple-on-release event as a distinguishable outcome (could set a "toppled"
flag the dispatcher logs/reports) rather than silently declaring `verify
ok`. It would not by itself prevent toppling or fix the grasp, but pairs
naturally with Tier 2's shape-aware sampler by giving it a trigger signal.

### Tier 2 — shape of the real grasp sampler (#P1 step (4) / PAPER_AUDIT.txt
item (l), streams.py:561-610)

Replace the single hardcoded `_GRASP_Z_OFFSETS = [0.10]` / fixed
`[0, pi, 0]` orientation with a small, cheap, axis-aligned grasp candidate
set, validated the same way TAMPURA's top-grasp library is (close-until-
collision / finger-width fit check at planning time), NOT a full antipodal
sampler — proportionate to the tabletop/box-only scene:

  1. Insertion point: `streams.py`, replace the body of `sample_grasp`
     (lines 561-610). Read the object's CURRENT live AABB (already
     available the same way `execute_pick` reads it, execution.py:696-699:
     `p.getAABB(obj_id)` -> `aabb_max - aabb_min` per axis) instead of
     assuming a canonical upright footprint.
  2. Yaw options: for each object, compute the two horizontal footprint
     extents (`ext_x`, `ext_y`). Yield TWO orientation candidates instead
     of one: yaw=0 (pads close along Y, spanning `ext_x`) and yaw=90 deg
     (pads close along X, spanning `ext_y`) — i.e. `p.getQuaternionFromEuler
     ([0, pi, yaw])` for `yaw in (0, pi/2)`. This directly targets the
     toppled-block case: whichever yaw makes the SHORTER extent the pinch
     span is the one that can physically close within the ~0.08 m finger
     opening; the other is rejected (see validation below). This is exactly
     "yaw options aligned to the object's AABB axes" per the task brief.
  3. Width validation before yielding (mirrors TAMPURA's close-until-
     collision check, cheaply, since PyBullet AABBs are already available
     here): reject a yaw candidate whose spanned extent exceeds the max
     finger opening (`FINGER_JOINTS` max travel, robot_utils.py — reuse the
     same 0.038 m per-finger-max-open constant `_release_and_verify_drop`
     already uses at execution.py:400, i.e. reject span > ~0.076-0.08 m
     total). This turns a currently-silent, eventually-infinite failure
     (Part B2) into a stream that simply doesn't certify a `Grasp` for a
     geometrically-impossible orientation, which PDDLStream's normal
     backtracking already handles.
  4. Z-offsets: keep `_GRASP_Z_OFFSETS = [0.10]` as one option but consider
     adding a slightly lower option (e.g. 0.06-0.08 m) for short/toppled
     objects, mirroring the existing `contact_z` clamp logic in
     `execute_pick` (execution.py:701-705, `_GRASP_MARGIN_FROM_TOP` /
     `min_contact_z`) so the sampler and the executor agree on reachable
     contact heights for non-canonical (lying-down) object poses.
  5. `test_boxel_fits` / `test_target_can_hide_in_shadow` (streams.py,
     called from pddlstream_planner.py:527-534) already gates `boxel_fits`
     on object EXTENTS relative to a candidate boxel — the new yaw-aware
     `sample_grasp` should stay consistent with whatever extents that
     stream already reads, so grasp-feasibility and placement-feasibility
     don't diverge.

  This keeps the change scoped to `streams.py` (the sampler) plus a small
  constant/threshold reuse from `robot_utils.py`/`execution.py`, and does
  not require touching `execute_pick`'s finger-pad contact verification
  (execution.py:618-...) — that already correctly rejects a bad
  orientation via `pad contacts=none`/partial; the sampler fix's job is to
  stop OFFERING orientations that are geometrically doomed in the first
  place, and to offer at least one that isn't, for a toppled object.
