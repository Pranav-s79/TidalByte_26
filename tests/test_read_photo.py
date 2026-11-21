import base64
import json

import pytest

import flood.read_photo as rp
from flood.read_photo import parse_reading, read_photo, save_observation

TIRE = "passenger car or small SUV tire, top of tire"  # 0.60-0.72 m in data/reference_heights.json
VALID = ('{"water_visible": true, "reference_object": "' + TIRE + '", "fraction_low": 0.5, '
         '"fraction_high": 0.75, "obstacles": [{"type": "stalled_vehicle", "note": "car in lane"}], '
         '"confidence": "medium", "reasoning": "water at top of tire"}')


def test_parse_valid_reading():
    r = parse_reading("Here you go:\n" + VALID)
    assert r["status"] == "ai_proposed" and (r["depth_m_low"], r["depth_m_high"]) == (0.3, 0.54) and r["error"] is None


def test_parse_fenced_json():
    assert parse_reading("```json\n" + VALID + "\n```")["status"] == "ai_proposed"


def test_parse_garbage_needs_review():
    r = parse_reading("I cannot tell")
    assert r["status"] == "needs_review" and r["depth_m_low"] is None and r["error"]


def test_no_reference_object_forces_null_depth():
    r = parse_reading(VALID.replace('"' + TIRE + '"', "null"))
    assert r["depth_m_low"] is None and r["depth_m_high"] is None and r["status"] == "ai_proposed"


def test_low_above_high_needs_review():
    assert parse_reading(VALID.replace("0.5,", "0.9,"))["status"] == "needs_review"


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
    assert sent[0]["max_tokens"] == 16384 and "chat_template_kwargs" not in sent[0]
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


# --- PyTorch detector (flood/detect.py): no torch needed for these tests ---

from PIL import Image

from flood.detect import debug_draw, keep, make_crops, padded_box

CAR = {"label": "car", "score": 0.91, "box": [330, 357, 826, 686]}


def test_keep_filters_classes_and_score_with_pixel_boxes():
    categories = ["__background__", "person", "car", "dog", "bench"]
    objs = keep([[0, 0, 100.4, 50.6], [10, 10, 20, 20], [0, 0, 1, 1], [5, 5, 9, 9]], [2, 3, 1, 4],
                [0.91, 0.99, 0.59, 0.95], categories)
    assert objs == [{"label": "car", "score": 0.91, "box": [0, 0, 100, 51]}]  # dog/bench not kept; person under 0.6


def test_padded_box_grows_20_percent_and_stays_in_the_image():
    assert padded_box([100, 100, 200, 150], 1000, 1000) == [80, 90, 220, 160]
    assert padded_box([0, 0, 100, 100], 110, 110) == [0, 0, 110, 110]


def test_crops_saved_for_every_object_and_two_largest_returned(tmp_path):
    img = Image.new("RGB", (400, 300), "white")
    dets = [{"label": "person", "score": 0.9, "box": [10, 10, 30, 60]},          # 1,000 px
            {"label": "car", "score": 0.8, "box": [100, 100, 300, 200]},         # 20,000 px
            {"label": "stop sign", "score": 0.7, "box": [320, 20, 380, 80]}]     # 3,600 px
    crops = make_crops(img, dets, str(tmp_path))
    assert [c["label"] for c in crops] == ["car", "stop sign"]
    assert crops[0]["crop_box"] == [60, 80, 340, 220] and crops[0]["jpeg"][:2] == b"\xff\xd8"
    assert len(list(tmp_path.iterdir())) == 3


def test_debug_draw_saves_a_boxed_copy(tmp_path):
    src = tmp_path / "frame.png"; Image.new("RGB", (400, 300), "white").save(src)
    out = debug_draw(str(src), [{"label": "car", "score": 0.91, "box": [100, 100, 300, 200]}], str(tmp_path / "debug.png"))
    drawn = Image.open(out)
    assert drawn.size == (400, 300) and drawn.getpixel((200, 200)) != (255, 255, 255)  # bottom edge of the box
    assert Image.open(src).getpixel((200, 200)) == (255, 255, 255)                     # original untouched


