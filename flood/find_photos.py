"""Find dry street-level reference photos near every point we model: python -m flood.find_photos

A reference photo shows the place, not the flood: curbs, posts and cars whose heights the water may hide.
Source: Mapillary (CC BY-SA 4.0). Needs MAPILLARY_TOKEN in the environment or in .env.
Writes data/reference_photos.json. Image files are not downloaded; open them by page_url.
"""
import argparse
import csv
import datetime
import json
import math
import os
from pathlib import Path

import numpy as np
import requests

API = "https://graph.mapillary.com/images"
FIELDS = "id,captured_at,computed_geometry,geometry,compass_angle,is_pano,creator"
M_PER_DEG_LAT = 111_320.0
FACING_DEG = 45  # a flat photo "faces" the point if the point is within ±45° of its heading
ROOT = Path(__file__).resolve().parents[1]


def token():
    if os.getenv("MAPILLARY_TOKEN"):
        return os.environ["MAPILLARY_TOKEN"]
    env = ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("MAPILLARY_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Set MAPILLARY_TOKEN (environment or .env). Get one at mapillary.com/dashboard/developers")


def points(marks_csv, cameras_json, observations_json, extra=()):
    pts = [{"id": r["id"], "kind": "usgs_mark", "label": r["description"], "lat": float(r["lat"]),
            "lon": float(r["lon"])} for r in csv.DictReader(open(marks_csv))]
    if os.path.exists(cameras_json):
        pts += [{"id": c["id"], "kind": "camera", "label": f"{c['road']} at {c['cross_street']}",
                 "lat": c["lat"], "lon": c["lon"]} for c in json.load(open(cameras_json))["cameras"]]
    if os.path.exists(observations_json):
        pts += [{"id": o["id"], "kind": "photo", "label": o["photo"], "lat": o["lat"], "lon": o["lon"]}
                for o in json.load(open(observations_json))]
    return pts + [{"id": label, "kind": "extra", "label": label, "lat": lat, "lon": lon} for label, lat, lon in extra]


def _dist_bearing(lat1, lon1, lat2, lon2):
    """Metres and compass bearing from point 1 to point 2. ponytail: flat-earth, fine under ~1 km."""
    dx = (lon2 - lon1) * M_PER_DEG_LAT * math.cos(math.radians(lat1))
    dy = (lat2 - lat1) * M_PER_DEG_LAT
    return math.hypot(dx, dy), math.degrees(math.atan2(dx, dy)) % 360


def matches(point, images, radius_m):
    """Images within radius_m, ones that can see the point first, then nearest first."""
    out = []
    for im in images:
        geom = im.get("computed_geometry") or im.get("geometry")
        if not geom:
            continue
        lon, lat = geom["coordinates"]
        dist, bearing = _dist_bearing(lat, lon, point["lat"], point["lon"])
        if dist > radius_m:
            continue
        heading = im.get("compass_angle")
        off = None if heading is None else abs((bearing - heading + 180) % 360 - 180)
        faces = bool(im.get("is_pano")) or dist < 5 or (off is not None and off <= FACING_DEG)
        taken = datetime.datetime.fromtimestamp(im["captured_at"] / 1000, datetime.timezone.utc)
        out.append({"source": "mapillary", "id": im["id"], "lat": round(lat, 6), "lon": round(lon, 6),
                    "distance_m": round(dist, 1), "faces_point": faces, "is_pano": bool(im.get("is_pano")),
                    "compass_angle": heading, "captured_at": taken.date().isoformat(),
                    "page_url": f"https://www.mapillary.com/app/?pKey={im['id']}",
                    "license": "CC BY-SA 4.0", "creator": (im.get("creator") or {}).get("username")})
    return sorted(out, key=lambda m: (not m["faces_point"], m["distance_m"]))


