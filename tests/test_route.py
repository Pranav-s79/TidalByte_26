import json
import re
from datetime import datetime, timedelta

import pytest

from flood.route import build_graph, recheck_route, route_options, write_routes

LON0, LAT0 = -95.45, 29.68  # toy roads near Meyerland; offsets of 0.001 deg are ~100 m
NOW = datetime(2026, 11, 21, 14, 0)


def pt(dx, dy):
    return [LON0 + dx, LAT0 + dy]


def road(osm_id, coords, depth, bridge=False):
    status = ("bridge_not_estimated" if bridge else "unknown" if depth is None
              else "likely_flooded" if depth > 0 else "no_flooding_estimated")
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"osm_id": osm_id, "name": f"Road {osm_id}", "highway": "residential",
                           "is_bridge": bridge, "status": status, "max_depth_m": depth}}


def fc(*features):
    return {"type": "FeatureCollection", "features": list(features)}


A, B, C = pt(0, 0), pt(0.010, 0), pt(0.005, 0.006)


def triangle(direct=0.40, via_ac=0.10, via_cb=0.10):
    """A-B direct (~0.97 km) versus A-C-B (~1.65 km)."""
    return build_graph(fc(road("direct", [A, B], direct), road("ac", [A, C], via_ac), road("cb", [C, B], via_cb)))


def kinds(out):
    return [o["kind"] for o in out["options"]]


def camera(cam_id, osm_ids, depth_now, rise_per_min=0.0, n=8, every_min=5):
    readings = [(NOW - timedelta(minutes=every_min * (n - 1 - i)),
                 depth_now - rise_per_min * every_min * (n - 1 - i), 0.02) for i in range(n)]
    return {"id": cam_id, "osm_ids": osm_ids, "readings": readings}


# --- §4 least-deep routing ---

def test_shallower_longer_route_beats_deeper_short_one():
    out = route_options(triangle(), A, B, 0.50)
    a, b = out["options"]
    assert (a["kind"], a["osm_ids"], a["depth_cap_m"]) == ("least_deep", ["ac", "cb"], 0.10)
    assert a["deepest"] == {"depth_m": 0.10, "source": "Estimated", "road": "Road ac"}
    assert (b["kind"], b["osm_ids"]) == ("shortest_within_limit", ["direct"])
    assert b["distance_km"] < a["distance_km"]


def test_road_over_limit_is_never_used_and_duplicates_dropped():
    out = route_options(triangle(), A, B, 0.30)
    assert kinds(out) == ["least_deep"]  # B and C are the same path as A
    assert out["options"][0]["osm_ids"] == ["ac", "cb"]


def test_no_route_lists_blocking_segments():
    out = route_options(triangle(), A, B, 0.05)
    assert out["status"] == "no_route_within_limit"
    assert out["options"] == []
    assert out["message"] == "No route within the depth limit you set."
    assert out["blocking"] == [{"osm_id": "direct", "road": "Road direct", "source": "Estimated", "depth_m": 0.40}]


def test_unobserved_km_counted_and_unknown_never_dry():
    best = route_options(triangle(via_ac=None, via_cb=0.0), A, B, 0.30)["options"][0]
    assert best["osm_ids"] == ["ac", "cb"]
    assert best["unobserved_km"] == pytest.approx(0.82, abs=0.02)
    assert best["deepest"]["depth_m"] == 0.0

    only_unknown = route_options(triangle(via_ac=None, via_cb=None), A, B, 0.30)["options"][0]
    assert only_unknown["deepest"] is None
    assert only_unknown["unobserved_km"] == only_unknown["distance_km"]
    assert only_unknown["unobserved_share"] == 1.0


def test_least_unobserved_option_penalises_unknown_roads():
    out = route_options(triangle(direct=None, via_ac=0.0, via_cb=0.0), A, B, 0.30)
    assert kinds(out) == ["least_deep", "least_unobserved"]
    assert out["options"][0]["osm_ids"] == ["direct"]
    assert out["options"][1]["osm_ids"] == ["ac", "cb"]
    assert out["options"][1]["unobserved_km"] == 0


def test_avoid_unobserved_removes_unknown_roads():
    out = route_options(triangle(direct=None, via_ac=0.0, via_cb=0.0), A, B, 0.30, avoid_unobserved=True)
    assert kinds(out) == ["least_deep"]
    assert out["options"][0]["osm_ids"] == ["ac", "cb"]
    blocked = route_options(triangle(direct=None, via_ac=None, via_cb=0.0), A, B, 0.30, avoid_unobserved=True)
    assert blocked["status"] == "no_route_within_limit"
    assert blocked["blocking"][0]["source"] == "Unknown: no data"


def test_bridges_count_as_unobserved():
    best = route_options(build_graph(fc(road("br", [A, B], None, bridge=True))), A, B, 0.30)["options"][0]
    assert best["n_bridges_not_estimated"] == 1
    assert best["unobserved_km"] == best["distance_km"]


