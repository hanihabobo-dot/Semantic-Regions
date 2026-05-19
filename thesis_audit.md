================================================================================
THESIS AUDIT — OPEN ISSUES
================================================================================
Date:   2026-05-16
Target: the Master-thesis proposal in proposal-template/ ("main.pdf", 20 pages),
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
after each fix, an individual commit in the proposal-template/ repo, then mark
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

SECTION -> SOURCE FILE  (all paths under proposal-template/)
   Abstract         sections/abstract.tex
   §1 Introduction  sections/introduction.tex
   §2 Background    sections/background.tex
   §3 Related Work  sections/related_work.tex
   §4 Approach      sections/approach.tex
   §5 Evaluation    sections/evaluation.tex
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
#  ISSUES — §2 BACKGROUND  (sections/background.tex)
################################################################################

================================================================================
#46  [T2 · Style] [POLISH]  "This representation underpins both motion planning ... and task planning"
================================================================================
Where: §2.4 — background.tex:133
What:  "This representation underpins both motion planning (navigating and
       avoiding collisions) and task planning (reasoning about object
       interactions and achieving goals)." Asserts a vague dependency; carries
       no usable information.
Fix:   Delete it — the next sentence (on partial observability) carries the real
       point.

================================================================================
#47  [T2 · Style] [POLISH]  "becomes even more acute"
================================================================================
Where: §2.4 — background.tex:133
What:  "The challenge of spatial representation becomes even more acute under
       partial observability..." Inflated phrasing for "is harder."
Fix:   "Representing space is harder under partial observability, because the
       robot must also represent what it does not yet know."


################################################################################
#  ISSUES — §3 RELATED WORK  (sections/related_work.tex)
################################################################################

================================================================================
#49  [T2 · Style] [POLISH]  Related Work opener — third sentence is filler
================================================================================
Where: §3 — related_work.tex:5
What:  "...This section reviews previous work on this topic... We examine the
       limitations of current methods to provide context for our work." The
       third sentence states what every related-work section does.
