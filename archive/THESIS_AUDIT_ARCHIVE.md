================================================================================
THESIS AUDIT — RESOLVED / ARCHIVED ISSUES
================================================================================
Archived: 2026-05-19
Source:   thesis_audit.md (open-issues file)

Full bodies of the 36 resolved thesis-audit issues (32 [DONE], 4 [REJECTED]),
moved out of thesis_audit.md to slim the open-issues file. These blocks were
removed entirely from thesis_audit.md; this file is the record of their
content and disposition. Issues appear in their original filing order.

Resolved issues archived here:
#6 #7 #16 #22 #23 #25 #26 #28 #30 #64 #65 #66 #67 #68 #69 #70 #71 #72 #73 #74
#75 #76 #77 #78 #79 #80 #82 #83 #84 #85 #112 #117 #120 #122 #133 #135

[REJECTED]: #6 #64 #120 #122


================================================================================
#6  [T1 · Over-claim] [THESIS]  "robust manipulation" — execution is friction-free and collision-blind [REJECTED]
================================================================================
Where: Abstract abstract.tex:21; §1 introduction.tex:23; §5.4 evaluation.tex:34
What:  The proposal repeatedly claims "robust manipulation" / "a scalable and
       robust framework." The built manipulation layer is deliberately
       idealized: grasping is a rigid p.createConstraint() weld (objects cannot
       slip or drop), the final ~10 cm approach bypasses planner collision
       checks, and collisions are logged but never trigger a replan.
Fix:   Scope "robust" to robustness against belief/observation uncertainty (the
       real contribution), not physical grasp/contact robustness. Replace
       "robust manipulation" with "manipulation under an idealized
       perfect-gripper model" and disclose the simplifications.
Refs:  THESIS_NOTES §2, §12, §16, §19


