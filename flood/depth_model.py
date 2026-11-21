"""Camera hotspots and the slide plot, built on flood/predict.py (Lane B, scikit-learn).

The per-camera depth model is Pri's `flood/predict.py` (the routing spec's rules), so the map, the router and
the slide all use the same numbers. This module adds:

  camera_depths(cameras, now)  each camera's planning depth now (mean + sigma, meters) from predict.depth_at
  hotspots(cameras)            DBSCAN groups nearby cameras whose planning depth is over 0.30 m
  plot_camera(readings, now, path)  readings, the model's mean and +/- 1 sigma band, and up to 60 min ahead

Readings are predict.py's: [(time, depth_m, sigma_m)], from predict.readings_from_observations. These are
estimates from camera readings, never a statement about a road.
"""
from datetime import datetime, timedelta

import numpy as np

from flood import predict

HOTSPOT_DEPTH_M = 0.30     # only cameras whose planning depth is over this can form a hotspot
HOTSPOT_EPS_M = 1500       # DBSCAN neighbourhood, meters
HOTSPOT_MIN_CAMERAS = 2


# --- hotspots ---

def camera_depths(cameras, now):
    """cameras: [{id, lat, lon, readings}] -> the same dicts plus planning_m and source ("Predicted",
    "Observed" or "Unknown: no data", following predict.depth_at's rules)."""
    out = []
    for c in cameras:
        d = predict.depth_at(c["readings"], now, now)
        out.append({**c, "planning_m": d["planning_m"] if d else None,
                    "source": d["source"] if d else "Unknown: no data"})
    return out


def hotspots(cameras):
    """cameras: [{id, lat, lon, planning_m}]. Returns hotspots, best first.

    Each hotspot: {camera_ids, n_cameras, max_planning_m, score, center: [lat, lon]}, where
    score = n_cameras x max_planning_m. Cameras DBSCAN marks as noise, or with no depth, belong to no hotspot.
    """
    from pyproj import Transformer
    from sklearn.cluster import DBSCAN

    deep = [c for c in cameras if c.get("planning_m") is not None and c["planning_m"] > HOTSPOT_DEPTH_M]
    if len(deep) < HOTSPOT_MIN_CAMERAS:
        return []
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32615", always_xy=True)  # UTM 15N, meters
    x, y = to_utm.transform([c["lon"] for c in deep], [c["lat"] for c in deep])
    labels = DBSCAN(eps=HOTSPOT_EPS_M, min_samples=HOTSPOT_MIN_CAMERAS).fit_predict(np.column_stack([x, y]))
    out = []
    for k in sorted(set(labels) - {-1}):
        members = [c for c, label in zip(deep, labels) if label == k]
        deepest = max(c["planning_m"] for c in members)
        out.append({"camera_ids": [c["id"] for c in members], "n_cameras": len(members),
                    "max_planning_m": deepest, "score": round(len(members) * deepest, 3),
                    "center": [round(float(np.mean([c["lat"] for c in members])), 6),
                               round(float(np.mean([c["lon"] for c in members])), 6)]})
    return sorted(out, key=lambda h: -h["score"])


# --- a picture for the slide ---

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, BLUE_DARK, BLUE_BAND = "#2a78d6", "#1c5cab", "#b7d3f6"


def plot_camera(readings, now, path, title="Water depth at one camera"):
    """Save a PNG: readings with their low-high range, the model's mean and +/- 1 sigma band up to now,
    and the prediction up to 60 minutes ahead (dashed). With too few recent readings, readings only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    now = now if isinstance(now, datetime) else datetime.fromisoformat(now)
    window = timedelta(minutes=predict.WINDOW_MIN)
    recent = [r for r in readings if now - window <= r[0] <= now]
    x = np.array([(t - now).total_seconds() / 60 for t, _, _ in recent])
    y = np.array([d for _, d, _ in recent])
    s = np.array([sg for _, _, sg in recent])

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    top = float(np.max(y + 2 * s)) if len(y) else 0.1
    if len(recent) >= predict.MIN_READINGS:
        model = predict._fit(recent, now)  # the same fit predict.depth_at uses
        for lo, hi, dashed in ((float(x.min()), 0.0, False), (0.0, float(predict.MAX_AHEAD_MIN), True)):
            grid = np.linspace(lo, hi, 200)
            mean, std = model.predict(grid)
            mean = np.maximum(mean, 0.0)
            ax.fill_between(grid, np.maximum(mean - std, 0), mean + std, color=BLUE_BAND,
                            alpha=0.45 if dashed else 0.7, linewidth=0, zorder=1)
            ax.plot(grid, mean, color=BLUE, linewidth=2, linestyle=(0, (5, 3)) if dashed else "-",
                    solid_capstyle="round", zorder=2)
            top = max(top, float(np.max(mean + std)))
        ax.annotate(f"predicted, up to {predict.MAX_AHEAD_MIN} min ahead", (grid[-1], mean[-1]), xytext=(-4, 10),
                    textcoords="offset points", ha="right", va="bottom", color=INK, fontsize=9)
        k = int(len(grid) * 0.75)
        ax.annotate("± 1 sigma", (grid[k], max(float(mean[k] - std[k]), 0.0)), xytext=(0, -6),
                    textcoords="offset points", ha="center", va="top", color=INK_2, fontsize=9)
    else:
        ax.text(0.02, 0.95, f"Too few recent readings to predict (needs {predict.MIN_READINGS} in "
                            f"{predict.WINDOW_MIN} min)", transform=ax.transAxes, color=INK_2, fontsize=9, va="top")
    if len(recent):
        ax.errorbar(x, y, yerr=2 * s, fmt="o", color=BLUE_DARK, ecolor=BLUE_DARK, elinewidth=1.5, capsize=3,
                    markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
        ax.annotate("readings (low–high)", (x[0], y[0] - 2 * s[0]), xytext=(6, -8), textcoords="offset points",
                    ha="left", va="top", color=INK_2, fontsize=9)
    ax.axvline(0, color=INK_2, linewidth=1, zorder=0)
    ax.annotate("now", (0, 1), xycoords=("data", "axes fraction"), xytext=(4, -4), textcoords="offset points",
                ha="left", va="top", color=INK_2, fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=12)
    ax.set_xlabel(f"minutes from {now:%H:%M}", color=INK_2)
    ax.set_ylabel("water depth (m)", color=INK_2)
    ax.set_ylim(bottom=0, top=max(top, 0.05) * 1.15)
    ax.margins(x=0.04)
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
