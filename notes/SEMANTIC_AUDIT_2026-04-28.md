================================================================================
SEMANTIC AUDIT — 2026-04-28
================================================================================
Scope:    Theory drift, planner cheats, hidden state, code smells, semantic
          gaps, and verification gaps in the Semantic Boxels TAMP project.
Method:   Read THESIS_NOTES.md, README.md, faq.html; read pddl/domain_pddlstream.pddl
          and pddl/stream.pddl as the *declared model*; cross-checked against
          pddlstream_planner.py, streams.py, execution.py, boxel_env.py,
          boxel_data.py, robot_utils.py, test_full_pipeline.py, reboxelize.py,
          shadow_calculator.py, free_space.py, cell_merger.py, belief.py.
          Skimmed CODEBASE_AUDIT.txt + archive/{RESOLVED,DEFERRED} so the
          findings below are NEW or refine an under-tracked aspect.
Author:   Audit pass, discovery only — no source edits, no entries added to
          CODEBASE_AUDIT.txt.

The bucket letters match the request brief:

  (a) THEORY DRIFT
  (b) PLANNER CHEATS
  (c) HIDDEN STATE / SIDE-CHANNELS
  (d) CODE SMELLS
  (e) SEMANTIC GAPS
  (f) VERIFICATION GAPS

Priority tiers match CODEBASE_AUDIT.txt:

  TIER 0   correctness bugs that can mask failure or produce false success
  TIER 1   meaningful drift that affects planner soundness or evaluation
  TIER 2   robustness / scalability hygiene
  TIER 3   code quality, doc/code drift, low-impact cleanups

================================================================================
TABLE OF CONTENTS
================================================================================

  S-01  Replan loop drops held object without telling the planner
  S-02  Pick contact target derived from oracle ground-truth, not planner pose
  S-03  Place Z-coordinate silently overridden by physics-derived height
  S-04  Stack-kin stream reads live PyBullet AABB during certification
  S-05  `random` module never seeded — `--seed` does not produce reproducible runs
  S-06  Sense `found_target` outcome does not verify hit lies in shadow AABB
  S-07  Place action has no symmetric `is_object` effect — boxel-type drift mid-plan
  S-08  PDDL comment claims `(clear ?o)` is conditional; init emits it unconditionally
  S-09  `contains_nontarget` outcome — Python invents new boxels mid-plan, no PDDL effect
  S-10  THESIS_NOTES §13 cites magic numbers that no longer exist in code
  S-11  `is_config_collision_free(allow_gripper_collisions=True)` is global, not local-approach
  S-12  Three different visibility ray densities — coarse placement-view gridding
  S-13  `test_boxel_fits` is AABB-extent only — orientation, shape, clearance ignored
  S-14  Pick contact-Z silently clamped above the planner-validated target
  S-15  `release_held_object_in_place` returns success when object name cannot be resolved
  S-16  `_hidden_xy_positions` post-spawn check is a printf, not the documented retry layer
  S-17  `oracle_hidden_shadow` computed for logging only — vestige of the string-cheat era
  S-18  Holding-goal SUCCESS reads from `belief`, never from physics
  S-19  `mark_occluder_moved` called for any placed object — name and gating are misleading
  S-20  `random.shuffle` of a 1-element list — dead code in `sample_grasp`
  S-21  Stack-goal randomisation uses unseeded module RNG — non-reproducible tower selection

  SUMMARY BY PRIORITY

================================================================================
## S-01. Replan loop drops held object without telling the planner
================================================================================
- **bucket:** (c) HIDDEN STATE / SIDE-CHANNEL
- **WHERE:** test_full_pipeline.py:511–540 (replan-loop "release before plan"
  block) → execution.py:193–346 (`release_held_object_in_place`)
- **WHAT:** Whenever the action loop `break`s mid-plan (sense returned
  empty/blocked, IK failure, missing shadow…), the orchestration loop calls
  `release_held_object_in_place` BEFORE the next `planner.plan()`.  The
  routine opens the gripper, removes the grasp constraint, lets physics
  settle, repositions the released body in the registry, and rebuilds
  `shadow_occluder_map` — all without a corresponding PDDL action.  The
  planner's next call sees `(handempty,)` (always emitted by `_build_init`)
  and a "moved" object recorded only as a registry mutation.  The PDDL trace
  jumps from "...pick…" to "(handempty)" with no intervening place.
- **EVIDENCE:**
  ```python
  # test_full_pipeline.py:511
  if held_body_id is not None:
      drop_ok, drop_state = release_held_object_in_place(...)
      ...
  ```
  ```python
  # execution.py:266
  p.removeConstraint(grasp_constraint_id)
  open_gripper(robot_id, gui)
  for _ in range(30 + 30 * (attempt - 1)):
      env.step_simulation()
  ```
  Domain (pddl/domain_pddlstream.pddl) declares only `pick`, `place`, `stack`
  as actions that mutate `(holding ?o) / (handempty)`.  No `release` /
  `drop_in_place` action exists.
- **WHY IT MATTERS:** This is exactly the "Hidden arm motions, gripper
  openings, or constraint manipulations inside dispatcher code that the
  planner does not see" pattern called out in the brief.  Symbolically the
  trace is unsound — the planner's `(handempty)` precondition for the next
  pick is satisfied only because the orchestrator unilaterally restored it.
  For thesis claims about TAMP soundness, this is the largest invisible
  state mutation in the pipeline.
- **SUGGESTED FIX:** Surface the drop as a first-class PDDL action — e.g.
  `(:action drop-in-place ?o ?b)` with effect `(handempty) (obj_at_boxel ?o ?b)
  (not (holding ?o))` — and let the planner emit it when an unrecoverable
  branch is detected.  Alternative: refuse to replan while `holding` is true
  and force the current plan to complete a `place` first (with stricter
  termination).
- **PRIORITY:** TIER 0 (soundness-of-trace; affects every replan that
  follows a partial pick branch)
