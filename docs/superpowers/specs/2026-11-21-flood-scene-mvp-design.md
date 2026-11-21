# Flood Scene 3D: MVP Design

Nov 21, 2026 · status: **built** (MVP on `main` at 1:00 PM). Product direction since then: TranStar cameras + short-term prediction + least-deep routing, specified in [`docs/routing-and-prediction.md`](../../routing-and-prediction.md).

## Intent

A dispatcher is about to send crews into a flooded neighborhood. Before they do, they open a 3D map of that neighborhood and size up the scene: where water probably is, how deep it is where we have evidence, what blocks roads, and where we simply don't know. Every layer says where it came from (USGS measured, AI-proposed, estimated, unknown).

This narrows `CLAUDE.md`: the 3D scene is now the centerpiece, built on top of the photo-to-pin idea rather than after it. The decision-support rules in `CLAUDE.md` still apply in full.

## Goals

1. **MVP first:** pass data in, get output out. One command turns input files into map layers; one web page shows them in 3D.
2. After the MVP, four teammates extend their own part independently against fixed file contracts.

## Non-goals

- Routing inside the MVP itself. Routing is now part of the product direction; its rules and math are in `docs/routing-and-prediction.md`.
- Flood forecasting or hydraulic simulation.
- Live camera ingestion (stretch only).

## Anti-goals (a failure even if it works)

- Any area or road shown or worded as "safe", "clear" or "passable".
- Unknown areas that look like dry ground.
- AI-proposed readings that look like measurements, or that change the water layer before a person confirms them.
- Invented coordinates, depths or photos.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Area | Meyerland, Houston, along Brays Bayou. Bounding box lon −95.460 to −95.425, lat 29.674 to 29.698 | It has the densest set of measured depths in Harris County: 10 USGS marks within 1.5 km, 9 rated good quality |
| Event | Hurricane Harvey, Aug 2017, shown as a **replay** | Measured data exists; no live flood today |
| Water levels | USGS high-water marks: `Harvey_HWMs_20180322.csv` from HydroShare resource `615d426f70cc4346875c725b4b8fdc59` | Public data with measured water elevation and depth above ground |
| Ground | USGS 1 m DEM, project `TX_CoastalRegion_2018_A18`, tile `x26y329`, clipped to the bounding box and resampled to 2 m | Surveyed right after Harvey; NAVD88, the same vertical datum as the marks |
| Roads and bridges | OpenStreetMap through osmnx, saved once to `data/roads.geojson` | 895 road ways and 33 bridges in the box; saving a copy removes the dependency on the flaky Overpass server |
| Buildings in 3D | Extruded from OpenFreeMap vector tiles (OpenStreetMap buildings) | Free, no key. OSM has no heights here, so heights are default values labeled "approximate" |
| Water layer | Bathtub fill (details below) | Simple, explainable math, and hydrologists recognize the method |
| Display | Static web page: MapLibre GL JS with the OpenFreeMap "liberty" style, loading GeoJSON files | No backend for the MVP; the web page reads files |
| AI | Nemotron VL on NVIDIA Build reads a photo and returns structured JSON | Required for the NVIDIA track; it does real work |
| Review | An AI reading starts as `ai_proposed`. Only `confirmed` readings with a depth feed the water layer | Keeps a human in the loop |

### Bathtub fill

1. Each mark gives a water level (m, NAVD88) as a low/high pair:
   - USGS mark: `water_elev_m ± uncertainty_m`
   - Confirmed AI reading: `ground_at_photo + depth_low` and `ground_at_photo + depth_high`
2. Water level per cell = inverse-distance blend (power 2) of every mark within **400 m**. Cells with no mark within 400 m get NaN and show as **unknown**.
3. A cell is wet if its level is above the ground and it connects (8-neighbour) through wet cells to a mark's cell. Mark cells count as wet.
4. Depth = level − ground on wet cells, 0 on dry cells, NaN on unknown cells.
5. The fill runs twice, once with the low levels and once with the high levels. **Likely** = wet in the low run. **Possible** = wet only in the high run. **No flooding estimated** = dry in both runs and known.
6. Bridges: a bare-earth DEM has the bridge deck removed, so a road segment tagged as a bridge gets the status `bridge_not_estimated` instead of a depth.

