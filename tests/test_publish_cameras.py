import json

from flood.run import publish_cameras


def test_publish_keeps_display_fields_and_drops_snapshots(tmp_path):
    src = tmp_path / "cameras.json"
    src.write_text(json.dumps({"source": "Houston TranStar", "cameras": [
        {"id": "630", "road": "IH-610", "cross_street": "Braeswood", "lat": 29.68, "lon": -95.45,
         "snapshot_url": "https://example/630.jpg", "inside_replay_bbox": True},
        {"id": "x", "road": "no location"}]}))
    n = publish_cameras(str(src), str(tmp_path / "out"))
    out = json.loads((tmp_path / "out" / "cameras.json").read_text())
    assert n == 1 and out["cameras"][0]["id"] == "630"
    assert "snapshot_url" not in out["cameras"][0]


def test_missing_catalog_publishes_nothing(tmp_path):
    assert publish_cameras(str(tmp_path / "none.json"), str(tmp_path)) == 0
