// Command center entry: loads the replay layers, builds the 3D scene and wires the panels.
import { loadCore, loadBuildings, loadContext, loadCameras, loadPhotorealisticData, loadReferenceViews, reloadPins, postReview, pinId } from './data.js';
import { createScene } from './scene.js';
import { createPhotorealisticLayer } from './photorealistic.js';
import { loadFlood3d, createWaterLevels, roadDepth } from './flood3d.js';
import * as ui from './ui.js';

const state = { data: {}, selected: null, closures: new Map(), playing: false, step: 3, timer: null };
let photorealisticLayer = null;
let photorealisticLoad = null;

// Analysis replay: how the picture is built from evidence. Not a time series: high-water marks
// record the peak only, so there is no recorded flood progression to replay.
const STEPS = [
  { name: 'Measured', desc: 'USGS high-water marks', layers: { evidence: true, water: false, roads: false },
    caption: () => `${state.data.meta?.n_marks ?? 'The'} surveyed high-water marks: the only measured depths in this replay.` },
  { name: 'Estimated water', desc: 'Bathtub peak extent', layers: { evidence: true, water: true, roads: false },
    caption: 'Water levels blended between marks and filled over lidar ground. An estimate of the peak, not measured water.' },
  { name: 'Road impact', desc: 'Roads by estimated depth', layers: { evidence: true, water: true, roads: true },
    caption: 'Cyan roads are likely flooded; click one for its estimated deepest point. Amber dashes: bridges, depth not estimated.' },
  { name: 'Unknown areas', desc: 'Beyond 400 m of evidence', layers: { evidence: true, water: true, roads: true },
    caption: 'Striped areas have no mark within 400 m. Unknown is not dry.' },
];

ui.hydrateIcons();
const scene = createScene(document.getElementById('cesium'), document.getElementById('credits'), {
  onTileError: () => { ui.toast('Basemap tiles are not loading. The flood layers still work.', 'error', 6000); },
});
window.floodScene = scene; // console debugging
scene.intro();

// ---------------------------------------------------------------- selection
function select(info, { fly = false, focus = false } = {}) {
  state.selected = info;
  scene.select(info);
  if (info) {
    ui.setCollapsed('right', false);
    if (window.matchMedia('(max-width: 900px)').matches) ui.setCollapsed('left', true);
  }
  ui.renderDetails(info, ctx(focus));
  ui.markObservation(info && info.kind === 'pin' ? info.id : null);
  if (info && fly) scene.flyToFeature(info, info.kind === 'pin' ? { range: 260, pitch: -22 } : undefined);
}

function ctx(focus = false) {
  return {
    meta: state.data.meta,
    terrain: Boolean(state.grid),
    referenceViews: state.data.referenceViews,
    focus,
    flyTo: (sel, opts) => scene.flyToFeature(sel, opts),
    overview: () => scene.flyOverview(),
    isClosed: (id) => state.closures.has(id),
    toggleClosure,
    review: async (id, status) => {
      await postReview(id, status);
      ui.toast('Review recorded. Refreshing observations…', 'info');
      await refreshPins();
    },
  };
}

function toggleClosure(feature) {
  const id = feature.properties.osm_id;
  const on = !state.closures.has(id);
  if (on) state.closures.set(id, feature); else state.closures.delete(id);
  scene.setClosure(feature, on);
  ui.renderClosures([...state.closures.values()], (f) => select({ kind: 'road', props: f.properties, feature: f }, { fly: true }),
    (f) => toggleClosure(f));
  if (state.selected && state.selected.kind === 'road') ui.renderDetails(state.selected, ctx());
  ui.toast(on ? 'Hypothetical closure added. Not an official closure.' : 'Hypothetical closure removed.', 'info', 2600);
}

scene.onPick((info) => select(info, { fly: !!info && info.kind === 'pin' }));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && state.selected) select(null);
});

// ---------------------------------------------------------------- layers + timeline
function setLayer(name, on, animate = true) {
  scene.setLayer(name, on, { animate });
  ui.syncLayer(name, on);
}

