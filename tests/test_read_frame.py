import json
import os

import numpy as np
import pytest
from PIL import Image

from flood import predict
from flood import read_frame as rf

CAM = {"id": "cam-7", "lat": 29.686, "lon": -95.444,
       "reference_heights": [{"name": "jersey barrier, top", "height_m_low": 0.8, "height_m_high": 0.84, "source": "x"}]}
DRY = ('{"water_visible": false, "reference_object": null, "fraction_low": null, "fraction_high": null, '
       '"obstacles": [], "confidence": "high", "reasoning": "dry road, same as baseline", "frame_issues": []}')
WET = ('{"water_visible": true, "reference_object": "jersey barrier, top", "fraction_low": 0.25, "fraction_high": 0.36, '
       '"obstacles": [], "confidence": "medium", "reasoning": "water a quarter up the barrier", "frame_issues": %s}')


def picture(path, level=128, noise=0, seed=0):
    rng = np.random.default_rng(seed)
    img = np.clip(np.full((120, 160), level, float) + rng.normal(0, noise, (120, 160)) if noise else
                  np.tile(np.linspace(level - 40, level + 40, 160), (120, 1)), 0, 255)
    Image.fromarray(img.astype("uint8")).convert("RGB").save(path)
    return str(path)


def never(messages):
    raise AssertionError("the model must not be called")


def test_dry_frame_is_read_at_the_camera_location(tmp_path):
    frame, base = picture(tmp_path / "f.jpg"), picture(tmp_path / "b.jpg", level=120)
    o = rf.read_frame(frame, CAM, "2026-11-21T14:00:00", client=lambda m: DRY, baseline_path=base)
    assert (o["water_visible"], o["status"], o["camera_id"], o["lat"], o["lon"]) == (False, "ai_proposed", "cam-7", 29.686, -95.444)
    assert o["frame_issues"] == [] and o["baseline"] == base


def test_frozen_feed_needs_review_without_calling_the_model(tmp_path):
    frame = picture(tmp_path / "f.jpg")
    prev = tmp_path / "p.jpg"; prev.write_bytes(open(frame, "rb").read())
    o = rf.read_frame(frame, CAM, "2026-11-21T14:05:00", client=never, baseline_path=frame, previous_path=str(prev))
    assert o["status"] == "needs_review" and o["depth_m_low"] is None and "frozen_feed" in o["frame_issues"]


def test_nearly_identical_frame_counts_as_frozen_but_a_changed_one_does_not(tmp_path):
    a = picture(tmp_path / "a.png", noise=0.3, seed=1)
    b = picture(tmp_path / "b.png", noise=0.3, seed=2)
    c = picture(tmp_path / "c.png", level=80)
    assert "frozen_feed" in rf.pixel_checks(a, b)[1]
    assert "frozen_feed" not in rf.pixel_checks(a, c)[1]


def test_dark_frame_is_night_and_low_confidence(tmp_path):
    frame, base = picture(tmp_path / "f.jpg", level=15, noise=2), picture(tmp_path / "b.jpg")
    o = rf.read_frame(frame, CAM, "2026-11-21T02:00:00", client=lambda m: WET % "[]", baseline_path=base)
    assert "night" in o["frame_issues"] and o["confidence"] == "low" and o["depth_m_low"] == 0.2


def test_camera_moved_needs_review_with_no_depth(tmp_path):
    frame, base = picture(tmp_path / "f.jpg"), picture(tmp_path / "b.jpg")
    o = rf.read_frame(frame, CAM, "2026-11-21T14:10:00", client=lambda m: WET % '["camera_moved"]', baseline_path=base)
    assert o["status"] == "needs_review" and o["depth_m_low"] is None and "camera_moved" in o["error"]


def test_glare_lowers_confidence_but_keeps_the_reading(tmp_path):
    frame, base = picture(tmp_path / "f.jpg"), picture(tmp_path / "b.jpg")
    o = rf.read_frame(frame, CAM, "2026-11-21T14:15:00", client=lambda m: WET % '["glare", "made_up"]', baseline_path=base)
    assert o["frame_issues"] == ["glare"] and o["confidence"] == "low" and o["status"] == "ai_proposed"


def test_no_baseline_is_low_confidence(tmp_path):
    frame = picture(tmp_path / "f.jpg")
    o = rf.read_frame(frame, CAM, "2026-11-21T14:20:00", client=lambda m: WET % "[]")
    assert "no_baseline" in o["frame_issues"] and o["confidence"] == "low"


def test_prompt_has_frame_rules_baseline_image_and_camera_heights(tmp_path):
    frame, base = picture(tmp_path / "f.jpg"), picture(tmp_path / "b.jpg", level=100)
    sent = []
    rf.read_frame(frame, CAM, "2026-11-21T14:25:00", client=lambda m: sent.append(m) or DRY, baseline_path=base)
    content = sent[0][0]["content"]
    text = content[0]["text"]
    assert '"frame_issues"' in text and "dry baseline" in text and "jersey barrier, top: 0.8-0.84 m" in text
    assert sum(part["type"] == "image_url" for part in content) == 2  # frame + baseline


def test_good_readings_feed_predict_and_low_confidence_ones_do_not(tmp_path):
    frame, base = picture(tmp_path / "f.jpg"), picture(tmp_path / "b.jpg")
    good = rf.read_frame(frame, CAM, "2026-11-21T14:30:00", client=lambda m: WET % "[]", baseline_path=base)
    glare = rf.read_frame(frame, CAM, "2026-11-21T14:35:00", client=lambda m: WET % '["glare"]', baseline_path=base)
    readings = predict.readings_from_observations([good, glare])
    assert len(readings) == 1 and readings[0][1] == pytest.approx(0.25)


def test_camera_needs_a_location(tmp_path):
    frame = picture(tmp_path / "f.jpg")
    with pytest.raises(ValueError):
        rf.read_frame(frame, {"id": "cam-x"}, "2026-11-21T14:40:00", client=lambda m: DRY)


def test_baseline_defaults_to_the_oldest_frame_in_the_camera_folder(tmp_path):
    folder = tmp_path / "cam-7"; folder.mkdir()
    old, new = picture(folder / "1400.jpg"), picture(folder / "1405.jpg")
    os.utime(old, (1, 1))
    assert rf.find_baseline(CAM, new, frames_dir=str(tmp_path)) == old
    assert rf.find_baseline({**CAM, "dry_baseline": "x.jpg"}, new, frames_dir=str(tmp_path)) == "x.jpg"  # cameras.json
    assert rf.find_baseline({**CAM, "dry_baseline": None}, new, frames_dir=str(tmp_path)) == old       # null -> folder
    assert rf.find_baseline({**CAM, "baseline": "y.jpg"}, new, frames_dir=str(tmp_path)) == "y.jpg"


def test_load_camera_reads_cameras_json(tmp_path):
    path = tmp_path / "cameras.json"; path.write_text(json.dumps({"cameras": [CAM]}))
    assert rf.load_camera("cam-7", str(path))["lat"] == 29.686
    with pytest.raises(ValueError):
        rf.load_camera("nope", str(path))
