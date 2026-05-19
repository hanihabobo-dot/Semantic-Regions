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
#  ISSUES — ABSTRACT  (sections/abstract.tex)
################################################################################

================================================================================
#1  [T2 · Style] [POLISH]  Abstract opens with proposal-meta throat-clearing
================================================================================
Where: Abstract — abstract.tex:4-6
What:  "This research proposal outlines a plan to extend Partially Observable
       Deterministic (POD) planning methods to the domain of Task and Motion
       Planning (TAMP) under partial observability." The reader already knows
       it is a proposal; "outlines a plan to" and "to the domain of" are padding.
Fix:   "This proposal extends Partially Observable Deterministic (POD) planning
       to Task and Motion Planning (TAMP) under partial observability."

================================================================================
#2  [T2 · Style] [POLISH]  "computationally intensive probabilistic models" — mildly inflated
================================================================================
Where: Abstract — abstract.tex:7-8
What:  "Existing TAMP frameworks often assume full observability or rely on
       computationally intensive probabilistic models." Clear, but slightly
       inflated.
Fix:   "Existing TAMP frameworks either assume the robot can see everything, or
       use probabilistic models that are expensive to compute."

================================================================================
#3  [T2 · Style] [POLISH]  Redundant appositive — "serve as the foundation" repeats "belief model"
================================================================================
Where: Abstract — abstract.tex:10-14
What:  "...construct an abstract belief model grounded in Semantic Boxels---
       task-relevant Cuboids that serve as the foundation for belief
       representation---enabling POD planning..." The appositive restates
       "abstract belief model grounded in Semantic Boxels."
Fix:   "...build a belief model from Semantic Boxels — task-relevant cuboids —
       so that POD planning can reason about spatial uncertainty..."

================================================================================
#4  [T2 · Style] [POLISH]  "leveraging its stream mechanism" — inflated verb
================================================================================
Where: Abstract — abstract.tex:15-18
What:  "The proposed methodology formally integrates this semantic abstraction
       with a PDDLStream-based TAMP framework, leveraging its stream mechanism
       to ground symbolic plans in continuous geometric domains." "leveraging"
       = "using"; "continuous geometric domains" = "continuous geometry."
Fix:   "We integrate this abstraction into a PDDLStream-based TAMP framework,
       using its streams to connect symbolic plans to continuous geometry."

================================================================================
#5  [T2 · Style] [POLISH]  Bloated abstract closing sentence
================================================================================
Where: Abstract — abstract.tex:19-21
What:  "...a scalable and conceptually simple framework that simplifies planning
       under spatial uncertainty for robotic systems, enabling them to perform
       complex tasks involving information gathering and robust manipulation in
       partially known environments." Long abstract tail; "simple"/"simplifies"
       repeat; "robotic systems ... enabling them" is stiff.
Fix:   "...a scalable, simple framework that lets a robot plan under spatial
       uncertainty — searching for objects it cannot see and then manipulating
       them." (See also #6 on "robust manipulation".)


################################################################################
#  ISSUES — §1 INTRODUCTION  (sections/introduction.tex)
################################################################################

================================================================================
#8  [T2 · Style] [POLISH]  Generic boilerplate opener of the whole thesis
================================================================================
Where: §1 — introduction.tex:5
What:  "Robotic systems are increasingly envisioned to operate autonomously in
       complex, dynamic, and human-centric environments, performing tasks that
       demand both long-horizon reasoning and intricate physical interaction."
       Interchangeable opener; the adjective pile-up and "intricate physical
       interaction" could front any robotics paper.
Fix:   "We want robots that can do everyday tasks on their own — fetch an
       object, clear a table — which needs both multi-step reasoning and
       careful physical manipulation."

================================================================================
#9  [T2 · Style] [POLISH]  "has emerged as a critical area of research"
================================================================================
Where: §1 — introduction.tex:5
What:  "To enable such capabilities, Task and Motion Planning (TAMP) has emerged
       as a critical area of research." Stock academic-ese; signals importance
       but adds no content.
Fix:   "Task and Motion Planning (TAMP) studies how to do exactly this."

