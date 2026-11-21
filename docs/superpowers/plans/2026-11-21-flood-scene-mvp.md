# Flood Scene 3D: MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command turns Harvey high-water marks, ground elevation, roads and AI photo readings into 3D map layers of Meyerland that a dispatcher can read.

**Architecture:** Python scripts read input files from `data/` and write GeoJSON files to `web/data/`. A static MapLibre page reads those files. The four lanes connect **only through files** in the formats fixed in the spec, so everyone can build at the same time against small sample files.

**Tech Stack:** Python 3.11+, numpy, scipy, rasterio, osmnx, requests, pytest. Plain HTML/JS with MapLibre GL JS 4.7.1 and OpenFreeMap tiles. Nemotron VL on NVIDIA Build.

**Spec:** `docs/superpowers/specs/2026-11-21-flood-scene-mvp-design.md`. Read the "Data contracts" and "Wording rules" sections before starting.

## Global Constraints

- Bounding box (west, south, east, north) = `(-95.460, 29.674, -95.425, 29.698)`.
- Search radius 400 m, IDW power 2, DEM cell 2 m, feet → meters × 0.3048.
- Python dependencies are limited to: numpy, scipy, rasterio, osmnx, requests, pytest. Web: MapLibre GL JS 4.7.1 from unpkg. No build step, no framework.
- UI and output text use the spec's exact phrases. Never "safe", "clear" or "passable".
- Never invent coordinates. A photo without a location is rejected.
- An observation feeds the water layer **only** if `status == "confirmed"` and its depth is not null.
- `NVIDIA_API_KEY` and `NEMOTRON_VL_MODEL` come from environment variables and are never committed.
- Each lane edits only its own files. Commit to `main` often; run `git pull --rebase` before every push.

## Review Focus

1. A mark outside the DEM, or on a nodata cell, is skipped. Nothing crashes and nothing fills from garbage. *(C1 test)*
2. A road that is partly in unknown territory takes its status from its known samples. A road that is entirely unknown stays "unknown". *(A2 test)*
3. Nemotron returns non-JSON, or a low depth above the high depth → the reading becomes `needs_review` instead of crashing or becoming a pin with a depth. *(B1 tests)*
4. An AI reading that is unconfirmed, or confirmed with a null depth, never changes the water layer. *(C2 tests)*
5. A photo with no location is rejected and never placed. *(B1 test)*

---

## Team and timeline

| Lane | Who | Owns | MVP tasks |
|---|---|---|---|
| **A: Data** | Prince | `flood/prep_data.py`, `flood/roads.py`, `data/` | A1, A2 |
| **B: AI** | Sujit | `flood/read_photo.py`, `data/reference_heights.json`, `data/observations.json` | B1 |
| **C: Flood math** | Pri | `flood/fill.py`, `flood/run.py` | Task 0, C1, C2 |
| **D: Web / design** | Pranav | `web/` | D1 |

| Time | What |
|---|---|
| 12:45–1:00 | C does Task 0 (skeleton). Everyone else: read the spec, set up a venv; B gets an NVIDIA Build key |
| 1:00–2:15 | MVP tasks in parallel. D works from sample files until C2 lands |
| 2:15–2:45 | **Task I: integration, all four together.** Data in → layers out → 3D page |
| 2:45–5:15 | Phase 2: each lane works through its own backlog |
| 5:15 | Feature freeze. 5:30 Devpost draft (due 6:00). 6:00–7:30 polish, backup video, rehearsal |

## File structure

```
requirements.txt
flood/__init__.py
flood/fill.py          C  bathtub math (constants created in Task 0)
flood/run.py           C  CLI: data/ → web/data/
flood/prep_data.py     A  download and clip inputs
flood/roads.py         A  road status from the flood grid
flood/read_photo.py    B  Nemotron photo reader
tests/test_fill.py  tests/test_run.py  tests/test_prep_data.py  tests/test_roads.py  tests/test_read_photo.py
data/marks.csv  data/dem.tif  data/roads.geojson  data/observations.json  data/reference_heights.json
web/index.html  web/app.js  web/style.css  web/data/*.geojson  web/data/meta.json
```

