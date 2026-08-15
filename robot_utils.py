"""
Shared Franka Panda robot constants and low-level control utilities.

All joint limits, rest poses, and link indices for the Panda arm are defined
here once. Every module that needs robot parameters imports from this file.
"""

import logging
import numpy as np
import pybullet as p

logger = logging.getLogger(__name__)


# =============================================================================
# Franka Panda Constants (from the Franka Emika Panda datasheet)
# =============================================================================

ARM_JOINT_INDICES = [0, 1, 2, 3, 4, 5, 6]
FINGER_JOINTS = [9, 10]  # panda_finger_joint1, panda_finger_joint2
END_EFFECTOR_LINK = 11   # panda_grasptarget

JOINT_LIMITS_LOW = np.array([
    -2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973
])
JOINT_LIMITS_HIGH = np.array([
    2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973
])
JOINT_RANGES = JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW

REST_POSES = [0, -0.785, 0, -2.356, 0, 1.571, 0.785]


# =============================================================================
# Low-level control utilities
# =============================================================================

# =============================================================================
# Collision checking for motion planning
# =============================================================================

# Self-collision pairs to ignore: adjacent links in the Panda kinematic chain
# plus finger/hand pairs that naturally overlap.
_PANDA_IGNORED_SELF_PAIRS = frozenset({
    (-1, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
    (6, 7), (7, 8), (8, 9), (8, 10), (9, 10), (9, 11), (10, 11),
})


_PANDA_GRIPPER_LINKS = frozenset({6, 7, 8, 9, 10, 11})


# =============================================================================
# Reference-counted rendering lock
# =============================================================================
# PyBullet's COV_ENABLE_RENDERING toggle forces an OpenGL buffer swap.
# During planning, IK and collision-check functions are called thousands of
# times — each wrapping its resetJointState calls with rendering off/on.
# The high-frequency toggling causes visible scene flickering (audit #60).
#
# RenderingLock is a nestable context manager backed by a global counter.
# The first acquire (0 → 1) disables rendering; the last release (1 → 0)
# re-enables it.  Inner acquires/releases are no-ops.  Wrapping the entire
# planning phase with one outer lock eliminates all intermediate toggles.
#
# Assumes a single PyBullet physics client (true for this codebase).

_rendering_lock_count = 0


class RenderingLock:
    """Nestable context manager that suppresses PyBullet rendering toggles.

    Usage::

        with RenderingLock(physics_client):
            # rendering is disabled here; nested locks are no-ops
            ...
        # rendering re-enabled when the outermost lock exits
    """

    def __init__(self, physics_client: int = 0):
        self.physics_client = physics_client

    def __enter__(self):
        global _rendering_lock_count
        if _rendering_lock_count == 0:
            p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0,
                                       physicsClientId=self.physics_client)
        _rendering_lock_count += 1
        return self

    def __exit__(self, *exc):
        global _rendering_lock_count
        _rendering_lock_count -= 1
        if _rendering_lock_count == 0:
            p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1,
                                       physicsClientId=self.physics_client)
        return False


