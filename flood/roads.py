"""Road status: sample the flood grid along each road line (DEM CRS)."""
import math

import numpy as np
from rasterio.transform import rowcol

from flood.fill import LIKELY, POSSIBLE, UNKNOWN


def _samples(line, step_m):
    pts = [line[0]]
    for (x0, y0), (x1, y1) in zip(line, line[1:]):
        n = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / step_m))
        pts += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return pts


def road_status(lines_xy, is_bridge, depth_high, cls, transform, step_m=5.0):
    out = []
    h, w = cls.shape
    for line, bridge in zip(lines_xy, is_bridge):
        if bridge:  # bare-earth DEM has no deck: a depth here would be the channel's
            out.append({"status": "bridge_not_estimated", "max_depth_m": None})
            continue
        known_cls, depths = [], []
        for x, y in _samples(line, step_m):
            r, c = (int(v) for v in rowcol(transform, x, y))
            if 0 <= r < h and 0 <= c < w and cls[r, c] != UNKNOWN:
                known_cls.append(cls[r, c])
                depths.append(depth_high[r, c])
        if not known_cls:
            out.append({"status": "unknown", "max_depth_m": None})
            continue
        status = ("likely_flooded" if LIKELY in known_cls else
                  "possibly_flooded" if POSSIBLE in known_cls else "no_flooding_estimated")
        out.append({"status": status, "max_depth_m": round(float(np.nanmax(depths)), 2)})
    return out
