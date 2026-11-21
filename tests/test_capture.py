import io
import json
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
import pytest
import requests

from flood import capture
from flood.prep_data import BBOX


def test_catalog_matches_replay_roads():
    root = Path(__file__).resolve().parents[1] / "data"
    cameras = json.loads((root / "cameras.json").read_text())["cameras"]
    road_ids = {f["properties"]["osm_id"] for f in json.loads((root / "roads.geojson").read_text())["features"]}
    assert len({c["id"] for c in cameras}) == len(cameras) >= 5
    west, south, east, north = BBOX
    for c in cameras:
        assert c["snapshot_url"].endswith("/" + c["id"] + ".jpg")
        assert c["inside_replay_bbox"] == (west <= c["lon"] <= east and south <= c["lat"] <= north)
        assert set(c["candidate_osm_ids"] + c["visible_osm_ids"]) <= road_ids


def test_capture_requires_permission_before_fetch(monkeypatch):
    get = Mock()
    monkeypatch.setattr(capture.requests, "get", get)
    with pytest.raises(SystemExit) as stopped:
        capture.main([])
    assert stopped.value.code == 2
    get.assert_not_called()


def test_batch_preserves_valid_frames_and_reports_failed_camera(tmp_path, monkeypatch, capsys):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="JPEG")
    payload = buf.getvalue()
    catalog = tmp_path / "cameras.json"
    catalog.write_text(json.dumps({"cameras": [
        {"id": "1", "snapshot_url": "https://example.test/1.jpg"},
        {"id": "2", "snapshot_url": "https://example.test/2.jpg"},
    ]}))

    def get(url, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(b"<html>offline</html>" if url.endswith("1.jpg") else payload)
        return response

    monkeypatch.setattr(capture.requests, "get", get)
    args = ["--catalog", str(catalog), "--frames", str(tmp_path), "--permission-confirmed"]
    assert capture.main(args) == 1
    assert "Camera 1" in capsys.readouterr().err
    assert not list((tmp_path / "1").iterdir())
    assert capture.main(args + ["--camera", "2"]) == 0
    frames = list((tmp_path / "2").glob("*.jpg"))
    assert len(frames) == 2
    assert all(frame.read_bytes() == payload for frame in frames)
