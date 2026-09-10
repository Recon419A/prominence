"""From a density grid to a named, exportable list of peaks."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.transform import Affine, rowcol, xy

from prominence.density import cell_areas_km2, read_density
from prominence.divide_tree import NO_PEAK, DivideTree, build_divide_tree

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class City:
    name: str
    country: str
    lat: float
    lon: float
    population: int


def load_geonames_cities(path: Path) -> list[City]:
    """Parse a GeoNames ``citiesNNNN.txt`` dump."""
    cities = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            cities.append(
                City(
                    name=row[1],
                    country=row[8],
                    lat=float(row[4]),
                    lon=float(row[5]),
                    population=int(row[14] or 0),
                )
            )
    return cities


def compute_tree(
    density_path: Path,
    count_path: Path | None,
    *,
    floor: float,
    min_prominence: float,
) -> tuple[DivideTree, Affine]:
    """Build and prune the divide tree of a density raster.

    ``count_path`` supplies the population per cell so each peak carries the
    number of people inside its key-col contour.
    """
    density, transform = read_density(density_path)
    weight = None
    if count_path is not None:
        with rasterio.open(count_path) as src:
            if src.shape != density.shape:
                raise ValueError("count and density grids must share a shape")
            weight = src.read(1, out_dtype="float32")
    row_area = cell_areas_km2(transform, density.shape[0])
    tree = build_divide_tree(density, floor=floor, weight=weight, row_area=row_area)
    return tree.prune(min_prominence), transform


@dataclass(frozen=True)
class PeakName:
    name: str
    country: str
    contains: bool
    """True if the city lies in the peak's territory, False if merely nearby."""


def name_peaks(
    tree: DivideTree,
    transform: Affine,
    cities: list[City],
    *,
    nearby_km: float = 30.0,
) -> list[PeakName | None]:
    """Name each peak after the most populous city in its territory.

    A peak whose territory holds no city borrows the name of the nearest city
    within ``nearby_km`` of its summit, flagged as such.
    """
    if tree.cell_peak is None:
        raise ValueError("tree has no territory map")
    nrows, ncols = tree.cell_peak.shape
    lats = np.array([c.lat for c in cities])
    lons = np.array([c.lon for c in cities])
    rows, cols = rowcol(transform, lons, lats)
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    inside = (rows >= 0) & (rows < nrows) & (cols >= 0) & (cols < ncols)
    owner = np.full(len(cities), NO_PEAK, np.int32)
    owner[inside] = tree.cell_peak[rows[inside], cols[inside]]

    names: list[PeakName | None] = [None] * len(tree)
    best_pop = np.full(len(tree), -1, dtype=np.int64)
    for i, city in enumerate(cities):
        p = owner[i]
        if p != NO_PEAK and city.population > best_pop[p]:
            best_pop[p] = city.population
            names[p] = PeakName(city.name, city.country, contains=True)

    unnamed = np.flatnonzero(best_pop < 0)
    if len(unnamed):
        peak_lons, peak_lats = xy(transform, tree.peak_row[unnamed], tree.peak_col[unnamed])
        for p, plat, plon in zip(unnamed, peak_lats, peak_lons, strict=True):
            d = _haversine_km(plat, plon, lats, lons)
            j = int(np.argmin(d))
            if d[j] <= nearby_km:
                names[p] = PeakName(cities[j].name, cities[j].country, contains=False)
    return names


def _haversine_km(lat: float, lon: float, lats: NDArray, lons: NDArray) -> NDArray:
    phi1, phi2 = math.radians(lat), np.radians(lats)
    dphi = phi2 - phi1
    dlam = np.radians(lons - lon)
    a = np.sin(dphi / 2) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def export_peaks(
    tree: DivideTree,
    transform: Affine,
    names: list[PeakName | None],
    path: Path,
    *,
    floor: float,
) -> None:
    """Write the peaks as compact JSON for the web app.

    Peaks are listed in id order so that ``parent`` indexes into the list.
    """
    peak_lon, peak_lat = xy(transform, tree.peak_row, tree.peak_col)
    has_col = tree.parent != NO_PEAK
    col_lon, col_lat = xy(transform, tree.col_row, tree.col_col)
    peaks = []
    for i in range(len(tree)):
        name = names[i]
        peaks.append(
            {
                "id": i,
                "lat": round(float(peak_lat[i]), 4),
                "lon": round(float(peak_lon[i]), 4),
                "height": round(float(tree.peak_height[i]), 1),
                "prominence": round(float(tree.prominence[i]), 1),
                "colHeight": round(float(tree.col_height[i]), 1),
                "col": (
                    [round(float(col_lat[i]), 4), round(float(col_lon[i]), 4)]
                    if has_col[i]
                    else None
                ),
                "parent": int(tree.parent[i]) if has_col[i] else None,
                "population": round(float(tree.mass[i])),
                "areaKm2": round(float(tree.area[i]), 1),
                "name": name.name if name else None,
                "country": name.country if name else None,
                "nameContained": name.contains if name else None,
            }
        )
    payload = {
        "units": {"height": "people per km²"},
        "floor": floor,
        "peaks": peaks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
