import json

from flood.run import build_outputs


def load(p):
    return json.load(open(p))


def test_writes_contract_files(tiny_inputs):
    meta = build_outputs(*tiny_inputs("ai_proposed"))
    out = tiny_inputs.out_dir
    water, roads, pins = load(out / "water.geojson"), load(out / "roads_status.geojson"), load(out / "pins.geojson")
    assert any(f["properties"]["status"] == "likely" for f in water["features"])
    assert roads["features"][0]["properties"]["status"] == "likely_flooded"
    assert {f["properties"]["kind"] for f in pins["features"]} == {"usgs_measured", "ai_photo"}
    assert meta["n_marks"] == 1 and meta["n_confirmed_photos"] == 0 and (out / "unknown.geojson").exists()
    assert load(out / "meta.json") == meta


def test_water_is_lonlat(tiny_inputs):
    build_outputs(*tiny_inputs(None))
    lon, lat = load(tiny_inputs.out_dir / "water.geojson")["features"][0]["geometry"]["coordinates"][0][0]
    assert -96 < lon < -95 and 29 < lat < 30


def test_unconfirmed_observation_does_not_change_water(tiny_inputs):
    build_outputs(*tiny_inputs("ai_proposed")); a = load(tiny_inputs.out_dir / "water.geojson")
    build_outputs(*tiny_inputs(None)); b = load(tiny_inputs.out_dir / "water.geojson")
    assert a == b


def test_confirmed_observation_counts(tiny_inputs):
    meta = build_outputs(*tiny_inputs("confirmed"))
    assert meta["n_confirmed_photos"] == 1 and "1 confirmed photo" in meta["label"]


def test_confirmed_without_depth_is_pin_only(tiny_inputs):
    meta = build_outputs(*tiny_inputs("confirmed", depth=None))
    assert meta["n_confirmed_photos"] == 0
    pins = load(tiny_inputs.out_dir / "pins.geojson")["features"]
    assert any(p["properties"]["kind"] == "ai_photo" for p in pins)


def test_small_radius_leaves_unknown_area(tiny_inputs):
    args = tiny_inputs(None)
    build_outputs(*args, radius_m=20)
    assert load(tiny_inputs.out_dir / "unknown.geojson")["features"]


def test_labels_never_say_safe(tiny_inputs):
    build_outputs(*tiny_inputs("ai_proposed"))
    text = "".join(open(p).read().lower() for p in tiny_inputs.out_dir.iterdir())
    assert not any(w in text for w in ("safe", "passable", "all clear"))


def test_water_surface_has_levels(tiny_inputs):
    # fixture mark: level 12.0 +/- 0.06 -> likely surface ~11.94, possible band up to ~12.06
    build_outputs(*tiny_inputs(None))
    feats = load(tiny_inputs.out_dir / "water_surface.geojson")["features"]
    likely = [f["properties"]["level_m"] for f in feats if f["properties"]["status"] == "likely"]
    possible = [f["properties"]["level_m"] for f in feats if f["properties"]["status"] == "possible"]
    assert likely and all(11.85 <= v <= 12.0 for v in likely)
    assert all(11.9 <= v <= 12.1 for v in possible)


def test_pins_carry_ground_height(tiny_inputs):
    build_outputs(*tiny_inputs(None))
    pin = load(tiny_inputs.out_dir / "pins.geojson")["features"][0]["properties"]
    assert abs(pin["ground_m"] - 10.0) < 0.05


def test_ground_samples_for_3d_alignment(tiny_inputs):
    build_outputs(*tiny_inputs(None))
    samples = load(tiny_inputs.out_dir / "ground_samples.json")
    assert samples and all({"lon", "lat", "ground_m"} <= s.keys() for s in samples)
    assert all(10.0 <= s["ground_m"] <= 13.0 for s in samples)
