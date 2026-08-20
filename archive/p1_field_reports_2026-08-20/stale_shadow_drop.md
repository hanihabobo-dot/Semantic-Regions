# Stale shadow drop bug — investigation notes

Bug: stack scene, --goal stack --stack-height 4 --n-objects 4 --seed 0 (2026-08-15 GUI run).
After 3-block tower built, arm picks 4th block, moves above the stale SHADOW of a previously
stacked block's original location, releases it there; run ends "no plan found".

## Status — COMPLETE
- [x] Run identified: run_2026-08-20_20-21-49 (user's GUI run; clock skew — see correction
      section). Earlier round run_2026-08-15_22-11-32 = same code, truncated log, identical
      prefix values.
- [x] Action sequence reconstructed (audit-#58 release-in-place, NOT a planned place/stack)
- [x] Shadow lifecycle: creation-only in stack runs; removal exists only via sense
- [x] Terminal no-plan: #P1 10 mm FK gate rejects all level-4 stack IK, deterministically
- [x] Verdict: (c), with real-but-benign stale shadow (registry+viz) explaining the visual

## Findings

### Run identification
- User's 2026-08-15 GUI run = `logs/run_2026-08-15_22-11-32/` (stack, h=4, n=4, seed 0, gui=True).
  Its .log is TRUNCATED at the first stack action's pre-release diag (11.6 KB, no
  timing_summary.json) — tail lost (run under WSL, log on /mnt/c; process ended without flush).
- Headless twin same day: `logs/run_2026-08-15_16-45-22/` (h=4 seed 0, gui=False, complete,
  different downstream physics: tower toppled, ended PHYSICAL_FAILURE after 3 plans).
