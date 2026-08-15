================================================================================
ARCHIVED 2026-08-15 — thesis submitted and graded (1.3).  Superseded by
PAPER_AUDIT.txt at the repo root (ICAPS 2027 workstreams).  Every issue in this
file carries a resolution marker; the trailing "OPEN ISSUES" summary block is
stale (trust the per-issue headers).  Do not work from this file.
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
#199  [DONE 2026-06-10 (light; commit b31dc06)] [T2] [THESIS]  Rename task terms to reader-facing names (drop code terms)
RESOLVED LIGHT (author choice): full prose rename rejected -- would desync the text from
every figure axis/legend and tab:headline (all render the code names); full rename needs a
plotter label map + regen of ~12 PNGs. Instead: reader-facing gloss at first use in §5.1
(holding = "find: locate a hidden target and pick it up"; find-and-tray-stack = "find and
stack"); code names stay canonical everywhere else. Abstract naming handled in #314.
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
#209  [DONE 2026-06-06] [T2] [THESIS]  Results: resolution-floor sweep -- DONE: subsec:resolution ("Free-Space Resolution") + fig:boxel-resolution already present; reports finer=flat (auto already at/above floor), coarser >=1.5x = -30-40% free-space cells, success unmoved. Number refresh from the new sweep is tracked under #282 (resolution arms pending).
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
#210  [DONE 2026-06-10 (commit ef12466; author un-killed it same day)] [T3] [POLISH]  Related Work: drop author names, cite by number ([4]) --- VERY LOW PRIORITY
RESOLVED: 5 author-name lead-ins in related-work.tex (Saleem, Ma, Zhao, Bai, Kaelbling/
Hadfield-Menell) -> bare numeric \cite as sentence subject, verbs to singular; system-name
subjects (TAMPURA, CLG, SS-Replan, IBSP, K-replanner, LW1) kept as names.
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
#258  [DONE 2026-06-06] [T2] [THESIS]  Background: explain what an MDP is, with examples -- added MDP definition (states/actions/stochastic transitions/reward; policy; Markov property) + grid-slip example + POMDP extension, in sec:pod "Probabilistic vs. Deterministic" subsec; no new cites (geffner2013/kaelbling1998 reused), no em-dashes.
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
#264  [DONE 2026-06-06] [T2] [THESIS]  Pose sampling vs (partial) occlusion -- VERIFIED IN CODE: oracle_detect_objects (boxel_env.py:1625) already marks an object visible iff ANY of 8 AABB corners is seen, i.e. hidden iff all 8 occluded (= the proposed criterion; nothing to relax). _hidden_xy_positions (boxel_env.py:1020) samples targets fully hidden (all 8 shrunk corners occluded), so partial occlusion never arises in eval. Added one clarifying sentence to methods.tex (Sensing Action); no code change.
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
#269  [DONE 2026-06-10 -- VERIFIED, no edit] [T2] [THESIS]  Methods: verify Boxel set is supplied to the planner as static facts in initial state
================================================================================
[AUTHOR] methods.tex:38 claims "the completed set of Boxels is supplied to the planner as static facts in
its initial state." Walk the code and confirm (static facts; initial state) before keeping the claim.
Refs: methods.tex:38; initial-state construction code.
RESULT 2026-06-10: confirmed. pddlstream_planner._build_init (:392-) iterates registry.boxels and
emits ('Boxel', id) + is_shadow/is_object/is_free_space into the init fact list for every cell; no
action effect modifies the Boxel membership facts (only is_free_space flips on place, which the
sentence does not contradict); the set is rebuilt + re-supplied before each plan() call, matching
§4.4 "Boxels enter each solve as fixed inputs". Claim stands as written.

================================================================================
#270  [DONE 2026-06-06] [T2] [THESIS]  Results: Figure 5.3 overhead-camera caption -- DONE: caption already rewritten (by #288); names cyan/red/grey Boxels, RGB+depth corner insets, oblique viewpoint, oracle detector. Nothing outdated remains.
================================================================================
[AUTHOR] results.tex:79 (fig:overhead-camera, Figure 5.3) caption is outdated. Identify what changed and
update it.
Refs: results.tex:79 (fig:overhead-camera).

================================================================================
#271  [DONE 2026-06-06] [T2] [THESIS]  Results: exit-reason / failure-mode list -- DONE: already updated (by #282) to the 2 plain categories (timed out / plan failed) in sec:metrics + subsec:failure-modes; old planner_failed/replan_limit/no_summary/physics_mismatch/all_searched/drop_failed all removed.
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
#282  [DONE 2026-06-10 (resolution remainder: commits 862ba10 figures, 3968114 results, 76c9676 discussion)] [T1] [THESIS]  Results/Discussion: refresh ALL numbers + conclusions from the NEW sweep
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

RESOLVED 2026-06-10 (deadline day; sweep still running): numbers frozen from the partial aggregate
aggregated_partial_2026-06-10_1854rows.csv (1854/2160 cells). ALL arms complete (90- or 180/90-cell)
EXCEPT the fine floors mbs0.001/0.01 at 117/270 each (randpairs occ2 complete 30+30, occ3 at 29+28;
occ4 + stack fine cells absent) -- thesis text scopes the fine arms to n_occ in {2,3} with n stated.
Headline 810 cells verified IDENTICAL to tab:headline (all 9 success rates + 9 plan times to the
hundredth; --skip-existing preserved them). Old thesis PNGs backed up in backups/thesis_graphics_
2026-06-10/; 7 of 9 regenerated headline PNGs byte-identical to committed versions.
  ADDENDUM [2026-06-10 honesty sweep] -- specifics the resolution refresh MUST catch (all measured
  from sweep_full_2026-05-28 vs current text):
  (a) [FIXED 2026-06-10, commit 3c46613] §5.5 "on the same 100-seed scenes" is stale: reworded to
      "the coarser arms were run as a separate sweep with 100 seeds per difficulty level". The NEW
      resolution arms are 48-49 cells each (holding 49+49, f-a-t-s 48+48 at mbs 0.135/0.18) and
      INCOMPLETE vs 90-cell headline arms -- items (b)-(e) below stay gated on a re-run.
  (b) [FIXED 2026-06-10, commits 3968114 + 76c9676] Stack resolution arms (mbs 0.09/0.12, 90
      cells each) COMPLETED in the canonical sweep -- old geometry-derived "(stack 28->22)"
      replaced with MEASURED: all five adaptive stack settings (auto 6cm; floors 5/9/10/12cm)
      succeed on the IDENTICAL 58/90 (height,seed) set; 9cm floor reproduces the auto partition
      outright (free 17.6); 10/12cm shrink free-space -32% (17.6->11.9), outcome unchanged.
  (c) [FIXED 2026-06-10, commits 3968114 + 76c9676] Re-derived from the COMPLETE 90-cell coarse
      arms (the 18.7s/26.3s figures were the n=48-49 partial): holding success-only time
      134.3 -> 33.6/36.7/47.1 s (0.1/0.135/0.18); f-a-t-s MIXED 77.3/131.5/79.1 vs 124.6 s.
      Free-space fall auto->coarse: holding 24.0 -> 10.1-10.5 (-55-58%), f-a-t-s 25.9 ->
      11.3-11.7 (-55-56%), FLAT from 10 to 18cm; totals -40-46%. Text states ~55%.
  (d) [FIXED 2026-06-10, commits 3968114 + 76c9676] Complete-arm success (n=90): holding coarse
      60.0/64.4/72.2 vs auto 65.6 (within seed noise, non-monotone); f-a-t-s 73.3/62.2/66.7 vs
      75.6 (10cm arm within 2pp; up to ~13pp non-monotone dip at 0.135). Stated as measured,
      no "within noise" overclaim on f-a-t-s. ALSO NEW (beyond the addendum): fine arms
      measured -- 1cm floor = ~3x free-space at unchanged success (66.1 vs 60.0 holding,
      69.0 vs 70.0 f-a-t-s, matched occ2-3 scenes); 1mm floor = every episode (58-59/goal)
      hits the 1800s wall (feasibility cost, reported honestly; implementation limit 6b00cd7).
  (e) [FIXED 2026-06-10, commit 862ba10] boxel_count_vs_resolution.png regenerated from the
      single canonical sweep: 6 arms (1/5/9.2 auto/10/13.5/18 cm), 1mm arm absent (no
      partitions -- all timeouts), caption discloses the 1cm bars' occ2-3 scope.

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
      and verified. RESOLUTION REMAINDER DONE 2026-06-10 (see RESOLVED note + ADDENDUM (b)-(e) above;
      commits 862ba10 / 3968114 / 76c9676; main.pdf rebuilt clean, 74pp, 0 undefined refs; rendered PDF
      spot-checked for the new resolution numbers). #282 fully CLOSED.
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
#287  [DONE 2026-06-10 (commits 2158b80 results, 0ed0ce0 discussion, 856e5b0 background)] [T2] [POLISH]  Whole document: remove em-dashes (---), an AI tell-tale
NOTE 2026-06-05: em-dashes removed (per-instance commas/parens/colons/period; lstlisting/code comments left)
from abstract, introduction, background, related-work, methods, conclusion (commits d402a40, ba44225, 81a1ad0,
e95c819, 8f498b9, 510f7a2). REMAINING: results.tex (~16) and discussion.tex (~36), deferred because both are
under active #282 editing -- sweep once #282 has settled to avoid conflicts.
COMPLETED 2026-06-10: results.tex (21 sites) + discussion.tex (26 sites) swept; background.tex had 10
reintroduced by the post-06-05 Fast Downward section (#253/#321), also swept. Verified 0 prose em-dashes
across all 8 chapters; the 8 remaining matches are PDDL-lstlisting comment separators (exempt by spec).
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
SUPERVISOR REVIEW 2026-06-09  (#300-#334)  -- Daniel Swoboda EMAIL + Till Hofmann /
Daniel handwritten annotations (most on the OLD PDF, some on the new). ALL OPEN.
================================================================================
Two inputs, one review: (a) Daniel's email -- higher level, "most is there but from my
perspective there's still some major things to work on"; (b) page-by-page handwritten
annotations transcribed by the author. Overlapping items are MERGED here with page refs.
[AUTHOR Q] = a question the author explicitly asked Claude to answer before that edit is
made (answer pending; do not edit until resolved). Recurring themes (naming, number/CPU
inconsistencies, missing integration/engineering detail, Know-If-literal honesty, §5/§6
structure) are filed ONCE as cross-cutting issues #300-#313; remaining page-local edits
follow as #314-#334.
HEADLINE (email): the symbolic layer is over-represented; integration / perception /
engineering is under-represented. "If you address these things, we're in a good shape."

APPLIED 2026-06-09 (batch mode; main; one commit per group):
  [x] #317 + #288 camera: "overhead camera" -> "fixed camera" across intro/methods/results/
      discussion/conclusion; true geometry (front-oblique, eye(0.1,-0.8,0.7)->target(0.1,0,0.5),
      pitch ~-14 deg, boxel_env.py:38-39,453) stated once in results perception para; dropped
      "observes the whole table at once". Commit 6f90819. DONE.
  [x] #321 (part): dropped unused "numeric fluents"; "is what lets FD scale"->"helps FD handle";
      conditional-effects KEEP confirmed. Commit 0431e5c. REMAINING: FD->PDDLStream forward-ref (minor).
  [x] #322 (part): KIF know-whether now cites Petrick&Bacchus PKS [petrick2002planning]+Brenner&Nebel;
      either/or already correct (no edit). Commit 0431e5c. DONE.
  [x] #323: streams introduce objects (existence/identity) not just params; IK multi-valued ->
      generator yields a sequence. [AUTHOR Q] answered. Commit 0431e5c. DONE.
  [x] #324 (part): "deep network"->"learned model"; rephrased "to make planning more efficient".
      Commit 0431e5c. REMAINING: L98 "often reduces" (KEEP qualifier, do NOT remove), cut-last-two
      (ambiguous/old-PDF), voxel "not in symbolic planning" qualifier.
  [x] #316 (part): em-dash appositive merged; "full observability of the world state". Commit 6f90819.
      REMAINING: backward-reasoning restructure; dense L26 (camera done, naming/beliefs/target-found
      pending); L5 citation verify.
  BLOCKED on author: #311 (supervisor names+titles), #312 (registered title confirm).
  GATED on framing #334: framing-dependent intro/overview rewrites (#300/#303/#318).

APPLIED 2026-06-09 (cont.):
  [x] #307 + #327 + #329 methods §4.4/§4.5: contingent-plan / CLG-LW1 guarantee stated; explicit
      "does NOT certify b_g subset S_G"; Daniel's optimistic-determinisation qualifier; "tractable"
      softened; removed false bounded-convergence claim + added "relocated objects emit no new
      shadows". Commit e562e52.
  [x] #311 + #312 front matter: Supervised-by -> Till Hofmann, Daniel Swoboda; title kept as
      registered (author-confirmed). Commit 0ad40c8.
  [x] #310 naming sweep: "Semantic Boxel"->"Boxel", "Semantic POD-TAMP"->"POD-TAMP" across 9 files +
      glossary. Registered title + descriptive "semantic discretization" + domain.pddl kept. Framing B
      author-confirmed. Commit 0ad40c8.
  [x] #308 (PART): metrics para reconciled (planning 134.30 vs end-to-end 144.4 = DIFFERENT metrics,
      ~10s execution NOT negligible -> false "negligible" claim dropped); §6.3 CPU contradiction fixed
      (local re-run same-machine; 2.5-vs-2.0 GHz scoped to TAMPURA PUBLISHED only). Commit 1e86112.
      HW ground truth: TAMPURA Xeon Gold 6248 @2.5GHz (paper); ours 8-core ~2.0GHz; local re-run on ours.
  [x] #308(a) RESOLVED (commit 432d91c): the NEW sweep_full_2026-05-28 has ONLY {semantic, mbs0.05,
      uniform} -- NO coarse resolution arms (mbs0.135/0.18 live only in OLD sweep_anytime/resolution).
      A literal coarse-arm refresh is impossible without re-running (won't finish by deadline). Applied:
      anchored §5.4.5 at/below-auto success to the headline 30-seed numbers (65.6/75.6/64.4), kept the
      geometry-derived compactness counts (35->20 etc., regime-independent), stated the coarsening
      insensitivity qualitatively. Removes the 42.3-vs-65.6 clash. RESIDUAL (flagged, not blocking):
      §5.4.5 still describes a 100-seed resolution sweep alongside the 30-seed headline. OPTIONAL:
      re-run resolution arms under the new (cap-removed) regime for true coarse-arm numbers (#282/#209).
  REMAINING BIG (need authoring/data; not started): #300 Boxel pseudocode, #301 stream impls, #302
  sense-plan-act loop pseudocode, #303 §4.1 flowchart/overview, #304 manipulation model up front, #305
  scene generation, #306 TAMPURA-indirect pass, #309 §5/§6 reorg, #314 abstract, #316 intro restructure,
  #318 contributions, #331 anytime rewrite, #333 threats wording, #326 belief->KIF wording.

UPDATE 2026-06-09 (review r2): #300 ALREADY DONE -- the Boxel pseudocode exists as
alg:discretization (methods.tex L31-57: object bounding -> occlusion subdivision -> octree ->
convex merge; faithful to free_space.py / cell_merger.py). It is the ONLY algorithm float in the
thesis; a fresh draft would have duplicated it. Daniel's "add a pseudocode algorithm" was on the
OLD PDF that predated it. Re-scoped GENUINE integration gaps: #302 (outer sense-plan-act loop has
NO pseudocode -- real gap; §4.5 prose only), #304 (manipulation model only in §6.5), #305 (scene-
generation approach thin in §5.1 -- verify), #303 (no main-loop flowchart; motion planner +
perception model not named in the chapter intro).
#302 DONE 2026-06-09 (commit 4f3aa25): added §4.6 "The Sense-Plan-Act Loop" + Algorithm 2
(alg:sense-plan-act), faithful to test_full_pipeline.py L912-1279 / reboxelize.py / execution.py
handle_sense_action. Build green 72pp. Remaining integration: #303 (flowchart/motion+perception),
#304 (manipulation model up front), #305 (scene-gen approach).
FAILURE-MODE BREAKDOWN DONE 2026-06-09 (commits 061bec0 plotter + be5150a thesis): once §4.6 + §5.2
name specific give-up reasons, the failure-mode graph was re-expanded (reversing the #282 fold).
eval_plotter.group_failure_modes gained fold=False (default True keeps the 3-variant pipeline);
regen_failure_modes_sem_uni.py now also emits failure_modes_sem_uni_detailed.png (plain labels: timed
out / no plan found / searched all regions / execution mismatch; manipulation-give-up = 0 cells in
sem/uni so absent). §5.2 metric def + §5.4 text/caption rewritten; fig:failure-modes -> detailed PNG;
old simplified PNG kept regenerable (read visually before commit). Build 73pp. CODEBASE: plotter fold
param at eval_plotter.py group_failure_modes.
#304 DONE 2026-06-09 (commit 8ba4541): manipulation model introduced up front (methods §4.5
paragraph: top-down fixed-offset grasp, rigid constraint attach, place/stack settle-under-gravity +
planner-invisible lift, physics-checked success so false successes count as failures). §6.5 full
simplifications kept (overlap to be trimmed under #309). Also relabeled physics_mismatch ->
"false success" in the failure graph (caught fake successes; commit 59627d8).
#305 DONE 2026-06-10 (commit 7a3a6be): §5.1 "Scene generation" paragraph (seed-deterministic
occluder+target placement, targets hidden behind occluders along sightlines, post-spawn raycast
verify + seed re-roll; stack visible-only). Faithful to boxel_env.random_pairs_scene/scalability_scene.
#303 DONE 2026-06-10 (commit 1344890): chapter intro now names motion planner (RRT) + IK + grasps +
perception (raycast/oracle) + the sense-plan-act loop; "abstract belief reasoning" -> "discrete belief
over workspace regions"; "symbolic facts" -> "Know-If fluents"; POD TAMP -> POD-TAMP. Flowchart skipped
(alg:sense-plan-act covers the loop).
=== INTEGRATION BATCH (Daniel email majors) COMPLETE: #300 #302 #303 #304 #305 #306 #307 #308 #310 #311 #312. ===
Remaining supervisor batch = line-edits (#314 abstract opener, #316 intro restructure, #318, #319, #325,
#326, #330, #331, #333) + #309 (§5/§6 structural reorg) + #313 (epigraph website variant). #334 framing = B (done).

--- CROSS-CUTTING / MAJOR (email + heaviest annotations) ---

#300  [DONE 2026-06-10 -- VERIFIED resolved by prior work, no edit] [T1] [THESIS]  Boxel algorithm never defined -- add PSEUDOCODE, put it FRONTWARDS
RESOLVED: methods 4.1 opens with the Boxel definition and carries Algorithm 1 "Adaptive
Semantic Discretization" (object bounding -> occlusion subdivision -> octree free-space
partition -> convex merge); background 2.4 builds voxels -> octrees -> CRs as the lead-in.
[EMAIL] "The Boxel algorithm is never properly defined -- this is YOUR key contribution.
Put it frontwards. A competent reader cannot reimplement the core method from Chapter 4
as written. Add a pseudocode algorithm." Also p.16 "FOCUS ON THIS!" (core-contribution
para) + "still not introduced properly" (the old Overview section carried the Boxel
definition; it was lost in the rewrite -- fold it back into the chapter-opening
description, do NOT reinstate the Overview section) + §4.2 "Start with voxels/octrees,
build up the evolution that led to Boxels; also consider shortening the name."
Fix: a named, numbered pseudocode for Boxel generation (object/occlusion Boxels via
raycast + recursive free-space partition + convex merge), introduced early, building from
voxels->octrees->Boxels. Cross-ref #254 (define Boxel at first body use).
Refs: methods.tex §4.1/§4.2; #254. EMAIL bullet 1.

