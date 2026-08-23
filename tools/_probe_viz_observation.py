"""#P1 F19 probe: the debug overlay must never appear in the observation.

Reproduces the GUI field failure headlessly (runs 2026-08-22_17-14-10 and
2026-08-23_11-25-45): BoxelVisualizer's phantom AABB fills are visual-only
multibodies, invisible to rayTestBatch but rendered by TinyRenderer — so
once step (3) moved sensing onto the rendered observation, a GUI run's
sense saw the overlay itself.  The visualizer only exists under the GUI,
which is why every headless battery stayed green while the user's GUI runs
kept dying; this probe creates the visualizer in DIRECT mode on purpose.

Checks:
  1. POLLUTION IS REAL: a raw getCameraImage (no concealment) shows the
     phantom's seg id and the phantom hides the object it covers.
  2. THE OBSERVATION IS CLEAN: env.detect_objects() (which conceals the
     overlay) contains no phantom ids, still detects the covered object,
     and sense_shadow_from_render over a phantom-covered fragment comes
     back clear_but_empty / found_target — never an unlocalizable
     phantom discovery.
  3. RESTORATION: the phantoms are back at their drawn positions after
     the observation.

Run:
  wsl_env/bin/python tools/_probe_viz_observation.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pybullet as p                                    # noqa: E402

from boxel_data import BoxelData, BoxelType             # noqa: E402
from boxel_env import BoxelTestEnv                      # noqa: E402
from execution import sense_shadow_from_render          # noqa: E402
from visualization import BoxelVisualizer, _PHANTOM_HOME  # noqa: E402


def _raw_render(env):
    view, proj = env._view_and_projection_matrices()
    _, _, _, depth, seg = p.getCameraImage(
        width=env.image_width, height=env.image_height,
        viewMatrix=view, projectionMatrix=proj,
        renderer=p.ER_TINY_RENDERER, physicsClientId=env.client_id)
    return (np.asarray(depth, dtype=float).reshape(
                (env.image_height, env.image_width)),
            np.asarray(seg).reshape((env.image_height, env.image_width)))


def main():
    env = BoxelTestEnv(gui=False)
    ok = True
    try:
        scene_ids = {info.object_id for info in env.objects.values()}
        names = {info.object_id: n for n, info in env.objects.items()}
        obj_names = [n for n in names.values()
                     if n not in ("plane", "table", "robot")]
        covered = obj_names[0]
        cov_info = env.objects[covered]
        omin, omax = p.getAABB(cov_info.object_id,
                               physicsClientId=env.client_id)

        # Overlay: one phantom over a real object (the OBJECT-boxel case
        # that hid green from the refresh) and one over an empty tabletop
        # fragment (the shadow case that stalled the senses).
        viz = BoxelVisualizer()
        table_z = env.table_surface_height
        frag = BoxelData(
            id="frag_probe", boxel_type=BoxelType.SHADOW,
            min_corner=np.array([-0.28, -0.30, table_z]),
            max_corner=np.array([-0.20, -0.22, table_z + 0.08]),
            object_name="frag_probe", is_occluder=False)
        obj_bd = BoxelData(
            id="cover_probe", boxel_type=BoxelType.OBJECT,
            min_corner=np.asarray(omin), max_corner=np.asarray(omax),
            object_name=covered, is_occluder=True)
        viz.draw_boxel_data(frag)
        viz.draw_boxel_data(obj_bd)
        phantom_ids = set(viz.shadow_bodies)
        print(f"phantom bodies: {sorted(phantom_ids)} "
              f"(scene ids {sorted(scene_ids)})")

        # --- 1. pollution is real on a raw render -----------------------
        _, raw_seg = _raw_render(env)
        raw_phantom_px = {b: int(np.count_nonzero(raw_seg == b))
                          for b in phantom_ids}
        print(f"raw render phantom px: {raw_phantom_px}")
        if not any(v > 0 for v in raw_phantom_px.values()):
            print("FAIL: raw render shows no phantom pixels — the "
                  "pollution this probe guards against did not reproduce")
            ok = False
        raw_covered_px = int(np.count_nonzero(
            raw_seg == cov_info.object_id))
        print(f"raw render {covered} px: {raw_covered_px}")

        # --- 2. the observation is clean --------------------------------
        detections, _, depth_buf, seg = env.detect_objects()
        obs_phantom_px = {b: int(np.count_nonzero(seg == b))
                          for b in phantom_ids}
        if any(v > 0 for v in obs_phantom_px.values()):
            print(f"FAIL: observation contains phantom pixels: "
                  f"{obs_phantom_px}")
            ok = False
        else:
            print("ok: observation contains zero phantom pixels")
        if covered not in detections:
            print(f"FAIL: {covered} not detected though only the overlay "
                  f"covered it")
            ok = False
        else:
            print(f"ok: {covered} detected "
                  f"({detections[covered].pixel_count} px) despite its "
                  f"overlay box")

        depth_m = env._depth_buffer_to_meters(depth_buf)
        view, proj = env._view_and_projection_matrices()
        outcome, bf, det_bodies, bbox, icounts = sense_shadow_from_render(
            frag, target_pybullet_id=-999,
            depth_image_m=depth_m, seg_mask=seg,
            view_matrix=view, projection_matrix=proj,
            occluder_pybullet_ids=set(),
            robot_id=env.objects["robot"].object_id,
            support_body_ids=frozenset({env.objects["plane"].object_id,
                                        env.objects["table"].object_id}))
        print(f"sense over the phantom-covered empty fragment: "
              f"outcome={outcome} detected={det_bodies} "
              f"interceptors={icounts}")
        if outcome != "clear_but_empty" or (det_bodies & phantom_ids):
            print("FAIL: the fragment's own overlay still pollutes its "
                  "sense classification")
            ok = False

        # --- 3. phantoms restored after the observation ------------------
        for b in phantom_ids:
            pos, _ = p.getBasePositionAndOrientation(
                b, physicsClientId=env.client_id)
            home = _PHANTOM_HOME.get(b)
            if home is None or abs(pos[2] - home[2]) > 1e-6:
                print(f"FAIL: phantom {b} not restored (pos={pos}, "
                      f"home={home})")
                ok = False
        if ok:
            print("ok: phantoms restored to their drawn positions")

        print("RESULT: PASS" if ok else "RESULT: FAIL")
        return 0 if ok else 1
    finally:
        try:
            p.disconnect(physicsClientId=env.client_id)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
