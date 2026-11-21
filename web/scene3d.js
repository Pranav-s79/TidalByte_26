// Realistic 3D: Google Photorealistic 3D Tiles (via Cesium ion) + estimated water at its real elevation.
// Heights: our data is NAVD88 (lidar); the 3D city is WGS84-ellipsoid. We measure the offset, not assume it.
const FALLBACK_OFFSET = -27; // ponytail: approx. geoid height near Houston; used only if alignment fails
const statusEl = document.getElementById('status');
const json = (p) => fetch(p).then((r) => r.json());

if (!window.Cesium || !window.CESIUM_ION_TOKEN) {
  statusEl.textContent = !window.Cesium ? 'Could not load Cesium. Check the connection or open the street map.'
    : 'The 3D city needs a Cesium ion token in web/config.local.js.';
  throw new Error(statusEl.textContent);
}
Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;

const viewer = new Cesium.Viewer('cesium', {
  globe: false, baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
  navigationHelpButton: false, timeline: false, animation: false, infoBox: false,
  selectionIndicator: false, fullscreenButton: false,
});
const meyerland = Cesium.Cartesian3.fromDegrees(-95.4506, 29.6820, -12);
const photoLocation = Cesium.Cartesian3.fromDegrees(recordedReading.lon, recordedReading.lat);
const photoPanel = document.getElementById('photo-panel');
const photoPin = viewer.entities.add({
  id: recordedReading.id, position: photoLocation,
  point: { pixelSize: 15, color: Cesium.Color.fromCssColorString('#89e4cf'), outlineWidth: 3,
    outlineColor: Cesium.Color.fromCssColorString('#123b36'), disableDepthTestDistance: Number.POSITIVE_INFINITY,
    heightReference: Cesium.HeightReference.CLAMP_TO_3D_TILE,
    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2600) },
  label: { text: 'USGS field photo · ±30 m', font: 'bold 14px system-ui', showBackground: true,
    pixelOffset: new Cesium.Cartesian2(0, -23), disableDepthTestDistance: Number.POSITIVE_INFINITY,
    heightReference: Cesium.HeightReference.CLAMP_TO_3D_TILE,
    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2600) },
});

function visitPlace(animate) {
  const atPhoto = location.hash === '#piney-point';
  document.getElementById('place').textContent = atPhoto ? 'Buffalo Bayou at Piney Point' : 'Meyerland';
  for (const link of document.querySelectorAll('.map-header nav a')) {
    if (link.id === (atPhoto ? 'piney-point' : 'meyerland')) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }
  photoPanel.hidden = !atPhoto;
  document.getElementById('panel').hidden = true;
  document.getElementById('legend').hidden = atPhoto;
  viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(atPhoto ? photoLocation : meyerland, 1), {
    offset: new Cesium.HeadingPitchRange(Cesium.Math.toRadians(atPhoto ? 185 : 25),
      Cesium.Math.toRadians(-40), atPhoto ? 430 : 550),
    duration: animate && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 1.8 : 0,
  });
}
visitPlace(false);
window.addEventListener('hashchange', () => visitPlace(true));
for (const link of document.querySelectorAll('.map-header nav a')) {
  link.addEventListener('click', () => { if (link.hash === location.hash) visitPlace(true); });
}
document.getElementById('close-photo').addEventListener('click', () => { photoPanel.hidden = true; });

// Low quantile of (3D-city height - lidar ground) at road points: trees and cars only push heights up.
async function alignToLidar(samples) {
  const cartos = samples.map((s) => Cesium.Cartographic.fromDegrees(s.lon, s.lat));
  const hit = await viewer.scene.sampleHeightMostDetailed(cartos);
  const diffs = hit.map((c, i) => (c && Number.isFinite(c.height) ? c.height - samples[i].ground_m : null))
    .filter((d) => d !== null).sort((a, b) => a - b);
  if (diffs.length < 10) return { offset: FALLBACK_OFFSET, how: `approximate (only ${diffs.length} road points hit)` };
  const offset = diffs[Math.floor(diffs.length * 0.25)];
  if (offset < -35 || offset > -18) return { offset: FALLBACK_OFFSET, how: `approximate (measured ${offset.toFixed(1)} m looked wrong)` };
  return { offset, how: `aligned on ${diffs.length} road points` };
}

