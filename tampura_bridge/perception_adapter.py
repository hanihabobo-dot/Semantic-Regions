"""Phase 3-B ITEM 6: P1 perception adapter — exposes TAMPURA's live find_dice
world through the exact BoxelTestEnv surface our perception consumes (APPENDIX A
of the plan), reading THEIR bodies on THEIR pybullet client. No second world.

Mapping (DELTA #1): the categories list has cups first and "dice" LAST. Each
non-"dice" body -> occluder (is_occluder=True); the "dice" body -> target
(is_occluder=False). The oracle RUN and shadow build come in ITEMs 7-8; this
item only exposes state + the object mapping.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np
import pybullet as p

from boxel_env import BoxelTestEnv
from boxel_types import ObjectInfo
from free_space import FreeSpaceGenerator
from tampura_environments.panda_utils import pb_utils as pbu
from tampura_bridge.sense_config import sense_camera_pose, set_sense_config

DIE_CATEGORY = "dice"


def _client_id(client):
    # BulletClient wraps the int connection id at ._client; tolerate a raw int.
    return getattr(client, "_client", client)


class FindDiceAdapter:
    """Lightweight stand-in for BoxelTestEnv over TAMPURA's state world.

    Exposes the attributes our oracle / shadow / free-space pipeline reads:
    .objects, .camera_position, .camera_target, .table_surface_height,
    .table_x_range/.table_y_range, ._SAFE_TABLE_*_RANGE, .use_uniform_grid,
    .free_space_generator (built in ITEM 8), and .client for physics_client
    threading.
    """

    def __init__(self, world, sense_at_home=True, camera_mode="external"):
        self.world = world
        self.client = world.client
        self.client_id = _client_id(world.client)

        self.objects = self._build_objects()
        (self.table_surface_height,
         self.table_x_range,
         self.table_y_range) = self._extract_table()
        # single support surface here -> free-space footprint == shadow footprint
        self._SAFE_TABLE_X_RANGE = self.table_x_range
        self._SAFE_TABLE_Y_RANGE = self.table_y_range

        if camera_mode == "external":
            # Fixed EXTERNAL RGB-D camera (our system's model): a high-oblique
            # view aimed at the OCCLUDER centroid (die-independent -- the die's
            # pose is never used to place it).  Sees the table clearly; a hidden
            # die stays occluded until its covering cup is relocated.
            self.camera_target = self._occluder_centroid_target()
            self.camera_quat = None
            self.camera_position = self._external_eye()
        else:  # "wrist": Phase 3-B eye-in-hand at the fixed home config
            if sense_at_home:
                set_sense_config(world)
            eye, quat = sense_camera_pose(world)
            self.camera_position = eye
            self.camera_quat = quat
            self.camera_target = self._scene_centroid_target()

        # semantic octree free-space generator over their table geometry
        # (ITEM 8).  min_resolution is set to auto_cell by the boxelize pass.
        self.use_uniform_grid = False
        self.free_space_generator = FreeSpaceGenerator(
            self.table_surface_height,
            table_x_range=self.table_x_range,
            table_y_range=self.table_y_range,
        )

    def _occluder_centroid_target(self):
        """Aim point = centroid of the OCCLUDERS (cups) at table height, so the
        fixed camera is placed without reference to the hidden die's pose."""
        occ = [o.position[:2] for o in self.objects.values() if o.is_occluder]
        if occ:
            cx, cy = np.mean(np.asarray(occ), axis=0)
        else:
            cx, cy = self._scene_centroid_target()[:2]
        return np.array([float(cx), float(cy), self.table_surface_height], dtype=float)

    def _external_eye(self):
        """High-oblique fixed external eye over the occluder footprint."""
        c = self.camera_target
        return np.array([float(c[0]), float(c[1]) - 0.3,
                         self.table_surface_height + 0.9], dtype=float)

    def segment_visible(self, w=320, h=240):
        """Genuine visibility: render the fixed external camera and read the
        segmentation mask -> the set of object NAMES actually seen (real
        occlusion).  Replaces the AABB-corner oracle, which mis-reports round
        cups from a clean external view.  A die hidden under a cup is NOT
        returned until that cup is relocated."""
        eye = [float(v) for v in self.camera_position]
        tgt = [float(v) for v in self.camera_target]
        view = self.client.computeViewMatrix(eye, tgt, [0, 0, 1])
        proj = self.client.computeProjectionMatrixFOV(60.0, w / float(h), 0.01, 5.0)
        img = self.client.getCameraImage(w, h, viewMatrix=view, projectionMatrix=proj,
                                          renderer=p.ER_TINY_RENDERER)
        seg = np.array(img[4]).reshape(h, w)
        ids = set(int(v) & ((1 << 24) - 1) for v in np.unique(seg) if v >= 0)
        id2name = {o.object_id: n for n, o in self.objects.items()}
        return sorted(id2name[i] for i in ids if i in id2name)

    def _build_objects(self):
        objects = {}
        bodies = list(self.world.objects)
        cats = list(self.world.categories)
        cup_i = 0
        for body, cat in zip(bodies, cats):
            pos, orn = pbu.get_pose(body, client=self.client)
            aabb = pbu.get_aabb(body, client=self.client)
            size = np.array(aabb.upper, dtype=float) - np.array(aabb.lower, dtype=float)
            is_die = (cat == DIE_CATEGORY)
            if is_die:
                name = "die"
            else:
                name = "cup_{}".format(cup_i)
                cup_i += 1
            objects[name] = ObjectInfo(
                object_id=int(body),
                name=name,
                position=np.array(pos, dtype=float),
                orientation=np.array(orn, dtype=float),
                size=size,
                is_visible=True,            # oracle sets the real value in ITEM 7
                is_occluder=(not is_die),   # cups occlude; die is the target
                is_tray=False,
            )
        return objects

    def _extract_table(self):
        aabb = pbu.get_aabb(self.world.floor, client=self.client)
        lo, hi = aabb.lower, aabb.upper
        # Support surface = where the OCCLUDERS actually rest (their AABB bottom),
        # not the floor-body top: find_dice objects sit ~1 cm above the floor mesh,
        # and the shadow surface-resting gate (shadow_calculator:73) needs the cup
        # bottom <= table_z + 0.01.  Falls back to the floor top if no occluders.
        occ_bottoms = [
            float(pbu.get_aabb(o.object_id, client=self.client).lower[2])
            for o in self.objects.values() if o.is_occluder
        ]
        table_z = min(occ_bottoms) if occ_bottoms else float(hi[2])
        return table_z, (float(lo[0]), float(hi[0])), (float(lo[1]), float(hi[1]))

    def _scene_centroid_target(self):
        pts = [o.position[:2] for o in self.objects.values()]
        if pts:
            cx, cy = np.mean(np.asarray(pts), axis=0)
        else:
            cx, cy = 0.0, 0.0
        return np.array([cx, cy, self.table_surface_height], dtype=float)

    def update_object_poses(self):
        """Re-read object poses from their world (mirrors update_object_positions)."""
        for o in self.objects.values():
            pos, orn = pbu.get_pose(o.object_id, client=self.client)
            o.position = np.array(pos, dtype=float)
            o.orientation = np.array(orn, dtype=float)

    def oracle_detect_objects(self, check_occlusion=True):
        """Run OUR oracle (BoxelTestEnv.oracle_detect_objects) on their world.

        Foreign-self reuse: that method only touches self.objects and
        self.camera_position (both exposed here), so calling it with this
        adapter as ``self`` runs the EXACT same code path as on our env.  We
        thread their state-world client id so its default-client p.* calls read
        THEIR world (boxel_env physics_client=None would hit our default client).
        """
        return BoxelTestEnv.oracle_detect_objects(
            self, check_occlusion=check_occlusion, physics_client=self.client_id
        )

    def generate_free_space(self, known_boxels, visualize=False):
        """Mirror BoxelTestEnv.generate_free_space (semantic octree path) so
        reboxelize_free_space can run unchanged on this adapter."""
        return self.free_space_generator.generate(known_boxels, visualize)

    def annotate_free_space_surface(self, free_boxels):
        """Foreign-self reuse of BoxelTestEnv.annotate_free_space_surface — it
        only touches table_surface_height + _SAFE_TABLE_*_RANGE (all exposed
        here) and is pure geometry, so it runs unchanged on this adapter."""
        return BoxelTestEnv.annotate_free_space_surface(self, free_boxels)


