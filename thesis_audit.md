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
OPEN ISSUES
================================================================================

After the 2026-05-23 prose + citation-accuracy pass, 1 issue remains open.
Each issue's header carries its tier (T0-T3) and disposition.
The nine issues resolved in that pass (#164 #166 #167 #169 #170 #171 #172 #173 #174)
have been removed; see `git log --grep="Fix #"` (thesis repo) and
`git log --grep="audit:"` (this repo) for their record.

OPEN:
  Figures: #168  (every figure one-by-one; figures agent)

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
