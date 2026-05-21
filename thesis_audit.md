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

################################################################################
#  ISSUE --- ADDED 2026-05-21  (CITATION CORRECTNESS, RELATED WORK)
################################################################################

================================================================================
#157  [T0] [NOW] [DONE]  Misattributed belief-representation claim in related work
================================================================================
Where: thesis/chapters/related-work.tex:12 (sec. POMDP-based TAMP Solutions).
       Was duplicated in proposal-template/sections/related_work.tex:12;
       proposal-template/ deleted 2026-05-21, so only the thesis copy remains.
What:  "Implementations often resort to particle filters over dense voxel
       grids to approximate these continuous belief states
       \cite{curtis2024partially, gothoskar2023bayes3d}, which does not scale
       well to large environments." Inaccurate on both citations:
       - TAMPURA (curtis2024partially): its voxel grid (find_dice, 15 mm) is a
         VISIBILITY/occupancy belief, not a pose belief; placement is
         continuous SE(3)-pose sampling; planning is a learned abstract MDP
         solved with LAO* --- not a particle filter over voxels.
       - Bayes3D (gothoskar2023bayes3d): a 3D-scene PERCEPTION system, not a
         POMDP-TAMP planner. It does GPU-accelerated coarse-to-fine sequential
         Monte Carlo (so "particle filter" fits Bayes3D, but not "voxel grid",
         and it does not belong under "POMDP-based TAMP Solutions").
Fix:   Replaced with an accurate per-system description (TAMPURA visibility
       grid + continuous-pose sampling; Bayes3D as SMC perception). The genuine
       first sentence (continuous-pose belief is a challenge) was kept.
       thesis/ commit "Fix #157"; clean latexmk build (58 pp).
Refs:  thesis/chapters/related-work.tex:12; references.bib curtis2024partially,
       gothoskar2023bayes3d


================================================================================
OPEN ISSUES
================================================================================

4 issues remain open. Each issue's header carries its tier (T0-T3) and
disposition ([NOW] / [THESIS] / [POLISH]). Resolved issues have been removed
from this file --- see `git log --grep="Fix #"` and `git log --grep="audit:
mark"` for their record.

Structural:      #126
Figure placement: #152 #153 #154

Gating: #141-#151, #130, #155, and #156 done --- all eval-write-up
content (Results, Discussion, abstract + conclusion closure) is in
thesis/, the chapters are clear of internal file-path and hardware-spec
clutter, the front/back matter (submission date, PDDL appendix) is in
place, curated screenshots are in thesis/graphics/sim/, and six sim
figures (boxelization companion, semantic vs uniform, sense action,
replan cycle, three-strike give-up, task triptych) are inserted across
methods/results/discussion. #125, #140, #121, #127 were closed jointly.
#126 (document-wide forward-voice conversion) is left open as a final
verification pass since the chapters individually are already
retrospective. The §5 sentence-level polish issues (#87-#111) were
resolved earlier in the audit walkthrough. Figure-placement issues
#152-#154 remain (n_occluders composite, overhead-camera inset,
introduction hero).
