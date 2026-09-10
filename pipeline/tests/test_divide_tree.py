from collections import deque

import numpy as np
import pytest

from prominence.divide_tree import NO_PEAK, build_divide_tree, merge_level


def _reachable_higher(h, start, level):
    """Brute force: is a strictly higher cell reachable from ``start`` staying >= level?"""
    nrows, ncols = h.shape
    seen = {start}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (rr, cc) in seen or not (0 <= rr < nrows and 0 <= cc < ncols):
                    continue
                if h[rr, cc] < level:
                    continue
                if h[rr, cc] > h[start]:
                    return True
                seen.add((rr, cc))
                queue.append((rr, cc))
    return False


def _brute_prominence(h, floor, peak):
    """Key col = highest level at which higher ground is reachable."""
    levels = sorted({float(v) for v in h.ravel() if v > floor}, reverse=True)
    for level in levels:
        if level > h[peak]:
            continue
        if _reachable_higher(h, peak, level):
            return h[peak] - level
    return h[peak] - floor


def test_single_peak_is_island_summit():
    h = np.array([[0, 0, 0], [0, 5, 0], [0, 0, 0]], dtype=np.float32)
    tree = build_divide_tree(h)
    assert len(tree) == 1
    assert tree.parent[0] == NO_PEAK
    assert tree.prominence[0] == pytest.approx(5.0)
    assert (tree.peak_row[0], tree.peak_col[0]) == (1, 1)


def test_two_peaks_share_a_col():
    h = np.array([[9, 4, 7]], dtype=np.float32)
    tree = build_divide_tree(h)
    assert tree.peak_height.tolist() == [9, 7]
    assert tree.parent.tolist() == [NO_PEAK, 0]
    assert tree.col_height.tolist() == [0, 4]
    assert (tree.col_row[1], tree.col_col[1]) == (0, 1)
    assert tree.prominence.tolist() == [9, 3]


def test_floor_raises_sea_level():
    h = np.array([[9, 4, 7]], dtype=np.float32)
    tree = build_divide_tree(h, floor=5)
    # The col at 4 is under water: two islands.
    assert tree.parent.tolist() == [NO_PEAK, NO_PEAK]
    assert tree.prominence.tolist() == [4, 2]


def test_plateau_yields_single_significant_peak():
    h = np.array([[3, 3, 3, 3]], dtype=np.float32)
    tree = build_divide_tree(h)
    assert (tree.prominence > 0).sum() == 1


def test_nan_is_sea():
    h = np.array([[9, np.nan, 7]], dtype=np.float32)
    tree = build_divide_tree(h)
    assert tree.parent.tolist() == [NO_PEAK, NO_PEAK]


def test_mass_and_area_inside_key_col_contour():
    h = np.array([[9, 8, 4, 7, 6]], dtype=np.float32)
    weight = np.array([[10, 20, 30, 40, 50]], dtype=np.float32)
    row_area = np.array([2.0])
    tree = build_divide_tree(h, weight=weight, row_area=row_area)
    # Peak 7 (with its shoulder 6) is enclosed above its col at 4.
    assert tree.peak_height.tolist() == [9, 7]
    assert tree.mass.tolist() == [150, 90]
    assert tree.area.tolist() == [10, 4]


def test_parent_out_prominences_child_and_prune_is_closed():
    rng = np.random.default_rng(0)
    h = rng.random((40, 40), dtype=np.float32)
    tree = build_divide_tree(h)
    child_has_parent = tree.parent != NO_PEAK
    assert np.all(
        tree.prominence[child_has_parent] <= tree.prominence[tree.parent[child_has_parent]]
    )
    pruned = tree.prune(0.2)
    assert np.all(pruned.prominence >= 0.2)
    assert np.all((pruned.parent == NO_PEAK) | (pruned.parent < np.arange(len(pruned))))


@pytest.mark.parametrize("seed", range(5))
def test_matches_brute_force_on_random_terrain(seed):
    rng = np.random.default_rng(seed)
    h = rng.random((12, 12)).astype(np.float32)
    floor = 0.1
    tree = build_divide_tree(h, floor=floor)
    for p in range(len(tree)):
        peak = (int(tree.peak_row[p]), int(tree.peak_col[p]))
        expected = _brute_prominence(h, floor, peak)
        assert tree.prominence[p] == pytest.approx(expected, abs=1e-6), peak


def test_merge_level_is_lowest_col_on_path():
    # Ridge: 9 . 5 . 8 . 2 . 7 . 6 . 4   -> peaks 9, 8, 7 (and shoulder 6)
    h = np.array([[9, 5, 8, 2, 7, 6, 4]], dtype=np.float32)
    tree = build_divide_tree(h)
    ids = {float(v): i for i, v in enumerate(tree.peak_height)}
    assert merge_level(tree, ids[9], ids[8]) == 5
    assert merge_level(tree, ids[8], ids[7]) == 2
    assert merge_level(tree, ids[9], ids[7]) == 2
    assert merge_level(tree, ids[7], ids[7]) == 7


def test_merge_level_across_islands_is_floor():
    h = np.array([[9, 1, 7]], dtype=np.float32)
    tree = build_divide_tree(h, floor=3)
    assert merge_level(tree, 0, 1) == 3
