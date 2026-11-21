# Routing and prediction

Nov 21, 2026 · status: **planned**. The router and `flood/predict.py` are not built yet. A related per-camera model is built in `flood/depth_model.py` (Lane B) with different rules; see the note at the end of §1. The replay pipeline they build on is built (`flood/fill.py`, `flood/roads.py`, `flood/run.py`).

This is the single source for how routing works and what it may say. Every other doc links here instead of restating it.

**Direction:** the Harvey 2017 Meyerland replay is the **proof of concept**. The **product** is live TranStar traffic cameras, short-term depth prediction, and least-deep route options for emergency dispatchers.

## Rules (every screen, every doc, every model output)

1. **Never say "safe", "clear", "passable" or "all clear".** Report numbers and their source: "Deepest point on route: est. 0.15–0.25 m (predicted for 14:20)".
2. **A person at the agency sets each vehicle type's depth limit.** The agent never sets, suggests or changes it. The limit field starts empty and must be filled in.
3. **Plan on the cautious number:** the upper end of every depth range (mean + 1 standard deviation).
4. **Every depth shows its source:** Observed, Estimated, Predicted (with the time it is for) or Unknown. See the table below.
5. **Unobserved roads are never dry.** They stay routable, because most roads have no camera. But every route option reports its unobserved distance, they are drawn gray, and the dispatcher can switch on "avoid unobserved roads".
6. **Predict at most 60 minutes ahead**, and only from a camera with enough recent readings. Otherwise the depth is Unknown.
7. **The agent proposes 2–3 options; the dispatcher picks one.** The agent re-plans and alerts when new readings change the chosen route, but never switches routes by itself.
8. **Label replay data.** Routes computed on the Harvey replay say "REPLAY".
9. **No dispatching.** The prototype never sends vehicles, talks to dispatch (CAD) systems or gives public directions.

## Where each depth comes from

| Source | What it is | Label on screen | Uncertainty |
|---|---|---|---|
| **Observed** | A camera reading (Nemotron reads a frame) or a USGS high-water mark | "Observed · camera 1234 · 14:05" / "USGS measured (surveyed after the flood)" | The reading's low–high range |
| **Estimated** | Spread from observed water levels to nearby roads by the bathtub fill (`flood/fill.py`) | "Estimated" | The fill's low/high runs |
| **Predicted** | One camera's recent readings projected forward to when the vehicle reaches that road | "Predicted for 14:20" | Grows with how far ahead |
| **Unknown** | None of the above | "Unknown: no data" | — |

## The math

### 1. One camera over time: now-cast and prediction (`flood/predict.py`)

- **Readings:** each reading becomes (time, depth, σ). Depth = the middle of Nemotron's range; σ = (high − low) / 4, treating the range as about ±2σ. Frames marked `needs_review` or low confidence are left out.
- **Model:** a Gaussian process per camera over time, using scikit-learn's `GaussianProcessRegressor` (add `scikit-learn` to `requirements.txt`).
  - Kernel: `ConstantKernel * RBF(length_scale, bounds=(15, 120) minutes) + WhiteKernel`.
  - Per-reading noise: `alpha = σ²`.
- **Output:** mean μ(t) and σ(t) at any time t. The rate of rise is μ(t + 10 min) − μ(t), per 10 minutes.
- **Limits:**
  - At least 4 readings in the last 90 minutes are needed to predict. Fewer than that: use the latest reading as Observed if it is under 20 minutes old, otherwise Unknown.
  - Never predict more than 60 minutes ahead.
- This is the same Gaussian-process math as spatial interpolation, with time in place of distance. It smooths noisy frame-by-frame readings, and its uncertainty widens on its own as you look further ahead.

