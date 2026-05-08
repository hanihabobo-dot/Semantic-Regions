"""
Uniform-grid free-space discretization (audit #10 baseline).

Drop-in replacement for ``FreeSpaceGenerator`` (free_space.py) that produces
a strict, static, uniform 3D lattice of FREE_SPACE BoxelData over the
workspace volume.  Cell positions are precomputed once at construction and
never change; ``generate()`` only filters the lattice against the current
OBJECT + SHADOW set.

This is the thesis baseline against which the semantic (octree + merge)
free-space pipeline is compared.  TAMPURA-style: voxel labels live in
Python (registry mutation + ``_build_init`` re-emit per planner.plan()
call); no PDDL domain changes are required.

The cell-size hyperparameter (default 0.05 m = 5 cm) is sized to roughly
one cube footprint per cell — fine enough that ``boxel_fits`` admits
single-cube placements, coarse enough that the cell count stays bounded.
"""

import numpy as np
from typing import List

from boxel_data import BoxelData, BoxelType


class UniformGridGenerator:
    """
    Produce FREE_SPACE BoxelData on a strict static uniform 3D lattice.

    The lattice is computed once in ``__init__`` from the workspace bounds
    and cell size.  Subsequent ``generate()`` calls walk the same lattice
    and emit only those cells that don't overlap any known OBJECT/SHADOW
    AABB — i.e., the topology is fixed and only the per-cell label flips
    as the world is sensed and manipulated.
    """

    def __init__(self, table_surface_height: float, cell_size: float = 0.05,
                 table_x_range: tuple = (0.0, 1.0),
                 table_y_range: tuple = (-0.5, 0.5)):
        """
        Initialize the uniform grid.

        Args:
            table_surface_height: Z height of the table surface (lattice z-min).
            cell_size: Edge length of each cubic cell, in metres.
                Default 0.05 m matches roughly one cube footprint per cell.
            table_x_range: (min, max) X bounds of the lattice.
            table_y_range: (min, max) Y bounds of the lattice.

        Workspace volume matches FreeSpaceGenerator (free_space.py:47-48):
        ``[x_range × y_range × (table_z, table_z + 0.5)]`` so the two
        generators cover the same physical region — only the cell shape
        and count differ.
        """
        self.table_surface_height = table_surface_height
        self.cell_size = float(cell_size)
        self.ws_min = np.array(
            [table_x_range[0], table_y_range[0], table_surface_height]
        )
        self.ws_max = np.array(
            [table_x_range[1], table_y_range[1], table_surface_height + 0.5]
        )
        self._cell_extent = np.array(
            [self.cell_size / 2.0,
             self.cell_size / 2.0,
             self.cell_size / 2.0]
        )
        # The static lattice — N×3 array of cell centres covering the
        # workspace.  Built once and reused by every generate() call;
        # this is the "strict static" property of the uniform baseline.
        self._cell_centres = self._build_lattice()

    def _build_lattice(self) -> np.ndarray:
        """Return an N×3 array of cell centres covering the workspace.

        Uses ``floor`` with a 1e-9 epsilon so FP imprecision in the
        division (e.g. 0.6 / 0.05 == 11.9999... which floors to 11
        instead of the intended 12) does not silently drop a full row
        of cells; a thin sliver at the upper edges may still go
        unmodelled when cell_size doesn't divide the workspace evenly,
        same as the octree generator's leaf-depth boundary.
        """
        cs = self.cell_size
        eps = 1e-9
        nx = max(int(np.floor((self.ws_max[0] - self.ws_min[0]) / cs + eps)), 1)
        ny = max(int(np.floor((self.ws_max[1] - self.ws_min[1]) / cs + eps)), 1)
        nz = max(int(np.floor((self.ws_max[2] - self.ws_min[2]) / cs + eps)), 1)
        x_centres = self.ws_min[0] + cs / 2.0 + np.arange(nx) * cs
        y_centres = self.ws_min[1] + cs / 2.0 + np.arange(ny) * cs
        z_centres = self.ws_min[2] + cs / 2.0 + np.arange(nz) * cs
        cx, cy, cz = np.meshgrid(
            x_centres, y_centres, z_centres, indexing='ij'
        )
        return np.stack([cx.ravel(), cy.ravel(), cz.ravel()], axis=1)

    def generate(self, known_boxels: List[BoxelData],
                 visualize: bool = False) -> List[BoxelData]:
        """
        Emit FREE_SPACE BoxelData for lattice cells that don't overlap any
        known OBJECT/SHADOW AABB.

        Args:
            known_boxels: List of OBJECT + SHADOW BoxelData (the obstacles
                that mask cells out of the free set).
            visualize: Accepted for API parity with FreeSpaceGenerator.
                Uniform-grid visualisation would emit thousands of
                wireframes (~5k cells at 0.05 m on a 1×1×0.5 m workspace);
                no-op here.  The grid is still drawn via BoxelVisualizer
                from the registry side after the cells are added.

        Returns:
            List of FREE_SPACE BoxelData with empty IDs (the consumer
            registers them via ``BoxelRegistry.add_boxel``).  Same return
            shape as ``FreeSpaceGenerator.generate`` so the call sites in
            ``BoxelTestEnv.generate_free_space`` and
            ``reboxelize_free_space`` are interchangeable.
        """
        del visualize  # see docstring

        free_boxels: List[BoxelData] = []
        known_bounds = [(b.min_corner, b.max_corner) for b in known_boxels]

        for centre in self._cell_centres:
            cell_min = centre - self._cell_extent
            cell_max = centre + self._cell_extent

            # Same AABB-AABB overlap test as the octree generator
            # (free_space.py:91-94): inclusive boundaries.  Cells that
            # exactly touch a known_boxel face are rejected — that
            # matches the octree's "is_mixed" branch and keeps free
            # cells strictly outside obstacles.
            occupied = False
            for b_min, b_max in known_bounds:
                if (np.all(cell_max >= b_min)
                        and np.all(cell_min <= b_max)):
                    occupied = True
                    break

            if not occupied:
                free_boxels.append(BoxelData.from_center_extent(
                    centre, self._cell_extent,
                    boxel_type=BoxelType.FREE_SPACE,
                ))

        return free_boxels