function applyStep(i, { camera = true } = {}) {
  state.step = i;
  const s = STEPS[i];
  for (const [name, on] of Object.entries(s.layers)) setLayer(name, on);
  ui.setTimelineStep(i, STEPS.length);
  document.getElementById('tl-caption').textContent = typeof s.caption === 'function' ? s.caption() : s.caption;
  if (!camera) return;
  if (i === 2) {
    const deepest = deepestPin();
    if (deepest) { const [lon, lat] = deepest.geometry.coordinates; scene.flyToPoint(lon, lat, { range: 1100, pitch: -38, duration: 2.6 }); }
  } else if (i === 0 || i === 3) scene.flyOverview({ duration: 2.6 });
}

function deepestPin() {
  const feats = state.data.pins ? state.data.pins.features : [];
  return [...feats].sort((a, b) => (b.properties.depth_m_low ?? -1) - (a.properties.depth_m_low ?? -1))[0];
}

function stopPlay() { state.playing = false; clearTimeout(state.timer); ui.setPlaying(false); }
function play() {
  if (state.playing) { stopPlay(); return; }
  state.playing = true; ui.setPlaying(true);
  let i = state.step >= STEPS.length - 1 ? 0 : state.step + 1;
  const tick = () => {
    applyStep(i);
    if (i >= STEPS.length - 1) { state.timer = setTimeout(stopPlay, 3600); return; }
    i += 1;
    state.timer = setTimeout(tick, 3600);
  };
  tick();
}

if (window.matchMedia('(max-width: 900px)').matches) {
  document.body.classList.add('left-collapsed', 'right-collapsed', 'timeline-collapsed');
}
ui.setupCollapse();
ui.setupLayerDock(scene.layerState(), (name, on) => { stopPlay(); setLayer(name, on); });
ui.setupTimeline(STEPS, { onStep: (i) => { stopPlay(); applyStep(i); }, onPlay: play });
ui.setTimelineStep(STEPS.length - 1, STEPS.length);
document.getElementById('tl-caption').textContent = 'Evidence → estimate → road impact → unknown. Press play to replay how the picture is built.';
document.getElementById('cam-overview').addEventListener('click', () => scene.flyOverview());
document.getElementById('cam-street').addEventListener('click', () => (state.selected ? scene.flyToFeature(state.selected, { range: 180, pitch: -14 }) : scene.streetLevel()));
document.getElementById('cam-top').addEventListener('click', () => scene.topDown());
document.getElementById('cam-north').addEventListener('click', () => scene.resetNorth());
// ---------------------------------------------------------------- observations
function renderLists() {
  ui.renderStats(state.data);
  ui.renderObservations(state.data.pins, state.selected && state.selected.kind === 'pin' ? state.selected.id : null,
    (id) => select(scene.pinInfo(id), { fly: true, focus: true }));
}

async function refreshPins() {
  let fresh;
  try { fresh = await reloadPins(); } catch { return; }
  const old = new Map((state.data.pins?.features || []).map((f) => [pinId(f.properties), f]));
  let added = 0;
  for (const f of fresh.features) {
    const id = pinId(f.properties);
    const prev = old.get(id);
    if (prev && prev.properties.status === f.properties.status) continue;
    if (prev) scene.removePin(id);
    scene.addPin(f, { pulse: true });
    added += 1;
    if (!prev) ui.toast(`New observation: ${f.properties.description || f.properties.label || id}`, 'new');
  }
  for (const id of old.keys()) if (!fresh.features.some((f) => pinId(f.properties) === id)) scene.removePin(id);
  state.data.pins = fresh;
  if (added || old.size !== fresh.features.length) renderLists();
}

