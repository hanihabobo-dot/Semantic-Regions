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

**References**: Archive #56 (dead computation), audit #14 (sparse
visibility check — the oracle itself has limitations).

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

**References**: Audit #4 (remaining work), old #44 (accepted).

---

## 9. No Stacking Goals

The goal is always `('holding', target_name)` — pick up a specific
target object.  There is no stacking, sorting, or multi-object
arrangement goal.

**Thesis framing**: The semantic boxel representation supports
arbitrary spatial goals in principle.  Stacking would require
extending the PDDL domain with `on(?a, ?b)` predicates and
corresponding streams.  This is noted as future work.

**References**: Audit #30 (goal as CLI parameter).

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
