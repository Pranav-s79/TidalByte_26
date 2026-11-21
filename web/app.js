// 3D scene: reads the pipeline outputs in web/data/ (spec: "Data contracts").
const DEPTH_COLORS = ['match', ['get', 'depth_band'],
  '0–0.3 m', '#c6dbef', '0.3–0.6 m', '#6baed6', '0.6–1.2 m', '#2171b5', '#08306b'];
const ROAD_PHRASE = {
  likely_flooded: 'Likely flooded',
  possibly_flooded: 'Possibly flooded',
  no_flooding_estimated: 'No flooding estimated (not verified)',
  unknown: 'Unknown: no data',
  bridge_not_estimated: 'Bridge: depth not estimated',
};

// Layer groups the user can toggle. "unknown" is deliberately NOT toggleable:
// hiding it would make areas with no data look dry.
const GROUPS = {
  water: ['water-possible', 'water-likely'],
  roads: ['roads-unknown', 'roads-none', 'roads-possible', 'roads-likely', 'roads-bridge'],
  gauges: ['pins', 'pin-labels'],
};
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const narrow = () => window.matchMedia('(max-width: 640px)').matches;

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/liberty',
  center: [-95.4425, 29.6862],
  zoom: 15.4,
  pitch: 62,
  bearing: -25,
  maxPitch: 80,
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
window.floodMap = map; // for debugging in the console

map.on('load', async () => {
  const [meta, pins] = await Promise.all([
    fetch('data/meta.json').then((r) => r.json()),
    fetch('data/pins.geojson').then((r) => r.json()),
  ]);
  document.getElementById('label').textContent = meta.label;

  for (const name of ['water', 'unknown', 'roads_status']) {
    map.addSource(name, { type: 'geojson', data: `data/${name}.geojson` });
  }
  map.addSource('pins', { type: 'geojson', data: pins });
  // Ground layers go under the building footprints so buildings stand in the water.
  const ground = map.getLayer('building') ? 'building' : undefined;
  const under3d = map.getLayer('building-3d') ? 'building-3d' : undefined;
  const status = (s) => ['==', ['get', 'status'], s];

  map.addLayer({ id: 'unknown', type: 'fill', source: 'unknown',
    paint: { 'fill-color': '#6b7280', 'fill-opacity': 0.55 } }, ground);
  map.addLayer({ id: 'water-possible', type: 'fill', source: 'water', filter: status('possible'),
    paint: { 'fill-color': '#6baed6', 'fill-opacity': 0.35 } }, ground);
  map.addLayer({ id: 'water-likely', type: 'fill', source: 'water', filter: status('likely'),
    paint: { 'fill-color': DEPTH_COLORS, 'fill-opacity': 0.72 } }, ground);

  // line-dasharray is not data-driven, so one layer per line style.
  const roadLayer = (id, filter, color, width, dash) => map.addLayer({
    id, type: 'line', source: 'roads_status', filter,
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': color, 'line-width': width, ...(dash ? { 'line-dasharray': dash } : {}) },
  }, under3d);
  roadLayer('roads-unknown', status('unknown'), '#374151', 1.5, [0.5, 2]);
  roadLayer('roads-none', status('no_flooding_estimated'), '#6b7280', 2.5);
  roadLayer('roads-possible', status('possibly_flooded'), '#fb7185', 3.5, [2, 1.5]);
  roadLayer('roads-likely', status('likely_flooded'), '#e11d48', 4);
  roadLayer('roads-bridge', status('bridge_not_estimated'), '#d97706', 4, [2, 1.5]);

  map.addLayer({ id: 'pins', type: 'circle', source: 'pins',
    paint: {
      'circle-radius': 8,
      'circle-pitch-alignment': 'viewport',
      'circle-color': ['case', ['==', ['get', 'kind'], 'usgs_measured'], '#111827',
        ['==', ['get', 'status'], 'rejected'], '#9ca3af', '#ffffff'],
      'circle-stroke-color': ['case', ['==', ['get', 'kind'], 'usgs_measured'], '#ffffff', '#7c3aed'],
      'circle-stroke-width': ['case', ['==', ['get', 'kind'], 'usgs_measured'], 2, 3],
    } });
  map.addLayer({ id: 'pin-labels', type: 'symbol', source: 'pins',
    layout: {
      'text-field': ['case', ['==', ['get', 'depth_m_low'], null], '?',
        ['concat', ['number-format', ['get', 'depth_m_low'], { 'max-fraction-digits': 2 }], ' m']],
      'text-font': ['Noto Sans Bold'], 'text-size': 13, 'text-offset': [0, -1.5], 'text-allow-overlap': true,
    },
    paint: { 'text-color': '#111827', 'text-halo-color': '#ffffff', 'text-halo-width': 2 } });

  const clickable = ['pins', 'roads-likely', 'roads-possible', 'roads-none', 'roads-unknown', 'roads-bridge'];
  for (const id of clickable) {
    map.on('click', id, (e) => show(e.features[0], id === 'pins'));
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
  }
  setupGaugeControls(pins);
});

