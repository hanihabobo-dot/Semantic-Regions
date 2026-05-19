# Thesis Writing Notes — Accepted Simplifications

This file collects all accepted simplifications and design deviations
in the Semantic Boxels codebase that should be acknowledged and
discussed in the thesis.  Each entry references the relevant audit
issue or archive entry for full context.

For resolved issues see `git log --grep="Fix #N"` or `git log --grep="audit: mark #N"`
(the resolved-audit archive was deleted 2026-05-12 (later) — see CODEBASE_AUDIT.txt header).
For deferred issues see `archive/CODEBASE_AUDIT_DEFERRED.txt`.
For open issues see `CODEBASE_AUDIT.txt`.

---

## 1. Oracle Perception (no real sensor detection)

Object detection uses `oracle_detect_objects()` in `boxel_env.py`,
which queries PyBullet's ground-truth body positions and casts rays
from the camera to AABB corners.  No learned detector, no noise model,
no segmentation from RGB/depth images.

The point cloud computation in `get_camera_observation()` is commented
out (unused by any downstream consumer).  RGB and depth images are
rendered for the PyBullet GUI camera panes but not processed.

**Thesis framing**: The contribution is the semantic boxel
representation and TAMP integration, not the perception pipeline.
Oracle perception isolates the planning contribution from perception
noise.  A real perception module could replace `oracle_detect_objects`
without changing the planning architecture.

**References**: Archive #56 (dead computation), archive #14 (deferred
2026-04-28: a 4×4×4 dense AABB ray lattice fixes the sliver-visibility
gap but ~triples per-call planning time on the default scene by
inflating the FastDownward grounded state — kept for the §evaluation
precision/planning-cost study, see thesis section 14 below).

---

## 2. Constraint-Based Grasping (not friction-based)

The robot attaches objects via `p.createConstraint()` (a rigid weld)
rather than simulating friction-based finger contact.  This means
objects cannot slip or be dropped during transport.

**Thesis framing**: Standard simplification in TAMP research.  The
focus is on task-level reasoning (which object to move where), not
grasp stability.  The constraint simulates a "perfect gripper."

**References**: Archive audit #7 part B, `execute_pick()` in
`test_full_pipeline.py`.

---

## 3. Fixed Overhead Camera (not robot-mounted)

Sensing uses a fixed scene camera positioned at `[0.1, -0.8, 0.7]`
looking at `[0.1, 0.0, 0.5]`.  The robot does not need to move to a
sensing configuration — the camera sees the entire table at all times.

The proposal (Section 4.4) described a `stream_find_sensing_config`
that computes a robot pose for sensing.  This is not implemented.

**Thesis framing**: The fixed camera is sufficient for the tabletop
scenario where all shadows are visible from one viewpoint.  A
robot-mounted sensor would be needed for scenarios with occluded
regions not visible from any fixed vantage point.

**References**: Archive PA-4 (accepted deviation), audit #3 (sense
action design).

---

## 4. Single Grasp Type (top-down only)

`sample_grasp()` in `streams.py` generates only top-down grasps with
a fixed orientation (pitch=180 deg) and a single height offset (0.10 m
above the object center).  No lateral, angled, or multi-finger grasps.

**Thesis framing**: Top-down grasping is sufficient for the tabletop
scenario with convex objects.  Grasp diversity is orthogonal to the
semantic boxel contribution.

**References**: Archive PA-6 (accepted deviation), deferred #59/#77.

---

## 5. Optimistic Sensing with Reactive Replanning

The PDDL `sense` action optimistically assumes the target is found.
When execution reveals otherwise (empty shadow or still blocked), the
Python execution loop breaks out of the current plan, updates belief,
and replans.

The proposal (Section 4.4.2) described conditional sensing effects
with branching outcomes.  PDDLStream + FastDownward do not support
contingent planning, so optimistic sensing + replanning is used
instead.

**Thesis framing**: This is a standard pattern in TAMP under partial
observability (Garrett et al., 2020; Kaelbling & Lozano-Perez, 2013).
Functionally equivalent to conditional planning for the uniform-prior
tabletop scenario.

**References**: Archive PA-5, PF-1, resolved #61, domain PDDL
comment block above the sense action.

---

## 6. Know-If Fluent Simplification

The conceptual model (proposal Sections 2.2.1 and 4.3) describes
belief with two K-literals, K(p) and K(not p), with "possibly" being
the absence of both.  The implemented domain collapses these into a
single Know-If fluent `obj_at_boxel_KIF` (present = the value is
known, absent = unknown), alongside `obj_at_boxel` which carries the
value.  Thesis audit #67 rewrote Section 4.5.1 (Listing 1) to the
real predicates and added a sentence disclosing this collapse and its
equivalence to the K-literal pair, so the deviation is now stated in
the thesis rather than silent.

