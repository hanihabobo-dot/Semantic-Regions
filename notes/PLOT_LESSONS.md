# PLOT_LESSONS — `eval_results/sweep_anytime/`

Plot-by-plot notes feeding thesis #142-#145.

Data source: 2026-05-20 sweep, ~94% complete (`CODEBASE_AUDIT.txt` #93).
Three goals (`holding`, `stack`, `find-and-tray-stack`), three variants
(`semantic`, `semantic+mbs0.05`, `uniform`), ~300 seeds per (goal, variant).
Anytime sweep with a wall-clock budget per call.

Variants:
- **semantic** — adaptive object/shadow/free Boxels; free-space leaf size
  set by the largest object's footprint (`auto_cell` ~6-9 cm).
- **semantic+mbs0.05** — same as semantic but with the free-space leaf
  floor forced to 5 cm.
- **uniform** — uniform voxel grid over the workspace; cell size auto-set
  to the largest object's footprint (same `auto_cell` as semantic, since
  finer cells break placement).

Skipped: `_pre_fix_99/` (archived snapshot), `plots_preliminary/` (early
consolidation, superseded).


## Cross-goal plots

### `solved_vs_time.png` / `solved_vs_time_linear.png` (anytime curves)
Cumulative solve rate vs wall-clock budget, per goal, per variant.
Headline final solve rates:
- find-and-tray-stack: semantic **119/299 (39.8%)**, mbs0.05 99/300 (33.0%), uniform 4/300 (1.3%).
- holding: semantic 127/300 (42.3%), mbs0.05 **139/300 (46.3%)**, uniform 100/300 (33.3%).
- stack: semantic 184/300 (61.3%), mbs0.05 184/300 (61.3%), uniform 118/301 (39.2%).

Anytime shape:
- Almost all solves happen below ~100 s of wall-clock. Curves are flat past
  ~200 s on every goal (linear plot confirms). The "anytime" budget beyond
  100 s buys very little.
- Semantic and mbs0.05 ramp **identically** on stack (curves overlap).
- On holding, mbs0.05 pulls slightly ahead of semantic after ~10 s and stays
  ahead by ~4 pp.
- On find-and-tray-stack, mbs0.05 sits 7 pp BELOW semantic from ~10 s onward
  — finer leaves hurt here.
- Uniform starts late (later ramp onset) on every goal and tops out lower.

Supports: semantic-vs-uniform is the real scaling story; semantic ≈ mbs0.05
overall; mbs0.05 is goal-dependent (small help on holding, small harm on
FATS, no effect on stack).
Undermines: any blanket claim that "finer Boxel resolution scales better."


### `tampura_wallclock_comparison.png`
Wall-clock per episode on find-and-tray-stack (success-only):
- Ours/semantic: 14.0 s (n=119, median ± IQR)
- Ours/semantic+mbs0.05: 14.9 s (n=99)
- Ours/uniform: 43.5 s (n=4) — very small sample
- TAMPURA Partial Obs.: 57.0 s (n=20, mean ± std, Table II of the paper)

~4× faster than TAMPURA on the same task family, but with the disclosed
hardware caveat: TAMPURA used a 20-core Xeon Gold 6248; ours an 8-core
consumer CPU. Per `THESIS_NOTES §21.1`, this is an **architectural**
comparison — offline Learn-Model vs online stream sampling — not a
hardware comparison. The 4× delta is on weaker hardware, which strengthens
the architectural reading but does not turn it into a fair benchmark.


### `failure_modes.png`
Stacked exit-reason bars per (goal, variant), 300 cells each. Successes
in green; failures broken into `planner_failed`, `replan_limit`,
`timeout`, `physics_mismatch`, `no_summary`, `drop_failed`, `all_searched`.

- `planner_failed` is the dominant failure mode across the board.
- `replan_limit` is noticeable only on `stack` (it's the second-largest
  slice for all three stack variants).
- `timeout` is small everywhere except find-and-tray-stack semantic and
  mbs0.05, where ~10% time out.
- `physics_mismatch` is tiny but non-zero on holding.
- find-and-tray-stack uniform is a near-total failure: ~3 successes, the
  rest planner_failed. Confirms uniform can't solve FATS at all.


### `plan_count_distribution.png`
Replan-count histograms per (goal, variant). All right-skewed; tail to
~60 replans. Means:
- find-and-tray-stack: semantic 3.9, mbs0.05 4.8, uniform 1.3
- holding: semantic 3.5, mbs0.05 3.7, uniform 3.3
- stack: semantic 2.0, mbs0.05 2.0, uniform 1.2

