# Agent B — Sense code-path map (unlocalizable guard + neighbours)

Scope: pure code reading (`execution.py`, `perception.py`, `belief.py`,
`test_full_pipeline.py`, `boxel_env.py`) plus the artifacts of
`logs/run_2026-08-22_17-14-10/` (log, `boxel_data.json`). No probes run.
Every claim is tagged **CONFIRMED** (read directly off the artifact/code) or
**HYPOTHESIS** (reasoning from code, not independently verified against a
render).

---

## 1. `handle_sense_action` (execution.py:1782-2312) — every branch, in order

### 1.1 The one render, and how it is threaded

One observation is taken at the top of the function and reused everywhere
below it:

```
execution.py:1865  sense_detections, _, _sense_depth_buf, sense_seg = env.detect_objects()
execution.py:1866  sense_depth_m = env._depth_buffer_to_meters(_sense_depth_buf)
execution.py:1867  sense_view, sense_proj = env._view_and_projection_matrices()
```
(comment block execution.py:1860-1864 states the single-render contract
explicitly). `env.detect_objects()` (boxel_env.py:1658-1701) does one
`p.getCameraImage(..., renderer=p.ER_TINY_RENDERER)` call and one
`perception.detect_objects_from_render(...)` call — this is where
`DETECTION_MIN_PIXELS` first applies (see §2).

Consumers of this single `(sense_detections, sense_depth_m, sense_seg,
sense_view, sense_proj)` tuple, all inside this one `handle_sense_action`
call:
- `sense_shadow_from_render` — main classification (execution.py:1869-1877).
- OBJECT-boxel registration for a found target, reusing
  `sense_detections.get(target_obj_str)` (execution.py:1907).
- `refresh_object_aabbs(..., detections=sense_detections, render=(sense_depth_m, sense_seg, sense_view, sense_proj), check_lost=True)`
  — called from **every** exit branch (execution.py:1943-1946, 1979-1983,
  2259-2262, 2304-2307).
- The sibling batch-sense's own `sense_shadow_from_render` calls, reusing
  `sense_depth_m/sense_seg/sense_view/sense_proj` (execution.py:2050-2054).
- OBJECT-boxel registration for a newly discovered non-target, reusing
  `sense_detections.get(obj_name)` (execution.py:2100).

### 1.2 Branch table, mapped to this run's log lines

| # | Condition | Code | Belief/registry effect | This run's occurrences |
|---|---|---|---|---|
| 0 | `shadow_boxel is None` | execution.py:1839-1842 | none, `ActionResult(False,"sense_missing_shadow")` | **never fired** — confirmed by grepping the full log for "WARNING"/"not found in registry": zero hits. |
| 1 | `found_target` | execution.py:1879-1951 | `belief.mark_sensed(found=True)`; registers target OBJECT boxel from `sense_detections` if localizable | **never fired** — blue was never found; run FAILED. |
| 2 | `contains_nontarget` **and** every detected body is unlocalizable (§2) | execution.py:1961-1989 | `blocked_counts[sid]+=1`; on the 3rd strike `belief.mark_sensed(found=False)` + `blocked_giveup_shadows.add`; boxel geometry **not** removed | log:243 (`shadow_of_green_object` attempt 1), 303 (attempt 2), 357-358 (attempt 3, giveup); log:529 (`shadow_of_red_object` attempt 2), 583-584 (attempt 3, giveup) |
| 3 | `clear_but_empty` or `contains_nontarget` **with** ≥1 localizable body | execution.py:1991-2271 | `belief.mark_sensed(found=False)`; `registry.remove_boxel(sid)`; sibling batch-sense (§4); discovery of new OBJECT+SHADOW boxels for localizable non-targets; `reboxelize_free_space` | **never fired** in this run (no such log line: "REPLANNING with updated belief" never appears) |
| 4 | else (`still_blocked`) | execution.py:2273-2312 | `blocked_counts[sid]+=1`; partial-reveal shrink if `blocked_bbox`; on the 3rd strike giveup (same as branch 2) | log:466-470 (`shadow_of_red_object` attempt 1, shrink 10.4×33.2×13.6→4.3×8.3×9.1 cm) |

