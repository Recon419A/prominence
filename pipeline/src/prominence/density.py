"""Turn a population-count grid into a density grid, and describe its geometry."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.windows import Window

#: Radius of the sphere with the same surface area as the WGS84 ellipsoid, km.
AUTHALIC_RADIUS_KM = 6371.0072

DENSITY_NODATA = np.float32(-1.0)


def cell_areas_km2(transform: Affine, nrows: int) -> NDArray[np.float64]:
    """Area of one cell in each row of a north-up geographic grid.

    Uses the spherical formula on the authalic sphere, which is within a few
    tenths of a percent of the ellipsoidal value everywhere.
    """
    if transform.b != 0 or transform.d != 0 or transform.e >= 0:
        raise ValueError("expected a north-up geographic transform")
    rows = np.arange(nrows + 1)
    lat_edges = np.radians(transform.f + rows * transform.e)
    dlon = np.radians(abs(transform.a))
    return AUTHALIC_RADIUS_KM**2 * dlon * (np.sin(lat_edges[:-1]) - np.sin(lat_edges[1:]))


def count_to_density(
    count_path: Path,
    density_path: Path,
    *,
    block_rows: int = 512,
    overviews: bool = True,
) -> Path:
    """Write people-per-km² from a people-per-cell GeoTIFF.

    Nodata in the source (ocean) stays nodata. Overviews are averaged, which is
    the right aggregation for an intensive quantity like density.
    """
    with rasterio.open(count_path) as src:
        if src.count != 1:
            raise ValueError("expected a single-band count raster")
        areas = cell_areas_km2(src.transform, src.height)
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="float32",
            nodata=float(DENSITY_NODATA),
            tiled=True,
            blockxsize=512,
            blockysize=512,
            compress="deflate",
            predictor=3,
            zlevel=6,
            bigtiff="yes",
        )
        density_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(density_path, "w", **profile) as dst:
            for row0 in range(0, src.height, block_rows):
                window = Window(0, row0, src.width, min(block_rows, src.height - row0))
                counts = src.read(1, window=window, masked=True)
                area = areas[row0 : row0 + window.height, None]
                density = np.asarray(counts / area, dtype=np.float32)
                density = np.where(counts.mask, DENSITY_NODATA, density)
                dst.write(density, 1, window=window)
            if overviews:
                factors = [2**k for k in range(1, 8) if src.width >> k >= 256]
                dst.build_overviews(factors, Resampling.average)
                dst.update_tags(ns="rio_overview", resampling="average")
    return density_path


def read_density(path: Path) -> tuple[NDArray[np.float32], Affine]:
    """Load a density grid with nodata as NaN."""
    with rasterio.open(path) as src:
        data = src.read(1)
        if src.nodata is not None:
            data[data == src.nodata] = np.nan
        return data, src.transform
