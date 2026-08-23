# #P1 field-regression swarm — final summary (2026-08-22)

Branch `p1-real-grasp-perception`, base `7cbaffd`, head `74c53a7` (pushed to
origin + github; wiki `668b687`).

Source run under investigation: `logs/run_2026-08-22_17-14-10/` (user GUI,
holding seed 0, target blue_object hidden in shadow_of_red_object, FAILED in
the F7 binding-death class after 8 plans).

## What shipped

| commit | finding | status |
|---|---|---|
| `2056f04` | **F17** headless world telemetry (`telemetry.py`) | DONE |
| `e6afa7d` | **F14** velocity-bounded executor | DONE |
| `13c79a7` | **F15(a)** name the unlocalizable interceptors | DONE |
| `b1a742b` | **F17 follow-up** FLING/GRIP_LOST false positives on release | DONE |
| `68a6207` | **F15(b)(c)** localize-from-pixels + park unresolved; **F16** full-registry sweep | DONE |
| `74c53a7` | F16 probe, audit entries, these reports | DONE |

## The five field issues, as they actually resolved

**I1 violent throw → F14. CONFIRMED, fixed, and wider than reported.**
`_smooth_path` (SMOOTH_ATTEMPTS=75) splices several `RRT_STEP_SIZE`=0.2 rad
tree edges into one edge, certified by a collision check that never bounds
edge length; the executor then ran it in a fixed 30 steps = **9.16 rad/s**,
4.2x joint 2's 2.175 rad/s limit (`C_motion_deltas.md`, 7 RNG realizations).
F17 telemetry showed ordinary LINEAR moves doing the same on their first hop
(**17.7 rad/s**, EE at 4.4 m/s), so the bound went in the executor, not the
smoother. After: peak |qd| **≤2.57 rad/s**, zero GRIP_LOST / OFF_SUPPORT.

**I2+I3 unlocalizable stall → F15. The brief's suspected cause did not hold.**
The thrown-orange-sliver hypothesis is a disclosed NEGATIVE: 347 probe poses
found none that renders <6 px while intercepting a sense endpoint
(`A_timeline_and_interceptor.md`), and blue renders 643 px so it
short-circuits to `found_target`. What actually retired the target's fragment
(`B_sense_code_path.md`):
  * the **3-strike budget is shared** — `blocked_counts` is incremented by
    both `still_blocked` and the unlocalizable branch, so shadow_of_red died
    on 1 blocked + 2 unresolvable strikes, never three of the same
    observation;
  * both giveups wrote `not_here`, i.e. "target absent", on observations that
    were evidence of **occupancy** or of **no view at all**. The
    `still_blocked` branch's own message admitted "Shadow is NOT observed
    empty" while doing it.
Fixed: separate strike namespaces, `min_pixels=1` localization with a
`NOMINAL_HIDDEN_EXTENTS` prior, and a third belief status `unresolved` that
withholds the fragment from the planner (so episodes still terminate) without
claiming absence, disclosed in the run outcome.

**I4 marginal band → F12. Measured; NOTHING CHANGED, on purpose.**
159 runs / 258 placements: 57 immediate re-blocks; re-blocking the target's
own shadow ended the episode 15/17 times vs 8/40 otherwise. The 0.15 gate
barely moved the rate (22.5% → 19.4%) and the seed-0 signature reproduces 7
times across the fix boundary. The work order's narrower "relocated-blocker"
candidate measures **negative**: 0 of 6 post-gate incidents, because all are
collateral (freeing one shadow occludes a different, untouched one).
`D_marginal_band_evidence.md`; thresholds left alone per F11's revert history.

**I5 opportunistic sense → F16. DONE and it mattered more than expected.**
`sweep_all_fragments` classifies every registry fragment per sense render and
runs on three branches, including the blocked and unresolved paths that used
to discard a whole render. Verified directly by `tools/_probe_f16_sweep.py`
(cross-caster empty fragment removed, occupied fragment kept). Field effect:
find-and-tray-stack 999 went from `no_plan_binding_death` in every one of
today's earlier runs (and 671 s / 1812 s single plan calls) to **SUCCESS in 5
plans at 2-5 s each**, with 5 fragments cleared by the sweep.

## New findings opened

* **F15.1** — the thrown object was never retired as LOST across 8 plans
  ("keeping last estimate" 7x). Offline reconstruction without the arm shows
  its believed region renders empty, so transient ARM occlusion at the
  refresh moments is defeating the 3c check. Census and object registry
  disagreed all episode.
* **F18** — found BY the telemetry on the first post-fix tray run: a transit
  carrying cyan knocked **orange flat (tilt 90°, DISTURBED x44)** and the
  episode still reported SUCCESS. F10 fixed the held-cargo *pose*; this is
  either executed-vs-validated motion divergence or the arm's own links.
  Telemetry's DISTURBED event is already the world-integrity detector #P2
  asks for; wiring it into the run outcome is the next step.

## Verification battery (post-F15/F16, `battery2.txt`)

holding seed 0 ×2 SUCCESS (zero telemetry anomalies) · stack h=2 SUCCESS ·
find-and-tray-stack 999 SUCCESS · F5 diag PASS · perception probe PASS ·
lost-object probe PASS · render-sense probe PASS (97.91% endpoint agreement,
0 outcome mismatches, 0 found-chain failures) · F16 sweep probe PASS.

## Honest caveats

* F14 roughly doubles an episode's *simulated motion* time — a real Panda
  needs 1.05 s for a 2.29 rad joint move; the old schedule did it in 0.125 s.
  Planning time, the metric CB#113 reports, is untouched, and `eval_runner`
  passes `--no-telemetry` so sweep wall-clock is unaffected by F17.
* The F15 unlocalizable branch is RARE headless (0 trips in 4 consecutive
  seed-0 runs), so (b) is lightly exercised in the field; (c) is the
  guarantee that matters when it does fire.
* Agent A could not reproduce the exact interceptor pose. Recorded as a
  negative result, not smoothed over.
* Step counts and search behaviour changed (F16 removes fragments earlier),
  so CB#113 re-baselines.

## Correction (2026-08-23) — the real interceptor was the GUI overlay (F19)

The user's next GUI run (11-25-45) tripped the guard again and the new
F15-diag NAMED the interceptors: seg ids 10 and 12 (348-1197 px), outside
the 0-6 scene-body range. They are the boxel visualizer's own phantom AABB
bodies: visual-only multibodies that rayTestBatch ignores (no collision
shape) but TinyRenderer renders — so step (3)'s switch to the rendered
observation put the debug overlay INTO the observation, GUI runs only.
A fragment's own translucent box stood in front of its own sense endpoints
(found_target could never fire with the target in plain sight through the
overlay), and an object's overlay hid the object from the refresh render.

This CORRECTS two claims above: agent A's orange-by-elimination hypothesis
is refuted (only scene bodies were considered — the 347-pose negative sweep
was the fingerprint of a non-scene cause), and F15.1's arm-occlusion
hypothesis is superseded (the overlay, not the arm, gated off the 3c
retirement; resolved by F19).

Fix (F19, commit on 2026-08-23): every phantom registers its home position;
`BoxelTestEnv.detect_objects` — the single chokepoint for all perception
renders — conceals the overlay (teleport 100 m down, try/finally) for
exactly the duration of the camera pass. Verified by
`tools/_probe_viz_observation.py`: raw render shows 6137/891 phantom px
with the covered object reduced to 1 px; the fixed observation has zero
phantom pixels, detects the covered object at 892 px, classifies the
phantom-covered fragment clear_but_empty, and restores the phantoms.
