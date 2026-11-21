import json
import threading
import urllib.error
import urllib.request

import pytest

from flood.serve import FloodState, make_server
from tests.conftest import CY, X0, lonlat


# The tiny road runs straight across the bowl, whose middle is about 2 m deep.
START, END = list(lonlat(X0 + 5, CY)), list(lonlat(X0 + 95, CY))


@pytest.fixture
def server(tiny_inputs, tmp_path):
    marks, dem, roads, obs, out = tiny_inputs("ai_proposed")
    cams = tmp_path / "cameras.json"
    json.dump({"source": "Houston TranStar", "cameras": [
        {"id": "631", "road": "IH-610 South Loop", "cross_street": "Stella Link", "lat": START[1], "lon": START[0],
         "snapshot_url": "https://example.invalid/631.jpg", "dry_baseline": None,
         "candidate_osm_ids": ["1"], "visible_osm_ids": []}]}, open(cams, "w"))
    srv = make_server(FloodState(marks, dem, roads, obs, out, cameras=str(cams)), 0, tmp_path)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.obs_path, srv.out_dir = obs, tiny_inputs.out_dir
    yield srv
    srv.shutdown()
    srv.server_close()


def post(srv, path, body, origin=True):
    host = f"127.0.0.1:{srv.server_port}"
    req = urllib.request.Request(f"http://{host}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Origin": f"http://{host}"} if origin else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_route_returns_options_within_the_limit(server):
    code, doc = post(server, "/route", {"start": START, "end": END, "depth_limit_m": 3.0})
    assert code == 200 and doc["status"] == "ok" and doc["label"].startswith("REPLAY")
    assert doc["depth_limit_m"] == 3.0 and doc["options"]
    for o in doc["options"]:
        assert o["deepest"]["depth_m"] <= 3.0 and "unobserved_km" in o


def test_route_under_a_low_limit_says_no_route(server):
    code, doc = post(server, "/route", {"start": START, "end": END, "depth_limit_m": 0.3})
    assert code == 200 and doc["status"] == "no_route_within_limit" and doc["options"] == []
    assert doc["message"].startswith("No route within the depth limit you set") and doc["blocking"]


@pytest.mark.parametrize("limit", [None, "", "deep", -1, True])
def test_route_needs_a_person_set_limit(server, limit):
    body = {"start": START, "end": END}
    if limit is not None:
        body["depth_limit_m"] = limit
    code, doc = post(server, "/route", body)
    assert code == 400 and "error" in doc


def test_route_rejects_bad_points_and_far_points(server):
    assert post(server, "/route", {"start": "here", "end": END, "depth_limit_m": 1})[0] == 400
    code, doc = post(server, "/route", {"start": [-95.0, 29.0], "end": END, "depth_limit_m": 1})
    assert code == 400 and "from the nearest road" in doc["error"]


def test_confirming_a_reading_raises_confirmed_count(server):
    before = json.load(open(server.out_dir / "meta.json"))["n_confirmed_photos"]
    code, doc = post(server, "/review", {"id": "obs-1", "status": "confirmed"})
    assert code == 200 and doc["meta"]["n_confirmed_photos"] == before + 1
    saved = json.load(open(server.obs_path))[0]
    assert saved["status"] == "confirmed" and saved["reviewed_at"]
    assert json.load(open(server.out_dir / "meta.json")) == doc["meta"]


def test_rejecting_a_confirmed_reading_takes_it_back_out(server):
    post(server, "/review", {"id": "obs-1", "status": "confirmed"})
    code, doc = post(server, "/review", {"id": "obs-1", "status": "rejected"})
    assert code == 200 and doc["meta"]["n_confirmed_photos"] == 0


def test_review_rejects_unknown_id_and_status(server):
    assert post(server, "/review", {"id": "nope", "status": "confirmed"})[0] == 404
    assert post(server, "/review", {"id": "obs-1", "status": "approved"})[0] == 400
    assert json.load(open(server.obs_path))[0]["status"] == "ai_proposed"


def test_posts_from_other_pages_are_refused(server):
    assert post(server, "/review", {"id": "obs-1", "status": "confirmed"}, origin=False)[0] == 403
    assert json.load(open(server.obs_path))[0]["status"] == "ai_proposed"


def test_serves_the_map_files(server):
    (server.out_dir.parent / "index.html").write_text("ok")
    srv_root = f"http://127.0.0.1:{server.server_port}"
    # the fixture serves tmp_path; index.html sits beside out/
    with urllib.request.urlopen(f"{srv_root}/index.html") as r:
        assert r.read() == b"ok" and r.headers["Cache-Control"] == "no-store"


def test_routes_name_prince_cameras_without_their_depth(server):
    code, doc = post(server, "/route", {"start": START, "end": END, "depth_limit_m": 3.0})
    cams = doc["options"][0]["cameras"]
    assert code == 200 and [(c["id"], c["view"], c["n_readings"]) for c in cams] == [("631", "not verified", 0)]
    assert any("view not verified" in c for c in doc["caveats"])


def test_camera_catalog_is_served_without_snapshot_urls(server):
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/data/cameras.json") as r:
        raw = r.read().decode()
    doc = json.loads(raw)
    assert doc["cameras"][0]["id"] == "631" and "snapshot_url" not in raw and "example.invalid" not in raw


def test_route_honours_closures_and_checks_them(server):
    code, doc = post(server, "/route", {"start": START, "end": END, "depth_limit_m": 3.0, "closed_osm_ids": ["1"]})
    assert code == 200 and doc["status"] == "no_route_within_limit" and doc["blocking"][0]["closed"] is True
    assert post(server, "/route", {"start": START, "end": END, "depth_limit_m": 3.0, "closed_osm_ids": "1"})[0] == 400
