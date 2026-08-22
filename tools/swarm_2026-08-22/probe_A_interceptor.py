#!/usr/bin/env python3
"""Swarm 2026-08-22 / Agent A, Part 2 (read-only probe).

Identify the sub-detection-minimum body that intercepted sense-grid
endpoints of shadow_of_green_object and shadow_of_red_object during
logs/run_2026-08-22_17-14-10 (seed 0, random-pairs, 3 occluders),
burning the 3-strike "contains something the render cannot localize"
guard on both shadows (log lines 243/303/357->358 and 466-468/529/583->584).

Builds the seed-0 scene exactly as the run did, then TELEPORTS bodies
(no arm replay) into three states of interest:

  S1  as-spawned (matches boxel_data.json / problem_initial.pddl)
  S2  green -> free_003 placed; orange "thrown" off the arm during the
      plan #1 place-at-free_005 transit.  Two rival endings for orange
      are tested since its true rest pose was never logged:
        S2a  orange knocked off the table, resting on the floor beside it
        S2b  orange still on the table, but at the far corner of the
             camera's / workspace's frame (near the free_005 boxel,
             which itself sits on the _SAFE_TABLE_Y_RANGE boundary)
  S3  log line 529/583 state: green at free_003, red relocated to
      free_011 (~[0.2039,-0.0019,0.3951], log line 452), orange still
      missing.  shadow_of_red_object is tested both at its ORIGINAL
      (spawn) AABB and at a reconstructed shrunk AABB sized to the
      logged 4.3x8.3x9.1 cm (exact center is not recoverable without
      replaying the arm that caused the shrink -- see report).

For every state: render depth+seg from the fixed scene camera (same
ER_TINY_RENDERER path env.detect_objects() uses), count seg pixels per
body id GLOBALLY (the same count detect_objects_from_render/
DETECTION_MIN_PIXELS uses), then run perception.first_surface_interceptors
over the shadow's sense-grid endpoints and report, per endpoint, which
body id is the first surface in front of it.

Run:  wsl_env/bin/python tools/swarm_2026-08-22/probe_A_interceptor.py
"""
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pybullet as p

from boxel_env import BoxelTestEnv, random_pairs_scene
from perception import (DETECTION_MIN_PIXELS, SENSE_MARGINAL_BLOCKED_FRACTION,
                        first_surface_interceptors, sense_ray_slices)

DUMP_PATH = os.path.join(os.path.dirname(__file__), "probe_A_dump.txt")
_dump_lines = []


def log(msg=""):
    print(msg)
    _dump_lines.append(msg)


def build_env(seed=0):
    import random
    random.seed(seed)
    np.random.seed(seed)
    cfg = random_pairs_scene(n_occluders=3, extra_distractors=0, seed=seed)
    env = BoxelTestEnv(gui=False, scene_config=cfg)
    for _ in range(50):
        env.step_simulation()
    env.update_object_positions()
    return env


def render_state(env):
    detections, rgb, depth_buf, seg = env.detect_objects()
    depth_m = env._depth_buffer_to_meters(depth_buf)
    view, proj = env._view_and_projection_matrices()
    ids, counts = np.unique(seg, return_counts=True)
    pixel_counts = {int(i): int(c) for i, c in zip(ids, counts)}
    return depth_m, seg, view, proj, pixel_counts, detections


def endpoints_for(frag_min, frag_max):
    slices, capped = sense_ray_slices(frag_min, frag_max)
    pts = []
    slice_idx = []
    for si, sl in enumerate(slices):
        for pt in sl.points:
            pts.append([float(pt[0]), float(pt[1]), float(pt[2])])
            slice_idx.append(si)
    return np.asarray(pts), np.asarray(slice_idx), slices, capped


