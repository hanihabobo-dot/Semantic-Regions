# P1 grip-loss diagnosis — first pick reports success, hand is empty

Status: COMPLETE (read-only diagnosis; no code edited, no sim run).

Bug: stack goal, seed 0, GUI runs (h=3 and h=4). First pick of the episode reports
success but the block is not in the gripper; the pipeline proceeds and "stacks" a
block it is not holding. Subsequent picks work.

## Verdict (one sentence)

The Panda's fingers SPAWN FULLY CLOSED (panda.urdf prismatic finger joints have
lower=0.0 and loadURDF initializes every joint to 0) and nothing in the pipeline ever
opens them before the first pick, so the episode-first descent lands the CLOSED
fingertips ON TOP of the object, the one-shot grip check passes because both finger
links (9, 10) are "in contact" (tips pressing DOWN on the object top at 500-800 N of
arm-servo grind, not a pinch), and the lift departs without the object; every later
pick works because the first release ran open_gripper, leaving the fingers at 0.04
for the rest of the episode.

## Runs used as evidence

Primary (machine clock fixed ~20:00, these are the newest):
- logs/run_2026-08-20_20-09-59  stack h=3 seed 0 gui=True
- logs/run_2026-08-20_20-12-20  holding seed 0 gui=True
- logs/run_2026-08-20_20-19-11  holding seed 0 gui=True (killed during plan #2)
- logs/run_2026-08-20_20-21-49  stack h=4 seed 0 gui=True

Cross-check (earlier round, same code, clock 5 days behind — numbers identical,
deterministic replay): run_2026-08-15_22-06-46 (h=3), run_2026-08-15_22-11-32 (h=4,
killed mid-stack).

## Exact causal chain (with log-line and file:line evidence)

1. Spawn state: boxel_env.py:746-766 (_setup_scene) loads franka_panda/panda.urdf and
   only calls changeDynamics for finger friction. No resetJointState, no open_gripper,
   anywhere in setup. panda.urdf finger joints (wsl_env/.../pybullet_data/franka_panda/
   panda.urdf:310-323) are prismatic with lower="0.0" upper="0.04"; loadURDF zeros all
   joints => fingers start at 0.0 = FULLY CLOSED. robot_utils.py:31 REST_POSES has 7 arm
   values only; move_robot_smooth (robot_utils.py:539-548) drives range(7) only; the
   defensive open_gripper in execute_pick was removed (execution.py:733-736, audit
   #37/#38: "Gripper state is implicit in the PDDL predicate ... init = open").
   The PDDL init is open; the PHYSICS init is closed. That divergence is the bug.

2. First descent: execute_pick lowers to contact with settle=True
   (execution.py:740). The closed fingers hang below the EE — grasptarget (link 11)
   is at hand+0.105 (urdf:335), finger joints at hand+0.0584 (urdf:313) with a
   ~54 mm finger mesh, so fingertips reach ~7 mm BELOW the grasptarget. Closed, they
   sit at the gripper center — directly over the object — so the descent bottoms out
   with the tips grinding into the object's top face. The position servo (force=240
   per arm joint, 60 stream steps + up to 120 settle steps) presses until contact
   stiffness balances it (URDF finger contact stiffness 30000, damping 1000).
   Evidence — the stall offset is CONSTANT across scenes of different heights:
   - h=3 first pick:    ee_z=0.3768 vs contact_z=0.3700 (+6.8 mm; cube top 0.375)
     [20-09-59 L130]
   - holding first pick: ee_z=0.4591 vs contact_z=0.4523 (+6.8 mm; occluder top
     0.4573) [20-12-20 L130]
   - h=4 first pick:    ee_z=0.3725 (+2.5 mm) with ee_xy_err=2.62mm (tips wedged and
     slid laterally) [20-21-49 L142]
   Later picks in the same episodes arrive +0.9 mm or better (e.g. 20-09-59 L218).

3. "Close": close_gripper (robot_utils.py:624-664) targets max(0.002, cube_hw-0.003)
   = 0.022 from execute_pick:767-768. The fingers are at ~0.0 and would have to slide
   OUTWARD along the object top while carrying ~300 N normal load each; available
   motor force is 40 N vs ~360 N of friction (mu 1.2) — they stay pinned near 0.
   (Even free, 0.022 < cube half-width 0.025: they could never pass the faces.)

4. One-shot grip verification passes falsely: execution.py:780-792 requires only
   pad_links == {9, 10} — LINK IDENTITY, not opposing normals, not finger aperture.
   Both fingertips standing on the object top satisfy it. The reported force is the
   arm-servo grind, not a pinch:
   - 563.04 N (h=3, L131), 600.16 N (holding, L131 — identical in both holding runs,
     deterministic), 491.42 N (h=4, L143)
   vs 78.97-80.00 N (= 2 x 40 N motor budget, exactly) on every genuine later grasp.
   The "first close of an episode shows a 500-800 N transient" headless observation
   is this same phenomenon — it is NOT a close-impact spike.

5. audit_robot_held_state(post-pick) stays silent by design: execution.py:794-798
   runs BEFORE the lift while the tips still press the object — contact with exactly
   the expected body id is a quiet success (execution.py:275-305, "success cases stay
   quiet"). No HELD-STATE ANOMALY lines exist in any of the four GUI logs.

6. Lift and transport are unchecked: _apply_post_action_lift (execution.py:595-615,
   called at 804-805) raises the EE 10 cm — tips leave the object top; the object
   never moves (h=3: pre-release pos [0.0181,0.2892,0.3500] == spawn pose +-0.7 mm,
   lateral_drift at drop-verify 0.01 mm). No contact re-check after the lift, none in
   move dispatch, and execute_stack's only entry gate is held_body_id is not None
   (execution.py:1015-1018). Dispatcher prints "*** PICKED UP! ***"
   (test_full_pipeline.py:1339) on the same one-shot verdict.

7. Detection, when it happens at all, is 2 actions late and only for stacks:
   _release_and_verify_drop gates (execution.py:385-422+): (i) fingers open — passes
   trivially (they open fine, nothing between them); (iii) stationary — passes
   (object never moved); (iv) no robot contact — passes trivially; (ii) bottom
   within 2 cm of support top — fails ONLY because the lost cube sits at table
   height 0.325 vs expected stack support top 0.375 (err=-50.0mm, 20-09-59 L145-147,
   20-21-49 L157-159). Abort -> clear held state -> replan (test_full_pipeline.py
   place branch 1385-1409, stack branch analogous) — the h=3/h=4 episodes then
   recover with a genuine second pick.

8. SILENT CORRUPTION for table-height places (worse than the reported symptom):
   holding run 20-12-20 — phantom first pick of the orange OCCLUDER, then
   "place at free_008" VERIFIES OK (L143: bottom_z=0.3250 expected=0.3250) because a
   never-moved object standing on the table also has its bottom at table height:
   gate (ii) is blind for table placements. The episode continues with belief
   "orange at free_008" while physics has orange at its spawn pose: sense actions
   fail repeatedly ("shadow_of_orange_object__01/00 blocked 3 times — giving up",
   L385/L439), then ~10 consecutive failed green picks (ee_vs_obj_xy up to 44 mm,
   one-pad 394-423 N contacts, then contacts=none loops, L795-1844). In 20-19-11 the
   replan after the phantom pick plans place(orange_object, ...) with compute_kin
   believing orange rides at the EE (ee_target z=0.4911) — the phantom "holding"
   infects planning; the user killed the run there. A holding-goal episode can even
   TERMINATE "successful" on a phantom pick.

## Why the FIRST pick specifically

Because the finger spawn state is the only episode-scoped one-shot: fingers start
closed (loadURDF zeros) and the first open_gripper call of an episode happens either
in the first release path (_release_and_verify_drop -> open_gripper) or on the first
grip-verify failure (execution.py:789). After that they sit at 0.04 and every later
descent straddles the object and pinches normally (79.9-80.0 N steady reads). Not an
impact transient, not scene settling, not IK cold start: the +6.8 mm arrival offset
reproducing EXACTLY at two different object heights (0.370->0.3768 and
0.4523->0.4591) is the geometric signature of the same rigid obstruction — closed
fingertips — bottoming out on the object top with the same servo/contact-stiffness
equilibrium (~5 mm apparent penetration under ~600 N with URDF stiffness 30000).

## Minimal fix proposal (no code edited; exact insertion points)

FIX 1 — root cause, one line (required):
  boxel_env.py, _setup_scene, immediately after the robot loadURDF + finger-friction
  changeDynamics block (after line 761):
      for fj in (9, 10):  # robot_utils.FINGER_JOINTS
          p.resetJointState(robot_id, fj, 0.04, physicsClientId=self.client_id)
  The plan client does NOT need its own reset: sync_to_plan_client runs before every
  planner.plan() INCLUDING plan #1 (test_full_pipeline.py:1039) and copies all joint
  states including fingers (boxel_env.py:706-715) — though mirroring the reset is
  cheap and harmless if preferred for symmetry.
  This reconciles physics with the documented convention at execution.py:733-736
  ("init = open") — that comment should be updated to note the spawn-state reset.

FIX 2 — post-lift re-verify (required; the definitive gate for this failure CLASS):
  execution.py, immediately after _apply_post_action_lift(...) at lines 804-805 and
  before the final_config read at 811: repeat the pad-contact check of lines 780-790
  against obj_id; on failure print a diag, open_gripper(robot_id, gui), and
  return None, None. The dispatcher's existing failure branch
  (test_full_pipeline.py:1313-1327) already does exactly the right recovery:
  env.update_object_positions() + refresh_object_aabbs() + replan. With the weld gone,
  "verified at close" can never again be assumed to mean "still held after the lift";
  this catches top-standing phantoms, close-then-eject, and future slip-on-lift, and
  it would have flagged all four GUI runs inside the pick action instead of one-or-two
  actions later (or never, for table places).

FIX 3 — held-contact assert at execute_stack / execute_place entry (recommended,
  cheap defense-in-depth; catches transport slip and closes the table-place blind
  spot of drop-verify gate (ii)):
  - execution.py execute_stack: after the held_body_id None check (line 1018).
  - execution.py execute_place: inside the held_body_id is not None branch (~line 863).
  Check p.getContactPoints(bodyA=robot_id, bodyB=held_body_id) contains both
  FINGER_JOINTS links; on failure return a value the dispatcher can DISTINGUISH from
  IK failure. Caveat for the implementer: the dispatcher currently classifies a None
  from place/stack by fingers_open (test_full_pipeline.py:1385-1411 place,
  ~1521-1528 stack); an empty-hand entry failure has fingers CLOSED and would be
  misclassified as "IK failure" and LEAVE held_body_id set. Either open the gripper
  before returning from the entry check, or (cleaner) add a distinct sentinel /
  exception handled as: held_body_id = None, held_object_boxel_id = None,
  env.update_object_positions(), refresh_object_aabbs(), replan.

NOT RECOMMENDED as a fix for THIS bug — two-stage close (low-force touch then ramp
to 40 N): the 500-800 N reading is not a close-impact spike (genuine closes settle at
exactly 2 x 40 N inside the same 60-step window; there is no observed spike on any
real grasp), it is arm-servo grind through closed fingertips. A gentle close would
still read both links in contact from the top-standing pose and still pass the
link-identity check. Optional hardening instead: make grip verification check finger
APERTURE plausibility (|finger_pos - cube_hw| <= ~6 mm; the phantom reads ~0.000-0.005
vs cube_hw 0.025) and/or opposing contact normals — link identity alone cannot
distinguish standing-on-top from pinching.

Secondary observations (out of scope, for the audit doc):
- _apply_post_action_lift docstring/comment says ~5 cm but the default and actual
  lift is 0.10 m (execution.py:596, 800-805).
- The settle=True descent can grind up to ~600 N into scene objects whenever the
  path is blocked; a contact-force abort during the descent would fail faster and
  gentler than the 120-step cap.
- 20-12-20's late green-pick loop (contacts=none 0.00 N repeated with identical
  ee 0.3771 arrivals ~10x) is the audit-#47/#83 stale-belief loop riding on top of
  the phantom-place corruption; it should disappear once Fixes 1-3 land, but the
  giving-up sense path deserves its own look.
