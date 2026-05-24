# TAMPURA Plan / Comparison

Created: 2026-05-12 (later)
Revised: 2026-05-23 - deep review.  The 2026-05-21 AI-drafted C1-C5
         items were checked against the actual TAMPURA source
         (../tampura, ../tampura_environments) and our own code.
         Several claims were wrong or overstated (see "Corrections").
         Restructured around ONE goal: a same-task comparison on the
         missing-dice (find_dice) problem.  Items not serving that
         goal (old C3 hybrid, C5 nested-occlusion) moved to a marked
         tail.
Revised: 2026-05-24 - second review.  Re-verified every 2026-05-23
         CORRECTION against source (all accurate -- see "SECOND REVIEW")
         and did a realism pass.  T1 was missing abstract.tex and the
         thesis's OWN self-contradiction; the holding==find_dice
         equivalence and the "TAMPURA trades success for speed" framing
         were overstated; T2 assumed a move-to-reveal capability the
         thesis flags as future work; the CAVEAT mis-stated our reveal
         mechanism.  Expanded T1/T2/CAVEAT accordingly.

Purpose: dedicated home for TAMPURA-related issues and the find_dice
         comparison plan.

GOAL (scope - read first)
-------------------------
We compare ONLY on the missing-dice problem (TAMPURA's find_dice).
find_dice = a die hidden under one of 1-5 cups; goal = pick up the die
and return home.  Its task analogue in OUR system is the `holding`
goal (find a hidden target, pick/hold it) -- NOT find-and-tray-stack.
Everything below is scoped to producing an honest same-task
comparison; anything else is out of scope (see the tail).

CORRECTIONS (verified against source this review; supersede the
2026-05-21 claims)
------------------
- PLANNER.  TAMPURA uses SymK, which is a TOP-K FORK of Fast Downward
  (tampura/solvers/symk.py shells out to third_party/symk/
  fast-downward.py with `--search symk-<dir>(...)`).  So "SymK, not
  FastDownward" is a false split: SymK enumerates K skeletons via an
  FD derivative; we use vanilla FD (single plan) inside PDDLStream.
  Both descend from FD.  (Memory reference_tampura_perf.md says
  "FastDownward in both systems" -- also imprecise; fix it + the
  thesis related-work wording.)
- SINGLE-PROCESS.  TAMPURA's planner is single-process (paper Algs 2
  & 3 are sequential nested loops; no parallelism).  It ran on a Xeon
  Gold 6248 but used ONE core.  So the thesis caption "20-core Xeon
  vs our 8-core" overstates the gap -- the real axis is single-core
  clock, and the gap is small/uncertain.
- find_dice MECHANICS (tampura_environments/find_dice/env.py,
  env_generator.py).  The die is placed AT a cup's XY, under an
  upside-down cup; a scene is saved only when the die is NOT
  camera-visible; 1-5 cups, one hides the die, the rest are decoys
  -- SINGLE-LAYER occlusion.  Goal = holding(die) AND at-home
  (env.py:1004).  Placement is continuous-pose, view-blind
  (placement_sample; no visibility check).  The 15 mm voxels live in
  the belief only -- never planner predicates (the abstract belief
  emits only known-pose/holding/is-target/moved/at-home).
- OCCLUSION MODE differs.  find_dice = a cup COVERING the die
  (containment; revealed by MOVING the cup -- the look action's
  success depends on moved(occluder)).  Ours = a LATERAL shadow
  behind a box occluder (shadow_calculator casts AABB shadows from
  the camera).  This bounds what "same problem" can mean -- see the
  occlusion-mode caveat below.
- CHECKOUT STATE.  ../tampura_environments is a sparse checkout; only
  find_dice is on disk.  panda_utils (pb_utils, panda_env_utils,
  robot, voxel_utils, placement_sample -- ALL imported by find_dice)
  is NOT present, so find_dice cannot run as-is.  ("only find_dice +
  voxel_utils checked out" was wrong: voxel_utils is a module inside
  panda_utils.)  Read any tracked file without materialising it via
  `git -C ../tampura_environments show HEAD:<path>`.
- THESIS LOCATION.  The proposal migrated to thesis/ (see
  proposal-template_PRE_MIGRATION.pdf).  The comparison lives in
  thesis/chapters/results.tex `\subsection{Comparison with TAMPURA}`
  (label subsec:tampura, figure fig:tampura) -- NOT "proposal-template"
  / "eval-chapter Plot 9".  There is no thesis_audit #159 (the
  2026-05-21 draft invented it).

