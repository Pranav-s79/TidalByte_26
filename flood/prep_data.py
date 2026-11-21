"""Download and clip the Meyerland inputs: python -m flood.prep_data  (writes data/)."""
import csv
import json
import math
import os

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

BBOX = (-95.460, 29.674, -95.425, 29.698)  # west, south, east north
HWM_URL = ("https://www.hydroshare.org/resource/615d426f70cc4346875c725b4b8fdc59/"
           "data/contents/Harvey_HWMs_20180322.csv")
DEM_URL = ("/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/"
           "TX_CoastalRegion_2018_A18/TIFF/USGS_1M_15_x26y329_TX_CoastalRegion_2018_A18.tif")
FT = 0.3048
MARK_COLS = ["id", "lat", "lon", "water_elev_m", "depth_m", "uncertainty_m", "quality", "source", "description"]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def marks_from_hwm_csv(src_csv, bbox, out_csv):
    """USGS high-water marks inside bbox with a measured height above ground, in metres. Drops staff names."""
    w, s, e, n = bbox
    out = []
    for r in csv.DictReader(open(src_csv, encoding="utf-8-sig")):
        lat, lon, hag = _num(r["latitude_dd"]), _num(r["longitude_dd"]), _num(r["height_above_gnd"])
        if lat is None or lon is None or not (s <= lat <= n and w <= lon <= e) or not hag or hag <= 0:
            continue
        unc = _num(r.get("uncertainty"))
        out.append([r["hwm_id"], lat, lon, round(float(r["elev_ft"]) * FT, 4), round(hag * FT, 4),
                    round(unc * FT, 4) if unc else 0.06, r["hwmQualityName"].split(":")[0],
                    "usgs_hwm", r["siteDescription"]])
    with open(out_csv, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(MARK_COLS)
        wr.writerows(out)
    return len(out)


def clip_dem(src, bbox, out_tif, cell_m=2.0):
    """Read only the bbox window (works over /vsicurl/), average to cell_m, write float32 nodata -9999."""
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(src) as s:
        win = from_bounds(*transform_bounds("EPSG:4326", s.crs, *bbox), transform=s.transform)
        win = Window(int(win.col_off), int(win.row_off), math.ceil(win.width), math.ceil(win.height))
        factor = cell_m / s.res[0]
        h, w = int(win.height / factor), int(win.width / factor)
        data = s.read(1, window=win, out_shape=(h, w), resampling=Resampling.average, masked=True)
        t = s.window_transform(win) * Affine.scale(win.width / w, win.height / h)
        crs = s.crs
    with rasterio.open(out_tif, "w", driver="GTiff", height=h, width=w, count=1, dtype="float32", crs=crs,
                       transform=t, nodata=-9999, compress="deflate") as d:
        d.write(np.ma.filled(data.astype("float32"), -9999), 1)


def _join(v, sep):
    if isinstance(v, list):
        return sep.join(str(x) for x in v)
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)


def fetch_roads(bbox, out_geojson):
    import osmnx as ox  # heavy import, only needed here

    g = ox.convert.to_undirected(ox.graph_from_bbox(bbox=bbox, network_type="drive"))
    edges = ox.graph_to_gdfs(g, nodes=False)
    feats = []
    for _, e in edges.iterrows():
        bridge = e.get("bridge")
        vals = bridge if isinstance(bridge, list) else [bridge]
        is_bridge = any(_join(v, "") not in (None, "no") for v in vals)
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": [[round(x, 6), round(y, 6)] for x, y in e.geometry.coords]},
                      "properties": {"osm_id": _join(e["osmid"], ","), "name": _join(e.get("name"), " / "),
                                     "highway": _join(e.get("highway"), ","), "is_bridge": is_bridge}})
    with open(out_geojson, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    return len(feats)


def main():
    os.makedirs("data/raw", exist_ok=True)
    raw = "data/raw/Harvey_HWMs_20180322.csv"
    if not os.path.exists(raw):
        r = requests.get(HWM_URL, timeout=120)
        r.raise_for_status()
        open(raw, "wb").write(r.content)
    print("marks:", marks_from_hwm_csv(raw, BBOX, "data/marks.csv"))
    clip_dem(DEM_URL, BBOX, "data/dem.tif")
    print("dem: data/dem.tif", os.path.getsize("data/dem.tif") // 1024, "KB")
    print("roads:", fetch_roads(BBOX, "data/roads.geojson"))


if __name__ == "__main__":
    main()
