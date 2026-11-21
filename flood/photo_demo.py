"""Serve the field-photo demo on localhost: python -m flood.photo_demo."""
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

from flood.detect import detect
from flood.read_photo import read_photo


WEB = Path(__file__).resolve().parents[1] / "web"
PHOTO = WEB / "photos" / "piney-point-2017-08-27.jpg"
API_PATH = "/api/piney-point/reading"


def analyze():
    start = time.monotonic()
    obs = read_photo(str(PHOTO), 29.749967, -95.523117, "2017-08-27T15:45:33Z", detector=detect)
    if (obs["error"] or "").startswith("model call failed"):
        raise RuntimeError("The model request failed. Check the server key or retry.")
    if obs["error"] and not obs["error"].startswith("Nemotron read "):
        raise RuntimeError("The model returned an unreadable result. Retry the reading.")
    obs["photo"] = PHOTO.name
    det = obs.get("detector") or {}
    obs["detector"] = {"model": det.get("model"), "objects": det.get("objects")}
    return {**obs, "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_s": round(time.monotonic() - start, 1)}


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
    args = parser.parse_args()
    if not os.getenv("NVIDIA_API_KEY") and sys.stdin.isatty():
        os.environ["NVIDIA_API_KEY"] = getpass("NVIDIA API key: ")
    if not os.getenv("NVIDIA_API_KEY"):
        parser.error("Set NVIDIA_API_KEY or start the server from an interactive terminal.")
    with make_server(args.port) as server:
        print(f"Photo demo: http://127.0.0.1:{server.server_port}/photos/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
