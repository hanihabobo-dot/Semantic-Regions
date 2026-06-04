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

================================================================================
#168  [DONE 2026-05-27] [T1] [THESIS]  Figures/captions review --- go through every figure one by one
NOTE 2026-05-27: closed cumulatively. Per-figure caption/accuracy fixes landed across prior
sessions (#176 boxelization, #191 intro-hero, #197 replan-cycle removed, #198 captions, #207
success-band); the 2026-05-27 supervisor-review pass then swept every Methods/Results figure for
readability --- enlarged fonts to body-text size (4.1, 5.4-5.12), converted the success-rate /
planning-time line+band plots to grouped BAR charts (5.5-5.8; CODEBASE #113/#114), moved 5.11's
tiny in-figure note into its caption, fixed 5.10's suptitle-vs-y-label overlap (short horizontal
labels), and reconciled the 5.5 + 5.11 captions with the regenerated images. Figure-specific
follow-ups stay tracked separately: #175 (shadow figures), #209 (resolution figure).
================================================================================
Every \includegraphics: intro fig:intro-hero; methods fig:boxelization,
fig:boxelization-real, fig:partition-semantic/uniform, fig:sense-action, fig:replan-cycle;
background fig:octmap_illustration; discussion fig:retry-giveup; results plots/composites.
Per figure, triage: (1) MISREPRESENTS (image doesn't match caption/text) = T0/T1, must
fix; (2) SUBOPTIMAL (accurate but unclear) = T2/T3. Inspect each PNG visually vs caption +
referencing paragraph. One-by-one, each figure its own commit; if regenerating, ADD a new
image (never overwrite), keep old regenerable, keep paths sim/<name>.png.
Refs: introduction.tex; methods.tex; background.tex; results.tex; discussion.tex; thesis/graphics/sim/.

================================================================================
#175  [T2] [THESIS]  methods.tex shadow-splitting text vs code (CODEBASE #102/#103)
NOTE 2026-05-25: conditional/surface-resting rewrite REVERTED per author; only the "by depth"
clause was dropped. The #102 (a non-intersecting occluder casts ONE shadow, no split) and #103
(only surface-resting occluders cast shadows) reconciliations remain if wanted.
================================================================================
CODEBASE #102 made the per-occluder depth split CONDITIONAL (a non-intersecting occluder
casts ONE shadow Boxel; only a shadow overlapping another region splits into near+far +
intervening obstacles); #103 stops mid-air/held occluders casting shadows (only objects on
the support surface do). Current prose implies every shadow splits by depth — overstates the
code. Fix: reword depth-split as conditional + note the occluder must rest on a surface.
Cross-check the shadow figures in #168 (they show the two-slab case).
Refs: methods.tex; CODEBASE_AUDIT.txt #102 #103; #168.

================================================================================
#176  [DONE 2026-05-25] [T3]  Discretization-progression figure (PyBullet captures) + free-space split->merge stages (merged #196)
NOTE 2026-05-25: resolved by REGENERATING the schematic (author wanted the free-space generation
steps shown, not dropped). New fig:boxelization is a 6-panel matplotlib figure
(thesis/graphics/boxelization_stages.png, generator tools/render_boxelization_schematic.py): (a)
scene, (b) object bounding, (c) occlusion subdivision, and the three free-space stages (d) whole
workspace -> (e) recursive quad-tree split -> (f) greedy convex merge. Covers merged #196 (the
split->merge stages). Old hand-made Boxelization.png kept (not overwritten).
================================================================================
2026-05-24 capture session grabbed PyBullet GUI frames of free-space discretization
building cell-by-cell (GUI required — offscreen path can't capture debug-draw). UNIFORM
progression captured (~16 frames, raw_captures/"Screenshot 2026-05-24 125056..125436";
still = capture_partition_uniform_angle.png); a clean SEMANTIC step-by-step was NOT
captured (schematic fig:boxelization (a)-(d) already shows the semantic build). Fix: decide
(a) add a real non-schematic progression figure (~3-4 curated frames/discretization, chrome
cropped, paired w/ fig:boxelization) — incl. the merged #196 free-space stages (all space,
octree split, convex merge) via tools/render_thesis_figs.py — or (b) drop as redundant.
Refs: methods.tex (fig:boxelization); thesis/graphics/sim/raw_captures/; tools/render_thesis_figs.py; #168.

================================================================================
#177  [DONE 2026-05-25] [T0]  TAMPURA comparison: wrong task + self-contradiction (now holding, wall-clock)
================================================================================
CLOSED. Figure+abstract+results+discussion re-pointed from find-and-tray-stack to HOLDING
(the find_dice analogue); self-contradiction w/ discussion:101 removed; success stated both
sides (ours ~42% vs TAMPURA >=63%). The "planning-time only / 14.0 s / ~4x" framing was
WRONG and dropped (TAMPURA Table II time includes simulated controller execution per-episode),
so it now reports our per-episode wall-clock (mean 13.7 s) vs TAMPURA's 57 s. See #190.
CORRECTION [2026-05-27]: "per-episode" above is WRONG -- Table II is PER-STEP incl. sim execution
(arXiv v2 PDF p.15). Comparison re-derived under #213.

================================================================================
#178  [DONE 2026-05-25] [T1]  Intro says the partition discretizes "only" objects + occlusions (omits free space)
================================================================================
introduction.tex:26,33 say the partition covers "only" the objects + the regions they
occlude — drops the Free Space Boxels stage (methods.tex:36, recursive octree + greedy
convex merge; captions :20,:27,:45 say "free space"). Fix: :26 -> "...the objects the robot
detects, the regions they occlude, and the free space between them"; :33 -> drop "only",
reframe as adaptive RESOLUTION (concentrate on task-relevant regions, cover remaining free
space with coarse cells, vs uniform). Keep the semantic-vs-uniform contrast.
Refs: introduction.tex:26,33; methods.tex:36,:20,:27,:45.

================================================================================
#179  [DONE 2026-05-25] [T2]  Intro contributions: drop TAMPURA from section 1, cut the "first-class state" opener
================================================================================
introduction.tex:31: (a) confine TAMPURA to Related Work — remove the "dense visibility
voxel grid of TAMPURA's Find Die ... learned model" clause + the "architectural comparison
with TAMPURA" preview (comparison stays in Results/Discussion, #177); (b) cut the empty "we
make occlusion first-class symbolic planning state" opener, run the colon into "each volume
the robot cannot see becomes a named region a classical POD planner reasons over and resolves
by sensing." Keep ablation + oracle-perception framing.
Refs: introduction.tex:31; #177; related-work.tex.

================================================================================
#180  [DONE 2026-05-25] [T3]  Background state-model notation: Pi for the tuple is unconventional
================================================================================
background.tex:13 uses tuple Pi=<S,s_0,S_G,Act,A,f>; :69 "state model S(P)". Standard
Geffner&Bonet formalism (geffner2013concise, cited :11), but Pi conventionally = plan/policy,
so it can trip a reader. Fix (optional, author picks): (a) leave; (b) cite geffner2013concise
at :13; (c) rename tuple to a neutral letter (e.g. M).
Refs: background.tex:11,13,69; geffner2013concise.

================================================================================
#181  [T2] [POLISH]  "POD ... rather than established terminology" -- name the real term (contingent planning)
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

================================================================================
#182  [DONE 2026-05-25] [T3]  Background heading "Voxel Grids and Octrees" -> "Voxel Grids"
================================================================================
background.tex:140 heading. Shorten to "Voxel Grids" (the body :143-150 + fig:octmap still
fits — an octree is a hierarchical voxel structure). Optionally fold octree text in with a
one-line lead. Author picks.
Refs: background.tex:140,143-150 (fig:octmap_illustration).

================================================================================
#183  [DONE 2026-05-25] [T0]  related-work.tex:12 Bayes3D scaling claim + TAMPURA belief source
================================================================================
CLOSED. Dropped the wrong "scales poorly as #hypotheses/objects grows" claim (Bayes3D is
GPU-parallel, ~2048 hypotheses scored in parallel) and scoped the Bayes3D belief source to
TAMPURA's real-robot pipeline (the released Find-Die sim uses ground-truth segmentation + a
visibility voxel grid).

================================================================================
#184  [DONE 2026-05-25] [T3]  pan2024task: "reactive controllers" -> their term is "behaviors"
================================================================================
related-work.tex:15. Verified: Pan et al. (TAMPER) fill plan gaps with closed-loop
"behaviors" (hand-designed OR learned), prioritising them over re-planning (the "struggle"
claim stands). Fix: "specialized reactive controllers" -> "specialized closed-loop behaviors
(hand-designed or learned)"; rest correct.
Refs: related-work.tex:15; pan2024task.