**Key cross-branch coupling (CONFIRMED):** branches 2 and 4 share the *same*
`blocked_counts` dict (`test_full_pipeline.py:1013`, passed by reference at
`test_full_pipeline.py:1426`), incremented at execution.py:1967 (branch 2)
and execution.py:2277 (branch 4). A shadow's giveup counter accumulates
across *different outcome types* — exactly what happened to
`shadow_of_red_object`: attempt 1 = branch 4 (`still_blocked`), attempts 2
and 3 = branch 2 (`contains_nontarget`-unlocalizable) → 3 strikes →
`belief.mark_sensed('shadow_of_red_object', found=False)` at execution.py:1978,
matching log:583-584. Every one of the 7 `[perception] ... keeping last
estimate: ['orange_object']` lines (log:148,244,304,359,470,530,585) is the
`refresh_object_aabbs` print (execution.py:1691-1694) that runs at the tail
of whichever branch just executed (branch 2 at 148? — no: log:148 is the
transit-loss handler in `test_full_pipeline.py:1573-1574`, the *only*
occurrence not inside `handle_sense_action`; all six subsequent occurrences,
log:244/304/359/470/530/585, are the `handle_sense_action` refresh calls
listed in §1.1).

**Arithmetic cross-check (CONFIRMED, derived from the log's own numbers, no
probe needed):** `shadow_occluder_map` is rebuilt only after `place` actions
(`test_full_pipeline.py:1746-1749`, "Shadow blockers (audit #78)"), not
between sense attempts. Right after Plan #5's place, the printed census
(log:454-456) lists **no** entry for `shadow_of_red_object` → it has zero
blockers → `occluder_pybullet_ids` passed into `sense_shadow_from_render`
for Plan #5's own sense call is the empty set (execution.py:1845-1848).
Under an empty `occ_set`, `still_blocked` can only come from `robot_hits`
(execution.py:196-199) — matching the log's own
"`NOTE: 4/388 endpoints hidden by robot arm (not occluder)`" (log:466), gated
at execution.py:228-230 by `robot_hits>0 and occluder_hits==0`. The reported
"8%" (log:467) is exactly `4/49` (one coarse 7×7 slice) = 8.16%, which
matches `SENSE_COARSE_N=49` points per coarse slice (perception.py:61) —
i.e. **CONFIRMED**: attempt 1's block on `shadow_of_red_object` was the
robot arm's own body sitting over one coarse slice, not an unmodelled
occluder.

---

## 2. `sense_contains_unlocalizable` path (branch 2 above)

**Condition (exact code, execution.py:1961-1971):**
```python
if sense_outcome == "contains_nontarget":
    _loc_names = [body_id_to_name[b] for b in detected_bodies
                  if b in body_id_to_name
                  and body_id_to_name[b] in sense_detections]
    if not _loc_names:
        sid_str = str(shadow_id)
        blocked_counts[sid_str] = blocked_counts.get(sid_str, 0) + 1
        print(f"    Shadow {shadow_id} contains something the render "
              f"cannot localize (below the detection minimum) — "
              f"keeping the fragment. [attempt {blocked_counts[sid_str]}]")
```
"Unlocalizable" means: `sense_shadow_from_render` (a per-*ray* seg-id test,
no pixel-count floor — see execution.py:189-201) found a non-target,
non-occluder, non-robot body id intercepting at least one grid endpoint
(`detected_bodies`, execution.py:172, 200-201), **but** that body's *whole-
frame* pixel footprint in `sense_detections` (a *separate*, per-object
aggregate) fell under `DETECTION_MIN_PIXELS`, so `body_id_to_name[b] in
sense_detections` is false for every `b`.