- **DEPENDENCIES:** Adjacent to CODEBASE_AUDIT.txt #21 (reactive policy
  after still_blocked) and #4 (post-action re-boxelization); independent.

================================================================================
## S-02. Pick contact target derived from oracle ground-truth, not the planner's certified boxel pose
================================================================================
- **bucket:** (b) PLANNER CHEAT
- **WHERE:** execution.py:404–408 (`contact_ee` derivation), and
  test_full_pipeline.py:830–838 (caller's `pick_pos` resolution)
- **WHAT:** `compute_kin_solution` (streams.py:867) certifies a config
  reaching `boxel.center + grasp.position`.  At execution, `execute_pick`
  ignores `boxel.center` and computes the contact frame from
  `obj_pos = env.objects[name].position` (the LIVE PyBullet pose) for X/Y
  and the live AABB for the table-clamped Z.  When the boxel is a SHADOW
  (target was just sensed-found), the planner's certified pose is the
  shadow's centre — but execution drives the arm to the actual hidden
  target's coordinates, which the planner never saw.
- **EVIDENCE:**
  ```python
  # streams.py:867
  target_pos = boxel.center + grasp.position
  ...
  config = self._pybullet_ik(target_pos, ee_orn, seed=seed)
  ```
  ```python
  # execution.py:404
  contact_ee = np.array([
      obj_pos[0] + grasp.position[0],
      obj_pos[1] + grasp.position[1],
      contact_z,
  ])
  ```
  ```python
  # test_full_pipeline.py:835
  pick_pos = np.array(env.objects[target_name].position)   # ground truth
  ```
- **WHY IT MATTERS:** The planner's `kin_solution` and any RRT trajectory
  validated against it presume the arm reaches `boxel.center`.  Execution
  silently substitutes a different point — fine in the common case where
  target ≈ shadow center, but the IK seeded from the planner's `config` is
  no longer guaranteed valid (collision, joint-limit, reach).  More
  importantly, this is the single largest oracle leak at execution time:
  the planner reasons over symbolic shadow IDs, the executor "cheats" with
  the target's live pose.  The "string cheat" is gone; this is its
  geometric residue.
- **SUGGESTED FIX:** At execution, drive to `boxel.center + grasp.position`
  using the planner's `config` directly (no live `obj_pos` substitution).
  If the post-sense knowledge "target is somewhere in shadow_X" is too
  coarse to reach physically, that is the planner's problem — emit a
  finer-grained `obj_at_boxel(target, sub_shadow_X)` after sensing or
  introduce a `compute-pick-from-shadow` stream that samples grasp poses
  from the SHADOW boxel, not from a guessed target centre.
- **PRIORITY:** TIER 0 (planner-vs-executor disagreement; thesis-relevant)
- **DEPENDENCIES:** Related to THESIS_NOTES §11 (string cheat) and audit #4
  (stale shadow geometry); precedes any rigorous claim about partial
  observability.

================================================================================
## S-03. `execute_place` overrides the planner's place Z with a physics-derived release height
================================================================================
- **bucket:** (b) PLANNER CHEAT  /  (e) SEMANTIC GAP
- **WHERE:** execution.py:514–535
- **WHAT:** The planner certifies `kin_solution` against `boxel.center +
  grasp.position`.  `execute_place`'s primary path queries
  `p.getAABB(held_body_id)` and the live EE→object Z offset, then computes
  `target_obj_z = table_z + obj_half_height` and `contact_z = target_obj_z
  - ee_to_obj_z`.  The planner-supplied `place_pos[2]` is unused unless the
  grasp constraint is missing (fallback branch).
- **EVIDENCE:**
  ```python
  # execution.py:519
  obj_half_height = (held_aabb_max[2] - held_aabb_min[2]) / 2.0
  ...
  target_obj_z = table_z + obj_half_height
  contact_z = target_obj_z - ee_to_obj_z
  ```
  Domain comment (pddl/domain_pddlstream.pddl:218–225): "move delivers the
  arm to the compute-kin config (10 cm above destination), place lowers to
  release height, drops the object". The PDDL `kin_solution` is what the
  symbolic planner reasoned with; execution silently picks a different Z.
- **WHY IT MATTERS:** Free boxels with non-table Z (centres lifted off the
  table by octree slabbing) are accepted as placements with no symbolic
  warning that execution will land the object somewhere else.  `on_surface`
  filtering protects most cases (audit #19, archived), but the failure mode
  if a high free-boxel slips through is silent geometric correction with no
  audit trail.
- **SUGGESTED FIX:** Either (a) require `place_pos[2]` to come from the
  planner-validated `kin_solution` and reject free boxels whose centre is
  not approximately `table_z + obj_half_height`; or (b) make execution use
  exactly the planner's contact pose and let the cube settle.  The current
  silent override should at minimum log when its computed Z differs from
  `place_pos[2]` by more than tolerance.
- **PRIORITY:** TIER 1
- **DEPENDENCIES:** None.  Audit #4 (re-boxelization) tangentially related.

================================================================================
## S-04. `compute_stack_kin_solution` reads live PyBullet AABB during stream certification
================================================================================
- **bucket:** (b) PLANNER CHEAT  /  (c) HIDDEN STATE
- **WHERE:** streams.py:957–977
- **WHAT:** The PDDL stream declaration is symbolic:
  ```
  (:stream compute-stack-kin
    :inputs (?o ?on_obj ?g)
    :domain (and (Obj ?o) (Obj ?on_obj) (valid_grasp ?o ?g))
    :outputs (?q)
    :certified (and (Config ?q) (stack_kin ?o ?on_obj ?g ?q)
                    (config_for_boxel ?q ?on_obj)))
  ```
  The Python implementation reads `p.getAABB(on_body_id)` for the support's
  current top, then derives the EE Z target.  The planner therefore relies
  on a stream whose certification depends on the *current physical state*
  at the moment the stream is invoked — not on the symbolic state the
  domain reasons over.
- **EVIDENCE:**
  ```python
  # streams.py:961
  aabb_min, aabb_max = p.getAABB(on_body_id, physicsClientId=self.physics_client)
  top_z = float(aabb_max[2])
  ```
- **WHY IT MATTERS:** This is acknowledged in the docstring ("multi-step
  stacks tolerate per-step settling") and is architecturally similar to
  PF-5's `ignored_body_ids` side-channel.  The drift from "PDDL is the
  symbolic model" is real: a PDDLStream stream is supposed to *certify a
  geometric witness for a symbolic claim*, not to read live world state.
  When the `stack` action chains pick→stack→pick→stack inside a single
  plan, intermediate stack tops have NOT yet settled physically (no
  execution has happened), so the AABB read here is the SUPPORT's pre-plan
  pose — yielding a stack height equal to "support top + held height" for
  every chained stack, instead of the running tower height the planner
  expects.
- **SUGGESTED FIX:** Carry stack height symbolically — emit
  `(stack_top ?obj ?z)` facts in init updated per replan, or use the
  registry's OBJECT-boxel `max_corner` (which test_full_pipeline.py already
  refreshes after each stack at lines 1009–1018) as the source of truth.
  Document either approach explicitly so the PDDL stream contract stays
  symbolic.
- **PRIORITY:** TIER 1 (interacts with the audit-#30 stack-goal slowdown
  story — chained stacks are the hot path)
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #30 (stack-goal perf), #40 (false
  success on toppled towers).

================================================================================
## S-05. `random` module never seeded — `--seed` does not produce reproducible runs
================================================================================
- **bucket:** (f) VERIFICATION GAP  /  (d) CODE SMELL
- **WHERE:**
  - test_full_pipeline.py:43 imports `random`; never `random.seed(args.seed)`.
  - test_full_pipeline.py:304 `random.choice(list(target_to_shadow.keys()))`
  - test_full_pipeline.py:314 `random.choice(all_targets)`
  - test_full_pipeline.py:145–148 `build_stack_goal` `rng = rng or random; rng.shuffle(chosen)`
  - pddlstream_planner.py:517 `random.shuffle(init)`
  - streams.py:408 `random.shuffle(offsets)` (single-element list — see S-20)
  - streams.py:731,805,806 RRT goal-bias and shortcut smoothing draw from `random`
- **WHAT:** The `--seed` flag flows into `np.random.RandomState(seed)` for
  scene generation only.  Module-level `random.*` calls — which control
  target-name selection in the holding scenario, init-fact ordering passed
  to FastDownward, RRT exploration, and stack-goal tower assembly — use
  process-wide global state seeded from the OS clock.
- **EVIDENCE:**
  ```bash
  $ rg "random\.seed|np\.random\.seed" --type py
  (no matches)
  ```
  THESIS_NOTES §14 timing tables advertise "default scene with seed 0"
  measurements; per-call planning times at "seed 0" range from 9.06–17.19 s
  in the same row — the variance is exactly the RRT/init-shuffle non-
  determinism this finding describes.
- **WHY IT MATTERS:** Any reproducibility claim in the thesis (success
  rate at seed K, planning time at seed K) is wrong: rerunning with the
  same `--seed` produces a different target, a different init ordering, a
  different RRT path.  For evaluation infrastructure (audit #9) this is a
  blocker — baselines vs. semantic boxels cannot be compared at fixed seed
  if the seed doesn't reach the random RNG.
- **SUGGESTED FIX:** Add `random.seed(args.seed)` (and ideally
  `np.random.seed(args.seed)`) in `__main__` immediately after parsing
  args, BEFORE any builder runs.  Pass an explicit `random.Random(seed)`
  instance into `BoxelStreams` and `build_stack_goal` so subprocess /
  thread isolation works in batch evaluation.
- **PRIORITY:** TIER 1 (blocks evaluation)
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #9 (eval runner), #14
  (perception-density timing study).

================================================================================
## S-06. Sense `found_target` outcome does not verify the camera ray hit lies INSIDE the shadow AABB
================================================================================
- **bucket:** (e) SEMANTIC GAP  /  (f) VERIFICATION GAP
- **WHERE:** execution.py:67–122 (`sense_shadow_raycasting`)
- **WHAT:** Rays go from `camera_pos` to a 7×7×3 grid of points inside
  `shadow_boxel`'s AABB.  PyBullet returns the FIRST body each ray hits.
  If the target body sits anywhere along the camera→shadow_interior
  segment — including IN FRONT of the shadow — the ray's first hit is the
  target body, and the function returns `("found_target", 0.0, set())`.
  The PDDL effect `(obj_at_boxel ?o ?region)` then asserts the target is
  in `?region` symbolically; the executor sets
  `belief.target_found_in = shadow_id` and the next pick aims at this
  shadow.
- **EVIDENCE:**
  ```python
  # execution.py:101
  for hit_obj_id, _link, _frac, _pos, _normal in results:
      if hit_obj_id == target_pybullet_id:
          return "found_target", 0.0, set()
  ```
  No `if min_corner <= hit_pos <= max_corner` check.
- **WHY IT MATTERS:** Marked **UNSURE — needs human review** because in
  the tabletop scenario shadows are by construction occluded from the
  camera, so a target that would be hit on the LOS is plausibly inside
  the shadow.  But: when a target is partially visible (oracle's 8-corner
  test passes), the SAME target body can be classified visible AND hit on
  rays into a shadow — assigning a wrong shadow as `target_found_in`.
  Compounded by S-02, the executor would then drive to the live target
  position, but the symbolic record of which shadow contained it is
  fabricated.
- **SUGGESTED FIX:** Add `if not aabb_contains(hit_pos, shadow_boxel):
  continue` in the per-ray loop, OR change the ray endpoints to start at
  the shadow's near-face plane rather than the camera origin so any
  target hit must be inside the volume.
- **PRIORITY:** TIER 1 — UNSURE — needs human review
- **DEPENDENCIES:** S-02 amplifies the consequences.

================================================================================
## S-07. PDDL `place` removes `is_free_space` but never asserts the boxel is now occupied
================================================================================
- **bucket:** (e) SEMANTIC GAP
- **WHERE:** pddl/domain_pddlstream.pddl:240–247
- **WHAT:** The `place` action effect is
  ```
  (handempty) (obj_at_boxel ?o ?b) (obj_at_boxel_KIF ?o ?b)
  (not (holding ?o)) (not (is_free_space ?b))
  ```
  After the action, `?b` is neither `is_free_space` nor `is_object`.  No
  predicate exists to mark "this boxel now contains an object" symmetric
  to `is_object` (which is set in init for OBJECT-typed boxels only).  A
  subsequent `place ?o2 ?b` would still need `(is_free_space ?b)`, which
  is correctly false — so this is not a soundness bug in isolation; but
  it does mean any future precondition that relies on "boxel is occupied"
  cannot be expressed with current predicates.
- **EVIDENCE:** Diff init types:
  - `is_free_space ?b`     — used in `place` precondition
  - `is_object ?b`         — used only in init for OBJECT-typed boxels
  - `is_shadow ?b`         — used in derived view_clear
  After `place`, `?b` has none of these three.
- **WHY IT MATTERS:** Replanning re-derives state from the registry, which
  hides the issue.  But within a single multi-step plan (e.g. place-then-
  place-something-else-on-top) the symbolic state cannot represent the
  occupancy.  Affects future extensions for multi-boxel placement
  (audit #6) and stack-on-placed-object scenarios.
- **SUGGESTED FIX:** Add `(is_occupied ?b)` predicate and emit it in
  `place` effect; mirror the asymmetry by NOT removing `is_free_space`
  (or by introducing the dual `is_free_space ↔ ¬is_occupied`).  Encodes
  the "convex-only merge → free regions stay small" trade-off discussed
  in the 2026-03-22 supervisor meeting.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #6 (multi-boxel placement).

================================================================================
## S-08. Domain comment claims `(clear ?o)` is conditional; init emits it unconditionally
================================================================================
- **bucket:** (a) THEORY DRIFT  /  (d) CODE SMELL (comment/code drift)
- **WHERE:** pddl/domain_pddlstream.pddl:67–70 vs pddlstream_planner.py:487–511
- **WHAT:** Domain comment:
  ```
  ;; (clear ?o) ...  Only emitted into init when stackable_objects is
  ;; supplied (i.e. the run is using --goal stack); holding-goal runs
  ;; never see these facts and pay no grounding cost (audit #30 ...)
  ```
  But planner code:
  ```python
  # pddlstream_planner.py:507
  for obj_id in all_obj_ids:
      if obj_id not in supports_with_obj_on_top:
          init.append(('clear', obj_id))
  ```
  The `if stackable_objects is not None` gate (line 513) controls only
  the `(on …)` emission, NOT `(clear …)`.  Code comment at 487–493 admits
  the unconditional emission was added for audit #39, but the *domain
  PDDL* comment at 67–70 still claims the old conditional behaviour.
- **EVIDENCE:** Direct quote from pddl/domain_pddlstream.pddl:67–70 vs
  the unconditional loop in pddlstream_planner.py:507–511.
- **WHY IT MATTERS:** Anyone reading the domain to understand grounding
  cost will believe holding-goal runs avoid `(clear …)` facts — they do
  not.  Affects audit #30 perf-cost narrative.
- **SUGGESTED FIX:** Update the domain PDDL comment to reflect the new
  invariant: "(clear ?o) is emitted for every Obj unconditionally to
  satisfy the pick precondition; the (on ?o ?x) facts remain stack-only".
- **PRIORITY:** TIER 3 (doc/code drift)
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #30 (stack-goal perf debate).

================================================================================
## S-09. `contains_nontarget` outcome — Python invents new boxels mid-plan, no PDDL effect represents it
================================================================================
- **bucket:** (a) THEORY DRIFT  /  (e) SEMANTIC GAP
- **WHERE:** execution.py:118–121 (outcome production), test_full_pipeline.py:693–775
  (handler that mutates the registry)
- **WHAT:** When `sense_shadow_raycasting` returns
  `contains_nontarget`, the orchestrator (a) removes the shadow from the
  registry, (b) creates a fresh OBJECT BoxelData for each newly-visible
  body, (c) runs `shadow_calculator.calculate_shadow_boxel` for each, (d)
  inserts the new SHADOW boxels, and (e) drops `reboxelize_free_space`.
  The PDDL `sense` effect schema only asserts
  `(obj_at_boxel ?o ?region) (obj_at_boxel_KIF ?o ?region) (obj_pose_known ?o)`
  for the symbolic target — it cannot represent "discovered new objects
  and new shadows".  The plan in flight continues with a now-stale
  registry view; the next planner.plan() picks up the new boxels.
- **EVIDENCE:** Compare execution.py:119 `return "contains_nontarget", 0.0,
  detected_bodies` and the resulting registry mutation in
  test_full_pipeline.py:705–775 against pddl/domain_pddlstream.pddl:142–155
  (`sense` action effect).
- **WHY IT MATTERS:** This is a Python-side perception+invention step that
  the symbolic model has no clause for.  Strictly worse than the optimistic
  sensing accepted in PA-5: there, the gap is one boolean (`obj_at_boxel`
  or not).  Here the gap is "registry now has new symbols the planner
  knew nothing about".  Fine architecturally for replan-after-sense, but
  it violates the "PDDL is the symbolic model" framing — sensing has
  side-effects that the model doesn't capture.
- **SUGGESTED FIX:** Document this as an accepted deviation alongside PA-5
  (probably becomes PA-7) since contingent perception expansion is also
  outside PDDLStream's expressive power.  Alternatively, post-sense
  refresh of the registry could be exposed as a no-op PDDL action
  `discover-objects` whose effect is `obj_pose_known(?o)` for new objects
  emitted in init at the next replan.
- **PRIORITY:** TIER 2
- **DEPENDENCIES:** CODEBASE_AUDIT.txt PA-5 (optimistic sensing), THESIS_NOTES §5.

================================================================================
## S-10. THESIS_NOTES §13 cites `approach_height = 0.10` and `lift_height = 0.25` magic numbers that no longer exist
================================================================================
- **bucket:** (d) CODE SMELL (comment/code drift)
- **WHERE:** THESIS_NOTES.md:218–224
- **WHAT:** §13 ("Hardcoded Magic Numbers and Overfitting") lists:
  > `approach_height = 0.10`, `lift_height = 0.25`: Hardcoded execution
  > heights that will fail if objects are taller than expected.
  Both names are absent from the current execution.py and from every other
  .py in the repo (only references are in archive/CODEBASE_AUDIT_RESOLVED.txt
  describing the prior implementation).  The audit-#37/#38 path-A refactor
  removed approach/lift waypoints — execution now lowers from the
  planner's `kin_solution` config and lets the next `move` action lift via
  plan-motion.
- **EVIDENCE:**
  ```bash
  $ rg "approach_height|lift_height" --type py
  (no matches)
  ```
- **WHY IT MATTERS:** A reader of THESIS_NOTES looking for those constants
  in the code to "discuss in the thesis" will not find them and may
  conclude the doc is out of date — which it is.  The accepted-
  simplification list is the canonical thesis-framing reference; stale
  entries undermine the whole document.
- **SUGGESTED FIX:** Update THESIS_NOTES §13 to reflect the post-refactor
  list of magic constants — `_GRASP_Z_OFFSETS = [0.02]` (streams.py:375),
  `_FINGER_TIP_DEPTH = 0.035` (execution.py:399), `min_resolution = 0.035`
  (free_space.py:27), the camera tuple in boxel_env.py:401, and the
  240 N motor force in robot_utils.py:501 — and remove the ghost names.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** None.

================================================================================
## S-11. `is_config_collision_free(allow_gripper_collisions=True)` is global to the pick/place trajectory, not local-approach
================================================================================
- **bucket:** (d) CODE SMELL  /  (e) SEMANTIC GAP
- **WHERE:** streams.py:490–583 (plan_motion), robot_utils.py:102–252
  (`is_config_collision_free`)
- **WHAT:** `is_pick_place = bool(q1.ignored_body_ids or q2.ignored_body_ids)`.
  When True, `allow_gripper_collisions=True` is passed to BOTH endpoint
  validation AND every per-edge collision check along the entire RRT path.
  This means: for the whole pick/place trajectory, gripper-vs-anything
  contacts are silently allowed, even mid-air segments far from the
  destination.  Comment at streams.py:486–489 acknowledges the limitation
  ("A decomposed transit+approach architecture could restrict the ignore
  set to the approach phase only") but the current code applies the relax
  globally.
- **EVIDENCE:**
  ```python
  # streams.py:514
  endpoint_ignored = base_ignored | self.support_body_ids if is_pick_place else base_ignored
  path_ignored     = base_ignored | self.support_body_ids if is_pick_place else base_ignored
  ```
  ```python
  # streams.py:530
  if not is_config_collision_free(self.robot_id, q1.joint_positions,
                                  pc, endpoint_ignored,
                                  allow_gripper_collisions=is_pick_place, ...):
  ```
- **WHY IT MATTERS:** A pick trajectory that swings the gripper through a
  cluttered region adjacent to the pick target gets a free pass on those
  collisions during planning, even when the gripper is nowhere near
  contact.  Trajectory may be reported "collision-free" while smashing
  into nearby objects on the approach.  CODEBASE_AUDIT #42 covers the
  *execution-time* collision logging; this is the *planning-time* dual.
- **SUGGESTED FIX:** Decompose plan_motion into transit + approach phases:
  transit uses strict gripper checking, approach (last K configs) relaxes
  it.  K can be chosen by EE distance to target (< 5 cm = approach).
- **PRIORITY:** TIER 2
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #42 (execution collisions ignored)
  and #97 (deferred — transit/approach decomposition is the canonical fix).

================================================================================
## S-12. Three different visibility ray densities for three "same kind of question"
================================================================================
- **bucket:** (d) CODE SMELL  /  (e) SEMANTIC GAP
- **WHERE:**
  - `oracle_detect_objects`: 8 AABB corners            — boxel_env.py:1206–1219
  - `compute_shadow_blockers`: 5×5 grid at z_mid       — execution.py:166–178
  - `_compute_placement_view_blocks`: 5×5 grid at z_mid — pddlstream_planner.py:304–323
  - `sense_shadow_raycasting`: 7×7 at 3 Z-levels       — execution.py:80–95
- **WHAT:** All four routines answer some flavour of "does X intercept the
  camera→shadow / camera→object line of sight?"  They pick four different
  ray densities with no shared infrastructure or documentation of why
  each density is appropriate.  In particular, `_compute_placement_view_blocks`
  uses a single-Z slice — a free boxel that intersects the LOS only at
  high or low Z is missed, so the planner may treat it as a valid place
  destination that subsequently re-blocks the cleared corridor.
- **EVIDENCE:** Side-by-side counts above; no `# density=` rationale comment
  on any of them; no shared helper.
- **WHY IT MATTERS:** Sets up false-negative blocking facts that audit #5
  (placement re-blocks corridor, archived RESOLVED) thought it had
  solved.  Also creates an asymmetry: sensing is denser than blocker
  detection, so the planner can be told "shadow is unblocked" while
  sensing finds it still blocked — the still_blocked replan handler then
  has to recover from a discrepancy the planner introduced.
- **SUGGESTED FIX:** Lift a single `cast_camera_to_shadow_grid(shadow,
  density)` helper into a shared module (e.g. `perception.py`) and have
  all three call sites use it with explicit density arguments.  Document
  the chosen density per call site.  THESIS_NOTES §14 (perception density
  vs planning cost) is the natural place to argue the trade-off.
- **PRIORITY:** TIER 2
- **DEPENDENCIES:** archive #5 (RESOLVED — placement re-blocking),
  THESIS_NOTES §14, CODEBASE_AUDIT.txt #14 (deferred dense lattice).

================================================================================
## S-13. `test_boxel_fits` is AABB-extent only — orientation, shape, clearance ignored
================================================================================
- **bucket:** (e) SEMANTIC GAP
- **WHERE:** streams.py:341–362
- **WHAT:** `test_boxel_fits(obj_id, boxel_id)` returns
  `np.all(dest_extents >= obj_extents)`, where extents come from
  axis-aligned `max_corner − min_corner`.  No accounting for object
  orientation (cylinders treated as their AABBs), no margin for
  approach clearance, no rotation reasoning.  The PDDL `boxel_fits`
  predicate is then taken as a sufficient placement-fitness gate.
- **EVIDENCE:**
  ```python
  # streams.py:360
  obj_extents  = obj_boxel.max_corner - obj_boxel.min_corner
  dest_extents = dest_boxel.max_corner - dest_boxel.min_corner
  return bool(np.all(dest_extents >= obj_extents))
  ```
- **WHY IT MATTERS:** For the current scene (axis-aligned cubes on a
  table), AABB extents suffice.  Mixed-shape and scalability scenes
  (boxel_env.py:188–343) include cylinders and spheres whose AABB
  fitness ≠ physical fitness in tight regions, especially for the
  cylinder-radius-vs-box-edge case.  Affects audit #6 (multi-boxel
  placement) and the eventual baseline runs (audit #10–#11).
- **SUGGESTED FIX:** When the object is a cylinder/sphere, compare the
  inscribed XY radius against `min(dest_extent_x, dest_extent_y)`.  Add
  a clearance margin (e.g. 5 mm) to absorb post-place settling drift.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #6.

================================================================================
## S-14. `execute_pick` clamps `contact_z` to a finger-tip floor — silently shifts the executed pose above the planner-validated target
================================================================================
- **bucket:** (b) PLANNER CHEAT  /  (e) SEMANTIC GAP
- **WHERE:** execution.py:399–408
- **WHAT:**
  ```python
  _FINGER_TIP_DEPTH = 0.035
  table_z = env.table_surface_height
  min_contact_z = table_z + _FINGER_TIP_DEPTH
  contact_z = max(obj_pos[2], min_contact_z)
  ```
  For a small target whose Z centre is below `table_z + 0.035`, the
  contact pose is silently raised to `min_contact_z`.  The planner
  certified `kin_solution` against `boxel.center + grasp.position` —
  where `boxel.center.z` for a 4-cm cube on the table is `table_z + 0.02`
  (below the floor).  The execution-time IK is seeded from the planner's
  config but solved against a different target.
- **EVIDENCE:** Quoted block above.  Compare with `compute_kin_solution`
  in streams.py:867 — there is no corresponding clamp.
- **WHY IT MATTERS:** Ground-truth target Z is below the executor's floor
  → executor reaches *above* the target → fingers close on air → graceful
  contact via the welded constraint hides the geometric mismatch.  The
  thesis claim "execute_pick lowers seeded from the planner's q to stay
  in the same IK branch" is overstated when the floor is hit.
- **SUGGESTED FIX:** Mirror the clamp into `compute_kin_solution` so the
  planner certifies IK at exactly the contact pose execution will use, OR
  remove the clamp and resize objects (#77 in archive) so the issue does
  not arise.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** archive #77 (graspability vs object size), audit #37/#38
  (resolved — path-A refactor).

================================================================================
## S-15. `release_held_object_in_place` returns success when the held object cannot be name-resolved
================================================================================
- **bucket:** (d) CODE SMELL  /  (f) VERIFICATION GAP
- **WHERE:** execution.py:245–254
- **WHAT:**
  ```python
  dropped_name = body_id_to_name.get(held_body_id)
  if dropped_name is None or dropped_name not in env.objects:
      try:
          if grasp_constraint_id is not None:
              p.removeConstraint(grasp_constraint_id)
      except Exception:
          pass
      return True, state_updates
  ```
  When name resolution fails the routine removes the constraint with a
  swallowed exception and reports success without verifying that the
  object actually separated from the gripper.  None of the verification
  heuristics (EE-to-obj distance, settling speed) run.
- **EVIDENCE:** Quoted block above; compare to the verification path at
  execution.py:281–305.
- **WHY IT MATTERS:** This is a low-probability path (every body created
  by the env is in `body_id_to_name`), but the contract "this returns
  True iff the object physically released" is broken on this branch.  The
  caller takes True at face value and proceeds to plan a fresh pick.
- **SUGGESTED FIX:** Either return False on the unknown-name branch
  (force the caller to abort), or call into the verification block even
  without the name, using the body id only.  Surface the swallowed
  exception via the state_updates dict.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** S-01 (release as side-channel).

================================================================================
## S-16. `_hidden_xy_positions` post-spawn check is a printf, not the documented retry layer
================================================================================
- **bucket:** (d) CODE SMELL (doc/code drift)  /  (f) VERIFICATION GAP
- **WHERE:** boxel_env.py:139–141, 277–280, 738–739; test_full_pipeline.py:185–212
- **WHAT:** `SceneConfig.n_hidden_targets` docstring says: "The retry
  layer in test_full_pipeline.main() verifies the guarantee after spawn
  via oracle_detect_objects() and nudges the seed if it is not met."
  `scalability_scene` docstring repeats: "The retry layer in
  test_full_pipeline.main() verifies the guarantee post-spawn and
  re-seeds if it is not met."  The actual code in main() at
  test_full_pipeline.py:202–212 only emits a `[warn]` line on stderr
  ("Continuing without retry").  No re-seed, no retry.
- **EVIDENCE:** Quotes from boxel_env.py:139–141 vs test_full_pipeline.py:208–212.
- **WHY IT MATTERS:** Anyone configuring `--n-hidden=K` and reading the
  docstring expects a guaranteed K hidden targets.  In practice, when
  placement passes the raycast verification but physics drift later
  exposes a target, the run silently proceeds with fewer hidden targets
  than requested — invalidating any per-run statistics conditioned on K.
- **SUGGESTED FIX:** Either (a) implement the retry-and-reseed loop the
  doc promises, or (b) update both docstrings to "post-spawn check is a
  warning only — physics drift after raycast verification is treated as
  acceptable".
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #14 (deferred dense lattice; same
  visibility consistency theme).

================================================================================
## S-17. `oracle_hidden_shadow` is computed for logging only — vestige of the string-cheat era
================================================================================
- **bucket:** (d) CODE SMELL
- **WHERE:** test_full_pipeline.py:289–308
- **WHAT:** `target_to_shadow` is built via AABB-containment ground truth.
  `oracle_hidden_shadow = target_to_shadow[target_name]` is then used
  ONLY in a print statement.  No planner call references it.  This is the
  remnant of the resolved string-cheat (audit #1, archived) where the
  shadow ID was the search key.
- **EVIDENCE:**
  ```python
  oracle_hidden_shadow = target_to_shadow[target_name]
  print(f"  ORACLE: Actually hidden in {oracle_hidden_shadow} ...")
  print(f"  Robot must search to find it!")
  ```
  After this block, `oracle_hidden_shadow` is not referenced again.
- **WHY IT MATTERS:** Reads as if the planner uses oracle data, even
  though it doesn't.  Confuses readers tracing the partial-observability
  story.  Per CODEBASE policy "commented-out code is preserved" — but
  this isn't dead code, just dead-data that survives only in a log line.
- **SUGGESTED FIX:** Replace the print with `print(f"  Robot must search
  ({len(target_to_shadow)} shadows are valid hiding places)")` and drop
  the variable.  Leaves a comment block describing audit #1's resolution
  for posterity.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** archive #1 (string cheat — resolved).

================================================================================
## S-18. Holding-goal SUCCESS reads from `belief.target_found_in`, never from physics
================================================================================
- **bucket:** (f) VERIFICATION GAP
- **WHERE:** test_full_pipeline.py:1046 (`success = belief.is_target_found()`)
  — and the pipeline's earlier setting of `belief.target_found_in =
  visible_target_locations.get(target_name, "picked")` (line 860)
- **WHAT:** For `--goal holding`, the run reports SUCCESS when
  `belief.is_target_found()` returns True.  That predicate flips on
  *either* a `found_target` sense outcome OR a successful pick of the
  target name (line 859–861 sets `target_found_in` to a sentinel).  No
  call to `p.getConstraintInfo` or `p.getBasePositionAndOrientation`
  verifies the target body is physically welded to the gripper at the
  end of the run.
- **EVIDENCE:**
  ```python
  # test_full_pipeline.py:859
  if pick_obj_name == target_name:
      belief.target_found_in = visible_target_locations.get(
          target_name, "picked")
  ```
  ```python
  # test_full_pipeline.py:1046
  success = belief.is_target_found()
  ```
  No physics check.  This is the holding-goal twin of CODEBASE_AUDIT.txt
  #40 (which only covers stack goals).
- **WHY IT MATTERS:** Same risk profile as #40: a held object that slips,
  a constraint that fails to attach, or a wrong-body pick all report
  SUCCESS as long as the symbolic state flipped.  Inflates evaluation
  success rates (audit #9).
- **SUGGESTED FIX:** At Phase 6, before printing SUCCESS, query the
  grasp constraint's `bodyB` and the target's PyBullet body ID; assert
  match.  For visible-target paths, also assert the target body's height
  is above the table (it's lifted after pick → next move's lift segment).
  Audit #40 fix should be expanded to cover holding goals at the same
  time.
- **PRIORITY:** TIER 0 (false-success channel for the project's primary
  goal kind)
- **DEPENDENCIES:** CODEBASE_AUDIT.txt #40 (stack-goal twin); audit #9
  (eval rates depend on truthful flags).

================================================================================
## S-19. `mark_occluder_moved` called for every placed object — name and gating are misleading
================================================================================
- **bucket:** (d) CODE SMELL
- **WHERE:** test_full_pipeline.py:966–971; belief.py:45–54
- **WHAT:** After a successful `place`, the orchestrator calls
  ```python
  if obj_str in boxel_to_pybullet:
      placed_obj_name = boxel_to_pybullet[obj_str]['name']
      belief.mark_occluder_moved(obj_str, boxel_id_str)
  ```
  but the gating `obj_str in boxel_to_pybullet` is true for every object
  the orchestrator knows about, not just occluders.  The PDDL `place`
  action can be applied to any held object the planner cares to move —
  the name `mark_occluder_moved` predates a more general design.
- **EVIDENCE:** `BeliefState.mark_occluder_moved` docstring says "Mark
  that an occluder has been pushed to a new location"; the call site
  gates by registry membership, not by `is_occluder`.
- **WHY IT MATTERS:** Naming asymmetry confuses replanning logic — the
  belief's `occluders_moved` dict in fact tracks "any object the planner
  has moved", which is closer to "moved_objects".  When the planner emits
  `obj_at_boxel(target, dest)` for a relocated target (hypothetically;
  currently no goal triggers this), the bookkeeping would be wrong only
  semantically, not functionally.
- **SUGGESTED FIX:** Rename to `mark_object_moved` and `objects_moved`
  in BeliefState; update planner docstring (`moved_occluders` parameter)
  in pddlstream_planner.py:121–123 to match.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** None.

================================================================================
## S-20. `random.shuffle` of a 1-element list — dead code in `sample_grasp`
================================================================================
- **bucket:** (d) CODE SMELL (dead code)
- **WHERE:** streams.py:407–408
- **WHAT:**
  ```python
  offsets = list(self._GRASP_Z_OFFSETS)   # [0.02]
  random.shuffle(offsets)
  ```
  `_GRASP_Z_OFFSETS = [0.02]` (line 375) has one element since the
  audit-#37/#38 path-A change.  The `shuffle` is a no-op but consumes
  the global `random` state — interacts with S-05 (unseeded RNG).
- **EVIDENCE:** Quoted block.  Old `_GRASP_Z_OFFSETS = [0.05, 0.10, 0.15]`
  in archive entries justified the shuffle; current value does not.
- **WHY IT MATTERS:** Reads as deliberate randomisation when the loop is
  in fact deterministic.  Misleading; will silently keep working if
  someone restores multiple offsets, but the CODEBASE policy on
  commented-out code argues for explicit annotation.
- **SUGGESTED FIX:** Remove the shuffle and comment why it was kept (or
  remove it entirely with an audit reference).  Restore the shuffle if
  multiple offsets ever come back.
- **PRIORITY:** TIER 3
- **DEPENDENCIES:** S-05.

================================================================================
## S-21. Stack-goal randomisation uses unseeded module RNG — non-reproducible tower selection
================================================================================
- **bucket:** (d) CODE SMELL  /  (f) VERIFICATION GAP
- **WHERE:** test_full_pipeline.py:111–154 (`build_stack_goal`)
- **WHAT:** `rng = rng or random; rng.shuffle(chosen)` — when no `rng`
  is passed (the only call site, line 337, passes none), the module
  `random` is used.  Since `random.seed` is never invoked (S-05), each
  run picks a different subset of `stackable_objects` and a different
  ordering.  The seed printed in `run_config` does not control which
  cubes form the goal tower.
- **EVIDENCE:**
  ```python
  # test_full_pipeline.py:145
  rng = rng or random
  chosen = list(stackable_objects)
  rng.shuffle(chosen)
  chosen = chosen[:stack_height]
  ```
  Caller at test_full_pipeline.py:337 omits the `rng` argument.
- **WHY IT MATTERS:** Same evaluation/reproducibility blocker as S-05,
  scoped to stack goals.  Audit #30's keep-or-kill timing comparison is
  conditioned on "same scene/seed"; if the goal differs across runs at
  fixed seed, the timing comparison is biased by which tower the planner
  has to build.
- **SUGGESTED FIX:** Pass `random.Random(args.seed)` (or seed the global
  `random` once at startup) into `build_stack_goal`.  Same fix as S-05;
  worth flagging separately because the tower selection is the most
  user-visible non-determinism.
- **PRIORITY:** TIER 1 (paired with S-05)
- **DEPENDENCIES:** S-05.

================================================================================
SUMMARY BY PRIORITY
================================================================================

TIER 0 — false-success / soundness-of-trace (3 items)
  S-01  Replan loop drops held object without telling the planner
        (hidden side-channel; PDDL trace becomes unsound after every
        partial-pick branch)
  S-02  Pick contact target derived from oracle ground-truth, not the
        planner's certified boxel pose
        (oracle leak at execution; partial-observability claim
        weakened — geometric residue of the resolved string cheat)
  S-18  Holding-goal SUCCESS reads from belief, never from physics
        (twin of audit #40 for the project's primary goal kind)

TIER 1 — meaningful drift / blocks evaluation (5 items)
  S-03  Place Z-coordinate silently overridden by physics-derived height
  S-04  Stack-kin stream reads live PyBullet AABB during certification
  S-05  `random` module never seeded — `--seed` does not produce
        reproducible runs
  S-06  Sense found_target outcome does not verify hit lies in shadow
        AABB *(UNSURE — needs human review)*
  S-21  Stack-goal randomisation uses unseeded module RNG

TIER 2 — robustness / scalability (3 items)
  S-09  contains_nontarget — Python invents new boxels mid-plan with no
        PDDL effect representing it
  S-11  is_config_collision_free(allow_gripper_collisions=True) is
        global to the pick/place trajectory, not local-approach
  S-12  Three different visibility ray densities for three "same kind
        of question"

TIER 3 — code quality / doc-code drift (10 items)
  S-07  PDDL place has no symmetric is_object effect
  S-08  Domain comment claims (clear ?o) is conditional; init emits it
        unconditionally
  S-10  THESIS_NOTES §13 cites magic numbers that no longer exist
  S-13  test_boxel_fits is AABB-extent only — orientation, shape,
        clearance ignored
  S-14  execute_pick clamps contact_z to a finger-tip floor — silently
        shifts the executed pose above the planner-validated target
  S-15  release_held_object_in_place returns success when the held
        object cannot be name-resolved
  S-16  _hidden_xy_positions post-spawn check is a printf, not the
        documented retry layer
  S-17  oracle_hidden_shadow computed for logging only — vestige
  S-19  mark_occluder_moved called for every placed object
  S-20  random.shuffle of a 1-element list — dead code in sample_grasp

Findings by bucket:
  (a) THEORY DRIFT                     2  (S-08, S-09)
  (b) PLANNER CHEATS                   4  (S-02, S-03, S-04, S-14)
  (c) HIDDEN STATE / SIDE-CHANNELS     2  (S-01, S-04 — also-tagged)
  (d) CODE SMELLS                     11  (S-05, S-08, S-10, S-11, S-12,
                                            S-15, S-16, S-17, S-19, S-20,
                                            S-21)
  (e) SEMANTIC GAPS                    7  (S-03, S-06, S-07, S-09, S-11,
                                            S-12, S-13, S-14)
  (f) VERIFICATION GAPS                6  (S-05, S-06, S-15, S-16, S-18,
                                            S-21)

(Some findings span multiple buckets; the totals above count primary plus
secondary tags.)

UNSURE — needs human review:
  S-06  Sense found_target hit-vs-shadow AABB containment.  In the
        tabletop scenario shadows are by construction occluded from the
        camera, so any target hit on the LOS plausibly lies inside the
        shadow.  But oracle_detect_objects can classify a partially-
        visible target as visible while sense_shadow_raycasting still
        returns found_target on rays into a shadow that target is in
        front of — the symbolic record of which shadow contained it
        would then be fabricated.  Worth a sanity-check pass with a
        constructed scene where target is between camera and a shadow.

End of audit.
