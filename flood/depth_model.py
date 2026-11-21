"""Depth over time per camera, hotspots, and a slide plot (Lane B, scikit-learn).

Part A  camera_state(readings): a Gaussian process over one camera's readings gives the depth
        now, its uncertainty, and whether the water is rising.
Part B  hotspots(cameras): DBSCAN groups nearby cameras whose cautious depth (mean + std) is
        over 30 cm, ranked by number of cameras x deepest cautious depth.
Part C  plot_camera(readings, path): the readings with error bars, the GP mean and a +/- 1 std band.

A reading is (timestamp, depth_cm_low, depth_cm_high, confidence). timestamp is an ISO string or a
datetime; confidence is "low", "medium" or "high". These are estimates from camera readings and
never a statement that a road is passable.
"""
import warnings
from datetime import datetime

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

RISING_CM = 3.0            # rise over 10 minutes above this counts as rising
LOW_CONFIDENCE_NOISE = 4   # a "low" confidence reading's variance is multiplied by this
HOTSPOT_DEPTH_CM = 30.0    # only cameras whose depth_upper is over this can form a hotspot
HOTSPOT_EPS_M = 1500       # DBSCAN neighbourhood, meters
HOTSPOT_MIN_CAMERAS = 2


# --- Part A: depth over time for one camera ---

def _time(t):
    return t if isinstance(t, datetime) else datetime.fromisoformat(t)


def _arrays(readings):
    """Readings sorted by time -> (t0, minutes since t0, mid depth, per-reading noise, low, high)."""
    rows = sorted(((_time(t), float(lo), float(hi), conf) for t, lo, hi, conf in readings), key=lambda r: r[0])
    t0 = rows[0][0]
    x = np.array([(r[0] - t0).total_seconds() / 60 for r in rows])
    lo, hi = np.array([r[1] for r in rows]), np.array([r[2] for r in rows])
    alpha = ((hi - lo) / 2) ** 2 * np.array([LOW_CONFIDENCE_NOISE if r[3] == "low" else 1 for r in rows])
    return t0, x, (lo + hi) / 2, alpha, lo, hi


def fit(readings):
    """Fit the per-camera GP. Returns (gp, t0); gp takes minutes since t0."""
    t0, x, y, alpha, _, _ = _arrays(readings)
    kernel = ConstantKernel(30 ** 2) * RBF(length_scale=20, length_scale_bounds=(5, 120)) + WhiteKernel(5 ** 2)
    # alpha floor: a reading with low == high would otherwise add zero to the diagonal
    gp = GaussianProcessRegressor(kernel=kernel, alpha=np.maximum(alpha, 1e-6), normalize_y=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)  # few points often push a bound; that's expected
        gp.fit(x.reshape(-1, 1), y)
    return gp, t0


def predict(gp, minutes):
    """GP mean and std (cm) at the given minutes since t0."""
    return gp.predict(np.asarray(minutes, dtype=float).reshape(-1, 1), return_std=True)


def camera_state(readings, now=None):
    """Depth now for one camera: {depth_mean, depth_std, depth_upper, rise_cm_per_10min, rising}.

    now defaults to the latest reading's time. rise = GP mean now minus GP mean 10 minutes earlier.
    With a single reading: that reading's range, and rising = False.
    """
    if not readings:
        raise ValueError("camera_state needs at least one reading")
    if len(readings) < 2:
        _, lo, hi, _ = readings[0]
        mean, std = (lo + hi) / 2, (hi - lo) / 2
        return {"depth_mean": mean, "depth_std": std, "depth_upper": mean + std,
                "rise_cm_per_10min": None, "rising": False}
    gp, t0 = fit(readings)
    t_now = _arrays(readings)[1][-1] if now is None else (_time(now) - t0).total_seconds() / 60
    mean, std = predict(gp, [t_now - 10, t_now])
    rise = float(mean[1] - mean[0])
    return {"depth_mean": round(float(mean[1]), 1), "depth_std": round(float(std[1]), 1),
            "depth_upper": round(float(mean[1] + std[1]), 1), "rise_cm_per_10min": round(rise, 1),
            "rising": rise > RISING_CM}