**Where `DETECTION_MIN_PIXELS` is applied (CONFIRMED):**
`perception.py:320` declares the constant (6). It is consumed only inside
`detect_objects_from_render` (perception.py:367-431), specifically:
```python
perception.py:404-406
    rows, cols = np.nonzero(seg == body_id)
    if rows.size < min_pixels:
        continue
```
i.e. an object is excluded from `sense_detections`/`ObjectDetection` (and
thus from `body_id_to_name[b] in sense_detections`) purely on *total
segmented-pixel count in the full frame*, independent of where those pixels
fall relative to the shadow's grid. This is a **different test** than the
per-endpoint interception test used by `sense_shadow_from_render` — a body
can trip a grid endpoint (single-pixel lookup, perception.py:259-270) while
having far fewer than 6 pixels overall in the frame. That gap is exactly
what routes execution into branch 2 instead of branch 3.

**Where the 3-strike counter lives:** `blocked_counts` dict,
`test_full_pipeline.py:1013` (`{}` at episode start, never reset per plan),
threaded by reference into `handle_sense_action` (`blocked_counts=
blocked_counts` at `test_full_pipeline.py:1426`), incremented at
execution.py:1967. Giveup test `if blocked_counts[sid_str] >= 3:`
(execution.py:1972).

**What state a giveup writes (execution.py:1972-1978):**
```python
blocked_giveup_shadows.add(sid_str)
belief.mark_sensed(sid_str, found=False)
```
- `belief.shadow_status[sid_str] = 'not_here'` (belief.py:37-43) — this is
  the ONLY state write that removes the shadow from planner consideration
  (`BeliefState.get_unknown_shadows`, belief.py:56-58, filters on status
  `'unknown'`).
- **`registry.remove_boxel(sid_str)` is NOT called on this path.** The
  fragment's geometry stays in the registry unchanged — the docstring at
  execution.py:1975-1976 says so explicitly ("the content stays
  unmodelled"). This differs from branch 3's giveup (clear_but_empty /
  localized contains_nontarget), which *does* remove the boxel
  (execution.py:1995).
- `blocked_giveup_shadows` (a `set`, `test_full_pipeline.py:988`) is used
  only for the end-of-run FAILED-message classification
  (`test_full_pipeline.py:1072-1080`), not by the planner.