================================================================================
#10  [T2 · Style] [POLISH]  "addresses the fundamental challenge of connecting"
================================================================================
Where: §1 — introduction.tex:6
What:  "TAMP addresses the fundamental challenge of connecting high-level
       symbolic task specifications (e.g., \"fetch the blue cup from the
       kitchen\") with the low-level, continuous motions a robot must perform."
       "addresses the fundamental challenge of connecting" is throat-clearing.
Fix:   "TAMP connects a high-level goal (e.g., \"fetch the blue cup from the
       kitchen\") to the actual motions the robot must perform to achieve it."

================================================================================
#11  [T2 · Style] [POLISH]  "the physical realities of robot operation"
================================================================================
Where: §1 — introduction.tex:9
What:  "Due to necessary abstractions, there exists a significant gap between
       these abstract plans and the physical realities of robot operation."
       Weak existential "there exists"; "physical realities" is inflated.
Fix:   "Because the symbolic plan ignores geometry, it can call for actions the
       robot cannot physically carry out."

================================================================================
#12  [T2 · Style] [POLISH]  PDDLStream "has become a widely used framework"
================================================================================
Where: §1 — introduction.tex:13
What:  "To this end, various methods have been developed, among which
       PDDLStream ... has become a widely used framework." Formulaic lead-in
       that delays naming PDDLStream.
Fix:   "One widely used framework for this is PDDLStream."

================================================================================
#13  [T2 · Style] [POLISH]  "strong assumptions that limit its applicability in realistic, real-world settings"
================================================================================
Where: §1 — introduction.tex:16
What:  "Despite its effectiveness, the original PDDLStream framework assumes
       full observability and deterministic action outcomes—strong assumptions
       that limit its applicability in realistic, real-world settings."
       Roundabout and redundant ("realistic, real-world").
Fix:   "But the original PDDLStream assumes the robot can see everything and
       that actions always succeed — assumptions that rarely hold in practice."

================================================================================
#14  [T2 · Style] [POLISH]  "necessitating active information gathering as part of task execution"
================================================================================
Where: §1 — introduction.tex:16
What:  "...may be initially unknown, necessitating active information gathering
       as part of task execution." Stiff nominalized academic-ese.
Fix:   "...may be unknown at the start, so the robot has to actively look for it
       while carrying out the task."

================================================================================
#15  [T2 · Style] [POLISH]  "Bridging this gap demands specialized mechanisms"
================================================================================
Where: §1 — introduction.tex:11-12
What:  "Bridging this gap demands specialized mechanisms to ground symbolic
       plans in continuous state and action spaces." Impersonal academic-ese;
       largely restates the preceding paragraph.
Fix:   "Closing this gap needs a way to fill in the geometric details of a
       symbolic plan." (Or delete — the next paragraph introduces PDDLStream as
       exactly that mechanism.)

================================================================================
#17  [T2 · Style] [POLISH]  "enhancing robot autonomy and robustness in complex, partially known environments"
================================================================================
Where: §1 — introduction.tex:23
What:  "The expected result is a framework that simplifies planning under
       spatial uncertainty, enhancing robot autonomy and robustness in complex,
       partially known environments." The tail clause is interchangeable
       boilerplate.
Fix:   "The result should be a framework that makes planning under spatial
       uncertainty simpler and more reliable." (Drop the boilerplate tail.)

================================================================================
#18  [T2 · Style] [POLISH]  "This is done by introducing" — throat-clearing connector
================================================================================
Where: §1 — introduction.tex:21
What:  "Here, we proposes a novel approach to discretizing the workspace based
       on perceived objects and the occluded regions they form. This is done by
       introducing Semantic Boxels..." "This is done by introducing" is a
       roundabout connector between two sentences that should be one.
Fix:   "We propose discretizing the workspace around the objects the robot
       detects and the regions they occlude. The unit of this discretization is
       the Semantic Boxel: a task-relevant cuboid the robot uses to represent
       belief." (See also #19, #20, #22.)

