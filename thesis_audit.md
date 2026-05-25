================================================================================
THESIS AUDIT — OPEN ISSUES
================================================================================
Date:   2026-05-16
Target: the Master thesis in thesis/ ("main.pdf", ~58 pages),
        "Semantic Partitioning for Partially Observable Deterministic Task and
        Motion Planning."
Method: six parallel review passes —
          - 3 proposal-vs-code deviation audits (Approach §4; Evaluation §5 +
            Introduction §1; §1-§3 narrative honesty);
          - 1 scientific-correctness + citation audit (whole document);
          - 2 writing-style audits (Abstract-§3; §4-§5).
        120 findings (#1-#120), consolidated and de-duplicated below.
        2026-05-17: a DISPOSITION axis ([NOW]/[POLISH]/[THESIS]) was added to
        every issue header, and 10 thesis-conversion issues (#121-#130) — the
        structural proposal-to-thesis work the sentence-level audit missed —
        were appended. See the DISPOSITION block below and, at the end,
        SUMMARY BY DISPOSITION.

This file is the thesis counterpart of CODEBASE_AUDIT.txt. Work it with the
/workflow skill — see its "Working a LaTeX / thesis audit" section: one issue
per turn, before/after preview, explicit approval, `latexmk main.tex` recompile
after each fix, an individual commit in the thesis/ repo, then mark
the issue [DONE] here.


================================================================================
CONTEXT & POLICY
================================================================================

PROPOSAL, NOT YET A THESIS
   main.pdf is a research PROPOSAL written 2025-09-29 — forward-looking
   ("we will", "we propose"). The codebase was built AFTER it and has drifted.
   Many issues below are reconciliations the eventual thesis must make; some
   are errors to fix in the proposal as it stands. For each issue, decide
   whether the fix belongs now (the text is simply wrong) or is a flagged
   rewrite for the proposal-to-thesis upgrade.

THESIS_NOTES.md IS CANONICAL FOR ACCEPTED SIMPLIFICATIONS
   notes/THESIS_NOTES.md lists 21 accepted simplifications. A deviation already
   disclosed there is still tracked here (the proposal TEXT was never updated
   to match) but is lower-risk — the author already knows. A deviation NOT in
   THESIS_NOTES is the dangerous kind; those are flagged "(undisclosed)".

SECTION -> SOURCE FILE  (all paths under thesis/)
   Abstract         chapters/abstract.tex
   §1 Introduction  chapters/introduction.tex
   §2 Background    chapters/background.tex
   §3 Related Work  chapters/related-work.tex
   §4 Methods       chapters/methods.tex
   §5 Results       chapters/results.tex
   §6 Discussion    chapters/discussion.tex
   §7 Conclusion    chapters/conclusion.tex
   Appendix         chapters/appendix.tex
   References       resources/references.bib

TIERS
   T0  factual / scientific error, or a misattributed citation. Wrong.
   T1  major proposal-vs-implementation deviation; the text materially
       misdescribes the built system.
   T2  style, clarity, or honest framing; prose that is robotic, empty,
       generic, inflated, roundabout, or mildly over-claims.
   T3  minor: naming, headings, small imprecision, LaTeX/build, polish.

DISPOSITION  (added 2026-05-17 — the proposal-to-thesis axis)
   Tiers grade SEVERITY. Disposition says WHY a fix exists and WHEN it
   applies. Every issue header (#1-#120) now also carries exactly one of:
   [NOW]     A correctness error — grammar, citation, LaTeX build, naming
             inconsistency, scientific imprecision. Wrong on the proposal's
             own terms; independent of the thesis upgrade; can be applied
             anytime.
   [POLISH]  A prose-quality rewrite. Not an error, not upgrade-specific.
             Lowest priority if the goal is strictly the thesis upgrade.
   [THESIS]  Exists BECAUSE the proposal is becoming a thesis: reconcile the
             text with the built system, convert forward-looking framing to
             completed-work voice, or report real results. This is the
             actual proposal-to-thesis conversion work.
   Counts across #1-#120: 20 [NOW], 55 [POLISH], 45 [THESIS]. The new
   thesis-conversion issues #121-#130 are all [THESIS]. The upgrade work is
   the 45 [THESIS] issues plus #121-#130 — see SUMMARY BY DISPOSITION.
   Note: [POLISH] fixes mostly TRIM prose; the thesis must still GROW
   overall — that growth is issues #121-#125.

ISSUE NUMBERING
   #N is filing order (grouped by proposal section), NOT priority. Read the
   TIER tag. The SUMMARY BY TIER at the end lists issues priority-first; start
   with T0 and T1.

STATUS
   An issue with no marker is OPEN. Resolved issues get "[DONE]" (or
   "[REJECTED]") added to the header line, matching CODEBASE_AUDIT.txt.

STYLE STANDARD (T2 Style issues)
   The target voice is a human explaining things simply and directly. Style
   issues flag prose that is empty filler, generic boilerplate, fancy/inflated,
   roundabout, or robotic, and each gives a plain-English rewrite. The rewrites
   are suggestions — keep the technical content, drop the fluff.


# ISSUE ADDED 2026-05-23 (FIGURES / CAPTIONS REVIEW): figures need a dedicated one-by-one pass.

================================================================================
#168  [T1] [THESIS]  Figures/captions review --- go through every figure one by one
================================================================================
Where: every \includegraphics in the thesis --- schematic diagrams, simulator
       screenshots, and results plots. Inventory by source file:
       - introduction.tex: fig:intro-hero (sim/scene_hidden_target.png)
       - methods.tex: fig:boxelization (Boxelization.png, schematic),
         fig:boxelization-real (sim/boxelization_real.png),
         fig:partition-semantic + fig:partition-uniform,
         fig:sense-action (sim/sense_targeting_shadow.png),
         fig:replan-cycle (sim/replan_cycle.png)
       - background.tex: fig:octmap_illustration (octmap_illustration.png)
       - discussion.tex: fig:retry-giveup (sim/sense_fail_retry3.png)
       - results.tex: results plots + composites (success rate, planning
         time, boxel counts, failure modes, TAMPURA, n_occluders, task
         triptych, overhead-camera inset)
What:  Two failure modes, triaged per figure:
       (1) MISREPRESENTS --- the image does not show what its caption or the
           surrounding text claims (labelled element absent, wrong scene, shows
           a different mechanism). Materially misdescribes the system: T0/T1,
           must be fixed (recapture, relabel, or correct the caption).
       (2) SUBOPTIMAL --- accurate but not the clearest illustration (cluttered,
           low contrast, bad crop/angle, key element too small). T2/T3; replace
           with a better shot or annotate.
       Inspect each image VISUALLY (read the PNG) against its caption and the
       paragraph that cites it; do not trust the caption text alone.
Fix:   One-by-one walkthrough, each figure its own commit. Per figure: read the
       image, compare to caption + referencing text, decide keep / recaption /
       re-annotate / recapture. If regenerating, ADD a new image --- never
       overwrite an existing one, and keep the old one regenerable. Keep
       \includegraphics paths as sim/<name>.png; no internal repo paths in
       captions.
Refs:  introduction.tex; methods.tex; background.tex; results.tex;
       discussion.tex; thesis/graphics/sim/.

================================================================================
#175  [T2] [THESIS]  methods.tex shadow-splitting text vs code (CODEBASE #102/#103)
================================================================================
Where: methods.tex shadow-Boxel description (the "one or more shadow
       Boxels, split by depth and by intervening obstacles" phrasing).
What:  Two CODEBASE_AUDIT fixes (2026-05-24) changed the shadow
       representation the methods text describes:
       - #102 made the per-occluder depth split CONDITIONAL.  A
         non-intersecting occluder now casts ONE shadow Boxel; only a
         shadow whose lateral overhang overlaps another shadow / object
         is split into near + far slabs (and further divided by
         intervening obstacles).
       - #103 stops a mid-air / held occluder from casting a shadow at
         all (only objects resting on the support surface do).
       The current prose implies every shadow is split by depth, which
       now overstates what the code produces.
Fix:   Reword so depth-splitting reads as conditional --- e.g. "a shadow
       is a single Boxel unless it overlaps another region, in which case
       it is split by depth and by intervening obstacles" --- and note
       that an occluder must rest on a surface to cast one.  Cross-check
       the shadow figures flagged in #168 (they show the two-slab case).
Refs:  methods.tex (thesis/); CODEBASE_AUDIT.txt #102 #103; #168.

================================================================================
#176  [T3] [THESIS]  Discretization-progression figure (PyBullet captures) + free-space split->merge stages (merged #196)
================================================================================
Where: methods.tex (thesis/) --- a possible companion to the schematic
       fig:boxelization; captures live under thesis/graphics/sim/raw_captures/.
What:  In the 2026-05-24 capture session the user grabbed PyBullet GUI frames
       showing the free-space discretization building up cell-by-cell with the
       wireframe/grid overlay visible (the offscreen getCameraImage path cannot
       capture PyBullet debug-draw, so the GUI is required).
       - UNIFORM progression: raw_captures/"Screenshot 2026-05-24 125056..125436"
         (~16 frames, fixed viewpoint; the cyan grid fills the workspace step by
         step).  A strong angled still is kept as capture_partition_uniform_angle.png.
       - SEMANTIC progression: the session was dominated by uniform-grid angle
         shots; a clean step-by-step SEMANTIC sequence was NOT clearly captured.
         (The schematic fig:boxelization (a)-(d) already shows the semantic build.)
Fix:   Decide: (a) add a real (non-schematic) progression figure to methods.tex
       --- ~3-4 curated frames per discretization, window chrome cropped, paired
       with fig:boxelization as "the partition as actually built in PyBullet" ---
       or (b) drop as redundant with the schematic.  If (a) and a clean SEMANTIC
       progression is wanted, capture it with tools/render_thesis_figs.py
       (--baseline semantic, GUI freeze).
Refs:  methods.tex (fig:boxelization); thesis/graphics/sim/raw_captures/;
       tools/render_thesis_figs.py; #168.

================================================================================
#177  [DONE 2026-05-25] [T0]  TAMPURA comparison: wrong task + self-contradiction (now holding, wall-clock)
================================================================================
CLOSED 2026-05-25.  Figure + abstract + results + discussion re-pointed from
find-and-tray-stack to HOLDING (the find_dice analogue); the self-contradiction
with discussion:101 removed; success stated on both sides (ours ~42% vs TAMPURA
>= 63%).  The "planning-time only / like-for-like / 14.0 s / ~4x" framing this
issue first prescribed was WRONG and was dropped: TAMPURA's Table II time
includes simulated controller execution (per-episode), so the comparison now
reports our per-episode wall-clock (mean 13.7 s) against TAMPURA's 57 s only.
Architectural framing: see #190 (online per-step, not offline).

# ISSUES ADDED 2026-05-24 (INTRO / BACKGROUND / RELATED-WORK read-through, agent-verified): #178-#189.

================================================================================
#178  [T1] [NOW]  Intro says the partition discretizes "only" objects + occlusions (omits free space)
================================================================================
Where: introduction.tex:26 ("discretizing the workspace around the objects the
       robot detects and the regions they occlude"); introduction.tex:33
       (contribution bullet: "discretizes only the task-relevant regions -- the
       objects themselves and the volumes they occlude").
What:  Factually misdescribes the built partition. methods.tex:36 partitions the
       leftover space into Free Space Boxels (recursive octree + greedy convex
       merge), and the figure captions (methods.tex:20, :27, :45) say "free space"
       explicitly. The intro's "only ... objects + occlusions" / "around the
       objects ... and the regions they occlude" drops the free-space stage.
Fix:   :26 -> "...into the objects the robot detects, the regions they occlude,
       and the free space between them". :33 -> drop "only"; reframe as adaptive
       RESOLUTION ("concentrates resolution on the task-relevant regions ... while
       covering the remaining free space with a few coarse cells, rather than
       partitioning all space uniformly"). Preserve the semantic-vs-uniform
       contrast (adaptive resolution, not "objects only").
Refs:  introduction.tex:26,33; methods.tex:36 (Free Space Boxels),:20,:27,:45.

================================================================================
#179  [T2] [POLISH]  Intro contributions: drop TAMPURA from section 1, cut the "first-class state" opener
================================================================================
Where: introduction.tex:31 (Contributions paragraph).
What:  (a) User wants TAMPURA confined to Related Work; section 1 currently
       contrasts against "the dense visibility voxel grid of TAMPURA's Find Die
       benchmark ... a learned model of action outcomes" and previews "an
       architectural comparison with TAMPURA". (b) The opener "we make occlusion
       first-class symbolic planning state" is flagged as empty.
Fix:   Cut the "we make occlusion first-class..." clause and let the colon run
       into "each volume the robot cannot see becomes a named region that a
       classical POD planner reasons over and resolves by sensing." Remove the
       TAMPURA Find-Die/voxel-grid clause and the "alongside an architectural
       comparison with TAMPURA, rather than claiming a benchmark win" clause; keep
       the ablation + oracle-perception framing. NOTE: the TAMPURA comparison stays
       in Results/Discussion (see #177); this only de-hypes section 1.
Refs:  introduction.tex:31; #177 (TAMPURA results comparison); related-work.tex.

================================================================================
#180  [T3] [POLISH]  Background state-model notation: Pi for the tuple is unconventional
================================================================================
Where: background.tex:13 ("a deterministic state-space model ... a tuple
       Pi = <S, s_0, S_G, Act, A, f>"); background.tex:69 ("the state model S(P)").
What:  User asked where S and Pi come from. Not a hallucination: this is the
       standard state-model formalism of Geffner & Bonet (geffner2013concise,
       already cited at background.tex:11); S(P) = "state model encoded by problem
       P". But Pi conventionally denotes a PLAN/POLICY, so using it for the model
       tuple can trip a reader.
Fix:   Optional. Either (a) leave; (b) add \cite{geffner2013concise} at the tuple
       definition (:13); or (c) rename the tuple symbol to a neutral letter (e.g.
       M) to avoid the plan/policy clash. Author to pick.
Refs:  background.tex:11,13,69; geffner2013concise.

================================================================================
#181  [T2] [POLISH]  "POD ... rather than established terminology" -- name the real term (contingent planning)
================================================================================
Where: background.tex:85 ("''POD'' is a descriptive label we adopt for this
       setting rather than established terminology in the contingent-planning
       literature it builds on").
What:  Claim VERIFIED accurate (agent): "POD"/"Partially Observable Deterministic"
       is NOT a standard term; the literature calls this exact setting
       (deterministic dynamics, partial observability resolved by sensing)
       CONTINGENT PLANNING. The hedge is true but bare -- it apologises without
       telling the reader the standard name.
Fix:   Reword to name the term: "This is the setting the planning literature calls
       \emph{contingent planning} \cite{albore2009translation, geffner2013concise};
       'POD' is simply the descriptive label we use for it throughout." Strengthens
       the sentence and answers "why mention it".
Refs:  background.tex:85; albore2009translation; geffner2013concise.

================================================================================
#182  [T3] [POLISH]  Background heading "Voxel Grids and Octrees" -> "Voxel Grids"
================================================================================
Where: background.tex:140 (\paragraph{Voxel Grids and Octrees}).
What:  User wants the heading shortened to "Voxel Grids". Caveat: the body
       (background.tex:143-150 + fig:octmap_illustration) spends a full paragraph
       on octrees, so the heading would be narrower than its content (an octree is
       a hierarchical voxel structure, so it still fits).
Fix:   Rename heading to "Voxel Grids". Optionally fold the octree text in with a
       one-line lead ("Octrees are a hierarchical voxel variant ...") so heading
       and body match. Author to pick whether to also retitle the octree text.
Refs:  background.tex:140,143-150 (fig:octmap_illustration).

================================================================================
#183  [DONE 2026-05-25] [T0]  related-work.tex:12 Bayes3D scaling claim + TAMPURA belief source
================================================================================
CLOSED.  Dropped the wrong "scales poorly as #hypotheses/objects grows" claim
(Bayes3D is GPU-parallel, ~2048 hypotheses scored in parallel) and scoped the
Bayes3D belief source to TAMPURA's real-robot pipeline (the released Find-Die
sim uses ground-truth segmentation + a visibility voxel grid).

================================================================================
#184  [T3] [POLISH]  pan2024task: "reactive controllers" -> their term is "behaviors"
================================================================================
Where: related-work.tex:15 (Partially Grounded Plans subsection: "specialized
       reactive controllers attempt to fill these gaps ... it can struggle with ...
       deciding which of several actions is most likely to reveal a hidden object").
What:  Claim VERIFIED FAIR (agent): Pan et al. (TAMPER) fill plan gaps with
       closed-loop "behaviors" (hand-designed OR learned), NOT a planner that
       re-reasons about uncertainty -- they explicitly prioritise behaviors over
       re-planning, so no proactive multi-step info-gathering. The "struggle" claim
       stands. Only "specialized reactive controllers" is slightly off their
       terminology and implies hardcoded-only.
Fix:   "specialized reactive controllers" -> "specialized closed-loop behaviors
       (hand-designed or learned)". Sentence otherwise correct; keep.
Refs:  related-work.tex:15; pan2024task.

================================================================================
#185  [T2] [POLISH]  Rewrite the hard-to-read Ma et al. paragraph
================================================================================
Where: related-work.tex:20 ("One approach adds high-level strategic reasoning on
       top of standard planners to handle real-world messiness. For instance, Ma et
       al. ...").
What:  User: opener is empty filler and the paragraph is very hard to read. Ma et
       al. description VERIFIED accurate (agent): Task-level Backward Search = work
       backward from an underspecified goal to identify which objects the task
       needs; Object Manipulation Constraint Graph = order the moves to reach
       cluttered objects without collisions.
Fix:   Drop the "real-world messiness" opener; rewrite for clarity (proposed text
       in chat 2026-05-24): "Ma et al. add a strategic reasoning layer on top of a
       standard planner ... Our approach differs at the representation level rather
       than adding a separate layer ...". Keep the oracle parenthetical.
Refs:  related-work.tex:20; ma2025task.

================================================================================
#186  [T2] [POLISH]  CoCo-TAMP description too thin -- expand mechanism
================================================================================
Where: related-work.tex:22 ("CoCo-TAMP ... using an LLM's commonsense priors to
       shape the belief over where task-relevant objects are likely to be").
What:  User wants more detail. Mechanism VERIFIED (agent, full paper): LLM queried
       with multiple-choice questions about likely locations; softmax over answer
       log-probs -> distribution over semantic locations (rooms/surfaces); a
       hierarchical Bayesian filter maintains the belief; the planner consumes it
       via SENSING-ACTION COST (looking where an object is unlikely costs more),
       steering the robot to informative views. Current one-liner understates that
       it also drives WHERE to look, not just the prior.
Fix:   Expand to ~2 sentences covering the QA->distribution->filter pipeline and
       the observation-cost coupling (proposed text in chat 2026-05-24).
Refs:  related-work.tex:22; kim2026llmguided (arXiv:2603.03704).

================================================================================
#187  [T1] [NOW]  related-work.tex:24 Bai et al.: wrong limitation + framework name/mechanism (merged #192)
================================================================================
Where: related-work.tex:24 (Bai et al. paragraph; both fixes hit the same sentences).
What:  (a) LIMITATION WRONG (T1): "adapting ... requires re-tuning hardcoded geometric
           constants" is NOT TRUE -- retargeting to a new goal requires adding NEW PDDL
           actions (+ streams), not tuning constants (evidence: the stack goal needed a
           new action + predicates + stream, #205). Do NOT use the oracle here (it is at
           :20/:22); this sentence is about retargeting cost.
       (b) NAMING + MECHANISM (T2; agent-verified, arXiv:2508.05186, CVPR 2026): the
           framework is named TAVP (the thesis calls it "TVVE"); the manipulation action
           is produced by an END-TO-END LEARNED policy (RVT-2 + action head + TaskMoE),
           NOT a planner, and a SEPARATE RL policy (MVEP) selects viewpoints. "A learned
           policy that selects viewpoints before acting" blurs the two policies.
Fix:   (a) replace the limitation with "retargeting to a new goal requires new PDDL
           actions (+ streams), not just a new goal spec."
       (b) use the name TAVP (or drop the acronym) and state the action is an end-to-end
           learned policy (no planner), sharpening the contrast with our planner-based
           sensing; optionally note the viewpoint selector is a distinct RL policy.
Refs:  related-work.tex:24; bai2025learning (arXiv:2508.05186, "TAVP"); #205.

================================================================================
#188  [DONE] [T0] [NOW]  related-work.tex:27 belief-space paragraph: false SS-Replan contrast (+ jargon)
================================================================================
Where: related-work.tex:27 (Belief-Space Planning and Replanning).
What:  (1) FACTUAL ERROR (T0): the claim that our info-gathering is "composed
       \emph{within} a plan rather than emerging only across replans" misrepresents
       SS-Replan. SS-Replan DOES plan sensing actions within a single plan (its own
       example: opening a drawer to observe its contents) -- verified
       (garrett2020online paper + SS-Replan code). The real distinction is the
       REPRESENTATION (we name occluded volumes as first-class symbolic state) and
       the determinization/branching axis (SS-Replan uses max-likelihood-observation
       determinization + replanning), NOT within-plan vs across-replan sensing.
       (2) JARGON (T2): "introduced hierarchical planning in belief space"
       (kaelbling2013integrated) and "interleaves symbolic and geometric reasoning"
       (hadfield2015modular) are opaque; user asked what they mean. Both verified
       accurate and distinct (K&LP'13 = HPN goal regression over belief; HM'15 =
       MODULAR interface between an off-the-shelf classical planner and the
       geometric layer, max-likelihood-observation determinization).
Fix:   Replace the false contrast: state the contribution as the explicit named
       occlusion REPRESENTATION, and explicitly acknowledge SS-Replan also plans
       sensing within a plan (proposed text 2026-05-24). Rewrite the
       kaelbling/hadfield sentence in plain terms ("plan over the robot's belief
       using hierarchical goal regression"; "interleave" -> "exchange information
       as the plan is built"; note HM'15's modularity vs K&LP'13's bespoke planner).
       (3) WORDING: replace "What we add is orthogonal to the replanning loop" -- never
       use "orthogonal" outside a geometry context; say "separate from" / "independent
       of" the replanning loop.
Refs:  related-work.tex:27; garrett2020online; kaelbling2013integrated;
       hadfield2015modular; SS-Replan code.

================================================================================
#189  [T0] [NOW]  related-work.tex:30 overgeneralizes the knowledge-literal / compile-to-classical claim
================================================================================
Where: related-work.tex:30 (POD Planning subsection: "Partially observable
       deterministic (POD) planning represents knowledge with explicit knowledge
       literals and reduces the problem to classical planning by compilation").
What:  User: is that true, or only LW1? VERIFIED OVERGENERALIZED (agent): the
       knowledge-literal + compile-to-classical mechanism belongs to the
       TRANSLATION-BASED family (Palacios & Geffner conformant; CLG; K-replanner;
       LW1) -- NOT all deterministic partial-observability planning. Counterexamples:
       Contingent-FF / MBP search belief space directly (no K-literals, no classical
       compilation); the FOND route (muise2014computing) compiles to non-deterministic,
       not classical. Stated as a property of "POD planning" as a whole it is wrong.
Fix:   Scope the opening to the translation-based line: "A prominent line within it
       represents knowledge with explicit knowledge literals and reduces the problem
       to classical planning by compilation: CLG ... K-replanner ... LW1 ...". Add a
       clause that other such planners search belief space directly / compile to
       FOND. Rest of the paragraph (already names CLG/K-replanner/LW1/FOND) unchanged.
Refs:  related-work.tex:30; albore2009translation (CLG); bonet2011planning
       (K-replanner); bonet2014flexible (LW1); muise2014computing (FOND);
       geffner2013concise.

================================================================================
#190  [DONE 2026-05-25] [T0]  TAMPURA model-learning is ONLINE per-step (was framed "pays it offline")
================================================================================
CLOSED 2026-05-25.  The false "offline Learn-Model" framing was removed from
discussion.tex / results.tex:108 / conclusion.tex:10 and reconciled in
THESIS_NOTES section 21.3: both systems sample online per-step; the real
difference is TAMPURA's probabilistic learned-MDP (solved for a policy) vs our
deterministic knowledge-literal planning with replanning.  Code-verified against
tampura policy.py / tampura_policy.py / config/default.yml (from_scratch=true,
envelope_threshold=1).  (Working-tree edits applied; not yet committed.)
Parked follow-ons, NOT part of #190's offline fix:
  (a) LAO* vs value iteration -- the released code's solve_mdp defaults to value
      iteration, not LAO*; the prose still says "LAO*".
  (b) Per the user's reading of the paper PDF, the Table II times INCLUDE the
      selected controller's execution in simulation, so #177's "planning-time
      only / like-for-like = our planning time" framing is itself wrong (our
      wall-clock would be the closer analogue) -- pending confirmation.

# ISSUES ADDED 2026-05-24 (Methods/Results/Discussion/Conclusion + figures, batch 2, agent-verified): #191-#209. Code follow-ups: CODEBASE_AUDIT #106-#112.

================================================================================
#191  [T3] [THESIS]  Intro hero caption: identify the target object
================================================================================
Where: introduction.tex:19 (fig:intro-hero caption, sim/scene_hidden_target.png).
What:  Caption says the target "may be hidden behind others and must be located" but
       never says which object is the target in the image.
Fix:   Add "the target is the cyan cube behind the green cube." Verify against the
       image (cross #168) before committing.
Refs:  introduction.tex:19; #168.

================================================================================
#192  [MERGED 2026-05-25 into #187]  Bai et al.: TAVP naming + end-to-end-learned-policy
================================================================================
Folded into #187 (same related-work.tex:24 Bai et al. paragraph).

================================================================================
#193  [T1] [THESIS]  Relocate/shrink "Spatial Belief Representation in TAMP" into Background
================================================================================
Where: related-work.tex:39-52 (\section{Spatial Belief Representation in TAMP}: Octree
       limitations + Sidd's Critical Regions limitations); also related-work.tex:35
       ("Belief-space replanning [11] ... does not make occlusion a first-class
       planning entity").
What:  User: this whole section reads like BACKGROUND, not related work, and its point
       is unclear. The intended message is small: we drew on octrees and Critical
       Regions for inspiration, and neither was usable out of the box during research.
       Background already has the homes -- octrees (background.tex:140, see #182) and
       Critical Regions (background.tex:156). The belief-space-replanning sentence
       (related-work.tex:35) is also flagged as maybe-background, not related work.
Fix:   Merge necessary octree/CR LIMITATION content into the background octree +
       Critical-Regions subsections, then delete the related-work section, leaving at
       most a brief note that octrees and CRs were the two inspirations and neither was
       directly reusable. Decide where the belief-space-replanning point belongs (fold
       into the #188 paragraph or background).
Refs:  related-work.tex:39-52,35; background.tex:140,156; #182; #188.

================================================================================
#194  [T2] [POLISH]  Related-work framing: drop marketing voice; cut the over-long "three advantages" paragraph
================================================================================
Where: related-work.tex:35 ("This thesis sits at the intersection ...");
       related-work.tex:37 (the "three concrete advantages ... each carrying a cost we
       state plainly" paragraph).
What:  (H) "sits at the intersection" is marketing language -- prefer plain "we extend
       / build upon". (I) the three-advantages paragraph is far too long (one dense
       block restating occlusion-as-state / no-probabilities / no-MDP with costs).
Fix:   :35 -> "We build on / extend ..." (state plainly what is extended). :37 ->
       condense to a few short sentences or a compact list; the long version is
       redundant with the summary elsewhere.
Refs:  related-work.tex:35,37.

================================================================================
#195  [T2] [NOW]  Methods clarity: rephrase "optimistic determinisation", explain "untyped STRIPS", delete a self-justification
================================================================================
Where: methods.tex:63 ("solve the result by optimistic determinisation and reactive
       replanning"); methods.tex:87,90 ("the implemented domain is untyped STRIPS";
       "Category predicates (untyped domain)"); methods.tex:133 ("optimistic planning
       with replanning on failure is a standard pattern for TAMP under partial
       observability").
What:  (O) "optimistic determinisation and reactive replanning" is opaque. (P) "untyped
       STRIPS / untyped domain" is unexplained. (Q) the "...is a standard pattern..."
       clause is an unnecessary self-justification.
Fix:   (O) rephrase, e.g. "we assume each sensing action succeeds (optimistic), plan as
       if the world were fully known, execute, and replan whenever an observation
       contradicts that assumption (reactive replanning)". (P) add a one-line gloss:
       untyped STRIPS = no PDDL type declarations, so object categories are ordinary
       predicates rather than types. (Q) delete the "standard pattern" clause -- no need
       to justify/apologize.
Refs:  methods.tex:63,87,90,133.

================================================================================
#196  [MERGED 2026-05-25 into #176]  Free-space generation stages (split -> convex merge) figure
================================================================================
Folded into #176 (overlapping discretization-progression figure).  Content: a
methods.tex figure of the free-space build -- (1) all space incl. objects, (2)
recursive octree split, (3) recursive convex merge -- via tools/render_thesis_figs.py.

================================================================================
#197  [T1] [NOW]  fig:replan-cycle caption is wrong vs the image
================================================================================
Where: methods.tex:145 (fig:replan-cycle caption, sim/replan_cycle.png).
What:  User: the caption ("the action log reads 'sense shadow_of_purple_object ---
       target not here' ... marks that shadow empty ... searching only the remaining
       shadows") does NOT match what the image shows.
Fix:   Inspect sim/replan_cycle.png (cross #168), then rewrite the caption to match the
       actual logged action / scene; recapture if the image itself is wrong.
Refs:  methods.tex:145; sim/replan_cycle.png; #168.

================================================================================
#198  [T3] [THESIS]  Figure captions/sizes to fix after visual inspection
================================================================================
Where: methods.tex:27 (fig:boxelization-real, sim/boxelization_real.png);
       methods.tex:40-57 (fig:partition-comparison: partition_semantic vs
       partition_uniform); results.tex:79 (eval-scene fig: oracle/RGB-D caption);
       discussion.tex:293 (fig:retry-giveup, sim/sense_fail_retry3.png).
What:  (M, :27) update caption by looking at the current image. (N, :40-57) make the two
       subfigures EQUAL SIZE; update caption; briefly state what each colour means.
       (T+U, results:79) "objects and their occlusion shadows are labelled in the
       overlay" is unclear and the figure needs a new image; rewrite after inspection.
       (AV, discussion:293) the "retry 3/3" caption is stale -- re-inspect and update.
Fix:   Inspect each PNG (cross #168), then recaption / resize / recapture. ADD any
       regenerated image; never overwrite; keep old regenerable.
Refs:  methods.tex:27,40-57; results.tex:79; discussion.tex:293; #168.

================================================================================
#199  [T2] [THESIS]  Rename task terms to reader-facing names (drop code terms)
================================================================================
Where: document-wide -- results.tex (task defs ~:100s, plots, captions), discussion,
       conclusion, abstract, methods. Code terms: holding, stack, find-and-tray-stack.
What:  User: the code task names are confusing in prose. Use FIND (= holding; locate a
       hidden object and pick it), STACK, and FIND AND STACK (= find-and-tray-stack).
       (pick is essentially holding.)
Fix:   Global rename in PROSE: holding -> find; find-and-tray-stack -> find and stack;
       stack stays. Keep figure FILE names as code artifacts; rename only reader-facing
       text + captions + axis labels (axis labels may need a plotter label map -- see
       CODEBASE). Audit-internal refs in #177/#190 keep "holding" (bookkeeping only).
Refs:  results.tex; discussion.tex; conclusion.tex; abstract.tex; methods.tex; #177.

================================================================================
#200  [T0] [NOW]  results:83 "well under a second per call" is FALSE
================================================================================
Where: results.tex:83 ("Most successful cells finish in well under a second per call;
       the budget exists to catch pathological cases rather than as the operating
       point.").
What:  DATA-CONTRADICTED (eval_results/sweep_anytime, agent). Pooled per-call planning
       time over successful cells: median ~1.99 s, mean ~5.4 s; only ~19% of calls
       < 1 s. By goal: stack median 0.97 s (54% <1s) -- the only goal near the claim;
       find(=holding) 2.05 s (10% <1s); find-and-stack 2.97 s (3% <1s). Also "budget
       exists to catch pathological cases rather than as the operating point" is unclear.
Fix:   Replace with real per-goal medians; describe the 1800 s cap as a safety bound hit
       only by rare pathological/timeout cells, not the typical runtime. Drop "well under
       a second".
Refs:  results.tex:83; eval_results/sweep_anytime (per_call_planning_time_s).

================================================================================
#201  [T2] [THESIS]  Results clarity: drop_failed, denominator note, "known to be empty", one-boxel-per-object
================================================================================
Where: results.tex:96 (failure-mode list); results.tex:98 ("two denominators differ by
       ~6%"); results.tex:105 ("where the workspace is empty"; "finer leaves break
       placement on the table dimensions used here").
What:  (Y) drop_failed listed with no explanation. (Z) "the two denominators differ by
       ~6% of cells (early timeouts without a recorded state)" is opaque. (AA) "where the
       workspace is empty" should be "where the workspace is KNOWN to be empty" (belief,
       not ground truth). (AC) "finer leaves break placement ... used here" is stated as
       self-evident but is a design choice (each object is bounded by exactly ONE boxel,
       so a finer free-space leaf can split a placement target).
Fix:   (Y) explain: when the gripper cannot release a non-target object it would hold it
       forever; after three failed drop events the episode exits (drop_failed). (Z)
       rephrase plainly. (AA) add "known to be". (AC) explain the one-boxel-per-object
       design choice. Y depends on the CODEBASE taxonomy change (#106).
Refs:  results.tex:96,98,105; CODEBASE_AUDIT #106.

================================================================================
#202  [T1] [THESIS]  semantic+mbs0.05 is effectively identical to semantic (a no-op variant)
================================================================================
Where: results.tex:106 ("semantic+mbs0.05 --- the same adaptive partition but with the
       free-space leaf-size floor forced to 5 cm ... test the effect of a finer
       free-space leaf floor").
What:  DATA-CONFIRMED (agent): semantic+mbs0.05 produces boxel counts identical to plain
       semantic to ~0.1% (e.g. find 35.07 vs 35.03) and the same results. The 5 cm floor
       never meaningfully binds (autosize ~6-9 cm) and finer floors are absorbed by the
       greedy convex merge (#203). Presenting it as "testing a finer floor" is misleading
       -- it has no effect.
Fix:   Drop the variant or reframe it honestly as evidence that the free-space floor does
       NOT change the partition (merge dominates), not as an independent resolution probe.
       Coordinate with #203 and CODEBASE #108.
Refs:  results.tex:106; eval_results/sweep_anytime; #203; CODEBASE_AUDIT #108.

================================================================================
#203  [T0] [NOW]  discussion:60 "at the cost of more cells" is FALSE; "characterisation of the regime" is empty
================================================================================
Where: discussion.tex:60 ("... at the cost of more cells in the partition. This is a
       characterisation of the regime, not a defect of the method.").
What:  (AK) DATA-CONTRADICTED (agent): a finer free-space floor does NOT add cells -- free
       cells are greedily convex-merged, so counts are essentially identical across
       semantic / mbs0.05 / mbs0.09 (e.g. stack free-space boxels 17.64 in all three);
       only COARSER floors reduce counts. So "finer resolution -> more cells" is wrong;
       the minimum size barely matters. (AL) "This is a characterisation of the regime,
       not a defect of the method" is empty filler.
Fix:   Correct the claim: the minimum free-space leaf size has little effect on cell count
       because of the convex merge (data); only coarsening reduces it. Delete the
       "characterisation of the regime" sentence. Supporting figure: CODEBASE #108.
Refs:  discussion.tex:60; eval_results/sweep_anytime; #202; CODEBASE_AUDIT #108.

================================================================================
#204  [T2] [THESIS]  discussion:24 stack-goal boxel ratio -- stack needs no free-space partition
================================================================================
Where: discussion.tex:24 ("On the stack goal the ratio is steeper (semantic ~25 vs
       uniform ~1340) ...").
What:  User: the stack goal is fully observable and needs no free-space partitioning, so
       the semantic-vs-uniform free-space cell ratio is not a meaningful comparison there.
Fix:   Either drop the stack-goal ratio, or state explicitly that stack is fully
       observable (no shadows) so the ratio only reflects the uniform baseline's
       free-space blow-up, not a partial-observability benefit.
Refs:  discussion.tex:24.

================================================================================
#205  [T0] [NOW]  discussion:266 stacking slowdown misattributed (bigger domain, not pick conditional-effects)
================================================================================
Where: discussion.tex:266 ("Enabling stacking roughly doubles per-call planning time,
       traced to the conditional-effects requirement on the pick action").
What:  CODE-CONTRADICTED (agent, git). Commit 0d5def7 "add --goal stack" added, all at
       once: a whole new \texttt{stack} action (7 preconds/6 effects), 3 new predicates
       (on, clear, stack_kin), a new stream compute-stack-kin (+stream.pddl/python), AND
       the conditional :requirement + a forall-when on pick. The conditional effect grounds
       to a no-op on find/holding runs (no (on ...) facts). So the slowdown is a LARGER
       DOMAIN (added action + predicates + stream), not specifically pick conditional effects.
Fix:   Re-attribute: enabling stacking enlarges the domain (an added stack action,
       predicates, and stream), raising grounding/search cost; do not pin it on the pick
       conditional effect.
Refs:  discussion.tex:266; pddl/domain_pddlstream.pddl; git 0d5def7.

================================================================================
#206  [T2] [THESIS]  Discussion section-6 trims and clarity
================================================================================
Where: discussion.tex -- :121 (restoring-blocked-view give-up clause), :123
       (\section{Failure modes}), :168 ("the ratio would narrow"), :239 (IK-bypass
       sentence), :245 ("non-pathological start configuration"), :258 (string-identifier
       proxies sentence), :268 (regression-accepted sentence).
What:  User edits: (AO) delete the entire \section{Failure modes} (:123) -- it duplicates
       the results failure-mode coverage. (AN) remove the :121 "restoring a blocked view
       ... give-up rule" trailing clause. (AQ) remove the :239 "final approach uses a local
       IK solver that bypasses collision checks ..." sentence. (AS) remove the :258 "string
       identifiers as proxies for geometric volumes ..." sentence. (AU) remove the :268
       "this regression is accepted rather than optimized away ..." sentence. (AP) :168 "the
       ratio would narrow" -> "could narrow". (AR) :245 explain "non-pathological start
       configuration" plainly (a collision-free start configuration for the next move, to
       avoid collisions).
Fix:   Apply the deletions + two wording fixes (over-explanation / over-hedging / apology
       the author wants gone).
Refs:  discussion.tex:121,123,168,239,245,258,268.

================================================================================
#207  [T3] [THESIS]  Success-rate-vs-n_occ caption should state what the band is
================================================================================
Where: results.tex (fig success rate vs n_occ).
What:  Verified (agent, eval_plotter): the shaded band is +/-1 SAMPLE STD of the per-trial
       0/1 success flags across ~80-100 corpus seeds per (variant, n_occ) point (clipped to
       [0,1]) -- NOT a confidence interval. The spread is the binomial noise of a success
       rate over a modest seed count; uniform sits near 0 (low spread), adaptive varies more.
Fix:   State in the caption that the band is +/-1 std of the per-trial success indicator over
       N~80-100 seeds (not a CI). Optionally switch to a Wilson interval (CODEBASE #112).
Refs:  results.tex; eval_plotter.py (group_success_rate, plot_metric); CODEBASE_AUDIT #112.

================================================================================
#208  [T3] [THESIS]  Add the code repository links (GitHub + GitLab)
================================================================================
Where: thesis front matter / introduction / an appendix or footnote (author's choice).
What:  The thesis does not mention where the implementation lives. The code is in a GitHub
       and a GitLab repository.
Fix:   Add the GitHub + GitLab URLs (author to PROVIDE the exact URLs -- do not guess) as a
       code-availability footnote/statement.
Refs:  introduction.tex / abstract.tex / appendix.tex.

================================================================================
#209  [T2] [THESIS]  Results: resolution-floor sweep -- effect of min free-space leaf size on total boxel count
================================================================================
Where: results.tex (Representation compactness, subsec:compactness ~:194; a new
       subsection + figure). Supplies the evidence for #203 (discussion.tex:60) and
       justifies the #202 variant framing.
What:  ADD a results study of how the free-space resolution floor (min_boxel_size)
       changes the TOTAL boxel count, swept BELOW and ABOVE autocell:
       <autocell (mbs0.05), autocell, 1.5x autocell, 2x autocell. (User: "what effect
       does increasing or decreasing have on our boxel count".)
       DATA already in eval_results/sweep_anytime/aggregated.csv (mean total boxels,
       baseline=semantic, 300 cells/arm; the 1.5x/2x arms = CODEBASE #100):
         find-and-stack: 0.05 -> 45.05 | auto(0.09) -> 44.95 | 1.5x(0.135) -> 26.96 | 2x(0.18) -> 26.59
         find (holding): 0.05 -> 35.03 | auto(0.09) -> 35.07 | 1.5x(0.135) -> 20.39 | 2x(0.18) -> 20.16
         stack:          0.05 -> 27.79 | auto(0.06) -> 27.79 | 1.5x(0.09) -> 27.79 | 2x(0.12) -> 22.24
       FINDING (data-confirmed 2026-05-24): going FINER than autocell does NOT add
       cells -- the greedy convex merge re-absorbs the finer leaves (mbs0.05 sets a
       strictly finer floor, 0.05 vs auto 0.09 on random-pairs, yet total is
       unchanged). Going COARSER (>= ~1.5x auto) reduces the count sharply. So the
       minimum free-space size matters only on the COARSE side; autocell is the
       natural operating point. (Object + shadow counts are unchanged at every floor
       -- the floor touches only free space. Stack 1.5x=0.09 still equals auto because
       stack autocell is already 0.06; the floor bites only at 2x=0.12.)
Fix:   Add a short results subsection + figure (figure generated by CODEBASE #108):
       total boxel count vs resolution floor (as a multiple of autocell), per goal.
       State the finding plainly: finer = no change (merge dominates), coarser = fewer
       cells. Optionally add a literal mbs0.1 point (CODEBASE #108 runs it). Coordinate
       with #202/#203 so the three do not repeat each other.
Refs:  results.tex:194 (subsec:compactness); discussion.tex:60; #202; #203;
       CODEBASE_AUDIT #108 (plot + mbs0.1 arm), #98/#100/#101 (resolution sweep data +
       eval-chapter writeup); eval_results/sweep_anytime/aggregated.csv.

--------------------------------------------------------------------------------
NB (verified, NO issue filed):
 - discussion.tex:121 "an object can be placed view-blind" (TAMPURA) is TRUE -- verified
   2026-05-24 from TAMPURA's find_dice code: the placement sampler is uniform x/y + random
   yaw with no visibility check, and the place action has no visibility precondition. The
   claim stands; optionally add a one-line basis ("evident from their released placement
   sampler"). [code-confirmed]

================================================================================
OPEN ISSUES
================================================================================

After the 2026-05-23 prose + citation-accuracy pass, 1 issue remained open
(#168); a 2026-05-24 follow-up (#175) tracks methods-text reconciliation after
CODEBASE_AUDIT #102/#103. A second 2026-05-24 pass -- a user read-through of
sections 1-3, agent-verified -- added #178-#189 (intro/background/related-work
prose + citation accuracy).
Each issue's header carries its tier (T0-T3) and disposition.
The nine issues resolved in that pass (#164 #166 #167 #169 #170 #171 #172 #173 #174)
have been removed; see `git log --grep="Fix #"` (thesis repo) and
`git log --grep="audit:"` (this repo) for their record.

OPEN:
  Figures: #168  (every figure one-by-one; figures agent)
  Figures: #176  (discretization-progression figure + free-space split->merge stages, merged #196; captures archived)
  Methods: #175  (shadow-splitting prose vs #102/#103 code; prose)
  Intro: #178 (partition omits free space; T1/NOW), #179 (de-hype TAMPURA + cut "first-class" opener)
  Background: #180 (Pi/S(P) notation), #181 (name "contingent planning"), #182 ("Voxel Grids" heading)
  Related Work: #184 (pan "behaviors"),
                #185 (Ma paragraph rewrite), #186 (CoCo-TAMP expand), #187 (Bai et al.: limitation + TAVP name/learned-policy; merged #192; T1/NOW),
                #189 (POD K-literal overgeneralized; T0/NOW)
  --- batch 2 (sections 4-7 + figures, 2026-05-24) ---
  Intro/RW: #191 (hero caption target), #193 (move Spatial-Belief section to background; T1), #194 (marketing voice + over-long paragraph)
  Methods: #195 (optimistic-determinisation/untyped/standard-pattern clarity), #197 (replan-cycle caption wrong; T1/NOW)
  Figures: #198 (boxelization-real/partition-comparison/eval-scene/give-up captions+sizes)
  Results: #199 (task rename find/stack/find-and-stack), #200 (per-call <1s FALSE; T0/NOW), #201 (drop_failed/denominator/known-empty/one-boxel clarity), #202 (mbs0.05 no-op; T1), #207 (success-rate band caption), #209 (resolution-floor vs total-boxel-count study + figure)
  Discussion: #203 ("more cells" FALSE + characterisation; T0/NOW), #204 (stack ratio mention), #205 (stacking slowdown misattributed; T0/NOW), #206 (section-6 trims + deletions)
  Conclusion/front: #208 (add GitHub+GitLab code links)

Gating: #141-#156 and #130 done --- all eval-write-up
content (Results, Discussion, abstract + conclusion closure) is in
thesis/, the chapters are clear of internal file-path and hardware-spec
clutter, the front/back matter (submission date, PDDL appendix) is in
place, curated screenshots are in thesis/graphics/sim/, and nine sim
figures (boxelization companion, semantic vs uniform, sense action,
replan cycle, three-strike give-up, task triptych, n_occluders composite,
overhead-camera inset, introduction hero) are inserted across
introduction/methods/results/discussion. #125, #140, #121, #127 were closed jointly.
#126 (document-wide forward-voice conversion) was verified and closed: the
chapters are already retrospective throughout, so no source change was needed. The §5 sentence-level polish issues (#87-#111) were
resolved earlier in the audit walkthrough.
