#!/usr/bin/env python3
"""F5 diagnostic (read-only): spawn-hidden classification vs sense geometry.

Rebuilds the random-pairs scene headless (DIRECT) for given seeds and checks:
  1. object poses/sizes after settle,
  2. oracle_detect_objects (8-corner criterion) visibility,
  3. pixel-level visibility via segmentation render (the step-(2) criterion),
  4. which final F3 shadow fragment contains each hidden target,
  5. post-fix: the SHARED sense grid (perception.sense_ray_slices) finds the
     target once occluders are removed (found_target), grid_would_hit agrees,
     and the dense low slice never grazes the table/plane.

No writes, no planning, no GUI.  Run:
  wsl_env/bin/python tools/_diag_f5_seed0.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pybullet as p

from boxel_env import BoxelTestEnv, random_pairs_scene
from boxel_data import BoxelType
from execution import sense_shadow_from_render
from perception import grid_would_hit, sense_ray_slices

SEEDS = [0, 3, 999]


def seg_pixel_counts(env):
    """Render the fixed camera and count pixels per body id."""
    view = p.computeViewMatrix(env.camera_position.tolist(),
                               env.camera_target.tolist(),
                               env.camera_up.tolist())
    proj = p.computeProjectionMatrixFOV(
        env.fov, env.image_width / env.image_height,
        env.near_plane, env.far_plane)
    _, _, _, _, seg = p.getCameraImage(env.image_width, env.image_height,
                                       view, proj,
                                       renderer=p.ER_TINY_RENDERER)
    seg = np.asarray(seg).reshape(env.image_height, env.image_width)
    ids, counts = np.unique(seg, return_counts=True)
    return dict(zip(ids.tolist(), counts.tolist()))


def table_graze_count(cam, frag, support_ids):
    """Cast the full shared grid; count rays terminating on plane/table."""
    slices, _ = sense_ray_slices(frag.min_corner, frag.max_corner)
    tos = [list(map(float, pt)) for sl in slices for pt in sl.points]
    froms = [list(cam)] * len(tos)
    res = p.rayTestBatch(froms, tos, numThreads=0)
    return sum(1 for r in res if r[0] in support_ids), len(tos)


def main():
    failures = 0
    for seed in SEEDS:
        print("=" * 72)
        print(f"SEED {seed}")
        print("=" * 72)
        cfg = random_pairs_scene(n_occluders=3, extra_distractors=0,
                                 seed=seed)
        env = BoxelTestEnv(gui=False, scene_config=cfg)
        for _ in range(50):
            env.step_simulation()
        env.update_object_positions()

        names = {}
        for name, info in env.objects.items():
            if name in ("plane", "table", "robot"):
                names[name] = info.object_id
                continue
            print(f"  {name:16s} id={info.object_id} "
                  f"occluder={info.is_occluder} "
                  f"pos=({info.position[0]:+.4f},{info.position[1]:+.4f},"
                  f"{info.position[2]:+.4f}) size={list(info.size)}")
            names[name] = info.object_id

        visible, _ = env.oracle_detect_objects()
        targets = [n for n, i in env.objects.items()
                   if not i.is_occluder and not getattr(i, 'is_tray', False)
                   and n not in ("plane", "table", "robot")]
        hidden = [t for t in targets if t not in visible]
        print(f"  oracle visible: {sorted(visible)}")
        print(f"  oracle hidden targets: {hidden}  "
              f"(n_hidden requested: {cfg.n_hidden_targets})")

        px = seg_pixel_counts(env)
        for t in targets:
            tid = env.objects[t].object_id
            print(f"  segmentation pixels of {t}: {px.get(tid, 0)} "
                  f"({'PIXEL-VISIBLE' if px.get(tid, 0) > 0 else 'zero px'})"
                  f"{'  <-- oracle-hidden' if t in hidden else ''}")

        obs = env.get_camera_observation()
        frags = [b for b in obs.boxels if b.boxel_type == BoxelType.SHADOW]
        print(f"  {len(frags)} shadow fragments:")
        for b in frags:
            print(f"    {b.id:34s} min=({b.min_corner[0]:+.4f},"
                  f"{b.min_corner[1]:+.4f},{b.min_corner[2]:.4f}) "
                  f"max=({b.max_corner[0]:+.4f},{b.max_corner[1]:+.4f},"
                  f"{b.max_corner[2]:.4f})")

        occluder_ids = [i.object_id for i in env.objects.values()
                        if i.is_occluder]
        support_ids = frozenset(names[k] for k in ("plane", "table")
                                if k in names)
        robot_id = env.objects["robot"].object_id

        plan = {}   # hidden target -> containing fragment
        for t in hidden:
            tpos = np.asarray(env.objects[t].position)
            containing = [b for b in frags
                          if np.all(tpos >= np.asarray(b.min_corner))
                          and np.all(tpos <= np.asarray(b.max_corner))]
            print(f"  hidden target {t} centre in fragments: "
                  f"{[b.id for b in containing] or 'NONE  <-- unwinnable, needs commit-2 re-roll'}")
            if containing:
                plan[t] = containing[0]
                t_min, t_max = p.getAABB(env.objects[t].object_id)
                would = grid_would_hit(env.camera_position,
                                       containing[0].min_corner,
                                       containing[0].max_corner,
                                       t_min, t_max)
                print(f"    grid_would_hit({containing[0].id}, {t}) = "
                      f"{would}{'' if would else '  <-- FAIL'}")
                if not would:
                    failures += 1

        # Post-clearing world: remove all occluders, re-sense with the
        # SHARED grid via the real sense function.
        for oid in occluder_ids:
            p.removeBody(oid)
        # step (3): the sense classifies against a rendered observation
        _, _, depth_buf, seg = env.detect_objects()
        depth_m = env._depth_buffer_to_meters(depth_buf)
        view_m, proj_m = env._view_and_projection_matrices()
        for t, frag in plan.items():
            tid = env.objects[t].object_id
            outcome, bf, det, _, _ = sense_shadow_from_render(
                frag, tid, depth_m, seg, view_m, proj_m,
                occluder_pybullet_ids=set(), robot_id=robot_id,
                support_body_ids=support_ids)
            ok = outcome == "found_target"
            if not ok:
                failures += 1
            print(f"  shared-grid sense on {frag.id} (occluders removed, "
                  f"target {t} inside): outcome={outcome} "
                  f"{'OK' if ok else '<-- FAIL (expected found_target)'}")
            grazes, nrays = table_graze_count(
                env.camera_position.tolist(), frag, support_ids)
            if grazes:
                failures += 1
            print(f"  table/plane grazes on the shared grid: "
                  f"{grazes}/{nrays} rays "
                  f"{'OK' if grazes == 0 else '<-- FAIL'}")

        env.close()
    print()
    print(f"RESULT: {'PASS' if failures == 0 else f'{failures} FAILURES'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
