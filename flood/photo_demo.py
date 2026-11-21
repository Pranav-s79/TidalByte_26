"""Serve the field-photo demo on localhost: python -m flood.photo_demo.

python -m flood.photo_demo --record runs the real detector and Nemotron on DEMO_PHOTOS and writes
web/photos/demo/ for the walkthrough page (web/photos/walkthrough.html).
"""
import argparse
from datetime import datetime, timezone
from functools import partial
from getpass import getpass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Lock
import time

from flood import read_photo as rp
from flood.detect import debug_draw, detect
from flood.read_photo import read_photo


WEB = Path(__file__).resolve().parents[1] / "web"
PHOTO = WEB / "photos" / "piney-point-2017-08-27.jpg"
API_PATH = "/api/piney-point/reading"
DEMO = WEB / "photos" / "demo"
# Photos the walkthrough replays. lat/lon only where a source gives them (Barker: the original file's EXIF GPS);
# None means the source states none, and that photo is never placed on a map.
DEMO_PHOTOS = [
    {"file": "piney-point-2017-08-27.jpg", "title": "Buffalo Bayou at Piney Point", "taken": "Aug 27, 2017, 10:45 CDT",
     "lat": 29.749967, "lon": -95.523117, "credit": "USGS · public domain",
     "url": "https://www.usgs.gov/media/images/hurricane-harvey-flooding-buffalo-bayou-piney-point"},
    {"file": "barker-reservoir-2017-08-29.jpg", "title": "Streamgage at Barker Reservoir",
     "taken": "Aug 29, 2017, 11:01 (camera clock)", "lat": 29.769803, "lon": -95.646583, "credit": "USGS · public domain",
     "url": "https://www.usgs.gov/media/images/servicing-a-streamgage-barker-reservoir-following-hurricane-harvey"},
    {"file": "huntsville-sign-2017-08-28.jpg", "title": "Road sign near Huntsville", "taken": "Aug 28, 2017",
     "lat": None, "lon": None, "credit": "USGS, Mackenzie K. Mullins · public domain",
     "url": "https://www.usgs.gov/media/images/hurricane-harvey-flooding-along-san-jacinto-river-1"},
    {"file": "houston-aerial-2017-08.jpg", "title": "Houston neighborhood from the air", "taken": "Aug 2017 (day not stated)",
     "lat": None, "lon": None, "credit": "USGS · public domain", "url": "https://www.usgs.gov/media/images/houston-harvey-flood"},
    {"file": "refs/22840.jpg", "title": "Dry street near Brays Bayou (control)", "taken": "May 16, 2015",
     "lat": 29.69189, "lon": -95.442757, "credit": "Mapillary · CC BY-SA 4.0",
     "url": "https://www.mapillary.com/app/?pKey=303316301368352"},
]


def analyze():
    start = time.monotonic()
    obs = read_photo(str(PHOTO), 29.749967, -95.523117, "2017-08-27T15:45:33Z", detector=detect)
    if (obs["error"] or "").startswith("model call failed"):
        raise RuntimeError("The model request failed. Check the server key or retry.")
    if obs["error"] and not any(r["reasoning"] for r in obs.get("readings") or [obs]):  # a disagreement is shown, not hidden
        raise RuntimeError("The model returned an unreadable result. Retry the reading.")
    obs["photo"] = PHOTO.name
    det = obs.get("detector") or {}
    obs["detector"] = {"model": det.get("model"), "objects": det.get("objects")}
    return {**obs, "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_s": round(time.monotonic() - start, 1)}


def record(photos=DEMO_PHOTOS):
    """Real detector + three Nemotron reads per photo -> boxes, crops and web/photos/demo/recorded.js."""
    DEMO.mkdir(exist_ok=True)
    rel = lambda f: os.path.relpath(f, WEB / "photos")  # noqa: E731
    runs = []
    for p in photos:
        path, slug = WEB / "photos" / p["file"], Path(p["file"]).stem
        start = time.monotonic()
        r = rp.read_image(str(path), detector=detect, crop_dir=str(DEMO / slug))
        if all((x["error"] or "").startswith("model call failed") for x in r.get("readings") or [r]):
            print(f"{slug}: skipped, {r['error']}", file=sys.stderr)
            continue
        det = r["detector"] or {}
        crops = det.get("crops") or []
        for f in (DEMO / slug).glob("*.jpg"):  # make_crops saves every object; keep the two Nemotron saw
            if str(f) not in crops:
                f.unlink()
        debug_draw(str(path), det.get("objects") or [], str(DEMO / f"{slug}-boxes.jpg"))
        runs.append({**p, **r, "boxes": rel(DEMO / f"{slug}-boxes.jpg"),
                     "detector": {**det, "crops": [{"src": rel(c), "label": Path(c).stem[3:].replace("_", " ")} for c in crops]},
                     "model": os.environ.get("NEMOTRON_VL_MODEL", rp.DEFAULT_MODEL),
                     "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "elapsed_s": round(time.monotonic() - start, 1)})
        print(f"{slug}: {r['status']}, {rp._span(r)}, {time.monotonic() - start:.0f} s", flush=True)
    (DEMO / "recorded.js").write_text(
        "// Written by python -m flood.photo_demo --record: real PyTorch detector and Nemotron output.\n"
        f"const referenceHeights = {json.dumps(rp._table(), indent=1)};\nconst recordedRuns = {json.dumps(runs, indent=1)};\n")


class PhotoHandler(SimpleHTTPRequestHandler):
    def reply(self, code, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == API_PATH:
            self.reply(200, {"reading": self.server.latest})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path != API_PATH:
            return self.send_error(404)
        host = self.headers.get("Host", "")
        port = self.server.server_port
        if (host not in {f"127.0.0.1:{port}", f"localhost:{port}"} or
                self.headers.get("Origin") != f"http://{host}"):
            return self.reply(403, {"error": "Open the demo on localhost to run a reading."})
        if not self.server.run_lock.acquire(blocking=False):
            return self.reply(409, {"error": "A reading is already running. Try again when it finishes."})
        try:
            reading = analyze()
            self.server.latest = reading
        except RuntimeError as exc:
            return self.reply(502, {"error": str(exc)})
        finally:
            self.server.run_lock.release()
        self.reply(200, {"reading": reading})


def make_server(port):
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(PhotoHandler, directory=str(WEB)))
    server.latest = None
    server.run_lock = Lock()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--record", action="store_true", help="record the walkthrough's photos, then exit")
    args = parser.parse_args()
    if not os.getenv("NVIDIA_API_KEY") and sys.stdin.isatty():
        os.environ["NVIDIA_API_KEY"] = getpass("NVIDIA API key: ")
    if not os.getenv("NVIDIA_API_KEY"):
        parser.error("Set NVIDIA_API_KEY or start the server from an interactive terminal.")
    if args.record:
        return record()
    with make_server(args.port) as server:
        print(f"3D flood demo: http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