#301  [DONE 2026-06-10 (commit e00b61c)] [T1] [THESIS]  Stream implementations are black boxes -- document them (appendix or up front)
RESOLVED: new methods §"Stream Implementations" (subsec:stream-impls) between the sensing
subsection and the manipulation-model paragraph; documents sample-grasp (single top-down,
0.10 m clearance, seeded contact IK), compute-kin (multi-seed null-space IK, lazy collision
deferral to plan-motion), compute-stack-kin (support-top release height), plan-motion
(endpoint checks -> direct linear -> RRT-Connect 2000 it / 0.2 rad / 5% goal bias / 8 edge
checks + 75-attempt shortcutting). All constants verified against streams.py. New bib entry
kuffner2000rrt. The existing #304 manipulation-model paragraph closes the subsection
(answers "how are grasps executed").
[EMAIL] "Stream implementations are black boxes. At least describe them in the appendix,
better up front. You could write 30 more pages before hitting the limit. How is plan-
motion done? compute-kin? How are grasps executed?" Also p.16 "What about motion
primitives? Motion planner used? Perception model?"; p.7 stream-description correctness
(#323). Fix: a stream/implementation section (appendix at minimum) covering the motion
planner, compute-kin (planning IK), grasp execution, and the perception/detection model.
Refs: methods.tex; appendix.tex. EMAIL bullet 2; annotation p.16.

#302  [DONE 2026-06-09 (commit 4f3aa25), see note above] [T1] [THESIS]  Outer sense-plan-act loop never introduced -- pseudocode for belief update + replan trigger
[EMAIL] "How does the outer sense-plan-act loop work? Never properly introduced.
Pseudocode for belief update and replan triggering? Boxelisation when? Pseudocode would
help here." Fix: an explicit main-loop description + pseudocode -- when boxelisation runs,
how the KIF belief updates on an observation, what triggers a replan. Pairs with #303
(flowchart) and #307 (honest framing of what the loop actually guarantees).
Refs: methods.tex §4.1/§4.5. EMAIL bullet 5.

#303  [DONE 2026-06-10 (commit 1344890), see note above] [T1] [THESIS]  §4.1 Overview is disconnected -- add high-level idea + main-loop flowchart + integration
p.16 (heaviest page): "this whole section is lacking. All feels very disconnected. No
proper introduction of the high-level idea, algorithms, integration, flow-chart of the
main loop. All very under-represented." + "What about motion primitives / motion planner /
perception model?" Umbrella for the structural rewrite of §4.1; the pseudocode pieces live
in #300/#301/#302, this issue owns the high-level intro + flowchart + naming the motion
planner & perception model in the overview. Note p.16 "Arguably the framework as-is is
your contribution" -- reframe "integrate these into a POD-TAMP framework through ...".
Refs: methods.tex §4.1. Annotation p.16.

#304  [DONE 2026-06-09 (commit 8ba4541), see note above] [T1] [THESIS]  Introduce the simplified manipulation model UP FRONT (not first in §6.5)
[EMAIL] "What's the manipulation model? You name some in 6.5... that's way too late."
Also p.31 "This is key!" + "It reads as if the planner is limited, but it's the execution.
That's why it's important to properly introduce the simplified manipulation model" (readers
misblame the planner for the stack-height decline). Fix: introduce the manipulation model
in the setup (§5 / §4), and at the stack-success paragraph attribute the h=4 decline to
manipulation/execution, not planning. Cross-ref #281 (same cause). NB p.31 "Your numbers
could be better" is NOT an action item (see #332).
Refs: methods.tex; results.tex stack-success; discussion.tex §6.5; #281. EMAIL bullet 6.

