/* global Cesium */
// Route options panel: asks flood/serve.py's POST /route for least-deep options within the depth limit a
// person at the agency sets, draws them on the map and lets the dispatcher pick one. Rules
// (docs/routing-and-prediction.md): never "safe/clear/passable"; the limit field starts empty and the page
// never fills it; every depth shows its source; unobserved distance on every option; nothing is dispatched.
import { h, toast } from './ui.js';

const DEMO_TRIP = { start: [-95.451197, 29.697717], end: [-95.446069, 29.674473], name: 'Demo trip across Meyerland' };
const KIND = { least_deep: 'Least-deep', shortest_within_limit: 'Shortest within your limit', least_unobserved: 'Least unobserved road' };
// Not green (reads as "safe"), not red (closures), not amber/orange (bridges), not cyan (flooded roads).
const ROUTE_COLOR = { A: '#c084fc', B: '#f472b6', C: '#cbd5e1' };
const ROUTE_DASH = { A: null, B: 16, C: 6 }; // pattern as well as colour
const ROAD_H = 1.6;

const C = (css, a = 1) => Cesium.Color.fromCssColorString(css).withAlpha(a);
const $ = (s) => document.querySelector(s);
const fmtM = (m) => `${m.toFixed(2)} m`;
const fmtPt = ([lon, lat]) => `${lat.toFixed(5)}, ${lon.toFixed(5)}`;