================================================================================
#7  [T2 · Over-claim] [THESIS]  "scalable" asserted as delivered fact [DONE]
================================================================================
Where: Abstract — abstract.tex:18-21 ("a scalable and conceptually simple
       framework")
What:  "Scalable" is the headline contribution claim, but planning cost still
       grows with scene complexity: the stack feature roughly doubles per-call
       planning time, denser perception raises it further, and convex-only
       free-space merge produces extra boxels. Scalability vs uniform
       voxelization is plausible but is a result to demonstrate, not assert.
Fix:   Soften to "a conceptually simple framework whose boxel abstraction is
       designed to scale better than uniform voxelization"; let §5 substantiate
       it. (See #92 on "conceptually simple".)
Refs:  THESIS_NOTES §7, §9, §14


================================================================================
#16  [T2 · Style] [POLISH]  "aims to develop a system where" + "as needed" padding [DONE]
================================================================================
Where: §1 — introduction.tex:23
What:  "This thesis aims to develop a system where a robot, facing uncertainty
       about object locations, can plan and execute a sequence of
       information-gathering and manipulation actions as needed." Roundabout
       frame; "as needed" adds nothing.
Fix:   "This thesis builds a system in which a robot that is unsure where
       objects are can plan and carry out a mix of look-around and manipulation
       actions."


================================================================================
#22  [T1 · Deviation] [THESIS]  "perceived objects" misrepresents a ground-truth oracle [DONE]
================================================================================
Where: §1 introduction.tex:21; §4.2 approach.tex:11, 27
What:  §1 says Semantic Boxels are "dynamically created based on perceived
       objects (using their known 3D models)"; §4.2 step 1 builds a box around
       an object's "perceived pose." There is no perception pipeline:
       oracle_detect_objects() reads PyBullet ground-truth body poses
       (boxel_env.py:1620-1674); the depth/point-cloud path is commented out.
Fix:   State plainly that object detection is a ground-truth oracle that returns
       true poses (isolating the planning contribution from perception noise),
       and that a learned detector is future work. Replace "perceived" with
       "detected (oracle-provided)" plus this disclaimer.
Refs:  THESIS_NOTES §1


================================================================================
#23  [T2 · Deviation] [THESIS]  "adaptively generated Cuboids" — adaptivity/recursion not built [DONE]
================================================================================
Where: §1 — introduction.tex:21
What:  §1 defines the contribution as "Semantic Boxels---task-relevant,
       adaptively generated Cuboids" that are "dynamically created." The
       generator is single-pass with no in-partition object discovery; all
       objects are detected upfront. Putting "adaptive/dynamic" in the central
       definition implies a capability the build lacks. (See #65 for the §4.2
       recursive-partitioning claim.)
Fix:   Call them "object-centric, occlusion-aware Cuboids"; reserve
       "adaptive/recursive" for explicitly-labelled future work.
Refs:  THESIS_NOTES §20


================================================================================
#25  [T2 · Over-claim] [THESIS]  §1 implies the robot moves to sense [DONE]
================================================================================
Where: §1 — introduction.tex:23
What:  §1 frames information-gathering as a continuous-capability action the
       robot "plans and executes" and connects to "its continuous perception
       and action capabilities," implying the robot may move to sense. Sensing
       uses a fixed overhead camera; the robot never moves to a sensing pose,
       and the proposal's own stream_find_sensing_config is not implemented.
Fix:   Clarify (here or by deferring to §4) that sensing is a symbolic action
       evaluated against a fixed overhead viewpoint; computing a robot sensing
       configuration is a design element not realized in this thesis.
Refs:  THESIS_NOTES §3


================================================================================
#26  [T1 · Deviation] [THESIS]  §1 implies a sound belief search; the build has a 3-strike false-negative give-up [DONE]
================================================================================
Where: §1 introduction.tex:18-23; §2.2.1 background.tex:85 ("observations
       prune it")
What:  §1 sells the contribution as a sound belief-based search; §2.2.1 says
       belief is pruned by observations. The build, after sense_shadow_-
       raycasting returns "still_blocked" three times, marks the shadow
       "not_here" WITHOUT ever observing it (execution.py:1514-1524) — a
       "lying-to-progress" step that breaks the belief-reflects-observation
       invariant for unreachable shadows.
Fix:   Add an honest limitations note: a shadow still blocked after three
       sensing attempts is marked not-present without direct observation — an
       unsound but bounded fallback; the sound remedy (re-grounding
       view-blocking facts) is future work. Do not let §1/§2.2.1 imply
       unqualified soundness.
Refs:  THESIS_NOTES §18


================================================================================
#28  [T2 · Deviation] [THESIS]  §1 omits the optimistic-sensing + replanning design [DONE]
================================================================================
Where: §1 — introduction.tex:16, 23
What:  §1 frames the planner as natively reasoning over uncertain/branching
       outcomes. PDDLStream + FastDownward cannot do contingent planning, so the
       built sense action optimistically assumes success and the Python loop
       replans on failure.
Fix:   State that partial observability is handled by optimistic deterministic
       sensing plus reactive replanning (a standard POD-TAMP pattern), not
       contingent planning. This honestly frames the "POD" label.
Refs:  THESIS_NOTES §5


================================================================================
#30  [T3 · Style] [NOW]  Grammar — "we proposes" [DONE]
================================================================================
Where: §1 — introduction.tex:21
What:  "Here, we proposes a novel approach..." Subject-verb disagreement in a
       sentence that states the proposal's core contribution. (See #118 for the
       companion error in §3.)
Fix:   "Here, we propose a novel approach..."


================================================================================
#64  [T2 · Deviation] [THESIS]  §4.2 component named "Adaptive Semantic Discretization" overpromises [REJECTED]
================================================================================
Where: §4.2 — approach.tex:11, 16-17
What:  Component 1 is named "Adaptive Semantic Discretization: A dynamic
       procedure..."; the generator is single-pass with no in-partition object
       discovery. "Adaptive/dynamic" as the contribution's name overstates.
Fix:   Rename to e.g. "Object-Centric Semantic Discretization" or
       "Occlusion-Aware Semantic Partitioning"; describe it as a
       perception-triggered partition pass.
Refs:  THESIS_NOTES §20; #23


================================================================================
#65  [T1 · Deviation] [THESIS]  §4.2 step 3 "Recursive Partitioning" is not implemented [DONE]
================================================================================
Where: §4.2 step 3 approach.tex:30; Fig 2(d) caption approach.tex:21
What:  Step 3: "...If new objects are found within a partition, the process
       repeats: bound the biggest object and define its occluded space. This
       continues until ... no new objects are detected." FreeSpaceGenerator.
       generate() is a single-pass octree; it never detects new objects inside
       partitions, and "bound the biggest object" has no code analogue.
Fix:   Reword step 3 to describe the single-pass octree subdivision that
       terminates at min_resolution; move the "if new objects are found, repeat"
       clause into a clearly-marked future-work paragraph (it would matter for
       partial-coverage sensors / concave geometry).
Refs:  THESIS_NOTES §20


================================================================================
#66  [T1 · Deviation] [THESIS]  §4.2 — Boxel generation is plain pre-planning Python, not "managed by PDDLStream procedures"  (undisclosed) [DONE]
================================================================================
Where: §4.2 approach.tex:17, 21; Fig 2 caption
What:  §4.2 says the discretization "will be managed by PDDLStream procedures"
       and that Boxels are "accessible to the planner via PDDL fluents."
       generate_boxels(), generate_free_space(), ShadowCalculator,
       FreeSpaceGenerator, CellMerger are ordinary Python run BEFORE solve().
       The four real streams (sample-grasp, plan-motion, compute-kin,
       compute-stack-kin) are all IK/motion/grasp — none generates Boxels. The
       planner receives a finished BoxelRegistry and reads it into static init
       facts.
Fix:   State that Boxel generation is a Python perception/discretization stage
       run before each planning call (re-run between actions via reboxelize.py),
       feeding the planner static init facts — it is not a PDDLStream procedure.
       Revise Figure 2's framing. NOT in THESIS_NOTES — undisclosed.
Refs:  (undisclosed deviation)


================================================================================
#67  [T1 · Deviation] [THESIS]  §4.4.1 Listing 1 PDDL fluent names do not exist in the domain [DONE]
================================================================================
Where: §4.4.1 Listing 1 — approach.tex:56-72; code pddl/domain_pddlstream.pddl
What:  Listing 1 declares (semantic_zone ?b - Boxel_id), (obj_in_Boxel ?o ?b),
       (obj_not_in_Boxel ?o ?b). None exist in the domain. The domain uses
       (Boxel ?x) instead of semantic_zone, (obj_at_boxel ?o ?b) plus a single
       Know-If fluent (obj_at_boxel_KIF ?o ?b) instead of the two K-literal
       predicates. Only obj_pose_known survives by name.
Fix:   Rewrite Listing 1 to the real predicates, or keep it illustrative and add
       a sentence (and a thesis subsection) disclosing the single-Know-If-fluent
       collapse. The semantic_zone -> Boxel rename is undisclosed.
Refs:  THESIS_NOTES §6


================================================================================
#68  [T1 · Deviation] [THESIS]  §4.4.2 sense action name and signature do not match the domain [DONE]
================================================================================
Where: §4.4.2 Listing 2 — approach.tex:79-85; code domain_pddlstream.pddl:156-171
What:  Listing 2 defines (:action sense_Boxel_for_object) with typed parameters
       ?Boxel_target - Boxel_id, ?q_sense - robot_config, ?obs_status -
       observation. The real action is "sense" with :parameters (?o ?region) —
       untyped (the domain is :strips :equality), no ?q_sense, no ?obs_status.
       The types Boxel_id / robot_config / observation appear nowhere in the
       code.
Fix:   Rename to "sense", show the real STRIPS signature, or state explicitly
       that the listing is an early illustrative sketch the build simplified.
Refs:  THESIS_NOTES §3, §5


================================================================================
#69  [T1 · Deviation] [THESIS]  §4.4.2 conditional found/not_found sense effects are not implemented [DONE]
================================================================================
Where: §4.4.2 Listing 2 — approach.tex:95-113; code domain_pddlstream.pddl:156-171
What:  Listing 2 uses contingent branching: "(when (= ?obs_status found) ...)"
       and "(when (= ?obs_status not_found) ...)". The real sense effect is
       unconditional and optimistic ("OPTIMISTIC: assume found"); belief update
       happens in the Python loop (belief.mark_sensed). PDDLStream/FastDownward
       cannot do contingent planning. A 36-line comment block in the domain
       already documents this.
Fix:   Add a thesis paragraph disclosing optimistic sensing + reactive
       replanning as an accepted simplification; the domain comment block has a
       thesis-ready justification.
Refs:  THESIS_NOTES §5


================================================================================
#70  [T1 · Deviation] [THESIS]  §4.4 streams stream_find_sensing_config / stream_get_sensing_outcome do not exist [DONE]
================================================================================
Where: §4.4.2 Listing 2 + closing para — approach.tex:92-93, 115; code
       pddl/stream.pddl
What:  Listing 2's precondition calls stream_find_sensing_config and
       stream_get_sensing_outcome, and the closing paragraph describes them as
       real. stream.pddl declares only four streams (sample-grasp, plan-motion,
       compute-kin, compute-stack-kin). There is no sensing-config stream — the
       fixed overhead camera makes a robot sensing pose (?q_sense) unnecessary.
Fix:   Disclose that no sensing streams are used: the fixed overhead camera
       makes a sensing pose unnecessary and the observation outcome is resolved
       by the Python execution loop. Update or remove the §4.4.2 closing
       paragraph.
Refs:  THESIS_NOTES §3


================================================================================
#71  [T1 · Scientific] [THESIS]  §4.4.2 Listing 2 claims an inference the formalism does not provide [DONE]
================================================================================
Where: §4.4.2 Listing 2 — approach.tex:98-104
What:  In the "found" branch the comment says "We can now infer it's not in any
       other Boxel. This inference is handled by the POD planner's belief
       update." The effect block only adds (obj_in_Boxel ...) and
       (obj_pose_known ...) — no (obj_not_in_Boxel ...) for other Boxels.
       Standard PDDLStream has no automatic belief-update mechanism; the
       mutual-exclusion is not encoded.
Fix:   Add an explicit universally-quantified effect ((forall (?b) (when (not
       (= ?b ?Boxel_target)) (obj_not_in_Boxel ?obj ?b)))) or a derived
       predicate / axiom for single-Boxel occupancy, and state which mechanism
       realizes it. Do not defer it to an unspecified "belief update."


================================================================================
#72  [T1 · Scientific] [THESIS]  §4.4.2 puts stream_* calls inside :precondition (stream vs certified-fluent confusion) [DONE]
================================================================================
Where: §4.4.2 Listing 2 — approach.tex:91-93
What:  The sense action's :precondition literally contains
       "(stream_find_sensing_config ...)" and "(stream_get_sensing_outcome
       ...)" as if the stream names were predicates. In PDDLStream a
       :precondition is a conjunction of fluents; streams are declared
       separately and produce CERTIFIED facts, which are what appear in
       preconditions. §2.3.1 explains this correctly — so §4.4.2 contradicts
       §2.3.1.
Fix:   Rewrite the precondition to reference certified fluents (e.g.
       (sensing_config ...), (sensing_outcome ...)) and add separate stream
       declarations whose :certified clauses produce them.
Refs:  #70


================================================================================
#73  [T1 · Deviation] [THESIS]  §4.3 formal element O (sensor model) is not a planner component [DONE]
================================================================================
Where: §4.3 — approach.tex:46; code domain_pddlstream.pddl, belief.py:37-43
What:  §4.3 lists O (Sensor Model) as a first-class element of M = <S, S0, SG,
       A, f, O>. There is no observation function in the planner; the optimistic
       sense action just asserts obj_at_boxel. The observation->belief mapping
       lives entirely in Python (BeliefState.mark_sensed); the labels
       found_target / not_found_target are not PDDL symbols.
Fix:   Disclose that the sensor model O is realized by the Python sense-plan-act
       loop (belief.py + the execution handler), not by an observation function
       inside the POD planner — a consequence of optimistic sensing.
Refs:  THESIS_NOTES §5; #69


================================================================================
#74  [T2 · Scientific] [NOW]  §4.3 "model taken from the work of Bonet and Geffner" — tuple likely not in that paper [DONE]
================================================================================
Where: §4.3 — approach.tex:35-37
What:  "We formalize our Semantic POD-TAMP system using a model taken from the
       work of Bonet and Geffner [bonet2014flexible]. The model is a tuple M =
       <S, S0, SG, A, f, O>." Ref bonet2014flexible (AAAI 2014) is a
       linear-translations paper; Bonet & Geffner's partially observable
       problems are conventionally given in factored, PDDL-like form, not as an
       explicit flat tuple of state sets with a transition function f. NEEDS
       VERIFICATION against the paper.
Fix:   Verify the formalism in Bonet & Geffner (2014). If the explicit-state
       tuple is not in that paper, cite geffner2013concise (the textbook) for
       the explicit POD model, or reword to "a model in the spirit of Bonet and
       Geffner's formulation" and present the tuple as the proposal's own.


================================================================================
#75  [T3 · Deviation] [THESIS]  §4.3 formal element f — no K-literal transition function [DONE]
================================================================================
Where: §4.3 — approach.tex:45
What:  §4.3 defines f as "a deterministic state-transition function ... based on
       an action's effects on the K-literals." State transitions are ordinary
       STRIPS effects on obj_at_boxel / obj_at_boxel_KIF; with one Know-If
       fluent instead of K(p)/K(¬p) literals, "effects on the K-literals" is not
       literally what f operates on. Consequence of #67.
Fix:   When §4.3 is reconciled with the real domain, restate f as STRIPS effect
       application over Know-If fluents.
Refs:  THESIS_NOTES §6; #67


================================================================================
#76  [T3 · Deviation] [THESIS]  §4.1/§4.2 "contrasts with octrees" is imprecise [DONE]
================================================================================
Where: §4.2 — approach.tex:32
What:  "This adaptive, object-centric approach contrasts with octrees and
       uniform voxel grids..." The free-space stage is itself an octree
       (free_space.py, "octree-based breadth-first subdivision"), and a
       UniformGridGenerator baseline is implemented for comparison.
Fix:   The approach contrasts with UNIFORM voxel grids by being object-centric;
       its free-space stage is an octree, and a uniform-grid baseline exists for
       comparison.


================================================================================
#77  [T3 · Deviation] [THESIS]  §4.3/§4.4 example action "pick_object_from_known_Boxel" + false precondition claim [DONE]
================================================================================
Where: §4.3 approach.tex:44; §4.4.2 closing approach.tex:115
What:  §4.3 lists an action "pick_object_from_known_Boxel"; the real action is
       "pick" with :parameters (?o ?b ?g ?q). §4.4.2's closing sentence says
       pick's precondition requires "(obj_pose_known ?obj)" — the real pick
       gates on (obj_at_boxel_KIF ?o ?b) and (obj_at_boxel ?o ?b), NOT
       obj_pose_known (which is only an effect of sense/place).
Fix:   Use the real action name "pick" and correct the precondition claim.


================================================================================
#78  [T3 · Deviation] [THESIS]  §4.4.1 obj_pose_known commented "K(HasExactPose)" — really Boxel-granularity [DONE]
================================================================================
Where: §4.4.1 Listing 1 — approach.tex:68
What:  Listing 1 comments "(obj_pose_known ?o) ; K(HasExactPose(?o))". After an
       optimistic sense, obj_pose_known becomes true even though the object was
       only assumed found in a Boxel REGION — the planner knows a region, not an
       exact pose.
Fix:   Reword the comment to "known to be in a specific Boxel" rather than
       "HasExactPose", or note Boxel-granularity is the operative precision.
Refs:  THESIS_NOTES §11


================================================================================
#79  [T3 · Deviation] [THESIS]  §4.2 step 2 occlusion wording overstates — single fixed viewpoint, geometry not refreshed [DONE]
================================================================================
Where: §4.2 step 2 — approach.tex:28
What:  Step 2 computes occlusion "from the robot's current or potential
       viewpoints." There is exactly one fixed camera at [0.1,-0.8,0.7]; there
       is no iteration over viewpoints. Separately, shadow geometry is computed
       once and is not recomputed after an occluder is relocated.
Fix:   "from the fixed camera viewpoint"; note shadow geometry is computed at
       initial boxelization and not refreshed after an occluder moves (the moved
       occluder is tracked in belief); full re-boxelization is future work.
Refs:  THESIS_NOTES §3, §8, §10
Note:  The shadow set is updated as the robot acts: sensing resolves a shadow,
       and discovering a new object adds one. A relocated object is NOT given a
       new shadow at its destination — re-creating shadows for moved objects
       could admit non-terminating plans, so it is omitted; safe handling needs
       extra belief bookkeeping and is future work. §4.2 step 2 states this.


================================================================================
#80  [T3 · Deviation] [THESIS]  §4.2 step 2 / Fig 2(c) "a new, distinct Boxel" singular [DONE]
================================================================================
Where: §4.2 step 2 — approach.tex:28; Fig 2(c) caption
What:  Step 2 says an occluder's occluded space "is calculated and designated as
       a new, distinct Boxel" (singular). ShadowCalculator splits each shadow
       into a near and far slab, and obstacle subtraction can fragment it
       further — one occluder usually yields 2+ shadow Boxels.
Fix:   Pluralize: an occluder's occluded volume becomes one or more shadow
       Boxels, split by depth and by intervening obstacles.


================================================================================
#82  [T3 · Deviation] [THESIS]  §4.3 state example K(InBoxel(obj_k, Boxel_j)) uses a non-existent relation [DONE]
================================================================================
Where: §4.3 — approach.tex:41, 43
What:  §4.3's state-proposition example "K(InBoxel(obj_k, Boxel_j))" uses the
       relation InBoxel; the real Know-If fluent is obj_at_boxel_KIF. (The goal
       example K(holding(target_obj)) is essentially correct — the real goal
       tuple is ('holding', target_name).)
Fix:   Replace InBoxel with the real obj_at_boxel_KIF fluent when reconciling
       §4.3. Consequence of #67.
Refs:  THESIS_NOTES §6, §9; #67


================================================================================
#83  [T3 · Deviation] [THESIS]  §4.4.2 Listing 2 precondition double-negation vs the real single-negation [DONE]
================================================================================
Where: §4.4.2 Listing 2 — approach.tex:88-90
What:  Listing 2 encodes uncertainty as "(not (obj_in_Boxel ...)) (not
       (obj_not_in_Boxel ...))". With one Know-If fluent the real sense
       precondition is a single "(not (obj_at_boxel_KIF ?o ?region))", plus
       (view_clear ?region) and (boxel_fits ?o ?region) which have no
       counterpart in Listing 2.