def is_config_collision_free(robot_id: int, joint_positions,
                              physics_client: int = 0,
                              ignored_bodies=None,
                              allow_gripper_collisions: bool = False,
                              log_collisions: bool = True,
                              held_body_ids=None,
                              held_body_ee_offset=None) -> bool:
    """
    Check whether a 7-DOF arm configuration is collision-free.

    Saves the robot's current joint state, sets the query configuration,
    runs broadphase + narrowphase collision detection, then restores the
    original state.  Contacts are filtered:

    * Self-contacts between adjacent / structurally overlapping links
      (defined in ``_PANDA_IGNORED_SELF_PAIRS``) are ignored.
    * The base link (-1) is excluded — it is fixed and rests on the
      mounting surface.
    * Bodies listed in *ignored_bodies* (e.g. a held object) are skipped.
    * When *allow_gripper_collisions* is True, collisions between the
      gripper links (7-11: wrist flange, hand, fingers, grasptarget)
      and non-robot bodies are also ignored.  Use this for pick/place
      endpoint checks where the gripper must enter cluttered space.

    When *held_body_ids* is provided, those bodies are repositioned to
    follow the end-effector at the hypothetical configuration and checked
    for environment collisions.  ``resetJointState`` does not move
    constraint-attached bodies, so we manually compute the EE world
    pose and teleport each held body there before collision detection.

    Rendering is managed via ``RenderingLock`` — safe to call both
    standalone and from within an outer lock (e.g. planning phase).

    Args:
        robot_id:                 PyBullet body ID of the robot.
        joint_positions:          Sequence of 7 target joint angles.
        physics_client:           PyBullet physics client ID.
        ignored_bodies:           Optional set/frozenset of body IDs to skip.
        allow_gripper_collisions: If True, exempt gripper links from
                                  environment collision reporting.
        log_collisions:           If True, log the first collision found
                                  at DEBUG level.
        held_body_ids:            Optional set/frozenset of body IDs
                                  attached to the gripper.  These are
                                  repositioned to the EE pose and checked
                                  for environment collisions.
        held_body_ee_offset:      Optional [x, y, z] offset from the EE
                                  to the held object center (the grasp
                                  clearance).  The held body is placed at
                                  ``ee_pos - offset`` in the EE frame.
                                  Without this, the body is placed at the
                                  EE origin, which is too high for
                                  top-down grasps.

    Returns:
        True if the configuration has no disallowed contacts.
    """
    if ignored_bodies is None:
        ignored_bodies = frozenset()
    if held_body_ids is None:
        held_body_ids = frozenset()

    saved = None
    saved_held = {}
    with RenderingLock(physics_client):
        try:
            saved = [p.getJointState(robot_id, i, physicsClientId=physics_client)[0]
                     for i in ARM_JOINT_INDICES]

            for i, angle in zip(ARM_JOINT_INDICES, joint_positions):
                p.resetJointState(robot_id, i, angle,
                                  physicsClientId=physics_client)

            if held_body_ids:
                ee_state = p.getLinkState(robot_id, END_EFFECTOR_LINK,
                                         computeForwardKinematics=True,
                                         physicsClientId=physics_client)
                ee_pos, ee_orn = ee_state[4], ee_state[5]

                if held_body_ee_offset is not None:
                    offset_local = [-held_body_ee_offset[0],
                                    -held_body_ee_offset[1],
                                    -held_body_ee_offset[2]]
                    held_pos, held_orn = p.multiplyTransforms(
                        ee_pos, ee_orn, offset_local, [0, 0, 0, 1])
                else:
                    held_pos, held_orn = ee_pos, ee_orn

                for hid in held_body_ids:
                    saved_held[hid] = p.getBasePositionAndOrientation(
                        hid, physicsClientId=physics_client)
                    p.resetBasePositionAndOrientation(
                        hid, ee_pos, ee_orn,
                        physicsClientId=physics_client)

            p.performCollisionDetection(physicsClientId=physics_client)
            contacts = p.getContactPoints(bodyA=robot_id,
                                          physicsClientId=physics_client)

            for c in contacts:
                body_a, body_b, link_a, link_b = c[1], c[2], c[3], c[4]

                if body_a == robot_id and body_b == robot_id:
                    pair = (min(link_a, link_b), max(link_a, link_b))
                    if pair not in _PANDA_IGNORED_SELF_PAIRS:
                        if log_collisions:
                            logger.debug("collision: self-contact links (%d, %d)",
                                         link_a, link_b)
                        return False
                    continue

                other = body_b if body_a == robot_id else body_a
                robot_link = link_a if body_a == robot_id else link_b

                if other in ignored_bodies:
                    continue
                if robot_link == -1:
                    continue
                if allow_gripper_collisions and robot_link in _PANDA_GRIPPER_LINKS:
                    continue

                if log_collisions:
                    logger.debug("collision: robot link %d <-> body %d (link %d)",
                                 robot_link,
                                 other,
                                 link_b if body_a == robot_id else link_a)
                return False

            for hid in held_body_ids:
                held_contacts = p.getContactPoints(bodyA=hid,
                                                   physicsClientId=physics_client)
                for c in held_contacts:
                    other = c[2] if c[1] == hid else c[1]
                    if other == robot_id:
                        continue
                    if other in ignored_bodies:
                        continue
                    if log_collisions:
                        logger.debug("collision: held body %d <-> body %d",
                                     hid, other)
                    return False

            return True
        finally:
            if saved is not None:
                for i, angle in zip(ARM_JOINT_INDICES, saved):
                    p.resetJointState(robot_id, i, angle,
                                      physicsClientId=physics_client)
            for hid, (pos, orn) in saved_held.items():
                p.resetBasePositionAndOrientation(
                    hid, pos, orn, physicsClientId=physics_client)


