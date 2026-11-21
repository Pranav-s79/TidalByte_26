"""Nemotron VL reads one flood photo into an observation (spec: data/observations.json)."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re

import requests

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-nano-12b-v2-vl"  # override with NEMOTRON_VL_MODEL from the event kit
REF_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "reference_heights.json")
CONFIDENCE = {"low", "medium", "high"}
OBSTACLE_TYPES = {"stalled_vehicle", "debris", "downed_tree", "barricade", "other"}

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
- Give a range, never a single number. Do not guess the location. List only obstacles that block a road."""


def _empty(error):
    return {"water_visible": False, "reference_object": None, "depth_m_low": None, "depth_m_high": None,
            "obstacles": [], "confidence": "low", "reasoning": "", "status": "needs_review", "error": error}


def parse_reading(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return _empty("no JSON object in model output")
    try:
        d = json.loads(m.group(0))
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
        obstacles = [{"type": o.get("type") if o.get("type") in OBSTACLE_TYPES else "other",
                      "note": str(o.get("note", ""))} for o in d.get("obstacles") or []]
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


def post_chat(messages):
    r = requests.post(ENDPOINT, timeout=120,
                      headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
                      json={"model": os.environ.get("NEMOTRON_VL_MODEL", DEFAULT_MODEL),
                            "messages": messages, "temperature": 0, "max_tokens": 800})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


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
    if not a.dry_run:
        items = json.load(open(a.out)) if os.path.exists(a.out) else []
        json.dump([o for o in items if o["id"] != obs["id"]] + [obs], open(a.out, "w"), indent=2)


if __name__ == "__main__":
    main()
