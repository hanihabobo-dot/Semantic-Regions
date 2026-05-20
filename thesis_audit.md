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
#  ISSUES — ADDED 2026-05-20  (EVAL-DESIGN GAP FROM SWEEP DATA)
################################################################################

================================================================================
#140  [Structural] [THESIS]  §5 needs a fine-resolution-discriminating scene (or honest null disclosure)
================================================================================
Where: §5 evaluation.tex (Experimental Setup + Baselines);
       CODEBASE_AUDIT.txt #97.
What:  The sweep data (CODEBASE_AUDIT.txt #93, refreshed
       2026-05-20 at ~94% coverage) shows semantic and
       semantic+mbs0.05 are statistically indistinguishable on
       every goal: stack identical seed-for-seed at 184/300
       each; holding 42.3% vs 46.3% (within seed noise);
       find-and-tray-stack 39.7% vs 32.3% (mbs0.05 actually
       worse).  The thesis therefore cannot honestly claim
       "finer resolution wins under a fixed time budget" on
       this data --- at the scene scales tested, the 0.05 m
       leaf floor does not change outcomes because auto_cell
       (~6-9 cm, the largest object's footprint) is the
       binding constraint.
Fix:   One of, ideally both:
       (a) Add a scene / task to the eval that ONLY finer
           resolution can solve --- see CODEBASE_AUDIT.txt #97
           for design candidates (narrow-corridor reach,
           sub-cell pocket placement, sub-cell hidden target,
           dense small-occluder shelf).  Then report a real
           positive result.
       (b) Disclose the null result honestly in the Results
           + Discussion: at the scene scales tested, the
           5 cm leaf floor does not change outcomes because
           auto_cell is the binding constraint.  This is a
           characterisation of the regime, not a negative for
           the method.
       Most honest: BOTH.  Implement (a) for a positive
       finding on a scene that discriminates; report (b) on
       the original scenes as a regime-characterisation
       finding.  The chapter then says where mbs0.05 helps
       and where it does not, instead of overclaiming or
       hand-waving.
Refs:  CODEBASE_AUDIT.txt #77 #93 #97


################################################################################
#  ISSUES — ADDED 2026-05-20  (EVAL WRITE-UP)
################################################################################

The sweep in eval_results/sweep_anytime/ is ~94% complete (CODEBASE_AUDIT.txt
#93). These issues take the raw data and turn it into chapters. Together
they subsume the relevant parts of #121, #125, and the eval-anchored bits
of #126/#127 --- once all five land, those umbrellas can be removed.

================================================================================
#142  [Thesis] [THESIS]  Write the "Experimental Setup" section of Results as built
================================================================================
Where: thesis/chapters/results.tex --- the current "Experimental Setup"
       \section is forward-looking ("we will vary the number of occluders").
What:  The setup must report what was actually run: hardware, # seeds, time
       budget per call, sweep grid (variants x goals x n_occluders), time
       budget anytime tracks, seed-pairing across variants, what was
       excluded from the analysis, software versions. None of this is in
       the text yet; the prose is proposal voice.
Fix:   Rewrite the section in past/present indicative. Document the
       hardware, the exact sweep grid as run (3 goals x N variants x
       n_occluders in {...}; M seeds each; T-second anytime budget), the
       semantic / semantic+mbs0.05 / uniform / TAMPURA-published variants,
       what was held fixed across seed pairs, software versions, and the
       single excluded condition if any. Resolves the procedure part of
       #121 and the results.tex pieces of #126.
Refs:  #121 #126 #141; THESIS_NOTES sweep_anytime

================================================================================
#143  [Thesis] [THESIS]  Write the "Results" section with figures, tables, and numbers
================================================================================
Where: thesis/chapters/results.tex --- new section between Experimental
       Setup and Baselines.
What:  results.tex contains no actual numbers, figures, or tables. The
       PNGs exist in eval_results/sweep_anytime/; the prose that interprets
       them does not.
Fix:   Add a Results section that embeds the headline plots
       (success_rate_vs_n_occluders, planning_time_vs_n_occluders,
       boxel_count_breakdown, init_state_facts_vs_n_occluders,
       solved_vs_time, tampura_wallclock_comparison, failure_modes) as
       figures, with one-paragraph commentary on each. Add a headline-
       numbers table --- success rate and median planning time per goal x
       variant. Carry over the #141 lessons. Resolves the results part of
       #121.
Refs:  #121 #140 #141 #142; eval_results/sweep_anytime/

================================================================================
#144  [Thesis] [THESIS]  Write the Discussion chapter content
================================================================================
Where: thesis/chapters/discussion.tex --- replace the lorem ipsum placeholder
       above the Limitations section.
What:  The Discussion chapter has no interpretive content yet. The
       Limitations subsection is in place, but the chapter has to actually
       discuss results: where semantic beats / matches / loses to uniform;
       what the TAMPURA bar shows architecturally (offline Learn-Model vs
       online stream sampling --- THESIS_NOTES sec.21, NOT a hardware
       comparison); failure-mode patterns from the failure_modes plot; the
       mbs0.05 null finding (#140); threats to validity.
Fix:   Write the discussion content from #141 + #143. Frame the TAMPURA
       comparison architecturally per THESIS_NOTES sec.21. Address mbs0.05
       honestly per #140(b). Leave the existing Limitations section
       in place. Resolves #125.
Refs:  #125 #140 #141 #143; THESIS_NOTES sec.21

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


================================================================================
OPEN ISSUES
================================================================================

10 issues remain open. Each issue's header carries its tier (T0-T3) and
disposition ([NOW] / [THESIS] / [POLISH]). Resolved issues have been removed
from this file --- see `git log --grep="Fix #"` and `git log --grep="audit:
mark"` for their record.

Structural:      #121 #125 #126 #127 #130 #140 #142 #143 #144 #145

Gating: #141 done --- notes/PLOT_LESSONS.md is the data backbone for
#142-#145. #142 is now the first concrete step (unblocked); #143-#145
chain off it. #130's remaining items (real submission date, appendix
decision) are independent and need user input. #121/#125/#127 are
umbrellas that #142-#145 subdivide; remove them after all four land.
The §5 sentence-level polish issues (#87-#111) were resolved earlier
in the audit walkthrough.