---

### Task 0: Skeleton (Lane C, 15 min)

**Files:**
- Create: `requirements.txt`, `flood/__init__.py`, `flood/fill.py`, `tests/__init__.py`, `data/observations.json`
- Modify: `.gitignore` (create it if it doesn't exist)

**Interfaces:**
- Produces: `flood.fill` constants `UNKNOWN = -1`, `DRY = 0`, `POSSIBLE = 1`, `LIKELY = 2` (Lane A imports these in A2 before C1 lands). `data/observations.json` = `[]`.

- [ ] **Step 1:** `requirements.txt` lists numpy, scipy, rasterio, osmnx, requests, pytest, one per line. `.gitignore`: `.venv/`, `__pycache__/`, `.superpowers/`, `.serena/`, `data/raw/`, `.env`.
- [ ] **Step 2:** `flood/fill.py` contains only the four constants for now.
- [ ] **Step 3:** Run `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pytest`. Expected: "no tests ran", exit 5, and no import errors.
- [ ] **Step 4:** Commit: `chore: project skeleton`. Push and tell the team.

---

### Task A1: Prepare the input data (Lane A)

**Files:**
- Create: `flood/prep_data.py`, `tests/test_prep_data.py`
- Produces data: `data/marks.csv`, `data/dem.tif`, `data/roads.geojson`

**Interfaces:**
- Produces: `marks_from_hwm_csv(src_csv: str, bbox: tuple[float, float, float, float], out_csv: str) -> int`, `clip_dem(src: str, bbox: tuple, out_tif: str, cell_m: float = 2.0) -> None`, `fetch_roads(bbox: tuple, out_geojson: str) -> int`. Module constants `BBOX`, `HWM_URL`, `DEM_URL`. File formats exactly as in the spec's "Data contracts".

- [ ] **Step 1: Write the failing tests** in `tests/test_prep_data.py`

```python
def test_marks_from_hwm_csv_filters_and_converts(tmp_path):
    # 3 rows using the real HydroShare column names: one outside BBOX, one with
    # an empty height_above_gnd, and one valid row at 29.68111,-95.45026 with
    # elev_ft=53.432, height_above_gnd=4.57, uncertainty=0.190289
    n = marks_from_hwm_csv(str(src), BBOX, str(out))
    rows = list(csv.DictReader(open(out)))
    assert n == 1 and len(rows) == 1
    assert abs(float(rows[0]["water_elev_m"]) - 16.2861) < 1e-3
    assert abs(float(rows[0]["depth_m"]) - 1.3929) < 1e-3
    assert abs(float(rows[0]["uncertainty_m"]) - 0.0580) < 1e-3
    assert rows[0]["source"] == "usgs_hwm"

@pytest.mark.skipif(not os.path.exists("data/dem.tif"), reason="run prep first")
def test_real_marks_ground_matches_dem():
    # the ground each mark implies (water_elev_m - depth_m) should match the DEM at that
    # point within 0.5 m for at least 80% of marks; this also checks datum and CRS handling
    assert agree >= 0.8 * len(marks)

@pytest.mark.skipif(not os.path.exists("data/roads.geojson"), reason="run prep first")
def test_real_roads_have_bridges():
    fc = json.load(open("data/roads.geojson"))
    assert len(fc["features"]) > 300
    assert any(f["properties"]["is_bridge"] for f in fc["features"])
```

- [ ] **Step 2:** Run `pytest tests/test_prep_data.py -v`. Expected: the first test FAILS (import error); the other two are skipped.
- [ ] **Step 3: Implement** in `flood/prep_data.py`:
  - `HWM_URL = "https://www.hydroshare.org/resource/615d426f70cc4346875c725b4b8fdc59/data/contents/Harvey_HWMs_20180322.csv"`
  - `DEM_URL = "/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/TX_CoastalRegion_2018_A18/TIFF/USGS_1M_15_x26y329_TX_CoastalRegion_2018_A18.tif"`
  - `marks_from_hwm_csv`: keep rows inside the bbox (`latitude_dd`, `longitude_dd`) with `height_above_gnd > 0`. `id` = `hwm_id`, `quality` = the first word of `hwmQualityName`, `description` = `siteDescription`. Do **not** copy the person-name columns.
  - `clip_dem`: reprojects the bbox into the source CRS with `rasterio.warp.transform_bounds`, reads only that window through `/vsicurl/` (no 400 MB download), resamples to 2 m (average), and writes float32 with nodata −9999 and `compress="deflate"`.
  - `fetch_roads`: `osmnx.graph_from_bbox(bbox=(w, s, e, n), network_type="drive")` (osmnx 2.x argument order), then `graph_to_gdfs(nodes=False)`. `is_bridge` = the `bridge` value is present and not `"no"`. Join list-valued `osmid` and `name` into strings.
  - `if __name__ == "__main__":` runs all three into `data/`.
- [ ] **Step 4:** Run `python -m flood.prep_data && pytest tests/test_prep_data.py -v`. Expected: 3 passed, and `data/marks.csv` has 10 or 11 rows. If the DEM test fails, stop and check CRS/datum handling before going further, because everything downstream depends on it.
- [ ] **Step 5:** Commit: `feat(data): Meyerland marks, DEM and roads`, including the three data files (dem.tif should be under 10 MB).

---

### Task A2: Road status (Lane A)

**Files:**
- Create: `flood/roads.py`, `tests/test_roads.py`

**Interfaces:**
- Consumes: the constants from `flood.fill`.
- Produces: `road_status(lines_xy: list[list[tuple[float, float]]], is_bridge: list[bool], depth_high: np.ndarray, cls: np.ndarray, transform: Affine, step_m: float = 5.0) -> list[dict]`. Each dict is `{"status": str, "max_depth_m": float | None}`. Line coordinates are already in the DEM's CRS.

- [ ] **Step 1: Write the failing tests** on a 5×5 grid, `T = from_origin(0, 10, 2, 2)`. Row 0 = UNKNOWN, row 1 = POSSIBLE (depth 0.5), row 2 = LIKELY (depth 1.0), rows 3–4 = DRY (depth 0.0). Use `step_m=1`.

```python
def test_statuses():
    out = road_status(
        [[(0.5, 5), (9.5, 5)],      # along row 2
         [(0.5, 9), (9.5, 9)],      # along row 0
         [(0.5, 1), (9.5, 1)],      # along row 4
         [(5, 9.5), (5, 6.5)],      # crosses rows 0 and 1: partly unknown
         [(0.5, 5), (9.5, 5)]],     # row 2, but a bridge
        [False, False, False, False, True], depth_high, cls, T, step_m=1)
    assert [o["status"] for o in out] == ["likely_flooded", "unknown", "no_flooding_estimated",
                                          "possibly_flooded", "bridge_not_estimated"]
    assert [o["max_depth_m"] for o in out] == [1.0, None, 0.0, 0.5, None]
```

- [ ] **Step 2:** Run `pytest tests/test_roads.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Sample points every `step_m` along each line, plus both endpoints, and ignore samples that fall outside the grid. Then apply these rules in order: bridge → `bridge_not_estimated`; no known samples → `unknown`; any LIKELY sample → `likely_flooded`; any POSSIBLE sample → `possibly_flooded`; otherwise `no_flooding_estimated`. `max_depth_m` = the NaN-ignoring max of `depth_high` over the samples, rounded to 2 decimals, or None.
- [ ] **Step 4:** Run `pytest tests/test_roads.py -v`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(roads): road status from flood grid`.

---

### Task B1: Nemotron photo reader (Lane B)

**Files:**
- Create: `flood/read_photo.py`, `tests/test_read_photo.py`, `data/reference_heights.json`

**Interfaces:**
- Produces: `parse_reading(raw: str) -> dict`, `read_photo(photo_path: str, lat: float | None, lon: float | None, taken_at: str, client: Callable[[list], str] = post_chat) -> dict` (returns one observation in the spec's format), `post_chat(messages: list) -> str`. CLI: `python -m flood.read_photo PHOTO --lat --lon --taken-at [--dry-run]`.

- [ ] **Step 1: Write the failing tests** (no network: every test passes a fake `client`)

```python
VALID = ('{"water_visible": true, "reference_object": "sedan tire", "depth_m_low": 0.35, '
         '"depth_m_high": 0.55, "obstacles": [{"type": "stalled_vehicle", "note": "car in lane"}], '
         '"confidence": "medium", "reasoning": "water at top of tire"}')

def test_parse_valid_reading():
    r = parse_reading("Here you go:\n" + VALID)
    assert r["status"] == "ai_proposed" and r["depth_m_low"] == 0.35 and r["error"] is None

def test_parse_garbage_needs_review():
    r = parse_reading("I cannot tell")
    assert r["status"] == "needs_review" and r["depth_m_low"] is None and r["error"]

def test_no_reference_object_forces_null_depth():
    r = parse_reading(VALID.replace('"sedan tire"', "null"))
    assert r["depth_m_low"] is None and r["depth_m_high"] is None and r["status"] == "ai_proposed"

def test_low_above_high_needs_review():
    assert parse_reading(VALID.replace("0.35", "0.9"))["status"] == "needs_review"

def test_photo_without_location_is_rejected(tmp_path):
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    with pytest.raises(ValueError):
        read_photo(str(p), None, None, "2017-08-27T09:36:00", client=lambda m: VALID)

def test_read_photo_fills_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("NEMOTRON_VL_MODEL", "test-model")
    p = tmp_path / "a.jpg"; p.write_bytes(b"x")
    o = read_photo(str(p), 29.68, -95.44, "2017-08-27T09:36:00", client=lambda m: VALID)
    assert (o["lat"], o["lon"], o["model"], o["status"]) == (29.68, -95.44, "test-model", "ai_proposed")
    assert o["id"].startswith("obs-") and o["obstacles"][0]["type"] == "stalled_vehicle"
```

- [ ] **Step 2:** Run `pytest tests/test_read_photo.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `data/reference_heights.json`: a list of `{name, height_m_low, height_m_high, source}`. Starting rows to **verify before the demo**: passenger-car tire diameter 0.60–0.70, curb 0.10–0.20, car door handle 0.80–1.05, adult knee 0.45–0.55. Fill in `source`, or delete any row you can't source.
  - Prompt requirements: include the reference table; ask for JSON only, with the keys shown in `VALID`; if no object of known height touches the waterline, set `reference_object` and both depths to null; obstacle types are `stalled_vehicle`, `debris`, `downed_tree`, `barricade`, `other`; never guess a location.
  - `post_chat`: POST to `https://integrate.api.nvidia.com/v1/chat/completions` with `temperature=0`. Model and key come from the environment. Check the image message format against the Nemotron VL docs linked in `CLAUDE.md`.
  - `id` = `"obs-"` + the first 10 hex characters of the SHA-1 of the photo bytes.
  - The CLI appends to `data/observations.json`. With `--dry-run` it only prints, which you use for test photos whose location you don't know.
- [ ] **Step 4:** Run `pytest tests/test_read_photo.py -v`. Expected: 6 passed. Then run one real photo: `python -m flood.read_photo some.jpg --lat 0 --lon 0 --taken-at 2017-08-27T00:00:00 --dry-run`. Expected: printed JSON with `status` `ai_proposed` or `needs_review` and a meaningful `reasoning`.
- [ ] **Step 5:** Commit: `feat(ai): Nemotron photo reader`.

---

### Task C1: Bathtub fill (Lane C)

**Files:**
- Modify: `flood/fill.py`
- Create: `tests/test_fill.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Mark(x: float, y: float, level_low: float, level_high: float)` (DEM CRS, m NAVD88). `level_surfaces(shape, transform, marks, radius_m=400.0, power=2.0) -> tuple[np.ndarray, np.ndarray]`. `fill_depth(dem, level, seeds: list[tuple[int, int]]) -> np.ndarray`. `classify(depth_low, depth_high) -> np.ndarray` (int8). `run_fill(dem, transform, marks, radius_m=400.0) -> tuple[depth_low, depth_high, cls]`.

- [ ] **Step 1: Write the failing tests.** `T = from_origin(0, 10, 2, 2)`. `bowl()` = a 5×5 grid of 3s with a ring of 1s and 0 at the center.

```python
def test_bowl_fills_to_level():
    d = fill_depth(bowl(), np.full((5, 5), 2.0), seeds=[(2, 2)])
    assert d[2, 2] == 2.0 and d[1, 1] == 1.0 and d[0, 0] == 0.0

def test_disconnected_basin_stays_dry():
    d = fill_depth(np.array([[0, 5, 0]], float), np.full((1, 3), 2.0), seeds=[(0, 0)])
    assert d[0, 0] == 2.0 and d[0, 2] == 0.0

def test_beyond_radius_is_unknown():
    low, high = level_surfaces((5, 5), T, [Mark(1, 9, 2, 2)], radius_m=3)
    assert not np.isnan(low[0, 0]) and np.isnan(low[4, 4])

def test_classify():
    lo, hi = np.array([1.0, 0.0, 0.0, np.nan]), np.array([1.2, 0.3, 0.0, np.nan])
    assert classify(lo, hi).tolist() == [LIKELY, POSSIBLE, DRY, UNKNOWN]

def test_mark_outside_grid_is_skipped():
    *_, cls = run_fill(bowl(), T, [Mark(500, 500, 2, 2)])
    assert (cls == UNKNOWN).all()

def test_mark_on_nodata_is_skipped():
    dem = bowl(); dem[2, 2] = np.nan
    *_, cls = run_fill(dem, T, [Mark(5, 5, 2, 2)])
    assert (cls == UNKNOWN).all()
```

- [ ] **Step 2:** Run `pytest tests/test_fill.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** using the spec's "Bathtub fill" section:
  - `level_surfaces`: distances from each cell center to each mark. A cell within 0.01 m of a mark takes that mark's level directly, so IDW never divides by zero. A cell with no mark within the radius gets NaN.
  - `fill_depth`:

    ```python
    wet = (level > dem) & ~np.isnan(dem)        # NaN compares False
    for r, c in seeds: wet[r, c] = True
    labels, _ = scipy.ndimage.label(wet, structure=np.ones((3, 3)))
    keep = np.isin(labels, [labels[r, c] for r, c in seeds if labels[r, c]])
    depth = np.where(keep, np.clip(level - dem, 0, None), 0.0)
    depth[np.isnan(level) | np.isnan(dem)] = np.nan
    ```

  - `run_fill`: drop marks whose cell is outside the grid or on NaN ground; if none remain, return all-NaN depths. Run the low and high fills, then `classify`.
- [ ] **Step 4:** Run `pytest tests/test_fill.py -v`. Expected: 6 passed.
- [ ] **Step 5:** Commit: `feat(fill): bathtub fill with uncertainty`.

---

### Task C2: The `run` command: data in, layers out (Lane C)

**Files:**
- Create: `flood/run.py`, `tests/test_run.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `run_fill`, `Mark` (C1); `road_status` (A2). Until A2 lands, use a temporary stub that returns `{"status": "unknown", "max_depth_m": None}` for every road.
- Produces: `build_outputs(marks_csv: str, dem_tif: str, roads_geojson: str, observations_json: str | None, out_dir: str, radius_m: float = 400.0) -> dict` (returns the meta dict) and writes the five output files from the spec. CLI: `python -m flood.run` with defaults `data/…` → `web/data`.

- [ ] **Step 1: Write the fixture and the failing tests.**
  - `conftest.py`: the fixture `tiny_inputs(tmp_path)` writes:
    - a 50×50 `dem.tif` in EPSG:26915, origin (263000, 3287000), 2 m cells, with z = 10 + 0.001·r² (r = meters from the center);
    - `marks.csv` with one mark at the center (lat/lon from `rasterio.warp.transform`), `water_elev_m=12.0`, `depth_m=2.0`, `uncertainty_m=0.06`;
    - `roads.geojson` with one non-bridge line crossing the center from east to west;
    - `observations.json` with one observation near a corner, depth 0.3–0.5, `status` passed in as a parameter.

```python
def test_writes_contract_files(tiny_inputs):
    meta = build_outputs(*tiny_inputs("ai_proposed"))
    out = tiny_inputs.out_dir
    water = load(out / "water.geojson"); roads = load(out / "roads_status.geojson"); pins = load(out / "pins.geojson")
    assert any(f["properties"]["status"] == "likely" for f in water["features"])
    assert roads["features"][0]["properties"]["status"] == "likely_flooded"
    assert {f["properties"]["kind"] for f in pins["features"]} == {"usgs_measured", "ai_photo"}
    assert meta["n_marks"] == 1 and meta["n_confirmed_photos"] == 0 and (out / "unknown.geojson").exists()

def test_unconfirmed_observation_does_not_change_water(tiny_inputs):
    build_outputs(*tiny_inputs("ai_proposed")); a = load(tiny_inputs.out_dir / "water.geojson")
    build_outputs(*tiny_inputs(None)); b = load(tiny_inputs.out_dir / "water.geojson")   # None = no observations file
    assert a == b

def test_confirmed_observation_counts(tiny_inputs):
    assert build_outputs(*tiny_inputs("confirmed"))["n_confirmed_photos"] == 1

def test_confirmed_without_depth_is_pin_only(tiny_inputs):
    meta = build_outputs(*tiny_inputs("confirmed", depth=None))
    assert meta["n_confirmed_photos"] == 0
```

- [ ] **Step 2:** Run `pytest tests/test_run.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `build_outputs`:**
  - Load the DEM, turning nodata into NaN.
  - Project mark and observation lat/lon into the DEM's CRS with `rasterio.warp.transform("EPSG:4326", crs, …)`.
  - A confirmed observation with a depth becomes a `Mark`, with its level = DEM ground at that point + depth.
  - Polygonize with `rasterio.features.shapes`: likely cells by the depth band of `depth_low`, possible cells by the depth band of `depth_high`, and unknown cells separately. Convert to 4326 with `rasterio.warp.transform_geom`.
  - Roads: project into the DEM CRS, call `road_status`, and merge the results into the original 4326 features.
  - Pins: every mark, plus every observation (rejected ones included, keeping their status). Pin labels use the spec's phrases.
  - `meta.label` follows the spec's pattern with the real counts.
- [ ] **Step 4:** Run `pytest -v`. Expected: all tests pass.
- [ ] **Step 5:** Commit: `feat(run): data in → map layers out`.

---

### Task D1: 3D scene page (Lane D)

**Files:**
- Create: `web/index.html`, `web/app.js`, `web/style.css`, sample `web/data/{water,unknown,roads_status,pins}.geojson` and `web/data/meta.json`

**Interfaces:**
- Consumes: the five output files from the spec. Until C2 lands, write sample files by hand with one or two features each near (−95.444, 29.686). `python -m flood.run` overwrites them later.

- [ ] **Step 1:** Write the sample files, exactly following the spec's property names and values.
- [ ] **Step 2:** `index.html` loads `maplibre-gl@4.7.1` (CSS and JS) from unpkg and contains `#map`, `#banner`, `#legend` and `#panel`.
- [ ] **Step 3:** `app.js` sets up the map:
  - Style `https://tiles.openfreemap.org/styles/liberty`, center `[-95.444, 29.686]`, zoom 15.5, pitch 60, bearing −20.
  - **Buildings:** if the style has no 3D buildings, add a `fill-extrusion` layer on source `openmaptiles`, source-layer `building`, height `coalesce(render_height, 6)`. Legend entry: "Building heights approximate".
  - **Layers, bottom to top, all inserted below the building layer:**
    - unknown: gray `#6b7280`, opacity 0.55
    - possible: `#6baed6`, opacity 0.35, dashed outline
    - likely: colored by `depth_band` with `#c6dbef`, `#6baed6`, `#2171b5`, `#08306b`, opacity 0.6
  - **Roads, colored by status:**
    - likely: `#08306b`, 5 px
    - possible: `#6baed6`, dashed
    - no_flooding_estimated: `#9ca3af`, thin. **Not green.**
    - unknown: `#6b7280`, dotted
    - bridge: `#b45309`, dashed
  - **Pins:** USGS = filled circle; AI = hollow ring; rejected = gray.
  - **Clicking a pin** shows its label, kind phrase, depth range, status phrase, photo link and obstacles in `#panel`.
- [ ] **Step 4:** The banner shows `meta.label` and "REPLAY · Hurricane Harvey, Aug 2017". The legend uses the spec's exact phrases.
- [ ] **Step 5:** Verify: run `python -m http.server 8000 -d web` and open http://localhost:8000. Expected: a 3D Meyerland view with the sample water, a road, a pin and a working click panel, and no console errors.
- [ ] **Step 6:** Commit: `feat(web): 3D scene page`.

---

### Task I: Integration, the MVP (all four, 2:15)

- [ ] **Step 1:** A: `python -m flood.prep_data`. The `data/` files are committed.
- [ ] **Step 2:** C: `python -m flood.run`. Expected: it prints the meta, and `web/data/` has the five files with real counts (`n_marks` 10 or 11).
- [ ] **Step 3:** B: run one photo that has a true location, if you have one. Otherwise skip, and say so in the demo.
- [ ] **Step 4:** D: serve the page and check:
  - [ ] REPLAY banner is visible
  - [ ] about 10 USGS pins along Brays Bayou
  - [ ] blue water along the bayou with depth shading
  - [ ] gray unknown area beyond 400 m
  - [ ] roads colored, bridges orange
  - [ ] a pin click shows the measured depth
  - [ ] the word "safe" appears nowhere
- [ ] **Step 5:** Run `pytest -v`. Expected: all pass.
- [ ] **Step 6:** Commit the generated `web/data/` (it doubles as the offline demo backup), then `git tag mvp` and push.

---

## Phase 2: independent backlogs (2:45 onward, top item first)

Each item works the same way: a test or a visible check, then a commit. Only the files your lane owns change.

**A: Data**
1. **Photo hunt:** teammates' phones (EXIF GPS), Flickr with the CC license filter for "Meyerland", and the UH EurekAlert image. Done when at least 3 photos with true locations have gone through B's reader, or `docs/data-notes.md` says none were found.
2. **Access impact** (CLAUDE.md P0 #5): `flood/access.py`. If the `likely_flooded` roads were unavailable, which road nodes would lose their connection to a chosen OSM facility? Writes `web/data/access.geojson` with "If these roads are closed…" wording. Done when a 4-node toy-graph test passes.
3. **History:** check for 2015/2016 marks near Meyerland. The USGS site blocks automated access, so this needs a person in a browser. Use it only if real records turn up.

**B: AI**
1. **Incident briefing:** Nemotron (a text model) reads `pins`, `roads_status` and `meta`, then writes `web/data/briefing.json` = `{summary, reviewer_tasks[], cites[]}`. Test: every cited id exists, and no banned words appear.
2. **Accuracy number:** run the reader on a labeled set (the flooded-cars dataset if you can download it, otherwise 20 hand-labeled photos). Write real counts to `docs/accuracy.md`. Never estimate or round up.
3. **Content Safety check** before reading a photo (optional).

**C: Flood math**
1. **Review server:** `flood/serve.py` (stdlib `http.server`) serves `web/` and handles `POST /review {id, status}`, which updates `observations.json` and reruns `build_outputs`. Test: confirming a reading with a depth raises `n_confirmed_photos`.
2. **Speed and smoothing:** the full run takes under 10 s, and polygons are simplified (shapely comes with osmnx).

**D: Web / design**
1. **Pick a layout:** scene first, scene + evidence, or briefing + scene (mockups: open `docs/mockups/scene-layouts.html` in a browser). Build the evidence panel with Confirm/Reject buttons that call C's `/review`.
2. **Patterns:** hatching for possible, dots for unknown, legend icons, a color-blind check.
3. **Briefing panel** from B's `briefing.json`.
4. **Pitch:** a 60–90 s script following `CLAUDE.md` §8, plus a backup screen recording by 6:30.

**If behind, cut in this order:** D3, B3, C2, A3. Never cut: the REPLAY label, unknown shading, or human confirmation before an AI reading feeds the fill.
