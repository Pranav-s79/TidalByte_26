"""Bake the dark terrain basemap for the 3D command center (web lane, one-off).

Writes web/assets/basemap.png: a lon/lat-aligned image of the replay box with
- lidar hillshade, tinted darker/bluer in low ground (so low-lying areas read at a glance),
- OSM water areas, Brays Bayou and other waterways, parks,
- a faint 100 m survey grid.
The page drapes it over the lidar terrain as a single imagery tile (no tile service, no key).

Run from the repo root:  python web/tools/make_basemap.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[2]
BBOX = (-95.460, 29.674, -95.425, 29.698)
STEP = 0.00003  # degrees per pixel (~3 m)
OUT = ROOT / "web" / "assets" / "basemap.png"


def main() -> None:
    w, s, e, n = BBOX
    width, height = round((e - w) / STEP), round((n - s) / STEP)
    dst_t = from_bounds(w, s, e, n, width, height)
    dem = np.full((height, width), np.nan, np.float32)
    with rasterio.open(ROOT / "data" / "dem.tif") as src:
        reproject(rasterio.band(src, 1), dem, dst_transform=dst_t, dst_crs="EPSG:4326",
                  src_nodata=src.nodata, dst_nodata=np.nan, resampling=Resampling.bilinear)
    dem = np.where(np.isnan(dem), np.nanmedian(dem), dem)

    # hillshade (sun from the north-west, 40 deg), slopes in metres
    dx = STEP * 111_320 * math.cos(math.radians((s + n) / 2))
    dy = STEP * 110_574
    gy, gx = np.gradient(dem * 2.0, dy, dx)  # 2x vertical exaggeration for the shading only
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315), math.radians(40)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(0.55 + 0.6 * shade, 0.35, 1.25)

    # elevation tint: low ground deep blue, high ground slate
    lo, hi = np.percentile(dem, [3, 97])
    t = np.clip((dem - lo) / (hi - lo), 0, 1)[..., None]
    low, high = np.array([9, 22, 44], float), np.array([30, 39, 56], float)
    rgb = (low * (1 - t) + high * t) * shade[..., None]

    ctx = json.load(open(ROOT / "web" / "assets" / "context.json", encoding="utf-8"))

    def poly(rings):
        return [{"type": "Polygon", "coordinates": [[[r[i], r[i + 1]] for i in range(0, len(r), 2)] + [[r[0], r[1]]]]}
                for r in rings if len(r) >= 6]

    def paint(geoms, color, alpha, all_touched=False):
        if not geoms:
            return
        m = rasterize(((g, 1) for g in geoms), out_shape=(height, width), transform=dst_t, fill=0,
                      all_touched=all_touched, dtype="uint8").astype(bool)
        rgb[m] = rgb[m] * (1 - alpha) + np.array(color, float) * alpha

    paint(poly(ctx.get("parks", [])), (16, 40, 34), 0.55)
    paint(poly(ctx.get("water_areas", [])), (14, 44, 76), 0.9)
    for kind, _name, c in ctx.get("waterways", []):
        line = {"type": "LineString", "coordinates": [[c[i], c[i + 1]] for i in range(0, len(c), 2)]}
        # rough channel width in pixels: rivers wider than ditches
        widths = 3 if kind in ("river", "drain") and _name else 1
        for k in range(widths):
            off = (k - widths // 2) * STEP
            shifted = {"type": "LineString", "coordinates": [[x, y + off] for x, y in line["coordinates"]]}
            paint([shifted], (31, 77, 122), 0.95, all_touched=True)

    # 100 m survey grid
    img = np.clip(rgb, 0, 255)
    alpha = np.full((height, width), 255, np.uint8)
    step_x = 100 / (111_320 * math.cos(math.radians((s + n) / 2))) / STEP
    step_y = 100 / 110_574 / STEP
    for xg in np.arange(0, width, step_x):
        img[:, int(xg)] = img[:, int(xg)] * 0.8 + np.array([125, 211, 252]) * 0.2 * 0.35
    for yg in np.arange(0, height, step_y):
        img[int(yg), :] = img[int(yg), :] * 0.8 + np.array([125, 211, 252]) * 0.2 * 0.35

    out = np.dstack([img.astype(np.uint8), alpha]).transpose(2, 0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", driver="PNG", width=width, height=height, count=4, dtype="uint8") as dst:
        dst.write(out)
    print(f"wrote {OUT} {width}x{height} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