================================================================================
#19  [T2 · Style] [POLISH]  Semantic Boxels definition restated three times in one paragraph
================================================================================
Where: §1 — introduction.tex:21, 23
What:  The same definition — task-relevant adaptive cuboids built from perceived
       objects and their occlusions — is given three times within ~10 lines
       ("adaptively generated Cuboids" / "dynamically created based on perceived
       objects ... and the occluded regions they form" / "reason over abstract
       beliefs about which Boxels objects might occupy").
Fix:   Define Semantic Boxels once, in full, then refer to them by name. Cut the
       redundant restatements.

================================================================================
#20  [T2 · Style] [POLISH]  "strike a balance between expressivity and computational efficiency"
================================================================================
Where: §1 — introduction.tex:18
What:  "Effective solutions must therefore strike a balance between expressivity
       and computational efficiency in belief representation and planning."
       Generic trade-off cliché.
Fix:   "A useful belief representation must therefore be detailed enough to be
       expressive, yet small enough to plan with quickly."

================================================================================
#21  [T2 · Style] [POLISH]  "explosion in the size of the belief space" — redundant clause
================================================================================
Where: §1 — introduction.tex:18
What:  "Naive representations—such as uniform voxelizations of 3D space—can
       quickly become computationally intractable, leading to an explosion in
       the size of the belief space." The explosion IS the intractability — the
       clause says the same thing twice. (The uniform-voxelization contrast is
       also softer than implied: the built semantic side also incurs fact-count
       growth — see THESIS_NOTES §9, §14.)
Fix:   "Naive representations — such as a uniform voxel grid over 3D space —
       make the belief space blow up in size and quickly become impractical to
       plan with."

================================================================================
#24  [T2 · Over-claim] [THESIS]  "long-horizon reasoning" / "complex tasks" vs the tabletop scenario
================================================================================
Where: §1 introduction.tex:5, 23; Abstract abstract.tex:21
What:  §1 opens with robots "performing tasks that demand ... long-horizon
       reasoning" and promises the system performs "complex tasks." The
       evaluated tasks are single-target hidden-object retrieval and
       stacking on one tabletop — short-horizon relative to the framing.
Fix:   State the thesis's own scope early: "This thesis demonstrates the
       approach on tabletop hidden-object retrieval and stacking; the
       partial-observability mechanism is the contribution, and longer task
       horizons are a natural extension."
Refs:  THESIS_NOTES §9

================================================================================
#27  [T2 · Over-claim] [THESIS]  "structured 3D model" vs the string-based planner state
================================================================================
Where: §1 introduction.tex:23; §3 related_work.tex:22
What:  The proposal presents the planner as reasoning over a "structured 3D
       model" / geometric belief. The PDDL planner builds its initial state
       from string dictionaries (known_empty_shadows: List[str],
       moved_occluders: Dict[str,str]); it reasons over string boxel IDs that
       proxy for volumes (THESIS_NOTES §11, "the String Cheat").
Fix:   Clarify that the planner reasons over symbolic boxel identifiers that
       abstract the 3D geometry held in the boxel registry; streams ground the
       symbols, but the symbolic state itself is discrete.
Refs:  THESIS_NOTES §11

================================================================================
#29  [T2 · Deviation] [THESIS]  "conceptually simple" contradicted by the documented hacks
================================================================================
Where: §1 introduction.tex:23; §5.4 evaluation.tex:34
What:  The proposal repeatedly calls the framework "conceptually simple" /
       claims it "simplifies planning." THESIS_NOTES catalogs 21 accepted
       simplifications that are mostly hacks: string-based state (§11),
       hardcoded magic numbers overfit to one table/robot (§13), the 3-strike
       give-up (§18), the hardcoded post-action lift (§19).
Fix:   Qualify "conceptually simple" to mean the boxel representation and the
       K-literal abstraction specifically, and add a forward reference to a
       "Limitations / Accepted Simplifications" section. Do not imply the
       implementation is simple.
Refs:  THESIS_NOTES §6, §11, §13, §18, §19


################################################################################
#  ISSUES — §2 BACKGROUND  (sections/background.tex)
################################################################################

================================================================================
#31  [T2 · Style] [POLISH]  §2 chapter intro is a contents-list filler sentence
================================================================================
Where: §2 — background.tex:5
What:  "This chapter covers the foundational concepts in AI planning, state
       representation, reasoning under uncertainty, and the relevant frameworks
       used in this thesis." Restates the subsection headings; no information.
Fix:   Delete it, or orient the reader: "This chapter builds up the pieces the
       thesis depends on, ending with PDDLStream and how 3D space is represented
       for planning."

================================================================================
#32  [T2 · Style] [POLISH]  "is concerned with the autonomous generation of"
================================================================================
Where: §2.1 — background.tex:8
What:  "Artificial Intelligence (AI) planning is concerned with the autonomous
       generation of a sequence of actions, or a plan, to achieve a specified
       goal from a given initial state." Nominalized, roundabout.
Fix:   "AI planning produces a sequence of actions — a plan — that gets from a
       given initial state to a specified goal."

================================================================================
#33  [T3 · Style] [POLISH]  "Conceptually," — empty lead word
================================================================================
Where: §2.1.1 — background.tex:11
What:  "Conceptually, a state-space model explicitly defines all possible
       configurations of the world..." The lead word adds nothing.
Fix:   "A state-space model defines every possible configuration of the world
       and how actions move between configurations."

================================================================================
#34  [T2 · Scientific] [NOW]  STRIPS prose under-describes the stack action's delete-list
================================================================================
Where: §2.1.1 — background.tex:51-60
What:  The :action stack effect lists both (not (clear ?obj2)) and (clear
       ?obj1); the schema itself is consistent with blocksworld semantics. But
       the prose below says only "(not (holding ?obj1)) is part of the
       delete-list, and (on ?obj1 ?obj2) is part of the add-list" — it omits
       that (not (clear ?obj2)) is ALSO a delete-list literal and that (clear
       ?obj1) and (hand-empty) are add-list literals.
Fix:   Expand the prose: delete-list = {(holding ?obj1), (clear ?obj2)};
       add-list = {(on ?obj1 ?obj2), (hand-empty), (clear ?obj1)}.

================================================================================
#35  [T3 · Scientific] [NOW]  Inconsistent predicate name: hand-empty vs handempty
================================================================================
Where: §2.1.1 background.tex:29, 55; §4.4.1 approach.tex:70
What:  §2.1.1 uses "(hand-empty)" (background.tex:29, 55); §4.4.1's fluent
       listing uses "(handempty)" (approach.tex:70). In PDDL these are two
       different predicates.
Fix:   Pick one spelling (the code uses "handempty") and use it everywhere.

================================================================================
#36  [T2 · Style] [POLISH]  "It is important to distinguish"
================================================================================
Where: §2.2.2 — background.tex:94
What:  "It is important to distinguish POD planning from Partially Observable
       Markov Decision Processes (POMDPs) planning, particularly as our approach
       will be compared with existing POMDP-based TAMP solutions." Stock
       academic frame.
Fix:   "POD planning differs from planning with Partially Observable Markov
       Decision Processes (POMDPs) — a distinction that matters because we later
       compare our approach to POMDP-based TAMP."

================================================================================
#37  [T2 · Style] [POLISH]  "inherent stochasticity of well-modeled actions"
================================================================================
Where: §2.2.2 — background.tex:94
What:  One very long sentence ending "...rather than inherent stochasticity of
       well-modeled actions." Dense, ornate phrasing for a simple idea.
Fix:   Split it: "POD planning assumes outcomes and observations are
       deterministic but unknown. This makes it more tractable than POMDPs, and
       it fits robotic problems where the uncertainty comes from not knowing the
       world rather than from actions behaving randomly."

================================================================================
#38  [T2 · Scientific] [NOW]  K-literal "possibly true" conflated with "uncertain"
================================================================================
Where: §2.2.1 — background.tex:86-91
What:  "If neither holds, p is uncertain. p is \"possibly true\" if K(¬p) is
       false." The definition is technically correct but stated so it blurs two
       distinct epistemic states: "possibly true" (¬K(¬p), which also includes
       p known true) is broader than "uncertain" (¬K(p) ∧ ¬K(¬p)).
Fix:   "p is uncertain if neither K(p) nor K(¬p) holds. p is possibly true if
       K(¬p) is false — note this also includes the case where p is known true."

================================================================================
#39  [T2 · Scientific] [NOW]  Overstated: POD problems "can often be compiled into classical planning"
================================================================================
Where: §2.2.1 — background.tex:91
What:  "POD problems can often be compiled into classical planning problems
       using these K-literals..." Omits key caveats: sound/complete polynomial
       compilations exist only for bounded-width problems; general contingent
       planning compiles to planning with sensing/branching or needs online
       replanning.
Fix:   "Under suitable conditions (e.g., bounded-width problems), POD problems
       can be compiled into classical planning using K-literals, or solved by
       classical replanning [bonet2011planning, bonet2014flexible]; in general,
       sensing introduces branching that requires contingent planning or online
       replanning."

================================================================================
#40  [T2 · Scientific] [NOW]  State-space-model tuple inconsistent between §2.1.1 and §4.3
================================================================================
Where: §2.1.1 background.tex:13; §4.3 approach.tex:36-37
What:  §2.1.1 defines the model as a six-tuple <S, s0, SG, Act, A, f> with a
       separate applicability function A. §4.3 defines M = <S, S0, SG, A, f, O>
       with no applicability function and A as the action set. A reader cannot
       tell whether applicability was dropped deliberately. The symbol S/script-S
       is also overloaded (whole model in §2.1.1, state set in §4.3); f is
       reused for two different transition functions.
Fix:   Make the two tuples consistent (include applicability in M, or note it is
       folded into action preconditions). Rename the §2.1.1 model symbol to
       avoid clashing with the state set.

================================================================================
#41  [T2 · Style] [POLISH]  "is why TAMP is an active research area"
================================================================================
Where: §2.3 — background.tex:98
What:  "This challenge of combining high-level logic with real-world geometry is
       why TAMP is an active research area, with frameworks like PDDLStream
       being developed to bridge the gap." Stock importance-claim; limp passive
       trailer.
Fix:   "Combining high-level logic with real-world geometry is the central
       difficulty of TAMP, and frameworks like PDDLStream exist to bridge it."

================================================================================
#42  [T2 · Style] [POLISH]  "prominent and flexible TAMP framework"
================================================================================
Where: §2.3.1 — background.tex:102
What:  "PDDLStream ... is a prominent and flexible TAMP framework designed to
       bridge this symbolic-continuous gap." "prominent and flexible" are
       unearned booster adjectives.
Fix:   "PDDLStream is a TAMP framework built to bridge this symbolic-continuous
       gap."

================================================================================
#43  [T3 · Scientific] [NOW]  PDDLStream example fluent name inconsistency
================================================================================
Where: §2.3.1 — background.tex:113 vs 123
What:  The streams paragraph certifies "(kinematics-sol ?obj ?p ?g ?q)"
       (line 113); the very next workflow paragraph certifies "(KinSolution
       ?obj ?p ?g ?q)" (line 123). Same concept, two names.