def pano_view(pano, pano_heading, yaw, fov=90.0, size=(1024, 768), pitch=0.0):
    """Flat camera view cut from an equirectangular 360° panorama (H x W x 3 array).

    ponytail: assumes the pano's centre column points at its compass heading (Mapillary's convention
    for these Streetside panos); check one view by eye before trusting a new source.
    """
    from scipy.ndimage import map_coordinates

    w, h = size
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    u, v = np.meshgrid(np.arange(w) - w / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
    p = math.radians(pitch)
    y, z = v * math.cos(p) - f * math.sin(p), v * math.sin(p) + f * math.cos(p)  # tilt up by pitch
    lon = np.arctan2(u, z) + math.radians(yaw - pano_heading)
    lat = -np.arctan2(y, np.hypot(u, z))
    ph, pw = pano.shape[:2]
    cols = ((lon / (2 * math.pi) + 0.5) % 1.0) * pw - 0.5
    rows = (0.5 - lat / math.pi) * ph - 0.5
    return np.stack([map_coordinates(pano[..., c], [rows, cols], order=1, mode="wrap")
                     for c in range(pano.shape[2])], axis=-1)


def bearing_to(from_lat, from_lon, to_lat, to_lon):
    return _dist_bearing(from_lat, from_lon, to_lat, to_lon)[1]


def fetch(lat, lon, radius_m, tok, get=requests.get):
    dlat = radius_m / M_PER_DEG_LAT
    dlon = dlat / math.cos(math.radians(lat))
    r = get(API, timeout=30, params={"access_token": tok, "fields": FIELDS, "limit": 500,
                                      "bbox": f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"})
    r.raise_for_status()
    return r.json().get("data", [])


def view_choice(found):
    """Panorama to aim at the point. ponytail: under ~10 m the bearing is GPS noise, so prefer 10-40 m."""
    panos = [m for m in found if m["is_pano"]]
    return next((m for m in panos if 10 <= m["distance_m"] <= 40), panos[0] if panos else None)


def save_view(pt, m, tok, out_dir, get=requests.get):
    """Download the panorama, cut a 75° view facing the point, save it as out_dir/<point id>.jpg."""
    from PIL import Image

    url = get(f"https://graph.mapillary.com/{m['id']}", timeout=30,
              params={"access_token": tok, "fields": "thumb_2048_url"}).json()["thumb_2048_url"]
    r = get(url, timeout=60)
    r.raise_for_status()
    pano = np.asarray(Image.open(__import__("io").BytesIO(r.content)).convert("RGB"))
    yaw = bearing_to(m["lat"], m["lon"], pt["lat"], pt["lon"])
    Image.fromarray(pano_view(pano, m["compass_angle"], yaw, fov=75, size=(960, 640))).save(
        Path(out_dir) / f"{pt['id']}.jpg", "JPEG", quality=85)
    return {**m, "file": f"{pt['id']}.jpg", "facing_deg": round(yaw)}


def _extra(s):
    label, lat, lon = s.rsplit(",", 2)
    return label, float(lat), float(lon)


def main():
    p = argparse.ArgumentParser(description="Find street-level reference photos near modeled points")
    p.add_argument("--marks", default="data/marks.csv")
    p.add_argument("--cameras", default="data/cameras.json")
    p.add_argument("--observations", default="data/observations.json")
    p.add_argument("--point", type=_extra, action="append", default=[], help='"label,LAT,LON" (repeatable)')
    p.add_argument("--radius", type=float, default=50.0, help="metres")
    p.add_argument("--keep", type=int, default=5, help="matches kept per point")
    p.add_argument("--out", default="data/reference_photos.json")
    p.add_argument("--views", help="also save a view facing each USGS mark here, e.g. web/photos/refs")
    a = p.parse_args()
    tok, results, views = token(), [], {}
    if a.views:
        os.makedirs(a.views, exist_ok=True)
    for pt in points(a.marks, a.cameras, a.observations, a.point):
        found = matches(pt, fetch(pt["lat"], pt["lon"], a.radius, tok), a.radius)
        best = view_choice(found) if a.views and pt["kind"] == "usgs_mark" else None
        if best:
            views[pt["id"]] = save_view(pt, best, tok, a.views)
        results.append({**pt, "radius_m": a.radius, "n_found": len(found),
                        "n_facing": sum(m["faces_point"] for m in found), "matches": found[:a.keep]})
        dates = sorted(m["captured_at"] for m in found)
        print(f"{pt['kind']:9} {pt['id']:>16}  {len(found):3} photos, {results[-1]['n_facing']:3} facing"
              + (f", nearest {found[0]['distance_m']:.0f} m, {dates[0]}..{dates[-1]}" if found else "")
              + f"  {pt['label'][:45]}")
    with open(a.out, "w") as f:
        json.dump({"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "note": "Dry reference photos of the place, not flood photos. Check capture date: "
                           "streets may have changed since the event.", "points": results}, f, indent=1)
    if a.views:
        with open(Path(a.views) / "index.json", "w") as f:
            json.dump(views, f, indent=1)


if __name__ == "__main__":
    main()
