================================================================================
T2 PHASE 3-B — IMPLEMENTATION PLAN (Architecture B-full: our pipeline on their env)
Handoff plan for an implementing agent.  Authored 2026-06-06.
================================================================================

>>> ITEM 0 RECHECK LOG — appended 2026-06-06 (implementing agent) <<<
--------------------------------------------------------------------------------
ITEM 0 done.  Branch decision: STAY ON MAIN (user reconfirmed 2026-06-06).
Spot-checked >10 KEY FACTS vs live code — all matched EXCEPT delta #1 below:
  OURS: oracle_detect_objects boxel_env.py:1620; getAABB :1651 + rayTestBatch
    :1662 BOTH call with NO physicsClientId (default-client assumption holds —
    risk #2 real); camera defaults :452-457; calculate_shadow_boxel
    shadow_calculator.py:41, surface-rest gate is the `if` at :73 (comment :67);
    test_target_can_hide_in_shadow streams.py:407 (n_grid=3).
  THEIRS: run_planner.py seed :125-6, env build :130, initialize :131, policy via
    tconfig.get_planner(config, env.problem_spec, execution_data=...) :135-7,
    rollout :138.  env.py: CAMERA_FRAME/DEFAULT_ARM_POS/PANDA_TOOL_TIP import
    :31-33; abstract :306 with at-home == np.allclose(current_conf,DEFAULT_ARM_POS)
    :319; look_execute_fn :523; look_sample_fn :585 reads CAMERA_FRAME link :639
    (eye-in-hand CONFIRMED); initialize :816, self.vis :819; get_problem_spec :878.
BASELINE: stock find_dice GUI episode (seed 0) RENDERS under WSLg and TAMPURA
  SOLVES it (Reward 1.0: pick relocates cup o_ph_0, ends holding die o_ph_1 at
  home).  Exit code 139 = harmless WSLg teardown segfault (expected).

>>> DELTA #1 (CORRECTION to KEY FACTS — scene schema): the die is the LAST
    category/pose, NOT categories[0].  Real file 1747173591.670785.json:
      {"categories": ["d_cups_ud","dice"], "poses": [[cup],[die]]}  (index-aligned)
    So cups come FIRST (one or more "*_cups_ud") and "dice" is LAST.  ITEM 6
    mapping = {occluders: every non-"dice" entry; target: the "dice" entry}.
    Containment holds (die XY == cup XY; die quat identity).  Seed 0 deterministically
    selects 1747173591.670785.json (1 cup, die co-located under it); runtime State
    labels o_ph_0=cup (gets 'moved'), o_ph_1=die (is-target, ends held). <<<
--------------------------------------------------------------------------------

>>> READ THIS FIRST — PROVENANCE & RECHECK MANDATE <<<
--------------------------------------------------------------------------------
THIS PLAN AND ITS ORDER WERE WRITTEN BY AN AI from a code reading on 2026-06-06.
EVERYTHING in it — file paths, line numbers, API names, signatures, behaviours,
the ordering, and the feasibility claims — IS AN ASSERTION THAT MAY BE WRONG OR
STALE.  Before you implement or test ANY item:

  1. RE-DERIVE the facts you depend on with Grep/Read against the LIVE code.
     Do not trust a single line number in this document.
  2. If reality differs from what an item assumes, STOP, write down the delta,
     and re-plan that item (and re-check whether later items still hold).
  3. Treat every item's "RECHECK / unknowns" field as a gate, not a footnote.
  4. The ITEM ORDER is a best-guess dependency order, also AI-written — confirm
     each item's "Depends on" is actually satisfied before starting it.

You are not executing a verified spec.  You are auditing and validating an
AI's hypothesis while you build it.  Expect to correct this document.

--------------------------------------------------------------------------------
HOW TO WORK THIS PLAN (skills + discipline)
--------------------------------------------------------------------------------
- Use the /workflow skill.  ONE item per turn: show a before/after preview, get
  EXPLICIT user approval, then make ONE commit for that item.  Never batch items.
- Use the /code-review skill at the review checkpoints (Item B1-REVIEW and Item
  14) on the working-tree diff; triage every finding (fix or log with reason).
- ENVIRONMENT (safety-critical):
    * Windows + PowerShell ONLY.  NEVER the Bash tool (MSYS2 fork emulation has
      fork-bombed this machine).  Run WSL via the PowerShell tool: `wsl ... `.
    * Git: one command at a time, never parallel/backgrounded.  After EVERY
      commit re-verify the branch (`git symbolic-ref HEAD`); if a stray branch
      absorbed a commit, recover it.
    * Use Glob/Grep/Read for exploration — no shell ls/cat/grep on Windows files.
      WSL-resident files (/root/tampura-work/**) may be read via the
      \\wsl.localhost\Ubuntu\... share with Read, or `wsl bash -lc 'sed -n ...'`.
- BRANCH: the user directed THIS session to make NO new branches → work on
  `main`, one commit per item.  *** RECHECK with the user before starting ***:
  the repo's standing policy (memory) is to branch for multi-commit work, and
  this is multi-commit.  Reconfirm which they want.  Do NOT create a worktree.
- GUI RULE (user requirement): every verification run that renders the sim MUST
  run with the GUI on (user watches).  If the GUI does not actually render under
  WSL, STOP driving and hand the user the exact command(s) to run themselves
  from that point.  (Import/unit smokes have no GUI — still give the command.)
- PUSH: commit only.  Do NOT push (origin/GitHub only when the user explicitly
  asks).  No Co-Authored-By trailer.
- Plots/screenshots ADD, never overwrite.  Don't delete commented-out code.

--------------------------------------------------------------------------------
SCOPE & EXIT GOALS (what "done" means for THIS phase)
--------------------------------------------------------------------------------
This is NOT the full find_dice solve and NOT the eval (PHASE 4, gated).  Architecture
chosen by the user: B-full = our full pipeline (oracle + boxel/shadow discretizer +
PDDLStream planner) operating on TAMPURA's find_dice env, with their robot/cups/die/
physics; camera stays eye-in-hand but SENSE is only legal from one fixed "home" arm
config (fixed viewpoint = our fixed-camera model).

By the end of this phase, these THREE goals must be demonstrable on the GUI:

  GOAL 1 — Our BOXELIZATION is visible on THEIR env.            (delivered by ITEM 8)
  GOAL 2 — Our PLANNER uses OUR action (modified is fine) to    (delivered by ITEM 12)
           perform a PICK in their env.
  GOAL 3 — Our ORACLE + BOXELIZATION run the EXACT same way as  (delivered by ITEM 9
           on our env; SENSE can only sense at home.             + ITEM 13)

Anything beyond this (full relocate->sense->pick(die)->home solve, faithful robot
controllers, >=20-seed eval) is OUT OF SCOPE here and listed under "LATER".

--------------------------------------------------------------------------------
KEY REFERENCE FACTS (AI-asserted 2026-06-06 — RECHECK ALL)
--------------------------------------------------------------------------------
THEIR side (WSL, EXT4 — must run from /root/tampura-work, NOT /mnt/c):
- Entry: tampura_environments/run_planner.py:130-138 — build env, `b0,store =
  env.initialize()`, instantiate Policy, `policy.rollout(env,b0,store)`.
- Policy contract: tampura/tampura/policies/policy.py:93 `get_action(belief,store)
  -> (Action,info,store)`; shared rollout loop :96-161 does env.step + belief
  update + reward + pkl; max_steps (=20); reward = holding(die) AND at-home.
- find_dice env: tampura_environments/tampura_environments/find_dice/env.py
  * initialize() :816 builds two pybullet worlds (state world `self.world` +
    sim/belief world `self.sim_world`); `self.vis` controls GUI (:819).
  * get_problem_spec() :878-1013: predicates/streams/actions.  Operators
    pick(?o,?g):925, place(?o,?g,?p):943, look(?o1,?o2,?q):962
    [depends=moved(?o2):966, verify_effects=known-pose(?o1):976], go-home:978.
    Samplers: look-conf-sample->?q, grasp-sample->?g, place-sample->?p (:893-921).
  * abstract() :306-321 emits known-pose/holding/at-grasp/is-target/moved/at-home.
  * CAMERA IS EYE-IN-HAND: look_execute_fn :523 plans+executes ARM motion to a
    look conf then images; look_sample_fn :584 returns an ARM config aiming the
    wrist camera.  Camera class panda_utils/robot.py:83, mounted on a link :120,
    robot.get_image :263.  DEFAULT_ARM_POS / CAMERA_FRAME / PANDA_TOOL_TIP at
    env.py import :31-33.
  * Problem scenes: find_dice/problems/*.json — schema {categories:[...],
    poses:[[[xyz],[quat]],...]} index-aligned; categories[0]="dice"; rest
    "*_cups_ud"; die XY ~= the hiding cup's XY (containment).  3 files present.
  * get_scene_data() :801 picks random.choice(os.listdir(problems)); the global
    seed (run_planner :125) determines which.
- Runbook (notes/TAMPURA_PLAN.md "HOW TO RUN REAL TAMPURA"): GUI one episode
  `bash /root/tampura-work/tampura_run_gui.sh 0 1`; headless `python run_planner.py
  --config=./env_configs/find_dice.yml --global-seed=0`.  GOTCHA: SymK shells to
  bare `python` -> venv MUST be activated.  GUI teardown segfaults on WSLg
  (harmless).  --vis uses bool() so bool("0")=True; pass True or omit.

OUR side (Windows repo C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels;
WSL path /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels; venv wsl_env;
PDDLStream vendored at ../pddlstream_lib):
- Oracle: boxel_env.py oracle_detect_objects:1620 — casts camera->8-AABB-corner
  rays; visible if ANY ray hits the body.  NOTE: calls p.getAABB / p.rayTestBatch
  WITHOUT physicsClientId (:1651,:1662) -> assumes the DEFAULT pybullet client.
- Camera defaults: boxel_env.py:452-457 eye (0.1,-0.8,0.7), target (0.1,0,0.5).
- Discretizer: BoxelRegistry boxel_data.py:101; shadow_calculator.py
  calculate_shadow_boxel:41 with surface-resting gate :67 (only an object
  resting on the table casts a shadow); free space reboxelize.py
  reboxelize_free_space (imported test_full_pipeline.py:91).  auto_cell sizing
  test_full_pipeline.py:485-527 (auto_cell = max_extent+0.01; sets octree
  min_resolution).
- Sense grounding gate: streams.py test_target_can_hide_in_shadow:407 (3x3 grid,
  fully-occluded, table-resting) — relevant once sense is exercised.
- Scene builders dispatch: test_full_pipeline.py:1698; argparse in
  run_logger.py:385 (`--scene` choices :412).  main() :433.

================================================================================
PHASE B0 — STATE CHECK, BRIDGE, ENVIRONMENT  (prerequisites)
================================================================================

### ITEM 0 — Re-verify repo state and THIS plan   [type: recon/recheck]
- Goal: establish a clean, known starting point and catch staleness in this doc.
- Depends on: nothing.
- Steps:
  1. `git symbolic-ref HEAD` (expect main); `git status` (note dirty files; do
     NOT touch unrelated thesis/eval files).  Confirm branch policy with user.
  2. Grep the repo for `find_dice`, `BoxelPolicy`, `run_boxel_on_finddice`,
     `tampura_bridge` — confirm none of the Phase-3B code already exists.
  3. Re-read notes/TAMPURA_PLAN.md PHASE 3 + CARE + CAVEAT + the "HOW TO RUN REAL
     TAMPURA" runbook.  Confirm the design here matches the user's latest intent
     (B-full; camera-on-arm but sense-at-home; execution TBD per ITEM 11).
  4. Spot-check 10+ of the "KEY REFERENCE FACTS" line numbers above against live
     code (ours via Read; theirs via \\wsl.localhost\Ubuntu\... or `wsl sed`).
     Record every mismatch at the top of this file.
  5. Re-run ONE stock TAMPURA episode to confirm their stack still works
     (baseline we are building against):
        wsl -d Ubuntu -e bash -lc 'bash /root/tampura-work/tampura_run_gui.sh 0 1'
     (GUI; user watches.  If GUI fails, give the headless command instead.)
- Verification: clean state understood; mismatches logged; stock episode runs.
- Commit: docs only if you corrected this file — "phase3b: reconcile plan facts
  with live code (item 0)".  Otherwise no commit.
- RECHECK / unknowns: the working tree was dirty on 2026-06-06 with unrelated
  thesis/eval changes — do not bundle them.

### ITEM 1 — Single-process import & venv strategy   [type: DECISION + test]  *** TOP RISK ***
- Goal: prove our pipeline (boxel_env, shadow_calculator, belief, streams, the
  PDDLStream planner, ../pddlstream_lib, and our FD/SymK backend) can be IMPORTED
  and RUN in the SAME Python process as their find_dice env.  B-full is infeasible
  if this can't be made to work — surface that NOW, before building anything.
- Depends on: ITEM 0.
- Why: their env runs in /root/tampura-work/.venv (py3.11, their pybullet, SymK).
  Our pipeline normally runs in wsl_env with ../pddlstream_lib and its own FD.
  One process must satisfy BOTH dependency sets.
- Steps:
  1. Inventory both venvs: `wsl bash -lc 'source /root/tampura-work/.venv/bin/
     activate && pip freeze'` vs our wsl_env freeze.  Diff the critical deps
     (pybullet version!, numpy, scipy).  A pybullet major mismatch is a red flag.
  2. Decide the strategy and RECORD it here:
       (A) run inside THEIR .venv, add our repo + ../pddlstream_lib to PYTHONPATH,
           and make our planner's FD/SymK backend resolvable; or
       (B) build a combined venv; or
       (C) our planner runs out-of-process (subprocess/RPC) and only exchanges
           PDDL/plans — heavier but isolates the dependency sets.
     Recommended starting point: (A).  Note our oracle uses the DEFAULT pybullet
     client (see KEY FACTS) — single-process + single default client matters.
  3. Write a throwaway smoke `tampura_bridge/_import_smoke.py` that does:
       `import tampura, tampura_environments` AND
       `import boxel_env, shadow_calculator, belief, streams` AND imports the
       PDDLStream entry our pipeline uses, then prints versions.  Run it with the
       chosen env from cwd /root/tampura-work/tampura_environments and
       PYTHONPATH spanning /mnt/c/...Semantic_Boxels and ../pddlstream_lib.
  4. Confirm our FD/SymK actually EXECUTES (not just imports) in this env — run
     the smallest planner call our pipeline can make.  (This is the part most
     likely to break.)
- Verification: smoke prints all imports + versions; a trivial plan call returns.
  No GUI (console).  Provide the exact command regardless.
- Commit: "phase3b: import/venv smoke for our-pipeline-in-their-env (item 1)"
  (keep _import_smoke.py under tampura_bridge/ or tools/; it documents the env).
- RECHECK / unknowns: pybullet ABI/version clash between venvs is the biggest
  failure mode; FD/SymK path resolution is the second.  If neither (A) nor (B)
  works, STOP and escalate to the user (option C is a re-scope, not a quick fix).

### ITEM 2 — Bridge runner + passthrough policy   [type: implement + test]
- Goal: our OWN entry point builds their env, plugs in OUR Policy subclass, and
  steps their world — proving the integration seam end-to-end with a no-op brain.
- Depends on: ITEM 1.
- Files (NEW, in OUR repo so it is version-controlled):
    tampura_bridge/__init__.py
    tampura_bridge/boxel_policy.py        (class BoxelPolicy(tampura...Policy))
    tampura_bridge/run_boxel_on_finddice.py  (mirrors run_planner.py:101-138 but
                                              constructs BoxelPolicy directly, so
                                              we never edit their clone)
- Steps:
  1. BoxelPolicy.get_action: for THIS item, return Action("no-op") (or a single
     hardcoded applicable action obtained via problem_spec.applicable_actions) so
     the rollout loop runs without our planner yet.
  2. run_boxel_on_finddice.py: replicate the env build + initialize + rollout
     from run_planner.py (config load via tampura.config; task=find_dice;
     vis=True for GUI).  Reuse their save_dir/logging.
  3. Add a tiny scene pin (optional): allow `--global-seed` so the chosen
     problems/*.json is reproducible.
- Verification (GUI): 
    wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
      cd /root/tampura-work/tampura_environments && \
      PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib:$PYTHONPATH \
      python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/run_boxel_on_finddice.py --global-seed 0'
  (RECHECK the exact PYTHONPATH/flags from ITEM 1.)  Watch: their scene loads in
  the GUI; the rollout advances through steps driven by BoxelPolicy; clean-ish
  exit (teardown segfault under GUI is the known-harmless gotcha).
- Commit: "phase3b: bridge runner + passthrough BoxelPolicy on find_dice (item 2)"
- RECHECK / unknowns: how the env/config is constructed (tconfig.get_env,
  tconfig.load_config) — read run_planner.py and tampura/config/config.py before
  copying.  Confirm cwd must be the env repo (relative problems/ path).

================================================================================
PHASE B1 — PERCEPTION PARITY ON THEIR ENV   (GOAL 1 + GOAL 3 perception)
================================================================================

### ITEM 3 — Enumerate the BoxelTestEnv surface our perception needs  [type: recon]
- Goal: produce an exact interface spec so we can feed their world to our oracle +
  boxelizer + shadow_calculator + reboxelize WITHOUT modifying our core code.
- Depends on: ITEM 0.
- Steps: Read oracle_detect_objects, shadow_calculator (ctor + calculate_shadow_
  boxel), BoxelRegistry, reboxelize_free_space, and the auto_cell block in
  test_full_pipeline.py.  List EVERY attribute/method/global they touch:
  e.g. env.objects (name -> obj with .object_id/.size/.position), camera_position,
  table_surface_height, _SAFE_TABLE_*_RANGE, the pybullet client used, etc.
- Verification: a written interface checklist appended to this file.  No GUI.
- Commit: "phase3b: document perception adapter surface (item 3)" (doc only).
- RECHECK / unknowns: the DEFAULT-client assumption in oracle_detect_objects
  (:1651,:1662) vs their world.client — decide adapter vs small core change here.

### ITEM 4 — Perception world strategy   [type: DECISION]  *** PIVOTAL — confirm with user ***
- Goal: choose HOW our perception sees their scene.  Two coherent options:
    (P1) SINGLE WORLD: our perception reads THEIR live pybullet world/client
         directly via an adapter (most faithful "on their env"; requires honoring
         their client id — our oracle currently assumes the default client).
    (P2) MIRROR: load their object poses/AABBs into a throwaway BoxelTestEnv (our
         pybullet) and run our perception there unmodified (lowest risk for GOAL
         1/3 "exact same way"; but it is our-sim-of-their-scene, not their world).
- Recommendation: P1 if ITEM 3 shows the client can be threaded through cleanly;
  else P2 as a de-risking fallback for GOAL 1/3 while execution (B2) still happens
  in their world.  RECORD the decision and its rationale here, and confirm with
  the user — it shapes every later item.
- Verification: decision documented.  No GUI.
- Commit: "phase3b: decide perception world strategy P1/P2 (item 4)" (doc only).
- RECHECK / unknowns: if P1 forces edits to our oracle (passing physicsClientId),
  treat that as a guarded change to shared code — /code-review it (Item B1-REVIEW).

### ITEM 5 — Fixed sense/home camera config + pose extraction  [type: implement + test]
- Goal: define the ONE arm configuration from which sensing is allowed, and
  extract the wrist camera's world pose at that config to feed our perception.
- Depends on: ITEM 2.
- Steps:
  1. Candidate config = DEFAULT_ARM_POS (their home).  Set the arm there, read
     the CAMERA_FRAME link world pose (eye) and a look direction (target on the
     table) — this becomes our perception's camera_position/target.
  2. If DEFAULT_ARM_POS's camera does NOT view the table usefully, choose a
     dedicated fixed "sense config" (a single, constant arm config whose wrist
     camera sees the table obliquely, mirroring our (0.1,-0.8,0.7)->(0.1,0,0.5)
     geometry as closely as their frame allows).  It must stay CONSTANT.
- Verification (GUI): drive the arm to the sense config and capture/show the
  camera image; confirm the table + cups + (covered) die region are in view.
- Commit: "phase3b: fixed sense/home camera config + pose extraction (item 5)"
- RECHECK / unknowns: their world frame vs our frame; the camera's link offset;
  whether a saved image or a live PyBullet view is the right artifact.

### ITEM 6 — Perception adapter over their world  [type: implement]
- Goal: implement the adapter from ITEM 3/ITEM 4 so our perception runs on their
  scene with the ITEM 5 camera pose.
- Depends on: ITEM 3, ITEM 4, ITEM 5.
- Files (NEW): tampura_bridge/perception_adapter.py.
- Steps: expose their objects (id/size/pose/category), table height/extents, the
  fixed camera pose, and the correct pybullet client through the exact surface
  ITEM 3 enumerated.  Map each find_dice cup -> an occluder; the die -> a target.
- Verification: a unit smoke that instantiates the adapter and prints object
  list + camera + table bounds (no GUI).  Provide the command.
- Commit: "phase3b: perception adapter exposing their world to our pipeline (item 6)"
- RECHECK / unknowns: concave YCB cups — our shadow_calculator uses AABBs, so a
  cup is approximated by its bounding box; confirm AABBs come out sane.

### ITEM 7 — Our ORACLE on their scene  [type: implement + test]
- Goal: run our oracle (8-corner camera raycast) on their scene from the fixed
  camera; confirm the die reads HIDDEN and the cups read VISIBLE.
- Depends on: ITEM 6.
- Verification (GUI): run the bridge; log the oracle's visible/hidden lists;
  confirm die hidden.  Cross-check against the fact that find_dice scenes are
  saved only when the die is hidden (to THEIR wrist camera) — note any scene that
  is trivially visible under our fixed camera (re-validation, see RECHECK).
- Commit: "phase3b: our oracle classifies hidden die on their scene (item 7)"
- RECHECK / unknowns: the released scenes' hidden-guarantee was computed against
  their MOVABLE camera; under our FIXED camera some scenes may be trivial or
  unsolvable.  If the chosen seed's die is already visible, pick another problem
  json / seed and record which scenes are valid under the fixed camera.

### ITEM 8 — Our BOXELIZATION + SHADOWS on their scene (GOAL 1)  [type: implement + test]
- Goal: run our boxelizer + shadow_calculator + reboxelize_free_space on their
  scene and DRAW the overlays in their GUI.  *** This delivers GOAL 1. ***
- Depends on: ITEM 7.
- Verification (GUI): overlays render in their PyBullet window; confirm the
  hiding cup casts a shadow region and the die sits inside it; confirm auto_cell
  prints a sane value (driven by the tallest object).  Capture a screenshot
  (ADD; never overwrite).
- Commit: "phase3b: our boxelization+shadows overlaid on find_dice scene (item 8)"
- RECHECK / unknowns: shadow surface-resting gate (shadow_calculator.py:67) — the
  cup must register as resting on the table in their world for it to cast a
  shadow; verify the table z and contact tolerance translate correctly.

### ITEM 9 — Perception PARITY check (GOAL 3, perception half)  [type: test]
- Goal: prove the oracle + boxelization use the EXACT same code paths/parameters
  as on our env.
- Depends on: ITEM 8.
- Steps: confirm the SAME functions/params run: auto_cell formula + octree
  min_resolution; reboxelize_free_space octree+merge; the 8-corner oracle; the
  surface-resting shadow gate; the test_target_can_hide_in_shadow gate (even if
  sense isn't solved yet).  Document any place the find_dice path diverges and
  WHY (e.g., adapter shims).  Ideally diff a boxelization summary on a comparable
  OUR scene vs the find_dice scene.
- Verification (GUI optional / log): a written parity note + matching log lines.
- Commit: "phase3b: perception parity (oracle+boxelization) note (item 9)"
- RECHECK / unknowns: any divergence is a GOAL-3 risk — list it explicitly.

### ITEM B1-REVIEW — Code review of the perception integration  [type: review]
- Run /code-review on the working diff so far.  Focus: the adapter, any change to
  shared oracle/shadow code (client threading), reuse vs duplication.  Triage and
  fix or log each finding.  Commit fixes individually.

================================================================================
PHASE B2 — PLANNER DOES A PICK + SENSE-AT-HOME   (GOAL 2 + GOAL 3 sense)
================================================================================

### ITEM 10 — Modified domain for their env  [type: implement]
- Goal: a find_dice variant of OUR domain in which a PICK can ground without our
  full IK/grasp streams (the user explicitly allows a MODIFIED action).
- Depends on: ITEM 8 (a belief our planner can consume).
- Files (NEW; do NOT edit the shared domain): pddl/domain_find_dice.pddl (copy of
  pddl/domain_pddlstream.pddl, tweaked) and, if needed, pddl/stream_find_dice.pddl.
- Steps:
  1. Keep our occlusion predicates (is_shadow / view_blocked / view_clear) so the
     boxelization is meaningful, but RELAX pick so it grounds from the adapted
     belief (e.g., precondition = known-pose/reachable; defer full IK).
  2. Add the SENSE precondition: sense is legal ONLY when the arm is at the fixed
     home/sense config (GOAL 3 "sense can only sense at home").
- Verification: PDDL parses; a dry plan call grounds a pick (no GUI; log).
- Commit: "phase3b: find_dice domain variant; pick grounds, sense requires home (item 10)"
- RECHECK / unknowns: whether our streams must be stubbed/replaced for their env;
  keep changes in the *_find_dice files so the shared domain is untouched.

### ITEM 11 — Minimal execution for a pick in their world  [type: implement]  *** see note ***
- Goal: make our planner's pick ACTUALLY execute in their world.
- Depends on: ITEM 10.
- DECISION (carried from the design discussion): in B the running world is THEIRS;
  our execution.py only drives our BoxelTestEnv and CANNOT move their robot.  So
  execution is either (a) their pick/place controllers (faithful motion + saved
  grasps; needs their-format params from their samplers) or (b) SIMPLIFIED
  pose-set/attach in their pybullet (no motion planning).  For THIS phase use (b)
  to prove the loop; (a) is a LATER fidelity upgrade.  Confirm with the user.
- Steps: implement a minimal "pick" that, on our planner's pick action, attaches/
  sets the target object as held in their world and updates state so the rollout
  continues.  Map our action -> a their-env Action the rollout can carry.
- Verification: unit smoke that executes one pick step in their world (GUI).
- Commit: "phase3b: minimal simplified pick execution in their world (item 11)"
- RECHECK / unknowns: how their rollout/env.step + belief.update consume a custom
  Action; whether attaching bypasses their step() cleanly.

### ITEM 12 — Our PLANNER performs a PICK (GOAL 2)  [type: implement + test]
- Goal: our PDDLStream planner, over the find_dice domain variant and the adapted
  belief, produces a plan whose action our policy executes as a PICK in their env.
  *** This delivers GOAL 2. ***
- Depends on: ITEM 10, ITEM 11.
- Steps: wire BoxelPolicy.get_action to: build our problem from the adapted
  belief -> run our planner -> return the first action (a pick) -> execute via
  ITEM 11.  A goal that yields a single pick is sufficient (e.g., pick a chosen
  cup or a visible object); the full die-solve is LATER.
- Verification (GUI): the log shows our planner emitting our (modified) pick; the
  robot/object performs the pick in their GUI.  Screenshot (ADD).
- Commit: "phase3b: our planner issues+executes a pick on find_dice (item 12)"
- RECHECK / unknowns: grounding may still fail if our streams are required —
  fall back to the relaxed pick from ITEM 10; do not silently widen scope.

### ITEM 13 — Sense-from-home demonstration (GOAL 3, sense half)  [type: test]
- Goal: demonstrate one SENSE that is only legal at the fixed home config.
- Depends on: ITEM 10, ITEM 12.
- Steps: force the arm to the home/sense config, run our sense (perception read +
  the test_target_can_hide_in_shadow gate) from the fixed camera; show that sense
  is rejected/blocked when NOT at home and runs when at home.
- Verification (GUI): the precondition is enforced (a non-home sense is illegal);
  a home sense executes and reads the scene.
- Commit: "phase3b: sense restricted to fixed home config, demonstrated (item 13)"
- RECHECK / unknowns: this need not reveal the die this phase; it only proves the
  at-home gate + that sense uses our perception.

================================================================================
PHASE B3 — REVIEW, RECORD, STOP
================================================================================

### ITEM 14 — Full /code-review  [type: review]
- Run /code-review on the complete working diff (all of Phase 3B).  Triage every
  correctness finding and cleanup; fix or log with a reason.  Commit fixes
  individually.

### ITEM 15 — Record results, capture, STOP  [type: doc + capture]
- Update notes/TAMPURA_PLAN.md (PHASE 3 -> B-full done to the 3 goals; note that
  the doc's old "copy domain + adapt their env" framing is realised here) and add
  a CODEBASE_AUDIT.txt note (pipeline/integration finding).  Capture the GUI
  screenshots for goals 1/2/3 (ADD, never overwrite).  Then STOP and get the
  user's confirmation.  Do NOT start any eval — PHASE 4 (>=20-seed comparison) is
  GATED by the supervisor rule (post-thesis, >=1 week free).
- Commit: "phase3b: record results + caveats; stop for confirmation (item 15)"

================================================================================
EXIT CRITERIA (verify all three on the GUI before declaring the phase done)
================================================================================
  [ ] GOAL 1  ITEM 8  — our boxelization + shadows visibly overlaid on their scene.
  [ ] GOAL 2  ITEM 12 — our planner emits our (modified) pick; it executes in their env.
  [ ] GOAL 3  ITEM 9  — oracle + boxelization run the same code paths/params as ours,
              ITEM 13   AND sense is only legal at the fixed home config.

================================================================================
RISK REGISTER (ranked; AI-assessed — re-judge as you learn)
================================================================================
1. ITEM 1 venv/import — pybullet version clash or FD/SymK not runnable in their
   .venv.  If unsolvable, B-full is blocked; escalate (do not silently re-scope).
2. ITEM 4/ITEM 7 default-client assumption — our oracle assumes the default
   pybullet client; their world may not be it.  P1 may need a guarded core edit.
3. ITEM 7 scene validity under a FIXED camera — released scenes were hidden to a
   MOVABLE camera; some may be trivial/unsolvable fixed.  Re-validate, pick valid
   problems, record them.
4. ITEM 11/ITEM 12 execution binding — simplified pose-set may not satisfy their
   step()/belief.update cleanly; their controllers need their-format params.
5. Two filesystems — TAMPURA must run from EXT4 (/root/tampura-work); our code is
   on /mnt/c.  Import our code via PYTHONPATH while cwd = their env repo.  Use
   ABSOLUTE paths for any file our code writes.
6. GUI under WSLg — teardown segfault is harmless; if the window never renders,
   hand the user the command (per the GUI rule).

================================================================================
OUT OF SCOPE THIS PHASE (LATER)
================================================================================
- Full solve: relocate cup -> sense reveals die -> pick(die) -> go-home, incl.
  the "which cup" replanning loop and give-up rule.
- Faithful robot motion via their pick/place controllers (execution option (a)).
- >=20-seed eval / head-to-head numbers (PHASE 4 — GATED).
- Any thesis-text edits (thesis/ is out of scope).
================================================================================

================================================================================
APPENDIX A — ITEM 3: PERCEPTION ADAPTER SURFACE (recon 2026-06-06; code-verified)
================================================================================
Exact BoxelTestEnv surface our perception stack touches.  ITEM 6 adapter must
expose ALL of this (P1), or we instantiate a real BoxelTestEnv (P2).

(1) OBJECT INVENTORY
  env.objects : Dict[str, ObjectInfo]                          boxel_env.py:509
    ObjectInfo (boxel_types.py:23): object_id:int  name:str  position:nd[3]
      orientation:nd[4] xyzw  size:nd[3] (w,h,d)  is_visible:bool
      is_occluder:bool  is_tray:bool=False
    oracle SKIPS names {"plane","table","robot"}               boxel_env.py:1639

(2) CAMERA (fixed = our model)
  env.camera_position : nd[3]   boxel_env.py:459 ;  env.camera_target : nd[3]

(3) TABLE GEOMETRY
  env.table_surface_height : float (ours 0.625+offset)         boxel_env.py:719
  env.table_x_range / table_y_range : WIDE logical range (shadow coverage)
  env._SAFE_TABLE_X_RANGE=(-0.1,0.70) _SAFE_TABLE_Y_RANGE=(-0.40,0.40) :815-816
    (free-space footprint = SAFE; shadow footprint = WIDE — keep both)

(4) METHODS CALLED ON env
  env.oracle_detect_objects(check_occlusion=True)              boxel_env.py:1620
      -> (visible_names, poses); uses self.objects, self.camera_position,
      DEFAULT-CLIENT p.getBasePositionAndOrientation / getAABB(:1651) /
      rayTestBatch(:1662).
  env.generate_free_space(known_obstacles, visualize=False)  (used by reboxelize)
  env.use_uniform_grid : bool (False = semantic octree)        boxel_env.py:549
  env.free_space_generator : FreeSpaceGenerator                boxel_env.py:538
      .min_resolution : float  (SET = effective_cell)   test_full_pipeline.py:527

(5) STANDALONE CONSUMERS (not env methods)
  ShadowCalculator(camera_position, table_surface_height,    shadow_calculator.py:23
      table_x_range, table_y_range).calculate_shadow_boxel(obj_boxel:BoxelData,
      obstacles:List[BoxelData]) ; surface-rest gate z_min<=table_h+0.01 (:73);
      DEFAULT-CLIENT p.rayTestBatch.
  BoxelRegistry() (boxel_data.py): .boxels dict of BoxelData OBJECT/SHADOW/
      FREE_SPACE ; .get_free_space_boxels()
  reboxelize_free_space(registry, env, boxel_centers:dict, viz,  reboxelize.py:18
      show_free) -> (new_ids, old_removed_ids)
  auto_cell = max_extent + 0.01 ; effective_cell = max(uniform,auto) | auto
      -> env.free_space_generator.min_resolution        test_full_pipeline.py:494-527

(6) BoxelData unit (boxel_data.py): center, extent(half), object_name,
    boxel_type, created_by_object, id.

(7) PYBULLET CLIENT — CRITICAL (risk #2)
  oracle(1651,1662) + shadow rayTestBatch pass NO physicsClientId -> DEFAULT
  client.  THEIR find_dice world is client_id=0 (verified in baseline State),
  created FIRST by our runner's env.initialize().
   => with NO second world, default-client calls naturally hit THEIR world.
   => a real BoxelTestEnv (P2) opens TWO more clients (boxel_env.py:513) ->
      "default" becomes ambiguous; P2 needs physicsClientId care.

ITEM 4 IMPLICATION: pipeline is bound to a full BoxelTestEnv (builds
shadow_calculator + free_space_generator in __init__; exposes generate_free_space).
  P1 = light adapter exposing (1)-(6), generate_free_space delegates to a
       FreeSpaceGenerator, reads THEIR bodies on the default client.  Faithful,
       no extra world; reproduces a broad surface; may need a guarded
       physicsClientId edit if the default-client assumption breaks.
  P2 = instantiate BoxelTestEnv, overwrite env.objects (+spawn matching bodies)
       from their poses; reuses all machinery but adds 2 clients (ambiguity).
================================================================================