SECOND REVIEW (2026-05-24) -- verification + realism pass
---------------------------------------------------------
VERDICT: the 2026-05-23 CORRECTIONS were re-checked against source and
are ACCURATE.  Confirmed on disk (real paths nest one level:
tampura/tampura/..., tampura_environments/tampura_environments/...; the
shorthand below drops the outer dir, as the rest of this file does):
  * SymK = top-k FD fork -- solvers/symk.py:69 builds
    `symk-<dir>(...,plan_selection=...(num_plans=num_skeletons))`
    shelling out to ../third_party/symk/fast-downward.py.
  * find_dice goal = holding(die) AND at-home -- env.py:1004 verbatim.
  * 15 mm voxels stay in the belief -- GRID_RESOLUTION=0.015 (env.py:36);
    abstract() emits only known-pose/holding/at-grasp/is-target/moved/
    at-home (env.py:306-321); no predicate is voxel-indexed.
  * look success depends on moved(occluder) -- env.py:966
    `depends=[Atom("moved",["?o2"])]` (comment "looking behind ?o2");
    place sets moved (env.py:955).  Reveal == relocate occluder.
  * continuous-pose place -- place-sample certifies a pose, env.py:913-919.
  * 1-5 cups / die-under-a-cup / save-only-when-hidden -- env_generator.py
    :85, :126-128, :168-180.
  * single-process -- no multiprocessing/Pool/threading in the planner
    (only the DQN baseline + the SymK C++ *build* touch cpu_count).
  * thesis location -- results.tex:206 subsec:tampura; no thesis_audit
    #159 (grep absent).
  Minor: "die at cup's XY" is the cup's full pose point
  (env_generator.py:127, occlusion outcome identical); "view-blind
  placement_sample" lives in the un-checked-out panda_utils, so it is
  inferred (and independently asserted by discussion.tex:101), not read.

WHAT THIS PASS ADDS (the 2026-05-23 plan was accurate but optimistic):
  1. T1 missed abstract.tex (carries the headline) AND the fact that the
     thesis ALREADY contradicts itself: the figure/abstract/results call
     find-and-tray-stack "the closest analogue", but discussion.tex:101
     already calls TAMPURA's Find Die "the closest analogue to our
     setting".  T1 is contradiction-RESOLUTION.
  2. holding==find_dice was overstated -- our holding goal is (holding ?o)
     ONLY; find_dice adds at-home (a final go-home).  And the
     planning-vs-episode time-measure parity was left unstated.
  3. The "TAMPURA trades success for speed" direction is UNVERIFIED -- our
     own holding success is only ~42 %; need TAMPURA's Table II number.
  4. T2 assumed our system can solve a find_dice-equiv AT ALL; deliberate
     view-restoration is flagged "future work" (discussion.tex:101) and
     bounded by a give-up rule.  Feasibility must be smoke-tested first.
  5. The CAVEAT mis-stated our reveal mechanism (we cannot raycast a
     view-blocked region; reveal requires relocation, like find_dice).

GOVERNING GATE (supervisor, 2026-05-06)
---------------------------------------
"Comparison with lw1 and tampura only after finishing the thesis if I
have >= 1 week free."  This gates empirical RUNS (T2, T3 below).  It
does NOT gate fixing the honesty of the ALREADY-CITED comparison
(T1) -- that is thesis-now editing of an existing figure/section.

Currently-open TAMPURA work
---------------------------
- #66 (place fails when object > cell).  Plan A [DONE on main
  2026-05-09]; Plan C [PENDING on audit-64-tampura-binary-grid].
  SCOPE NOTE: #66 Plan C is an INTERNAL uniform-baseline correctness
  fix (continuous-pose place for the uniform ablation).  It is NOT the
  find_dice comparison and is not required for it -- the comparison
  uses our SEMANTIC system.  The #66 body below is UNCHANGED: it is a
  shared-across-branches artifact (see its own Care note), so it must
  not be edited on this branch.
- T1 -- honesty fixes to the cited fig:tampura comparison (thesis-now).
- T2 -- run our holding pipeline on a find_dice-equivalent scene.
- T3 -- stand up & run real TAMPURA find_dice on our hardware.
- CAVEAT -- occlusion-mode mismatch (comparability boundary).

Related (closed, in archive):
- #10 [DONE 2026-05-08] -- uniform voxelization baseline (free-space-
  only swap).