async function setMapMode(mode, { announce = true } = {}) {
  if (mode === 'operational') {
    scene.setMode('operational');
    ui.setStatus('ok', 'Operational map');
    if (announce) ui.toast('Analysis view enabled.', 'info', 2200);
    scene.flyOverview({ duration: 1.8 });
    return;
  }
  if (!window.CESIUM_ION_TOKEN) throw new Error('Photorealistic mode needs web/config.local.js with CESIUM_ION_TOKEN');
  ui.setStatus('loading', 'Loading photorealistic city');
  if (!photorealisticLayer) {
    photorealisticLoad ||= (async () => {
      const extra = await loadPhotorealisticData();
      return createPhotorealisticLayer(scene.viewer, { ...state.data, ...extra, grid: state.grid }, window.CESIUM_ION_TOKEN);
    })();
    try {
      photorealisticLayer = await photorealisticLoad;
    } catch (error) {
      photorealisticLoad = null;
      throw error;
    }
  }
  photorealisticLayer.waterLevels?.setDrop(state.levels ? state.levels.drop : 0);
  scene.setMode('photorealistic', photorealisticLayer);
  const al = photorealisticLayer.alignment;
  console.info('[command] photorealistic height alignment', al);
  ui.setStatus(al.how.startsWith('approximate') ? 'warn' : 'ok',
    `3D city ${al.how.startsWith('approximate') ? 'roughly ' : ''}aligned · NAVD88→ellipsoid ${al.offset.toFixed(1)} m`);
  if (announce) ui.toast('Photorealistic view enabled.', 'info', 2200);
  scene.flyOverview({ duration: 2.2 });
}

// Water level control: levels below the measured peak (connectivity from Brays Bayou, flood/inundation.py).
const LEVEL_STEPS = 8;           // slider positions; right end = measured peak
const LEVEL_STEP_M = 0.25;
function setupLevels() {
  const box = document.getElementById('levels');
  const range = document.getElementById('lv-range');
  const value = document.getElementById('lv-value');
  const playBtn = document.getElementById('lv-play');
  const peakCells = state.levels.cellsAt(0) || 1;
  const counts = new Map();
  let timer = null;
  box.hidden = false;
  const apply = (v) => {
    const drop = (LEVEL_STEPS - v) * LEVEL_STEP_M;
    state.levels.setDrop(drop);
    photorealisticLayer?.waterLevels?.setDrop(drop);
    if (!counts.has(drop)) counts.set(drop, state.levels.cellsAt(drop));
    const share = Math.round((100 * counts.get(drop)) / peakCells);
    const text = drop === 0 ? 'Measured peak · mapped extent' : `${drop.toFixed(2)} m below peak · ${share}% of peak area`;
    value.textContent = text;
    range.setAttribute('aria-valuetext', text);
  };
  const stop = () => { clearInterval(timer); timer = null; playBtn.innerHTML = ''; playBtn.insertAdjacentHTML('afterbegin', ui.iconSvg('play')); };
  range.addEventListener('input', () => { if (timer) stop(); apply(Number(range.value)); });
  playBtn.addEventListener('click', () => {
    if (timer) { stop(); return; }
    let v = Number(range.value) >= LEVEL_STEPS ? 0 : Number(range.value);
    range.value = String(v); apply(v);
    playBtn.innerHTML = ''; playBtn.insertAdjacentHTML('afterbegin', ui.iconSvg('pause'));
    timer = setInterval(() => {
      v += 1; range.value = String(v); apply(v);
      if (v >= LEVEL_STEPS) stop();
    }, 900);
  });
  // warm the cache for smooth scrubbing
  state.levels.prebuild(Array.from({ length: LEVEL_STEPS }, (_, i) => (i + 1) * LEVEL_STEP_M));
}

// Road status for the 3D page from the terrain-aware model (2D map and router keep roads_status).
function deriveRoads(fc, grid) {
  return { ...fc, features: fc.features.map((f) => {
    const p = f.properties;
    if (p.is_bridge) return { ...f, properties: { ...p, status: 'bridge_not_estimated', max_depth_m: null, model: 'flood3d' } };
    const r = roadDepth(grid, f.geometry.coordinates);
    if (!r.sampled) return f;
    const status = r.flooded ? 'likely_flooded' : r.inExtent ? 'possibly_flooded' : 'no_flooding_estimated';
    return { ...f, properties: { ...p, status, max_depth_m: r.flooded ? Math.round(r.maxDepth * 100) / 100 : null, model: 'flood3d' } };
  }) };
}

