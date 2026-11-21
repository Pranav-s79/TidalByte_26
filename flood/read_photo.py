"""Nemotron VL reads one flood photo into an observation (spec: data/observations.json)."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import sys

import requests

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"  # event kit's vision pick; listed on integrate.api.nvidia.com
REF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reference_heights.json")
CONFIDENCE = {"low", "medium", "high"}
OBSTACLE_TYPES = {"stalled_vehicle", "debris", "downed_tree", "barricade", "other"}
REVIEWED = {"confirmed", "rejected"}  # a person decided; re-running the reader never replaces these

PROMPT = """You inspect one street photo for flood water. Reply with ONE JSON object and nothing else:
{{"water_visible": true|false,
 "reference_object": "<object of known height that the waterline touches>" or null,
 "depth_m_low": number or null, "depth_m_high": number or null,
 "obstacles": [{{"type": "stalled_vehicle|debris|downed_tree|barricade|other", "note": "<short>"}}],
 "confidence": "low|medium|high",
 "reasoning": "<one or two sentences: what you saw and how you got the depth>"}}
Rules:
- Estimate depth ONLY from where the waterline meets an object in this table of known heights:
{table}
- If no such object touches the waterline, set reference_object, depth_m_low and depth_m_high to null.
- Give a range, never a single number. Do not guess the location. List only obstacles that block a road.
- Never write out license plates or describe people's faces."""


def _empty(error):
    return {"water_visible": False, "reference_object": None, "depth_m_low": None, "depth_m_high": None,
            "obstacles": [], "confidence": "low", "reasoning": "", "status": "needs_review", "error": error}


def _extract_json(raw):
    """First JSON object in the reply, skipping any <think>...</think> block."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _obstacle(o):
    kind, note = str(o.get("type") or "other"), str(o.get("note") or "")
    if kind in OBSTACLE_TYPES:
        return {"type": kind, "note": note}
    return {"type": "other", "note": f"{kind}: {note}" if note else kind}  # keep what the model saw


def parse_reading(raw):
    d = _extract_json(raw)
    if d is None:
        return _empty("no JSON object in model output")
    try:
        ref = d.get("reference_object")
        lo, hi = (None, None) if ref is None else (d.get("depth_m_low"), d.get("depth_m_high"))
        if (lo is None) != (hi is None):
            raise ValueError("depth range has only one end")
        if lo is not None:
            lo, hi = float(lo), float(hi)
            if not 0 <= lo <= hi:
                raise ValueError(f"bad depth range {lo}..{hi}")
        if not isinstance(d.get("water_visible"), bool):
            raise ValueError("water_visible is not true/false")
        if d.get("confidence") not in CONFIDENCE:
            raise ValueError(f"bad confidence {d.get('confidence')!r}")
        obstacles = [_obstacle(o) for o in d.get("obstacles") or []]
    except (ValueError, TypeError, AttributeError) as e:  # JSONDecodeError is a ValueError
        return _empty(str(e))
    return {"water_visible": d["water_visible"], "reference_object": ref, "depth_m_low": lo, "depth_m_high": hi,
            "obstacles": obstacles, "confidence": d["confidence"], "reasoning": str(d.get("reasoning", "")),
            "status": "ai_proposed", "error": None}


def _box(box):
    return "[" + ",".join(str(v) for v in box) + "]"


def _detector_note(objects):
    """The PyTorch detector's boxes as text, e.g. "car at [330,357,826,686], score 0.91"."""
    if objects is None:
        return ""
    if not objects:
        return "\nA PyTorch object detector found no vehicles, people or signs in the current frame."
    rows = "\n".join(f"  - {o['label']} at {_box(o['box'])}, score {o['score']:.2f}" for o in objects)
    return ("\nA PyTorch object detector found these objects in the current frame (pixel boxes [x1,y1,x2,y2]). "
            "It cannot see water. Judge the waterline against these objects:\n" + rows)


def _image(data, mime):
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