def is_path_collision_free(robot_id: int, q_start, q_end,
                            physics_client: int = 0, n_checks: int = 8,
                            ignored_bodies=None,
                            allow_gripper_collisions: bool = False,
                            held_body_ids=None,
                            held_body_ee_offset=None) -> bool:
    """
    Check a straight-line joint-space path for collisions.

    Evaluates *n_checks* evenly-spaced configurations (including the
    endpoints) along the linear interpolation from *q_start* to *q_end*.

    Args:
        robot_id:        PyBullet body ID of the robot.
        q_start:         Start joint positions (array-like, length 7).
        q_end:           End joint positions (array-like, length 7).
        physics_client:  PyBullet physics client ID.
        n_checks:        Number of intermediate configurations to test.
                         Default 8 matches BoxelStreams.RRT_EDGE_CHECKS —
                         see the RRT-Connect parameter block in streams.py
                         for the empirical-tuning rationale.
        ignored_bodies:  Optional set/frozenset of body IDs to skip.
        allow_gripper_collisions: If True, exempt gripper/wrist links
            from environment collision reporting (same as in
            is_config_collision_free).
        held_body_ids:   Optional set/frozenset of body IDs attached to
            the gripper, passed through to is_config_collision_free.
        held_body_ee_offset: Optional [x, y, z] grasp offset, passed
            through to is_config_collision_free.

    Returns:
        True if every sampled configuration is collision-free.
    """
    q_s = np.asarray(q_start, dtype=float)
    q_e = np.asarray(q_end, dtype=float)
    with RenderingLock(physics_client):
        for t in np.linspace(0.0, 1.0, n_checks):
            q = (1.0 - t) * q_s + t * q_e
            if not is_config_collision_free(robot_id, q, physics_client,
                                            ignored_bodies,
                                            allow_gripper_collisions=allow_gripper_collisions,
                                            log_collisions=False,
                                            held_body_ids=held_body_ids,
                                            held_body_ee_offset=held_body_ee_offset):
                return False
        return True


# =============================================================================
# Runtime collision monitoring (execution phase)
# =============================================================================

def detect_execution_collisions(robot_id: int,
                                physics_client: int = 0,
                                held_body_id: int = None,
                                support_body_ids: frozenset = frozenset(),
                                label: str = "",
                                body_names: dict = None) -> list:
    """
    Check the live simulation state for collisions and print any found.

    Unlike the planning-time ``is_config_collision_free``, this operates
    on the *actual* physics state — no joint save/restore or body
    repositioning is needed because ``stepSimulation`` already keeps
    constrained bodies in the correct position.

    Args:
        robot_id:         PyBullet body ID of the robot.
        physics_client:   PyBullet physics client ID.
        held_body_id:     Body ID currently attached to the gripper via
                          constraint, or None if the gripper is empty.
        support_body_ids: Body IDs of surfaces to ignore (table, ground).
        label:            Context string printed with each collision
                          (e.g. "move to free_001").
        body_names:       Optional {body_id: name} dict for readable output.

    Returns:
        List of collision description strings (empty = no collisions).
    """
    if body_names is None:
        body_names = {}

    def _name(bid):
        return body_names.get(bid, f"body_{bid}")

    p.performCollisionDetection(physicsClientId=physics_client)

    collisions = []
    skip = support_body_ids | ({held_body_id} if held_body_id is not None else set())

    contacts = p.getContactPoints(bodyA=robot_id, physicsClientId=physics_client)
    for c in contacts:
        body_a, body_b, link_a, link_b = c[1], c[2], c[3], c[4]
        if body_a == robot_id and body_b == robot_id:
            pair = (min(link_a, link_b), max(link_a, link_b))
            if pair in _PANDA_IGNORED_SELF_PAIRS:
                continue
            msg = f"robot self-collision links ({link_a}, {link_b})"
            collisions.append(msg)
            continue
        other = body_b if body_a == robot_id else body_a
        robot_link = link_a if body_a == robot_id else link_b
        if other in skip or robot_link == -1:
            continue
        msg = f"robot link {robot_link} <-> {_name(other)}"
        collisions.append(msg)

    if held_body_id is not None:
        held_name = _name(held_body_id)
        held_contacts = p.getContactPoints(bodyA=held_body_id,
                                           physicsClientId=physics_client)
        for c in held_contacts:
            other = c[2] if c[1] == held_body_id else c[1]
            if other == robot_id or other in support_body_ids:
                continue
            if other == held_body_id:
                continue
            msg = f"{held_name} (held) <-> {_name(other)}"
            collisions.append(msg)

    if collisions:
        tag = f" [{label}]" if label else ""
        for msg in collisions:
            print(f"    *** COLLISION{tag}: {msg} ***")
        logger.warning("execution collisions%s: %s", tag, collisions)

    return collisions