Fix:   Use one name consistently in both places.

================================================================================
#44  [T3 · Scientific] [NOW]  Octree definition imprecise about leaves; citation choice
================================================================================
Where: §2.4.1 — background.tex:141
What:  "An Octree is a tree data structure where each internal node has exactly
       eight children." Acceptable but never explicitly says leaf nodes have
       none, and "internal node" is undefined. The generic octree definition is
       cited to hornung2013octomap + riegler2017octnet; the data structure
       predates both by decades.
Fix:   Add "(leaf nodes have none)"; cite a foundational source for the
       definition, or drop the citation for the pure definition and keep
       hornung2013octomap for OctoMap specifically.

================================================================================
#45  [T2 · Style] [POLISH]  §2.4 intro — "a critical component is how ... are represented"
================================================================================
Where: §2.4 — background.tex:133
What:  "For robotic agents interacting with the physical world, a critical
       component is how the continuous, often 3D, environment and the objects
       within it are represented." Buries the subject; circles before reaching
       the point.
Fix:   "A robot needs some way to represent the 3D space around it and the
       objects in it."

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

================================================================================
#48  [T2 · Style] [POLISH]  Voxelization lead-in — second sentence restates the first
================================================================================
Where: §2.4.1 — background.tex:136
What:  "Robots operate in continuous spaces, but many planning algorithms ...
       reason over discrete states or abstractions. Therefore, methods to
       discretize or abstract continuous spatial information are essential."
       The second sentence restates the first and ends in a content-free "are
       essential."