**Thesis framing**: Valid KIF simplification (Bonet & Geffner style).
Equivalent expressiveness for the current scenario.

**References**: Archive PA-3 (accepted deviation); thesis audit #67.

---

## 7. Convex-Only Free-Space Merge

The `CellMerger` in `cell_merger.py` only merges free-space cells
that share an exactly aligned face (same extent on the non-merge
axes).  Full semantic merge (identical `blocks_view_at`, same
observability, back-to-front order) was deferred.

**Thesis framing**: Convex-only merge produces more boxels than a
full semantic merge but is simpler and sufficient for the current
object counts.  The planner handles the extra boxels within
acceptable planning time.

**References**: Deferred #2 (full merge condition),
`archive/CODEBASE_AUDIT_DEFERRED.txt`.

---

## 8. Stale Shadow Geometry After Occluder Relocation

After an occluder is picked up and placed elsewhere, its shadow AABB
still describes the pre-relocation geometry.  Shadow recomputation at
the new position is not implemented.

This is functionally safe because:
- `sense_shadow_raycasting` uses PyBullet body IDs, not AABBs
- The occluder has been physically removed from the shadow region
- The planner replans with updated `blocks_view_at` facts

**Thesis framing**: Accepted simplification.  Full shadow
recomputation would require re-running the camera observation
pipeline, which is a separate future-work item.

**References**: resolved #4 (post-action re-boxelization /
stale shadow partition accepted 2026-05-03 — see git log), old #44 (accepted).

---

## 9. Primary goal is holding; stack and tray-stack are extensions

