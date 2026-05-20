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
#  ISSUES — ADDED 2026-05-20  (EVAL WRITE-UP)
################################################################################

The sweep in eval_results/sweep_anytime/ is ~94% complete (CODEBASE_AUDIT.txt
#93). These issues take the raw data and turn it into chapters. Together
they subsume the relevant parts of #121, #125, and the eval-anchored bits
of #126/#127 --- once all five land, those umbrellas can be removed.

================================================================================
#145  [Thesis] [THESIS]  Close out Conclusion and Abstract with eval-supported claims
================================================================================
Where: thesis/chapters/conclusion.tex (above the Future Work section);
       thesis/chapters/abstract.tex.
What:  Both chapters currently state contributions without referring to the
       actual eval outcomes. The abstract claims the framework "scales
       better than uniform voxelization" with no number attached; the
       conclusion says "Future work will focus on..." without first
       summarizing what the demonstrated work showed.
Fix:   Update the conclusion to summarize the demonstrated contribution
       with the #143 headline numbers (semantic vs uniform; the TAMPURA
       architectural finding; the mbs0.05 null result). Rewrite the
       abstract per #127 with 1-2 sentences of headline results. Closes the
       remaining proposal-voice items of #126/#127 in these chapters.
Refs:  #126 #127 #143 #144


################################################################################
#  ISSUES --- ADDED 2026-05-20  (SIM-SCREENSHOT FIGURE PLACEMENT)
################################################################################

60 PyBullet screenshots sit unused in thesis/graphics/sim screen shots/.
The thesis currently contains only two figures (Boxelization.png schematic,
octmap_illustration.png in background). Methods, Results, and Discussion
have no sim screenshots. These issues identify concrete places where one
screenshot would make a concept, algorithm, or shortcoming visible that is
currently described in prose only. The image filenames named below are
candidates from thesis/graphics/sim screen shots/; final picks may be
recropped or substituted. Aside: thesis/graphics/sim screen shots/Screenshot
2026-04-20 160547.png is a stray browser screenshot (demo.emson.cloud) and
should be removed from this folder.

================================================================================
#146  [Thesis] [THESIS]  Real-sim companion to the Boxelization schematic
================================================================================
Where: methods.tex:17-22 (fig:boxelization)
What:  The boxelization figure is a four-panel schematic. Nowhere in the
       methods chapter does the reader see the partition applied to a real
       PyBullet scene --- object AABBs over real cubes and red shadow
       wireframes labeled by object. A real-scene companion makes the
       abstraction concrete and shows that the cyan/red boxes are not
       imaginary.
Fix:   Add a one-panel figure (or fourth subpanel of fig:boxelization)
       showing a single sim screenshot with visible object boxels and
       labeled shadow wireframes. Candidates: Screenshot 2026-04-26
       143036.png; 2026-04-22 121333.png; 2026-04-26 142916.png. Pick the
       clearest label visibility.
Refs:  methods.tex:17-22

================================================================================
#147  [Thesis] [THESIS]  Visual contrast: semantic vs uniform partition
================================================================================
Where: methods.tex end of Adaptive Semantic Discretization section, or
       results.tex line 25 (Uniform Voxelization baseline)
What:  The thesis claims the uniform baseline yields many more cells than
       the semantic partition. Only the quantitative plots show this; no
       figure lets the reader SEE "thousands of cyan cells" vs "a small
       labelled set" in one image.
Fix:   Two-panel figure on matching scenes/angles: (a) semantic partition
       and (b) uniform voxel grid. Candidates (a): 2026-04-26 143036.png,
       2026-04-22 121333.png. Candidates (b): 2026-05-09 113613.png,
       113951.png, 115027.png, 115755.png, 120308.png, 134715.png.
Refs:  methods.tex (Recursive Partitioning paragraph); results.tex:25;
       CODEBASE_AUDIT.txt #93 #97

