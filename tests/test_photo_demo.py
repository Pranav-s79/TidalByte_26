from threading import Thread
from unittest.mock import Mock

import requests

from flood import photo_demo


def test_live_reading_requires_local_origin_and_preserves_last_success(monkeypatch):
    reading = {"water_visible": True, "confidence": "low"}
    analyze = Mock(side_effect=[reading, RuntimeError("Please retry.")])
    monkeypatch.setattr(photo_demo, "analyze", analyze)
    with photo_demo.make_server(0) as server:
        root = f"http://127.0.0.1:{server.server_port}"
        url = root + photo_demo.API_PATH
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert requests.get(url, timeout=5).json()["reading"] is None
            assert requests.post(url, headers={"Origin": "https://example.org"}, timeout=5).status_code == 403
            headers = {"Origin": root}
            with server.run_lock:
                assert requests.post(url, headers=headers, timeout=5).status_code == 409
            analyze.assert_not_called()
            assert requests.post(url, headers=headers, timeout=5).json()["reading"] == reading
            assert requests.post(url, headers=headers, timeout=5).status_code == 502
            assert requests.get(url, timeout=5).json()["reading"] == reading
        finally:
            server.shutdown()
            thread.join()


def test_locate_marks_table_points_on_the_matching_close_up():
    rows = [{"name": "passenger car or small SUV tire, top of tire"}, {"name": "passenger car or small SUV wheel, center of hub"},
            {"name": "standing adult, middle of kneecap"}]
    run = {"readings": [{"reference_object": "passenger car or small SUV tire, top of tire", "reasoning": "water at the hub"}],
           "detector": {"crops": [{"src": "demo/houston-lot-2017-08-27-a/01-car.jpg", "label": "car"}]}}
    reply = ('{"x": 400, "ground_y": 185, "points": {"passenger car or small SUV tire, top of tire": 130, '
             '"passenger car or small SUV wheel, center of hub": 158, "standing adult, middle of kneecap": 100, "made up": 90}}')
    seen = []
    m = photo_demo.locate(run, rows, client=lambda msgs: seen.append(msgs) or reply)
    assert m["crop"].endswith("01-car.jpg") and m["size"] == [562, 239] and m["ground_y"] == 185
    assert m["points"] == {"passenger car or small SUV tire, top of tire": 130, "passenger car or small SUV wheel, center of hub": 158}
    assert "water at the hub" in seen[0][0]["content"][0]["text"]  # the reading's words steer it to the same object
    assert photo_demo.parse_locate('{"x": 1, "ground_y": 50, "points": {"a": 60}}', ["a"], (100, 100)) is None  # below ground
    assert photo_demo.parse_locate('{"x": 1, "ground_y": 20, "points": {"a": 4}}', ["a"], (100, 100)) is None  # too small
    run["readings"][0]["reference_object"] = "street curb, top of curb face"
    assert photo_demo.locate(run, rows, client=lambda msgs: reply) is None  # nothing to mark it on
