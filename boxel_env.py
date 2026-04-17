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

from boxel_types import ObjectInfo, Boxel, CameraObservation
from shadow_calculator import ShadowCalculator
from free_space import FreeSpaceGenerator
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
    """
    occluders: List[ObjectSpec]
    targets: List[ObjectSpec]
    occluder_positions: Optional[List[List[float]]] = None
    target_positions: Optional[List[List[float]]] = None
    seed: Optional[int] = None


# ---------------------------------------------------------------------------
# Preset scenes
# ---------------------------------------------------------------------------

def default_scene() -> SceneConfig:
    """
    Original hardcoded scene (3 occluders, 4 targets, all cubes).

    Preserved for backward compatibility and regression testing.
    Occluder cubes are 0.075 m half-extent (7.5 cm) — graspable by
    the Panda gripper.  All positions within 0.65 m of robot base
    (fix #17: shifted -0.4 m in X, sizes halved from original).
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


def scalability_scene(n_occluders: int = 3, n_targets: int = 4,
                      seed: int = 0) -> SceneConfig:
    """
    Randomly generated scene for scalability evaluation.

    Occluder and target shapes are drawn from a pool; positions are
    randomised within the table bounds.  Use different ``seed`` values
    to produce distinct instances for batch evaluation.
    """
    rng = np.random.RandomState(seed)

    occ_pool = [
        lambda: ObjectSpec(ObjectShape.CYLINDER,
                           [rng.uniform(0.025, 0.035),
                            rng.uniform(0.06, 0.08)],
                           mass=0.5),
        lambda: ObjectSpec(ObjectShape.BOX,
                           [rng.uniform(0.025, 0.035),
                            rng.uniform(0.025, 0.035),
                            rng.uniform(0.06, 0.08)],
                           mass=0.5),
    ]

    tgt_pool = [
        lambda: ObjectSpec(ObjectShape.BOX,
                           [rng.uniform(0.02, 0.03)] * 3,
                           mass=0.1),
        lambda: ObjectSpec(ObjectShape.CYLINDER,
                           [rng.uniform(0.015, 0.025),
                            rng.uniform(0.025, 0.035)],
                           mass=0.1),
        lambda: ObjectSpec(ObjectShape.SPHERE,
                           [rng.uniform(0.02, 0.028)],
                           mass=0.1),
    ]

    occluders = [rng.choice(occ_pool)() for _ in range(n_occluders)]
    targets = [rng.choice(tgt_pool)() for _ in range(n_targets)]

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
    )


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
        p.resetSimulation()
        p.setGravity(0, 0, -9.81)  # standard gravitational acceleration
        p.setRealTimeSimulation(0)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        # Store object information
        self.objects: Dict[str, ObjectInfo] = {}
        
        # Initialize the scene
        self._setup_scene()
        
        # Initialize helper components
        self.shadow_calculator = ShadowCalculator(
            self.camera_position, self.table_surface_height,
            table_x_range=self.table_x_range, table_y_range=self.table_y_range
        )
        self.free_space_generator = FreeSpaceGenerator(
            self.table_surface_height,
            table_x_range=self.table_x_range, table_y_range=self.table_y_range
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

    def _setup_scene(self):
        """Set up the simulation scene with plane, table, robot, and objects."""
        # Load ground plane
        plane_id = p.loadURDF("plane.urdf", [0, 0, 0], [0, 0, 0, 1])
        self.objects["plane"] = ObjectInfo(
            object_id=plane_id, name="plane",
            position=np.array([0, 0, 0]), orientation=np.array([0, 0, 0, 1]),
            size=np.array([10, 10, 0.1]), is_visible=True, is_occluder=False
        )
        
        # Load table
        table_z_offset = -0.3
        table_position = [0.5, 0.0, table_z_offset]
        table_id = p.loadURDF("table/table.urdf", table_position, [0, 0, 0, 1], useFixedBase=True)
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
        robot_id = p.loadURDF("franka_panda/panda.urdf", robot_pos, [0, 0, 0, 1], useFixedBase=True)
        self.objects["robot"] = ObjectInfo(
            object_id=robot_id, name="robot",
            position=np.array(robot_pos), orientation=np.array([0, 0, 0, 1]),
            size=np.array([0.5, 0.5, 0.8]), is_visible=True, is_occluder=False
        )
        
        # Create occluders
        self._create_occluders()
        
        # Create targets
        self._create_targets()
        
        # Let objects settle under gravity after placement.
        # 10 steps at 240 Hz ≈ 0.04 s — sufficient for cubes on a flat
        # table to reach static equilibrium.
        for _ in range(10):
            p.stepSimulation()
        
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

    def _random_xy_positions(self, n: int, rng: np.random.RandomState,
                             margin: float = 0.10) -> List[List[float]]:
        """
        Sample *n* non-overlapping XY positions within the table bounds.

        Uses rejection sampling with a minimum separation of ``margin``
        metres to avoid objects spawning on top of each other.
        """
        x_lo, x_hi = self.table_x_range
        y_lo, y_hi = self.table_y_range
        x_lo += margin
        x_hi -= margin
        y_lo += margin
        y_hi -= margin
        positions = []
        for _ in range(n * 200):
            if len(positions) >= n:
                break
            x = rng.uniform(x_lo, x_hi)
            y = rng.uniform(y_lo, y_hi)
            if all(np.hypot(x - px, y - py) >= margin
                   for px, py in positions):
                positions.append([x, y])
        if len(positions) < n:
            raise RuntimeError(
                f"Could not place {n} objects with margin={margin} m "
                f"in table bounds x={self.table_x_range} y={self.table_y_range}"
            )
        return positions

    def _create_occluders(self):
        """Create occluder objects on the table from scene_config."""
        cfg = self.scene_config
        rng = np.random.RandomState(cfg.seed)

        if cfg.occluder_positions is not None:
            xys = cfg.occluder_positions
        else:
            xys = self._random_xy_positions(len(cfg.occluders), rng)

        for i, (spec, xy) in enumerate(zip(cfg.occluders, xys)):
            he = spec.aabb_half_extents
            z = self.table_surface_height + float(he[2])
            pos = [xy[0], xy[1], z]

            body_id = self._spawn_object(spec, pos)
            name = spec.name if spec.name is not None else f"occluder_{i + 1}"
            self.objects[name] = ObjectInfo(
                object_id=body_id, name=name,
                position=np.array(pos), orientation=np.array([0, 0, 0, 1]),
                size=spec.full_extents, is_visible=True, is_occluder=True
            )

    def _create_targets(self):
        """Create target objects on the table from scene_config."""
        cfg = self.scene_config
        rng = np.random.RandomState(
            cfg.seed + 1000 if cfg.seed is not None else None
        )

        if cfg.target_positions is not None:
            xys = cfg.target_positions
        else:
            xys = self._random_xy_positions(len(cfg.targets), rng)

        for i, (spec, xy) in enumerate(zip(cfg.targets, xys)):
            he = spec.aabb_half_extents
            z = self.table_surface_height + float(he[2])
            pos = [xy[0], xy[1], z]

            body_id = self._spawn_object(spec, pos)
            name = spec.name if spec.name is not None else f"target_{i + 1}"
            self.objects[name] = ObjectInfo(
                object_id=body_id, name=name,
                position=np.array(pos), orientation=np.array([0, 0, 0, 1]),
                size=spec.full_extents, is_visible=False, is_occluder=False
            )
    
    def generate_boxels(self, visible_objects: List[str]) -> List[Boxel]:
        """
        Generate Semantic Boxels for visible objects and their shadows.
        
        Args:
            visible_objects: List of visible object names
            
        Returns:
            List of Boxel objects (objects + shadows)
        """
        boxels = []
        solid_boxels = []
        
        # Generate object boxels (initially not marked as occluders)
        for obj_name in visible_objects:
            if obj_name not in self.objects:
                continue
                
            obj_info = self.objects[obj_name]
            aabb_min, aabb_max = p.getAABB(obj_info.object_id)
            
            center = (np.array(aabb_min) + np.array(aabb_max)) / 2.0
            extent = (np.array(aabb_max) - np.array(aabb_min)) / 2.0
            
            obj_boxel = Boxel(center=center, extent=extent, object_name=obj_name,
                             is_occluded=False, is_shadow=False, is_occluder=False)
            solid_boxels.append(obj_boxel)

        # Generate shadow boxels and mark objects as occluders if they cast shadows
        for obj_boxel in solid_boxels:
            obstacles = [b for b in solid_boxels if b.object_name != obj_boxel.object_name]
            shadow_parts = self.shadow_calculator.calculate_shadow_boxel(obj_boxel, obstacles)
            
            # If this object casts any shadows, mark it as an occluder
            if shadow_parts:
                obj_boxel.is_occluder = True
            
            boxels.extend(shadow_parts)
        
        # Add all object boxels (now with correct is_occluder status)
        boxels.extend(solid_boxels)
            
        return boxels
    
    def generate_free_space(self, known_boxels: List[Boxel], visualize: bool = False) -> List[Boxel]:
        """
        Discretize the free space using octree subdivision.
        
        Args:
            known_boxels: List of known boxels (objects + shadows)
            visualize: If True, animates the generation process
            
        Returns:
            List of free space boxels
        """
        return self.free_space_generator.generate(known_boxels, visualize)

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
                results = p.rayTestBatch(
                    [cam] * len(ray_targets), ray_targets
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
        """Step the simulation forward."""
        for _ in range(num_steps):
            p.stepSimulation()
    
    def reset(self, scene_config: Optional[SceneConfig] = None):
        """
        Reset the environment to initial state.

        Args:
            scene_config: New scene layout.  ``None`` → reuse the config
                from ``__init__``.
        """
        if scene_config is not None:
            self.scene_config = scene_config
        p.resetSimulation()
        p.setGravity(0, 0, -9.81)  # standard gravitational acceleration
        p.setRealTimeSimulation(0)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        self.objects.clear()
        self._setup_scene()
    
    def close(self):
        """Close the PyBullet connection."""
        p.disconnect(self.client_id)
