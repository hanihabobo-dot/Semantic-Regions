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
Revised: 2026-05-25 - Phase-1 bring-up STOOD UP; find_dice RUNS (GUI seed 0
         + headless confirmed; 20-seed sweep in progress).  Added the
         "HOW TO RUN REAL TAMPURA" operational runbook below.  Headline
         gotcha: SymK shells out to bare `python`, so the venv MUST be
         activated / on PATH or the run dies ~33 s in at symk_translate.

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
- T1 -- MOVED to thesis_audit.md #177 (thesis-prose contradiction; thesis-now).
- T2 -- find_dice head-to-head [REDONE 2026-05-25].  PHASE 1 (stand up real
  TAMPURA, was T3) DONE -- runs GUI + headless in WSL; PHASE 2 (20-seed
  sweep: success + wall-clock + planning time) IN PROGRESS; PHASE 3/4 gated.
  HOW-TO: see the "HOW TO RUN REAL TAMPURA" runbook below.
- T3 -- FOLDED INTO T2 PHASE 1 (2026-05-25); body kept below as bring-up ref.
- CAVEAT -- occlusion-mode mismatch (comparability boundary).
- VERIFY (2026-05-25) -- paper version / section-number reconciliation.
  The §V-A quote ("repeatedly construct optimistic, deterministic
  plans...") IS present verbatim in the arXiv HTML (§V-A "Guiding learning
  with determinized plans"); the user could not find it in the attached
  17-page PDF (password-protected -- likely a different version).  Before
  citing any TAMPURA section number in the thesis, confirm which version
  `curtis2024partially` resolves to and map the section numbers.  Quick
  check; fold into T2 PHASE 1 bring-up.

Related (closed, in archive):
- #10 [DONE 2026-05-08] -- uniform voxelization baseline (free-space-
  only swap).
- #64 [DONE 2026-05-08] -- TAMPURA-faithful GUI framing.

Tail (NOT the find_dice comparison): old C3 (hybrid) and C5 (nested
occlusion) are preserved at the bottom under their own banner.

================================================================================
HOW TO RUN REAL TAMPURA -- OPERATIONAL RUNBOOK (2026-05-25)
================================================================================
Phase-1 bring-up is DONE; this is the how-to for re-running find_dice.
Everything lives in WSL2 Ubuntu on EXT4 (NOT /mnt/c -- the rrt*.png Windows
blocker, see T2 PHASE 1).  Invoke from Windows via PowerShell:
    wsl -d Ubuntu -e bash -lc '<linux command>'
PowerShell<->WSL roundtrip hangs ~60-120 s AFTER the call returns on this
machine; for long runs launch in the background and read the output file.

Layout (WSL):
  /root/tampura-work/tampura/                planner repo (incl. SymK build)
  /root/tampura-work/tampura_environments/   env repo (run_planner.py is here)
  /root/tampura-work/.venv/                  python 3.11 venv
  .../tampura_environments/env_configs/find_dice.yml     the config
  .../tampura_environments/runs/run_<ts>/    one dir per episode (pkl + logs)

*** GOTCHA #1 (the one that bites): SymK shells out to bare `python`. ***
tampura/solvers/symk.py (symk_translate ~line 51, and the search step) calls
subprocess.run(["python", ...]).  Ubuntu has only `python3`; the name
`python` exists ONLY inside the venv (.venv/bin/python -> python3.11).
=> You MUST run with the venv ACTIVATED (its bin on PATH).  If you instead
   call the venv python by ABSOLUTE PATH without activating, run_planner.py
   starts fine but DIES ~33 s in with:
     FileNotFoundError: [Errno 2] No such file or directory: 'python'
     (raised in tampura/solvers/symk.py -> symk_translate -> subprocess.run)
   The GUI launcher works precisely because tampura_run_gui.sh:34 does
   `source .venv/bin/activate`.  For a programmatic child process, instead
   prepend .venv/bin to the child's PATH (what tampura_sweep.py does).

