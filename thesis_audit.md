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
#177  [T0] [NOW]  TAMPURA comparison: wrong task cited + self-contradicts on the analogue
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
       >= 63 %, derived) and frame honestly: architectural difference (offline
       Learn-Model vs online stream sampling), NO speed/quality winner -- we are
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

================================================================================
OPEN ISSUES
================================================================================

After the 2026-05-23 prose + citation-accuracy pass, 1 issue remained open
(#168); a 2026-05-24 follow-up (#175) tracks methods-text reconciliation after
CODEBASE_AUDIT #102/#103.
Each issue's header carries its tier (T0-T3) and disposition.
The nine issues resolved in that pass (#164 #166 #167 #169 #170 #171 #172 #173 #174)
have been removed; see `git log --grep="Fix #"` (thesis repo) and
`git log --grep="audit:"` (this repo) for their record.

OPEN:
  Figures: #168  (every figure one-by-one; figures agent)
  Figures: #176  (optional real discretization-progression figure; captures archived)
  Methods: #175  (shadow-splitting prose vs #102/#103 code; prose)
  Results/Disc: #177  (TAMPURA fig cites wrong task + self-contradiction + time/success framing; prose + plot)

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