#305  [DONE 2026-06-10 (commit 7a3a6be), see note above] [T1] [THESIS]  Scene generation never described -- add the approach (pseudocode/diagram)
[EMAIL] "How are scenes generated, what's the approach here? Pseudocode? Diagram?" Also
p.32 "tasks and environments are not introduced at all" + p.25 reorder (#309). Fix: a
setup subsection describing how scenes/seeds are generated (seed-generic; reuses TAMPURA's
20 seeds for find_dice), with a diagram or short pseudocode.
Refs: results.tex §5 setup. EMAIL bullet 4; annotations p.25/p.32.

#306  [DONE 2026-06-10 (commits 9ad3d20, 0a4d56e)] [T1] [THESIS]  TAMPURA comparison is INDIRECT -- say so from the start; don't push our numbers favorably
RESOLVED: abstract quotes the published-implied >=63% (not the local 55%); 6.4.8 flags the
local re-run as possibly under-representing TAMPURA; every 55% mention now paired with the
published figure; 'favours us'/'somewhat more reliable' -> 'comparable reliability'
throughout. DISCOUNTED-RETURN sub-item: 0.63+-0.07 verified against arXiv 2403.10454
Table I -- the supervisor's 0.30 annotation was mistaken; #293 stands, no regression.
[EMAIL] "The comparison to TAMPURA is indirect -- make that VERY clear from the get-go and
whenever you compare these numbers." Also p.35: "the local re-run may UNDER-represent
TAMPURA" (running it on our machine disadvantages it); "It seems like you're pushing your
numbers" (used local 55% vs their reported 63%); "in 6 you report diff. CPU numbers"
(simulated execution + replanning on the same CPU). Fix: state the comparison is indirect
wherever numbers are compared; report TAMPURA's published figure alongside our local re-run
and flag the local run may disadvantage them; reconcile the CPU framing with #308.
  - DISCOUNTED RETURN (p.35, possible REGRESSION): supervisor "In the paper it's 0.63 +/-
    0.30." But #293 is marked [DONE] having changed that error bar 0.30 -> 0.07. These
    contradict -- either #293 changed a CORRECT 0.30 to a wrong 0.07, or the annotation
    predates the fix. VERIFY against the TAMPURA paper; if 0.30 is right, reopen/revert #293.
Refs: results.tex §5.4.5/§5.4.6; discussion.tex; fig:tampura; #293. EMAIL bullet 7;
annotations p.34/p.35/p.39.

#307  [DONE 2026-06-10 (commit e838398; bulk via prior passes)] [T1] [THESIS]  Own the Know-If literals upfront + DROP-IN §4.4 POD-model replacement (Daniel's text)
RESOLVED: 4.3 already carried Daniel's drop-in in substance (contingent-solver guarantee,
optimistic determinisation, 'does NOT certify b_g subset S_G'); e838398 adds the missing
S0 (|S0|>1, sensing shrinks belief) and SG (belief-containment) details and the upfront
ownership sentence in 4.2 (KIFs are bookkeeping; sensing+replanning do the work).
[EMAIL] "Be honest about the Know-If literals: they are helpers to make things more
readable; the sensing actions and re-planning do the actual hard work. That was agreed
between us and is fine, nothing is broken, but it needs to be owned upfront." This is the
recurring honesty theme across: p.1/p.3 "POD planner reasons over ... (not true / weaker
version)"; p.2 "which you don't fully do"; p.16 "you don't reason over 'abstract beliefs'"
(we use KIFs); p.19 "belief doesn't, KIF does" (replace "belief"->KIF in "the belief
tracks whether..."/"the belief records one know..."); p.20 "optimistically -- maybe / the
algorithm doesn't provide this certainty" ("goal states reached with certainty"); p.21
sensor-model S: a full POD model is CONTINGENT over outcomes, our implementation is
OPTIMISTIC sensing + replanning. Fix: state upfront that KIFs are readability helpers and
that sensing+replanning do the work; we do NOT certify b_g subset S_G. Use Daniel's
verbatim drop-in for §4.4 below; pairs with #289 (already flags the approximation) and #329
(remove the convergence claim).
DANIEL'S DROP-IN for §4.4 (verbatim from email; adapts Geffner & Bonet [13] -- not the
current "[21]"; cite [13] -- see #321):
  We formalize the problem our system addresses as a partially observable deterministic
  (POD) state model, adapting the state-space formulation of Geffner and Bonet [13] to the
  POD setting. The model defines the planning task; Section 4.5 then describes the
  optimistic, replanning-based procedure with which our system approximately solves it.
  The model is a tuple  M = <S, S0, S_G, A, f, O>  where:
    S (States): a finite set of states. Each state is a consistent assignment of truth
      values to the atomic propositions AP grounded in the Boxel representation, e.g. the
      fact InBoxel(obj_k, Boxel_j) together with the Know-If fluent recording whether its
      value is known.
    S0 (Initial belief): a set S0 subset S of states consistent with the agent's initial
      knowledge. Because the target's Boxel is unknown, |S0| > 1; the belief is this set of
      candidate world states, and sensing shrinks it.
    S_G (Goal states): the set of states satisfying the goal formula over AP (e.g.
      K(holding(target_obj))). The task is solved only once the belief is contained in S_G
      -- i.e. the goal holds in every world still consistent with what the agent observed.
    A (Actions): abstract action schemas operating on the state, realized as PDDLStream
      actions such as sense and pick.
    f (Transition function): the deterministic successor s' = f(a, s) applying an action's
      add/delete effects.
    O (Sensor model): the relation between a sensing action and its observation (target
      found in a Boxel, or not) and the induced belief update -- which states O prunes.
  A sound POD solver for M returns a contingent plan that branches on observations, driving
  the belief from S0 into S_G along every branch, reaching the goal with certainty for
  every world consistent with S0. This is the guarantee of knowledge-literal POD planners
  such as CLG and LW1 [1, 5]. We write the POD problem as: find a policy mapping belief S0
  to a goal belief b_g subset S_G.
  We solve a SINGLE OPTIMISTIC DETERMINIZATION of M: the sense action assumes its target is
  found, reducing the problem to one branch. The classical planner solves it, the plan is
  executed, and the true observation (supplied by O, a Python callable) triggers a replan
  whenever it contradicts the optimistic assumption. The system therefore does NOT certify
  b_g subset S_G over all states in the belief.
Refs: methods.tex §4.4/§4.5; introduction.tex p.1/p.3; #289 #329 #321. EMAIL para "Know-If".

#308  [DONE 2026-06-10 -- VERIFIED resolved by prior work, no edit] [T0] [THESIS]  §5/§6 number + CPU inconsistencies (the TRUE threats to validity)
RESOLVED, all four sub-items verified against current text: (a) metrics paragraph
reconciles 134.30s planning vs 144.4s end-to-end (execution adds ~10s); (b) resolution
section carries new-sweep numbers (66.1/69.0% etc., not 42.3/40.3/45.7); (c) overhead no
longer called negligible, quantified instead; (d) one CPU story (per-episode pair same
machine; Xeon-vs-Ryzen named only for the published per-step figure, flagged as favouring
TAMPURA).
[EMAIL] "Several inconsistencies in Section 5 and 6 (among each other and with cited
papers): CPU claims, reported metrics for supposedly the same approaches with different
numbers. These are the true threats to validity -- rectify them." Concrete catches:
  (a) p.29 MAJOR: holding+semantic mean plan time = 134.30s in Table 5.1 but 144s in
      §5.4.6. AUTHOR read: the table is current (new run), the 144s is from the OLD run
      (so just sync §5.4.6 to 134.30) -- OR it is the execution-time delta (p.27); execution
      is >=~10s, so CHECK THE CALCULATION before syncing.
  (b) p.34 RED FLAG: §5.4.5 holding 42.3 / 40.3 / 45.7% (the "1x" arm) vs the earlier
      semantic holding 65.6% in Table 5.1. AUTHOR: "we forgot to update the numbers from
      the new sweep" -- §5.4.5 still holds OLD numbers. Sync to the new sweep.
  (c) p.27: "execution, perception, and motion overhead are negligible" / "wall-clock ~=
      planning time" -- Daniel: "How does execution time play into this? You have some
      number inconsistencies later -- this might be the source." Re-examine; this framing is
      likely the root of (a).
  (d) p.39/p.35 CPU contradiction: §6.3 "TAMPURA's CPU has a marginally higher base clock
      (2.5 vs 2.0 GHz)" -- Daniel "same or not? contradiction"; §6 reports different CPU
      numbers than §5 ("including simulated execution and replanning on the same CPU").
      Reconcile to ONE consistent CPU story; cross-ref #306.
