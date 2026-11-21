import json

import numpy as np
import rasterio
from rasterio.transform import from_origin

from flood.validate_extent import compare_extent


def test_scope_excludes_unknown_only_from_classified_comparison(tmp_path):
    # Three cell centres in the replay bbox. First is likely, second possible, third unknown.
    x, y, cell = -95.45, 29.69, 0.001
    dem = tmp_path / "dem.tif"
    with rasterio.open(dem, "w", driver="GTiff", width=3, height=1, count=1, dtype="uint8",
                       crs="EPSG:4326", transform=from_origin(x, y, cell, cell)) as src:
        src.write(np.ones((1, 3), dtype="uint8"), 1)

    def feature(start, end, status):
        left, right = x + start * cell, x + end * cell
        ring = [[left, y], [right, y], [right, y - cell], [left, y - cell], [left, y]]
        return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"status": status}}

    for name, features in [("water", [feature(0, 1, "likely"), feature(1, 2, "possible")]),
                           ("unknown", [feature(2, 3, "unknown")]), ("reference", [feature(0, 3, "mapped")])]:
        (tmp_path / (name + ".geojson")).write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    result = compare_extent(tmp_path / "reference.geojson", tmp_path, dem)
    assert result["replay_clip"]["reference_cells"] == 3
    assert result["classified_only"]["reference_cells"] == 2
    assert result["classified_only"]["pct_intersection_over_union"] == 50
    assert result["replay_clip"]["overlap_cells"] == result["classified_only"]["overlap_cells"] == 1