- #64 [DONE 2026-05-08] -- TAMPURA-faithful GUI framing.

Tail (NOT the find_dice comparison): old C3 (hybrid) and C5 (nested
occlusion) are preserved at the bottom under their own banner.
================================================================================
#66. UNIFORM/TAMPURA BASELINES — PLACE FAILS WHEN OBJECT > CELL (split fix)
================================================================================
Status:   Plan A [DONE on main 2026-05-09 (later)] — auto-tune cell
          size landed in test_full_pipeline.main.  Plan C [PENDING on
          audit-64-tampura-binary-grid] — continuous-pose placement
          (the actual TAMPURA-faithful approach).
Priority: TIER 1 — correctness blocker for the uniform baseline.
          Without this, --baseline uniform with default cell size
          0.05 m cannot ground occluder-relocation place actions
          (default occluders are 5-7 cm wide, 12-16 cm tall; no
          uniform cell satisfies boxel_fits).  The 2026-05-09
          stalled run (logs/run_2026-05-09_10-48-13/) was a direct
          consequence: PDDLStream looped at increasing complexity
          searching for a plan that cannot exist.
Where:    Two-branch fix.  Plan A on `main` (the free-space-only-
          swap baseline), Plan C on `audit-64-tampura-binary-grid`
          (the TAMPURA-faithful baseline).  ONE shared issue body
          across both branches: edit on main, merge forward.
          Plan A:  test_full_pipeline.main (auto-tune cell size).
          Plan C:  pddl/domain_pddlstream.pddl + pddl/stream.pddl
                   + streams.py (sample_place_pose) +
                   pddlstream_planner._build_init + execution.py
                   place handler.
Depends:  None — independent of in-flight work.

What:  Under --baseline uniform, free cells are 5 cm cubes
       (default --uniform-cell-size 0.05).  test_boxel_fits
       (streams.py:350-371) compares full AABB extents of the
       OBJECT vs the candidate destination cell.  Default scene
       occluders are 5-7 cm wide and 12-16 cm tall (boxel_env.py:
       296-317), so for any 6-7 cm occluder the comparison
       0.05 >= 0.07 fails on every uniform cell.  Result: zero
       (boxel_fits occluder ?cell) atoms emit; the PDDL place
       action's precondition is unsatisfiable; any plan that
       requires relocating an occluder fails to ground.

       Quantified from the 2026-05-09 stalled run log:
       - 2480 cells emitted under uniform 0.05 m
       - 2472 boxel_fits atoms (~25% of 4 visible obj × 2470
         free cells = ~9880 candidate pairs)
       - The passing 25% are the 4 cm targets fitting in 5 cm
         cells; the failing 75% are 6-7 cm occluders
       - PDDLStream stalled at iter-1 (Cost: inf, Search Time
         0.010 s) because no skeleton can satisfy place

       Three options were considered:
         (A) Auto-tune cell size to fit the largest visible AABB
             (+1 cm headroom for PyBullet contact margin).
             ~30 LOC patch in test_full_pipeline.main; no domain
             change; cuts cell count ~8x as a side-effect (also
             fixes the grounding-cost half of the stall).  Cell
             size becomes scene-dependent: typical default scene
             -> ~0.10 m; smaller-target scenes -> ~0.05 m stays.
             Lands on `main` (the free-space-only-swap baseline).
         (B) Multi-cell place — symbolic place over a CLUSTER of
             cells covering the object footprint.  Requires PDDL
             action change + new "anchor cell" semantics.  RULED
             OUT 2026-05-09: combinatorial blowup (planner picks
             a SET of cells); not TAMPURA-faithful; not cheap.
         (C) Continuous-pose place — replace boxel-indexed place
             with TAMPURA-style continuous SE(3)-pose placement.
             Stream samples (x, y, z) within the free volume,
             returns a Pose certificate; place action takes ?p
             (Pose) instead of ?b (Boxel).  Major domain rewrite;
             the actual TAMPURA approach (Curtis et al. 2024 —
             find_dice/env.py uses continuous poses).  Lands on
             `audit-64-tampura-binary-grid`.