# =============================================================================
# Inverse kinematics
# =============================================================================

def solve_ik(robot_id: int, target_pos: np.ndarray,
             target_orn=None, physics_client: int = 0,
             seed=None):
    """
    Null-space IK with configurable seed for consistent results.

    Saves the robot's current joint state, resets to ``seed`` (or
    ``REST_POSES`` if no seed is given) to give the iterative solver
    a deterministic starting point, runs IK with null-space bias, then
    restores the original state.

    Without a seed the call is independent of where execution left the
    arm — critical for fresh replans.  With a seed the call preserves
    the IK branch the seed already lives in — used by execute_pick /
    execute_place / execute_stack to lower the arm a couple of
    centimetres into contact without snapping to a different IK
    solution between move and contact (audit #37 / #38).

    Applies the same validation as ``BoxelStreams._pybullet_ik()`` in
    streams.py: null-check, joint-limit check (0.1 rad tolerance), and
    clipping.  Returns ``None`` on failure so callers can handle it.

    Args:
        robot_id: PyBullet body ID of the robot.
        target_pos: Desired end-effector position [x, y, z].
        target_orn: Desired orientation as quaternion [x, y, z, w] or
                    any sequence accepted by PyBullet.
                    Defaults to gripper pointing straight down.
        physics_client: PyBullet physics client ID.
        seed:   Optional joint-angle seed (length 7, list or ndarray).
                When provided, the solver resets the model to ``seed``
                and uses it as ``restPoses`` for the null-space bias —
                so the returned solution stays in the same IK branch.
                When ``None`` (default), behaviour is identical to the
                previous version: reset to ``REST_POSES``.

    Returns:
        Array of 7 joint angles, or ``None`` if IK failed.
    """
    if target_orn is None:
        target_orn = p.getQuaternionFromEuler([0, np.pi, 0])

    orn_list = (target_orn.tolist() if isinstance(target_orn, np.ndarray)
                else list(target_orn))

    seed_poses = (list(seed) if seed is not None else list(REST_POSES))

    saved = None
    with RenderingLock(physics_client):
        try:
            saved = [p.getJointState(robot_id, i,
                                     physicsClientId=physics_client)[0]
                     for i in ARM_JOINT_INDICES]

            for i, angle in zip(ARM_JOINT_INDICES, seed_poses):
                p.resetJointState(robot_id, i, angle,
                                  physicsClientId=physics_client)

            joint_positions = p.calculateInverseKinematics(
                robot_id, END_EFFECTOR_LINK,
                target_pos.tolist(), orn_list,
                lowerLimits=JOINT_LIMITS_LOW.tolist(),
                upperLimits=JOINT_LIMITS_HIGH.tolist(),
                jointRanges=JOINT_RANGES.tolist(),
                restPoses=seed_poses,
                maxNumIterations=100,
                residualThreshold=1e-4,
                physicsClientId=physics_client,
            )

            if joint_positions is None or len(joint_positions) < 7:
                return None

            arm_joints = np.array(joint_positions[:7])

            # 0.1 rad tolerance (~5.7°) accommodates PyBullet's iterative IK
            # solver, which can slightly overshoot joint limits.  Solutions
            # within tolerance are clipped; beyond it they're rejected.
            if np.any(arm_joints < JOINT_LIMITS_LOW - 0.1) or \
               np.any(arm_joints > JOINT_LIMITS_HIGH + 0.1):
                return None

            arm_joints = np.clip(arm_joints, JOINT_LIMITS_LOW,
                                 JOINT_LIMITS_HIGH)

            # FK verification (#P1, 2026-08-15): clipping (and reach-edge
            # convergence failures) can leave a solution whose ACTUAL EE
            # pose is centimetres from the target — under the weld this
            # merely looked sloppy, but a friction grasp descending 60 mm
            # off-centre bulldozes the scene (random-pairs seed 3: the
            # arm pressed onto a tall occluder's top edge at the same
            # wrong pose on every replan).  Set the candidate joints,
            # read the EE link pose, and reject solutions more than
            # 10 mm from the Cartesian target so callers get an honest
            # IK failure -> abort -> replan instead of a silently wrong
            # config.  The model state is restored by the finally block
            # regardless.
            for i, angle in zip(ARM_JOINT_INDICES, arm_joints):
                p.resetJointState(robot_id, i, angle,
                                  physicsClientId=physics_client)
            fk_pos = p.getLinkState(robot_id, END_EFFECTOR_LINK,
                                    physicsClientId=physics_client)[0]
            fk_err = float(np.linalg.norm(
                np.asarray(fk_pos) - np.asarray(target_pos, dtype=float)))
            if fk_err > 0.010:
                logger.debug("solve_ik: rejected solution with FK error "
                             "%.1f mm for target %s", fk_err * 1000,
                             np.asarray(target_pos).tolist())
                return None

            return arm_joints

        except Exception as e:
            logger.warning("solve_ik failed for pos=%s: %s", target_pos.tolist(), e)
            return None
        finally:
            if saved is not None:
                for i, angle in zip(ARM_JOINT_INDICES, saved):
                    p.resetJointState(robot_id, i, angle,
                                      physicsClientId=physics_client)


