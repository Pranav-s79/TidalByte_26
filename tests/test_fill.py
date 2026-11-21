import numpy as np
from rasterio.transform import from_origin

from flood.fill import DRY, LIKELY, POSSIBLE, UNKNOWN, Mark, classify, fill_depth, level_surfaces, run_fill

T = from_origin(0, 10, 2, 2)  # 5x5 grid of 2 m cells, top-left corner at (0, 10)


def bowl():
    return np.array([[3, 3, 3, 3, 3],
                     [3, 1, 1, 1, 3],
                     [3, 1, 0, 1, 3],
                     [3, 1, 1, 1, 3],
                     [3, 3, 3, 3, 3]], float)


def test_bowl_fills_to_level():
    d = fill_depth(bowl(), np.full((5, 5), 2.0), seeds=[(2, 2)])
    assert d[2, 2] == 2.0 and d[1, 1] == 1.0 and d[0, 0] == 0.0


def test_disconnected_basin_stays_dry():
    d = fill_depth(np.array([[0, 5, 0]], float), np.full((1, 3), 2.0), seeds=[(0, 0)])
    assert d[0, 0] == 2.0 and d[0, 2] == 0.0


def test_beyond_radius_is_unknown():
    low, high = level_surfaces((5, 5), T, [Mark(1, 9, 2, 2)], radius_m=3)
    assert not np.isnan(low[0, 0]) and np.isnan(low[4, 4])


def test_idw_blends_two_marks():
    low, _ = level_surfaces((1, 3), from_origin(0, 2, 2, 2), [Mark(1, 1, 10, 10), Mark(5, 1, 12, 12)])
    assert low[0, 0] == 10 and low[0, 2] == 12 and abs(low[0, 1] - 11) < 1e-9


def test_classify():
    lo, hi = np.array([1.0, 0.0, 0.0, np.nan]), np.array([1.2, 0.3, 0.0, np.nan])
    assert classify(lo, hi).tolist() == [LIKELY, POSSIBLE, DRY, UNKNOWN]


def test_mark_outside_grid_is_skipped():
    *_, cls = run_fill(bowl(), T, [Mark(500, 500, 2, 2)])
    assert (cls == UNKNOWN).all()


def test_mark_on_nodata_is_skipped():
    dem = bowl(); dem[2, 2] = np.nan
    *_, cls = run_fill(dem, T, [Mark(5, 5, 2, 2)])
    assert (cls == UNKNOWN).all()


def test_run_fill_low_and_high_runs():
    # level 0.5..1.5 at the bowl centre: low run wets only the centre, high run also the ring
    low, high, cls = run_fill(bowl(), T, [Mark(5, 5, 0.5, 1.5)])
    assert cls[2, 2] == LIKELY and cls[1, 1] == POSSIBLE and cls[0, 0] == DRY