def test_super_vl_gets_frame_baseline_crops_boxes_and_camera_heights():
    crops = [{"label": "car", "score": 0.91, "box": [330, 357, 826, 686], "jpeg": b"crop1"},
             {"label": "person", "score": 0.8, "box": [1, 2, 3, 4], "jpeg": b"crop2"}]
    heights = [{"name": "jersey barrier, top", "height_m_low": 0.8, "height_m_high": 0.84, "source": "x"}]
    content = rp._messages(b"frame", "a.jpg", [CAR], crops, (b"dry", "image/jpeg"), heights)[0]["content"]
    text = content[0]["text"]
    assert "car at [330,357,826,686], score 0.91" in text and "jersey barrier, top: 0.8-0.84 m" in text
    images = [part["image_url"]["url"] for part in content if part["type"] == "image_url"]
    assert [base64.b64decode(u.split(",")[1]) for u in images] == [b"frame", b"dry", b"crop1", b"crop2"]


def test_camera_heights_come_from_cameras_json(tmp_path):
    path = tmp_path / "cameras.json"
    path.write_text(json.dumps([{"id": "cam-1", "reference_heights": [{"name": "curb"}]}, {"id": "cam-2"}]))
    assert rp.camera_heights("cam-1", str(path)) == [{"name": "curb"}]
    assert rp.camera_heights("cam-2", str(path)) is None
    with pytest.raises(ValueError):
        rp.camera_heights("cam-9", str(path))


def test_depth_against_a_vehicle_the_detector_missed_needs_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID,
                   detector=lambda path, crop_dir: ([], []))
    assert o["status"] == "needs_review" and o["depth_m_low"] is None and "found no vehicle" in o["error"]


def test_depth_against_a_detected_vehicle_stands(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID,
                   detector=lambda path, crop_dir: ([CAR], []))
    assert o["status"] == "ai_proposed" and o["depth_m_low"] == 0.3 and o["detector"]["objects"] == [CAR]


def test_curb_reading_has_nothing_to_cross_check(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    curb = VALID.replace(TIRE, "street curb, top of curb face")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: curb,
                   detector=lambda path, crop_dir: ([], []))
    assert o["status"] == "ai_proposed"


def test_detector_failure_still_reads_the_photo(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")

    def broken(path, crop_dir):
        raise OSError("not an image")

    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID, detector=broken)
    assert o["status"] == "ai_proposed" and "detector failed" in o["detector"]["error"]


# --- Improvement 1: the model gives a fraction of a reference height; code turns it into a depth ---

def test_a_third_of_the_tire_is_20_to_24_cm():
    r = parse_reading(VALID.replace("0.5,", "0.333,").replace("0.75,", "0.333,"))
    assert (r["depth_m_low"], r["depth_m_high"]) == (0.2, 0.24) and (r["fraction_low"], r["fraction_high"]) == (0.333, 0.333)


def test_reference_not_in_the_table_needs_review():
    r = parse_reading(VALID.replace(TIRE, "sedan tire"))
    assert r["status"] == "needs_review" and r["depth_m_low"] is None and "not in the height table" in r["error"]


def test_a_little_above_the_point_is_kept_but_far_above_needs_review():
    r = parse_reading(VALID.replace("0.75,", "1.2,"))
    assert r["status"] == "ai_proposed" and r["depth_m_high"] == 0.86  # 1.2 x 0.72
    assert parse_reading(VALID.replace("0.75,", "1.6,"))["status"] == "needs_review"


def test_camera_table_is_used_for_the_depth():
    heights = [{"name": "jersey barrier, top", "height_m_low": 0.8, "height_m_high": 0.84}]
    r = parse_reading(VALID.replace(TIRE, "Jersey barrier, top"), heights)
    assert (r["depth_m_low"], r["depth_m_high"]) == (0.4, 0.63)