def analyze_shadow(tag, frag_min, frag_max, depth_m, seg, view, proj,
                    target_id, ignore_ids, name_by_id, pixel_counts):
    pts, slice_idx, slices, capped = endpoints_for(frag_min, frag_max)
    icp, hids, in_view = first_surface_interceptors(pts, depth_m, seg, view, proj)

    n_total = len(pts)
    n_offimage = int(np.count_nonzero(~in_view))
    n_intercepted = int(np.count_nonzero(icp & in_view))

    per_body = {}
    for i in range(n_total):
        if not in_view[i] or not icp[i]:
            continue
        bid = int(hids[i])
        per_body.setdefault(bid, []).append(i)

    log(f"  [{tag}] endpoints={n_total} off_image={n_offimage} "
        f"intercepted={n_intercepted} capped={capped}")
    for bid, idxs in sorted(per_body.items(), key=lambda kv: -len(kv[1])):
        nm = name_by_id.get(bid, f"id{bid}")
        role = "TARGET" if bid == target_id else (
            "ignored(robot/support)" if bid in ignore_ids else "INTERCEPTOR")
        gpix = pixel_counts.get(bid, 0)
        below = " <6px GLOBAL (below DETECTION_MIN_PIXELS)" if (
            role == "INTERCEPTOR" and gpix < DETECTION_MIN_PIXELS) else ""
        log(f"      body {bid:>2} ({nm:<14}) {role:<24} "
            f"endpoints_hit={len(idxs):>4}  global_seg_px={gpix:>6}{below}")
        _dump_lines.append(f"        endpoint indices (first 20): {idxs[:20]}")

    interceptors = {bid: len(idxs) for bid, idxs in per_body.items()
                    if bid not in ignore_ids and bid != target_id}
    sub_min = {bid: n for bid, n in interceptors.items()
               if pixel_counts.get(bid, 0) < DETECTION_MIN_PIXELS}
    return {
        "n_total": n_total, "n_offimage": n_offimage,
        "n_intercepted": n_intercepted,
        "per_body": per_body, "interceptors": interceptors,
        "sub_detection_interceptors": sub_min,
    }


def name_map(env):
    m = {}
    for name, info in env.objects.items():
        m[info.object_id] = name
    return m


def report_global_pixels(tag, pixel_counts, name_by_id):
    log(f"  [{tag}] GLOBAL seg pixel counts (whole 640x480 image):")
    for bid, n in sorted(pixel_counts.items()):
        if bid < 0:
            continue
        nm = name_by_id.get(bid, f"id{bid}")
        flag = " <-- below DETECTION_MIN_PIXELS=6" if (
            n < DETECTION_MIN_PIXELS and nm not in ("plane", "table", "robot")
        ) else ""
        log(f"      body {bid:>2} ({nm:<14}) pixels={n:>6}{flag}")


def teleport(env, name, pos, orn=(0, 0, 0, 1)):
    bid = env.objects[name].object_id
    p.resetBasePositionAndOrientation(bid, list(pos), list(orn),
                                       physicsClientId=env.client_id)
    p.resetBasePositionAndOrientation(
        env.plan_body_id(bid), list(pos), list(orn),
        physicsClientId=env.plan_client_id)


def hide_far_away(env, name):
    """Teleport a body far outside the camera frustum -- models 'gone /
    unlocatable' without deleting the body (keeps ids stable)."""
    teleport(env, name, (50.0, 50.0, 50.0))


