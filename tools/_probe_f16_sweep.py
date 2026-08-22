"""#P1 F16 probe: does the full-registry sweep classify EVERY fragment?

The sibling batch-sense only ever re-checked the same caster's fragments,
and only on clear_but_empty.  F16 replaces it with
execution.sweep_all_fragments, which classifies every registry SHADOW
fragment against one render.  This probe checks the two properties that
matter and that a passing pipeline run does NOT exercise (a run that finds
the target on its first sense returns before any sweep):

  1. a fragment whose volume is genuinely empty and camera-visible is
     REMOVED, with belief marked not_here and the registry/shadow list
     cleaned up — even though it belongs to a DIFFERENT caster than the
     fragment the sense action named;
  2. a fragment that really contains a body is KEPT (never removed on the
     strength of someone else's observation).

Run:
  wsl_env/bin/python tools/_probe_f16_sweep.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pybullet as p                                    # noqa: E402

from belief import BeliefState                          # noqa: E402
from boxel_data import BoxelData, BoxelType             # noqa: E402
from boxel_env import BoxelTestEnv                      # noqa: E402
from execution import sweep_all_fragments               # noqa: E402


def _fragment(fid, min_corner, max_corner, caster):
    return BoxelData(
        id=fid,
        boxel_type=BoxelType.SHADOW,
        min_corner=np.asarray(min_corner, dtype=float),
        max_corner=np.asarray(max_corner, dtype=float),
        object_name=fid,
        is_occluder=False,
        created_by_object=caster,
    )


def main():
    env = BoxelTestEnv(gui=False)
    try:
        names = {info.object_id: name for name, info in env.objects.items()}
        print(f"scene bodies: {sorted(names.values())}")
        obj_names = [n for n in names.values()
                     if n not in ("plane", "table", "robot")]
        if not obj_names:
            print("RESULT: SKIP (no movable objects in the default scene)")
            return 0

        # Occupied fragment: a tight box around a real object.
        occupied_name = obj_names[0]
        occ_id = env.objects[occupied_name].object_id
        omin, omax = p.getAABB(occ_id, physicsClientId=env.client_id)
        occupied = _fragment("frag_occupied",
                             np.asarray(omin) - 0.005,
                             np.asarray(omax) + 0.005,
                             caster="casterA")

        # Empty fragment: table-top volume placed away from every body,
        # cast by a DIFFERENT caster so the old sibling-scoped pass could
        # never have looked at it.
        table_z = env.table_surface_height
        empty = _fragment("frag_empty",
                          [-0.28, -0.30, table_z],
                          [-0.20, -0.22, table_z + 0.08],
                          caster="casterB")
        for bn in obj_names:
            bmin, bmax = p.getAABB(env.objects[bn].object_id,
                                   physicsClientId=env.client_id)
            overlap = all(bmin[i] < empty.max_corner[i]
                          and bmax[i] > empty.min_corner[i] for i in range(3))
            if overlap:
                print(f"RESULT: SKIP (chosen empty volume overlaps {bn})")
                return 0

        registry = env.registry if hasattr(env, "registry") else None
        from boxel_data import BoxelRegistry
        registry = BoxelRegistry()
        registry.add_boxel(occupied)
        registry.add_boxel(empty)

        shadows = ["frag_occupied", "frag_empty"]
        belief = BeliefState(shadows, target="__no_such_target__")
        shadow_occluder_map = {"frag_occupied": [], "frag_empty": []}
        boxel_centers = {"frag_occupied": occupied.center,
                         "frag_empty": empty.center}

        detections, _, depth_buf, seg = env.detect_objects()
        depth_m = env._depth_buffer_to_meters(depth_buf)
        view, proj = env._view_and_projection_matrices()
        support_ids = frozenset({env.objects["plane"].object_id,
                                 env.objects["table"].object_id})

        removed, shrunk, target_seen = sweep_all_fragments(
            registry=registry, belief=belief, viz=None, shadows=shadows,
            shadow_occluder_map=shadow_occluder_map,
            boxel_centers=boxel_centers, boxel_to_pybullet={},
            target_pybullet_id=-999,          # no target in this scene
            robot_id=env.objects["robot"].object_id,
            sense_support_ids=support_ids,
            sense_depth_m=depth_m, sense_seg=seg,
            sense_view=view, sense_proj=proj,
            skip_ids=frozenset())

        print(f"removed={removed} shrunk={shrunk} target_seen={target_seen}")
        print(f"belief: {belief.shadow_status}")

        ok = True
        if "frag_empty" not in removed:
            print("FAIL: the empty cross-caster fragment was NOT removed — "
                  "the sweep is not reaching other casters' fragments")
            ok = False
        else:
            if registry.get_boxel("frag_empty") is not None:
                print("FAIL: frag_empty still in the registry after removal")
                ok = False
            if "frag_empty" in shadows:
                print("FAIL: frag_empty still in the shadow list")
                ok = False
            if belief.shadow_status.get("frag_empty") != "not_here":
                print("FAIL: frag_empty belief not marked not_here")
                ok = False

        if "frag_occupied" in removed:
            print(f"FAIL: the fragment containing {occupied_name} was "
                  f"REMOVED — the sweep erased an occupied volume")
            ok = False
        else:
            print(f"ok: fragment containing {occupied_name} kept "
                  f"(shrunk={'frag_occupied' in shrunk})")

        print("RESULT: PASS" if ok else "RESULT: FAIL")
        return 0 if ok else 1
    finally:
        try:
            p.disconnect(physicsClientId=env.client_id)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
