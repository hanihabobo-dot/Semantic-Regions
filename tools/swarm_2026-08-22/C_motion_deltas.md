# Agent C — Motion / The Violent Throw

Investigation of `logs/run_2026-08-22_17-14-10/` (GUI, seed 0, goal=holding,
random-pairs, 3 occluders, target blue_object). Focus: whether the
fixed-step-count executor produces a violent joint-space swing on the
smoothed RRT transit that flings the grasped orange_object off the arm
(log:145, `pad_normal_force=0.00N` at place entry).

All claims are tagged **CONFIRMED** (read from source / log, or reproduced
by `tools/swarm_2026-08-22/probe_C_motion.py`, a pure-pybullet DIRECT probe
— no `test_full_pipeline.py`, no pddlstream, no FastDownward) or
**HYPOTHESIS** (reasoning only). Probe stdout and full per-trial JSON are at
`tools/swarm_2026-08-22/probe_C_motion_output.json`.

---

## 1. `move_robot_smooth` and its call site — CONFIRMED

**Signature** (`robot_utils.py:578-579`):
```python
def move_robot_smooth(robot_id: int, target_joints, gui: bool = False,
                      steps: int = 60, settle: bool = False):
```
Default `steps=60`.

**Body** (`robot_utils.py:598-611`): linear interpolation from the robot's
*current* joint state to `target_joints` over `steps` equal increments —
`alpha = (t+1)/steps` for `t in range(steps)`. **One `p.stepSimulation()`
call per interpolation step** (`robot_utils.py:609`), i.e. exactly `steps`
physics steps per invocation, regardless of how far apart the start and
target configs are in joint space.

**Controller** (`robot_utils.py:607-608`):
```python
p.setJointMotorControl2(robot_id, i, p.POSITION_CONTROL,
                        targetPosition=interp[i], force=240)
```
`p.POSITION_CONTROL` (PD position servo) for each of the 7 arm joints.
`force=240` is the only limit passed — **no `maxVelocity` argument is set
anywhere in `move_robot_smooth`**, so PyBullet's internal PD servo is free
to drive the joint at whatever angular rate is needed to close the gap to
`targetPosition` within the 240 N·m torque budget over the timestep. There
is no software velocity clamp in this path at all.

Incidental finding: `force=240` is applied uniformly to all 7 joints. The
code comment (`robot_utils.py:605-606`) justifies 240 N·m against the
Panda's joints 1-4 datasheet peak (87 N·m nominal, so 240 is already a
large margin over spec for those); but joints 5-7 (wrist) carry only a
12 N·m real effort limit per the URDF (`panda.urdf:162,189,216`,
`wsl_env/.../pybullet_data/franka_panda/panda.urdf`) — the commanded force
budget on the wrist is ~20x its real hardware limit. Not the direct cause
of the throw (pybullet's motor is not fighting a real robot's amplifier
saturation), but consistent with "nothing here would prevent a violent
wrist swing."

**Sim timestep** — CONFIRMED by exhaustive grep: `setTimeStep` and
`setPhysicsEngineParameter` have **zero matches anywhere in the repo**
(`*.py`, checked from repo root). PyBullet's default timestep applies:
**1/240 s (240 Hz)**. `boxel_env.py:479,495,513` calls `p.connect(...)`
with no timestep override.

**Call site** (`test_full_pipeline.py:1346-1350`, the `move` action
dispatcher):
```python
last_wp_idx = len(traj.waypoints) - 1
for wi, wp in enumerate(traj.waypoints[1:], start=1):
    move_robot_smooth(robot_id, wp.joint_positions,
                      gui, steps=30,
                      settle=(wi == last_wp_idx))
```
This **overrides `move_robot_smooth`'s own default of 60 with a hardcoded
`steps=30`**, applied identically to *every* consecutive waypoint pair in
*every* trajectory the dispatcher executes — whether that pair came from a
10-waypoint linear interpolation (`streams.py:916-928`, evenly spaced,
small per-pair deltas by construction) or from a 3-waypoint
shortcut-smoothed RRT path (`streams.py:890-897`, where a single pair can
span what used to be several 0.2-rad-bounded RRT edges). This confirms the
hypothesis literally: **a fixed step count per waypoint pair, independent
of joint-space distance.**

(Other callers of `move_robot_smooth` — the pick-descent alignment at
`execution.py:981` and the contact descent at `execution.py:1017` — call it
with no `steps` kwarg, i.e. they get the *function's own* default of 60,
not 30. Only the transit dispatcher hardcodes 30. Not implicated in this
transit's throw since contact descents use `settle=True` and are IK-seeded
short hops, but noted as an inconsistency.)