export function setupRouting(scene, { getClosures = () => [], onFocus = () => {} } = {}) {
  const viewer = scene.viewer;
  const st = { start: null, end: null, startName: null, endName: null, picking: null, pickedAt: 0,
    doc: null, req: null, seq: 0, active: null, chosen: null, chosenKey: null, chosenInfo: null, replan: null, ents: [] };

  // ------------------------------------------------------------ map drawing
  function clear() { st.ents.forEach((e) => viewer.entities.remove(e)); st.ents = []; }
  const photoreal = () => scene.mapMode && scene.mapMode() === 'photorealistic';
  function positions(coords) {
    return photoreal() ? Cesium.Cartesian3.fromDegreesArray(coords.flat())
      : Cesium.Cartesian3.fromDegreesArrayHeights(coords.flatMap(([x, y]) => [x, y, ROAD_H]));
  }
  function marker([lon, lat], text, color) {
    return viewer.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat, photoreal() ? 0 : ROAD_H),
      point: { pixelSize: 13, color: C(color), outlineColor: C('#0a1220'), outlineWidth: 3,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: photoreal() ? Cesium.HeightReference.CLAMP_TO_GROUND : Cesium.HeightReference.NONE },
      label: { text, font: '700 11px Inter, system-ui, sans-serif', fillColor: C('#0a1220'), showBackground: true,
        backgroundColor: C(color, 0.95), backgroundPadding: new Cesium.Cartesian2(7, 4),
        pixelOffset: new Cesium.Cartesian2(0, -22), disableDepthTestDistance: Number.POSITIVE_INFINITY,
        heightReference: photoreal() ? Cesium.HeightReference.CLAMP_TO_GROUND : Cesium.HeightReference.NONE } });
  }
  function draw() {
    clear();
    const opts = st.doc && st.doc.options ? st.doc.options : [];
    // Draw the highlighted option last so it sits on top.
    const order = [...opts].sort((a, b) => (a.id === st.active) - (b.id === st.active));
    for (const o of order) {
      const on = o.id === st.active;
      // Over aerial imagery faded lines disappear: keep the other options solid there, just thinner.
      const pr = photoreal();
      const color = C(ROUTE_COLOR[o.id], on || pr ? 1 : 0.55);
      const material = ROUTE_DASH[o.id]
        ? new Cesium.PolylineDashMaterialProperty({ color, gapColor: C('#0a1220', on || pr ? 0.85 : 0.4), dashLength: ROUTE_DASH[o.id] })
        : new Cesium.PolylineOutlineMaterialProperty({ color, outlineColor: C('#0a1220', 0.9), outlineWidth: 2 });
      st.ents.push(viewer.entities.add({ polyline: { positions: positions(o.geometry.coordinates), width: on ? 9 : pr ? 6 : 5,
        // Ground-clamped lines need a geodesic arc: ArcType.NONE with clampToGround stops Cesium's renderer.
        arcType: photoreal() ? Cesium.ArcType.GEODESIC : Cesium.ArcType.NONE, clampToGround: photoreal(), material,
        depthFailMaterial: photoreal() ? undefined : material } }));
      const c = o.geometry.coordinates; const mid = c[Math.floor(c.length / 2)];
      st.ents.push(viewer.entities.add({ position: Cesium.Cartesian3.fromDegrees(mid[0], mid[1], photoreal() ? 20 : 8),
        label: { text: `${o.id}${o.id === st.chosen ? ' · CHOSEN' : ''}`, font: '700 12px Inter, system-ui, sans-serif',
          fillColor: C('#0a1220'), showBackground: true, backgroundColor: C(ROUTE_COLOR[o.id], 0.95),
          backgroundPadding: new Cesium.Cartesian2(7, 4), disableDepthTestDistance: Number.POSITIVE_INFINITY } }));
    }
    if (st.start) st.ents.push(marker(st.start, 'START', '#e6edf7'));
    if (st.end) st.ents.push(marker(st.end, 'END', '#e6edf7'));
  }
  function flyToRoutes() {
    const pts = [];
    for (const o of st.doc?.options || []) pts.push(...o.geometry.coordinates);
    if (st.start) pts.push(st.start);
    if (st.end) pts.push(st.end);
    if (!pts.length) return;
    // Top-down over the routes, padded so they land in the part of the map the panels and bars leave
    // visible (a tilted view hid START under the toolbar and the west side under this panel).
    const lons = pts.map((p) => p[0]); const lats = pts.map((p) => p[1]);
    let [w, s, e, n] = [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
    const dx = Math.max(e - w, 0.002); const dy = Math.max(n - s, 0.002);
    const panel = document.getElementById('left');
    const open = panel && !document.body.classList.contains('left-collapsed');
    const left = open ? Math.min(panel.getBoundingClientRect().right / innerWidth, 0.45) : 0.04;
    const pad = { left: left + 0.04, right: 0.12, top: 0.16, bottom: 0.14 };
    const W = dx / (1 - pad.left - pad.right); const H = dy / (1 - pad.top - pad.bottom);
    [w, e] = [w - pad.left * W, e + pad.right * W];
    [s, n] = [s - pad.bottom * H, n + pad.top * H];
    viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(w, s, e, n), duration: 1.8 });
  }

  // ------------------------------------------------------------ picking start/end on the map
  const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction(async (e) => {
    if (!st.picking) return;
    const which = st.picking;
    const pos = Cesium.Cartesian2.clone(e.position);
    st.pickedAt = performance.now();
    let cart = photoreal() ? await pickOnCity(pos) : null;
    if (!cart) cart = viewer.camera.pickEllipsoid(pos, viewer.scene.globe.ellipsoid);
    if (!cart || st.picking !== which) return; // missed the earth, or the person cancelled meanwhile
    const g = Cesium.Cartographic.fromCartesian(cart);
    st.pickedAt = performance.now();
    setPicking(null);
    setPoints({ [which]: [Cesium.Math.toDegrees(g.longitude), Cesium.Math.toDegrees(g.latitude)], [`${which}Name`]: null });
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  // The point on the 3D city under the click. Inside the click event Cesium's depth pick can come back empty
  // (seen on 3D Tiles: the roof is found one frame later), and the flat-globe fallback then lands tens of metres
  // off on a tilted view. So retry once after the next rendered frame before falling back.
  function pickOnCity(pos) {
    const sc = viewer.scene;
    if (!sc.pickPositionSupported) return Promise.resolve(null);
    const now = sc.pickPosition(pos);
    if (now) return Promise.resolve(now);
    return new Promise((resolve) => {
      const off = sc.postRender.addEventListener(() => { off(); resolve(sc.pickPosition(pos) || null); });
      sc.requestRender();
    });
  }
  function setPicking(which) {
    st.picking = which;
    viewer.scene.canvas.style.cursor = which ? 'crosshair' : '';
    document.body.classList.toggle('route-picking', !!which);
    if (which) toast(`Click the map to set the ${which}. Esc cancels.`, 'info', 3000);
    render();
  }
  // A new start or end makes the shown options answer a different trip: drop them (and the choice).
  function setPoints(change) {
    Object.assign(st, change);
    st.doc = null; st.req = null; st.active = null; st.chosen = null; st.chosenKey = null; st.replan = null;
    render(); draw();
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && st.picking) setPicking(null); });

  // ------------------------------------------------------------ server
  const LIMIT_MAX = 3; // matches the field's max
  function readLimit() {
    const el = $('#rt-limit');
    const raw = el.value.trim();
    if (!raw) return { error: el.validity.badInput ? 'The depth limit must be a number of metres.' : 'Enter the depth limit your agency set for this vehicle.' };
    const v = Number(raw);
    if (!Number.isFinite(v) || v < 0) return { error: 'The depth limit must be 0 m or more.' };
    if (v > LIMIT_MAX) return { error: `The depth limit must be ${LIMIT_MAX} m or less. Check the value your agency set.` };
    // The router echoes the limit to the centimetre; a finer value would be shown as a different number.
    if (Math.abs(v * 100 - Math.round(v * 100)) > 1e-6) return { error: 'Use at most two decimals for the depth limit (for example 0.30).' };
    return { value: Math.round(v * 100) / 100 };
  }
  const routeKey = (o) => o.geometry.coordinates.map((c) => c.join(',')).join(';');

  // rerun: repeat the last request (its limit, vehicle and switch) with the current closures, so editing the
  // form without pressing Find never changes what a re-plan uses.
  async function findRoutes({ rerun = false } = {}) {
    let req = st.req;
    if (!rerun) {
      const lim = readLimit();
      if (lim.error) { toast(lim.error, 'error', 4500); $('#rt-limit').focus(); return; }
      if (!st.start || !st.end) { toast('Set a start and an end first.', 'error', 3500); return; }
      req = { start: st.start, end: st.end, depth_limit_m: lim.value, avoid_unobserved: $('#rt-avoid').checked,
        vehicle: $('#rt-vehicle').value };
    }
    if (!req) return;
    const btn = $('#rt-go'); btn.disabled = true;
    const seq = (st.seq = (st.seq || 0) + 1);
    try {
      const res = await fetch('route', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start: req.start, end: req.end, depth_limit_m: req.depth_limit_m,
          avoid_unobserved: req.avoid_unobserved, closed_osm_ids: getClosures() }) })
        .catch(() => { throw new Error('Could not reach the route server. Start it with: python -m flood.serve'); });
      const doc = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(res.status === 501 || res.status === 404
          ? 'Route server not running. Start it with: python -m flood.serve' : doc.error || `HTTP ${res.status}`);
      }
      if (seq !== st.seq || req.start !== st.start || req.end !== st.end) return; // superseded
      st.doc = doc; st.req = req;
      keepChoice(doc);
      render(); draw(); if (!rerun) flyToRoutes();
    } catch (err) {
      toast(err.message, 'error', 6000);
    } finally {
      if ($('#rt-go')) $('#rt-go').disabled = false;
    }
  }

  // Rule 7: re-planning never switches the dispatcher's route. If the chosen route is still offered, keep it
  // chosen (its letter may change); if not, say so with its old numbers and leave the choice to them.
  function keepChoice(doc) {
    const opts = doc.options || [];
    const prev = st.chosenKey ? st.chosenInfo : null;
    const same = prev ? opts.find((o) => routeKey(o) === st.chosenKey) : null;
    st.replan = null;
    if (same) {
      if (same.id !== prev.id) toast(`The route you chose is now option ${same.id}.`, 'info', 4000);
      st.chosen = same.id; st.active = same.id; st.chosenInfo = { ...prev, id: same.id };
      return;
    }
    if (prev) {
      st.replan = prev;
      toast(`Re-planned: the route you chose (option ${prev.id}) is no longer offered. Choose again.`, 'error', 6000);
    }
    st.chosen = null; st.chosenKey = null; st.chosenInfo = null;
    st.active = opts[0] ? opts[0].id : null;
  }
  function choose(o) {
    st.chosen = o.id; st.active = o.id; st.chosenKey = routeKey(o); st.replan = null;
    st.chosenInfo = { id: o.id, distance_km: o.distance_km, deepest: o.deepest };
  }

  // ------------------------------------------------------------ panel
  function pointRow(which, label) {
    const p = st[which];
    const snap = st.doc && st.doc[which];
    const name = st[`${which}Name`] || (snap && snap.snapped_to);
    const away = snap && snap.snap_distance_m > 20 ? ` · ${snap.snap_distance_m} m from your point` : '';
    return h('div', { class: 'rt-point' },
      h('span', { class: 'rt-point-label' }, label),
      h('span', { class: 'rt-point-val', title: p ? fmtPt(p) : '' }, p ? (name || fmtPt(p)) + (snap ? away : '') : 'Not set'),
      h('button', { class: `btn btn-ghost rt-pick${st.picking === which ? ' on' : ''}`, type: 'button', icon: 'locate',
        'aria-pressed': String(st.picking === which), 'data-focus': `pick-${which}`,
        onclick: () => setPicking(st.picking === which ? null : which) }, st.picking === which ? 'Cancel' : 'Pick on map'));
  }

  function optionCard(o) {
    const d = o.deepest;
    const cams = o.cameras || [];
    const active = o.id === st.active; const chosen = o.id === st.chosen;
    return h('div', { class: `rt-card${active ? ' active' : ''}${chosen ? ' chosen' : ''}`, style: `--rc:${ROUTE_COLOR[o.id]}`,
      role: 'button', tabindex: '0', 'aria-pressed': String(active), 'data-focus': `card-${o.id}`,
      onclick: () => { st.active = o.id; render(); draw(); },
      onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); st.active = o.id; render(); draw(); } } },
    h('div', { class: 'rt-card-head' },
      h('span', { class: `rt-swatch rt-swatch-${o.id}` }, o.id),
      h('span', { class: 'rt-kind' }, KIND[o.kind] || o.kind),
      h('span', { class: 'rt-dist' }, `${o.distance_km.toFixed(2)} km`)),
    h('dl', { class: 'rt-facts' },
      h('dt', {}, 'Deepest point'),
      h('dd', {}, d ? h('span', {}, h('b', {}, fmtM(d.depth_m)), ` · ${d.source} · ${d.road || 'unnamed road'}`)
        : 'No depth on any road (all unobserved)'),
      h('dt', {}, 'Unobserved'),
      h('dd', { class: o.unobserved_share >= 0.5 ? 'rt-warn' : '' },
        `${o.unobserved_km.toFixed(2)} km (${Math.round(o.unobserved_share * 100)}%)${o.unobserved_km > 0 ? ' · no data, not dry' : ''}`),
      ...(o.n_bridges_not_estimated ? [h('dt', {}, 'Bridges'), h('dd', {}, `${o.n_bridges_not_estimated} not estimated`)] : []),
      h('dt', {}, 'Cameras'),
      h('dd', {}, cams.length ? cams.map((c) => `Camera ${c.id} · ${c.road}${c.cross_street ? ` at ${c.cross_street}` : ''} · `
        + `${c.route_km.toFixed(2)} km · view ${c.view} · ${c.n_readings} readings`).join('; ') : 'None along this route'),
      h('dt', {}, 'Re-checked'),
      h('dd', {}, o.recheck)),
    chosen
      ? h('div', { class: 'rt-chosen' }, 'Chosen by dispatcher · not dispatched')
      : h('button', { class: 'btn btn-confirm rt-choose', type: 'button', 'data-focus': `choose-${o.id}`,
        onclick: (e) => { e.stopPropagation(); choose(o); render(); draw();
          toast(`Option ${o.id} chosen. Nothing is dispatched; this prototype only records the choice on this page.`, 'info', 4500); } },
      `Choose option ${o.id}`));
  }

  // One line per road name and kind (closed / no data / a depth range), not one per OSM segment.
  function groupBlocking(list) {
    const groups = new Map();
    for (const b of list) {
      const kind = b.closed ? 'closed' : b.depth_m === null ? 'nodata' : `d:${b.source}`;
      const k = `${b.road || ''}|${kind}`;
      const g = groups.get(k);
      if (!g) { groups.set(k, { ...b, low: b.depth_m, n: 1 }); continue; }
      g.n += 1;
      if (b.depth_m !== null) { g.depth_m = Math.max(g.depth_m, b.depth_m); g.low = Math.min(g.low, b.depth_m); }
    }
    return [...groups.values()];
  }

  function results() {
    const doc = st.doc;
    if (!doc) return h('p', { class: 'sec-note' }, 'Options appear here and on the map. The router plans on the deeper end of every depth and never calls a road safe.');
    const out = [h('div', { class: 'rt-label' }, doc.label),
      h('div', { class: 'rt-limit-note' }, `${st.req && st.req.vehicle ? `${st.req.vehicle} · ` : ''}Limit ${fmtM(doc.depth_limit_m)} · set by your agency`
        + (doc.avoid_unobserved ? ' · avoiding unobserved roads' : '')
        + (doc.closed_osm_ids && doc.closed_osm_ids.length ? ` · ${doc.closed_osm_ids.length} hypothetical closure${doc.closed_osm_ids.length > 1 ? 's' : ''}` : ''))];
    if (st.replan) {
      const p = st.replan;
      out.push(h('div', { class: 'rt-replan', role: 'alert' }, h('b', {}, 'Re-planned after your change'),
        h('p', {}, `The route you chose (option ${p.id} · ${p.distance_km.toFixed(2)} km · deepest `
          + `${p.deepest ? `${fmtM(p.deepest.depth_m)} ${p.deepest.source}` : 'unknown'}) is not among these options. `
          + 'Nothing was switched for you; choose again.')));
    }
    if (doc.status !== 'ok') {
      const blocking = groupBlocking(doc.blocking || []);
      const noData = blocking.some((b) => !b.closed && b.depth_m === null);
      out.push(h('div', { class: 'rt-none' }, h('b', {}, doc.message),
        doc.shallowest_deepest_m != null
          ? h('p', {}, `The shallowest way through has a deepest point of ${fmtM(doc.shallowest_deepest_m)}, over your ${fmtM(doc.depth_limit_m)} limit.`)
          : null,
        blocking.length
          ? [h('p', {}, 'Roads in the way:'),
            h('ul', {}, ...blocking.map((b) => h('li', {}, `${b.road || 'Unnamed road'}: `
              + (b.closed ? 'closed (hypothetical)' : b.depth_m === null ? 'no data'
                : `${b.low !== b.depth_m ? `${b.low.toFixed(2)}–` : ''}${fmtM(b.depth_m)} · ${b.source}`)
              + (b.n > 1 ? ` (${b.n} segments)` : ''))))]
          : h('p', {}, 'Start and end are not connected by any mapped road.'),
        noData && doc.avoid_unobserved
          ? h('p', { class: 'rt-help' }, 'Roads with no data are left out because "Avoid unobserved roads" is on. '
            + 'Turning it off lets the router use them; no data does not mean dry.')
          : null));
    } else {
      out.push(...doc.options.map(optionCard));
    }
    out.push(h('details', { class: 'rt-caveats' }, h('summary', {}, 'Caveats'),
      h('ul', {}, ...(doc.caveats || []).map((c) => h('li', {}, c)))));
    return h('div', { class: 'rt-results' }, ...out);
  }

  function render() {
    const host = $('#routing');
    if (!host) return;
    const keep = { limit: $('#rt-limit')?.value ?? '', vehicle: $('#rt-vehicle')?.value ?? '', avoid: $('#rt-avoid')?.checked ?? false };
    const closures = getClosures().length;
    // Re-rendering replaces the panel; keep keyboard focus on the same card (a used Choose button becomes its card).
    const fk = host.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    host.replaceChildren(
      h('div', { class: 'rt-form' },
        h('label', { class: 'rt-field' }, h('span', {}, 'Vehicle'),
          h('select', { id: 'rt-vehicle', onchange: () => {
            // Each vehicle type has its own agency-set limit: never carry one vehicle's limit over to another.
            if (!$('#rt-limit').value) return;
            $('#rt-limit').value = ''; $('#rt-limit').focus();
            toast(`Enter the depth limit your agency set for: ${$('#rt-vehicle').value}.`, 'info', 4000);
          } }, ...['Ambulance', 'Fire engine', 'High-water rescue vehicle', 'Other']
            .map((v) => h('option', { value: v }, v)))),
        h('label', { class: 'rt-field' }, h('span', {}, 'Depth limit (m)', h('small', {}, 'set by your agency')),
          h('input', { id: 'rt-limit', type: 'number', min: '0', max: '3', step: '0.01', inputmode: 'decimal',
            placeholder: 'Required', 'aria-describedby': 'rt-limit-help' })),
        h('p', { class: 'rt-help', id: 'rt-limit-help' }, 'The deepest water this vehicle may cross. Nobody fills this in for you.'),
        pointRow('start', 'Start'),
        pointRow('end', 'End'),
        h('button', { class: 'btn btn-ghost rt-demo', type: 'button', icon: 'route', 'data-focus': 'demo',
          onclick: () => { setPicking(null);
            setPoints({ start: DEMO_TRIP.start, end: DEMO_TRIP.end, startName: 'Newcastle Drive', endName: 'Lymbar Drive' }); } },
        'Use demo trip (Newcastle Dr → Lymbar Dr)'),
        h('label', { class: 'rt-check' }, h('input', { id: 'rt-avoid', type: 'checkbox' }), 'Avoid unobserved roads'),
        closures ? h('p', { class: 'rt-help' }, `Includes ${closures} hypothetical closure${closures > 1 ? 's' : ''} you marked.`) : null,
        h('button', { id: 'rt-go', class: 'btn btn-confirm rt-go', type: 'button', icon: 'route', 'data-focus': 'go',
          onclick: () => findRoutes() }, 'Find route options')),
      results());
    $('#rt-limit').value = keep.limit;
    if (keep.vehicle) $('#rt-vehicle').value = keep.vehicle;
    $('#rt-avoid').checked = keep.avoid;
    if (fk) (host.querySelector(`[data-focus="${fk}"]`) || host.querySelector(`[data-focus="card-${fk.split('-')[1]}"]`))?.focus();
  }

  render();
  return {
    // True while choosing a point, and for a moment after, so the map's own click selection ignores that click.
    isPicking: () => !!st.picking || performance.now() - st.pickedAt < 400,
    redraw: draw,
    refresh: render,
    rerun: () => { if (st.req) findRoutes({ rerun: true }); },
  };
}