// ---------------------------------------------------------------- toggles
for (const box of document.querySelectorAll('.toggles input[data-group]')) {
  box.addEventListener('change', () => {
    for (const id of GROUPS[box.dataset.group]) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', box.checked ? 'visible' : 'none');
    }
  });
}

// ---------------------------------------------------------------- gauges (on demand only)
const depthOf = (f) => (f.properties.depth_m_low === null ? -Infinity : Number(f.properties.depth_m_low));

// Keep the target clear of the legend (left on desktop, bottom on phones).
const viewPadding = () => (narrow() ? { top: 60, bottom: 180, left: 20, right: 20 }
  : { top: 70, bottom: 40, left: 290, right: 40 });

function flyToGauge(f, duration) {
  const target = { center: f.geometry.coordinates, zoom: 16.6, pitch: 64, bearing: -30, padding: viewPadding() };
  if (reduceMotion) { map.jumpTo(target); show(f, true); return; }
  map.flyTo({ ...target, duration, curve: 1.3, essential: false });
  map.once('moveend', () => {
    const [lon, lat] = f.geometry.coordinates;
    const c = map.getCenter();
    // Only open if the flight finished, not if the user grabbed the map mid-flight.
    if (Math.abs(c.lng - lon) < 1e-3 && Math.abs(c.lat - lat) < 1e-3) show(f, true);
  });
}

function setupGaugeControls(pins) {
  const select = document.getElementById('gauge-select');
  const gauges = pins.features
    .filter((f) => f.properties.kind === 'usgs_measured')
    .sort((a, b) => depthOf(b) - depthOf(a));
  select.replaceChildren(new Option('Choose a gauge…', ''));
  gauges.forEach((f, i) => {
    const p = f.properties;
    const depth = p.depth_m_low === null ? 'depth unknown' : `${Number(p.depth_m_low).toFixed(2)} m`;
    select.append(new Option(`${depth} · ${p.description || p.label}`, String(i)));
  });
  select.addEventListener('change', () => {
    const f = gauges[Number(select.value)];
    if (!select.value || !f) return;
    lastFocus = select;
    flyToGauge(f, 2500);
  });
  document.getElementById('replay-fly').addEventListener('click', () => {
    closePanel();
    if (gauges[0]) flyToGauge(gauges[0], 5000);
  });
}

// ---------------------------------------------------------------- panel
// Build panel content with textContent only: descriptions and AI reasoning are untrusted text.
let lastFocus = null;
function show(feature, isPin) {
  const p = feature.properties;
  const body = document.getElementById('panel-body');
  body.replaceChildren();
  const h = document.createElement('h3');
  h.tabIndex = -1;
  const dl = document.createElement('dl');
  const add = (k, v) => {
    if (v === undefined || v === null || v === '' || v === 'null') return;
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  };
  const caveat = document.createElement('p');
  caveat.className = 'caveat';

  if (isPin) {
    h.textContent = p.label;
    const lo = Number(p.depth_m_low), hi = Number(p.depth_m_high);
    add('Depth', p.depth_m_low === null || p.depth_m_low === 'null' ? 'Unknown (no reference object)'
      : lo === hi ? `${lo.toFixed(2)} m above ground` : `${lo.toFixed(2)}–${hi.toFixed(2)} m`);
    add('Where', p.description);
    add('USGS quality', p.quality);
    add('Taken', p.taken_at);
    add('Confidence', p.confidence);
    add('AI reasoning', p.reasoning);
    const obstacles = typeof p.obstacles === 'string' ? JSON.parse(p.obstacles) : (p.obstacles || []);
    add('Obstacles', obstacles.map((o) => `${o.type}: ${o.note}`).join('; '));
    caveat.textContent = p.kind === 'usgs_measured'
      ? 'High-water mark: the peak water line, surveyed after the flood. It is not a reading at a single moment.'
      : 'AI reading. It changes the water layer only after a reviewer confirms it.';
  } else {
    h.textContent = p.name && p.name !== 'null' ? p.name : 'Unnamed road';
    add('Status', ROAD_PHRASE[p.status] || p.status);
    add('Max est. depth', p.max_depth_m === null || p.max_depth_m === 'null' ? null : `${Number(p.max_depth_m).toFixed(2)} m`);
    add('Road type', p.highway);
    caveat.textContent = p.status === 'bridge_not_estimated'
      ? 'The ground model has no bridge decks, so no depth is estimated on bridges.'
      : 'Estimated from ground height and nearby measurements. Not measured on this road.';
  }
  body.append(h, dl, caveat);
  document.getElementById('panel').hidden = false;
  if (lastFocus) h.focus({ preventScroll: true }); // keyboard users land in the panel
}

function closePanel() {
  document.getElementById('panel').hidden = true;
  if (lastFocus) { lastFocus.focus(); lastFocus = null; }
}
document.getElementById('close').addEventListener('click', closePanel);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !document.getElementById('panel').hidden) closePanel();
});
map.on('mousedown', () => { lastFocus = null; }); // mouse users: don't steal focus

if (narrow()) document.getElementById('legend-details').open = false;
