import csv
import json
import os

import pytest
import rasterio
from rasterio.transform import rowcol
from rasterio.warp import transform as warp

from flood.prep_data import BBOX, marks_from_hwm_csv

COLS = ["latitude_dd", "longitude_dd", "elev_ft", "height_above_gnd", "uncertainty", "hwm_id",
        "hwmQualityName", "siteDescription", "flagMemberName"]


def test_marks_from_hwm_csv_filters_and_converts(tmp_path):
    src, out = tmp_path / "hwm.csv", tmp_path / "marks.csv"
    with open(src, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerow([27.83, -97.06, 9.7, 3.85, 0.19, 1, "Good: +/- 0.10 ft", "outside bbox", "A Person"])
        w.writerow([29.685, -95.44, 51.0, "", 0.19, 2, "Good: +/- 0.10 ft", "no height", "A Person"])
        w.writerow([29.68111, -95.45026, 53.432, 4.57, 0.190289, 3, "Good: +/- 0.10 ft", "Meyerwood Dr", "A Person"])
    n = marks_from_hwm_csv(str(src), BBOX, str(out))
    rows = list(csv.DictReader(open(out)))
    assert n == 1 and len(rows) == 1
    assert abs(float(rows[0]["water_elev_m"]) - 16.2861) < 1e-3
    assert abs(float(rows[0]["depth_m"]) - 1.3929) < 1e-3
    assert abs(float(rows[0]["uncertainty_m"]) - 0.0580) < 1e-3
    assert rows[0]["source"] == "usgs_hwm" and rows[0]["quality"] == "Good" and rows[0]["id"] == "3"
    assert "A Person" not in open(out).read()


@pytest.mark.skipif(not os.path.exists("data/dem.tif"), reason="run prep first")
def test_real_marks_ground_matches_dem():
    marks = list(csv.DictReader(open("data/marks.csv")))
    with rasterio.open("data/dem.tif") as src:
        dem = src.read(1)
        xs, ys = warp("EPSG:4326", src.crs, [float(m["lon"]) for m in marks], [float(m["lat"]) for m in marks])
        cells = [rowcol(src.transform, x, y) for x, y in zip(xs, ys)]
    implied = [float(m["water_elev_m"]) - float(m["depth_m"]) for m in marks]
    agree = sum(abs(float(dem[int(r), int(c)]) - g) < 0.5 for (r, c), g in zip(cells, implied))
    assert agree >= 0.8 * len(marks)


@pytest.mark.skipif(not os.path.exists("data/roads.geojson"), reason="run prep first")
def test_real_roads_have_bridges():
    fc = json.load(open("data/roads.geojson"))
    assert len(fc["features"]) > 300
    assert any(f["properties"]["is_bridge"] for f in fc["features"])
