import pytest

from flood.read_photo import parse_reading, read_photo

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
