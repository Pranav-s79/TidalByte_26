// DOM for the command center. Untrusted strings (descriptions, AI reasoning, names) are only ever
// set with textContent; innerHTML is used solely for our constant icon markup.
import { icon } from './icons.js';
import { PHRASE, ROAD_PHRASE, AI_STATUS_PHRASE, CRITICAL_DEPTH_M, isUsgs, pinId, safeUrl } from './data.js';
import { pinTier, roadTier } from './scene.js';
import { CLS, CLASS_LABEL } from './flood3d.js';

export const $ = (sel) => document.querySelector(sel);
export const iconSvg = (name) => icon(name);

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'icon') el.insertAdjacentHTML('afterbegin', icon(v));
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

const fmtDepth = (m) => (m === null || m === undefined || Number.isNaN(Number(m)) ? null : `${Number(m).toFixed(2)} m`);
const coordText = (lon, lat) => `${Math.abs(lat).toFixed(5)}°${lat >= 0 ? 'N' : 'S'}  ${Math.abs(lon).toFixed(5)}°${lon >= 0 ? 'E' : 'W'}`;

// Static markup uses <span data-icon="name"> placeholders.
export function hydrateIcons(root = document) {
  for (const el of root.querySelectorAll('[data-icon]')) { el.outerHTML = icon(el.dataset.icon); }
}

// ---------------------------------------------------------------- loader
export function loaderStep(name, state, detail) {
  const row = document.querySelector(`#loader [data-step="${name}"]`);
  if (!row) return;
  row.dataset.state = state;
  if (detail) row.querySelector('.ld-detail').textContent = detail;
}
export function hideLoader() {
  const el = $('#loader');
  el.classList.add('done');
  setTimeout(() => el.remove(), 700);
}

// ---------------------------------------------------------------- toasts
export function toast(text, kind = 'info', ms = 4200) {
  const host = $('#toasts');
  const t = h('div', { class: `toast toast-${kind}`, role: kind === 'error' ? 'alert' : 'status',
    icon: kind === 'error' ? 'alert' : kind === 'new' ? 'activity' : 'info' }, h('span', {}, text));
  host.append(t);
  requestAnimationFrame(() => t.classList.add('in'));
  setTimeout(() => { t.classList.remove('in'); setTimeout(() => t.remove(), 400); }, ms);
}

// ---------------------------------------------------------------- top bar status
export function setStatus(kind, text) {
  const el = $('#sys-status');
  el.dataset.kind = kind;
  el.querySelector('.st-text').textContent = text;
}
export function setBuilt(meta) {
  const el = $('#sys-built');
  if (!meta || !meta.generated_at) { el.hidden = true; return; }
  const d = new Date(meta.generated_at);
  el.querySelector('.st-text').textContent = `Layers built ${d.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}`;
  el.hidden = false;
}

// ---------------------------------------------------------------- map appearance
export function setupMapMode({ available, onChange, onError }) {
  const buttons = [...document.querySelectorAll('[data-map-mode]')];
  const photo = buttons.find((b) => b.dataset.mapMode === 'photorealistic');
  if (!available && photo) {
    photo.disabled = true;
    photo.title = 'Add CESIUM_ION_TOKEN to web/config.local.js to enable this mode';
  }
  const activate = async (mode, options) => {
    const button = buttons.find((candidate) => candidate.dataset.mapMode === mode);
    if (!button || button.disabled || button.getAttribute('aria-pressed') === 'true') return false;
    buttons.forEach((candidate) => { candidate.disabled = true; });
    button.dataset.loading = 'true';
    try {
      await onChange(mode, options);
      buttons.forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
      return true;
    } catch (error) {
      onError?.(error);
      return false;
    } finally {
      delete button.dataset.loading;
      buttons.forEach((candidate) => {
        candidate.disabled = candidate.dataset.mapMode === 'photorealistic' && !available;
      });
    }
  };
  for (const button of buttons) button.addEventListener('click', () => activate(button.dataset.mapMode));
  return { activate };
}

