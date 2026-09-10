import numpy as np
import pytest
from rasterio.transform import Affine, from_origin

from prominence.density import AUTHALIC_RADIUS_KM, cell_areas_km2


def test_cell_areas_sum_to_sphere():
    # A 1-degree global grid.
    transform = from_origin(-180, 90, 1, 1)
    areas = cell_areas_km2(transform, 180)
    total = areas.sum() * 360
    assert total == pytest.approx(4 * np.pi * AUTHALIC_RADIUS_KM**2, rel=1e-9)


def test_cells_shrink_toward_poles():
    transform = from_origin(-180, 90, 1, 1)
    areas = cell_areas_km2(transform, 180)
    assert areas[0] < areas[89]
    assert areas[89] == pytest.approx(areas[90])


def test_rejects_rotated_grid():
    with pytest.raises(ValueError):
        cell_areas_km2(Affine(1, 0.5, 0, 0, -1, 0), 10)