CANONICAL COMMANDS (always activate the venv first):
  # GUI, one episode (args: SEED VIS_GRAPH; vis-graph=1 renders the graphs):
  wsl -d Ubuntu -e bash -lc 'bash /root/tampura-work/tampura_run_gui.sh 0 1'

  # Headless, one episode (faster, no window, exits cleanly):
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    python run_planner.py --config=./env_configs/find_dice.yml --global-seed=0'

GOTCHA #2: headless = OMIT --vis and --vis-graph (both default false in
find_dice.yml).  Do NOT pass --vis=0: run_planner uses argparse type=bool and
bool("0") is True, so --vis=0 STILL shows the GUI.  Omit the flag entirely.

GOTCHA #3 (cosmetic): with the GUI, PyBullet teardown SEGFAULTS on WSLg
(exit 139) AFTER the episode finishes and artifacts are saved.  Harmless.
Headless (PyBullet DIRECT mode) exits 0 -- no segfault.

READING A RESULT (per episode -> runs/run_<ts>/<date>.pkl):
The pkl is a tampura.policies.policy.RolloutHistory (load with the venv
python; tampura must be importable).  Fields used:
  - rewards     : list[float].  SUCCESS  <=>  rewards[-1] == 1.0 (target die
                  grasped AND robot at-home on the terminal belief).  Reward
                  flips to 1.0 at the solve step, then holds via no-op() out
                  to max_steps (=20); episodes do not terminate early.
  - time_deltas : list[float], CUMULATIVE elapsed seconds (a running clock,
                  NOT per-step deltas).  time_deltas[-1] = the planner-LOOP
                  wall time (planning + pybullet execution inside the policy
                  loop).  Seed 0: ~70 s headless, ~110 s with GUI.
  - actions     : the executed plan (e.g. pick/place/look/pick/go-home, then
                  no-op... ).
NB: pure planning is NOT cleanly separable from execution in the pkl.  SymK
solve times print to stdout ("... | Time: T"); tqdm shows Outcome-Sampling
time.  Capture stdout if you need the planning/execution split.

