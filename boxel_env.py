"""
Boxel Test Environment for Semantic POD-TAMP Research.

This module implements the main PyBullet simulation environment for testing
Semantic Partitioning for Partially Observable Deterministic Task and Motion Planning.
"""

import numpy as np
import pybullet as p
import pybullet_data
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from boxel_types import ObjectInfo, CameraObservation
from boxel_data import BoxelData, BoxelType
from shadow_calculator import ShadowCalculator
from free_space import FreeSpaceGenerator
from uniform_grid import UniformGridGenerator
from visualization import BoxelVisualizer


# ---------------------------------------------------------------------------
# Debug visualizer (main GL view) — fixed defaults only
# ---------------------------------------------------------------------------
# ``getCameraImage`` uses ``computeViewMatrix(eye, target, up)``.  The
# ExampleBrowser view only supports ``resetDebugVisualizerCamera(distance,
# yaw, pitch, target)``.  Values below were **precomputed once** (see
# ``tools/calibrate_debug_camera.py``) by grid-matching
# ``computeViewMatrixFromYawPitchRoll`` to the default semantic camera:
#   eye (0.1, -0.8, 0.7), target (0.1, 0.0, 0.5), up (0, 0, 1).

_DEFAULT_DEBUG_VIS_TARGET = [0.1, 0.0, 0.5]
_DEFAULT_DEBUG_VIS_DISTANCE = 0.8246211251235323
_DEFAULT_DEBUG_VIS_YAW = 0.0
_DEFAULT_DEBUG_VIS_PITCH = -14.04

_DEFAULT_SEMANTIC_EYE = np.array([0.1, -0.8, 0.7])
_DEFAULT_SEMANTIC_TARGET = np.array([0.1, 0.0, 0.5])


# ---------------------------------------------------------------------------
# Scene configuration types
# ---------------------------------------------------------------------------

class ObjectShape(Enum):
    """Primitive shapes available in PyBullet."""
    BOX = "box"
    CYLINDER = "cylinder"
    SPHERE = "sphere"


# ---------------------------------------------------------------------------
# Named colour palette for scene objects
# ---------------------------------------------------------------------------
# Seven visually distinct RGBA colours used by the scene-preset functions
# to give every manipulable object a unique appearance and a human-readable
# name (e.g. "red_object", "blue_object").  Each entry is [R, G, B, 1.0].

OBJECT_COLORS: Dict[str, List[float]] = {
    "red":    [0.85, 0.20, 0.20, 1.0],
    "green":  [0.15, 0.75, 0.20, 1.0],
    "orange": [0.90, 0.55, 0.10, 1.0],
    "blue":   [0.20, 0.35, 0.90, 1.0],
    "cyan":   [0.15, 0.80, 0.80, 1.0],
    "purple": [0.70, 0.20, 0.80, 1.0],
    "yellow": [0.90, 0.85, 0.10, 1.0],
}


@dataclass
class ObjectSpec:
    """
    Specification for a single scene object.

    Shapes and their ``size`` semantics:
      - BOX:      [half_x, half_y, half_z]  (half-extents)
      - CYLINDER: [radius, half_height]
      - SPHERE:   [radius]

    All dimensions in metres.
    """
    shape: ObjectShape
    size: List[float]
    color: List[float] = field(default_factory=lambda: [0.5, 0.5, 0.5, 1.0])
    mass: float = 0.5
    lateral_friction: float = 1.0
    name: Optional[str] = None  # color-based name; overrides auto-generated occluder_N / target_N

    @property
    def aabb_half_extents(self) -> np.ndarray:
        """Axis-aligned half-extents used for shadow/boxel computation."""
        if self.shape == ObjectShape.BOX:
            return np.array(self.size)
        elif self.shape == ObjectShape.CYLINDER:
            r, hz = self.size
            return np.array([r, r, hz])
        else:
            r = self.size[0]
            return np.array([r, r, r])

    @property
    def full_extents(self) -> np.ndarray:
        """Full dimensions (2 * half-extents)."""
        return self.aabb_half_extents * 2.0

    @property
    def max_horizontal_width(self) -> float:
        """Largest horizontal dimension — must be < 0.08 m for Panda grasping."""
        he = self.aabb_half_extents
        return float(max(he[0], he[1])) * 2.0


@dataclass
class SceneConfig:
    """
    Parameterised scene layout.

    Holds lists of ``ObjectSpec`` for occluders and targets plus their
    world positions.  When ``positions`` is ``None``, objects are placed
    randomly (using ``seed`` for reproducibility).

    Attributes:
        occluders: Specifications for occluder objects.
        targets: Specifications for target objects.
        occluder_positions: XY positions on the table (Z is derived from
            table height + object half-height).  ``None`` → random.
        target_positions: Same, for targets.
        seed: RNG seed for random placement.  ``None`` → non-deterministic.
        constrain_to_reach: When True, random XY sampling is restricted
            to the intersection of (a) a safe on-table window and (b)
            a disk around the robot base.  Used by stack_scene where
            every cube must be both pickable and a viable stack target
            (audit #30).
        n_hidden_targets: When > 0, the first N targets (index-order)
            are placed with XY biased to sit inside occluder footprints
            so they fail the camera's 8-corner visibility check
            (audit #29).  Requires at least one occluder.  The retry
            layer in test_full_pipeline.main() verifies the guarantee
            after spawn via oracle_detect_objects() and nudges the seed
            if it is not met.
    """
    occluders: List[ObjectSpec]
    targets: List[ObjectSpec]
    occluder_positions: Optional[List[List[float]]] = None
    target_positions: Optional[List[List[float]]] = None
    seed: Optional[int] = None
    constrain_to_reach: bool = False
    n_hidden_targets: int = 0
    # audit #49 — when True, spawn a fixed-base tray as a non-pickable
    # support surface (see BoxelTestEnv._create_tray).  Default off so
    # existing scenes/runs are unaffected.  The tray-stack goal mode
    # (audit #49 commit 3) auto-enables it.
    enable_tray: bool = False


# ---------------------------------------------------------------------------
# Preset scenes
# ---------------------------------------------------------------------------

def default_scene() -> SceneConfig:
    """
    Original hardcoded scene (3 occluders, 4 targets, all cubes).

    Preserved for backward compatibility and regression testing.
    Occluder cubes are 0.075 m on a side (0.0375 m half-extent) —
    graspable by the Panda gripper.  All positions within 0.65 m of
    robot base (fix #17: shifted -0.4 m in X, sizes halved from original).
    """
    return SceneConfig(
        occluders=[
            ObjectSpec(ObjectShape.BOX, [0.0375, 0.0375, 0.0375],
                       color=OBJECT_COLORS["red"],    mass=0.5, name="red_object"),
            ObjectSpec(ObjectShape.BOX, [0.0375, 0.0375, 0.0375],
                       color=OBJECT_COLORS["green"],  mass=0.5, name="green_object"),
            ObjectSpec(ObjectShape.BOX, [0.0375, 0.0375, 0.0375],
                       color=OBJECT_COLORS["orange"], mass=0.5, name="orange_object"),
        ],
        targets=[
            ObjectSpec(ObjectShape.BOX, [0.02, 0.02, 0.02],
                       color=OBJECT_COLORS["blue"],   mass=0.1, name="blue_object"),
            ObjectSpec(ObjectShape.BOX, [0.02, 0.02, 0.02],
                       color=OBJECT_COLORS["cyan"],   mass=0.1, name="cyan_object"),
            ObjectSpec(ObjectShape.BOX, [0.02, 0.02, 0.02],
                       color=OBJECT_COLORS["purple"], mass=0.1, name="purple_object"),
            ObjectSpec(ObjectShape.BOX, [0.02, 0.02, 0.02],
                       color=OBJECT_COLORS["yellow"], mass=0.1, name="yellow_object"),
        ],
        occluder_positions=[[0.1, 0.2], [0.2, -0.1], [0.0, -0.2]],
        target_positions=[[0.1, 0.4], [0.2, 0.1], [0.0, -0.1], [0.3, -0.2]],
    )


def mixed_shapes_scene(seed: int = 42) -> SceneConfig:
    """
    Scene with diverse shapes — cylinders, boxes, and spheres.

    All objects fit the Panda gripper (max horizontal width < 0.08 m).
    Occluders are tall enough (0.12–0.15 m) to cast shadows from the
    overhead camera that fully hide targets (0.04–0.06 m).
    """
    return SceneConfig(
        occluders=[
            ObjectSpec(ObjectShape.CYLINDER, [0.03, 0.075],
                       color=OBJECT_COLORS["red"],    mass=0.5, name="red_object"),
            ObjectSpec(ObjectShape.BOX, [0.03, 0.03, 0.075],
                       color=OBJECT_COLORS["orange"], mass=0.5, name="orange_object"),
            ObjectSpec(ObjectShape.CYLINDER, [0.035, 0.06],
                       color=OBJECT_COLORS["purple"], mass=0.5, name="purple_object"),
        ],
        targets=[
            ObjectSpec(ObjectShape.BOX, [0.025, 0.025, 0.025],
                       color=OBJECT_COLORS["blue"],   mass=0.1, name="blue_object"),
            ObjectSpec(ObjectShape.CYLINDER, [0.02, 0.03],
                       color=OBJECT_COLORS["cyan"],   mass=0.1, name="cyan_object"),
            ObjectSpec(ObjectShape.SPHERE, [0.025],
                       color=OBJECT_COLORS["green"],  mass=0.1, name="green_object"),
            ObjectSpec(ObjectShape.BOX, [0.02, 0.02, 0.03],
                       color=OBJECT_COLORS["yellow"], mass=0.1, name="yellow_object"),
        ],
        occluder_positions=[[0.5, 0.2], [0.6, -0.1], [0.4, -0.2]],
        target_positions=[[0.5, 0.4], [0.6, 0.1], [0.4, -0.1], [0.7, -0.2]],
        seed=seed,
    )