Fix:   When Listing 2 is reconciled, show the single-negation obj_at_boxel_KIF
       form and mention the view_clear / boxel_fits preconditions that gate real
       sensing. Consequence of #67 + #69.
Refs:  THESIS_NOTES §6; #67, #69


================================================================================
#84  [T2 · Style] [POLISH]  §4.4 — "we can define" hedge stack [DONE]
================================================================================
Where: §4.4 — approach.tex:51
What:  "To illustrate how this model can be implemented, we can define a set of
       PDDL-like fluents ... This is not a complete implementation, but it
       should give an idea of how the model can be used." Stacked hedges make
       the author sound unsure.
Fix:   "We now define example PDDL fluents and PDDLStream actions that operate
       on the belief state over Boxels. This is a sketch, not a full
       implementation, but it shows how the model is used."


================================================================================
#85  [T2 · Style] [POLISH]  §4.4.2 — "Information gathering is a central part of the framework" [DONE]
================================================================================
Where: §4.4.2 — approach.tex:76
What:  "Information gathering is a central part of the framework. The following
       action allows the robot to sense a specific Boxel..." The first sentence
       is interchangeable filler.
Fix:   Delete the first sentence: "The following action lets the robot sense a
       specific Boxel to check whether a target object is present."


================================================================================
#112  [T0 · Citation] [NOW]  "Critical Regions" and "RBVD" attributed to the wrong paper [DONE]
================================================================================
Where: §2.4 background.tex:154-157; §3.2.2 related_work.tex:39;
       references.bib (shah2022abstractions)
