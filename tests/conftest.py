import csv
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as warp

CRS = "EPSG:26915"
X0, Y0, CELL, N = 263000.0, 3287000.0, 2.0, 50
CX, CY = X0 + CELL * N / 2, Y0 - CELL * N / 2  # bowl centre


def lonlat(x, y):
    lon, lat = warp(CRS, "EPSG:4326", [x], [y])
    return lon[0], lat[0]


class TinyInputs:
    """Writes a 100 m x 100 m bowl (z = 10 + 0.001 r^2) with one USGS mark at the centre (level 12 m)."""

    def __init__(self, d):
        self.d, self.out_dir = d, d / "out"

    def __call__(self, obs_status, depth=0.3):
        d = self.d
        rows, cols = np.indices((N, N))
        r2 = ((cols + 0.5) * CELL - CELL * N / 2) ** 2 + ((rows + 0.5) * CELL - CELL * N / 2) ** 2
        with rasterio.open(d / "dem.tif", "w", driver="GTiff", height=N, width=N, count=1, dtype="float32",
                           crs=CRS, transform=from_origin(X0, Y0, CELL, CELL), nodata=-9999) as f:
            f.write((10 + 0.001 * r2).astype("float32"), 1)
        lon, lat = lonlat(CX, CY)
        with open(d / "marks.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "lat", "lon", "water_elev_m", "depth_m", "uncertainty_m", "quality", "source", "description"])
            w.writerow(["1", lat, lon, 12.0, 2.0, 0.06, "Good", "usgs_hwm", "centre"])
        line = [list(lonlat(X0 + 5, CY)), list(lonlat(X0 + 95, CY))]
        json.dump({"type": "FeatureCollection", "features": [{"type": "Feature",
                   "geometry": {"type": "LineString", "coordinates": line},
                   "properties": {"osm_id": "1", "name": "Test Rd", "highway": "residential", "is_bridge": False}}]},
                  open(d / "roads.geojson", "w"))
        obs_path = None
        if obs_status is not None:
            olon, olat = lonlat(X0 + 10, Y0 - 10)
            obs = {"id": "obs-1", "lat": olat, "lon": olon, "taken_at": "2017-08-27T09:36:00", "photo": "a.jpg",
                   "water_visible": True, "depth_m_low": depth, "depth_m_high": None if depth is None else depth + 0.2,
                   "reference_object": "sedan tire", "obstacles": [{"type": "debris", "note": "branches"}],
                   "confidence": "medium", "reasoning": "test", "model": "test", "status": obs_status, "error": None}
            obs_path = d / "observations.json"
            json.dump([obs], open(obs_path, "w"))
        return (str(d / "marks.csv"), str(d / "dem.tif"), str(d / "roads.geojson"),
                None if obs_path is None else str(obs_path), str(self.out_dir))


@pytest.fixture
def tiny_inputs(tmp_path):
    return TinyInputs(tmp_path)
