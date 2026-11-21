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


def _messages(photo_bytes, photo_path):
    table = "\n".join(f"  - {r['name']}: {r['height_m_low']}-{r['height_m_high']} m"
                      for r in json.load(open(REF_PATH)))
    mime = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
    url = f"data:{mime};base64,{base64.b64encode(photo_bytes).decode()}"
    # ponytail: OpenAI-style image_url content; check against the Nemotron VL docs if the endpoint rejects it
    return [{"role": "user", "content": [{"type": "text", "text": PROMPT.format(table=table)},
                                         {"type": "image_url", "image_url": {"url": url}}]}]


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


def read_photo(photo_path, lat, lon, taken_at, client=post_chat):
    if lat is None or lon is None:
        raise ValueError("photo has no location: rejected (never guess one)")
    data = open(photo_path, "rb").read()
    try:
        reading = parse_reading(client(_messages(data, photo_path)))
    except Exception as e:  # network/auth/endpoint failure must not crash the pipeline
        reading = _empty(f"model call failed: {e}")
    return {"id": "obs-" + hashlib.sha1(data).hexdigest()[:10], "lat": lat, "lon": lon, "taken_at": taken_at,
            "photo": photo_path, **reading, "model": os.environ.get("NEMOTRON_VL_MODEL", DEFAULT_MODEL)}


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
    a = p.parse_args()
    obs = read_photo(a.photo, a.lat, a.lon, a.taken_at)
    print(json.dumps(obs, indent=2))
    if a.dry_run:
        return
    if (obs["error"] or "").startswith("model call failed"):
        sys.exit(f"not saved: {obs['error']}")  # a failed call is not a reading; fix it and run again
    if not save_observation(obs, a.out):
        sys.exit(f"not saved: {obs['id']} was already reviewed by a person in {a.out}")


if __name__ == "__main__":
    main()