**What the caller does afterwards:** regardless of strike count, the branch
runs one more `refresh_object_aabbs(... check_lost=True)` call
(execution.py:1979-1983) and returns `ActionResult(continue_=False,
reason="sense_contains_unlocalizable")` (execution.py:1988-1989) — the
dispatch loop in `test_full_pipeline.py` breaks to replan
(`if not sense_result.continue_: break`, `test_full_pipeline.py:1435-1436`).
On the next `planner.plan()` call, the shadow is simply absent from
`get_unknown_shadows()` and PDDLStream's init facts no longer offer it as a
sense target — matches the log's `Unknown shadows remaining` counter
dropping (3→2 after `shadow_of_green_object`'s giveup at log:358→361;
2→1 after `shadow_of_red_object`'s giveup at log:584→588).

**DISCARDED diagnostic (the gap the report should close):** `detected_bodies`
(the raw set of intercepting body ids, execution.py:172) and
`body_id_to_name` (in scope in `handle_sense_action`) together could name
*which* body tripped the unlocalizable path. Instead, the only names kept
are the *localizable* ones (`_loc_names`, which is empty on this path by
construction) — the print at execution.py:1968-1971 never mentions
`detected_bodies` or its resolved names at all, so the log says only
"contains something the render cannot localize," never *what*. A one-line
change (`[body_id_to_name.get(b, b) for b in detected_bodies]`) would have
surfaced the culprit's identity in this run's log without any extra
rendering. See §3 for the parallel gap on the `still_blocked` side.

---

## 3. `sense_shadow_from_render` (execution.py:69-264) — outcomes, tolerance, discarded identity

**Grid geometry** shared with the census and the spawn-time guarantee:
`perception.sense_ray_slices` (perception.py:88-146), called at
execution.py:154. One dense low slice (12 mm spacing, `SENSE_DENSE_SPACING`,
perception.py:56) 2 cm above the fragment base (`SENSE_LOW_SLICE_OFFSET`,
perception.py:48), plus two coarse 7×7 slices (`SENSE_COARSE_N=7`,
perception.py:61) at 0.33/0.67 fragment height.

**Per-ray classification loop (execution.py:179-201):**
```python
ignore_ids = {-1, robot_id} | support_body_ids | occluder_pybullet_ids | {target_pybullet_id}
for i in range(len(ray_tos)):
    if not in_view[i]: blocked_targets.append(...); continue      # off-frame
    if not intercepted[i]: continue                                 # clear
    hit_obj_id = int(hit_ids[i])
    if hit_obj_id == target_pybullet_id: return "found_target", ...   # short-circuits, NO pixel-count gate
    if hit_obj_id in occ_set: occluder_hits += 1; blocked_targets.append(...)
    elif robot_id is not None and hit_obj_id == robot_id: robot_hits += 1; blocked_targets.append(...)
    elif hit_obj_id not in ignore_ids: detected_bodies.add(hit_obj_id)   # <- identity kept only as a SET, no counts
```
Note `found_target` triggers on a *single* endpoint's seg id matching the
target — there is no `DETECTION_MIN_PIXELS` floor on this path (that floor
only lives in the separate full-frame `detect_objects_from_render` used for
OBJECT-boxel registration and for the "localizable" filter in §2).

**Per-slice marginal tolerance (execution.py:203-259):**
```python
slice_fractions = [blocked_per_slice[si] / len(sl.points) for si, sl in enumerate(slices)]
blocked_fraction = max(slice_fractions)              # WORST slice, not global average
if blocked_fraction > SENSE_MARGINAL_BLOCKED_FRACTION:   # 0.05, perception.py:37
    ... return "still_blocked", blocked_fraction, set(), (b_min, b_max)
```
Classifying by the worst slice (not `blocked_total/len(ray_tos)`) is
deliberate (comment execution.py:205-221) so a fully-blocked coarse upper
slice cannot be diluted by hundreds of clear dense-slice rays.

**The four outcomes, in the order the function can return them:**
1. `found_target` (execution.py:191) — 0 blocked_fraction, no
   `blocked_bbox`.
2. `still_blocked` (execution.py:255) — `blocked_fraction` = worst-slice
   fraction; `blocked_bbox = (b_min, b_max)` — the padded union of every
   blocked endpoint's per-slice pad box, clamped to the fragment
   (execution.py:242-254); this is the "partial-reveal shrink" input
   consumed by `_shrink_shadow_fragment` (execution.py:1737-1779, called at
   execution.py:2286-2289 and, for a sibling, at execution.py:2059-2062).
3. `contains_nontarget` (execution.py:262) — `detected_bodies` non-empty,
   `blocked_bbox=None`.
4. `clear_but_empty` (execution.py:264) — nothing hit, nothing blocked.

**Interceptor identity available but DISCARDED, per decision point:**
- `still_blocked`: `occluder_hits` and `robot_hits` are separate *counts*
  (execution.py:170-171, 193/197), but **which specific occluder body id(s)**
  contributed to `occluder_hits` is never retained — only membership in
  `occ_set` is tested (execution.py:192); no per-id tally exists. If
  `shadow_occluder_map` under-lists the true blockers (stale census, see the
  cross-check in §1.2), the caller cannot tell "the robot" from "an
  unmodelled body" from the aggregate `occluder_hits`/`robot_hits` split
  alone — it happens to work in this run only because `robot_hits>0 and
  occluder_hits==0` gates a dedicated NOTE line (execution.py:228-230); the
  general case (mixed occluder + robot + unknown-body blocking) has no
  such disclosure at all.
- `contains_nontarget`: `detected_bodies` (execution.py:172) is a `set` of
  raw body ids with **no per-endpoint or per-slice breakdown** — unlike
  `blocked_targets`/`blocked_per_slice` for the blocked case, there is no
  equivalent `detected_targets`/`detected_per_slice` structure, so the
  caller cannot know *how many* endpoints saw the intruder, *where in the
  fragment* (which slice/z), or *how large* its footprint inside the shadow
  is — only "this set of body ids was seen somewhere." Combined with §2's
  finding (the print only fires when `detected_bodies` is *entirely*
  unlocalizable), the actual identity in `detected_bodies` is available in
  local scope at execution.py:1962 but never logged, never attached to the
  `ActionResult`, and never fed back into `blocked_giveup_shadows` bookkeeping
  beyond the boolean strike.

This is the diagnostic gap the investigation needs closed: at the exact
moment `shadow_of_red_object` (blue's real hiding place) took its 2nd and
3rd strikes (log:529, 583), `detected_bodies` held the answer to "what is
in here blocking `found_target`" and it was discarded before ever reaching
a print statement or a data structure a human/other-agent could inspect
post hoc.

---

## 4. Sibling batch-sense (execution.py:2022-2074)

**Trigger condition:** only reached from *inside* branch 3 (§1.2) — i.e.
only when the *primary* sense outcome is `clear_but_empty` or
`contains_nontarget` **with at least one localizable body** (the `if
sense_outcome in ("clear_but_empty", "contains_nontarget"):` gate at
execution.py:1991, which branch 2's early `return` at execution.py:1988-1989
never reaches). **It never ran in this failing episode** — no
"sibling fragment ... also observed empty" line appears anywhere in the log
(confirmed: neither `shadow_of_green_object` nor `shadow_of_red_object` ever
reached branch 3).

**Which fragments it re-checks (execution.py:2034-2041):**
```python
caster_id = shadow_boxel.created_by_boxel_id or shadow_boxel.created_by_object
caster_bd = registry.get_boxel(caster_id) if caster_id else None
...
if caster_bd is not None:
    for sib_sid in list(getattr(caster_bd, "shadow_boxel_ids", [])):
```
i.e. exactly the *siblings sharing the same casting object* (`caster_bd`),
enumerated from that caster's own `shadow_boxel_ids` list — **CONFIRMED:
"same caster only,"** matching the claim to verify.

**Removal condition (execution.py:2050-2072):**
```python
sib_outcome, _, _, sib_bbox = sense_shadow_from_render(sib_bd, target_pybullet_id, ...)
if sib_outcome != "clear_but_empty":
    if sib_outcome == "still_blocked" and sib_bbox:
        _shrink_shadow_fragment(...)          # partial-reveal shrink, not removed
    continue
belief.mark_sensed(sib_sid, found=False)
registry.remove_boxel(sib_sid)
...
```
**CONFIRMED: "clear_but_empty only"** for removal — a sibling that comes
back `still_blocked` is shrunk (not removed) and a sibling that comes back
`contains_nontarget` (localizable or not) is neither removed nor processed
for discovery — it is simply `continue`d past, silently. This means: (a) a
non-target object discovered inside a *sibling* fragment during a batch pass
does **not** get an OBJECT/SHADOW boxel the way the *primary* shadow's
`contains_nontarget` branch does (execution.py:2090-2245) — that discovery
pipeline only runs for the primary shadow, never for siblings; (b) a
sibling whose content is unlocalizable gets no strike counted against it at
all (the batch pass does not touch `blocked_counts`).

---

## 5. F5 chain — `grid_would_hit`, and every fragment-removal/`not_here` site

**Spawn-time findability contract:** `perception.grid_would_hit`
(perception.py:274-296) generates the *identical* endpoint list
`sense_ray_slices` would produce for a given fragment AABB and segment-tests
it against the target's (1 mm-shrunk) AABB — pure geometry, no physics
client. Consumed at two points:
- `test_full_pipeline.py:2173-2200` (pre-flight, inside the seed-retry
  loop, on a throwaway `probe_env`): every oracle-hidden target must have
  `grid_would_hit(...)==True` for at least one final F3 shadow fragment
  that contains its position, else the seed is re-rolled
  (`RuntimeError("F5 pre-flight: ...")`, retried at
  `test_full_pipeline.py:2219-2225`).
- `test_full_pipeline.py:687-714` (Phase 4, on the *real* env): used to pick,
  among all shadow fragments containing the hidden target's position, the
  one the guarantee actually applies to, for the oracle log line
  (`target_to_shadow[tname] = shadow_id`).

**Both consult sites check the ORIGINAL, pre-episode fragment geometry.**
There is no re-verification anywhere in the codebase that `grid_would_hit`
still holds after a fragment's bounds change mid-episode — confirmed by
`grep grid_would_hit` across `execution.py`: the only match
(execution.py:150, a comment) is not a call. Concretely, the F5 guarantee
was checked once, against `shadow_of_red_object`'s *original* AABB (min
`[-0.0327,-0.2198,0.325]`, max `[0.0711,0.1122,0.4615]` —
`boxel_data.json:212-220`); after Plan #5's `still_blocked` shrink
(log:468) the *live* fragment is a different, smaller AABB
(4.3×8.3×9.1 cm) that `grid_would_hit` was never re-run against.

**Every site that removes a fragment or marks it `not_here`, and whether
target-in-fragment-per-`grid_would_hit` survives it:**

| Site | file:line | Trigger | Registry effect | Observation-backed? | Could it discard a `grid_would_hit`-approved fragment while the target is really in it? |
|---|---|---|---|---|---|
| A. `found_target` | execution.py:1879-1951 | target's own seg id hit | none (fragment kept; belief=found) | yes, direct hit | N/A — this is the success path |
| B. `contains_nontarget` giveup, 3 strikes | execution.py:1972-1978 | `blocked_counts[sid]>=3` on the unlocalizable path | `belief.mark_sensed(False)` only; **boxel geometry NOT removed** | **NO** — "the content stays unmodelled" is a repeated *non-empty, unresolved* observation, not a confirmed-empty one (execution.py:1975-1976 says so explicitly) | **YES — this is exactly what happened in this run.** `shadow_of_red_object` is `grid_would_hit`-approved (F5 pre-flight passed for this seed, per the task's own facts) and genuinely contains blue, yet it was marked `not_here` at log:584 purely because 3 consecutive senses could not localize *something else* in it. The planner now treats it as eliminated even though the guarantee's target is still physically there. |
| C. `still_blocked` giveup, 3 strikes | execution.py:2290-2301 | `blocked_counts[sid]>=3` on the blocked path | `belief.mark_sensed(False)` only; boxel geometry stays at its last-shrunk extent | **NO** — the print itself says "Shadow is NOT observed empty" (execution.py:2293-2295), citing audit #47 as unaddressed | Same structural risk as B: a shadow can be given up purely for *repeatedly failing to clear*, independent of whether the target sits in the still-unobserved sub-region. |
| D. `clear_but_empty` / localized `contains_nontarget` | execution.py:1991-1995, 2064-2072 (sibling) | every grid endpoint observed clear (or all localizable discovered bodies handled) | `belief.mark_sensed(False)`; `registry.remove_boxel(sid)` — fragment fully deleted | **YES** — every endpoint of the *current* (possibly already-shrunk) fragment rendered clear/resolved | Only unsafe if the *current* fragment geometry has drifted from what `grid_would_hit` was checked against (see the shrink caveat above) — for an *unshrunk* fragment this is the safe, intended elimination path the F5 guarantee is designed to protect. |
| E. `retire_lost_objects` (object-lost path) | execution.py:1698-1734 | a STALE object's *own* AABB (not the shadow's) renders confirmed-empty via `refresh_object_aabbs(check_lost=True)` | removes **all** of that object's `shadow_boxel_ids` wholesale (`registry.remove_boxel(sid)`, `belief.mark_sensed(sid, found=False)`) | Partially — backed by the *object's* emptiness, not by an independent re-sense of the *shadow* region itself | **Architectural gap (CONFIRMED by code, not exercised in this run):** a shadow can have *multiple* blockers (`compute_shadow_blockers` explicitly supports this, execution.py:267-422), but `shadow_boxel_ids` links a shadow only to its *original creator*. If that creator goes LOST while a second, independent blocker still stands, this path deletes the shadow (and marks it `not_here`) without ever re-checking whether the shadow's own grid is now actually clear — no call to `sense_shadow_from_render` occurs here at all. Did not fire in this run (0 "LOST object(s)" lines in the whole log — see §6). |

**Bottom line for the guard we must not break:** the F5 spawn-time promise
(`grid_would_hit`) is only ever checked once, against the *original*
fragment. Sites B and C above can eliminate a shadow from planner
consideration (`belief`-level `not_here`) on a policy timeout (3 strikes)
that carries **no geometric proof of absence**, and B is confirmed
(CONFIRMED, log:584) to be the mechanism that wrote off blue's actual
hiding place in this run — not a `clear_but_empty` (safe) removal, and not
a `grid_would_hit` failure at spawn (the task's own facts state the pre-
flight guarantee held for this seed).

---

## 6. `refresh_object_aabbs` (execution.py:1580-1695) + `retire_lost_objects` (execution.py:1698-1734) — why orange was never retired

**Log fact (CONFIRMED):** grepping the entire log for `LOST` or `retired`
returns zero matches — `retire_lost_objects`'s own print
("`-> retired LOST ...`", execution.py:1733-1734) never fires in this run.
Every one of the 7 stale-orange refreshes ends in the "keeping last
estimate" branch (execution.py:1691-1694).

**Does the 3c check run on every sense-action refresh site? YES (CONFIRMED
by code):** every `refresh_object_aabbs` call inside `handle_sense_action`
passes `check_lost=True` (execution.py:1946, 1983, 2262, 2307), and so does
the transit-loss handler that produced the *first* stale report
(`test_full_pipeline.py:1573-1574`, right after the EmptyHandError from
Plan #1's failed place, log:145-148). So the 3c path is armed at every one
of the 7 occasions orange showed up stale — it simply never concluded
"lost."

**Exact condition for LOST (quoted, execution.py:1666-1686):**
```python
lost = []
if stale and check_lost and render is not None:
    depth_m, seg, view_m, proj_m = render
    for oid in list(stale):
        if oid in exclude_ids:
            continue
        bd = registry.get_boxel(oid)
        if bd is None:
            continue
        slices, _ = sense_ray_slices(bd.min_corner, bd.max_corner)
        observed_empty = bool(slices)
        for sl in slices:
            icp, _hids, in_view = first_surface_interceptors(
                sl.points, depth_m, seg, view_m, proj_m)
            not_visible = np.count_nonzero(icp | ~in_view)
            if (not_visible / len(sl.points)
                    > SENSE_MARGINAL_BLOCKED_FRACTION):
                observed_empty = False
                break
        if observed_empty:
            stale.remove(oid)
            lost.append(oid)
```
Two structural facts explain why this never fires for `orange_object` in
this run:

**(i) The tested region is `bd.min_corner`/`bd.max_corner` — orange's
*frozen, never-updated* registry boxel — not orange's true current
position.** Earlier in the same function, the geometry-update branch that
would move an OBJECT boxel to a fresh estimate only executes when a
detection exists (`det is not None`, execution.py:1644-1664); for a stale
object `det is None` and the loop does `stale.append(obj_boxel.id);
continue` (execution.py:1645-1646) — the boxel's `min_corner`/`max_corner`
are **never touched**. Since `orange_object` has had `det is None` at
*every* observation from the very first failed place onward (log:148
onward), its registry boxel has sat frozen at its **pre-pick spawn
position** (`boxel_data.json:88-99`: min `[0.1328,0.1377,0.325]`, max
`[0.1870,0.1919,0.4585]`) for the rest of the episode. The check therefore
never asks "is orange's *actual* current resting spot empty" (unknown —
orange is invisible to the camera wherever it truly is, since it never
regains a detection either); it only ever asks "is orange's *old pick
site* now empty of anything," a completely different question from where
the flung object physically is.

**(ii) The interceptor test used inside this loop has no ignore-list at
all.** Contrast with `sense_shadow_from_render`, which builds an explicit
`ignore_ids = {-1, robot_id} | support_body_ids | occluder_pybullet_ids |
{target_pybullet_id}` before classifying a hit (execution.py:128-135) —
robot links, table/tray, and known occluders are all excluded from counting
as a blocker. The check-lost call at execution.py:1677-1678,
`first_surface_interceptors(sl.points, depth_m, seg, view_m, proj_m)`,
passes **no such set** — `first_surface_interceptors` itself takes no
ignore-list parameter (perception.py:231-271; its signature has no
`ignore_ids`/`robot_id`/`support_body_ids` argument at all). So `icp[i]`
(intercepted) is `True` for *any* rendered surface in front of an endpoint
— the robot arm, a tray wall, or any other dynamic body — with zero
discrimination between "a legitimate reason this region can't be confirmed
empty right now" and "the object is still/again there." The
`not_visible = icp | ~in_view` mask folds all of these into one undcircumscribed
bucket, and a single slice exceeding the 5% marginal tolerance
(`SENSE_MARGINAL_BLOCKED_FRACTION`, perception.py:37) is enough to keep the
object "stale," never "lost." The code comment at execution.py:1621-1623
states the intended semantics plainly: *"A stale object whose region is
occluded (arm, another body, tray walls) stays kept-with-last-estimate as
before — cannot see, cannot claim"* — but because of (i), "the region" here
means orange's stale spawn-site, not orange's real location, so this
conservative-by-design behavior ends up protecting a fiction (the spawn
site) rather than the genuinely unresolved unknown (orange's real
whereabouts).

**HYPOTHESIS (not verified by a probe):** which specific surface keeps
intercepting orange's frozen spawn-site footprint on every one of the 7
checks is not determinable from static code/log reading alone. The most
plausible code-consistent candidate is the robot arm itself (it is the one
body guaranteed to be near the workspace at every sense instant, and it
already causes an analogous coarse-slice block for `shadow_of_red_object`
attempt 1, §1.2's arithmetic cross-check) rather than orange's own
displaced body, since `orange_object`'s spawn AABB (`x≈0.133-0.187,
y≈0.138-0.192`) sits geometrically apart from every shadow region sensed in
this run (`shadow_of_green_object`: `x≈-0.226..0.041, y≈0.228..0.5`;
`shadow_of_red_object`: `x≈-0.033..0.071, y≈-0.220..0.112`,
`boxel_data.json:130-247`) and from `free_005`
(`x≈-0.1..0.1, y≈-0.4..-0.3`), the intended (failed) place target of the
object that got flung. Confirming this would require rendering the seg
mask at one of the 7 timestamps — out of this task's pure-reading scope.

**Net effect on the episode:** because orange is neither re-detected nor
retired, `refresh_object_aabbs`'s "keep last estimate" clause
(execution.py:1602-1603, "An object with no detection at all... keeps its
last estimate — honest staleness, logged") leaves `orange_object`'s boxel
sitting at its spawn position for the planner's entire remaining init-fact
generation, `obj_at_boxel('orange_object')` stays pinned there in every
subsequent `_build_init` (matches log:73, 158, 260, 314, 369, 486, 540, 595:
`'orange_object': ['orange_object']` unchanged across all 8 plans), and no
mechanism in this codebase ever revisits that belief — the object is
simply gone from the planner's reachable world while remaining "known" at a
stale location it provably is not at.

---

## Report metadata

- `unlocalizable_condition` (§2): `detected_bodies` non-empty **and**
  `body_id_to_name[b] not in sense_detections` for every `b` in
  `detected_bodies` — i.e. every intercepting body's whole-frame pixel
  count is below `DETECTION_MIN_PIXELS=6` (perception.py:320,
  applied at perception.py:404-406; tested at execution.py:1962-1971).
- `strike_counter_site`: `blocked_counts` dict, declared
  `test_full_pipeline.py:1013`, shared across the `contains_nontarget`-
  unlocalizable branch (execution.py:1967) and the `still_blocked` branch
  (execution.py:2277) for the same shadow id.
- `f5_removal_sites`: see the table in §5 (rows A-E, file:line in the
  "Site" column).
- `lost_object_gap`: §6 (i)+(ii) — the check-lost region is frozen at the
  object's last-detected (here: pre-pick spawn) boxel, and the interceptor
  test it uses has no robot/support/occluder ignore-list, so any surface in
  front of that frozen footprint — not necessarily the object itself — is
  enough to keep it "stale" forever instead of "lost."
