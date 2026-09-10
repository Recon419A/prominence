"""Command line entry point: ``prominence --help``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prominence import density, peaks, sources, tiles

app = typer.Typer(help="Build the population-as-terrain dataset.", no_args_is_help=True)

DataDir = Annotated[Path, typer.Option(help="Root of raw and derived data.")]
Epoch = Annotated[int, typer.Option(help="GHS-POP epoch year.")]

ATTRIBUTION = (
    "Population: GHS-POP R2023A, European Commission JRC (CC BY 4.0). "
    "Place names: GeoNames (CC BY 4.0)."
)


def _paths(data_dir: Path, epoch: int) -> dict[str, Path]:
    source = sources.GhsPop(epoch=epoch)
    return {
        "raw": data_dir / "raw",
        "count": data_dir / "raw" / f"{source.stem}.tif",
        "density": data_dir / "derived" / f"density_{epoch}_30ss.tif",
        "tree": data_dir / "derived" / f"tree_{epoch}.npz",
        "peaks": data_dir / "derived" / f"peaks_{epoch}.json",
        "tiles": data_dir / "derived" / f"density_{epoch}.pmtiles",
    }


@app.command()
def fetch(data_dir: DataDir = Path("data"), epoch: Epoch = 2025) -> None:
    """Download GHS-POP and GeoNames into the raw data directory."""
    p = _paths(data_dir, epoch)
    typer.echo(sources.fetch_ghs_pop(sources.GhsPop(epoch=epoch), p["raw"]))
    typer.echo(sources.fetch_geonames_cities(p["raw"]))


@app.command("density")
def density_cmd(data_dir: DataDir = Path("data"), epoch: Epoch = 2025) -> None:
    """Convert population counts to people per km² with averaged overviews."""
    p = _paths(data_dir, epoch)
    typer.echo(density.count_to_density(p["count"], p["density"]))


MinProminence = Annotated[float, typer.Option(help="Keep peaks at least this prominent.")]


@app.command("peaks")
def peaks_cmd(
    data_dir: DataDir = Path("data"),
    epoch: Epoch = 2025,
    floor: Annotated[float, typer.Option(help="Sea level, people per km².")] = 1.0,
    min_prominence: MinProminence = 100.0,
    export_prominence: Annotated[
        float, typer.Option(help="Prominence threshold for the JSON export.")
    ] = 3000.0,
) -> None:
    """Compute and name the divide tree, save it, and export peaks as JSON."""
    p = _paths(data_dir, epoch)
    tree, transform = peaks.compute_tree(
        p["density"], p["count"], floor=floor, min_prominence=min_prominence
    )
    cities = peaks.load_geonames_cities(p["raw"] / "cities15000.txt")
    names = peaks.name_peaks(tree, transform, cities)
    peaks.save_tree(tree, names, transform, floor, p["tree"])
    typer.echo(f"{len(tree)} peaks with prominence >= {min_prominence} -> {p['tree']}")
    export(data_dir, epoch, export_prominence)


@app.command()
def export(
    data_dir: DataDir = Path("data"),
    epoch: Epoch = 2025,
    min_prominence: MinProminence = 3000.0,
) -> None:
    """Export peaks from a saved tree as JSON, at a chosen prominence threshold."""
    p = _paths(data_dir, epoch)
    tree, names, transform, floor = peaks.load_tree(p["tree"])
    n = peaks.export_peaks(
        tree, names, transform, p["peaks"], floor=floor, min_prominence=min_prominence
    )
    typer.echo(f"{n} peaks with prominence >= {min_prominence} -> {p['peaks']}")


@app.command("tiles")
def tiles_cmd(
    data_dir: DataDir = Path("data"),
    epoch: Epoch = 2025,
    max_zoom: Annotated[int, typer.Option(help="Deepest zoom to render.")] = 8,
    workers: Annotated[int | None, typer.Option(help="Render processes.")] = None,
) -> None:
    """Render Terrain-RGB tiles of density into a PMTiles archive."""
    p = _paths(data_dir, epoch)
    n = tiles.render_pmtiles(
        p["density"],
        p["tiles"],
        max_zoom=max_zoom,
        native_zoom=7,
        workers=workers,
        attribution=ATTRIBUTION,
    )
    typer.echo(f"{n} tiles -> {p['tiles']}")


@app.command()
def build(data_dir: DataDir = Path("data"), epoch: Epoch = 2025) -> None:
    """Run every step: fetch, density, peaks, tiles."""
    fetch(data_dir, epoch)
    density_cmd(data_dir, epoch)
    peaks_cmd(data_dir, epoch)
    tiles_cmd(data_dir, epoch)
