"""Bake the dark terrain basemap for the 3D command center (web lane, one-off).

Writes web/assets/basemap.png: a lon/lat-aligned image of the replay box with
- lidar hillshade, tinted slightly bluer in low ground (low-lying areas read at a glance),
- OSM water areas, waterways and parks,
- every OSM road as a quiet, anti-aliased line (major roads a little stronger), so ordinary
  streets need no 3D overlay,
- edges that fade to transparent over the outer ~250 m, so there is no hard rectangle.
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
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
BBOX = (-95.460, 29.674, -95.425, 29.698)
STEP = 0.00002  # degrees per pixel (~2 m)
SS = 2          # supersampling for the vector layers (anti-aliasing)
FADE_M = 250
OUT = ROOT / "web" / "assets" / "basemap.png"
MAJOR = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link"}


def main() -> None:
    w, s, e, n = BBOX
    width, height = round((e - w) / STEP), round((n - s) / STEP)
    dst_t = from_bounds(w, s, e, n, width, height)
    dem = np.full((height, width), np.nan, np.float32)
    with rasterio.open(ROOT / "data" / "dem.tif") as src:
        reproject(rasterio.band(src, 1), dem, dst_transform=dst_t, dst_crs="EPSG:4326",
                  src_nodata=src.nodata, dst_nodata=np.nan, resampling=Resampling.bilinear)
    dem = np.where(np.isnan(dem), np.nanmedian(dem), dem)
    dem = ndimage.gaussian_filter(dem, 0.8)  # take the lidar speckle out of the shading

    mx = 111_320 * math.cos(math.radians((s + n) / 2))
    dx, dy = STEP * mx, STEP * 110_574
    gy, gx = np.gradient(dem * 2.5, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(315), math.radians(42)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(0.62 + 0.55 * shade, 0.42, 1.2)

    lo, hi = np.percentile(dem, [3, 97])
    t = np.clip((dem - lo) / (hi - lo), 0, 1)[..., None]
    low, high = np.array([12, 24, 42], float), np.array([31, 37, 48], float)
    rgb = (low * (1 - t) + high * t) * shade[..., None]

    big_t = from_bounds(w, s, e, n, width * SS, height * SS)

    def coverage(geoms, all_touched=False):
        """Anti-aliased coverage 0..1: rasterise at SS x and box-average down."""
        if not geoms:
            return np.zeros((height, width))
        m = rasterize(((g, 1) for g in geoms), out_shape=(height * SS, width * SS), transform=big_t, fill=0,
                      all_touched=all_touched, dtype="uint8").astype(float)
        return m.reshape(height, SS, width, SS).mean(axis=(1, 3))

    def paint(cov, color, alpha):
        a = (cov * alpha)[..., None]
        rgb[:] = rgb * (1 - a) + np.array(color, float) * a

    ctx = json.load(open(ROOT / "web" / "assets" / "context.json", encoding="utf-8"))

    def polys(rings):
        return [{"type": "Polygon", "coordinates": [[[r[i], r[i + 1]] for i in range(0, len(r), 2)] + [[r[0], r[1]]]]}
                for r in rings if len(r) >= 6]

    def buffered_lines(lines, metres):
        from shapely.geometry import LineString, mapping
        deg = metres / mx
        return [mapping(LineString(c).buffer(deg, cap_style=1, join_style=1)) for c in lines if len(c) >= 2]

    paint(coverage(polys(ctx.get("parks", []))), (18, 38, 36), 0.5)
    paint(coverage(polys(ctx.get("water_areas", []))), (16, 44, 72), 0.85)
    ways = [[[c[i], c[i + 1]] for i in range(0, len(c), 2)] for kind, name, c in ctx.get("waterways", [])]
    channel = [[[c[i], c[i + 1]] for i in range(0, len(c), 2)] for kind, name, c in ctx.get("waterways", []) if name == "Brays Bayou"]
    paint(coverage(buffered_lines(ways, 1.6)), (26, 60, 96), 0.8)
    paint(coverage(buffered_lines(channel, 6.0)), (22, 56, 92), 0.75)

    roads = json.load(open(ROOT / "data" / "roads.geojson", encoding="utf-8"))["features"]
    minor = [f["geometry"]["coordinates"] for f in roads if f["properties"]["highway"] not in MAJOR]
    major = [f["geometry"]["coordinates"] for f in roads if f["properties"]["highway"] in MAJOR]
    paint(coverage(buffered_lines(minor, 2.2)), (70, 80, 96), 0.38)
    paint(coverage(buffered_lines(major, 4.0)), (88, 98, 114), 0.45)

    img = np.clip(rgb, 0, 255).astype(np.uint8)
    # fade the outer edge to transparent so the box never shows as a hard rectangle
    fx = np.minimum(np.arange(width), np.arange(width)[::-1]) * dx / FADE_M
    fy = np.minimum(np.arange(height), np.arange(height)[::-1]) * dy / FADE_M
    fade = np.clip(np.minimum(fx[None, :], fy[:, None]), 0, 1)
    alpha = (255 * (fade * fade * (3 - 2 * fade))).astype(np.uint8)

    out = np.dstack([img, alpha]).transpose(2, 0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", driver="PNG", width=width, height=height, count=4, dtype="uint8") as dst:
        dst.write(out)
    aux = OUT.with_suffix(".png.aux.xml")
    if aux.exists():
        aux.unlink()
    print(f"wrote {OUT} {width}x{height} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
