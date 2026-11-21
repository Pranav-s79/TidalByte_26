import base64
import json

import pytest

import flood.read_photo as rp
from flood.read_photo import parse_reading, read_photo, save_observation

VALID = ('{"water_visible": true, "reference_object": "sedan tire", "depth_m_low": 0.35, '
         '"depth_m_high": 0.55, "obstacles": [{"type": "stalled_vehicle", "note": "car in lane"}], '
         '"confidence": "medium", "reasoning": "water at top of tire"}')


def test_parse_valid_reading():
    r = parse_reading("Here you go:\n" + VALID)
    assert r["status"] == "ai_proposed" and r["depth_m_low"] == 0.35 and r["error"] is None


def test_parse_fenced_json():
    assert parse_reading("```json\n" + VALID + "\n```")["status"] == "ai_proposed"


def test_parse_garbage_needs_review():
    r = parse_reading("I cannot tell")
    assert r["status"] == "needs_review" and r["depth_m_low"] is None and r["error"]


def test_no_reference_object_forces_null_depth():
    r = parse_reading(VALID.replace('"sedan tire"', "null"))
    assert r["depth_m_low"] is None and r["depth_m_high"] is None and r["status"] == "ai_proposed"


def test_low_above_high_needs_review():
    assert parse_reading(VALID.replace("0.35", "0.9"))["status"] == "needs_review"


def test_bad_confidence_needs_review():
    assert parse_reading(VALID.replace('"medium"', '"very sure"'))["status"] == "needs_review"


def test_photo_without_location_is_rejected(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    with pytest.raises(ValueError):
        read_photo(str(p), None, None, "2017-08-27T09:36:00", client=lambda m: VALID)


def test_read_photo_fills_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("NEMOTRON_VL_MODEL", "test-model")
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID)
    assert (o["lat"], o["lon"], o["model"], o["status"]) == (29.68, -95.44, "test-model", "ai_proposed")
    assert o["id"].startswith("obs-") and o["obstacles"][0]["type"] == "stalled_vehicle"


def test_client_error_becomes_needs_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")

    def boom(messages):
        raise RuntimeError("503 from endpoint")

    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=boom)
    assert o["status"] == "needs_review" and "503" in o["error"]


# --- found in the first real calls to nemotron-3.5-super-vl (Sujit, Nov 21) ---

class FakeResponse:
    status_code = 200

    def __init__(self, content, finish_reason="stop"):
        self._body = {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}

    def json(self):
        return self._body


def test_think_block_is_ignored():
    r = parse_reading('<think>maybe {"water_visible": false}</think>\n' + VALID)
    assert r["water_visible"] is True and r["status"] == "ai_proposed"


def test_unknown_obstacle_type_keeps_its_name():
    r = parse_reading(VALID.replace("stalled_vehicle", "fallen_sign"))
    assert r["obstacles"] == [{"type": "other", "note": "fallen_sign: car in lane"}]


def test_messages_carry_image_and_sourced_table():
    parts = rp._messages(b"jpegbytes", "a.jpg")[0]["content"]
    assert "street curb, top of curb face" in parts[0]["text"]
    assert parts[1]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"jpegbytes").decode()


def test_thinking_switch_changes_the_request(monkeypatch):
    sent = []
    monkeypatch.setattr(rp.requests, "post", lambda url, **kw: sent.append(kw["json"]) or FakeResponse(VALID))
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    rp.post_chat([])
    monkeypatch.setenv("NEMOTRON_VL_THINKING", "off")
    rp.post_chat([])
    assert sent[0]["max_tokens"] == 8192 and "chat_template_kwargs" not in sent[0]
    assert sent[1]["chat_template_kwargs"] == {"enable_thinking": False}


def test_reply_cut_off_while_reasoning_needs_review(tmp_path, monkeypatch):
    monkeypatch.setattr(rp.requests, "post", lambda url, **kw: FakeResponse(None, "length"))
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=rp.post_chat)
    assert o["status"] == "needs_review" and "tokens reasoning" in o["error"]


def test_rerun_refreshes_ai_reading_but_never_a_reviewed_one(tmp_path):
    path = str(tmp_path / "observations.json")
    assert save_observation({"id": "obs-1", "status": "ai_proposed"}, path)
    assert save_observation({"id": "obs-1", "status": "needs_review"}, path)
    assert json.load(open(path)) == [{"id": "obs-1", "status": "needs_review"}]
    json.dump([{"id": "obs-1", "status": "confirmed"}], open(path, "w"))
    assert not save_observation({"id": "obs-1", "status": "ai_proposed"}, path)
    assert json.load(open(path)) == [{"id": "obs-1", "status": "confirmed"}]


# --- PyTorch detector as a second opinion (no torch needed for these tests) ---

CAR = {"label": "car", "score": 0.97, "box": [0.26, 0.38, 0.64, 0.68]}


def test_to_objects_keeps_reference_classes_as_fractions():
    from flood.detect import to_objects
    categories = ["__background__", "person", "car", "dog"]
    objs = to_objects([[0, 0, 100, 50], [10, 10, 20, 20], [0, 0, 1, 1]], [2, 3, 1], [0.9, 0.99, 0.3],
                      categories, width=200, height=100)
    assert objs == [{"label": "car", "score": 0.9, "box": [0.0, 0.0, 0.5, 0.5]}]  # dog: not a reference; person: low score


def test_detector_boxes_go_into_the_prompt():
    text = rp._messages(b"x", "a.jpg", [CAR])[0]["content"][0]["text"]
    assert "car (0.97): left 26%, top 38%, right 64%, bottom 68%" in text


def test_depth_against_a_vehicle_the_detector_missed_needs_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID, detector=lambda path: [])
    assert o["status"] == "needs_review" and o["depth_m_low"] is None and "found no vehicle" in o["error"]


def test_depth_against_a_detected_vehicle_stands(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID, detector=lambda path: [CAR])
    assert o["status"] == "ai_proposed" and o["depth_m_low"] == 0.35 and o["detector"]["objects"] == [CAR]


def test_curb_reading_has_nothing_to_cross_check(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    curb = VALID.replace('"sedan tire"', '"street curb, top of curb face"')
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: curb, detector=lambda path: [])
    assert o["status"] == "ai_proposed"


def test_detector_failure_still_reads_the_photo(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")

    def broken(path):
        raise OSError("not an image")

    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID, detector=broken)
    assert o["status"] == "ai_proposed" and "detector failed" in o["detector"]["error"]