---

## 2. `streams.py` RRT + shortcut smoothing — CONFIRMED

**RRT parameters** (`streams.py:725-730`):
```python
RRT_MAX_ITERATIONS = 2000
RRT_STEP_SIZE = 0.2          # max joint displacement per extend (rad)
RRT_GOAL_BIAS = 0.05
RRT_EDGE_CHECKS = 8          # collision samples per edge
RRT_CONNECT_ATTEMPTS = 50
SMOOTH_ATTEMPTS = 75         # shortcut smoothing iterations
```

`_steer` (`streams.py:952-962`) bounds every **raw RRT tree edge** to at
most `RRT_STEP_SIZE = 0.2` rad on any joint — this is why the raw RRT path
in the log and in every probe trial has per-pair deltas capped at ~0.2 rad
(see §3).

`_smooth_path` (`streams.py:1101-1128`), called from `plan_motion` at
`streams.py:894-897` right after RRT succeeds:
```python
for _ in range(self.SMOOTH_ATTEMPTS):        # 75 iterations
    if len(smoothed) <= 2:
        break
    i = random.randint(0, len(smoothed) - 3)
    j = random.randint(i + 2, len(smoothed) - 1)
    if is_path_collision_free(self.robot_id, smoothed[i], smoothed[j],
                              pc, self.RRT_EDGE_CHECKS, ...):
        smoothed = smoothed[:i + 1] + smoothed[j:]
```
This picks two **non-adjacent** waypoints `i < j` and, if the *straight
joint-space line* between them passes an 8-sample collision check
(`is_path_collision_free`, `robot_utils.py:271-330`, same
`RRT_EDGE_CHECKS=8`), **splices out everything between them** and replaces
it with that one direct edge. Critically: **`is_path_collision_free` never
bounds the per-joint distance of the edge it certifies** — it only checks
that 8 evenly-spaced samples along the line are collision-free. A shortcut
that collapses 6 of 7 raw `0.2`-rad-bounded RRT edges into one edge is
certified exactly the same way as a short one, with no cap on the
resulting joint-space span. This is the mechanism: **smoothing removes the
`RRT_STEP_SIZE` bound that the RRT tree itself enforced**, and the
downstream executor has no bound of its own either (§1).

---

## 3. Probe reproduction — CONFIRMED

`tools/swarm_2026-08-22/probe_C_motion.py` builds the seed-0 scene DIRECT
(`random_pairs_scene(n_occluders=3, extra_distractors=0, seed=0)`),
reconstructs the registry (object + shadow boxels + merged free space, same
order as `test_full_pipeline.py` Phase 2/3) so that boxel id numbering
matches the run, then:

1. Computes `q_kin_orange_object_2`-equivalent (pick approach) via
   `streams.compute_kin_solution('orange_object','orange_object', grasp)`.
2. **Physically executes** `execution.execute_pick(...)` (same function the
   real dispatcher calls at `test_full_pipeline.py:1437-1439`) to get the
   REAL post-pick joint state (`post_pick_contact`), not an approximation.
   Grip verified in the probe: `pad_normal_force=106.74N` (probe stdout) —
   consistent with the run's `112.25N` (log:133).
3. Resolves `free_005` from the registry — **confirmed identical id** to
   the run (`used_free_boxel_id=free_005`, `id_matches_log=True` in
   `probe_C_motion_output.json`) — and computes
   `q_kin_orange_object_3`-equivalent via
   `compute_kin_solution('orange_object','free_005', grasp)`.
4. Builds `post_pick_contact_runtime` exactly as
   `test_full_pipeline.py:1321-1327` does, derives `held_body_ids`/
   `path_ignored` exactly as `plan_motion` does (`streams.py:773-821`):
   probe reports `held_body_ids=[5] path_ignored=[0, 1, 5]` — **exact match**
   to log:138 `endpoint_ignored=[0, 1, 5] ... held=[5]`.
5. Confirms `direct path collision-free? False` — matches log:139 "direct
   path blocked — running RRT-Connect".
6. Calls `streams._rrt_connect` then `streams._smooth_path` directly (the
   same two calls `plan_motion` makes internally, `streams.py:879-897`)
   across **7 RNG realizations** (seeds 1000-1006; task required ≥5).

### Results (full data: `probe_C_motion_output.json`)

