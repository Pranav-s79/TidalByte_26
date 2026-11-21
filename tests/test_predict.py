from datetime import datetime, timedelta

import numpy as np
import pytest

from flood.predict import depth_at, readings_from_observations

NOW = datetime(2026, 11, 21, 14, 0)


def series(slope_m_per_min, noise_m=0.0, n=13, every_min=5, start=0.10, sigma=0.02, seed=0):
    """n readings ending at NOW, every `every_min` minutes."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        t = NOW - timedelta(minutes=every_min * (n - 1 - i))
        mins = every_min * i
        out.append((t, start + slope_m_per_min * mins + rng.normal(0, noise_m), sigma))
    return out


def truth(slope, n=13, every_min=5, start=0.10, ahead=0):
    return start + slope * (every_min * (n - 1) + ahead)


def test_rising_series_30_min_prediction_within_2_sigma():
    r = depth_at(series(0.02, noise_m=0.01), NOW, NOW + timedelta(minutes=30))
    assert r["source"] == "Predicted"
    assert abs(r["mean_m"] - truth(0.02, ahead=30)) <= 2 * r["sigma_m"]


def test_flat_series_has_no_rise():
    r = depth_at(series(0.0, noise_m=0.005), NOW, NOW)
    assert abs(r["rise_m_per_10min"]) < 0.01


def test_rising_series_reports_rise():
    r = depth_at(series(0.02, noise_m=0.005), NOW, NOW)
    assert r["rise_m_per_10min"] > 0.1


def test_uncertainty_grows_further_ahead():
    s = series(0.01, noise_m=0.005)
    assert depth_at(s, NOW, NOW + timedelta(minutes=60))["sigma_m"] > depth_at(s, NOW, NOW + timedelta(minutes=10))["sigma_m"]


def test_more_than_60_minutes_ahead_is_none():
    assert depth_at(series(0.01), NOW, NOW + timedelta(minutes=61)) is None


def test_fewer_than_4_recent_readings_is_not_a_prediction():
    old = [(NOW - timedelta(minutes=m), 0.2, 0.02) for m in (150, 120, 100)]  # outside the 90-min window
    recent3 = [(NOW - timedelta(minutes=m), 0.2, 0.02) for m in (25, 15, 5)]
    r = depth_at(old + recent3, NOW, NOW + timedelta(minutes=10))
    assert r["source"] == "Observed"  # latest reading is 5 min old
    assert r["for_time"] == (NOW - timedelta(minutes=5)).isoformat()

    stale = [(NOW - timedelta(minutes=m), 0.2, 0.02) for m in (60, 45, 30)]
    assert depth_at(stale, NOW, NOW) is None  # latest is 30 min old -> Unknown


def test_planning_depth_is_mean_plus_sigma():
    r = depth_at(series(0.0), NOW, NOW + timedelta(minutes=20))
    assert abs(r["planning_m"] - (r["mean_m"] + r["sigma_m"])) < 1e-3


def test_readings_skip_review_low_confidence_and_missing_depth():
    obs = [{"taken_at": "2026-11-21T13:50:00", "depth_m_low": 0.1, "depth_m_high": 0.3, "confidence": "medium", "status": "ai_proposed"},
           {"taken_at": "2026-11-21T13:40:00", "depth_m_low": 0.1, "depth_m_high": 0.3, "confidence": "low", "status": "confirmed"},
           {"taken_at": "2026-11-21T13:30:00", "depth_m_low": 0.1, "depth_m_high": 0.3, "confidence": "high", "status": "needs_review"},
           {"taken_at": "2026-11-21T13:20:00", "depth_m_low": None, "depth_m_high": None, "confidence": "high", "status": "confirmed"},
           {"taken_at": "2026-11-21T13:10:00", "depth_m_low": 0.2, "depth_m_high": 0.6, "confidence": "high", "status": "confirmed"}]
    r = readings_from_observations(obs)
    assert [t.minute for t, _, _ in r] == [10, 50]
    assert r[0][1:] == pytest.approx((0.4, 0.1))  # middle of 0.2-0.6, sigma = 0.4 / 4
