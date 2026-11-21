"""Terrain-aware inundation (flood/inundation.py): small hand-built grids, no network, no real files."""
import numpy as np
from rasterio.transform import from_origin

from flood.inundation import (DRY, PROFILE, SHORELINE, UNRESOLVED, build_inundation, downsample, fwdet_levels,
                              level_codes, order_channel, profile_levels)

T = from_origin(0, 100, 1, 1)  # 1 m cells, x 0..100, y 100..0


def valley(n=100):
    """Channel along the row 50; ground rises 0.1 m per metre away from it; a ridge at column 70."""
    rows = np.abs(np.arange(n) - 50)[:, None] * 0.1 + np.zeros((1, n))
    dem = 10.0 + rows
    dem[:, 70] = 20.0  # ridge: the right side is cut off from the channel west of it
    return dem


def test_order_channel_chains_reversed_pieces_west_to_east():
    a = np.array([[50.0, 0], [100, 0]])
    b = np.array([[50.0, 0], [0, 0]])  # touches a, drawn backwards
    pts, st = order_channel([a, b])
    assert pts[0, 0] == 0 and pts[-1, 0] == 100
    assert st[-1] == 100


def test_profile_averages_duplicate_stations_and_interpolates():
    assert profile_levels([0, 50, 100], [0, 0, 100], [10, 12, 14])[1] == 12.5  # (11 + 14) / 2
    assert profile_levels([200], [0, 100], [10, 14])[0] == 14  # held beyond the last mark


def test_fwdet_takes_nearest_shoreline_elevation():
    dem = valley()
    dem[:, 70] = dem[:, 69]  # no ridge: a ridge would itself act as a (low) shoreline
    flood = dem < 12.0  # rows 31..69: shoreline cells sit near 11.9 m
    wse = fwdet_levels(dem, flood, smooth_cells=1)
    assert np.nanmax(np.abs(wse[flood] - 11.9)) < 0.11
    assert np.isnan(wse[~flood]).all()


def model(dem, flood):
    channel = [np.array([[0.0, 49.5], [99.0, 49.5]])]
    marks = [(20.0, 49.5), (60.0, 49.5)]  # x, y in metres
    return build_inundation(dem, T, flood, marks, [12.0, 12.0], channel, reach_buffer_m=10, blend_m=10)


def test_water_only_inside_the_mapped_extent_and_depth_is_surface_minus_ground():
    dem = valley()
    flood = np.zeros_like(dem, bool)
    flood[40:61, :] = True
    m = model(dem, flood)
    assert np.isnan(m["wse"][~flood]).all()
    assert (m["cls"][~flood] == DRY).all()
    wet = (m["cls"] == PROFILE) | (m["cls"] == SHORELINE)
    np.testing.assert_allclose(m["depth"][wet], m["wse"][wet] - dem[wet])
    assert (m["depth"][wet] > 0).all()


def test_mapped_cells_above_the_water_surface_are_unresolved_not_given_a_depth():
    dem = valley()
    flood = np.zeros_like(dem, bool)
    flood[20:81, :40] = True  # rows 20..29 and 71..80 are above 12 m
    m = model(dem, flood)
    # inside the measured reach (marks at x=20 and x=60) the level is 12 m from the marks, so mapped
    # cells at or above 12 m get no depth; beyond the reach FwDET may legitimately set a higher level
    high = flood & (dem >= 12.0)
    high[:, 40:] = False
    high[:, :15] = False
    assert (m["cls"][high] == UNRESOLVED).all()


def test_higher_ground_stays_dry_as_the_level_drops():
    dem = valley()
    wse = np.full(dem.shape, 12.0)
    cls = np.full(dem.shape, PROFILE, np.uint8)
    channel = np.zeros(dem.shape, bool)
    channel[50, :60] = True
    codes = level_codes(dem, wse, cls, channel, step=0.5, max_drop=2.0)
    # freeboard at a cell = 2.0 - 0.1 * |row - 50|; it stays wet while freeboard > drop
    assert codes[50, 10] == 3  # freeboard 2.0 -> wet up to drop 1.5
    assert codes[45, 10] == 2  # freeboard 1.5 -> wet up to drop 1.0
    assert codes[31, 10] == 0  # freeboard 0.1 -> only at the peak


def test_disconnected_low_pocket_does_not_flood_below_the_peak():
    dem = valley()
    wse = np.full(dem.shape, 12.0)
    cls = np.full(dem.shape, PROFILE, np.uint8)
    channel = np.zeros(dem.shape, bool)
    channel[50, :60] = True  # source only west of the ridge at column 70
    codes = level_codes(dem, wse, cls, channel, step=0.5, max_drop=2.0)
    # east of the ridge is just as low but has no connection to the channel
    assert codes[50, 85] == 0
    assert codes[50, 10] > 0


def test_rising_level_only_adds_water():
    rng = np.random.default_rng(1)
    dem = 10 + rng.random((60, 60)) * 2
    wse = np.full(dem.shape, 11.5)
    cls = np.full(dem.shape, PROFILE, np.uint8)
    channel = np.zeros(dem.shape, bool)
    channel[30, :] = True
    codes = level_codes(dem, wse, cls, channel, step=0.1, max_drop=1.5)
    wet = [((codes != 255) & (codes >= k)) for k in range(16)]
    for lower, higher in zip(wet[1:], wet[:-1]):  # drop k+1 (lower water) must be a subset of drop k
        assert not (lower & ~higher).any()


def test_dry_cells_never_get_a_level_code():
    dem = valley()
    wse = np.full(dem.shape, np.nan)
    cls = np.full(dem.shape, DRY, np.uint8)
    codes = level_codes(dem, wse, cls, np.ones(dem.shape, bool))
    assert (codes == 255).all()


def test_downsample_keeps_majority_class_and_mean_surface():
    dem = np.arange(36, dtype=float).reshape(6, 6)
    wse = np.where(dem < 18, dem + 1, np.nan)
    cls = np.where(dem < 18, PROFILE, DRY).astype(np.uint8)
    g, w, k = downsample(dem, wse, cls, 3)
    assert k.shape == (2, 2) and (k[0] == PROFILE).all() and (k[1] == DRY).all()
    assert np.isnan(w[1]).all() and abs(w[0, 0] - (dem[:3, :3].mean() + 1)) < 1e-9
