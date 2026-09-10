"""From a density grid to a named, exportable list of peaks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.transform import Affine, rowcol, xy
from scipy.spatial import cKDTree

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
class PeakNames:
    """Parallel arrays of names for every peak of a tree; empty string = unnamed."""

    name: NDArray[np.str_]
    country: NDArray[np.str_]
    contains: NDArray[np.bool_]
    """True if the city lies in the peak's territory, False if merely nearby."""

    def __getitem__(self, keep: NDArray[np.bool_]) -> PeakNames:
        return PeakNames(self.name[keep], self.country[keep], self.contains[keep])


def name_peaks(
    tree: DivideTree,
    transform: Affine,
    cities: list[City],
    *,
    nearby_km: float = 30.0,
) -> PeakNames:
    """Name peaks after the cities standing on their mountains.

    Each city belongs to the peak whose territory it stands in, and by
    extension to every ancestor of that peak. Peaks then claim names in
    descending order of prominence: each takes the most populous city on its
    mountain that no more prominent peak has already claimed. So a summit is
    named for the metropolis rather than for the district its cell happens to
    sit in, while its shoulders pick up the districts.

    A peak left without a city borrows the name of the nearest city within
    ``nearby_km`` of its summit, flagged as such.
    """
    if tree.cell_peak is None:
        raise ValueError("tree has no territory map")
    nrows, ncols = tree.cell_peak.shape
    n = len(tree)
    lats = np.array([c.lat for c in cities])
    lons = np.array([c.lon for c in cities])
    rows, cols = rowcol(transform, lons, lats)
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    inside = (rows >= 0) & (rows < nrows) & (cols >= 0) & (cols < ncols)
    owner = np.full(len(cities), NO_PEAK, np.int32)
    owner[inside] = tree.cell_peak[rows[inside], cols[inside]]

    # Cities on each peak's mountain, most populous first.
    candidates: dict[int, list[int]] = {}
    for i in np.argsort([-c.population for c in cities], kind="stable"):
        p = owner[i]
        while p != NO_PEAK:
            candidates.setdefault(int(p), []).append(int(i))
            p = tree.parent[p]

    name = np.full(n, "", dtype=object)
    country = np.full(n, "", dtype=object)
    contains = np.zeros(n, dtype=bool)
    claimed = np.zeros(len(cities), dtype=bool)
    for p in np.argsort(-tree.prominence, kind="stable"):
        for i in candidates.get(int(p), ()):
            if not claimed[i]:
                claimed[i] = True
                name[p], country[p], contains[p] = cities[i].name, cities[i].country, True
                break

    unnamed = np.flatnonzero(~contains)
    if len(unnamed) and len(cities):
        peak_lons, peak_lats = xy(transform, tree.peak_row[unnamed], tree.peak_col[unnamed])
        index = cKDTree(_unit_vectors(lats, lons))
        chord = 2 * np.sin(nearby_km / EARTH_RADIUS_KM / 2)
        dist, j = index.query(_unit_vectors(np.asarray(peak_lats), np.asarray(peak_lons)))
        for p, d, city_ix in zip(unnamed, dist, j, strict=True):
            if d <= chord:
                name[p], country[p] = cities[city_ix].name, cities[city_ix].country
    return PeakNames(name.astype(str), country.astype(str), contains)


def _unit_vectors(lats: NDArray, lons: NDArray) -> NDArray[np.float64]:
    phi, lam = np.radians(lats), np.radians(lons)
    return np.column_stack((np.cos(phi) * np.cos(lam), np.cos(phi) * np.sin(lam), np.sin(phi)))


def save_tree(
    tree: DivideTree, names: PeakNames, transform: Affine, floor: float, path: Path
) -> None:
    """Persist a named tree (without its territory map) as compressed NumPy arrays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        peak_row=tree.peak_row,
        peak_col=tree.peak_col,
        peak_height=tree.peak_height,
        col_row=tree.col_row,
        col_col=tree.col_col,
        col_height=tree.col_height,
        parent=tree.parent,
        mass=tree.mass,
        area=tree.area,
        name=names.name,
        country=names.country,
        contains=names.contains,
        transform=np.array(transform.to_gdal()),
        floor=np.array(floor),
    )


def load_tree(path: Path) -> tuple[DivideTree, PeakNames, Affine, float]:
    with np.load(path) as z:
        tree = DivideTree(
            peak_row=z["peak_row"],
            peak_col=z["peak_col"],
            peak_height=z["peak_height"],
            col_row=z["col_row"],
            col_col=z["col_col"],
            col_height=z["col_height"],
            parent=z["parent"],
            mass=z["mass"],
            area=z["area"],
        )
        names = PeakNames(z["name"], z["country"], z["contains"])
        transform = Affine.from_gdal(*z["transform"].tolist())
        floor = float(z["floor"])
    return tree, names, transform, floor


def export_peaks(
    tree: DivideTree,
    names: PeakNames,
    transform: Affine,
    path: Path,
    *,
    floor: float,
    min_prominence: float = 0.0,
) -> int:
    """Write peaks with at least ``min_prominence`` as compact columnar JSON.

    Every column has one entry per peak, in id order, so ``parent`` indexes
    the columns directly. Returns the number of peaks written.
    """
    keep = tree.prominence >= min_prominence
    tree = tree.prune(min_prominence)
    names = names[keep]
    peak_lon, peak_lat = xy(transform, tree.peak_row, tree.peak_col)
    has_col = tree.parent != NO_PEAK
    col_lon, col_lat = xy(transform, tree.col_row, tree.col_col)
    named = names.name != ""
    payload = {
        "units": {"height": "people per km²"},
        "floor": floor,
        "minProminence": min_prominence,
        "lat": _round(peak_lat, 3),
        "lon": _round(peak_lon, 3),
        "height": _round(tree.peak_height, 0),
        "prominence": _round(tree.prominence, 0),
        "colHeight": _round(tree.col_height, 0),
        "col": [
            [round(float(la), 3), round(float(lo), 3)] if has else None
            for la, lo, has in zip(col_lat, col_lon, has_col, strict=True)
        ],
        "parent": tree.parent.tolist(),
        "population": _round(tree.mass, 0),
        "areaKm2": _round(tree.area, 0),
        "name": names.name.tolist(),
        "country": np.where(named, names.country, "").tolist(),
        "nameContained": np.where(named, names.contains.astype(int), -1).tolist(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    return len(tree)


def _round(values: NDArray, decimals: int) -> list[float | int]:
    if decimals == 0:
        return np.rint(np.asarray(values, dtype=np.float64)).astype(np.int64).tolist()
    return np.round(np.asarray(values, dtype=np.float64), decimals).tolist()
