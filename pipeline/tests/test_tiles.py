import numpy as np

from prominence.tiles import decode_terrain_rgb, encode_terrain_rgb


def test_terrain_rgb_round_trip_to_a_tenth():
    elevation = np.array([[0.0, 0.05, 12.3, 60_000.0, 333_333.3], [np.nan, -3.0, 1.0, 2.0, 3.0]])
    decoded = decode_terrain_rgb(encode_terrain_rgb(elevation))
    expected = np.nan_to_num(elevation)
    assert np.allclose(decoded, np.round(expected, 1), atol=0.051)


def test_sea_level_is_zero_and_shape_is_rgb():
    rgb = encode_terrain_rgb(np.zeros((4, 4)))
    assert rgb.shape == (4, 4, 3)
    assert decode_terrain_rgb(rgb).tolist() == np.zeros((4, 4)).tolist()
