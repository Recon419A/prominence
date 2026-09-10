import json

import numpy as np
from rasterio.transform import from_origin

from prominence.divide_tree import build_divide_tree
from prominence.peaks import City, export_peaks, name_peaks


def _ridge():
    # One row of cells 1 degree wide starting at lon 0, lat 1..0.
    h = np.array([[9, 8, 4, 7, 6]], dtype=np.float32)
    transform = from_origin(0, 1, 1, 1)
    return build_divide_tree(h), transform


def test_peaks_named_by_most_populous_contained_city():
    tree, transform = _ridge()
    cities = [
        City("Bigtown", "AA", 0.5, 0.5, 1_000_000),
        City("Suburb", "AA", 0.5, 1.5, 50_000),
        City("Smallville", "AA", 0.5, 4.5, 20_000),
        City("Offgrid", "ZZ", 50, 50, 5),
    ]
    names = name_peaks(tree, transform, cities)
    assert [n.name for n in names] == ["Bigtown", "Smallville"]
    assert all(n.contains for n in names)


def test_lonely_peak_borrows_nearby_name():
    tree, transform = _ridge()
    cities = [City("Faraway", "AA", 0.5, 3.6, 10)]  # in the 7-peak's land, off the summit cell
    names = name_peaks(tree, transform, cities, nearby_km=30)
    assert names[0] is None  # nothing within 30 km of the 9-peak at (0.5, 0.5)
    assert names[1].name == "Faraway"


def test_export_round_trips(tmp_path):
    tree, transform = _ridge()
    names = name_peaks(tree, transform, [City("Bigtown", "AA", 0.5, 0.5, 1)])
    out = tmp_path / "peaks.json"
    export_peaks(tree, transform, names, out, floor=0)
    data = json.loads(out.read_text())
    assert data["floor"] == 0
    first, second = data["peaks"]
    assert first["parent"] is None and first["col"] is None
    assert second["parent"] == 0 and second["colHeight"] == 4 and second["prominence"] == 3
    assert first["name"] == "Bigtown" and second["name"] is None