function hierarchy(rings) {
  const pos = (r) => Cesium.Cartesian3.fromDegreesArray(r.slice(0, -1).flat()); // GeoJSON repeats first point
  return new Cesium.PolygonHierarchy(pos(rings[0]), rings.slice(1).map((r) => new Cesium.PolygonHierarchy(pos(r))));
}

function addWater(features, offset) {
  const instances = (status) => features.filter((f) => f.properties.status === status).map((f) =>
    new Cesium.GeometryInstance({ geometry: new Cesium.PolygonGeometry({
      polygonHierarchy: hierarchy(f.geometry.coordinates),
      height: f.properties.level_m + offset,
      vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT,
    }) }));
  const water = new Cesium.Material({ fabric: { type: 'Water', uniforms: {
    baseWaterColor: new Cesium.Color(0.16, 0.3, 0.42, 0.78),
    blendColor: new Cesium.Color(0.2, 0.4, 0.55, 0.78),
    normalMap: Cesium.buildModuleUrl('Assets/Textures/waterNormals.jpg'),
    frequency: 2500.0, animationSpeed: 0.008, amplitude: 4.0, specularIntensity: 0.6,
  } } });
  viewer.scene.primitives.add(new Cesium.Primitive({ geometryInstances: instances('likely'),
    appearance: new Cesium.EllipsoidSurfaceAppearance({ material: water, aboveGround: true, translucent: true }) }));
  const possible = instances('possible');
  if (possible.length) {
    viewer.scene.primitives.add(new Cesium.Primitive({ geometryInstances: possible,
      appearance: new Cesium.EllipsoidSurfaceAppearance({ aboveGround: true, translucent: true,
        material: Cesium.Material.fromType('Color', { color: new Cesium.Color(0.58, 0.77, 0.99, 0.45) }) }) }));
  }
}

function addGauges(pins, offset) {
  for (const f of pins) {
    const p = f.properties;
    if (p.ground_m === null || p.depth_m_low === null) continue;
    const [lon, lat] = f.geometry.coordinates;
    const usgs = p.kind === 'usgs_measured';
    const base = p.ground_m + offset;
    const top = base + p.depth_m_low;
    viewer.entities.add({
      info: p,
      polyline: { positions: Cesium.Cartesian3.fromDegreesArrayHeights([lon, lat, base, lon, lat, top + 0.6]),
        width: 7, material: new Cesium.PolylineOutlineMaterialProperty({
          color: usgs ? Cesium.Color.fromCssColorString('#facc15') : Cesium.Color.fromCssColorString('#a78bfa'),
          outlineColor: Cesium.Color.BLACK, outlineWidth: 2 }) },
    });
    viewer.entities.add({
      info: p,
      position: Cesium.Cartesian3.fromDegrees(lon, lat, top + 0.6),
      point: { pixelSize: 11, color: usgs ? Cesium.Color.fromCssColorString('#111827') : Cesium.Color.WHITE,
        outlineColor: Cesium.Color.WHITE, outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      label: { text: `${p.depth_m_low.toFixed(2)} m`, font: 'bold 15px system-ui', fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK, outlineWidth: 4, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -18), disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
  }
}

function addRoads(roads) {
  const style = {
    likely_flooded: new Cesium.ColorMaterialProperty(Cesium.Color.fromCssColorString('#e11d48').withAlpha(0.85)),
    bridge_not_estimated: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.fromCssColorString('#d97706') }),
  };
  for (const f of roads.features) {
    const material = style[f.properties.status];
    if (!material) continue;
    viewer.entities.add({ info: { ...f.properties, isRoad: true }, polyline: {
      positions: Cesium.Cartesian3.fromDegreesArray(f.geometry.coordinates.flat()),
      clampToGround: true, width: 5, material } });
  }
}

function addEvidenceEdge(unknown) {
  for (const f of unknown.features) {
    for (const ring of f.geometry.coordinates.slice(1)) { // holes = where we do have evidence
      viewer.entities.add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArray(ring.flat()),
        clampToGround: true, width: 3,
        material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.WHITE.withAlpha(0.9), dashLength: 24 }) } });
    }
  }
}

