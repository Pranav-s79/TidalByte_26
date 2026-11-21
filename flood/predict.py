"""One camera over time: now-cast and short-term prediction (docs/routing-and-prediction.md §1).

A Gaussian process over the camera's recent readings gives depth mean and sigma at a chosen time, at most
60 minutes ahead. With too few recent readings it falls back to the latest reading (Observed) if fresh,
otherwise returns None (Unknown). Depths are meters. These are estimates, never a statement about a road.
"""
import warnings
from datetime import datetime, timedelta

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

MIN_READINGS = 4
WINDOW_MIN = 90
MAX_AHEAD_MIN = 60
OBSERVED_MAX_AGE_MIN = 20
RISE_STEP_MIN = 10
EXCLUDED_STATUS = {"needs_review", "rejected"}


def _time(t):
    return t if isinstance(t, datetime) else datetime.fromisoformat(t)


def readings_from_observations(observations):
    """Observations -> sorted [(time, depth_m, sigma_m)]. Depth = middle of the range, sigma = (high - low) / 4.

    Left out: needs_review or rejected frames, low confidence, and readings without a depth range.
    """
    out = []
    for o in observations:
        lo, hi = o.get("depth_m_low"), o.get("depth_m_high")
        if o.get("status") in EXCLUDED_STATUS or o.get("confidence") == "low" or lo is None or hi is None:
            continue
        out.append((_time(o["taken_at"]), (lo + hi) / 2, (hi - lo) / 4))
    return sorted(out, key=lambda r: r[0])


class _TrendGP:
    """Weighted linear trend + the spec's Gaussian process on what the trend leaves over.

    A zero-mean RBF process pulls a rising series back toward its average when looking ahead, which is the
    wrong direction for rising water. The trend carries the rise; its own uncertainty is added to sigma.
    """

    def __init__(self, x, y, alpha):
        X = np.column_stack([np.ones_like(x), x])
        XtW = X.T / alpha
        cov = np.linalg.inv(XtW @ X)
        self.beta = cov @ XtW @ y
        resid = y - X @ self.beta
        chi2 = float(resid @ (resid / alpha)) / max(1, len(x) - 2)  # readings noisier than stated -> widen
        self.cov = cov * max(1.0, chi2)
        kernel = (ConstantKernel(0.01, (1e-6, 25.0)) * RBF(30.0, length_scale_bounds=(15, 120))
                  + WhiteKernel(1e-4, (1e-8, 1.0)))
        self.gp = GaussianProcessRegressor(kernel=kernel, alpha=alpha, n_restarts_optimizer=2, random_state=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)  # a few points often push a bound; expected
            self.gp.fit(x.reshape(-1, 1), resid)

    def predict(self, m):
        m = np.asarray(m, dtype=float)
        X = np.column_stack([np.ones_like(m), m])
        g_mean, g_std = self.gp.predict(m.reshape(-1, 1), return_std=True)
        trend_var = np.einsum("ij,jk,ik->i", X, self.cov, X)
        return X @ self.beta + g_mean, np.sqrt(g_std ** 2 + trend_var)


def _fit(recent, now):
    x = np.array([(t - now).total_seconds() / 60 for t, _, _ in recent])
    y = np.array([d for _, d, _ in recent])
    alpha = np.maximum(np.array([s for _, _, s in recent]) ** 2, 1e-6)  # floor: low == high adds nothing
    return _TrendGP(x, y, alpha)


def depth_at(readings, now, at):
    """Depth for one camera at time `at`, given readings up to `now`.

    Returns {"source", "for_time", "mean_m", "sigma_m", "planning_m", "rise_m_per_10min"} or None (Unknown).
    source is "Predicted" (Gaussian process) or "Observed" (latest reading, when there are too few recent
    readings to fit but the latest is under 20 minutes old).
    """
    now, at = _time(now), _time(at)
    if at - now > timedelta(minutes=MAX_AHEAD_MIN):
        return None
    recent = [r for r in readings if now - timedelta(minutes=WINDOW_MIN) <= r[0] <= now]
    if len(recent) < MIN_READINGS:
        past = [r for r in readings if r[0] <= now]
        if past and now - past[-1][0] < timedelta(minutes=OBSERVED_MAX_AGE_MIN):
            t, d, s = past[-1]
            return {"source": "Observed", "for_time": t.isoformat(), "mean_m": round(d, 3), "sigma_m": round(s, 3),
                    "planning_m": round(max(0.0, d + s), 3), "rise_m_per_10min": None}
        return None
    gp = _fit(recent, now)
    m = (at - now).total_seconds() / 60
    mean, std = gp.predict([m, m + RISE_STEP_MIN])
    mu, sigma = max(0.0, float(mean[0])), float(std[0])
    return {"source": "Predicted", "for_time": at.isoformat(), "mean_m": round(mu, 3), "sigma_m": round(sigma, 3),
            "planning_m": round(mu + sigma, 3), "rise_m_per_10min": round(float(mean[1] - mean[0]), 3)}
