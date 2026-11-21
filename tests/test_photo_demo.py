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
