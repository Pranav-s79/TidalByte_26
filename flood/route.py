"""Least-deep routing for dispatchers (docs/routing-and-prediction.md §3–5).

A person at the agency sets the depth limit; the router never sets, suggests or raises it. Unknown roads stay
routable (most roads have no camera) but every option reports its unobserved distance. Output reports numbers
and their source only.
"""
import argparse
import datetime
import json
import math
import re

import networkx as nx

from flood.predict import depth_at

SNAP_MAX_M = 150.0
DEFAULT_SPEED_KMH = 30.0
UNOBSERVED_PENALTY = 5.0     # option C: unknown road length counts 5x
ALERT_RISE_M = 0.05          # §5: deepest point rose by 5 cm or more
EPS = 1e-9
UNKNOWN = "Unknown: no data"
REPLAY_LABEL = "REPLAY · Harvey 2017 estimated peak · not current conditions"
NO_ROUTE = "No route within the depth limit you set"
CAVEATS = [
    "Roads with no data are counted as unobserved, not dry.",
    "A road's deepest estimated point is applied along its whole length.",
    "Every road is treated as two-way.",
    f"Arrival times assume the posted speed limit, or {DEFAULT_SPEED_KMH:.0f} km/h where none is mapped.",
]
REPLAY_CAVEATS = ["Depths are the estimated peak of the whole event, not one moment in time."]