def readings_from_observations(observations):
    """Our observations (depths in meters) -> readings in cm, skipping any without a depth."""
    return [(o["taken_at"], o["depth_m_low"] * 100, o["depth_m_high"] * 100, o["confidence"])
            for o in observations if o.get("depth_m_low") is not None and o.get("depth_m_high") is not None]


# --- Part B: hotspots ---

def hotspots(cameras):
    """cameras: [{id, lat, lon, depth_upper (cm)}]. Returns hotspots, best first.

    Each hotspot: {camera_ids, n_cameras, max_depth_upper, score, center: [lat, lon]}, where
    score = n_cameras x max_depth_upper. Cameras DBSCAN marks as noise belong to no hotspot.
    """
    from pyproj import Transformer
    from sklearn.cluster import DBSCAN

    deep = [c for c in cameras if c.get("depth_upper") is not None and c["depth_upper"] > HOTSPOT_DEPTH_CM]
    if len(deep) < HOTSPOT_MIN_CAMERAS:
        return []
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32615", always_xy=True)  # UTM 15N, meters
    x, y = to_utm.transform([c["lon"] for c in deep], [c["lat"] for c in deep])
    labels = DBSCAN(eps=HOTSPOT_EPS_M, min_samples=HOTSPOT_MIN_CAMERAS).fit_predict(np.column_stack([x, y]))
    out = []
    for k in sorted(set(labels) - {-1}):
        members = [c for c, label in zip(deep, labels) if label == k]
        deepest = max(c["depth_upper"] for c in members)
        out.append({"camera_ids": [c["id"] for c in members], "n_cameras": len(members),
                    "max_depth_upper": deepest, "score": round(len(members) * deepest, 1),
                    "center": [round(float(np.mean([c["lat"] for c in members])), 6),
                               round(float(np.mean([c["lon"] for c in members])), 6)]})
    return sorted(out, key=lambda h: -h["score"])


# --- Part C: a picture for the slide ---

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, BLUE_DARK, BLUE_BAND = "#2a78d6", "#1c5cab", "#b7d3f6"


def plot_camera(readings, path, title="Water depth at one camera"):
    """Save a PNG: readings as dots with low-high error bars, the GP mean line, and a mean +/- std band."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t0, x, y, _, lo, hi = _arrays(readings)
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if len(x) >= 2:
        gp, _ = fit(readings)
        grid = np.linspace(x.min(), x.max(), 300)
        mean, std = predict(gp, grid)
        ax.fill_between(grid, mean - std, mean + std, color=BLUE_BAND, alpha=0.7, linewidth=0, zorder=1)
        ax.plot(grid, mean, color=BLUE, linewidth=2, solid_capstyle="round", zorder=2)
        ax.annotate("GP mean", (grid[-1], mean[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=INK, fontsize=9)
        mid = len(grid) // 2
        ax.annotate("± 1 std", (grid[mid], mean[mid] - std[mid]), xytext=(0, -12), textcoords="offset points",
                    ha="center", va="top", color=INK_2, fontsize=9)
    ax.errorbar(x, y, yerr=[y - lo, hi - y], fmt="o", color=BLUE_DARK, ecolor=BLUE_DARK, elinewidth=1.5,
                capsize=3, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.annotate("readings (low–high)", (x[0], hi[0]), xytext=(0, 8), textcoords="offset points",
                ha="left", va="bottom", color=INK_2, fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=12)
    ax.set_xlabel(f"minutes since {t0:%H:%M}", color=INK_2)
    ax.set_ylabel("water depth (cm)", color=INK_2)
    ax.set_ylim(bottom=0, top=max(float(np.max(hi)), 1.0) * 1.15)
    ax.margins(x=0.08)
    ax.grid(axis="y", color=GRID, linewidth=1, linestyle="-")
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path