def move_robot_smooth(robot_id: int, target_joints, gui: bool = False,
                      steps: int = 60):
    """
    Smoothly interpolate joint positions from the current state to
    *target_joints*.

    Args:
        robot_id: PyBullet body ID of the robot.
        target_joints: Sequence of 7 target joint angles.
        gui: If True, sleep between steps for real-time visualisation.
        steps: Number of interpolation steps.
    """
    import time
    current = [p.getJointState(robot_id, i)[0] for i in range(7)]
    for t in range(steps):
        alpha = (t + 1) / steps
        interp = [(1 - alpha) * c + alpha * tgt
                   for c, tgt in zip(current, target_joints)]
        for i in range(7):
            # 240 N·m is the Franka Emika Panda's peak joint torque for
            # joints 1-4 (per datasheet); sufficient for position control.
            p.setJointMotorControl2(robot_id, i, p.POSITION_CONTROL,
                                    targetPosition=interp[i], force=240)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 120)

    # Endpoint convergence hold (#P1, 2026-08-15): streamed
    # interpolation can undershoot the FINAL target by 10-20 mm of EE
    # travel at awkward postures — tolerable for transit, fatal for a
    # friction grasp that needs lateral centering within the ~10 mm
    # descent clearance (grip verification was tripping on exactly
    # this: [#P1-diag] ee_xy_err 14-21 mm on the missed picks).  Hold
    # the final target until the arm converges in joint space or a
    # short cap expires; near-instant when the stream already arrived.
    # Same endpoint-hold pattern the archived bridge's
    # follow_trajectory used for its grasp descents
    # (archive/tampura_bridge_v1/execution_boxel.py).
    target = [float(v) for v in target_joints]
    for _ in range(120):
        cur = [p.getJointState(robot_id, i)[0] for i in range(7)]
        if max(abs(c - t) for c, t in zip(cur, target)) < 2e-3:
            break
        for i in range(7):
            p.setJointMotorControl2(robot_id, i, p.POSITION_CONTROL,
                                    targetPosition=target[i], force=240)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 120)