def _dist_m(a, b):
    """Great-circle distance between two (lon, lat) points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def _key(p):
    return (round(float(p[0]), 6), round(float(p[1]), 6))


def _speed_kmh(maxspeed):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(mph)?", str(maxspeed or ""))
    if not m:
        return DEFAULT_SPEED_KMH
    v = float(m.group(1))
    return v * 1.609344 if m.group(2) else v


def build_graph(roads_fc):
    """One edge per pair of consecutive road points; roads that meet share a point.

    Each edge keeps its road's Estimated depth (max_depth_m, the fill's high run) or None (Unknown).
    """
    G = nx.Graph()
    for f in roads_fc["features"]:
        geom, props = f["geometry"], f["properties"]
        lines = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        est = props.get("max_depth_m")
        data = {"est_depth_m": None if est is None else float(est), "osm_id": str(props.get("osm_id")),
                "name": props.get("name"), "is_bridge": bool(props.get("is_bridge")),
                "speed_kmh": _speed_kmh(props.get("maxspeed"))}
        for line in lines:
            for a, b in zip(line, line[1:]):
                ka, kb = _key(a), _key(b)
                if ka == kb:
                    continue
                old = G.get_edge_data(ka, kb)
                # Two roads on the same stretch: keep the deeper known depth (the cautious one).
                if old and (data["est_depth_m"] is None or
                            (old["est_depth_m"] is not None and old["est_depth_m"] >= data["est_depth_m"])):
                    continue
                length = _dist_m(ka, kb)
                G.add_edge(ka, kb, length_m=length, travel_s=length / (data["speed_kmh"] / 3.6), **data)
    return G


def _hhmm(iso):
    return datetime.datetime.fromisoformat(iso).strftime("%H:%M")


def set_planning_depths(G, start_node, cameras=None, depart=None):
    """§3: the depth the router plans on, per edge, written to edge["depth_m"] and edge["source"].

    cameras: [{"id", "osm_ids": [...], "readings": [(time, depth_m, sigma_m), ...]}], used only with depart.
    A camera road uses mean + sigma at the vehicle's arrival time. If the camera can't give a depth (too few
    fresh readings, or arrival more than 60 min ahead) the road falls back to its Estimated depth, else Unknown.
    """
    for _, _, e in G.edges(data=True):
        e["depth_m"] = e["est_depth_m"]
        e["source"] = "Estimated" if e["est_depth_m"] is not None else UNKNOWN
        e["camera_ids"] = []
    if not cameras or depart is None:
        return
    depart = datetime.datetime.fromisoformat(depart) if isinstance(depart, str) else depart
    arrive_s = nx.single_source_dijkstra_path_length(G, start_node, weight="travel_s")
    by_road = {}
    for cam in cameras:
        for osm_id in cam["osm_ids"]:
            by_road.setdefault(str(osm_id), []).append(cam)
    for u, v, e in G.edges(data=True):
        cams = by_road.get(e["osm_id"])
        if not cams:
            continue
        e["camera_ids"] = [str(c["id"]) for c in cams]
        secs = min(arrive_s.get(u, math.inf), arrive_s.get(v, math.inf))
        if math.isinf(secs):
            continue
        arrival = depart + datetime.timedelta(seconds=secs)
        best = None
        for cam in cams:  # several cameras on one road: plan on the deepest
            d = depth_at(cam["readings"], depart, arrival)
            if d is not None and (best is None or d["planning_m"] > best[1]["planning_m"]):
                best = (cam, d)
        if best is None:
            continue
        cam, d = best
        e["depth_m"] = d["planning_m"]
        e["source"] = (f"Predicted for {_hhmm(d['for_time'])}" if d["source"] == "Predicted"
                       else f"Observed · camera {cam['id']} · {_hhmm(d['for_time'])}")


def _snap(G, lonlat, which):
    node = min(G.nodes, key=lambda n: _dist_m(n, lonlat))
    d = _dist_m(node, lonlat)
    if d > SNAP_MAX_M:
        raise ValueError(f"{which} point is {d:.0f} m from the nearest road (max {SNAP_MAX_M:.0f} m)")
    name = next((e["name"] for _, _, e in G.edges(node, data=True) if e["name"]), None)
    return node, {"lon": lonlat[0], "lat": lonlat[1], "snapped_to": name, "snap_distance_m": round(d)}


def _edges(G, path):
    return [G[u][v] for u, v in zip(path, path[1:])]


def _edge_set(path):
    return frozenset(frozenset(p) for p in zip(path, path[1:]))


def _deepest(edges):
    known = [e for e in edges if e["depth_m"] is not None]
    if not known:
        return None
    e = max(known, key=lambda e: e["depth_m"])
    return {"depth_m": round(e["depth_m"], 2), "source": e["source"], "road": e["name"]}


def _summary(G, path, kind, replay):
    edges = _edges(G, path)
    dist = sum(e["length_m"] for e in edges)
    unobs = sum(e["length_m"] for e in edges if e["depth_m"] is None)
    osm_ids, via, cams = [], [], []
    for e in edges:
        if e["osm_id"] not in osm_ids:
            osm_ids.append(e["osm_id"])
        if e["name"] and (not via or via[-1] != e["name"]):
            via.append(e["name"])
        cams += [c for c in e["camera_ids"] if c not in cams]
    recheck = ("Not re-checked: REPLAY data" if replay else
               f"On each new reading from camera{'s' if len(cams) > 1 else ''} {', '.join(cams)}" if cams else
               "Not watched by any camera")
    return {"kind": kind,
            "distance_km": round(dist / 1000, 2),
            "deepest": _deepest(edges),
            "unobserved_km": round(unobs / 1000, 2),
            "unobserved_share": round(unobs / dist, 2) if dist else 0.0,
            "n_bridges_not_estimated": len({e["osm_id"] for e in edges if e["is_bridge"] and e["depth_m"] is None}),
            "recheck": recheck,
            "via": via,
            "osm_ids": osm_ids,
            "geometry": {"type": "LineString", "coordinates": [list(n) for n in path]}}


def _ok(e, cap, avoid_unobserved):
    return (not avoid_unobserved) if e["depth_m"] is None else e["depth_m"] <= cap + EPS


def route_options(G, start, end, depth_limit_m, avoid_unobserved=False, cameras=None, depart=None, step_cm=5):
    """§4: up to three options from start to end (lon, lat), never using a road deeper than depth_limit_m.

    A: least-deep (first depth cap that connects, shortest under it). B: shortest within the limit.
    C: least unobserved (unknown length x5). Duplicates dropped.
    """
    if not isinstance(depth_limit_m, (int, float)) or isinstance(depth_limit_m, bool) \
            or math.isnan(depth_limit_m) or depth_limit_m < 0:
        raise ValueError(f"depth limit must be a number of metres >= 0, set by a person (got {depth_limit_m!r})")
    s, start_info = _snap(G, start, "start")
    e, end_info = _snap(G, end, "end")
    if s == e:
        raise ValueError("start and end snap to the same road point")
    set_planning_depths(G, s, cameras, depart)
    replay = not cameras or depart is None
    L = float(depth_limit_m)
    out = {"depth_limit_m": round(L, 2), "avoid_unobserved": avoid_unobserved, "start": start_info, "end": end_info}

    def view(cap):
        return nx.subgraph_view(G, filter_edge=lambda u, v: _ok(G[u][v], cap, avoid_unobserved))

    within = view(L)
    if not nx.has_path(within, s, e):
        out.update(status="no_route_within_limit", options=[], message=NO_ROUTE + ".", blocking=_blocking(G, s, e, L, avoid_unobserved))
        return out

    caps = [c / 100 for c in range(0, math.floor(L * 100 + EPS) + 1, step_cm)]
    if not caps or caps[-1] < L - EPS:
        caps.append(L)
    cap = next(c for c in caps if nx.has_path(view(c), s, e))
    candidates = [
        ("least_deep", nx.shortest_path(view(cap), s, e, weight="length_m")),
        ("shortest_within_limit", nx.shortest_path(within, s, e, weight="length_m")),
        ("least_unobserved", nx.shortest_path(within, s, e, weight=lambda u, v, d: d["length_m"] * (
            UNOBSERVED_PENALTY if d["depth_m"] is None else 1))),
    ]
    options, seen = [], set()
    for kind, path in candidates:
        if _edge_set(path) in seen:
            continue
        seen.add(_edge_set(path))
        opt = _summary(G, path, kind, replay)
        if kind == "least_deep":
            opt["depth_cap_m"] = round(cap, 2)
        opt["id"] = "ABC"[len(options)]
        options.append(opt)
    out.update(status="ok", options=options)
    return out


def _blocking(G, s, e, L, avoid_unobserved):
    """Segments over the limit on the way through that uses the least blocked road."""
    if not nx.has_path(G, s, e):
        return []
    path = nx.shortest_path(G, s, e, weight=lambda u, v, d: d["length_m"] * (1 if _ok(d, L, avoid_unobserved) else 1e6))
    out, seen = [], set()
    for ed in _edges(G, path):
        if not _ok(ed, L, avoid_unobserved) and ed["osm_id"] not in seen:
            seen.add(ed["osm_id"])
            out.append({"osm_id": ed["osm_id"], "road": ed["name"], "source": ed["source"],
                        "depth_m": None if ed["depth_m"] is None else round(ed["depth_m"], 2)})
    return out


def recheck_route(G, option, depth_limit_m, cameras=None, depart=None):
    """§5: recompute the chosen option's planning depths after new readings.

    Alerts if the deepest point rose by 5 cm or more, or any segment is now above the limit. Never switches
    routes: the caller shows old and new numbers plus fresh options, and the dispatcher decides.
    """
    path = [tuple(p) for p in option["geometry"]["coordinates"]]
    set_planning_depths(G, path[0], cameras, depart)
    edges = _edges(G, path)
    new = _deepest(edges)
    old = option.get("deepest")
    reasons = []
    if new and (old is None or new["depth_m"] >= old["depth_m"] + ALERT_RISE_M - EPS):
        reasons.append(f"Deepest point {'rose from ' + format(old['depth_m'], '.2f') + ' m' if old else 'now'} "
                       f"to {new['depth_m']:.2f} m ({new['source']}, {new['road']}).")
    over = [ed for ed in edges if ed["depth_m"] is not None and ed["depth_m"] > depth_limit_m + EPS]
    for ed in {ed["osm_id"]: ed for ed in over}.values():
        reasons.append(f"{ed['name'] or 'A road'} is now {ed['depth_m']:.2f} m ({ed['source']}), "
                       f"over the {depth_limit_m:.2f} m limit you set.")
    return {"alert": bool(reasons), "reasons": reasons, "old_deepest": old, "new_deepest": new}


def write_routes(roads_path, start, end, depth_limit_m, out_path, avoid_unobserved=False, label=REPLAY_LABEL):
    G = build_graph(json.load(open(roads_path)))
    result = route_options(G, start, end, depth_limit_m, avoid_unobserved=avoid_unobserved)
    doc = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "label": label,
           "depth_limit_note": "Set by the person running this; the router never chooses it.",
           **result,
           "caveats": REPLAY_CAVEATS + CAVEATS}
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=1)
    return doc


def _lonlat(s):
    lon, lat = (float(v) for v in s.split(","))
    return lon, lat


def main():
    p = argparse.ArgumentParser(description="Least-deep route options within a depth limit you set (replay data)")
    p.add_argument("--start", type=_lonlat, required=True, help="LON,LAT")
    p.add_argument("--end", type=_lonlat, required=True, help="LON,LAT")
    p.add_argument("--limit", type=float, required=True, help="deepest water the vehicle may cross, metres (set by your agency)")
    p.add_argument("--avoid-unobserved", action="store_true", help="drop roads with no data")
    p.add_argument("--roads", default="web/data/roads_status.geojson")
    p.add_argument("--out", default="web/data/routes.json")
    a = p.parse_args()
    doc = write_routes(a.roads, a.start, a.end, a.limit, a.out, avoid_unobserved=a.avoid_unobserved)
    print(f"{doc['label']}\nLimit {doc['depth_limit_m']:.2f} m · {doc['start']['snapped_to']} → {doc['end']['snapped_to']}"
          + (" · avoiding unobserved roads" if a.avoid_unobserved else ""))
    if doc["status"] != "ok":
        print(doc["message"])
        for b in doc["blocking"]:
            depth = "no data" if b["depth_m"] is None else f"{b['depth_m']:.2f} m"
            print(f"  blocked by {b['road'] or 'unnamed road'} ({b['osm_id']}): {depth}, {b['source']}")
    for o in doc["options"]:
        d = o["deepest"]
        deepest = "no observed roads" if d is None else f"{d['depth_m']:.2f} m ({d['source']}, {d['road']})"
        print(f"  {o['id']} {o['kind']:<22} {o['distance_km']:>5.2f} km · deepest {deepest} · "
              f"unobserved {o['unobserved_km']:.2f} km ({o['unobserved_share']:.0%})")
    print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