================================================================================
#185  [DONE 2026-05-25] [T2]  Rewrite the hard-to-read Ma et al. paragraph
================================================================================
related-work.tex:20. Opener "real-world messiness" is filler; paragraph hard to read.
Ma et al. verified: Task-level Backward Search = work backward from an underspecified goal to
find needed objects; Object Manipulation Constraint Graph = order moves through clutter
collision-free. Fix: drop the opener, rewrite for clarity ("Ma et al. add a strategic
reasoning layer ... we differ at the representation level rather than adding a layer"); keep
the oracle parenthetical.
Refs: related-work.tex:20; ma2025task.

================================================================================
#186  [REJECTED 2026-05-25] [T2]  CoCo-TAMP description too thin -- expand mechanism
NOTE 2026-05-25: expansion REVERTED per author; concise one-sentence description kept by choice.
================================================================================
related-work.tex:22. Verified mechanism: LLM asked multiple-choice location questions ->
softmax over answer log-probs -> distribution over semantic locations -> hierarchical Bayesian
filter; planner consumes it via SENSING-ACTION COST (unlikely views cost more), so it drives
WHERE to look, not just the prior. Fix: expand to ~2 sentences (QA->distribution->filter +
observation-cost coupling).
Refs: related-work.tex:22; kim2026llmguided (arXiv:2603.03704).

================================================================================
#187  [DONE 2026-05-25] [T1]  related-work.tex:24 Bai et al.: wrong limitation + framework name/mechanism (merged #192)
================================================================================
related-work.tex:24 (both fixes hit the same sentences). (a) LIMITATION WRONG (T1): "adapting
... requires re-tuning hardcoded geometric constants" is NOT TRUE — retargeting to a new goal
requires NEW PDDL actions (+streams), not constants (stack goal needed a new action+predicates+
stream, #205); don't use the oracle here (it's at :20/:22). (b) NAMING+MECHANISM (T2, arXiv:
2508.05186, CVPR 2026): framework is TAVP (thesis says "TVVE"); the manipulation action is an
END-TO-END LEARNED policy (RVT-2 + action head + TaskMoE), NOT a planner, and a SEPARATE RL
policy (MVEP) selects viewpoints. Fix: (a) -> "retargeting to a new goal requires new PDDL
actions (+streams), not just a new goal spec"; (b) use "TAVP", state action is end-to-end
learned (no planner), optionally note the distinct RL viewpoint selector.
Refs: related-work.tex:24; bai2025learning (arXiv:2508.05186, "TAVP"); #205.

================================================================================
#188  [DONE] [T0] [NOW]  related-work.tex:27 belief-space paragraph: false SS-Replan contrast (+ jargon)
================================================================================
CLOSED. (1) Removed the false contrast — SS-Replan DOES plan sensing within a single plan
(drawer example; verified garrett2020online + code); restated our contribution as the named
occluded-volume REPRESENTATION. (2) Plain-languaged kaelbling2013integrated ("plan over the
robot's belief using hierarchical goal regression") and hadfield2015modular ("modular interface
exchanging info between an off-the-shelf classical planner and the geometric layer, max-
likelihood-observation determinisation"). (3) "orthogonal to the replanning loop" -> "separate
from". Follow-on refinements committed: HM MLO note; novelty claim (related-work.tex:32) scoped
vs IBSP MLOccludes / SS-Replan BOccluded near-misses + dropped stale "offline" TAMPURA framing.
Refs: related-work.tex:27,32; garrett2020online; kaelbling2013integrated; hadfield2015modular.

================================================================================
#189  [DONE 2026-05-25] [T0]  related-work.tex:30 overgeneralizes the knowledge-literal / compile-to-classical claim
================================================================================
related-work.tex:30. Verified overgeneralized: K-literal + compile-to-classical is the
TRANSLATION-BASED family (CLG, K-replanner, LW1), not all POD planning (Contingent-FF/MBP
search belief space directly; FOND route, muise2014computing, compiles to non-deterministic).
Fix: scope the opener to "a prominent line within it ...: CLG ... K-replanner ... LW1 ..." +
a clause that other planners search belief space / compile to FOND; rest unchanged.
Refs: related-work.tex:30; albore2009translation, bonet2011planning, bonet2014flexible, muise2014computing, geffner2013concise.

================================================================================
#190  [DONE 2026-05-25] [T0]  TAMPURA model-learning is ONLINE per-step (was framed "pays it offline")
================================================================================
CLOSED. The false "offline Learn-Model" framing removed from discussion.tex / results.tex:108 /
conclusion.tex:10 and reconciled in THESIS_NOTES §21.3: both systems sample online per-step;
real difference = TAMPURA's probabilistic learned-MDP (solved for a policy) vs our deterministic
knowledge-literal planning w/ replanning. Code-verified (tampura policy.py / tampura_policy.py /
config/default.yml: from_scratch=true, envelope_threshold=1).
Parked follow-ons (NOT part of this fix): (a) solve_mdp defaults to value iteration, not LAO* —
prose still says "LAO*"; (b) Table II times include controller execution, so #177's old
planning-time framing was itself wrong (wall-clock is the closer analogue).
CORRECTION [2026-05-27]: (b) understated it -- Table II is PER-STEP incl. execution (arXiv v2 PDF
p.15), so even "per-episode wall-clock vs 57 s" is unit-mismatched. Re-derived under #213.

================================================================================
#191  [DONE 2026-05-25] [T3]  Intro hero caption: identify the target object
================================================================================
introduction.tex:19 (fig:intro-hero). Caption never says which object is the target. Fix: add
"the target is the cyan cube behind the green cube"; verify vs image (#168) first.
Refs: introduction.tex:19; #168.

================================================================================
#192  [MERGED 2026-05-25 into #187]  Bai et al.: TAVP naming + end-to-end-learned-policy
================================================================================
Folded into #187 (same related-work.tex:24 Bai et al. paragraph).

================================================================================
#193  [T1] [THESIS]  Relocate/shrink "Spatial Belief Representation in TAMP" into Background
================================================================================
related-work.tex:39-52 (octree + Critical Regions limitations) reads like BACKGROUND, point
unclear. Intended message is small: octrees and Critical Regions were inspirations, neither
usable out of the box. Background already has the homes (octrees :140 #182; CRs :156). Fix:
merge the limitation content into the background subsections, delete the related-work section
(leave a brief note); decide where the belief-space-replanning sentence (:35) belongs (#188 or
background).
Refs: related-work.tex:39-52,35; background.tex:140,156; #182; #188.

================================================================================
#194  [DONE 2026-05-25] [T2]  Related-work framing: drop marketing voice; cut the over-long "three advantages" paragraph
================================================================================
related-work.tex:35 "sits at the intersection" = marketing -> "we build on / extend ...";
:37 three-advantages paragraph far too long (restates occlusion-as-state / no-probabilities /
no-MDP w/ costs) -> condense to a few sentences or compact list.
Refs: related-work.tex:35,37.

================================================================================
#195  [DONE 2026-05-25] [T2]  Methods clarity: rephrase "optimistic determinisation", explain "untyped STRIPS", delete a self-justification
================================================================================
methods.tex:63,87,90,133. (O) "optimistic determinisation and reactive replanning" opaque ->
"assume each sensing action succeeds (optimistic), plan as if the world were fully known,
execute, and replan when an observation contradicts that (reactive replanning)". (P) "untyped
STRIPS" unexplained -> gloss "no PDDL type declarations, so object categories are ordinary
predicates not types". (Q) delete the ":133 standard pattern" self-justification.
Refs: methods.tex:63,87,90,133.
NOTE 2026-05-25: (P) untyped-STRIPS gloss REVERTED per author; (O) optimistic-determinisation
gloss and (Q) self-justification deletion stand.

================================================================================
#196  [MERGED 2026-05-25 into #176]  Free-space generation stages (split -> convex merge) figure
================================================================================
Folded into #176. Content: a methods.tex figure of the free-space build — (1) all space incl.
objects, (2) recursive octree split, (3) recursive convex merge — via tools/render_thesis_figs.py.

================================================================================
#197  [DONE 2026-05-25] [T1]  fig:replan-cycle caption is wrong vs the image
NOTE 2026-05-25: resolved by REMOVING the figure. The image is a drop-on-tray action, unrelated
to sensing/replanning (author-confirmed); recapture declined. Figure + in-text reference deleted.
================================================================================
methods.tex:145 (sim/replan_cycle.png). Caption ("action log reads 'sense
shadow_of_purple_object --- target not here' ... marks shadow empty ... searching remaining
shadows") does NOT match the image. Fix: inspect the PNG (#168), rewrite caption to match the
actual logged action/scene; recapture if the image is wrong.
Refs: methods.tex:145; sim/replan_cycle.png; #168.

================================================================================
#198  [DONE 2026-05-25] [T3]  Figure captions/sizes to fix after visual inspection
NOTE 2026-05-25: (M) boxelization-real caption corrected (free-space cells ARE rendered in cyan,
author-confirmed). (N) partition-comparison subfigs already equal-size (0.48\textwidth); added
cyan/free-space + object/shadow colour meanings. (T+U) eval-scene caption: dropped unclear "labelled
in the overlay" claim, described the RGB/depth insets (no recapture). (AV) fig:retry-giveup REMOVED
(image has no "retry 3/3"/action log; author chose remove).
================================================================================
(M) methods.tex:27 fig:boxelization-real — update caption from the current image. (N)
methods.tex:40-57 fig:partition-comparison — make subfigures EQUAL SIZE, update caption, state
what each colour means. (T+U) results.tex:79 eval-scene — "objects and occlusion shadows
labelled in the overlay" unclear + needs a new image; rewrite after inspection. (AV)
discussion.tex:293 fig:retry-giveup — "retry 3/3" caption stale, re-inspect. Inspect each PNG
(#168); ADD any regenerated image, never overwrite.
Refs: methods.tex:27,40-57; results.tex:79; discussion.tex:293; #168.

================================================================================
#199  [T2] [THESIS]  Rename task terms to reader-facing names (drop code terms)
================================================================================
Document-wide. Code task names confusing in prose. Use FIND (= holding; locate a hidden object
and pick it), STACK, FIND AND STACK (= find-and-tray-stack). Fix: rename in PROSE only (holding
-> find; find-and-tray-stack -> find and stack; stack stays); keep figure FILE names; axis
labels may need a plotter label map (CODEBASE). Audit-internal refs in #177/#190 keep "holding".
Refs: results.tex; discussion.tex; conclusion.tex; abstract.tex; methods.tex; #177.

================================================================================
#200  [DONE 2026-05-25] [T0]  results:83 "well under a second per call" is FALSE
================================================================================
results.tex:83. Data-contradicted (sweep_anytime): pooled per-call planning over successful
cells median ~1.99 s, mean ~5.4 s, only ~19% <1 s. By goal: stack 0.97 s (54% <1s); find 2.05 s
(10%); find-and-stack 2.97 s (3%). Fix: replace w/ real per-goal medians; describe the 1800 s
cap as a safety bound hit only by rare pathological/timeout cells. Drop "well under a second".
Refs: results.tex:83; eval_results/sweep_anytime (per_call_planning_time_s).

================================================================================
#201  [DONE 2026-05-25] [T2]  Results clarity: drop_failed, denominator note, "known to be empty", one-boxel-per-object
================================================================================
results.tex:96,98,105. (Y) drop_failed unexplained -> when the gripper can't release a non-
target object, after three failed drop events the episode exits (depends on CODEBASE #106). (Z)
":98 two denominators differ by ~6% (early timeouts without a recorded state)" opaque -> rephrase
plainly. (AA) ":105 where the workspace is empty" -> "...KNOWN to be empty" (belief). (AC) "finer
leaves break placement" is a design choice (each object bounded by exactly ONE boxel) — explain.
Refs: results.tex:96,98,105; CODEBASE_AUDIT #106.

================================================================================
#202  [DONE 2026-05-25] [T1]  semantic+mbs0.05 is effectively identical to semantic (a no-op variant)
================================================================================
results.tex:106. Data-confirmed: semantic+mbs0.05 = plain semantic to ~0.1% (find 35.07 vs
35.03), same results — the 5 cm floor never binds (autosize ~6-9 cm) and finer floors are
absorbed by the convex merge (#203). Presenting it as "testing a finer floor" is misleading.
Fix: drop the variant or reframe honestly as evidence the floor does NOT change the partition
(merge dominates). Coordinate w/ #203, CODEBASE #108.
Refs: results.tex:106; eval_results/sweep_anytime; #203; CODEBASE_AUDIT #108.

================================================================================
#203  [DONE 2026-05-25] [T0]  discussion:60 "at the cost of more cells" is FALSE; "characterisation of the regime" is empty
================================================================================
discussion.tex:60. (AK) Data-contradicted: a finer free-space floor does NOT add cells (greedy
convex merge -> counts identical across semantic/mbs0.05/mbs0.09, e.g. stack free 17.64 in all);
only COARSER floors reduce counts. (AL) "characterisation of the regime, not a defect" = filler.
Fix: correct to "min free-space leaf size has little effect on cell count (convex merge); only
coarsening reduces it"; delete the filler sentence. Figure: CODEBASE #108.
Refs: discussion.tex:60; eval_results/sweep_anytime; #202; CODEBASE_AUDIT #108.

================================================================================
#204  [DONE 2026-05-25] [T2]  discussion:24 stack-goal boxel ratio -- stack needs no free-space partition
================================================================================
discussion.tex:24 ("stack ratio steeper, semantic ~25 vs uniform ~1340"). Stack is fully
observable and needs no free-space partitioning, so the ratio isn't meaningful there. Fix: drop
it, or state stack is fully observable (no shadows) so the ratio reflects only the uniform
baseline's free-space blow-up, not a partial-observability benefit.
Refs: discussion.tex:24.
NOTE 2026-05-25: resolved by DELETING the stack-ratio sentence (author: don't mention stack/uniform here).

================================================================================
#205  [DONE 2026-05-25] [T0]  discussion:266 stacking slowdown misattributed (bigger domain, not pick conditional-effects)
================================================================================
discussion.tex:266 ("stacking ~doubles per-call planning, traced to the pick conditional-
effects requirement"). Code-contradicted (git 0d5def7): "add --goal stack" added all at once a
new stack action (7 pre/6 eff), 3 predicates (on, clear, stack_kin), a stream compute-stack-kin,
AND the conditional :requirement + forall-when on pick (which grounds to a no-op on find runs).
So the slowdown is a LARGER DOMAIN, not the pick conditional effect. Fix: re-attribute to the
enlarged domain (added action+predicates+stream raising grounding/search cost).
Refs: discussion.tex:266; pddl/domain_pddlstream.pddl; git 0d5def7.
NOTE 2026-05-25: resolved by REMOVING the stacking-slowdown claim entirely (author: don't mention
that adding stacking made things slower). No misattribution remains.

================================================================================
#206  [DONE 2026-05-25] [T2]  Discussion section-6 trims and clarity
================================================================================
discussion.tex. (AO) delete the whole \section{Failure modes} (:123) — duplicates results
coverage. (AN) remove :121 "restoring a blocked view ... give-up rule" clause. (AQ) remove :239
"local IK solver bypasses collision checks" sentence. (AS) remove :258 "string identifiers as
proxies for geometric volumes" sentence. (AU) remove :268 "this regression is accepted rather
than optimized away" sentence. (AP) :168 "would narrow" -> "could narrow". (AR) :245 explain
"non-pathological start configuration" = a collision-free start configuration for the next move.
Refs: discussion.tex:121,123,168,239,245,258,268.

================================================================================
#207  [DONE 2026-05-25] [T3]  Success-rate-vs-n_occ caption should state what the band is
================================================================================
results.tex (success-rate-vs-n_occ fig). The shaded band is +/-1 SAMPLE STD of per-trial 0/1
success flags over ~80-100 seeds/point (clipped [0,1]) — NOT a CI. Fix: say so in the caption;
optionally switch to a Wilson interval (CODEBASE #112).
Refs: results.tex; eval_plotter.py (group_success_rate, plot_metric); CODEBASE_AUDIT #112.

================================================================================
#208  [T3] [THESIS]  Add the code repository links (GitHub + GitLab)
================================================================================
The thesis never says where the implementation lives (GitHub + GitLab). Fix: add both URLs
(author to PROVIDE — do not guess) as a code-availability footnote/statement.
Refs: introduction.tex / abstract.tex / appendix.tex.

================================================================================
#209  [T2] [THESIS]  Results: resolution-floor sweep -- effect of min free-space leaf size on total boxel count
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
#210  [T3] [POLISH]  Related Work: drop author names, cite by number ([4]) --- VERY LOW PRIORITY
================================================================================
related-work.tex throughout. Replace inline "<Author> et al." lead-ins with numeric citation
labels (e.g. "[4] introduces ..."). Mechanical low-priority polish once T0/T1 content is settled;
watch sentences whose grammar depends on the author name as subject.
Refs: related-work.tex (document-wide citation style).

================================================================================
#211  [DONE 2026-05-26] [T1]  Abstract repeats #178's "only" (omits free-space Boxels)
================================================================================
abstract.tex:6 said "...cuboids that discretise only the objects and the regions they
occlude" -- the same false "only" that #178 fixed in the intro, but the abstract was missed.
It drops the Free Space Boxels (methods.tex octree + greedy convex merge; the partition has
object, occlusion AND free-space cells). Fix: "...concentrate resolution on the objects and
the regions they occlude, covering the free space with a few coarse cells", matching
introduction.tex:26,33.
Refs: abstract.tex:5-7; #178; introduction.tex:26,33; methods.tex.

================================================================================
#212  [DONE 2026-05-26] [T1]  Abstract: drop TAMPURA, clarify "compiling belief", fix false "no speed winner"
================================================================================
Three author-reported abstract fixes: (1) "Compiling the belief over Boxel occupancy to Know-If
literals" was opaque -> "...belief about which Boxels are occupied is encoded as Know-If literals
---one per Boxel, marking whether its contents are known---so...". (2) Remove the TAMPURA
holding/Find-Die comparison from the abstract (author: no TAMPURA in the abstract); it stays in
results/discussion. (3) The deleted "...implies no speed or quality winner" was false on speed --
we are ~4x faster (13.7 vs 57 s); dropping the TAMPURA sentences removes the hedge and the speed
advantage now stands plainly against the uniform baseline. NOTE: results/discussion still carry
the TAMPURA "no winner" framing (#177) -- correct the speed-winner wording there separately if wanted.
Refs: abstract.tex:8-15; #177; #211; results.tex; discussion.tex.

================================================================================
#213  [DONE 2026-05-27] [T1]  TAMPURA Table II is PER-STEP, not per-episode (arXiv v2 PDF) -- re-derive comparison
================================================================================
TRUTH (source: arXiv:2403.10454 v2 PDF p.15, Table II + caption; author screenshot 2026-05-27).
Caption verbatim: "Average and standard deviation of PER-STEP planning times (seconds) averaged
over trials and steps within each trial.  These include execution time of the selected controller
in simulation."  So the Partial-Observability cell (Bayes-Optimistic + LAO*) 57 +- 38 is PER-STEP
INCLUDING simulated controller execution -- NOT per-episode, NOT planning-only.

SOURCE OF MISCONCEPTION: the paper states something different than the PDF -- the v2 PDF Table II
caption (per-step, above) is authoritative.  #177 and #190(b) both recorded 57 s as "per-episode
(incl. execution)"; that is the error this issue corrects.

Matched axes (author decision 2026-05-27, "both, per-episode primary"):
  - PER-EPISODE, SAME HARDWARE (primary; the figure): TAMPURA find_dice local on our Ryzen 7730U
    (runs/sweep_2026-05-26.json) = 166 +- 85 s/ep success-only (n=11), 240 +- 151 all (n=20),
    success 55%; OURS holding-semantic = 13.7 s/ep (success-only, median 8.5), success 42%
    (127/300).  ~12x slower per successful episode, more reliable.
  - PER-STEP (prose reconciliation, vs the PUBLISHED number): TAMPURA 57 +- 38 s/step (paper);
    OURS = wall_clock/plan_count = 13.676/2.315 = 5.9 s per PDDLStream solve (avg 2.315 plans/ep,
    holding-semantic success-only, execution-inclusive to match).  ~9.7x.  UNIT CAVEAT: a TAMPURA
    "step" = one control-action re-solve; our "plan" = one solve executing a multi-action plan.
Cross-environment caveat stays (find_dice containment vs our lateral-shadow holding).

DO: (a) trackers+notes record truth [this commit]; (b) eval_plotter figure -> local 166 +- 85;
(c) results/discussion/conclusion -> 13.7 vs 166 primary + 5.9 vs 57 per-step; (d) THESIS_NOTES
§21.2/§21.5.
DONE [2026-05-27]: trackers+notes+figure+prose all landed; figure regenerated to 166 +- 85
same-HW per-episode; results/discussion/conclusion now report 13.7 vs 166 (same HW) + 5.9 vs 57
per-step.
Refs: results.tex subsec:tampura; discussion.tex sec:disc-tampura; conclusion.tex:10;
eval_plotter.py plot_tampura_wallclock_comparison; THESIS_NOTES §21; #177; #190; CODEBASE_AUDIT.txt.

--------------------------------------------------------------------------------
NB (verified, NO issue filed):
 - discussion.tex:121 "an object can be placed view-blind" (TAMPURA) is TRUE — verified from
   find_dice code (placement sampler = uniform x/y + random yaw, no visibility check; place has
   no visibility precondition). Optionally add a one-line basis. [code-confirmed]

================================================================================
SUPERVISOR REVIEW BATCH --- #214-#253 added 2026-06-01
================================================================================
Source: Till Hofmann's annotated PDF (thesis/20260527_hani-thesis-comments.pdf, returned
2026-05-27) + his cover email (2026-05-31). Full verbatim transcription with page images:
thesis/supervisor_comments_20260527.md. EVERY annotation is filed below --- including the
three highlights with no written comment and the bare "?" --- per author request.
Annotation kind: [INK] handwritten margin note - [TYPED] typed comment on a highlight -
[HL-ONLY] highlight with no written comment. Pages are PRINTED thesis pages (PDF = printed+6).
Tiers/dispositions are my triage; re-tier freely. Open questions to raise with Till Wed 2026-06-03.

================================================================================
#214  [DONE 2026-06-01] [T2] [POLISH]  Abstract: "Semantic Boxel" used before it is defined -- p.iii (PDF4)
================================================================================
[INK] "not defined yet", pointing at the highlighted term "Semantic Boxel".
The thesis's central term appears in the abstract with no gloss. Add a one-clause
definition at first use (or an explicit "(defined in Sec. 4.x)" forward-ref).
Refs: abstract.tex; #211; #212; supervisor_comments_20260527.md.

================================================================================
#215  [DONE 2026-06-01] [T3] [THESIS]  Abstract: "PDDLStream-based planner" highlighted, no comment -- p.iii (PDF4)
NOTE 2026-06-01: PDDLStream is already defined (background.tex:103 "PDDLStream for TAMP" subsection)
and is a published, citable framework --- NOT a Boxel-style neologism --- so no abstract definition is
warranted. Per author decision, added the citation \cite{garrett2018pddlstream} and a brief gloss
("classical search plus continuous samplers") to the abstract at first mention. Not actioned
as a "define it" item.
================================================================================
[HL-ONLY] no written note. Intent unclear; most likely flags that the descriptor needs
introduction, or questions "PDDLStream-based" vs the FastDownward backend the system
actually plans with (cf. #241 and the planned FastDownward section, #253). Confirm with Till Wed.
Refs: abstract.tex.

================================================================================
#216  [DONE 2026-06-01] [T2] [NOW]  Intro: sensing actions do not "succeed" -- p.2 (PDF8)
NOTE 2026-06-01: reworded intro:28 and methods:63 from "assumed to succeed" / "succeeds" to
"yields the outcome the plan expects (optimistic)". methods:79 already used outcome framing
("assumes the target is found", "true outcome") --- left as-is. Grep over chapters/ found no
other sensing-success framing (discussion.tex clean).
================================================================================
[INK] "usually there is no 'success' in sensing actions; you just assume a certain
outcome", on the highlighted clause "---a sensing action is assumed to succeed".
Reword: sensing is modeled by ASSUMING an outcome (optimistic determinisation), not by
"succeeding". Align with the sense-action framing in methods + discussion.
Refs: introduction.tex; methods.tex (sense action); discussion.tex:261.

================================================================================
#217  [DONE 2026-06-01] [T2] [POLISH]  Intro: briefly explain Know-If Fluents at first mention -- p.3 (PDF9)
NOTE 2026-06-01: added an em-dash gloss at intro:34. CORRECTED per author: Know-If Fluents are a
general construct that predates (and is not specific to) Boxels, so the gloss must not define them
via Boxels --- now reads "atoms marking whether the truth of a fact is known". "over Boxels" stays
in the sentence (that is the application). Full definition stays in Background.
================================================================================
[TYPED] "briefly explain what they are", on "Know-If Fluents over...". Add a one-line
plain gloss at the first mention in the intro.
Refs: introduction.tex; #223; #224.

================================================================================
#218  [DONE 2026-06-01] [T2] [POLISH]  Background: introduce states directly as sets of atoms -- p.4 (PDF10)
NOTE 2026-06-01: reworked the state-space-model itemize (background.tex:15-20) so a state is
introduced as a set of ground atoms with atom notation (S, s0, SG, f examples), and trimmed the
later STRIPS paragraph (:25) that re-introduced "a state is a set of propositions".
================================================================================
[INK] "Directly introduce states as sets of atoms". Streamline the state-model
definition to present a state as a set of atoms up front, without the longer build-up.
Refs: background.tex; #180.

================================================================================
#219  [SKIPPED 2026-06-01] [T3] [POLISH]  Background: "see before" -- redundant with earlier text -- p.5 (PDF11)
NOTE 2026-06-01: skipped per author --- redundancy target ambiguous from the ink. Candidates: the
initial-state/goal concept stated 3x (background.tex:16-17 state-model, :40 STRIPS, :65-66 PDDL),
or the add/delete re-explanation at :60. Confirm exact location with Till Wed if revisited.
================================================================================
[INK] "see before". The passage repeats something already stated earlier; cut or condense
and cross-reference instead of restating.
Refs: background.tex.

================================================================================
#220  [DONE 2026-06-01] [T3] [POLISH]  Background: do not expand the STRIPS acronym -- p.5 (PDF11)
NOTE 2026-06-01: changed the only \ac{strips} (background.tex:27) to \acs{strips}, so STRIPS no
longer expands inline. All other mentions were already plain "STRIPS". Acronym-list entry
(acronyms.tex:5) keeps the expansion (conventional) per author -- inline fix only.
================================================================================
[INK] "no need to show full name / the acronym lost its original meaning". Drop the
full expansion of STRIPS; use the acronym alone.
Refs: background.tex.

================================================================================
#221  [SKIPPED 2026-06-01] [T3] [THESIS]  Background: bare highlight on "The" -- p.5 (PDF11)
NOTE 2026-06-01: skipped per author. Bare highlight on the stop-word "The", no comment; grep found
no doubled-article typo and ~10 grammatical "The..." sentence starts on the page. Unactionable from
the ink. Confirm with Till Wed if revisited (mild candidate: background.tex:43 "The PDDL...").
================================================================================
[HL-ONLY] the single word "The" is highlighted with no note. Intent unclear --- likely a
local wording/typo flag (e.g. a duplicated article or an awkward sentence opening) at that
spot. Inspect the sentence; confirm with Till Wed if not obvious.
Refs: background.tex.

================================================================================
#222  [DONE 2026-06-01] [T0] [NOW]  Background: is goal_achieved an atom? -- p.7 (PDF13)
NOTE 2026-06-01: replaced the example $K(goal\_achieved)$ (background.tex:93) with a genuine goal
atom $K(holding(target\_obj))$ --- answers "is it an atom?" (yes), drops the implicit dependence on
a derived goal_achieved predicate the simplified planner does not define, and matches methods.tex:76.
================================================================================
[TYPED] "is goal-achieved an atom?", on the highlighted "K(goal_achieved)---". Verify and
make the formalization precise: state whether goal_achieved is an atom (and if so, how it
is defined), or rephrase the notation.
Refs: background.tex.

================================================================================
#223  [DONE 2026-06-01] [T0] [NOW]  Background: cite the origin of Know-If Fluents -- p.7 (PDF13)
NOTE 2026-06-01: Till's "Brewer/Breuer et al." matches NO real author. Investigation (per author's
hint to check who the cited sources credit): the Geffner-Bonet textbook we cite (geffner2013concise,
pp.69/88) and the LW1 poster (bonet2014flexible) both attribute the K(L)/K(\neg L) translation --- what
this thesis calls a KIF --- to PALACIOS & GEFFNER (2006 AAAI original / 2009 JAIR). Web searches for
"Know-If fluent" and for Brewer/Bremer/Breuer/Breuuer in TAMP/POD/planning/AI returned nothing. Added
\cite{palacios2006compiling} (AAAI 2006, pp.900-905) at background.tex:93. ACTION: confirm the surname
with Till Wed --- he almost certainly meant Palacios & Geffner.
================================================================================
[INK] "KIFs were originally introduced by Brewer et al. --- cite!"  (SURNAME to confirm:
the ink reads "Brewer" OR "Breuer"; no citation for the KIF origin exists anywhere in the
thesis today.) Find the originating paper and add the citation at first use.
Refs: background.tex; resources/references.bib; supervisor_comments_20260527.md.

================================================================================
#224  [DONE 2026-06-01] [T2] [THESIS]  Background: motivate KIFs vs K-literals -- p.7 (PDF13)
NOTE 2026-06-01: appended a motivation sentence at background.tex:93. REVISED per author (the reason
is fluent economy, verified against domain.pddl:42-45): the domain already carries the value fluent
obj_at_boxel for geometry, so a single Know-If flag (obj_at_boxel_KIF) replaces the K(L)/K(neg L)
pair -- one knowledge fluent per fact instead of two, and no mutual-exclusion axioms. Head-to-head
the counts match ("equivalent encoding", discussion.tex:260), but vs value+K-pair it saves one and
drops the axioms. Ties to #237 (Methods KIF/K-literal consistency) and #239/#248 (deductive axioms).
2026-06-01 (2nd pass): prose simplified per author to one plain sentence ("keep the belief compact...
a single flag per fact... instead of two separate knowledge literals"); the axiom angle is kept here
in the audit but dropped from the thesis sentence for readability.
================================================================================
[INK] "Why KIFs instead of K literals?" Add a sentence motivating the design choice (the
single Know-If fluent collapses the K(p)/K(not p) pair --- see discussion.tex:258-259).
Tightly related to #237 (the same KIF-vs-K-literal confusion flagged in Methods).
Refs: background.tex; discussion.tex:258-259; #237.

================================================================================
#225  [DONE 2026-06-01] [T2] [NOW]  Related Work: "Sidd's Critical Regions" -- is that the real term? -- p.10 (PDF16)
NOTE 2026-06-01: dropped the informal "Sidd's" (Siddharth Srivastava) from the bold heading at
related-work.tex:52 -> "Critical Regions (CRs):". The (CRs) abbreviation it introduces is kept.
================================================================================
[TYPED] "do they call it that? if not, just call them critical regions", on "Sidd's
Critical Regions." Verify the source's terminology; most likely drop "Sidd's" and just
write "critical regions".
Refs: related-work.tex.

================================================================================
#226  [DONE 2026-06-01] [T0] [NOW]  Related Work: "combines these techniques" -- you don't learn regions -- p.10 (PDF16)
NOTE 2026-06-01: actual locus is background.tex (not related-work). Reworded background.tex:161 "Our
work combines these techniques" -> "borrows the idea of task-relevant spatial regions, but constructs
Boxels geometrically from detected objects and their occlusions rather than learning a region
predictor" -- corrects the false implication that we learn regions. ALSO fixed a SECOND "Sidd's
Critical Regions" heading at background.tex:156 -> "Critical Regions." (the #225 issue's likely true
locus, same page; the related-work.tex:52 copy was fixed under #225).
================================================================================
[TYPED] "Is that really correct? You don't learn any regions", on "...combines these
techniques". Correct the claim --- our method does not learn regions; reword to match what
the system actually does.
Refs: related-work.tex.

================================================================================
#227  [DONE 2026-06-01] [T2] [POLISH]  Related Work: "treated by Geffner and Bonet" is unclear -- p.13 (PDF19)
NOTE 2026-06-01: reworded related-work.tex:30 "The underlying models are treated by Geffner and Bonet"
-> "The formal models these planners rest on...presented in Geffner and Bonet's textbook" (names the
models, replaces vague "treated"). 2nd pass (same day): per author, DELETED the sentence entirely --
it was a low-value textbook pointer and the textbook is cited in Background where the models are
introduced. The reword is superseded by the deletion.
================================================================================
[TYPED] "not sure what this means", on "The underlying models are treated by Geffner and
Bonet [1...". Reword the sentence so the point is explicit.
Refs: related-work.tex.

================================================================================
#228  [DONE 2026-06-01] [T3] [POLISH]  Related Work: add a back-reference to Section 2.2 -- p.13 (PDF19)
NOTE 2026-06-01: 2.2 = "Planning under Partial Observability" (background.tex:81), which was unlabeled.
Added \label{sec:pod} there and a (\cref{sec:pod}) at related-work.tex:30 after "knowledge literals".
================================================================================
[INK] "refer back to 2.2". Add a \cref back to Section 2.2 where this material was
introduced.
Refs: related-work.tex.

================================================================================
#229  [DONE 2026-06-01] [T2] [POLISH]  Related Work: "?" on the bounded-give-up sentence -- p.14 (PDF20)
NOTE 2026-06-01: per author + supervisor "?", DELETED the confusing trailing clause at
related-work.tex:37 (", an invariant the bounded give-up on unreachable shadows (\cref{sec:limitations})
deliberately relaxes."). Sentence now ends at "...sound only while belief reflects observation."
================================================================================
[INK] a bare "?" beside the highlighted sentence "...an invariant the bounded give-up on
unreachable shadows (Section 6.5) deliberately relaxes." Till does not follow the sentence;
reword for clarity (the forward-ref to 6.5 from Related Work is also awkward this early).
Refs: related-work.tex.

================================================================================
#230  [SKIPPED 2026-06-01] [T1] [THESIS]  Related Work: cite the AAAI'25 online critical-regions follow-up -- p.15 (PDF21)
NOTE 2026-06-01: skipped per author -- confirm the exact paper with Till Wed. INVESTIGATION: no paper
literally titled/about "critical regions online" found (web + Srivastava's lab page). The term likely
drifted (author's hunch): the lab's line went critical regions -> learned abstractions -> option
invention -> world models. STRONGEST CANDIDATE = Rashmeet Kaur Nayyar & Siddharth Srivastava,
"Autonomous Option Invention for Continual Hierarchical Reinforcement Learning and Planning", AAAI 2025
(ojs.aaai.org/index.php/AAAI/article/view/34163) -- right lab, right venue, "Continual" = "online".
BUT it is temporal OPTIONS + continual state abstraction, NOT spatial critical regions updated online;
thematic match, not literal. (sns_corl25.pdf = "Learning Symbolic World Models...", CoRL 2025, is a
different paper -- world-model invention, also not it.) WHEN RESOLVED: (b) scope the static claim to
\cite{shah2022abstractions} at related-work.tex:52 + background.tex:159 (currently overstates "CRs do
not adapt"), and optionally add the confirmed AAAI'25 cite as the line's move to continual abstraction.
Refs: related-work.tex:52; background.tex:159; shah2022abstractions; molina2020learn.
================================================================================
[INK] "There is actually a follow-up paper where they modify CRs online --- AAAI '25".
Locate the AAAI 2025 follow-up that modifies critical regions online, cite it, and update
the surrounding claim.
Refs: related-work.tex; resources/references.bib.

================================================================================
#231  [INFO] [NO ACTION]  Methods: "good intro so far" -- p.16 (PDF22)
================================================================================
[INK] positive margin note. Recorded for completeness; no action.

================================================================================
#232  [DONE 2026-06-01] [T3] [POLISH]  Methods: simplify the (BXset) symbol -- p.16 (PDF22)
NOTE 2026-06-01: dropped the "set" subscript -> $\mathcal{BX}$, in both the inline use (methods.tex:16)
and the nomenclature rendering (symbols.tex:67, key boxel_set kept). Only occurrence of the symbol.
================================================================================
[TYPED] "Why not just BX?", on the highlighted "(BXset)" (script-B X with the "set"
subscript). Consider simplifying the notation to "BX".
Refs: methods.tex.

================================================================================
#233  [DONE 2026-06-01] [T2] [THESIS]  Methods: separate the concept from the implementation -- p.16 (PDF22)
NOTE 2026-06-01: moved the implementation detail out of the conceptual section. methods.tex:16 (sec 4.2
concept) keeps the adaptivity ("re-run as the scene changes"); the "Python stage before each planner
call, not a PDDLStream procedure" fact moved to the PDDLStream Integration section intro (methods.tex:84).
================================================================================
[TYPED] "Try to separate the conceptual description from the implementation", on "It runs
as a Python stage...". Split conceptual description from implementation detail (the
"Python stage" wording belongs to the implementation part).
Refs: methods.tex; #195.

================================================================================
#234  [INFO] [NO ACTION]  Methods: "good figure!" -- p.17 (PDF23)
================================================================================
[INK] positive margin note (on the Methods figure, ~Fig 4.1). Recorded for completeness; no action.

================================================================================
#235  [SKIPPED 2026-06-01] [T2] [THESIS]  Methods: "Line of sight" legend entry -- "I don't see it" -- p.17 (PDF23)
NOTE 2026-06-01: skipped per author. DIAGNOSIS (fig:boxelization, generator
tools/render_boxelization_schematic.py): the LOS dashed rays ARE drawn in panel (c) (_los(), line
347-351: camera->objects, linestyle (0,(4,3))) but in faint light gray (C_LOS=#95a5a6) at zorder=2,
i.e. UNDER the occlusion patches (zorder=3) and objects -- so they read as nearly invisible in print
("I don't see it"). FIX IF REVISITED: raise the LOS zorder above the occlusion/object layers (e.g.
zorder>=6) and darken/thicken C_LOS; then regenerate boxelization_stages.png and inspect visually.
================================================================================
[INK] "I don't see it", pointing at the "Line of sight" legend entry. The legend names a
line-of-sight element that is not visible in the figure. Make it visible or remove the
legend entry.
Refs: methods.tex; the referenced figure + its generator.

================================================================================
#236  [DONE 2026-06-01] [T3] [NOW]  Methods: Fig 4.2 is not referenced in the text -- p.17 (PDF23)
NOTE 2026-06-01: Fig 4.2 = fig:boxelization-real (PyBullet-scene partition), which was only \label'd,
never \cref'd. Added a \cref at methods.tex:16 alongside the schematic fig:boxelization. Checked the
other Methods figures: fig:sense-action IS referenced (methods.tex:133), so no further unref'd figures.
================================================================================
[INK] "This fig is not referenced in the text". Add a \cref to Fig 4.2 from the body.
Refs: methods.tex.

================================================================================
#237  [DONE 2026-06-01] [T1] [NOW]  Methods: KIFs vs K-literals -- "I'm confused" -- p.19 (PDF25)
NOTE 2026-06-01: added a bridging sentence at methods.tex:61 (sec:kif_belief): "a Know-If fluent is
exactly this K(L)/K(neg L) pair; the implemented domain represents it more compactly as one flag
(obj_at_boxel_KIF) together with the location value, an equivalent encoding..." -- ties the three
terms (KIF / K-literal / single fluent) together. Consistent with #224 (background) and discussion.tex:258-261.
2nd pass 2026-06-01: re-explained clearer per author -- spells out the three belief cases (known
true / known false / unknown) and states plainly "the K-literals are the concept, the single flag
(obj_at_boxel + obj_at_boxel_KIF) is its implementation".
3rd pass 2026-06-01: flipped to KIF-forward per author ("why have K-literals as the concept?"). Now
Know-If is the concept; K-literals are demoted to "the standard pair-form that carries this knowledge",
cited for grounding; single flag is the implementation. Consistent with the #224 background framing.
================================================================================
[TYPED] "I'm confused, do you use KIFs or K literals?", on "belief carries the K-literal
K(InBoxel(obj, Boxel))...". The text switches between Know-If Fluents and K-literals.
Make terminology consistent throughout and point to the clarification in discussion.tex:258-259.
Refs: methods.tex; discussion.tex:258-259; #224.

================================================================================
#238  [DONE 2026-06-01] [T1] [THESIS]  Methods: state explicitly that this is simplified POD planning -- p.22 (PDF28)
NOTE 2026-06-01: at methods.tex:133, scoped the "functionally equivalent to a conditional plan" claim
to "this single-target search", and added an explicit framing: "a deliberately simplified form of POD
planning---a single optimistic plan repaired by replanning, rather than the branching contingent plans
of a full POD planner; suffices for the tasks evaluated here but not for problems that require
contingent reasoning (\cref{sec:limitations})". Kept lean to avoid #251 redundancy; #239 adds the
deductive-axioms specifics, #248 is the Discussion side.
================================================================================
[INK] "So you don't actually do POD planning but a simplified version; this is OK but
should be discussed more explicitly, especially its limitations." Add an explicit statement
that the planning is a SIMPLIFIED form of POD planning and spell out its limitations.
RECURRING THEME (see #239, #248, #251): Till raises this three times.
Refs: methods.tex; #239; #248.

================================================================================
#239  [DONE 2026-06-01] [T1] [THESIS]  Methods: a real POD planner (e.g. LW1) has deductive axioms -- p.23 (PDF29)
NOTE 2026-06-01: at methods.tex:142 ("sound treatment...left to future work"), added a BRIEF clause
per Till's note: "a full POD planner with deductive axioms (e.g. LW1 \cite{bonet2014flexible}) could
express this directly (\cref{sec:limitations})". Kept short on purpose -- the full discussion lives in
#248 (limitations); this avoids the #251 redundancy while still naming LW1 where Till marked it.
================================================================================
[INK] "This could actually be taken care of by a real POD planner, e.g. LW1 has deductive
axioms." Note that a full POD planner (he cites LW1 as an example) handles this via
deductive axioms, which the simplified approach lacks. Part of the recurring theme (#238, #248).
Refs: methods.tex; #238; #248.

================================================================================
#240  [DONE 2026-06-01] [T2] [POLISH]  Results: clarify the stack goal -- specific tower or any stack? -- p.24 (PDF30)
NOTE 2026-06-01: code-verified answer (run_logger.py:450 "randomised tower"; test_full_pipeline.py
goal_satisfied handles ('and',('on',a,b),...); boxel_env.py stack_scene spawns identical cubes).
Clarified results.tex:16: the goal is a concrete conjunction of (on a b) facts (a specific tower),
generated at random each episode; cubes are identical so which ones form the tower is immaterial.
================================================================================
[INK] "So is it a specific stack, e.g. (on b1 b2) (on b2 b3), or is it any stack of the
given size?" Clarify whether the stacking goal is a specific ordered tower or any stack of
the target size.
Refs: results.tex; #204.

================================================================================
#241  [DONE 2026-06-02] [T3] [THESIS]  Results: "Software" paragraph highlighted, no comment -- p.26 (PDF32)
================================================================================
[HL-ONLY] the paragraph "PyBullet [6]; PDDLStream [10] with the FastDownward classical
planner backend; Python 3.10." is highlighted with no note. Likely flagged for the planned
FastDownward / planning-algorithms background section (#253), or wants version detail.
Confirm with Till Wed.
Refs: results.tex; #253; #215.
NOTE 2026-06-02: added the missing Fast Downward citation (Helmert 2006, JAIR 26:191--246) to
references.bib and cited it at results.tex:85; also fixed spelling FastDownward -> Fast~Downward
there. One no-space "FastDownward" remains at discussion.tex:264 (deferred to a separate pass).
SUPERSEDED 2026-06-02 by #256: the author chose to delete the Software paragraph entirely; the
Fast Downward citation moves to the planned Background section (#253). helmert2006fast bib entry kept.

================================================================================
#242  [DONE 2026-06-02] [T1] [THESIS]  Results: explain the performance degradation (Fig 5.6) -- p.30 (PDF36)
================================================================================
[INK] "Explanation for performance degradation!" next to Fig 5.6. Add a textual explanation
for the degradation the figure shows.
Refs: results.tex; Fig 5.6.
NOTE 2026-06-02: Fig 5.6 = fig:success-stack (success vs stack height). Added a two-sentence
mechanism to the stack paragraph (results.tex:164): success falls with height because each layer
is another sequential pick-and-place and an off-pose settle forces a replan, so adaptive variants
fail mainly via replan_limit (cf. fig:failure-modes) not planner failure; uniform collapses faster
from its ~20x higher per-call planning cost (tab:headline). Mechanism, not interpretation -- the
gap analysis stays in discussion.tex (not duplicated).

================================================================================
#243  [DONE 2026-06-02] [T3] [THESIS]  Results: Fig 5.12 reds are too similar -- p.35 (PDF41)
================================================================================
[INK] "These red colors are very similar" on Fig 5.12. Recolor for distinguishability
(distinct hues / line styles). New image only; never overwrite the old PNG.
Refs: results.tex; Fig 5.12 + its generator.
NOTE 2026-06-02: Fig 5.12 = fig:failure-modes (failure_modes.png); generator eval_plotter.py
plot_failure_modes via EXIT_REASON_COLOUR. The "similar reds" were planner_failed (#d62728) and
the vivid-red timeout (#ff1744) adjacent wherever replan_limit was absent. Per author: swapped
timeout -> orange (#ff7f0e) and replan_limit -> vivid red (#ff1744) so the pinned top band
(timeout) is distinct from planner_failed red. CODE ONLY committed; thesis PNG deliberately NOT
regenerated -- user owns the regen with the next data iteration (which drops no_summary and
replan_limit, leaving green/red/orange, all distinct). Compiled thesis shows old colours until
that regen + a results.tex \includegraphics swap to the new PNG.

================================================================================
#244  [SKIPPED 2026-06-02] [T2] [POLISH]  Discussion: separate Discussion section -- accepted, optional merge -- p.36 (PDF42)
================================================================================
[INK] "I'm not particularly fond of having a separate Discussion section, but it's OK."
Low priority: optionally fold Discussion into Results/Conclusion. He accepts it as-is.
Refs: discussion.tex.
NOTE 2026-06-02: SKIPPED per author "go". Supervisor accepts the separate Discussion section
as-is ("it's OK"); folding it into Results/Conclusion is a chapter-level restructure
disproportionate to a T2 polish and would conflict with #245 (an overall-conclusion sentence
added TO the Discussion). Structure kept.

================================================================================
#245  [DONE 2026-06-02] [T2] [THESIS]  Discussion: state the overall conclusion of the comparison -- p.38 (PDF44)
================================================================================
[INK] "So what's the overall conclusion of the comparison?" Add an explicit takeaway
sentence summarizing what the comparison shows.
Refs: discussion.tex.
NOTE 2026-06-02: "the comparison" = the TAMPURA comparison (sec:disc-tampura). Added one summative
paragraph at the end of that section (after the line-of-sight/representation paragraph, before
Threats to Validity): a deterministic knowledge-literal planner with replanning is sufficient to
reach the goal on this task class -- cheaper to run and simpler to model than TAMPURA's learned
probabilistic policy, though less reliable -- and plans over occlusions a sub-symbolic visibility
grid leaves implicit. Synthesis of existing threads only; grounded in discussion.tex :85, :116-124, :126.

================================================================================
#246  [DONE 2026-06-02] [T0] [NOW]  Discussion: "This is not entirely true." -- p.39 (PDF45)
================================================================================
[INK] "This is not entirely true." next to a claim on p.39 (locate the exact sentence ---
on or near the TAMPURA comparison). Correct the overstatement. See #247, which is the
adjacent correction on the same page/claim.
Refs: discussion.tex; #247; #177; #213.
NOTE 2026-06-02: DONE with #247 (same locus). The false claim "rather than re-running [their
code/it]" contradicted discussion.tex's own "we re-ran the released Find Die environment"
(sec:disc-tampura). Rewrote the Threats paragraph "TAMPURA via published numbers" -> "TAMPURA on a
different task": we re-ran TAMPURA's Find Die locally + cross-checked published Table II, but did
NOT run it on our scenes (Find Die is the closest analogue, not the same problem). Also fixed the
matching "rather than re-running it" at results.tex:108 (baselines) in the same commit. Ties #177/#213.

================================================================================
#247  [DONE 2026-06-02] [T0] [NOW]  Discussion: "You did run TAMPURA, just not on the same problem." -- p.39 (PDF45)
================================================================================
[INK] "You did run TAMPURA, just not on the same problem." The text implies TAMPURA was not
run; in fact it was, on a different problem. Fix the framing. Same locus as #246; ties to
the TAMPURA-comparison corrections #177/#213.
Refs: discussion.tex; #246; #177; #213.
NOTE 2026-06-02: DONE with #246 (same commit) -- see #246 NOTE. Framing now states TAMPURA was
re-run on its own Find Die task, not on our tabletop problem.

================================================================================
#248  [DONE 2026-06-01] [T1] [THESIS]  Discussion: simplified POD does not scale (missing deductive axioms) -- p.41 (PDF47)
NOTE 2026-06-01: per author ("also discuss in the limitations"), expanded the "Simplifications
disclosed" paragraph (discussion.tex:261, sec:limitations) with the explicit simplified-POD-planning
discussion: full POD planner (LW1 \cite{bonet2014flexible}) has contingent branching + deductive axioms
the base predicates leave implicit; ours determinises optimistically + replans; suffices for the
studied tasks but not for problems needing contingent reasoning; ties to the bounded give-up. This is
the home for the recurring theme (#238 methods framing, #239 methods note kept brief to avoid #251).
================================================================================
[INK] "More importantly, you use a simplified version of POD planning that does not work on
more complex problems (e.g. because of missing deductive axioms)." State this limitation
explicitly as a key point of the comparison/limitations. Third instance of the recurring
theme (#238, #239).
Refs: discussion.tex; #238; #239.

================================================================================
#249  [DONE 2026-06-02] [T2] [POLISH]  Conclusion: too much detail -- p.42 (PDF48)
================================================================================
[INK] "too much detail for the conclusion". Trim implementation/results detail from the
conclusion; keep it high-level.
Refs: conclusion.tex.
NOTE 2026-06-02: trimmed conclusion.tex para 3 (contributions/results) -- removed the per-number
results dump (39.8/1.3, 13.7/166/57, 42/55, the semantic+mbs0.05 null result, the per-step vs
per-episode unit note) and cross-referenced \cref{ch:results,ch:discussion} for the detail; kept
both headline findings (ablation: fewer cells + solves what uniform can't; TAMPURA: cheaper but
less reliable, no probabilistic policy). Also "first-class symbolic state" -> "explicit symbolic
state" (consistent with intro #179 + discussion). Paras 1-2 left as-is.

================================================================================
#250  [DONE 2026-06-02] [T2] [THESIS]  Conclusion: future work -- real-robot experiments -- p.43 (PDF49)
================================================================================
[INK] "experiments on real robots!" Add real-robot experiments to the future-work outlook.
Refs: conclusion.tex.
NOTE 2026-06-02: added a "Real-robot experiments." paragraph as the closing capstone of Future
Work (conclusion.tex, after the free-space-merge paragraph): run the system on a physical Franka
Panda, combining the learned detector + robot-mounted active-sensing camera, exposed to real
perception noise/calibration/contact; reuses the perception-agnosticism framing (narrow detection
interface -> Boxel layer + POD planner transfer unchanged). Ties to the learned-perception and
active-sensing future-work items.

================================================================================
#251  [DONE 2026-06-02] [T2] [POLISH]  Cross-cutting: redundancy -- things explained multiple times -- (email 2026-05-31)
================================================================================
Email: "Some things are explained multiple times and in a redundant way (e.g., how the
comparison to TAMPURA was done)." De-duplicate; consolidate the TAMPURA-comparison
explanation into one place and cross-reference instead of repeating.
Refs: results.tex; discussion.tex; methods.tex; #177; #213.
NOTE 2026-06-02: methods.tex has NO TAMPURA content (that ref was spurious). The real duplication was
discussion.tex:70-86 re-explaining the same methodology+numbers already in results.tex subsec:tampura
(:221, with fig:tampura). Condensed the Discussion recap to a headline (cheaper end-to-end, less
reliable: 13.7 vs 166s, 42 vs 55%) + cross-ref to subsec:tampura/fig:tampura, keeping the unique
architectural "differ in kind" analysis (:87+). Every removed number remains in results.tex:221.
Left results.tex:108 (baseline definition) and the threats "different task" paragraph (distinct
validity angle) as-is.

================================================================================
#252  [INFO] [NO ACTION]  Overall verdict (email 2026-05-31)
================================================================================
Email: "Overall, it reads very well!"; "It's not missing anything major"; "your
modifications since our last meeting already improved the overall flow." Positive context;
no action.

================================================================================
#253  [DONE 2026-06-02] [T3] [THESIS]  Background: add a FastDownward + planning-algorithms section  (AUTHOR-PLANNED, not a Till comment)
================================================================================
From Hani's 2026-05-31 reply ("planning to add a section about FastDownward and planning
algorithms to the background"). Tracked here because it is part of this revision cycle and
relates to the abstract/software highlights (#215, #241). Remove if not wanted.
Refs: background.tex; #215; #241.
NOTE 2026-06-02: added subsection 2.1.2 "Classical Planning Algorithms and Fast Downward"
(background.tex, end of the AI Planning Fundamentals section, before sec:pod; label
subsec:planning-algorithms). Fuller treatment per author: heuristic state-space search (greedy/A*),
domain-independent heuristics (delete-relaxation incl. FF; landmarks/LAMA), and Fast Downward's
SAS+ multi-valued translation + causal graph, framed as PDDLStream's backend. Added 3 bib entries
(hart1968formal, hoffmann2001ff, richter2010lama). RESOLVES the Fast Downward citation deferred from
#256 -- helmert2006fast is now cited here, closing the interim uncited gap.

================================================================================
#254  [DONE 2026-06-02] [T2] [THESIS]  Define "Boxel" crisply at first body use (intro/methods)  [follow-up to #214]
================================================================================
The abstract now defines a Boxel (fix #214: "a cuboidal cell of the workspace"), but the
body never states plainly what a Boxel is: introduction.tex:33 and methods.tex:16 describe
how Boxels are GENERATED ("adaptive semantic discretization") without first defining the
coined unit. Add the same one-line definition at first substantive body use --- most
naturally methods.tex:16, or intro.tex:33.
Refs: methods.tex:16; introduction.tex:33; #214; supervisor_comments_20260527.md.
NOTE 2026-06-02: intro already defines it at first body use -- introduction.tex:26 "the Semantic
Boxel: a task-relevant, occlusion-aware cuboid, built from objects' known 3D models" (before the
:33 contributions bullet the audit cited), so NO intro change. The real gap was methods.tex:16,
which opened the methods chapter with "We build the Boxel abstraction" without restating the unit;
prepended the abstract's canonical one-liner "A Boxel is a cuboidal cell of the workspace;" so the
definition is consistent abstract -> intro -> methods and the methods chapter is self-contained.

================================================================================
#255  [DONE 2026-06-01] [T3] [POLISH]  Related Work: "cost" overloaded vs "plan cost"  [author finding, not on Till's list]
================================================================================
The "three advantages, each with a cost" paragraph (related-work.tex:37) used "cost" for the
downside of each advantage, clashing with "minimises plan cost" in the same paragraph (two senses of
"cost"). 2026-06-01: replaced the 4 downside-sense uses with "limitation" (author's choice over
"tradeoff"); kept "plan cost". Surfaced while working #229.
Refs: related-work.tex:37; #229.

================================================================================
#256  [DONE 2026-06-02] [T2] [THESIS]  Results: delete the "Software" paragraph  (author decision; supersedes #241)
================================================================================
[AUTHOR] Per author (2026-06-02): the one-line \paragraph{Software.} in the Experimental Setup
(results.tex) is redundant and should be removed entirely, not merely cited (cf. #241, which had
added a Fast Downward citation there).
NOTE 2026-06-02: deleted the Software paragraph at results.tex ("PyBullet; PDDLStream with the
Fast Downward classical planner backend; Python 3.10"). Citations preserved elsewhere: PyBullet at
results.tex:11; PDDLStream at background.tex:104, abstract.tex:7, introduction.tex:5. Fast Downward
(helmert2006fast) was cited ONLY in this paragraph -- bib entry KEPT (unused for now); its citation
now belongs to the planned Background Fast Downward section (#253), so Fast Downward is uncited in
the interim. Supersedes the #241 cite-in-Results approach.
Refs: results.tex; #241; #253; #215.

================================================================================
#257  [DONE 2026-06-02] [T1] [THESIS]  Background: text cutoff (overfull \hbox) in state-space example  (author/build finding)
================================================================================
[AUTHOR] Recompiled PDF showed text running past the right margin on p.10 (background, the
state-space model bullets): inline-math typewriter state sets did not line-break.
NOTE 2026-06-02: latexmk log showed three overfull \hbox in background.tex -- lines 16-17 (the
$s_0$ set, 96pt over, the visible cutoff in the screenshot), 13-15 (the tuple $M=\langle...\rangle$,
23pt), 20-21 (the $f$ bullet's two sets, 20pt). Added \allowbreak after the commas in the tuple and
the example sets so they wrap; rendering otherwise unchanged. Recompile confirms all three overfull
\hbox gone (exit 0, 68pp). Minor 4.7pt overfull at results.tex:153-154 ($n_occ \in \{2,3,4\}$) left
as-is (sub-visible).
Refs: background.tex:13,16,20.

################################################################################
# AUTHOR NOTES 2026-06-02 (from notes/personal notes on Thesis) -- #258-#273
# Logged, not yet fixed. Already-resolved notes recorded under RESOLVED at end.
################################################################################

================================================================================
#258  [T2] [THESIS]  Background: explain what an MDP is, with examples
================================================================================
[AUTHOR] "explain what a classical planner is and give examples; same for MDPs." Classical-planner
half is RESOLVED by #253 (new 2.1.2 with Fast Downward/FF/LAMA). Remaining: Background never defines a
Markov Decision Process / MDP with examples, yet MDPs are leaned on in the TAMPURA comparison and RW.
Add a short MDP (and POMDP contrast) explanation in Background, parallel to the classical-planner section.
Refs: background.tex (2.2.2 / sec:pod); #253; discussion.tex:84-106; related-work.tex:11.

================================================================================
#259  [T2] [THESIS]  Related Work: clarify "provably optimal ones"
================================================================================
[AUTHOR] related-work.tex:11 -- TAMPURA produces "risk-aware, information-gathering plans rather than
provably optimal ones." What does "provably optimal" mean here and what is it contrasted with? Clarify
or drop.
Refs: related-work.tex:11.

================================================================================
#260  [T2] [THESIS]  Related Work: state how we differ from TAMPURA and Saleem (end of POMDP-TAMP para)
================================================================================
[AUTHOR] The POMDP-based-TAMP paragraph (related-work.tex:11-12; TAMPURA + Saleem et al. + Bayes3D)
ends without saying how THIS thesis differs from TAMPURA and Saleem. Add a differentiation sentence at
the end of that paragraph.
Refs: related-work.tex:11-12; curtis2024partially; saleem2024pomdp.

================================================================================
#261  [T2] [THESIS]  Related Work: verify Ma et al. "separate pre-planning step" claim
================================================================================
[AUTHOR] related-work.tex:20 distinguishes us from Ma et al. by "information-gathering becomes a core
planner action rather than a separate pre-planning step." Do they really do a pre-planning step in
ma2025task? Verify against the paper and correct if wrong.
Refs: related-work.tex:20; ma2025task.

================================================================================
#262  [T2] [THESIS]  Related Work: Contingent-FF and MBP named without citations
================================================================================
[AUTHOR] related-work.tex:30 "other POD planners instead search belief space directly, as in
Contingent-FF and MBP" -- both named with NO \cite (unlike CLG/K-replanner/LW1). Add citations
(Contingent-FF: Hoffmann & Brafman; MBP: Bertoli et al.) and verify the "search belief space directly"
characterization.
Refs: related-work.tex:30.

================================================================================
#263  [DONE 2026-06-04] [T1] [THESIS]  Related Work: "Object Integrity" octree argument does not apply to our system
NOTE 2026-06-04: REMOVED the "Object Integrity" bullet (related-work.tex:48) and folded the remaining
"Lack of Semantic Structure" limitation into prose; fixed "two key limitations" -> "a key limitation".
Object integrity is not a Boxel-vs-octree discriminator: pick targets an object by identity
(domain.pddl:158 pick ?o ?b ?g ?q), each object is one object-centric Boxel built at its oracle pose
(methods.tex:33), and the grasp is a single sampled pose (streams.py:534) -- no "pick voxels 1,2,5"
case exists. Chose REMOVE over QUALIFY since the grasp frame uses the Boxel center, so a "poses not
cells" qualifier would be a new inaccuracy.
================================================================================
[AUTHOR] related-work.tex:48 motivates Boxels over octrees via "Object Integrity" (octrees split an
object across voxels, complicating "pick up object A"). That only holds if Boxels were used to grasp;
we pick up using a sampled pose (oracle here), not the Boxels. Fix/remove -- it misstates our own design.
Refs: related-work.tex:48; methods.tex (pick action / pose sampling).

================================================================================
#264  [T2] [THESIS]  Pose sampling vs (partial) occlusion; relax "hidden" to all-8-corners-occluded
================================================================================
[AUTHOR] How are object poses sampled -- can we sample a (partially) hidden object? If so, the visibility
test could count an object as hidden only when all 8 bounding-box corners are occluded (vs the current
criterion). Investigate in code, then decide whether to relax the hidden/visible test and update methods.
Refs: methods.tex (perception/visibility, sense action); pose-sampling stream code.

================================================================================
#265  [T2] [THESIS]  Methods: fig:boxelization caption "largest occluder" -> "bottom occluder"
================================================================================
[AUTHOR] methods.tex:20 panel (a): "fully occluded target (cyan) sitting in the shadow behind the
largest occluder." It is not the largest occluder, just the bottom one. Correct (verify against the scene).
Refs: methods.tex:20 (fig:boxelization).

================================================================================
#266  [DONE 2026-06-04] [T1] [THESIS]  Methods: shadow extends to end of hidden region, not the workspace boundary
NOTE 2026-06-04: fixed fig:boxelization panel (c) caption (methods.tex:20): "swept ... out to the
workspace boundary" -> "swept ... along the lines of sight to the far end of the region it occludes,
where those sightlines meet the table behind it". Matches shadow_calculator.py:76-177 (back-corner
sightlines hit the table surface = hidden-region end, clamped to the table; height >= object). Body
text methods.tex:34 was already neutral. The schematic FIGURE still over-extends shadows to the
workspace BOUNDS -- logged as #274 (code-side CODEBASE_AUDIT.txt #114).
================================================================================
[AUTHOR] methods.tex:20 panel (c) (and any matching body text): shadow Boxel "swept from the object's
back face out to the workspace boundary" is wrong -- it extends to the end of the shadow/hidden region
behind the object, not the workspace boundary. Read the shadow-generation code and describe it correctly.
Refs: methods.tex:20 (fig:boxelization); shadow-generation code.

================================================================================
#267  [T2] [THESIS]  Methods: fig:boxelization-real caption "object bounding cuboids" correction
================================================================================
[AUTHOR] methods.tex:27: "object bounding cuboids enclose the visible cubes and red wireframe Boxels mark
the volumes they occlude." Author began a correction ("actually the bounding boxels are...") but the note
is TRUNCATED -- exact fix TBD; get the author's full correction (what the bounding Boxels actually are).
Refs: methods.tex:27 (fig:boxelization-real).

================================================================================
#268  [T2] [THESIS]  Methods: add pseudocode for adaptive semantic discretization
================================================================================
[AUTHOR] The 3-step generation (methods.tex:31-37: object bounding, occlusion subdivision, recursive
octree partition + convex-only merge) would be much clearer as an algorithm/pseudocode block (esp. the
recursive partition + merge).
Refs: methods.tex:31-37.

================================================================================
#269  [T2] [THESIS]  Methods: verify Boxel set is supplied to the planner as static facts in initial state
================================================================================
[AUTHOR] methods.tex:38 claims "the completed set of Boxels is supplied to the planner as static facts in
its initial state." Walk the code and confirm (static facts; initial state) before keeping the claim.
Refs: methods.tex:38; initial-state construction code.

================================================================================
#270  [T2] [THESIS]  Results: Figure 5.3 (overhead-camera) caption is outdated
================================================================================
[AUTHOR] results.tex:79 (fig:overhead-camera, Figure 5.3) caption is outdated. Identify what changed and
update it.
Refs: results.tex:79 (fig:overhead-camera).

================================================================================
#271  [T2] [THESIS]  Results: exit-reason / failure-mode list needs an update
================================================================================
[AUTHOR] results.tex:96 exit-reason list (planner_failed, timeout, replan_limit, physics_mismatch,
drop_failed, ...) needs updating; ties to #243 (no_summary/replan_limit change in the next data
iteration). Reconcile with the current exit reasons.
Refs: results.tex:96; #243.

================================================================================
#272  [DONE 2026-06-04] [T1] [THESIS]  Results: explain why uniform planning cost grows with n_occ (Fig 5.8)
NOTE 2026-06-04: added an explanatory passage to subsec:planning-time (results.tex:183) for the n_occ
slope in fig:plantime-holding. Verified in code: pddlstream_planner.py:452-471 emits a view-blocking
fact blocks_view_at(obj, free_cell, shadow) for EVERY free cell on a camera->shadow line of sight, per
shadow per object, so the fact count scales as O(#obj x #free-cells-in-corridor x #shadows). More
occluders -> more shadows, multiplied by the free-cell count, which uniform_grid.py keeps ~10x larger
than the adaptive partition -> uniform's steep climb. Refined the author's "more cells" framing to the
real driver (view-blocking facts ~ shadows x free-cells). Cross-ref subsec:compactness (results.tex:195).
NOTE: the fig:plantime-holding NUMBERS (21->83 s) are from the OLD sweep and will be refreshed under
#282; the MECHANISM added here is data-independent and stands.
================================================================================
[AUTHOR] Fig 5.8 (fig:plantime-holding): why do uniform scenes cost more / have more cells with more
occluders? Likely because the uniform variant keeps the object+shadow Boxels and only replaces the
free-space partition with a uniform grid, so more occluders -> more shadow Boxels -> more facts/cost
(results.tex:107). Verify and state this explicitly so it "adds up."
Refs: results.tex (subsec:planning-time, fig:plantime-holding); results.tex:107.

================================================================================
#273  [T3] [POLISH]  Terminology: find a better word than "cuboid"
================================================================================
[AUTHOR] "cuboid" reads awkwardly; find a better term (e.g. box / rectangular cell / axis-aligned box).
5 uses: abstract.tex, introduction.tex, methods.tex (x3). Apply consistently with the Boxel definition.
Refs: abstract.tex; introduction.tex; methods.tex.

================================================================================
#274  [DONE 2026-06-04] [T2] [THESIS]  Methods fig:boxelization panel (c): schematic renders shadows to workspace boundary, not hidden-region end
NOTE 2026-06-04: regenerated thesis/graphics/boxelization_3d.png with Windows Python
(python tools\render_boxelization_3d.py) after the CODEBASE #114 code fix. Visually verified: panel (c)
orange occlusion Boxels now stop mid-table where the sightlines meet the table (no longer sweeping to the
workspace edge), the dashed lines of sight end at the same point, and the largest shadow behind the rear
occluder still encloses the cyan hidden target; the freed edge space now shows as Free Space Boxels in
(e)-(f). Camera tripod (#283) intact; other panels unchanged. Matches the #266 caption. Code-side = #114.
================================================================================
[FOUND 2026-06-04 while fixing #266] The figure boxelization_3d.png panel (c) (thesis/graphics/) visibly
sweeps the orange occlusion Boxels back to the table/workspace edges. Root cause is figure-rendering code:
render_boxelization_schematic.py _swept_shadow casts shadow rays to the workspace BOUNDS (_ray_box_exit,
~lines 146-162), a 2-D top-down approximation with no object height, reused by render_boxelization_3d.py.
The real system (shadow_calculator.py:76-177) ends each shadow where the back-corner sightlines meet the
table surface (the hidden-region end), clamped to the table. The #266 caption now describes the real
behaviour, so the figure is the remaining inaccuracy. Fix = regenerate the schematic so panel (c) ends
shadows at the hidden-region end (do NOT overwrite the PNG silently; regenerate + visually verify).
Code-side fix cross-filed as CODEBASE_AUDIT.txt #114.
Refs: methods.tex:20 (fig:boxelization); thesis/graphics/boxelization_3d.png; tools/render_boxelization_schematic.py (_swept_shadow); CODEBASE_AUDIT.txt #114.

================================================================================
#275  [DONE 2026-06-04] [T1] [THESIS]  Abstract: drop the PDDLStream mention
NOTE 2026-06-04: abstract.tex -- "into a PDDLStream-based planner (classical search plus continuous
samplers)~\cite{garrett2018pddlstream}" -> "into a classical TAMP planner" (author's wording). Dropped
the abstract-level PDDLStream name + citation; garrett2018pddlstream still cited in background.tex:141
and introduction.tex (no orphan bib). PDDLStream stays in methods/background. The stray "the" of #279 is
elsewhere (the abstract said "a PDDLStream-based...", not "the").
================================================================================
[SUPERVISOR 2026-06-04] Remove "PDDLStream" from the abstract. Per Till, whether we use PDDLStream or
our own TAMP framework does not crucially affect the capabilities claimed, so naming it in the abstract
is noise. Drop the term (and any "PDDLStream-based"/"the PDDLStream" phrasing) from abstract.tex; the
implementation detail stays in methods. (Touches the #215 abstract highlight locus.)
Refs: abstract.tex (impl stays in methods.tex). Related: #279 (stray "the" near PDDL), #215.

================================================================================
#276  [DONE 2026-06-04] [T1] [THESIS]  Background: present STRIPS first, then DERIVE the state model (don't define it twice)
NOTE 2026-06-04: restructured background.tex sec:2.1.1 to STRIPS-first per Till's canonical form. Now:
factored representation -> STRIPS (state = set of atoms; action = pre/add/del; applicable iff pre(a)
subset of s; successor (s\del(a)) U add(a)) -> PDDL syntax P=<D,I> (domain predicates + action schemas,
kept the stack lstlisting; instance objects/s0/goal) -> state model S(P)=<S,s0,SG,Act,A,f> DERIVED ONCE
as the semantics. Removed the duplicate upfront model tuple/itemize and the \paragraph heading; kept all
5 citations, the blocksworld example, the lstlisting+label, and the commented-out derived-predicates
block; tuple notation matches symbols.tex; STRIPS stays unexpanded (\acs, per #220).
================================================================================
[SUPERVISOR 2026-06-04] Background currently introduces an abstract state model and THEN re-introduces it
in STRIPS terms. Till: start from STRIPS syntax (states as sets of atoms; action schemas with
preconditions/add(a)/del(a) as sets of atoms; problem P=<D,I>, domain D=<P,A>, instance I=<O,s0,g>) and
let the state model S(P) FOLLOW as the semantics (successor f(a,s)=(s\del(a)) U add(a)), so it is defined
once. Follow the canonical "Classical Planning" presentation Till shared (screenshot/attachment 2026-06-04).
Refs: background.tex (classical-planning + state-model subsections).

================================================================================
#277  [DONE 2026-06-04] [T2] [THESIS]  Whole document: fix many small language/grammar errors
NOTE 2026-06-04: conservative chapter-by-chapter language pass (clear errors only, no voice restyling).
Fixed: introduction.tex (repeated "in practice"); methods.tex (PDDL-fluents KIF cross-ref reconciled with
sec:kif_belief [a #278 leftover] + "meaningful/semantically meaningful" redundancy); discussion.tex (two
metaphorical "orthogonal" -> "separate", per the no-orthogonal-outside-geometry rule); background.tex (two
contractions "can't"->"cannot", "it's"->"it is"). Abstract, related-work, results, conclusion read clean.
Prose is well-polished overall; remaining content/data issues are tracked separately (#281 stack-degradation
explanation, #282 stale numbers/replan_limit, #199 task naming), NOT grammar. Any further subtle polish is
best left to the author's LLM bulk pass (Marc's suggestion).
================================================================================
[SUPERVISOR 2026-06-04] Both reviewers note many small language errors throughout. Suggested approach
(Marc): run the full thesis text through an LLM for a grammar/style pass, then apply fixes by hand. Scope
= all chapters + abstract; do NOT change technical meaning. Any wording change that touches a claim gets
tracked separately.
Refs: thesis/chapters/*.tex; abstract.tex.

================================================================================
#278  [DONE 2026-06-04] [T1] [THESIS]  KIFs vs K-literals: not interchangeable; use KIFs consistently + cite their source
NOTE 2026-06-04: corrected the KIF/K-literal conflation per Till. Source confirmed: Brenner & Nebel
(2009), AAMAS 19(3):297-331, DOI 10.1007/s10458-009-9081-1 (user supplied the PDF; it is
password-protected, so citation confirmed via web search instead). Reframed background.tex sec:2.2.1: a
KIF (Brenner-Nebel know-whether) records that the agent knows the VALUE of a fact (paired with the value
fluent), NOT a compacted K(L)/K(neg L) pair; K(L) is know-that; the two are not interchangeable. Added
@article{brenner2009continual} to references.bib; retitled subsection to "...K-Literals, and Know-If
Fluents". Consistency pass (our representation now called Know-If Fluents, not K-/knowledge literals):
methods.tex (:61 belief + pair sentences; :74 AP propositions + example), abstract.tex, conclusion.tex:8,
discussion.tex (simplifications note), related-work.tex (:30, :37(ii)). Kept "knowledge literals" for the
GENERAL POD line (CLG/K-replanner/LW1) -- correct. introduction.tex:34 already correct. Did NOT overhaul
K(...) math notation beyond touched spots, nor discussion.tex:91/116 generic "knowledge-literal".
================================================================================
[SUPERVISOR 2026-06-04] The thesis conflates Know-If Fluents (KIFs) and K-literals and uses them
interchangeably; Till flags this as a real error (his own prior misunderstanding too). We actually use
KIFs. They are NOT just a compact form of K-literals: a KIF expresses that we know the VALUE of L, not
whether L is true or false (you cannot assert "I know L" with a KIF alone). Fix: (1) use
"KIF"/"Know-If Fluent" consistently everywhere (the PDDL domain uses KIFs, e.g. obj_at_boxel_KIF);
(2) drop the "compact representation of K-literals" framing; (3) cite the KIF source -- Brenner & Nebel
(2009), "Continual planning and acting in dynamic multiagent environments", Auton. Agent. Multi-Agent
Syst. 19(3), https://link.springer.com/article/10.1007/s10458-009-9081-1 (DOI 10.1007/s10458-009-9081-1);
add to references.bib; (4) keep the K-literal link as "closely related to" with the distinction stated.
Refs: background.tex (KIF intro, #223/#224 locus); methods.tex (KIF fluents); references.bib. Related: #223 #224.

================================================================================
#279  [DONE 2026-06-04] [T3] [THESIS]  Delete the stray article "the" before PDDL/PDDLStream
NOTE 2026-06-04: author identified two spots where "the" precedes PDDL as the head noun, both dropped:
background.tex:15 (PDDL-introduction sentence "The PDDL~[23] ..." -> "PDDL~[23] ...") and background.tex:99
("extends the classical PDDL" -> "extends classical PDDL"). Left "the PDDL state/description" and "the
PDDLStream framework/planner/integration" untouched (PDDL/PDDLStream used as an adjective there, so "the"
is correct). Abstract's "a PDDLStream-based planner" already removed in #275.
================================================================================
[SUPERVISOR 2026-06-04] Author note: "delete the 'the' behind the PDDL." Locate the stray "the" preceding
PDDL/PDDLStream/STRIPS (a leftover article) and remove it. Verify by grep before editing. Low priority;
likely subsumed by #275 (abstract) and the #277 language pass if those land first.
Refs: grep "the PDDL" / "the PDDLStream" / "the STRIPS" across thesis/chapters + abstract.tex.

================================================================================
#280  [DONE 2026-06-04] [T1] [THESIS]  Related Work/Background (Critical Regions): cite the new DYNAMIC-abstraction paper; "static" claim no longer holds
NOTE 2026-06-04: cited the dynamic-abstraction follow-up and softened the "static" claim. Paper (Till's
primary rkn_aaai25): Nayyar & Srivastava, "Autonomous Option Invention for Continual Hierarchical
Reinforcement Learning and Planning", AAAI 2025 (vol 39); confirmed via AAAI OJS (article 34163) + web
search -- user supplied the PDF but it stayed password-protected to the reader, so not read directly.
Added @inproceedings{nayyar2025option} to references.bib (by shah2022abstractions). related-work.tex:
retitled "Limitations of Static Semantic Abstractions" -> "...Learned...", scoped the once-per-scene
behaviour to that formulation, noted later dynamic-abstraction work (RL, not POD-TAMP), kept our
geometric/no-predictor contrast. background.tex:154: same softening on the trailing "predicted once and
held fixed" sentence. Alt (less likely, Till): AAAI'26 Context-Sensitive Abstractions -- swap if preferred.
================================================================================
[SUPERVISOR 2026-06-04] Our Critical Regions discussion says the abstraction is predicted once and held
STATIC. A newer AAIR-Lab paper makes the abstraction DYNAMIC -- it switches abstractions as the goal
changes (its Fig. 1: coloured areas are abstract states that change with the goal). So the "static" claim
is no longer true. Fix: cite the new paper and soften/correct the static claim, but KEEP the contrast --
it is a very different approach (RL-driven, different task, likely not 3D), so ours is not superseded.
New paper (AAAI'25, AAIR Lab / Nayyar et al. -- VERIFY authors+year):
https://aair-lab.github.io/Publications/rkn_aaai25.pdf  (alt/less likely AAAI'26: 23127 / NayyarR-ML).
Add to references.bib. NOTE: published AAAI'25/'26, so prior unawareness is fine -- no panic.
Refs: related-work.tex (Critical Regions / Limitations of Static Semantic Abstractions); background.tex; references.bib. Related: #225 #226.

================================================================================
#281  [DONE 2026-06-04] [T1] [THESIS]  Results/Discussion: stack-goal degradation explanation is WRONG (sim/control limit, not planning difficulty)
NOTE 2026-06-04: rewrote the stack-goal degradation explanation in results.tex (the "This decline with
height is expected..." sentence). Reattributed the success collapse with stack height to a simulation/
control limit -- the simplified manipulation model (top-down grasps at a fixed height offset, a hardcoded
post-place lift, collisions logged but never triggering recovery) means the arm cannot reliably place
on/clear the growing tower past a few layers -- NOT planning difficulty or the replan budget. Cross-refs
\cref{sec:limitations} ("Manipulation and execution"). Dropped the replan_limit claim (removed under #282)
and the fig:failure-modes ref in that paragraph; changed no numbers (refresh under #282). discussion.tex
needed no change: its stack mention explains the semantic/uniform overhead gap, not the wrong replan-budget
cause. Confirmation experiment CODEBASE #116 KILLED; cause accepted from Till+Marc.
================================================================================
[SUPERVISOR 2026-06-04] The current explanation for stack-goal success degradation with stack height
(framed as planning difficulty: more pick/place loops -> more chances to fail under the time limit) is
wrong. Real cause (Till+Marc): a simulation/control limitation -- past a certain height the arm crashes
into / cannot reach the growing stack (a model-free controller limit), NOT the POD planning. Fix the
prose once confirmed. Confirmation experiment cross-filed as CODEBASE_AUDIT.txt #116 (build multiple
SEPARATE stacks side-by-side; if those succeed more often, it is stacking-height/control, unrelated to
planning; also inspect sim runs for the crash / out-of-reach failure).
Refs: results.tex (stack success vs height; failure modes); discussion.tex; CODEBASE_AUDIT.txt #116.
UPDATE 2026-06-04 (author decision): CODEBASE #116 (the confirmation experiment) is KILLED -- the cause is
accepted from Till+Marc's observation, so #281 is to be written DIRECTLY, no experiment. TASK: rewrite the
stack-goal degradation explanation (results.tex:162; check discussion.tex too) to attribute the collapse to
a simulation/control limit -- past a certain height the arm collides with / cannot reliably reach the
growing tower (a model-free controller limit) -- NOT planning difficulty or the replan budget. (The current
text also cites replan_limit, which is being removed under #282.) NEXT-BATCH ORDER: #281 (this) ->
CODEBASE #114 (shadow-schematic code) -> #274 (regenerate the figure).

================================================================================
#282  [T1] [THESIS]  Results/Discussion: refresh ALL numbers + conclusions from the NEW sweep
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

PENDING (when coarse mbs arms finish): refresh fig:boxel-resolution + subsec:resolution/disc-validity
resolution numbers, then re-run this same diff against those.

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
  FOUND BEYOND CATALOG (fix each in its own section):
    - results.tex sec:metrics: "Success ... without exceeding the per-episode replan limit" -> cap removed (#107).
    - results.tex sec:metrics: failure-mode list still names replan_limit + no_summary (both gone).
    - results.tex (denominators para): "differ by about 6% of cells" -> re-verify vs new sweep.
    - results.tex (planning-budget para): per-call medians 0.97/2.05/2.97 + "flat past ~200s" -> re-verify.
    - discussion.tex sec:disc-mbs0: "replan count rises slightly on holding and FATS" -> holding mbs05 now LOWER.
    - results.tex subsec:failure-modes: "across all 6 (goal,variant) cells" -> should be 9; confirm vs refreshed fig.

================================================================================
#283  [DONE 2026-06-04] [T2] [THESIS]  fig:boxelization: camera glyph unreadable at print scale (make it look like a camera)
NOTE 2026-06-04: regenerated thesis/graphics/boxelization_3d.png with a tripod-mounted camera. Edited
tools/render_boxelization_3d.py _camera(): raised the body onto three splayed legs (foot radius 0.95,
wider than the body half-width so the tripod is visible) so it reads as a camera rather than a black box.
Rendered with Windows Python and visually verified the new PNG (camera clearly a tripod-mounted camera,
lens aimed at the scene; rest of the 6-panel figure unchanged). Code-side = CODEBASE_AUDIT.txt #115.
================================================================================
[SUPERVISOR 2026-06-04] In boxelization_3d.png the camera marker is just a black box -- indistinguishable
from objects at print scale (Marc had to zoom ~469%). Make it clearly a camera: add a small tripod, give
it a distinct shape, or move it outside the task space to mark it as different. Must read on a PRINTED
page. Figure-code fix cross-filed as CODEBASE_AUDIT.txt #115; regenerate the figure (do NOT overwrite the
PNG silently; regenerate + visually verify).
Refs: thesis/graphics/boxelization_3d.png; methods.tex:20 (fig:boxelization); CODEBASE_AUDIT.txt #115. Related: #274 (same figure).

================================================================================
#284  [DONE 2026-06-04] [T3] [ADMIN]  Check whether a printed thesis copy is required (likely paperless now)
NOTE 2026-06-04: checked current RWTH policy (web). Digital submission via RWTHonline/DivA is now the
standard and is MANDATORY for theses registered from 2025-10-01 onward (theses registered before that
could choose digital or printed in agreement with the primary examiner). So no printed copy is expected
for a thesis submitted now -- submit the PDF digitally via RWTHonline. Caveat: a few programs may still
require printed+bound copies (3 to the ZPA) per PROGRAM-SPECIFIC examination regulations; confirm against
your program's regs and with your examiner/ZPA. Sources: rwth-aachen.de "Registering and Submitting Your
Thesis"; ITC blog "The Digital Submission of Theses Is Here!" (2024-12). Matches Marc's "paperless now".
ADDENDUM 2026-06-04 (author shared the internal RD wiki "Abschlussarbeit digital abgeben"):
Link: https://wiki-intern.rwth-aachen.de/spaces/RD/pages/108963485/Abschlussarbeit+digital+abgeben
  (RWTH-internal; needs RWTH login). It confirms the digital, no-print process and spells it out:
  - Tool: RWTHonline -> "Abgabe Abschlussarbeiten" (submit-thesis) application. TWO steps -- first UPLOAD
    the files, then click SUBMIT. Uploading alone does NOT count as handing in; only "Submit" is official.
  - Required documents: the thesis as a PDF; the Eidesstattliche Versicherung (statutory declaration of
    authorship); and, ONLY if the combined institute logo appears on the cover, a logo-usage request form.
    Main categories must be PDF; any extra files go in a zip.
  - Prerequisite, "ZPA-registered": ZPA = Zentrales Pruefungsamt (RWTH Central Examination Office). You can
    only submit once your thesis has been formally REGISTERED (Anmeldung der Abschlussarbeit) and approved
    by the ZPA; that registration fixes the official topic, the examiner(s), and the submission deadline,
    and only then does the "Abgabe Abschlussarbeiten" app accept your upload. NB: "ZPA-registered" refers
    to the THESIS being registered, NOT a special PDF format -- the file you upload is just your normal PDF.
  - Deadlines are in German CET. After you click Submit the files are LOCKED (cannot be changed), so upload
    the final version -- incl. the #281/#282 sweep-data refresh -- before submitting.
  - Confidential theses: password-protect the PDF and share access only with the examiner(s) + ZPA.
  No printed/bound copy is mentioned anywhere -- the process is fully digital.
================================================================================
[SUPERVISOR 2026-06-04] Confirm the current RWTH submission regulations: whether a physical printout is
required or submission is now paperless (Marc believes paperless, but verify against current rules;
printing can be expensive). Action item, not a document change.
Refs: RWTH / examination-office submission regulations.

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
  Methods: #175 (shadow-split #102/#103 -- only "by depth" dropped; conditional/surface-resting remain)
  Intro/RW: #193 (move Spatial-Belief to background; T1)
  Results: #199 (task rename), #209 (resolution-floor study + figure)
  Conclusion/front: #208 (add GitHub+GitLab code links)
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

DONE: #168, #176, #177, #178, #179, #180, #182, #183, #184, #185, #187, #188, #189, #190, #191, #194, #195, #197, #198, #200, #201, #202, #203, #204, #205, #206, #207, #211, #212, #213. MERGED: #192->#187, #196->#176. REJECTED: #186 (expansion declined).

Gating: #141-#156, #130 done — eval write-up (Results/Discussion/abstract/conclusion) is in
thesis/, chapters clear of internal paths + hardware clutter, front/back matter in place, nine
sim figures inserted. #125/#140/#121/#127 closed jointly. #126 (forward-voice conversion)
verified+closed (chapters already retrospective). §5 polish (#87-#111) resolved earlier.
