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


################################################################################
#  ISSUE --- ADDED 2026-05-23  (FIGURES / CAPTIONS REVIEW)
################################################################################
Surfaced 2026-05-23: the figures need a dedicated pass. Several either do not
show what their caption / surrounding text claims, or are not the clearest
illustration of the concept. Go through them ONE BY ONE. OPEN.

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
#176  [T3] [THESIS]  Real discretization-progression figure (PyBullet captures)
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
#177  [DONE] [T0] [NOW]  TAMPURA comparison: wrong task cited + self-contradicts on the analogue
================================================================================
Where: abstract.tex:14-17 ("closest analogue ... 14.0 s vs 57 s" headline);
       results.tex:209-216 (subsec:tampura, fig:tampura; "find-and-tray-stack,
       the closest analogue", 14.0 s, n=119, ~4x); discussion.tex:70-94 (14.0 s
       on find-and-tray-stack) vs discussion.tex:101 (already calls TAMPURA's
       Find Die "the closest analogue to our setting"); the plot in
       eval_plotter.py plot_tampura_wallclock_comparison (goal filter =
       find-and-tray-stack). TAMPURA = curtis2024partially, Tables I-II.
What:  The thesis contradicts itself AND compares the wrong task.
       (1) SELF-CONTRADICTION: abstract/results/discussion:70 call our FIND-AND-
           TRAY-STACK "the closest analogue" to TAMPURA's Partial Observability
           (find_dice); but discussion:101 already calls find_dice "the closest
           analogue to OUR setting". find_dice (find a hidden object, pick it, go
           home) IS our HOLDING task -- not find-and-tray-stack, which adds trays
           + stacking (strictly more). The figure/abstract/results compare the
           wrong, harder task.
       (2) TIME-MEASURE CATEGORY ERROR: ours (14.0 s) is per-episode WALL-CLOCK
           incl. PyBullet execution + replanning (eval_runner.py wall_clock_s);
           TAMPURA's 57+-38 s (Table II) is PLANNING TIME ONLY (table caption:
           "...planning times..."). Different spans -> the "~4x" delta is not
           like-for-like. Our planning-only analogue is total_planning_time_s
           (holding semantic mean 7.78 s).
       (3) RELIABILITY FRAMING BACKWARDS: no success rate sits beside the time,
           and TAMPURA is MORE reliable, not less. TAMPURA reports discounted
           return 0.63+-0.30 (Table I, gamma=0.98) under a binary terminal reward
           -> success >= 63 %; our holding-semantic success is ~42 %. We are the
           LESS-reliable side; any "faster/better" reading misleads.
