"""Compare replay flood polygons with a reference extent on the Meyerland DEM grid."""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

from flood.prep_data import BBOX


def compare_extent(reference, layers=Path("web/data"), dem_path=Path("data/dem.tif")):
    def geometries(path, status=None):
        for f in json.loads(path.read_text())["features"]:
            if status is None or f["properties"]["status"] == status:
                yield f["geometry"]

    with rasterio.open(dem_path) as dem:
        def mask(geoms):
            projected = [transform_geom("EPSG:4326", dem.crs, g) for g in geoms]
            if not projected:
                return np.zeros(dem.shape, dtype=bool)
            return geometry_mask(projected, dem.shape, dem.transform, invert=True)

        w, s, e, n = BBOX
        boundary = {"type": "Polygon", "coordinates": [[(w, s), (e, s), (e, n), (w, n), (w, s)]]}
        clip = mask([boundary]) & (dem.read_masks(1) > 0)
        unknown = mask(geometries(layers / "unknown.geojson"))
        likely = mask(geometries(layers / "water.geojson", "likely"))
        mapped = mask(geometries(reference))

    result = {}
    for name, domain in [("replay_clip", clip), ("classified_only", clip & ~unknown)]:
        overlap = int((domain & likely & mapped).sum())
        likely_count = int((domain & likely).sum())
        reference_count = int((domain & mapped).sum())
        union = likely_count + reference_count - overlap
        result[name] = {
            "domain_cells": int(domain.sum()), "likely_cells": likely_count,
            "reference_cells": reference_count, "overlap_cells": overlap,
            "pct_likely_in_reference": 100 * overlap / likely_count if likely_count else None,
            "pct_reference_in_likely": 100 * overlap / reference_count if reference_count else None,
            "pct_intersection_over_union": 100 * overlap / union if union else None,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="flood polygons in WGS84 GeoJSON")
    print(json.dumps(compare_extent(parser.parse_args().reference), indent=2))
