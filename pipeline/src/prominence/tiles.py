"""Render a density raster as Terrain-RGB map tiles in a PMTiles archive.

MapLibre can drape, shade and contour any ``raster-dem`` source, so encoding
population density as elevation gets the whole terrain toolchain for free.
Tiles use a Terrain-RGB encoding without the Mapbox -10000 m offset:
``elevation = 0.1 * (R*65536 + G*256 + B)``. Density is never negative, and
dropping the offset keeps sea level exactly representable in the reduced
precision of GPU fragment shaders, where ``-10000 + 100000 * 0.1`` is not.
The range still comfortably covers the densest cells on Earth.
"""

from __future__ import annotations

import io
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

TILE_SIZE = 256
BASE_SHIFT = 0.0
INTERVAL = 0.1

#: MapLibre ``raster-dem`` source options describing this encoding.
ENCODING = {
    "encoding": "custom",
    "redFactor": 65536 * INTERVAL,
    "greenFactor": 256 * INTERVAL,
    "blueFactor": INTERVAL,
    "baseShift": -BASE_SHIFT,
}


def encode_terrain_rgb(elevation: NDArray[np.floating]) -> NDArray[np.uint8]:
    """Terrain-RGB encoding of an elevation grid, clipped to its range."""
    value = np.rint((np.nan_to_num(elevation, nan=0.0) + BASE_SHIFT) / INTERVAL)
    value = np.clip(value, 0, 256**3 - 1).astype(np.uint32)
    rgb = np.empty((*elevation.shape, 3), np.uint8)
    rgb[..., 0] = value >> 16
    rgb[..., 1] = (value >> 8) & 0xFF
    rgb[..., 2] = value & 0xFF
    return rgb


def decode_terrain_rgb(rgb: NDArray[np.uint8]) -> NDArray[np.float64]:
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    return -BASE_SHIFT + (r * 65536 + g * 256 + b) * INTERVAL


def _png_bytes(rgb: NDArray[np.uint8]) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@dataclass(frozen=True)
class RenderedTile:
    z: int
    x: int
    y: int
    png: bytes


_reader = None


def _open_reader(path: str):
    # One reader per worker process; rio-tiler datasets are not picklable.
    global _reader
    if _reader is None:
        from rio_tiler.io import Reader

        _reader = Reader(path)
    return _reader


def _render(args: tuple[str, int, int, int, int]) -> RenderedTile | None:
    """Render one tile, or None if it holds no population at all."""
    path, z, x, y, native_zoom = args
    reader = _open_reader(path)
    resampling = "average" if z < native_zoom else "bilinear"
    data = reader.tile(x, y, z, tilesize=TILE_SIZE, resampling_method=resampling)
    grid = np.where(data.mask[0] > 0, data.data[0], 0.0)
    if not np.any(grid > 0):
        return None
    return RenderedTile(z, x, y, _png_bytes(encode_terrain_rgb(grid)))


def render_pmtiles(
    density_path: Path,
    out_path: Path,
    *,
    max_zoom: int,
    native_zoom: int,
    workers: int | None = None,
    attribution: str = "",
) -> int:
    """Write Terrain-RGB tiles for zooms 0..``max_zoom``; returns the tile count.

    The quadtree is pruned as it descends: a tile with no population has no
    populated children, so those are never rendered. Every unrendered tile is
    then written as one shared all-sea tile, which PMTiles stores once, so the
    map never has to treat a missing tile differently from open ocean.
    """
    path = str(density_path)
    tiles: list[RenderedTile] = []
    frontier = [(0, 0, 0)]
    with ProcessPoolExecutor(workers) as pool:
        for z in range(max_zoom + 1):
            jobs = [(path, z, x, y, native_zoom) for (_, x, y) in frontier]
            rendered = [t for t in pool.map(_render, jobs, chunksize=16) if t is not None]
            tiles.extend(rendered)
            frontier = [
                (z + 1, 2 * t.x + dx, 2 * t.y + dy)
                for t in rendered
                for dx in (0, 1)
                for dy in (0, 1)
            ]

    rendered = {zxy_to_tileid(t.z, t.x, t.y): t.png for t in tiles}
    sea = _png_bytes(encode_terrain_rgb(np.zeros((TILE_SIZE, TILE_SIZE))))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        writer = Writer(fh)
        for z in range(max_zoom + 1):
            for x in range(2**z):
                for y in range(2**z):
                    tile_id = zxy_to_tileid(z, x, y)
                    writer.write_tile(tile_id, rendered.get(tile_id, sea))
        writer.finalize(
            {
                "tile_type": TileType.PNG,
                "tile_compression": Compression.NONE,
                "min_zoom": 0,
                "max_zoom": max_zoom,
                "min_lon_e7": -180_0000000,
                "min_lat_e7": -85_0511288,
                "max_lon_e7": 180_0000000,
                "max_lat_e7": 85_0511288,
                "center_zoom": 2,
                "center_lon_e7": 0,
                "center_lat_e7": 20_0000000,
            },
            {
                "name": "Population density as Terrain-RGB",
                **ENCODING,
                "units": "people per km² encoded as metres",
                "attribution": attribution,
            },
        )
    return len(tiles)