Fix:   SPLIT ACROSS TWO BRANCHES, ONE SHARED AUDIT BODY (this entry).

       On `main` (the free-space-only-swap baseline)
       ---------------------------------------------
       Plan A — auto-tune cell size.  Single commit:

       In test_full_pipeline.main, after env.use_uniform_grid is
       set, compute auto_cell = max(visible AABB extent across all
       scene objects) + 0.01 m.  If auto_cell > the user-supplied
       --uniform-cell-size, call env.set_uniform_cell_size(
       auto_cell) and log the bump.  Preserves user override
       (passing --uniform-cell-size 0.20 stays at 0.20 — only the
       default 0.05 is auto-bumped).  Smoke-run the previously-
       stuck scene (--scene default --baseline uniform --seed 0)
       to verify it succeeds.

       On `audit-64-tampura-binary-grid` (the TAMPURA-faithful baseline)
       -----------------------------------------------------------------
       Plan C — continuous-pose placement.  Multi-commit, in order:
       (i)   pddl/domain_pddlstream.pddl: place action takes ?p
             (Pose) instead of ?b (Boxel); pose-based precondition
             stream replaces boxel_fits.
       (ii)  pddl/stream.pddl: new sample-place-pose stream that
             yields valid free-volume poses per object (uniform
             rejection sample within table_x_range x table_y_range
             x table_z, AABB-checked against current OBJECT/SHADOW
             set).
       (iii) streams.py: implement sample_place_pose; modify
             compute_kin_solution to accept a Pose argument for the
             place case (pose.position + grasp_offset = EE target).
       (iv)  pddlstream_planner._build_init: drop boxel_fits and
             obj_at_boxel emission for free cells under uniform
             mode (free cells become a visualisation aid only;
             placement is continuous).
       (v)   execution.py place handler: read ?p (Pose) from the
             action params instead of ?b (Boxel).
       (vi)  Audit DONE entries for both A and C at landing.

       Ordering note: A landing on main + C landing on audit-64
       are independent; either can land first.  When audit-64
       eventually merges back to main (post-thesis or per
       supervisor direction), the planner has BOTH placement modes
       — boxel-indexed for semantic baseline, pose-indexed for
       tampura baseline.

Care: The ONE-SHARED-AUDIT-BODY constraint means this issue body
       appears IDENTICALLY on main and audit-64-tampura-binary-grid.
       Update from main and merge forward to audit-64; avoid
       divergent edits to the issue body.  The audit changelog at
       the top of CODEBASE_AUDIT.txt MAY differ between branches —
       that's history, and main/audit-64 have different DONE tracks
       for #64 etc.

       Plan A is the smaller of the two and should land first to
       unblock --baseline uniform smoke runs and the eval matrix.
       Plan C is the larger commit and the genuine TAMPURA-
       faithful contribution.

