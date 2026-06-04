#!/usr/bin/env python3
"""
render_boxelization_3d.py -- a 3-D version of the discretization schematic, laid
out as the SAME six-panel (a)-(f) progression as the 2-D figure
(render_boxelization_schematic.py) but with each panel drawn in 3-D. Boxels are
cuboids, so 3-D is the honest view.

    (a) initial scene (camera viewpoint + objects)
    (b) object-centric bounding
    (c) occlusion-aware subdivision (+ line of sight)
    (d) free space: whole workspace as one cell
    (e) free space: recursive octree split (splits in z too, not just x-y)
    (f) free space: greedy convex merge

The robot viewpoint is drawn as a camera emoji when Segoe UI Emoji is available
(run with Windows Python); otherwise it falls back to a dark cube.

Headless (Agg). Writes a NEW file, thesis/graphics/boxelization_3d.png.

RUN (Windows Python, repo root -- emoji needs the Windows font):
    python tools\\render_boxelization_3d.py
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.colors import to_rgba

# reuse layout + shadow geometry from the 2-D generator. The 3-D figure has its
# OWN free-space partition (a real octree, below), so it does NOT import the
# 2-D quad-tree.
from render_boxelization_schematic import (
    OBJECTS, VIEW, CAM_Z, W, H, _rect_of,
    compute_shadows, silhouette_rays,
    C_VIEW, C_OBJ, C_OBJBOX, C_OCC_E, C_FREE_E, C_TITLE, C_LOS,
    C_HIDE_F, C_HIDE_E,
)

# All four occluders are shown. With the finite occlusion shadows (they now end
# at the table behind each object instead of sweeping to the workspace edge) the
# 3-D view no longer gets crowded, so it uses the full scene and recomputes the
# shadow / free-space partition through the shared functions.
OBJECTS_3D = list(OBJECTS)
OBJ_RECTS_3D = [_rect_of(o) for o in OBJECTS_3D]
OCC_RECTS_3D = compute_shadows(OBJECTS_3D)

# The camera glyph sits at the ACTUAL shadow viewpoint (VIEW) and is raised to
# the projection height CAM_Z, so the occlusion shadows and lines of sight
# genuinely originate from the drawn camera -- a fixed overhead camera looking
# down at the table -- rather than from an unmarked point above the room.
CAM = VIEW
ZVIEW = CAM_Z + 1.0   # z-limit of the view: tall enough to show the raised camera

ZTOP = 2.0           # workspace height; the octree's first z-split lands at the
                     # object top, exposing the free LAYER above the objects
OBJ_H = 1.0          # object cube height
OCC_H = 1.0          # shadow height = object height (shadow_calculator clamps
                     # the ray hits to the table and sets the top to the object
                     # top); the old 2.0 left no room for a free layer above
MIN_RES = 2.0        # octree stop size (schematic units): coarse enough to keep
                     # the figure readable, fine enough to show the z-layering
WALL_H = 0.9         # LOW perimeter wall -- kept short + faint so matplotlib's
                     # 3-D painter can't draw a tall back wall over the target
C_WALL = "#cdd5da"   # perimeter wall
C_TABLE = "#d8cdb0"  # table slab edge (side)
C_FLOOR = "#ece3d0"  # table-top surface (no longer white)


def _shadow_area(obj):
    r = compute_shadows([obj])[0]
    return r[2] * r[3]


def _biggest_shadow_hidden():
    """Hidden target sits inside the shadow of the object casting the LARGEST
    occluded region (the one most worth reasoning about): a little way behind
    that object along the camera ray, clamped to stay inside its shadow."""
    best = max(OBJECTS_3D, key=_shadow_area)
    rx, ry, rw, rh = compute_shadows([best])[0]
    d = np.array([best[0] - VIEW[0], best[1] - VIEW[1]], float)
    d /= np.linalg.norm(d)
    px = min(max(best[0] + d[0] * 1.8, rx + 0.4), rx + rw - 0.4)
    py = min(max(best[1] + d[1] * 1.8, ry + 0.4), ry + rh - 0.4)
    return (px, py, 0.6)


HIDDEN_3D = _biggest_shadow_hidden()

# per-face brightness for a lit-from-above look. _faces order: b, t, f, k, l, r
_SHADE = [0.55, 1.0, 0.84, 0.68, 0.9, 0.6]


def _faces(x, y, z, dx, dy, dz):
    x1, y1, z1 = x + dx, y + dy, z + dz
    return [
        [(x, y, z), (x1, y, z), (x1, y1, z), (x, y1, z)],       # bottom
        [(x, y, z1), (x1, y, z1), (x1, y1, z1), (x, y1, z1)],   # top
        [(x, y, z), (x1, y, z), (x1, y, z1), (x, y, z1)],       # front
        [(x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)],   # back
        [(x, y, z), (x, y1, z), (x, y1, z1), (x, y, z1)],       # left
        [(x1, y, z), (x1, y1, z), (x1, y1, z1), (x1, y, z1)],   # right
    ]


def _box(ax, x, y, z, dx, dy, dz, *, fc, ec, alpha, lw=1.0, zorder=1,
         fill=True, shade=False):
    faces = _faces(x, y, z, dx, dy, dz)
    pc = Poly3DCollection(faces, linewidths=lw)
    if not fill:
        pc.set_facecolor((1.0, 1.0, 1.0, 0.0))
    elif shade:
        r, g, b, _ = to_rgba(fc, alpha)
        pc.set_facecolor([(r * s, g * s, b * s, alpha) for s in _SHADE])
    else:
        pc.set_facecolor(to_rgba(fc, alpha))
    pc.set_edgecolor(to_rgba(ec, 1.0))
    pc.set_zorder(zorder)
    ax.add_collection3d(pc)


# ---------------------------------------------------------------- element draws
def _cylinder(ax, base, axis, radius, length, *, fc, ec, alpha, n=24, zorder=9):
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    tmp = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(a, tmp); u /= np.linalg.norm(u)
    v = np.cross(a, u)
    base = np.asarray(base, float)
    th = np.linspace(0, 2 * np.pi, n + 1)
    r0 = [base + radius * (np.cos(t) * u + np.sin(t) * v) for t in th]
    r1 = [p + length * a for p in r0]
    faces = [[r0[i], r0[i + 1], r1[i + 1], r1[i]] for i in range(n)]
    faces.append(r0[:-1]); faces.append(r1[:-1])
    pc = Poly3DCollection(faces, linewidths=0.3)
    pc.set_facecolor(to_rgba(fc, alpha))
    pc.set_edgecolor(to_rgba(ec, 1.0))
    pc.set_zorder(zorder)
    ax.add_collection3d(pc)


def _camera(ax):
    """The fixed overhead camera, drawn at its true viewpoint (VIEW) raised to the
    projection height CAM_Z so the shadows and lines of sight visibly originate
    from it. A compact dark body + viewfinder on a tall tripod, with a lens
    barrel aimed down at the scene so the lens reads in the image. Composed
    from polygons because matplotlib has no camera primitive."""
    cx, cy = CAM
    bw, bd, bh = 0.95, 0.6, 0.6          # compact body (~half the earlier size)
    bz = CAM_Z - bh / 2                   # body centred on the camera height CAM_Z
    # tall tripod from the body base down to the table
    apex = np.array([cx, cy, bz])
    for ang in (90.0, 210.0, 330.0):
        foot = np.array([cx + 0.5 * np.cos(np.radians(ang)),
                         cy + 0.5 * np.sin(np.radians(ang)), 0.0])
        leg = foot - apex
        length = float(np.linalg.norm(leg))
        _cylinder(ax, apex, leg / length, 0.06, length, fc="#1b2631",
                  ec="#1b2631", alpha=1.0, zorder=7)                    # tripod leg
    _box(ax, cx - bw / 2, cy - bd / 2, bz, bw, bd, bh, fc=C_VIEW, ec="#1b2631",
         alpha=1.0, lw=0.4, zorder=8, shade=True)                       # body
    _box(ax, cx - 0.15, cy - 0.12, bz + bh, 0.3, 0.24, 0.16, fc=C_VIEW,
         ec="#1b2631", alpha=1.0, lw=0.4, zorder=8, shade=True)         # viewfinder
    # prominent lens barrel aimed down at the scene centre
    centre = np.array([cx, cy, CAM_Z])
    axis = np.array([5.0 - cx, 4.0 - cy, 0.0 - CAM_Z]); axis /= np.linalg.norm(axis)
    base = centre + axis * (bd / 2)
    _cylinder(ax, base, axis, 0.24, 0.6, fc="#566573", ec="#1b2631",
              alpha=1.0, zorder=9)                                      # lens barrel
    _cylinder(ax, base + axis * 0.6, axis, 0.19, 0.05, fc="#aed6f1",
              ec="#5dade2", alpha=1.0, zorder=10)                       # lens glass


def _hidden(ax):
    cx, cy, s = HIDDEN_3D
    _box(ax, cx - s / 2, cy - s / 2, 0, s, s, OBJ_H * 0.8, fc=C_HIDE_F,
         ec=C_HIDE_E, alpha=0.7, lw=1.4, zorder=5, shade=True)


def _objects(ax):
    for cx, cy, w, h, _ in OBJECTS_3D:
        _box(ax, cx - w / 2, cy - h / 2, 0, w, h, OBJ_H,
             fc=C_OBJ, ec="#7b241c", alpha=1.0, lw=0.5, zorder=6, shade=True)


def _objboxels(ax):
    for cx, cy, w, h, _ in OBJECTS_3D:
        _box(ax, cx - w / 2 - 0.16, cy - h / 2 - 0.16, -0.05,
             w + 0.32, h + 0.32, OBJ_H + 0.32, fc="none", ec=C_OBJBOX,
             alpha=1.0, lw=1.6, zorder=7, fill=False)


def _occlusion(ax):
    for rx, ry, rw, rh in OCC_RECTS_3D:
        _box(ax, rx, ry, 0, rw, rh, OCC_H, fc="#f5cba7", ec=C_OCC_E,
             alpha=0.16, lw=1.3, zorder=3)


def _los(ax):
    # Mathematically accurate line of sight: each ray leaves the camera (at VIEW,
    # height CAM_Z), grazes an object's top silhouette edge (z=OBJ_H) and
    # continues to where it meets the table (z=0) at the far edge of that object's
    # shadow. Along the ray the horizontal position at height z is
    # view + ((CAM_Z - z)/CAM_Z)*(hit - view), which passes through the top corner
    # at z=OBJ_H and the table hit (= shadow boundary) at z=0.
    cam = (float(VIEW[0]), float(VIEW[1]), CAM_Z)
    segs = []
    for obj in OBJECTS_3D:
        for _p0, hit in silhouette_rays(obj):
            hit = np.array(hit, float)
            segs.append([cam, (hit[0], hit[1], 0.0)])
    ax.add_collection3d(Line3DCollection(segs, colors=C_LOS, linewidths=1.0,
                                         linestyles=(0, (4, 3)), zorder=2))


def _free(ax, cells):
    for cmin, cmax in cells:
        _box(ax, cmin[0], cmin[1], cmin[2],
             cmax[0] - cmin[0], cmax[1] - cmin[1], cmax[2] - cmin[2],
             fc="#a9dfbf", ec=C_FREE_E, alpha=0.10, lw=0.9, zorder=1)


# ---------------------------------------------------- free-space octree (3-D)
# Faithful port of free_space.FreeSpaceGenerator.generate + cell_merger: an
# octree subdivides the workspace into octants and keeps any node clear of all
# content as a free Boxel, so free space splits in z too -- a big layer ABOVE
# the objects, finer cells around them -- then adjacent free boxels sharing a
# full face are greedily merged. This replaces the 2-D quad-tree the 3-D figure
# used to extrude into full-height columns.
def _content_boxes_3d():
    boxes = []
    for rx, ry, rw, rh in OBJ_RECTS_3D:
        boxes.append((np.array([rx, ry, 0.0]), np.array([rx + rw, ry + rh, OBJ_H])))
    for rx, ry, rw, rh in OCC_RECTS_3D:
        boxes.append((np.array([rx, ry, 0.0]), np.array([rx + rw, ry + rh, OCC_H])))
    return boxes


def octree_free(content, min_res):
    """BFS octree subdivision; returns free boxels as (min_xyz, max_xyz)."""
    free = []
    layer = [(np.array([0.0, 0.0, 0.0]), np.array([W, H, ZTOP]))]
    while layer:
        nxt = []
        for nmin, nmax in layer:
            # MIXED iff the node's INTERIOR overlaps content (strict <). A node
            # that merely rests on a content face (e.g. the free layer sitting
            # exactly on the object tops) only touches it and stays free -- so
            # free space is never split, only mixed space is. (free_space.py
            # uses >=/<=; it never trips this because real content heights don't
            # land on octree boundaries, but the schematic's round numbers do.)
            mixed = any(np.all(nmax > bmin) and np.all(nmin < bmax)
                        for bmin, bmax in content)
            if not mixed:
                free.append((nmin, nmax))                 # clear -> free Boxel
                continue
            if float(np.max(nmax - nmin)) <= min_res:
                continue                                  # at resolution -> drop
            mid = (nmin + nmax) / 2.0
            for ix in (0, 1):
                for iy in (0, 1):
                    for iz in (0, 1):
                        cmin = np.array([nmin[0] if ix == 0 else mid[0],
                                         nmin[1] if iy == 0 else mid[1],
                                         nmin[2] if iz == 0 else mid[2]])
                        cmax = np.array([mid[0] if ix == 0 else nmax[0],
                                         mid[1] if iy == 0 else nmax[1],
                                         mid[2] if iz == 0 else nmax[2]])
                        nxt.append((cmin, cmax))
        layer = nxt
    return free


def _try_merge_3d(a, b, tol=1e-4):
    a_min, a_max = a
    b_min, b_max = b
    for axis in range(3):
        others = [i for i in range(3) if i != axis]
        if not all(abs(a_min[o] - b_min[o]) < tol and abs(a_max[o] - b_max[o]) < tol
                   for o in others):
            continue
        if abs(a_max[axis] - b_min[axis]) < tol:
            return (a_min.copy(), b_max.copy())
        if abs(b_max[axis] - a_min[axis]) < tol:
            return (b_min.copy(), a_max.copy())
    return None


def _merge_quality_3d(box):
    ext = (box[1] - box[0]) / 2.0
    mx = float(np.max(ext))
    return float(np.min(ext)) / mx if mx > 1e-9 else 0.0


def merge_3d(boxels, max_iter=100):
    """Greedy face-merge (mirrors CellMerger): combine adjacent boxels aligned
    on the other two axes, preferring the most cubic result."""
    cur = [(b[0].copy(), b[1].copy()) for b in boxels]
    for _ in range(max_iter):
        done = [False] * len(cur)
        result, n_merges = [], 0
        for i in range(len(cur)):
            if done[i]:
                continue
            best, best_j = None, -1
            for j in range(i + 1, len(cur)):
                if done[j]:
                    continue
                m = _try_merge_3d(cur[i], cur[j])
                if m is not None and (best is None or
                                      _merge_quality_3d(m) > _merge_quality_3d(best)):
                    best, best_j = m, j
            if best is not None:
                result.append(best)
                done[i] = done[best_j] = True
                n_merges += 1
            else:
                result.append(cur[i])
        cur = result
        if n_merges == 0:
            break
    return cur


def _room(ax):
    """A coloured table-top surface at z=0 (no longer a white floor), a slab
    edge below it for table thickness, and LOW translucent perimeter walls on
    the back + sides (front left open toward the camera). The walls are short
    (WALL_H) and faint so matplotlib's 3-D painter can no longer draw a tall
    back wall over the hidden target."""
    # table-top surface -- the floor is now coloured. Force it to sort behind
    # everything (very negative sort z) so matplotlib's 3-D painter cannot draw
    # this large flat polygon over the cubes/boxels that sit on it.
    top = [[(0, 0, 0), (W, 0, 0), (W, H, 0), (0, H, 0)]]
    surf = Poly3DCollection(top, facecolor=C_FLOOR, edgecolor="#cdbf9c", linewidths=0.8)
    surf.set_zorder(0)
    surf.set_sort_zpos(-1e5)
    ax.add_collection3d(surf)
    # slab edge (table thickness, below z=0)
    t, th = 0.3, 0.4
    rim = dict(fc=C_TABLE, ec="#b8ac8c", alpha=1.0, lw=0.5, zorder=0, shade=True)
    _box(ax, -t, -t, -th, W + 2 * t, t, th, **rim)   # front edge (y < 0)
    _box(ax, -t, H, -th, W + 2 * t, t, th, **rim)    # back edge  (y > H)
    _box(ax, -t, 0, -th, t, H, th, **rim)            # left edge  (x < 0)
    _box(ax, W, 0, -th, t, H, th, **rim)             # right edge (x > W)
    # LOW perimeter walls (back + sides); front (-y) left open toward the camera
    _box(ax, 0, H, 0, W, 0.06, WALL_H, fc=C_WALL, ec="#bcc4c9", alpha=0.18, lw=0.4, zorder=0)
    _box(ax, -0.06, 0, 0, 0.06, H, WALL_H, fc=C_WALL, ec="#bcc4c9", alpha=0.16, lw=0.4, zorder=0)
    _box(ax, W, 0, 0, 0.06, H, WALL_H, fc=C_WALL, ec="#bcc4c9", alpha=0.16, lw=0.4, zorder=0)


def _panel(ax, title):
    ax.set_box_aspect((W, H, ZVIEW * 1.25))
    ax.view_init(elev=28, azim=-55)
    ax.set_axis_off()
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_zlim(0, ZVIEW)
    ax.set_title(title, fontsize=26, color=C_TITLE, fontweight="bold", y=0.96)


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo, "thesis", "graphics", "boxelization_3d.png")

    content = _content_boxes_3d()
    free_split = octree_free(content, MIN_RES)
    free_merged = merge_3d(free_split)
    whole = [(np.array([0.0, 0.0, 0.0]), np.array([W, H, ZTOP]))]

    fig = plt.figure(figsize=(15, 9.5))
    fig.patch.set_facecolor("white")
    specs = [
        ("(a)", dict()),
        ("(b)", dict(objbox=True)),
        ("(c)", dict(objbox=True, occ=True, los=True)),
        ("(d)", dict(objbox=True, occ=True, free=whole)),
        ("(e)", dict(objbox=True, occ=True, free=free_split)),
        ("(f)", dict(objbox=True, occ=True, free=free_merged)),
    ]
    for i, (title, opt) in enumerate(specs, 1):
        ax = fig.add_subplot(2, 3, i, projection="3d")
        _room(ax)
        if opt.get("free") is not None:
            _free(ax, opt["free"])
        if opt.get("occ"):
            _occlusion(ax)
        _objects(ax)
        if opt.get("objbox"):
            _objboxels(ax)
        _hidden(ax)
        if opt.get("los"):
            _los(ax)
        _camera(ax)
        _panel(ax, title)

    legend = [
        Patch(facecolor=C_VIEW, edgecolor="none", label="Camera (viewpoint)"),
        Patch(facecolor=C_OBJ, edgecolor="none", label="Detected object"),
        Patch(facecolor=C_HIDE_F, edgecolor=C_HIDE_E, label="Hidden target"),
        Patch(facecolor="none", edgecolor=C_OBJBOX, linewidth=1.8, label="Object Boxel"),
        Patch(facecolor="#f5cba7", edgecolor=C_OCC_E, label="Occlusion Boxel"),
        Patch(facecolor="#d4efdf", edgecolor=C_FREE_E, label="Free Space Boxel"),
        Line2D([0], [0], linestyle=(0, (4, 3)), color=C_LOS, label="Line of sight"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=4, frameon=False,
               fontsize=24, markerscale=1.8, handlelength=2.4,
               columnspacing=2.2, handletextpad=0.8,
               bbox_to_anchor=(0.5, 0.01))
    fig.tight_layout(rect=(0, 0.11, 1, 0.99))
    fig.savefig(out, dpi=190, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}  ({len(free_split)} split -> {len(free_merged)} merged)")


if __name__ == "__main__":
    main()
