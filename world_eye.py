"""
World Eye — textual snapshots of the world, the belief and the camera view.

User request 2026-09-18 (after the #P1 F20/F21 forensics): a run must leave
behind enough state that a reader can rebuild a mental picture of ANY
moment of the episode without a GUI — where every object really is, where
the robot BELIEVES it is, what the camera can see, and what the symbolic
state says — and that material must be queryable by time rather than
scrolled through.

Two outputs per run, both in the run directory:

  eye.log    — human-readable blocks, one per snapshot (read top to bottom
               like the run log; a few KB per snapshot).
  eye.jsonl  — one JSON record per snapshot for tooling.  ``tools/eye.py``
               selects a snapshot by index / plan / sim step / wall time /
               tag and re-renders it, including the ASCII camera view and
               the planner's init facts.

Snapshots are taken at the observation and decision points of the
sense-plan-act loop (initial observation, every replan after planning,
before every executed action, every sense observation, and the final
state), not per simulation step — the F17 telemetry stream already covers
physics at frame rate.  Cost: a few milliseconds per snapshot without a
camera view; one TinyRenderer pass (~0.2 s) when a view is requested and
no render is supplied.  Ground truth (true poses, the segmentation mask)
is read here ONLY for logging: nothing in this module feeds the registry,
the belief or the planner (same contract as telemetry.py).

Module API mirrors telemetry.py: ``enable`` / ``disable`` / ``snapshot`` /
``is_active``; every call is a no-op while disabled.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pybullet as p

import telemetry
from boxel_data import BoxelType

EE_LINK = 11            # panda_grasptarget (robot_utils.END_EFFECTOR_LINK)
ARM_JOINTS = (0, 1, 2, 3, 4, 5, 6)
FINGER_JOINTS = (9, 10)
_SUPPORTS = ("plane", "table", "robot")

# Init predicates worth spelling out verbatim in a snapshot.  The rest
# (Boxel/is_free_space/on_surface and the per-free-cell KIF and
# blocks_view_at explosions) are summarised as counts only.
_VERBATIM_PREDICATES = {
    "obj_at_boxel", "holding", "handempty", "on", "clear", "on_table",
    "at_config", "is_object", "is_shadow", "is_tray", "obj_pose_known",
    "Obj",
}

_ACTIVE: "WorldEye | None" = None


def _r(v, nd: int = 4):
    return [round(float(x), nd) for x in np.asarray(v, dtype=float).ravel()]


def _fmt3(v) -> str:
    v = np.asarray(v, dtype=float).ravel()
    return f"({v[0]:+.3f},{v[1]:+.3f},{v[2]:+.3f})"


def _tilt_deg(quat) -> float:
    rot = np.array(p.getMatrixFromQuaternion(quat)).reshape(3, 3)
    up = rot[:, 2]
    return float(np.degrees(np.arccos(np.clip(up[2], -1.0, 1.0))))


class WorldEye:
    """Snapshot writer.  See the module docstring."""

    def __init__(self, run_dir, env, robot_id, body_names: Dict[int, str],
                 ascii_cols: int = 96, ascii_rows: int = 36):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.env = env
        self.robot_id = robot_id
        self.body_names = dict(body_names or {})
        self.ascii_cols = int(ascii_cols)
        self.ascii_rows = int(ascii_rows)
        self.t0 = time.monotonic()
        self.count = 0
        self._log = open(self.run_dir / "eye.log", "w", encoding="utf-8")
        self._jsonl = open(self.run_dir / "eye.jsonl", "w", encoding="utf-8")
        self._letters = self._assign_letters()
        legend = ", ".join(f"{ch}={self.body_names[b]}"
                           for b, ch in sorted(self._letters.items(),
                                               key=lambda kv: kv[1]))
        self._log.write(
            "# Semantic Boxels world eye — one block per snapshot.\n"
            "# true = simulator pose (logging only); believed = registry "
            "OBJECT boxel (what the planner sees); err = |believed centre "
            "- true centre|.\n"
            f"# camera-view letters: {legend}; '#'=robot, '.'=table, "
            "' '=nothing/plane\n\n")
        self._legend = legend

    # ----- lifecycle -------------------------------------------------------

    def close(self):
        for fh in (self._log, self._jsonl):
            try:
                fh.flush()
                fh.close()
            except Exception:
                pass

    def _assign_letters(self) -> Dict[int, str]:
        letters: Dict[int, str] = {}
        used = set("#. ")
        for bid, name in sorted(self.body_names.items(), key=lambda kv: kv[1]):
            if name in _SUPPORTS:
                continue
            cand = name[0].upper()
            if cand in used:
                for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
                    if ch not in used:
                        cand = ch
                        break
            used.add(cand)
            letters[bid] = cand
        return letters

    # ----- state readers (logging only) -----------------------------------

    def _robot(self) -> Optional[dict]:
        if self.robot_id is None:
            return None
        try:
            st = p.getLinkState(self.robot_id, EE_LINK)
            q = [p.getJointState(self.robot_id, j)[0] for j in ARM_JOINTS]
            fingers = [p.getJointState(self.robot_id, j)[0]
                       for j in FINGER_JOINTS]
        except Exception:
            return None
        return {"ee_pos": _r(st[0]), "q": _r(q, 4), "fingers": _r(fingers, 4)}

    def _objects(self, registry, detections, seg) -> List[dict]:
        out = []
        for name, info in self.env.objects.items():
            if name in _SUPPORTS:
                continue
            bid = info.object_id
            try:
                pos, quat = p.getBasePositionAndOrientation(bid)
                amin, amax = p.getAABB(bid)
            except Exception:
                continue
            rec = {
                "name": name, "id": bid,
                "role": ("tray" if getattr(info, "is_tray", False)
                         else "occluder" if info.is_occluder else "target"),
                "true_pos": _r(pos), "true_aabb": [_r(amin), _r(amax)],
                "tilt_deg": round(_tilt_deg(quat), 1),
            }
            bd = registry.get_boxel(name) if registry is not None else None
            if bd is not None and bd.boxel_type == BoxelType.OBJECT:
                c = bd.center
                rec["believed_aabb"] = [_r(bd.min_corner), _r(bd.max_corner)]
                rec["believed_pos"] = _r(c)
                rec["err_mm"] = round(float(np.linalg.norm(
                    np.asarray(c) - np.asarray(pos))) * 1000.0, 1)
                rec["on_surface"] = bd.on_surface
                rec["is_occluder"] = bool(bd.is_occluder)
                rec["shadow_ids"] = list(bd.shadow_boxel_ids)
            else:
                rec["believed_aabb"] = None
            if seg is not None:
                rec["visible_px"] = int(np.count_nonzero(seg == bid))
            if detections is not None and name in detections:
                d = detections[name]
                rec["detected"] = {"px": int(d.pixel_count),
                                   "est_min": _r(d.est_min),
                                   "est_max": _r(d.est_max)}
            out.append(rec)
        return out

    def _shadows(self, registry, belief, shadow_occluder_map) -> List[dict]:
        if registry is None:
            return []
        out = []
        for bd in registry.get_shadow_boxels():
            sid = str(bd.id)
            out.append({
                "id": sid,
                "aabb": [_r(bd.min_corner), _r(bd.max_corner)],
                "caster": bd.created_by_boxel_id or bd.created_by_object,
                "status": (belief.shadow_status.get(sid, "?")
                           if belief is not None else None),
                "blockers": (list(shadow_occluder_map.get(sid, []))
                             if shadow_occluder_map else None),
            })
        return out

    def _free(self, registry) -> List[dict]:
        if registry is None:
            return []
        return [{"id": b.id, "aabb": [_r(b.min_corner, 3), _r(b.max_corner, 3)]}
                for b in registry.get_free_space_boxels()]

    def _belief(self, belief, on_relations) -> Optional[dict]:
        if belief is None:
            return None
        return {
            "target": belief.target,
            "target_found_in": belief.target_found_in,
            "unknown": belief.get_unknown_shadows(),
            "known_empty": belief.get_known_empty_shadows(),
            "parked": belief.get_parked_shadows(),
            "occluders_moved": dict(belief.occluders_moved),
            "on_relations": dict(on_relations or {}),
        }

    @staticmethod
    def _symbolic(init_facts) -> Optional[dict]:
        if not init_facts:
            return None
        counts: Dict[str, int] = {}
        verbatim: List[str] = []
        for fact in init_facts:
            try:
                pred = str(fact[0])
            except Exception:
                continue
            counts[pred] = counts.get(pred, 0) + 1
            if pred in _VERBATIM_PREDICATES:
                verbatim.append("(" + " ".join(str(a) for a in fact) + ")")
            elif pred == "obj_at_boxel_KIF" and len(fact) == 3 \
                    and not str(fact[2]).startswith("free_"):
                verbatim.append("(" + " ".join(str(a) for a in fact) + ")")
            elif pred == "blocks_view_at" and len(fact) == 4 \
                    and not str(fact[2]).startswith("free_"):
                verbatim.append("(" + " ".join(str(a) for a in fact) + ")")
        return {"counts": counts, "facts": sorted(verbatim)}

    def _view(self, seg) -> Optional[dict]:
        """Downsample the segmentation mask to an ASCII picture."""
        if seg is None:
            return None
        H, W = seg.shape
        rows, cols = self.ascii_rows, self.ascii_cols
        bh, bw = H // rows, W // cols
        if bh < 1 or bw < 1:
            return None
        crop = seg[:bh * rows, :bw * cols].reshape(rows, bh, cols, bw)
        crop = crop.transpose(0, 2, 1, 3).reshape(rows, cols, bh * bw)
        block_px = bh * bw
        name_of = self.body_names
        lines = []
        for r in range(rows):
            chars = []
            for c in range(cols):
                ids, cnt = np.unique(crop[r, c], return_counts=True)
                best_obj, best_obj_n = None, 0
                maj_id, maj_n = None, 0
                for i, n in zip(ids.tolist(), cnt.tolist()):
                    if i in self._letters and n > best_obj_n:
                        best_obj, best_obj_n = i, n
                    if n > maj_n:
                        maj_id, maj_n = i, n
                # Objects win a block at 8 % occupancy so a half-hidden
                # 3 cm cube (~50 px spread over a few blocks) still shows.
                if best_obj is not None and best_obj_n >= max(2, 0.08 * block_px):
                    chars.append(self._letters[best_obj])
                    continue
                nm = name_of.get(maj_id)
                if maj_id == self.robot_id:
                    chars.append("#")
                elif nm == "table":
                    chars.append(".")
                else:
                    chars.append(" ")
            lines.append("".join(chars))
        return {"rows": lines, "legend": self._legend,
                "image": [int(W), int(H)]}

    # ----- the snapshot ----------------------------------------------------

    def snapshot(self, tag: str, *, registry=None, belief=None,
                 plan_count=None, action=None, held=None, detections=None,
                 render=None, with_view: bool = False, on_relations=None,
                 shadow_occluder_map=None, init_facts=None, plan=None,
                 extra=None) -> dict:
        """Write one snapshot.  ``render`` is (depth_m, seg, view, proj)
        from an observation already taken (the sense action's); with
        ``with_view=True`` and no render, one TinyRenderer pass is made
        here and its detections are recorded too."""
        self.count += 1
        seg = None
        if render is not None:
            seg = render[1]
        elif with_view:
            try:
                dets, _, _, seg = self.env.detect_objects()
                if detections is None:
                    detections = dets
            except Exception:
                seg = None
        tele = telemetry.active()
        if action is None and tele is not None:
            action = getattr(tele, "_phase", None)
        rec = {
            "k": self.count,
            "tag": tag,
            "t_wall": round(time.monotonic() - self.t0, 2),
            "sim_step": (tele.step_count if tele is not None else None),
            "sim_t": (round(tele.sim_time, 3) if tele is not None else None),
            "plan": plan_count,
            "action": action,
            "held": held,
            "robot": self._robot(),
            "camera": {"position": _r(self.env.camera_position),
                       "target": _r(self.env.camera_target)},
            "objects": self._objects(registry, detections, seg),
            "shadows": self._shadows(registry, belief, shadow_occluder_map),
            "free": self._free(registry),
            "belief": self._belief(belief, on_relations),
            "symbolic": self._symbolic(init_facts),
            "plan_actions": ([" ".join([str(a[0])]
                                       + [x for x in a[1:] if isinstance(x, str)])
                              for a in plan] if plan else None),
            "view": self._view(seg),
            "extra": extra,
        }
        self._jsonl.write(json.dumps(rec) + "\n")
        self._jsonl.flush()
        self._log.write(render_snapshot(rec) + "\n")
        self._log.flush()
        # One compact line in the main run log so a reader can follow
        # along without opening eye.log.
        objs = " ".join(
            f"{o['name']}@({o['true_pos'][0]:.3f},{o['true_pos'][1]:.3f})"
            + ("" if o.get("believed_aabb") is None
               else f"[bel {o.get('err_mm', 0):.0f}mm]")
            + ("[NO BOXEL]" if o.get("believed_aabb") is None else "")
            for o in rec["objects"])
        unk = (len(rec["belief"]["unknown"]) if rec["belief"] else "-")
        print(f"    [eye #{self.count}] {tag} | held={held or 'none'} | "
              f"unknown shadows={unk} | {objs}")
        return rec


# ----- rendering (shared with tools/eye.py) --------------------------------

def render_snapshot(rec: dict, *, view: bool = True, facts: bool = True,
                    free: bool = False) -> str:
    """Human-readable block for one snapshot record."""
    L: List[str] = []
    hdr = (f"==== eye #{rec['k']}  {rec['tag']}  | plan={rec.get('plan')} "
           f"| wall={rec.get('t_wall')}s")
    if rec.get("sim_step") is not None:
        hdr += f" | sim step={rec['sim_step']} t={rec.get('sim_t')}s"
    hdr += f" | held={rec.get('held') or 'none'}"
    L.append(hdr)
    if rec.get("action"):
        L.append(f"  action: {rec['action']}")
    rob = rec.get("robot")
    if rob:
        L.append(f"  robot: ee={_fmt3(rob['ee_pos'])} fingers="
                 f"[{rob['fingers'][0]:.3f},{rob['fingers'][1]:.3f}] "
                 f"q=[{','.join(f'{v:.2f}' for v in rob['q'])}]")
    cam = rec.get("camera") or {}
    if cam:
        L.append(f"  camera: at {_fmt3(cam['position'])} looking at "
                 f"{_fmt3(cam['target'])}")
    L.append(f"  {'OBJECT':<15} {'role':<8} {'true centre':<24} "
             f"{'believed centre':<24} {'err':>7} {'px':>5}  boxel/shadows")
    for o in rec.get("objects", []):
        if o.get("believed_aabb") is None:
            bel, err = "--- NOT IN REGISTRY ---", ""
            tail = ""
        else:
            bel = _fmt3(o["believed_pos"])
            err = f"{o.get('err_mm', 0):.1f}mm"
            tail = (f"on={o.get('on_surface')} occ={o.get('is_occluder')} "
                    f"shadows={o.get('shadow_ids') or []}")
        px = o.get("visible_px")
        px_s = "" if px is None else str(px)
        det = o.get("detected")
        if det:
            tail += f" det={det['px']}px"
        L.append(f"  {o['name']:<15} {o['role']:<8} {_fmt3(o['true_pos']):<24} "
                 f"{bel:<24} {err:>7} {px_s:>5}  {tail}")
    sh = rec.get("shadows") or []
    if sh:
        L.append(f"  SHADOW FRAGMENTS ({len(sh)}):")
        for s in sh:
            a = s["aabb"]
            L.append(f"    {s['id']:<28} {s.get('status') or '?':<10} "
                     f"caster={s.get('caster')} blockers={s.get('blockers')} "
                     f"min={_fmt3(a[0])} max={_fmt3(a[1])}")
    fr = rec.get("free") or []
    L.append(f"  FREE CELLS: {len(fr)}" + ("" if not free else ""))
    if free and fr:
        for f in fr:
            a = f["aabb"]
            L.append(f"    {f['id']:<10} min={_fmt3(a[0])} max={_fmt3(a[1])}")
    b = rec.get("belief")
    if b:
        L.append(f"  BELIEF: target={b['target']} found_in={b['target_found_in']} "
                 f"unknown={b['unknown']} known_empty={b['known_empty']} "
                 f"parked={b['parked']} moved={b['occluders_moved']} "
                 f"on={b['on_relations']}")
    sym = rec.get("symbolic")
    if sym:
        cnt = ", ".join(f"{k}={v}" for k, v in sorted(sym["counts"].items()))
        L.append(f"  SYMBOLIC (last planner init): {cnt}")
        if facts:
            for f in sym["facts"]:
                L.append(f"    {f}")
    if rec.get("plan_actions"):
        L.append("  PLAN: " + " ; ".join(rec["plan_actions"]))
    if rec.get("extra"):
        L.append(f"  extra: {rec['extra']}")
    v = rec.get("view")
    if v and view:
        L.append(f"  CAMERA VIEW ({v['image'][0]}x{v['image'][1]} px -> "
                 f"{len(v['rows'][0])}x{len(v['rows'])}; {v['legend']}; "
                 f"#=robot .=table):")
        L.append("    +" + "-" * len(v["rows"][0]) + "+")
        for row in v["rows"]:
            L.append("    |" + row + "|")
        L.append("    +" + "-" * len(v["rows"][0]) + "+")
    return "\n".join(L)


# ----- module API ----------------------------------------------------------

def enable(run_dir, env, robot_id, body_names, **kwargs) -> WorldEye:
    global _ACTIVE
    _ACTIVE = WorldEye(run_dir, env, robot_id, body_names, **kwargs)
    return _ACTIVE


def disable():
    global _ACTIVE
    if _ACTIVE is not None:
        _ACTIVE.close()
    _ACTIVE = None


def is_active() -> bool:
    return _ACTIVE is not None


def snapshot(tag: str, **kwargs):
    if _ACTIVE is not None:
        try:
            return _ACTIVE.snapshot(tag, **kwargs)
        except Exception as e:  # never let the observer break the run
            print(f"    [eye] snapshot '{tag}' failed: {e}")
    return None