| seed | raw wps | smoothed wps | raw worst Δ/pair (rad) | raw worst Δ/step@30 (rad) | raw vel (rad/s) | smoothed worst Δ/pair (rad) | smoothed worst Δ/step@30 (rad) | smoothed vel (rad/s) |
|---|---|---|---|---|---|---|---|---|
| 1000 | 8  | 3 | 0.200 | 0.00667 | 1.600 | 1.000 | 0.03333 | 8.000 |
| 1001 | 9  | 3 | 0.200 | 0.00667 | 1.600 | 1.104 | 0.03682 | 8.836 |
| 1002 | 10 | 3 | 0.200 | 0.00667 | 1.600 | 0.823 | 0.02744 | 6.585 |
| 1003 | 12 | 3 | 0.200 | 0.00667 | 1.600 | 0.991 | 0.03302 | 7.925 |
| 1004 | 10 | 3 | 0.200 | 0.00667 | 1.600 | 1.074 | 0.03579 | 8.589 |
| 1005 | 8  | 3 | 0.200 | 0.00667 | 1.600 | 0.767 | 0.02557 | 6.138 |
| 1006 | 8  | 3 | 0.200 | 0.00667 | 1.600 | **1.146** | **0.03819** | **9.164** |

Three of seven trials (seeds 1000, 1005, 1006) reproduce the log's exact
**"RRT path 8 wps → smoothed 3 wps"** (log:111, log:140). The other four
land at 9, 10, 10, 12 raw waypoints — RRT-Connect is stochastic (random
tree growth), so the log's specific 8-waypoint raw path is one realization
among several nearby ones, all of which smooth down to 3 waypoints (2
executed segments) with a large collapsed first edge every time.

**Worst case across all 7 trials** (seed 1006, smoothed pair 0 — joint
index 1, i.e. `panda_joint2`):
- Pair Δ: **1.14556 rad** in one waypoint-to-waypoint hop.
- Per-step Δ at the executor's fixed `steps=30`: **0.03819 rad/step**.
- Implied joint velocity at `dt=1/240s`: **9.164 rad/s**.
- Median across the 7 trials: pair Δ 1.000 rad, per-step Δ 0.03333 rad,
  velocity **8.0 rad/s**.

**Contrast — the docile linear move** (`q_home → q_pick`, the SAME
executor and SAME `steps=30`, log:107-108 "direct path clear"): worst pair
Δ **0.320 rad**, per-step Δ **0.01068 rad**, velocity **2.563 rad/s** — this
sits *inside* `panda_joint7`'s real 2.610 rad/s URDF limit
(`panda.urdf:216`). The smoothed-RRT transit's 9.164 rad/s is **3.6-4.2x
over `panda_joint2`'s real 2.175 rad/s URDF limit** (`panda.urdf:80`) and
**4.6-9.2x over the task's suggested 1-2 rad/s sane wrist target**. The
docile 10-waypoint linear moves stay physically plausible under the exact
same fixed schedule; only the smoothed-RRT segment blows past hardware
limits — because smoothing (§2), not the fixed step count alone, is what
removes the joint-space bound.

**Mechanism, stated precisely from the data**: the raw RRT path's first 6
of 7 edges (each ≤0.2 rad, `RRT_STEP_SIZE`) get spliced into **one** edge by
`_smooth_path` (seed 1006: 6 edges of ~0.2 rad ≈ 1.2 rad total collapse
into a single 1.146-rad edge). The executor then interpolates that single
edge over the **same fixed 30 steps** it would have used for a single
0.2-rad raw edge — i.e., ~6x the joint-space distance in the same number
of physics steps and the same wall-clock time. This is exactly what flings
a friction-held object: `p.setJointMotorControl2(POSITION_CONTROL,
force=240)` with no velocity cap chases a per-step target that is ~6x
further away than the schedule was tuned for, at joint 2 (shoulder lift) —
a large, fast swing of the whole arm, not a wrist flick.

---

## 4. Fix quantification — CONFIRMED (probe-measured, this transit)

Velocity-bounded interpolation (steps scaled so `max|Δ|/steps ≤ cap`),
applied to the **smoothed** (as-executed) 2-pair path, across the 7 trials:

| cap (rad/step) | total steps (min/median/max) | wall-clock (median, `dt=1/240s`) | vs current fixed (60 steps = 30×2 pairs, 0.250 s) |
|---|---|---|---|
| 0.02 | 58 / 65 / 81 | 0.271 s | **slightly more** than current (65 vs 60) |
| 0.05 | 24 / 27 / 33 | 0.113 s | **~2.2x fewer** steps |
| 0.10 | 12 / 14 / 17 | 0.058 s | **~4.3x fewer** steps |

