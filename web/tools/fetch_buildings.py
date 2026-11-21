"""Fetch OpenStreetMap building footprints for the Meyerland replay box (one-off, web lane).

Writes web/assets/buildings.json, a compact format the 3D command center extrudes:
  {"attribution": ..., "bbox": [w, s, e, n], "default_height_m": 6,
   "buildings": [[height_m, height_source, [lon, lat, lon, lat, ...]], ...]}
height_source: "tag" (OSM height), "levels" (building:levels x 3.2 m) or "default".
Most Meyerland houses have no height in OSM, so most heights are defaults: the UI says
"Building heights approximate".

Run from the repo root:  python web/tools/fetch_buildings.py            (buildings)
                         python web/tools/fetch_buildings.py --context  (waterways, water, parks)
Stdlib only. Data (c) OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BBOX = (-95.460, 29.674, -95.425, 29.698)  # west, south, east, north (spec "Decisions")
DEFAULT_H = 6.0
LEVEL_H = 3.2
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OUT = Path(__file__).resolve().parents[1] / "assets" / "buildings.json"


def query(q: str | None = None) -> dict:
    w, s, e, n = BBOX
    q = q or f'[out:json][timeout:90];way["building"]({s},{w},{n},{e});out geom;'
    body = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": "flood-scene-hackathon/0.1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as exc:  # try the next mirror
            last = exc
            print(f"{url} failed: {exc}", file=sys.stderr)
    raise SystemExit(f"all Overpass endpoints failed: {last}")


def height(tags: dict) -> tuple[float, str]:
    try:
        return round(float(str(tags["height"]).split()[0]), 1), "tag"
    except (KeyError, ValueError):
        pass
    try:
        return round(float(tags["building:levels"]) * LEVEL_H, 1), "levels"
    except (KeyError, ValueError):
        return DEFAULT_H, "default"


def fetch_context() -> None:
    """Waterways and water areas (Brays Bayou etc.) for the dark ground plate: web/assets/context.json."""
    w, s, e, n = BBOX
    pad = 0.004
    b = f"{s - pad},{w - pad},{n + pad},{e + pad}"
    q = (f'[out:json][timeout:90];(way["waterway"~"river|stream|canal|drain|ditch"]({b});'
         f'way["natural"="water"]({b});way["leisure"="park"]({b}););out geom;')
    data = query(q)
    lines, areas, parks = [], [], []
    for el in data.get("elements", []):
        geom = el.get("geometry") or []
        tags = el.get("tags", {})
        coords = [c for p in geom for c in (round(p["lon"], 6), round(p["lat"], 6))]
        if len(coords) < 4:
            continue
        if "waterway" in tags:
            lines.append([tags.get("waterway"), tags.get("name"), coords])
        elif tags.get("natural") == "water" and geom[0] == geom[-1]:
            areas.append(coords[:-2])
        elif tags.get("leisure") == "park" and geom[0] == geom[-1]:
            parks.append(coords[:-2])
    out = OUT.parent / "context.json"
    out.write_text(json.dumps({"attribution": "(c) OpenStreetMap contributors, ODbL", "waterways": lines,
                               "water_areas": areas, "parks": parks}, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(lines)} waterways, {len(areas)} water areas, {len(parks)} parks to {out}")


def main() -> None:
    if "--context" in sys.argv:
        fetch_context()
        return
    data = query()
    out = []
    for el in data.get("elements", []):
        geom = el.get("geometry") or []
        if el.get("type") != "way" or len(geom) < 4:
            continue
        h, src = height(el.get("tags", {}))
        ring = [c for p in geom[:-1] for c in (round(p["lon"], 6), round(p["lat"], 6))]  # drop closing point
        out.append([h, src, ring])
    payload = {
        "attribution": "Buildings (c) OpenStreetMap contributors, ODbL",
        "bbox": list(BBOX),
        "default_height_m": DEFAULT_H,
        "buildings": out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    srcs = {k: sum(1 for b in out if b[1] == k) for k in ("tag", "levels", "default")}
    print(f"wrote {len(out)} buildings to {OUT} ({OUT.stat().st_size // 1024} KB); height sources {srcs}")


if __name__ == "__main__":
    main()