Fix:   "Robots operate in continuous space, but symbolic planners reason over
       discrete states — so the continuous space has to be discretized somehow."


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
#55  [T1 · Deviation] [THESIS]  §3 "builds a structured 3D model of the world from sensor data" — contradicts oracle perception
================================================================================
Where: §3.1.3 — related_work.tex:22
What:  Contrasting with Zhao et al. (VLM perception): "Our method, in contrast,
       builds a structured 3D model of the world from sensor data." The built
       system grounds in simulator ground truth (oracle_detect_objects); the
       depth/point-cloud path is commented out. The claimed advantage over a VLM
       — grounding in real sensor data — is exactly what the build does not do.
Fix:   "Our method builds a structured, object-centric 3D belief representation;
       in the current implementation the object poses are supplied by a
       ground-truth oracle, so the comparison is at the level of representation
       and reasoning, not perception. Integrating a real detector is future
       work." Do not claim "from sensor data."
Refs:  THESIS_NOTES §1, §20

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

================================================================================
#58  [T2 · Style] [POLISH]  §4.1 overview opener buries the point
================================================================================
Where: §4.1 — approach.tex:9
What:  "The main idea of our methodology is to link abstract belief
       representation with continuous geometric reasoning. This is done through
       three key components:" Slow run-up; does not start delivering until word
       eight.
Fix:   "Our methodology links abstract belief representation to continuous
       geometric reasoning through three components:"

================================================================================
#59  [T2 · Style] [POLISH]  §4.1 bullet 3 repeats itself
================================================================================
Where: §4.1 — approach.tex:13
What:  "PDDLStream Integration: A concrete implementation using custom PDDL
       fluents, actions, and streams to realize the formal model within the
       PDDLStream framework. This is done by defining PDDL fluents and actions
       that operate on the belief state over Boxels." The second sentence
       re-lists "PDDL fluents and actions."
Fix:   "PDDLStream Integration: An implementation using custom PDDL fluents,
       actions, and streams that operate on the belief state over Boxels,
       realizing the formal model in PDDLStream."

================================================================================
#60  [T2 · Style] [POLISH]  §4.2 — "To create a spatial abstraction that is both meaningful and scalable"
================================================================================
Where: §4.2 — approach.tex:17
What:  "To create a spatial abstraction that is both meaningful and scalable, we
       propose a process of adaptive semantic discretization." The goal clause
       is generic padding in front of the actual point.
Fix:   "We propose adaptive semantic discretization, a process that generates
       the Boxel abstraction." (See #64 on the word "adaptive".)

================================================================================
#61  [T2 · Style] [POLISH]  §4.2 — Object-Centric Bounding says one thing four times
================================================================================
Where: §4.2 — approach.tex:27
What:  "When an object ... is detected, a dedicated Boxel is generated to be a
       tight bounding box around its perceived pose. This uses the object's
       known 3D model to define the volume. This isolates known objects into
       distinct spatial regions. This is done by generating a cuboid that fully
       contains the object's 3D model." Sentences 1 and 4 both describe
       generating a bounding cuboid.
Fix:   "When an object is detected, we generate a dedicated Boxel: a cuboid that
       tightly bounds the object's known 3D model at its detected pose. This
       isolates each known object in its own spatial region."

================================================================================
#62  [T2 · Style] [POLISH]  §4.2 — "first-class citizens" borrowed jargon + "This is critical"
================================================================================
Where: §4.2 — approach.tex:28
What:  "This is critical as it explicitly represents currently unobservable
       regions, making them first-class citizens for information-gathering
       actions." "This is critical" editorializes; "first-class citizens" is
       borrowed programming jargon.
Fix:   "This explicitly represents regions the robot currently cannot observe,
       so the planner can target them with information-gathering actions."

================================================================================
#63  [T2 · Style] [POLISH]  §4 — "is done through / is done by" passive padding
================================================================================
Where: §4.1 — approach.tex:9, 13
What:  "This is done through three key components:" and "This is done by
       defining PDDL fluents and actions..." Impersonal stock connectors that
       add words without agency.
Fix:   See #58 (line 9) and #59 (line 13) — both remove the connector.

================================================================================
#81  [T3 · Deviation] [THESIS]  §4.2 free-space merge is convex-only — over-segments vs the "task-relevant/scalable" framing
================================================================================
Where: §4.2 — approach.tex:30, 32
What:  §4.2 implies a small set of meaningful task-relevant free-space
       subspaces. CellMerger merges two free cells only when they share an
       exactly aligned face; there is no semantic merge (identical
       observability / blocks_view_at). This leaves more, smaller free Boxels
       than a semantic partition would.
Fix:   Note that free-space merging is convex-only (aligned-face), producing
       more Boxels than a full semantic merge — acceptable for current object
       counts.