// ---------------------------------------------------------------- boot
(async () => {
  ui.renderDetails(null, ctx());
  ui.loaderStep('data', 'active');
  const core = await loadCore();
  state.data = core;
  if (core.errors.length) {
    ui.loaderStep('data', 'error', core.errors.join(' · '));
    ui.setStatus('warn', 'Some layers failed to load');
    ui.toast(`Could not load: ${core.errors.join(', ')}`, 'error', 8000);
  } else {
    ui.loaderStep('data', 'done', `${core.pins.features.length} marks · ${core.roads.features.length} roads`);
    ui.setStatus('ok', 'Replay data loaded');
  }
  renderLists();
  const [cameras, referenceViews] = await Promise.all([loadCameras(), loadReferenceViews()]);
  state.data.referenceViews = referenceViews;
  state.cameras = cameras.cameras;
  ui.renderCameras(cameras, (cam) => select({ kind: 'camera', id: `cam-${cam.id}`, cam }, { fly: true, focus: true }));

  ui.loaderStep('layers', 'active');
  try {
    const BBOX = [-95.460, 29.674, -95.425, 29.698];
    state.grid = await loadFlood3d().catch((e) => { console.warn('[command] flood3d unavailable, using bathtub layers', e); return null; });
    if (state.grid) {
      // Terrain-aware model: lidar terrain, USACE extent, water level from USGS marks (docs/inundation.md).
      await scene.useTerrain(state.grid, { bbox: BBOX });
      state.levels = createWaterLevels(scene.viewer, state.grid);
      scene.addFloodSurface(state.levels, state.grid.header.reach_outline || []);
      setupLevels();
      if (core.roads) {
        state.data.roads = deriveRoads(core.roads, state.grid);
        scene.addRoads(state.data.roads);
        // Ordinary streets are in the basemap; the flooded-road overlay is opt-in ("Road impact").
        setLayer('roads', false, false);
      }
      renderLists();
      ui.loaderStep('layers', 'done', `Terrain flood model · ${state.grid.header.cell_m} m grid`);
    } else {
      scene.addContext(await loadContext().catch(() => ({})), BBOX);
      if (core.unknown) scene.addUnknown(core.unknown);
      if (core.water) scene.addWater(core.water);
      if (core.roads) scene.addRoads(core.roads);
      ui.loaderStep('layers', 'done', 'Water · roads · unknown');
    }
  } catch (e) {
    ui.loaderStep('layers', 'error', e.message);
    console.error('[command] layers', e);
  }

  ui.loaderStep('city', 'active');
  try {
    const n = await scene.addBuildings(await loadBuildings());
    ui.loaderStep('city', 'done', `${n.toLocaleString()} buildings · heights approximate`);
  } catch (e) {
    ui.loaderStep('city', 'error', 'Building footprints unavailable');
    ui.toast('3D buildings could not load. Flood layers still work.', 'error', 6000);
    console.error('[command] buildings', e);
  }

  (core.pins ? core.pins.features : []).forEach((feature, index) => {
    scene.addPin(feature, { delay: 900 + index * 140, pulse: true });
  });
  scene.addCameras(state.cameras || []);

  const mapModes = ui.setupMapMode({
    available: Boolean(window.CESIUM_ION_TOKEN),
    onChange: setMapMode,
    onError: (error) => {
      ui.setStatus('warn', 'Photorealistic mode unavailable');
      ui.toast(`Could not switch map mode: ${error.message}`, 'error', 8000);
      console.error('[command] map mode', error);
    },
  });

  const startedPhotorealistic = window.CESIUM_ION_TOKEN
    ? await mapModes.activate('photorealistic', { announce: false })
    : false;
  ui.hideLoader();
  if (!startedPhotorealistic) scene.flyOverview({ duration: 3.2 });
  setInterval(refreshPins, 30000);
})();