def _messages(photo_bytes, photo_path, objects=None, crops=None, baseline=None, heights=None):
    """Prompt + current frame, then the dry baseline frame and the detector's close-up crops when we have them.

    heights: the camera's reference heights (from data/cameras.json); default data/reference_heights.json.
    baseline: (bytes, mime) of the same camera's dry frame.
    """
    rows = heights if heights is not None else json.load(open(REF_PATH))
    table = "\n".join(f"  - {r['name']}: {r['height_m_low']}-{r['height_m_high']} m" for r in rows)
    text = PROMPT.format(table=table) + _detector_note(objects)
    if baseline is not None or crops:
        text += "\nThe first image is the current frame."
    content = [{"type": "text", "text": text}, _image(photo_bytes, mimetypes.guess_type(photo_path)[0] or "image/jpeg")]
    if baseline is not None:
        content += [{"type": "text", "text": "Dry baseline frame from the same camera, with no flood. "
                                             "Compare the current frame against it:"}, _image(*baseline)]
    for c in crops or []:
        content += [{"type": "text", "text": f"Close-up of the {c['label']} at {_box(c['box'])} "
                                             "(padded crop of the current frame):"}, _image(c["jpeg"], "image/jpeg")]
    return [{"role": "user", "content": content}]


def thinking_on():
    """Reasoning is on unless NEMOTRON_VL_THINKING=off.

    Measured on one Harvey photo with Super VL: thinking on took 17-43 s and its depth matched
    the object it named; thinking off took 2 s but named the tire top while describing water
    at the tire's center.
    """
    return os.environ.get("NEMOTRON_VL_THINKING", "on").strip().lower() not in {"0", "off", "false", "no"}


