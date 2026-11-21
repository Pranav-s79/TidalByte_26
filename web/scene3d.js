// Realistic 3D: Google Photorealistic 3D Tiles (via Cesium ion) + estimated water at its real elevation.
// Heights: our data is NAVD88 (lidar); the 3D city is WGS84-ellipsoid. We measure the offset, not assume it.
const FALLBACK_OFFSET = -27; // ponytail: approx. geoid height near Houston; used only if alignment fails
const statusEl = document.getElementById('status');
const json = (p) => fetch(p).then((r) => r.json());

if (!window.CESIUM_ION_TOKEN) {
  document.getElementById('label').textContent = 'Missing web/config.local.js with CESIUM_ION_TOKEN';
  throw new Error('no Cesium ion token');
}
Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN;

const viewer = new Cesium.Viewer('cesium', {
  globe: false, baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
  navigationHelpButton: false, timeline: false, animation: false, infoBox: false,
  selectionIndicator: false, fullscreenButton: false,
});
viewer.camera.setView({
  destination: Cesium.Cartesian3.fromDegrees(-95.4455, 29.6772, 330),
  orientation: { heading: Cesium.Math.toRadians(20), pitch: Cesium.Math.toRadians(-28), roll: 0 },
});

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
  document.getElementById('panel').hidden = false;
}
document.getElementById('close').addEventListener('click', () => { document.getElementById('panel').hidden = true; });
new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas).setInputAction((click) => {
  const picked = viewer.scene.pick(click.position);
  const info = picked && picked.id && picked.id.info;
  if (info) showPanel(info);
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

(async () => {
  try {
    viewer.scene.primitives.add(await Cesium.createGooglePhotorealistic3DTileset());
    const [meta, surface, pins, roads, unknown, samples] = await Promise.all([
      json('data/meta.json'), json('data/water_surface.geojson'), json('data/pins.geojson'),
      json('data/roads_status.geojson'), json('data/unknown.geojson'), json('data/ground_samples.json')]);
    document.getElementById('label').textContent = meta.label;
    const { offset, how } = await alignToLidar(samples);
    console.log('[flood3d] height offset', offset, how);
    statusEl.textContent = `Heights ${how} (offset ${offset.toFixed(1)} m).`;
    addWater(surface.features, offset);
    addEvidenceEdge(unknown);
    addRoads(roads);
    addGauges(pins.features, offset);
  } catch (e) {
    console.error('[flood3d]', e);
    statusEl.textContent = `Could not load the 3D scene: ${e.message}`;
  }
})();