All are stale-text/framing SYNC (not pipeline re-runs); verify each value against
sweep_full_2026-05-28 before editing. Cross-ref #282 (new-sweep refresh).
Refs: results.tex §5.4.5/§5.4.6 + planning-budget para; discussion.tex §6.3/§6.4; #282 #306.

#309  [DONE 2026-06-10 (commit ca86685)] [T1] [THESIS]  Structural reorg of §5 and §6 (setup before goals; collapse §6 redundancy)
RESOLVED: (p.25) §5.1 reordered sim/robot -> Perception(+camera fig) -> Goals -> scene gen ->
seeds -> budget (block move, no text changes). (p.40) §6.4+§6.5 merged into one section
"Limitations and Threats to Validity" (labels sec:disc-validity AND sec:limitations both kept):
Oracle-perception threat folded into the Perception paragraph, Bounded-give-up threat deleted
(fully duplicated in the Planning paragraph), Shadow-under-coverage folded into Spatial
representation; Scene-family / TAMPURA-different-task / Resolution-regime kept. (p.37) §5/§6
chapter split KEPT per the #244 author decision; the merge removes the flagged redundancy.
Three structural notes:
  - p.25 (MAJOR): "First explain the setup and environment properly, THEN talk about
    goals." The Goals subsection currently precedes a proper setup/env description -- reorder.
  - p.37 (Discussion general): "the discussion section doesn't add much. It covers things
    out of evaluation, forcing readers back and forth. Either collapse it, or move results
    from 5 to 6 -- 5 then only setup." Decide: keep §5=results / §6=discussion but stop the
    cross-section ping-pong, OR consolidate.
  - p.40: "§6.5 and §6.4 are mostly duplicates -- collapse them." Threats to Validity (§6.4)
    and Limitations & Accepted Simplifications (§6.5) overlap heavily (perception oracle,
    bounded give-up, resolution regime appear in both).
Refs: results.tex §5; discussion.tex §6.4/§6.5. Annotations p.25/p.37/p.40.

