"""Nemotron Lightning compares the router's route options for a dispatcher (Lane B, polish task 3).

Spec: docs/routing-and-prediction.md §6. The model writes at most three sentences and may quote only numbers
that are in the router's output. Every reply is checked before anyone sees it: a number the router didn't
produce, a banned word ("safe", "clear", "passable"...) or more than three sentences rejects it. A rejected
reply gets one retry with the problems listed; if that fails too, the comparison falls back to a fixed
template built from the same numbers, which passes the same check. The agent never recommends a route and
never sets the depth limit; the dispatcher picks.

CLI: python -m flood.present_routes [web/data/routes.json] [--out web/data/route_summary.json] [--dry-run]
"""
import argparse
import datetime
import json
import os
import re
import sys

import requests

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"  # listed on integrate.api.nvidia.com
MAX_SENTENCES = 3
BANNED = re.compile(r"\b(safe|safer|safest|safely|safety|clear|clears|cleared|clearer|clearly|passable)\b", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")
SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
KIND = {"least_deep": "least-deep", "shortest_within_limit": "shortest within the limit",
        "least_unobserved": "least unobserved road"}
NO_ROUTE = "No route within the depth limit you set"

PROMPT = """You write route comparisons for an emergency dispatcher. You get route options from a routing tool as JSON.
Write at most three sentences comparing the options.
Rules:
- Quote only numbers that appear in the JSON, written exactly as they appear there. Do not round, convert units or work out new numbers.
- For each option give its letter, its distance in km, its deepest point in m with its source label and road, and its unobserved distance.
- Never use the words safe, clear or passable, in any form. Never recommend an option or tell anyone to drive: the dispatcher picks.
- Never mention a depth limit other than the one in the JSON.
- If the label starts with REPLAY, begin with "REPLAY:".
- If status is not "ok", say there is no route within the depth limit set, and name the roads in "blocking".
Reply with the sentences only."""


def facts(doc):
    """The router output, cut down to what the comparison may quote. Only these numbers may appear in the text."""
    options = []
    for o in doc.get("options", []):
        deepest = o.get("deepest") or {}
        options.append({
            "option": o.get("id"),
            "kind": KIND.get(o.get("kind"), o.get("kind")),
            "distance_km": o.get("distance_km"),
            "deepest_m": deepest.get("depth_m"),
            "deepest_source": deepest.get("source", "Unknown: no data"),
            "deepest_road": deepest.get("road"),
            "unobserved_km": o.get("unobserved_km"),
            "unobserved_percent": round((o.get("unobserved_share") or 0) * 100),
            "bridges_not_estimated": o.get("n_bridges_not_estimated", 0),
        })
    out = {"label": doc.get("label"), "depth_limit_m": doc.get("depth_limit_m"), "status": doc.get("status"),
           "options": options}
    if doc.get("status") != "ok":
        blocking = [{"road": b.get("road"), "source": b.get("source"), "depth_m": b.get("depth_m")}
                    for b in doc.get("blocking", [])]
        out.update(message=doc.get("message") or NO_ROUTE, blocking=blocking, blocking_count=len(blocking))
    return out


def _allowed_numbers(f):
    return {float(n) for n in NUMBER.findall(json.dumps(f, ensure_ascii=False))}


def check(text, f):
    """Problems with a comparison text, or [] if it may be shown."""
    problems = []
    if not text.strip():
        return ["empty reply"]
    allowed = _allowed_numbers(f)
    invented = sorted({n for n in NUMBER.findall(text) if float(n) not in allowed}, key=float)
    if invented:
        problems.append("numbers not in the router output: " + ", ".join(invented))
    banned = sorted({m.lower() for m in BANNED.findall(text)})
    if banned:
        problems.append("banned words: " + ", ".join(banned))
    sentences = len(SENTENCE_END.findall(text.strip())) or 1
    if sentences > MAX_SENTENCES:
        problems.append(f"{sentences} sentences; at most {MAX_SENTENCES}")
    return problems


def template(f):
    """A comparison built only from the router's numbers, for when the model's reply can't be used."""
    prefix = "REPLAY: " if str(f.get("label") or "").startswith("REPLAY") else ""
    if f.get("status") != "ok":
        roads = sorted({b["road"] for b in f.get("blocking", []) if b.get("road")})
        text = f"{prefix}{f.get('message', NO_ROUTE).rstrip('.')}."
        if roads:
            text += f" Over the limit on the way through: {', '.join(roads)}."
        return text
    parts = []
    for o in f["options"][:MAX_SENTENCES]:
        deepest = (f"deepest point {o['deepest_m']} m ({o['deepest_source']}) on {o['deepest_road'] or 'an unnamed road'}"
                   if o["deepest_m"] is not None else "deepest point unknown (no data on any of its roads)")
        parts.append(f"Option {o['option']} ({o['kind']}) is {o['distance_km']} km, {deepest}, "
                     f"with {o['unobserved_km']} km ({o['unobserved_percent']}%) unobserved.")
    return prefix + " ".join(parts)


def _clean(raw):
    return re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()


def chat(messages, model):
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    r = requests.post(ENDPOINT, timeout=120, headers={"Authorization": f"Bearer {key}"},
                      json={"model": model, "messages": messages, "temperature": 0, "max_tokens": 4096})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from Nemotron: {r.text[:300]}")
    choice = r.json()["choices"][0]
    content = choice["message"].get("content") or ""
    if not content and choice.get("finish_reason") == "length":
        raise RuntimeError("Nemotron used all its tokens before answering")
    return content


def present(doc, client=None, model=None, retries=1):
    """Compare the router's options. Returns {text, source ("nemotron" or "template"), model, attempts, ...}."""
    f = facts(doc)
    model = model or os.environ.get("NEMOTRON_TEXT_MODEL", DEFAULT_MODEL)
    client = client or (lambda messages: chat(messages, model))
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(f, ensure_ascii=False)}]
    attempts = []
    for _ in range(1 + retries):
        try:
            text = _clean(client(messages))
        except Exception as e:  # a failed call falls back to the template; it never blocks the dispatcher
            attempts.append({"text": None, "problems": [f"model call failed: {e}"]})
            break
        problems = check(text, f)
        attempts.append({"text": text, "problems": problems})
        if not problems:
            return _result(f, text, "nemotron", model, attempts)
        messages = messages + [{"role": "assistant", "content": text},
                               {"role": "user", "content": "That reply broke these rules: " + "; ".join(problems)
                                + ". Write it again, following every rule."}]
    text = template(f)
    assert not check(text, f), check(text, f)
    return _result(f, text, "template", model, attempts)


def _result(f, text, source, model, attempts):
    return {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "label": f.get("label"), "depth_limit_m": f.get("depth_limit_m"), "text": text, "source": source,
            "model": model if source == "nemotron" else None, "attempts": attempts}


def main(argv=None):
    p = argparse.ArgumentParser(description="Nemotron compares the router's route options for a dispatcher")
    p.add_argument("routes", nargs="?", default="web/data/routes.json")
    p.add_argument("--out", default="web/data/route_summary.json")
    p.add_argument("--dry-run", action="store_true", help="print only; don't write --out")
    a = p.parse_args(argv)
    result = present(json.load(open(a.routes)))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not a.dry_run:
        with open(a.out, "w") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
        print(f"wrote {a.out} ({result['source']})", file=sys.stderr)


if __name__ == "__main__":
    main()