def stack_scene(n_objects: int = 3, seed: int = 0,
                cube_half_extent: float = 0.025) -> SceneConfig:
    """
    Scene for ``--goal stack`` (audit #30): ``n_objects`` identical cubes
    spawned at random reach-constrained positions on the table.

    Identical cubes guarantee flat-on-flat contact during stacking, so
    ``execute_stack`` can compute the release height from a single
    half-extent without per-pair geometry checks.  Every cube is a
    candidate to pick AND a candidate stack support — no occluders.

    Cubes are stored in the ``targets`` list (registered with
    ``is_visible=False``) only because that field has been historically
    used for "things the planner manipulates"; visibility is recomputed
    by ``oracle_detect_objects`` on the first camera pass anyway.

    Args:
        n_objects: Number of cubes to spawn.  Must be >= stack height.
        seed: RNG seed for reproducible XY positions.
        cube_half_extent: Half-side of each cube in metres.  0.025 m
            (5 cm cube) fits the Panda gripper and stacks reliably.
    """
    color_keys = list(OBJECT_COLORS.keys())

    targets = []
    for i in range(n_objects):
        ck = color_keys[i % len(color_keys)]
        suffix = "" if i < len(color_keys) else f"_{i // len(color_keys) + 1}"
        targets.append(ObjectSpec(
            ObjectShape.BOX,
            [cube_half_extent, cube_half_extent, cube_half_extent],
            color=OBJECT_COLORS[ck],
            mass=0.2,
            name=f"{ck}_object{suffix}",
        ))

    return SceneConfig(
        occluders=[],
        targets=targets,
        seed=seed,
        constrain_to_reach=True,
    )


def scalability_scene(n_occluders: int = 3, n_targets: int = 4,
                      n_hidden: int = 0,
                      seed: int = 0) -> SceneConfig:
    """
    Randomly generated scene for scalability evaluation.

    Occluder and target shapes are drawn from a pool; positions are
    randomised within the table bounds.  Use different ``seed`` values
    to produce distinct instances for batch evaluation.

    When ``n_hidden > 0``, the first ``n_hidden`` targets are placed
    with XY biased toward occluder footprints so they fail the
    camera's visibility check (audit #29).  The retry layer in
    ``test_full_pipeline.main()`` verifies the guarantee post-spawn
    and re-seeds if it is not met.  ``n_hidden`` is capped at
    ``n_targets``; callers must ensure ``n_occluders >= 1`` when
    requesting hidden targets.
    """
    n_hidden = max(0, min(int(n_hidden), int(n_targets)))
    if n_hidden > 0 and n_occluders < 1:
        raise ValueError(
            "scalability_scene: n_hidden > 0 requires n_occluders >= 1"
        )
    rng = np.random.RandomState(seed)

    # Cubes only — big occluders, small targets.  No cylinders, no
    # spheres, no rectangular boxes (user pref).  Half-extent ranges
    # are sized so an occluder reliably hides a target placed in its
    # shadow cone: big_half ≥ small_half + buffer in every axis, and
    # the lateral jitter window in ``_hidden_xy_positions`` (≈ occ_half
    # − target_half) stays positive so multiple hidden targets can sit
    # behind the same occluder.
    occluders = [
        ObjectSpec(ObjectShape.BOX,
                   [rng.uniform(0.030, 0.045)] * 3,
                   mass=0.5)
        for _ in range(n_occluders)
    ]
    targets = [
        ObjectSpec(ObjectShape.BOX,
                   [rng.uniform(0.020, 0.028)] * 3,
                   mass=0.1)
        for _ in range(n_targets)
    ]

    # Assign palette colours and names in index order.
    # Sizes/shapes above are unchanged; only color and name are set here.
    # Cycle through the 7-colour palette; append "_2", "_3"... on repeats.
    color_keys = list(OBJECT_COLORS.keys())
    used_names: Dict[str, int] = {}
    for i, spec in enumerate(occluders):
        ck = color_keys[i % len(color_keys)]
        base = f"{ck}_object"
        count = used_names.get(base, 0) + 1
        used_names[base] = count
        spec.color = OBJECT_COLORS[ck]
        spec.name = base if count == 1 else f"{base}_{count}"
    for j, spec in enumerate(targets):
        ck = color_keys[(n_occluders + j) % len(color_keys)]
        base = f"{ck}_object"
        count = used_names.get(base, 0) + 1
        used_names[base] = count
        spec.color = OBJECT_COLORS[ck]
        spec.name = base if count == 1 else f"{base}_{count}"

    return SceneConfig(
        occluders=occluders,
        targets=targets,
        seed=seed,
        n_hidden_targets=n_hidden,
    )


def random_pairs_scene(n_occluders: int = 3,
                       extra_distractors: int = 0,
                       seed: int = 0) -> SceneConfig:
    """
    Scene with a fixed occluder count and a randomly-drawn hidden-target
    count (audit #68).

    ``n_occluders`` is set by the caller (default 3); the per-run hidden
    count is drawn uniformly from ``[1, n_occluders]`` using ``seed`` so
    the same seed always produces the same scene.  Each hidden target is
    placed behind one of the occluders via the standard scalability_scene
    + _hidden_xy_positions path (audit #29 raycast verification).
    ``extra_distractors`` adds visible (non-hidden) distractor targets on
    top of the K hidden ones; required >= 1 for ``--goal
    find-and-tray-stack`` (auto-bumped in run_logger).

    Vary ``seed`` per run for structurally distinct scenes; run_logger
    draws a fresh seed by default when --scene random-pairs is selected
    without an explicit --seed.
    """
    if n_occluders < 1:
        raise ValueError(
            f"random_pairs_scene: n_occluders must be >= 1 "
            f"(got {n_occluders})"
        )
    if extra_distractors < 0:
        raise ValueError(
            "random_pairs_scene: extra_distractors must be >= 0"
        )
    rng = np.random.RandomState(seed)
    n_hidden = int(rng.randint(1, n_occluders + 1))
    cfg = scalability_scene(
        n_occluders=n_occluders,
        n_targets=n_hidden + int(extra_distractors),
        n_hidden=n_hidden,
        seed=seed,
    )
    # audit #70 (reopened 2026-05-12) — without this, occluders +
    # visible targets sample in the wide _TABLE_PLACE_* window and
    # ~half the placements fall outside the Panda's 0.65 m reach
    # disk; pick IK then succeeds via slack-beyond-comfort-reach
    # and the grasp constraint hangs the cube mid-air on lift.
    # Forcing constrain_to_reach pins occluders and visible-target
    # spawns to _SAFE_TABLE_* ∩ reach disk (same pattern as
    # stack_scene).  Hidden targets are placed behind occluders by
    # _hidden_xy_positions, which is reach-disk-unaware; if a
    # hidden target lands outside reach despite its occluder being
    # inside, the post-spawn assert in _create_objects /
    # _create_targets (audit #70 hardening) will catch it and
    # raise so the seed-retry layer can re-roll.
    cfg.constrain_to_reach = True
    return cfg