#310  [DONE 2026-06-10 -- VERIFIED resolved by prior work, no edit] [T2] [THESIS]  Document-wide: DROP "Semantic" -> "Boxels" / "POD-TAMP"
RESOLVED: grep over all chapters finds no "Semantic Boxel" / "Semantic POD" compounds.
The title keeps "Semantic Space Abstractions" (registered title, #312); "Adaptive Semantic
Discretization" (algorithm name) and the "semantic" eval-variant name (#330) are distinct
terms, not the flagged compounds.
RECURS p.3 ("keep using 'semantic' here -- why? Implies it's an extension of a previous
concept. Why not just boxels?"), again p.3 ("also semantic pod tamp"), p.20 ("why
'Semantic'? -- suggestion in my email"), abstract, methods. Daniel's §4.4 drop-in (#307)
already uses bare "Boxel"/"POD". Fix: remove "Semantic" from "Semantic Boxel" and
"Semantic POD-TAMP" throughout -> "Boxel(s)" / "POD-TAMP". Cross-ref #214 (Semantic Boxel
used before defined). Document-wide find + per-instance read.
Refs: all chapters; #214. Annotations p.3/p.20 + email.

#311  [DONE 2026-06-10 -- VERIFIED resolved by prior work, no edit] [T0] [ADMIN]  Supervisor names missing -- add Till Hofmann and Daniel Swoboda
RESOLVED: main.tex defines \supervisor{Till Hofmann, Daniel Swoboda} and
resources/title-page.tex:45 renders it.
p.40 + EMAIL closing. The supervisors' names are absent from the title page / front matter.
Add: Till Hofmann, Daniel Swoboda. MUST-FIX.
Refs: thesis/ title page / front matter.

#312  [DONE 2026-06-10 -- author confirmed] [T0] [ADMIN]  Title must MATCH the registered title exactly
RESOLVED: author confirmed the main.tex title "Semantic Space Abstractions for Partially
Observable Deterministic Task and Motion Planning" matches the registered title.
[EMAIL] "Make sure the title matches what we registered -- I'm pretty sure it needs to be
exactly the same as on the registration form. A title change can be requested with the
examination board ahead of time, but don't count on getting it done before Wednesday
night; double check." Action: confirm the registered title and reconcile main.tex; if a
change is wanted, request it with the board but assume the registered title for submission.
Refs: thesis/ title page.

#313  [DONE 2026-06-10 (commits 70c3b1b, 3c9f269)] [T3] [ADMIN]  Epigraph -- keep Trump quote in submission, make a chair-website variant WITHOUT it
RESOLVED (superseded by author decision 2026-06-10): epigraph REMOVED from the build entirely
("kill trump quote completely") -- include dropped from main.tex, websiteversion toggle
removed, no website variant needed. chapters/epigraph.tex stays on disk, just not built;
say the word to delete the file too. One PDF for both submission and chair website.
Front matter: epigraph "Everything is Computer -- DJT". Supervisor: "the chair doesn't want
to publish Trump quotes -- I'd ask for a version without this for our chair website, but
fine for submission if you want. Hector & Morris will see it..." Action: author may keep it
in the SUBMITTED version (their call); produce a second build/variant with the epigraph
removed for the chair website.
Refs: thesis/ front matter (epigraph page).

--- PAGE-LOCAL EDITS ---

#314  [DONE 2026-06-10 (commit 20eac0a)] [T2] [THESIS]  Abstract (p.iii): ground the problem first; reword 3 unclear spots; reader-facing task names
  - First two sentences "a bit too quick -- usually one grounds the reader in a problem
    first before presenting it": add a one-sentence problem grounding.
  - "hard to follow": "the partition concentrates resolution on the objects and the regions
    they occlude, covering the free space with a few coarse cells" -- reword for clarity.
  - "reads unclear, an artifact from implementation": the term "per-call planning time" --
    rename/clarify.
  - "find-and-tray-stack" / "FATS" (also undefined at p.32): name comes from code, not
    meaningful to a reader -- rename to "find and stack on a tray" (or similar). Cross-ref
    #199 (document-wide task rename).
Refs: abstract.tex; results.tex p.32; #199.

#315  [DONE 2026-06-10 (commit fadb375)] [T0] [THESIS]  Intro p.1: citation [8,11] after "TAMP studies how to do exactly this." is wrong
RESOLVED: garrett2021integrated (the TAMP survey) added as the lead citation; the existing
pddlstream + tampura refs KEPT per author decision (supervisor flagged [8]=TAMPURA as
misplaced, so be ready to defend keeping it).
"[8] is TAMPURA" -- the cite is misplaced/incorrect for that sentence. Verify what [8] and
[11] are and replace with the correct TAMP reference(s).
Refs: introduction.tex p.1; references.bib.

#316  [DONE 2026-06-10 (commit cc27263)] [T2] [THESIS]  Intro p.1: small wording/structure edits cluster
NOTE: the "of what" bullet was already satisfied (text reads "full observability of the world
state") and the em-dash bullet was covered by #287's intro pass; the other five applied.
  - "this is a bit of backward reasoning": the intro argues symbolic-planning-is-insufficient
    by reasoning from the solution backwards -- restructure to argue forward.
  - "of what": "PDDLStream assumes full observability" -- say full observability OF WHAT.
  - "combine the em-dashes with this sentence": the em-dash clause ("...the concrete
    parameters required to execute them -- such as object poses, grasp configurations...")
    -- merge (also #287 em-dash sweep).
  - "facing uncertainty about object locations" -> drop "locations".
  - "assumed to yield the outcome the plan expects" (Daniel "?") -> e.g. "target found".
  - "a framework that makes planning simpler" -- complete the phrase ("simpler to ?").
  - "instead": small wording edit near "This thesis develops a system."
Refs: introduction.tex p.1; #287.

#317  [DONE 2026-06-10 (commit b681f1f; camera wording via prior passes)] [T1] [THESIS]  Intro p.2 (Fig 1.1 + over-claims): camera, POD-before-definition, belief-state claim
RESOLVED: overhead-camera wording already gone (fixed camera, oblique, in front of and
slightly above); b681f1f softens the belief-state claim (discrete belief over regions, not
full probabilistic belief), expands POD at first use in the research question, and replaces
the generic 'space is part of the planning problem' with the specific symbolic-state claim.
  - OVERHEAD CAMERA (also EMAIL bullet 3, factual): "Fixed overhead camera is literally not
    correct -- the camera is not placed overhead." Caption arrow "implies full obs. from
    top" -- a fixed overhead cam implies full observability from above, in tension with the
    partial-obs framing, AND it is not how we do it (the camera is fixed and its view shows
    in the corner panels). Fix the caption + any "overhead" wording document-wide. MUST-FIX
    (recurs in §4 setup). Cross-ref #288 (overhead-camera caption).
  - "first time POD is mentioned": "...into a POD-TAMP framework" -- acronym used before
    §2.2 defines it; expand on first use.
  - "which you don't fully do -- weaker version": the claim about representing/reasoning over
    belief states for continuous spatial uncertainty -- soften (KIFs, not full belief; #307).
  - "sure, but not unique": "space is part of the planning problem" -- true but not unique to
    us; qualify.
  - "most planning in robotics already has some level of spatial representation": "into a
    probabilistic occupancy grid but structure the planner should weigh directly" -- reword.
  - "example fig might already be good here": add an illustrative figure this early.
Refs: introduction.tex p.2; fig:hero/fig:1.1; #288 #307; EMAIL bullet 3.

#318  [DONE 2026-06-10 (commit 9e0e64a)] [T2] [THESIS]  Intro p.3 (Contributions/Outline): trims + soften claim + naming
  - "not true": "partially observable deterministic (POD) planner reasons over ..." -- soften
    per the honesty theme (#307).
  - scratched "of this thesis" -> "Contributions" (not "Contributions of this thesis").
  - scratched "thesis" in the outline sentence.
  - naming (cross-ref #310).
Refs: introduction.tex p.3; #307 #310.

#319  [DONE 2026-06-10 (commit b625ab8)] [T3] [THESIS]  Background intro: "This chapter builds up the pieces the thesis depends on" -- rephrase
Underlined; "maybe doesn't say much". Rephrase or cut.
Refs: background.tex.

#320  [DONE 2026-06-10 -- final alignment after author clarification] [T0] [THESIS]  Background §2.1.1 STRIPS: stop mixing STRIPS syntax with the planning model
RESOLUTION (full, after author clarified Daniel's annotation): Daniel's point is the
syntax/model LAYERING -- the listing shows :precondition/:effect (positive + negated
literals), no add/delete LISTS; the sets and the successor equation are the MODEL. Fixed
per Till's structure: syntax paragraph now says 'positive effects add(a), negative effects
del(a)' (Till's wording, no 'list'), applicability + successor formula live ONLY in the
state-model sentence, post-listing bridge maps effects to add(a)/del(a). Opener uses
Daniel's scratched-phrase suggestion. D=<P,A>, I=<O,s0,g> per Till's excerpt.
p.4: "Bit short -- either drop and integrate with 2.1.1, or extend." Daniel scratched "A
foundational language for this is" and wrote after STRIPS: "is a common language to
express ...". CORE correction: "you are mixing STRIPS syntax and the typical planning model
-- STRIPS has no add/delete list as shown in the PDDL action stack" (the passage from "A
foundational language..." through "...produces the successor state (s\del(a)) U add(a))").
"STRIPS is already standardized and is a SUBSET of PDDL!" -> "PDDL gives this a
standardized, more expressive syntax." AUTHOR (personal): base the model definition on
Till's formulation (the picture of how he defined the model) -- do NOT be creative.
CURRENT TEXT (2026-06-09, post-#276): background.tex L13-27 ALREADY does this -- STRIPS
add/delete-list first (L13), then "PDDL gives this a standardized, more expressive syntax"
(L15 -- the supervisor's exact suggested wording), PDDL effects mapped to add/delete (L25),
and the state model S(P)=<S,s0,SG,Act,A,f> cited to geffner2013concise + hofmann2024learning
(Till's own formulation) at L27. The p.4 annotation was on the OLD PDF. REMAINING: verify only.
Refs: background.tex §2.1.1; the PDDL (stack) listing. Annotation p.4.

#321  [DONE 2026-06-10 (commit af0a7d8; bulk via prior passes)] [T0] [THESIS]  Background §2.1 Fast Downward (p.5): citation + relevance + over-claims cluster
RESOLVED: citation/numeric-fluents/scaling-claim sub-items verified already applied;
af0a7d8 closes the last residual (PDDLStream forward-reference now points at new label
sec:tamp).
  - "[21] does not define this" -- AUTHOR: Till likely means [13] (Garrett et al., Online
    Replanning), but that uses POMDPs; the CORRECT source is Hoffmann & Geffner. VERIFY and
    fix (the §4.4 drop-in already attributes the state model to Geffner & Bonet [13]).
    [AUTHOR Q] confirm the intended reference.
  - "relevant? If yes explain/define, if no drop": "PDDL also supports features beyond STRIPS
    such as conditional effects (when ...), derived predicates." AUTHOR leans KEEP (it
    foreshadows the §4 conditional-effect design that was later switched out) and asks
    Claude's input. [AUTHOR Q]
  - "name-dropping FF etc. doesn't help if not explained; not very relevant": cut/soften the
    FF heuristic + planner names.
  - "not true order of operation in FD": fix the "grounded task into ..." order-of-operations
    claim.
  - "reads badly because PDDLStream not introduced yet": "(SAS+)" forward-references
    PDDLStream -- reorder/avoid.
  - "I think most modern planners can deal with your domain": soften the claim that FD's
    specific SAS+/causal-graph machinery is what makes it scale.
  - "?" on "it implies" in "the state space it implies for a path" -- reword.
CURRENT TEXT (2026-06-09): citation concern largely RESOLVED -- state model cited
geffner2013concise + hofmann2024learning at L27 (the author's "Hofmann and Geffner" =
hofmann2024learning); FF cited hoffmann2001ff at L43. REMAINING (actionable): (a) KEEP the
conditional-effects line L25 (used by the §4 abandoned design / #328) but drop "numeric
fluents" (never used); (b) soften L45 "is what lets Fast Downward scale" (overstated --
most modern planners handle this domain); (c) L45 forward-references PDDLStream before §2.3
defines it -- add a pointer or rephrase.
Refs: background.tex §2.1; references.bib ([13]/Hoffmann&Geffner); #307. Annotation p.5.

#322  [DONE 2026-06-10 (commits f453396 + r2 rewrite, see body)] [T0] [THESIS]  Background §2.2 (p.6): K-literal either/or + KIF attribution + citation style
  - "not quite correct -- either/or, not both": a K-literal is known-true, known-false, OR
    unknown -- NOT both. Fix the explanation. [AUTHOR Q] (author wants to understand/verify
    the source before editing.)
  - "KIFs are based on know-whether -- Petrick PKS 2002": attribute Know-If Fluents to
    Petrick's PKS (know-whether) as the source/extra reference, alongside Brenner & Nebel
    (#278). Verify and cite.
  - "(at least that's one way of doing it)": soften "it must reason about its belief state."
  - "better to do the citation like this": near "POD builds on [1,5,13]" -- prefer numeric
    citations to author names (cross-ref #210).
CURRENT TEXT (2026-06-09, post-#278): the either/or explanation is ALREADY CORRECT (L54-57:
K(p) / K(~p) / neither=unknown, never both) and KIF-vs-K-literal is already distinguished
(L59). The [AUTHOR Q] on either/or is answered -- NO edit needed there. REMAINING (real):
L59 attributes know-whether to "Brenner and Nebel"; know-whether/know-if originates with
Petrick & Bacchus PKS (2002/2004) -- ADD that as the source (keep Brenner&Nebel for the
continual/assumption-based usage). Needs a references.bib entry for Petrick & Bacchus PKS.
UPDATE 2026-06-09 (review r2): the supervisor's "either/or, not both" actually targets the
TRANSLATION sentence (L59: "each literal replaced by the two fluents K(L), K(neg L)"), NOT the
K(p) definition. Rewrote it: two SEPARATE fluents, jointly consistent (never both true) but not
exhaustive (unknown = both false); two needed since K(neg L) != not-K(L). VERIFIED by subagent
vs Palacios&Geffner AAAI2006 p.901 Def.1 + JAIR2009 §4/App.B -- all four sub-claims SUPPORTED
(B stated as "jointly consistent", enforced by construction, hence that term over "mutually
exclusive"). Impl confirmed single-KIF: domain.pddl:42-45 (obj_at_boxel + obj_at_boxel_KIF, no
K(neg) pred) + sense effect :115-129; methods.tex:135. Petrick pages 212-222 added. Commits
f453396 + (this). DONE.
Refs: background.tex §2.2; references.bib (Petrick PKS 2002); #278 #210. Annotation p.6.

#323  [DONE 2026-06-10 (commit e208c70; bulk via prior passes)] [T0] [THESIS]  Background §2.3 (p.7): complexity argument wrong + stream definition + IK "sequence"
RESOLVED: complexity reframe, stream existence/identity correction, and IK candidate-pool
wording verified already applied; e208c70 closes the residual TAMP opener ('ignore
geometry' -> abstraction omits geometry; 'from the start' framing dropped).
  - "Delete-relaxed classical planning is still PSPACE-complete. Not the argument": the
    passage "while highly expressive, POMDPs are ... from actions behaving randomly." POD
    planning (delete-relaxed classical) is still PSPACE-complete, so "POMDP intractable / POD
    tractable because deterministic" does not hold. Reframe the tractability argument.
  - "it's less about deliberately ignoring delete-lists and more about a tractable/admissible
    approximation": reword "high-level planners often ignore geometry."
  - "Why does the point in time matter?": clarify "including all geometric details from the
    start makes ...".
  - "Not really. Some streams express existence and identity of objects -- so it's not just
    params": correct the procedural-component description of streams. He underlined the
    "Streams: declarative procedures for continuous parameters" line -- VERIFY this against
    the PDDLStream paper's own definition.
  - "why does IK give a sequence?": "produces a (potentially infinite) sequence of output
    values" -- clarify what an IK solver / stream actually outputs (it is the STREAM that
    yields a sequence of sampled solutions, not "IK gives a sequence"). [AUTHOR Q] (author
    asked what it actually does.)
Refs: background.tex §2.3; PDDLStream paper. Annotation p.7.

#324  [DONE 2026-06-10 (commit a03e6ee; bulk via prior passes)] [T2] [THESIS]  Background §2.3/§2.4 (p.8-9): readability + qualifiers + cut tail
RESOLVED: a03e6ee drops 'often' and qualifies the voxel-grid opener (common in robotic
mapping, not in symbolic planning); remaining sub-items verified already applied; the
'To make planning more efficient' AUTHOR-Q was already settled by the current rewording.
  - "hard to read": Example PDDLStream workflow -- put all args of (pick ?obj ?p ?g ?q ?t)
    on the SAME line.
  - "Not always?": remove "often" in "The overall PDDLStream algorithm often reduces a TAMP".
  - "common, but not in symbolic planning": qualify the §2.4.1 opening (voxel-grid
    discretization is common, but not in symbolic planning).
  - "a learned model predicts the CRs": "a deep network is trained to predict the critical
    regions" -> "a learned model predicts the critical regions" (it's the learned approach,
    not specifically a deep net).
  - scratched "To make planning more efficient" -- AUTHOR leans KEEP, asks Claude's input.
    [AUTHOR Q]
  - cut the last two sentences of the Background section (scratched).
Refs: background.tex §2.3/§2.4. Annotation p.8-9.

#325  [DONE 2026-06-10 (commit 5ac9fbc)] [T2] [THESIS]  §4.2 (p.18): clarify detection mechanism (raycast) + cross-cameras note
  - "detected how?": at "When an object is detected, we generate a dedicated Boxel" -- explain
    the detection mechanism (the raycast).
  - "In discussion, explain how this might be extended to more cameras or real settings": the
    Recursive Partitioning paragraph -- add such a note to the discussion.
Refs: methods.tex §4.2; discussion.tex.

#326  [DONE 2026-06-10 (commit a12d285)] [T2] [THESIS]  §4.x (p.19): viewpoint wording + typography + belief->KIF + keep re-explanation
  - "from a VP [viewpoint]": "the objects themselves and the occluded spaces" ("occluded"
    underlined) -- make occlusion viewpoint-dependent in the wording.
  - "renders weirdly": fix the inline italic "obj"/"Boxel" in "For each object obj and Boxel
    Boxel" (typography).
  - "belief doesn't, KIF does": replace "belief"->KIF in "the belief tracks whether the
    robot..." and "the belief records one know..." (cross-ref #307).
  - "not necessary to explain again": the KIF-vs-K-literal re-explanation repeats Ch2 --
    AUTHOR wants to KEEP it. Likely no-op; recorded so it isn't re-raised.
Refs: methods.tex §4 (p.19); #307. Annotation p.19.

#327  [DONE 2026-06-10 (commit cc5fb79)] [T2] [THESIS]  §4.4 (p.20): modesty of "tractable" + "optimistic sensing" qualifier
  - "tractable" (underlined): make modest -> "easier"/"less computationally intensive"/
    "more efficient"; keep the claim minimal.
  - add Daniel's qualifier to the reduction paragraph: "In our domain this reduction lets an
    ordinary classical planner reason directly about where objects might be and plan sensing
    actions to resolve that uncertainty within the same classical search, rather than
    delegating belief to a separate contingent or belief-space planner" + "under optimistic
    assumptions for sensing actions".
  - naming (#310); the model formalization itself = #307.
Refs: methods.tex §4.4; #307 #310. Annotation p.20.

#328  [REJECTED 2026-06-10 (added 047f823, REVERTED 164473d)] [T2] [THESIS]  §4.5 sense action (p.22): pessimistic-version note + abandoned conditional-effect design
ANSWER to the author Q (recorded here, not in the thesis): pessimistic sensing = determinise to
the worst case (every sense finds nothing); under our encoding a search goal then admits no plan
until the target's location can be DEDUCED from exhausted alternatives -- the LW1-style axiom
machinery we lack. Author decided AGAINST mentioning it in the text; sentence reverted.
"Would've been interesting to compare a pessimistic version." -- the optimistic sense action
(and the abandoned conditional-effect design). Optionally note pessimistic sensing as future
work / a design alternative. [AUTHOR Q] author asks "what is pessimistic sensing?" -- answer
before deciding whether/how to mention it.
Refs: methods.tex §4.5. Annotation p.22.

#329  [DONE 2026-06-10 -- VERIFIED resolved by prior work, no edit] [T1] [THESIS]  §4.5 (p.23, Fig 4.4): REMOVE the convergence claim; note relocated objects emit no new shadows
RESULT: the convergence/"equivalent to a conditional plan" claim no longer exists in
methods.tex (removed by the #307 §4.4 drop-in era rewrites); the no-new-shadows fact is
already stated twice (§4.2 "not given a new shadow at its destination"; §4.5 "moving an
object cannot spawn new shadows to search").
"N candidates AND no new occluders -- if there's a new occluder, this doesn't hold." The
"converges in at most N replanning cycles / equivalent to a conditional plan" claim breaks
when sensing reveals a new occluder. AUTHOR: remove the convergence claim completely; also
state here that in our implementation relocated objects do NOT emit new shadows. Cross-ref
#307 (honest framing).
Refs: methods.tex §4.5; fig:replan-cycle; #307. Annotation p.23.

#330  [DONE 2026-06-10 (commit dd23482)] [T1] [THESIS]  §5.3 Baselines (p.28): "semantic" is our METHOD, not a baseline; clarify variant differences
"'semantic' is arguably your approach, not a baseline" -- reframe baseline #1 in §5.3 as our
method. "Make the difference [between variants] clearer" (likely the TAMPURA section,
possibly §5.3 as a whole) -- make the semantic / +mbs0.05 / uniform distinctions
self-explanatory. Pairs with p.34 "make the environment/variant difference self-explanatory".
Refs: results.tex §5.3/§5.4.5. Annotation p.28/p.34.

#331  [DONE 2026-06-10 (commit a91d46a)] [T2] [THESIS]  §5.4 anytime (p.29): rewrite "Three observations stand out" -- findings first
"?" on "Three observations stand out. First, the semantic curves rise in a goal-dependent
way." AUTHOR agrees it reads weird; the whole subsection needs restructuring -- state the
interesting FINDINGS first, then the facts of the graph in a structured way ("shape of curve
per goal is not it"). NB #282 already rewrote these three observations once; the structure
still doesn't land -- this is a further pass.
Refs: results.tex subsec:anytime; #282. Annotation p.29.

#332  [INFO] [THESIS]  p.31 stack numbers "could be better" -- NO ACTION (recorded only)
"Your numbers could be better" -- the stack success rates (esp. the h=4 collapse) would lift
with a better manipulation model. AUTHOR: "okay nice but not an issue to resolve." No edit;
the framing fix lives in #304. Recorded so it isn't re-raised.
Refs: results.tex stack-success; #304.

#333  [DONE 2026-06-10 -- resolved by #309 merge (commit ca86685)] [T2] [THESIS]  §6.4 Threats (p.39): "this implies bad exp setup" -- reword
The Threats-to-Validity wording reads as if the experimental setup were flawed. Reword so it
frames genuine threats without implying a bad setup. (Daniel: the real threats are the
number/CPU inconsistencies -- see #308.)
Refs: discussion.tex §6.4; #308. Annotation p.39.
RESOLVED: the #309 merge replaced the old threats intro with "deliberate simplifications ...
adopted to isolate the contribution"; #308 fixed the number/CPU inconsistencies Daniel named
as the real threats. No apologetic framing remains; author approved closing without further edit.

#334  [DONE 2026-06-10 (commit b018b92)] [T2] [THESIS]  Related-work shortening: confirm the move to Background + resolve the framing question
RESOLVED: framing = "space abstraction is the contribution, TAMP is the demonstration" (matches
intro Contributions). Background 2.4 keeps the mechanics (move confirmed, unchanged); NEW
Related Work 3.1 "Spatial Representations for Planning under Occlusion" leads the chapter with
the positioning (occupancy grids/octrees with pointer to the uniform ablation as the controlled
in-thesis comparison; critical regions; occlusion-in-belief: TAMPURA visibility grid, IBSP,
SS-Replan, Bejjani -- all existing citations, none new). TAMP under PO -> 3.2; POD subsection
second para deduplicated; 3.2.6 gap summary repointed from 2.4 to 3.1; intro outline updated.
Defense answer now in writing: the uniform-grid ablation IS the discretization comparison at
matched cell size, and the resolution sweep rules out tuning.
AUTHOR meta-note (p.9): the visual-representation material was shortened and MOVED from
Related Work into Background -- the major change between the last two versions. Open framing
question: "am I doing TAMP + space abstractions, or space abstractions with a TAMP
implementation that proves the abstraction is useful?" [AUTHOR Q] Claude to weigh in; also
RAISE with the supervisors whether the relocation is acceptable. Affects how #303/#300 frame
the contribution.
Refs: related-work.tex; background.tex §2.4; #300 #303. Annotation p.9.

#335  [DONE 2026-06-10 (commit 6e3aa7b)] [T0] [THESIS]  "blocked from view" failure mode is MISATTRIBUTED -- most all_searched
cells were NOT blocked; the search finished and the target was simply never seen
[CLAUDE honesty sweep 2026-06-10; measured from sweep_full_2026-05-28 cells/*/stdout.log]
results.tex §5.2 (metrics) defines "blocked from view" as failing "only because the target's
region stayed blocked from the fixed camera, so its absence was never actually observed";
§5.6 + fig:failure-modes caption repeat it, and conclusion.tex asserts "The scenes studied
here are arranged so that every place an object can hide is one such anticipated shadow
region."  The data contradicts all three:
  - Of the 18 HEADLINE all_searched cells, only 5 contain the audit-#21 "blocked-unresolved"
    give-up line.  The other 13 printed "All N shadows searched -- target not found": every
    shadow WAS observed (empty) and the target was still never seen.
  - Of those 13: 11 were spawn-time "boundary case" scenes (audit-#67 oracle line: target
    camera-occluded but its centre OUTSIDE every shadow AABB -- shadow under-coverage near
    cone edges), e.g. randpairs_occ2_seed44_holding_uc0_semantic; 2 (occ4_seed50 semantic +
    uniform) had the target IN a shadow at spawn yet sensed that shadow empty (target likely
    displaced during execution, or the sense raycast missed it).
  - Across the whole sweep dir (incl. resolution arms): 41 all_searched cells = 8 blocked /
    33 observed-all-empty.
So the dominant cause is NOT an unresolvable line of sight; it is the partition failing to
cover the place the target actually hides (or losing it during manipulation) -- the search
completes "successfully" and misses the object.  That is a more substantive limitation of
the shadow-AABB representation and is currently presented as something else.
FIX: (1) §5.2: rename/redefine the mode honestly, e.g. "search exhausted: every candidate
region was sensed empty or given up, and the target was never observed", and state the two
sub-causes (shadow-AABB under-coverage at the occlusion-cone boundary; bounded give-up on
still-blocked regions) with the 13-vs-5 split.  (2) §5.6 text + fig caption: same.
(3) conclusion.tex: delete or qualify the "every place an object can hide is an anticipated
shadow region" sentence -- the eval itself refutes it.  (4) §6.4/§6.5: bounded-give-up
paragraphs stay (true for the 5), add the under-coverage gap as its own accepted limitation
(links THESIS_NOTES §14 / audit #67/#72 lateral-overhang work).  Machine-readability of this
distinction is filed as CODEBASE_AUDIT #124.
Refs: results.tex §5.2 + subsec:failure-modes + fig caption; conclusion.tex (anticipated-
shadow sentence); discussion.tex §6.4 "Bounded give-up" + §6.5 Planning; CODEBASE_AUDIT
#124; THESIS_NOTES §14, §18.

#336  [DONE 2026-06-10 (commit 66255db)] [T2] [THESIS]  §5.2: "a failed object release ... did not occur in these runs" is FALSE
[CLAUDE honesty sweep 2026-06-10]  results.tex §5.2 closes the failure-mode list with "A
further give-up, a failed object release after repeated retries, is possible but did not
occur in these runs."  It DID occur, once, in a headline cell: drop_failed on
find-and-tray-stack, semantic+mbs0.05, seed 36, n_occ=3 (aggregated.csv; #282's own
FINDINGS block lists "drop_failed 1 (f-a-t-s)").  Fix: "...occurred once in 810 cells" or
drop the claim.  (fig:failure-modes shows only the semantic/uniform variants, where it
indeed never occurs -- if that is the intended scope, say so explicitly.)
Refs: results.tex §5.2; eval_results/sweep_full_2026-05-28/aggregated.csv; #282 FINDINGS.

#337  [DONE 2026-06-10 -- VERIFIED, no edit] [T3] [ADMIN]  Verify the intro source-code footnote URL actually resolves
RESULT: anonymous `git ls-remote https://git.rwth-aachen.de/hani.alassiri.alhabboub/
Semantic_Space_Abstractions.git` returns HEAD c41440c2, and that commit exists in the local
history -- the GitLab project was renamed to Semantic_Space_Abstractions (old pybullet.git
remote URL redirects), is PUBLIC, and is this repo.  Footnote URL is correct as printed.
[CLAUDE honesty sweep 2026-06-10]  introduction.tex footnote links
git.rwth-aachen.de/hani.alassiri.alhabboub/Semantic_Space_Abstractions, but the local git
remote is .../pybullet.git (GitLab) and the GitHub remote is hanihabobo-dot/Semantic-Regions
.git.  If the GitLab project was renamed, the old remote URL redirects and the link is fine;
if not, the printed link 404s.  Confirm in a browser (logged out, to check visibility too)
and align with whatever #208 intended (GitHub link present?).
Refs: introduction.tex footnote; #208; git remote -v.

#338  [DONE 2026-06-10 (commit 11c4e9b)] [T0] [THESIS]  FATS goal misdescribed -- it is a TWO-CUBE
tray tower with ONE hidden cube, not "find them all"
[AUTHOR finding 2026-06-10, code-verified]  test_full_pipeline.py:736-781 (audit #55): the
find-and-tray-stack goal is ('on', visible_cube, tray) + ('on', hidden_cube, visible_cube) --
ONE randomly chosen visible cube on the tray, ONE randomly chosen hidden cube stacked on top;
--stack-height is never consulted (height always 2); the scene's other K-1 hidden cubes are
in-shadow distractors only.  build_tray_stack_goal (the #49 multi-cube builder, :387) is dead
on this path.  The thesis said "must locate hidden cubes ... and stack them" / "must find them
ALL" -- false.  Sweep data: FATS scenes have K=1/2/3/4 hidden in 93/66/19/7 of 185 recorded
headline cells, so the scenes DO contain multiple hidden cubes; only the goal involves one.
FIXED: §5.1 Goals bullet + scene-gen sentence + fig:eval-tasks caption + abstract now state
the two-cube-tower goal; discussion §6.1 explains FATS(75.6) > holding(65.6) via the two
holding-only failure channels (search exhausted 8 + false success 7 on holding-semantic;
without them holding would be ~82%) and the height-2 tower being the most reliable
manipulation.  Re-run on a richer FATS setup judged infeasible pre-deadline (days of compute)
and unnecessary once the description is honest; note for future work if supervisors push.
Refs: results.tex §5.1 + fig:eval-tasks; abstract.tex; discussion.tex §6.1;
test_full_pipeline.py:387,736-781; aggregated.csv n_hidden.

#339  [DONE 2026-06-10 (commit 85f48d6)] [T1] [THESIS]  Merge Discussion chapter into Results
(supervisor Daniel 2026-06-10: too much Results<->Discussion flipping; separate discussion
chapter unusual; conclusion stays its own chapter). Ch.5 is now "Results and Discussion":
each discussion section interleaved directly after the results it interprets -- 5.4.5
Adaptive vs Uniform Partitioning (after compactness), 5.4.7 Resolution Regime and the 5cm
Leaf-Floor Variant (after free-space resolution; old disc-mbs0 + the limitations "Resolution
regime" para merged, duplicate convex-merge explanation removed), 5.4.9 Architectural
Comparison with TAMPURA (after the numbers). Old §6.4 became §5.5 with title softened
"Limitations and Threats to Validity" -> "Limitations" (author: threats-framing sounded like
a broken setup); intro sentence reworded to scope-framing. ch:discussion label deleted; all
5 referring sentences fixed (introduction outline, conclusion, results x3); labels
sec:disc-* and sec:limitations preserved so the 9 \cref{sec:limitations} references and
sec:disc-tampura ref were untouched. chapters/discussion.tex deleted; main.tex include
removed; conclusion renumbered ch.7 -> ch.6. Build clean 74pp, 0 undefined.
Refs: results.tex; main.tex; introduction.tex; conclusion.tex.

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
  --- Supervisor review 2026-06-09 (#300-#334; Daniel Swoboda EMAIL + Till/Daniel handwritten
      annotations on the OLD PDF) -- all OPEN. Headline: symbolic layer over-represented,
      integration/perception/engineering under-represented. ---
      MUST-FIX:          #311 (supervisor names: Till Hofmann + Daniel Swoboda) #312 (title = registered)
      Cross-cutting (T1):#300 (Boxel algorithm + pseudocode, FRONTWARDS) #301 (stream impls)
                         #302 (sense-plan-act loop pseudocode) #303 (§4.1 flowchart/intro)
                         #304 (manipulation model up front) #305 (scene generation)
                         #306 (TAMPURA comparison is INDIRECT) #309 (§5/§6 reorg)
      Correctness (T0):  #308 (§5/§6 number+CPU inconsistencies -- the true threats) #315 (cite [8,11])
                         #317 (overhead camera NOT overhead) #320 (STRIPS != PDDL model)
                         #321 ([21]->[13]/Hoffmann-Geffner) #322 (K-literal either/or; Petrick PKS)
                         #323 (PSPACE-complete; stream defn; IK sequence)
      Honesty theme:     #307 (Know-If literals are helpers; Daniel's §4.4 drop-in; we don't certify b_g)
                         #329 (remove convergence claim) #310 (drop "Semantic" doc-wide)
      [AUTHOR Q] (answer before edit): #321 (cond-effects keep?) #322 (K-literal source)
                         #323 (what IK outputs) #324 ("efficient" keep?) #328 (pessimistic sensing?)
                         #334 (related-work move + framing)
      No-action/admin:   #313 (epigraph website variant) #332 (stack numbers -- recorded only)
      Page-local edits:  #314 (abstract) #316 #318 (intro) #319 #324 (background) #325 #326 #327
                         (approach) #330 #331 (results) #333 (discussion)
  --- Honesty sweep 2026-06-10 (#335-#337; full entries above) -- all OPEN. ---
      Correctness (T0):  #335 ("blocked from view" misattributed: 13/18 headline all_searched
                         cells observed every shadow empty -- shadow-AABB under-coverage, not a
                         blocked line of sight; conclusion's "every hiding place is an
                         anticipated shadow region" refuted by the sweep's own logs)
      Correctness (T2):  #336 (drop_failed DID occur once -- §5.2 sentence false)
      Admin (T3):        #337 (verify intro repo-link URL resolves)
      Also: #282 ADDENDUM (resolution-refresh specifics: 100-seed claim stale, no stack arms,
            plan-time fall 79-86 % not 30-65 %, old 4-arm figure); cross-filed code issues
            CODEBASE_AUDIT #123 (bridge go_home forced success) #124 (persist give-up +
            spawn-classification fields) #125 (stale TAMPURA plotter docstring).

DONE: #168, #176, #177, #178, #179, #180, #182, #183, #184, #185, #187, #188, #189, #190, #191, #193, #194, #195, #197, #198, #200, #201, #202, #203, #204, #205, #206, #207, #208, #211, #212, #213, #259, #261, #262, #288, #289, #290, #291, #292, #293, #294, #295, #297, #298, #299. MERGED: #192->#187, #196->#176. REJECTED: #186 (expansion declined), #175 (shadow #102/#103 reconciliation declined; by-depth drop already done), #260 (TAMPURA/Saleem differentiation -- redundant, declined).

Gating: #141-#156, #130 done — eval write-up (Results/Discussion/abstract/conclusion) is in
thesis/, chapters clear of internal paths + hardware clutter, front/back matter in place, nine
sim figures inserted. #125/#140/#121/#127 closed jointly. #126 (forward-voice conversion)
verified+closed (chapters already retrospective). §5 polish (#87-#111) resolved earlier.
