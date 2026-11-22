# Every Photo Is a River Gauge

Hackathon prototype: turn street cameras and field photos into reviewable flood-depth readings, put them on a 3D map, and give dispatchers least-deep route options within a depth limit their agency sets.

The working demo is a **replay of Hurricane Harvey (2017) in Meyerland, Houston**, built from 10 USGS high-water marks, lidar ground and the USACE flood extent. It is decision support, not a flood forecast or a road-safety system. It never calls a road safe.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m flood.run      # data/ -> web/data/ map layers
python -m flood.serve    # serves web/ and the router on http://127.0.0.1:8765/
```

Open http://127.0.0.1:8765/3d.html. Press **Demo** in the top bar for the guided replay.

Use `flood.serve`, not a plain static server: route options need its `POST /route`.

Optional:

- `web/config.local.js` with `window.CESIUM_ION_TOKEN = '...'` enables the satellite and photorealistic 3D views.
- `NVIDIA_API_KEY` lets `python -m flood.photo_demo` read field photos with Nemotron (walkthrough at `web/photos/walkthrough.html`).

## What's in the repo

| Path | What it is |
| --- | --- |
| `flood/` | Pipeline: flood fill from marks, road status, Nemotron photo reader, per-camera prediction, router, local server |
| `web/3d.html`, `web/command/` | 3D command center (Cesium) |
| `web/map.html` | 2D map |
| `docs/` | Pitch and research, inundation method, routing rules, validation notes |
| `tests/` | `pytest` |

## Ground rules

- Every depth is labelled Observed, Estimated, Predicted or Unknown. Unknown is never treated as dry.
- A person at the agency sets each vehicle's depth limit. The page never fills it in.
- The router proposes options. A dispatcher picks one, and nothing is dispatched.

Full rules: [`docs/routing-and-prediction.md`](docs/routing-and-prediction.md).