What:  The proposal says Critical Regions were "introduced by Siddharth
       Srivastava [shah2022abstractions]" (Shah & Srivastava, "Using Deep
       Learning to Bootstrap Abstractions...", AAMAS 2022). The concept of
       learned Critical Regions originates in Molina, Kumar & Srivastava, "Learn
       and Link: Learning Critical Regions for Efficient Planning" (ICRA 2020).
       shah2022abstractions uses and extends CRs but is not the originating
       paper; "introduced by Siddharth Srivastava" also wrongly implies sole
       authorship.
Fix:   Cite Molina, Kumar & Srivastava ("Learn and Link", ICRA 2020) as the
       origin; keep shah2022abstractions for the abstraction-bootstrapping use.
       Reword to "introduced by Molina et al. and extended by Shah and
       Srivastava [shah2022abstractions]." (Verify against the papers.)


================================================================================
#117  [T2 · Build] [NOW]  Duplicate \label and figure \label placed outside the float [DONE]
================================================================================
Where: background.tex:50 & approach.tex:55 (duplicate label); background.tex:
       141-147 & approach.tex:18-23 (label outside float)
What:  (a) Two listings share \label{lst:pddl_fluents_k_literal} (the §2.1.1
       stack listing and the §4.4.1 fluents listing) — duplicate-label warning;
       any \ref resolves to whichever was processed last. (b)
       \label{fig:octmap_illustration} (background.tex:147) and
       \label{fig:boxelization} (approach.tex:23) are placed AFTER \end{figure},
       so \ref captures the section counter, not the figure number. The octree
       \ref is also bare instead of \cref.