Reading: uniform's lower mean replan count on FATS and stack is **not** a
win — it reflects giving up early (planner_failed without entering the
sense-plan-act loop). On holding (where uniform actually completes some
runs) the means converge. mbs0.05 replans slightly more than semantic on
holding/FATS — finer leaves mean more sensing/replanning cycles, which is
plausible mechanically but doesn't translate into more successes.


## Per-goal: holding

### `success_rate_vs_n_occluders__holding.png`
Success rate flat across n_occluders ∈ {2, 3, 4}:
- semantic ~40–47 %, mbs0.05 ~43–48 %, uniform ~31–36 %.
Semantic & mbs0.05 are within seed noise of each other; uniform sits ~10 pp
below. **No scalability degradation** with occluder count in this range.

### `planning_time_vs_n_occluders__holding.png`
Mean total planning time on success-only cells:
- semantic / mbs0.05: 2 s → 14 s as n_occluders 2 → 4 (≈ linear).
- uniform: 21 s → 49 s → 83 s (much steeper; ~4-5× semantic at each point).

Wide CI bands on uniform — the success cases that DO complete take a wide
range of time. Reading: uniform pays a large per-occluder time penalty
that semantic does not.

### `boxel_count_breakdown__holding.png`
Stacked OBJECT / SHADOW / FREE_SPACE Boxel counts per variant:
- semantic and mbs0.05: ~25-43 Boxels total (mostly object + shadow + a
  handful of free).
- uniform: ~300 free-space Boxels alone (and growing slowly with
  n_occluders). Object/shadow contribution is negligible — uniform doesn't
  generate them in the same way.

**~10-30× more cells under uniform.** This is the headline scalability
number for the representation itself.

### `init_state_facts_vs_n_occluders__holding.png`
Mean grounded facts in the planner's initial state:
- semantic / mbs0.05: 180 → 430 (≈ linear).
- uniform: 2,050 → 2,650 (5-6× more grounded facts, growing slowly).

Tracks the Boxel-count finding: more cells → more grounded facts → larger
PDDL state.

### `per_call_planning_time__holding.png`
Per-call planning time vs replan index. Semantic & mbs0.05 stay under
~25 s per call across all replan indices and converge low. Uniform
spikes high early (one ~95 s peak around replan 5) and stays elevated
(~20-60 s per call) for replan indices up to ~45. The semantic/mbs0.05
trace is essentially flat near zero past replan ~10.

### `boxel_volume_histogram__holding.png`
Volume distributions (log-x).
- semantic: ~7,300 free cells, spread across volumes 10⁻⁴ – 10⁻¹ m³,
  multiple peaks (heterogeneous cells).
- mbs0.05: ~7,200 free cells, distribution almost identical to semantic.
- uniform: ~89,700 free cells concentrated at one bin (~10⁻³ m³) — the
  fixed grid cell size.

The semantic partition's heterogeneity is the abstraction in action: a
small number of large free regions where the space is empty, and finer
cells where the geometry warrants.

### `boxel_evolution_per_replan__holding.png`
Boxel count across replan index per variant. Semantic & mbs0.05: roughly
25-30 cells, flat across all replans (the representation is stable).
Uniform: starts ~300, decreases monotonically to ~300 over the first
~12 replans, then flat. Same takeaway — uniform pays a 10× cell-count
overhead at every step.

### `wallclock_vs_planning__holding.png`
Wall-clock vs total planning time is essentially `y = x` (on the diagonal)
for all variants. Planning IS the wall-clock; perception, motion-planning,
and execution overhead are negligible compared to planning time on this
goal. Important for the time-budget framing: when we say "planning time",
that's also wall-clock.


## Per-goal: stack

X-axis here is `stack_height ∈ {2, 3, 4}`, not n_occluders.

### `success_rate_vs_n_occluders__stack.png`
- height 2: all variants ~97 % (trivial).
- height 3: semantic / mbs0.05 ~74 %; uniform ~20 %.
- height 4: semantic / mbs0.05 ~13 %; uniform ~1 %.

Steep degradation with stack height; semantic still beats uniform by a
factor of 3-13× at the harder heights. Semantic and mbs0.05 lie on top of
each other across all heights — confirms the seed-for-seed equivalence
shown in #140.

### `planning_time_vs_n_occluders__stack.png`
Success-only mean planning time:
- semantic / mbs0.05: ~2 s, essentially flat across heights.
- uniform: 20 s → 32 s → 220 s. The 220 s point is n=1, so high variance,
  but the trend is clear: uniform's cost explodes with stack height.