def open_gripper(robot_id: int, gui: bool = False):
    """Open the Panda gripper to URDF max (0.04 m per finger) through
    the finger motors — a real release, no teleport.

    #P1 friction grasp (2026-08-15): the audit-#81 resetJointState
    teleport is removed.  It existed because the JOINT_FIXED weld
    pinned the held object rigidly between the pads while
    POSITION_CONTROL tried to drag them apart — the motor lost that
    fight (seed-999 log run_2026-05-15_18-57-21: fingers stalled short
    of 0.04, pads grazed the cube during retraction).  With the weld
    gone the object is held by pad friction alone: opening withdraws
    each pad NORMAL to the face it presses on, so breaking contact is
    not a friction fight and plain position control reaches 0.04.
    200 N motor budget over 160 steps (~0.66 s at 240 Hz); the caller
    adds settle time (base_settle_steps in _release_and_verify_drop)
    for the object to fall free.

    User direction 2026-05-15 still honoured: no "letting-go grasp" is
    sampled — the fingers just open as maximally as they can.

    A stall short of 0.038 prints a loud warning; the release verify
    gate in _release_and_verify_drop reads the same joint states and
    fails the release if the fingers did not physically open.
    """
    import time
    for _ in range(160):
        p.setJointMotorControl2(robot_id, FINGER_JOINTS[0],
                                p.POSITION_CONTROL,
                                targetPosition=0.04, force=200)
        p.setJointMotorControl2(robot_id, FINGER_JOINTS[1],
                                p.POSITION_CONTROL,
                                targetPosition=0.04, force=200)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 120)
    finger_pos = [p.getJointState(robot_id, fj)[0] for fj in FINGER_JOINTS]
    if min(finger_pos) < 0.038:
        print(f"    WARNING: open_gripper fingers stalled at "
              f"[{finger_pos[0]:.4f}, {finger_pos[1]:.4f}] "
              f"(target 0.04) — release may be incomplete")


def close_gripper(robot_id: int, gui: bool = False,
                  target_finger_pos: float = 0.01, force: float = 40):
    """Close the Panda gripper toward ``target_finger_pos`` per finger.

    #P1 friction grasp (2026-08-15): close_gripper is now the LOAD
    PATH.  The JOINT_FIXED weld that used to provide all grip
    stability is gone; the pads must build and HOLD a normal force so
    that pad friction (μ = 1.2, boxel_env finger-pad setup) carries
    the object through every subsequent motion.  execute_pick passes a
    target slightly INSIDE the object surface (cube_hw − 3 mm): the
    pads stop at the surface, the residual position error keeps the
    motors pressing at up to ``force`` N, and PyBullet motor targets
    persist across stepSimulation — the squeeze stays active during
    transport with no re-assertion needed.

    40 N default sits inside the real Panda's grasp envelope (70 N
    continuous / 140 N peak) and yields ~48 N of tangential friction
    capacity per pad at μ 1.2 — far above the ≤ 5 N scene-object
    weights, with margin for transport accelerations.

    Audit #81 history (partially superseded): force was dropped
    50 → 10 N when the weld carried the load and the close was
    cosmetic ("we dont want smashing", user 2026-05-15).  The
    no-smashing contract still holds — the target sits 3 mm inside
    the surface, not 2 cm as pre-#81, so the pads press without
    visibly deforming the scene; but 10 N left no margin once the
    weld stopped carrying the load, hence 40 N.
    """
    import time
    for _ in range(60):
        p.setJointMotorControl2(robot_id, FINGER_JOINTS[0],
                                p.POSITION_CONTROL,
                                targetPosition=target_finger_pos,
                                force=force)
        p.setJointMotorControl2(robot_id, FINGER_JOINTS[1],
                                p.POSITION_CONTROL,
                                targetPosition=target_finger_pos,
                                force=force)
        p.stepSimulation()
        if gui:
            time.sleep(1 / 120)
