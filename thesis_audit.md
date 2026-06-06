================================================================================
THESIS AUDIT — OPEN ISSUES
================================================================================
Date:   2026-05-16
Target: the Master thesis in thesis/ ("main.pdf", ~58 pages),
        "Semantic Partitioning for Partially Observable Deterministic Task and
        Motion Planning."
Method: six parallel review passes (proposal-vs-code deviation, scientific/citation
        correctness, writing style). 120 findings (#1-#120), de-duplicated; #121-#130
        added 2026-05-17 (proposal-to-thesis structural work).

Counterpart of CODEBASE_AUDIT.txt. Work with the /workflow skill: one issue per turn,
before/after, explicit approval, `latexmk main.tex` recompile, individual commit, mark [DONE].

================================================================================
CONTEXT & POLICY
================================================================================
PROPOSAL, NOT YET A THESIS — main.pdf is a research proposal (2025-09-29, forward-
   looking); the code was built after and drifted. Some issues are now-fixes, some are
   proposal-to-thesis reconciliations.
THESIS_NOTES.md is canonical for accepted simplifications — a deviation disclosed there
   is lower-risk; one NOT disclosed is flagged "(undisclosed)".

SECTION -> SOURCE FILE (all under thesis/)
   Abstract  chapters/abstract.tex      §1 Intro   chapters/introduction.tex
   §2 Background chapters/background.tex §3 RelWork chapters/related-work.tex
   §4 Methods chapters/methods.tex       §5 Results chapters/results.tex
   §6 Discussion chapters/discussion.tex §7 Concl   chapters/conclusion.tex
   Appendix chapters/appendix.tex        References resources/references.bib

TIERS   T0 factual/scientific/citation error · T1 major proposal-vs-impl deviation ·
        T2 style/clarity/honest-framing · T3 minor (naming, headings, build, polish).
DISPOSITION  [NOW] correctness error, apply anytime · [POLISH] prose-quality rewrite ·
        [THESIS] proposal-to-thesis conversion (reconcile w/ built system, report results).
STATUS  no marker = OPEN; resolved = [DONE] (or [REJECTED]) on the header line.
NUMBERING  #N is filing order, not priority — read the TIER tag.

#168  [DONE 2026-05-27] [T1] [THESIS]  Figures/captions review --- go through every figure one by one
#175  [REJECTED 2026-06-06] [T2] [THESIS]  methods.tex shadow-splitting text vs code (CODEBASE #102/#103)
#176  [DONE 2026-05-25] [T3]  Discretization-progression figure (PyBullet captures) + free-space split->merge stages (merged #196)
#177  [DONE 2026-05-25] [T0]  TAMPURA comparison: wrong task + self-contradiction (now holding, wall-clock)
#178  [DONE 2026-05-25] [T1]  Intro says the partition discretizes "only" objects + occlusions (omits free space)
#179  [DONE 2026-05-25] [T2]  Intro contributions: drop TAMPURA from section 1, cut the "first-class state" opener
#180  [DONE 2026-05-25] [T3]  Background state-model notation: Pi for the tuple is unconventional
================================================================================
#181  [DONE 2026-06-06] [T2] [POLISH]  POD vs contingent-planning naming -- bare hedge already removed in #285/#286 rewrite; current text presents POD as our descriptive label + cites the compilation lit (albore2009/geffner2013) without equating it to contingent planning. No edit (author reverted naming).
NOTE 2026-05-25: naming attempt REVERTED per author. POD is the problem setting (deterministic
+ partially observable); contingent planning is a SOLUTION family for it (branching plans) and
not the approach this thesis uses (it determinises-and-replans). Don't equate the two. Original
hedge restored; if reworded, name contingent planning as a solution family, not a synonym for POD.
================================================================================
background.tex:85 hedges that "POD" isn't established terminology. Verified: the literature
calls this exact setting CONTINGENT PLANNING; the hedge is true but bare. Fix: name it —
"This is the setting the planning literature calls \emph{contingent planning}
\cite{albore2009translation, geffner2013concise}; 'POD' is the descriptive label we use."
Refs: background.tex:85; albore2009translation; geffner2013concise.

#182  [DONE 2026-05-25] [T3]  Background heading "Voxel Grids and Octrees" -> "Voxel Grids"
#183  [DONE 2026-05-25] [T0]  related-work.tex:12 Bayes3D scaling claim + TAMPURA belief source
#184  [DONE 2026-05-25] [T3]  pan2024task: "reactive controllers" -> their term is "behaviors"
#185  [DONE 2026-05-25] [T2]  Rewrite the hard-to-read Ma et al. paragraph
#186  [REJECTED 2026-05-25] [T2]  CoCo-TAMP description too thin -- expand mechanism
#187  [DONE 2026-05-25] [T1]  related-work.tex:24 Bai et al.: wrong limitation + framework name/mechanism (merged #192)
#188  [DONE] [T0] [NOW]  related-work.tex:27 belief-space paragraph: false SS-Replan contrast (+ jargon)
#189  [DONE 2026-05-25] [T0]  related-work.tex:30 overgeneralizes the knowledge-literal / compile-to-classical claim
#190  [DONE 2026-05-25] [T0]  TAMPURA model-learning is ONLINE per-step (was framed "pays it offline")
#191  [DONE 2026-05-25] [T3]  Intro hero caption: identify the target object
#192  [MERGED 2026-05-25 into #187]  Bai et al.: TAVP naming + end-to-end-learned-policy
#193  [DONE 2026-06-06] [T1] [THESIS]  Relocate/shrink "Spatial Belief Representation in TAMP" into Background
#194  [DONE 2026-05-25] [T2]  Related-work framing: drop marketing voice; cut the over-long "three advantages" paragraph
#195  [DONE 2026-05-25] [T2]  Methods clarity: rephrase "optimistic determinisation", explain "untyped STRIPS", delete a self-justification
#196  [MERGED 2026-05-25 into #176]  Free-space generation stages (split -> convex merge) figure
#197  [DONE 2026-05-25] [T1]  fig:replan-cycle caption is wrong vs the image
#198  [DONE 2026-05-25] [T3]  Figure captions/sizes to fix after visual inspection
================================================================================
#199  [T2] [THESIS]  Rename task terms to reader-facing names (drop code terms)
================================================================================
Document-wide. Code task names confusing in prose. Use FIND (= holding; locate a hidden object
and pick it), STACK, FIND AND STACK (= find-and-tray-stack). Fix: rename in PROSE only (holding
-> find; find-and-tray-stack -> find and stack; stack stays); keep figure FILE names; axis
labels may need a plotter label map (CODEBASE). Audit-internal refs in #177/#190 keep "holding".
Refs: results.tex; discussion.tex; conclusion.tex; abstract.tex; methods.tex; #177.

#200  [DONE 2026-05-25] [T0]  results:83 "well under a second per call" is FALSE
#201  [DONE 2026-05-25] [T2]  Results clarity: drop_failed, denominator note, "known to be empty", one-boxel-per-object
#202  [DONE 2026-05-25] [T1]  semantic+mbs0.05 is effectively identical to semantic (a no-op variant)
#203  [DONE 2026-05-25] [T0]  discussion:60 "at the cost of more cells" is FALSE; "characterisation of the regime" is empty
#204  [DONE 2026-05-25] [T2]  discussion:24 stack-goal boxel ratio -- stack needs no free-space partition
#205  [DONE 2026-05-25] [T0]  discussion:266 stacking slowdown misattributed (bigger domain, not pick conditional-effects)
#206  [DONE 2026-05-25] [T2]  Discussion section-6 trims and clarity
#207  [DONE 2026-05-25] [T3]  Success-rate-vs-n_occ caption should state what the band is
#208  [DONE 2026-06-06] [T3] [THESIS]  Add the code repository links (GitHub + GitLab)
================================================================================
#209  [T2] [THESIS]  Results: resolution-floor sweep -- effect of min free-space leaf size on total boxel count
================================================================================
results.tex (subsec:compactness ~:194; new subsection+figure). Supplies evidence for #203 and
justifies #202. ADD a study of how the free-space floor (min_boxel_size) changes TOTAL boxel
count, swept below+above autocell. Data in eval_results/sweep_anytime/aggregated.csv (mean total,
baseline=semantic, 300 cells/arm; 1.5x/2x = CODEBASE #100):
  find-and-stack: 0.05->45.05 | auto(0.09)->44.95 | 1.5x->26.96 | 2x->26.59
  find:           0.05->35.03 | auto(0.09)->35.07 | 1.5x->20.39 | 2x->20.16
  stack:          0.05->27.79 | auto(0.06)->27.79 | 1.5x->27.79 | 2x->22.24
FINDING (data-confirmed): finer than autocell does NOT add cells (convex merge re-absorbs);
coarser (>=~1.5x) cuts sharply; object+shadow counts unchanged (floor touches only free space).
Fix: short subsection + figure (CODEBASE #108) total boxels vs floor (multiple of autocell) per
goal; state finer=no change, coarser=fewer. Coordinate w/ #202/#203.
Refs: results.tex:194; discussion.tex:60; #202; #203; CODEBASE_AUDIT #108, #98/#100/#101; eval_results/sweep_anytime/aggregated.csv.

================================================================================
#210  [T3] [POLISH]  Related Work: drop author names, cite by number ([4]) --- VERY LOW PRIORITY
================================================================================
related-work.tex throughout. Replace inline "<Author> et al." lead-ins with numeric citation
labels (e.g. "[4] introduces ..."). Mechanical low-priority polish once T0/T1 content is settled;
watch sentences whose grammar depends on the author name as subject.
Refs: related-work.tex (document-wide citation style).

#211  [DONE 2026-05-26] [T1]  Abstract repeats #178's "only" (omits free-space Boxels)
#212  [DONE 2026-05-26] [T1]  Abstract: drop TAMPURA, clarify "compiling belief", fix false "no speed winner"
#213  [DONE 2026-05-27] [T1]  TAMPURA Table II is PER-STEP, not per-episode (arXiv v2 PDF) -- re-derive comparison
#214  [DONE 2026-06-01] [T2] [POLISH]  Abstract: "Semantic Boxel" used before it is defined -- p.iii (PDF4)
#215  [DONE 2026-06-01] [T3] [THESIS]  Abstract: "PDDLStream-based planner" highlighted, no comment -- p.iii (PDF4)
#216  [DONE 2026-06-01] [T2] [NOW]  Intro: sensing actions do not "succeed" -- p.2 (PDF8)
#217  [DONE 2026-06-01] [T2] [POLISH]  Intro: briefly explain Know-If Fluents at first mention -- p.3 (PDF9)
#218  [DONE 2026-06-01] [T2] [POLISH]  Background: introduce states directly as sets of atoms -- p.4 (PDF10)
#219  [SKIPPED 2026-06-01] [T3] [POLISH]  Background: "see before" -- redundant with earlier text -- p.5 (PDF11)
#220  [DONE 2026-06-01] [T3] [POLISH]  Background: do not expand the STRIPS acronym -- p.5 (PDF11)
#221  [SKIPPED 2026-06-01] [T3] [THESIS]  Background: bare highlight on "The" -- p.5 (PDF11)
#222  [DONE 2026-06-01] [T0] [NOW]  Background: is goal_achieved an atom? -- p.7 (PDF13)
#223  [DONE 2026-06-01] [T0] [NOW]  Background: cite the origin of Know-If Fluents -- p.7 (PDF13)
#224  [DONE 2026-06-01] [T2] [THESIS]  Background: motivate KIFs vs K-literals -- p.7 (PDF13)
#225  [DONE 2026-06-01] [T2] [NOW]  Related Work: "Sidd's Critical Regions" -- is that the real term? -- p.10 (PDF16)
#226  [DONE 2026-06-01] [T0] [NOW]  Related Work: "combines these techniques" -- you don't learn regions -- p.10 (PDF16)
#227  [DONE 2026-06-01] [T2] [POLISH]  Related Work: "treated by Geffner and Bonet" is unclear -- p.13 (PDF19)
#228  [DONE 2026-06-01] [T3] [POLISH]  Related Work: add a back-reference to Section 2.2 -- p.13 (PDF19)
#229  [DONE 2026-06-01] [T2] [POLISH]  Related Work: "?" on the bounded-give-up sentence -- p.14 (PDF20)
#230  [SKIPPED 2026-06-01] [T1] [THESIS]  Related Work: cite the AAAI'25 online critical-regions follow-up -- p.15 (PDF21)
#231  [INFO] [NO ACTION]  Methods: "good intro so far" -- p.16 (PDF22)
#232  [DONE 2026-06-01] [T3] [POLISH]  Methods: simplify the (BXset) symbol -- p.16 (PDF22)
#233  [DONE 2026-06-01] [T2] [THESIS]  Methods: separate the concept from the implementation -- p.16 (PDF22)
#234  [INFO] [NO ACTION]  Methods: "good figure!" -- p.17 (PDF23)
#235  [SKIPPED 2026-06-01] [T2] [THESIS]  Methods: "Line of sight" legend entry -- "I don't see it" -- p.17 (PDF23)
#236  [DONE 2026-06-01] [T3] [NOW]  Methods: Fig 4.2 is not referenced in the text -- p.17 (PDF23)
#237  [DONE 2026-06-01] [T1] [NOW]  Methods: KIFs vs K-literals -- "I'm confused" -- p.19 (PDF25)
#238  [DONE 2026-06-01] [T1] [THESIS]  Methods: state explicitly that this is simplified POD planning -- p.22 (PDF28)
#239  [DONE 2026-06-01] [T1] [THESIS]  Methods: a real POD planner (e.g. LW1) has deductive axioms -- p.23 (PDF29)
#240  [DONE 2026-06-01] [T2] [POLISH]  Results: clarify the stack goal -- specific tower or any stack? -- p.24 (PDF30)
#241  [DONE 2026-06-02] [T3] [THESIS]  Results: "Software" paragraph highlighted, no comment -- p.26 (PDF32)
#242  [DONE 2026-06-02] [T1] [THESIS]  Results: explain the performance degradation (Fig 5.6) -- p.30 (PDF36)
#243  [DONE 2026-06-02] [T3] [THESIS]  Results: Fig 5.12 reds are too similar -- p.35 (PDF41)
#244  [SKIPPED 2026-06-02] [T2] [POLISH]  Discussion: separate Discussion section -- accepted, optional merge -- p.36 (PDF42)
#245  [DONE 2026-06-02] [T2] [THESIS]  Discussion: state the overall conclusion of the comparison -- p.38 (PDF44)
#246  [DONE 2026-06-02] [T0] [NOW]  Discussion: "This is not entirely true." -- p.39 (PDF45)
#247  [DONE 2026-06-02] [T0] [NOW]  Discussion: "You did run TAMPURA, just not on the same problem." -- p.39 (PDF45)
#248  [DONE 2026-06-01] [T1] [THESIS]  Discussion: simplified POD does not scale (missing deductive axioms) -- p.41 (PDF47)
#249  [DONE 2026-06-02] [T2] [POLISH]  Conclusion: too much detail -- p.42 (PDF48)
#250  [DONE 2026-06-02] [T2] [THESIS]  Conclusion: future work -- real-robot experiments -- p.43 (PDF49)
#251  [DONE 2026-06-02] [T2] [POLISH]  Cross-cutting: redundancy -- things explained multiple times -- (email 2026-05-31)
#252  [INFO] [NO ACTION]  Overall verdict (email 2026-05-31)
#253  [DONE 2026-06-02] [T3] [THESIS]  Background: add a FastDownward + planning-algorithms section  (AUTHOR-PLANNED, not a Till comment)
#254  [DONE 2026-06-02] [T2] [THESIS]  Define "Boxel" crisply at first body use (intro/methods)  [follow-up to #214]
#255  [DONE 2026-06-01] [T3] [POLISH]  Related Work: "cost" overloaded vs "plan cost"  [author finding, not on Till's list]
#256  [DONE 2026-06-02] [T2] [THESIS]  Results: delete the "Software" paragraph  (author decision; supersedes #241)
#257  [DONE 2026-06-02] [T1] [THESIS]  Background: text cutoff (overfull \hbox) in state-space example  (author/build finding)
================================================================================
#258  [T2] [THESIS]  Background: explain what an MDP is, with examples
================================================================================
[AUTHOR] "explain what a classical planner is and give examples; same for MDPs." Classical-planner
half is RESOLVED by #253 (new 2.1.2 with Fast Downward/FF/LAMA). Remaining: Background never defines a
Markov Decision Process / MDP with examples, yet MDPs are leaned on in the TAMPURA comparison and RW.
Add a short MDP (and POMDP contrast) explanation in Background, parallel to the classical-planner section.
Refs: background.tex (2.2.2 / sec:pod); #253; discussion.tex:84-106; related-work.tex:11.

#259  [DONE 2026-06-06] [T2] [THESIS]  Related Work: clarify "provably optimal ones"
#260  [REJECTED 2026-06-06] [T2] [THESIS]  Related Work: state how we differ from TAMPURA and Saleem (end of POMDP-TAMP para)
#261  [DONE 2026-06-06] [T2] [THESIS]  Related Work: verify Ma et al. "separate pre-planning step" claim
#262  [DONE 2026-06-06] [T2] [THESIS]  Related Work: Contingent-FF and MBP named without citations
#263  [DONE 2026-06-04] [T1] [THESIS]  Related Work: "Object Integrity" octree argument does not apply to our system
================================================================================
#264  [T2] [THESIS]  Pose sampling vs (partial) occlusion; relax "hidden" to all-8-corners-occluded
================================================================================
[AUTHOR] How are object poses sampled -- can we sample a (partially) hidden object? If so, the visibility
test could count an object as hidden only when all 8 bounding-box corners are occluded (vs the current
criterion). Investigate in code, then decide whether to relax the hidden/visible test and update methods.
Refs: methods.tex (perception/visibility, sense action); pose-sampling stream code.

#265  [REVERTED 2026-06-06] [T2] [THESIS]  Methods: fig:boxelization caption "largest occluder" -> "bottom occluder"
#266  [DONE 2026-06-04] [T1] [THESIS]  Methods: shadow extends to end of hidden region, not the workspace boundary
#267  [DONE 2026-06-05] [T2] [THESIS]  Methods: fig:boxelization-real caption "object bounding cuboids" correction
#268  [DONE 2026-06-05] [T2] [THESIS]  Methods: add pseudocode for adaptive semantic discretization
================================================================================
#269  [T2] [THESIS]  Methods: verify Boxel set is supplied to the planner as static facts in initial state
================================================================================
[AUTHOR] methods.tex:38 claims "the completed set of Boxels is supplied to the planner as static facts in
its initial state." Walk the code and confirm (static facts; initial state) before keeping the claim.
Refs: methods.tex:38; initial-state construction code.

================================================================================
#270  [T2] [THESIS]  Results: Figure 5.3 (overhead-camera) caption is outdated
================================================================================
[AUTHOR] results.tex:79 (fig:overhead-camera, Figure 5.3) caption is outdated. Identify what changed and
update it.
Refs: results.tex:79 (fig:overhead-camera).

================================================================================
#271  [T2] [THESIS]  Results: exit-reason / failure-mode list needs an update
================================================================================
[AUTHOR] results.tex:96 exit-reason list (planner_failed, timeout, replan_limit, physics_mismatch,
drop_failed, ...) needs updating; ties to #243 (no_summary/replan_limit change in the next data
iteration). Reconcile with the current exit reasons.
Refs: results.tex:96; #243.

#272  [DONE 2026-06-04] [T1] [THESIS]  Results: explain why uniform planning cost grows with n_occ (Fig 5.8)
#273  [DONE 2026-06-05] [T3] [POLISH]  Terminology: find a better word than "cuboid"
#274  [DONE 2026-06-04] [T2] [THESIS]  Methods fig:boxelization panel (c): schematic renders shadows to workspace boundary, not hidden-region end
#275  [DONE 2026-06-04] [T1] [THESIS]  Abstract: drop the PDDLStream mention
#276  [DONE 2026-06-04] [T1] [THESIS]  Background: present STRIPS first, then DERIVE the state model (don't define it twice)
#277  [DONE 2026-06-04] [T2] [THESIS]  Whole document: fix many small language/grammar errors
#278  [DONE 2026-06-04] [T1] [THESIS]  KIFs vs K-literals: not interchangeable; use KIFs consistently + cite their source
#279  [DONE 2026-06-04] [T3] [THESIS]  Delete the stray article "the" before PDDL/PDDLStream
#280  [DONE 2026-06-04] [T1] [THESIS]  Related Work/Background (Critical Regions): cite the new DYNAMIC-abstraction paper; "static" claim no longer holds
#281  [DONE 2026-06-04] [T1] [THESIS]  Results/Discussion: stack-goal degradation explanation is WRONG (sim/control limit, not planning difficulty)
================================================================================
#282  [T1] [THESIS]  Results/Discussion: refresh ALL numbers + conclusions from the NEW sweep
================================================================================
[SUPERVISOR 2026-06-04] Current results/discussion numbers, figures, and conclusions (success rates, plan
times, reliability-vs-TAMPURA, failure-mode plot colours) are from the OLD data; the author now has a new
sweep. Refresh everything once the canonical sweep lands: re-derive tab:headline, fig:plantime-holding,
fig:success-*, fig:boxel-count-*, the TAMPURA comparison numbers, and the discussion's reliability claims.
Failure-mode plot: replan_limit removed (limit dropped) and no_summary was a bug (removed) -> only timeout
+ planner_failed remain (orange + red). Gated on CODEBASE_AUDIT.txt #113 (canonical sweep) and #104.
Refs: results.tex; discussion.tex; abstract.tex; CODEBASE_AUDIT.txt #113 #104. Related: #199 #209.

[FINDINGS 2026-06-04 — measured from sweep_full_2026-05-28] Core 3 goals x 3 variants {semantic,
+mbs0.05, uniform} COMPLETE at 90 cells each (30 seeds x 3 difficulties; OLD was 300 = 100 x 3, so
sample is smaller -> wider CIs). Coarse free-space resolution arms (mbs 0.135/0.18/...) still running,
so fig:boxel-resolution + the resolution-axis numbers in subsec:resolution / disc-validity are NOT yet
refreshed (old resolution sweep retained). Figures refreshed from this sweep (old PNGs backed up in
backups/thesis_graphics_2026-06-04_20-29-58): success_rate_vs_n_occluders__{holding,find-and-tray-stack,
stack}, planning_time_vs_n_occluders__holding, boxel_count_breakdown__holding, tampura_wallclock_
comparison, failure_modes, solved_vs_time. Preserved: boxel_count_vs_resolution.

A. ROOT CAUSE (drives nearly every change) — per-episode replan cap REMOVED (code #107); episodes now
   run to the 1800s wall-clock budget. Effects: mean replan count up 3-6x (holding sem 2.31->12.59,
   stack sem 1.19->11.14, f-a-t-s sem 3.03->7.59); success-only mean planning time up ~17x (holding sem
   7.78->134.30s); the replan_limit exit reason DISAPPEARS (0 cells) and those episodes now end in
   timeout instead.

B. RESULTS (results.tex) — OLD -> NEW (success% / mean success-only plan s):
   tab:headline (full replace; n_cells 299/300 -> 90):
     f-a-t-s: sem 39.8/28.37 -> 75.6/124.62 ; mbs05 33.0/21.49 -> 72.2/82.14 ; uni 1.3/156.10 -> 34.4/692.11
     holding: sem 42.3/7.78  -> 65.6/134.30 ; mbs05 46.3/7.42  -> 66.7/56.64 ; uni 33.3/50.35 -> 47.8/438.53
     stack:   sem 61.3/1.23  -> 64.4/17.16  ; mbs05 61.3/1.23  -> 64.4/3.10  ; uni 39.2/23.84 -> 35.6/924.13
   - "semantic vs uniform differ by an order of magnitude or more in BOTH axes" -> in TIME now only stack
     (~54x); holding ~3.3x, f-a-t-s ~5.6x. Reword to "several-fold (holding/FATS) to >50x (stack)".
   - subsec:anytime "uniform on FATS never gets off the ground (4/300)" -> FALSE: FATS uniform now
     31/90 = 34.4%. "semantic curves rise to final value within ~10-30s" -> success-only planning is now
     ~57-134s; fig:solved_vs_time shifted right (refreshed).
   - subsec:success-rate per-goal text: holding "sem 39-47 / mbs05 44-48 / uni 31-36" -> sem 60-77 /
     mbs05 63-70 / uni 43-53. stack "97/74/13, uniform 97/20/1" -> sem 100/80/13.3, uniform 90/16.7/0.
     FATS "uniform <=2/100, semantic ~40" -> uniform 60/16.7/26.7, semantic 73.3/66.7/86.7
     (NB semantic FATS no longer flat — rises with n_occ).
   - subsec:planning-time holding "adaptive <20s, uniform 21->83s" -> adaptive ~85-234s, uniform 302-570s.
   - subsec:compactness — boxel + init-fact counts ~UNCHANGED (geometry-derived): holding sem ~31 / uni
     ~329, stack init-facts ~268 vs ~12,100. Compactness story STANDS.
   - subsec:tampura "our planning mean 7.8s, success 42% vs TAMPURA >=63%" -> planning 134.30s, success
     65.6%. fig:tampura refreshed.
   - subsec:failure-modes "planner_failed dominant; replan_limit predominantly on stack" -> replan_limit
     GONE; no_summary gone; TIMEOUT now dominant. Core-3-variant failure counts (match refreshed fig):
     timeout 194, planner_failed 96, physics_mismatch 27 (holding only), all_searched 18 (holding only),
     drop_failed 1 (f-a-t-s). By goal: f-a-t-s=timeout 85/pf 20/drop 1; holding=timeout 44/physmis 27/
     pf 19/allsrch 18; stack=timeout 65/pf 57. (Refreshed fig:failure-modes renders 3 visible bands —
     success/planner_failed/timeout — physics_mismatch+all_searched appear folded into planner_failed,
     consistent with code #106 intent.) Rewrite caption+text: stack now fails via timeout+planner_failed,
     not replan_limit; FATS uniform is mostly timeout (not planner_failed).
   - planning-budget para median per-call (0.97 stack / 2.05 find / 2.97 f-a-t-s): re-verify vs new sweep.

C. DISCUSSION (discussion.tex):
   - sec:disc-semantic-vs-uniform: "uniform still solves about a third" (holding) -> now ~half (47.8%);
     "find-and-tray-stack ... uniform is effectively broken (1.3%)" -> FALSE, now 34.4% — reframe
     "broken" as "much weaker but functional"; stack "97->13 vs uniform 97->1" -> 100->13.3 vs 90->0.
   - sec:disc-mbs0: "holding floor ~4pp ahead; FATS ~7pp behind with degradation as n_occ grows" ->
     holding mbs05 ~1pp ahead; FATS ~3pp behind and NON-monotonic (70/76.7/70). stack overlap holds.
   - sec:disc-tampura: CENTRAL CLAIM COLLAPSES. Two framings, both kill "order of magnitude cheaper":
       (i) wall-clock vs TAMPURA per-episode (fig:tampura axis): OLD 13.7s vs 166s (~12x cheaper) ->
           NEW 144.4s vs 166s = PARITY (~1.15x).
       (ii) planning-only vs TAMPURA Table II 57s: our success-only planning 7.78 -> 134.30s = now
            ~2.3x SLOWER.
     Reliability flips the other way: success 42% -> 65.6%, i.e. now COMPARABLE-or-BETTER than TAMPURA's
     ~55-63%. Net: "cheaper-but-less-reliable" -> "comparable/slower-but-more-reliable". Major rewrite of
     this section + fig:tampura caption. (The architectural/qualitative contrast — deterministic replanning
     vs learned MDP, plannable occlusion — is data-independent and STANDS.)
   - sec:disc-validity Resolution-regime para: numbers unchanged for now (resolution arms pending) — flag.

D. CONCLUSION (conclusion.tex):
   - "solves cluttered scenes the uniform baseline effectively cannot" -> WEAKENED (uniform now solves
     ~34% of FATS, ~36-48% of holding/stack).
   - "roughly an order of magnitude cheaper end-to-end, though less reliably" -> INVERTED (now comparable/
     slower but more reliable) — sync with disc-tampura.
   - "order of magnitude fewer cells" (compactness) -> STILL HOLDS.

E. LIMITATIONS (sec:limitations) + FUTURE WORK (sec:future_work): no hard eval numbers; qualitative
   claims unaffected. Bounded give-up still counts as failure (unchanged). Future-work directions unchanged.

F. ALSO (outside the 5 sections but same headline): abstract.tex almost certainly repeats "order of
   magnitude cheaper / fewer cells" — refresh together with disc-tampura/conclusion.

PENDING (when coarse mbs arms finish): refresh fig:boxel-resolution + subsec:resolution/disc-validity
resolution numbers, then re-run this same diff against those.

APPLIED (2026-06-04, /workflow; one commit per unit):
  [x] B tab:headline full replace (n_cells 299/300 -> 90) + "order of magnitude in both axes" framing
      reworded to several-fold (holding ~3.3x, FATS ~5.6x) to >50x (stack); success-rate gap ~1.4-2.2x.
      Caption notes the new 90 = 30 seeds x 3 difficulties sample.
  [x] subsec:anytime: rewrote the 3 observations (semantic rise ~15s on stack / ~124-134s on holding+FATS;
      uniform FATS solves 34.4% not 4/300; uniform stack 0 -> 36% after ~800s) + caption. Axis wording made
      neutral pending the log -> linear figure change (separate unit, author request).
  [x] fig:solved-vs-time -> linear x-axis (author request; outside original catalog): repointed the
      \includegraphics to solved_vs_time_linear.png (already emitted by eval_plotter from this sweep, log_x=False);
      the log solved_vs_time.png is preserved in thesis/graphics, not deleted.
  [x] subsec:success-rate: holding 60-77/63-70/43-53 (~18pp gap, 30 seeds); stack 100/80/13.3 vs 90/16.7/0;
      FATS uniform 60/16.7/26.7, semantic 73.3/66.7/86.7 (no longer flat), mbs05 70/76.7/70 non-monotonic.
      Captions updated; fig:success-stack caption left as-is (still accurate).
  [x] subsec:planning-time: holding adaptive ~38-234s (not <20s), uniform 302-570s; stack sem 2-31s vs
      uniform 875-1189s; FATS sem 20-253s vs uniform 623-865s. Dropped "scale gracefully"/"four-to-five
      times" (adaptive now non-monotonic, semantic peaks at n_occ=3); representation mechanism kept verbatim.
  [x] subsec:failure-modes: regenerated to semantic-vs-uniform ONLY (6 bars) per author "just this figure"
      -> added thesis/graphics/failure_modes_sem_uni.png (3-variant failure_modes.png preserved) via
      tools/regen_failure_modes_sem_uni.py; rewrote text+caption: timeout now dominant, no replan_limit
      mention, no mbs0.05. TEMPORARY MISMATCH (author-accepted): this figure shows 2 variants, the rest of
      Results (table + other figures) still shows 3; mbs0.05 removal scope = this figure only for now.
  [x] AUTHOR DIRECTIVE (never mention the replan limit): removed all replan-limit/cap references + change-narration
      from prose -- sec:metrics Success def + failure-mode list; subsec:anytime + subsec:planning-time dropped the
      "with the cap removed" framing and the "before / no longer" wording. Thesis presents the system as-is.
  [x] AUTHOR DIRECTIVE (explain planner_failed; drop physics_mismatch/all_searched jargon): failure-modes caption
      now glosses planner_failed as the non-timeout failures (no usable plan, or a plan found but execution/search
      never reached the goal); removed the sub-identifier names from caption + paragraph. Label "planner_failed"
      kept to match the figure legend; optional figure-legend rename offered to the author.
  [x] subsec:setup (Scenes and seeds): 100 -> 30 random scenes; headline 2700 -> 810 cells; decoupled the
      resolution-arm count (PENDING earlier 100-seed sweep, reported in subsec:resolution) instead of a mixed ~4500.
  [x] AUTHOR: rename failure bands to plain words (success / plan failed / timed out) -- regenerated
      failure_modes_sem_uni.png (relabeled via tools/regen_failure_modes_sem_uni.py; colours carried over) +
      rewrote sec:metrics Failure-mode def, subsec:failure-modes paragraph + caption to the two plain
      categories; dropped ALL raw identifiers (planner_failed/timeout/physics_mismatch/all_searched/drop_failed).
      Legend title still "exit_reason" -- offered to rename to "outcome".
  [x] subsec:setup planning-budget para (L83) + metrics denominator (L96): re-derived from the sweep --
      1800s is the per-CELL wall-clock budget (not per-call); timeout now 24% of cells (FATS 31 / stack 24 /
      holding 16), not "rare"; per-call medians stack 1.3 / holding 3.4 / FATS 7.0s (median over successful
      cells); dropped the stale "flat past ~200s"; snapshot-null denominator gap 6% -> 18% (144/810).
  [x] subsec:compactness: verified vs refreshed boxel_count_breakdown__holding figure -- compactness STANDS.
      Only tweak: adaptive holding total $\sim$25--43 -> $\sim$22--38 (new 30-seed scenes); uniform ~300 free-space,
      stack ~25 vs ~1340, and adaptive-vs-uniform fact counts all confirmed within rounding (geometry-derived).
  [x] subsec:tampura (Results): reframed per author choice -- per-episode wall-clock 144.4s vs 166s = PARITY
      (was 13.7 vs 166 "order of magnitude cheaper"); median 8.5 -> 21.6s; per-step ~11s vs 57s (still cheaper,
      NOT "2.3x slower" -- avoided the #213 per-episode-vs-per-step mismatch); reliability 42 -> 65.6% vs local
      55% (now AHEAD). Net "cheaper-but-less-reliable" -> "parity-on-cost, somewhat-more-reliable". Caption updated.
  [x] AUTHOR wording (Results): (1) planning-budget per-call sentence: my right-skewed rewrite was REVERTED to
      the original wording per author. MATH CAVEAT (verified): medians 1.3/3.4/7.0s are correct, but the
      original's "rather than slow calls" is unsupported -- mean/call (total/plans) = 1.5/10.7/16.4s, >> median
      on holding/FATS, and FATS reaches ~125s with only ~7.6 replans, so slow calls drive the long episodes.
      RESOLVED 2026-06-06: re-verified (sanity-checked sum(per-call)==sum(total); max call ~1350s holding /
      ~1606s FATS; 56-58% of holding/FATS planning time from above-median (slow) calls; stack only 7%) and
      corrected the sentence to "usually short but heavy-tailed; long holding/FATS episodes from the slow-call
      tail + repeated replanning; stack = many fast calls". (2) subsec:tampura: dropped before/after "now" ("Reliability now runs in our favour" -> "On
      reliability the comparison favours us") and the "picture is similar / still well under" phrasing.
  [x] sec:disc-semantic-vs-uniform: holding uniform "about a third" -> "about half" (47.8%); stack adaptive
      97->13 -> 100->13, uniform 97->1 -> 90->0; FATS "effectively broken (1.3%)" -> "much weaker but still
      functional (34.4% vs semantic 75.6%)"; compactness 25-43 -> 22-38, ~320 -> ~300 (match Results).
  [x] sec:disc-mbs0: holding floor ~4pp -> ~1pp ahead; FATS ~7pp -> ~3pp behind + non-monotonic (70/77/70)
      not "steady degradation"; replan-count claim scoped to FATS only (8.7 vs 7.6; holding mbs05 actually
      replans FEWER, so the "rises on holding" claim was dropped). Mechanism paragraph unchanged.
  [x] sec:disc-tampura (CENTRAL): opening "order of magnitude cheaper (13.7 vs 166) but less reliable (42 vs 55)"
      -> "rough parity (144.4 vs 166) and somewhat more reliable (65.6 vs 55)"; closing "cheaper to run ... though
      less reliably" -> "comparable cost, simpler to model, somewhat more reliably". Architecture/framing paras
      kept verbatim (data-independent).
  [x] conclusion.tex: "solves cluttered scenes the uniform baseline effectively cannot" -> "solves cluttered
      FATS scenes far more often than uniform" (75.6 vs 34.4); "order of magnitude cheaper ... though less
      reliably" -> "comparable end-to-end cost and somewhat more reliably". "Order of magnitude fewer cells" kept.
  [x] abstract.tex: "(39.8% vs 1.3%)" + "scenes that the uniform baseline effectively cannot" -> "(75.6% vs
      34.4%)" + "scenes far more often than the uniform baseline". "Order of magnitude fewer cells" + "cuts
      per-call planning time" kept. introduction.tex verified clean (no hero numbers).
  VERIFICATION 2026-06-04: latexmk main.tex builds CLEAN (68 pp, exit 0, no new undefined refs). Rendered PDF
      (pdftotext) confirms every refreshed value (tab:headline 75.6/34.4/692.11/924.13/...; tampura 144.4 /
      median 21.6 / 65.6%; failure-modes "timed out"/"plan failed"; budget 24% timeout / 18% snapshot-null;
      abstract + conclusion synced) and shows NO stale values/jargon (13.7, 28.37, 156.10, "order of magnitude
      cheaper", "effectively cannot", replan_limit, no_summary, physics_mismatch, all_searched -> all absent).
  STATUS: all #282 PROSE + the 2 regenerated figures (solved_vs_time_linear, failure_modes_sem_uni) are DONE
      and verified. ONLY the resolution arms remain PENDING (subsec:resolution + disc-validity "Resolution
      regime" para + fig:boxel_count_vs_resolution), gated on the still-running coarse mbs sweep. #282 stays
      OPEN for that remainder.
  FOUND BEYOND CATALOG (fix each in its own section):
    - [done] results.tex sec:metrics: dropped "without exceeding the per-episode replan limit" from Success def.
    - [done] results.tex sec:metrics: dropped replan_limit + no_summary from the failure-mode list (cannot occur).
    - [done] results.tex (denominators para): 6% -> 18% (144/810 snapshot-null cells).
    - [done] results.tex (planning-budget para): per-call medians refreshed (1.3/3.4/7.0s); "flat past ~200s" dropped; 1800s is per-cell.
    - [done] discussion.tex sec:disc-mbs0: replan-count claim scoped to FATS (holding mbs05 replans fewer).
    - results.tex subsec:failure-modes: cell-count wording RESOLVED in the 2-variant rewrite (kept "6" = 3 goals x 2 variants).

#283  [DONE 2026-06-04] [T2] [THESIS]  fig:boxelization: camera glyph unreadable at print scale (make it look like a camera)
#284  [DONE 2026-06-04] [T3] [ADMIN]  Check whether a printed thesis copy is required (likely paperless now)
#285  [DONE 2026-06-05] [T2] [THESIS]  Background sec:pod: "POD builds on \cite{...}." is a sentence fragment / placeholder
#286  [DONE 2026-06-05] [T3] [POLISH]  Background: rephrase or cut "a distinction that matters because we later compare..."
================================================================================
#287  [PARTIAL 2026-06-05] [T2] [POLISH]  Whole document: remove em-dashes (---), an AI tell-tale
NOTE 2026-06-05: em-dashes removed (per-instance commas/parens/colons/period; lstlisting/code comments left)
from abstract, introduction, background, related-work, methods, conclusion (commits d402a40, ba44225, 81a1ad0,
e95c819, 8f498b9, 510f7a2). REMAINING: results.tex (~16) and discussion.tex (~36), deferred because both are
under active #282 editing -- sweep once #282 has settled to avoid conflicts.
================================================================================
[AUTHOR 2026-06-05] The author wants ALL em-dashes ("---" in LaTeX, the long dash) removed from the prose --
they read as a tell-tale sign of machine-written text. ~97 em-dash occurrences across the 8 chapters
(abstract 1, background 13, related-work 7, methods 13, results 16, discussion 36, conclusion 3,
introduction 8). Fix: replace each "---" with a comma, parentheses, a colon, or a full stop as the sentence
needs; this is NOT a blanket find/replace, since the right substitute varies. LEAVE en-dash ranges
("2--4", page ranges -- those are "--", not "---") and any "---" inside lstlisting/verbatim. Sweep chapter
by chapter and re-read each rewritten sentence. Large but mechanical.
Refs: thesis/chapters/*.tex (all 8). Related: #277 (language sweep), #251 (cross-cutting redundancy/polish).

#288  [DONE 2026-06-06] [T3] [THESIS]  Overhead-camera caption: name the cyan/red Boxels
#289  [DONE 2026-06-06] [T1] [THESIS]  Approach: flag that the implementation approximates the formal POD model
#290  [DONE 2026-06-06] [T2] [THESIS]  Evaluation headline: lead with the success gap, cell-count as mechanism
#291  [DONE 2026-06-06] [T3] [THESIS]  Chapter titles match their labels (Approach->Methods, Evaluation->Results)
#292  [DONE 2026-06-06] [T2] [THESIS]  Abstract: add holding + TAMPURA numbers
#293  [DONE 2026-06-06] [T0] [THESIS]  Correct TAMPURA discounted-return error bar (0.30 -> 0.07)
#294  [DONE 2026-06-06] [T2] [THESIS]  Discussion: stack 54x gap is pure grounding cost (occlusion inactive)
#295  [DONE 2026-06-06] [T3] [THESIS]  Add nayyar2025option page numbers
#296  [INFO 2026-06-06] [THESIS]  Reference-verification report triage (37 refs; 1 hard error, attributions re-checked)
#297  [DONE 2026-06-06] [T2] [THESIS]  semantic+mbs0.05 named before it is defined
#298  [DONE 2026-06-06] [T2] [THESIS]  Methods: §Overview duplicates the chapter intro's three-component list
#299  [DONE 2026-06-06] [T2] [THESIS]  Cite Wumpus World at its mention (geffner2013concise)
================================================================================
RESOLVED (author notes 2026-06-02 -- no new issue):
  - "explain what a classical planner is + examples" -> DONE in #253 (Background 2.1.2).
    MDP half carried forward as #258.
  - results TAMPURA "...rather than re-running it" -> DONE in #246/#247 (now "we re-ran the
    released Find Die environment locally"); the user's note quotes the pre-fix text.
================================================================================

================================================================================
OPEN ISSUES
================================================================================
OPEN:
  Background: #181 (POD vs contingent-planning naming -- reverted; reconsider, don't equate them)
  Results: #199 (task rename), #209 (resolution-floor study + figure)
  Style (very low priority): #210 (drop author names, cite by number; T3/POLISH)
  --- Supervisor review 2026-06-01 (#214-#253; full batch above) -- all OPEN except
      #231/#234/#252 ([INFO], no action). Discuss open Qs with Till Wed 2026-06-03. ---
      Correctness (T0): #222 #223 #226 #246 #247
      Major (T1):       #216 #230 #237 #238 #239 #242 #248  (+#251 redundancy; T2)
      Recurring theme:  #238/#239/#248 -- "simplified POD planning, state its limits
                        (missing deductive axioms)" -- Till raises it 3x (p.22/23/41)
      Bare annotations: #215 #221 #241 (highlight, no comment) #229 (bare "?") -- confirm intent Wed
      Author-planned:   #253 (FastDownward/planning-algorithms background section)
      Follow-ups filed: #254 (define Boxel at first body use; spun off from #214)
  --- Author notes 2026-06-02 (#258-#273; full entries above) -- all OPEN.
      Correctness (T1): #263 (Object-Integrity argument) #266 (shadow-to-boundary) #272 (uniform cost vs n_occ)
      Verify-in-code:   #264 (pose sampling) #266 (shadow code) #269 (static facts)
      Captions/outdated:#265 #267 #270 #271      Adds/clarify: #258 #259 #260 #261 #262 #268      Style: #273
      Resolved (no issue): classical-planner=#253; TAMPURA re-run text=#246/#247
  --- Supervisor review 2026-06-04 (#275-#284; + codebase CODEBASE_AUDIT.txt #115-#116) -- all OPEN. ---
      Correctness (T1): #275 (drop PDDLStream from abstract) #276 (STRIPS-first, derive state model)
                        #278 (KIFs != K-literals; cite Brenner&Nebel 2009) #280 (Critical Regions now dynamic)
                        #281 (stack-degradation cause = sim/control) #282 (refresh all numbers from new sweep)
      Language (T2):    #277 (whole-doc grammar pass) #283 (camera glyph readable in print; code #115)
      Low/admin (T3):   #279 (stray "the" near PDDL) #284 (check printing requirement)
      Cross-filed code: CODEBASE_AUDIT.txt #115 (camera glyph render) #116 (stack-degradation experiment)

DONE: #168, #176, #177, #178, #179, #180, #182, #183, #184, #185, #187, #188, #189, #190, #191, #193, #194, #195, #197, #198, #200, #201, #202, #203, #204, #205, #206, #207, #208, #211, #212, #213, #259, #261, #262, #288, #289, #290, #291, #292, #293, #294, #295, #297, #298, #299. MERGED: #192->#187, #196->#176. REJECTED: #186 (expansion declined), #175 (shadow #102/#103 reconciliation declined; by-depth drop already done), #260 (TAMPURA/Saleem differentiation -- redundant, declined).

Gating: #141-#156, #130 done — eval write-up (Results/Discussion/abstract/conclusion) is in
thesis/, chapters clear of internal paths + hardware clutter, front/back matter in place, nine
sim figures inserted. #125/#140/#121/#127 closed jointly. #126 (forward-voice conversion)
verified+closed (chapters already retrospective). §5 polish (#87-#111) resolved earlier.