Fix:   Rename the §2.1.1 listing label (e.g. lst:pddl_stack_action). Move each
       figure \label inside the figure environment, right after \caption.
       Replace bare \ref{fig:...} with \cref{fig:...}.


================================================================================
#120  [T3 · Style] [NOW]  Informal nickname — "Sidd's Critical Regions" / "Sidd's approach" [REJECTED]
================================================================================
Where: §2.4 background.tex:154-157; §3.2.2 related_work.tex:39
What:  The §2.4 paragraph heading is "Sidd's Critical Regions"; the text says
       "In Sidd's approach"; §3.2.2 has "Sidd's Critical Regions (CRs):". "Sidd"
       is an informal nickname for Siddharth Srivastava and is inappropriate in
       a formal thesis; it also implies sole authorship.
Fix:   Use formal phrasing — heading "Critical Regions"; in text "the Critical
       Regions approach of Shah and Srivastava" / "Molina et al." Remove all
       "Sidd" references.
Refs:  #112
Note:  [REJECTED 2026-05-18] User keeps the "Sidd's" naming for disambiguation;
       many distinct notions of "critical region" exist. The wrong-paper
       attribution is a separate, still-open matter — see #112.


================================================================================
#122  [Structural] [THESIS]  No Implementation chapter — the built system is undocumented [REJECTED]
================================================================================
Where: new chapter; §4 approach.tex
What:  §4 "Approach" describes a DESIGN — "we propose", and §4.4 states outright
       "This is not a complete implementation, but it should give an idea". A
       thesis needs a chapter documenting what was actually BUILT: the PyBullet
       environment, the boxel pipeline (generate_boxels, ShadowCalculator,
       FreeSpaceGenerator, CellMerger, reboxelize), the real PDDLStream domain
       (the four real streams; the real STRIPS sense action), and the
       sense-plan-act execution loop. The §4 deviation issues #64-#83 each say
       "reconcile the text with the code" — that reconciliation IS this chapter.
