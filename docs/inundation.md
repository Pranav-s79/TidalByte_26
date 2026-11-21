# Terrain-aware flood surface (3D views)

`python -m flood.inundation` builds `web/data/flood3d.json` + `flood3d.bin`, which the Cesium command center (`web/3d.html`) draws in both map modes. It is **additive**: `flood.run`, `water.geojson`, `roads_status.geojson`, the 2D map and the router are unchanged. Only real data is used: no synthetic scenarios.

## Why the old 3D water looked like blobs

`flood/fill.py` blends the 10 USGS high-water-mark levels by inverse distance and **stops at 400 m from the nearest mark**. Inside that radius it is terrain-aware, but the outer edge of the water is the radius itself, so the footprint is a union of circles. The water *levels* were fine (leave-one-out error 0.19 m, below). The *extent* was the problem: the bathtub's "likely" area covered only 22.7% of the USACE modelled extent (`docs/validation.md`).

## Method

| Piece | Source | How |
|---|---|---|
| Extent | USACE maximum inundation extent, Brays Bayou, Harvey 2017 (daily HEC-RAS runs; [CUAHSI service](https://arcgis.cuahsi.org/arcgis/rest/services/MaximumFloodExtents_Harvey2017/MapServer)) | 507 polygons (median edge 5.8 m), rasterised on the 2 m lidar DEM. Covers 88.8% of the box. |
| Water level, measured reach | 10 USGS high-water marks (`data/marks.csv`) | Interpolated linearly **along the Brays Bayou channel** (OSM centreline, chained); each flooded cell takes the level at its nearest channel station. Reach = stations of the marks ± 150 m (2.3 km of channel). |
| Water level, beyond the reach | FwDET (Cohen et al. 2018) | Elevation of the nearest mapped shoreline cell, 30 m focal mean; blended over 300 m at the reach ends. Labelled **lower confidence**. |
| Depth | Lidar DEM, 2 m, NAVD88 | Water level − ground. Mapped cells where that is ≤ 0 keep the USACE footprint but get **no depth** ("depth not resolved"). |
| Levels below the peak (slider) | Same surface, lowered by D | A cell stays wet only while its freeboard > D **and** it is connected (8-neighbour, through wet cells) to the bayou channel. Low pockets with no connection never flood. Nested by construction. |

The browser grid is 6 m (3×3 blocks of the DEM), int16 cm heights, georeferenced to within 0.23 m.

## Validation against the marks (n = 10)

| Water-surface estimate | Mean abs error | Bias | Max |
|---|---:|---:|---:|
| Bayou profile, leave-one-out (used inside the reach) | **0.16 m** | −0.00 m | 0.38 m |
| FwDET from the USACE extent alone (used beyond the reach) | 0.39 m | −0.26 m | 0.94 m |
| Old 400 m inverse-distance, leave-one-out (n = 9; one mark has no neighbour) | 0.19 m | +0.04 m | 0.38 m |

- All 10 marks fall inside the USACE extent.
- The 0.38 m maximum is the co-located pair 22842/22884: same coordinates, surveyed levels 0.38 m apart. That is the noise floor of the marks themselves.
- Rendered terrain vs each mark's surveyed ground: mean difference 0.02 m.
- Surveyed water elevation vs "lidar ground + recorded depth" differs by up to 0.96 m (mark 22892, USGS quality "Poor"). The 3D waterline dot uses the surveyed elevation.

Area as the level drops below the peak (6 m cells drawn): peak 203,892 · −0.5 m 63% · −1.0 m 30% · −1.5 m 11% · −2.0 m 6% (channel). Tests: `tests/test_inundation.py` (higher ground stays dry, disconnected pockets don't flood, rising level only adds water, water only inside the mapped extent, depth = surface − ground).

## Photorealistic alignment (the −14.7 m warning)

Cesium's `sampleHeightMostDetailed` hits *every* primitive, visible or not. The alignment step was sampling the command center's own hidden geometry (ground plate at 0 m), so it measured `0 − lidar ground ≈ −14.7 m`, fell outside the expected range and used a −27 m guess. Now only the Google tileset is sampled (our primitives, entities and the lidar-terrain globe are excluded). Measured NAVD88→ellipsoid offset: **−28.8 m** (25th percentile over 60 road points; Houston geoid ≈ −27 to −28 m). The status bar shows the value and whether it was measured or approximate.

## Limitations (say these in the demo)

- **Peak only.** HWMs record the highest water. The level slider shows levels *below* that peak filled over the terrain; it is not a recorded time series and says so on screen.
- **Not a hydraulic simulation.** No flow, timing, drainage or storm-sewer effects. The extent is a model (USACE HEC-RAS), not observed water; it covers riverine flooding from the bayous, not rain ponding elsewhere.
- **10 marks, two clusters.** Depths are best inside the 2.3 km measured reach; beyond it the level comes from the mapped shoreline (biased ~0.26 m low at the marks). The dashed outline on the map marks the reach.
- **Terrain resolution.** 6 m in the browser (2 m in the analysis). Curbs, driveways and floor heights are below that. Bare-earth lidar has no buildings or bridge decks: bridges are drawn level between their approaches (approximate), elevated roads are not modelled as barriers, and the depth at a building is ground depth, not depth inside it.
- **Buildings** are OSM footprints with mostly default 6 m heights, placed at the lowest lidar ground under each footprint.
- **The photorealistic city is today's Houston**, not 2017.

## Rebuild

```sh
python -m flood.inundation --fetch     # downloads the USACE extent to data/raw/ (gitignored), writes web/data/flood3d.*
python web/tools/make_basemap.py       # dark hillshade basemap for the analysis view (web/assets/basemap.png)
pytest tests/test_inundation.py
```

## Rendering notes (3D command center)

What caused the grainy, cluttered look and what replaced it:

| Problem | Cause | Fix |
|---|---|---|
| Soft, grainy city on laptop screens | Cesium rendered at CSS pixels and the browser upscaled (`useBrowserRecommendedResolution`) | Render at device pixel density, capped at 2x; MSAA x4 kept |
| Blocky blue patches, painted-on water | Five separately coloured meshes, one per depth band, uniform alpha, hard edges | One water surface with depth per vertex; a small custom appearance on Cesium's Water material sets colour and opacity from depth, fades the shoreline, calms ripples with distance and adds a grazing-angle sheen |
| Cyan lines on every street | Every road drawn as a 3D overlay | Ordinary streets baked quietly into the basemap; the flooded-road overlay is opt-in ("Road impact") |
| Grid, striped ring, hard rectangle | Grid and stripes drawn over the scene; terrain dropped to a flat plane at the box edge | No grid or stripes; terrain eases out over 450 m; basemap fades to transparent at its edges; a thin dashed line marks the analysis edge |
| Buildings melting into the water | Same navy as the water, low light | Neutral slate palette, higher key light, soft shadows cast onto the terrain (cast-only: receiving them produced shadow acne on roofs) |
| Photorealistic tiles | Default 16 px screen-space error; whole city casting shadows | Error 10 px; no shadows from the tileset |

`python web/tools/make_basemap.py` rebuilds the basemap (hillshade, water, parks, streets, faded edges).
