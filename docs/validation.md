# Harvey replay extent in Meyerland

The USGS Harvey release cited in the project plan has **0% mapped study-area coverage** in the replay box. I checked the 18 study-boundary layers in the vector archives across all seven child records, transformed them to WGS84 and tested intersection with the box. None intersected. Flood overlap against that release is **undefined**. The USGS high-water marks used by the replay are point observations and do occur inside the box. [USGS data release](https://doi.org/10.5066/F7VH5N3N) · [USGS methods and study maps](https://pubs.usgs.gov/publication/sir20185070)

## Comparison with the USACE Brays Bayou extent

The U.S. Army Corps of Engineers modeled the maximum extent along Brays Bayou during Harvey. Against that reference, the replay covers **22.68%** of the modeled flood area in the full Meyerland box and **91.64%** of the modeled flood area where the replay has evidence. The replay classifies only **22.33%** of the box. These percentages measure spatial agreement between two estimates. Neither street depth nor route conditions were tested. [USACE maximum extents, hosted by CUAHSI](https://arcgis.cuahsi.org/arcgis/rest/services/MaximumFloodExtents_Harvey2017/MapServer)

| Comparison domain | Domain cells | Replay likely | USACE extent | In both | Share of likely in USACE | Share of USACE in likely | Intersection / union |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full replay box | 2,252,866 | 455,379 | 2,007,486 | 455,232 | 99.97% | 22.68% | 22.68% |
| Where the replay classifies cells | 503,102 | 455,379 | 496,741 | 455,232 | 99.97% | 91.64% | 91.62% |

The comparison uses the checked-in replay from commit `8682f39`, with 10 USGS marks, a 400 m evidence radius and zero confirmed photos. Select every depth band labeled `likely` in `web/data/water.geojson`. Rasterize the replay and reference polygons by cell center on the same approximately 2 m NAD83 / UTM 15N DEM grid. Clip both to valid DEM cells within the WGS84 box from `flood/prep_data.py` (west −95.460°, south 29.674°, east −95.425°, north 29.698°). The second row also excludes the replay's unknown polygons. Possible flooding does not count toward the likely footprint. The full-box result measures how much reference area the replay represents, including the effect of its limited reach.

## Reproduce the USACE comparison

Run from the repository root with the project environment active. The spatial query returned 257 Brays Bayou features on November 21, 2026. Verify that the GeoJSON feature count matches the service count before computing overlap, since the service can limit a response.

```sh
mkdir -p data/raw
endpoint='https://arcgis.cuahsi.org/arcgis/rest/services/MaximumFloodExtents_Harvey2017/MapServer/0/query'
query_extent() {
  curl --fail --silent --show-error --get "$endpoint" \
    --data-urlencode "where=RiverBasin='Brays Bayou'" \
    --data-urlencode 'geometry=-95.46,29.674,-95.425,29.698' \
    --data 'geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects' "$@"
}
query_extent --data 'outFields=OBJECTID&outSR=4326&returnGeometry=true&f=geojson' > data/raw/brays_usace.geojson
query_extent --data 'returnCountOnly=true&f=json' > data/raw/brays_count.json
python -c "import json; assert len(json.load(open('data/raw/brays_usace.geojson'))['features']) == json.load(open('data/raw/brays_count.json'))['count']"
python -m flood.validate_extent data/raw/brays_usace.geojson
```
