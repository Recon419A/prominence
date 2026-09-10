import json

import numpy as np
from rasterio.transform import from_origin

from prominence.divide_tree import build_divide_tree
from prominence.peaks import City, export_peaks, load_tree, name_peaks, save_tree


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
    assert names.name.tolist() == ["Bigtown", "Smallville"]
    assert names.contains.all()


def test_summit_claims_the_metropolis_before_its_shoulder():
    # The metropolis stands on the shoulder's territory, but the summit is more
    # prominent and claims it first; the shoulder falls back to the district.
    h = np.array([[9, 8, 4, 7, 6]], dtype=np.float32)
    transform = from_origin(0, 1, 1, 1)
    tree = build_divide_tree(h)
    cities = [
        City("Metropolis", "AA", 0.5, 3.5, 5_000_000),  # on the 7-peak's summit cell
        City("District", "AA", 0.5, 4.5, 100_000),
    ]
    names = name_peaks(tree, transform, cities)
    assert names.name.tolist() == ["Metropolis", "District"]


def test_lonely_peak_borrows_nearby_name():
    tree, transform = _ridge()
    # Just south of the grid: ~61 km from the 7-peak's summit, ~330 km from the 9-peak's.
    cities = [City("Faraway", "AA", -0.05, 3.5, 10)]
    names = name_peaks(tree, transform, cities, nearby_km=100)
    assert names.name[0] == ""
    assert names.name[1] == "Faraway"
    assert not names.contains[1]


def test_save_and_load_round_trip(tmp_path):
    tree, transform = _ridge()
    names = name_peaks(tree, transform, [City("Bigtown", "AA", 0.5, 0.5, 1)])
    save_tree(tree, names, transform, 0.5, tmp_path / "tree.npz")
    loaded, loaded_names, loaded_transform, floor = load_tree(tmp_path / "tree.npz")
    assert loaded.prominence.tolist() == tree.prominence.tolist()
    assert loaded.parent.tolist() == tree.parent.tolist()
    assert loaded_names.name.tolist() == names.name.tolist()
    assert loaded_transform == transform
    assert floor == 0.5


def test_export_prunes_and_round_trips(tmp_path):
    tree, transform = _ridge()
    names = name_peaks(tree, transform, [City("Bigtown", "AA", 0.5, 0.5, 1)])
    out = tmp_path / "peaks.json"
    assert export_peaks(tree, names, transform, out, floor=0) == 2
    data = json.loads(out.read_text())
    assert data["floor"] == 0
    assert data["parent"] == [-1, 0]
    assert data["col"] == [None, [0.5, 2.5]]
    assert data["colHeight"] == [0, 4] and data["prominence"] == [9, 3]
    assert data["name"] == ["Bigtown", ""]
    assert data["nameContained"] == [1, -1]
    # Raising the bar drops the 7-peak (prominence 3).
    assert export_peaks(tree, names, transform, out, floor=0, min_prominence=4) == 1
    assert json.loads(out.read_text())["parent"] == [-1]