def test_roads_crossing_mid_line_connect():
    G = build_graph(fc(road("ew", [pt(0, 0), pt(0.005, 0), pt(0.010, 0)], 0.0),
                       road("ns", [pt(0.005, -0.005), pt(0.005, 0), pt(0.005, 0.005)], 0.0)))
    assert route_options(G, pt(0, 0), pt(0.005, 0.005), 0.30)["options"][0]["osm_ids"] == ["ew", "ns"]


def test_endpoint_far_from_roads_is_refused():
    with pytest.raises(ValueError, match="from the nearest road"):
        route_options(triangle(), pt(0.1, 0.1), B, 0.30)


def test_depth_limit_is_required_and_valid():
    with pytest.raises(TypeError):
        route_options(triangle(), A, B)  # noqa
    for bad in (None, -0.1, float("nan"), True):
        with pytest.raises(ValueError, match="depth limit"):
            route_options(triangle(), A, B, bad)


# --- §3 planning depths from cameras ---

def test_camera_prediction_overrides_estimate():
    """The direct road's estimate is dry, but its camera shows 0.5 m: the router goes round."""
    G = triangle(direct=0.0)
    cams = [camera("cam1", ["direct"], depth_now=0.5), camera("cam2", ["cb"], depth_now=0.20)]
    out = route_options(G, A, B, 0.30, cameras=cams, depart=NOW)
    opt = out["options"][0]
    assert opt["osm_ids"] == ["ac", "cb"]
    assert opt["deepest"]["source"].startswith("Predicted for 14:")  # cb's camera (~0.22 m) beats ac's 0.10 m estimate
    assert opt["deepest"]["road"] == "Road cb"
    assert 0.20 < opt["deepest"]["depth_m"] <= 0.30
    assert opt["recheck"] == "On each new reading from camera cam2"


def test_camera_with_stale_readings_falls_back_to_estimate():
    stale = camera("cam1", ["direct"], depth_now=0.5)
    stale["readings"] = [(t - timedelta(hours=3), d, s) for t, d, s in stale["readings"]]
    out = route_options(triangle(direct=0.0), A, B, 0.30, cameras=[stale], depart=NOW)
    assert out["options"][0]["osm_ids"] == ["direct"]
    assert out["options"][0]["deepest"]["source"] == "Estimated"


def test_replay_options_say_not_rechecked():
    assert route_options(triangle(), A, B, 0.50)["options"][0]["recheck"] == "Not re-checked: REPLAY data"


# --- §5 re-planning alerts ---

def test_recheck_alerts_when_route_goes_over_limit():
    G = triangle(direct=0.0)
    chosen = route_options(G, A, B, 0.30)["options"][0]
    assert chosen["osm_ids"] == ["direct"]
    alert = recheck_route(G, chosen, 0.30, cameras=[camera("cam1", ["direct"], 0.4, rise_per_min=0.005)], depart=NOW)
    assert alert["alert"]
    assert alert["old_deepest"]["depth_m"] == 0.0
    assert alert["new_deepest"]["depth_m"] > 0.30
    assert any("over the 0.30 m limit you set" in r for r in alert["reasons"])


def test_recheck_quiet_when_nothing_changed():
    G = triangle(direct=0.0)
    chosen = route_options(G, A, B, 0.30)["options"][0]
    assert recheck_route(G, chosen, 0.30) == {"alert": False, "reasons": [], "old_deepest": chosen["deepest"],
                                              "new_deepest": chosen["deepest"]}


# --- output file ---

def test_written_file_avoids_forbidden_words(tmp_path):
    roads = tmp_path / "roads.geojson"
    json.dump(fc(road("direct", [A, B], 0.40), road("ac", [A, C], None), road("cb", [C, B], 0.10)), open(roads, "w"))
    out = tmp_path / "routes.json"
    for limit in (0.50, 0.05):
        write_routes(str(roads), A, B, limit, str(out))
        assert not re.search(r"\b(safe|clear|passable|all clear)\b", out.read_text(), re.IGNORECASE)
    assert json.load(open(out))["depth_limit_m"] == 0.05


def test_replay_routes_cross_meyerland(tmp_path):
    """Harvey replay depths (Estimated only, no time): options cross Brays Bayou, labeled REPLAY."""
    out = tmp_path / "routes.json"
    north, south = (-95.451197, 29.697717), (-95.446069, 29.674473)
    doc = write_routes("web/data/roads_status.geojson", north, south, 0.30, str(out))
    assert doc["status"] == "ok" and doc["options"]
    assert doc["label"].startswith("REPLAY")
    for o in doc["options"]:
        lats = [c[1] for c in o["geometry"]["coordinates"]]
        assert max(lats) > 29.69 and min(lats) < 29.68
        assert o["deepest"] is None or o["deepest"]["depth_m"] <= 0.30
