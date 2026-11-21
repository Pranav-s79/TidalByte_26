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

map.on('load', async () => {
  const meta = await (await fetch('data/meta.json')).json();
  document.getElementById('label').textContent = meta.label;

  for (const name of ['water', 'unknown', 'roads_status', 'pins']) {
    map.addSource(name, { type: 'geojson', data: `data/${name}.geojson` });
  }
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
});

// Build panel content with textContent only: descriptions and AI reasoning are untrusted text.
function show(feature, isPin) {
  const p = feature.properties;
  const body = document.getElementById('panel-body');
  body.replaceChildren();
  const h = document.createElement('h3');
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
}
document.getElementById('close').addEventListener('click', () => { document.getElementById('panel').hidden = true; });
