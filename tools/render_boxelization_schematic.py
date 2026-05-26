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

import matplotlib
matplotlib.use("Agg")  # headless: just save a PNG
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D

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
# occlusion Boxels (shadows) beyond each object from the viewpoint: (cx,cy,w,h)
OCCLUSIONS = [
    (4.5, 5.4, 1.7, 1.4),
    (7.5, 6.8, 1.7, 1.3),
    (4.4, 2.4, 1.8, 1.2),
    (8.3, 3.4, 1.5, 1.2),
]


def _rect_of(c):
    cx, cy, w, h = c[:4]
    return (cx - w / 2, cy - h / 2, w, h)


def _intersects(cell, rect):
    cx, cy, cw, ch = cell
    rx, ry, rw, rh = rect
    return not (cx + cw <= rx or rx + rw <= cx or cy + ch <= ry or ry + rh <= cy)


OCC_RECTS = [_rect_of(o) for o in OCCLUSIONS]
OBJ_RECTS = [_rect_of(o) for o in OBJECTS]
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
                               edgecolor=C_OCC_E, linewidth=1.4, alpha=0.9, zorder=3))


def _los(ax):
    for cx, cy, w, h, _ in OBJECTS:
        ax.add_patch(FancyArrowPatch(VIEW, (cx, cy), arrowstyle="-",
                                     linestyle=(0, (4, 3)), color=C_LOS,
                                     linewidth=1.0, zorder=2))


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
    _frame(a, "(a) Initial scene"); _view(a); _objects(a)

    # (b) object bounding
    _frame(b, "(b) Object-centric bounding"); _view(b); _objects(b); _objboxels(b)

    # (c) occlusion subdivision
    _frame(c, "(c) Occlusion-aware subdivision"); _view(c)
    _los(c); _occlusions(c); _objects(c, labels=False); _objboxels(c)

    # (d) free space: whole workspace one cell
    _frame(d, "(d) Free space: whole workspace")
    _free(d, [(0.0, 0.0, W, H)], lw=2.0)
    _occlusions(d); _objects(d, labels=False); _objboxels(d)

    # (e) free space: recursive split
    _frame(e, "(e) Free space: recursive split")
    _free(e, free_split); _occlusions(e); _objects(e, labels=False); _objboxels(e)

    # (f) free space: convex merge (final)
    _frame(f, "(f) Free space: convex merge")
    _free(f, free_merged); _occlusions(f); _objects(f, labels=False); _objboxels(f)

    # legend
    handles = [
        ("Robot viewpoint", C_VIEW, "s", None),
        ("Detected object", C_OBJ, "s", None),
        ("Object Boxel", "white", "s", C_OBJBOX),
        ("Occlusion Boxel", C_OCC_F, "s", C_OCC_E),
        ("Free Space Boxel", C_FREE_F, "s", C_FREE_E),
    ]
    proxies = [Line2D([0], [0], marker="s", linestyle="none", markersize=11,
                      markerfacecolor=fc, markeredgecolor=(ec or fc),
                      markeredgewidth=1.6) for _, fc, _, ec in handles]
    proxies.append(Line2D([0], [0], linestyle=(0, (4, 3)), color=C_LOS, linewidth=1.4))
    labels = [h[0] for h in handles] + ["Line of sight"]
    fig.legend(proxies, labels, loc="lower center", ncol=6, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, -0.01),
               handletextpad=0.5, columnspacing=1.6)

    fig.suptitle("Adaptive Semantic Discretization", fontsize=15,
                 fontweight="bold", color=C_TITLE, y=0.99)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}  ({len(free_split)} split cells -> {len(free_merged)} merged)")


if __name__ == "__main__":
    main()
