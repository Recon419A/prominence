"""Divide tree of a raster "terrain": peaks, key cols, prominence and parents.

The terrain is any 2-D grid of heights. For this project heights are population
densities, but nothing here knows that: the algorithm is the classic one used
for mountains.

Cells are visited in descending order of height (a "falling water level"). Each
cell joins the component of any already-visited 8-neighbour. A cell with no
visited neighbour starts a new component and is a **peak**. When a cell touches
two or more components they merge; the cell is the **key col** of every merged
component except the one with the highest peak, and each of those components'
peaks gets

    prominence = peak height - key col height
    parent     = the highest peak of the merged component (its island parent)

Two useful properties fall out of this construction:

- A parent always has prominence >= its child, so filtering peaks by a
  prominence threshold yields a closed subtree.
- Key col heights are non-increasing walking up the tree, so the *merge level*
  of two peaks (the highest contour at which they are one landmass) is the
  minimum key col height along the tree path between them.

Cells at or below ``floor`` (or NaN) are sea and never visited. The summit of
each island keeps ``parent = -1`` and a key col height equal to ``floor``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
from numpy.typing import NDArray

NO_PEAK = -1

_NEIGHBOURS = np.array(
    [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)], dtype=np.int64
)


@dataclass(frozen=True)
class DivideTree:
    """Every peak of a terrain and how it relates to the others.

    All arrays are indexed by peak id. Peaks are numbered in descending order
    of height, so ``peak_height`` is non-increasing and a parent always has a
    smaller id than its children.
    """

    peak_row: NDArray[np.int32]
    peak_col: NDArray[np.int32]
    peak_height: NDArray[np.float32]
    col_row: NDArray[np.int32]
    col_col: NDArray[np.int32]
    col_height: NDArray[np.float32]
    parent: NDArray[np.int32]
    mass: NDArray[np.float64]
    """Sum of ``weight`` over the cells enclosed by the peak's key-col contour."""
    area: NDArray[np.float64]
    """Sum of ``row_area`` over the same cells."""
    cell_peak: NDArray[np.int32] | None = None
    """Per cell, the peak whose *territory* it lies in: the peak whose key-col
    contour encloses the cell while no child's contour does. Sea is ``NO_PEAK``.
    Same shape as the input grid."""

    @property
    def prominence(self) -> NDArray[np.float32]:
        return self.peak_height - self.col_height

    def __len__(self) -> int:
        return len(self.peak_height)

    def prune(self, min_prominence: float) -> DivideTree:
        """Keep peaks with at least ``min_prominence``, renumbering ids.

        Parents always out-prominence children, so the kept set is closed under
        taking parents and no re-parenting is needed.
        """
        keep = self.prominence >= min_prominence
        new_id = np.full(len(self), NO_PEAK, dtype=np.int32)
        new_id[keep] = np.arange(int(keep.sum()), dtype=np.int32)
        parent = self.parent[keep]
        parent = np.where(parent == NO_PEAK, NO_PEAK, new_id[parent]).astype(np.int32)
        cell_peak = None
        if self.cell_peak is not None:
            # A dropped peak's territory folds into its nearest kept ancestor.
            owner = _nearest_kept_ancestor(keep, self.parent)
            lookup = np.append(new_id[owner], NO_PEAK)  # index -1 -> NO_PEAK
            cell_peak = lookup[self.cell_peak]
        return DivideTree(
            peak_row=self.peak_row[keep],
            peak_col=self.peak_col[keep],
            peak_height=self.peak_height[keep],
            col_row=self.col_row[keep],
            col_col=self.col_col[keep],
            col_height=self.col_height[keep],
            parent=parent,
            mass=self.mass[keep],
            area=self.area[keep],
            cell_peak=cell_peak,
        )


@numba.njit(cache=True)
def _nearest_kept_ancestor(keep, parent):
    """For each peak, itself if kept, else its closest kept ancestor (or NO_PEAK).

    Parents have smaller ids than children, so one ascending pass suffices.
    """
    out = np.full(keep.shape[0], NO_PEAK, np.int32)
    for p in range(keep.shape[0]):
        if keep[p]:
            out[p] = p
        elif parent[p] != NO_PEAK:
            out[p] = out[parent[p]]
    return out


def build_divide_tree(
    height: NDArray[np.floating],
    floor: float = 0.0,
    weight: NDArray[np.floating] | None = None,
    row_area: NDArray[np.floating] | None = None,
) -> DivideTree:
    """Compute the divide tree of ``height``.

    Args:
        height: 2-D grid. NaN and values ``<= floor`` are sea.
        floor: sea level; prominence of island summits is measured from here.
        weight: optional 2-D grid summed into ``mass`` (e.g. population count).
        row_area: optional per-row cell area summed into ``area``.
    """
    if height.ndim != 2:
        raise ValueError("height must be 2-D")
    h = np.ascontiguousarray(height, dtype=np.float32)
    nrows = h.shape[0]
    w = np.zeros((0, 0), np.float32) if weight is None else np.ascontiguousarray(weight, np.float32)
    if weight is not None and w.shape != h.shape:
        raise ValueError("weight must have the same shape as height")
    ra = np.zeros(0, np.float64) if row_area is None else np.ascontiguousarray(row_area, np.float64)
    if row_area is not None and ra.shape != (nrows,):
        raise ValueError("row_area must have one entry per row")

    active = np.flatnonzero(_is_land(h, np.float32(floor)))
    # Descending height; ties broken by cell index for determinism.
    order = active[np.argsort(-h.reshape(-1)[active], kind="stable")]
    del active

    n_peaks = _count_peaks(h, order, np.float32(floor))
    (peak_row, peak_col, peak_height, col_row, col_col, col_height, parent, mass, area, cells) = (
        _sweep(h, w, ra, order, n_peaks, np.float32(floor))
    )
    return DivideTree(
        peak_row=peak_row,
        peak_col=peak_col,
        peak_height=peak_height,
        col_row=col_row,
        col_col=col_col,
        col_height=col_height,
        parent=parent,
        mass=mass,
        area=area,
        cell_peak=cells.reshape(h.shape),
    )


