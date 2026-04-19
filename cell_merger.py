"""
Cell Merger for Convex Free Space Optimization.

This module merges adjacent free space boxels into larger convex regions,
reducing the total number of boxels while maintaining accurate space representation.
"""

import numpy as np
from typing import List, Tuple, Optional

from boxel_data import BoxelData, BoxelType


class CellMerger:
    """
    Merges adjacent free space cells into larger convex regions.

    Uses a greedy algorithm to iteratively merge pairs of adjacent boxels
    that share a common face and have compatible dimensions.
    """

    def __init__(self, tolerance: float = 1e-4):
        """
        Initialize the cell merger.

        Args:
            tolerance: Floating point tolerance for face-alignment checks.
                1e-4 m (0.1 mm) matches the shadow calculator's downstream
                tolerance; tighter values cause missed merges due to FP noise.
        """
        self.tolerance = tolerance

    def merge_free_space(self, free_boxels: List[BoxelData],
                         max_iterations: int = 100) -> List[BoxelData]:
        """
        Merge adjacent free space boxels into larger convex regions.

        Args:
            free_boxels: List of FREE_SPACE BoxelData to merge (typically the
                output of :class:`FreeSpaceGenerator`).  IDs may be empty.
            max_iterations: Maximum number of merge passes to perform.

        Returns:
            List of merged FREE_SPACE BoxelData (fewer, larger AABBs) with
            empty IDs — the caller registers them via the registry.
        """
        if not free_boxels:
            return []

        current_boxels = list(free_boxels)

        for iteration in range(max_iterations):
            merged_boxels, num_merges = self._merge_pass(current_boxels)

            if num_merges == 0:
                break

            current_boxels = merged_boxels
            print(f"  Merge iteration {iteration + 1}: {num_merges} merges, {len(current_boxels)} boxels remaining")

        # Return fresh BoxelData copies to discard any per-iteration state
        # (e.g. partially-mutated min/max from earlier passes that didn't
        # ultimately merge).  All survivors are FREE_SPACE.
        final_boxels = [
            BoxelData(
                boxel_type=BoxelType.FREE_SPACE,
                min_corner=b.min_corner.copy(),
                max_corner=b.max_corner.copy(),
            )
            for b in current_boxels
        ]

        print(f"  Merging complete: {len(free_boxels)} -> {len(final_boxels)} boxels")
        return final_boxels

    def _merge_pass(self, boxels: List[BoxelData]) -> Tuple[List[BoxelData], int]:
        """
        Perform one pass of merging adjacent boxels.

        Args:
            boxels: List of boxels to process

        Returns:
            Tuple of (merged boxels list, number of merges performed)
        """
        if len(boxels) <= 1:
            return boxels, 0

        merged = [False] * len(boxels)
        result: List[BoxelData] = []
        num_merges = 0

        for i in range(len(boxels)):
            if merged[i]:
                continue

            best_merge: Optional[BoxelData] = None
            best_j = -1

            for j in range(i + 1, len(boxels)):
                if merged[j]:
                    continue

                merged_boxel = self._try_merge(boxels[i], boxels[j])
                if merged_boxel is not None:
                    # Prefer merges that create the most cubic result
                    # (higher min/max extent ratio).
                    if best_merge is None:
                        best_merge = merged_boxel
                        best_j = j
                    elif self._merge_quality(merged_boxel) > self._merge_quality(best_merge):
                        best_merge = merged_boxel
                        best_j = j

            if best_merge is not None:
                result.append(best_merge)
                merged[i] = True
                merged[best_j] = True
                num_merges += 1
            else:
                result.append(boxels[i])

        return result, num_merges

    def _try_merge(self, boxel_a: BoxelData,
                   boxel_b: BoxelData) -> Optional[BoxelData]:
        """
        Try to merge two boxels if they share a common face.

        Two boxels can be merged if:
        1. They share a common face (adjacent with touching boundaries)
        2. The shared face has the same dimensions
        3. They are aligned on the non-merge axes

        Args:
            boxel_a: First boxel
            boxel_b: Second boxel

        Returns:
            Merged BoxelData if merge is possible, None otherwise.
        """
        a_min, a_max = boxel_a.min_corner, boxel_a.max_corner
        b_min, b_max = boxel_b.min_corner, boxel_b.max_corner

        for axis in range(3):
            other_axes = [i for i in range(3) if i != axis]

            aligned = True
            for oa in other_axes:
                if not (self._approx_equal(a_min[oa], b_min[oa]) and
                        self._approx_equal(a_max[oa], b_max[oa])):
                    aligned = False
                    break

            if not aligned:
                continue

            # Adjacent along this axis: a then b
            if self._approx_equal(a_max[axis], b_min[axis]):
                return self._create_merged_boxel(a_min.copy(), b_max.copy())

            # Adjacent along this axis: b then a
            if self._approx_equal(b_max[axis], a_min[axis]):
                return self._create_merged_boxel(b_min.copy(), a_max.copy())

        return None

    def _approx_equal(self, a: float, b: float) -> bool:
        """Check if two floats are approximately equal."""
        return abs(a - b) < self.tolerance

    def _create_merged_boxel(self, min_pt: np.ndarray,
                             max_pt: np.ndarray) -> BoxelData:
        """Create a merged FREE_SPACE BoxelData from min/max bounds."""
        return BoxelData(
            boxel_type=BoxelType.FREE_SPACE,
            min_corner=min_pt,
            max_corner=max_pt,
        )

    def _merge_quality(self, boxel: BoxelData) -> float:
        """
        Calculate merge quality score (higher is better).

        Prefers more cubic shapes over elongated ones.
        """
        ext = boxel.extent
        min_ext = float(np.min(ext))
        max_ext = float(np.max(ext))
        if max_ext < self.tolerance:
            return 0.0
        return min_ext / max_ext


def merge_free_space_cells(free_boxels: List[BoxelData], tolerance: float = 1e-4,
                           max_iterations: int = 100) -> List[BoxelData]:
    """
    Convenience function to merge free space cells.

    Args:
        free_boxels: List of FREE_SPACE BoxelData to merge.
        tolerance: Floating point tolerance for dimension comparisons.
        max_iterations: Maximum number of merge passes.

    Returns:
        List of merged FREE_SPACE BoxelData (with empty IDs).
    """
    merger = CellMerger(tolerance=tolerance)
    return merger.merge_free_space(free_boxels, max_iterations=max_iterations)