Fix:   Keep the first two sentences, drop the third (or fold it in:
       "...focusing on planning approaches and belief representations, and on
       where each falls short").

================================================================================
#50  [T3 · Scientific] [NOW]  TAMPURA description slightly imprecise
================================================================================
Where: §3.1.1 — related_work.tex:11
What:  "TAMPURA ... makes this approach more tractable by learning a simplified,
       abstract model of the problem. The planner then chooses from a library of
       pre-defined controllers..." It is the abstract preconditions/effects of
       the (given) controllers that are learned, and the result is a
       non-deterministic MDP solved by an uncertainty-aware solver (LAO*).
Fix:   "TAMPURA learns a coarse abstract model of each given closed-loop
       controller's preconditions and effects, builds a non-deterministic MDP,
       and solves it with an uncertainty-aware solver (LAO*) to produce
       risk-aware, information-gathering plans."
Refs:  #116 (missing LAO* citation)

================================================================================
#51  [T2 · Style] [POLISH]  "offers a semantically grounded framework for abstracting planning challenges"
================================================================================
Where: §3.2.2 — related_work.tex:39
What:  "The method proposed in [shah2022abstractions] for learning a global set
       of task-relevant Critical Regions (CRs) offers a semantically grounded
       framework for abstracting planning challenges." Abstract and ornate;
       "abstracting planning challenges" is vague jargon.
Fix:   "The Critical Regions method [shah2022abstractions] learns a global set
       of task-relevant regions, giving the planner a meaningful, non-uniform
       way to abstract the space."

================================================================================
#52  [T2 · Style] [POLISH]  "may prove inadequate" — hedged academic-ese
================================================================================
Where: §3.2.2 — related_work.tex:39
What:  "However, in dynamic manipulation scenarios involving specific objects,
       this global and often static partitioning may prove inadequate."
Fix:   "But this partitioning is global and mostly fixed, so it does not work
       well when objects move."

================================================================================
#53  [T2 · Style] [POLISH]  "struggles to accommodate" — repeats the prior sentence
================================================================================
Where: §3.2.2 — related_work.tex:39
What:  "A pre-defined or globally fixed CR map struggles to accommodate such
       dynamic, object-specific uncertainties." Abstract academic-ese; largely
       repeats the sentence before it.
Fix:   Merge with the previous sentence or cut: "...for example, the region
       \"behind object A\" depends on where A currently is and where the robot
       is standing — a fixed map cannot track that."

================================================================================
#54  [T2 · Over-claim] [THESIS]  §3 "reason directly about what it can and cannot see"
================================================================================
Where: §3.1.3 — related_work.tex:20
What:  Contrasting with Ma et al.: "...This allows our planner to reason
       directly about what it can and cannot see..." The visibility judgement
       is computed by an oracle (ray-casting against ground-truth bodies); the
       planner reasons over symbolic boxel facts, not raw sensor data.
Fix:   "...reason about which regions are observed versus occluded as
       first-class planning state" — and note the visibility signal is
       currently oracle-provided. Keep the (accurate) point that
       information-gathering is a core planner action.
Refs:  THESIS_NOTES §1, §11

================================================================================
#56  [T1 · Deviation] [THESIS]  §3 "applied to new ... environments without needing to be retrained" overstates generality
================================================================================
Where: §3.1.3 — related_work.tex:24
What:  Contrasting with Bai et al.: "...can be applied to new goals and
       environments without needing to be retrained." "No retraining" is true,
       but "new environments" implies portability the build lacks: hardcoded
       constants overfit it to one table, the Franka Panda, and the test
       objects (grasp offsets, approach/lift heights, octree resolution, camera
       pose).
Fix:   "...can be retargeted to new goals without retraining a policy" — and
       acknowledge that a new environment currently requires re-tuning hardcoded
       geometric constants (a generalization future-work item).
Refs:  THESIS_NOTES §3, §13


################################################################################
#  ISSUES — §4 APPROACH  (sections/approach.tex)
################################################################################

================================================================================
#57  [T2 · Style] [POLISH]  §4 chapter opener — filler "aims to create" sentence
================================================================================
Where: §4 — approach.tex:6
What:  "The approach aims to create a tractable yet expressive system for
       planning under spatial uncertainty." Restates the goal already implied;
       "tractable yet expressive" is an empty virtue-pairing.
Fix:   Delete it, or fold the one real word into the prior sentence.


################################################################################
#  ISSUES — §5 EVALUATION PLAN  (sections/evaluation.tex)
################################################################################

================================================================================
#87  [T1 · Deviation] [THESIS]  §5.3 "Fixed Semantic Regions" baseline does not exist — it was killed
================================================================================
Where: §5.3 — evaluation.tex:26
What:  §5.3 lists three baselines and describes the second as live: "Fixed
       Semantic Regions: A baseline using a fixed, pre-defined set of Critical
       Regions (inspired by [shah2022abstractions])..." CODEBASE_AUDIT.txt #11
       is [WONTFIX] — this baseline was killed; no fixed-region generator
       exists, and run_logger.py's --baseline choices are only
       semantic / uniform.
Fix:   Remove baseline (2) from the §5.3 enumeration, or relabel it future work.
       If retained as a contrast, note the tray entity (audit #49) is the
       closest shipped analogue of a fixed labelled region.
Refs:  CODEBASE_AUDIT.txt #11; THESIS_NOTES §9

================================================================================
#88  [T1 · Deviation] [THESIS]  §5.3 TAMPURA baseline is not a re-implementation — only two published numbers are used
================================================================================
Where: §5.3 — evaluation.tex:27
What:  §5.3: "POMDP-based TAMP (Conceptual/Simplified): If feasible, we will
       compare against a simplified implementation or published results of a
       POMDP-based TAMP system like TAMPURA..." eval_plotter.py hardcodes
       TAMPURA_MEAN = 57.0, TAMPURA_STD = 38.0 from arXiv:2403.10454 Table II.
       No TAMPURA planner code exists; a live comparison is "FOR LATER" per
       TAMPURA_PLAN.md.
Fix:   State plainly that the TAMPURA comparison uses published Table II numbers
       only (not a re-implementation) — a single bar chart. Drop "simplified
       implementation" as an option.
Refs:  THESIS_NOTES §21; CODEBASE_AUDIT.txt #73; TAMPURA_PLAN.md

================================================================================
#89  [T1 · Deviation] [THESIS]  §5.1 names Bayes3D for perception — integrated nowhere
================================================================================
Where: §5.1 — evaluation.tex:10
What:  §5.1: "...a stream that interfaces with a library like Bayes3D
       [gothoskar2023bayes3d] or a mock perception oracle..." A repo-wide search
       finds Bayes3D only in the proposal LaTeX and references.bib — zero Python
       hits. Perception is oracle_detect_objects() reading ground-truth poses.
Fix:   Remove the Bayes3D mention. State that perception is an oracle reading
       PyBullet ground-truth poses, providing exact estimates and isolating the
       planning contribution from perception noise.
Refs:  THESIS_NOTES §1

================================================================================
#90  [T1 · Deviation] [THESIS]  §5.2 "Plan Quality / Cost" metric is never logged or plotted
================================================================================
Where: §5.2 — evaluation.tex:18
What:  §5.2: "Plan Quality / Cost: The length or cost of the executed plan
       (e.g., number of actions, total path length of the end-effector)."
       run_logger.py logs success, exit_reason, plan_count (replan count),
       n_sense_actions, planning times, boxel/fact counts — but no plan action
       count, no PDDL plan cost, no end-effector path length. eval_plotter.py
       has no such plot.
Fix:   Either implement an action-count / plan-cost / EE-path-length metric, or
       replace "Plan Quality / Cost" in §5.2 with the metrics actually logged
       (replan count, boxel counts, init-state fact counts).
Refs:  CODEBASE_AUDIT.txt #73; THESIS_NOTES §17

================================================================================
#91  [T2 · Deviation] [THESIS]  §5.1 "pose estimates with simulated uncertainty" — the oracle returns exact ground truth
================================================================================
Where: §5.1 — evaluation.tex:10
What:  §5.1: "...a mock perception oracle that provides pose estimates with
       simulated uncertainty." There is no pose-noise injection; the oracle
       returns exact poses. The only modeled uncertainty is visibility/occlusion
       uncertainty (which shadow hides the target), not pose noise.
Fix:   "...exact pose estimates for visible objects." Clarify the modeled
       uncertainty is occlusion/visibility uncertainty over which Boxel a hidden
       object occupies, not perceptual pose noise.
Refs:  THESIS_NOTES §1

================================================================================
#92  [T2 · Deviation] [THESIS]  §5.1 implies perception is a stream over simulated sensor data
================================================================================
Where: §5.1 — evaluation.tex:10
What:  §5.1's framing ("a stream that interfaces with ... simulated sensor
       data") implies perception is a PDDLStream stream consuming RGB/depth.
       RGB/depth are rendered for the GUI but not processed; detection happens
       up front via oracle_detect_objects, not as an on-demand stream.
Fix:   Describe perception as an up-front oracle detection step plus a sense
       action backed by raycasting from a fixed overhead camera. Remove the
       implication that simulated sensor data is processed.
Refs:  THESIS_NOTES §1, §3

================================================================================
#93  [T2 · Deviation] [THESIS]  §5.1/§5.2 scalability "size of the workspace" — no such axis
================================================================================
Where: §5.1 evaluation.tex:9; §5.2 evaluation.tex:19
What:  §5.1: "We will vary the number of occluders and the complexity of the
       scene"; §5.2: scalability tested by "increasing the number of objects,
       occluders, or the size of the workspace." eval_runner.py varies
       n_occluders, n_targets, seed, goal, baseline, min_boxel_size — there is
       no workspace-size axis; the workspace bounds are hardcoded.
Fix:   Drop "size of the workspace." State scalability is measured against
       occluder count and target count (the actual swept axes).
Refs:  CODEBASE_AUDIT.txt #9; THESIS_NOTES §13

================================================================================
#94  [T2 · Deviation] [THESIS]  §5.3 calls the Uniform Voxelization baseline "fine-grained"
================================================================================
Where: §5.3 — evaluation.tex:25
What:  §5.3: "Uniform Voxelization: A version of our planner that uses a
       fine-grained, uniform voxel grid..." The uniform baseline cannot run
       fine-grained: a cell finer than the largest object breaks placement, so
       audit #66 auto-tunes cell_size to ~17 cm for the default scene — coarser
       than the semantic free-space octree leaf (35 mm).
Fix:   Drop "fine-grained." Describe the uniform baseline as a static uniform
       grid whose cell size is auto-set to the largest object's footprint (a
       correctness constraint) — itself a finding about uniform grids.
Refs:  THESIS_NOTES §21.4; CODEBASE_AUDIT.txt #66

================================================================================
#95  [T2 · Deviation] [THESIS]  §5.3/§1 imply the uniform baseline voxelizes belief; it only swaps free-space
================================================================================
Where: §5.3 evaluation.tex:25; §1 introduction.tex:18
What:  §5.3 describes the uniform baseline as one that "uses a fine-grained,
       uniform voxel grid to represent spatial belief." Per CODEBASE_AUDIT #10
       it is a free-space-only swap: UniformGridGenerator replaces
       FreeSpaceGenerator; OBJECT + SHADOW boxels are untouched. The belief over
       hidden objects is the same semantic representation in both arms.
Fix:   Clarify that the uniform baseline replaces only the free-space
       discretization, keeping the same object/shadow belief boxels — it
       isolates the free-space partition strategy, it is not a fully uniform
       belief grid.
Refs:  CODEBASE_AUDIT.txt #10; THESIS_NOTES §21.4

================================================================================
#96  [T3 · Deviation] [THESIS]  §5.1 names only the "hidden object" task; the code ships three goal modes
================================================================================
Where: §5.1 — evaluation.tex:9
What:  §5.1 names only the "hidden object" scenario. run_logger.py's --goal has
       choices holding / stack / find-and-tray-stack, and eval_runner.py sweeps
       all three.
Fix:   List all three evaluated goal modes; note holding is the primary
       narrative task and stack/tray-stack add goal diversity.
Refs:  THESIS_NOTES §9; CODEBASE_AUDIT.txt #49

================================================================================
#97  [T3 · Deviation] [THESIS]  §5.2 "metrics similar to those used for TAMPURA" — only partial overlap
================================================================================
Where: §5.2 — evaluation.tex:14
What:  §5.2: "...we plan to adopt evaluation metrics similar to those used for
       TAMPURA." Success rate and planning time align with TAMPURA; the actually
       plotted metrics also include boxel counts, init-state fact counts, and
       replan-count distributions — boxel-specific, not TAMPURA metrics.
Fix:   "We adopt success rate and planning time, which permit comparison with
       TAMPURA's reported numbers, alongside boxel-specific compactness
       metrics."
Refs:  THESIS_NOTES §21.2; CODEBASE_AUDIT.txt #73

================================================================================
#98  [T3 · Deviation] [THESIS]  §5.1 environment is hedged ("such as PyBullet", "e.g., a Franka Emika Panda arm")
================================================================================
Where: §5.1 — evaluation.tex:8
What:  "We will use a physics-based simulation environment, such as PyBullet,
       with a multi-degree-of-freedom robotic manipulator (e.g., a Franka Emika
       Panda arm)." PyBullet is the actual and only simulator; the robot is
       definitively the 7-DOF Franka Panda (hardcoded Panda link indices,
       self-collision pairs).
Fix:   For the thesis, state these as fact: the environment is PyBullet and the
       manipulator is the 7-DOF Franka Emika Panda.
Refs:  THESIS_NOTES §13

================================================================================
#99  [T2 · Style] [POLISH]  §5 opener is boilerplate
================================================================================
Where: §5 — evaluation.tex:5
What:  "To validate our proposed framework, we will conduct a series of
       experiments in a simulated robotic manipulation environment." The most
       interchangeable possible opening for an evaluation section.
Fix:   "We evaluate the framework in a simulated robotic manipulation
       environment, described below."

================================================================================
#100  [T2 · Style] [POLISH]  §5.2 — "To facilitate direct comparison with state-of-the-art approaches"
================================================================================
Where: §5.2 — evaluation.tex:14
What:  "To facilitate direct comparison with state-of-the-art approaches, we
       plan to adopt evaluation metrics similar to those used for TAMPURA."
       Wordy lead-in; "state-of-the-art" is filler since TAMPURA is named next.
Fix:   "For comparability, we adopt evaluation metrics similar to TAMPURA's."

================================================================================
#101  [T2 · Style] [POLISH]  §5.2 — "This helps assess the efficiency of the generated plans"
================================================================================
Where: §5.2 — evaluation.tex:18
What:  "Plan Quality / Cost: ... This helps assess the efficiency of the
       generated plans." The second sentence says the plan-cost metric measures
       plan efficiency — true by definition.
Fix:   Delete the second sentence; the metric name and parenthetical already
       explain it.

================================================================================
#102  [T2 · Style] [POLISH]  §5.2 — "This will be a key metric for evaluating the tractability"
================================================================================
Where: §5.2 — evaluation.tex:17
What:  "Planning Time: The wall-clock time required for the planner to find a
       solution. This will be a key metric for evaluating the tractability of
       our approach." States the self-evident.
Fix:   Delete the second sentence, or make it carry weight: "Planning Time: the
       wall-clock time the planner needs to find a solution — the central
       measure of whether the adaptive abstraction scales."

================================================================================
#103  [T2 · Style] [POLISH]  §5.3 — "empirically demonstrate whether"
================================================================================
Where: §5.3 — evaluation.tex:29
What:  "The goal of this evaluation is to empirically demonstrate whether our
       proposed framework offers a scalable and effective solution..."
       "demonstrate whether" is awkward (you demonstrate THAT, you TEST
       whether); abstract padding stacked.
Fix:   "This evaluation tests whether the framework scales and performs well on
       TAMP under partial observability, especially on tasks that require
       reasoning about occlusions and information gathering."

================================================================================
#104  [T1 · Over-claim] [THESIS]  §5.4 conclusion is written as a finished paper
================================================================================
Where: §5.4 — evaluation.tex:32, 34
What:  The conclusion of a forward-looking PROPOSAL uses completed-work past
       tense and the wrong noun: "This paper presented a novel approach...",
       "As demonstrated, this enables the robot to reason about what it
       knows...". Nothing has been presented or demonstrated; it is a proposal,
       and it is a thesis proposal, not a "paper."
Fix:   In the thesis, §5.4 becomes the real Conclusion: KEEP the completed-work
       voice, but back every claim with actual results. "As demonstrated" must
       point to the §121 results chapter; "This paper" becomes "This thesis".
       Do NOT downgrade §5.4 to proposal voice ("This proposal has outlined")
       — that moves the document away from being a thesis. (The soften-to-
       "outlines" option would apply only if the proposal were ever revised AS
       a proposal, which is not the goal here.)
Note:  Fix text corrected 2026-05-17 — the original fix steered §5.4 toward
       proposal voice, which contradicts the proposal-to-thesis goal. See #126.

================================================================================
#105  [T3 · Style] [NOW]  §5.4 heading is lowercase "conclusion"
================================================================================
Where: §5.4 — evaluation.tex:31
What:  "\subsection{conclusion}" — lowercase, while every other heading is
       title-case.
Fix:   "\subsection{Conclusion}"

================================================================================
#106  [T2 · Style] [POLISH]  §5.4 — "seamlessly combine"
================================================================================
Where: §5.4 — evaluation.tex:34
What:  "...plans that seamlessly combine information-gathering and manipulation
       actions." "Seamlessly" is a marketing intensifier with no technical
       meaning.
Fix:   "...plans that interleave information-gathering and manipulation
       actions."

================================================================================
#107  [T2 · Style] [POLISH]  §5.4 — "paves the way for" cliché + inflated closing
================================================================================
Where: §5.4 — evaluation.tex:36
What:  "...this work paves the way for more autonomous and capable robotic
       systems that can operate effectively in the complexities of the real
       world." Stacked generic boilerplate that could end any robotics paper.
Fix:   "...this work aims to make TAMP practical in environments where the robot
       starts out only partially aware of its surroundings."

================================================================================
#108  [T2 · Style] [POLISH]  §5.4 — "reason effectively about"
================================================================================
Where: §5.4 — evaluation.tex:32
What:  "...allows a PDDLStream-based TAMP framework to reason effectively about
       object locations and occlusions." Soft, interchangeable phrase; does not
       say what the system does with that reasoning.
Fix:   "...lets a PDDLStream-based TAMP framework plan around uncertain object
       locations and occlusions."

================================================================================
#109  [T2 · Style] [POLISH]  §5.4 — "scalable and task-relevant representation" abstract virtue-stacking
================================================================================
Where: §5.4 — evaluation.tex:32
What:  "The core of our methodology is the adaptive semantic discretization of
       the workspace, which provides a scalable and task-relevant representation
       of spatial uncertainty." A chain of abstract adjectives; the reader
       cannot picture the output.
Fix:   "At the core of the methodology is adaptive semantic discretization: it
       partitions the workspace into Boxels, concentrating detail on the objects
       and occluded regions that matter for the task."

================================================================================
#110  [T2 · Style] [POLISH]  §5.4 — "expected contribution" reuses the same empty adjectives
================================================================================
Where: §5.4 — evaluation.tex:36
What:  "The expected contribution of this research is a scalable and robust
       framework for TAMP in partially known environments." Repeats the empty
       adjective pair; states a contribution without saying what is new.
Fix:   "The expected contribution is a TAMP framework that handles partial
       observability without enumerating an exhaustive state space, by reasoning
       over a compact, object-centric abstraction."

================================================================================
#111  [T2 · Style] [POLISH]  §5.4 — "leveraging a semantically meaningful abstraction"
================================================================================
Where: §5.4 — evaluation.tex:36
What:  "By moving away from exhaustive state-space representations and leveraging
       a semantically meaningful abstraction, this work paves the way for..."
       "leveraging" is corporate-speak; "semantically meaningful abstraction" is
       abstract where "Boxels" is concrete.
Fix:   "By replacing exhaustive state-space representations with the Boxel
       abstraction, this work aims to..."


################################################################################
#  ISSUES — THESIS CONVERSION (STRUCTURAL)          (added 2026-05-17)
################################################################################

These ten issues are NOT defects of the proposal — as a forward-looking
proposal it is correct. They are the structural, document-level work the
proposal-to-thesis upgrade requires, and which the sentence-by-sentence audit
of #1-#120 never captured. They sit outside the T0-T3 severity scale (that
scale grades proposal defects) and are all disposition [THESIS]. For the
upgrade these come FIRST: a thesis cannot exist without #121-#123.