Fix:   Add an Implementation chapter. Keep §4 as the conceptual approach;
       describe the real system in the new chapter. Reconcile #64-#83 against
       it, rather than as 20 isolated sentence-patches.
Refs:  #64-#83; THESIS_NOTES §1-§20
Note:  [REJECTED] 2026-05-19 — a separate Implementation chapter is not added.
       The #64-#83 reconciliation was instead carried out within §4 itself: the
       §4.3 and §4.5 rewrites now describe the built system (the real PDDL
       domain and sense action, the four streams, optimistic sensing, the boxel
       pipeline). A separate Implementation chapter would duplicate §4. A
       placeholder stub was created then removed (commits 91a04da, 4f6cda6).


================================================================================
#133  [T3 · Style] [NOW]  §1 roadmap term — "voxelization" vs §4 "discretization" [DONE]
================================================================================
Where: §1 introduction.tex:24
What:  The §1 roadmap referred to "adaptive semantic voxelization" while §4.2
       names the process "Adaptive Semantic Discretization" — two terms for the
       same process.
Fix:   Changed the §1 roadmap to "adaptive semantic discretization" to match
       §4. Done in commit c140cfa (the §1 thesis-voice conversion).


================================================================================
#135  [Structural] [THESIS]  KIF + stream synthesis is undocumented; §2.2.1 K-literal coverage is thin [DONE]
================================================================================
Where: §2.2.1 background.tex:84-91; §4 approach.tex (new subsection needed)
What:  The thesis's belief representation is the Geffner-Bonet K-literal
       translation (Know-If Fluents, KIFs), combined with PDDLStream streams for
       continuous geometry. §2.2.1 mentions K-literals only briefly and never
       explains the translation or names KIFs; §4 never presents the synthesis
       (KIF belief + streams in one PDDL domain) as the core idea of the
       approach.
Fix:   (A) Expand §2.2.1 to present the K-literal translation (each literal L
       becomes K(L)/K(not L), unknown = neither, compiling partial observability
       into a classical problem) and introduce the term Know-If Fluent.
       (B) Add a new §4 subsection presenting the synthesis: belief carried by
       KIFs over Boxels, mixed with PDDLStream streams for the continuous
       geometry, in one PDDL domain.