class BoxelTestEnv:
    """
    PyBullet environment for testing Semantic Boxel-based POD-TAMP.
    
    This environment creates a scene with:
    - A Franka Panda arm (fixed base)
    - Multiple occluder cubes (larger, can hide objects)
    - Multiple target cubes (smaller, may be hidden)
    - A fixed depth camera for perception
    - Oracle functions for object detection and pose estimation
    """
    
    def __init__(
        self,
        gui: bool = True,
        scene_config: Optional[SceneConfig] = None,
        camera_position: Optional[np.ndarray] = None,
        camera_target: Optional[np.ndarray] = None,
        camera_up: Optional[np.ndarray] = None,
        image_width: int = 640,
        image_height: int = 480,
        fov: float = 60.0,
        near_plane: float = 0.01,
        far_plane: float = 5.0,
        window_width: int = 1280,
        window_height: int = 600
    ):
        """
        Initialize the Boxel test environment.
        
        Args:
            gui: Whether to show the PyBullet GUI
            scene_config: Scene layout and object specifications.
                ``None`` → ``default_scene()`` (original hardcoded layout).
            camera_position: Position of the camera [x, y, z]
            camera_target: Point the camera looks at [x, y, z]
            camera_up: Camera up vector [x, y, z]
            image_width: Width of camera images in pixels
            image_height: Height of camera images in pixels
            fov: Field of view in degrees
            near_plane: Near clipping plane distance
            far_plane: Far clipping plane distance
            window_width: Width of the PyBullet GUI window
            window_height: Height of the PyBullet GUI window
        """
        self.scene_config = scene_config or default_scene()
        # Store camera parameters
        self.image_width = image_width
        self.image_height = image_height
        self.fov = fov
        self.near_plane = near_plane
        self.far_plane = far_plane
        
        # Set default camera position
        if camera_position is None:
            camera_position = np.array([0.1, -0.8, 0.7])
        if camera_target is None:
            camera_target = np.array([0.1, 0.0, 0.5])
        if camera_up is None:
            camera_up = np.array([0, 0, 1])
        
        self.camera_position = camera_position
        self.camera_target = camera_target
        self.camera_up = camera_up
        
        # Connect to PyBullet with window size options
        if gui:
            self.client_id = p.connect(p.GUI, options=f"--width={window_width} --height={window_height}")
            # Disable mouse picking so left-click rotates camera instead of grabbing objects
            p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 0)
            # Disable segmentation mask preview window
            p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)
            # Main view: match fixed semantic camera immediately (before resetSimulation).
            if np.allclose(self.camera_position, _DEFAULT_SEMANTIC_EYE) and np.allclose(
                self.camera_target, _DEFAULT_SEMANTIC_TARGET
            ):
                p.resetDebugVisualizerCamera(
                    cameraDistance=_DEFAULT_DEBUG_VIS_DISTANCE,
                    cameraYaw=_DEFAULT_DEBUG_VIS_YAW,
                    cameraPitch=_DEFAULT_DEBUG_VIS_PITCH,
                    cameraTargetPosition=list(_DEFAULT_DEBUG_VIS_TARGET),
                )
        else:
            self.client_id = p.connect(p.DIRECT)
        self._gui = gui

        # Reset simulation
        p.resetSimulation(physicsClientId=self.client_id)
        p.setGravity(0, 0, -9.81, physicsClientId=self.client_id)
        p.setRealTimeSimulation(0, physicsClientId=self.client_id)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(),
                                  physicsClientId=self.client_id)

        # Plan client (audit #46): a separate DIRECT-mode PyBullet world that
        # mirrors the live scene.  All planning-time work — IK, RRT-Connect,
        # plan_motion, and is_config_collision_free — runs against this client
        # so the visible arm in self.client_id is never teleported during
        # planner.plan().  The GUI no longer freezes; the per-IK rendering
        # toggle is moot on a DIRECT client.  Body ids do NOT match between
        # clients, so we keep self._gui_to_plan to translate at the planner
        # boundary; execution-side code keeps using the GUI ids unchanged.
        self.plan_client_id = p.connect(p.DIRECT)
        p.resetSimulation(physicsClientId=self.plan_client_id)
        p.setGravity(0, 0, -9.81, physicsClientId=self.plan_client_id)
        p.setRealTimeSimulation(0, physicsClientId=self.plan_client_id)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(),
                                  physicsClientId=self.plan_client_id)
        self._gui_to_plan: Dict[int, int] = {}
        self.plan_robot_id: Optional[int] = None

        # Store object information
        self.objects: Dict[str, ObjectInfo] = {}

        # Initialize the scene.  If placement fails partway (e.g. the
        # hidden-target budget is exhausted at an unlucky seed) we'd
        # otherwise leak the two PyBullet clients already opened above;
        # disconnect them so the caller's retry layer can reseed and
        # rebuild without accumulating dead physics servers.
        try:
            self._setup_scene()
        except Exception:
            self.close()
            raise
        
        # Initialize helper components
        self.shadow_calculator = ShadowCalculator(
            self.camera_position, self.table_surface_height,
            table_x_range=self.table_x_range, table_y_range=self.table_y_range
        )
        # Free-space workspace matches the safe placement footprint —
        # intersection of the physical table mesh and the Panda reach
        # disk (_SAFE_TABLE_*_RANGE, the same window used for spawning).
        # NOT the wider logical voxel grid (self.table_*_range), which is
        # deliberately extended past the near table edge for SHADOW
        # coverage only.  Generating free boxels over that wider volume
        # created cells overhanging the physical table edge (audit #44):
        # #43 made them unplaceable, but the wireframes still extended
        # into empty air past the near edge.  ShadowCalculator above
        # keeps the wider range so near-field shadow volumes behind
        # occluders remain covered.
        self.free_space_generator = FreeSpaceGenerator(
            self.table_surface_height,
            table_x_range=self._SAFE_TABLE_X_RANGE,
            table_y_range=self._SAFE_TABLE_Y_RANGE,
        )
        # audit #10 — uniform-grid baseline: drop-in replacement for the
        # octree-based FreeSpaceGenerator.  Default off (semantic);
        # enabled by setting ``use_uniform_grid=True`` after construction
        # (test_full_pipeline.main does this when --baseline=uniform).
        # Cell size is reassignable via ``set_uniform_cell_size`` so the
        # eval matrix can sweep it without recreating BoxelTestEnv.
        self.use_uniform_grid: bool = False
        self.uniform_grid_generator = UniformGridGenerator(
            self.table_surface_height,
            cell_size=0.05,
            table_x_range=self._SAFE_TABLE_X_RANGE,
            table_y_range=self._SAFE_TABLE_Y_RANGE,
        )
        self.visualizer = BoxelVisualizer()

        if self._gui and np.allclose(
            self.camera_position, _DEFAULT_SEMANTIC_EYE
        ) and np.allclose(self.camera_target, _DEFAULT_SEMANTIC_TARGET):
            # resetSimulation can reset the debug camera — re-apply fixed view after scene load.
            p.resetDebugVisualizerCamera(
                cameraDistance=_DEFAULT_DEBUG_VIS_DISTANCE,
                cameraYaw=_DEFAULT_DEBUG_VIS_YAW,
                cameraPitch=_DEFAULT_DEBUG_VIS_PITCH,
                cameraTargetPosition=list(_DEFAULT_DEBUG_VIS_TARGET),
            )
            self.debug_camera_distance = _DEFAULT_DEBUG_VIS_DISTANCE
            self.debug_camera_yaw = _DEFAULT_DEBUG_VIS_YAW
            self.debug_camera_pitch = _DEFAULT_DEBUG_VIS_PITCH
            self.debug_camera_target = np.array(_DEFAULT_DEBUG_VIS_TARGET, dtype=float)
        else:
            self.debug_camera_distance = 1.5
            self.debug_camera_yaw = 45.0
            self.debug_camera_pitch = -30.0
            self.debug_camera_target = np.array(
                [0.1, 0.0, self.table_surface_height], dtype=float
            )

        occ_shapes = [s.shape.value for s in self.scene_config.occluders]
        tgt_shapes = [s.shape.value for s in self.scene_config.targets]
        print("Boxel Test Environment initialized successfully!")
        print(f"Camera position: {self.camera_position}")
        print(f"Camera target: {self.camera_target}")
        print(f"Occluders: {len(occ_shapes)} ({', '.join(occ_shapes)})")
        print(f"Targets:   {len(tgt_shapes)} ({', '.join(tgt_shapes)})")
        print(f"Objects in scene: {list(self.objects.keys())}")

    # ------------------------------------------------------------------
    # Plan-client mirroring helpers (audit #46)
    # ------------------------------------------------------------------
    # _mirror_load_urdf and _mirror_spawn_object load/create the same body
    # in BOTH clients so motion planning sees the same scene as physics
    # execution.  Both helpers register the gui→plan body-id mapping so
    # callers that need to translate at the planner boundary can use
    # self.plan_body_id(gui_id).

    def _mirror_load_urdf(self, *args, **kwargs) -> int:
        """Load the same URDF in self.client_id and self.plan_client_id.

        Returns the GUI body id (callers store this in ObjectInfo and pass
        it to execution code unchanged).  The plan-side body id is recorded
        in self._gui_to_plan and looked up via plan_body_id().
        """
        kwargs.pop("physicsClientId", None)
        gid = p.loadURDF(*args, **kwargs, physicsClientId=self.client_id)
        pid = p.loadURDF(*args, **kwargs, physicsClientId=self.plan_client_id)
        self._gui_to_plan[gid] = pid
        return gid

    def _mirror_spawn_object(self, spec: 'ObjectSpec',
                             position: List[float]) -> int:
        """Create an ObjectSpec body in both clients; return the GUI body id."""
        gid = pid = None
        for cid in (self.client_id, self.plan_client_id):
            shape = spec.shape
            if shape == ObjectShape.BOX:
                half = list(spec.size)
                vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half,
                                          rgbaColor=spec.color,
                                          physicsClientId=cid)
                col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half,
                                             physicsClientId=cid)
            elif shape == ObjectShape.CYLINDER:
                r, hz = spec.size
                vis = p.createVisualShape(p.GEOM_CYLINDER, radius=r,
                                          length=hz * 2,
                                          rgbaColor=spec.color,
                                          physicsClientId=cid)
                col = p.createCollisionShape(p.GEOM_CYLINDER, radius=r,
                                             height=hz * 2,
                                             physicsClientId=cid)
            elif shape == ObjectShape.SPHERE:
                r = spec.size[0]
                vis = p.createVisualShape(p.GEOM_SPHERE, radius=r,
                                          rgbaColor=spec.color,
                                          physicsClientId=cid)
                col = p.createCollisionShape(p.GEOM_SPHERE, radius=r,
                                             physicsClientId=cid)
            else:
                raise ValueError(f"Unsupported shape: {shape}")
            body_id = p.createMultiBody(
                baseMass=spec.mass,
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=position,
                physicsClientId=cid,
            )
            if spec.lateral_friction != 0.5:
                p.changeDynamics(body_id, -1,
                                 lateralFriction=spec.lateral_friction,
                                 physicsClientId=cid)
            if cid == self.client_id:
                gid = body_id
            else:
                pid = body_id
        self._gui_to_plan[gid] = pid
        return gid

    def plan_body_id(self, gui_id: int) -> int:
        """Translate a GUI-client body id to the plan client's body id.

        Raises KeyError if gui_id wasn't created via the mirror helpers
        (i.e. exists only in the GUI world).  Use this at the planner
        boundary to build object_body_ids / support_body_ids.
        """
        return self._gui_to_plan[gui_id]

    def sync_to_plan_client(self, held_body_id: Optional[int] = None) -> None:
        """Mirror the live GUI-client state into the plan client.

        Call this once per replan (right before planner.plan()).  Cheap —
        a few dozen p.* calls — and avoids the per-IK save/restore handshake
        that the single-client design needed.

        Copies:
          * Base pose of every mirrored body (objects, plane, table, robot
            base — the latter is fixed but cheap to refresh).
          * All robot joint states (arm 0-6 + fingers + any fixed joints).
          * The held body (if any) inherits the EE pose via its base-pose
            sync; planning-time collision checks reposition it to each
            hypothetical EE config in is_config_collision_free.

        held_body_id is accepted for symmetry with execute_pick / pre-replan
        bookkeeping; it isn't required for correctness because the held
        body's base pose is already covered by the loop above.
        """
        for gid, pid in self._gui_to_plan.items():
            pos, orn = p.getBasePositionAndOrientation(
                gid, physicsClientId=self.client_id)
            p.resetBasePositionAndOrientation(
                pid, pos, orn, physicsClientId=self.plan_client_id)
        if self.plan_robot_id is not None:
            gui_robot = self.objects["robot"].object_id
            n_joints = p.getNumJoints(gui_robot,
                                      physicsClientId=self.client_id)
            for j in range(n_joints):
                angle, vel = p.getJointState(
                    gui_robot, j, physicsClientId=self.client_id)[:2]
                p.resetJointState(self.plan_robot_id, j, angle,
                                  targetVelocity=vel,
                                  physicsClientId=self.plan_client_id)

    def _setup_scene(self):
        """Set up the simulation scene with plane, table, robot, and objects."""
        # Load ground plane
        plane_id = self._mirror_load_urdf("plane.urdf", [0, 0, 0], [0, 0, 0, 1])
        self.objects["plane"] = ObjectInfo(
            object_id=plane_id, name="plane",
            position=np.array([0, 0, 0]), orientation=np.array([0, 0, 0, 1]),
            size=np.array([10, 10, 0.1]), is_visible=True, is_occluder=False
        )

        # Load table
        table_z_offset = -0.3
        table_position = [0.5, 0.0, table_z_offset]
        table_id = self._mirror_load_urdf("table/table.urdf", table_position,
                                          [0, 0, 0, 1], useFixedBase=True)
        self.table_surface_height = 0.625 + table_z_offset

        # XY bounds for voxelization / shadows / free-space (logical workspace).
        # Table mesh stays centered at [0.5, 0]; this window is shifted −0.4 m
        # in X so the voxel grid encloses objects near the robot without clipping.
        self.table_x_range = (-0.4, 0.6)
        self.table_y_range = (-0.5, 0.5)

        self.objects["table"] = ObjectInfo(
            object_id=table_id, name="table",
            position=np.array(table_position), orientation=np.array([0, 0, 0, 1]),
            size=np.array([1.0, 1.0, 0.8]), is_visible=True, is_occluder=False
        )

        # Load robot
        robot_pos = [-0.4, 0.0, 0.0]
        robot_id = self._mirror_load_urdf("franka_panda/panda.urdf", robot_pos,
                                          [0, 0, 0, 1], useFixedBase=True)
        self.plan_robot_id = self._gui_to_plan[robot_id]
        self.objects["robot"] = ObjectInfo(
            object_id=robot_id, name="robot",
            position=np.array(robot_pos), orientation=np.array([0, 0, 0, 1]),
            size=np.array([0.5, 0.5, 0.8]), is_visible=True, is_occluder=False
        )

        # Tray (audit #49) — fixed-base support surface, only spawned when
        # the scene_config opts in.  Created BEFORE occluders/targets so its
        # XY can be reserved against random-placement collisions.
        self._tray_xy: Optional[List[float]] = None
        if self.scene_config.enable_tray:
            self._create_tray()

        # Create occluders
        self._create_occluders()

        # Create targets
        self._create_targets()

        # Let objects settle under gravity after placement.
        # 10 steps at 240 Hz ≈ 0.04 s — sufficient for cubes on a flat
        # table to reach static equilibrium.
        for _ in range(10):
            p.stepSimulation(physicsClientId=self.client_id)

        self.update_object_positions()
    
    # ------------------------------------------------------------------
    # Object spawning (supports BOX, CYLINDER, SPHERE via ObjectSpec)
    # ------------------------------------------------------------------

    @staticmethod
    def _spawn_object(spec: ObjectSpec, position: List[float]) -> int:
        """
        Create a PyBullet rigid body from an ObjectSpec.

        Returns the PyBullet body ID.
        """
        shape = spec.shape
        if shape == ObjectShape.BOX:
            half = list(spec.size)
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half,
                                      rgbaColor=spec.color)
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half)
        elif shape == ObjectShape.CYLINDER:
            r, hz = spec.size
            vis = p.createVisualShape(p.GEOM_CYLINDER, radius=r,
                                      length=hz * 2, rgbaColor=spec.color)
            col = p.createCollisionShape(p.GEOM_CYLINDER, radius=r,
                                         height=hz * 2)
        elif shape == ObjectShape.SPHERE:
            r = spec.size[0]
            vis = p.createVisualShape(p.GEOM_SPHERE, radius=r,
                                      rgbaColor=spec.color)
            col = p.createCollisionShape(p.GEOM_SPHERE, radius=r)
        else:
            raise ValueError(f"Unsupported shape: {shape}")

        body_id = p.createMultiBody(baseMass=spec.mass,
                                    baseCollisionShapeIndex=col,
                                    baseVisualShapeIndex=vis,
                                    basePosition=position)
        if spec.lateral_friction != 0.5:
            p.changeDynamics(body_id, -1,
                             lateralFriction=spec.lateral_friction)
        return body_id

    # Robot base XY (matches franka_panda spawn in _setup_scene) and the
    # Panda's effective tabletop reach radius.  Used to keep random
    # placements inside the arm's workspace when constrain_to_reach=True.
    _ROBOT_BASE_XY = (-0.4, 0.0)
    _PANDA_REACH_RADIUS = 0.65

    # Reach-constrained on-table window: intersection of the actual
    # table mesh, the Panda reach disk, and a small edge buffer.  Used
    # by ``stack_scene`` (and any scene with ``constrain_to_reach=True``)
    # where every cube must be both pickable AND a viable stack target.
    _SAFE_TABLE_X_RANGE = (-0.1, 0.70)
    _SAFE_TABLE_Y_RANGE = (-0.40, 0.40)

    # Random-placement window for scenes that DO NOT constrain to reach
    # (scalability / random-pairs / scalability-derived).  Contained
    # inside the actual table mesh footprint (probed AABB ≈ x ∈ [-0.251,
    # 1.251], y ∈ [-0.501, 0.501] for the standard pybullet_data table
    # at [0.5, 0]) with an edge buffer that survives the additional
    # 0.10 m intra-object margin.  Lower x bound shifted from the old
    # voxel-grid value (-0.4) inward to -0.20 because anything at
    # x < -0.251 sat off the mesh and tipped off when physics started
    # (this was the "object placed outside the table" bug).  The wider
    # ``table_x_range`` / ``table_y_range`` describe the LOGICAL
    # voxel-grid workspace (extended back to x=-0.4 to enclose the
    # robot's near field for boxelization), NOT a valid spawn area.
    _TABLE_PLACE_X_RANGE = (-0.20, 0.60)
    _TABLE_PLACE_Y_RANGE = (-0.50, 0.50)

    def _random_xy_positions(self, n: int, rng: np.random.RandomState,
                             margin: float = 0.10,
                             constrain_to_reach: bool = False,
                             reach_radius: Optional[float] = None,
                             reserved_xys: Optional[List[List[float]]] = None,
                             ) -> List[List[float]]:
        """
        Sample *n* non-overlapping XY positions inside the on-table
        placement window (``_TABLE_PLACE_*_RANGE``; or
        ``_SAFE_TABLE_*_RANGE`` plus a reach-disk filter when
        ``constrain_to_reach`` is True).

        Uses rejection sampling with a minimum separation of ``margin``
        metres to avoid objects spawning on top of each other.

        When ``constrain_to_reach`` is True, samples must ALSO lie inside
        a disk of radius ``reach_radius`` around the robot base.  Used by
        scenes like ``stack`` where every object must be both pickable
        and a viable stack destination (audit #30).

        When ``reserved_xys`` is provided, samples must also stay at
        least ``margin`` away from those pre-existing positions.  Used
        by ``_create_targets`` to keep visible-target placements clear
        of occluders and pre-placed hidden targets (audit #29).
        """
        if constrain_to_reach:
            x_lo, x_hi = self._SAFE_TABLE_X_RANGE
            y_lo, y_hi = self._SAFE_TABLE_Y_RANGE
        else:
            x_lo, x_hi = self._TABLE_PLACE_X_RANGE
            y_lo, y_hi = self._TABLE_PLACE_Y_RANGE
        x_lo += margin
        x_hi -= margin
        y_lo += margin
        y_hi -= margin
        bx, by = self._ROBOT_BASE_XY
        r_max = (reach_radius if reach_radius is not None
                 else self._PANDA_REACH_RADIUS)
        reserved = list(reserved_xys) if reserved_xys else []
        positions = []
        # 400 rejection-sampling attempts per object — empirical budget
        # that succeeds for typical 2-8 object scenes within the safe
        # placement window.  Exhaustion is hard-raised below (no silent
        # fallback) so over-constrained configurations surface as
        # actionable errors.
        for _ in range(n * 400):
            if len(positions) >= n:
                break
            x = rng.uniform(x_lo, x_hi)
            y = rng.uniform(y_lo, y_hi)
            if constrain_to_reach and np.hypot(x - bx, y - by) > r_max:
                continue
            if any(np.hypot(x - px, y - py) < margin
                   for px, py in reserved):
                continue
            if all(np.hypot(x - px, y - py) >= margin
                   for px, py in positions):
                positions.append([x, y])
        if len(positions) < n:
            bounds_msg = (f"placement window x=({x_lo}, {x_hi}) "
                          f"y=({y_lo}, {y_hi})")
            if constrain_to_reach:
                bounds_msg += f" within reach={r_max}"
            raise RuntimeError(
                f"Could not place {n} objects with margin={margin} m in "
                f"{bounds_msg}"
            )
        return positions

    def _assert_xys_in_reach(self, xys, label: str) -> None:
        """audit #70 (reopened 2026-05-12) hardening.

        Raise RuntimeError if any (x, y) lies outside the Panda's
        _PANDA_REACH_RADIUS disk around _ROBOT_BASE_XY.  Callers gate
        this on cfg.constrain_to_reach so non-reach-bound scenes
        (default scalability matrix) are unaffected.

        Catches _hidden_xy_positions placements that escape the reach
        disk despite the parent occluder being inside it (the helper
        samples behind occluders without filtering), and defends any
        future caller-supplied cfg.{occluder,target}_positions that
        sidesteps _random_xy_positions' filter.  RuntimeError surfaces
        to the seed-retry layer in test_full_pipeline.main() (mirrors
        audit #29's hidden-target post-spawn check).
        """
        bx, by = self._ROBOT_BASE_XY
        r_max = self._PANDA_REACH_RADIUS
        for i, xy in enumerate(xys):
            d = float(np.hypot(float(xy[0]) - bx, float(xy[1]) - by))
            if d > r_max:
                raise RuntimeError(
                    f"audit #70: {label}[{i}] spawned at "
                    f"({float(xy[0]):.3f}, {float(xy[1]):.3f}) is "
                    f"{d:.3f} m from robot base — outside reach disk "
                    f"(r_max={r_max} m). Re-roll seed (--seed-retry) "
                    f"or widen --n-occluders."
                )

    # audit #49 — tray (fixed-base support surface, default-off).
    # Uses the built-in pybullet_data tray/traybox.urdf (textured mesh
    # visual, box-primitive collision, mass=0).  At globalScaling=0.4
    # the footprint is ~0.24 x 0.24 m with angled walls ~0.03 m high.
    # Position (0.10, 0.40) sits in the back-left corner of the table,
    # closest to the Panda base; for default_scene the (0.10, 0.40)
    # yellow target slot conflicts with this and needs to be moved when
    # enable_tray is opted in (random-placement scenes auto-reserve
    # via _create_targets).
    _TRAY_XY = (-0.130, 0.380)
    _TRAY_SCALE = 0.4
    _TRAY_NAME = "tray"

    def _create_tray(self):
        """Spawn the built-in traybox URDF as a non-pickable support (audit #49).

        Loaded via ``_mirror_load_urdf`` so both GUI and plan clients see
        it.  Registered in ``self.objects`` with ``is_tray=True`` so
        downstream filters (oracle_detect_objects, shadow loop, planner
        init) can recognise it.  ``self._tray_xy`` is exposed so random-
        placement helpers can reserve the footprint.
        """
        cx, cy = self._TRAY_XY
        cz = self.table_surface_height

        body_id = self._mirror_load_urdf(
            "tray/traybox.urdf",
            [cx, cy, cz],
            [0, 0, 0, 1],
            useFixedBase=True,
            globalScaling=self._TRAY_SCALE,
        )

        aabb_min, aabb_max = p.getAABB(body_id,
                                        physicsClientId=self.client_id)
        size = np.array([aabb_max[0] - aabb_min[0],
                         aabb_max[1] - aabb_min[1],
                         aabb_max[2] - aabb_min[2]])

        self.objects[self._TRAY_NAME] = ObjectInfo(
            object_id=body_id,
            name=self._TRAY_NAME,
            position=np.array([cx, cy, cz]),
            orientation=np.array([0, 0, 0, 1]),
            size=size,
            is_visible=True,
            is_occluder=False,
            is_tray=True,
        )
        self._tray_xy = [float(cx), float(cy)]

    def _create_occluders(self):
        """Create occluder objects on the table from scene_config."""
        cfg = self.scene_config
        rng = np.random.RandomState(cfg.seed)

        if cfg.occluder_positions is not None:
            xys = cfg.occluder_positions
        else:
            reserved = ([list(self._tray_xy)]
                        if self._tray_xy is not None else None)
            xys = self._random_xy_positions(
                len(cfg.occluders), rng,
                constrain_to_reach=cfg.constrain_to_reach,
                reserved_xys=reserved,
            )

        # audit #70 (reopened 2026-05-12) hardening — defends against
        # caller-supplied cfg.occluder_positions sidestepping the reach
        # filter.  _random_xy_positions already filters by reach when
        # constrain_to_reach=True; the assert is the safety net for
        # the pre-baked-positions path.  Gated so non-reach-bound
        # scenes stay on the wide _TABLE_PLACE_* window.
        if cfg.constrain_to_reach:
            self._assert_xys_in_reach(xys, "occluder")

        for i, (spec, xy) in enumerate(zip(cfg.occluders, xys)):
            he = spec.aabb_half_extents
            z = self.table_surface_height + float(he[2])
            pos = [xy[0], xy[1], z]

            body_id = self._mirror_spawn_object(spec, pos)
            name = spec.name if spec.name is not None else f"occluder_{i + 1}"
            self.objects[name] = ObjectInfo(
                object_id=body_id, name=name,
                position=np.array(pos), orientation=np.array([0, 0, 0, 1]),
                size=spec.full_extents, is_visible=True, is_occluder=True
            )

    def _hidden_xy_positions(
        self,
        target_specs: List[ObjectSpec],
        occluder_info: List[Tuple[Tuple[float, float], float]],
        rng: np.random.RandomState,
        hidden_margin: float = 0.10,
        reserved_xys: Optional[List[List[float]]] = None,
        constrain_to_reach: bool = False,
        reach_radius: Optional[float] = None,
    ) -> Optional[List[List[float]]]:
        """
        Sample XY positions that are GUARANTEED hidden from the camera
        (audit #29).

        For each target spec:
          1. Pick a random occluder; compute a shadow-axis unit vector
             pointing from the camera XY toward the occluder and
             continuing away.
          2. Sample a candidate XY slightly BEHIND the occluder along
             that axis (distance = target_half + occluder_half + buffer
             + small random radial + lateral jitter bounded by the
             occluder's own width).  This places the target in the
             occluder's shadow cone without physically overlapping it.
          3. Verify with PyBullet raycasts: 8 rays from camera to the 8
             shrunk AABB corners of the prospective target.  Accept
             only if every corner ray is intercepted by a non-background
             body (an occluder).  Same 8-corner criterion as
             ``oracle_detect_objects`` → the scene is self-consistent
             with the downstream visibility check.
          4. Physical-overlap margin against ``reserved_xys`` is
             computed per-occluder (occ_half + target_half + small
             buffer); the ``hidden_margin`` only applies to spacing
             between placed hidden targets, not to occluder clearance.

        Occluders are already spawned in PyBullet when this runs
        (``_create_occluders`` before ``_create_targets`` in
        ``_setup_scene``), so the raycast has live geometry to test
        against.

        Returns ``None`` if the per-slot 400-candidate budget is
        exhausted.  ``_create_targets`` then raises with an actionable
        error — no silent fallback, no retry loop.

        Args:
            target_specs: ObjectSpec for each target slot to hide
                (list length = N-hidden).  Needed to know each
                prospective AABB's half-extents.
            occluder_info: ``((x, y), horizontal_half_extent)`` tuples
                for every already-placed occluder.
            rng: Numpy RandomState for all sampling decisions.
            hidden_margin: Minimum XY separation between two hidden
                target centres, in metres.  Does NOT apply to
                occluders — those use physical-overlap margins only.
            reserved_xys: Pre-existing XY positions that the samples
                must stay clear of.  Must match ``occluder_info`` in
                order; entries beyond ``len(occluder_info)`` are
                treated as additional reserved points kept at the
                ``hidden_margin`` distance.
        """
        if not occluder_info or not target_specs:
            return None
        cam = [float(v) for v in self.camera_position]
        cam_x, cam_y = cam[0], cam[1]
        # Match _random_xy_positions: bound spawns to the actual table
        # mesh, not the wider voxelization workspace.  Otherwise a
        # candidate placed at x < ~-0.25 would tip off the table edge
        # when physics steps and the scene would silently lose objects.
        # audit #70 hardening (iii) — when constrain_to_reach, bound
        # candidates to _SAFE_TABLE_* (matches _random_xy_positions'
        # behaviour for visible-target placement) AND apply the
        # Panda reach-disk filter at sample time inside the candidate
        # loop below.  Without this the post-spawn _assert_xys_in_-
        # reach catches out-of-reach hidden targets and aborts under
        # strict --seed pinning (no --seed-retry).  Defended on
        # 2026-05-12 (later) repro: --seed 505998003 placed target[0]
        # at (0.225, 0.190), 3 mm beyond the reach disk, after the
        # original (i)+(ii) fix.
        if constrain_to_reach:
            x_lo, x_hi = self._SAFE_TABLE_X_RANGE
            y_lo, y_hi = self._SAFE_TABLE_Y_RANGE
        else:
            x_lo, x_hi = self._TABLE_PLACE_X_RANGE
            y_lo, y_hi = self._TABLE_PLACE_Y_RANGE
        x_lo += hidden_margin
        x_hi -= hidden_margin
        y_lo += hidden_margin
        y_hi -= hidden_margin
        bx, by = self._ROBOT_BASE_XY
        r_max = (reach_radius if reach_radius is not None
                 else self._PANDA_REACH_RADIUS)

        background_ids = set()
        for k in ("plane", "table", "robot"):
            if k in self.objects:
                background_ids.add(self.objects[k].object_id)

        # Shrink corners inward by EPS so rayTest does not touch the
        # AABB surface exactly (PyBullet returns ambiguous fractions
        # at grazing / coincident surfaces).
        EPS = 1e-3
        # Physical-overlap buffer between target and occluder bodies.
        OVERLAP_BUFFER = 0.005

        # Reserved entries BEYOND the known occluder list (hidden
        # targets generated earlier in the same call, other reserved
        # points the caller passed).  Those use hidden_margin.
        non_occluder_reserved: List[List[float]] = []
        if reserved_xys:
            non_occluder_reserved = [
                list(xy) for xy in reserved_xys[len(occluder_info):]
            ]

        positions: List[List[float]] = []
        for spec in target_specs:
            he = spec.aabb_half_extents
            hx, hy, hz = float(he[0]), float(he[1]), float(he[2])
            target_half = max(hx, hy)
            cz = self.table_surface_height + hz
            placed = False
            # 800 candidate attempts per hidden target — bumped from
            # 400 on 2026-05-12 (later) when audit #70 hardening (iii)
            # added the reach-disk filter inside the candidate loop.
            # The added filter rejects ~10-20% more candidates near the
            # back of the reach disk; the per-attempt success rate goes
            # down accordingly, so the budget doubles to keep the
            # exhaustion-rate-per-seed roughly constant for eval sweeps.
            # Bumped 800 -> 4000 on 2026-05-15 for audit #77: the
            # n_occluders=2 + n_hidden=2 and n_occluders=3 + n_hidden=3
            # corners of random_pairs_scene have the tightest feasibility
            # window (small placer disk behind small occluders intersected
            # with reach disk, table window, and 0.10 m spacing); at 800
            # the per-seed exhaustion rate was ~70% on the audit-77 eval
            # corpus, which would have dropped 2/3 of n_occluders=2 and
            # half of n_occluders=3 cells.  4000 puts the exhaustion rate
            # <5% per seed in those corners; cheap geometric tests
            # (~25 us/iter), so worst-case wall-clock impact per failing
            # seed is ~100 ms.
            # On exhaustion we return None and _create_targets raises
            # 'Could not place ...' which the seed-retry layer in
            # test_full_pipeline.main() treats as retryable (audit #68
            # auto-rolls under --seed-retry / seed_auto).
            for _ in range(4000):
                idx = int(rng.randint(len(occluder_info)))
                (ox, oy), occ_half = occluder_info[idx]
                dx = ox - cam_x
                dy = oy - cam_y
                norm = float(np.hypot(dx, dy))
                if norm < 1e-6:
                    continue
                ux = dx / norm
                uy = dy / norm
                # Perpendicular for lateral jitter within the occluder
                # silhouette width.
                px_u = -uy
                py_u = ux
                # Distance BEHIND the occluder center: at least enough
                # to clear physical overlap; add a small random bump so
                # multiple hidden targets don't stack on one line.
                base_d = occ_half + target_half + OVERLAP_BUFFER
                d = base_d + float(rng.uniform(0.0, max(occ_half, 1e-3)))
                lat_range = max(occ_half - target_half - OVERLAP_BUFFER,
                                0.0)
                lat = float(rng.uniform(-lat_range, lat_range))
                tx = ox + ux * d + px_u * lat
                ty = oy + uy * d + py_u * lat
                if not (x_lo <= tx <= x_hi and y_lo <= ty <= y_hi):
                    continue
                # audit #70 hardening (iii) — reach-disk filter at
                # sample time.  The post-spawn _assert_xys_in_reach
                # remains as a safety net for caller-supplied
                # cfg.target_positions that bypass this helper.
                if constrain_to_reach and np.hypot(tx - bx, ty - by) > r_max:
                    continue
                # Physical-overlap check against EVERY occluder (not
                # just the one we biased toward — the candidate may
                # collide with a neighbouring occluder).
                too_close_occ = False
                for (ox2, oy2), occ_half2 in occluder_info:
                    min_d = occ_half2 + target_half + OVERLAP_BUFFER
                    if np.hypot(tx - ox2, ty - oy2) < min_d:
                        too_close_occ = True
                        break
                if too_close_occ:
                    continue
                # Spacing margin against non-occluder reserved points
                # and already-accepted hidden targets.
                if any(np.hypot(tx - rx, ty - ry) < hidden_margin
                       for rx, ry in non_occluder_reserved):
                    continue
                if any(np.hypot(tx - px, ty - py) < hidden_margin
                       for px, py in positions):
                    continue
                corners = []
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        for sz in (-1, 1):
                            corners.append([
                                tx + sx * (hx - EPS),
                                ty + sy * (hy - EPS),
                                cz + sz * (hz - EPS),
                            ])
                # rayTestBatch numThreads=0: let Bullet pick max threads
                # (audit #69). Safe — no concurrent stepSimulation on this
                # client during target placement.
                hits = p.rayTestBatch([cam] * 8, corners, numThreads=0)
                all_occluded = True
                for h in hits:
                    hit_uid = h[0]
                    if hit_uid < 0 or hit_uid in background_ids:
                        all_occluded = False
                        break
                if not all_occluded:
                    continue
                positions.append([float(tx), float(ty)])
                placed = True
                break
            if not placed:
                return None
        return positions

    def _create_targets(self):
        """Create target objects on the table from scene_config."""
        cfg = self.scene_config
        rng = np.random.RandomState(
            cfg.seed + 1000 if cfg.seed is not None else None
        )

        if cfg.target_positions is not None:
            xys = cfg.target_positions
        else:
            n_total = len(cfg.targets)
            n_hidden = max(0, min(int(cfg.n_hidden_targets), n_total))

            # Pull live occluder XYs + horizontal half-extents from the
            # already-spawned ObjectInfo records instead of threading a
            # second data stream through SceneConfig.
            occluder_info = [
                ((float(info.position[0]), float(info.position[1])),
                 float(max(info.size[0], info.size[1]) / 2.0))
                for info in self.objects.values() if info.is_occluder
            ]
            reserved_xys: List[List[float]] = [
                list(xy) for xy, _ in occluder_info
            ]
            # audit #49 — also reserve the tray footprint when present so
            # random target placement does not spawn cubes inside the tray.
            if self._tray_xy is not None:
                reserved_xys.append(list(self._tray_xy))

            hidden_xys: List[List[float]] = []
            if n_hidden > 0 and occluder_info:
                result = self._hidden_xy_positions(
                    target_specs=cfg.targets[:n_hidden],
                    occluder_info=occluder_info,
                    rng=rng,
                    hidden_margin=0.10,
                    reserved_xys=reserved_xys,
                    constrain_to_reach=cfg.constrain_to_reach,
                )
                if result is None:
                    # Single-shot contract: if the raycast-verified
                    # placement helper cannot satisfy the request, fail
                    # immediately with an actionable error.  No silent
                    # fallback to random placement — that would produce
                    # a scene that does not match the --n-hidden promise
                    # (audit #29).
                    raise RuntimeError(
                        f"Could not place {n_hidden} hidden targets "
                        f"with {len(occluder_info)} occluders at "
                        f"seed={cfg.seed}. Try --n-occluders higher, "
                        f"--n-hidden lower, or a different --seed."
                    )
                hidden_xys = result
                reserved_xys = reserved_xys + hidden_xys

            n_remaining = n_total - len(hidden_xys)
            if n_remaining > 0:
                visible_xys = self._random_xy_positions(
                    n_remaining, rng,
                    constrain_to_reach=cfg.constrain_to_reach,
                    reserved_xys=reserved_xys,
                )
            else:
                visible_xys = []

            xys = hidden_xys + visible_xys

        # audit #70 (reopened 2026-05-12) hardening — _hidden_xy_-
        # positions is reach-disk-unaware (samples behind occluders
        # without filtering), so a hidden target whose parent occluder
        # sits at the back of the reach disk can land beyond it.  This
        # assert catches that case (and any caller-supplied
        # cfg.target_positions sidestepping the filter).  RuntimeError
        # triggers seed-retry via test_full_pipeline.main() (audit #29
        # mechanism).
        if cfg.constrain_to_reach:
            self._assert_xys_in_reach(xys, "target")

        for i, (spec, xy) in enumerate(zip(cfg.targets, xys)):
            he = spec.aabb_half_extents
            z = self.table_surface_height + float(he[2])
            pos = [xy[0], xy[1], z]

            body_id = self._mirror_spawn_object(spec, pos)
            name = spec.name if spec.name is not None else f"target_{i + 1}"
            self.objects[name] = ObjectInfo(
                object_id=body_id, name=name,
                position=np.array(pos), orientation=np.array([0, 0, 0, 1]),
                size=spec.full_extents, is_visible=False, is_occluder=False
            )
    
    def generate_boxels(self, visible_objects: List[str]) -> List[BoxelData]:
        """
        Generate Semantic BoxelData for visible objects and their shadows.

        Object boxels get ``id=<object_name>`` (e.g. "red_object") so the
        planner can reference them with their human-readable label.
        Shadow boxels get ``id=shadow_of_<object_name>`` and
        ``created_by_boxel_id`` / ``created_by_object`` set to the parent
        object name (which is also the parent's boxel ID).

        Args:
            visible_objects: List of visible object names.

        Returns:
            List of OBJECT + SHADOW BoxelData with semantic IDs and parent
            relationships fully populated, ready to be added to a registry.
        """
        table_z = self.table_surface_height
        on_surface_tol = 0.01  # PyBullet contact margin + AABB rounding

        object_boxels: List[BoxelData] = []
        for obj_name in visible_objects:
            if obj_name not in self.objects:
                continue

            obj_info = self.objects[obj_name]
            aabb_min, aabb_max = p.getAABB(obj_info.object_id)
            aabb_min = np.array(aabb_min)
            aabb_max = np.array(aabb_max)

            object_boxels.append(BoxelData(
                id=obj_name,
                boxel_type=BoxelType.OBJECT,
                min_corner=aabb_min,
                max_corner=aabb_max,
                object_name=obj_name,
                is_occluder=False,  # set below if any shadow is cast
                on_surface="table" if aabb_min[2] <= table_z + on_surface_tol else None,
                surface_z=table_z,
            ))

        # Compute shadows; mark casters as occluders.
        # audit #49 — tray (is_tray=True) is a support surface, not an
        # occluder.  Skip it as a shadow CASTER so no shadow_of_tray
        # boxel is generated and no blocks_view_at facts emit for it.
        # The tray remains in obstacles for OTHER objects' shadow rays
        # (its 3 cm walls barely obstruct anything anyway).
        #
        # Audit #68 follow-up — previously-computed shadows are passed
        # in as obstacles too, so overlap regions get carved out of the
        # later shadow and each table point belongs to at most one
        # SHADOW boxel.  Without this, two shadows that overlap both
        # claim "target might be here", and sensing one leaves the
        # other's overlap region still flagged unknown — the planner
        # then re-plans to sense the same physical volume from the
        # other shadow's name.  Iteration order is sorted by parent
        # object name so the carve is deterministic across runs.
        shadow_boxels: List[BoxelData] = []
        for obj_boxel in sorted(object_boxels, key=lambda b: b.id):
            obj_info = self.objects.get(obj_boxel.id)
            if obj_info is not None and obj_info.is_tray:
                continue
            obstacles = [b for b in object_boxels if b.id != obj_boxel.id]
            obstacles.extend(shadow_boxels)
            shadow_parts = self.shadow_calculator.calculate_shadow_boxel(
                obj_boxel, obstacles)

            if shadow_parts:
                obj_boxel.is_occluder = True

            for idx, sp in enumerate(shadow_parts):
                # ShadowCalculator leaves ID empty; assign a stable
                # "shadow_of_<parent>" name and link parent ↔ shadow IDs
                # so downstream consumers (planner, visualizer) can
                # rely on the relationship.  Audit #72: shadow_parts is
                # 2+ slabs per occluder (option C two-slab carve, plus
                # any obstacle-subtraction fragments).  Suffix the ID
                # with __NN when more than one slab exists so the
                # registry's id-keyed dict doesn't overwrite earlier
                # slabs.  Single-slab case keeps the bare name for
                # backward compat.
                suffix = f"__{idx:02d}" if len(shadow_parts) > 1 else ""
                sp.id = f"shadow_of_{obj_boxel.id}{suffix}"
                sp.created_by_boxel_id = obj_boxel.id
                sp.on_surface = (
                    "table"
                    if sp.min_corner[2] <= table_z + on_surface_tol
                    else None
                )
                sp.surface_z = table_z
                obj_boxel.shadow_boxel_ids.append(sp.id)
                shadow_boxels.append(sp)

        return object_boxels + shadow_boxels

    def generate_free_space(self, known_boxels: List[BoxelData],
                            visualize: bool = False) -> List[BoxelData]:
        """
        Discretize the free space using octree subdivision.

        Args:
            known_boxels: List of OBJECT + SHADOW BoxelData (the obstacles).
            visualize: If True, animates the generation process.

        Returns:
            List of FREE_SPACE BoxelData fragments (with empty IDs).
            ``on_surface`` / ``surface_z`` are NOT populated here — the
            execution layer annotates them after cell merging because
            CellMerger emits fresh BoxelData copies that would otherwise
            strip these fields.

        Under the uniform-grid baseline (``use_uniform_grid=True``,
        audit #10) the call dispatches to UniformGridGenerator instead;
        the static lattice replaces the adaptive octree, only the labels
        on each cell flip as objects are revealed/moved.
        """
        if self.use_uniform_grid:
            return self.uniform_grid_generator.generate(
                known_boxels, visualize
            )
        return self.free_space_generator.generate(known_boxels, visualize)

    def set_uniform_cell_size(self, cell_size: float) -> None:
        """Recreate the uniform-grid generator with a new cell size.

        Used by ``test_full_pipeline`` when --uniform-cell-size is passed
        on the CLI; cell size is hyperparameter-scope, not run-scope, so
        rebuilding the lattice once at startup is fine.
        """
        self.uniform_grid_generator = UniformGridGenerator(
            self.table_surface_height,
            cell_size=cell_size,
            table_x_range=self._SAFE_TABLE_X_RANGE,
            table_y_range=self._SAFE_TABLE_Y_RANGE,
        )

    def annotate_free_space_surface(self, free_boxels: List[BoxelData]) -> None:
        """
        Set ``on_surface`` / ``surface_z`` on FREE_SPACE BoxelData.

        Free-space cells flow through stateless geometry stages
        (FreeSpaceGenerator → CellMerger) before reaching the registry.
        Those stages don't know the table height, so this helper carries
        that knowledge to the call site.  Required by the planner so
        ``place`` actions (precondition: ``(on_surface ?b)``) can fire.

        A free boxel is "on the table" only when BOTH:
          (a) its bottom is within 0.01 m of the table z (existing test), AND
          (b) its XY CENTRE lies within ``_SAFE_TABLE_*_RANGE`` — the
              intersection of the physical table mesh and the Panda's
              reach disk (same window used for spawning).
        The logical voxel grid extends to x=-0.4 m (behind the robot) so
        shadow volumes cover the near field; without (b) the planner
        would pick FREE boxels whose centre is off the table mesh, and
        execute_place (which drops at boxel.center) would release the
        object over empty air.  Observed 2026-04-26: cubes falling off
        the near edge in front of the robot (audit #43).

        Mutates ``free_boxels`` in place.  The 0.01 m tolerance accounts
        for PyBullet contact margin and AABB rounding.
        """
        table_z = self.table_surface_height
        x_lo, x_hi = self._SAFE_TABLE_X_RANGE
        y_lo, y_hi = self._SAFE_TABLE_Y_RANGE
        for b in free_boxels:
            on_z = b.min_corner[2] <= table_z + 0.01
            cx = 0.5 * (b.min_corner[0] + b.max_corner[0])
            cy = 0.5 * (b.min_corner[1] + b.max_corner[1])
            on_xy = (x_lo <= cx <= x_hi) and (y_lo <= cy <= y_hi)
            b.on_surface = "table" if (on_z and on_xy) else None
            b.surface_z = table_z

    def _view_and_projection_matrices(self):
        """View and projection matrices for the semantic camera (matches oracle rays)."""
        view_matrix = p.computeViewMatrix(
            cameraEyePosition=self.camera_position,
            cameraTargetPosition=self.camera_target,
            cameraUpVector=self.camera_up,
        )
        projection_matrix = p.computeProjectionMatrixFOV(
            fov=self.fov,
            aspect=self.image_width / self.image_height,
            nearVal=self.near_plane,
            farVal=self.far_plane,
        )
        return view_matrix, projection_matrix

    def refresh_debug_camera_views(self) -> None:
        """
        Re-run the OpenGL camera render (no return values needed).

        PyBullet's ExampleBrowser shows RGB/depth in the left panes when the
        hardware renderer draws the off-screen camera; that only happens while
        COV_ENABLE_RENDERING is on.  Call after exiting RenderingLock or
        between executed actions so the thumbnails update.
        """
        if not self._gui:
            return
        view_matrix, projection_matrix = self._view_and_projection_matrices()
        p.getCameraImage(
            width=self.image_width,
            height=self.image_height,
            viewMatrix=view_matrix,
            projectionMatrix=projection_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL,
        )

    def get_camera_observation(self) -> CameraObservation:
        """
        Capture an observation from the camera.

        In GUI mode, order matches pre--#56 history (e.g. parent of ff6384f):
        ``getCameraImage`` first so ExampleBrowser RGB/depth panes update, then
        oracle boxels.  In DIRECT mode, skip rendering (audit #56 fast path).
        """
        if not self._gui:
            visible_objects, object_poses = self.oracle_detect_objects()
            boxels = self.generate_boxels(visible_objects)
            return CameraObservation(
                visible_objects=visible_objects,
                object_poses=object_poses,
                boxels=boxels,
            )

        view_matrix, projection_matrix = self._view_and_projection_matrices()
        _, _, rgb_array, depth_array, _ = p.getCameraImage(
            width=self.image_width,
            height=self.image_height,
            viewMatrix=view_matrix,
            projectionMatrix=projection_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL,
        )
        rgb_image = np.array(rgb_array, dtype=np.uint8).reshape(
            (self.image_height, self.image_width, 4)
        )[:, :, :3]
        depth_image = self._depth_buffer_to_meters(
            np.array(depth_array).reshape((self.image_height, self.image_width))
        )
        # Point cloud is not used by any downstream consumer; commented
        # out to avoid the expensive depth→world-coordinate transform.
        # Re-enable if a real perception pipeline replaces the oracle.
        # point_cloud = self._depth_to_point_cloud(
        #     depth_image, view_matrix, projection_matrix
        # )

        visible_objects, object_poses = self.oracle_detect_objects()
        boxels = self.generate_boxels(visible_objects)

        return CameraObservation(
            rgb_image=rgb_image,
            depth_image=depth_image,
            visible_objects=visible_objects,
            object_poses=object_poses,
            boxels=boxels,
        )
    
    def _depth_buffer_to_meters(self, depth_buffer: np.ndarray) -> np.ndarray:
        """Convert depth buffer values to meters."""
        return self.far_plane * self.near_plane / (
            self.far_plane - (self.far_plane - self.near_plane) * depth_buffer
        )
    
    def _depth_to_point_cloud(self, depth_image: np.ndarray, view_matrix, projection_matrix) -> np.ndarray:
        """Convert depth image to 3D point cloud."""
        height, width = depth_image.shape
        u, v = np.meshgrid(np.arange(width), np.arange(height))
        z_ndc = depth_image.flatten()
        
        fx = fy = (width / 2.0) / np.tan(np.radians(self.fov / 2.0))
        cx, cy = width / 2.0, height / 2.0
        
        x_cam = (u.flatten() - cx) * z_ndc / fx
        y_cam = (v.flatten() - cy) * z_ndc / fy
        
        points_cam = np.stack([x_cam, y_cam, z_ndc], axis=1)
        
        view_matrix_4x4 = np.array(view_matrix).reshape(4, 4)
        camera_to_world = np.linalg.inv(view_matrix_4x4)
        
        points_cam_homogeneous = np.hstack([points_cam, np.ones((points_cam.shape[0], 1))])
        points_world = (camera_to_world @ points_cam_homogeneous.T).T[:, :3]
        
        valid_mask = (points_world[:, 2] > -1.0) & (points_world[:, 2] < 2.0)
        return points_world[valid_mask]
    
    def oracle_detect_objects(self, check_occlusion: bool = True) -> Tuple[List[str], Dict[str, Tuple[np.ndarray, np.ndarray]]]:
        """
        Oracle function to detect visible objects and their poses.

        Visibility is determined by casting rays from the camera to the
        8 corners of each object's AABB.  An object is visible if ANY ray
        reaches it (hit body == object body).  This catches partial
        visibility where an object edge sticks out from behind an occluder.

        Only used for initial scene observation — the sensing action uses
        ``sense_shadow_raycasting()`` with its own ray grid.
        
        Returns:
            Tuple of (visible object names, dict of all object poses)
        """
        visible_objects = []
        object_poses = {}
        
        for name, obj_info in self.objects.items():
            if name in ["plane", "table", "robot"]:
                continue
            
            pos, orn = p.getBasePositionAndOrientation(obj_info.object_id)
            position = np.array(pos)
            orientation = np.array(orn)
            
            obj_info.position = position
            obj_info.orientation = orientation
            
            is_visible = True
            if check_occlusion:
                aabb_min, aabb_max = p.getAABB(obj_info.object_id)
                ray_targets = []
                for x in (aabb_min[0], aabb_max[0]):
                    for y in (aabb_min[1], aabb_max[1]):
                        for z in (aabb_min[2], aabb_max[2]):
                            ray_targets.append([x, y, z])

                cam = self.camera_position.tolist()
                # rayTestBatch numThreads=0: let Bullet pick max threads
                # (audit #69). Safe — Phase 1/4 calls are sequential w.r.t.
                # stepSimulation on this client.
                results = p.rayTestBatch(
                    [cam] * len(ray_targets), ray_targets, numThreads=0,
                )
                is_visible = any(
                    r[0] == obj_info.object_id for r in results
                )
            
            obj_info.is_visible = is_visible
            if is_visible:
                visible_objects.append(name)
            object_poses[name] = (position.copy(), orientation.copy())
        
        return visible_objects, object_poses

    def update_object_positions(self):
        """
        Synchronise every dynamic object's ObjectInfo with its current PyBullet
        pose.  Call this after any batch of physics steps (settling, pushing,
        etc.) so that downstream code never uses stale spawn-time positions.

        Static bodies (plane, table, robot) are skipped — they cannot move.
        """
        for name, obj_info in self.objects.items():
            if name in ("plane", "table", "robot"):
                continue
            pos, orn = p.getBasePositionAndOrientation(obj_info.object_id)
            obj_info.position = np.array(pos)
            obj_info.orientation = np.array(orn)

    def step_simulation(self, num_steps: int = 1):
        """Step the simulation forward (GUI client only — physics lives there)."""
        for _ in range(num_steps):
            p.stepSimulation(physicsClientId=self.client_id)

    def reset(self, scene_config: Optional[SceneConfig] = None):
        """
        Reset the environment to initial state.

        Args:
            scene_config: New scene layout.  ``None`` → reuse the config
                from ``__init__``.
        """
        if scene_config is not None:
            self.scene_config = scene_config
        for cid in (self.client_id, self.plan_client_id):
            p.resetSimulation(physicsClientId=cid)
            p.setGravity(0, 0, -9.81, physicsClientId=cid)
            p.setRealTimeSimulation(0, physicsClientId=cid)
            p.setAdditionalSearchPath(pybullet_data.getDataPath(),
                                      physicsClientId=cid)
        self._gui_to_plan.clear()
        self.plan_robot_id = None
        self.objects.clear()
        self._setup_scene()

    def close(self):
        """Close both PyBullet connections (GUI + plan client)."""
        try:
            p.disconnect(self.client_id)
        except Exception:
            pass
        try:
            p.disconnect(self.plan_client_id)
        except Exception:
            pass
