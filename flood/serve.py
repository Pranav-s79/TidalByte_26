"""Local server for the maps: python -m flood.serve  (serves web/ on http://127.0.0.1:8765/).

POST /route   {"start": [lon, lat], "end": [lon, lat], "depth_limit_m": 0.3, "avoid_unobserved": false,
               "closed_osm_ids": []}   (closed_osm_ids: roads a person marked closed as a what-if)
              → route options on the current map data (docs/routing-and-prediction.md §4). The depth limit
                is required: a person at the agency sets it, the server never fills one in.
GET  /data/cameras.json  → Prince's TranStar catalog for the page, without snapshot URLs (no TxDOT permission).
POST /review  {"id": "<observation id>", "status": "confirmed" | "rejected" | "needs_review"}
              → updates data/observations.json, rebuilds the map layers and returns the new meta.json.
                Only confirmed readings with a depth change the water (flood/run.py).

Both POSTs only answer pages opened from this server on localhost. Nothing here dispatches vehicles,
closes roads or talks to any outside system.
"""
import argparse
import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
from threading import Lock

from flood.route import REPLAY_LABEL, build_graph, caveats, load_cameras, route_options
from flood.run import build_outputs

ROOT = Path(__file__).resolve().parents[1]
REVIEW_STATUSES = {"confirmed", "rejected", "needs_review"}
MAX_BODY = 64 * 1024


class BadRequest(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _point(body, key):
    p = body.get(key)
    if (not isinstance(p, list) or len(p) != 2 or
            not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p)):
        raise BadRequest(400, f"{key} must be [lon, lat]")
    lon, lat = p
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise BadRequest(400, f"{key} must be [lon, lat]")
    return float(lon), float(lat)


class FloodState:
    """The paths the pipeline reads and writes, plus the road graph the router uses.

    route_options writes planning depths onto the graph's edges, so routing and rebuilding share one lock.
    """

    def __init__(self, marks, dem, roads, observations, out_dir, radius_m=400.0, cameras=None):
        self.marks, self.dem, self.roads, self.observations = marks, dem, roads, observations
        self.cameras_path = cameras
        self.out_dir, self.radius_m = Path(out_dir), radius_m
        self.lock = Lock()
        self.graph = None
        if not (self.out_dir / "roads_status.geojson").exists():
            self._rebuild()
        self._load_graph()

    def _load_graph(self):
        with open(self.out_dir / "roads_status.geojson") as f:
            self.graph = build_graph(json.load(f))

    def _rebuild(self):
        return build_outputs(self.marks, self.dem, self.roads, self.observations, str(self.out_dir), self.radius_m)

    def _observations(self):
        if self.observations and os.path.exists(self.observations):
            with open(self.observations) as f:
                return json.load(f)
        return []

    def cameras(self):
        """Prince's TranStar catalog with readings from observations; [] when there is no catalog."""
        if not self.cameras_path or not os.path.exists(self.cameras_path):
            return []
        return load_cameras(self.cameras_path, self._observations())

    def public_catalog(self):
        """The catalog for the page, without snapshot URLs: TxDOT permission to show snapshots isn't in place."""
        if not self.cameras_path or not os.path.exists(self.cameras_path):
            return None
        with open(self.cameras_path) as f:
            raw = json.load(f)
        for c in raw.get("cameras", []):
            c.pop("snapshot_url", None)
            c.pop("dry_baseline", None)
        raw["snapshots"] = "Not shown: TxDOT snapshot permission is not in place for this demo."
        return raw

    def route(self, body):
        start, end = _point(body, "start"), _point(body, "end")
        if "depth_limit_m" not in body or body["depth_limit_m"] in (None, ""):
            raise BadRequest(400, "Enter the depth limit your agency set for this vehicle.")
        avoid = body.get("avoid_unobserved", False)
        if not isinstance(avoid, bool):
            raise BadRequest(400, "avoid_unobserved must be true or false")
        closed = body.get("closed_osm_ids", [])
        if not isinstance(closed, list) or not all(isinstance(c, str) for c in closed) or len(closed) > 500:
            raise BadRequest(400, "closed_osm_ids must be a list of road ids")
        cameras = self.cameras()
        with self.lock:
            try:
                result = route_options(self.graph, start, end, body["depth_limit_m"], avoid_unobserved=avoid,
                                       cameras=cameras, closed=closed)
            except ValueError as exc:
                raise BadRequest(400, str(exc)) from None
        return {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "label": REPLAY_LABEL,
                "depth_limit_note": "Set by the person running this; the router never chooses it.",
                **result,
                "caveats": caveats(True, cameras)}

    def review(self, body):
        obs_id, status = body.get("id"), body.get("status")
        if not isinstance(obs_id, str) or not obs_id:
            raise BadRequest(400, "id must be an observation id")
        if status not in REVIEW_STATUSES:
            raise BadRequest(400, f"status must be one of: {', '.join(sorted(REVIEW_STATUSES))}")
        with self.lock:
            obs = self._observations()
            match = next((o for o in obs if o.get("id") == obs_id), None)
            if match is None:
                raise BadRequest(404, f"no observation with id {obs_id!r}")
            match["status"] = status
            match["reviewed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            tmp = f"{self.observations}.part"
            with open(tmp, "w") as f:
                json.dump(obs, f, indent=1)
            os.replace(tmp, self.observations)
            meta = self._rebuild()
            self._load_graph()
        return {"id": obs_id, "status": status, "meta": meta}


class FloodHandler(SimpleHTTPRequestHandler):
    ROUTES = {"/route": "route", "/review": "review"}

    def reply(self, code, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        if self.command != "GET":  # end_headers adds it for GET
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/data/cameras.json":
            catalog = self.server.state.public_catalog()
            return self.reply(200, catalog) if catalog else self.send_error(404)
        super().do_GET()

    def end_headers(self):
        if self.command == "GET":  # map layers change after a review; don't let the browser keep old ones
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        action = self.ROUTES.get(self.path)
        if action is None:
            return self.send_error(404)
        host, port = self.headers.get("Host", ""), self.server.server_port
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"} or self.headers.get("Origin") != f"http://{host}":
            return self.reply(403, {"error": "Open the map from this server on localhost."})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                raise BadRequest(400, "send a JSON body")
            try:
                body = json.loads(self.rfile.read(length))
            except ValueError:
                raise BadRequest(400, "body is not valid JSON") from None
            if not isinstance(body, dict):
                raise BadRequest(400, "body must be a JSON object")
            self.reply(200, getattr(self.server.state, action)(body))
        except BadRequest as exc:
            self.reply(exc.code, {"error": str(exc)})


def make_server(state, port, web_dir):
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(FloodHandler, directory=str(web_dir)))
    server.state = state
    return server


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--marks", default="data/marks.csv")
    p.add_argument("--dem", default="data/dem.tif")
    p.add_argument("--roads", default="data/roads.geojson")
    p.add_argument("--observations", default="data/observations.json")
    p.add_argument("--cameras", default="data/cameras.json", help="TranStar camera catalog (Prince)")
    p.add_argument("--out", default="web/data")
    p.add_argument("--web", default=str(ROOT / "web"))
    a = p.parse_args()
    state = FloodState(a.marks, a.dem, a.roads, a.observations, a.out, cameras=a.cameras)
    with make_server(state, a.port, a.web) as server:
        print(f"Flood maps: http://127.0.0.1:{server.server_port}/  (POST /route, POST /review)", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
