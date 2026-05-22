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

################################################################################
#  ISSUES --- ADDED 2026-05-21  (TAMPURA-COMPARISON FRAMING, DISCUSSION)
################################################################################
Surfaced during a full audit of every TAMPURA mention in the thesis
(prompted 2026-05-21). The audit found the thesis text already accurate and
well-hedged --- #157 was the only outright error. These two are
tightening/disclosure refinements, not corrections of wrong claims.

================================================================================
#158  [T3] [POLISH] [DONE]  "task family" overstated comparability (discussion)
================================================================================
Where: thesis/chapters/discussion.tex (Architectural comparison with TAMPURA).
What:  "competitive ... on this task family" implied find-and-tray-stack and
       TAMPURA's Partial Observability are the same family.
Fix:   -> "on the closest analogous task", matching the abstract/results hedge.
       thesis/ commit "Fix #158"; clean latexmk build.

================================================================================
#159  [T2] [THESIS] [DONE]  Undisclosed hardware-comparison direction (discussion)
================================================================================
Where: thesis/chapters/discussion.tex (Threats to validity, "TAMPURA via
       published numbers").
What:  Thesis said the comparison is "not a hardware benchmark" but never stated
       which way the hardware tilts.
Fix:   Added one sentence: both planners single-threaded; TAMPURA's CPU has a
       marginally higher base clock (2.5 vs 2.0 GHz), so the hardware gap, if
       anything, favours TAMPURA. Avoids the 20-vs-8-core framing (moot under
       single-threading). thesis/ commit "Fix #159"; clean latexmk build.

################################################################################
#  ISSUES --- ADDED 2026-05-21  (TAMPURA ENGINE, RELATED WORK, CONTRIBUTION)
################################################################################
Surfaced in the 2026-05-21 working session (TAMPURA code dive + a related-work /
contribution discussion). #160 is a factual error; #161-#162 are the structural
gaps the author flagged as the thesis's weakest points. All OPEN.

================================================================================
#160  [T0->T3] [NOW] [DONE]  TAMPURA's determinised planner: SymK (code) / FastDownward (paper)
================================================================================
Where: thesis/chapters/discussion.tex:83-84; also notes/THESIS_NOTES.md sec 21.3.
What:  Both state "Both systems use FastDownward as the inner determinised
       planner, so the difference is not the search engine." Verified false in
       TAMPURA's source (git/tampura): determinised planning uses SymK --- a
       Fast Downward-derived symbolic top-k planner (contingent_policy.py ->
       symk_search/symk_translate; setup.py builds third_party/symk) --- and
       LAO* (solvers/lao_star.py) solves the MDP. The search engines DO differ
       (FD heuristic search vs SymK symbolic top-k); only the PDDL->SAS+
       translation layer is shared. (Our side does use FastDownward via
       PDDLStream --- confirm before finalising the rewrite.)
Fix:   Rewrite the sentence (we use FastDownward via PDDLStream; TAMPURA uses
       SymK; symbolic search is cheap in both, so the salient difference is WHEN
       geometry sampling is paid) and fix the same false claim in THESIS_NOTES
       sec 21.3.
Refs:  discussion.tex:83-84; THESIS_NOTES sec 21.3; git/tampura sources.
Done (2026-05-21): NOT a clean error -- the paper's Algorithm 2 literally
       names FastDownward; only the released CODE uses SymK (FD-derived top-k).
       Reworded discussion.tex (thesis commit "Fix #160", clean build) and added
       an implementation note to THESIS_NOTES sec 21.3, rather than asserting the
       thesis was wrong. Effective tier ~T3 (precision), not T0.

================================================================================
#161  [T2] [THESIS] [DONE]  Related Work is thin --- enrich from emails and pdfs/SOURCES.md
================================================================================
Where: thesis/chapters/related-work.tex (whole chapter, ~40 lines).
What:  Covers TAMPURA, pan2024task, ma2025task, zhao2025seeing, bai2025learning,
       OctoMap, Shah CRs --- but OMITS the thesis's own lineage. Key gaps (all
       catalogued in emails and pdfs/SOURCES.md, which tags each work's bib key
       or marks it absent):
       - Belief-space TAMP: Kaelbling & Lozano-Perez 2013 (foundational; NOT in
         bib) and Garrett et al. 2020 "Online Replanning in Belief Space"
         (SS-Replan; NOT in bib). SS-Replan is the CLOSEST precedent to this
         thesis's optimistic-determinise-and-replan loop --- must be positioned.
       - POD / translation lineage the thesis BUILDS ON: LW1 (bonet2014flexible,
         in bib but never discussed), CLG (albore2009), K-replanner (bonet2011),
         PO-PRP (Muise et al. 2014, NOT in bib).
       - TAMP foundations: PDDLStream (garrett2018, the framework we build on)
         and the TAMP survey (garrett2021) --- in bib, not discussed.
       - Recent POD-TAMP: CoCo-TAMP (Kim et al. 2026, LLM state estimation; NOT
         in bib); Contingent TAMP for HRI (2020; NOT in bib).
       - Supervisors' work: Plan2Pose (Swoboda & Hofmann 2026; NOT in bib).
