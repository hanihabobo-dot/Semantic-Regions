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
#168  [T1] [THESIS]  Figures/captions review --- go through every figure one by one
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
================================================================================
CODEBASE #102 made the per-occluder depth split CONDITIONAL (a non-intersecting occluder
casts ONE shadow Boxel; only a shadow overlapping another region splits into near+far +
intervening obstacles); #103 stops mid-air/held occluders casting shadows (only objects on
the support surface do). Current prose implies every shadow splits by depth — overstates the
code. Fix: reword depth-split as conditional + note the occluder must rest on a surface.
Cross-check the shadow figures in #168 (they show the two-slab case).
Refs: methods.tex; CODEBASE_AUDIT.txt #102 #103; #168.

================================================================================
#176  [T3] [THESIS]  Discretization-progression figure (PyBullet captures) + free-space split->merge stages (merged #196)
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
#179  [T2] [POLISH]  Intro contributions: drop TAMPURA from section 1, cut the "first-class state" opener
================================================================================
introduction.tex:31: (a) confine TAMPURA to Related Work — remove the "dense visibility
voxel grid of TAMPURA's Find Die ... learned model" clause + the "architectural comparison
with TAMPURA" preview (comparison stays in Results/Discussion, #177); (b) cut the empty "we
make occlusion first-class symbolic planning state" opener, run the colon into "each volume
the robot cannot see becomes a named region a classical POD planner reasons over and resolves
by sensing." Keep ablation + oracle-perception framing.
Refs: introduction.tex:31; #177; related-work.tex.

================================================================================
#180  [T3] [POLISH]  Background state-model notation: Pi for the tuple is unconventional
================================================================================
background.tex:13 uses tuple Pi=<S,s_0,S_G,Act,A,f>; :69 "state model S(P)". Standard
Geffner&Bonet formalism (geffner2013concise, cited :11), but Pi conventionally = plan/policy,
so it can trip a reader. Fix (optional, author picks): (a) leave; (b) cite geffner2013concise
at :13; (c) rename tuple to a neutral letter (e.g. M).
Refs: background.tex:11,13,69; geffner2013concise.

================================================================================
#181  [T2] [POLISH]  "POD ... rather than established terminology" -- name the real term (contingent planning)
================================================================================
background.tex:85 hedges that "POD" isn't established terminology. Verified: the literature
calls this exact setting CONTINGENT PLANNING; the hedge is true but bare. Fix: name it —
"This is the setting the planning literature calls \emph{contingent planning}
\cite{albore2009translation, geffner2013concise}; 'POD' is the descriptive label we use."
Refs: background.tex:85; albore2009translation; geffner2013concise.

================================================================================
#182  [T3] [POLISH]  Background heading "Voxel Grids and Octrees" -> "Voxel Grids"
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
#184  [T3] [POLISH]  pan2024task: "reactive controllers" -> their term is "behaviors"
================================================================================
related-work.tex:15. Verified: Pan et al. (TAMPER) fill plan gaps with closed-loop
"behaviors" (hand-designed OR learned), prioritising them over re-planning (the "struggle"
claim stands). Fix: "specialized reactive controllers" -> "specialized closed-loop behaviors
(hand-designed or learned)"; rest correct.
Refs: related-work.tex:15; pan2024task.