// Dry street views facing each USGS mark (python -m flood.find_photos --views web/photos/refs).
let markViews = {};
json('photos/refs/index.json').then((v) => { markViews = v; }).catch(() => {});

function refFigure(v) {
  const fig = document.createElement('figure');
  fig.className = 'ref-view';
  const img = document.createElement('img');
  const when = v.captured_at < '2017-08-25' ? `${v.captured_at}, before Harvey` : v.captured_at;
  Object.assign(img, { src: `photos/refs/${v.file}`, width: 960, height: 640, loading: 'lazy',
    alt: `Dry street view near this high-water mark, ${when}` });
  const cap = document.createElement('figcaption');
  const credit = document.createElement('a');
  Object.assign(credit, { href: v.page_url, target: '_blank', rel: 'noopener',
    textContent: `${v.creator || 'Mapillary contributor'} · ${v.license}, cropped` });
  cap.append(`Dry street view ${Math.round(v.distance_m)} m away (${when}). It shows the place for scale; `
    + 'the depth is the USGS measurement. ', credit);
  fig.append(img, cap);
  return fig;
}

function showPanel(p) {
  const body = document.getElementById('panel-body');
  body.replaceChildren();
  const h = document.createElement('h3');
  const dl = document.createElement('dl');
  const add = (k, v) => {
    if (v === undefined || v === null || v === '') return;
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  };
  const caveat = document.createElement('p');
  caveat.className = 'caveat';
  if (p.isRoad) {
    h.textContent = p.name || 'Unnamed road';
    add('Status', p.status === 'bridge_not_estimated' ? 'Bridge: depth not estimated' : 'Likely flooded');
    add('Max est. depth', p.max_depth_m === null ? null : `${p.max_depth_m.toFixed(2)} m`);
    caveat.textContent = 'Estimated from ground height and nearby measurements. Not measured on this road.';
  } else {
    h.textContent = p.label;
    add('Water depth', `${p.depth_m_low.toFixed(2)} m above ground`);
    add('Where', p.description);
    add('USGS quality', p.quality);
    caveat.textContent = 'High-water mark: the peak water line, surveyed after the flood. It is not a reading at a single moment.';
  }
  body.append(h, dl, caveat);
  if (!p.isRoad && markViews[p.id]) body.append(refFigure(markViews[p.id]));
  document.getElementById('panel').hidden = false;
}
document.getElementById('close').addEventListener('click', () => { document.getElementById('panel').hidden = true; });
new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction((click) => {
  const picked = viewer.scene.pick(click.position);
  if (picked && picked.id === photoPin) {
    if (location.hash === '#piney-point') photoPanel.hidden = false;
    else location.hash = 'piney-point';
    return;
  }
  const info = picked && picked.id && picked.id.info;
  if (info) showPanel(info);
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

(async () => {
  try {
    const city = viewer.scene.primitives.add(await Cesium.createGooglePhotorealistic3DTileset());
    // Let the visible buildings stream before requesting off-screen road samples for the water heights.
    const firstView = new Promise((resolve) => city.initialTilesLoaded.addEventListener(resolve));
    const [meta, surface, pins, roads, unknown, samples] = await Promise.all([
      json('data/meta.json'), json('data/water_surface.geojson'), json('data/pins.geojson'),
      json('data/roads_status.geojson'), json('data/unknown.geojson'), json('data/ground_samples.json')]);
    document.getElementById('label').textContent = 'Peak extent estimated from ' + meta.n_marks + ' surveyed USGS marks.';
    await firstView;
    statusEl.textContent = '3D city loaded · aligning flood layers…';
    let alignment;
    try {
      alignment = await alignToLidar(samples.filter((_, i) => i % 3 === 0));
    } catch {
      alignment = { offset: FALLBACK_OFFSET, how: 'approximate (road sampling unavailable)' };
    }
    const { offset, how } = alignment;
    console.log('[flood3d] height offset', offset, how);
    statusEl.textContent = `Present-day 3D city · replay heights ${how}.`;
    addWater(surface.features, offset);
    addEvidenceEdge(unknown);
    addRoads(roads);
    addGauges(pins.features, offset);
  } catch (e) {
    statusEl.textContent = 'Could not load the 3D scene. Check the connection and Cesium asset access, or open the street map.';
  }
})();
