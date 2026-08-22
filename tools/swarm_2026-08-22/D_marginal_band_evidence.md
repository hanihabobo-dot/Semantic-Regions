# Agent D — F12/I4 Marginal-Band Evidence Sweep

Read-only forensics. All numbers below are reproducible from
`tools/swarm_2026-08-22/D_marginal_band_sweep.py` (parser) and its outputs
`D_primary_sweep_results.json` / `D_primary_incidents_readable.txt`
(today's `logs/run_2026-08-22_*`, 159 runs) and
`D_secondary_sweep_results.json` / `D_secondary_incidents_readable.txt`
(`eval_results/sweep_full_2026-05-28/cells`, 1478 runs, pre-F11 code —
kept separate, never mixed into the primary quantification). Follow-up
queries `D_query_followup{1..6}.py` are also in this directory.

Thresholds at their source (CONFIRMED by direct read):
- `PLACEMENT_EGREGIOUS_BLOCKED_FRACTION = 0.15` — pddlstream_planner.py:61
- `SENSE_MARGINAL_BLOCKED_FRACTION = 0.05` — perception.py:37 (imported at
  execution.py:45, applied at execution.py:228,382,388,1683 and inside
  `compute_shadow_blockers`'s "Shadow blockers (audit #78):" census print)

## 1. The signature this sweep detects

For every `*** X PLACED at Y! ***` line, the parser checks whether the
**immediately preceding** "Shadow blockers (audit #78):" census block
already lists the just-placed `X` as a blocker of some shadow. That is the
observable trace of a placement that cleared whatever prospective gate was
active (today: the 0.15 egregious-volume test, `pddlstream_planner.py:462`)
being re-flagged by the very next post-place census at the 0.05 margin —
i.e. a placement that fell in the open `(0.05, 0.15)` band, or that the
prospective test never modeled at all (see §5).

## 2. Headline numbers — PRIMARY corpus (today, all regimes)

| | value |
|---|---|
| runs parsed | 159 |
| total `place` actions | 258 |
| runs with ≥1 incident | 52 |
| total incidents (immediate re-block) | **57** |
| incidents where the run ended right there (no later `planner.plan()` call, FAILED) | **23** |
| incidents whose run ultimately SUCCEEDED anyway (absorbed by replanning) | 34 |
| incidents where the re-blocked shadow WAS the oracle's true hiding place | **17** |

(CONFIRMED by direct count in `D_query_followup6.py` output — every one of
the 57 incidents falls cleanly into "run SUCCEEDED" (34) or "this incident
is the terminal event of a FAILED run" (23); zero cases where the run
failed for some *other*, later reason. `episode_ended_by_this` is a
line-count heuristic — see §7 Caveats.)

Of the 17 incidents that hit the oracle's true hiding shadow, **15/17
(88%)** ended the episode; of the 40 that hit a non-target shadow, only
**8/40 (20%)** did. Re-blocking the shadow the target is actually hiding in
is by far the more lethal case — mechanically expected, since sensing that
shadow is then unavoidable and its blocker-relocation is exactly the F7
binding-death machinery (PAPER_AUDIT.txt F7, and F11 line 903).

## 3. Regime split: did the 0.15 gate (commit c0fb6ec) change the rate?

CONFIRMED from `git log`: `c0fb6ec` "F11: per-object egregious placement-
blocking triples at 0.15" lands 2026-08-22 15:40:09; before it the working
tree had no per-object volume test at all (regime A, most of the day) or a
brief stricter 0.05 test (335ddc1, 12:22:42–12:42:53, reverted at
12:42:53 — zero runs in this log corpus fall inside that ~20 min window).
The sweep classifies every run's regime by its directory timestamp against
15:40:09.

| regime | runs | placements | immediate re-blocks | rate |
|---|---|---|---|---|
| A/B/C (pre-fix / no gate, most of the day) | 131 | 227 | 51 | 22.5% |
| D (current, 0.15 egregious gate) | 28 | 31 | 6 | 19.4% |

The 0.15 gate produced only a modest drop (22.5% → 19.4%), consistent with
PAPER_AUDIT.txt F11's own measurement ("median seed gains 3 triples...
vs median 7... at the census margin" — the 0.15 gate structurally leaves
most of the marginal band open by design, it was tuned for planning-cost,
not for closing this band). One caveat lowers confidence in the regime-D
rate specifically: n=31 placements is a small sample and is itself
dominated by repeat re-runs of a few seeds during same-day smoke testing
(§6) — 19.4% should be read as "consistent with, not lower than, the
pre-fix rate," not as a precise post-fix estimate.

## 4. Regime-D incident catalog (post-fix, the regime that matters for "does
the residual still fire today") — full detail, all CONFIRMED by direct log
read

| run | line | placed@boxel | reblocks | true hiding place? | episode ended by this? | outcome |
|---|---|---|---|---|---|---|
| 15-49-51 | 252 | red_object@free_013 | shadow_of_orange_object | No | No | SUCCESS |
| 15-58-09 | 148 | orange_object@free_005 | shadow_of_red_object | **Yes** | **Yes** | FAILED (F7 binding death, [F7-diag], 2 unsearched shadows) |
| 15-59-17 | 271 | red_object@free_013 | shadow_of_cyan_object | n/a (find-and-tray-stack, no oracle) | No | SUCCESS |
| 17-14-10 | 456 | red_object@free_011 | shadow_of_orange_object | No | **Yes** | FAILED (F7 binding death, 1 unsearched shadow) |
| 17-50-31 | 324 | orange_object@free_005 | shadow_of_red_object | **Yes** | **Yes** | FAILED (F7 binding death, 1 unsearched shadow) |
| 18-20-23 | 322 | orange_object@free_005 | shadow_of_red_object | **Yes** | **Yes** | FAILED (F7 binding death, 1 unsearched shadow) |

Every one of these 6 incidents was directly re-read from its log file
(census line + the immediately following `*** X PLACED ***` line) to
confirm the parser's match — CONFIRMED, not just JSON-trusted. Example,
run 17-14-10 (the run cited in the task brief), lines 450–456:

```
450:  Executing: place
451:    Placing red_object at free_011...
452:    [#84-diag] pre-release red_object: pos=[0.2039,-0.0019,0.3951] ...
453:    -> Released red_object (audit #80 verify ok; ...)
454:  Shadow blockers (audit #78):
455:    shadow_of_orange_object blocked by: ['red_object']
456:    *** red_object PLACED at free_011! ***
```

**All 6 regime-D incidents also carry zero `[F11-diag]` lines anywhere in
their run's log** (grep-verified per run) — meaning the 0.15 egregious-
volume test never even fired a candidate triple in these episodes; the
placements that caused the reblock were never close to the 15% line, they
simply weren't modeled by the prospective test's chosen shadow/cell/class
combinations. This directly confirms the incidents sit in the open
`(SENSE_MARGINAL_BLOCKED_FRACTION, PLACEMENT_EGREGIOUS_BLOCKED_FRACTION)`
band the task asked about.

## 5. The three runs the task brief names, individually

**run_2026-08-22_17-14-10** (the run under primary investigation): line 455
CONFIRMED verbatim above. `red_object` placed at `free_011` (chosen by the
plan specifically to vacate `shadow_of_red_object`, its own former spot —
Action plan at log line 413: `place(red_object, free_011, ...)` then
`move(..., shadow_of_red_object, ...)`, `sense(blue_object,
shadow_of_red_object)`) instead re-blocks the unrelated
`shadow_of_orange_object`. `shadow_of_orange_object` is not the target's
hiding place (oracle says `shadow_of_red_object`), so this specific
incident is *not* the one that kills the episode directly, but the run
still ends in the F7 binding-death class (already established by the main
loop) after the 8th plan.

**run_2026-08-22_15-58-09**: PAPER_AUDIT.txt F12 (line 1021-1022) already
cites this run alongside 15-25-35. CONFIRMED: `orange_object` placed at
`free_005` (plan at log line 100: `pick(orange_object,...)`,
`place(orange_object, free_005,...)`, `sense(blue_object,
shadow_of_orange_object,...)` — red_object is **never touched** by this
plan) re-blocks `shadow_of_red_object`, which IS the oracle's true hiding
place. Episode ends in the disclosed F7 binding-death class.

**run_2026-08-22_15-25-35**: cited in PAPER_AUDIT.txt F11's own "RESIDUAL"
paragraph (line 955-961) as the fix's own live repro, with an offline
re-measurement (`tools/_f11_census_check.py`) of **12.2%** blocked
fraction for `orange_object@free_005` against `shadow_of_red_object`'s
worst slice — squarely inside the 5–15% band. This sweep's parser
independently reproduces the same incident from the log text alone (line
259: `orange_object@free_005` → `shadow_of_red_object`, oracle match,
episode-ending). Timestamp note: 15:25:35 predates the `c0fb6ec` commit
(15:40:09) by ~15 min, so the automatic regime classifier labels it
"A/B/C"; PAPER_AUDIT.txt's own text says this run used the fixed
working-tree code before the commit landed. Treated as regime-D-equivalent
for interpretation, flagged separately rather than silently reclassified.

## 6. The seed-0 signature repeats identically across BOTH regimes — direct
evidence the 0.15 fix did not close this gap

The single most-reproduced incident in the entire primary corpus:
`orange_object` placed at `free_005`, re-blocking `shadow_of_red_object`
(the seed-0 scene's true target hiding place), episode always ends. It
recurs **7 times**, spanning the fix boundary:

| run | regime | ended? |
|---|---|---|
| 11-38-37 | pre-fix | Yes |
| 12-09-28 | pre-fix (the *original* F11 discovery run, PAPER_AUDIT.txt F11 line 894) | Yes |
| 12-28-23 | pre-fix | Yes |
| 15-25-35 | fix-code, pre-commit (see §5) | Yes |
| 15-58-09 | **post-fix (0.15 gate live)** | Yes |
| 17-50-31 | **post-fix (0.15 gate live)** | Yes |
| 18-20-23 | **post-fix (0.15 gate live)** | Yes |

CONFIRMED (`D_query_followup5.py`): all 7 are seed 0, goal `holding`, and
all 7 end the episode. This is the strongest evidence in the corpus that
the 0.15 threshold is not the lever that closes this band — the exact
scenario that motivated F11 recurs unchanged after F11 shipped, exactly as
PAPER_AUDIT.txt's own "RESIDUAL (accepted, by design)" note predicts (line
955-963: "Closing the band = re-running the measured 0.05 regression; the
actual lever is F7").

Caveat: this determinism means the "57 incidents" / "17 oracle-hits" counts
above are **not 57/17 independent trials**. A handful of seeds (0, 3, 5, 7,
9, 10, 11, 13, 16, 17, 346043753, 1013818839, 1155324522, 343879192) were
re-run many times during the same-day fix/revert/re-fix cycle visible in
git log §3, and several of those reruns reproduce the identical geometric
incident. Treat the incident *rate per placement* (22.5% pre-fix, 19.4%
post-fix) as the informative number; treat "57 total incidents" as
"repeated observations of perhaps a dozen distinct underlying scene/plan
interactions," not a sample of 57 independent scenes.

## 7. Context: self-shadow vs cross-object, and the secondary (pre-F11) corpus

Primary corpus: of 57 reblocks, only 7 are the placed object re-blocking a
shadow bearing *its own* name (e.g. `orange_object` re-blocking
`shadow_of_orange_object`); 51 are cross-object (e.g. `red_object`
re-blocking `shadow_of_orange_object`). Every regime-D incident in §4 is
cross-object.

Secondary corpus (`eval_results/sweep_full_2026-05-28`, 1478 cell-runs,
older code with **no** `PLACEMENT_EGREGIOUS_BLOCKED_FRACTION` gate at all —
only the free-cell-AABB pair test): 1934 placements, 1801 immediate
re-blocks (93%!), 333 episode-ending, 352 hitting the oracle shadow. This
is a different code regime and is not mixed into the primary
quantification above, but it is useful context: it shows the *pair* test
alone (no per-object volume test whatsoever) leaves the band wide open —
93% of placements are immediately re-flagged — which is the situation F11
was built to improve on, and against which even the modest 22.5%→19.4%
primary-corpus drop (§3) is a real, if partial, improvement.

## 8. PAPER_AUDIT.txt cross-reference (read directly, line numbers exact)

- **F11** (line 892-969): `[DONE]`. Ships the 0.15 egregious-volume gate
  (line 926-934, "the LOOSER PLACEMENT_EGREGIOUS_BLOCKED_FRACTION = 0.15
  instead of the census margin 0.05"), chosen by measurement over the 20
  A/B eval seeds because 0.05 (335ddc1, first implementation) regressed
  planning time (8.3s→15.8s mean) and success (11/20 gated). The entry's
  own **RESIDUAL** paragraph (line 955-969) explicitly names this exact
  5-15% gap as "accepted, by design," cites run 15-25-35 with the 12.2%
  measurement, and states plainly: "Closing the band = re-running the
  measured 0.05 regression; the actual lever is F7 (and see F12 below)."
- **F12** (line 1020-1040): `[OPEN, parked with F6]`. Notes that
  `view_clear`'s stratified-negation over `blocks_view` makes ANY
  census-listed blocker (>5% of some slice) absolutely un-sensable in
  planning, citing runs 15-25-35 and 15-58-09 (both reproduced above),
  and proposes either a "usefully observable" `view_clear` criterion above
  the census margin, or letting `sense` ground on marginally blocked
  shadows at a cost penalty. Explicitly deferred, evaluated together with
  F6.
- **[STEP (3)]** (line 819-890): the render-based sense/census rewrite
  landed the same day; §(3c) (line 870-890) is the lost-object belief
  update the task brief's background facts describe for run 17-14-10
  (orange_object's stale boxel). Not itself about the marginal band, but
  establishes that the census this report analyzes is now a single
  TinyRenderer depth+seg observation shared with sense (line 839-843), not
  a separate ray-cast pass — i.e. the 5% margin and the 0.15 gate are
  compared against the *same* rendered geometry, so the gap between them
  is a genuine criterion mismatch, not a measurement-channel mismatch.

## 9. The user's narrower candidate: "triple the prospective census-margin
volume test [0.05 × 3 = 0.15, i.e. the existing value] ONLY for shadows
whose blockers the current plan relocates"

This is not a new threshold value (3 × 0.05 = 0.15 is exactly today's
`PLACEMENT_EGREGIOUS_BLOCKED_FRACTION`); it is a proposal to **narrow the
scope** of the existing 0.15 test from "every free-cell × shadow ×
object-class combination not already pair-flagged" (today's blanket
initial-state generation, PAPER_AUDIT.txt F11 line 926-934) down to only
those shadows whose *current* blocker the plan is actively relocating —
presumably to buy back planning-cost budget for tightening the survivors
to something stricter than 0.15, or simply to make the check cheaper.

**Direct test against this session's regime-D evidence (the only evidence
that reflects the current, post-fix code): 0 of 6 incidents (§4) would
have been caught by this narrower criterion**, verified by reading each
incident's actual Action plan:

- **15-58-09 / 17-50-31 / 18-20-23** (the seed-0 signature, §6): the
  executing plan is `pick(orange_object) → place(orange_object,
  free_005) → sense(blue_object, shadow_of_orange_object)` (log line 100,
  15-58-09). `red_object`, whose presence is what blocks
  `shadow_of_red_object`, is **never touched** by this plan — the plan's
  own goal is to clear a *different* shadow (its own). The narrowed
  criterion, scoped to "shadows whose blockers this plan relocates," would
  not test `shadow_of_red_object` at all, and this is precisely the
  pattern that repeats 7 times and always ends the episode.
- **17-14-10**: plan is `pick(red_object) → place(red_object, free_011) →
  sense(blue_object, shadow_of_red_object)` (log line 413). `orange_object`
  (whatever currently blocks `shadow_of_orange_object`) is never touched.
  Same structural mismatch.
- **15-49-51**: plan is `pick(red_object) → place(red_object, free_013) →
  sense(blue_object, shadow_of_red_object)` (log line 205).
  `orange_object` is untouched; the incident re-blocks
  `shadow_of_orange_object`.

In every regime-D incident, the re-blocked shadow's own blocker is
**not** an object the current plan relocates — the collision is *collateral*:
a placement made to free up one shadow ends up standing close enough to
occlude a completely different, untouched shadow. This is the dominant
failure shape in the data (also true of most of the 51 cross-object
pre-fix incidents, §7), and it is structurally invisible to a criterion
keyed on "the shadow this plan is trying to clear."

**What an A/B measurement of this candidate would have to show to beat
the status quo**, given the above:
1. First, resolve the scope ambiguity this evidence exposes: if scoped
   literally to "the blocked shadow's own occupant is being relocated,"
   the candidate's real-world hit rate on this corpus is 0/6 — it would
   need a broader trigger (e.g. "any shadow whose class-based
   `boxel_fits` corridor lies within some radius of the cell being placed
   into," or simply "every shadow the *remaining* plan still needs to
   sense," which is closer to what F12 already proposes) before an A/B
   trial is even worth running.
2. Once scoped, it would need to catch a materially larger fraction of
   the 6 (or, honestly, ~4 distinct) regime-D incidents than 0/6 without
   reproducing the 335ddc1 regression (planning time 8.3s→15.8s mean,
   gated success 20/20→11/20, PAPER_AUDIT.txt F11 line 914-925) —
   i.e. it needs to be cheap specifically because it's narrow, which is
   the intent, but "narrow by shadow-whose-blocker-is-relocated" is
   demonstrably too narrow on this evidence.
3. It would need to be measured against the same 20 A/B eval seeds
   PAPER_AUDIT.txt F11 used (`tools/_probe_f11_volume.py` is the existing
   harness), not just today's seed-0/seed-3/seed-346043753/etc. smoke
   corpus, since §6 shows this corpus is dominated by a handful of
   repeated seeds.

## 10. Recommendation

**Do not change any threshold now.** The evidence supports three
conclusions, all already reflected in PAPER_AUDIT.txt's own text, plus one
new negative finding from this sweep:

1. The 5-15% marginal band is real and still fires post-fix (6 regime-D
   incidents, 3 of them the literal 12.2%-measured seed-0 repro,
   recurring identically before and after the 0.15 gate landed) —
   CONFIRMED, not disputed.
2. Tightening the global threshold (335ddc1's 0.05 attempt) already has a
   measured regression on record (planning time doubled, gated success
   collapsed 20/20→11/20) — CONFIRMED by PAPER_AUDIT.txt F11's own numbers,
   independently re-cited here. Any new blanket-threshold proposal
   inherits the burden of beating that same regression.
3. The user's narrower "relocated-blocker" candidate is not a threshold
   change (3×0.05 already equals today's value) but a scoping change, and
   **this session's regime-D evidence shows it would have fired on 0/6**
   of the incidents actually observed after the fix, because every one is
   collateral (a placement freeing one shadow occludes a different,
   untouched one) rather than a relocation of the blocked shadow's own
   occupant — HYPOTHESIS-turned-CONFIRMED-negative on this specific
   corpus, not yet measured on the full 20-seed A/B harness.

`evidence_sufficient = false`: this sweep is sufficient to confirm the band
exists, is unchanged by F11's 0.15 fix, and to rule out (on today's
evidence) the literal form of the user's narrower candidate — but it is
not sufficient to select or size a replacement criterion, because (a) the
regime-D sample (n=6 incidents / 31 placements, dominated by one repeated
seed) is too small and too seed-correlated to fit a new threshold to, and
(b) no version of a "narrower, relocation-scoped" test has been run at all
— it needs its scope redefined per §9 and then measured on the 20-seed A/B
harness before any numeric commitment. PAPER_AUDIT.txt F11's own
conclusion — "the actual lever is F7 (and see F12 below)" — is consistent
with everything found here: 23/57 (40%) of primary-corpus reblocks, and
4/6 of the post-fix ones, are absorbed only when F7's binding-death class
is itself fixed; no census-margin or egregious-volume threshold change
touches that half of the picture.

## Appendix: files in this directory

- `D_marginal_band_sweep.py` — the parser (read-only, log-text regex based)
- `D_primary_sweep_results.json`, `D_primary_incidents_readable.txt` —
  full per-run and flattened incident dumps, today's 159 runs
- `D_secondary_sweep_results.json`, `D_secondary_incidents_readable.txt` —
  same for the 1478-cell 2026-05-28 sweep (pre-F11 code)
- `D_query_followup{1..6}.py` — the specific breakdowns cited by section
  above (regime split, oracle-shadow hits, seed-0 signature count,
  self-shadow/cross-shadow split, episode-ending breakdown)
- `D_sweep_stdout.txt` — captured stdout of the main sweep re-run
