"""
PDDLStream Streams for Semantic Boxel TAMP.

This module implements the geometric reasoning streams that generate and test
continuous parameters for the symbolic planner. Streams interface with PyBullet
for inverse kinematics and motion planning.

Sensing uses the fixed scene camera (not the robot's end-effector), so there
is no sensing_config stream.

Streams:
    - sample_grasp: Generate grasp poses for an object
    - plan_motion: Plan collision-free trajectory between configs
    - compute_kin_solution: Compute IK for pick/place
    - compute_stack_kin_solution: Compute IK for stacking on a support (audit #30)
"""

import logging
import random
import numpy as np
import pybullet as p
from typing import List, Tuple, Optional, Generator, Iterator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from boxel_data import BoxelRegistry, BoxelData, BoxelType
from robot_utils import (ARM_JOINT_INDICES, END_EFFECTOR_LINK, FINGER_JOINTS,
                         JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH, JOINT_RANGES,
                         REST_POSES, RenderingLock,
                         is_config_collision_free, is_path_collision_free)


# =============================================================================
# PDDL Atom Data Types
# =============================================================================
# These three dataclasses are the continuous objects that flow between streams
# and into the PDDL plan.  PDDLStream requires them to be hashable and
# comparable, so all three use name-based __hash__/__eq__ — this lets them
# serve as dictionary keys and PDDL atoms inside the planner.

@dataclass
class RobotConfig:
    """
    Robot configuration (joint angles for Franka Panda).

    Represents a 7-DOF arm configuration.  The ``ignored_body_ids`` field
    carries PyBullet body IDs that should be excluded from collision checks
    when planning motion TO this config (e.g. the grasped object at a pick
    pose).  This field is set by ``compute_kin_solution`` and read by
    ``plan_motion``.
    """
    joint_positions: np.ndarray  # 7 DOF
    name: str = ""
    is_heuristic: bool = False
    ignored_body_ids: frozenset = field(default_factory=frozenset)
    grasp_ee_offset: np.ndarray = None
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if not isinstance(other, RobotConfig):
            return NotImplemented
        return self.name == other.name
    
    def __repr__(self):
        return self.name if self.name else f"RobotConfig({self.joint_positions})"


@dataclass 
class Trajectory:
    """
    Motion trajectory as sequence of configurations.

    Produced by ``plan_motion``.  Contains an ordered list of RobotConfig
    waypoints forming a collision-free path in joint space.  During
    execution, the robot follows these waypoints sequentially.
    """
    waypoints: List[RobotConfig]
    name: str = ""
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if not isinstance(other, Trajectory):
            return NotImplemented
        return self.name == other.name
    
    def __repr__(self):
        return self.name if self.name else f"Trajectory({len(self.waypoints)} waypoints)"


@dataclass
class Grasp:
    """
    Grasp transformation relative to object frame.

    Produced by ``sample_grasp``.  ``position`` is a [x, y, z] offset
    added to the boxel center to get the world-frame EE target.
    ``orientation`` is a [x, y, z, w] quaternion for the EE.
    Currently all grasps are top-down (pitch=180deg) with only Z-height
    variation — no side grasps, angled approaches, or yaw rotation.
    """
    position: np.ndarray   # [x, y, z] offset from boxel center
    orientation: np.ndarray  # [x, y, z, w] quaternion
    name: str = ""
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if not isinstance(other, Grasp):
            return NotImplemented
        return self.name == other.name
    
    def __repr__(self):
        return self.name if self.name else f"Grasp({self.position})"


