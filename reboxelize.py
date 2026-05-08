"""
Free-space re-boxelization helper.

Extracted from test_full_pipeline.py during the audit #26 refactor.
Re-runs the octree + merge pipeline on the current OBJECT/SHADOW set
and diffs against the registry's existing FREE_SPACE boxels so only
the changed cells are mutated and re-drawn.
"""

from typing import List, Set, Tuple

import numpy as np

from boxel_data import BoxelData, BoxelRegistry, BoxelType
from cell_merger import merge_free_space_cells


def reboxelize_free_space(registry: BoxelRegistry, env, boxel_centers: dict,
                          viz, show_free: bool) -> Tuple[List[str], Set[str]]:
    """
    Re-run the full octree + merge pipeline and diff against the current
    registry's free-space boxels.  Only changed boxels are removed/added.

    Call this after any mutation that changes which regions are free
    (object placement, shadow removal, new objects discovered, etc.).

    Args:
        registry: BoxelRegistry — will be mutated in place.
        env: BoxelTestEnv — for ``generate_free_space``.
        boxel_centers: Dict[str, np.ndarray] — updated in place.
        viz: BoxelVisualizer or None.
        show_free: Whether to draw free-space boxels.

    Returns:
        Tuple[List[str], Set[str]]: (new_ids, old_removed_ids).
    """
    old_free = {b.id: b for b in registry.get_free_space_boxels()}

    # Pass OBJECT + SHADOW BoxelData straight into the octree generator —
    # post-#35 it consumes BoxelData directly (no Boxel conversion).
    known_obstacles = [
        bd for bd in registry.boxels.values()
        if bd.boxel_type in (BoxelType.OBJECT, BoxelType.SHADOW)
    ]

    fresh_cells = env.generate_free_space(known_obstacles, visualize=False)
    # audit #10 — under the uniform baseline the lattice is strict and
    # static; merging adjacent uniform cubes would defeat the property.
    # Mirror the same gate used in test_full_pipeline.py phase 2.
    merged = (fresh_cells if env.use_uniform_grid
              else merge_free_space_cells(fresh_cells))

    # 1e-4 m (0.1 mm) AABB-equality tolerance — same FP-noise budget as
    # CellMerger.tolerance.  Anything tighter would falsely classify
    # numerically-equivalent boxels as new (forcing pointless removal +
    # re-add cycles); anything looser risks merging boxels that should
    # actually be split.
    _tol = 1e-4
    old_matched: Set[str] = set()
    new_unmatched: List[BoxelData] = []
    for m in merged:
        found = False
        for oid, od in old_free.items():
            if oid in old_matched:
                continue
            if (np.allclose(m.min_corner, od.min_corner, atol=_tol) and
                    np.allclose(m.max_corner, od.max_corner, atol=_tol)):
                old_matched.add(oid)
                found = True
                break
        if not found:
            new_unmatched.append(m)
    old_removed = set(old_free) - old_matched

    for oid in old_removed:
        registry.remove_boxel(oid)
        boxel_centers.pop(oid, None)

    env.annotate_free_space_surface(new_unmatched)
    new_ids: List[str] = []
    for frag in new_unmatched:
        fid = registry.add_boxel(frag)
        new_ids.append(fid)
        boxel_centers[fid] = frag.center

    total_free = len(registry.get_free_space_boxels())
    print(f"    Re-boxelize: {len(old_removed)} removed, "
          f"{len(new_ids)} new, "
          f"{len(old_matched)} unchanged "
          f"({total_free} free total)")

    registry.mark_clean()

    if viz is not None:
        for oid in old_removed:
            viz.remove_boxel_viz(oid)
        if show_free:
            for nid in new_ids:
                bd = registry.get_boxel(nid)
                if bd is not None:
                    viz.draw_boxel_data(bd)

    return new_ids, old_removed
