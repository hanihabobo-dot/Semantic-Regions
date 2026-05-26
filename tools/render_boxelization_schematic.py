#!/usr/bin/env python3
"""
render_boxelization_schematic.py -- regenerate the methods.tex discretization
schematic (fig:boxelization) as a clean 2-D figure, now INCLUDING the three
free-space generation stages that the old hand-made Boxelization.png skipped
(it jumped straight to the final partition).

Six panels, left-to-right, top-to-bottom:
    (a) Initial scene           -- robot viewpoint + detected objects
    (b) Object-centric bounding -- one object Boxel per detected object
    (c) Occlusion subdivision   -- shadow Boxels beyond each object + line of sight
    (d) Free space: whole workspace as a single cell
    (e) Free space: recursive quad-tree split (cells overlapping content subdivide)
    (f) Free space: greedy convex merge -> the final partition

Pure 2-D matplotlib (no PyBullet); deterministic; headless (Agg). Writes a NEW
file, thesis/graphics/boxelization_stages.png -- it does NOT overwrite the old
Boxelization.png (kept for history / regenerability).

RUN (WSL venv, repo root):
    source wsl_env/bin/activate
    python3 tools/render_boxelization_schematic.py
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless: just save a PNG
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

# Camera emoji for the robot viewpoint. matplotlib/Agg renders it as a clean
# monochrome glyph from Segoe UI Emoji (Windows). If the font is unavailable
# (e.g. a bare WSL env), EMOJI_PROP stays None and we fall back to a dark square.
CAMERA = "\U0001F4F7"  # camera emoji


def _emoji_prop():
    for path in (r"C:\Windows\Fonts\seguiemj.ttf",
                 "/mnt/c/Windows/Fonts/seguiemj.ttf"):
        if os.path.exists(path):
            try:
                return _fm.FontProperties(fname=path)
            except Exception:
                pass
    return None


EMOJI_PROP = _emoji_prop()

# ---------------------------------------------------------------- palette
C_VIEW   = "#2c3e50"   # robot viewpoint
C_OBJ    = "#e74c3c"   # detected objects
C_OBJBOX = "#3498db"   # object Boxel outline
C_OCC_F  = "#f8d7b0"   # occlusion Boxel fill
C_OCC_E  = "#e67e22"   # occlusion Boxel edge
C_FREE_F = "#abebc6"   # free-space Boxel fill
C_FREE_E = "#27ae60"   # free-space Boxel edge
C_LOS    = "#95a5a6"   # line of sight
C_PANEL  = "#fbfcfd"   # panel background
C_PANELE = "#d5dbdb"   # panel border
C_TITLE  = "#34495e"
C_HIDE_F = "#4dd0e1"   # hidden target fill (cyan)
C_HIDE_E = "#00838f"   # hidden target edge

# ---------------------------------------------------------------- scene (units)
W, H = 10.0, 8.0
VIEW = (0.7, 1.0)

# objects: (cx, cy, w, h, label)
OBJECTS = [
    (3.5, 4.5, 1.0, 0.8, "obj1"),
    (6.4, 5.9, 1.0, 1.0, "obj2"),
    (3.3, 1.8, 1.0, 0.7, "obj3"),
    (7.3, 2.8, 1.0, 0.8, "obj4"),
]
# the workspace = the "table" the occlusion rays terminate on (shadow_calculator
# clamps every ray hit to the table bounds).
BOUNDS = (0.0, 0.0, W, H)
# the hidden target: sits inside obj1's occlusion (in its shadow), so the camera
# cannot see it -- the robot must reason about the shadow to find it. (cx, cy, s)
HIDDEN = (4.8, 5.6, 0.6)


def _rect_of(c):
    cx, cy, w, h = c[:4]
    return (cx - w / 2, cy - h / 2, w, h)


def _intersects(cell, rect):
    cx, cy, cw, ch = cell
    rx, ry, rw, rh = rect
    return not (cx + cw <= rx or rx + rw <= cx or cy + ch <= ry or ry + rh <= cy)


OBJ_RECTS = [_rect_of(o) for o in OBJECTS]


# ----------------------------------------------- occlusion (shadow) geometry
# Faithful 2-D port of shadow_calculator.ShadowCalculator.calculate_shadow_boxel
# (top-down view): from the camera, rays graze each object's far ("back")
# corners and continue to the workspace boundary; the shadow Boxel is the AABB
# of {object box U ray-hit points} with its near face clipped to the object's
# back face, then split around any OTHER object it sweeps over (the slab
# directly behind that object is dropped as it is occluded twice over). This
# replaces the hand-placed rectangles the schematic used before.
def _ray_box_exit(origin, direction, bounds):
    """Smallest t>0 at which origin + t*direction leaves the bounds box."""
    x0, y0, x1, y1 = bounds
    ts = []
    if direction[0] > 1e-12:
        ts.append((x1 - origin[0]) / direction[0])
    elif direction[0] < -1e-12:
        ts.append((x0 - origin[0]) / direction[0])
    if direction[1] > 1e-12:
        ts.append((y1 - origin[1]) / direction[1])
    elif direction[1] < -1e-12:
        ts.append((y0 - origin[1]) / direction[1])
    ts = [t for t in ts if t > 0]
    return min(ts) if ts else 0.0


def _corners(cx, cy, w, h):
    return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2],
                     [cx - w / 2, cy + h / 2], [cx + w / 2, cy + h / 2]])


def _swept_shadow(obj):
    """One object's swept shadow AABB (x, y, w, h) plus its shadow direction,
    before any obstacle splitting."""
    cx, cy, w, h, _ = obj
    center = np.array([cx, cy], float)
    view = np.array(VIEW, float)
    cam_dir = center - view
    cam_dir /= np.linalg.norm(cam_dir)
    corners = _corners(cx, cy, w, h)
    back = [c for c in corners if np.dot(c - center, cam_dir) > 0] or list(corners)
    hits = []
    for corner in back:
        d = corner - view
        d /= np.linalg.norm(d)
        hit = corner + d * _ray_box_exit(corner, d, BOUNDS)
        hit[0] = min(max(hit[0], BOUNDS[0]), BOUNDS[2])
        hit[1] = min(max(hit[1], BOUNDS[1]), BOUNDS[3])
        hits.append(hit)
    hits = np.array(hits)
    o_min = center - np.array([w / 2, h / 2])
    o_max = center + np.array([w / 2, h / 2])
    s_min = np.minimum(o_min, hits.min(axis=0))
    s_max = np.maximum(o_max, hits.max(axis=0))
    shadow_dir = hits.mean(axis=0) - center
    dom = int(np.argmax(np.abs(shadow_dir)))
    if shadow_dir[dom] > 0:
        s_min[dom] = max(s_min[dom], o_max[dom])
    else:
        s_max[dom] = min(s_max[dom], o_min[dom])
    s_min[0] = max(s_min[0], BOUNDS[0]); s_min[1] = max(s_min[1], BOUNDS[1])
    s_max[0] = min(s_max[0], BOUNDS[2]); s_max[1] = min(s_max[1], BOUNDS[3])
    return (s_min[0], s_min[1], s_max[0] - s_min[0], s_max[1] - s_min[1]), shadow_dir


def _subtract(shadow, obstacle, direction):
    """2-D port of _subtract_aabb + _is_downstream: carve `obstacle` out of
    `shadow`, keep the before/around fragments, drop the slab behind it."""
    s_min = [shadow[0], shadow[1]]
    s_max = [shadow[0] + shadow[2], shadow[1] + shadow[3]]
    o_min = [obstacle[0], obstacle[1]]
    o_max = [obstacle[0] + obstacle[2], obstacle[1] + obstacle[3]]
    if (s_min[0] >= o_max[0] or s_max[0] <= o_min[0] or
            s_min[1] >= o_max[1] or s_max[1] <= o_min[1]):
        return [shadow]
    frags = []
    if s_min[0] < o_min[0]:
        frags.append((s_min[:], [o_min[0], s_max[1]])); s_min[0] = o_min[0]
    if s_max[0] > o_max[0]:
        frags.append(([o_max[0], s_min[1]], s_max[:])); s_max[0] = o_max[0]
    if s_min[1] < o_min[1]:
        frags.append((s_min[:], [s_max[0], o_min[1]])); s_min[1] = o_min[1]
    if s_max[1] > o_max[1]:
        frags.append(([s_min[0], o_max[1]], s_max[:])); s_max[1] = o_max[1]
    dom = 0 if abs(direction[0]) >= abs(direction[1]) else 1
    out = []
    for mn, mx in frags:
        if mx[0] - mn[0] <= 1e-6 or mx[1] - mn[1] <= 1e-6:
            continue
        if direction[dom] > 0 and mn[dom] >= o_max[dom] - 1e-4:
            continue
        if direction[dom] <= 0 and mx[dom] <= o_min[dom] + 1e-4:
            continue
        out.append((mn[0], mn[1], mx[0] - mn[0], mx[1] - mn[1]))
    return out


def _center_inside(rect, obj):
    rx, ry, rw, rh = rect
    return rx <= obj[0] <= rx + rw and ry <= obj[1] <= ry + rh


def compute_shadows(objects=None):
    """All objects' shadow Boxels, swept from the camera then split around the
    other objects (the obstacle pass of shadow_calculator). An object only
    splits a shadow when its centre actually lies inside that shadow's swept
    AABB -- the obstacle pass is meant to carve genuine occluders, not objects
    the axis-aligned AABB merely grazes at a corner.

    `objects` defaults to the module scene; the 3-D figure passes its own
    (smaller) object list so it can reuse this exact geometry."""
    objs = OBJECTS if objects is None else objects
    obj_rects = [_rect_of(o) for o in objs]
    shadows = []
    for i, obj in enumerate(objs):
        rect, shadow_dir = _swept_shadow(obj)
        active = [rect]
        for j in range(len(objs)):
            if j == i or not _center_inside(rect, objs[j]):
                continue
            nxt = []
            for sh in active:
                nxt.extend(_subtract(sh, obj_rects[j], shadow_dir))
            active = nxt
        shadows.extend(active)
    return shadows


def silhouette_rays(obj):
    """The two camera rays grazing the object's silhouette, continued past it to
    the workspace boundary -- the line of sight drawn in panel (c)."""
    cx, cy, w, h, _ = obj
    view = np.array(VIEW, float)
    corners = _corners(cx, cy, w, h)
    angles = [np.arctan2(c[1] - view[1], c[0] - view[0]) for c in corners]
    rays = []
    for idx in (int(np.argmin(angles)), int(np.argmax(angles))):
        d = corners[idx] - view
        d /= np.linalg.norm(d)
        end = view + d * _ray_box_exit(view, d, BOUNDS)
        rays.append(((view[0], view[1]), (end[0], end[1])))
    return rays


OCC_RECTS = compute_shadows()
CONTENT = OCC_RECTS + OBJ_RECTS


def quadtree_free(min_size=0.85):
    """Recursively split the workspace; keep cells clear of all content as free."""
    free, content_cells = [], CONTENT
    stack = [(0.0, 0.0, W, H)]
    while stack:
        cell = stack.pop()
        cx, cy, cw, ch = cell
        hit = any(_intersects(cell, r) for r in content_cells)
        if not hit:
            free.append(cell)                      # fully clear -> free Boxel
        elif min(cw, ch) <= min_size:
            # leaf still touching content: keep only if its centre is clear
            centre = (cx + cw / 2, cy + ch / 2)
            inside = any(r[0] <= centre[0] <= r[0] + r[2] and
                         r[1] <= centre[1] <= r[1] + r[3] for r in content_cells)
            if not inside:
                free.append(cell)
        else:
            hw, hh = cw / 2, ch / 2
            stack += [(cx, cy, hw, hh), (cx + hw, cy, hw, hh),
                      (cx, cy + hh, hw, hh), (cx + hw, cy + hh, hw, hh)]
    return free


def merge_free(cells):
    """Greedy convex merge: combine cells sharing an exactly aligned full edge,
    rows first then columns. Schematic approximation of cell_merger."""
    cells = list(cells)
    changed = True
    while changed:
        changed = False
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                a, b = cells[i], cells[j]
                # horizontal neighbour, equal y/height
                if (abs(a[1] - b[1]) < 1e-6 and abs(a[3] - b[3]) < 1e-6 and
                        (abs(a[0] + a[2] - b[0]) < 1e-6 or abs(b[0] + b[2] - a[0]) < 1e-6)):
                    x0 = min(a[0], b[0])
                    cells[i] = (x0, a[1], a[2] + b[2], a[3]); del cells[j]
                    changed = True; break
                # vertical neighbour, equal x/width
                if (abs(a[0] - b[0]) < 1e-6 and abs(a[2] - b[2]) < 1e-6 and
                        (abs(a[1] + a[3] - b[1]) < 1e-6 or abs(b[1] + b[3] - a[1]) < 1e-6)):
                    y0 = min(a[1], b[1])
                    cells[i] = (a[0], y0, a[2], a[3] + b[3]); del cells[j]
                    changed = True; break
            if changed:
                break
    return cells


# ---------------------------------------------------------------- drawing
def _frame(ax, title):
    ax.set_xlim(-0.4, W + 0.4)
    ax.set_ylim(-0.4, H + 0.4)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.add_patch(FancyBboxPatch((-0.4, -0.4), W + 0.8, H + 0.8,
                                boxstyle="round,pad=0.02,rounding_size=0.5",
                                linewidth=1.2, edgecolor=C_PANELE,
                                facecolor=C_PANEL, mutation_aspect=1.0, zorder=0))
    ax.set_title(title, fontsize=11, color=C_TITLE, fontweight="bold", pad=7)


def _view(ax):
    x, y = VIEW
    if EMOJI_PROP is not None:
        ax.text(x, y, CAMERA, fontproperties=EMOJI_PROP, fontsize=20,
                ha="center", va="center", zorder=8)
    else:
        ax.add_patch(Rectangle((x - 0.28, y - 0.28), 0.56, 0.56,
                               facecolor=C_VIEW, edgecolor="none", zorder=6))


def _objects(ax, labels=True):
    for cx, cy, w, h, lab in OBJECTS:
        ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h,
                               facecolor=C_OBJ, edgecolor="none", zorder=5))
        if labels:
            ax.text(cx, cy, lab, color="white", ha="center", va="center",
                    fontsize=7.5, fontweight="bold", zorder=7)


def _objboxels(ax):
    for cx, cy, w, h, _ in OBJECTS:
        ax.add_patch(Rectangle((cx - w / 2 - 0.16, cy - h / 2 - 0.16),
                               w + 0.32, h + 0.32, fill=False,
                               edgecolor=C_OBJBOX, linewidth=1.8, zorder=4))


def _occlusions(ax):
    for rx, ry, rw, rh in OCC_RECTS:
        ax.add_patch(Rectangle((rx, ry), rw, rh, facecolor=C_OCC_F,
                               edgecolor=C_OCC_E, linewidth=1.2, alpha=0.55, zorder=3))


def _los(ax):
    for obj in OBJECTS:
        for p0, p1 in silhouette_rays(obj):
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], linestyle=(0, (4, 3)),
                    color=C_LOS, linewidth=1.0, zorder=2)


def _hidden(ax):
    cx, cy, s = HIDDEN
    ax.add_patch(Rectangle((cx - s / 2, cy - s / 2), s, s, facecolor=C_HIDE_F,
                           edgecolor=C_HIDE_E, linewidth=1.6, linestyle="--",
                           alpha=0.7, zorder=4.5))
    ax.text(cx, cy, "?", color="white", ha="center", va="center",
            fontsize=10, fontweight="bold", zorder=5)


def _free(ax, cells, lw=1.0):
    for rx, ry, rw, rh in cells:
        ax.add_patch(Rectangle((rx, ry), rw, rh, facecolor=C_FREE_F,
                               edgecolor=C_FREE_E, linewidth=lw, alpha=0.55, zorder=1))


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo, "thesis", "graphics", "boxelization_stages.png")

    free_split = quadtree_free()
    free_merged = merge_free(free_split)

    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.6))
    fig.patch.set_facecolor("white")

    a, b, c, d, e, f = axes.flat

    # (a) initial scene
    _frame(a, "(a) Initial scene"); _view(a); _objects(a); _hidden(a)

    # (b) object bounding
    _frame(b, "(b) Object-centric bounding"); _view(b); _objects(b); _objboxels(b)
    _hidden(b)

    # (c) occlusion subdivision
    _frame(c, "(c) Occlusion-aware subdivision"); _view(c)
    _los(c); _occlusions(c); _objects(c, labels=False); _objboxels(c); _hidden(c)

    # (d) free space: whole workspace one cell
    _frame(d, "(d) Free space: whole workspace")
    _free(d, [(0.0, 0.0, W, H)], lw=2.0)
    _occlusions(d); _objects(d, labels=False); _objboxels(d); _hidden(d)

    # (e) free space: recursive split
    _frame(e, "(e) Free space: recursive split")
    _free(e, free_split); _occlusions(e); _objects(e, labels=False); _objboxels(e); _hidden(e)

    # (f) free space: convex merge (final)
    _frame(f, "(f) Free space: convex merge")
    _free(f, free_merged); _occlusions(f); _objects(f, labels=False); _objboxels(f); _hidden(f)

    # legend
    handles = [
        ("Robot viewpoint", C_VIEW, "s", None),
        ("Detected object", C_OBJ, "s", None),
        ("Hidden target", C_HIDE_F, "s", C_HIDE_E),
        ("Object Boxel", "white", "s", C_OBJBOX),
        ("Occlusion Boxel", C_OCC_F, "s", C_OCC_E),
        ("Free Space Boxel", C_FREE_F, "s", C_FREE_E),
    ]
    proxies = [Line2D([0], [0], marker="s", linestyle="none", markersize=11,
                      markerfacecolor=fc, markeredgecolor=(ec or fc),
                      markeredgewidth=1.6) for _, fc, _, ec in handles]
    proxies.append(Line2D([0], [0], linestyle=(0, (4, 3)), color=C_LOS, linewidth=1.4))
    labels = [h[0] for h in handles] + ["Line of sight"]
    fig.legend(proxies, labels, loc="lower center", ncol=7, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, -0.01),
               handletextpad=0.5, columnspacing=1.4)

    fig.suptitle("Adaptive Semantic Discretization", fontsize=15,
                 fontweight="bold", color=C_TITLE, y=0.99)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}  ({len(free_split)} split cells -> {len(free_merged)} merged)")


if __name__ == "__main__":
    main()