Related: #50 — planner perf investigation.  Plan A's cell-size
              bump cuts grounding cost ~8x as a side effect; #50
              loses one of its hotspots after Plan A lands.
         #62 — replan-while-holding still slow.  Same grounding-
              cost lineage as #50; Plan A indirectly mitigates.
         #64 [DONE on audit-64-tampura-binary-grid] — TAMPURA-
              faithful uniform-baseline GUI framing (visualizer
              uniform_mode flag).  Plan C is the natural
              continuation: visualizer change was cosmetic; this
              is the placement-semantics change.
         #65 — boxel -> hanixel rename.  Coordinate landing
              order (per #65 Care): merge audit-64 back to main
              first, OR rebase audit-64 after the rename, to
              avoid identifier-collision merge noise.


================================================================================
COMPARISON ITEMS (restructured 2026-05-23; supersede the 2026-05-21 C1/C2/C4)
================================================================================
Old C1 (run TAMPURA on our HW) -> T3.  Old C2 (run ours on their
scene) -> T2, re-scoped to task-replication.  Old C4 (keep source
local) -> folded into T3 prerequisites.  Old C3/C5 -> tail (not the
comparison).  All factual claims here verified against source this
review (see CORRECTIONS at top).

================================================================================
T1. HONEST-IFY THE CITED fig:tampura COMPARISON  (thesis-now, NOT gated)
================================================================================
Priority: TIER 1 of the comparison -- cheapest, highest value, and the
          only item not blocked by the supervisor gate.  It fixes (and
          RESOLVES a self-contradiction in) a comparison the thesis
          ALREADY makes; needs no TAMPURA run.
Where:    eval_plotter.py plot_tampura_wallclock_comparison (goal filter
          line 1007 `r.get("goal") != "find-and-tray-stack"`; caption
          lines 1073-1078 -- STILL says "20-core Xeon ... ours 8-core");
          thesis/chapters/results.tex subsec:tampura (209-216: "the
          closest analogue", 14.0 s, n=119, ~4x);
          thesis/chapters/abstract.tex (14-17: "closest analogue ...
          14.0 s vs 57 s" -- THE HEADLINE; MISSED by the 2026-05-23 draft);
          thesis/chapters/discussion.tex (70-94 still uses 14.0 s on
          f-a-t-s; 101 ALREADY calls find_dice the closest analogue;
          158 ALREADY has the single-threaded/clock framing);
          thesis/chapters/related-work.tex (SymK/FD wording);
          THESIS_NOTES §21.1 (hardware caveat; fix the stale
          proposal-template path there).
Depends:  None.  Holding wall-clock already exists in the SAME eval rows
          the plot reads -- VERIFIED: sweep_anytime has holding rows
          (semantic n_success=127; summary_table_aggregate.csv).  The
          core fix is changing the line-1007 filter string.

What:  THE THESIS CONTRADICTS ITSELF.  fig:tampura + results.tex:209 +
       abstract.tex:14-17 + discussion.tex:70-94 compare OUR find-and-
       tray-stack (median 14.0 s, n=119) against TAMPURA find_dice (mean
       57+-38 s) and call f-a-t-s "the closest analogue".  But
       discussion.tex:101 ALREADY states the opposite -- TAMPURA's "Find
       Die ... the closest analogue to our setting" -- and find_dice IS
       our `holding` task, not f-a-t-s (which adds trays + stacking,
       strictly more).  So T1 is contradiction-RESOLUTION, and the
       thesis's own discussion is the justification.  Gaps:
       (a) TASK: figure/abstract/results compare the wrong task (f-a-t-s);
           discussion.tex:101 already names the right one (find_dice).
       (b) STATISTIC: ours = median + IQR, success-only; theirs =
           mean +- std over ALL 20 anytime trials.  Mixed statistics.
       (c) SUCCESS RATE absent AND its DIRECTION unverified.  The
           2026-05-23 draft assumed "TAMPURA trades success for speed"
           (TAMPURA = lower success) -- but OUR holding success is only
           ~42 % (semantic) / ~46 % (mbs0.05) / ~33 % (uniform).  If
           TAMPURA's find_dice success (Table II) is high, WE are the
           low-success side and "4x faster" misleads the OTHER way.  Pull
           the actual number; state direction FROM data.
       (d) HARDWARE: the figure CAPTION still says "20-core Xeon vs
           8-core" (eval_plotter.py:1076) -- but discussion.tex:158
           ALREADY has the correct framing (both single-threaded; TAMPURA
           2.5 vs our 2.0 GHz base clock slightly favours TAMPURA).  So
           this is a caption/abstract CONSISTENCY fix to match the
           already-correct discussion, not a fresh correction.
       (e) SymK: related-work wording only.  discussion.tex:84-87 ALREADY
           calls SymK "a Fast Downward-derived top-k planner" -- again
           consistency, not new.
       (f) TIME MEASURE (new): confirm BOTH numbers are per-episode
           wall-clock INCLUDING PyBullet execution + replanning, not
           solve-only.  results.tex:209 says "per-episode wall-clock" and
           14.0 s is median wall_clock_s -- but the summary table reports
           a DIFFERENT, smaller mean_plan_time_s (holding semantic 7.78 s);
           do NOT conflate.  TAMPURA's 57 s is per-episode (memory
           reference_tampura_perf: 21-129 s/episode).  If the two sides
           measure different spans the comparison is a category error --
           check before re-deriving any delta.
       (g) TASK ASYMMETRY (new): find_dice goal = holding(die) AND at-home
           (env.py:1004).  OUR holding goal = (holding ?o) ONLY -- the
           domain has NO home goal predicate (home_config is just the
           motion rest pose, streams.py:190; goal tuple is ('holding',obj),
           pddlstream_planner.py:145).  find_dice does strictly MORE (one
           final go-home).  State "holding ~ find_dice MINUS homing"; do
           NOT claim exact equivalence.

Fix:   - Switch the line-1007 goal filter to `holding` (or add a holding
         series alongside f-a-t-s, labelled).  Re-derive the delta from
         holding rows; it WILL change (holding < f-a-t-s wall-clock, so
         the gap likely GROWS in our favour) -- do NOT carry over 14.0 s
         / "~4x".
       - Fix abstract.tex:14-17 (the headline) AND results.tex:209 +
         discussion.tex:70-94 to name `holding` as the analogue, aligning
         them with discussion.tex:101.
       - Report ours as mean +- std too, OR annotate the median-vs-mean
         and success-only-vs-all-trials mismatch in caption + THESIS_NOTES.
       - Add success rate, BOTH sides (ours from eval ~42 %; TAMPURA from
         Table II), and state who trades success for speed FROM the data.
       - Rewrite the figure caption (eval_plotter.py:1076) to drop
         "20-core"; match discussion.tex:158 (single-threaded; clock
         slightly favours TAMPURA).
       - Correct SymK/FD in related-work + memory reference_tampura_perf.md
         (discussion already correct).
       - Verify the (f) time-measure parity before trusting any delta.
       - State NO speed winner; keep the architectural framing (offline
         Learn-Model vs online stream sampling) the thesis already has.
Effort: ~0.5-1 day, mostly plot + prose + caption.  Re-read the
        regenerated PNG before commit (feedback_plot_regeneration).
Care:  (1) Switching to holding changes the headline number -- state it
           from data; do not reuse 14.0 s / 4x.
       (2) T1 buys task-TYPE parity, NOT scenario parity: the holding rows
           are our default/random scenes, NOT find_dice-equiv scenes.  The
           residual scene-distribution gap is closed only by T2.  Say so;
           do not over-sell T1 as "same problem".
       (3) Keep success-only vs all-trials explicit: TAMPURA's 57 s is
           over all 20 trials (incl. failures); ours is success-only.
       (4) THESIS_NOTES §21.1 path is stale (proposal-template) -- fix
           while there.
       (5) Update abstract + discussion in the SAME pass (memory
           feedback_update_notes); leaving abstract.tex stale REINTRODUCES
           the contradiction T1 set out to remove.

================================================================================
T2. RUN OUR HOLDING PIPELINE ON A find_dice-EQUIVALENT SCENE  (post-thesis, gated)
================================================================================
Priority: TIER 2 -- the genuine same-task number (our system solving
          the missing-dice problem on our hardware).  Gated by the
          supervisor rule.  Realistic replacement for the 2026-05-21
          "run ours on their scene" (C2), which understated the work.
Where:    boxel_env.py scene generators (scalability_scene ~271,
          random_pairs_scene ~344 already parametrize n_occluders and
          a hidden count); eval_runner.py MATRIX_PRESETS; --goal
          holding.
Depends:  (1) The occlusion-mode caveat (below).  (2) NOT #66 Plan C
          (that is the uniform ablation; T2 uses the SEMANTIC system).
          (3) CAPABILITY FEASIBILITY (new) -- must be smoke-confirmed
          FIRST.

CAPABILITY FEASIBILITY (new -- the 2026-05-23 T2 assumed this away):
       find_dice's CORE mechanic is move-the-occluder-to-reveal: the die
       is invisible until the cup is relocated.  Our reveal is the same
       STRUCTURALLY (sense needs view_clear; an occluder makes the region
       view_blocked until relocated -- see CAVEAT), BUT the thesis itself
       hedges whether we do it deliberately:
       - discussion.tex:101 calls deliberate view-RESTORATION ("restoring
         a blocked view by first moving the obstruction") FUTURE WORK, and
         says the loop "bounds itself with a give-up rule".
       - that give-up rule fires after 3 "still_blocked" strikes per
         shadow (test_full_pipeline.py:938; execution.py:1508-1523; audit
         #78c / #21) -> exit_reason replan_limit / blocked-giveup.
       - YET holding succeeds ~42 %, and the loop DOES relocate occluders
         and refresh blocks_view_at on relocation (test_full_pipeline.py
         :1442-1464).  So single-layer move-to-reveal partly works; the
         "future work" caveat is either over-broad or refers to harder
         cases (nested / guaranteed restoration -> tail C5).
       ACTION: before spending gated run-time, SMOKE-TEST one canonical
       find_dice-equiv scene (1 die-sized target fully behind exactly one
       movable box "cup"; --goal holding --baseline semantic).  Confirm
       the planner CHOOSES to relocate the occluder, then senses, then
       picks -- i.e. SOLVES rather than gives up.  Reconcile with
       discussion.tex:101 (and correct that text if it over-claims a
       limitation we do not actually have).  IF it mostly gives up, T2 is
       NOT plot-only: it needs robust view-restoration first (dev work) or
       a re-scoped weaker task -- either changes T2's effort.  The smoke
       test is a single feasibility run, arguably NOT gated (like the #66
       smoke runs), and de-risks the gated comparison.

What:  C2 proposed transplanting TAMPURA's PyBullet scene (concave YCB
       cups + die + Panda + saved grasps) into our pipeline and
       "defining shadows over their occluders".  That is NOT moderate:
       their occlusion is CONTAINMENT (cup over die), ours is LATERAL
       shadow; concave cups, a different robot, and grasp generation
       all fight our box-occluder/shadow model.
       The realistic path replicates the find_dice TASK STRUCTURE in
       OUR framework: 1 small "die" target, 1-5 box "cup" occluders,
       single-layer (target hidden by exactly one occluder, the rest
       decoys), goal = holding.  Our scene generators already take
       n_occluders and a hidden count, so this is a new PRESET
       (n_hidden = 1, n_occluders in [1,5], die-sized target), not a
       transplant.

Fix:   - SMOKE-TEST feasibility first (above).
       - Add a `find_dice_equiv` scene preset (single hidden die-sized
         target; 1-5 box occluders; exactly one occluding -- and the
         occluding box must ACTUALLY view-block the target so a relocation
         is FORCED, else the task is easier than find_dice).
       - Run --goal holding over >= 20 seeds (match TAMPURA's N=20) for a
         comparable mean +- std; collect wall-clock AND success.
       - Plot vs TAMPURA's published 57+-38 s (and vs T3 if it lands):
         same task, our hardware.  Report success rate BESIDE wall-clock.
Effort: ~2-4 days IF feasible as a preset (preset + smoke + full run +
        plot).  MORE if the feasibility smoke test exposes a
        view-restoration gap.  Gated.
Care:  (1) Single-layer ONLY -- match find_dice; nested occlusion is a
           DIFFERENT experiment (tail, old C5).
       (2) Target ~ a die (~2-4 cm), occluders ~ cup-scale, so
           auto_cell stays comparable to the default scene.
       (3) Add a final go-home if matching find_dice's at-home goal
           exactly (T1 gap g); else note the one-action asymmetry.
       (4) Document the occlusion-mode reinterpretation (caveat).

================================================================================
T3. STAND UP & RUN REAL TAMPURA find_dice ON OUR HARDWARE  (post-thesis, gated, optional)
================================================================================
Priority: TIER 3 -- pins the hardware axis (TAMPURA measured on our HW
          removes the cross-hardware caveat, making T2-vs-T3 same-task
          AND same-hardware).  Hardest item, highest bring-up risk.
          OPTIONAL: if it will not build, the published 57+-38 s stands.
Where:    ../tampura (planner), ../tampura_environments (find_dice).
Depends:  T2 (so there is a same-task number to compare against on our
          HW).

What:  The 2026-05-21 C1 called this "~1-2 days, just run their
       released code" and "highest value/effort".  Both are wrong:
       - VALUE: it only addresses the HARDWARE caveat, which is small
         (TAMPURA is single-process).  The dominant caveat was
         cross-TASK, fixed by T1/T2 -- so T3 is LOWER value than the
         draft claimed, not highest.
       - PREREQUISITES (omitted by C1):
         * checkout panda_utils + models/srl, not just find_dice
           (find_dice imports panda_utils for everything).  The fuller
           checkout is blocked on Windows by an illegal-filename file
           (`rrt*.png`) -- do it on WSL/Linux or via a renamed fork.
         * build SymK (third_party/symk -- a Fast Downward C++ build)
           on WSL/Linux.
         * saved grasps (GRASP_MODE="saved"), YCB assets, deps
           (pybullet, scipy, ...).
Fix:   - Bring up on WSL/Linux; verify find_dice runs headless on the
         released problems/*.json scenes.
       - Record per-episode wall-clock + success on our 8-core CPU.
       - Plot vs T2 (our holding on find_dice-equiv): same task, same
         hardware.
       - TIMEBOX (~2 days).  If it does not build, FALL BACK to the
         published number and document the attempt.
       - Source hygiene (old C4): keep ../tampura + the find_dice
         slice local; read any uncheckout file via
         `git -C ../tampura_environments show HEAD:<path>`.  Cite the
         planner-side definitions -- look/pick/place controllers
         (find_dice/env.py), MDP solver (solvers/mdp_solver.py,
         lao_star.py), SymK glue (solvers/symk.py,
         policies/{tampura_policy,contingent_policy}.py).
Effort: days, real risk of not running (version rot).  Gated + optional.
Care:  (1) find_dice ~ our holding -- pair their find_dice with our
           holding-on-find_dice-equiv (T2), not f-a-t-s.
       (2) Single-process: per-core clock is what matters, not cores.

================================================================================
CAVEAT. OCCLUSION-MODE MISMATCH (comparability boundary for T2/T3)
================================================================================
find_dice occludes by CONTAINMENT: the die is placed at a cup's pose,
under an upside-down cup; the camera cannot see it; it is revealed by
MOVING the cup (look's success depends on moved(occluder), env.py:966).
Our system occludes by LATERAL SHADOW: an occluder casts an AABB shadow
region behind it from the camera viewpoint, and a hidden target sits in
that shadow.

REVEAL MECHANISM -- closer than "mismatch" suggests.  Our camera is FIXED
(domain_pddlstream.pddl:117 "fixed scene camera") and sense REQUIRES
view_clear (= is_shadow AND NOT view_blocked; domain:108-111, 161).
While an occluder sits in the line of sight the region is view_blocked
and CANNOT be sensed -- we cannot "raycast" a blocked shadow.  Revealing
the target therefore requires RELOCATING the occluder, exactly as
find_dice requires moving the cup.  So the planning STRUCTURE (clear
occluder -> sense -> pick -> [home]) is parallel; only the GEOMETRIC mode
differs.  (NB: the 2026-05-23 caveat's "sensed by raycasting, or
relocating" wording was loose -- a view-blocked region is not senseable
in our domain.)

Residual differences to STATE wherever the comparison appears
(results.tex / discussion.tex):
  - mode: lateral shadow (ours) vs containment (find_dice) -- no
    pixel-faithful "same scene"; a literal transplant is geometrically
    awkward.
  - reveal: find_dice's look is PROBABILISTIC in moved(occluder); ours is
    a HARD view_clear precondition (deterministic).
  - restoration: ours leans on a give-up rule and flags guaranteed
    view-restoration as future work (discussion.tex:101) -- the T2
    feasibility smoke test must confirm this does not block single-layer
    find_dice (see T2).
The defensible comparison is on the TASK ("a die hidden by an occluder;
find it, pick it, go home"), realised in each system's native occlusion
model.  This is the honest scope of "we compared on find_dice".

================================================================================
TAIL -- SEPARATE EXPERIMENTS, NOT THE find_dice COMPARISON
================================================================================
Kept for the record (moved here 2026-05-23).  Neither is the
missing-dice comparison: C3 is a research direction; C5 is our OWN
distinguishing experiment (the OPPOSITE of find_dice -- find_dice is
single-layer).  The "C1/C2" inside C5 refer to the OLD numbering (now
T3/T2).  Text preserved verbatim.

C3. TAMPURA x BOXEL HYBRID (research idea -- test or implement?). TAMPURA's
    voxels only *compute the probability* that look flips known-pose(die); a
    voxel need not be 15 mm. So: COARSE voxels could cover large visibility
    regions cheaply, while boxels go FINER than 15 mm only where object/occlusion
    structure demands it -- a multi-resolution space belief (coarse
    occupancy/visibility grid for the "could-be-here" support + adaptive boxels
    for place-grounding and symbolic occlusion). Prototype and measure (cells,
    planning time, success) vs pure-semantic and pure-uniform. Open question:
    does the hybrid beat both?

C5. NESTED-OCCLUSION TEST (our distinguishing experiment -- "this is our test").
    Multi-blocker / nested occlusion is where first-class symbolic occlusion
    should pay off: view_clear(?region) = is_shadow AND NOT view_blocked, and
    view_blocked is true if ANY object blocks the corridor -- so a region
    blocked by several objects forces the planner to clear ALL of them before
    sensing, and a sense that reveals a new occluder spawns a new SHADOW + a
    re-partition (peeling nested layers). TAMPURA does NOT exercise this:
    find_dice hides the die under ONE cup (single-layer; env_generator.py), its
    `look` is keyed on a single occluder, and the location belief collapses to
    one binary predicate -- deep nesting would stress its learned model.
    DO: build scenes with 2-3 NESTED occluders (target behind A behind B...);
    run semantic vs uniform (and, if C1/C2 land, TAMPURA); measure success /
    plan length / #discovered-occluders / replans. Expected story: ours peels
    nested layers deliberately; uniform/TAMPURA-style approaches degrade. The
    cleanest demonstration of the contribution (#163/#165) -- stronger than the
    semantic-vs-uniform compactness result. FIRST confirm our scene generator
    can actually PRODUCE nested occlusion (capability vs demonstration).