Note the non-monotonic-looking result at `cap=0.02`: the current fixed
`steps=30` is *already* too coarse for the 1.1-1.15-rad collapsed edge
(0.0382 rad/step, §3) — a genuinely safe 0.02 rad/step cap needs **more**
steps than 30 on that specific edge (55-57 steps), while the second,
smaller edge (~0.2 rad, matching the raw RRT bound) only needs ~10-14
steps at that same cap. This shows the fix is not "raise the fixed
step count" — a single larger fixed number still either wastes steps on
short pairs or under-serves long ones. **Per-pair adaptive scaling (the
velocity-bounded interpolation itself) is what's needed**, not a bigger
constant.

### Run-wide impact — CONFIRMED (waypoint counts) / HYPOTHESIS (extrapolated deltas for unreproduced pairs)

Parsed directly from `logs/run_2026-08-22_17-14-10/run_2026-08-22_17-14-10.log`
(`probe_C_motion.py`'s `parse_log_moves`):

- **12** `move` actions dispatched total.
- **11** are 10-waypoint **linear** moves ("direct path clear") — orange_object,
  green_object, free_003, shadow_of_green_object (×3), red_object, free_011,
  shadow_of_red_object (×3). 9 pairs each → **99 linear pairs**.
- **1** is the 3-waypoint **smoothed-RRT** move (to free_005) — **2 pairs**.
- The two `"RRT path N wps → smoothed M wps"` log lines (log:111, log:140)
  are both for this SAME orange→free_005 transit (once at planning time,
  once at the runtime replan that actually executes) — **every other
  transit in the entire failing run used a direct linear path**. This is
  not a broad problem across the run; it is concentrated in exactly the
  one transit that also happens to be the one that lost the grasp.

Fixed-schedule cost for the whole run (CONFIRMED: `steps=30` uniformly,
`test_full_pipeline.py:1346-1350`, applied to every pair regardless of
source):
```
(99 linear pairs + 2 smoothed pairs) x 30 steps = 3030 steps
3030 x (1/240 s) = 12.62 s of stepSimulation
```
The 99 linear pairs were **not** re-simulated per-pair in this probe (would
require replaying all 7 remaining plan states — out of the probe's scope);
their per-pair deltas are HYPOTHESIS-by-analogy only, but the *one* linear
pair actually measured (§3 contrast, `q_home→q_pick`, 2.563 rad/s worst)
stays under the real joint-velocity limits, and by construction
(`_linear_trajectory`, `streams.py:916-928`, 9 *uniform* segments) every
other direct-path linear move distributes its total reach evenly — the
mechanism that produces a >1-rad single-pair jump (shortcut smoothing
collapsing several RRT edges into one) structurally cannot occur on a
linear-interpolation path. So a velocity cap would leave the 99 linear
pairs close to unchanged (already within safe rad/step, confirmed for one
representative case) while fixing only the 2 pathological smoothed pairs —
at a wall-clock cost of roughly **+0.02 s (cap 0.02) to -0.19 s (cap 0.10)**
relative to the current 0.25 s spent on those 2 pairs, against a ~12.6 s
run-wide total. **Net runtime impact of the fix: negligible (well under
1% of total dispatched-motion wall-clock), because only 2 of 101 total
executed waypoint pairs in this entire failing run are affected.**

---

## Summary of files and lines

- `robot_utils.py:578-639` — `move_robot_smooth` (signature, controller,
  step loop, settle hold).
- `robot_utils.py:271-330` — `is_path_collision_free` (8-sample edge check,
  no distance bound).
- `test_full_pipeline.py:1300-1369` — move-action dispatcher; `1346-1350`
  is the fixed `steps=30` call site.
- `streams.py:725-730` — RRT/smoothing constants (`RRT_STEP_SIZE=0.2`,
  `SMOOTH_ATTEMPTS=75`).
- `streams.py:952-962` — `_steer` (bounds raw RRT edges to 0.2 rad).
- `streams.py:1101-1128` — `_smooth_path` (unbounded shortcut splice).
- `streams.py:773-897` — `plan_motion` (ignore/held-set derivation, direct
  path check, RRT dispatch, smoothing dispatch).
- `wsl_env/lib/python3.10/site-packages/pybullet_data/franka_panda/panda.urdf:53,80,108,135,162,189,216`
  — real joint effort/velocity limits (87 N·m / 2.175 rad/s for joints
  1-4, 12 N·m / 2.610 rad/s for joints 5-7).
- `logs/run_2026-08-22_17-14-10/run_2026-08-22_17-14-10.log:106-145` —
  the failing transit end-to-end (kin solve, plan_motion, execution,
  grip loss).
- `tools/swarm_2026-08-22/probe_C_motion.py` — reproduction probe (this
  investigation).
- `tools/swarm_2026-08-22/probe_C_motion_output.json` — full per-trial
  numeric data (all 7 trials, all waypoint pairs, all 7 joints).