================================================================================
#148  [Thesis] [THESIS]  Sense action targeting a shadow
================================================================================
Where: methods.tex:89-111 (sense action subsection)
What:  The sense action is given as PDDL and prose only. Several shots
       have the action-log overlay visible (e.g. "Sensing shadow of green
       object") and labeled red shadow wireframes, making (view_clear ?r)
       and the targeted region concrete.
Fix:   One figure with a labeled shadow shot. Caption maps the visible
       overlay to the symbolic action. Candidates: 2026-04-23 145402.png
       ("Sensing shadow of green object" caption visible), 2026-04-26
       145847.png, 2026-04-28 091354.png, 2026-05-02 105108.png.
Refs:  methods.tex:89-111 (lst:pddl_sense_k_literal)

================================================================================
#149  [Thesis] [THESIS]  Optimistic-sense -> reactive-replan cycle figure
================================================================================
Where: methods.tex:107-109 (optimistic + replanning paragraph)
What:  The architectural choice "optimistic effect + replan when execution
       disagrees" is central but currently invisible. Screenshot 2026-05-12
       135205.png catches the exact moment: action log reads "sense
       shadow_of_purple_object --- target not here".
Fix:   Embed that screenshot. Caption ties the visible "target not here"
       log line to: (i) the optimistic add-effect, (ii) the execution-time
       rejection, (iii) the replan with the shadow now marked empty.
       Candidates: 2026-05-12 135205.png; 2026-05-15 200153.png;
       2026-05-15 202947.png.
Refs:  methods.tex:107-109

================================================================================
#150  [Thesis] [THESIS]  Three-strike give-up limitation figure
================================================================================
Where: discussion.tex:70-80 (Planning paragraph, "still-blocked three
       times in succession")
What:  The unsound shortcut where a shadow is marked empty after three
       still-blocked sensing attempts is described in prose. Screenshot
       2026-05-15 200153.png shows "retry 3/3" in the action log --- the
       exact loop event the text describes.
Fix:   Include the "retry 3/3" screenshot under the Limitations Planning
       paragraph. Caption: the visible retry counter is the moment the
       loop hits the bounded give-up and the shadow gets marked empty
       without ever being directly observed. Candidates: 2026-05-15
       200153.png.
Refs:  discussion.tex:70-80; methods.tex:109

================================================================================
#151  [Thesis] [THESIS]  Experimental Setup: one figure per task variant
================================================================================
Where: results.tex:6-11 (Experimental Setup, task bullet)
What:  Three goals are evaluated --- holding (hidden-object), stack,
       find-and-tray-stack --- and the reader is told what they are in one
       sentence each. No figure shows what they look like.
Fix:   A three-panel fig:eval_tasks. Candidates:
         (a) holding: 2026-04-22 121333.png or 2026-04-26 143036.png
         (b) stack:   2026-05-11 171834.png or 171855.png
         (c) tray:    2026-05-15 110407.png, 110411.png, or 191212.png
Refs:  results.tex:9; methods.tex:53 (sense-plan-act loop)

================================================================================
#152  [Thesis] [THESIS]  n_occluders scalability composite
================================================================================
Where: results.tex:19-20 (Scalability bullet), alongside the
       planning_time_vs_n_occluders plot referenced in #143
What:  The plot conveys planning time as a curve but the reader has no
       visual sense of what "more occluders" means in the scene.
Fix:   A three-panel figure: low / medium / high n_occluders.
       Candidates: 2026-05-11 171834.png (light); 2026-05-12 121849.png
       (moderate); 2026-05-15 185934.png (heavy).
Refs:  results.tex:19; #143; eval_results/sweep_anytime/

================================================================================
#153  [Thesis] [THESIS]  Overhead-camera RGB+depth inset figure
================================================================================
Where: results.tex:10 (Perception bullet) or discussion.tex:22-34
       (Perception paragraph)
What:  Almost every sim shot has corner insets labeled "Synthetic Camera
       RGB data" and "Synthetic Camera Depth data". This is the fixed
       overhead camera the perception bullet describes. Including it
       lets the reader see what a future learned detector would consume,
       and what the oracle bypasses by reading ground-truth poses.
Fix:   Crop one RGB+depth inset (or include a whole-scene shot with the
       inset visible) as fig:overhead_camera. Caption: oracle reads
       ground truth; depth/RGB show the input a future learned detector
       could use. Candidates: 2026-04-26 142916.png; 2026-05-02 105108.png.
Refs:  results.tex:10; discussion.tex:22-34

================================================================================
#154  [Thesis] [THESIS]  Introduction hero figure
================================================================================
Where: introduction.tex (after the opening paragraph, around line 5-10)
What:  The introduction has no figure. A "what does the problem look
       like" hero shot would anchor the reader in the actual scene the
       thesis works in: robot arm, cluttered table, hidden target, and a
       preview of the boxel overlay.
Fix:   One figure: a representative hidden-object scene with the boxel
       overlay visible. Candidates: 2026-04-22 121333.png or 2026-04-26
       143036.png.
Refs:  introduction.tex:5-21

================================================================================
#155  [Thesis] [THESIS]  Curate screenshots into thesis/graphics/sim/ with stable names
================================================================================
Where: thesis/graphics/sim screen shots/ (current dir name has a space ---
       a LaTeX hazard); thesis/graphics/sim/ (proposed)
What:  #146-#154 will reference 8-10 screenshots by filename. Using the
       raw "Screenshot 2026-MM-DD HHMMSS.png" names in \includegraphics
       is fragile: the directory name contains a space, and the
       timestamps are not self-documenting in source. A small one-time
       curation --- copy the picked screenshots to thesis/graphics/sim/
       with stable names (scene_hidden_target.png, partition_semantic.png,
       partition_uniform.png, sense_targeting_shadow.png,
       sense_fail_retry3.png, task_stack.png, task_tray.png,
       overhead_camera_inset.png, etc.) --- pays off immediately.
Fix:   Curate the final picks; copy with stable filenames into
       thesis/graphics/sim/. Optionally crop the IDE chrome (taskbars,
       editor side panels, window borders) for thesis-grade figures.
       Also remove the stray browser screenshot 2026-04-20 160547.png
       (demo.emson.cloud, unrelated) from the source folder.
Refs:  #146-#154


================================================================================
OPEN ISSUES
================================================================================

15 issues remain open. Each issue's header carries its tier (T0-T3) and
disposition ([NOW] / [THESIS] / [POLISH]). Resolved issues have been removed
from this file --- see `git log --grep="Fix #"` and `git log --grep="audit:
mark"` for their record.

Structural:      #121 #126 #127 #130 #145
Figure placement: #146 #147 #148 #149 #150 #151 #152 #153 #154 #155

Gating: #141 #142 #143 #144 #156 done --- chapters are clear of internal
file-path / hardware-spec clutter and the Results + Discussion content
is in thesis/. #145 (conclusion + abstract eval-anchored closure) is
next; #125 and #140 are resolved jointly with #144. #130's remaining
items (real submission date, appendix decision) are independent and
need user input. #121 and #127 are umbrellas that #142-#145 subdivide;
remove them after #145 lands. The §5 sentence-level polish issues
(#87-#111) were resolved earlier in the audit walkthrough.
Figure-placement issues #146-#154 are all gated by #155 (screenshot
curation); #155 is independent and can be done in any order against
the others.