// ---------------------------------------------------------------- left panel
export function renderStats({ meta, pins, roads }) {
  const host = $('#stats');
  host.replaceChildren();
  const feats = pins ? pins.features : [];
  const marks = feats.filter((f) => isUsgs(f.properties)).length;
  const ai = feats.filter((f) => !isUsgs(f.properties));
  const awaiting = ai.filter((f) => f.properties.status === 'ai_proposed' || f.properties.status === 'needs_review').length;
  const rf = roads ? roads.features.map((f) => f.properties) : [];
  const count = (pred) => rf.filter(pred).length;
  const likely = count((p) => p.status === 'likely_flooded');
  const critical = count((p) => p.status === 'likely_flooded' && p.max_depth_m !== null && p.max_depth_m >= CRITICAL_DEPTH_M);
  const unknown = count((p) => p.status === 'unknown');
  const tile = (cls, ic, value, label, sub) => h('div', { class: `stat ${cls}` },
    h('div', { class: 'stat-top', icon: ic }, h('span', { class: 'stat-label' }, label)),
    h('div', { class: 'stat-value' }, value), sub ? h('div', { class: 'stat-sub' }, sub) : null);
  const tiles = [
    tile('t-cyan', 'gauge', marks, 'Measured marks', 'USGS · observed'),
    tile('t-red', 'route', likely, 'Roads likely flooded', `${critical} over ${CRITICAL_DEPTH_M} m est.`),
    tile('t-slate', 'info', unknown, 'Roads unknown', 'no mark within 400 m'),
  ];
  if (ai.length) tiles.splice(1, 0, tile('t-amber', 'sparkles', ai.length, 'AI readings', `${awaiting} awaiting review`));
  host.append(...tiles);
  const note = $('#stats-note');
  note.textContent = meta?.n_confirmed_photos
    ? `${meta.n_confirmed_photos} confirmed photo${meta.n_confirmed_photos === 1 ? '' : 's'} · ${meta.radius_m} m evidence radius`
    : '';
  note.hidden = !note.textContent;
}

export function renderCameras(result, onSelect) {
  const host = $('#cameras');
  const section = host.closest('.sec');
  host.replaceChildren();
  $('#cam-count').textContent = result.cameras.length ? String(result.cameras.length) : '0';
  if (!result.cameras.length) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  for (const cam of result.cameras) {
    const src = safeUrl(cam.snapshot);
    host.append(h('button', { class: 'cam', type: 'button', onclick: () => onSelect(cam) },
      h('div', { class: 'cam-thumb' }, src ? h('img', { src, alt: '', loading: 'lazy' }) : h('span', { icon: 'video' })),
      h('div', { class: 'cam-meta' }, h('div', { class: 'cam-name' }, cam.name),
        h('div', { class: 'cam-sub' }, `${cam.source ? `${cam.source} · ` : ''}${cam.direction ? `${cam.direction} lanes · ` : ''}no frames yet`))));
  }
}

const TIER_META = {
  observed: { cls: 'k-cyan', tag: 'USGS · Observed' },
  critical: { cls: 'k-red', tag: 'USGS · Observed · over 1.2 m' },
  uncertain: { cls: 'k-amber', tag: 'AI · awaiting review' },
  confirmed: { cls: 'k-cyan', tag: 'AI · confirmed' },
  rejected: { cls: 'k-slate', tag: 'AI · rejected' },
};

