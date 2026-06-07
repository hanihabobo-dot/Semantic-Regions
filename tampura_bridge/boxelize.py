#!/usr/bin/env python3
"""Phase 3-B ITEM 8 (GOAL 1): run OUR boxelizer + shadow_calculator +
reboxelize_free_space on TAMPURA's live find_dice scene and DRAW the overlays in
their PyBullet GUI.

Reuses our exact perception code (BoxelData, ShadowCalculator, FreeSpaceGenerator,
reboxelize_free_space, the wireframe/colour helpers) over the FindDiceAdapter
(ITEM 6/7).  Overlays are drawn on THEIR state-world client, so no visualizer
core edit is needed; the only shared-core change is the guarded physics_client
thread in ShadowCalculator (APPENDIX B).

NOTE (containment vs shadow): find_dice hides the die INSIDE/under the cup, while
our ShadowCalculator models line-of-sight occlusion behind the occluder.  The die
center may therefore fall in the cup's subtracted footprint rather than the
shadow volume; _main reports die_in_shadow straight.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np
import pybullet as p

from boxel_data import BoxelData, BoxelRegistry, BoxelType
from reboxelize import reboxelize_free_space
from shadow_calculator import ShadowCalculator
from visualization import _color_for_boxel, wireframe_corners_and_edges
from tampura_environments.panda_utils import pb_utils as pbu
from tampura_bridge.perception_adapter import FindDiceAdapter


def build_object_boxels(adapter):
    """OBJECT BoxelData from each adapter object's live AABB (cup, die)."""
    out = []
    for name, o in adapter.objects.items():
        aabb = pbu.get_aabb(o.object_id, client=adapter.client)
        lo = np.array(aabb.lower, dtype=float)
        hi = np.array(aabb.upper, dtype=float)
        out.append(BoxelData.from_center_extent(
            (lo + hi) / 2.0, (hi - lo) / 2.0, BoxelType.OBJECT,
            object_name=name, is_occluder=o.is_occluder))
    return out


def boxelize_scene(adapter):
    """Full perception pass -> populated BoxelRegistry + auto_cell."""
    registry = BoxelRegistry()
    for bd in build_object_boxels(adapter):
        registry.add_boxel(bd)

    # SHADOWS for occluders: our ShadowCalculator, reading their world via the
    # guarded physics_client.
    shadow_calc = ShadowCalculator(
        adapter.camera_position, adapter.table_surface_height,
        table_x_range=adapter.table_x_range, table_y_range=adapter.table_y_range)
    objs = registry.get_object_boxels()
    for ob in objs:
        if ob.is_occluder:
            obstacles = [x for x in objs if x.id != ob.id]
            for sh in shadow_calc.calculate_shadow_boxel(
                    ob, obstacles, physics_client=adapter.client_id):
                registry.add_boxel(sh)

    # auto_cell (test_full_pipeline.py:494): tallest/widest object extent + 1 cm.
    max_extent = max(float(np.max(b.max_corner - b.min_corner))
                     for b in registry.get_object_boxels())
    auto_cell = max_extent + 0.01
    adapter.free_space_generator.min_resolution = auto_cell

    # FREE_SPACE via the exact reboxelize path (through adapter.generate_free_space).
    reboxelize_free_space(registry, adapter, {}, viz=None, show_free=False)
    return registry, auto_cell


def draw_registry_on_client(client, registry, fill_opacity=0.4):
    """Draw OBJECT/SHADOW (filled phantom + wireframe) and FREE_SPACE (wireframe)
    on THEIR client, so overlays show in the GUI and in getCameraImage."""
    for bd in registry.boxels.values():
        c, e = bd.center, bd.extent
        color = _color_for_boxel(bd)
        corners, edges = wireframe_corners_and_edges(c, e)
        thin = bd.boxel_type in (BoxelType.SHADOW, BoxelType.FREE_SPACE)
        for i, j in edges:
            client.addUserDebugLine(
                list(corners[i]), list(corners[j]), color,
                1.0 if thin else 2.0, 0)
        if bd.boxel_type in (BoxelType.OBJECT, BoxelType.SHADOW):
            vs = client.createVisualShape(
                p.GEOM_BOX, halfExtents=list(e),
                rgbaColor=[color[0], color[1], color[2], fill_opacity])
            client.createMultiBody(
                baseMass=0, baseVisualShapeIndex=vs, basePosition=list(c))


