"""Capture one candidate baseline per camera after obtaining snapshot permission."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from PIL import Image
import requests


def capture_frame(camera, frames):
    camera_id = camera["id"]
    if not camera_id.isascii() or not camera_id.isdecimal():
        raise ValueError("expected a numeric TranStar camera ID")
    with requests.get(camera["snapshot_url"], stream=True, timeout=(5, 20)) as response:
        response.raise_for_status()
        directory = frames / camera_id
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        tmp = NamedTemporaryFile(dir=directory, prefix=stamp + "-", suffix=".part", delete=False)
        path = Path(tmp.name)
        try:
            with tmp:
                size = 0
                for chunk in response.iter_content(64 * 1024):
                    size += len(chunk)
                    if size > 8 * 1024 * 1024:
                        raise ValueError("snapshot exceeds 8 MiB")
                    tmp.write(chunk)
            with Image.open(path, formats=["JPEG"]) as image:
                image.load()
            return path.rename(path.with_suffix(".jpg"))
        finally:
            path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permission-confirmed", action="store_true", required=True,
                        help="confirm written TxDOT permission covers the intended use")
    parser.add_argument("--catalog", type=Path, default=Path("data/cameras.json"))
    parser.add_argument("--frames", type=Path, default=Path("data/frames"))
    parser.add_argument("--camera", help="capture only this catalog ID")
    args = parser.parse_args(argv)
    cameras = json.loads(args.catalog.read_text())["cameras"]
    if args.camera:
        cameras = [c for c in cameras if c["id"] == args.camera]
        if not cameras:
            parser.error("unknown camera ID")
    failed = False
    for camera in cameras:
        try:
            print(capture_frame(camera, args.frames))
        except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError) as exc:
            print(f"Camera {camera['id']}: {exc}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