def _main():
    import argparse
    import logging
    import random
    import time

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 — registers the find_dice env

    p = argparse.ArgumentParser(description="ITEM 6: instantiate FindDiceAdapter")
    p.add_argument("--config", default="./env_configs/find_dice.yml")
    p.add_argument("--global-seed", type=int)
    p.add_argument("--vis", type=int, default=0)  # smoke: headless
    p.add_argument(
        "--save-dir",
        default=os.path.join(os.getcwd(), "runs", "boxel_adapter_{}".format(time.time())),
    )
    args = p.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)

    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()

    ad = FindDiceAdapter(env.world)
    print("=== FindDiceAdapter (ITEM 6) ===")
    print("client              :", ad.client)
    print("camera_position(eye):", np.round(ad.camera_position, 4).tolist())
    print("camera_quat (xyzw)  :", np.round(ad.camera_quat, 4).tolist())
    print("camera_target       :", np.round(ad.camera_target, 4).tolist())
    print("table_surface_height:", round(ad.table_surface_height, 4))
    print("table_x_range       :", tuple(round(v, 4) for v in ad.table_x_range))
    print("table_y_range       :", tuple(round(v, 4) for v in ad.table_y_range))
    print("objects:")
    for name, o in ad.objects.items():
        aabb = pbu.get_aabb(o.object_id, client=ad.client)
        lo, hi = aabb.lower, aabb.upper
        print(
            "  {:6s} body={} pos={} size={} occluder={} target={} "
            "aabb_z=[{:.4f},{:.4f}] rest_gap={:+.4f}".format(
                name, o.object_id, np.round(o.position, 4).tolist(),
                np.round(o.size, 4).tolist(), o.is_occluder, not o.is_occluder,
                lo[2], hi[2], lo[2] - ad.table_surface_height,
            )
        )

    print("--- ITEM 7: oracle on their scene (fixed home camera) ---")
    visible, _poses = ad.oracle_detect_objects()
    hidden = [n for n in ad.objects if n not in visible]
    print("visible:", visible)
    print("hidden :", hidden)
    die_hidden = "die" not in visible
    cups_visible = all(n in visible for n in ad.objects if n.startswith("cup"))
    print("die hidden? {}   all cups visible? {}".format(die_hidden, cups_visible))


if __name__ == "__main__":
    _main()
