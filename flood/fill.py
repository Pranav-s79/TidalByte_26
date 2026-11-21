"""Bathtub fill: spread measured water levels over the ground model.

Not a hydraulic model: ignores drainage, flow and timing (see spec).
"""
from dataclasses import dataclass

import numpy as np
from rasterio.transform import rowcol
from scipy import ndimage

UNKNOWN = -1
DRY = 0
POSSIBLE = 1
LIKELY = 2


@dataclass(frozen=True)
class Mark:
    x: float  # DEM CRS, metres
    y: float
    level_low: float  # water surface elevation, m NAVD88
    level_high: float


def _cell_centers(shape, transform):
    rows, cols = np.indices(shape)
    xs = transform.c + (cols + 0.5) * transform.a + (rows + 0.5) * transform.b
    ys = transform.f + (cols + 0.5) * transform.d + (rows + 0.5) * transform.e
    return xs, ys


def level_surfaces(shape, transform, marks, radius_m=400.0, power=2.0):
    """Inverse-distance blend of mark levels; NaN where no mark is within radius_m."""
    xs, ys = _cell_centers(shape, transform)
    wsum, lo, hi = np.zeros(shape), np.zeros(shape), np.zeros(shape)
    exact = []
    for m in marks:
        d = np.hypot(xs - m.x, ys - m.y)
        w = np.where(d <= radius_m, 1.0 / np.maximum(d, 0.01) ** power, 0.0)
        wsum += w
        lo += w * m.level_low
        hi += w * m.level_high
        exact.append((d < 0.01, m))
    with np.errstate(invalid="ignore", divide="ignore"):
        lo, hi = lo / wsum, hi / wsum  # 0/0 -> NaN = unknown
    for on_mark, m in exact:  # a cell sitting on a mark takes its level exactly
        lo[on_mark], hi[on_mark] = m.level_low, m.level_high
    return lo, hi


def fill_depth(dem, level, seeds):
    """Depth where ground is below level AND connected (8-neighbour) to a seed cell."""
    with np.errstate(invalid="ignore"):
        wet = (level > dem) & ~np.isnan(dem)
    for r, c in seeds:
        wet[r, c] = True
    labels, _ = ndimage.label(wet, structure=np.ones((3, 3)))
    keep = np.isin(labels, [labels[r, c] for r, c in seeds if labels[r, c]])
    depth = np.where(keep, np.clip(level - dem, 0, None), 0.0)
    depth[np.isnan(level) | np.isnan(dem)] = np.nan
    return depth


def classify(depth_low, depth_high):
    cls = np.full(depth_high.shape, DRY, np.int8)
    with np.errstate(invalid="ignore"):
        cls[depth_high > 0] = POSSIBLE
        cls[depth_low > 0] = LIKELY
    cls[np.isnan(depth_high)] = UNKNOWN
    return cls


def run_fill(dem, transform, marks, radius_m=400.0):
    """Low and high fills plus classes. Marks outside the grid or on nodata are skipped."""
    valid, seeds = [], []
    for m in marks:
        r, c = rowcol(transform, m.x, m.y)
        r, c = int(r), int(c)
        if 0 <= r < dem.shape[0] and 0 <= c < dem.shape[1] and not np.isnan(dem[r, c]):
            valid.append(m)
            seeds.append((r, c))
    if not valid:
        nan = np.full(dem.shape, np.nan)
        return nan, nan.copy(), classify(nan, nan)
    low, high = level_surfaces(dem.shape, transform, valid, radius_m)
    depth_low, depth_high = fill_depth(dem, low, seeds), fill_depth(dem, high, seeds)
    return depth_low, depth_high, classify(depth_low, depth_high)