export function renderObservations(pins, selectedId, onSelect) {
  const host = $('#observations');
  host.replaceChildren();
  const feats = pins ? [...pins.features] : [];
  $('#obs-count').textContent = String(feats.length);
  if (!feats.length) {
    host.append(h('div', { class: 'empty', icon: 'gauge' }, h('div', { class: 'empty-title' }, 'No observations loaded'),
      h('div', { class: 'empty-text' }, 'Run python -m flood.run to build web/data/.')));
    return;
  }
  // AI readings needing review first, then measured marks by depth.
  const order = (f) => (pinTier(f.properties) === 'uncertain' ? 0 : 1);
  feats.sort((a, b) => order(a) - order(b) || (b.properties.depth_m_low ?? -1) - (a.properties.depth_m_low ?? -1));
  for (const f of feats) {
    const p = f.properties;
    const tier = pinTier(p);
    const id = pinId(p);
    const meta = TIER_META[tier];
    host.append(h('button', { class: `obs ${meta.cls}${id === selectedId ? ' active' : ''}`, type: 'button',
      'data-id': id, 'aria-pressed': id === selectedId ? 'true' : 'false', onclick: () => onSelect(id) },
    h('span', { class: `obs-mark ${isUsgs(p) ? 'disc' : 'diamond'}`, 'aria-hidden': 'true' }),
    h('span', { class: 'obs-main' }, h('span', { class: 'obs-title' }, p.description || p.label || 'Observation'),
      h('span', { class: 'obs-sub' }, `${meta.tag}${p.quality ? ` · ${p.quality} quality` : ''}`)),
    h('span', { class: 'obs-depth' }, fmtDepth(p.depth_m_low) || '?')));
  }
}