The default narrative experiments use `('holding', target_name)`.
The codebase also implements `--goal stack` with stack height and
related PDDL `on(?a, ?b)` wiring (see audit #30 and the resolved
implementation debrief).  A third goal mode — `--goal find-and-tray-
stack` (audit #49, requested 2026-05-06 by user + supervisor) — adds
a fixed tray entity to the scene and asks the system to discover
hidden targets via sense and stack them on the tray.  The tray goal
is the natural cross-product of existing capabilities (sense + stack
+ placement on a non-cube support) and is the simplest concrete
instance of the fixed-semantic-region baseline (audit #11).

**Stack goal planner cost is accepted, not optimised**: enabling the
stack feature roughly doubles per-call planning time on holding-goal
runs, traced to the `:conditional-effects` requirement on the pick
action's `forall` clause (audit #30, debrief in commit log —
`git log --grep="Fix #30"`).  A "split-pick" mitigation
was sketched (move the `forall` into a separate `unstack` action,
drop `:conditional-effects`) but **scrapped 2026-05-06 per supervisor
decision** as "not interesting or relevant for the thesis."  The ~2×
slowdown is the accepted cost of having the stack/tray-stack feature.
Audit #30 is therefore [WONTFIX]; the broader planner-perf question
moved to audit #50 (profile-driven redundancy hunt).

**Thesis framing**: The core contribution is semantic boxels and
TAMP under partial observability; holding goals tell that story.
Stack and tray-stack are shipped extensions that give the evaluation
chapter (#9–#13) more goal diversity — particularly the place-down
case which holding alone does not exercise.  The known planner-cost
regression (#30 [WONTFIX]) and symbolic-vs-physics verification gaps
(landed #40, open #48) are disclosed honestly and do not block the
main thesis claim.

**References**: `CODEBASE_AUDIT.txt` #30 [WONTFIX], #40 [DONE], #41,
#48, #49, #50; commit log for the 2026-04-24 stack debrief
(`git log --before=2026-04-25 --after=2026-04-23 --grep="stack"`).

---

## 10. Shadow Blocker Map Not Refreshed After Place

After an occluder is relocated, `compute_shadow_blockers()` should
recompute which objects now block which shadows.  This call is
currently commented out in `test_full_pipeline.py`.

**Thesis framing**: The planner may use stale `blocks_view_at` facts
on replan.  In practice, the occluder that was just moved is recorded
in `belief.occluders_moved`, and the planner emits correct
`obj_at_boxel` facts for the new position.  The stale geometric facts
can cause suboptimal but not incorrect behavior in most cases.

**References**: Audit #24.

---

## 11. String-Based State Representation (The "String Cheat")

The planner and execution loop rely heavily on string matching rather than pure spatial or geometric reasoning. For example, the hidden object scenario setup determines the ground-truth location of the hidden object and stores it as a string ID (`oracle_hidden_shadow`). 

When the robot "senses" a shadow, earlier versions of the code checked `if sensed_shadow_id == oracle_hidden_shadow`. Even with recent fixes, the PDDL planner (`pddlstream_planner.py`) builds its initial state using string dictionaries (`known_empty_shadows: List[str]`, `moved_occluders: Dict[str, str]`) instead of passing 3D bounding boxes or occupancy grids.

**Thesis framing**: This is a simplification to bridge the gap between continuous geometry and discrete symbolic planning. The string IDs act as proxies for the underlying geometric volumes.

**References**: Audit #1, #2 (resolved), and `pddlstream_planner.py` state construction.

---

## 12. Collision-Blind Execution (The Approach Phase)

During the final 10 centimeters of a pick action (the "approach"), the execution layer (`execute_pick` and `execute_place`) uses a local Inverse Kinematics (IK) solver that bypasses the planner's collision checks. 

The planner finds a safe path to a point *above* the object, but the final downward motion does not verify if the approach trajectory intersects with other objects. Additionally, there is a hack (`support_body_ids`) that explicitly ignores the table during pick/place operations because the Panda robot's base overlaps with the table geometry.

**Thesis framing**: This is a common TAMP simplification where the final local approach is assumed to be free of complex obstacles if the pre-grasp pose is valid. Ignoring the table is a PyBullet-specific workaround for the Panda's kinematic setup.

**References**: Audit #1 (resolved), `execution.py` (`execute_pick`), and `robot_utils.py`.

---

## 13. Hardcoded Magic Numbers and Overfitting

The codebase relies on highly specific, hardcoded numbers that overfit the system to this exact table, the Franka Panda robot, and the specific test objects. 

Examples include:
- `_GRASP_Z_OFFSETS = [0.1]`: The robot only grasps exactly 10cm above the object's center.
- `approach_height = 0.10`, `lift_height = 0.25`: Hardcoded execution heights that will fail if objects are taller than expected.
- `min_resolution = 0.035`: The free space octree stops dividing at exactly 3.5cm.
- Fixed camera position (`[0.1, -0.8, 0.7]`) and specific motor forces.

**Thesis framing**: These constants were empirically tuned for the specific evaluation scenario to ensure stable simulation and planning times. Generalizing these parameters (e.g., dynamic grasp sampling based on object geometry) is orthogonal to the core contribution and left as future work.

**References**: Audit #69, #84 (resolved), `streams.py`, `execution.py`, and `boxel_env.py`.

---

## 14. Perception Density vs Planning Cost (Dense Visibility Trade-off)

`oracle_detect_objects()` in `boxel_env.py` currently classifies an
object as visible if **any** of 8 AABB-corner rays from the camera
reaches its body id. This is known to miss sliver-visible occluders
(audit #14, observed 2026-04-03 mission failure).

A drop-in fix using a 4×4×4 = 64-point parametric lattice over each
AABB was implemented and **measurably correct**: previously-missed
occluders re-enter the `BoxelRegistry`, their shadows get computed,
and the planner gains the option to relocate them.

That implementation lives on branch `audit-14-dense-lattice-attempt`
(commit `92b37fc`, pushed to both remotes) but is **not on `main`**.
On the default scene with seed 0 (2026-04-28 measurements):

| variant       | scene found      | plans | avg per-call | per-call (s)                          |
| ------------- | ---------------- | ----- | ------------ | ------------------------------------- |
| 8-corner      | 3 occl / 4 shad  | 1     |  ~9 s        | post-stack baseline, see audit #30    |
| 64-ray, run A | 3 occl / 4 shad  | 5     |  8.90 s      | 9.06, 3.47, 13.21, 11.66, 7.08        |
| 64-ray, run B | 3 occl / 4 shad  | 1     |  8.91 s      | 8.91                                  |
| 64-ray, run C | **6 occl / 6 shad** (dense lattice discovers slivers) | 5 | **12.32 s** | 21.04, 6.55, 9.02, 7.81, 17.19 |

The cost is purely **planner-side**: more visible objects → more
`(Obj ?o)`, `(Shadow ?s)`, `(boxel_fits ?o ?b)`, and
`(blocks_view_at ?s ?o)` facts in the initial state → larger
FastDownward grounding → longer translator + search. The same
mechanism drives the audit #30 stack-goal slowdown (extra `(on ?o ?x)`
groundings), so this is not a perception-specific phenomenon — it is a
recurring "init-state size dominates planning cost" theme.

**Thesis framing** — this is exactly the kind of cross-layer
interaction the semantic boxel approach is meant to expose:

1. **Perception density is a tunable knob** that the experiment
   runner (audit #9) can sweep: `VISIBILITY_GRID_N ∈ {2, 3, 4, 5}`
   plus an upper-bound depth-buffer-segmentation oracle. Report
   (success rate, planning time, # discovered occluders, # init
   facts) per setting.
2. **Cross-baseline relevance**: the uniform-voxelization baseline
   (audit #10) suffers the same fact-count blowup; the
   fixed-semantic-regions baseline (audit #11) does not. Comparing
   the three under varying perception density isolates whether the
   planner's cost comes from the partition strategy or from
   perception completeness.
3. **Honest reporting**: the project does NOT silently accept the
   sliver-blindness on `main`. The fix exists, was measured, and is
   shelved for principled measurement instead of unprincipled
   inclusion. A single sentence in the thesis is enough to disclose
   this; the §evaluation chapter then quantifies the trade-off.

**References**: Branch `audit-14-dense-lattice-attempt` (commit
`92b37fc`), `archive/CODEBASE_AUDIT_DEFERRED.txt` section "#14",
audit #9 (experiment runner), audit #10/#11 (baselines), audit #30
(parallel "init facts dominate planner cost" finding), audit #15
(shadow splitting still affected on main).

---

## 15. Stack support chain — explicit `on_table` predicate (#41 [DONE 2026-05-07])

Stack goals were originally expressed with `(on ?object ?support)`
only; the base cube was **not** named as resting on the table in the
goal tuple, and the domain treated cubes absent from any `(on ?o ?x)`
fact as implicitly table-resting.  That convention admitted floating-
tower interpretations the physics verifier (#40) could not refute.

`(on_table ?o)` is now an explicit domain predicate (pick removes,
place emits; stack untouched — the held cube was already off-table
from the prior pick).  `_build_init` emits `(on_table X)` for every
non-stacked cube, `build_stack_goal` appends `(on_table base)` to
the goal AST, and `_verify_on_table` extends the #40 physics
verifier to the clause.

No longer an accepted simplification — kept here for cross-reference
stability (later sections reference §15+).

**References**: `CODEBASE_AUDIT.txt` #41 [DONE 2026-05-07], #40;
`pddl/domain_pddlstream.pddl` (`on_table` predicate, pick/place
effects); `pddlstream_planner.py` `_build_init`;
`test_full_pipeline.py` `build_stack_goal` / `_verify_on_table`.

---

## 16. Execution collision logs — no automatic replan (#42)

When motion or `execute_pick` / `execute_place` / `execute_stack`
detects collisions, the code may print collision diagnostics and
continue.  The main loop does **not** break out to replan based on a
collision counter; residual physical desync is acknowledged and left
to logging, manual review, and the planned physics-based goal check
(open #40).

**References**: `archive/CODEBASE_AUDIT_DEFERRED.txt` #42.

---

## 17. Action costs: `stack`=2, all others=1

The PDDL domain assigns unit cost 1 to `move` / `pick` / `place` /
`sense` and cost 2 to `stack`.  Without these costs all actions are
free, and the PDDLStream `adaptive` algorithm will select `stack` as a
"rescue" whenever motion planning to a chosen free boxel fails — even
when the goal is `holding` and the user did not request stacking.
Observed in run `2026-05-05_10-25-00`: `place(green_object,
free_004)` failed kinematic feasibility for several IK seeds, and the
planner replaced it with `stack(green_object, orange_object)` rather
than trying another free boxel.

Making `stack` strictly more expensive than `place` (2 > 1) forces the
planner to exhaust place destinations before falling back to stack.
Confirmed in run `2026-05-05_11-05-43`: two consecutive plans both
chose `place` (cost 7.000), no stack rescue.

**Thesis framing**: This is a planner-search bias, not a domain
semantic change.  `stack` remains a legal action whenever the goal
demands it; the cost only resolves ties between functionally
equivalent skeletons.  An alternative — hard-gating `:action stack`
with a `(stack_allowed)` precondition that is set only when the goal
contains an `(on ...)` literal — is recorded under FOR LATER as a
fallback if the cost bias proves insufficient at scale.

**Evaluation knob**: `test_full_pipeline.py --unit-costs` passes
`unit_costs=True` to `pddlstream.algorithms.meta.solve()`, which
overrides the domain's numeric `(increase (total-cost) ...)` effects
and treats every action as cost 1.  The bias and the original
"stack-as-rescue" failure mode both reappear under that flag, which
makes paired runs (`--unit-costs` vs default) the natural way to
quantify how much of the success-rate / plan-shape difference is
attributable to the cost bias rather than to other planner state.
Default is off (domain costs apply), so existing runs are unchanged.

**References**: `pddl/domain_pddlstream.pddl` (action cost effects);
commit `6f91d0c`; `pddlstream_planner.py` `plan(..., unit_costs=...)`;
`run_logger.py` `--unit-costs` argparse flag;
`CODEBASE_AUDIT.txt` FOR LATER (stack_allowed fallback).

---

## 18. Shadow Give-Up After Repeated Still-Blocked (Audit #21 / #47)

When `sense_shadow_raycasting` returns `still_blocked` three times in a
row for the same shadow, the execution loop calls
`belief.mark_sensed(sid, found=False)` and the shadow is treated as
`not_here` for the rest of the run.  The shadow is NEVER directly
observed; the loop concludes from outside that it is unreachable for
the current scene.

This is a **lying-to-progress** simplification accepted to keep the
sense-plan-act loop bounded.  Without it, runs that hit a still_blocked
configuration the planner cannot resolve spin indefinitely on the same
`(move, sense, pick)` skeleton (observed in the reverted attempt on
branch `claude/friendly-chandrasekhar-a27be5`, commit `689169e`,
14+ replans on the same blocked shadow before the user killed the run).

**What the run report says today** (after audit-#21 log fix): the
final FAILED message distinguishes
- shadows actually observed empty (`clear_but_empty` /
  `contains_nontarget` outcomes), from
- shadows given up after repeated `still_blocked` (the lying case).

`exit_reason` remains `"all_searched"` for both cases (no behavior
change), but the printed breakdown is honest.

**Real remedy (deferred out of scope, audit #47)**: the principled
fix would re-ground the planner's view-blocking atoms from current
physics after N `still_blocked` outcomes — re-run
`compute_shadow_blockers` with up-to-date AABBs and sense-grade ray
density and re-emit `blocks_view_at` facts that match the **current**
blockers, not the ones at planning time.  This was tracked as open
audit #47 but **deferred out of scope 2026-05-06 per user decision**:
the log-only band-aid is the accepted level of correctness for the
thesis, and evaluation tooling (#9–#12) filters gave-up cases as
failures rather than masking them as successes.

**Thesis framing**: the partial-observability search is sound only as
long as belief reflects observation.  The 3-strike give-up violates
this invariant for unreachable shadows — disclosed honestly as an
accepted simplification rather than fixed.  The false-not_here only
mis-labels physically unreachable shadows; the run still terminates,
the report distinguishes the two failure modes, and eval treats the
gave-up case as a failure outcome.  In a real deployment the
give-up would be replaced by the atom-regrounding remedy described
above; that work is out of scope for this thesis.

**References**: resolved #21 (log-only band-aid; see
`git log --grep="Fix #21"`), `CODEBASE_AUDIT.txt` #47 [DEFERRED
OUT OF SCOPE 2026-05-06] (real fix abandoned), `belief.py`
`mark_sensed`, `test_full_pipeline.py` sense-handler
still_blocked branch, resolved #78(c) (3-strike behavior
historical context — `git log --grep="#78"`).

---

## 19. Hardcoded post-action lift — workaround for motion-planning fragility (#36)

After the 2026-04-22 execution refactor, none of `execute_pick` /
`execute_place` / `execute_stack` lift the arm before returning.
Every action ends at its contact pose.  The original design intent
was that the next planned `move` action's `plan_motion` would lift
naturally as part of its collision-free trajectory, keeping execution
strictly one-to-one with PDDL actions (no hidden motion the planner
does not see).

In practice the existing motion planner is fragile when the start
config places the EE in contact with a cube — particularly after
`place` (gripper sitting on the just-placed cube) and `stack`
(gripper on top of a freshly stacked column).  The fragility is a
property of the chosen sampling-based motion planner, not of the
TAMP integration; supervisor framing 2026-05-06: "this is not
cheating, it's a workaround for the shotty motion planning."

**Resolution (audit #36)**: a small (~10 cm) hardcoded Z-lift is
added at the END of `execute_place` and `execute_stack`, before
reading `actual_joints` into `final_config`.  The lift IK is seeded
from the contact joints; if it fails it falls through silently to
the contact pose — the surrounding place/stack is never aborted by
the cosmetic lift.  An optional smaller lift in `execute_pick`
(~5 cm) is purely cosmetic for the holding-goal terminate-at-contact
case.

**Why `place` and `stack` matter more than `pick`**: after pick the
next `move`'s plan_motion runs in genuine free space (the cube is
attached to the EE and everything below is what the planner already
saw); after place/stack the EE starts on top of a cube that the
planner now treats as a placement obstacle.  The lift gives that
plan_motion safe headroom.

**Earlier proposal that was DROPPED** (2026-05-06): an alternative
fix would have added `(at_config q_home)` to the holding goal so the
planner chains `pick → move(home)` and the second move's
plan_motion does the lift "for free" — principled and one-to-one
with PDDL.  Skipped per supervisor decision because relying on the
existing motion planner for the second move is exactly the
fragility this workaround is sidestepping.

**Thesis framing**: this is a deliberate, scoped departure from the
"execution one-to-one with PDDL" invariant.  The lift is invisible
to the planner — `final_config` carries the lifted pose forward as
the seed for the next move's plan_motion, so PDDL state remains
consistent.  Acceptable because the lift is along the gravity axis
only (no sideways manoeuvre), produces no PDDL state change, and
its sole purpose is to give the downstream motion planner a
non-pathological start.

**References**: `CODEBASE_AUDIT.txt` #36; `execution.py`
`execute_place` / `execute_stack` / `execute_pick`; #49 (every tray-
goal run terminates in place or stack — this lift directly improves
the tray-goal evaluation experience).

---

## 20. Free-space octree partitioning; mid-run object discovery is future work (#13, audit #65)

§4.2 step 3 ("Recursive Partitioning") describes the free-space
octree.  Starting from one workspace-spanning Boxel, any Boxel that
overlaps an object or occlusion is recursively split into eight
octants down to a minimum size; the resulting free cells are then
merged greedily across shared faces.  This is implemented by
`FreeSpaceGenerator` (octree) and `CellMerger` (greedy merge), and the
whole pipeline is re-run by `reboxelize.py` whenever the scene
changes.  Thesis audit #65 reconciled the proposal text with this;
the earlier wording ("if new objects are found within a partition...
bound the biggest object and define its occluded space") wrongly
implied the octree re-runs object bounding, and was removed.

What the partitioning does *not* do is discover objects: it consumes
a set of objects identified before generation runs and never finds a
previously-unknown object inside a partition.  Letting it reveal a
new object — and recurse to bound it and the occlusion it casts — is
future work.  It would matter for partial-coverage sensors (e.g. a
robot-mounted camera that has to move to see the back of the table)
or objects hidden inside concave geometry (containers, cupboards) not
present in the tabletop scenes.  The semantic-boxel representation
does not preclude it: the registry would gain new object/shadow
boxels mid-run and re-trigger reboxelize.

**Thesis framing**: with a single overhead viewpoint every tabletop
object is observed up front (modulo sliver occluders — see §14), so
no current scene triggers mid-run discovery.  Cited as future work in
the perception chapter, not as a TAMP limitation.

**References**: `CODEBASE_AUDIT.txt` #13; thesis audit #65;
`free_space.py` `FreeSpaceGenerator`, `cell_merger.py` `CellMerger`,
`reboxelize.py`; section 1 (oracle perception) and section 14
(perception density vs planning cost) of this file.

---

## 21. TAMPURA baseline — hardware, planning times, and architectural difference

This section collects the empirical context for comparing Semantic
Boxels against TAMPURA (Curtis et al. 2024, arXiv:2403.10454).
Findings gathered from the paper's experiments section, the project
page (https://aidan-curtis.github.io/tampura.github.io/), and the
two source repositories (the planner core
https://github.com/aidan-curtis/tampura and the environments
https://github.com/aidan-curtis/tampura_environments) on 2026-05-09.

### 21.1 Hardware

**TAMPURA** (paper § Experiments, verbatim):

> "All experiments were run on a single Intel Xeon Gold 6248
>  processor with 9 GB of memory."
> — Curtis et al. 2024, arXiv:2403.10454

The Xeon Gold 6248 is a 20-core / 40-thread Cascade Lake server CPU
(2.5 GHz base, 3.9 GHz boost, ~150 W TDP, released 2019).  No GPU
reported, no parallelism mentioned in Algorithms 2 and 3 (sequential
nested for-loops over indices `I`, `K`, `J`).

**This thesis** (host machine for all Semantic Boxels measurements):

| Component | Spec |
| --- | --- |
| CPU | AMD Ryzen 7 PRO 7730U with Radeon Graphics |
| Cores / threads | 8 cores / 16 threads |
| Base / boost clock | 2.0 GHz / ~4.5 GHz (Zen 3 mobile, 15–28 W TDP, released 2022) |
| RAM | 30.8 GB |
| GPU | AMD Radeon (integrated, 1 GB; not used by PyBullet/PDDLStream) |
| OS | Windows 11 Business 64-bit (kernel 10.0.26200) |
| Python stack | PyBullet + PDDLStream + FastDownward |

**Comparison framing**: TAMPURA's Xeon has ~2.5× our core count
(20 vs 8) and a marginally higher base clock (2.5 vs 2.0 GHz), but
*both systems plan single-threaded*.  PDDLStream's adaptive search
is non-parallel; TAMPURA's planner core is likewise sequential —
verified by inspection of
`tampura/policies/tampura_policy.py`
(https://github.com/aidan-curtis/tampura), which uses `tqdm`-wrapped
sequential loops and contains no occurrence of `multiprocessing`,
`joblib`, `Pool`, `ProcessPool`, `ThreadPool`, `concurrent.futures`,
`parallel`, or `n_jobs`.  This matches the paper's algorithmic
description (Algorithms 2–3 are explicit sequential nested loops
over indices `I`, `K`, `J`).

The operative comparison is therefore per-thread performance:

| Benchmark | Xeon Gold 6248 | Ryzen 7 PRO 7730U | Faster |
| --- | --- | --- | --- |
| Cinebench R20 single-thread | 347 (gadgetversus.com) | ~570 (Zen 3 mobile typical) | Ryzen ~1.6× |
| Cinebench R23 single-thread | ~885 (R20 × 2.55, est.) | ~1 455 (notebookcheck.net) | Ryzen ~1.6× |
| Cinebench R23 multi-thread | ~18 090 (R20 × 2.55, est.) | ~10 095 (notebookcheck.net) | Xeon ~1.8× |
| PassMark CPU Mark | 31 274 (gadgetversus.com) | ~22 500 (cpubenchmark.net, mobile thermals) | Xeon ~1.4× |

Zen 3 mobile (released 2022, ~15 % IPC over Cascade Lake) at a
4.5 GHz boost outperforms the Xeon 6248's 3.9 GHz boost on
single-thread by roughly **60 %**.  Multi-threaded throughput goes
the other way: the Xeon's 20 cores beat our 8 by roughly **80 %**.

Since the operative axis (single-thread, established above) favours
the host machine, **the host is not at a hardware disadvantage on
the relevant axis**.  Memory subsystem differences (Xeon: 6 channels
DDR4-2933, 27.5 MB L3; Ryzen 7730U: 2 channels DDR4-3200, 16 MB L3)
could give the Xeon a 10–20 % edge on memory-bound state-space
search even single-threaded — real but small relative to the wall-
clock differences observed.  Total system RAM is not a constraint
(TAMPURA cites 9 GB; we have 30.8 GB).

Wall-clock differences between the two systems are therefore
attributable to the planner architecture (§ 21.3), not the
hardware.  Cinebench numbers above flagged with "est." are
R20→R23 conversions using the standard ~2.55× ratio; quoted
real measurements are sourced inline.

### 21.2 Planning times

Per-episode planning times reported by TAMPURA (Table II; 20 trials
each; "anytime — planning can be terminated earlier with lower
success rates"):

| Task | Time per episode (s, mean ± std) |
| --- | --- |
| Class Uncertainty | 28 ± 26 |
| Pose Uncertainty | 21 ± 13 |
| Partial Observability | **57 ± 38**  ← closest analogue to our hidden-target / shadow-search setting |
| Physical Uncertainty | 23 ± 7 |
| SLAM (manipulation-free) | 31 ± 11 |
| SLAM (with manipulation) | 129 ± 55 |

Direct quote on the anytime guarantee:

> "All of these algorithms run in an anytime fashion, meaning that
>  planning can be terminated earlier with lower success rates."
> — Curtis et al. 2024, arXiv:2403.10454

**Caveat on demo videos**: project-page demonstrations
(https://aidan-curtis.github.io/tampura.github.io/) appear to be
played at compressed wall-clock; they should not be cited as
real-time evidence.  The numerical 21–129 s/episode range above is
the citable benchmark.

### 21.3 Why TAMPURA's planner is faster — algorithmic, not hardware

TAMPURA's planner pays its geometry-sampling cost **offline** in a
model-learning phase, then plans cheaply over the resulting sparse
MDP.  PDDLStream (this thesis) interleaves stream sampling with
search on every plan call.

Direct quote on the offline learning phase:

> "TAMPURA's approach to constructing ℬ̄_sparse is to repeatedly
>  construct optimistic, deterministic plans which begin in abstract
>  belief state b̄, and reach the goal."
> — Curtis et al. 2024, § V-A

> "The robot calculates an uncertainty and risk aware plan in the
>  sparse MDP it has learned, and executes this plan."
> — Curtis et al. 2024, § IV (Figure 3 caption)

Direct quote on the inner deterministic plan (FastDownward) and the
outer probabilistic plan (LAO*):

> "for i = 1, …, I do … for k = 1, …, K do … τ_k ← FastDownward(M, b̄₀, G)"
> — Algorithm 2 (Learn-Model), lines 7–11

> "TAMPURA uses … LAO* probabilistic planner."
> — Curtis et al. 2024, § IX

| | TAMPURA | Semantic Boxels (this thesis) |
| --- | --- | --- |
| Geometry sampling | Offline, in `Learn-Model` (Alg. 2): J simulations per controller, builds a sparse MDP before execution | Online, every PDDLStream plan call: streams sample inside the planner loop |
| Plan-time engine | LAO* on the *already-learned* sparse MDP — the abstraction is finite and small | PDDLStream adaptive search interleaved with stream sampling |
| Determinized inner loop | FastDownward inside Learn-Model, called K times per learning iteration | FastDownward inside PDDLStream, called every replan |
| Cross-episode model reuse | "No mention" of cross-episode caching in the paper | Same — `_build_init` re-emits all static facts every call (audit #50 candidate fix) |

The asymmetry is *when the geometry cost is paid*, not the search
engine itself (FastDownward is shared by both).  TAMPURA front-loads
the sampling cost; PDDLStream pays it per replan.

### 21.4 Voxel grid resolution comparison

TAMPURA's `find_dice/env.py` (line 8): `GRID_RESOLUTION = 0.015`
(15 mm).  The grid is a **visibility / occupancy belief structure**
— voxels start occupied and flip to free as raycasts confirm
visibility.  Placement itself is continuous SE(3)-pose sampling
(`placement_sample_fn_wrapper` in the same file); there is no
place-grounding lattice.  Other tasks in `tampura_environments` (e.g.
`class_uncertain`) have no `GRID_RESOLUTION` constant at all —
purely continuous-pose, continuous-IK.

Important: the 15 mm number is an **implementation choice in the
codebase**, not a parameter committed to in the paper.  The paper
(§ XII-A1 "Find Die") describes Pick / Place / Look controllers
abstractly without numeric voxel sizes.  Cite as "find_dice/env.py
line 8" rather than "Curtis et al. 2024 reports 15 mm voxels."

Resolutions in this thesis for the same purposes:

| Mechanism | Where | Resolution |
| --- | --- | --- |
| Visibility raycasting (TAMPURA-15-mm analogue) | `execution.py` `sense_shadow_raycasting` — 7×7 grid × 3 z-slices = 147 rays per shadow, spacing adaptive via `np.linspace(min_corner, max_corner, 7)` | ~17 mm for a default-size 10 × 10 × 10 cm shadow (per-shadow AABB linspace, not a global lattice) |
| Semantic free-space octree leaf | `free_space.py` `min_resolution = 0.035` | 35 mm ("half the target object size 0.08 m — fine enough to place") |
| Uniform baseline cell (default) | `boxel_env.py` `cell_size = 0.05`, `uniform_grid.py` | 50 mm |
| Uniform baseline cell (auto-tuned, audit #66 Plan A, commit `ce24e84`) | `test_full_pipeline.main` — `max(visible AABB axis) + 0.01 m` | ~170 mm for the default scene (forced by occluder height; `test_boxel_fits` checks all 3 axes) |

Our visibility raycasting spacing (~17 mm) is at the same scale as
TAMPURA's 15 mm, but the *mechanism* differs (per-shadow linspace vs
global voxel lattice).  Our place-grounding resolutions (35 mm
semantic / 50–170 mm uniform) have no TAMPURA analogue, because
TAMPURA does not discretise placement.

### 21.5 Implications for thesis evaluation

1. **Comparable per-thread hardware**: cite the host CPU spec
   (§ 21.1) so reviewers do not attribute Semantic Boxels' wall-clock
   to a slower machine.  Both systems are single-threaded; the host
   is in the same ballpark on per-thread performance.
2. **Anytime caveat**: when reporting our planner times against the
   21–129 s TAMPURA range, clarify whether either side terminated
   anytime-style or ran to optimal completion.
3. **Architectural comparison is the right axis**: the speed gap is
   "online stream sampling vs offline `Learn-Model`," not Xeon vs
   Ryzen.  Frame the discussion this way in the eval chapter.
4. **No cross-episode caching in either system**: TAMPURA does not
   cache its learned MDP across initial-belief problems (per § 21.3);
   our `_build_init` does not cache static atoms across replans.
   Either system would benefit from cross-replan caching — audit
   #50(a)/(c) and #62(c) propose this fix on our side, mirroring
   TAMPURA's offline-then-online split.

**References**: `CODEBASE_AUDIT.txt` #50, #62, #66 (Plan A landed
2026-05-09 in commit `ce24e84`; Plan C pending on
`audit-64-tampura-binary-grid`); memory entries
`reference_tampura_grid.md` and `reference_tampura_perf.md`;
arXiv:2403.10454 (Curtis et al. 2024); `tampura_environments/`
`find_dice/env.py` lines 8 and ~362–379.
