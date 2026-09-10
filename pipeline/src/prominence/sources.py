"""Public datasets the pipeline builds on, and a small download cache."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

GHSL_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
GEONAMES_CITIES_URL = "https://download.geonames.org/export/dump/cities15000.zip"

Resolution = Literal["30ss", "3ss"]


@dataclass(frozen=True)
class GhsPop:
    """A GHS-POP population-count grid (people per cell) in WGS84.

    The Global Human Settlement Layer is published by the European Commission's
    Joint Research Centre under CC BY 4.0. ``30ss`` is roughly 1 km at the
    equator, ``3ss`` roughly 100 m.
    """

    epoch: int = 2025
    resolution: Resolution = "30ss"
    release: str = "R2023A"

    @property
    def product(self) -> str:
        return f"GHS_POP_E{self.epoch}_GLOBE_{self.release}_4326_{self.resolution}"

    @property
    def stem(self) -> str:
        return f"{self.product}_V1_0"

    def global_url(self) -> str:
        return f"{GHSL_BASE}/GHS_POP_GLOBE_{self.release}/{self.product}/V1-0/{self.stem}.zip"

    def tile_url(self, row: int, col: int) -> str:
        """URL of one tile of the GHSL tiling scheme (used for the 3ss grid)."""
        return (
            f"{GHSL_BASE}/GHS_POP_GLOBE_{self.release}/{self.product}/V1-0/tiles/"
            f"{self.stem}_R{row}_C{col}.zip"
        )


def download(url: str, dest: Path, *, client: httpx.Client | None = None) -> Path:
    """Download ``url`` to ``dest`` unless it already exists."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    own_client = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=60)
    try:
        with client.stream("GET", url) as response, partial.open("wb") as fh:
            response.raise_for_status()
            for chunk in response.iter_bytes(1 << 20):
                fh.write(chunk)
    finally:
        if own_client:
            client.close()
    partial.replace(dest)
    return dest


def extract_member(archive: Path, suffix: str, dest_dir: Path) -> Path:
    """Extract the single member of ``archive`` ending in ``suffix``."""
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if n.endswith(suffix)]
        if len(names) != 1:
            raise ValueError(f"expected one *{suffix} in {archive.name}, found {names}")
        target = dest_dir / Path(names[0]).name
        if not target.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            zf.extract(names[0], dest_dir)
            extracted = dest_dir / names[0]
            if extracted != target:
                extracted.replace(target)
        return target


def fetch_ghs_pop(source: GhsPop, raw_dir: Path) -> Path:
    """Return the local GeoTIFF for ``source``, downloading and unzipping if needed."""
    archive = download(source.global_url(), raw_dir / f"{source.stem}.zip")
    return extract_member(archive, ".tif", raw_dir)


def fetch_geonames_cities(raw_dir: Path) -> Path:
    archive = download(GEONAMES_CITIES_URL, raw_dir / "cities15000.zip")
    return extract_member(archive, ".txt", raw_dir)
