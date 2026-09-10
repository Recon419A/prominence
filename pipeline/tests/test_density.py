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


def test_count_to_density_smooths_and_preserves_totals(tmp_path):
    import rasterio

    from prominence.density import count_to_density

    counts = np.zeros((8, 8), dtype=np.float64)
    counts[4, 4] = 900.0
    transform = from_origin(0, 8, 1, 1)
    src_path = tmp_path / "count.tif"
    with rasterio.open(
        src_path,
        "w",
        driver="GTiff",
        width=8,
        height=8,
        count=1,
        dtype="float64",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(counts, 1)
    raw_path = count_to_density(src_path, tmp_path / "raw.tif", smooth=1, overviews=False)
    smooth_path = count_to_density(src_path, tmp_path / "smooth.tif", smooth=3, overviews=False)
    with rasterio.open(raw_path) as f:
        raw = f.read(1)
    with rasterio.open(smooth_path) as f:
        smooth = f.read(1)
    areas = cell_areas_km2(transform, 8)
    assert raw[4, 4] == pytest.approx(900 / areas[4])
    assert (raw > 0).sum() == 1
    assert (smooth > 0).sum() == 9
    assert smooth[4, 4] == pytest.approx(raw[4, 4] / 9)
    # Mass is conserved by the box filter away from the edges.
    assert (smooth * areas[:, None]).sum() == pytest.approx(900, rel=1e-3)