Refs:  THESIS_NOTES §7

================================================================================
#86  [T3 · Style] [POLISH]  §4.3 — "drives the belief state"
================================================================================
Where: §4.3 — approach.tex:48
What:  "...a sequence of actions ... that drives the belief state, initially
       b0 = S0, to a belief state bg..." "drives" is a mildly dramatic verb.
Fix:   "...a sequence of actions ... that moves the belief state from b0 = S0 to
       a belief state bg in which every possible state is a goal state..."


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
#  ISSUES — CITATIONS, BIBLIOGRAPHY & LATEX BUILD
################################################################################

================================================================================
#113  [T1 · Citation] [NOW]  references.bib entry [1] (PDDL) is malformed — corporate author mis-parsed  [DONE]
================================================================================
Where: references.bib (aeronautiques1998pddl)
What:  The entry renders the author as "C. Aeronautiques, A. Howe, ...". The
       Google-Scholar mis-parse: "Aeronautiques, Constructions" is the corporate
       author "Constructions Aeronautiques", not a person; "McDermott, ISI Drew"
       absorbs his institution (ISI); "Sri, David Wilkins" absorbs SRI. The
       title has a stray "|"; it is an @article with journal "Technical Report,
       Tech. Rep." — it is actually a tech report.
Fix:   Replace with a clean @techreport entry: authors Ghallab, Howe, Knoblock,
       McDermott, Ram, Veloso, Weld, Wilkins; title "{PDDL} -- The Planning
       Domain Definition Language"; institution "AIPS-98 Planning Competition
       Committee"; number "CVC TR-98-003"; year 1998.

================================================================================
#114  [T2 · Citation] [NOW]  Multiple orphan (uncited) bibliography entries  [DONE]
================================================================================
Where: references.bib (lipovetzky2012width, wang2024open, belle2023epistemic,
       bolander2017gentle, hansen2001lao, coumans2021pybullet)