### `init_state_facts_vs_n_occluders__stack.png`
Stack heights make uniform's state grow superlinearly:
- semantic / mbs0.05: ~300-400 facts, near-flat.
- uniform: 11,200 → 11,150 → 13,900 facts.

40× difference in grounded facts at height 4.

### `boxel_count_breakdown__stack.png`
- semantic / mbs0.05: ~20-30 Boxels total.
- uniform: ~1,340 free Boxels at every height (stack height doesn't change
  the free-space partition, just the object stack).

~50× difference in Boxel count.

Other stack plots (`per_call`, `volume`, `evolution`, `wallclock`) mirror
the holding patterns and add no goal-specific findings.


## Per-goal: find-and-tray-stack

### `success_rate_vs_n_occluders__find-and-tray-stack.png`
- semantic: ~39-42 %, flat across n_occluders.
- mbs0.05: starts at 40 % (n=2), drops to 31 % (n=3), 28 % (n=4).
- uniform: 0-2 % at all sizes.

**mbs0.05 actively degrades** as n_occluders grows on this goal. This is
the strongest evidence for the #140 "finer leaves don't help, sometimes
hurt" finding.

### `planning_time_vs_n_occluders__find-and-tray-stack.png`
Success-only mean:
- semantic: 20 s → 50 s → 20 s (noisy).
- mbs0.05: 5 s → 18 s → 50 s.
- uniform: 25 s → 40 s → 530 s (n=1 at the high end).

Wide CI bands; not many successful uniform episodes to compute over. The
clean reading is: semantic and mbs0.05 are within a factor of 2-3 of each
other; uniform blows up.

### `boxel_count_breakdown__find-and-tray-stack.png`
- semantic / mbs0.05: 35-50 Boxels total, slight rise with n_occluders.
- uniform: ~325-336 free Boxels.

~7-10× ratio. Same story as holding.

Other FATS plots (`per_call`, `volume`, `evolution`, `wallclock`,
`init_state_facts`) follow the holding/stack template: per-call time
~few seconds for semantic and 10-50 s for uniform; volume histograms
heterogeneous for semantic and grid-peaked for uniform; wall-clock ≈
planning time; init-state facts ~order of magnitude more under uniform.


## Synthesis / headline lessons for the thesis

1. **Semantic vs uniform is the real scaling claim.** Across all three
   goals: semantic produces 7-50× fewer Boxels, 5-40× fewer grounded
   facts, and dramatically lower per-call planning time. Uniform crashes
   entirely on find-and-tray-stack (1.3 % success) and degrades steeply
   with stack height (1 % at h=4 vs 13 % for semantic).

2. **mbs0.05 doesn't discriminate.** On stack the curves overlap exactly;
   on holding mbs0.05 is ~4 pp better; on find-and-tray-stack it's
   ~7 pp WORSE. At the scene scales tested (object footprints ~6-9 cm,
   `auto_cell` ~6-9 cm), the 5 cm leaf floor is not the binding
   constraint — confirms #140. The thesis should report this as a
   regime characterisation, not as a method failure, and either add a
   sub-cell scene per #140 (a) or disclose the null honestly per
   #140 (b).

3. **Anytime budget plateaus fast.** Curves are essentially flat after
   ~100-200 s of wall-clock. Increasing the time budget further yields
   diminishing returns; the relevant comparison is at the 100-200 s
   horizon, not "given infinite time".

4. **TAMPURA wall-clock is ~4× ours, on weaker hardware.** The comparison
   is architectural (Learn-Model offline vs PDDLStream online), per
   `THESIS_NOTES §21.1`. The hardware caveat means the comparison
   doesn't prove ours is "faster" in a benchmarking sense, but it does
   strengthen the architectural reading.

5. **Failure dominated by `planner_failed`.** Apart from `replan_limit`
   on stack, the bulk of failures are planner_failed. The follow-up
   question for the thesis is whether these are unsolvable scenes or
   timeouts inside the planner — the data we have can't fully separate
   those.

6. **Boxel sets are stable across replans.** The boxel_evolution plots
   show semantic/mbs0.05 cell counts almost flat over a sequence of
   30-45 replans. The partition doesn't blow up during replanning. Worth
   stating as a sanity check on the representation.

7. **Wall-clock ≈ planning time.** Sense / motion / execution overhead is
   negligible on these goals. The "planning time" axis on every plot is
   effectively also wall-clock. Useful for prose simplicity.
