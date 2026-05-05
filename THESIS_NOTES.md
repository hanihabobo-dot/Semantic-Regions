# Thesis Writing Notes — Accepted Simplifications

This file collects all accepted simplifications and design deviations
in the Semantic Boxels codebase that should be acknowledged and
discussed in the thesis.  Each entry references the relevant audit
issue or archive entry for full context.

For resolved issues see `archive/CODEBASE_AUDIT_RESOLVED.txt`.
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

The proposal defines two predicates: `obj_in_Boxel` (K(p)) and
`obj_not_in_Boxel` (K(not p)), with "possibly in" being the absence
of both.  The implementation uses a single `obj_at_boxel_KIF`
predicate: present = "we know", absent = "unknown".

**Thesis framing**: Valid KIF simplification (Bonet & Geffner style).
Equivalent expressiveness for the current scenario.

**References**: Archive PA-3 (accepted deviation).

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

**References**: Resolved archive #4 (post-action re-boxelization /
stale shadow partition accepted 2026-05-03,
`archive/CODEBASE_AUDIT_RESOLVED.txt`), old #44 (accepted).

---

## 9. Primary goal is holding; stack is an optional extension

The default narrative experiments use `('holding', target_name)`.
The codebase also implements `--goal stack` with stack height and
related PDDL `on(?a, ?b)` wiring (see audit #30 and the resolved
implementation debrief).

**Thesis framing**: The core contribution is semantic boxels and
TAMP under partial observability; holding goals are enough to tell
that story.  Stack goals are a shipped extension with known planner
cost regression (#30) and symbolic-vs-physics verification gaps (open
#40), not a prerequisite for the main thesis claim.

**References**: `CODEBASE_AUDIT.txt` #30, #40,
`archive/CODEBASE_AUDIT_RESOLVED.txt` (2026-04-24 stack debrief).

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

## 15. Stack support chain — implicit base today, explicit `on_table` open (#41)

Stack goals are expressed with `(on ?object ?support)` only; the base
cube is **not** named as resting on the table in the goal tuple today
(`build_stack_goal` documents implicit table support).  The domain
comments describe the same convention: objects absent from any `(on ?o ?x)`
fact are treated as table-resting.

Making that constraint **explicit** in the PDDL goal (e.g. `(on_table ?o)`
or a table object) is tracked as **open** `CODEBASE_AUDIT.txt` **#41**
and pairs with the physics verifier in **#40**.

**References**: `CODEBASE_AUDIT.txt` #41, #40; `pddl/domain_pddlstream.pddl`
(~lines 61–65); `test_full_pipeline.py` `build_stack_goal`.

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

**References**: `pddl/domain_pddlstream.pddl` (action cost effects);
commit `6f91d0c`; `CODEBASE_AUDIT.txt` FOR LATER (stack_allowed
fallback).