def suppress_pomdp_and_draw(world, fill_opacity=0.4):
    """Part B: clear TAMPURA's dark-blue visibility-grid voxels from their
    state-world GUI (addUserDebugLine OOBBs drawn at env.initialize, env.py:874)
    and draw OUR boxelization in their place.  Returns (adapter, registry) so a
    caller can redraw after the scene changes."""
    world.client.removeAllUserDebugItems()
    adapter = FindDiceAdapter(world)
    registry, _ = boxelize_scene(adapter)
    draw_registry_on_client(world.client, registry, fill_opacity=fill_opacity)
    return adapter, registry


def capture(client, path, eye, target, w=960, h=720):
    from PIL import Image

    view = client.computeViewMatrix(eye, target, [0, 0, 1])
    proj = client.computeProjectionMatrixFOV(60.0, w / float(h), 0.01, 5.0)
    img = client.getCameraImage(w, h, viewMatrix=view, projectionMatrix=proj,
                                renderer=p.ER_BULLET_HARDWARE_OPENGL)
    rgb = np.reshape(np.array(img[2], dtype=np.uint8), (h, w, 4))[:, :, :3]
    abspath = os.path.abspath(path)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    Image.fromarray(rgb).save(abspath)
    return abspath


def die_in_shadow(registry):
    """True iff the die OBJECT center lies inside any SHADOW boxel."""
    die = next((b for b in registry.get_object_boxels()
                if b.object_name == "die"), None)
    if die is None:
        return False
    c = die.center
    return any(np.all(c >= sh.min_corner) and np.all(c <= sh.max_corner)
               for sh in registry.get_shadow_boxels())


def _main():
    import argparse
    import logging
    import random
    import time

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 — registers the find_dice env

    pr = argparse.ArgumentParser(description="ITEM 8: boxelize their scene (GOAL 1)")
    pr.add_argument("--config", default="./env_configs/find_dice.yml")
    pr.add_argument("--global-seed", type=int)
    pr.add_argument("--vis", type=int, default=1)
    pr.add_argument(
        "--save-dir",
        default=os.path.join(os.getcwd(), "runs", "boxel_goal1_{}".format(time.time())),
    )
    pr.add_argument(
        "--out",
        default=os.path.join(_REPO, "tampura_bridge", "captures", "item8_boxels_goal1.png"),
    )
    args = pr.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None and k != "out"}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)

    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()

    adapter = FindDiceAdapter(env.world)
    registry, auto_cell = boxelize_scene(adapter)

    print("=== ITEM 8 (GOAL 1) boxelization on their scene ===")
    print("object boxels:", len(registry.get_object_boxels()),
          " shadow boxels:", len(registry.get_shadow_boxels()),
          " free boxels:", len(registry.get_free_space_boxels()))
    print("auto_cell: {:.4f} m  (= free_space min_resolution)".format(auto_cell))
    print("table_surface_height:", round(adapter.table_surface_height, 4))
    print("die inside a shadow boxel?", die_in_shadow(registry))

    draw_registry_on_client(env.world.client, registry)
    cen = adapter.camera_target  # scene centroid at table height
    eye = [float(cen[0]) + 0.45, float(cen[1]) - 0.45, float(cen[2]) + 0.5]
    saved = capture(env.world.client, args.out, eye,
                    [float(cen[0]), float(cen[1]), float(cen[2])])
    print("overlay capture saved ->", saved)


if __name__ == "__main__":
    _main()