Fix:   Re-point the figure + abstract:14-17 + results:209 + discussion:70-94 to
       HOLDING (the find_dice analogue), aligning them with discussion:101;
       re-derive the number from holding rows (do NOT reuse 14.0 s / "~4x").
       Show BOTH our wall-clock AND our planning-time vs TAMPURA's planning-only
       57 s (decided 2026-05-24). State success on both sides (ours ~42 %; TAMPURA
       >= 63 %, derived) and frame honestly: architectural difference (probabilistic learned-MDP +
       LAO* vs deterministic K-literal classical planning + replanning; both
       sample ONLINE -- it is NOT offline-vs-online, that premise is WRONG, see
       #190), NO speed/quality winner -- we are
       cheaper-to-plan but less reliable and on a slightly less-constrained task
       (find_dice goal = holding AND at-home; ours is holding only). Plot:
       eval_plotter.py plot_tampura_wallclock_comparison -- switch goal filter
       find-and-tray-stack -> holding, add the planning-time series, drop "20-core"
       from the caption (the single-threaded framing in discussion:158 and the
       SymK wording in discussion:84-87 are already correct). Reconcile
       THESIS_NOTES §21 the same turn. Data in eval_results/sweep_anytime/ --
       holding rows already exist, no eval RUN needed.
Refs:  abstract.tex; results.tex (subsec:tampura, fig:tampura); discussion.tex
       (70-101, 158); eval_plotter.py; eval_runner.py (wall_clock_s);
       notes/THESIS_NOTES.md §21; curtis2024partially (arXiv:2403.10454, Tables
       I-II); reference_tampura_perf.md (memory). Was notes/TAMPURA_PLAN.md T1,
       moved here 2026-05-24.

################################################################################
#  ISSUES --- ADDED 2026-05-24  (INTRO / BACKGROUND / RELATED-WORK READ-THROUGH)
################################################################################
Surfaced 2026-05-24 from a user read-through of sections 1-3 against a freshly
compiled main.pdf. Factual claims about TAMPURA/Bayes3D, the "POD" label, and the
cited related work were verified by three research agents (TAMPURA/Bayes3D from
the local tampura + tampura_environments code AND both papers; the POD/contingent
literature; the pan/ma/CoCo-TAMP/SS-Replan/kaelbling/hadfield papers). Two of the
user's instincts caught real errors (#183 scaling claim, #188 SS-Replan contrast).
OPEN.

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
#183  [T0] [NOW]  related-work.tex:12 mischaracterizes Bayes3D scaling; clarify TAMPURA belief source
================================================================================
Where: related-work.tex:12 (POMDP-based TAMP subsection: "TAMPURA samples
       placements in continuous pose space and draws its object-pose belief from
       its perception front-end, Bayes3D ... sequential Monte Carlo over rendered
       scene hypotheses. Such sampling-heavy posterior representations tend to
       scale poorly as the number of hypotheses and objects grows.").
What:  (1) FACTUAL ERROR: "scale poorly as #hypotheses/objects grows" is wrong --
       Bayes3D is explicitly GPU-PARALLEL (renders+scores ~2048 scene hypotheses
       in parallel) precisely to avoid sequential blow-up (paper-confirmed). The
       sequential-scaling criticism does not hold. (2) UNCLEAR: "sequential Monte
       Carlo over rendered scene hypotheses" needs a plain gloss. (3) PRECISION:
       Bayes3D is TAMPURA's REAL-ROBOT front-end; the released Find-Die SIM uses
       ground-truth segmentation + a visibility voxel grid (code-confirmed), so
       "draws its belief from Bayes3D" should be scoped to the real-robot pipeline.
Fix:   Drop the "scale poorly" sentence. Reword: "TAMPURA samples object placements
       in continuous pose space and, in its real-robot pipeline, draws its
       object-pose belief from a perception front-end, Bayes3D: a generative
       inverse-graphics model that infers a posterior over 3D scenes by rendering
       candidate object arrangements and scoring them against the observed depth
       image." If a fair critique is wanted, it is render/memory cost of holding
       many full-scene hypotheses -- NOT sequential scaling.
Refs:  related-work.tex:12,37; curtis2024partially; gothoskar2023bayes3d; local
       tampura/tampura_environments code.

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
#187  [T1] [NOW]  related-work.tex:24 states the wrong limitation ("hardcoded geometric constants")
================================================================================
Where: related-work.tex:24 (end of Bai et al. paragraph: "adapting it to a new
       environment, however, currently requires re-tuning hardcoded geometric
       constants").
What:  User: this is not our real limitation -- mention the ORACLE instead. Our
       actual current limitation (stated elsewhere: related-work.tex:20,22,
       introduction.tex, sec:limitations) is that visibility / object poses come
       from a ground-truth oracle, not a learned perception module.
Fix:   Replace "...requires re-tuning hardcoded geometric constants" with the
       oracle limitation: "...its current limitation lies elsewhere -- the
       visibility signal it relies on is supplied by a ground-truth oracle rather
       than a learned perception module (\cref{sec:limitations})." Avoid verbatim
       repeat of :20/:22 wording.
Refs:  related-work.tex:24,20,22; sec:limitations.

================================================================================
#188  [T0] [NOW]  related-work.tex:27 belief-space paragraph: false SS-Replan contrast (+ jargon)
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
#190  [T0] [NOW]  "TAMPURA pays it offline" -- WRONG; its model-learning is ONLINE (per-step)
================================================================================
Where: discussion.tex:76-99 (sec:disc-tampura -- :77 "TAMPURA pays it offline in a
       Learn-Model phase", :81-82 "done once per problem and amortised", :94 "the
       offline-MDP architecture ... without front-loading", :96 "the offline
       architecture must estimate"); results.tex:108 ("the comparison is
       architectural -- offline Learn-Model vs online stream sampling");
       conclusion.tex:10 ("TAMPURA front-loads it offline; PDDLStream pays it per
       call").
What:  FALSE PREMISE. Code-verified 2026-05-24 against the local tampura repo (the
       same released code whose find_dice = our holding analogue). TAMPURA's
       model-learning (outcome sampling -> sparse abstract MDP) is NOT offline; it
       runs ONLINE, inside the per-timestep control loop, rooted at the CURRENT
       belief, rebuilt from scratch by default:
       - policy.py:105-120 rollout() loops over timesteps; each step calls
         get_action() THEN env.step() (real execution).
       - tampura_policy.py:120-145 get_action() runs the Outcome Sampling loop
         (policy_search -> builds transition model F + reward R), then solves the
         MDP with LAO*/VI (:149-168) and returns ONE action.
       - default.yml: from_scratch=true + envelope_threshold=1 => model re-learned
         at virtually every step (the envelope can be reused only when the realized
         transition had probability 1; stochastic sensing in find_dice invalidates
         it each step).
       The "envelope" (tampura_policy.py:82-99) is an ONLINE cache reusing the last
       solved policy while the plan stays on-track -- NOT an offline phase. The
       paper's "mental simulation" (Algorithm 2) describes HOW outcomes are sampled
       (in imagination vs on the real robot), not WHEN -- it is not evidence of
       offline timing. So the discussion's central axis -- "the real difference is
       WHEN sampling is paid: TAMPURA offline vs us online" -- COLLAPSES: both
       sample online. "done once per problem" is also wrong for find_dice
       (re-sampled per step).
Fix:   Drop the offline/online "when is sampling paid" framing in all three places
       (discussion:76-99, results:108, conclusion:10). Reframe the real
       architectural difference: TAMPURA learns a PROBABILISTIC sparse MDP at
       planning time and solves it with LAO* for a risk-aware policy; ours uses
       DETERMINISTIC classical planning with knowledge literals + optimistic
       replanning (no outcome-probability model, no MDP solve). Both sample online
       inside a Fast Downward-derived loop (already noted at discussion:84-87), so
       any 14.0s-vs-57s gap reflects MDP-learning+LAO* machinery vs lightweight
       classical replanning, NOT offline vs online. CAUTION: this may require
       rethinking the wall-clock ARGUMENT, not just rewording -- author to decide
       the honest new framing. Invalidates the framing #177 prescribes (now fixed
       there); also correct memory reference_tampura_perf.md. Reconcile
       THESIS_NOTES if it repeats the offline claim.
Refs:  discussion.tex:76-99; results.tex:108; conclusion.tex:10; #177;
       tampura/tampura/policies/policy.py:105-120,
       policies/tampura_policy.py:82-168, config/default.yml;
       curtis2024partially (Alg 1/2); reference_tampura_perf.md (memory).

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
  Figures: #176  (optional real discretization-progression figure; captures archived)
  Methods: #175  (shadow-splitting prose vs #102/#103 code; prose)
  Results/Disc/Concl: #190 (TAMPURA "offline" model-learning is WRONG -- it's online per-step; T0/NOW; #177's task/number/success part now DONE)
  Intro: #178 (partition omits free space; T1/NOW), #179 (de-hype TAMPURA + cut "first-class" opener)
  Background: #180 (Pi/S(P) notation), #181 (name "contingent planning"), #182 ("Voxel Grids" heading)
  Related Work: #183 (Bayes3D scaling claim wrong + belief source; T0/NOW), #184 (pan "behaviors"),
                #185 (Ma paragraph rewrite), #186 (CoCo-TAMP expand), #187 (oracle not "hardcoded constants"; T1/NOW),
                #188 (SS-Replan false contrast + jargon; T0/NOW), #189 (POD K-literal overgeneralized; T0/NOW)

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