class BoxelStreams:
    """
    PDDLStream-compatible streams for Semantic Boxel TAMP.

    These are generator functions that yield tuples of output values.
    PDDLStream calls them lazily during planning.

    Stream call order during planning:
      1. sample_grasp(obj)          -> "how to grab this object?"
      2. compute_kin_solution(obj, boxel, grasp) -> "what joint angles reach it?"
         (or compute_stack_kin_solution(obj, on_obj, grasp) for stack actions)
      3. plan_motion(q1, q2)        -> "collision-free path between configs?"

    The ignored_body_ids field threads through all three: compute_kin_solution
    attaches the grasped object's body ID to each config, and plan_motion
    reads it to exclude that body from collision checks.
    """
    
    def __init__(self, registry: BoxelRegistry, robot_id: int = None,
                 physics_client: int = None, object_body_ids: dict = None,
                 support_body_ids: frozenset = None):
        """
        Initialize streams with environment context.

        Args:
            registry: BoxelRegistry containing all boxels
            robot_id: PyBullet body ID of the robot (required for IK).
                Must be provided; without it compute_kin_solution yields
                nothing and plan_motion falls back to linear interpolation.
            physics_client: PyBullet physics client ID (0 if using default)
            object_body_ids: Mapping from object/boxel identifiers to PyBullet
                body IDs. Used to exclude the grasped object from collision
                checks in compute_kin and plan_motion. Keys should include
                both object names ("red_object") and boxel IDs ("obj_003").
            support_body_ids: Body IDs of support surfaces (table, ground
                plane).  Ignored during all collision checks for pick/place
                motions (both endpoint validation and RRT path planning)
                because the Panda is mounted on the table and its lower arm
                links overlap the table's collision geometry in PyBullet.
                Not ignored for pure transit motions with no grasped object.
        """
        # -- Environment context (all PyBullet-specific) --------------------------
        self.registry = registry            # Boxel grid world representation
        self.robot_id = robot_id            # PyBullet body ID of the Panda
        self.physics_client = physics_client if physics_client is not None else 0
        # Maps object names ("red_block") and boxel IDs ("obj_003") to PyBullet
        # body IDs.  Used by compute_kin_solution to build ignored_body_ids for
        # collision exclusion during motion planning.
        self.object_body_ids = object_body_ids or {}
        # Table/ground plane body IDs.  Ignored during pick/place collision
        # checks because the Panda is mounted on the table — its lower arm
        # links physically overlap the table geometry in PyBullet, causing
        # false-positive collisions on nearly every config.
        self.support_body_ids = support_body_ids or frozenset()
        
        if self.robot_id is None:
            raise ValueError(
                "BoxelStreams requires robot_id for kinematically valid IK. "
                "Heuristic IK fallback has been removed (audit #80)."
            )
        
        # Home configuration — the Panda's neutral rest pose, used as the
        # default start/end for transit motions.
        self.home_config = RobotConfig(
            joint_positions=np.array(REST_POSES),
            name="q_home"
        )
        
        # Monotonic counters for unique, human-readable naming of PDDL atoms.
        # Names like "q_kin_red_block_7" or "traj_3" appear in logs and plans.
        self._config_counter = 0
        self._traj_counter = 0
        self._grasp_counter = 0
        
        # IK solver parameters (PyBullet's iterative Jacobian-based IK).
        # 100 iterations is the PyBullet recommended default; convergence
        # threshold 1e-4 m balances precision vs speed (empirically tuned —
        # tighter values rarely improve the solution but slow planning).
        self.ik_max_iterations = 100
        self.ik_residual_threshold = 1e-4
    
    IK_NUM_SEEDS = 8

    # Seed perturbations for multi-start IK (radians, added to REST_POSES).
    # First row is zero (start from rest); rows 2-3 are uniform ±0.4 rad
    # pushes; rows 4-8 are hand-tuned pseudo-random perturbations chosen
    # to spread the 7-DOF null-space exploration.  Magnitudes stay within
    # ±0.8 rad so that clipped seeds remain well inside joint limits.
    # Empirically, 8 seeds resolve >95% of reachable targets on the first
    # planning call; increasing beyond 8 showed diminishing returns.
    _IK_SEED_OFFSETS = [
        [0, 0, 0, 0, 0, 0, 0],
        [0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4],
        [-0.4, -0.4, -0.4, -0.4, -0.4, -0.4, -0.4],
        [0.8, -0.3, 0.5, -0.6, 0.3, 0.7, -0.2],
        [-0.6, 0.5, -0.3, 0.8, -0.5, -0.2, 0.6],
        [0.2, -0.7, 0.6, 0.3, -0.8, 0.4, -0.5],
        [-0.3, 0.6, -0.8, -0.2, 0.7, -0.5, 0.3],
        [0.5, 0.2, -0.5, 0.7, 0.2, -0.6, 0.4],
    ]

    def _pybullet_ik(self, ee_pos: np.ndarray,
                     ee_orn: np.ndarray,
                     seed: list = None) -> Optional[RobotConfig]:
        """
        Compute IK using PyBullet's null-space calculateInverseKinematics.

        Saves the robot's current joint state, resets joints to *seed*
        (defaulting to REST_POSES), runs IK with null-space parameters,
        then restores the original state.  Different seeds steer the
        iterative solver into different local minima, producing arm
        configurations that may avoid obstacles the default solution hits.

        Args:
            ee_pos: Desired end-effector position.
            ee_orn: Desired end-effector orientation (quaternion).
            seed:   7-element list of joint angles used as the IK starting
                    point.  ``None`` → REST_POSES.

        Returns:
            RobotConfig if valid solution found, None otherwise.
        """
        if seed is None:
            seed = REST_POSES
        saved_joints = None
        pc = self.physics_client
        # RenderingLock suppresses OpenGL buffer swaps — without it, the
        # thousands of resetJointState calls during planning cause visible
        # scene flickering.  Nestable: inner locks are no-ops.
        with RenderingLock(pc):
            try:
                # 1. Save current joint state (restored in finally block)
                saved_joints = [
                    p.getJointState(self.robot_id, i,
                                    physicsClientId=pc)[0]
                    for i in ARM_JOINT_INDICES
                ]

                # 2. Reset joints to seed — this steers the iterative IK
                #    solver toward a specific local minimum.  Different seeds
                #    produce different arm configs (elbow-up vs elbow-down etc.)
                for i, angle in zip(ARM_JOINT_INDICES, seed):
                    p.resetJointState(self.robot_id, i, angle,
                                      physicsClientId=pc)

                # 3. Run PyBullet's null-space IK.  The null-space parameters
                #    (lowerLimits, upperLimits, jointRanges, restPoses) bias
                #    the solver toward the seed when multiple solutions exist.
                joint_positions = p.calculateInverseKinematics(
                    bodyUniqueId=self.robot_id,
                    endEffectorLinkIndex=END_EFFECTOR_LINK,
                    targetPosition=ee_pos.tolist(),
                    targetOrientation=ee_orn.tolist(),
                    lowerLimits=JOINT_LIMITS_LOW.tolist(),
                    upperLimits=JOINT_LIMITS_HIGH.tolist(),
                    jointRanges=JOINT_RANGES.tolist(),
                    restPoses=list(seed),
                    maxNumIterations=self.ik_max_iterations,
                    residualThreshold=self.ik_residual_threshold,
                    physicsClientId=pc
                )

                # 4. Validate: PyBullet returns ALL joint positions (arm +
                #    fingers + fixed joints); we only need the first 7 (arm).
                if joint_positions is None or len(joint_positions) < 7:
                    return None

                arm_joints = np.array(joint_positions[:7])

                # 5. Joint-limit check with 0.1 rad (~5.7deg) tolerance.
                #    PyBullet's iterative solver can slightly overshoot;
                #    solutions within tolerance are clipped, beyond → rejected.
                if np.any(arm_joints < JOINT_LIMITS_LOW - 0.1) or \
                   np.any(arm_joints > JOINT_LIMITS_HIGH + 0.1):
                    return None

                arm_joints = np.clip(arm_joints, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)

                return RobotConfig(joint_positions=arm_joints)

            except Exception as e:
                logger.error("IK failed for pos=%s: %s", ee_pos.tolist(), e)
                return None

            finally:
                # Always restore original joint state so IK calls don't
                # mutate the simulation — critical for deterministic planning.
                if saved_joints is not None:
                    for i, angle in zip(ARM_JOINT_INDICES, saved_joints):
                        p.resetJointState(self.robot_id, i, angle,
                                          physicsClientId=pc)

    def _ik_seeds(self):
        """Yield IK seed configurations: REST_POSES first, then perturbations."""
        rest = np.array(REST_POSES)
        for offset in self._IK_SEED_OFFSETS[:self.IK_NUM_SEEDS]:
            seed = rest + np.array(offset)
            seed = np.clip(seed, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
            yield seed.tolist()
    
    def _resolve_body_id(self, obj_id) -> Optional[int]:
        """
        Look up the PyBullet body ID for an object or boxel identifier.

        Handles both direct object names (e.g. "blue_object") and boxel IDs
        (e.g. "obj_003") by falling back to the boxel's object_name.
        """
        key = str(obj_id)
        if key in self.object_body_ids:
            return self.object_body_ids[key]
        boxel = self.registry.get_boxel(key)
        if boxel and boxel.object_name and boxel.object_name in self.object_body_ids:
            return self.object_body_ids[boxel.object_name]
        return None

    # =========================================================================
    # Boxel fitness (place precondition) — used from pddlstream_planner init
    # =========================================================================
    # True pairs are emitted as static (boxel_fits ?o ?b) in _build_init, not via
    # a PDDLStream test stream (adaptive search would re-test combinatorially).

    def test_boxel_fits(self, obj_id: str, boxel_id: str) -> bool:
        """
        Whether a free-space boxel is large enough to contain an object.

        Compares axis-aligned extents (max_corner - min_corner) of both
        boxels.  Returns True iff the free boxel's extent >= the object
        boxel's extent on all three axes.

        Args:
            obj_id: Boxel ID of the object being placed
            boxel_id: Boxel ID of the candidate free-space destination

        Returns:
            True if the free boxel can contain the object, False otherwise
        """
        obj_boxel = self.registry.get_boxel(obj_id)
        dest_boxel = self.registry.get_boxel(boxel_id)
        if obj_boxel is None or dest_boxel is None:
            return False
        obj_extents = obj_boxel.max_corner - obj_boxel.min_corner
        dest_extents = dest_boxel.max_corner - dest_boxel.min_corner
        return bool(np.all(dest_extents >= obj_extents))

    # =========================================================================
    # STREAM 1: Sample Grasp
    # =========================================================================
    # Called first during planning: "how can I grab this object?"
    #
    # Fixed top-down grasp clearance above the object center (m).
    # 0.10 m: the planner certifies an approach pose 10 cm above the
    # object centre.  Execution then lowers to contact via solve_ik
    # seeded from the planner's q (audit #37/#38) so the contact pose
    # stays in the same IK branch the planner validated.
    #
    # The 2 cm experiment (briefly tried in the original #37/#38 fix)
    # was reverted on 2026-04-29: a 2 cm clearance parked the wrist
    # inside the camera→shadow ray path, so any move→sense sequence
    # had the arm itself blocking the view and sense_shadow_raycasting
    # always returned still_blocked.  IK seeding (the actual #37/#38
    # win) is independent of this offset and is retained.
    _GRASP_Z_OFFSETS = [0.10]

    def sample_grasp(self, obj_id: str) -> Iterator[Tuple[Grasp]]:
        """
        Generate grasp poses for an object with varying clearance.

        Yields a single top-down grasp at a fixed 0.10 m above the
        object center.  Execution uses a constraint-based weld so grip
        security is independent of the exact EE height; the contact-
        pose IK is seeded from the planner's q (audit #37/#38) so it
        stays in the same IK branch.

        PDDLStream declaration (see pddl/stream.pddl):
            (:stream sample-grasp
              :inputs (?o)
              :domain (Obj ?o)
              :outputs (?g)
              :certified (and (Grasp ?g) (valid_grasp ?o ?g)))

        Args:
            obj_id: ID of the object to grasp

        Yields:
            Tuples of (grasp,) for the object — one per Z offset.
        """
        # Top-down orientation: pitch=180deg = gripper pointing straight down
        orn = np.array(p.getQuaternionFromEuler([0, np.pi, 0]))
        # Yield one grasp per Z-offset (currently 0.10 m above object).
        # Execution lowers from this height to contact via solve_ik
        # seeded from this q (audit #37/#38) so the contact pose stays
        # in the same IK branch the planner validated.
        # position=[0,0,z] means no X/Y offset — directly above boxel center.
        # compute_kin_solution later adds this to boxel.center to get the
        # world-frame EE target position.
        offsets = list(self._GRASP_Z_OFFSETS)
        random.shuffle(offsets)
        for z in offsets:
            self._grasp_counter += 1
            grasp = Grasp(
                position=np.array([0, 0, z]),
                orientation=orn,
                name=f"grasp_{obj_id}_{self._grasp_counter}"
            )
            logger.debug("sample_grasp: %s -> %s (z=%.2f)", obj_id,
                         grasp.name, z)
            yield (grasp,)
    
    # =========================================================================
    # STREAM 3: Plan Motion (RRT-Connect with shortcut smoothing)
    # =========================================================================
    # Called last during planning: "can the robot move between these configs
    # without hitting anything?"
    #
    # RRT-Connect parameters (Kuffner & LaValle, 2000).
    # MAX_ITERATIONS and STEP_SIZE follow standard practice for 7-DOF arms;
    # GOAL_BIAS 5% is the canonical value.  EDGE_CHECKS, CONNECT_ATTEMPTS,
    # and SMOOTH_ATTEMPTS were empirically tuned on the tabletop scenario
    # (2-4 objects, table-mounted Panda) — higher values improved solution
    # quality marginally while increasing planning time significantly.
    RRT_MAX_ITERATIONS = 2000    # sufficient for tabletop clutter
    RRT_STEP_SIZE = 0.2          # max joint displacement per extend (rad)
    RRT_GOAL_BIAS = 0.05         # probability of sampling the goal
    RRT_EDGE_CHECKS = 8          # collision samples per edge
    RRT_CONNECT_ATTEMPTS = 50    # max extends for the connect phase
    SMOOTH_ATTEMPTS = 75         # shortcut smoothing iterations

    def plan_motion(self, q1: RobotConfig, q2: RobotConfig) -> Iterator[Tuple[Trajectory]]:
        """
        Plan collision-free motion between two configurations.

        Collision checks respect ``ignored_body_ids`` carried by each
        config (set by ``compute_kin_solution`` for pick/place poses).
        This prevents the grasped object from blocking its own pick
        motion.

        Strategy:
          1. If no robot is loaded (heuristic mode), fall back to linear
             interpolation — there is no physics to check against.
          2. Verify both endpoints are collision-free.
          3. Try the direct linear path (fast path — most moves are simple
             reaches that don't collide with anything).
          4. If the direct path collides, run bidirectional RRT-Connect.
          5. Smooth the RRT path with random shortcutting.

        PDDLStream declaration (see pddl/stream.pddl)::

            (:stream plan-motion
              :inputs (?q1 ?q2)
              :domain (and (Config ?q1) (Config ?q2))
              :outputs (?t)
              :certified (and (Trajectory ?t) (motion ?q1 ?q2 ?t)))

        Args:
            q1: Start configuration.
            q2: Goal configuration.

        Yields:
            Tuples of ``(trajectory,)`` connecting *q1* to *q2*.
            Yields nothing if no collision-free path is found.
        """
        # --- Step 0: No-robot fallback (should not happen in production) ------
        if self.robot_id is None:
            yield (self._linear_trajectory(q1, q2),)
            return

        pc = self.physics_client

        # --- Step 1: Build ignored-bodies sets --------------------------------
        # Union of both endpoints' ignored bodies.  When moving from home
        # (ignored={}) to a pick config (ignored={obj}), this ignores the
        # grasped object for the entire path — which is necessary because
        # the pick endpoint places the gripper AT the object.  Without the
        # union, intermediate configs near the goal would be rejected for
        # colliding with the object and RRT could never connect to it.
        # A decomposed transit+approach architecture could restrict the
        # ignore set to the approach phase only, but the current single-
        # motion design requires the union.
        base_ignored = q1.ignored_body_ids | q2.ignored_body_ids
        is_pick_place = bool(q1.ignored_body_ids or q2.ignored_body_ids)

        # Intersection: bodies ignored by BOTH endpoints are genuinely held
        # by the gripper throughout the motion.  Bodies in only one endpoint
        # (e.g. the pick target) are being approached, not carried.
        held_body_ids = q1.ignored_body_ids & q2.ignored_body_ids

        # grasp_ee_offset describes where the held body sits relative to the
        # EE (e.g. [0, 0, 0.10] = 10 cm below EE for a top-down grasp at the
        # current _GRASP_Z_OFFSETS).
        # Without this, the planning-time checker places the held body AT the
        # EE, which is too high and misses collisions at the real object height.
        held_body_ee_offset = None
        if held_body_ids:
            for q in (q1, q2):
                if q.grasp_ee_offset is not None:
                    held_body_ee_offset = q.grasp_ee_offset
                    break

        # For pick/place, also ignore support surfaces (table) because the
        # Panda is mounted ON the table — its lower arm links overlap the
        # table's collision geometry in PyBullet, producing false positives
        # on nearly every intermediate config.  Not needed for pure transit.
        endpoint_ignored = base_ignored | self.support_body_ids if is_pick_place else base_ignored
        path_ignored = base_ignored | self.support_body_ids if is_pick_place else base_ignored

        logger.debug("plan_motion: %s -> %s  endpoint_ignored=%s "
                      "path_ignored=%s gripper_relax=%s held=%s",
                      q1, q2,
                      sorted(endpoint_ignored) if endpoint_ignored else '{}',
                      sorted(path_ignored) if path_ignored != endpoint_ignored else '=',
                      is_pick_place,
                      sorted(held_body_ids) if held_body_ids else '{}')

        # --- Step 2: Validate endpoints are collision-free --------------------
        # If either config is already in collision, no point trying to plan.
        # allow_gripper_collisions=True for pick/place lets the gripper enter
        # cluttered space (it must touch the object at the pick pose).
        if not is_config_collision_free(self.robot_id, q1.joint_positions,
                                        pc, endpoint_ignored,
                                        allow_gripper_collisions=is_pick_place,
                                        held_body_ids=held_body_ids,
                                        held_body_ee_offset=held_body_ee_offset):
            logger.warning("plan_motion: start config %s in collision "
                           "(ignored=%s)", q1, sorted(endpoint_ignored))
            return
        if not is_config_collision_free(self.robot_id, q2.joint_positions,
                                        pc, endpoint_ignored,
                                        allow_gripper_collisions=is_pick_place,
                                        held_body_ids=held_body_ids,
                                        held_body_ee_offset=held_body_ee_offset):
            logger.warning("plan_motion: goal config %s in collision "
                           "(ignored=%s)", q2, sorted(endpoint_ignored))
            return

        # --- Step 3: Try direct linear path (fast path) -----------------------
        # Most tabletop moves are simple reaches that don't collide with
        # anything.  Check 8 evenly-spaced configs along the straight line;
        # if all clear, yield a 10-waypoint linear trajectory immediately.
        if is_path_collision_free(self.robot_id, q1.joint_positions,
                                  q2.joint_positions, pc,
                                  n_checks=self.RRT_EDGE_CHECKS,
                                  ignored_bodies=path_ignored,
                                  allow_gripper_collisions=is_pick_place,
                                  held_body_ids=held_body_ids,
                                  held_body_ee_offset=held_body_ee_offset):
            logger.info("plan_motion: direct path clear — linear trajectory")
            yield (self._linear_trajectory(q1, q2),)
            return

        # --- Step 4: RRT-Connect (direct path blocked) ------------------------
        # Bidirectional RRT-Connect: grow two trees (from start and goal),
        # extend toward random samples, try to connect them.
        logger.info("plan_motion: direct path blocked — running RRT-Connect")
        path = self._rrt_connect(q1.joint_positions, q2.joint_positions,
                                 path_ignored,
                                 allow_gripper_collisions=is_pick_place,
                                 held_body_ids=held_body_ids,
                                 held_body_ee_offset=held_body_ee_offset)

        if path is None:
            logger.warning("plan_motion: RRT-Connect failed (%d iters)",
                           self.RRT_MAX_ITERATIONS)
            return

        # --- Step 5: Smooth the RRT path with random shortcutting -------------
        # RRT paths are jagged; random shortcutting picks two non-adjacent
        # waypoints 75 times and removes everything between them if the
        # direct edge is collision-free.
        smoothed = self._smooth_path(path, path_ignored,
                                     allow_gripper_collisions=is_pick_place,
                                     held_body_ids=held_body_ids,
                                     held_body_ee_offset=held_body_ee_offset)
        logger.info("plan_motion: RRT path %d wps -> smoothed %d wps",
                     len(path), len(smoothed))

        # Wrap the joint-space waypoints into RobotConfig objects
        waypoints = []
        for i, joints in enumerate(smoothed):
            waypoints.append(RobotConfig(
                joint_positions=joints,
                name=f"{q1.name}_to_{q2.name}_rrt{i}"
            ))

        self._traj_counter += 1
        traj = Trajectory(waypoints=waypoints,
                          name=f"traj_{self._traj_counter}")
        yield (traj,)

    # ----- helpers -----------------------------------------------------------

    def _linear_trajectory(self, q1: RobotConfig, q2: RobotConfig,
                           n_waypoints: int = 10) -> Trajectory:
        """Build a linearly-interpolated trajectory (no collision check)."""
        waypoints = []
        for t in np.linspace(0, 1, n_waypoints):
            waypoints.append(RobotConfig(
                joint_positions=(1 - t) * q1.joint_positions
                                + t * q2.joint_positions,
                name=f"{q1.name}_to_{q2.name}_wp{int(t * 10)}"
            ))
        self._traj_counter += 1
        return Trajectory(waypoints=waypoints,
                          name=f"traj_{self._traj_counter}")

    # ----- RRT-Connect helpers ------------------------------------------------
    # These implement the core RRT-Connect algorithm (Kuffner & LaValle, 2000):
    #   _random_config  — sample a random point in C-space
    #   _nearest         — find closest tree node (brute-force L2)
    #   _steer           — take a bounded step toward a target config
    #   _try_connect     — greedily extend a tree until it reaches the target
    #   _trace_path      — walk parent pointers to reconstruct the path
    #   _rrt_connect     — the main bidirectional loop

    def _random_config(self) -> np.ndarray:
        """Sample a uniform random configuration within joint limits."""
        return np.random.uniform(JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)

    def _nearest(self, nodes: List[np.ndarray], q: np.ndarray) -> int:
        """Return the index of the node closest to *q* (L2 in joint space)."""
        best_idx, best_dist = 0, np.inf
        for i, n in enumerate(nodes):
            d = np.linalg.norm(n - q)
            if d < best_dist:
                best_idx, best_dist = i, d
        return best_idx

    def _steer(self, q_near: np.ndarray, q_target: np.ndarray,
               max_step: float) -> np.ndarray:
        """
        Move from *q_near* toward *q_target*, limiting the maximum
        per-joint displacement to *max_step* radians.
        """
        diff = q_target - q_near
        max_diff = np.max(np.abs(diff))
        if max_diff <= max_step:
            return q_target.copy()
        return q_near + diff * (max_step / max_diff)

    def _try_connect(self, nodes: List[np.ndarray],
                     parents: List[int],
                     q_target: np.ndarray,
                     ignored_bodies: frozenset = frozenset(),
                     allow_gripper_collisions: bool = False,
                     held_body_ids: frozenset = frozenset(),
                     held_body_ee_offset=None) -> Optional[int]:
        """
        Greedily extend a tree toward *q_target* until it either reaches
        the target or hits a collision.  Returns the connecting node index,
        or ``None`` on failure.
        """
        cur_idx = self._nearest(nodes, q_target)
        pc = self.physics_client
        for _ in range(self.RRT_CONNECT_ATTEMPTS):
            q_cur = nodes[cur_idx]
            q_new = self._steer(q_cur, q_target, self.RRT_STEP_SIZE)
            if not is_path_collision_free(self.robot_id, q_cur, q_new, pc,
                                          self.RRT_EDGE_CHECKS,
                                          ignored_bodies=ignored_bodies,
                                          allow_gripper_collisions=allow_gripper_collisions,
                                          held_body_ids=held_body_ids,
                                          held_body_ee_offset=held_body_ee_offset):
                return None
            new_idx = len(nodes)
            nodes.append(q_new)
            parents.append(cur_idx)
            cur_idx = new_idx
            if np.allclose(q_new, q_target, atol=1e-3):
                return new_idx
        return None

    def _trace_path(self, nodes: List[np.ndarray],
                    parents: List[int], idx: int) -> List[np.ndarray]:
        """Walk parent pointers back to the root and return the path."""
        path = []
        while idx != -1:
            path.append(nodes[idx])
            idx = parents[idx]
        path.reverse()
        return path

    def _rrt_connect(self, q_start: np.ndarray,
                     q_goal: np.ndarray,
                     ignored_bodies: frozenset = frozenset(),
                     allow_gripper_collisions: bool = False,
                     held_body_ids: frozenset = frozenset(),
                     held_body_ee_offset=None
                     ) -> Optional[List[np.ndarray]]:
        """
        Bidirectional RRT-Connect (Kuffner & LaValle, 2000).

        Grows two trees — one from *q_start*, one from *q_goal* — and
        alternately extends them toward random samples.  When one tree
        successfully connects to a new node of the other tree, the two
        half-paths are spliced into a complete trajectory.

        Returns:
            List of joint-space waypoints from start to goal, or ``None``.
        """
        # Two trees: A grows from start, B grows from goal.
        # Each tree is a list of joint configs with parallel parent indices.
        # Parent of root is -1 (sentinel).
        nodes_a: List[np.ndarray] = [q_start.copy()]
        parents_a: List[int] = [-1]
        nodes_b: List[np.ndarray] = [q_goal.copy()]
        parents_b: List[int] = [-1]

        # Track whether trees have been swapped (needed to orient the
        # final path correctly: start → goal, not goal → start).
        swapped = False
        pc = self.physics_client

        for iteration in range(self.RRT_MAX_ITERATIONS):
            if iteration > 0 and iteration % 500 == 0:
                logger.debug("RRT-Connect: iter %d/%d  tree_a=%d  tree_b=%d",
                             iteration, self.RRT_MAX_ITERATIONS,
                             len(nodes_a), len(nodes_b))

            # Sample: 5% of the time aim at the other tree's root (goal bias)
            # to speed convergence; otherwise sample uniformly in C-space.
            if random.random() < self.RRT_GOAL_BIAS:
                q_rand = nodes_b[0].copy()
            else:
                q_rand = self._random_config()

            # Extend tree A toward the sample by one bounded step
            near_idx = self._nearest(nodes_a, q_rand)
            q_new = self._steer(nodes_a[near_idx], q_rand, self.RRT_STEP_SIZE)

            # If the edge is in collision, skip and swap trees for balance
            if not is_path_collision_free(self.robot_id,
                                          nodes_a[near_idx], q_new, pc,
                                          self.RRT_EDGE_CHECKS,
                                          ignored_bodies=ignored_bodies,
                                          allow_gripper_collisions=allow_gripper_collisions,
                                          held_body_ids=held_body_ids,
                                          held_body_ee_offset=held_body_ee_offset):
                nodes_a, nodes_b = nodes_b, nodes_a
                parents_a, parents_b = parents_b, parents_a
                swapped = not swapped
                continue

            # Add the new node to tree A
            new_idx_a = len(nodes_a)
            nodes_a.append(q_new)
            parents_a.append(near_idx)

            # Try to greedily connect tree B to this new node.
            # If successful, splice the two half-paths into a full trajectory.
            connect_idx = self._try_connect(nodes_b, parents_b, q_new,
                                            ignored_bodies,
                                            allow_gripper_collisions,
                                            held_body_ids,
                                            held_body_ee_offset)
            if connect_idx is not None:
                path_a = self._trace_path(nodes_a, parents_a, new_idx_a)
                path_b = self._trace_path(nodes_b, parents_b, connect_idx)
                # Orient correctly: path must go start → goal regardless
                # of which tree is currently "A".
                if swapped:
                    path_a.reverse()
                    full = path_b + path_a[1:]
                else:
                    path_b.reverse()
                    full = path_a + path_b[1:]
                return full

            # Swap trees each iteration so both grow at similar rates
            nodes_a, nodes_b = nodes_b, nodes_a
            parents_a, parents_b = parents_b, parents_a
            swapped = not swapped

        return None

    # ----- Shortcut smoothing ------------------------------------------------

    def _smooth_path(self, path: List[np.ndarray],
                     ignored_bodies: frozenset = frozenset(),
                     allow_gripper_collisions: bool = False,
                     held_body_ids: frozenset = frozenset(),
                     held_body_ee_offset=None
                     ) -> List[np.ndarray]:
        """
        Random shortcut smoothing: pick two non-adjacent waypoints and
        replace the segment between them with a direct edge if that edge
        is collision-free.
        """
        if len(path) <= 2:
            return list(path)
        smoothed = list(path)
        pc = self.physics_client
        for _ in range(self.SMOOTH_ATTEMPTS):
            if len(smoothed) <= 2:
                break
            i = random.randint(0, len(smoothed) - 3)
            j = random.randint(i + 2, len(smoothed) - 1)
            if is_path_collision_free(self.robot_id, smoothed[i], smoothed[j],
                                      pc, self.RRT_EDGE_CHECKS,
                                      ignored_bodies=ignored_bodies,
                                      allow_gripper_collisions=allow_gripper_collisions,
                                      held_body_ids=held_body_ids,
                                      held_body_ee_offset=held_body_ee_offset):
                smoothed = smoothed[:i + 1] + smoothed[j:]
        return smoothed
    
    # =========================================================================
    # STREAM 2: Compute IK for Pick/Place
    # =========================================================================
    # Called second during planning: "what joint angles get the arm to this
    # grasp at this boxel?"
    #
    def compute_kin_solution(self, obj_id: str, boxel_id: str,
                             grasp: Grasp) -> Iterator[Tuple[RobotConfig]]:
        """
        Compute IK solutions for picking object from boxel with grasp.

        Tries multiple IK seeds to produce diverse arm configurations.
        Each successful config carries ``ignored_body_ids`` containing the
        PyBullet body ID of the grasped object.  ``plan_motion()`` uses this
        to exclude the grasped body from collision checks — necessary because
        the gripper must be in contact with the object at the pick pose.

        Collision validation is deliberately NOT done here.  In a TAMP plan,
        earlier actions may relocate objects that currently block the target
        boxel.  Checking collisions against the static planning-time world
        would reject configs that are valid at execution time (e.g. picking
        a target from a shadow after the occluder has been moved).
        ``plan_motion()`` handles collision checking with the union of
        ignored bodies from both endpoints, which naturally covers objects
        moved earlier in the plan.

        PDDLStream declaration (see pddl/stream.pddl):
            (:stream compute-kin
              :inputs (?o ?b ?g)
              :domain (and (Obj ?o) (Boxel ?b) (valid_grasp ?o ?g))
              :outputs (?q)
              :certified (and (Config ?q) (kin_solution ?o ?b ?g ?q)
                              (config_for_boxel ?q ?b)))

        Args:
            obj_id: Object to grasp
            boxel_id: Boxel containing object
            grasp: Grasp to use

        Yields:
            Tuples of (config,) for grasping — one per successful IK seed.
        """
        # --- Look up the boxel's 3D center from the grid registry ---------------
        boxel = self.registry.get_boxel(boxel_id)
        if boxel is None:
            return

        # --- Compute the world-frame EE target pose ---------------------------
        # grasp.position is a relative offset (e.g. [0, 0, 0.05] = 5 cm above
        # the boxel center).  Adding it to boxel.center gives the absolute
        # position the end-effector must reach.
        target_pos = boxel.center + grasp.position
        ee_orn = grasp.orientation

        # --- Resolve the grasped object's PyBullet body ID --------------------
        # This body must be EXCLUDED from collision checks in plan_motion(),
        # because the gripper will intentionally be in contact with it at the
        # pick pose.  The frozenset travels with the config through the plan.
        body_id = self._resolve_body_id(obj_id)
        ignored = frozenset({body_id}) if body_id is not None else frozenset()

        if self.robot_id is None:
            logger.warning("compute_kin: no robot_id — cannot compute IK "
                           "for %s at %s", obj_id, boxel_id)
            return

        # --- Multi-seed IK loop -----------------------------------------------
        # Try 8 different IK seeds (see _IK_SEED_OFFSETS) to get diverse arm
        # configurations.  Different seeds steer PyBullet's iterative solver
        # into different local minima (elbow-up, elbow-down, etc.).
        seen = set()     # dedup by rounded joint angles
        yielded = 0
        for seed_idx, seed in enumerate(self._ik_seeds()):
            config = self._pybullet_ik(target_pos, ee_orn, seed=seed)
            if config is None:
                continue

            # Deduplicate: round to 3 decimal places (0.001 rad ≈ 0.06 deg)
            # to avoid yielding configs that differ only by floating-point noise.
            sig = tuple(np.round(config.joint_positions, 3))
            if sig in seen:
                continue
            seen.add(sig)

            # Attach the ignored-body set so plan_motion knows to skip this
            # object during collision checks for the entire motion to/from
            # this config.
            config.ignored_body_ids = ignored
            config.grasp_ee_offset = grasp.position
            self._config_counter += 1
            config.name = f"q_kin_{obj_id}_{self._config_counter}"
            logger.debug("compute_kin: %s at %s -> %s  "
                         "ee_target=%s ignored_body=%s seed=%d",
                         obj_id, boxel_id, config.name,
                         target_pos.tolist(), body_id, seed_idx)
            yield (config,)
            yielded += 1

        # If no seed produced a valid IK solution, log for diagnostics.
        # The generator simply ends with no outputs, telling PDDLStream
        # this (obj, boxel, grasp) combination has no feasible pick config.
        if yielded == 0:
            logger.debug("compute_kin: all %d IK seeds failed for %s at %s "
                         "(target_pos=%s)", self.IK_NUM_SEEDS, obj_id,
                         boxel_id, target_pos.tolist())

    # =========================================================================
    # STREAM 4: Compute IK for Stack  (audit #30; lazy-collision fix in #55)
    # =========================================================================
    # Like compute_kin_solution but the EE target is derived from
    # ?on_obj's CURRENT AABB rather than a precomputed boxel center,
    # so a stack built across a multi-step plan keeps targeting the
    # running stack height rather than the support's spawn pose.
    #
    # ignored_body_ids includes BOTH the held cube AND the support cube
    # (audit #55).  Mirrors compute_kin_solution's lazy-collision pattern
    # (see L843-851) and extends it to the support: an earlier action
    # may have relocated ?on_obj (picked + stacked elsewhere), but at
    # planning time the plan-client world still shows ?on_obj at its
    # initial pose.  Without ignoring ?on_obj, plan_motion would reject
    # trajectories that pass through where ?on_obj statically sits.
    # execute_stack reads ?on_obj's LIVE AABB at runtime and re-solves
    # IK seeded with the planner's config, so the IK target being
    # "above initial pose" at planning time is recovered to "above
    # current pose" at execution.  Full symbolic pose-threading
    # (Path C) was prototyped on branch audit-55-pose-aware-stack —
    # functionally correct but slow under PDDLStream's exogenous-
    # axiom compilation; revisit if a future goal mode needs precise
    # pre-execution arm-routing.
    #
    # Compared to the pre-#55 implementation, the only diff is this
    # ignored-set extension; IK seed loop, dedup, target-pose
    # derivation are unchanged.
    def compute_stack_kin_solution(self, obj_id: str, on_obj_id: str,
                                   grasp: Grasp) -> Iterator[Tuple[RobotConfig]]:
        """
        IK to release the held ``obj_id`` on top of ``on_obj_id``.

        Pose derivation: read ``on_obj_id``'s current AABB from PyBullet
        (falling back to its registry boxel) and compute the EE z so the
        held object's bottom face rests on the support's top face:

            ee_target.xy = on_obj_top.xy + grasp.position[:2]
            ee_target.z  = on_obj_top.z + held_half_height + grasp.position[2]

        ``held_half_height`` comes from the held object's registry boxel
        (compute_kin_solution sized it from the AABB at scan time).

        ``ignored_body_ids`` on the yielded config includes BOTH the held
        cube AND the support cube (audit #55).  See the section comment
        above for the lazy-collision rationale: at planning time the
        support may symbolically be elsewhere (e.g. on the tray after a
        prior stack action) while the plan-client world still places it
        at its initial pose.  execute_stack salvages this at runtime via
        a fresh IK against the support's live AABB.

        Certifies (Config ?q), (stack_kin ?o ?on_obj ?g ?q), and
        (config_for_boxel ?q ?on_obj) — the last so the preceding move
        action can deliver the arm to the support's OBJECT boxel.
        """
        # Held cube half-height: prefer registry boxel; fall back to live
        # AABB for hidden targets that don't have OBJECT-type registry
        # boxels (audit #55).  Their bodies ARE mirrored in plan_client
        # via _mirror_load_urdf even before sense reveals their pose,
        # and the cube's z-extent doesn't depend on knowing where it is.
        held_boxel = self.registry.get_boxel(obj_id)
        if held_boxel is not None:
            held_half_height = float(held_boxel.extent[2])
        else:
            body_id = self._resolve_body_id(obj_id)
            if body_id is None:
                return
            try:
                h_min, h_max = p.getAABB(
                    body_id, physicsClientId=self.physics_client)
            except Exception:
                return
            held_half_height = float(h_max[2] - h_min[2]) / 2.0

        on_body_id = self._resolve_body_id(on_obj_id)
        top_z: Optional[float] = None
        if on_body_id is not None:
            try:
                aabb_min, aabb_max = p.getAABB(on_body_id,
                                               physicsClientId=self.physics_client)
                top_z = float(aabb_max[2])
                cx = (aabb_min[0] + aabb_max[0]) / 2.0
                cy = (aabb_min[1] + aabb_max[1]) / 2.0
            except Exception:
                top_z = None

        if top_z is None:
            on_boxel = self.registry.get_boxel(on_obj_id)
            if on_boxel is None:
                return
            top_z = float(on_boxel.max_corner[2])
            cx, cy, _ = on_boxel.center.tolist()

        target_obj_pos = np.array([cx, cy, top_z + held_half_height])
        target_pos = target_obj_pos + grasp.position
        ee_orn = grasp.orientation

        # audit #55 — ignore BOTH held cube AND support cube; see section
        # comment above for the lazy-collision rationale.
        held_body_id = self._resolve_body_id(obj_id)
        support_body_id = self._resolve_body_id(on_obj_id)
        ignored = frozenset(
            bid for bid in (held_body_id, support_body_id) if bid is not None
        )

        if self.robot_id is None:
            logger.warning("compute_stack_kin: no robot_id — cannot compute IK "
                           "for %s on %s", obj_id, on_obj_id)
            return

        seen = set()
        yielded = 0
        for seed_idx, seed in enumerate(self._ik_seeds()):
            config = self._pybullet_ik(target_pos, ee_orn, seed=seed)
            if config is None:
                continue
            sig = tuple(np.round(config.joint_positions, 3))
            if sig in seen:
                continue
            seen.add(sig)
            config.ignored_body_ids = ignored
            config.grasp_ee_offset = grasp.position
            self._config_counter += 1
            config.name = f"q_stack_{obj_id}_on_{on_obj_id}_{self._config_counter}"
            logger.debug("compute_stack_kin: %s on %s -> %s "
                         "ee_target=%s seed=%d",
                         obj_id, on_obj_id, config.name,
                         target_pos.tolist(), seed_idx)
            yield (config,)
            yielded += 1

        if yielded == 0:
            logger.debug("compute_stack_kin: all %d seeds failed for %s on %s "
                         "(target_pos=%s)", self.IK_NUM_SEEDS, obj_id,
                         on_obj_id, target_pos.tolist())
