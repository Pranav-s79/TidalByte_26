import numpy as np
from rasterio.transform import from_origin

from flood.fill import DRY, LIKELY, POSSIBLE, UNKNOWN
from flood.roads import road_status

T = from_origin(0, 10, 2, 2)


def grid():
    cls = np.array([[UNKNOWN] * 5, [POSSIBLE] * 5, [LIKELY] * 5, [DRY] * 5, [DRY] * 5], np.int8)
    depth_high = np.array([[np.nan] * 5, [0.5] * 5, [1.0] * 5, [0.0] * 5, [0.0] * 5])
    return depth_high, cls


def test_statuses():
    depth_high, cls = grid()
    out = road_status(
        [[(0.5, 5), (9.5, 5)],      # along row 2
         [(0.5, 9), (9.5, 9)],      # along row 0
         [(0.5, 1), (9.5, 1)],      # along row 4
         [(5, 9.5), (5, 6.5)],      # crosses rows 0 and 1: partly unknown
         [(0.5, 5), (9.5, 5)]],     # row 2, but a bridge
        [False, False, False, False, True], depth_high, cls, T, step_m=1)
    assert [o["status"] for o in out] == ["likely_flooded", "unknown", "no_flooding_estimated",
                                          "possibly_flooded", "bridge_not_estimated"]
    assert [o["max_depth_m"] for o in out] == [1.0, None, 0.0, 0.5, None]


def test_road_outside_grid_is_unknown():
    depth_high, cls = grid()
    out = road_status([[(100, 100), (120, 100)]], [False], depth_high, cls, T, step_m=1)
    assert out == [{"status": "unknown", "max_depth_m": None}]