Fix:   Add a belief-space-TAMP + POD-translation-lineage subsection; DISCUSS
       (not just \cite) works already in bib; add the missing relevant ones to
       references.bib; close with a research-gap paragraph that sets up #162.
Refs:  related-work.tex; emails and pdfs/SOURCES.md; references.bib.

================================================================================
#162  [T1] [THESIS]  Contribution / motivation under-justified
================================================================================
Where: introduction.tex (contribution statement), related-work.tex framing,
       discussion.tex / conclusion.tex.
What:  The contribution is not foregrounded; the semantic-vs-uniform evaluation
       reads as "two variants of my own system," underselling the idea. The real
       contribution is a REPRESENTATION: Boxels make occlusion/visibility
       FIRST-CLASS SYMBOLIC planning state in a POD (knowledge-literal) TAMP
       planner --- promoting occluded volume to enumerable SHADOW regions the
       planner branches over. The 2026-05-21 TAMPURA code dive supports the
       novelty: TAMPURA keeps occlusion SUB-symbolic (find_dice look_effects_fn
       uses a voxel dict only to weight one predicate's success probability),
       whereas this thesis lifts it into symbolic state (POD, not POMDP).
       semantic-vs-uniform is the ABLATION that isolates the adaptive structure,
       not the contribution.
Fix:   Add an explicit contribution statement (intro) + research-gap paragraph
       (end of related work); position against the POMDP (TAMPURA) and reactive/
       replanning (SS-Replan, pan2024task) paradigms; reframe the eval as
       ablation-of-a-representation, not "beats baselines." Honest scope:
       representation/architecture contribution under oracle perception, not a
       benchmark win. Depends on #161 (novelty needs the survey).
Refs:  introduction.tex; related-work.tex; discussion.tex; conclusion.tex.

================================================================================
#163  [T1] [THESIS]  *** TOP PRIORITY *** State explicitly WHY our approach is better
================================================================================
Where: thesis/chapters/related-work.tex (the "why ours differs" contrasts) and
       discussion.tex. Complements #162; this one lists the concrete advantages.
What:  Related work hints at differences but never states the ADVANTAGES plainly.
       Make these three explicit as the "this is why our approach is better" case:
       (1) OCCLUSION IS FIRST-CLASS, INSPECTABLE SYMBOLIC STATE. Both systems
           gather information --- "we do info-gathering" is NOT the edge. The edge
           is the REPRESENTATION: our planner reasons over named, human-inspectable
           regions (observed vs occluded SHADOW boxels); TAMPURA's spatial belief
           is a voxel grid + an opaque, learned statistical effect model that is
           hard to inspect.
       (2) WE REASON ABOUT UNCERTAINTY WITHOUT PROBABILITIES. POD knowledge-literals
           (obj_at_boxel_KIF, view_clear) capture known/unknown deterministically;
           no per-controller probability estimation, no offline model-learning.
           (_build_init re-emits symbolic facts every replan; no probabilities.)
       (3) NO MDP MACHINERY. A lightweight deterministic PDDL planning layer (POD
           style) instead of TAMPURA's learn-a-sparse-MDP + LAO* stack --- simpler,
           and no learned abstraction to mis-estimate (see #162 "assumes its
           abstraction").
Fix:   Add an explicit "advantages" paragraph to related work; echo in discussion.
       Pair each advantage with its honest cost (oracle perception; no risk-
       weighting; relies on replanning). NOTE: still need a fair empirical way to
       compare the two --- eval design belongs in CODEBASE_AUDIT.txt, not here.
Refs:  related-work.tex; discussion.tex; #162; #160.

================================================================================
#164  [T2] [THESIS]  Disclose the stack-cost caveat (stack costs 2x other actions)
================================================================================
Where: thesis methods/limitations + pddl/domain_pddlstream.pddl:302.
What:  The PDDL domain gives `stack` cost 2 while sense/move/pick/place all cost 1
       (verified: domain_pddlstream.pddl:302 `(increase (total-cost) 2)` vs `1`
       elsewhere). This is a deliberate, undisclosed nudge: a deterministic cost
       penalty that discourages stacking which would obstruct the camera view ---
       a workaround for the planner's inability to reason about action ORDER /
       outcome likelihood (it minimises cost; it does not weigh probabilities).
Fix:   Disclose as a methods design-choice / limitation, and add a comment in the
       domain explaining the rationale. Frame honestly: a hand-tuned cost to
       compensate for the lack of probabilistic action selection.
Refs:  pddl/domain_pddlstream.pddl:302; thesis methods/limitations; #163(2).

================================================================================
#165  [T1] [THESIS]  Defend "space is part of the planning" as the headline
================================================================================
Where: introduction.tex (thesis statement) + related-work.tex + discussion.tex.
What:  The crispest framing of the contribution: we make SPACE part of the
       planning state. We promote the hidden volume to symbolic regions (SHADOW
       boxels) the planner branches over, whereas TAMPURA keeps the volume
       sub-symbolic and collapses it into one predicate's success probability
       (verified: find_dice look_effects_fn). That is the concrete, defensible
       POD-vs-POMDP distinction. State it as the headline and DEFEND why it
       matters: inspectable & plannable occlusion; uncertainty without
       probabilities; the planner can deliberately clear/avoid view-blocking
       (TAMPURA places view-blind -- placement_sample has no visibility check).
Fix:   Add the headline contribution sentence (intro) + a "why this matters"
       defense (related work / discussion). Unifying thesis of #162 and #163.
Refs:  introduction.tex; related-work.tex; discussion.tex; #162; #163.

================================================================================
#166  [T2] [THESIS]  Real novelty / related-work search -- who else is near us?
================================================================================
Where: related-work.tex + references.bib (feeds #161).
What:  Before claiming novelty, run a genuine literature search for prior work
       overlapping our specific combination -- not just the papers on hand. Find
       out whether anyone has:
       - used KNOWLEDGE LITERALS / KIF-style state (POD; Kp / K-not-p) WITH
         PDDLStream or TAMP;
       - done PARTIALLY OBSERVABLE DETERMINISTIC (POD) planning in a TAMP /
         manipulation setting;
       - represented OCCLUSION / shadow regions as first-class SYMBOLIC planning
         state (object-centric, not a voxel/occupancy grid);
       - anything else doing essentially what we do.
       This substantiates-or-tempers the novelty claim AND shows "where we
       shine." A thin survey is itself a threat to the contribution (#162):
       cannot claim novel without showing what exists.
Fix:   Targeted search (Scholar / Semantic Scholar / dblp; cite-chains from LW1,
       PDDLStream, TAMPURA, SS-Replan, the Bonet/Geffner POD line). Record hits
       in references.bib; fold into the #161 enrichment; flag any work that
       overlaps our core claim so we can position against it honestly.
Refs:  related-work.tex; references.bib; #161; #162.

################################################################################
#  ISSUE --- ADDED 2026-05-22  (LW1 POSITIONING, MODEL-VS-METHOD)
################################################################################
Surfaced 2026-05-22 working session (re-read the LW1 paper + emails and
pdfs/SOURCES.md, then a model-vs-method discussion). This is the SUBSTANCE of
the LW1 comparison that #161 ("LW1 in bib but never discussed") only asks to
add. OPEN.

================================================================================
#167  [T2] [THESIS]  Position LW1 precisely: same compile-to-classical idea, but determinise-and-replan, not contingent solving
================================================================================
Where: thesis/chapters/related-work.tex (POD-lineage subsection added by #161);
       methods.tex:63 (K-literal compile-to-classical); discussion.tex:257-261
       (optimistic sense + reactive replanning); background.tex:85 (LW1 cite).
What:  The thesis builds on LW1 (bonet2014flexible) --- the K-literal / linear
       translation of a partially observable problem into classical planning ---
       and already uses its core idea (obj_at_boxel_KIF Know-If fluents), but
       never states the precise relationship, risking the implication that it
       "does LW1 / POD planning." Separate MODEL from METHOD:
       - MODEL: ours is POD --- deterministic dynamics, noiseless sensing,
         uncertainty only in the initial location of the hidden object, resolved
         by sensing. Geffner's "POMDP of a special type" (Master's thesis on POD
         TAMP.txt). NOT POMDP (no probabilities), NOT FOND/POND (no nondet
         effects). Same model class LW1 targets.
       - METHOD: we do NOT solve it the way LW1 does. LW1 tracks belief soundly
         (X(P) progression + unit resolution), selects actions via H(P), and is
         complete for width-1. We instead OPTIMISTICALLY DETERMINISE the sensing
         (assume target found), plan a classical plan, execute until an
         observation contradicts belief, then REPLAN (belief.py shadow_status ---
         the determinise-and-replan / K-replanner school, not contingent/
         belief-space solving).
       LAYER (the key clarification): LW1 is NOT a peer of FastDownward --- it is
       a POD->classical COMPILER that itself calls a classical engine (FF). The
       component LW1 would replace is our hand-written Know-If/sense PDDL
       encoding, not the inner search. So "use LW1" = swap our hand-rolled
       translation for LW1's, while STILL needing PDDLStream for geometry and
       making LW1's translation re-run against PDDLStream's per-iteration
       re-grounding --- large integration cost, little gain. -> keep LW1 as named
       lineage + method contrast; do NOT add it as a code dependency.
       Do NOT repeat two tempting-but-wrong anti-LW1 arguments:
         (a) "LW1 can't do continuous geometry" --- a non-distinction:
             FastDownward can't either; geometry lives in the PDDLStream streams.
         (b) "LW1 reintroduces the voxel blowup" --- false: the blowup is a
             property of the DISCRETISATION (uniform grid vs Boxels), independent
             of the planner; LW1 on the Boxel partition has the same small cell
             count.
       The one substantive distinction that survives is WIDTH: LW1's width-1
       completeness is the right lens for when our optimism is safe --- width-1
       occlusion (single hidden target, independent shadows) is effectively
       complete under determinise-and-replan; interacting occluders exceed
       width-1 and degrade it to sound-but-heuristic.
Fix:   (1) related-work: in the POD-lineage subsection (#161), state the
       model-vs-method split and position ours as compile-to-classical (LW1/CLG/
       K-replanner) solved by optimistic determinisation + replanning (closest
       precedent SS-Replan, #161). (2) methods: one sentence --- we adopt LW1's
       K-literal translation but solve by determinise-and-replan, not contingent
       solving. (3) discussion: state the width-1 boundary as the guarantee
       envelope. Do NOT integrate cp2fsc-and-replanner as code.
Refs:  background.tex:85; methods.tex:63; discussion.tex:257-261; belief.py;
       emails and pdfs/SOURCES.md sec 3.6 + PDF #1; bonet2014flexible,
       albore2009translation, bonet2011planning; #161 #162 #163 #165 #166.


================================================================================
OPEN ISSUES
================================================================================

7 issues remain open. Each issue's header carries its tier (T0-T3) and
disposition ([NOW] / [THESIS] / [POLISH]). Resolved issues have been removed
from this file --- see `git log --grep="Fix #"` and `git log --grep="audit:
mark"` for their record.

Structural:      #126
Related work & framing: #162 #166 #167  (#160, #161 DONE)
Why-ours-is-better & caveats: #163 (TOP PRIORITY) #164 #165  (added 2026-05-21)

Gating: #141-#156 and #130 done --- all eval-write-up
content (Results, Discussion, abstract + conclusion closure) is in
thesis/, the chapters are clear of internal file-path and hardware-spec
clutter, the front/back matter (submission date, PDDL appendix) is in
place, curated screenshots are in thesis/graphics/sim/, and nine sim
figures (boxelization companion, semantic vs uniform, sense action,
replan cycle, three-strike give-up, task triptych, n_occluders composite,
overhead-camera inset, introduction hero) are inserted across
introduction/methods/results/discussion. #125, #140, #121, #127 were closed jointly.
#126 (document-wide forward-voice conversion) is left open as a final
verification pass since the chapters individually are already
retrospective. The §5 sentence-level polish issues (#87-#111) were
resolved earlier in the audit walkthrough.
