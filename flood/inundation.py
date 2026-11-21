"""Terrain-aware flood extent and depth for the 3D views (additive: flood.run is unchanged).

Method (details and validation in docs/inundation.md):
1. Extent. USACE maximum inundation extent for Brays Bayou during Harvey (daily HEC-RAS model runs,
   hosted by CUAHSI), rasterised onto the 2 m lidar DEM. It replaces the 400 m evidence circles as the
   footprint: we do not spread water by distance from the marks.
2. Water surface inside the measured reach. The 10 USGS high-water marks sit along a 2 km stretch of
   the Brays Bayou channel. Their water levels are interpolated linearly along the channel (by channel
   station) and each flooded cell takes the level at its nearest station. This is the stream-profile
   approach used for flood-inundation mapping, simplified.
3. Water surface outside the reach. No marks to interpolate from, so FwDET (Cohen et al., 2018): the
   ground elevation of the nearest mapped shoreline cell, smoothed. Blended over 300 m at the reach ends.
   Labelled lower confidence.
4. Depth = water surface - lidar ground. Flooded cells where that is <= 0 keep the USACE footprint but
   get no depth ("depth not resolved").

Not a hydraulic simulation: no flow, timing, drainage or rain ponding beyond what the USACE model shows.
Heights are metres NAVD88 (lidar datum).

Run:  python -m flood.inundation            (needs data/raw/brays_usace_pad.geojson; --fetch downloads it)
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import urllib.parse
import urllib.request
import warnings

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import rowcol, xy
from rasterio.warp import transform as warp, transform_geom
from scipy import ndimage
from scipy.spatial import cKDTree

NODATA, DRY, PROFILE, SHORELINE, UNRESOLVED = 0, 1, 2, 3, 4
CLASS_NAMES = {NODATA: "no data", DRY: "not in mapped extent", PROFILE: "estimated depth (measured reach)",
               SHORELINE: "estimated depth (lower confidence)", UNRESOLVED: "mapped flooded, depth not resolved"}
BBOX = (-95.460, 29.674, -95.425, 29.698)
LEVEL_STEP, LEVEL_MAX = 0.1, 2.0  # levels below the measured peak shown by the slider
PAD = 0.006
USACE_QUERY = "https://arcgis.cuahsi.org/arcgis/rest/services/MaximumFloodExtents_Harvey2017/MapServer/0/query"
USACE_SOURCE = "https://arcgis.cuahsi.org/arcgis/rest/services/MaximumFloodExtents_Harvey2017/MapServer"


# ---------------------------------------------------------------- channel
def order_channel(lines, max_gap_m=80.0):
    """Chain polylines ((N,2) arrays, metres) into one west->east polyline; returns (points, stations)."""
    rest = [np.asarray(line, float) for line in lines if len(line) >= 2]
    if not rest:
        raise ValueError("no channel lines")
    rest.sort(key=len, reverse=True)
    chain = rest.pop(0)
    while rest:
        best = None
        for i, line in enumerate(rest):
            for at_end in (True, False):
                anchor = chain[-1] if at_end else chain[0]
                for flip in (False, True):
                    seg = line[::-1] if flip else line
                    joint = seg[0] if at_end else seg[-1]
                    d = float(np.hypot(*(anchor - joint)))
                    if best is None or d < best[0]:
                        best = (d, i, at_end, seg)
        d, i, at_end, seg = best
        if d > max_gap_m:
            break
        rest.pop(i)
        chain = np.vstack([chain, seg]) if at_end else np.vstack([seg, chain])
    if chain[0, 0] > chain[-1, 0]:
        chain = chain[::-1]
    stations = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(chain, axis=0).T))])
    return chain, stations


def densify(points, stations, step=5.0):
    s = np.arange(0.0, stations[-1] + step, step)
    return np.c_[np.interp(s, stations, points[:, 0]), np.interp(s, stations, points[:, 1])], s


def profile_levels(at_stations, mark_stations, mark_levels):
    """Linear interpolation of mark levels by channel station; marks at the same station are averaged;
    constant beyond the first/last mark (callers only use it inside the measured reach)."""
    s = np.round(np.asarray(mark_stations, float), 1)
    w = np.asarray(mark_levels, float)
    us = np.unique(s)
    uw = np.array([w[s == v].mean() for v in us])
    return np.interp(at_stations, us, uw)


# ---------------------------------------------------------------- FwDET
def fwdet_levels(dem, flood, smooth_cells=15):
    """Water surface = ground elevation of the nearest shoreline cell (flooded cell next to a dry,
    valid cell), then a focal mean inside the flooded area. NaN outside the flood."""
    valid = ~np.isnan(dem)
    dry = valid & ~flood
    shore = flood & ndimage.binary_dilation(dry, structure=np.ones((3, 3)))
    if not shore.any():
        return np.full(dem.shape, np.nan)
    _, (ri, ci) = ndimage.distance_transform_edt(~shore, return_indices=True)
    raw = np.where(flood, dem[ri, ci], 0.0)
    num = ndimage.uniform_filter(raw, smooth_cells)
    den = ndimage.uniform_filter(flood.astype(float), smooth_cells)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(flood, num / den, np.nan)


# ---------------------------------------------------------------- model
def build_inundation(dem, transform, flood, marks_xy, mark_levels, channel_lines,
                     reach_buffer_m=150.0, blend_m=300.0):
    """Returns dict(wse, depth, cls, mark_stations, reach)."""
    flood = flood & ~np.isnan(dem)
    pts, st = order_channel(channel_lines)
    pts, st = densify(pts, st)
    tree = cKDTree(pts)
    mx, my = np.asarray(marks_xy, float).T
    mark_st = st[tree.query(np.c_[mx, my])[1]]
    lo, hi = mark_st.min() - reach_buffer_m, mark_st.max() + reach_buffer_m

    rr, cc = np.nonzero(flood)
    cx, cy = xy(transform, rr, cc)
    cell_st = st[tree.query(np.c_[cx, cy])[1]]
    prof = profile_levels(cell_st, mark_st, mark_levels)
    fw_all = fwdet_levels(dem, flood)
    fw = fw_all[rr, cc]
    # weight of FwDET: 0 inside the reach, ramps to 1 over blend_m beyond either end
    beyond = np.maximum(lo - cell_st, cell_st - hi)
    w = np.clip(beyond / blend_m, 0.0, 1.0)
    w = np.where(np.isnan(fw), 0.0, w)
    level = (1 - w) * prof + w * np.nan_to_num(fw)

    wse = np.full(dem.shape, np.nan)
    wse[rr, cc] = level
    depth = wse - dem
    cls = np.full(dem.shape, NODATA, np.uint8)
    cls[~np.isnan(dem)] = DRY
    cls[rr, cc] = np.where(beyond <= 0, PROFILE, SHORELINE)
    with np.errstate(invalid="ignore"):
        unresolved = flood & ~(depth > 0)
    cls[unresolved] = UNRESOLVED
    # Zone whose nearest channel station lies inside the measured reach (flooded or not): its outline
    # is drawn as the "edge of measured reach". Edges are cross-section lines, straight by construction.
    model_channel = pts  # densified channel (metres), reused for level connectivity
    vr, vc = np.nonzero(~np.isnan(dem))
    vx, vy = xy(transform, vr, vc)
    vst = st[tree.query(np.c_[vx, vy])[1]]
    reach_zone = np.zeros(dem.shape, bool)
    reach_zone[vr, vc] = (vst >= lo) & (vst <= hi)
    return {"wse": wse, "depth": depth, "cls": cls, "mark_stations": mark_st, "reach": (lo, hi),
            "fwdet": fw_all, "channel_length_m": float(st[-1]), "reach_zone": reach_zone, "channel": model_channel}


def validate_at_marks(model, dem, transform, marks_xy, mark_levels, mark_depths):
    """Leave-one-out check of the channel profile, plus FwDET (which never sees the marks)."""
    rows = []
    levels = np.asarray(mark_levels, float)
    st = model["mark_stations"]
    for i, (x, y) in enumerate(marks_xy):
        r, c = (int(v) for v in rowcol(transform, x, y))
        keep = np.arange(len(levels)) != i
        loo = float(profile_levels([st[i]], st[keep], levels[keep])[0])
        g = float(dem[r, c])
        rows.append({"wse_measured": round(float(levels[i]), 3), "depth_measured": round(float(mark_depths[i]), 3),
                     "ground_lidar": round(g, 3), "wse_profile_loo": round(loo, 3),
                     "wse_fwdet": None if np.isnan(model["fwdet"][r, c]) else round(float(model["fwdet"][r, c]), 3),
                     "in_usace_extent": bool(model["cls"][r, c] in (PROFILE, SHORELINE, UNRESOLVED))})

    def stats(key):
        e = np.array([row[key] - row["wse_measured"] for row in rows if row[key] is not None])
        return {"n": int(len(e)), "mae_m": round(float(np.abs(e).mean()), 3), "bias_m": round(float(e.mean()), 3),
                "max_abs_m": round(float(np.abs(e).max()), 3)}
    return {"marks": rows, "profile_leave_one_out": stats("wse_profile_loo"), "fwdet": stats("wse_fwdet"),
            "marks_in_extent": sum(r["in_usace_extent"] for r in rows)}


# ---------------------------------------------------------------- levels below the peak (connectivity)
def level_codes(ground, wse, cls, channel, step=0.1, max_drop=2.0):
    """For each cell, the largest drop D (in steps of `step`) such that, with the whole measured-peak
    water surface lowered by D, the cell is still under water AND connected (8-neighbour, through
    flooded cells) to the Brays Bayou channel. Low pockets with no connection never flood.
    255 = not under water at the peak. Codes are nested: a cell wet at drop D is wet at every smaller D.
    This is not a recorded time series: HWMs record only the peak."""
    with np.errstate(invalid="ignore"):
        freeboard = np.where((cls == PROFILE) | (cls == SHORELINE), wse - ground, np.nan)
    out = np.full(ground.shape, 255, np.uint8)
    peak = ~np.isnan(freeboard)
    out[peak] = 0  # at the measured peak the mapped (USACE) extent is shown as is
    for k in range(int(round(max_drop / step)) + 1):
        with np.errstate(invalid="ignore"):
            wet = freeboard > k * step
        labels, _ = ndimage.label(wet, structure=np.ones((3, 3)))
        ids = np.unique(labels[channel & wet])
        ids = ids[ids > 0]
        if not len(ids):
            break
        out[np.isin(labels, ids)] = k
    return out


def channel_mask(shape, transform, channel_xy, dilate=1):
    rows, cols = rowcol(transform, channel_xy[:, 0], channel_xy[:, 1])
    rows, cols = np.asarray(rows), np.asarray(cols)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    m = np.zeros(shape, bool)
    m[rows[ok], cols[ok]] = True
    return ndimage.binary_dilation(m, iterations=dilate) if dilate else m


# ---------------------------------------------------------------- export for the browser
def _blocks(a, f, fill):
    r, c = a.shape
    pr, pc = (-r) % f, (-c) % f
    a = np.pad(a, ((0, pr), (0, pc)), constant_values=fill)
    return a.reshape(a.shape[0] // f, f, a.shape[1] // f, f).swapaxes(1, 2).reshape(a.shape[0] // f, a.shape[1] // f, f * f)


def downsample(dem, wse, cls, factor):
    """Block-aggregate to factor x factor cells: ground = mean, flooded if most valid sub-cells are,
    class = most common flooded class, water surface = mean over flooded sub-cells."""
    g, w, k = _blocks(dem, factor, np.nan), _blocks(wse, factor, np.nan), _blocks(cls, factor, NODATA)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN blocks are expected at the edges
        ground = np.nanmean(g, axis=2)
        wet = (k >= PROFILE)
        n_wet, n_valid = wet.sum(2), (k != NODATA).sum(2)
        counts = np.stack([(k == v).sum(2) for v in (PROFILE, SHORELINE, UNRESOLVED)], axis=2)
        out_cls = np.where(n_valid == 0, NODATA, DRY).astype(np.uint8)
        flooded = (n_wet * 2 >= n_valid) & (n_valid > 0)
        out_cls[flooded] = np.array([PROFILE, SHORELINE, UNRESOLVED], np.uint8)[counts.argmax(2)][flooded]
        out_wse = np.where(flooded, np.nanmean(np.where(w == w, w, np.nan), axis=2), np.nan)
    return ground, out_wse, out_cls


def lonlat_affine(transform, crs, rows, cols, factor):
    """Least-squares affine (col,row) -> (lon,lat) for output cell centres, plus its max error in metres."""
    cs, rs = np.meshgrid(np.linspace(0, cols - 1, 24), np.linspace(0, rows - 1, 24))
    x = transform.c + (cs * factor + factor / 2) * transform.a
    y = transform.f + (rs * factor + factor / 2) * transform.e
    lon, lat = warp(crs, "EPSG:4326", x.ravel().tolist(), y.ravel().tolist())
    A = np.c_[cs.ravel(), rs.ravel(), np.ones(cs.size)]
    plon, *_ = np.linalg.lstsq(A, lon, rcond=None)
    plat, *_ = np.linalg.lstsq(A, lat, rcond=None)
    err = np.hypot((A @ plon - lon) * 96_500, (A @ plat - lat) * 111_000).max()
    return [float(v) for v in (*plon, *plat)], float(err)


def reach_outline(zone, transform, crs, tolerance_deg=0.00004):
    """Outline rings (lon/lat) of the measured-reach zone, simplified."""
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape
    rings = []
    for geom, val in shapes(zone.astype(np.uint8), mask=zone, transform=transform):
        g = shape(transform_geom(crs, "EPSG:4326", geom)).simplify(tolerance_deg)
        if g.area < 1e-7:
            continue
        for poly in getattr(g, "geoms", [g]):
            rings.append([[round(x, 6), round(y, 6)] for x, y in mapping(poly)["coordinates"][0]])
    return rings


def export_web(out_dir, dem, transform, crs, model, validation, factor=3, extras=None):
    extras = {**(extras or {}), "reach_outline": reach_outline(model["reach_zone"], transform, crs)}
    ground, wse, cls = downsample(dem, model["wse"], model["cls"], factor)
    rows, cols = ground.shape
    affine, err_m = lonlat_affine(transform, crs, rows, cols, factor)
    out_t = transform * rasterio.Affine.scale(factor)
    codes = level_codes(ground, wse, cls, channel_mask(ground.shape, out_t, model["channel"]), LEVEL_STEP, LEVEL_MAX)
    enc = lambda a: np.where(np.isnan(a), -32768, np.round(a * 100)).astype("<i2")  # noqa: E731 cm, int16
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "flood3d.bin"), "wb") as f:
        f.write(enc(ground).tobytes() + enc(wse).tobytes() + cls.astype(np.uint8).tobytes() + codes.tobytes())
    extras["level_step_m"], extras["level_max_drop_m"] = LEVEL_STEP, LEVEL_MAX
    extras["level_cells"] = {f"{k * LEVEL_STEP:.1f}": int(((codes != 255) & (codes >= k)).sum())
                             for k in range(0, int(round(LEVEL_MAX / LEVEL_STEP)) + 1, 5)}
    counts = {CLASS_NAMES[v]: int((cls == v).sum()) for v in CLASS_NAMES}
    header = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "cols": int(cols), "rows": int(rows), "cell_m": round(float(transform.a * factor), 2),
        "affine": affine, "affine_max_error_m": round(err_m, 3),
        "layout": "int16 ground_cm[n], int16 wse_cm[n] (-32768 = none), uint8 class[n], uint8 level_code[n] (255 = dry at peak; k = still under water and connected to the bayou when the peak surface is lowered by k*level_step_m); n = rows*cols, row 0 = north",
        "height_datum": "NAVD88 metres (lidar)", "classes": {str(k): v for k, v in CLASS_NAMES.items()},
        "cell_counts": counts, "validation": validation,
        "sources": {"extent": f"USACE Harvey maximum inundation extent, Brays Bayou (HEC-RAS), {USACE_SOURCE}",
                    "water_levels": "USGS Harvey high-water marks (data/marks.csv)",
                    "ground": "USGS 3DEP lidar DEM, 2 m (data/dem.tif)"},
        "method": "Water surface interpolated along Brays Bayou from USGS high-water marks inside the measured "
                  "reach; FwDET (nearest mapped shoreline elevation) outside it. Depth = surface - ground. "
                  "Not a hydraulic simulation.",
        **extras,
    }
    with open(os.path.join(out_dir, "flood3d.json"), "w") as f:
        json.dump(header, f, indent=1)
    return header


# ---------------------------------------------------------------- inputs
def fetch_usace_extent(path):
    w, s, e, n = BBOX[0] - PAD, BBOX[1] - PAD, BBOX[2] + PAD, BBOX[3] + PAD
    q = {"where": "RiverBasin='Brays Bayou'", "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope",
         "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "OBJECTID", "outSR": "4326",
         "returnGeometry": "true", "f": "geojson"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(f"{USACE_QUERY}?{urllib.parse.urlencode(q)}", timeout=180) as r:
        data = r.read()
    with open(path, "wb") as f:
        f.write(data)
    return path


def channel_lines_xy(context_path, crs, name="Brays Bayou"):
    ctx = json.load(open(context_path, encoding="utf-8"))
    lines = []
    for _kind, nm, coords in ctx.get("waterways", []):
        # OSM tags the concrete-lined stretch west of -95.447 as "drain" and the rest as "river".
        if nm == name:
            x, y = warp("EPSG:4326", crs, coords[0::2], coords[1::2])
            lines.append(np.c_[x, y])
    return lines


def run(extent_path="data/raw/brays_usace_pad.geojson", dem_path="data/dem.tif", marks_path="data/marks.csv",
        context_path="web/assets/context.json", out_dir="web/data", factor=3):
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(float)
        if src.nodata is not None:
            dem[dem == src.nodata] = np.nan
        transform, crs = src.transform, src.crs
    ext = json.load(open(extent_path, encoding="utf-8"))
    geoms = [transform_geom("EPSG:4326", crs, f["geometry"]) for f in ext["features"]]
    flood = rasterize(((g, 1) for g in geoms), out_shape=dem.shape, transform=transform, fill=0,
                      dtype="uint8").astype(bool)
    rows = list(csv.DictReader(open(marks_path)))
    xs, ys = warp("EPSG:4326", crs, [float(r["lon"]) for r in rows], [float(r["lat"]) for r in rows])
    levels = [float(r["water_elev_m"]) for r in rows]
    depths = [float(r["depth_m"]) for r in rows]
    model = build_inundation(dem, transform, flood, list(zip(xs, ys)), levels, channel_lines_xy(context_path, crs))
    validation = validate_at_marks(model, dem, transform, list(zip(xs, ys)), levels, depths)
    for row, r in zip(validation["marks"], rows):
        row["id"] = r["id"]
    extras = {"measured_reach_m": [round(v, 1) for v in model["reach"]],
              "channel_length_m": round(model["channel_length_m"], 1),
              "usace_features": len(ext["features"])}
    return export_web(out_dir, dem, transform, crs, model, validation, factor, extras)


def main():
    p = argparse.ArgumentParser(description="Terrain-aware flood extent and depth for the 3D views")
    p.add_argument("--extent", default="data/raw/brays_usace_pad.geojson")
    p.add_argument("--fetch", action="store_true", help="download the USACE extent first")
    p.add_argument("--out", default="web/data")
    a = p.parse_args()
    if a.fetch or not os.path.exists(a.extent):
        fetch_usace_extent(a.extent)
    h = run(a.extent, out_dir=a.out)
    print(json.dumps({k: h[k] for k in ("cols", "rows", "cell_m", "affine_max_error_m", "cell_counts", "validation")}, indent=1))


if __name__ == "__main__":
    main()