def post_chat(messages):
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    payload = {"model": os.environ.get("NEMOTRON_VL_MODEL", DEFAULT_MODEL), "messages": messages, "temperature": 0}
    if thinking_on():
        payload["max_tokens"] = 8192  # Super VL reasons first: 2,500-6,100 tokens over 5 runs of one photo
    else:
        payload.update(max_tokens=1024, chat_template_kwargs={"enable_thinking": False})
    r = requests.post(ENDPOINT, timeout=180, headers={"Authorization": f"Bearer {key}"}, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from Nemotron: {r.text[:300]}")
    choice = r.json()["choices"][0]
    content = choice["message"].get("content") or ""
    if not content and choice.get("finish_reason") == "length":
        raise RuntimeError(f"Nemotron used all {payload['max_tokens']} tokens reasoning before it answered; run it again")
    return content


# Words in a reference object's name -> detector classes that must be in the photo for that reading to stand.
NEEDS = [
    (("tire", "wheel", "hub", "car", "suv", "sedan", "vehicle", "truck", "bumper", "door"),
     {"car", "truck", "bus", "motorcycle"}, "vehicle"),
    (("knee", "adult", "person", "waist", "ankle"), {"person"}, "person"),
    (("stop sign",), {"stop sign"}, "stop sign"),
    (("hydrant",), {"fire hydrant"}, "fire hydrant"),
]


def cross_check(reading, objects):
    """Second opinion: a depth read against a vehicle, person or sign the detector didn't find goes to review.

    When the two models disagree we keep the disagreement visible instead of passing a depth through.
    """
    ref = (reading.get("reference_object") or "").lower()
    if objects is None or reading["depth_m_low"] is None or not ref:
        return reading
    found = {o["label"] for o in objects}
    for words, classes, what in NEEDS:
        if any(w in ref for w in words):
            if found & classes:
                return reading
            return {**reading, "status": "needs_review", "depth_m_low": None, "depth_m_high": None,
                    "error": f"Nemotron read {reading['depth_m_low']}-{reading['depth_m_high']} m against "
                             f"'{reading['reference_object']}', but the PyTorch detector found no {what}"}
    return reading  # e.g. a curb: the detector has no class for it, so there is nothing to check


CROP_ROOT = os.path.join("cache", "crops")  # gitignored; one folder of crops per observation


def read_photo(photo_path, lat, lon, taken_at, client=post_chat, detector=None, baseline_path=None, heights=None):
    """One frame in, one observation out.

    detector(path, crop_dir) -> (detections, crops), e.g. flood.detect.detect. baseline_path is the same
    camera's dry frame; heights is that camera's reference-height table.
    """
    if lat is None or lon is None:
        raise ValueError("photo has no location: rejected (never guess one)")
    data = open(photo_path, "rb").read()
    obs_id = "obs-" + hashlib.sha1(data).hexdigest()[:10]
    baseline = None
    if baseline_path:
        baseline = (open(baseline_path, "rb").read(), mimetypes.guess_type(baseline_path)[0] or "image/jpeg")
    objects, crops, det = None, [], None
    if detector is not None:
        name = getattr(detector, "model_name", getattr(detector, "__name__", "detector"))
        try:
            objects, crops = detector(photo_path, os.path.join(CROP_ROOT, obs_id))
            det = {"model": name, "objects": objects, "crops": [c.get("path") for c in crops]}
        except Exception as e:  # the detector is a second opinion; Nemotron still reads the photo without it
            det = {"model": name, "objects": None, "crops": [], "error": f"detector failed: {e}"}
    try:
        messages = _messages(data, photo_path, objects, crops, baseline, heights)
        reading = cross_check(parse_reading(client(messages)), objects)
    except Exception as e:  # network/auth/endpoint failure must not crash the pipeline
        reading = _empty(f"model call failed: {e}")
    return {"id": obs_id, "lat": lat, "lon": lon, "taken_at": taken_at,
            "photo": photo_path, **reading, "detector": det,
            "model": os.environ.get("NEMOTRON_VL_MODEL", DEFAULT_MODEL)}


def camera_heights(camera_id, path="data/cameras.json"):
    """The camera's "reference_heights" rows from cameras.json (same format as data/reference_heights.json).

    Returns None, so the default table is used, if the camera has no rows of its own.
    """
    cameras = json.load(open(path))
    cameras = cameras.get("cameras", cameras) if isinstance(cameras, dict) else cameras
    cam = next((c for c in cameras if str(c.get("id")) == str(camera_id)), None)
    if cam is None:
        raise ValueError(f"camera {camera_id!r} is not in {path}")
    return cam.get("reference_heights")


def _default_detector():
    """Load the detector once at startup, or None if PyTorch isn't installed."""
    try:
        import torch  # noqa: F401

        from flood import detect
        detect.load()
        return detect.detect
    except ImportError:
        print("note: PyTorch is not installed (pip install -r requirements.txt); reading without the detector",
              file=sys.stderr)
        return None


def save_observation(obs, path):
    """Add obs to path, or refresh an earlier AI reading of the same photo.

    Returns False and changes nothing if a person already confirmed or rejected that photo.
    """
    items = json.load(open(path)) if os.path.exists(path) else []
    if any(o["id"] == obs["id"] and o.get("status") in REVIEWED for o in items):
        return False
    items = [o for o in items if o["id"] != obs["id"]] + [obs]
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(items, f, indent=2)
    os.replace(tmp, path)
    return True


def main():
    p = argparse.ArgumentParser(description="Read one flood photo with Nemotron VL")
    p.add_argument("photo")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--taken-at", required=True)
    p.add_argument("--out", default="data/observations.json")
    p.add_argument("--dry-run", action="store_true", help="print only; use for photos whose location you don't know")
    p.add_argument("--no-detector", action="store_true", help="skip the PyTorch object detector")
    p.add_argument("--camera", help="camera id in data/cameras.json; its reference_heights replace the default table")
    p.add_argument("--baseline", help="dry baseline frame from the same camera, sent with the current frame")
    a = p.parse_args()
    heights = None
    if a.camera:
        heights = camera_heights(a.camera)
        if heights is None:
            print(f"note: camera {a.camera} has no reference_heights; using data/reference_heights.json", file=sys.stderr)
    detector = None if a.no_detector else _default_detector()
    obs = read_photo(a.photo, a.lat, a.lon, a.taken_at, detector=detector, baseline_path=a.baseline, heights=heights)
    print(json.dumps(obs, indent=2))
    if a.dry_run:
        return
    if (obs["error"] or "").startswith("model call failed"):
        sys.exit(f"not saved: {obs['error']}")  # a failed call is not a reading; fix it and run again
    if not save_observation(obs, a.out):
        sys.exit(f"not saved: {obs['id']} was already reviewed by a person in {a.out}")


if __name__ == "__main__":
    main()