export function markObservation(id) {
  for (const b of document.querySelectorAll('#observations .obs')) {
    const on = b.dataset.id === id;
    b.classList.toggle('active', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  }
}

// ---------------------------------------------------------------- right panel: details
function depthBar(lo, hi, cls) {
  if (lo === null || lo === undefined) return null;
  const max = Math.max(2, (hi ?? lo) * 1.2);
  const pct = (v) => `${Math.min(100, (v / max) * 100)}%`;
  const ticks = [0.3, 0.6, 1.2].filter((t) => t < max);
  return h('div', { class: `dbar ${cls}`, role: 'img', 'aria-label': `Depth ${fmtDepth(lo)}${hi && hi !== lo ? ` to ${fmtDepth(hi)}` : ''} on a 0 to ${max.toFixed(1)} m scale` },
    h('div', { class: 'dbar-track' },
      h('div', { class: 'dbar-fill', style: `width:${pct(hi ?? lo)}` }),
      hi !== null && hi !== undefined && hi !== lo ? h('div', { class: 'dbar-range', style: `left:${pct(lo)};width:calc(${pct(hi)} - ${pct(lo)})` }) : null,
      ...ticks.map((t) => h('div', { class: 'dbar-tick', style: `left:${pct(t)}` }))),
    h('div', { class: 'dbar-scale' }, h('span', {}, '0 m'), ...ticks.map((t) => h('span', { style: `left:${pct(t)}` }, `${t}`)), h('span', { class: 'end' }, `${max.toFixed(1)} m`)));
}

const field = (k, v, mono = false) => (v === null || v === undefined || v === '' ? null
  : [h('dt', {}, k), h('dd', { class: mono ? 'mono' : null }, v)]);

function header(badges, title, sub) {
  return h('div', { class: 'd-head' }, h('div', { class: 'badges' }, ...badges), h('h2', { class: 'd-title', tabindex: '-1' }, title),
    sub ? h('div', { class: 'd-sub mono' }, sub) : null);
}
const badge = (cls, ic, text) => h('span', { class: `badge ${cls}`, icon: ic }, text);

function depthBlock(value, qualifier, cls) {
  return h('div', { class: `d-depth ${cls}` }, h('div', { class: 'd-depth-val' }, value), h('div', { class: 'd-depth-q' }, qualifier));
}

function confidenceMeter(level) {
  const n = { low: 1, medium: 2, high: 3 }[level] || 0;
  return h('span', { class: 'conf', 'aria-label': `Confidence ${level || 'unknown'}` },
    ...[1, 2, 3].map((i) => h('i', { class: i <= n ? 'on' : null })), h('span', {}, level || 'unknown'));
}

export function renderDetails(sel, ctx) {
  const host = $('#details');
  host.replaceChildren();
  $('#right').classList.toggle('has-selection', !!sel);
  if (!sel) {
    host.append(h('div', { class: 'empty empty-lg', icon: 'locate' },
      h('div', { class: 'empty-title' }, 'Select something on the map'),
      h('div', { class: 'empty-text' }, 'Click a gauge, a road or a flooded area to see its evidence, depth range and confidence.'),
      h('ul', { class: 'hint-list' },
        h('li', {}, h('kbd', {}, 'Click'), ' gauge or road for evidence'),
        h('li', {}, h('kbd', {}, 'Drag'), ' or two-finger left/right to rotate'),
        h('li', {}, 'Two-finger up/down to zoom'),
        h('li', {}, h('kbd', {}, 'Ctrl'), '+drag to tilt · ', h('kbd', {}, 'Esc'), ' to deselect'))));
    return;
  }
  const actions = h('div', { class: 'd-actions' });
  const fly = (label, ic, fn) => h('button', { class: 'btn btn-ghost', type: 'button', icon: ic, onclick: fn }, label);

  if (sel.kind === 'pin') {
    const p = sel.feature.properties;
    const [lon, lat] = sel.feature.geometry.coordinates;
    const usgs = isUsgs(p);
    const tier = pinTier(p);
    const badges = [usgs ? badge('k-cyan', 'gauge', PHRASE.usgs)
      : badge(tier === 'rejected' ? 'k-slate' : tier === 'confirmed' ? 'k-cyan' : 'k-amber', 'sparkles', AI_STATUS_PHRASE[p.status] || p.status)];
    if (tier === 'critical') badges.push(badge('k-red', 'alert', `Over ${CRITICAL_DEPTH_M} m · high priority`));
    host.append(header(badges, p.description || p.label || 'Observation', coordText(lon, lat)));
    const lo = p.depth_m_low, hi = p.depth_m_high;
    const range = lo === null || lo === undefined ? 'Depth unknown' : hi !== null && hi !== undefined && hi !== lo ? `${fmtDepth(lo)}–${fmtDepth(hi)}` : fmtDepth(lo);
    host.append(depthBlock(range, usgs ? 'Observed · peak water above ground' : tier === 'confirmed' ? 'Estimated by AI · confirmed by a reviewer' : 'Estimated by AI · not yet confirmed',
      tier === 'critical' ? 'c-red' : usgs || tier === 'confirmed' ? 'c-cyan' : 'c-amber'));
    const bar = depthBar(lo, hi, tier === 'critical' ? 'c-red' : usgs ? 'c-cyan' : 'c-amber');
    if (bar) host.append(bar);
    if (!usgs) {
      const photo = safeUrl(p.photo);
      host.append(h('div', { class: 'photo' }, photo ? h('img', { src: photo, alt: 'Photo analysed by the AI reader' })
        : h('div', { class: 'photo-empty', icon: 'video' }, 'No photo attached')));
    }
    const obstacles = typeof p.obstacles === 'string' ? JSON.parse(p.obstacles || '[]') : (p.obstacles || []);
    host.append(h('dl', { class: 'fields' },
      field('Source', usgs ? 'USGS high-water mark, Harvey 2017' : (p.model || 'AI photo reader')),
      field('Mark ID', usgs ? p.id : null, true),
      field('Quality', p.quality),
      field('Confidence', usgs ? null : confidenceMeter(p.confidence)),
      field('Ground', p.ground_m !== undefined && p.ground_m !== null ? `${Number(p.ground_m).toFixed(2)} m NAVD88` : null, true),
      field('Taken', p.taken_at, true),
      field('Reference', p.reference_object),
      field('Obstacles', obstacles.length ? obstacles.map((o) => [o.type, o.note].filter(Boolean).join(': ')).join('; ') : null)));
    const reference = usgs ? ctx.referenceViews?.[String(p.id)] : null;
    const referenceImage = reference ? safeUrl(`photos/refs/${reference.file}`) : null;
    if (reference && referenceImage) {
      const captured = reference.captured_at < '2017-08-25'
        ? `${reference.captured_at} · before Harvey`
        : reference.captured_at;
      const source = safeUrl(reference.page_url);
      host.append(h('figure', { class: 'reference-photo' },
        h('img', { src: referenceImage, loading: 'lazy', alt: `Dry street reference near high-water mark ${p.id}` }),
        h('figcaption', {},
          h('strong', {}, `Dry street reference · ${Math.round(reference.distance_m)} m away`),
          h('span', {}, captured),
          source ? h('a', { href: source, target: '_blank', rel: 'noopener' }, `${reference.creator || 'Mapillary contributor'} · ${reference.license}`) : null)));
    }
    if (p.reasoning) host.append(h('div', { class: 'reasoning' }, h('div', { class: 'sec-label', icon: 'sparkles' }, 'AI findings'), h('p', {}, p.reasoning)));
    host.append(h('p', { class: 'caveat', icon: 'info' }, usgs
      ? 'High-water mark: the peak water line, surveyed after the flood. It is not a reading at a single moment.'
      : 'AI reading. It changes the water layer only after a reviewer confirms it.'));
    if (usgs) {
      host.append(h('div', { class: 'review review-na', icon: 'check' }, 'Measured evidence: no AI review needed.'));
    } else {
      const msg = h('div', { class: 'review-msg', role: 'status' });
      const review = (status) => async (e) => {
        const btns = e.currentTarget.parentElement.querySelectorAll('button');
        btns.forEach((b) => { b.disabled = true; });
        msg.textContent = 'Recording decision…';
        try { await ctx.review(pinId(p), status); msg.textContent = 'Decision recorded. Layers will rebuild.'; }
        catch (err) { msg.textContent = err.message; msg.classList.add('err'); }
        finally { btns.forEach((b) => { b.disabled = false; }); }
      };
      host.append(h('div', { class: 'review' }, h('div', { class: 'sec-label', icon: 'check' }, 'Dispatcher review'),
        h('div', { class: 'review-btns' },
          h('button', { class: 'btn btn-confirm', type: 'button', icon: 'check', onclick: review('confirmed') }, 'Confirm'),
          h('button', { class: 'btn btn-reject', type: 'button', icon: 'x', onclick: review('rejected') }, 'Reject'),
          h('button', { class: 'btn btn-ghost', type: 'button', onclick: review('needs_review') }, 'Needs review')),
        msg));
    }
    actions.append(fly('Street level', 'street', () => ctx.flyTo(sel, { range: 180, pitch: -14 })), fly('Overview', 'overview', ctx.overview));
  } else if (sel.kind === 'road') {
    const p = sel.feature.properties;
    const tier = roadTier(p);
    const cls = { critical: 'k-red', likely: 'k-cyan', possible: 'k-amber', bridge: 'k-amber' }[tier] || 'k-slate';
    const badges = [badge(cls, 'route', ROAD_PHRASE[p.status] || p.status)];
    if (tier === 'critical') badges.push(badge('k-red', 'alert', `Over ${CRITICAL_DEPTH_M} m est. · high priority`));
    if (ctx.isClosed(p.osm_id)) badges.push(badge('k-red', 'ban', 'Closed (hypothetical)'));
    host.append(header(badges, p.name && p.name !== 'null' ? p.name : 'Unnamed road', `OSM ${p.osm_id} · ${p.highway}`));
    const d = p.max_depth_m;
    host.append(depthBlock(fmtDepth(d) || 'Not estimated', d === null || d === undefined
      ? (p.status === 'bridge_not_estimated' ? 'The ground model has no bridge decks' : 'No depth on this segment')
      : 'Estimated · deepest point on this segment', tier === 'critical' ? 'c-red' : tier === 'likely' ? 'c-cyan' : 'c-amber'));
    const bar = depthBar(d, d, tier === 'critical' ? 'c-red' : 'c-cyan');
    if (bar) host.append(bar);
    host.append(h('dl', { class: 'fields' }, field('Status', ROAD_PHRASE[p.status] || p.status), field('Road type', p.highway),
      field('Bridge', p.is_bridge ? 'Yes' : 'No')));
    host.append(h('p', { class: 'caveat', icon: 'info' }, p.status === 'bridge_not_estimated'
      ? 'The ground model has no bridge decks, so no depth is estimated on bridges.'
      : p.status === 'unknown' ? 'No USGS mark within 400 m. This road is not shown as dry.'
        : 'Estimated from ground height and nearby measurements. Not measured on this road.'));
    const closed = ctx.isClosed(p.osm_id);
    host.append(h('div', { class: 'review' }, h('div', { class: 'sec-label', icon: 'ban' }, 'Hypothetical closure'),
      h('p', { class: 'review-note' }, 'If this road were closed… Mark it to see it on the map. This is a planning what-if, not an official closure.'),
      h('div', { class: 'review-btns' }, h('button', { class: `btn ${closed ? 'btn-ghost' : 'btn-reject'}`, type: 'button', icon: closed ? 'x' : 'ban',
        onclick: () => ctx.toggleClosure(sel.feature) }, closed ? 'Remove hypothetical closure' : 'Mark closed (hypothetical)'))));
    actions.append(fly('Zoom to road', 'locate', () => ctx.flyTo(sel)), fly('Overview', 'overview', ctx.overview));
  } else if (sel.kind === 'water' && sel.at) {
    // A clicked point on the terrain-aware flood model (flood3d grid).
    const a = sel.at;
    const meta = {
      [CLS.PROFILE]: ['k-cyan', 'droplet', CLASS_LABEL[CLS.PROFILE], 'c-cyan'],
      [CLS.SHORELINE]: ['k-amber', 'droplet', CLASS_LABEL[CLS.SHORELINE], 'c-amber'],
      [CLS.UNRESOLVED]: ['k-amber', 'info', CLASS_LABEL[CLS.UNRESOLVED], 'c-amber'],
      [CLS.DRY]: ['k-slate', 'info', CLASS_LABEL[CLS.DRY], 'c-amber'],
    }[a.cls] || ['k-slate', 'info', PHRASE.unknown, 'c-amber'];
    host.append(header([badge(meta[0], meta[1], meta[2])], a.cls === CLS.DRY ? 'Outside the mapped flood extent' : 'Estimated flooding at this point',
      coordText(a.lon, a.lat)));
    const value = a.depth !== null ? fmtDepth(a.depth) : a.cls === CLS.UNRESOLVED ? 'Depth not resolved' : a.cls === CLS.DRY ? 'Not mapped' : 'Unknown';
    const q = a.cls === CLS.PROFILE ? 'Estimated peak depth · water level from nearby USGS marks'
      : a.cls === CLS.SHORELINE ? 'Estimated peak depth · lower confidence (no marks on this reach)'
        : a.cls === CLS.UNRESOLVED ? 'Inside the USACE extent, but the estimated water level is at or below the ground here'
          : 'The USACE model shows no riverine flooding here. Not verified, and rain ponding is not modelled.';
    host.append(depthBlock(value, q, meta[3]));
    if (a.depth !== null) { const bar = depthBar(a.depth, a.depth, meta[3]); if (bar) host.append(bar); }
    const m = (v) => (v === null || v === undefined ? null : `${Number(v).toFixed(2)} m NAVD88`);
    host.append(h('dl', { class: 'fields' },
      field('Water level', a.wse !== null ? `${m(a.wse)} (estimated)` : null, false),
      field('Ground', m(a.ground) ? `${m(a.ground)} (lidar)` : null),
      field('Extent', 'USACE HEC-RAS maximum, Harvey 2017 (modelled)'),
      field('Level from', a.cls === CLS.PROFILE ? `USGS high-water marks, interpolated along Brays Bayou`
        : a.cls === CLS.SHORELINE ? 'Nearest mapped shoreline elevation (FwDET)' : null)));
    host.append(h('p', { class: 'caveat', icon: 'info' },
      'Peak estimate from a modelled extent and 10 surveyed marks. Not a hydraulic simulation. Not an all-clear.'));
    actions.append(fly('Zoom here', 'locate', () => ctx.flyTo(sel)), fly('Overview', 'overview', ctx.overview));
  } else if (sel.kind === 'water') {
    const p = sel.props;
    const likely = p.status === 'likely';
    host.append(header([badge(likely ? 'k-cyan' : 'k-amber', 'droplet', likely ? PHRASE.likely : PHRASE.possible)], 'Estimated flood area'));
    host.append(depthBlock(p.depth_band, 'Estimated depth range · peak, bathtub model', likely ? 'c-cyan' : 'c-amber'));
    host.append(h('dl', { class: 'fields' },
      field('Confidence', likely ? 'Higher: wet even with the lower water-level estimate' : 'Lower: wet only with the upper water-level estimate'),
      field('Method', `Water levels blended from USGS marks within ${ctx.meta?.radius_m ?? 400} m, filled over lidar ground`)));
    host.append(h('p', { class: 'caveat', icon: 'info' }, ctx.meta?.label || 'Estimated peak extent. Not measured water. Not an all-clear.'));
    actions.append(fly('Zoom to area', 'locate', () => ctx.flyTo(sel)), fly('Overview', 'overview', ctx.overview));
  } else if (sel.kind === 'camera') {
    const c = sel.cam;
    host.append(header([badge('k-slate', 'video', `${c.source || 'Traffic'} camera ${c.id}`)], c.name, coordText(c.lon, c.lat)));
    host.append(h('dl', { class: 'fields' },
      field('Camera ID', c.id, true),
      field('Lanes nearest', c.direction),
      field('Replay area', c.inBox === null ? null : c.inBox ? 'Inside' : 'Outside, within 1.7 km'),
      field('Frames', 'None yet. TxDOT snapshot permission is pending, so no water reading comes from this camera.')));
    host.append(h('p', { class: 'caveat', icon: 'info' },
      'Planned input for live readings. In this replay, depths come from USGS high-water marks, not cameras.'));
    actions.append(fly('Zoom here', 'locate', () => ctx.flyTo(sel)), fly('Overview', 'overview', ctx.overview));
  } else if (sel.kind === 'unknown') {
    host.append(header([badge('k-slate', 'info', PHRASE.unknown)], 'No evidence here'));
    host.append(h('p', { class: 'caveat', icon: 'info' }, ctx.terrain
      ? 'Outside the analysis area: no lidar, no flood model. Unknown is not dry.'
      : 'No USGS high-water mark within 400 m, so no depth is estimated. Unknown is not dry.'));
    actions.append(fly('Overview', 'overview', ctx.overview));
  }
  host.append(actions);
  if (ctx.focus) host.querySelector('.d-title')?.focus({ preventScroll: true });
}

export function renderClosures(list, onSelect, onRemove) {
  const sec = $('#closures-sec');
  const host = $('#closures');
  host.replaceChildren();
  sec.hidden = list.length === 0;
  for (const f of list) {
    const p = f.properties;
    host.append(h('div', { class: 'closure' },
      h('button', { class: 'closure-name', type: 'button', icon: 'ban', onclick: () => onSelect(f) }, p.name && p.name !== 'null' ? p.name : `OSM ${p.osm_id}`),
      h('button', { class: 'icon-btn sm', type: 'button', 'aria-label': `Remove hypothetical closure on ${p.name || p.osm_id}`, icon: 'x', onclick: () => onRemove(f) })));
  }
}

// ---------------------------------------------------------------- layer dock + legend
export function setupLayerDock(state, onToggle) {
  for (const b of document.querySelectorAll('#layer-dock [data-layer]')) {
    b.setAttribute('aria-pressed', state[b.dataset.layer] ? 'true' : 'false');
    if (b.dataset.locked) continue;
    b.addEventListener('click', () => onToggle(b.dataset.layer, b.getAttribute('aria-pressed') !== 'true'));
  }
  const keyBtn = $('#key-btn');
  keyBtn.addEventListener('click', () => {
    const open = keyBtn.getAttribute('aria-expanded') !== 'true';
    keyBtn.setAttribute('aria-expanded', String(open));
    $('#legend').hidden = !open;
  });
}
export function syncLayer(name, on) {
  const b = document.querySelector(`#layer-dock [data-layer="${name}"]`);
  if (b) b.setAttribute('aria-pressed', on ? 'true' : 'false');
}

// ---------------------------------------------------------------- timeline
export function setupTimeline(steps, { onStep, onPlay }) {
  const host = $('#tl-steps');
  host.replaceChildren();
  steps.forEach((s, i) => host.append(h('button', { class: 'tl-step', type: 'button', 'data-i': i,
    'aria-label': `${i + 1} of ${steps.length}: ${s.name}. ${s.desc}`, onclick: () => onStep(i) },
    h('span', { class: 'tl-dot', 'aria-hidden': 'true' }), h('span', { class: 'tl-name' }, s.name), h('span', { class: 'tl-desc' }, s.desc))));
  $('#tl-play').addEventListener('click', onPlay);
}
export function setTimelineStep(i, total) {
  document.querySelectorAll('.tl-step').forEach((b, j) => {
    b.classList.toggle('done', j < i); b.classList.toggle('current', j === i);
    b.setAttribute('aria-current', j === i ? 'step' : 'false');
  });
  $('#tl-progress').style.width = `${total > 1 ? (Math.max(0, i) / (total - 1)) * 100 : 0}%`;
}
export function setPlaying(on) {
  const b = $('#tl-play');
  b.innerHTML = icon(on ? 'pause' : 'play');
  b.setAttribute('aria-label', on ? 'Pause analysis replay' : 'Play analysis replay');
}

// ---------------------------------------------------------------- collapsible panels
export function setCollapsed(id, collapsed, { focus = false } = {}) {
  document.body.classList.toggle(`${id}-collapsed`, collapsed);
  document.querySelectorAll(`[data-collapse="${id}"]`).forEach((b) => b.setAttribute('aria-expanded', String(!collapsed)));
  const panel = document.getElementById(id);
  if (panel) {
    panel.setAttribute('aria-hidden', String(collapsed));
    panel.toggleAttribute('inert', collapsed);
  }
  if (!focus) return;
  const target = collapsed
    ? document.querySelector(`.panel-tab[data-collapse="${id}"]`)
    : panel?.querySelector('.panel-head button');
  target?.focus({ preventScroll: true });
}

export function setupCollapse() {
  for (const id of ['left', 'right', 'timeline']) setCollapsed(id, document.body.classList.contains(`${id}-collapsed`));
  for (const btn of document.querySelectorAll('[data-collapse]')) {
    btn.addEventListener('click', () => {
      const id = btn.dataset.collapse;
      const collapsed = !document.body.classList.contains(`${id}-collapsed`);
      if (!collapsed && window.matchMedia('(max-width: 900px)').matches) {
        if (id === 'left') setCollapsed('right', true);
        if (id === 'right') setCollapsed('left', true);
      }
      setCollapsed(id, collapsed, { focus: id !== 'timeline' });
    });
  }
}
