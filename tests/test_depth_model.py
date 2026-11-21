from datetime import datetime, timedelta

import pytest

from flood.depth_model import _arrays, camera_state, fit, hotspots, plot_camera, predict

T0 = datetime(2026, 11, 21, 14, 0)


def series(depths, minutes_apart=5, half_range=2, confidence="medium"):
    return [(T0 + timedelta(minutes=i * minutes_apart), d - half_range, d + half_range, confidence)
            for i, d in enumerate(depths)]


# --- the three tests from the spec ---

def test_rising_series_is_rising():
    state = camera_state(series([10, 15, 22, 30]))
    assert state["rising"] is True and state["rise_cm_per_10min"] > 3


def test_flat_series_is_not_rising():
    state = camera_state(series([20, 20, 20, 20]))
    assert state["rising"] is False and abs(state["rise_cm_per_10min"]) <= 3


def test_std_smaller_at_a_reading_than_between_far_apart_readings():
    readings = [(T0, 18, 22, "medium"), (T0 + timedelta(minutes=5), 18, 22, "medium"),
                (T0 + timedelta(minutes=300), 18, 22, "medium"), (T0 + timedelta(minutes=305), 18, 22, "medium")]
    gp, _ = fit(readings)
    _, std = predict(gp, [0, 152.5])
    assert std[0] < std[1]


# --- smaller checks ---

def test_single_reading_returns_its_range():
    state = camera_state([(T0, 10, 20, "high")])
    assert state == {"depth_mean": 15, "depth_std": 5, "depth_upper": 20, "rise_cm_per_10min": None, "rising": False}


def test_low_confidence_reading_gets_four_times_the_noise():
    _, _, _, alpha, _, _ = _arrays([(T0, 10, 14, "medium"), (T0 + timedelta(minutes=5), 10, 14, "low")])
    assert alpha.tolist() == [4.0, 16.0]


def test_hotspots_cluster_deep_cameras_and_rank_them():
    cams = [
        {"id": "a1", "lat": 29.6860, "lon": -95.4440, "depth_upper": 45},  # Meyerland, ~1 km apart
        {"id": "a2", "lat": 29.6900, "lon": -95.4360, "depth_upper": 38},
        {"id": "a3", "lat": 29.6880, "lon": -95.4400, "depth_upper": 12},  # shallow: not considered
        {"id": "b1", "lat": 29.7600, "lon": -95.3700, "depth_upper": 60},  # downtown, ~11 km away
        {"id": "b2", "lat": 29.7610, "lon": -95.3690, "depth_upper": 31},
        {"id": "c1", "lat": 29.9000, "lon": -95.6000, "depth_upper": 90},  # alone: DBSCAN noise
    ]
    out = hotspots(cams)
    assert [h["camera_ids"] for h in out] == [["b1", "b2"], ["a1", "a2"]]   # 2 x 60 = 120 beats 2 x 45 = 90
    assert out[0]["score"] == 120 and out[1]["max_depth_upper"] == 45


def test_no_hotspot_without_two_deep_cameras():
    assert hotspots([{"id": "x", "lat": 29.68, "lon": -95.44, "depth_upper": 80}]) == []


def test_plot_writes_a_png(tmp_path):
    out = plot_camera(series([10, 15, 22, 30]), str(tmp_path / "cam.png"))
    assert open(out, "rb").read(8) == b"\x89PNG\r\n\x1a\n"


def test_empty_readings_raise():
    with pytest.raises(ValueError):
        camera_state([])
