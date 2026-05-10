# Audit #50 — Planner Performance Sweep

**Branch**: `audit-50-perf-sweep` (off `main` @ b47be63)
**Date**: 2026-05-10
**Status**: investigation only; no source edits yet.

This document is the read-only deliverable that audit #50 explicitly
asks for ("APPROACH (no single commit — investigation first) ... Do
not start optimising before profiling"). It identifies suspected
redundancies, scores them by expected impact and confidence, and
defines the measurement harness that has to land before any
optimisation commit. Every fix lands as its own commit, gated on
before/after numbers from this harness.

---

## 1. Scope and ground rules

* **Files swept** (read-only): `pddlstream_planner.py`, `streams.py`,
  `execution.py`, `test_full_pipeline.py` (replan loop only),
  `boxel_env.py` (sync_to_plan_client + free-space dispatch),
  `free_space.py`, `uniform_grid.py`, `cell_merger.py`,
  `reboxelize.py`, `robot_utils.py` (collision-check primitives),
  `run_logger.py` (timing_summary writer), `pddl/domain_pddlstream.pddl`,
  `pddl/stream.pddl`.
* **Out of scope here**: belief.py, visualization.py, smart_filter.py,
  shadow_calculator.py, eval_plotter.py — none are in the planner
  hot path. (smart_filter is per-line stdout work; revisit if
  measurement shows ≥ 5 % time spent in `_process`.)
* **No code changes on this branch**. The branch exists so that the
  measurement harness (Section 4) and any downstream fixes can land
  as ordered commits with regression evidence; this file is
  commit 1.
* **Each later optimisation commit must include**:
  - top-10 cumulative-time delta from the cProfile harness on a
    fixed three-cell sweep (Section 4.6), and
  - success-rate parity from the smoke regression on the same
    seeds — no silent success-rate regressions allowed.

---

## 2. Findings — ranked by expected wall-clock impact

Each finding is tagged with **Impact** (H / M / L expected), **Confidence**
(H / M / L the diagnosis is correct without measurement), and **File:lines**.

### Tier H — likely big wins; profile, then fix

#### H1. `_compute_placement_view_blocks` — Python ray-AABB loop + quadratic fact emission
File: `pddlstream_planner.py:297-333` (compute) and `:444-463` (emit). **Impact H, Confidence M.**

Two costs in one block:

1. **Compute cost.** For each of `S` shadows, builds a 5×5 ray endpoint
   set, then for each of `F` free boxels iterates all 25 ray
   endpoints in pure Python and calls `_ray_aabb_intersects` per
   ray. That is `O(S · 25 · F)` ray-AABB tests per replan; at
   `S=5, F≈50` it is 6 250 Python-level numpy calls; at `S=10,
   F≈150` (uniform baseline) it is 37 500. The math inside
   `_ray_aabb_intersects` is correctly numpy-vectorised; the OUTER
   loops are not.
2. **Emission cost.** Lines 461-463 emit
   `('blocks_view_at', obj_id, free_id, shadow_id)` once per
   `(blocking_pair, OBJECT_boxel)` — i.e. `O(P · O)` ground atoms,
   where `P` is the count of blocking `(free_id, shadow_id)` pairs
   and `O` is the count of OBJECT boxels currently in the registry.
   These are duplicates from the planner's point of view; the
   derived predicate `(blocks_view ?obj ?region)` only needs an
   object-existence quantification.

**Suggested fixes (in order of risk)**:

* **(a) Vectorise compute.** Stack ray endpoints into one
  `(S·25, 3)` array and free-boxel AABBs into one `(F, 3)` array;
  compute the slab-method t_enter / t_exit as a single batched
  numpy op. Expected: 5–20× on the compute side.
* **(b) Cache compute by registry fingerprint.** The compute
  depends only on `(camera_pos, shadow AABBs, free-boxel AABBs)`.
  None of those change between replans unless the registry mutates
  free space or shadows. Cache keyed by a fingerprint
  `(frozenset((id, min, max)) for shadows + frees)`; invalidate at
  the same seam where `registry.dirty` flips.
* **(c) Trim emission.** Add a 2-arg PDDL predicate
  `(would_block_view_at ?b ?s)` (object-agnostic placement
  geometry) and a derived `(any_obj_at_boxel ?b)`; rewrite the
  derived `view_blocked` to combine them. Drops the `O(P·O)`
  emission to `O(P)` per replan AND shrinks the FD grounded fact
  set. **Risk**: this is a domain change — must move on its own
  branch, with goal-equivalence test (final plans should still be
  identical at the same seed).

The audit body's suspect (b) ("`_compute_placement_view_blocks`
runs every `_build_init` at O(S × 25 × F)") is exactly H1. The
suspect framing under-counts the emission half.

#### H2. `_build_init` re-emits invariant facts every replan
File: `pddlstream_planner.py:335-554`. **Impact H, Confidence M.**

Per replan, `_build_init` walks every `boxel` in the registry and
re-emits the type predicates (`Boxel`, `is_shadow`, `is_object`,
`is_free_space`, `on_surface`, `obj_at_boxel`, `obj_at_boxel_KIF`),
the static `blocks_view_at` facts (lines 431-442), and — most
expensively — the full `boxel_fits` cross-product
(`pddlstream_planner.py:489-503`, `O · F` calls to
`streams.test_boxel_fits`). For a uniform-baseline scalability cell
with `O=10, F≈150`, that is 1 500 `test_boxel_fits` calls per
replan, each doing six numpy-vector comparisons. None of these
facts change between replans unless the registry's set of boxels or
their AABBs change.

**Suggested fix**: split `_build_init` into a static section and a
dynamic section. Cache the static section's emitted tuple-list,
keyed by a registry fingerprint
`hash((tuple(sorted(boxels by id)), per-id (min, max), shadow_occluder_map_hash, camera_pos_hash))`.
Invalidate when `registry.dirty` flips OR when
`shadow_occluder_map` is mutated. Reuse the cached list and tack
on the dynamic facts (`current_config`, `at_config`, `holding`/
`handempty`, `on_relations`, `clear`, `on_table`, the
`visible_target_locations` patches). The existing
`registry.dirty` flag (`boxel_data.py:107-114`) is the right seam
but it's only flipped today by `update_after_place` — extend it to
flip on `add_boxel`, `remove_boxel`, and any direct AABB mutation.

**Cross-ref**: the existing CODEBASE POLICY block "BOXEL_FITS /
STATIC INIT FACTS — REBUILT EACH REPLAN" (`CODEBASE_AUDIT.txt:1191-1203`)
records that an earlier *test-stream* version was abandoned because
adaptive search re-evaluated it heavily. Caching the **Python-side**
tuple list is a different mechanism — the planner still receives
the facts as static init, just without paying the recompute. Both
notes can coexist.

**Risks**:
* `random.shuffle(init)` at line 553 currently scrambles fact
  order each call. Caching defeats this unless we shuffle the
  cached list per-call too (cheap). The shuffle itself is a
  questionable feature — see M1.
* If we cache a pre-shuffled list and `_build_init` is called
  back-to-back with different `target_objects`, the cached
  `obj_at_boxel_KIF` rows must be keyed on the target set.

#### H3. `is_path_collision_free` × `is_config_collision_free` → PyBullet save/restore per config
File: `robot_utils.py:255-298` and `:102-252`. **Impact H, Confidence H.**

Hottest inner loop in the entire system. RRT-Connect
(`streams.py:722-813`) calls `is_path_collision_free` per edge;
each call evaluates 8 configs (`RRT_EDGE_CHECKS=8`); each config
calls `is_config_collision_free` which:

* reads 7 joint states (7 × `p.getJointState`),
* writes 7 joint states (7 × `p.resetJointState`),
* if held bodies, repositions each (`p.getLinkState` +
  `p.multiplyTransforms` + N × `p.getBasePositionAndOrientation`
  + N × `p.resetBasePositionAndOrientation`),
* `p.performCollisionDetection` + `p.getContactPoints`,
* restores all of the above.

That is ≥ 16 PyBullet round-trips per **config**, ≥ 128 per
**edge**, and an RRT-Connect run does thousands of edge checks.
The shortcut smoother (`SMOOTH_ATTEMPTS=75`,
`streams.py:817-844`) doubles down with another 75 edges per
plan_motion call.

**Suggested fixes** (ordered by risk):

* **(a) Memoise per-config**: hash `(round(joints, 3), held_pose_key)`
  inside a single RRT-Connect run; the `_steer` pattern frequently
  visits near-identical configs across iterations and across
  smoothing attempts. Expected: 1.5–3× on RRT-heavy plans.
* **(b) Drop the save/restore on the plan client**: `boxel_env.sync_to_plan_client`
  resets the plan client every replan anyway, so as long as no
  other code reads joints during `plan()`, the restore is dead
  weight. Verify: grep for `p.getJointState(... physicsClientId=plan_client_id)`
  outside `is_*_collision_free` and `_pybullet_ik`.
* **(c) Swept-volume AABB pre-check**: maintain per-link AABBs
  (one `p.getAABB(robot_id, link)` per link per replan, ~12 calls)
  and pre-reject edges whose linearly-interpolated swept volume
  doesn't intersect ANY non-ignored body's AABB. Skip narrowphase
  for those. Expected biggest wins on tabletop scenes where most
  RRT samples are far from any obstacle.
* **(d) Batch joint reset**: PyBullet exposes `resetJointStatesMultiDof`;
  one call vs. seven. Saves overhead but probably small (≤ 10 %).

**Risks**: (a) and (b) require that nothing inside the IK / IK seed
loop mutates the plan-client robot pose between checks. Hold off
on (b) until (a) is measured.

#### H4. CellMerger — `O(N² · passes)` greedy merge
File: `cell_merger.py:76-123`. **Impact M-H, Confidence H.**

`merge_free_space` runs up to 100 passes; each pass is a nested
`for i: for j>i:` over the current boxel list, calling `_try_merge`
(three axis tests with `_approx_equal`) per pair, AND calling
`_merge_quality` twice for tie-breaking. `merge_free_space` is
called from `reboxelize_free_space` after every successful place
(via `test_full_pipeline.py` registry.dirty path) — i.e. several
times per run. With ~150 cells before merge dropping to ~30 after
and converging in ~5-10 passes, we're at 100k+ axis-equality
comparisons per call.

**Suggested fix**: replace the all-pairs scan with face-keyed
buckets. For each boxel, compute six face keys
`(axis, side, rounded_other_two_corners_min, rounded_other_two_corners_max)`;
two boxels can merge along an axis iff one's `+axis` face key
equals the other's `−axis` face key. That is `O(N)` per pass to
build the dict, `O(N)` per pass to merge.

**Risks**: same FP-tolerance issue (`tolerance=1e-4`) — round to
the nearest integer multiple of `tolerance` when computing keys.

#### H5. `reboxelize_free_space` — `O(N×M)` AABB match loop
File: `reboxelize.py:61-72`. **Impact M, Confidence H.**

For every merged cell, walks the ENTIRE old free-space list with
`np.allclose` to find a match. With `len(merged) ≈ len(old_free) ≈ 100`,
that's `~10 000 np.allclose` calls per reboxelize.

**Suggested fix**: index `old_free` by a key
`(round(min, 4), round(max, 4))` in a dict. One pass to build,
O(N) to look up. ~50–100× on this loop in isolation; doesn't
matter wall-clock-wise unless reboxelize fires several times per
replan.

### Tier M — measure, fix opportunistically

#### M1. `random.shuffle(init)` is silently non-deterministic
File: `pddlstream_planner.py:553`. **Impact L, Confidence H.**

`_build_init` shuffles its return list. The intent (per code
archaeology — no comment on the line) is presumably to prevent
FastDownward from latching onto fact-order artefacts; in practice,
the master `--seed` plumbing in `test_full_pipeline.py` (audit
#9) seeds `random` once at process start, so the shuffle is
deterministic-given-seed but order-dependent on every prior call
of `random.*` in the run (target choice, IK seeds, RRT goal-bias
samples, ...). That makes per-replan reproducibility brittle.

**Suggested fix**: drop the shuffle, OR seed it from a stable hash
of the fact-set (so the order depends only on inputs). Pair with
profile data — if removing it changes FD grounding time visibly,
that itself is a finding.

**Risk**: shuffle removal can change FD's plan choice at unstable
seeds. Smoke sweep before and after.

#### M2. IK 8 seeds per (obj, boxel, grasp) — does adaptive search consume them?
Files: `streams.py:210-228, 918-941, 1070-1096`. **Impact M, Confidence L.**

`compute_kin_solution` and `compute_stack_kin_solution` both yield
up to 8 IK configs per call. Each `_pybullet_ik` does 100
iterations. PDDLStream's adaptive solver may consume only the
first 1-2 before finding a satisfying skeleton. We don't know — no
counter today.

**Suggested fix**: add a per-call counter (Section 4.3) that
records how many seeds were generated AND how many were consumed
(via a wrapping generator). If consumption < 50 % of generation in
the median, lower `IK_NUM_SEEDS` adaptively or yield seeds in
priority order with a lazy cap.

#### M3. `compute_stack_kin_solution` re-reads support AABB inside the seed loop
File: `streams.py:1036-1052`. **Impact L, Confidence H.**

The support body's AABB is read **once** outside the seed loop
(line 1036-1044) — good. But `held_boxel.extent` (line 1024) and
the body-id resolutions (lines 1014-1015) are also outside. So this
is fine as written. Marked here for reference only — earlier
version of the file had the AABB read inside the loop; current
code post-#55 is correct.

**No fix**. Confirm with profiler.

#### M4. `compute_shadow_blockers` — fires after every place
File: `execution.py:143-235`, called from `test_full_pipeline.py:1332`. **Impact L, Confidence M.**

Single 5×5 ray batch per shadow + parent-relationship fallback.
Cheap individually (~25 rays/shadow × ~5 shadows = 125 rays).
Runs after every relocation. If profiling shows ≥ 5 % spent here,
cache by occluder-pose fingerprint.

#### M5. `sync_to_plan_client` — full mirror every replan
File: `boxel_env.py:615-648`. **Impact L, Confidence M.**

For every mirrored body it does `getBasePositionAndOrientation`
+ `resetBasePositionAndOrientation` (so 2 calls/body). Plus a
joint-by-joint robot mirror. With 1 robot + ~6 objects + 2 supports,
that's ~30 PyBullet calls per replan. Cheap. Probably not worth
optimising; verify with profiler.

#### M6. The `time_outer = 1800.0` budget per `planner.plan()` call
File: `test_full_pipeline.py:971, 1039`. **Impact varies, Confidence H.**

Not a redundancy per se, but a perf-relevant config: `max_time=1800 s`
(30 min) per call, set during the #54 follow-up. With 9 replans per
holding-goal episode, the worst-case wall-clock is huge. After
TIER-H fixes land, we should consider lowering this and exposing
it via `--max-time-per-replan`.

### Tier L — small or risky; defer

#### L1. PDDL grounder cardinality
File: `pddl/domain_pddlstream.pddl`. **Impact unknown, Confidence L.**

Three predicates dominate the grounded fact set:
* `(blocks_view_at ?obj ?b ?region)` — 3-arg, cardinality
  `|O| · |B| · |S|` worst case (only `O · P` are emitted in init).
  H1.(c) above proposes a 2-arg replacement.
* `(obj_at_boxel_KIF ?o ?b)` — 2-arg, cardinality `|targets| · |B|`.
  Emitted for every observed-clear boxel × every target. Today
  EVERY non-target-bearing boxel is observed-clear (per the
  audit-#67 fix); so this is `|T| · (|B| - |T|)`.
* `(boxel_fits ?o ?b)` — `|O| · |F|`. Could be replaced with
  `(boxel_fits_size ?b SIZE_TOKEN)` if we discretise object sizes,
  but that's a bigger refactor; not now.

**Suggested fix**: nothing immediate; revisit if FD translator
time dominates after Tier-H fixes.

#### L2. `print()` overhead via SmartConsoleFilter
File: `smart_filter.py:271-296`. **Impact L, Confidence L.**

Per-line work; low cost individually but compounds in RRT logs
(thousands of lines per failing plan). Profile first.

#### L3. PDDLStream `solve()` algorithm choice
File: `pddlstream_planner.py:614-620`. **Impact unknown, Confidence L.**

Currently `algorithm='adaptive'`. The PDDLStream paper suggests
`'binding'` and `'incremental'` may be faster on simpler tasks.
Worth a per-cell A/B once H1-H5 land.

---

## 3. Cross-cutting risks

* **Caching `_build_init` (H2)** must hook every registry mutation
  seam, not just `update_after_place`. Risks silently stale plans
  if a mutation path is missed. Mitigation: add `_dirty=True` in
  `add_boxel` / `remove_boxel`; assert `not registry.dirty` at the
  top of every cached `_build_init`.
* **`would_block_view_at` predicate (H1.c)** is a domain change.
  Goal-equivalence: at the same seed and identical init topology,
  the new domain must produce the same plan. Test via a fixed-seed
  smoke set comparing action lists.
* **Removing `random.shuffle(init)` (M1)** can shift FD's plan
  choice at unstable seeds. Run the full smoke matrix and compare
  plans.
* **Lowering `IK_NUM_SEEDS` (M2)** can flip a previously-solvable
  scene to no-plan. Don't lower; wrap in a counter and lazy-yield.

The TAMPURA reference in user memory (`reference_tampura_grid.md`)
is **NOT** relevant here — TAMPURA's voxel grid is a *visibility
belief*; placement uses continuous-pose sampling. Our placement is
boxel-indexed, so its perf characteristics are different from
TAMPURA's. (TAMPURA's reported 21–129 s/episode gain came from
offline Learn-Model, not from the grid representation; per
`reference_tampura_perf.md`.)

---

## 4. Measurement plan

Six instruments. Each is a small-radius change that lands as its
own commit BEFORE any optimisation commit, so every later "fix
landed Δ -X %" claim has both a baseline and an a/b.

### 4.1. cProfile harness — `tools/profile_plan.py` (new file)

Wrap `test_full_pipeline.main()` in `cProfile.Profile()` controlled
by an env var `BOXEL_PROFILE=1`. On exit, dump pstats next to
`timing_summary.json`. CLI mirrors `test_full_pipeline.py` so the
same alias (`run_boxels`) works.

```
python tools/profile_plan.py --scene scalability \
    --n-occluders 3 --n-targets 2 --n-hidden 2 --seed 0 \
    --goal holding --baseline semantic
# writes eval_results/.../profile_plan.pstats and the usual log/json
```

Companion script: `tools/profile_summary.py prof.pstats` →
top-30 cumulative + top-30 own-time table.

### 4.2. `_build_init` and `planner.plan` slice profilers

In-process, light: a `cProfile.Profile` instance bound to each
function via context manager, accumulated into the run logger and
written into `timing_summary.json` as
`per_replan_profile_top10` (a list of `(replan_idx, top10)`
tuples). Saves the cost of running the full-process profiler on
long sweeps.

### 4.3. Per-stream call counters

Wrap `BoxelStreams.sample_grasp / plan_motion / compute_kin_solution
/ compute_stack_kin_solution` with a counter decorator that
increments a class-level `Counter` and aggregates `time.perf_counter`
deltas. Dump per replan into `timing_summary.json` as:

```json
"stream_call_counts": [{"sample_grasp": 12, "plan_motion": 28, ...}, ...],
"stream_time_s":      [{"sample_grasp": 0.04, "plan_motion": 1.21, ...}, ...]
```

Adds zero hot-path cost when counters are off; the wrapper is
attached only when `BOXEL_PROFILE=1`.

### 4.4. PyBullet-call counters

Same pattern around `is_config_collision_free`, `is_path_collision_free`,
and `_pybullet_ik`. Records both call count and cumulative time.
Lets H3 fixes show their work without a full-process profile.

### 4.5. Init-fact-count metric

After each `_build_init`, log `len(init)` and a per-predicate
breakdown:

```python
from collections import Counter
predicate_counts = Counter(fact[0] for fact in init)
```

Append to `timing_summary.json` as `init_fact_counts` (list, one
dict per replan). Lets us see the H1.c predicate-trim land
visibly.

### 4.6. Fixed three-cell profile sweep

The reproducer that every Tier-H fix has to beat. Three cells, all
seed=0, all `--baseline semantic` for now (uniform sweep can be a
follow-up):

| Tag | n_occluders | n_targets | n_hidden | goal |
|-----|-------------|-----------|----------|------|
| `tiny`   | 1 | 1 | 1 | holding |
| `medium` | 3 | 2 | 2 | holding |
| `large`  | 6 | 3 | 3 | holding |

Driver script `tools/profile_sweep.py`:

```
python tools/profile_sweep.py --tag baseline_pre_fix
# → eval_results/profile_sweep_<timestamp>/{tiny,medium,large}/
#   profile_plan.pstats, timing_summary.json, run.log
```

Output table format (committed alongside each fix):

```
                tiny           medium          large
total plan(s)   T_t            T_m             T_l
avg replan      ...            ...             ...
top-1 fn        ...            ...             ...
top-2 fn        ...            ...             ...
init fact count ...            ...             ...
```

### 4.7. Regression smoke (no perf, just correctness gate)

`python eval_runner.py --matrix smoke --output eval_results/smoke_audit50/<tag>` —
1 cell. Asserts no crash, success-rate parity, plan-count parity.

---

## 5. Workflow / commit order

Recommended commit chain on this branch (each is independently
revertible):

1. ✅ **commit 1** — this document (`AUDIT_50_SWEEP.md`).
   No source changes.
2. **commit 2** — `tools/profile_plan.py` + `tools/profile_summary.py`
   + `tools/profile_sweep.py` (Section 4.1, 4.6). New files only.
3. **commit 3** — counter wrappers (Sections 4.2-4.5). Touches
   `pddlstream_planner.py`, `streams.py`, `robot_utils.py`,
   `run_logger.py`. Gated on `BOXEL_PROFILE=1`; off-path
   identical to today.
4. **commit 4** — baseline numbers. Run the three-cell sweep,
   commit `eval_results/profile_sweep_baseline/` with the report
   + raw pstats files. From this point on every later commit
   reports a delta vs. this baseline.
5. **commits 5-N** — one fix per commit, in priority order:
   H5 → H4 → H3.(a) → H3.(b) → H1.(b) → H1.(a) → H2 → H1.(c).
   H1.(c) and (any other domain-touching commit) move to a
   sub-branch.
6. **final commit** — update `CODEBASE_AUDIT.txt` to mark #50
   `[DONE]` (or break #50 into closed sub-items if not all of
   H1-H5 landed).

Per CODEBASE POLICY (changelog, line ~1146-1154): push the branch
to BOTH github and origin after each meaningful commit.

---

## 6. Out-of-scope follow-ups (for FOR LATER)

These surfaced during the sweep but are not part of #50:

* `is_config_collision_free` is reachable via `compute_kin_solution`
  → `_pybullet_ik` only indirectly (IK doesn't collision-check
  during the seed loop, by design — `streams.py:863-870` notes
  "Collision validation is deliberately NOT done here"). If a
  future audit re-adds collision validation inside compute_kin to
  prune bad seeds early, the H3 caching becomes even more
  valuable.
* The `RRT_*` parameters (`streams.py:449-454`) are empirical and
  documented. After H3 lands they may want re-tuning at the new
  per-edge cost.
* Audit #62 (replan-while-holding) is **explicitly a sub-hotspot
  of #50**. After H2 lands, re-run #62's reproducer; if the
  hold-vs-empty delta has shrunk to noise, close #62 as MERGED
  INTO #50.

---

## 7. What this document does NOT do

* Does not commit to a target speedup. Premature.
* Does not change any source file. The next commit on this branch
  will (the profiling harness).
* Does not promise that all of H1-H5 are net wins — H2 in
  particular has a real cache-invalidation risk that may eat the
  savings. Each fix's commit message must show it pays for itself.