Label on the layer: **"Estimated peak extent from N USGS high-water marks (+ M confirmed photos). Not measured water. Not an all-clear."** High-water marks record the *peak*, so the MVP shows the peak, not a moment in time.

## Data contracts (fixed; every lane builds against these)

**`data/marks.csv`** (Lane A writes it). Columns:
`id,lat,lon,water_elev_m,depth_m,uncertainty_m,quality,source,description`
`source` is always `usgs_hwm`. `depth_m` = height above ground. `uncertainty_m` = the CSV's `uncertainty` column in ft × 0.3048, or 0.06 if that column is empty.

**`data/dem.tif`** (Lane A). GeoTIFF, single band float32, projected CRS in meters (whatever the USGS tile uses, expected EPSG:26915), heights in m NAVD88, 2 m cells, nodata −9999.

**`data/roads.geojson`** (Lane A). FeatureCollection of LineStrings, EPSG:4326, properties `osm_id` (str), `name` (str or null), `highway` (str), `is_bridge` (bool).

**`data/observations.json`** (Lane B). A JSON list; each item has:
```
id: str, lat: float, lon: float, taken_at: ISO str, photo: str (path or URL),
water_visible: bool, depth_m_low: float|null, depth_m_high: float|null,
reference_object: str|null, obstacles: [{type: str, note: str}],
confidence: "low"|"medium"|"high", reasoning: str, model: str,
status: "ai_proposed"|"confirmed"|"rejected"|"needs_review", error: str|null
```

**Outputs in `web/data/`** (Lane C writes them, Lane D reads them). All EPSG:4326:
- `water.geojson`: Polygons with `status` ("likely" | "possible") and `depth_band` ("0–0.3 m" | "0.3–0.6 m" | "0.6–1.2 m" | "over 1.2 m"). Likely areas are banded by low-run depth; possible areas by high-run depth.
- `unknown.geojson`: Polygons covering cells inside the DEM with no mark within 400 m.
- `roads_status.geojson`: road LineStrings plus `status` ("likely_flooded" | "possibly_flooded" | "no_flooding_estimated" | "unknown" | "bridge_not_estimated") and `max_depth_m` (float or null).
- `pins.geojson`: Points with `kind` ("usgs_measured" | "ai_photo"), `depth_m_low`, `depth_m_high`, `status`, `label`, `photo` (str or null), `obstacles` (list).
- `meta.json`: `{generated_at, n_marks, n_confirmed_photos, radius_m, label}`.

## Wording rules (UI and outputs)

Use exactly these phrases:
- "Likely flooded"
- "Possibly flooded"
- "No flooding estimated (not verified)"
- "Unknown: no data"
- "Bridge: depth not estimated"
- "USGS measured (surveyed after the flood)"
- "AI-proposed: awaiting review"
- "REPLAY · Hurricane Harvey, Aug 2017"
- Routes: "Deepest point on route: est. X m", "Predicted for HH:MM", "Within the depth limit you set", "Not covered by any camera: X km"

Never use "safe", "clear" or "passable".

## Approaches considered

- **Water layer:** (A) water drawn only at observed spots: honest, but too sparse to read as a scene. (B) bathtub fill from the marks: **chosen**. (C) hydraulic simulation: impossible in a day, and out of scope.
- **Dispatcher task:** routing a truck vs. sizing up a scene. **Sizing up a scene was chosen**, which puts the effort into the 3D view.
- **3D display:** Google Photorealistic 3D Tiles (needs a billing key, can't be modified, overlay is harder); CesiumJS (heavier); **MapLibre + OpenFreeMap (chosen: free, no key, simple GeoJSON layers)**.
- **Screen layout:** scene first / scene + evidence / briefing + scene, in the mockups. **Deferred**: Lane D chooses after the MVP.

## Left to the builders

Default building heights, colors (must be color-blind safe and must not rely on color alone), the exact Nemotron model ID (taken from the event kit or build.nvidia.com), prompt wording, and polygon simplification.
