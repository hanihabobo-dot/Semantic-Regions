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
    (e) free space: recursive quad-tree split
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

# reuse layout + free-space algorithm from the 2-D generator
from render_boxelization_schematic import (
    OBJECTS, OCC_RECTS, VIEW, W, H, HIDDEN,
    quadtree_free, merge_free,
    C_VIEW, C_OBJ, C_OBJBOX, C_OCC_E, C_FREE_E, C_TITLE, C_LOS,
    C_HIDE_F, C_HIDE_E,
)

# camera body position (nudged in from the corner so the lens has room)
CAM = (VIEW[0] + 0.4, VIEW[1] + 0.6)

ZTOP = 2.6           # room / ceiling height
OBJ_H = 1.0          # object cube height
OCC_H = 2.0          # occlusion (shadow) Boxel height
FREE_H = ZTOP        # free-space Boxels span the full room height (>= the
                     # object/occlusion Boxels they sit among)
C_WALL = "#dfe3e6"   # room walls
C_TABLE = "#e5e8e8"  # table base

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
    """A small 3-D camera model: dark body box + viewfinder bump + a protruding
    lens cylinder aimed at the scene centre. Composed from polygons because
    matplotlib has no camera primitive."""
    cx, cy = CAM
    bw, bd, bh, bz = 1.1, 0.7, 0.7, 0.15
    _box(ax, cx - bw / 2, cy - bd / 2, bz, bw, bd, bh, fc=C_VIEW, ec="#1b2631",
         alpha=1.0, lw=0.4, zorder=8, shade=True)                       # body
    _box(ax, cx - 0.18, cy - 0.15, bz + bh, 0.36, 0.3, 0.18, fc=C_VIEW,
         ec="#1b2631", alpha=1.0, lw=0.4, zorder=8, shade=True)         # viewfinder
    axis = np.array([5.0 - cx, 4.0 - cy, 0.0]); axis /= np.linalg.norm(axis)
    base = np.array([cx, cy, bz + bh / 2]) + axis * (bd / 2)
    _cylinder(ax, base, axis, 0.26, 0.5, fc="#566573", ec="#1b2631",
              alpha=1.0, zorder=9)                                      # lens barrel
    _cylinder(ax, base + axis * 0.5, axis, 0.20, 0.03, fc="#aed6f1",
              ec="#5dade2", alpha=1.0, zorder=10)                       # lens glass


def _hidden(ax):
    cx, cy, s = HIDDEN
    _box(ax, cx - s / 2, cy - s / 2, 0, s, s, OBJ_H * 0.8, fc=C_HIDE_F,
         ec=C_HIDE_E, alpha=0.45, lw=1.2, zorder=5, shade=True)


def _objects(ax):
    for cx, cy, w, h, _ in OBJECTS:
        _box(ax, cx - w / 2, cy - h / 2, 0, w, h, OBJ_H,
             fc=C_OBJ, ec="#7b241c", alpha=1.0, lw=0.5, zorder=6, shade=True)


def _objboxels(ax):
    for cx, cy, w, h, _ in OBJECTS:
        _box(ax, cx - w / 2 - 0.16, cy - h / 2 - 0.16, -0.05,
             w + 0.32, h + 0.32, OBJ_H + 0.32, fc="none", ec=C_OBJBOX,
             alpha=1.0, lw=1.6, zorder=7, fill=False)


def _occlusion(ax):
    for rx, ry, rw, rh in OCC_RECTS:
        _box(ax, rx, ry, 0, rw, rh, OCC_H, fc="#f5cba7", ec=C_OCC_E,
             alpha=0.16, lw=1.3, zorder=3)


def _los(ax):
    vx, vy = CAM
    segs = [[(vx, vy, 0.5), (cx, cy, OBJ_H / 2)] for cx, cy, *_ in OBJECTS]
    ax.add_collection3d(Line3DCollection(segs, colors=C_LOS, linewidths=1.0,
                                         linestyles=(0, (4, 3)), zorder=2))


def _free(ax, cells):
    for rx, ry, rw, rh in cells:
        _box(ax, rx, ry, 0, rw, rh, FREE_H, fc="#a9dfbf", ec=C_FREE_E,
             alpha=0.09, lw=0.9, zorder=1)


def _room(ax):
    """Table EDGE only (a rim frame around the workspace perimeter, OUTSIDE the
    green tile footprint so nothing shows through the translucent green) plus
    back and side walls. NO interior table surface and NO front wall."""
    t, th = 0.3, 0.4  # rim thickness, rim height (top at z=0)
    rim = dict(fc=C_TABLE, ec="#b3b6b7", alpha=1.0, lw=0.5, zorder=0, shade=True)
    _box(ax, -t, -t, -th, W + 2 * t, t, th, **rim)   # front edge (y < 0)
    _box(ax, -t, H, -th, W + 2 * t, t, th, **rim)    # back edge  (y > H)
    _box(ax, -t, 0, -th, t, H, th, **rim)            # left edge  (x < 0)
    _box(ax, W, 0, -th, t, H, th, **rim)             # right edge (x > W)
    # back wall (far, +y) and the two side walls (x=0, x=W); front (-y) left open
    _box(ax, 0, H, 0, W, 0.06, ZTOP, fc=C_WALL, ec="#c4c9cc", alpha=0.35, lw=0.5, zorder=0)
    _box(ax, -0.06, 0, 0, 0.06, H, ZTOP, fc=C_WALL, ec="#c4c9cc", alpha=0.30, lw=0.5, zorder=0)
    _box(ax, W, 0, 0, 0.06, H, ZTOP, fc=C_WALL, ec="#c4c9cc", alpha=0.30, lw=0.5, zorder=0)


def _panel(ax, title):
    ax.set_box_aspect((W, H, ZTOP * 1.5))
    ax.view_init(elev=28, azim=-55)
    ax.set_axis_off()
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_zlim(0, ZTOP)
    ax.set_title(title, fontsize=11.5, color=C_TITLE, fontweight="bold", y=0.96)


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo, "thesis", "graphics", "boxelization_3d.png")

    free_split = quadtree_free()
    free_merged = merge_free(free_split)
    whole = [(0.0, 0.0, W, H)]

    fig = plt.figure(figsize=(15, 9.5))
    fig.patch.set_facecolor("white")
    specs = [
        ("(a) Initial scene",               dict()),
        ("(b) Object-centric bounding",     dict(objbox=True)),
        ("(c) Occlusion-aware subdivision", dict(objbox=True, occ=True, los=True)),
        ("(d) Free space: whole workspace", dict(objbox=True, occ=True, free=whole)),
        ("(e) Free space: recursive split", dict(objbox=True, occ=True, free=free_split)),
        ("(f) Free space: convex merge",    dict(objbox=True, occ=True, free=free_merged)),
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
    fig.legend(handles=legend, loc="lower center", ncol=7, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, 0.015))
    fig.suptitle("Adaptive Semantic Discretization (3-D)", fontsize=16,
                 fontweight="bold", color=C_TITLE, y=0.99)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out, dpi=190, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}  ({len(free_split)} split -> {len(free_merged)} merged)")


if __name__ == "__main__":
    main()