@numba.njit(cache=True)
def _is_land(h, floor):
    out = np.empty(h.shape, np.bool_)
    for r in range(h.shape[0]):
        for c in range(h.shape[1]):
            v = h[r, c]
            out[r, c] = v == v and v > floor
    return out


@numba.njit(cache=True)
def _is_peak_cell(h, floor, r, c, idx):
    """True if no neighbour is visited before cell (r, c) in sweep order."""
    nrows, ncols = h.shape
    v = h[r, c]
    for k in range(8):
        rr = r + _NEIGHBOURS[k, 0]
        cc = c + _NEIGHBOURS[k, 1]
        if rr < 0 or rr >= nrows or cc < 0 or cc >= ncols:
            continue
        nv = h[rr, cc]
        if nv != nv or nv <= floor:
            continue
        if nv > v or (nv == v and rr * ncols + cc < idx):
            return False
    return True


@numba.njit(cache=True)
def _count_peaks(h, order, floor):
    ncols = h.shape[1]
    n = 0
    for i in range(order.shape[0]):
        idx = order[i]
        if _is_peak_cell(h, floor, idx // ncols, idx % ncols, idx):
            n += 1
    return n


@numba.njit(cache=True)
def _find(uf, x):
    root = x
    while uf[root] != root:
        root = uf[root]
    while uf[x] != root:
        nxt = uf[x]
        uf[x] = root
        x = nxt
    return root


@numba.njit(cache=True)
def _sweep(h, w, row_area, order, n_peaks, floor):
    nrows, ncols = h.shape
    has_weight = w.shape[0] > 0
    has_area = row_area.shape[0] > 0

    peak_row = np.empty(n_peaks, np.int32)
    peak_col = np.empty(n_peaks, np.int32)
    peak_height = np.empty(n_peaks, np.float32)
    col_row = np.full(n_peaks, -1, np.int32)
    col_col = np.full(n_peaks, -1, np.int32)
    col_height = np.full(n_peaks, floor, np.float32)
    parent = np.full(n_peaks, NO_PEAK, np.int32)
    mass = np.zeros(n_peaks, np.float64)
    area = np.zeros(n_peaks, np.float64)

    # Union-find over peak ids. Peaks are created in descending height order,
    # so the dominant root of any merge is simply the smallest id.
    uf = np.empty(n_peaks, np.int32)
    comp_mass = np.zeros(n_peaks, np.float64)
    comp_area = np.zeros(n_peaks, np.float64)
    cell_comp = np.full(nrows * ncols, NO_PEAK, np.int32)
    roots = np.empty(8, np.int32)
    next_peak = 0

    for i in range(order.shape[0]):
        idx = order[i]
        r = idx // ncols
        c = idx % ncols
        v = h[r, c]

        n_roots = 0
        for k in range(8):
            rr = r + _NEIGHBOURS[k, 0]
            cc = c + _NEIGHBOURS[k, 1]
            if rr < 0 or rr >= nrows or cc < 0 or cc >= ncols:
                continue
            comp = cell_comp[rr * ncols + cc]
            if comp == NO_PEAK:
                continue
            root = _find(uf, comp)
            seen = False
            for j in range(n_roots):
                if roots[j] == root:
                    seen = True
                    break
            if not seen:
                roots[n_roots] = root
                n_roots += 1

        if n_roots == 0:
            dominant = next_peak
            next_peak += 1
            peak_row[dominant] = r
            peak_col[dominant] = c
            peak_height[dominant] = v
            uf[dominant] = dominant
        else:
            dominant = roots[0]
            for j in range(1, n_roots):
                if roots[j] < dominant:
                    dominant = roots[j]
            for j in range(n_roots):
                other = roots[j]
                if other == dominant:
                    continue
                col_row[other] = r
                col_col[other] = c
                col_height[other] = v
                parent[other] = dominant
                mass[other] = comp_mass[other]
                area[other] = comp_area[other]
                comp_mass[dominant] += comp_mass[other]
                comp_area[dominant] += comp_area[other]
                uf[other] = dominant

        cell_comp[idx] = dominant
        if has_weight:
            comp_mass[dominant] += w[r, c]
        if has_area:
            comp_area[dominant] += row_area[r]

    # Island summits never merged: their contour is the whole island.
    for p in range(n_peaks):
        if parent[p] == NO_PEAK:
            mass[p] = comp_mass[p]
            area[p] = comp_area[p]

    return (
        peak_row,
        peak_col,
        peak_height,
        col_row,
        col_col,
        col_height,
        parent,
        mass,
        area,
        cell_comp,
    )


def merge_level(tree: DivideTree, a: int, b: int) -> float:
    """Highest contour at which peaks ``a`` and ``b`` are one landmass.

    Returns the tree's floor if they lie on different islands.
    """
    if a == b:
        return float(tree.peak_height[a])
    ancestors: dict[int, float] = {}
    lowest = np.inf
    node = a
    while node != NO_PEAK:
        ancestors[node] = lowest
        lowest = min(lowest, float(tree.col_height[node]))
        node = int(tree.parent[node])
    lowest = np.inf
    node = b
    while node != NO_PEAK:
        if node in ancestors:
            return min(lowest, ancestors[node])
        lowest = min(lowest, float(tree.col_height[node]))
        node = int(tree.parent[node])
    # Different islands: b's walk ended at an island summit, whose key col
    # height is the floor, so ``lowest`` is already the floor.
    return lowest