================================================================================
#121  [Structural] [THESIS]  §5 "Evaluation Plan" must become an "Evaluation / Results" chapter
================================================================================
Where: §5 — evaluation.tex (whole section); main.tex:24
What:  §5 is a forward-looking PLAN — "we will conduct", "we will vary", "we
       plan to adopt", "If feasible, we will compare". A thesis needs a results
       chapter: the experimental setup as executed, the actual results (tables
       and plots from the eval sweep in eval_results/sweep_anytime/), and their
       analysis. Issues #87-#103 patch individual §5 sentences; none of them
       restructures the section. This issue owns that restructure.
Fix:   Rewrite §5 as a completed Evaluation chapter: (1) Experimental Setup as
       built; (2) Results — success rate, planning time, boxel/fact counts,
       replan counts, the semantic-vs-uniform comparison, the TAMPURA bar
       chart; (3) hand interpretation to #125. Resolve #87-#103 inside this
       rewrite, not as 17 isolated sentence edits.
Refs:  #87-#103; #125; THESIS_NOTES §21; eval_results/sweep_anytime/

================================================================================
#125  [Structural] [THESIS]  No Discussion of results
================================================================================
Where: new section (may be folded into the #121 Evaluation chapter)
What:  A thesis interprets its results; a proposal has none to interpret. There
       is no discussion of why the semantic partition beats (or does not beat)
       the uniform baseline, what the TAMPURA comparison shows, or where the
       approach breaks down.
Fix:   Add a Discussion that interprets the #121 results: semantic vs uniform
       free-space partitioning; the TAMPURA comparison framed architecturally
       (offline Learn-Model vs online stream sampling — THESIS_NOTES §21 — not
       a hardware comparison); and the observed failure modes. May be a
       subsection of the Evaluation chapter or a standalone chapter.
Refs:  #121; THESIS_NOTES §21

================================================================================
#126  [Structural] [THESIS]  Document-wide framing conversion — forward-looking to retrospective
================================================================================
Where: whole document
What:  The entire document is written as a proposal: forward-looking tense
       ("we will", "we propose", "we plan to", "the expected result", "the
       expected contribution") and proposal self-reference ("This research
       proposal", "This proposal is structured as follows", "This project",
       "This paper"). A thesis is retrospective. Issues #1, #16, #104 are
       isolated instances of this; #126 is the systematic pass.
Fix:   One document-wide pass: convert completed work to past/present voice;
       "this proposal / this project / this paper" -> "this thesis / this
       work". Do this AFTER the chapters exist (#121-#125) so the tense matches
       reality. Note: #104's fix text was corrected 2026-05-17 — do not regress
       §5.4 to proposal voice.
Refs:  #1 #16 #104; #127 #128

================================================================================
#127  [Structural] [THESIS]  Abstract must be recast as a thesis abstract
================================================================================
Where: Abstract — abstract.tex
What:  The abstract is a proposal abstract: "This research proposal outlines a
       plan to ...", "The proposed methodology ...", "The expected contribution
       is ...". A thesis abstract states what was built and what the evaluation
       found. Issues #1-#7 only tighten the wording of the proposal abstract.
Fix:   Recast the abstract for the thesis: what was built (the Boxel
       abstraction + the PDDLStream POD-TAMP integration), how it was
       evaluated, and the key results. Apply the #1-#7 wording fixes within
       this recast rather than separately.
Refs:  #1 #2 #3 #4 #5 #6 #7; #126

================================================================================
#128  [Structural] [THESIS]  §1 needs a Contributions list and a thesis chapter outline
================================================================================
Where: §1 — introduction.tex:24
What:  §1 has no explicit contributions list, and its closing paragraph ("This
       proposal is structured as follows: Section~... ") is a proposal outline
       naming the proposal's five sections.
Fix:   Add an explicit "Contributions of this thesis" list (bulleted or
       numbered). Replace the "This proposal is structured as follows"
       paragraph with a thesis outline matching the final chapter structure
       (including the new Implementation, Results, and Discussion chapters).
Refs:  #121 #122 #125 #129

================================================================================
#130  [Build] [THESIS]  Thesis front and back matter is missing
================================================================================
Where: main.tex; resources/title.tex; resources/acronyms.tex; sections/appendix.tex
What:  main.tex has no thesis front/back matter. \date{\today} (main.tex:10)
       still carries a "TODO use \formatdate" note. sections/appendix.tex
       exists but is commented out (main.tex:26-27).
Fix:   Add what an RWTH Master's thesis requires: a declaration of authorship
       (Eidesstattliche Versicherung); a proper title page (examiners,
       institute, real submission date — replace \date{\today}); a table of
       contents; a list of figures; a list of tables; optionally
       acknowledgements; a printed acronyms list (resources/acronyms.tex
       already exists). Decide the appendix content (e.g. the full PDDL domain,
       parameter tables, extra plots) or remove the commented-out stub.
Refs:  main.tex:10,26-27; #117 #129


################################################################################
#  ISSUES — ADDED DURING THE AUDIT WALKTHROUGH      (added 2026-05-18)
################################################################################

Defects surfaced while working the audit walkthrough that were not among
#1-#130. Numbering continues from #130.

================================================================================
#136  [Structural] [THESIS]  The official i6 thesis template has not been obtained
================================================================================
Where: project setup — proposal-template/ is built on the *proposal* template
What:  The entire thesis is being written inside the Chair of Machine Learning
       and Reasoning *proposal* template (git.rwth-aachen.de/i6/general/
       proposal-template). The chair's thesis guidelines
       (https://ml.rwth-aachen.de/theses/guidelines/) provide a SEPARATE
       official thesis template (https://git.rwth-aachen.de/i6/general/
       thesis-template), distinct from the proposal template. The thesis
       template defines the correct document class, top-level unit (chapter
       vs section), front/back matter, and declaration-of-authorship slot.
       Surfaced by the 2026-05-19 RWTH-compliance check.
Fix:   Clone git.rwth-aachen.de/i6/general/thesis-template (requires RWTH
       GitLab login) into a readable location. It supersedes the manual
       structural retrofit attempted in #130.
Refs:  #130 #137

================================================================================
#137  [Structural] [THESIS]  Written content must be migrated into the thesis template
================================================================================
Where: whole document
What:  Once the official i6 thesis template (#136) is obtained, the prose,
       references, figures, listings, macros, and acronyms written in the
       proposal template must be transferred into it. The thesis template's
       class and structure determine the correct top-level unit and front/back
       matter, which subsumes the manual #130 (front/back matter) retrofit.
Fix:   Map each proposal section/file onto the thesis template's structure;
       carry over references.bib, graphics, custom macros, and acronyms;
       re-resolve all \cref targets; rebuild and verify. The content-level
       conversions (#121 results chapter, #126 retrospective voice, #127
       abstract recast, #128 contributions list + outline) are then applied
       inside the thesis template, not the proposal template.
Refs:  #121 #126 #127 #128 #130 #136

================================================================================
#138  [T3 · Style] [THESIS]  Label prefixes inconsistent — chap: used on \section labels
================================================================================
Where: approach.tex:4 (chap:methodology); evaluation.tex:4 (chap:evaluation);
       discussion.tex:4 (chap:discussion); conclusion.tex:4 (chap:conclusion)
What:  Several top-level \section labels use a "chap:" prefix while other
       sections use "sec:". The proposal template has no chapters, so "chap:"
       is misleading. Surfaced by the 2026-05-19 template-compliance audit.
Fix:   Settle a single label-prefix convention. Best handled during the
       thesis-template migration (#137), since the thesis template's
       chapter/section structure decides the correct prefix; update every
       \label and its \cref/\ref sites together.
Refs:  #135 #137


================================================================================
OPEN ISSUES
================================================================================

44 issues remain open. Each issue's header carries its tier (T0-T3) and
disposition ([NOW] / [THESIS] / [POLISH]). Resolved issues have been removed
from this file --- see `git log --grep="Fix #"` and `git log --grep="audit:
mark"` for their record.

§2 Background:   #46 #47
§3 Related Work: #49 #50 #51 #52 #53 #54 #56
§4 Approach:     #57
§5 Evaluation:   #87 #88 #89 #90 #91 #92 #93 #94 #95 #96 #97 #98 #99 #100
                 #101 #102 #103 #104 #105 #106 #107 #108 #109 #110 #111
Structural:      #121 #125 #126 #127 #128 #130 #136 #137 #138

Gating: the §5 issues (#87-#111) are subsumed by the #121 evaluation rewrite;
#121/#126/#127/#128/#130 and the #137 migration depend on obtaining the
official i6 thesis template (#136); #125 (Discussion) needs evaluation results.
