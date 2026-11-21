"""Data in, map layers out: python -m flood.run  (data/ -> web/data/)."""
import argparse
import csv
import datetime
import json
import math
import os

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.transform import rowcol
from rasterio.warp import transform as warp
from rasterio.warp import transform_geom

from flood.fill import LIKELY, POSSIBLE, UNKNOWN, Mark, run_fill
from flood.roads import road_status

BANDS = [(0.0, 0.3, "0–0.3 m"), (0.3, 0.6, "0.3–0.6 m"), (0.6, 1.2, "0.6–1.2 m"), (1.2, math.inf, "over 1.2 m")]
OBS_PHRASE = {"ai_proposed": "AI-proposed: awaiting review", "confirmed": "Confirmed by reviewer",
              "rejected": "Rejected by reviewer", "needs_review": "Needs review: AI reading failed"}


def _feature(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def _polygons(mask, transform, crs, props):
    if not mask.any():
        return []
    return [_feature(transform_geom(crs, "EPSG:4326", g, precision=6), props)
            for g, _ in shapes(mask.astype(np.uint8), mask=mask, transform=transform)]


def _dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def build_outputs(marks_csv, dem_tif, roads_geojson, observations_json, out_dir, radius_m=400.0):
    with rasterio.open(dem_tif) as src:
        dem = src.read(1).astype(float)
        if src.nodata is not None:
            dem[dem == src.nodata] = np.nan
        transform, crs = src.transform, src.crs

    def to_xy(lons, lats):
        return warp("EPSG:4326", crs, list(lons), list(lats)) if lons else ([], [])

    def ground_at(x, y):
        r, c = (int(v) for v in rowcol(transform, x, y))
        inside = 0 <= r < dem.shape[0] and 0 <= c < dem.shape[1]
        return dem[r, c] if inside and not np.isnan(dem[r, c]) else None

    rows = list(csv.DictReader(open(marks_csv)))
    xs, ys = to_xy([float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows])
    marks = [Mark(x, y, float(r["water_elev_m"]) - float(r["uncertainty_m"]),
                  float(r["water_elev_m"]) + float(r["uncertainty_m"])) for r, x, y in zip(rows, xs, ys)]

    obs = json.load(open(observations_json)) if observations_json and os.path.exists(observations_json) else []
    oxs, oys = to_xy([o["lon"] for o in obs], [o["lat"] for o in obs])
    n_photos = 0
    for o, x, y in zip(obs, oxs, oys):  # only reviewer-confirmed readings with a depth change the water
        g = ground_at(x, y)
        if o["status"] == "confirmed" and o["depth_m_low"] is not None and g is not None:
            marks.append(Mark(x, y, g + o["depth_m_low"], g + o["depth_m_high"]))
            n_photos += 1

    depth_low, depth_high, cls = run_fill(dem, transform, marks, radius_m)

    water = []
    for lo, hi, band in BANDS:
        with np.errstate(invalid="ignore"):
            water += _polygons((cls == LIKELY) & (depth_low > lo) & (depth_low <= hi), transform, crs,
                               {"status": "likely", "depth_band": band})
            water += _polygons((cls == POSSIBLE) & (depth_high > lo) & (depth_high <= hi), transform, crs,
                               {"status": "possible", "depth_band": band})
    unknown = _polygons(cls == UNKNOWN, transform, crs, {"status": "unknown"})

    roads = json.load(open(roads_geojson))
    lines = []
    for f in roads["features"]:
        lon, lat = zip(*f["geometry"]["coordinates"])
        lines.append(list(zip(*to_xy(lon, lat))))
    statuses = road_status(lines, [f["properties"]["is_bridge"] for f in roads["features"]],
                           depth_high, cls, transform)
    for f, s in zip(roads["features"], statuses):
        f["properties"].update(s)

    pins = [_feature({"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                     {"kind": "usgs_measured", "id": r["id"], "status": "usgs_measured",
                      "depth_m_low": float(r["depth_m"]), "depth_m_high": float(r["depth_m"]),
                      "label": f"USGS measured (surveyed after the flood) · {float(r['depth_m']):.2f} m deep",
                      "quality": r["quality"], "description": r["description"], "photo": None, "obstacles": []})
            for r in rows]
    for o in obs:
        depth = ("depth unknown (no reference object)" if o["depth_m_low"] is None
                 else f"{o['depth_m_low']:.2f}–{o['depth_m_high']:.2f} m deep")
        pins.append(_feature({"type": "Point", "coordinates": [o["lon"], o["lat"]]},
                             {"kind": "ai_photo", "id": o["id"], "status": o["status"],
                              "depth_m_low": o["depth_m_low"], "depth_m_high": o["depth_m_high"],
                              "label": f"{OBS_PHRASE.get(o['status'], o['status'])} · {depth}",
                              "photo": o["photo"], "obstacles": o["obstacles"], "reasoning": o["reasoning"],
                              "confidence": o["confidence"], "taken_at": o["taken_at"]}))

    label = f"Estimated peak extent from {len(rows)} USGS high-water marks"
    if n_photos:
        label += f" + {n_photos} confirmed photo{'s' if n_photos != 1 else ''}"
    meta = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "n_marks": len(rows), "n_confirmed_photos": n_photos, "radius_m": radius_m,
            "label": label + ". Not measured water. Not an all-clear."}

    os.makedirs(out_dir, exist_ok=True)
    fc = lambda feats: {"type": "FeatureCollection", "features": feats}  # noqa: E731
    _dump(os.path.join(out_dir, "water.geojson"), fc(water))
    _dump(os.path.join(out_dir, "unknown.geojson"), fc(unknown))
    _dump(os.path.join(out_dir, "roads_status.geojson"), roads)
    _dump(os.path.join(out_dir, "pins.geojson"), fc(pins))
    _dump(os.path.join(out_dir, "meta.json"), meta)
    return meta


def main():
    p = argparse.ArgumentParser(description="Turn marks, DEM, roads and observations into map layers")
    p.add_argument("--marks", default="data/marks.csv")
    p.add_argument("--dem", default="data/dem.tif")
    p.add_argument("--roads", default="data/roads.geojson")
    p.add_argument("--observations", default="data/observations.json")
    p.add_argument("--out", default="web/data")
    p.add_argument("--radius", type=float, default=400.0)
    a = p.parse_args()
    print(json.dumps(build_outputs(a.marks, a.dem, a.roads, a.observations, a.out, a.radius), indent=2))


if __name__ == "__main__":
    main()
