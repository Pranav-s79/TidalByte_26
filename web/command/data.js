// Data access + wording for the 3D command center.
// Reads the pipeline outputs in web/data/ (spec "Data contracts") without changing them.

// Exact phrases from docs/superpowers/specs/2026-11-21-flood-scene-mvp-design.md ("Wording rules").
// Never "safe", "clear" or "passable".
export const PHRASE = {
  likely: 'Likely flooded',
  possible: 'Possibly flooded',
  noFlood: 'No flooding estimated (not verified)',
  unknown: 'Unknown: no data',
  bridge: 'Bridge: depth not estimated',
  usgs: 'USGS measured (surveyed after the flood)',
  aiProposed: 'AI-proposed: awaiting review',
  replay: 'REPLAY · Hurricane Harvey, Aug 2017',
};

export const ROAD_PHRASE = {
  likely_flooded: PHRASE.likely,
  possibly_flooded: PHRASE.possible,
  no_flooding_estimated: PHRASE.noFlood,
  unknown: PHRASE.unknown,
  bridge_not_estimated: PHRASE.bridge,
};

export const AI_STATUS_PHRASE = {
  ai_proposed: PHRASE.aiProposed,
  confirmed: 'Confirmed by a reviewer',
  rejected: 'Rejected by a reviewer',
  needs_review: 'Needs review: reading could not be used',
};

// Depth bands written by flood/run.py, shallow → deep, with the band's middle (for drawing the
// estimated water sheet at a representative height above ground).
export const BANDS = [
  { band: '0–0.3 m', mid: 0.15 },
  { band: '0.3–0.6 m', mid: 0.45 },
  { band: '0.6–1.2 m', mid: 0.9 },
  { band: 'over 1.2 m', mid: 1.5 },
];

// "High priority" = the deepest band the pipeline already uses (over 1.2 m). It is a display
// tier for attention, not a safety threshold.
export const CRITICAL_DEPTH_M = 1.2;

export const isUsgs = (p) => p.kind === 'usgs_measured';
export const pinId = (p) => String(p.id ?? p.label);

async function getJson(path, { optional = false } = {}) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) {
    if (optional && res.status === 404) return null;
    throw new Error(`${path}: HTTP ${res.status}`);
  }
  return res.json();
}

// Required layers. Each one reports success or failure separately so the UI can show partial states.
export async function loadCore() {
  const names = { meta: 'data/meta.json', pins: 'data/pins.geojson', water: 'data/water.geojson',
    unknown: 'data/unknown.geojson', roads: 'data/roads_status.geojson' };
  const out = {}; const errors = [];
  await Promise.all(Object.entries(names).map(async ([k, path]) => {
    try { out[k] = await getJson(path); } catch (e) { errors.push(e.message); out[k] = null; }
  }));
  return { ...out, errors };
}

export const loadBuildings = () => getJson('assets/buildings.json');
export const loadContext = () => getJson('assets/context.json');

// Camera catalog is planned (Prince: data/cameras.json, copied to web/data/ for the page).
// Accepts a list or {cameras: [...]}; returns [] when the file isn't there yet.
export async function loadCameras() {
  try {
    const raw = await getJson('data/cameras.json', { optional: true });
    if (!raw) return { cameras: [], missing: true };
    const list = Array.isArray(raw) ? raw : raw.cameras || [];
    const cameras = list.map((c, i) => ({
      id: String(c.id ?? c.camera_id ?? i),
      name: c.name || c.label || c.description || `Camera ${c.id ?? i + 1}`,
      lat: Number(c.lat ?? c.latitude ?? c.location?.lat),
      lon: Number(c.lon ?? c.lng ?? c.longitude ?? c.location?.lon),
      road: c.road || c.faces || c.road_name || null,
      snapshot: c.snapshot_url || c.snapshot || c.thumbnail || c.baseline || null,
    })).filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon)); // never invent a location
    return { cameras, missing: false };
  } catch (e) {
    return { cameras: [], missing: false, error: e.message };
  }
}

export const reloadPins = () => getJson('data/pins.geojson');

// Pri's review loop (flood/serve.py): POST /review {id, status}. A plain static server answers 501.
export async function postReview(id, status) {
  const res = await fetch('review', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, status }) });
  if (!res.ok) throw new Error(res.status === 501 || res.status === 404
    ? 'Review server not running. Start flood/serve.py to record decisions.'
    : `Review failed (HTTP ${res.status})`);
  return res.json().catch(() => ({}));
}

// Only http(s) links or relative paths for photos/snapshots.
export function safeUrl(url) {
  if (typeof url !== 'string' || !url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) return url;
  return null;
}