20-SEED SWEEP (this is T2 PHASE 2):
Driver: /root/tampura-work/tampura_sweep.py -- headless; one ISOLATED
subprocess per seed (so a teardown segfault can't kill the sweep); times each
with perf_counter; reads success+timing from the pkl; writes an incremental,
RESUMABLE JSON after every seed (skips seeds already marked complete).
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    python -u /root/tampura-work/tampura_sweep.py --seeds 0-19 \
    --out runs/sweep_2026-05-25.json'
JSON shape: per-seed {success, wall_s, loop_s, solve_step, rewards, ...} +
aggregate {success_rate, wall_s/loop_s mean+-std}.  ~110 s/episode headless.
COMPARE loop_s (TAMPURA's own loop clock) -- NOT wall_s (which includes
process startup) -- against the paper's 57+-38 s; success_rate vs >= 0.63
(Curtis et al. 2024, Partial-Observability task, N=20).  Phase-2 results:
summarise BOTH here and in CODEBASE_AUDIT.txt (per the PHASE 2 instruction).

LOCAL PATCH (do NOT push the public-repo clones): tampura_environments/
__init__.py was patched to try/except each subpackage import -- the public
repo ships 5 of 6 env subpackages (toy_discrete is missing) and the stock
__init__ imported it unconditionally.  find_dice resolves regardless.

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
T1. -> MOVED to thesis_audit.md #177 (2026-05-24)
================================================================================
"Honest-ify the cited fig:tampura comparison" is fundamentally a THESIS-PROSE
self-contradiction (abstract/results/discussion name two different "closest
analogues" to find_dice), so it now lives in the thesis audit as #177 [T0] [NOW],
with the full analysis folded in (wrong task: find-and-tray-stack vs holding;
planning-only 57 s vs our wall-clock; success >= 63 % vs ~42 %).  T2/T3/CAVEAT
below still say "T1" for context = that issue.

================================================================================
T2. find_dice HEAD-TO-HEAD: REAL TAMPURA, THEN OUR PLANNER ON THEIR ENV
    [REDONE 2026-05-25 per user -- supersedes the preset approach below]
================================================================================
NEW BROAD PLAN (2026-05-25, user direction).  Drop the "replicate the task
in OUR framework via a preset" approach (kept below for record; its
smoke-test findings still stand) and instead do a DIRECT head-to-head on
TAMPURA's ACTUAL find_dice PyBullet env.  Old T3 (stand up real TAMPURA) is
no longer a separate/optional item -- it is PHASE 1 here.  Run everything
WITH GUI.  Four phases, each gated on the previous being CONFIRMED by the
user before proceeding:

  PHASE 1 -- STAND UP & RUN REAL TAMPURA find_dice ON THIS MACHINE (GUI).
     STATUS 2026-05-25: DONE.  Stood up in WSL (/root/tampura-work); SymK
     built; find_dice runs GUI (seed 0) AND headless (rc=0).  20-seed sweep
     (PHASE 2) in progress.  Operational details: see the "HOW TO RUN REAL
     TAMPURA" runbook near the top of this file.
     Bring-up state VERIFIED ON DISK 2026-05-25 (no longer hypothetical):
     - ../tampura (planner) is FULLY present incl. third_party/symk C++
       source -> needs a py3.11 env, `pip install -e .`, pygraphviz, and a
       SymK BUILD (third_party/symk/build.py; cmake + g++; Linux/WSL).
       RUN ENTRY POINT (corrected 2026-05-25 -- the planner repo has no CLI,
       but the ENV repo does): tampura_environments has run_planner.py at
       root + env_configs/find_dice.yml.  README command:
         python run_planner.py --config=./env_configs/find_dice.yml --vis=1
                               --global-seed=0 --vis-graph=1
       (--vis=1 -> PyBullet GUI; --vis-graph needs pygraphviz, set 0 to
       skip).  find_dice.yml: planner=tampura_policy, max_steps=20,
       gamma=0.98, from_scratch=true (= ONLINE per-step learning, confirms
       #190), num_samples=200, num_skeletons=10.  No custom driver needed.
     - ../tampura_environments is a SPARSE checkout: only
       find_dice/{env.py,env_generator.py} + 3 released problems/*.json are
       on disk.  find_dice imports
       tampura_environments.panda_utils.{pb_utils,panda_env_utils,
       primitives,robot,voxel_utils} (+ a bundled motion_planning/ RRT
       suite) and models/srl (Panda URDF, YCB meshes, SAVED GRASPS for
       GRASP_MODE="saved") -- ALL unmaterialized.  Must un-sparse
       panda_utils/ + models/.  env registers as "find_dice" /
       "find_dice_simple" (env.py:1032-1033); TARGET_OBJECT="dice";
       GRID_RESOLUTION=0.015.
     - WINDOWS BLOCKER (confirmed; exactly ONE file in the 3452-file tree):
       panda_utils/motion_planning/images/rrt*.png -- the only NTFS-illegal
       name (a doc image).  A full checkout on /mnt/c (NTFS) aborts on it.
       FIX: do the TAMPURA bring-up on WSL EXT4 (e.g. ~/tampura,
       ~/tampura_environments -- NOT /mnt/c), where `*` is legal and SymK
       builds Linux-native.  Cleanest mechanic: `git clone` from the
       EXISTING local /mnt/c clones into ~/ (their .git pack already holds
       the full tree, so no re-download; a fresh clone does a FULL checkout
       on ext4, materialising panda_utils + models incl. rrt*.png).  (Alt:
       sparse-exclude that one file in place.)
     - Run find_dice on the 3 released problems/*.json with GUI (WSLg
       DISPLAY=:0); GRASP_MODE="saved" so no grasp regeneration.
  PHASE 2 -- RECORD success rate + per-episode wall-clock + (if separable)
     planning time on OUR hardware (Ryzen 7 PRO 7730U, 8c; THESIS_NOTES
     §21.1).  Save to JSON (e.g. eval_results/tampura_real/<ts>.json) AND
     summarise here + in CODEBASE_AUDIT.txt.  Compare vs published
     57+-38 s + success >= 63% (#177 / reference_tampura_perf).  [NB 2026-05-26:
     that 57+-38 s is PER-STEP incl. sim controller execution, NOT planning-only
     -- Table II caption; the "planning-only" label was wrong, see PHASE 2 RESULT.]
  PHASE 2 RESULT [2026-05-26] -- DONE.  Headless 20-seed sweep on our HW
     (Ryzen 7 PRO 7730U, 8c; TAMPURA is single-process).  Driver
     tampura_sweep.py -> runs/sweep_2026-05-26.json, one clean uninterrupted
     session (an earlier 05-25 sweep was DISCARDED: an overnight Windows
     suspend inflated one seed's time_deltas to ~9 h; re-run sleep-guarded).
     n=20:
       - SUCCESS 11/20 = 55%  (paper >= 63%; ~1.5 episodes at N=20 -> same
         regime, slightly low).
       - loop_s (planning + pybullet execution): all 239.9 +- 151.1 s;
         successes 166 +- 85 s; failures ~330 s (a failed episode plans every
         step to max_steps=20, ~2x a success).
       - wall_s (full process): all 253.3 +- 150.9 s.
       - solve step (successes): mostly 5-7; two at 11, one at 15.
     CAVEAT [CORRECTED 2026-05-26 vs paper, Table II screenshot] -- the 57+-38 s
     (Task C = Partial Observability, Bayes-Optimistic+LAO* row) is NOT
     planning-only and NOT per-episode.  Caption verbatim: "Average and standard
     deviation of PER-STEP planning times (seconds) averaged over trials and
     steps within each trial.  These include execution time of the selected
     controller in simulation."  => PER-STEP, INCLUDING sim controller
     execution.  Our loop_s is PER-EPISODE (20 steps); matched per-step =
     loop_s/20 ~ 8 s/step (success) to ~16 s/step (fail), ~16-28 s per MEANINGFUL
     step (no-ops ~free).  run_planner.py IS TAMPURA, so this sweep = TAMPURA
     ON OUR HW vs TAMPURA's published their-HW number (a hardware/repro check,
     NOT ours-vs-theirs -- that's PHASE 3).  Per-step our HW is AT/BELOW 57+-38,
     so (a) the "3-4x slower" read was an artifact of per-episode-vs-per-step,
     and (b) no evidence their HW is much better (cf. single-process /
     single-core-clock correction up top).  STILL don't declare a winner: their
     averaging (incl no-ops?) + benchmark task config may differ from the
     released find_dice.  SUPERSEDES the "planning-only" wording in #177 /
     THESIS_NOTES (thesis-prose fix flagged, not done here).  Mirrored in
     CODEBASE_AUDIT.txt.
     CONFIRMED [2026-05-27] against arXiv 2403.10454 v2 PDF p.15 (Table II screenshot): per-step,
     incl. sim execution -- definitive.  Source of misconception: the paper states something
     different than the PDF (v2 PDF caption authoritative).  Thesis framing (author 2026-05-27):
     BOTH axes, per-episode primary -- (i) same-HW per-episode 13.7 (ours) vs 166 (TAMPURA local) s,
     42% vs 55%; (ii) per-step ours = wall/plans = 13.676/2.315 = 5.9 s/solve vs paper 57 s/step.
     Tracked as thesis_audit #213; THESIS_NOTES §21.2/§21.5 updated.
  PHASE 3 -- RUN OUR PLANNER ON THEIR find_dice ENV (GUI), minor code
     adjustments.  Write a NEW domain: COPY pddl/domain_pddlstream.pddl to a
     find_dice variant (e.g. pddl/domain_find_dice.pddl) and tweak it for
     their env, rather than editing the shared domain.  Bridge their scene
     (object poses, the die, the cups) into our belief/streams; ground a
     problem; plan; execute.  STOP and get user CONFIRMATION that it works
     before the eval.
     NOTE (scope, not pushback -- "the code wins"): the integration surface
     is LARGER than the domain file alone.  Their occlusion is CONTAINMENT
     (cup over die) vs our LATERAL shadow (CAVEAT below); their
     robot/grasps/IK/motion differ from our streams; our execution loop
     assumes our env API.  Expect adapter work beyond the new .pddl -- the
     new domain is the START of Phase 3, not the whole change.
  PHASE 4 -- EVAL.  Both systems on the SAME env + SAME hardware: success
     rate + time over >= 20 problems/seeds.  Plot ours vs real-TAMPURA
     (Phase 2) -- now same task AND same hardware, removing the
     cross-hardware caveat the published-number comparison carries.

CARE (new plan):
  - GUI for every run (user drives it).  Per-change: one commit, before/
    after preview, explicit approval (workflow skill); plots ADD never
    overwrite.
  - find_dice goal = holding(die) AND at-home; ours is holding only -- add a
    go-home in the Phase-3 problem or note the one-action asymmetry (#177).
  - Keep the CAVEAT (occlusion-mode) section below -- it now bounds Phase 3,
    not a preset design.
  - reference_tampura_perf.md / thesis #190: TAMPURA model-learning is
    ONLINE per-step; do NOT reintroduce the "offline Learn-Model" framing
    when writing up Phase 2/4.

--------------------------------------------------------------------------------
SUPERSEDED APPROACH (preset-in-our-framework; kept for record 2026-05-25).
The SMOKE-TEST RESULT below is still a VALID finding about our system (the
relocate->sense->pick capability works; a lone small occluder fails to
ground via test_target_can_hide_in_shadow).  Only the "build a
find_dice_equiv preset and sweep OUR scenes" plan is dropped, in favour of
the head-to-head on THEIR env above.
--------------------------------------------------------------------------------
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

SMOKE-TEST RESULT (2026-05-24 -- feasibility CONFIRMED-WITH-CAVEATS; the
       failure mode is NOT the one this block hypothesized).  Headless WSL,
       --goal holding --baseline semantic.
       (1) CAPABILITY EXISTS.  default scene, seed 0, SOLVES in one plan,
           NO give-up: move->pick(green=occluder)->place(green,free_005)->
           sense->pick(cyan=hidden target).  The planner DELIBERATELY
           relocates an occluder to reveal, senses, picks.  So
           discussion.tex:101's blanket "view-restoration = future work" is
           OVER-BROAD for single-layer (finding only; prose is thesis-side,
           do NOT edit under this empirical task).
       (2) NAIVE single-occluder find_dice-equiv FAILS TO GROUND (not
           gives up).  --scene random-pairs --n-occluders 1 -> NO PLAN, 0
           skeletons at complexity 0-3.  ROOT CAUSE (exported problem +
           code): sense needs (boxel_fits ?o ?region) over the SHADOW
           (domain:162); for shadows that is gated by
           test_target_can_hide_in_shadow (pddlstream_planner.py:531-534,
           streams.py:407), which raycasts the target's 8 AABB corners over
           a 3x3 grid and emits ONLY if a candidate is FULLY occluded.  A
           lone small box (0.078 m) casts a shadow whose AABB (0.216 x
           0.244 m) over-covers the true occlusion cone, so no candidate is
           fully occluded -> boxel_fits(target,shadow) absent -> sense
           unsatisfiable -> 0 skeletons.  SCENE-GEOMETRY/preset issue.
       (3) DECOY OCCLUDER grounds but exposes a 2nd issue.  --scene
           scalability --n-occluders 2 --n-targets 1 --n-hidden 1, seed 0:
           GROUNDS + plans the correct pick->place->sense->pick, but
           EXECUTION collides relocating the occluder into the decoy,
           drop-verify fails 3x (#75/#80), replans, then stalls in
           escalating-timeout sampling (#50/#62 slow-planning pathology).
       VERDICT: T2 NOT plot-only, but the gating risk is DIFFERENT from
       this block's hypothesis -- not "robust view-restoration dev work",
       but (a) PRESET DESIGN: occluder sized/placed so the hide-test
       RELIABLY passes (Care(2) hinted this) AND relocation has
       collision-free room; (b) robustness vs the known execution-collision
       + slow-replanning pathology in tight decoy scenes.  "2-4 days if
       feasible as a preset" still holds; days go to preset geometry + run
       robustness, not view-restoration.

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
    [FOLDED INTO T2 PHASE 1 -- 2026-05-25; body kept below as the bring-up reference]
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