def main():
    env = build_env(seed=0)
    name_by_id = name_map(env)
    robot_id = env.objects["robot"].object_id
    support_ids = {env.objects["plane"].object_id, env.objects["table"].object_id}
    target_id = env.objects["blue_object"].object_id
    ignore_common = support_ids | {robot_id, -1}

    log("=" * 78)
    log("Body id map (S1, as-spawned):")
    for name, info in env.objects.items():
        log(f"  {name:<14} -> body_id {info.object_id}")
    log(f"  robot_id={robot_id} support_ids={support_ids} target(blue)={target_id}")
    log(f"  DETECTION_MIN_PIXELS={DETECTION_MIN_PIXELS}  "
        f"SENSE_MARGINAL_BLOCKED_FRACTION={SENSE_MARGINAL_BLOCKED_FRACTION}")
    log(f"  camera_position={list(env.camera_position)} "
        f"camera_target={list(env.camera_target)}")

    # boxel_data.json (spawn-time) fragment AABBs -- ground truth from the
    # actual run's Phase 2/3 boxelization, log:39-49 / boxel_data.json.
    SHADOW_GREEN_MIN = np.array([-0.2255147310505379, 0.2279122149324581, 0.325])
    SHADOW_GREEN_MAX = np.array([0.04144249476730944, 0.5, 0.45346276066682156])
    SHADOW_RED_MIN = np.array([-0.03269528558374073, -0.2197767889941315, 0.325])
    SHADOW_RED_MAX = np.array([0.07114116041628536, 0.11218942078167213, 0.4614709191203409])

    # ------------------------------------------------------------------
    # S1 -- as spawned
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    log("STATE S1 -- as-spawned (matches boxel_data.json)")
    depth_m, seg, view, proj, pix, det = render_state(env)
    report_global_pixels("S1", pix, name_by_id)
    analyze_shadow("S1 shadow_of_green_object (unblocked by any occluder "
                   "list -- own caster still on table at spawn)",
                   SHADOW_GREEN_MIN, SHADOW_GREEN_MAX,
                   depth_m, seg, view, proj, target_id,
                   ignore_common | {env.objects["green_object"].object_id},
                   name_by_id, pix)
    analyze_shadow("S1 shadow_of_red_object",
                   SHADOW_RED_MIN, SHADOW_RED_MAX,
                   depth_m, seg, view, proj, target_id,
                   ignore_common | {env.objects["red_object"].object_id},
                   name_by_id, pix)

    # ------------------------------------------------------------------
    # S2 -- green at free_003 (log line 228: pos=[0.2051,-0.1545,0.3913]),
    # orange thrown off the arm during the plan #1 place-at-free_005
    # transit (log lines 138-148).  Two rival endings for orange.
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    log("STATE S2 -- green placed at free_003; orange thrown (two endings)")
    teleport(env, "green_object", (0.2051, -0.1545, 0.3913))

    orange_id = env.objects["orange_object"].object_id
    orange_half_z = 0.0341  # boxel_data.json orange_object extent[2] (half-height)

    endings = {
        "S2a floor-beside-table": (0.00, -0.55, orange_half_z),
        "S2b on-table frame-edge (near free_005 corner)": (-0.08, -0.38, 0.325 + orange_half_z),
    }
    ignore_S2 = ignore_common | {env.objects["green_object"].object_id}
    for label, pos in endings.items():
        log(f"\n  -- {label}: teleporting orange_object to {pos} --")
        teleport(env, "orange_object", pos)
        depth_m, seg, view, proj, pix, det = render_state(env)
        report_global_pixels(label, pix, name_by_id)
        res = analyze_shadow(f"{label} / shadow_of_green_object",
                              SHADOW_GREEN_MIN, SHADOW_GREEN_MAX,
                              depth_m, seg, view, proj, target_id,
                              ignore_S2, name_by_id, pix)
        orange_global_px = pix.get(orange_id, 0)
        orange_in_sense_detections = "orange_object" in det
        log(f"      orange_object global_seg_px={orange_global_px} "
            f"(<{DETECTION_MIN_PIXELS} -> {'NOT in sense_detections' if not orange_in_sense_detections else 'IN sense_detections'})")
        reproduces = (orange_global_px < DETECTION_MIN_PIXELS
                      and orange_id in res["sub_detection_interceptors"])
        log(f"      REPRODUCES log pattern (<6px AND intercepts "
            f"shadow_of_green endpoints)? {reproduces}")

    # ------------------------------------------------------------------
    # S3 -- log line 529/583 state: green at free_003, red at free_011
    # (log line 452: pos=[0.2039,-0.0019,0.3951]), orange still missing
    # (never relocated by the planner -- registry keeps believing it is
    # at its ORIGINAL boxel the whole run, log lines 148/244/.../585).
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    log("STATE S3 -- green@free_003, red@free_011, orange missing "
        "(log line 529/583 -- shadow_of_red_object unlocalizable strikes 2/3)")
    teleport(env, "red_object", (0.2039, -0.0019, 0.3951))
    # orange: test the same two endings again (whichever reproduced S2's
    # pattern is used as the primary hypothesis; both are reported).
    for label, pos in endings.items():
        log(f"\n  -- {label}: orange_object at {pos} --")
        teleport(env, "orange_object", pos)
        depth_m, seg, view, proj, pix, det = render_state(env)
        report_global_pixels(f"S3/{label}", pix, name_by_id)

        ignore_S3 = ignore_common | {env.objects["red_object"].object_id}

        res_full = analyze_shadow(
            f"S3/{label} / shadow_of_red_object (ORIGINAL spawn AABB)",
            SHADOW_RED_MIN, SHADOW_RED_MAX,
            depth_m, seg, view, proj, target_id, ignore_S3, name_by_id, pix)

        # Reconstructed shrunk AABB (log: "10.4x33.2x13.6 -> 4.3x8.3x9.1
        # cm").  The exact center depends on the ROBOT ARM's transient
        # pose during attempt 1's still_blocked classification (log line
        # 466: "4/388 endpoints hidden by robot arm"), which this probe
        # deliberately does NOT replay.  We anchor the reconstructed box
        # at the ORIGINAL fragment's centroid in XY (the shrink formula
        # clamps to the original fragment and pads from blocked-endpoint
        # positions, so the surviving box stays inside the original
        # bounds) -- this is a HYPOTHESIS placement, not a replay of the
        # true shrunk region.
        shrink_size = np.array([0.043, 0.083, 0.091])
        orig_center = (SHADOW_RED_MIN + SHADOW_RED_MAX) / 2.0
        shrink_min = orig_center - shrink_size / 2.0
        shrink_max = orig_center + shrink_size / 2.0
        # clamp to original fragment
        shrink_min = np.maximum(shrink_min, SHADOW_RED_MIN)
        shrink_max = np.minimum(shrink_max, SHADOW_RED_MAX)
        log(f"      reconstructed shrunk AABB (HYPOTHESIS center): "
            f"min={shrink_min.tolist()} max={shrink_max.tolist()} "
            f"size_cm={(100*(shrink_max-shrink_min)).tolist()}")
        res_shrunk = analyze_shadow(
            f"S3/{label} / shadow_of_red_object (RECONSTRUCTED shrunk AABB)",
            shrink_min, shrink_max,
            depth_m, seg, view, proj, target_id, ignore_S3, name_by_id, pix)

        orange_global_px = pix.get(orange_id, 0)
        for tag, res in (("original-AABB", res_full), ("shrunk-AABB", res_shrunk)):
            reproduces = (orange_global_px < DETECTION_MIN_PIXELS
                          and orange_id in res["sub_detection_interceptors"])
            log(f"      [{tag}] orange global_px={orange_global_px} "
                f"REPRODUCES unlocalizable-interceptor pattern? {reproduces}")

    # ------------------------------------------------------------------
    # S2-sweep -- neither hand-picked ending reproduced the log pattern
    # (see probe_A_stdout.txt: S2a had 0 global px / 0 intercepts, S2b
    # had 6372 global px -- fully visible, not a sliver).  Grid-search
    # BOTH candidate regions for an orange_object pose that DOES produce
    # a sub-DETECTION_MIN_PIXELS body intercepting shadow_of_green_object
    # endpoints, so the "two endings" framing gets an actual answer
    # instead of two dead ends.  green stays at free_003 throughout.
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    log("S2-SWEEP -- grid search for an orange pose reproducing the log's "
        "'<6px AND intercepts shadow_of_green_object' pattern")
    teleport(env, "green_object", (0.2051, -0.1545, 0.3913))
    ignore_sweep = ignore_common | {env.objects["green_object"].object_id}

    def sweep(region_name, x_range, y_range, z, nx=13, ny=13):
        xs = np.linspace(*x_range, nx)
        ys = np.linspace(*y_range, ny)
        hits = []
        for x in xs:
            for y in ys:
                teleport(env, "orange_object", (float(x), float(y), z))
                depth_m, seg, view, proj = None, None, None, None
                _, _, depth_buf, seg = env.detect_objects()
                depth_m = env._depth_buffer_to_meters(depth_buf)
                view, proj = env._view_and_projection_matrices()
                ids, counts = np.unique(seg, return_counts=True)
                opx = int(counts[ids == orange_id][0]) if orange_id in ids else 0
                pts, _, _, _ = endpoints_for(SHADOW_GREEN_MIN, SHADOW_GREEN_MAX)
                icp, hids, in_view = first_surface_interceptors(
                    pts, depth_m, seg, view, proj)
                mask = icp & in_view & (hids.astype(int) == orange_id)
                n_hit = int(np.count_nonzero(mask))
                if n_hit > 0:
                    hits.append((float(x), float(y), z, opx, n_hit))
        hits.sort(key=lambda h: (h[3], -h[4]))  # fewest global px first
        log(f"  region '{region_name}': grid {nx}x{ny} over "
            f"x={x_range} y={y_range} z={z:.4f}  "
            f"-> {len(hits)} pose(s) intercept >=1 shadow_of_green endpoint")
        for x, y, zz, opx, n_hit in hits[:15]:
            below = " <-- SUB-DETECTION-MIN INTERCEPTOR" if opx < DETECTION_MIN_PIXELS else ""
            log(f"      pos=({x:+.3f},{y:+.3f},{zz:.3f}) "
                f"orange_global_px={opx:>5} endpoints_hit={n_hit:>3}{below}")
        return hits

    hits_floor = sweep("floor-beside-table", (-0.35, 0.35), (-0.95, -0.50),
                       orange_half_z)
    hits_edge = sweep("table-frame-edge (near-y strip, y=-0.40..-0.30)",
                      (-0.10, 0.30), (-0.40, -0.30), 0.325 + orange_half_z)
    hits_edge2 = sweep("table-frame-edge (near-x strip, x=-0.10)",
                       (-0.10, -0.10), (-0.45, 0.45), 0.325 + orange_half_z,
                       nx=1, ny=19)

    all_hits = hits_floor + hits_edge + hits_edge2
    sub_min_hits = [h for h in all_hits if h[3] < DETECTION_MIN_PIXELS]
    log(f"\n  TOTAL sub-DETECTION_MIN_PIXELS interceptor poses found: "
        f"{len(sub_min_hits)} / {len(all_hits)} intercepting poses tried")
    if sub_min_hits:
        bx, by, bz, bpx, bn = sub_min_hits[0]
        log(f"  BEST MATCH: pos=({bx:+.3f},{by:+.3f},{bz:.3f}) "
            f"orange_global_px={bpx} endpoints_hit={bn} -- teleporting "
            f"there and re-confirming with full analyze_shadow():")
        teleport(env, "orange_object", (bx, by, bz))
        depth_m, seg, view, proj, pix, det = render_state(env)
        report_global_pixels("S2-best-match", pix, name_by_id)
        analyze_shadow("S2-best-match / shadow_of_green_object",
                       SHADOW_GREEN_MIN, SHADOW_GREEN_MAX,
                       depth_m, seg, view, proj, target_id, ignore_sweep,
                       name_by_id, pix)
    else:
        log("  No sub-DETECTION_MIN_PIXELS interceptor pose found in either "
            "swept region -- see report for the geometric explanation "
            "(orange's own footprint is >= 6px whenever it is close/large "
            "enough to a sense endpoint's line of sight to intercept it; "
            "the interceptor is more likely visible from ONE endpoint's "
            "narrow projection while occluded from most of the frame by "
            "another body, not a free-standing sliver).")

    # ------------------------------------------------------------------
    # S2-wedge -- the flat-sweep found intercepting poses only where
    # orange sits fully exposed (hundreds-to-thousands of px, never
    # <6).  Try WEDGED / partially-occluded / frame-corner poses: a
    # sliver of orange peeking from behind red_object, or cropped at
    # the extreme table corner nearest the image edge.
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    log("S2-WEDGE -- partially-occluded / frame-corner candidate poses")
    red_pos, red_orn = p.getBasePositionAndOrientation(
        env.objects["red_object"].object_id, physicsClientId=env.client_id)
    wedge_candidates = {
        "behind red_object (+3cm further from camera)":
            (red_pos[0], red_pos[1] + 0.03, red_pos[2]),
        "behind red_object (+1.5cm further, tighter graze)":
            (red_pos[0], red_pos[1] + 0.015, red_pos[2]),
        "table far corner (near image edge, +x+y)": (0.66, 0.46, 0.325 + orange_half_z),
        "table near corner (near image edge, -x-y)": (-0.08, -0.39, 0.325 + orange_half_z),
    }
    for label, pos in wedge_candidates.items():
        teleport(env, "orange_object", pos)
        _, _, depth_buf, seg = env.detect_objects()
        depth_m = env._depth_buffer_to_meters(depth_buf)
        view, proj = env._view_and_projection_matrices()
        ids, counts = np.unique(seg, return_counts=True)
        opx = int(counts[ids == orange_id][0]) if orange_id in ids else 0
        pts, _, _, _ = endpoints_for(SHADOW_GREEN_MIN, SHADOW_GREEN_MAX)
        icp, hids, in_view = first_surface_interceptors(pts, depth_m, seg, view, proj)
        mask = icp & in_view & (hids.astype(int) == orange_id)
        n_hit = int(np.count_nonzero(mask))
        flag = " <-- SUB-DETECTION-MIN INTERCEPTOR (reproduces log)" if (
            0 < opx < DETECTION_MIN_PIXELS and n_hit > 0) else ""
        log(f"  {label:<48} pos={tuple(round(v,3) for v in pos)} "
            f"orange_px={opx:>5} shadow_green_hits={n_hit:>3}{flag}")

    # ------------------------------------------------------------------
    # blue_object's own global pixel count in S3 -- was blue itself ever
    # a candidate for the "cannot localize" interceptor?  (Sanity check;
    # sense_shadow_from_render's early `if hit_obj_id == target_pybullet_id:
    # return "found_target"` means a blue hit can never reach the
    # contains_nontarget/unlocalizable branch for ANY shadow, since blue
    # is the sense target in every sense action this run -- this is a
    # logic fact, not just a per-state pixel count, but we report the S3
    # count for completeness.)
    # ------------------------------------------------------------------
    log("\n" + "=" * 78)
    depth_m, seg, view, proj, pix, det = render_state(env)
    blue_px = pix.get(target_id, 0)
    log(f"blue_object global seg pixels in final S3 render: {blue_px} "
        f"(id={target_id})")
    log("blue_object CANNOT be the 'unlocalizable interceptor' by "
        "construction: sense_shadow_from_render returns found_target "
        "immediately on ANY endpoint hit against target_pybullet_id, "
        "before the DETECTION_MIN_PIXELS/localizability check is ever "
        "reached (execution.py sense_shadow_from_render ~line 190).")

    # ------------------------------------------------------------------
    # PART 2 (authoritative, added after discovering execution.py carries
    # an UNCOMMITTED working-tree change (`git status` -- porcelain " M
    # execution.py", 41 insertions/8 deletions vs HEAD 2056f04) that adds
    # a #P1 F15 diagnostic: sense_shadow_from_render now returns a 5th
    # element `interceptor_counts` ({seg id -> endpoints intercepted}),
    # and handle_sense_action prints an "[F15-diag] discoveries: ..."
    # line naming exactly this probe's target -- BUT this fix postdates
    # run_2026-08-22_17-14-10 (whose log has no [F15-diag] lines), so the
    # investigated run never got to print it.  This section calls the
    # REAL execution.sense_shadow_from_render (not a reimplementation)
    # with occluder_pybullet_ids CORRECTED to match the actual audit-78
    # census at sense time: EMPTY for shadow_of_green_object (green
    # moved off its own casting position, log:230-232) and EMPTY for
    # shadow_of_red_object (red moved to free_011, log:454-455) -- NOT
    # the shadow's own historical caster id, which the S2/S3 sweep above
    # incorrectly excluded via ignore_S2/ignore_S3.  This both (a)
    # validates the sweep's sub-detection-interceptor conclusions were
    # not an artefact of that over-exclusion, and (b) gets the exact
    # F15-diag interceptor name+pixel-count string the real code would
    # have printed, for any state where the guard actually fires.
    # ------------------------------------------------------------------
    from execution import sense_shadow_from_render
    from boxel_data import BoxelData, BoxelType

    def real_sense(tag, frag_min, frag_max, occluder_ids, orange_pos=None,
                   hide_orange=False):
        if hide_orange:
            hide_far_away(env, "orange_object")
        elif orange_pos is not None:
            teleport(env, "orange_object", orange_pos)
        depth_m, seg, view, proj, pix, det = render_state(env)
        shadow_bd = BoxelData(boxel_type=BoxelType.SHADOW,
                              min_corner=np.asarray(frag_min, dtype=float),
                              max_corner=np.asarray(frag_max, dtype=float))
        outcome, blocked_frac, detected, bbox, icounts = \
            sense_shadow_from_render(
                shadow_bd, target_id, depth_m, seg, view, proj,
                occluder_pybullet_ids=occluder_ids,
                robot_id=robot_id, support_body_ids=support_ids)
        log(f"  [REAL sense_shadow_from_render / {tag}] outcome={outcome} "
            f"blocked_fraction={blocked_frac:.3f} "
            f"detected_bodies={sorted(detected)} "
            f"interceptor_counts={icounts}")
        for bid, n in sorted(icounts.items(), key=lambda kv: -kv[1]):
            nm = name_by_id.get(bid, f"id{bid}")
            gp = pix.get(bid, 0)
            role = "TARGET" if bid == target_id else (
                "occluder/robot/support(excluded-from-detected)"
                if bid not in detected else
                ("LOCALIZED(>=6px)" if gp >= DETECTION_MIN_PIXELS
                 else "SUB-DETECTION-MIN INTERCEPTOR"))
            log(f"      seg id {bid:>2} ({nm:<14}) endpoints={n:>4} "
                f"global_px={gp:>6}  {role}")
        # Reproduce the exact string handle_sense_action would print
        # (execution.py [F15-diag] block) when outcome is
        # contains_nontarget with zero localized discoveries.
        if outcome == "contains_nontarget":
            loc_names = [name_by_id[b] for b in detected
                        if b in name_by_id and name_by_id[b] in det]
            if not loc_names:
                diag = []
                for b in sorted(detected):
                    nm = name_by_id.get(b, f"<seg id {b}>")
                    px = pix.get(b, 0)
                    diag.append(f"{nm}(id={b}) endpoints={icounts.get(b,0)} "
                               f"seg_px={px} "
                               f"{'localized' if nm in det else 'BELOW_MIN'}")
                log(f"      [F15-diag, reproduced] discoveries: "
                    f"{'; '.join(diag)} | detection minimum "
                    f"{DETECTION_MIN_PIXELS} px | localized this render: "
                    f"{sorted(det)}")
        return outcome, detected, icounts, pix

    log("\n" + "=" * 78)
    log("PART 2 -- authoritative replay via the REAL "
        "execution.sense_shadow_from_render (with #P1 F15 "
        "interceptor_counts), occluder_pybullet_ids CORRECTED to the "
        "actual audit-78 census (empty for both shadows once their "
        "caster relocated)")

    teleport(env, "green_object", (0.2051, -0.1545, 0.3913))
    teleport(env, "red_object", (0.0434, -0.2475, 0.3932))  # red's ORIGINAL spawn (not yet moved during plan #2/3/4)

    log("\n  -- shadow_of_green_object, orange HIDDEN (sanity: is anything "
        "ELSE -- green's own new position, red at original spawn -- an "
        "interceptor once orange is out of the picture?) --")
    real_sense("green-shadow / orange hidden far away",
              SHADOW_GREEN_MIN, SHADOW_GREEN_MAX, set(), hide_orange=True)

    log("\n  -- shadow_of_green_object, orange at S2a (floor-beside-table) --")
    real_sense("green-shadow / S2a", SHADOW_GREEN_MIN, SHADOW_GREEN_MAX,
              set(), orange_pos=endings["S2a floor-beside-table"])

    log("\n  -- shadow_of_green_object, orange at S2b (on-table frame-edge) --")
    real_sense("green-shadow / S2b", SHADOW_GREEN_MIN, SHADOW_GREEN_MAX,
              set(), orange_pos=endings["S2b on-table frame-edge (near free_005 corner)"])

    # shadow_of_red_object: red now at free_011 (its post-place position),
    # green at free_003, occluder set EMPTY (log:454-455 shows red's own
    # OLD shadow gets no blocker line printed -> blockers=0, matching
    # diag "shadow_of_red_object(blockers=0)" at plan #6, log:484).
    teleport(env, "red_object", (0.2039, -0.0019, 0.3951))

    log("\n  -- shadow_of_red_object (ORIGINAL AABB), orange HIDDEN (sanity) --")
    real_sense("red-shadow(orig) / orange hidden far away",
              SHADOW_RED_MIN, SHADOW_RED_MAX, set(), hide_orange=True)

    log("\n  -- shadow_of_red_object (ORIGINAL AABB), orange at S2a --")
    real_sense("red-shadow(orig) / S2a", SHADOW_RED_MIN, SHADOW_RED_MAX,
              set(), orange_pos=endings["S2a floor-beside-table"])

    log("\n  -- shadow_of_red_object (ORIGINAL AABB), orange at S2b --")
    real_sense("red-shadow(orig) / S2b", SHADOW_RED_MIN, SHADOW_RED_MAX,
              set(), orange_pos=endings["S2b on-table frame-edge (near free_005 corner)"])

    shrink_size = np.array([0.043, 0.083, 0.091])
    orig_center = (SHADOW_RED_MIN + SHADOW_RED_MAX) / 2.0
    shrink_min = np.maximum(orig_center - shrink_size / 2.0, SHADOW_RED_MIN)
    shrink_max = np.minimum(orig_center + shrink_size / 2.0, SHADOW_RED_MAX)

    log("\n  -- shadow_of_red_object (RECONSTRUCTED SHRUNK AABB), orange at S2a --")
    real_sense("red-shadow(shrunk) / S2a", shrink_min, shrink_max,
              set(), orange_pos=endings["S2a floor-beside-table"])

    log("\n  -- shadow_of_red_object (RECONSTRUCTED SHRUNK AABB), orange at S2b --")
    real_sense("red-shadow(shrunk) / S2b", shrink_min, shrink_max,
              set(), orange_pos=endings["S2b on-table frame-edge (near free_005 corner)"])

    # ------------------------------------------------------------------
    # PART 3 -- why does orange_object's registry belief STAY stale
    # ("keeping last estimate") for all 7 refreshes instead of ever
    # flipping to LOST (execution.py refresh_object_aabbs, check_lost
    # branch, ~line 1691-1712)?  That check runs first_surface_interceptors
    # DIRECTLY on orange's OWN (still-original-spawn) OBJECT boxel with
    # NO ignore_ids at all (no robot/support/occluder exclusion, unlike
    # sense_shadow_from_render) -- ANY interceptor on >5% of one slice
    # keeps it "stale" rather than "lost".  Test this on orange's
    # ORIGINAL AABB (boxel_data.json orange_object corners) at every
    # reconstructed state.
    # ------------------------------------------------------------------
    from perception import first_surface_interceptors as _fsi, sense_ray_slices as _srs
    ORANGE_OWN_MIN = np.array([0.13282831545758614, 0.13767994520604762, 0.325])
    ORANGE_OWN_MAX = np.array([0.18704286899097097, 0.19189449873943246, 0.4584766931587999])

    def lost_check(tag):
        depth_m, seg, view, proj, pix, det = render_state(env)
        slices, _ = _srs(ORANGE_OWN_MIN, ORANGE_OWN_MAX)
        observed_empty = True
        worst = 0.0
        worst_ids = {}
        for sl in slices:
            icp, hids, in_view = _fsi(sl.points, depth_m, seg, view, proj)
            not_vis = np.count_nonzero(icp | ~in_view)
            frac = not_vis / len(sl.points)
            if frac > worst:
                worst = frac
                blocking = {}
                for i in range(len(sl.points)):
                    if icp[i] and in_view[i]:
                        bid = int(hids[i])
                        blocking[bid] = blocking.get(bid, 0) + 1
                worst_ids = blocking
            if frac > SENSE_MARGINAL_BLOCKED_FRACTION:
                observed_empty = False
        log(f"  [orange-own-boxel LOST-check / {tag}] observed_empty="
            f"{observed_empty} worst_slice_blocked_fraction={worst:.3f} "
            f"worst_slice_blockers={ {name_by_id.get(k,k): v for k, v in worst_ids.items()} }")

    log("\n" + "=" * 78)
    log("PART 3 -- does orange_object's OWN original-spawn OBJECT boxel "
        "ever render 'observed empty' (which would flip it LOST instead "
        "of staying 'stale/keeping last estimate')?  refresh_object_aabbs "
        "check_lost path uses first_surface_interceptors with NO "
        "ignore_ids at all.")
    teleport(env, "green_object", (0.2051, -0.1545, 0.3913))
    teleport(env, "red_object", (0.04336833419833798, -0.24754961521207888, 0.3932354595601705))  # red original
    hide_far_away(env, "orange_object")
    lost_check("green@free_003, red@ORIGINAL, orange hidden (models plan #2/3/4 refresh)")
    teleport(env, "red_object", (0.2039, -0.0019, 0.3951))  # red@free_011
    lost_check("green@free_003, red@free_011, orange hidden (models plan #6/7 refresh)")

    env.close()

    with open(DUMP_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_dump_lines) + "\n")
    log(f"\nRaw per-endpoint dump written to {DUMP_PATH}")


if __name__ == "__main__":
    main()