- COMPLETE GUI REPRODUCTION: `logs/run_2026-08-20_20-21-49/` (identical config incl. gui=True;
  identical plan #1 prefix down to pad_normal_force=491.42N and identical #84-diag values
  => deterministic same trajectory as the user's truncated run). This run ends exactly as the
  user described: 3-block tower, 4th block picked, carried to a spot away from the tower,
  released, then "ERROR: No plan found!".

### Reconstructed action sequence (run_2026-08-20_20-21-49.log line refs)
- PLAN #1 (L64-161): pick green "PICKED UP" (pad force 491N) but block NEVER MOVED
  (pre-release pos=[0.1394,0.2036,0.3500] = green's original spot; live_obj_z=0.35);
  drop-verify failed 3x -> "clearing held state and replanning (audit #79)".
- PLAN #2 (L163-308): full 12-action plan.
  - green picked (80N) and STACKED on blue (L257).
  - red picked and STACKED on green (L283). Tower = blue+green+red done.
  - orange (4th block) picked (L295).
  - move "to red_object" = move to q_stack_orange_object_on_red_object_12, whose ee_target
    was computed AT PLAN TIME as [0.02442, -0.06159, 0.49999] (L205) = RED'S ORIGINAL TABLE
    POSITION (red still on table when plan #2 was generated). So the arm carries orange to a
    hover above red's OLD spot — exactly where shadow_of_red_object still sits in the GUI.
  - stack handler recomputes live contact: contact_ee=[0.2023,0.1210,0.5204] (tower top, L305)
    -> solve_ik REJECTED, FK error 29.4 mm (L306) -> "IK failure during stack — replanning
    (audit #30)" (L308).
- PLAN #3a while HOLDING orange (L310-357): planner needs compute-stack-kin(orange,red);
  approach target [0.20232, 0.12099, 0.59997]; ALL 8 IK seeds FK-rejected
  (errors 25.0/17.6/42.5/21.2 mm, L344-348) -> outcome=no_plan ->
  "audit #58: planner found no plan with orange_object held — falling back to
  release-and-replan." (L357).
- RELEASE-IN-PLACE (L358-366): "Replanning while holding orange_object — releasing." at
  pre-release pos=[0.0242,-0.0627,0.4800] -> "Dropped orange_object at (0.023, -0.07, 0.35)"
  = RED'S ORIGINAL POSITION. Post-drop shadow blockers (audit #78, L361-365):
  shadow_of_red_object blocked by ['orange_object'] — orange physically landed INSIDE the
  stale shadow region of red. This is the exact moment the user saw.
- PLAN #3b after release (L367-417): plan found (re-pick orange, stack on red), but
  compute_stack_kin again FK-rejects ALL 8 seeds for the SAME target
  [0.20232, 0.12104, 0.59997] (identical error values 25.0/17.6/42.5/21.2 mm — deterministic,
  L400-404); complexity bump + sampling finds nothing new -> "ERROR: No plan found!" (L417)
  -> "FAILED: Planner returned no plan (4 unsearched shadows remaining)" (L420).

### Interpretation so far
- The drop above the stale shadow is the audit-#58 release-in-place fallback, executed while
  the arm was parked at the STALE plan-#2 stack config (computed from red's pre-move pose).
  The stale shadow wireframe at red's original spot made it LOOK like the planner targeted
  the shadow; it did not.
- Terminal no-plan root cause: FK-verified IK gate rejects every seed for the level-4 stack
  approach pose z=0.5999 above [0.2023,0.1210] (min FK error 17.6 mm > gate). Deterministic
  -> replans can never succeed.
- Shadow staleness is real (shadow_of_red_object persists after red stacked; only its
  BLOCKERS list is recomputed) but did NOT poison the goal/plan in this episode.

## Run identification — CORRECTED (coordinator note 2026-08-20)
Machine clock was 5 days behind until ~20:00 tonight. `run_2026-08-20_20-21-49` IS the
user's latest GUI run of stack h=4 seed 0 (primary evidence, complete log).
`run_2026-08-15_22-11-32` is the user's EARLIER round of the same check (same branch code,
[#P1-diag] markers present); its log truncates at plan #1's first stack pre-release but the
147 lines it does have are byte-for-byte-value identical to 20-21-49 (pad force 491.42N,
same #84-diag numbers) — deterministic same trajectory, so both rounds showed the same bug.

## Code evidence (all paths absolute, branch p1-real-grasp-perception @ 41ecb04)

### Shadow lifecycle
- CREATED once: shadow_calculator.py:242-255 (BoxelData(boxel_type=SHADOW,
  created_by_object=...)), from the Phase-2/3 startup pass ("27 boxels, 4 shadows"); in the
  stack scene the 4 cubes cast them (no occluders). Also created for newly-discovered
  objects in sense's contains_nontarget branch.
- REMOVED only in two places, BOTH gated on a sense action:
  - execution.py:1354 (handle_sense_action, outcome clear_but_empty/contains_nontarget:
    registry.remove_boxel(sid_str) + viz cleanup)
  - execution.py:1413-1422 (discovery cleanup: removes an object's OLD shadow entries when
    the object is re-registered)
- NO path removes/recomputes a shadow when its CASTING object is picked/placed/stacked:
  - refresh_object_aabbs, execution.py:1186-1217 — docstring 1192-1195: "SHADOW boxels are
    NOT recomputed here — accepted thesis gap per user-explicit scope cut".
  - post-stack registry update, test_full_pipeline.py:1559-1577 — refreshes ONLY the stacked
    cube's OBJECT boxel AABB; shadows untouched.
  - reboxelize_free_space, reboxelize.py:41-44 — treats every SHADOW boxel as a static
    obstacle when re-partitioning free space; never removes one.
  - compute_shadow_blockers (execution.py:166) recomputes only WHO currently blocks the
    camera ray to each (fixed) shadow region — the region itself never moves/expires.
- => In stack runs (goal never emits sense actions) every initial shadow survives the whole
  episode in BOTH registry and GUI, regardless of where its caster went. Structural, and
  pre-existing (not introduced by #P1; #P1 only made the downstream failure reachable).

### The release above the stale shadow (audit #58 fallback, NOT a planned place)
- Log proof: no "Placing X at" line; instead "audit #58: planner found no plan with
  orange_object held — falling back to release-and-replan." + "Replanning while holding
  orange_object — releasing."
- Caller: test_full_pipeline.py:1075-1093 (plan is None and held_obj_name is not None ->
  release_held_object_in_place).
- release_held_object_in_place: execution.py:~490-592 — opens the gripper at the arm's
  CURRENT configuration, no repositioning; reads back joints as "post_emergency_drop"
  (execution.py:582-588). It DOES mark registry dirty + recompute shadow BLOCKERS
  (execution.py:576-580) but does not touch shadow geometry.
- Why the arm was parked there: plan #2's move had delivered orange to
  q_stack_orange_object_on_red_object_12, whose ee_target [0.02442,-0.06159,0.49999] was
  computed AT PLAN TIME from red's then-current table AABB (compute_stack_kin_solution
  reads the support's live AABB at planning time, streams.py:1211-1217; the docstring
  1173-1179 explicitly says execute_stack "salvages this at runtime via a fresh IK against
  the support's live AABB"). Red then got stacked; the config went stale; the salvage IK
  failed (below); the fallback released orange right where the arm was = above red's
  ORIGINAL spot = the persisting shadow_of_red_object region. Post-drop blockers line
  confirms: "shadow_of_red_object blocked by: ['orange_object']".

### Terminal no-plan root cause: #P1 FK-verified IK gate at the level-4 stack pose
- Gate (10 mm) added by #P1:
  - execution side: robot_utils.py:498-504 (solve_ik, fk_err > 0.010 -> None; comment block
    474-494 dated 2026-08-20)
  - planning side: streams.py:328-334 (_pybullet_ik; comment 307-317: added so planner
    "certifies at execution standard", commit f55901e)
- Level-4 numbers: red tower-top AABB top_z=0.4750; held half height 0.025; fixed grasp
  z-offset 0.10 (sample_grasp yields exactly ONE grasp, _GRASP_Z_OFFSETS=[0.10],
  streams.py:561, straight-down orientation streams.py:591) -> stream stack-kin EE target
  [0.2023, 0.1210, 0.5999] (streams.py:1228-1229). Runtime contact target z=0.5204
  (execute_stack live recompute, execution.py:1020-1041, seeded from the STALE planner
  config, execution.py:1063-1064).
- Both fail the gate: runtime 29.4 mm (log L306); stream: all 8 seeds (IK_NUM_SEEDS=8,
  REST_POSES+offsets, streams.py:210/350-356) rejected at 25.0/17.6/42.5/21.2 mm — twice,
  with IDENTICAL values (log L344-348 and L400-404). Deterministic: single grasp, fixed
  seeds, fixed orientation => replanning can never produce a level-4 stack kin. Panda base
  [-0.4,0,0] (boxel_env.py:747), table top 0.325 (boxel_env.py:728-732): EE at horizontal
  0.61 m + z 0.60 with wrist vertical is at the reach margin; PyBullet IK (100 iters,
  residual 1e-4, streams.py:207-208) converges no closer than ~18 mm there.
- Level-3 comparison: contact z=0.4704 runtime IK PASSED (log L279-283) — the ceiling bites
  between z=0.47 and z=0.52 (contact) / 0.60 (approach).
- Weld-era h=4 runs (2026-06-06, seeds 89/92/94) also never completed level 4 (drop-verify
  tilt-90 failures, one pre-P1 no-plan) — level-4 was already marginal; #P1's gate turned
  it into a clean deterministic no-plan.

### Verdict: (c), with a real but non-causal (b)-style stale shadow
- (c) The drop location was coincidental-but-explainable: audit-#58 release-in-place at the
  stale plan-#2 stack config, which by construction hovers over the support's ORIGINAL
  location — the same place its stale shadow still displays. The planner never targeted a
  shadow; no place action was involved.
- The stale shadow itself is REAL and lives in BOTH registry and viz (creation-only
  lifecycle in stack runs), so it is not purely visualization — but in this episode it
  poisoned nothing: init deltas are only blocks_view_at 100->101 and blocker reshuffles;
  boxel_fits stayed 48; the stack goal never consults shadows. "(4 unsearched shadows
  remaining)" in the FAILED banner is cosmetic reporting.
- (a) is ruled out for THIS failure: the no-plan is fully explained by the FK-gate
  rejections; identical failure would occur with shadows deleted.

## Minimal fix proposal (no edits made)
1. PRIMARY — make level-4 stack kin pass the FK gate (restores h=4):
   a. streams.py:561 `_GRASP_Z_OFFSETS = [0.10]` -> add lower approach offsets, e.g.
      [0.10, 0.06] (sampler then has a reachable alternative when 0.10 fails the gate;
      sample_grasp already shuffles/iterates offsets, streams.py:599-601). AND/OR
   b. IK refinement at the reach edge: in streams.py:_pybullet_ik (after line 289) and
      robot_utils.py:solve_ik (after line 457), re-invoke calculateInverseKinematics seeded
      from its own previous output 2-3 times (or raise maxNumIterations well above 100)
      BEFORE the 10 mm gate — PyBullet's iterative IK routinely needs restarts to converge
      near the workspace boundary; 17-21 mm residuals are recoverable if the pose is
      reachable.
   c. Cheap runtime half: execute_stack (execution.py:1063) falls back to a second solve_ik
      seeded from REST_POSES when the stale-config-seeded attempt fails (fixes the 29.4 mm
      rejection when the plan-time config went stale). Not sufficient alone — the stream
      gate still blocks the replan.
2. SECONDARY — shadow hygiene so the GUI/registry stop lying after a caster moves:
   in the post-stack registry refresh (test_full_pipeline.py, immediately after the OBJECT
   AABB refresh at 1564-1577), retire the stacked cube's cast shadows exactly like the
   discovery cleanup does: for old_sid in list(bd.shadow_boxel_ids): registry.remove_boxel,
   viz.remove_boxel_viz, shadows.remove, shadow_occluder_map.pop, boxel_centers.pop; then
   registry dirty -> next reboxelize frees the region. Mirror in the place handler and in
   release_held_object_in_place (execution.py after line 572). Removal-only is consistent
   with the documented scope cut at execution.py:1192-1195 (no shadow RECOMPUTE required).
3. OPTIONAL — de-weird the #58 fallback: in release_held_object_in_place (execution.py,
   before _release_and_verify_drop at line 545), lift/retract to a safe hover before
   opening the fingers, so emergency drops stop landing at stale plan configs. Cosmetic;
   not the failure cause.