# --- Improvement 2: three reads at once; they must agree or the photo goes to review ---

def replies(*texts):
    it = iter(texts)
    return lambda m: next(it)


def frac(lo, hi):
    return VALID.replace("0.5,", f"{lo},").replace("0.75,", f"{hi},")


def test_agreeing_reads_give_the_envelope(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(frac(0.3, 0.4), frac(0.35, 0.5), frac(0.38, 0.45)))
    assert o["status"] == "ai_proposed" and len(o["readings"]) == 3
    assert (o["depth_m_low"], o["depth_m_high"]) == (0.18, 0.36) and (o["fraction_low"], o["fraction_high"]) == (0.3, 0.5)


def test_two_of_three_agree_and_the_odd_read_is_named(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    seq = iter([frac(0.3, 0.4), frac(0.35, 0.5), frac(0.8, 1)])
    o = read_photo(str(p), 29.68, -95.44, "t", client=lambda m: next(seq))
    odd = next(i for i, r in enumerate(o["readings"]) if r["depth_m_low"] == 0.48) + 1
    assert o["status"] == "ai_proposed" and (o["depth_m_low"], o["depth_m_high"]) == (0.18, 0.36)
    assert odd not in o["agreeing"] and len(o["agreeing"]) == 2 and f"read {odd}: 0.48-0.72 m" in o["note"]


def test_no_majority_goes_to_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(frac(0.1, 0.2), frac(0.4, 0.5), frac(0.8, 1)))
    assert o["status"] == "needs_review" and o["depth_m_low"] is None and "disagree" in o["error"]
    assert sorted(r["depth_m_low"] for r in o["readings"]) == [0.06, 0.24, 0.48]  # every read kept for the reviewer


def test_two_pairs_that_each_agree_but_not_all_three_go_to_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")  # 0.18-0.29, 0.24-0.43, 0.42-0.65: 1&2 and 2&3 meet, 1&3 don't
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(frac(0.3, 0.4), frac(0.4, 0.6), frac(0.7, 0.9)))
    assert o["status"] == "needs_review" and "disagree" in o["error"]


def test_depth_in_two_reads_beats_no_depth_in_one(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(VALID, VALID, VALID.replace('"' + TIRE + '"', "null")))
    assert o["status"] == "ai_proposed" and o["depth_m_low"] == 0.3 and "water, no depth" in o["note"]


def test_a_detector_mismatch_in_any_read_sends_the_photo_to_review(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    curb = VALID.replace(TIRE, "street curb, top of curb face")
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(VALID, curb, curb), detector=lambda path, crop_dir: ([], []))
    assert o["status"] == "needs_review" and "found no vehicle" in o["error"]


def test_a_failed_read_does_not_vote(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    calls = iter([VALID, VALID, None])

    def flaky(m):
        reply = next(calls)
        if reply is None:
            raise RuntimeError("503")
        return reply

    o = read_photo(str(p), 29.68, -95.44, "t", client=flaky)
    assert o["status"] == "ai_proposed" and o["depth_m_low"] == 0.3 and "503" in o["note"]


def test_one_clean_read_is_too_few_to_vote(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "t", client=replies(VALID, "no json", "still no json"))
    assert o["status"] == "needs_review" and o["depth_m_low"] is None


def test_reads_run_at_the_same_time(tmp_path):
    import threading
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    barrier = threading.Barrier(3, timeout=5)  # sequential reads would never all reach it
    o = read_photo(str(p), 29.68, -95.44, "t", client=lambda m: barrier.wait() * 0 or VALID)
    assert o["status"] == "ai_proposed"


def test_one_read_when_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("NEMOTRON_VL_READS", "1")
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    sent = []
    o = read_photo(str(p), 29.68, -95.44, "t", client=lambda m: sent.append(m) or VALID)
    assert len(sent) == 1 and "readings" not in o