> **Built vs. this spec (1:30 PM).** `flood/depth_model.py` (Sujit) already fits a Gaussian process per camera with scikit-learn, but under different rules. Pick one set before `predict.py` is built; `predict.py` can reuse its `fit()` and `predict()`.
>
> | | This spec | `depth_model.py` |
> | --- | --- | --- |
> | Minimum readings | 4 in the last 90 min | 2 (one reading returns its own range) |
> | Length-scale bounds | 15–120 min | 5–120 min |
> | Per-reading noise | σ = (high − low) / 4; low-confidence frames left out | ((high − low) / 2)², ×4 for low confidence |
> | Rate of rise | μ(t + 10) − μ(t), looking ahead | μ(now) − μ(now − 10), looking back |
> | Forecast | up to 60 min ahead | none: depth now only |
> | Units | meters, as in observations | centimeters (`readings_from_observations()` converts) |
>
> Its `hotspots()` clusters cameras that are deep **right now** (DBSCAN, 1.5 km). That is not `CLAUDE.md`'s recurring hotspot, which counts flooding across different events.

### 2. From cameras to nearby roads (`flood/fill.py`, `flood/roads.py`, already built)

1. Turn each camera's depth into a water level: level = lidar ground at the camera's reference point + depth.
2. Run the bathtub fill with the levels at μ ± σ to get low and high depth grids, then sample them along each road segment.
3. The 400 m radius still applies: beyond it is Unknown. Bridges count as Unknown, because the ground model has no decks.

### 3. The depth the router plans on, per road segment

The arrival time is the time a vehicle would reach that segment. Version 1 computes it once from a shortest-travel-time tree out of the start, at the OSM speed limit or 30 km/h if missing. Treat that speed as a planning assumption.

| Segment type | Planning depth |
|---|---|
| Watched by a camera | μ(arrival) + σ(arrival), from step 1 |
| Estimated | The fill's high run |
| Unknown | No depth. Routable, but counted as unobserved distance |

### 4. Least-deep routing (`flood/route.py`)

Inputs: a start, an end, the person-set limit L, and an "avoid unobserved roads" switch.

1. Drop every segment whose planning depth is above L. With "avoid unobserved" on, also drop Unknown segments.
2. Try depth caps of 0, 5, 10 cm … up to L. The first cap under which start and end connect wins. Within that cap, take the shortest path by length (networkx). That path is **option A: least-deep**.
3. **Option B: shortest within the limit.** The shortest path using every segment at or under L.
4. **Option C: least unobserved.** The shortest path in the same graph, with Unknown segments' length multiplied by 5.
5. Drop duplicate options.
6. Each option reports: total km, deepest point (its value, source label and road name), unobserved km, and when it will be re-checked.
7. If nothing connects under L, report "No route within the depth limit you set", list the segments that block it, and draw no route.

### 5. Re-planning and alerts

After each new reading, recompute the chosen route's planning depths. Alert the dispatcher if:
- the deepest point rose by 5 cm or more, or
- any segment's predicted depth at arrival goes above L.

The alert shows the old and new numbers plus fresh options. Only the dispatcher switches routes.

### 6. What Nemotron does here

1. Nemotron Lightning calls the tool `route_options(start, end, vehicle_type)`.
2. It writes at most three sentences comparing the options, quoting only numbers from the tool output.
3. A test checks that every number matches the tool output and that none of the banned words from rule 1 appear.

## Tests that pin the math

- **predict:**
  - A synthetic series rising 2 cm/min with noise → the 30-minute prediction lands within 2σ of the truth.
  - A flat series → rate of rise ≈ 0.
  - σ at 60 min is greater than σ at 10 min.
  - Asking for 61 min returns None.
  - Fewer than 4 recent readings → no prediction.
- **route:**
  - A shallower, longer route beats a deeper, shorter one for option A.
  - Nothing under L → "no route" plus the blocking list.
  - Unobserved km is counted correctly.
  - "Avoid unobserved" removes Unknown segments.
  - Duplicates are dropped.
- **replay:** the router on Harvey replay depths (Estimated only, no time) returns options that cross Meyerland, labeled REPLAY.

## Proof of concept vs. product

| | Proof of concept (works today) | Product (planned) |
|---|---|---|
| Water depth | 10 USGS high-water marks (peak water line) + bathtub estimate | Live camera readings, predicted to arrival time, + bathtub estimate |
| Time | Peak only | A reading every few minutes, prediction up to 60 min ahead |
| Router | Runs on replay depths (Estimated) | Runs on planning depths (Observed / Estimated / Predicted) |
| Cameras | None. TranStar keeps no recordings | TranStar snapshots, with dry baselines captured Nov 21 |