What:  references.bib has 25 entries; the sections \cite only ~19. The six above
       are never cited and so silently vanish from the printed bibliography.
       Notably hansen2001lao (LAO* search) is directly relevant — TAMPURA uses
       LAO* — a missing-citation opportunity (see #50).
Fix:   Delete genuinely unused entries, or cite them where relevant: add
       \cite{coumans2021pybullet} where PyBullet is named (evaluation.tex:8),
       and consider \cite{hansen2001lao} where TAMPURA / uncertainty-aware
       solvers are discussed.

================================================================================
#115  [T3 · Citation] [NOW]  Malformed bib entries — coumans2021pybullet, belle2023epistemic  [DONE]
================================================================================
Where: references.bib
What:  coumans2021pybullet has a garbled journal field ("ed: PyBullet Quickstart
       Guide. https://docs. google. com/document/u/1/d") and PyBullet is
       currently uncited. belle2023epistemic is typed @misc but carries
       journal/volume/pages/publisher fields — it should be @article.
Fix:   Fix coumans2021pybullet to a clean @misc with howpublished =
       \url{http://pybullet.org}; change belle2023epistemic to @article (only if
       it will be cited — otherwise see #114).

================================================================================
#116  [T3 · Scientific] [NOW]  TAMPURA uses LAO* — flag the missing-citation opportunity  [DONE]
================================================================================
Where: §2.2.2 / §3.1.1 — background.tex:94 / related_work.tex:11
What:  The proposal discusses POMDP-based TAMP and TAMPURA but never cites the
       LAO* solver that TAMPURA's planner relies on. hansen2001lao is already in
       references.bib but uncited (see #114).
Fix:   Cite hansen2001lao where TAMPURA's uncertainty-aware solving is described
       (ties in with #50).
Refs:  #50, #114

================================================================================
#118  [T3 · Build] [NOW]  Octree figure filename contains a space; grammar error in §3  [DONE]
================================================================================
Where: background.tex:144; related_work.tex:12
What:  (a) \includegraphics{../graphics/octmap illustration.png} — the filename
       has a literal space, which risks a file-not-found / wrong-path error
       under lualatex; the explicit ../graphics/ prefix is also redundant given
       \graphicspath. (b) related_work.tex:12: "...which is does not scale well"
       — grammar error (companion to #30's "we proposes").
Fix:   Rename the file to octmap_illustration.png (no space) and reference it
       relying on \graphicspath. Fix the §3 sentence to "...which does not scale
       well to large environments."

================================================================================
#119  [T3 · Build] [NOW]  The committed main.pdf is stale  [DONE]
================================================================================
Where: proposal-template/main.pdf
What:  The committed PDF shows the citation "[bai2025learning]" as raw
       unresolved text on page 10. The key bai2025learning IS present in
       references.bib and the \cite is correct — so the PDF simply predates the
       bib entry. The PDF is out of sync with the sources.
Fix:   Recompile (`latexmk main.tex`, which runs biber + lualatex) so main.pdf
       matches the current sources, and commit the regenerated PDF. Recompiling
       is also the verification step for every fix in this audit.


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
#123  [Structural] [THESIS]  No "Limitations / Accepted Simplifications" section  [DONE]
================================================================================
Where: new section (end of Approach/Implementation, or before the Conclusion)
What:  The audit repeatedly forward-references a limitations section that does
       not exist: #29 says "add a forward reference to a 'Limitations /
       Accepted Simplifications' section"; #6, #26, #69 say "add an honest
       limitations note" / "disclose". notes/THESIS_NOTES.md catalogs 21
       accepted simplifications whose stated purpose is to be "acknowledged and
       discussed in the thesis" — and not one has an assigned home.
Fix:   Add a Limitations / Accepted Simplifications section. Give every
       THESIS_NOTES.md item (§1-§21) a home — here, or in the relevant chapter
       with a cross-reference. This section is the target of the "disclose" /
       "limitations note" fixes in #6 #7 #22 #26 #28 #29 #54 #55 #66 #69 #73
       #79 #81.
Refs:  notes/THESIS_NOTES.md §1-§21; #6 #7 #22 #26 #28 #29 #54 #55 #66 #69 #73 #79 #81

================================================================================
#124  [Structural] [THESIS]  No real "Future Work" section  [DONE]
================================================================================
Where: §5.4 evaluation.tex:36; new section
What:  §5.4's only future-work sentence is generic ("extending the variety of
       semantic information used for discretization and exploring more complex,
       multi-robot planning scenarios") and does not match the project's actual
       deferred items.
Fix:   Add a Future Work section enumerating the real deferred items: recursive
       free-space / in-partition object discovery (THESIS_NOTES §20; #23 #65);
       a learned perception detector replacing the oracle (#22 #55 #89); a
       robot-mounted sensor and the sensing-config stream (THESIS_NOTES §3;
       #25 #70); the dense-visibility ray lattice (THESIS_NOTES §14);
       atom-regrounding to replace the 3-strike give-up (THESIS_NOTES §18;
       #26); and generalizing the hardcoded geometric constants (THESIS_NOTES
       §13; #56).
Refs:  THESIS_NOTES §3 §13 §14 §18 §20; #22 #23 #25 #26 #55 #56 #65 #70 #89

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
#129  [Build] [THESIS]  Top-level units are \section, not \chapter
================================================================================
Where: main.tex; all sections/*.tex
What:  main.tex \input{}s files whose top-level unit is \section (Introduction,
       Background, ...). The labels already assume chapters —
       \label{chap:methodology}, \label{chap:evaluation}. A thesis uses
       \chapter, which needs a chapter-bearing document class (report,
       scrreprt, or the RWTH thesis class).
Fix:   Switch to a document class with \chapter; convert each top-level
       \section to \chapter and demote the nested headings one level. Confirm
       the RWTH thesis template's intended class. Recompile and verify every
       \cref / \ref still resolves.
Refs:  #117 #130

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
#131  [T3 · Build] [NOW]  amssymb "already defined" errors — every build exits 12
================================================================================
Where: resources/preamble.tex (amssymb load); whole-document build
What:  latexmk / LuaLaTeX reports "! LaTeX Error: Command \eth already defined"
       (also \smallsetminus, \digamma, \backepsilon) — amssymb redefines four
       symbols a previously-loaded package already provides. The errors are
       non-fatal (LuaLaTeX continues; main.pdf builds, 20 pages), but every
       build then exits 12, masking any genuine error behind the same code.
Fix:   Find the package that already defines those symbols and resolve the
       clash — drop amssymb if redundant, or fix the load order — so the build
       exits 0.

================================================================================
#132  [T2 · Style] [POLISH]  §3 opens casually — "Solving TAMP problems is hard"
================================================================================
Where: §3 related_work.tex:5
What:  §3 opens "Solving TAMP problems is hard, especially when a robot only
       has partial information." Too colloquial for a thesis Related Work
       opener.
Fix:   Recast in a measured register, e.g. "Integrating task and motion
       planning with partial observability is challenging..." — plain and
       direct, not inflated.

================================================================================
#134  [T3 · Style] [NOW]  §4.2 Figure 2 caption says "Voxelization" not "Discretization"
================================================================================
Where: §4.2 Figure 2 caption — approach.tex:21
What:  The caption titles the figure "Adaptive Semantic Voxelization Process",
       while §4.2 names the process "Adaptive Semantic Discretization" and the
       component is built around Boxels (graphic file Boxelization.png, label
       fig:boxelization). Same term inconsistency as #133, which fixed only the
       §1 roadmap (introduction.tex:24) and did not reach this caption.
Fix:   Change "Voxelization" to "Discretization" in the Figure 2 caption.


================================================================================
SUMMARY BY TIER  (updated 2026-05-17)
================================================================================

Numbers are filing order, not priority. Work T0 -> T1 -> T2 -> T3.

TIER 0 — factual / citation errors (1):
  #112  Critical Regions / RBVD attributed to the wrong paper.

TIER 1 — major proposal-vs-implementation deviations (20):
  #6    "robust manipulation" — friction-free weld + collision-blind execution.
  #22   "perceived objects" misrepresents a ground-truth oracle.
  #26   §1 implies a sound belief search; build has a 3-strike false-negative.
  #55   §3 "structured 3D model from sensor data" contradicts oracle perception.
  #56   §3 "applied to new environments without retraining" overstates generality.
  #65   §4.2 step 3 "Recursive Partitioning" is not implemented.
  #66   Boxel generation is plain Python, not "PDDLStream procedures" (undisclosed).
  #67   §4.4.1 Listing 1 PDDL fluent names do not exist in the domain.
  #68   §4.4.2 sense action name/signature do not match the domain.
  #69   §4.4.2 conditional found/not_found sense effects are not implemented.
  #70   §4.4 sensing streams do not exist.
  #71   §4.4.2 Listing 2 claims an inference the formalism does not provide.
  #72   §4.4.2 puts stream_* calls inside :precondition (modeling error).
  #73   §4.3 formal element O (sensor model) is not a planner component.
  #87   §5.3 "Fixed Semantic Regions" baseline does not exist (killed).
  #88   §5.3 TAMPURA baseline is published numbers only, not a re-implementation.
  #89   §5.1 names Bayes3D for perception — integrated nowhere.
  #90   §5.2 "Plan Quality / Cost" metric is never logged or plotted.
  #104  §5.4 conclusion is written as a finished paper ("As demonstrated").
  #113  references.bib entry [1] (PDDL) is malformed — corporate author mis-parse.

TIER 2 — style, clarity, honest framing (74):
  Abstract:   #1 #2 #3 #4 #5 #7
  §1:         #8 #9 #10 #11 #12 #13 #14 #15 #16 #17 #18 #19 #20 #21 #23 #24 #25
              #27 #28 #29
  §2:         #31 #32 #34 #36 #37 #38 #39 #40 #41 #42 #45 #46 #47 #48
  §3:         #49 #51 #52 #53 #54
  §4:         #57 #58 #59 #60 #61 #62 #63 #64 #74 #84 #85
  §5:         #91 #92 #93 #94 #95 #99 #100 #101 #102 #103 #106 #107 #108 #109
              #110 #111
  Biblio:     #114 #117

TIER 3 — minor: naming, headings, build, polish (25):
  #30 #33 #35 #43 #44 #50 #75 #76 #77 #78 #79 #80 #81 #82 #83 #86 #96 #97 #98
  #105 #115 #116 #118 #119 #120

Total: 120 tiered issues (#1-#120) — 1 T0, 20 T1, 74 T2, 25 T3.
Plus 10 untiered thesis-conversion issues (#121-#130) — see SUMMARY BY
DISPOSITION below.

NEEDS VERIFICATION before fixing:
  #74   Confirm the M = <S,S0,SG,A,f,O> tuple against Bonet & Geffner (2014).
  #112  Confirm the Critical Regions origin (Molina et al., "Learn and Link").


================================================================================
SUMMARY BY DISPOSITION  (added 2026-05-17)
================================================================================

The proposal-to-thesis axis. Tiers (above) grade severity; disposition says
why a fix exists. If the goal is specifically the thesis upgrade, work the
THESIS group and #121-#130 first; the POLISH group can wait, and the NOW group
is independent quick wins.

THESIS-CONVERSION — structural; the upgrade cannot happen without these (10):
  #121 #122 #123 #124 #125 #126 #127 #128 #129 #130

THESIS — reconcile the text with the built system / report real results (45):
  #6 #7 #22 #23 #24 #25 #26 #27 #28 #29 #54 #55 #56 #64 #65 #66 #67 #68 #69
  #70 #71 #72 #73 #75 #76 #77 #78 #79 #80 #81 #82 #83 #87 #88 #89 #90 #91 #92
  #93 #94 #95 #96 #97 #98 #104

NOW — correctness errors, independent of the upgrade (20):
  #30 #34 #35 #38 #39 #40 #43 #44 #50 #74 #105 #112 #113 #114 #115 #116 #117
  #118 #119 #120

POLISH — prose quality, not upgrade-specific; lowest upgrade priority (55):
  #1 #2 #3 #4 #5 #8 #9 #10 #11 #12 #13 #14 #15 #16 #17 #18 #19 #20 #21 #31 #32
  #33 #36 #37 #41 #42 #45 #46 #47 #48 #49 #51 #52 #53 #57 #58 #59 #60 #61 #62
  #63 #84 #85 #86 #99 #100 #101 #102 #103 #106 #107 #108 #109 #110 #111

Total: 130 issues — 120 audited (#1-#120) + 10 thesis-conversion (#121-#130).


================================================================================
ADDENDUM  (2026-05-18 — audit walkthrough)
================================================================================

Changes after the 2026-05-17 summaries above:
  - #131-#133 added (see "ISSUES — ADDED DURING THE AUDIT WALKTHROUGH"):
    #131 [T3 Build / NOW], #132 [T2 Style / POLISH],
    #133 [T3 Style / NOW, DONE].
  - #120 marked [REJECTED] — user keeps the "Sidd's" naming.
  Current totals: 133 issues = 123 tiered (1 T0, 20 T1, 75 T2, 27 T3)
  + 10 thesis-conversion (#121-#130). Disposition: 10 THESIS-CONVERSION,
  45 THESIS, 22 NOW, 56 POLISH.