================================================================================
#185  [T2] [POLISH]  Rewrite the hard-to-read Ma et al. paragraph
================================================================================
related-work.tex:20. Opener "real-world messiness" is filler; paragraph hard to read.
Ma et al. verified: Task-level Backward Search = work backward from an underspecified goal to
find needed objects; Object Manipulation Constraint Graph = order moves through clutter
collision-free. Fix: drop the opener, rewrite for clarity ("Ma et al. add a strategic
reasoning layer ... we differ at the representation level rather than adding a layer"); keep
the oracle parenthetical.
Refs: related-work.tex:20; ma2025task.

================================================================================
#186  [T2] [POLISH]  CoCo-TAMP description too thin -- expand mechanism
================================================================================
related-work.tex:22. Verified mechanism: LLM asked multiple-choice location questions ->
softmax over answer log-probs -> distribution over semantic locations -> hierarchical Bayesian
filter; planner consumes it via SENSING-ACTION COST (unlikely views cost more), so it drives
WHERE to look, not just the prior. Fix: expand to ~2 sentences (QA->distribution->filter +
observation-cost coupling).
Refs: related-work.tex:22; kim2026llmguided (arXiv:2603.03704).

================================================================================
#187  [T1] [NOW]  related-work.tex:24 Bai et al.: wrong limitation + framework name/mechanism (merged #192)
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

================================================================================
#191  [T3] [THESIS]  Intro hero caption: identify the target object
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
#194  [T2] [POLISH]  Related-work framing: drop marketing voice; cut the over-long "three advantages" paragraph
================================================================================
related-work.tex:35 "sits at the intersection" = marketing -> "we build on / extend ...";
:37 three-advantages paragraph far too long (restates occlusion-as-state / no-probabilities /
no-MDP w/ costs) -> condense to a few sentences or compact list.
Refs: related-work.tex:35,37.

================================================================================
#195  [T2] [NOW]  Methods clarity: rephrase "optimistic determinisation", explain "untyped STRIPS", delete a self-justification
================================================================================
methods.tex:63,87,90,133. (O) "optimistic determinisation and reactive replanning" opaque ->
"assume each sensing action succeeds (optimistic), plan as if the world were fully known,
execute, and replan when an observation contradicts that (reactive replanning)". (P) "untyped
STRIPS" unexplained -> gloss "no PDDL type declarations, so object categories are ordinary
predicates not types". (Q) delete the ":133 standard pattern" self-justification.
Refs: methods.tex:63,87,90,133.

================================================================================
#196  [MERGED 2026-05-25 into #176]  Free-space generation stages (split -> convex merge) figure
================================================================================
Folded into #176. Content: a methods.tex figure of the free-space build — (1) all space incl.
objects, (2) recursive octree split, (3) recursive convex merge — via tools/render_thesis_figs.py.

================================================================================
#197  [T1] [NOW]  fig:replan-cycle caption is wrong vs the image
================================================================================
methods.tex:145 (sim/replan_cycle.png). Caption ("action log reads 'sense
shadow_of_purple_object --- target not here' ... marks shadow empty ... searching remaining
shadows") does NOT match the image. Fix: inspect the PNG (#168), rewrite caption to match the
actual logged action/scene; recapture if the image is wrong.
Refs: methods.tex:145; sim/replan_cycle.png; #168.

================================================================================
#198  [T3] [THESIS]  Figure captions/sizes to fix after visual inspection
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
#200  [T0] [NOW]  results:83 "well under a second per call" is FALSE
================================================================================
results.tex:83. Data-contradicted (sweep_anytime): pooled per-call planning over successful
cells median ~1.99 s, mean ~5.4 s, only ~19% <1 s. By goal: stack 0.97 s (54% <1s); find 2.05 s
(10%); find-and-stack 2.97 s (3%). Fix: replace w/ real per-goal medians; describe the 1800 s
cap as a safety bound hit only by rare pathological/timeout cells. Drop "well under a second".
Refs: results.tex:83; eval_results/sweep_anytime (per_call_planning_time_s).

================================================================================
#201  [T2] [THESIS]  Results clarity: drop_failed, denominator note, "known to be empty", one-boxel-per-object
================================================================================
results.tex:96,98,105. (Y) drop_failed unexplained -> when the gripper can't release a non-
target object, after three failed drop events the episode exits (depends on CODEBASE #106). (Z)
":98 two denominators differ by ~6% (early timeouts without a recorded state)" opaque -> rephrase
plainly. (AA) ":105 where the workspace is empty" -> "...KNOWN to be empty" (belief). (AC) "finer
leaves break placement" is a design choice (each object bounded by exactly ONE boxel) — explain.
Refs: results.tex:96,98,105; CODEBASE_AUDIT #106.

================================================================================
#202  [T1] [THESIS]  semantic+mbs0.05 is effectively identical to semantic (a no-op variant)
================================================================================
results.tex:106. Data-confirmed: semantic+mbs0.05 = plain semantic to ~0.1% (find 35.07 vs
35.03), same results — the 5 cm floor never binds (autosize ~6-9 cm) and finer floors are
absorbed by the convex merge (#203). Presenting it as "testing a finer floor" is misleading.
Fix: drop the variant or reframe honestly as evidence the floor does NOT change the partition
(merge dominates). Coordinate w/ #203, CODEBASE #108.
Refs: results.tex:106; eval_results/sweep_anytime; #203; CODEBASE_AUDIT #108.

================================================================================
#203  [T0] [NOW]  discussion:60 "at the cost of more cells" is FALSE; "characterisation of the regime" is empty
================================================================================
discussion.tex:60. (AK) Data-contradicted: a finer free-space floor does NOT add cells (greedy
convex merge -> counts identical across semantic/mbs0.05/mbs0.09, e.g. stack free 17.64 in all);
only COARSER floors reduce counts. (AL) "characterisation of the regime, not a defect" = filler.
Fix: correct to "min free-space leaf size has little effect on cell count (convex merge); only
coarsening reduces it"; delete the filler sentence. Figure: CODEBASE #108.
Refs: discussion.tex:60; eval_results/sweep_anytime; #202; CODEBASE_AUDIT #108.

================================================================================
#204  [T2] [THESIS]  discussion:24 stack-goal boxel ratio -- stack needs no free-space partition
================================================================================
discussion.tex:24 ("stack ratio steeper, semantic ~25 vs uniform ~1340"). Stack is fully
observable and needs no free-space partitioning, so the ratio isn't meaningful there. Fix: drop
it, or state stack is fully observable (no shadows) so the ratio reflects only the uniform
baseline's free-space blow-up, not a partial-observability benefit.
Refs: discussion.tex:24.

================================================================================
#205  [T0] [NOW]  discussion:266 stacking slowdown misattributed (bigger domain, not pick conditional-effects)
================================================================================
discussion.tex:266 ("stacking ~doubles per-call planning, traced to the pick conditional-
effects requirement"). Code-contradicted (git 0d5def7): "add --goal stack" added all at once a
new stack action (7 pre/6 eff), 3 predicates (on, clear, stack_kin), a stream compute-stack-kin,
AND the conditional :requirement + forall-when on pick (which grounds to a no-op on find runs).
So the slowdown is a LARGER DOMAIN, not the pick conditional effect. Fix: re-attribute to the
enlarged domain (added action+predicates+stream raising grounding/search cost).
Refs: discussion.tex:266; pddl/domain_pddlstream.pddl; git 0d5def7.

================================================================================
#206  [T2] [THESIS]  Discussion section-6 trims and clarity
================================================================================
discussion.tex. (AO) delete the whole \section{Failure modes} (:123) — duplicates results
coverage. (AN) remove :121 "restoring a blocked view ... give-up rule" clause. (AQ) remove :239
"local IK solver bypasses collision checks" sentence. (AS) remove :258 "string identifiers as
proxies for geometric volumes" sentence. (AU) remove :268 "this regression is accepted rather
than optimized away" sentence. (AP) :168 "would narrow" -> "could narrow". (AR) :245 explain
"non-pathological start configuration" = a collision-free start configuration for the next move.
Refs: discussion.tex:121,123,168,239,245,258,268.

================================================================================
#207  [T3] [THESIS]  Success-rate-vs-n_occ caption should state what the band is
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

--------------------------------------------------------------------------------
NB (verified, NO issue filed):
 - discussion.tex:121 "an object can be placed view-blind" (TAMPURA) is TRUE — verified from
   find_dice code (placement sampler = uniform x/y + random yaw, no visibility check; place has
   no visibility precondition). Optionally add a one-line basis. [code-confirmed]

================================================================================
OPEN ISSUES
================================================================================
OPEN:
  Figures: #168  (every figure one-by-one; figures agent)
  Figures: #176  (discretization-progression figure + free-space split->merge stages, merged #196)
  Methods: #175  (shadow-splitting prose vs #102/#103 code)
  Intro: #179 (de-hype TAMPURA + cut "first-class" opener)
  Background: #180 (Pi/S(P) notation), #181 (name "contingent planning"), #182 ("Voxel Grids" heading)
  Related Work: #184 (pan "behaviors"), #185 (Ma paragraph rewrite), #186 (CoCo-TAMP expand),
                #187 (Bai: limitation + TAVP name/learned-policy; merged #192; T1/NOW)
  Intro/RW: #191 (hero caption target), #193 (move Spatial-Belief to background; T1), #194 (marketing voice + over-long para)
  Methods: #195 (optimistic-determinisation/untyped/standard-pattern clarity), #197 (replan-cycle caption wrong; T1/NOW)
  Figures: #198 (boxelization-real/partition-comparison/eval-scene/give-up captions+sizes)
  Results: #199 (task rename), #200 (per-call <1s FALSE; T0/NOW), #201 (drop_failed/denominator/known-empty/one-boxel),
           #202 (mbs0.05 no-op; T1), #207 (success-rate band caption), #209 (resolution-floor study + figure)
  Discussion: #203 ("more cells" FALSE; T0/NOW), #204 (stack ratio mention), #205 (stacking slowdown misattributed; T0/NOW), #206 (section-6 trims)
  Conclusion/front: #208 (add GitHub+GitLab code links)
  Style (very low priority): #210 (drop author names, cite by number; T3/POLISH)

DONE: #177, #178, #183, #188, #189, #190. MERGED: #192->#187, #196->#176.

Gating: #141-#156, #130 done — eval write-up (Results/Discussion/abstract/conclusion) is in
thesis/, chapters clear of internal paths + hardware clutter, front/back matter in place, nine
sim figures inserted. #125/#140/#121/#127 closed jointly. #126 (forward-voice conversion)
verified+closed (chapters already retrospective). §5 polish (#87-#111) resolved earlier.
