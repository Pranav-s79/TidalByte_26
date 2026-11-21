"""Camera frame reader (Lane B, polish task 2).

Reads one frame from a fixed traffic camera into an observation, on top of flood/read_photo.py:
  - The location is the camera's, from data/cameras.json; never read from the image.
  - Super VL compares the frame with the camera's dry baseline and reads the water only against fixed
    references visible in both (the camera's reference_heights, else data/reference_heights.json).
  - Frame quality is vetted two ways. Without a model: a frame unchanged from the previous one is a frozen
    feed, and a very dark frame is night. Super VL also reports night, glare, rain on the lens, blur, an
    obstructed view, or a view that no longer matches the baseline (camera moved).
  - Rules, never a guess: frozen_feed, camera_moved or obstructed -> needs_review with no depth.
    night, glare, rain_on_lens, blurry or no baseline -> low confidence (predict.py leaves those out).

The observation is read_photo's, plus camera_id, frame_issues, frame_checks and baseline, so
predict.readings_from_observations can use it directly.

cameras.json fields used: id, lat and lon (or location: {lat, lon}), reference_heights (optional, same rows as
data/reference_heights.json) and dry_baseline (Prince's field: a reviewed dry frame's path; "baseline" also
works). Without one, the oldest image in data/frames/<id>/ (where flood/capture.py saves frames) is used.

CLI: python -m flood.read_frame FRAME --camera ID --taken-at ISO [--previous PREV] [--baseline PATH] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

from flood import read_photo as rp

HARD = {"frozen_feed", "camera_moved", "obstructed"}            # the frame can't be read: needs_review, no depth
SOFT = {"night", "glare", "rain_on_lens", "blurry", "no_baseline"}  # readable, but only at low confidence
MODEL_ISSUES = {"night", "glare", "rain_on_lens", "blurry", "obstructed", "camera_moved"}
FROZEN_DIFF = 1.0   # mean absolute grey-level difference (0-255) below which two frames count as the same
DARK_LEVEL = 40     # mean grey level (0-255) below which a frame counts as night
FRAMES_DIR = os.path.join("data", "frames")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif"}

FRAME_RULES = """
This is a frame from a fixed traffic camera.{baseline}
- Read the depth only where the water meets a reference object from the table that you can see in both images. If there is none, set reference_object and both fractions to null.
- Also include "frame_issues": a list of any of "night", "glare", "rain_on_lens", "blurry", "obstructed", "camera_moved" (the view no longer matches the dry baseline: turned, tilted or zoomed). Use [] if the frame is fine."""
WITH_BASELINE = " The second image is the same camera's dry baseline, with no flood. Compare the two."
NO_BASELINE = " There is no dry baseline for this camera, so read the frame on its own."


def load_camera(camera_id, path="data/cameras.json"):
    cameras = json.load(open(path))
    cameras = cameras.get("cameras", cameras) if isinstance(cameras, dict) else cameras
    cam = next((c for c in cameras if str(c.get("id")) == str(camera_id)), None)
    if cam is None:
        raise ValueError(f"camera {camera_id!r} is not in {path}")
    return cam


def camera_location(cam):
    loc = cam.get("location") if isinstance(cam.get("location"), dict) else cam
    lat, lon = loc.get("lat"), loc.get("lon")
    if lat is None or lon is None:
        raise ValueError(f"camera {cam.get('id')!r} has no lat/lon in cameras.json; a frame is never placed without one")
    return float(lat), float(lon)


def find_baseline(cam, frame_path, frames_dir=FRAMES_DIR):
    """The camera's dry baseline: its "dry_baseline" (or "baseline") field, else the oldest image in
    data/frames/<id>/."""
    if cam.get("dry_baseline") or cam.get("baseline"):
        return cam.get("dry_baseline") or cam["baseline"]
    folder = os.path.join(frames_dir, str(cam["id"]))
    if not os.path.isdir(folder):
        return None
    images = sorted(os.path.join(folder, f) for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in IMAGE_EXT)
    images = [p for p in images if os.path.abspath(p) != os.path.abspath(frame_path)]
    return min(images, key=os.path.getmtime) if images else None


def _grey(path, size=(160, 120)):
    return np.asarray(Image.open(path).convert("L").resize(size), dtype=float)


def pixel_checks(frame_path, previous_path=None):
    """Checks that need no model. Returns ({brightness, diff_from_previous}, issues)."""
    frame = _grey(frame_path)
    checks, issues = {"brightness": round(float(frame.mean()), 1), "diff_from_previous": None}, set()
    if checks["brightness"] < DARK_LEVEL:
        issues.add("night")
    if previous_path:
        same_bytes = hashlib.sha1(open(frame_path, "rb").read()).digest() == hashlib.sha1(open(previous_path, "rb").read()).digest()
        diff = 0.0 if same_bytes else float(np.abs(frame - _grey(previous_path)).mean())
        checks["diff_from_previous"] = round(diff, 2)
        if diff < FROZEN_DIFF:
            issues.add("frozen_feed")
    return checks, issues


def model_issues(raw):
    data = rp._extract_json(raw or "")
    found = data.get("frame_issues") if isinstance(data, dict) else None
    if not isinstance(found, list):
        return set()
    return {str(i).strip().lower() for i in found} & MODEL_ISSUES


def apply_frame_rules(obs, issues):
    """HARD issues: needs_review, no depth. SOFT issues: low confidence. Never upgrades a reading."""
    hard = sorted(issues & HARD)
    if hard:
        note = "frame not usable: " + ", ".join(hard)
        return {**obs, "status": "needs_review", "depth_m_low": None, "depth_m_high": None,
                "error": f"{obs['error']}; {note}" if obs.get("error") else note}
    if issues & SOFT and obs["status"] == "ai_proposed":
        return {**obs, "confidence": "low"}
    return obs


def read_frame(frame_path, cam, taken_at, client=rp.post_chat, detector=None, baseline_path=None, previous_path=None):
    """One camera frame in, one observation out (read_photo's format plus camera fields)."""
    lat, lon = camera_location(cam)
    checks, issues = pixel_checks(frame_path, previous_path)
    if baseline_path is None:
        issues.add("no_baseline")
    if "frozen_feed" in issues:  # same picture as last time: nothing new to read, so don't call the model
        data = open(frame_path, "rb").read()
        obs = {"id": "obs-" + hashlib.sha1(data).hexdigest()[:10], "lat": lat, "lon": lon, "taken_at": taken_at,
               "photo": frame_path, **rp._empty("frame not usable: frozen_feed"), "detector": None, "model": None}
    else:
        replies = []

        def remember(messages):
            replies.append(client(messages))
            return replies[-1]

        extra = FRAME_RULES.format(baseline=WITH_BASELINE if baseline_path else NO_BASELINE)
        obs = rp.read_photo(frame_path, lat, lon, taken_at, client=remember, detector=detector,
                            baseline_path=baseline_path, heights=cam.get("reference_heights"), extra_prompt=extra)
        issues |= set().union(*map(model_issues, replies))  # an issue any read reports counts
    obs = apply_frame_rules(obs, issues)
    return {**obs, "camera_id": cam["id"], "frame_issues": sorted(issues), "frame_checks": checks,
            "baseline": baseline_path}


def main():
    p = argparse.ArgumentParser(description="Read one traffic-camera frame with Nemotron VL")
    p.add_argument("frame")
    p.add_argument("--camera", required=True, help="camera id in data/cameras.json (gives the location)")
    p.add_argument("--taken-at", required=True)
    p.add_argument("--previous", help="the camera's previous frame, to catch a frozen feed")
    p.add_argument("--baseline", help="dry baseline frame; default: the camera's baseline or oldest in data/frames/<id>/")
    p.add_argument("--cameras", default="data/cameras.json")
    p.add_argument("--out", default="data/observations.json")
    p.add_argument("--no-detector", action="store_true", help="skip the PyTorch object detector")
    p.add_argument("--dry-run", action="store_true", help="print only; don't write observations.json")
    a = p.parse_args()
    cam = load_camera(a.camera, a.cameras)
    baseline = a.baseline or find_baseline(cam, a.frame)
    detector = None if a.no_detector else rp._default_detector()
    obs = read_frame(a.frame, cam, a.taken_at, detector=detector, baseline_path=baseline, previous_path=a.previous)
    print(json.dumps(obs, indent=2))
    if a.dry_run:
        return
    if (obs["error"] or "").startswith("model call failed"):
        sys.exit(f"not saved: {obs['error']}")
    if not rp.save_observation(obs, a.out):
        sys.exit(f"not saved: {obs['id']} was already reviewed by a person in {a.out}")


if __name__ == "__main__":
    main()
