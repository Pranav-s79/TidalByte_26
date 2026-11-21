# Lane B: photo-reader accuracy improvements (handoff)

Nov 21, 2026 · branch `sujit/model-improvements` · owner: open (started by Sujit)

The reader (`flood/read_photo.py`) works, but on one test photo the same image gave different readings on different runs: wheel hub (0.30–0.36 m) 3 of 5 times, curb once, no depth once. Accuracy is not measured yet. Three improvements were planned; **3 is done on this branch, 1 and 2 are open**. Do 1 first: it helps accuracy most.

## Done on this branch

**3. More rows in the height table** (`data/reference_heights.json`). Added, with sources:
- standing adult, ankle bone: 0.05–0.08 m (ANSUR II lateral malleolus height)
- standing adult, waist at the navel: 0.90–1.14 m (ANSUR II omphalion height)

Ranges run from the 5th-percentile woman to the 95th-percentile man, barefoot, computed from the public ANSUR II CSVs (https://www.openlab.psu.edu/ansur2/). No fire-hydrant row yet: add one only with a source. Tests still pass.

## Open

### 1. Model judges the waterline; code computes the depth

Today the model picks a reference object **and** invents the depth number, so it can name the top of the tire while describing water at the tire's middle. The FloodVision paper (arXiv 2509.04772) got 8.17 cm error this way vs. 10.28 cm for the model alone.

- Ask the model for `submerged_fraction_low` / `submerged_fraction_high` (0–1): how much of the named object's height, from the ground up, is under water. Example: water covers half the tire → 0.45–0.55.
- Code computes `depth_m_low = fraction_low × height_m_low` and `depth_m_high = fraction_high × height_m_high` from the table row.
- `reference_object` must match a table row name (normalize case and spaces; reject anything else as `needs_review`). The table now describes **objects from the ground up**, so the hub row can go (it is half the tire).
- Keep accepting the old `depth_m_low` / `depth_m_high` replies so existing tests and `photo_demo.py`'s recorded reading still work, but record `depth_method: "model_estimate"` vs. `"fraction_of_reference"` on the observation.
- `parse_reading` needs the table: pass `heights` through from `read_photo` (camera tables come from `cameras.json` via `read_frame`).
- Fractions also fill the table's 15–30 cm gap (a third of a tire ≈ 0.20–0.24 m).

### 2. Read each photo three times; disagreement goes to review

- In `read_photo`, call the model 3 times in parallel (`ThreadPoolExecutor`) with the same messages; wall time stays about the same.
- Agree = same `water_visible`, all give a depth or all give none, and the depth ranges overlap. Then combine: range = lowest low to highest high, confidence = the lowest of the three, and record `"agreement": "3/3"` plus a short summary of each read.
- Anything else → `needs_review` with the reads listed in `error`. Fewer than 2 usable reads → `needs_review`.
- The detector cross-check runs after combining. In `read_frame.py`, take `frame_issues` from **all** replies (today it reads only the last one).
- Watch NVIDIA Build rate limits: 3 calls per photo.

### Then measure (polish task 5)

Collect about 20 public-domain or CC flood photos where the waterline touches something in the table. Two teammates label a depth range for each, independently. Report agreement with a human reader (not "accuracy": nobody measured the water) for: Super VL alone, with the detector, and with 1 and 2. Also report how often a depth was given, how often readings went to review, and seconds per photo. Real counts only, in `docs/accuracy.md`.

## How to test

```
git switch sujit/model-improvements && git pull
pytest                     # 107 passed, 1 xfailed on this branch before any changes
export NVIDIA_API_KEY=...  # NEMOTRON_VL_MODEL defaults to nvidia/nemotron-3.5-super-vl-120b-a12b
python -m flood.read_photo PHOTO --lat 0 --lon 0 --taken-at 2017-08-27T08:18:00 --dry-run
```

Super VL reasons before answering: 17–67 s per photo, so keep `max_tokens` at 8192.
