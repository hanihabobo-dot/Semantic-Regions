# TAMPURA Plan / Comparison

Created: 2026-05-12 (later)

This file is the dedicated home for TAMPURA-related issues and the
TAMPURA comparison plan.  Collected here first, planned afterwards.

Background:
- TAMPURA is Curtis et al. 2024 (find_dice/env.py — voxel-grid belief,
  continuous-pose placement, offline Learn-Model).
- Memory notes (see ~/.claude/projects/.../memory/reference_tampura_*.md)
  capture grid resolution (15 mm visibility belief) and hardware
  baseline (Xeon Gold 6248, 9 GB, no GPU; 21-129 s/episode).
- THESIS_NOTES §21 captures the TAMPURA hardware / planning-times
  contextualisation used in eval-chapter Plot 9 (TAMPURA comparison bar).

Currently-open TAMPURA work:
- #66 (uniform/TAMPURA baselines — place fails when object > cell).
  Plan A [DONE on main 2026-05-09] (auto-tune cell size); Plan C
  [PENDING on audit-64-tampura-binary-grid] (continuous-pose place,
  the actual TAMPURA approach).

Related (closed, in archive):
- #10 [DONE 2026-05-08] — uniform voxelization baseline (free-space-
  only swap).
- #64 [DONE 2026-05-08] — TAMPURA-faithful GUI framing.

Related FOR LATER (still in CODEBASE_AUDIT.txt FOR LATER block):
- "LW1 / TAMPURA empirical comparison" — supervisor direction
  2026-05-06: only after thesis writing if >=1 week free time.

Next step (NOT NOW): once TAMPURA-related issues are collected here,
draft a unified TAMPURA plan (Plan C completion + empirical comparison
scoping + thesis Plot 9 inputs).
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

