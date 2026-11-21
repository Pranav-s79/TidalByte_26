/* global Cesium */
// Cesium scene for the command center: dark basemap, extruded OSM buildings, estimated water,
// road status, unknown areas and evidence markers. No Cesium ion assets are required.
import { BANDS, CRITICAL_DEPTH_M, isUsgs, pinId } from './data.js';

const C = (css, a = 1) => Cesium.Color.fromCssColorString(css).withAlpha(a);
const CENTER = [-95.4425, 29.686];
const STALK_M = 20;          // marker stalk height (a pointer, not a depth)
const ROAD_H = 0.5;          // draw roads just above the ground plane

export const COLORS = {
  cyan: '#22d3ee', red: '#f43f5e', amber: '#fbbf24', slate: '#64748b', white: '#e6edf7',
  band: ['#67e8f9', '#22d3ee', '#0ea5e9', '#3b82f6'], // shallow → deep
  bandAlpha: [0.24, 0.32, 0.42, 0.52],
};

export function pinTier(p) {
  if (isUsgs(p)) return p.depth_m_low !== null && p.depth_m_low >= CRITICAL_DEPTH_M ? 'critical' : 'observed';
  if (p.status === 'rejected') return 'rejected';
  if (p.status === 'confirmed') return 'confirmed';
  return 'uncertain';
}
const TIER_COLOR = { observed: COLORS.cyan, critical: COLORS.red, uncertain: COLORS.amber, confirmed: COLORS.cyan, rejected: COLORS.slate };

// Roads stay cyan when likely flooded: in this replay most flooded roads exceed 1.2 m somewhere,
// so a depth-based red would mean "almost everything". Red is kept for rare, high-priority items.
export function roadTier(p) {
  if (p.status === 'likely_flooded') return 'likely';
  return { possibly_flooded: 'possible', bridge_not_estimated: 'bridge', no_flooding_estimated: 'none' }[p.status] || 'unknown';
}

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
function tween(ms, step, done) {
  if (reduceMotion() || ms <= 0) { step(1); if (done) done(); return; }
  const t0 = performance.now();
  const frame = (now) => {
    const t = Math.min(1, (now - t0) / ms);
    step(ease(t));
    if (t < 1) requestAnimationFrame(frame); else if (done) done();
  };
  requestAnimationFrame(frame);
}

function hierarchy(rings) {
  const ring = (r) => Cesium.Cartesian3.fromDegreesArray(r.slice(0, -1).flat()); // GeoJSON repeats the first point
  return new Cesium.PolygonHierarchy(ring(rings[0]), rings.slice(1).map((r) => new Cesium.PolygonHierarchy(ring(r))));
}

function whenReady(scene, prim) {
  return new Promise((resolve) => {
    if (prim.ready) { resolve(prim); return; }
    const off = scene.postRender.addEventListener(() => { if (prim.ready) { off(); resolve(prim); } });
  });
}

export function createScene(container, creditContainer, { onTileError } = {}) {
  const viewer = new Cesium.Viewer(container, {
    baseLayer: false, baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false, creditContainer, msaaSamples: 4,
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    skyBox: false, skyAtmosphere: false, contextOptions: { webgl: { alpha: true } },
  });
  const scene = viewer.scene;
  scene.backgroundColor = Cesium.Color.TRANSPARENT; // CSS gradient shows through as the night sky
  scene.globe.baseColor = C('#0a1220');
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  scene.fog.enabled = false;
  if (scene.sun) scene.sun.show = false;
  if (scene.moon) scene.moon.show = false;
  scene.screenSpaceCameraController.minimumZoomDistance = 40;
  scene.screenSpaceCameraController.maximumZoomDistance = 30000;
  scene.screenSpaceCameraController.enableRotate = true;
  scene.screenSpaceCameraController.enableTilt = true;
  scene.screenSpaceCameraController.enableZoom = true;
  scene.screenSpaceCameraController.rotateEventTypes = [Cesium.CameraEventType.LEFT_DRAG];
  scene.screenSpaceCameraController.zoomEventTypes = [Cesium.CameraEventType.WHEEL, Cesium.CameraEventType.PINCH];
  scene.screenSpaceCameraController.tiltEventTypes = [
    Cesium.CameraEventType.MIDDLE_DRAG,
    { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL },
  ];
  scene.screenSpaceCameraController.inertiaSpin = 0.7;
  scene.screenSpaceCameraController.inertiaZoom = 0.75;

  // Soft key light from the south-west so building faces read in 3D.
  const enu = Cesium.Transforms.eastNorthUpToFixedFrame(Cesium.Cartesian3.fromDegrees(...CENTER));
  const local = Cesium.Cartesian3.normalize(new Cesium.Cartesian3(0.5, 0.6, -0.62), new Cesium.Cartesian3());
  const dir = Cesium.Matrix4.multiplyByPointAsVector(enu, local, new Cesium.Cartesian3());
  scene.light = new Cesium.DirectionalLight({ direction: Cesium.Cartesian3.normalize(dir, dir), intensity: 2.4,
    color: C('#d6e4ff') });

  // Keep status colours crisp. Bloom makes dense road networks harder to distinguish.
  const bloom = scene.postProcessStages.bloom;
  bloom.enabled = false;

  // No third-party basemap tiles: the "basemap" is our own dark ground plate drawn from OSM vectors
  // (addContext), so nothing needs an API key and the look stays consistent.
  void onTileError;
  viewer.creditDisplay.addStaticCredit(new Cesium.Credit('Buildings, roads & water © OpenStreetMap contributors (ODbL)', false));

  const layers = { context: [], buildings: [], water: [], roads: [], evidence: [], unknown: [] };
  const pins = new Map();           // id → { feature, tier, entities: {...}, color }
  const closures = new Map();       // osm_id → [entities]
  let selected = null;
  let hoverEnt = null;
  let selectEnt = null;
  let mode = 'operational';
  let photorealisticLayer = null;

  // ---------------------------------------------------------------- ground plate (context)
  // A slightly lifted navy plate over the replay box with a faint 100 m survey grid, plus OSM water
  // and parks so Brays Bayou reads at a glance. Outside the plate: empty night ground.
  function addContext(ctx, bbox) {
    const pad = 0.004;
    const rect = Cesium.Rectangle.fromDegrees(bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad);
    const plate = (material, height) => {
      const prim = scene.primitives.add(new Cesium.Primitive({
        geometryInstances: new Cesium.GeometryInstance({ geometry: new Cesium.RectangleGeometry({ rectangle: rect, height,
          vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT }) }),
        appearance: new Cesium.EllipsoidSurfaceAppearance({ material, aboveGround: false, translucent: true }),
        allowPicking: false, asynchronous: true }));
      layers.context.push({ prim });
      return prim;
    };
    plate(Cesium.Material.fromType('Color', { color: C('#0c1628', 0.96) }), 0);
    const kmX = Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(rect.west * 180 / Math.PI, bbox[1]),
      Cesium.Cartesian3.fromDegrees(rect.east * 180 / Math.PI, bbox[1])) / 1000;
    const kmY = Cesium.Cartesian3.distance(Cesium.Cartesian3.fromDegrees(bbox[0], rect.south * 180 / Math.PI),
      Cesium.Cartesian3.fromDegrees(bbox[0], rect.north * 180 / Math.PI)) / 1000;
    plate(Cesium.Material.fromType('Grid', { color: C('#7dd3fc', 0.07), cellAlpha: 0.0,
      lineCount: new Cesium.Cartesian2(Math.round(kmX * 10), Math.round(kmY * 10)), lineThickness: new Cesium.Cartesian2(1, 1) }), 0.02);
    // plate edge
    const [w, s, e, n] = [rect.west, rect.south, rect.east, rect.north].map((r) => r * 180 / Math.PI);
    const edge = viewer.entities.add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArrayHeights([w, s, 0.1, e, s, 0.1, e, n, 0.1, w, n, 0.1, w, s, 0.1]),
      width: 1.2, material: C('#7dd3fc', 0.22), arcType: Cesium.ArcType.NONE } });
    layers.context.push({ entity: edge });

    const fill = (rings, color, height) => {
      if (!rings.length) return null;
      const prim = scene.primitives.add(new Cesium.Primitive({
        allowPicking: false, asynchronous: true,
        geometryInstances: rings.filter((r) => r.length >= 6).map((r) => new Cesium.GeometryInstance({
          geometry: new Cesium.PolygonGeometry({ polygonHierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(r)),
            height, vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT }) })),
        appearance: new Cesium.EllipsoidSurfaceAppearance({ material: Cesium.Material.fromType('Color', { color }), aboveGround: true, translucent: true }),
      }));
      layers.context.push({ prim });
      return prim;
    };
    fill(ctx.parks || [], C('#10241f', 0.75), 0.03);
    fill(ctx.water_areas || [], C('#0f2a47', 0.95), 0.035);
    const ways = (ctx.waterways || []).filter((wy) => wy[2].length >= 4);
    if (ways.length) {
      const waterways = scene.primitives.add(new Cesium.Primitive({
        allowPicking: false, asynchronous: true,
        geometryInstances: ways.map(([kind, , coords]) => new Cesium.GeometryInstance({
          geometry: new Cesium.PolylineGeometry({ positions: Cesium.Cartesian3.fromDegreesArrayHeights(
            coords.flatMap((v, i) => (i % 2 ? [v, 0.06] : [v]))), width: kind === 'river' ? 5 : 2,
          vertexFormat: Cesium.PolylineColorAppearance.VERTEX_FORMAT, arcType: Cesium.ArcType.NONE }),
          attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(C(kind === 'river' ? '#1f4d7a' : '#18375a', 0.95)) },
        })),
        appearance: new Cesium.PolylineColorAppearance({ translucent: true }),
      }));
      layers.context.push({ prim: waterways });
    }
  }

  // ---------------------------------------------------------------- buildings
  async function addBuildings(data) {
    const shades = ['#2c3b56', '#30405c', '#283651', '#33435f', '#2a3955'].map((c) => C(c));
    const tall = C('#3c4e6d');
    const instances = [];
    data.buildings.forEach(([h, , ring], i) => {
      if (ring.length < 6) return;
      instances.push(new Cesium.GeometryInstance({
        geometry: new Cesium.PolygonGeometry({
          polygonHierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(ring)),
          height: 0, extrudedHeight: h, vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT,
        }),
        attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(h > 9 ? tall : shades[(i * 7) % shades.length]) },
      }));
    });
    const prim = scene.primitives.add(new Cesium.Primitive({
      geometryInstances: instances, allowPicking: false, asynchronous: true,
      appearance: new Cesium.PerInstanceColorAppearance({ translucent: false, closed: true }),
    }));
    layers.buildings.push({ prim });
    await whenReady(scene, prim);
    return instances.length;
  }

  // ---------------------------------------------------------------- water (estimated)
  // One sheet per depth band, drawn at the band's middle depth above ground. Translucent:
  // it is an estimate of peak extent, not measured water.
  function addWater(fc) {
    const groups = new Map();
    for (const f of fc.features) {
      const { status, depth_band: band } = f.properties;
      const key = `${status}|${band}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(f);
    }
    for (const [key, feats] of groups) {
      const [status, band] = key.split('|');
      const bi = Math.max(0, BANDS.findIndex((b) => b.band === band));
      const possible = status === 'possible';
      const color = possible ? C(COLORS.amber) : C(COLORS.band[bi]);
      const alpha = possible ? 0.16 : COLORS.bandAlpha[bi];
      const height = possible ? 0.08 : BANDS[bi].mid;
      const mat = Cesium.Material.fromType('Color', { color: color.withAlpha(alpha) });
      const prim = scene.primitives.add(new Cesium.Primitive({
        asynchronous: true,
        geometryInstances: feats.map((f) => new Cesium.GeometryInstance({
          geometry: new Cesium.PolygonGeometry({ polygonHierarchy: hierarchy(f.geometry.coordinates), height,
            vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT }),
          id: { kind: 'water', props: f.properties, feature: f },
        })),
        appearance: new Cesium.EllipsoidSurfaceAppearance({ material: mat, aboveGround: true, translucent: true }),
      }));
      layers.water.push({ prim, mat, key: 'color', alpha });
    }
  }

  // ---------------------------------------------------------------- unknown + evidence edge
  function addUnknown(fc) {
    for (const f of fc.features) {
      const mat = Cesium.Material.fromType('Stripe', {
        evenColor: C('#94a3b8', 0.1), oddColor: C('#0b1322', 0.12), repeat: 240, horizontal: false,
      });
      const prim = scene.primitives.add(new Cesium.Primitive({
        asynchronous: true,
        geometryInstances: new Cesium.GeometryInstance({
          geometry: new Cesium.PolygonGeometry({ polygonHierarchy: hierarchy(f.geometry.coordinates), height: 0.04,
            stRotation: Math.PI / 4, vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT }),
          id: { kind: 'unknown', props: f.properties },
        }),
        appearance: new Cesium.EllipsoidSurfaceAppearance({ material: mat, aboveGround: true, translucent: true }),
      }));
      layers.unknown.push({ prim });
      // Holes in the unknown polygon are where evidence exists: outline them as the "edge of evidence".
      const rings = f.geometry.coordinates.slice(1);
      if (rings.length) {
        const edgeMat = Cesium.Material.fromType('PolylineDash', { color: C('#cbd5e1', 0.55), gapColor: Cesium.Color.TRANSPARENT, dashLength: 18 });
        const edge = scene.primitives.add(new Cesium.Primitive({
          asynchronous: true,
          geometryInstances: rings.map((r) => new Cesium.GeometryInstance({
            geometry: new Cesium.PolylineGeometry({ positions: Cesium.Cartesian3.fromDegreesArrayHeights(r.flatMap(([x, y]) => [x, y, 0.3])),
              width: 1.6, vertexFormat: Cesium.PolylineMaterialAppearance.VERTEX_FORMAT, arcType: Cesium.ArcType.NONE }),
          })),
          appearance: new Cesium.PolylineMaterialAppearance({ material: edgeMat }),
        }));
        layers.unknown.push({ prim: edge });
      }
    }
  }

  // ---------------------------------------------------------------- roads
  const ROAD_STYLE = {
    unknown: { width: 1.6, alpha: 0.5, mat: () => Cesium.Material.fromType('PolylineDash', { color: C('#64748b', 0.5), gapColor: Cesium.Color.TRANSPARENT, dashLength: 10 }) },
    none: { width: 2, alpha: 0.75, mat: () => Cesium.Material.fromType('Color', { color: C('#7c8aa0', 0.75) }) },
    possible: { width: 3, alpha: 0.95, mat: () => Cesium.Material.fromType('PolylineDash', { color: C(COLORS.amber, 0.95), gapColor: Cesium.Color.TRANSPARENT, dashLength: 16 }) },
    bridge: { width: 3.4, alpha: 0.95, mat: () => Cesium.Material.fromType('PolylineDash', { color: C(COLORS.amber, 0.95), gapColor: C('#0a1220', 0.85), dashLength: 7 }) },
    likely: { width: 3.5, alpha: 0.9, mat: () => Cesium.Material.fromType('Color', { color: C(COLORS.cyan, 0.9) }) },
  };
  function addRoads(fc) {
    const groups = {};
    for (const f of fc.features) (groups[roadTier(f.properties)] ||= []).push(f);
    for (const tier of ['unknown', 'none', 'possible', 'bridge', 'likely']) {
      const feats = groups[tier];
      if (!feats || !feats.length) continue;
      const style = ROAD_STYLE[tier];
      const mat = style.mat();
      const prim = scene.primitives.add(new Cesium.Primitive({
        asynchronous: true,
        geometryInstances: feats.map((f) => new Cesium.GeometryInstance({
          geometry: new Cesium.PolylineGeometry({
            positions: Cesium.Cartesian3.fromDegreesArrayHeights(f.geometry.coordinates.flatMap(([x, y]) => [x, y, ROAD_H])),
            width: style.width, vertexFormat: Cesium.PolylineMaterialAppearance.VERTEX_FORMAT, arcType: Cesium.ArcType.NONE }),
          id: { kind: 'road', props: f.properties, feature: f, tier },
        })),
        appearance: new Cesium.PolylineMaterialAppearance({ material: mat }),
      }));
      layers.roads.push({ prim, mat, key: 'color', alpha: style.alpha });
    }
  }

  // ---------------------------------------------------------------- evidence markers
  const LABEL_SCALE = new Cesium.NearFarScalar(350, 1.0, 9000, 0.55);
  function addPin(f, { delay = 0, pulse = false } = {}) {
    const p = f.properties;
    const id = pinId(p);
    if (pins.has(id)) return;
    const [lon, lat] = f.geometry.coordinates;
    const tier = pinTier(p);
    const color = C(TIER_COLOR[tier]);
    const usgs = isUsgs(p);
    const depth = p.depth_m_low === null || p.depth_m_low === undefined ? null : Number(p.depth_m_low);
    const info = { kind: 'pin', id, feature: f, tier };
    let grow = 0;
    const base = Cesium.Cartesian3.fromDegrees(lon, lat, 0.2);
    // Neighbouring markers get taller poles so their labels stack instead of overlapping.
    const near = [...pins.values()].filter((g) => Cesium.Cartesian3.distance(g.base, base) < 200).length;
    const stalkM = STALK_M + 10 * near;
    const top = (k) => Cesium.Cartesian3.fromDegrees(lon, lat, 0.2 + stalkM * k);

    const ring = viewer.entities.add({
      position: base,
      ellipse: { semiMajorAxis: 8, semiMinorAxis: 8, height: 0.25, material: color.withAlpha(usgs ? 0.55 : 0.18),
        outline: true, outlineColor: color.withAlpha(0.95), outlineWidth: 2 },
    });
    const stalk = viewer.entities.add({
      polyline: { positions: new Cesium.CallbackProperty(() => [base, top(grow)], false), width: 2,
        material: color.withAlpha(0.9),
        arcType: Cesium.ArcType.NONE },
    });
    // The real peak water height on the pole, so the marker can be read against the houses.
    const waterline = depth === null ? null : viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat, depth),
      point: { pixelSize: 7, color: C(COLORS.cyan), outlineColor: C('#ffffff'), outlineWidth: 1.5 },
    });
    const head = depth === null ? '? m' : `${depth.toFixed(2)} m`;
    const sub = usgs ? 'USGS · OBSERVED' : { confirmed: 'AI · CONFIRMED', rejected: 'AI · REJECTED' }[tier] || 'AI · AWAITING REVIEW';
    const label = viewer.entities.add({
      position: top(1), show: false,
      label: { text: head, font: '600 15px Inter, system-ui, sans-serif', fillColor: C('#f8fafc'),
        showBackground: true, backgroundColor: C('#060c18', 0.86), backgroundPadding: new Cesium.Cartesian2(9, 6),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -22),
        scaleByDistance: LABEL_SCALE, pixelOffsetScaleByDistance: LABEL_SCALE,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2800),
        disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
    const subLabel = viewer.entities.add({
      position: top(1), show: false,
      label: { text: sub, font: '700 10px Inter, system-ui, sans-serif', fillColor: color,
        showBackground: true, backgroundColor: C('#060c18', 0.86), backgroundPadding: new Cesium.Cartesian2(7, 4),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -2),
        scaleByDistance: LABEL_SCALE, pixelOffsetScaleByDistance: LABEL_SCALE,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2200), // declutter the overview
        disableDepthTestDistance: Number.POSITIVE_INFINITY },
    });
    const ents = [ring, stalk, label, subLabel, waterline].filter(Boolean);
    for (const e of ents) { e.cc = info; e.show = e === label || e === subLabel ? false : true; }
    pins.set(id, { feature: f, tier, color, ents, ring, label, subLabel, base });
    layers.evidence.push(...ents.map((entity) => ({ entity })));

    setTimeout(() => {
      tween(700, (k) => { grow = k; }, () => { label.show = subLabel.show = layerOn.evidence; });
      if (pulse) pulseRing(lon, lat, color);
    }, reduceMotion() ? 0 : delay);
  }

  // A single expanding ring when a new observation lands. Restrained: one pulse, then gone.
  function pulseRing(lon, lat, color) {
    if (reduceMotion()) return;
    let k = 0;
    const ent = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat, 0.3),
      ellipse: {
        semiMajorAxis: new Cesium.CallbackProperty(() => 8 + 70 * k, false),
        semiMinorAxis: new Cesium.CallbackProperty(() => 8 + 70 * k, false),
        height: 0.3,
        material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => color.withAlpha(0.45 * (1 - k)), false)),
      },
    });
    tween(1600, (t) => { k = t; }, () => viewer.entities.remove(ent));
  }

  function setPinSelected(id, on) {
    const g = pins.get(id);
    if (!g) return;
    g.label.label.backgroundColor = on ? g.color.withAlpha(0.9) : C('#060c18', 0.86);
    g.label.label.fillColor = on ? C('#04121a') : C('#f8fafc');
    g.ring.ellipse.semiMajorAxis = g.ring.ellipse.semiMinorAxis = on ? 13 : 8;
  }

  // ---------------------------------------------------------------- highlight overlays
  function lineEntity(coords, color, width, glow = true) {
    return viewer.entities.add({ polyline: {
      positions: mode === 'photorealistic'
        ? Cesium.Cartesian3.fromDegreesArray(coords.flat())
        : Cesium.Cartesian3.fromDegreesArrayHeights(coords.flatMap(([x, y]) => [x, y, ROAD_H + 0.3])),
      width, arcType: Cesium.ArcType.NONE, clampToGround: mode === 'photorealistic',
      material: glow ? new Cesium.PolylineGlowMaterialProperty({ color, glowPower: 0.35, taperPower: 1 }) : color,
    } });
  }
  function outline(sel) {
    if (!sel) return null;
    if (sel.kind === 'road') return lineEntity(sel.feature.geometry.coordinates, C('#ffffff', 0.55), 14);
    if (sel.kind === 'water') return lineEntity(sel.feature.geometry.coordinates[0], C('#ffffff', 0.8), 3, false);
    return null;
  }
  function setHover(info) {
    if (hoverEnt) { viewer.entities.remove(hoverEnt); hoverEnt = null; }
    if (info && info.kind === 'road' && !(selected && selected.kind === 'road' && selected.feature === info.feature)) {
      hoverEnt = lineEntity(info.feature.geometry.coordinates, C('#ffffff', 0.28), 12);
    }
  }
  function select(info) {
    if (selected && selected.kind === 'pin') setPinSelected(selected.id, false);
    if (selectEnt) { viewer.entities.remove(selectEnt); selectEnt = null; }
    selected = info;
    if (!info) return;
    if (info.kind === 'pin') setPinSelected(info.id, true);
    else selectEnt = outline(info);
  }

  function setClosure(feature, on) {
    const id = feature.properties.osm_id;
    if (!on) { (closures.get(id) || []).forEach((e) => viewer.entities.remove(e)); closures.delete(id); return; }
    if (closures.has(id)) return;
    const coords = feature.geometry.coordinates;
    const line = viewer.entities.add({ polyline: {
      positions: Cesium.Cartesian3.fromDegreesArrayHeights(coords.flatMap(([x, y]) => [x, y, ROAD_H + 0.4])),
      width: 7, arcType: Cesium.ArcType.NONE,
      material: new Cesium.PolylineDashMaterialProperty({ color: C(COLORS.red), gapColor: C('#0a1220', 0.9), dashLength: 12 }) } });
    const mid = coords[Math.floor(coords.length / 2)];
    const tag = viewer.entities.add({ position: Cesium.Cartesian3.fromDegrees(mid[0], mid[1], 6),
      label: { text: 'CLOSED (HYPOTHETICAL)', font: '700 10px Inter, system-ui, sans-serif', fillColor: C('#fff1f2'),
        showBackground: true, backgroundColor: C(COLORS.red, 0.88), backgroundPadding: new Cesium.Cartesian2(7, 4),
        disableDepthTestDistance: Number.POSITIVE_INFINITY, scaleByDistance: LABEL_SCALE } });
    line.cc = tag.cc = { kind: 'road', props: feature.properties, feature, tier: roadTier(feature.properties) };
    closures.set(id, [line, tag]);
    if (!reduceMotion()) {
      let k = 0;
      line.polyline.width = new Cesium.CallbackProperty(() => 7 + 8 * (1 - k), false);
      tween(600, (t) => { k = t; }, () => { line.polyline.width = 7; });
    }
  }

  // ---------------------------------------------------------------- layer visibility (with fades)
  const layerOn = { buildings: true, water: true, roads: true, evidence: true, unknown: true };
  function applyOperationalLayer(name, on, animate = false) {
    if (!layers[name]) return;
    for (const it of layers[name]) {
      if (it.entity) {
        const isLabel = !!it.entity.label;
        it.entity.show = on && (!isLabel || true);
      } else if (it.mat && animate) {
        const u = it.mat.uniforms[it.key];
        const from = it.prim.show ? u.alpha : 0;
        const to = on ? it.alpha : 0;
        it.prim.show = true;
        tween(450, (t) => { u.alpha = from + (to - from) * t; }, () => { if (!on) it.prim.show = false; });
      } else {
        if (it.mat) it.mat.uniforms[it.key].alpha = on ? it.alpha : 0;
        it.prim.show = on;
      }
    }
  }
  function setLayer(name, on, { animate = true } = {}) {
    layerOn[name] = on;
    if (mode === 'operational') applyOperationalLayer(name, on, animate);
    else photorealisticLayer?.setLayer(name, on);
  }

  function setMode(next, layer = photorealisticLayer) {
    if (next !== 'operational' && next !== 'photorealistic') throw new Error(`Unknown map mode: ${next}`);
    if (next === 'photorealistic' && !layer) throw new Error('Photorealistic layer is not ready');
    photorealisticLayer = layer;
    mode = next;
    const operational = mode === 'operational';
    scene.globe.show = operational;
    applyOperationalLayer('context', operational);
    for (const name of ['buildings', 'water', 'roads', 'evidence', 'unknown']) {
      applyOperationalLayer(name, operational && layerOn[name]);
      photorealisticLayer?.setLayer(name, layerOn[name]);
    }
    photorealisticLayer?.setVisible(!operational);
    for (const entities of closures.values()) for (const entity of entities) entity.show = operational;
    if (selectEnt) { viewer.entities.remove(selectEnt); selectEnt = null; }
    if (selected && selected.kind !== 'pin') selectEnt = outline(selected);
  }

  // ---------------------------------------------------------------- camera
  const dur = (s) => (reduceMotion() ? 0 : s);
  const headingDeg = () => Cesium.Math.toDegrees(viewer.camera.heading);
  function flyOverview({ duration = 2.4 } = {}) {
    viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(...CENTER, 0), 1500), {
      offset: new Cesium.HeadingPitchRange(Cesium.Math.toRadians(14), Cesium.Math.toRadians(-36), 3900),
      duration: dur(duration), easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT });
  }
  function flyToPoint(lon, lat, { range = 260, pitch = -24, duration = 2.2, height = 2 } = {}) {
    viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(lon, lat, height), 12), {
      offset: new Cesium.HeadingPitchRange(Cesium.Math.toRadians(headingDeg()), Cesium.Math.toRadians(pitch), range),
      duration: dur(duration), easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT });
  }
  function flyToFeature(info, opts) {
    if (info.kind === 'pin') { const [lon, lat] = info.feature.geometry.coordinates; flyToPoint(lon, lat, opts); return; }
    const coords = info.kind === 'water' ? info.feature.geometry.coordinates[0] : info.feature.geometry.coordinates;
    const pts = Cesium.Cartesian3.fromDegreesArray(coords.flat());
    const sphere = Cesium.BoundingSphere.fromPoints(pts);
    viewer.camera.flyToBoundingSphere(sphere, {
      offset: new Cesium.HeadingPitchRange(Cesium.Math.toRadians(headingDeg()), Cesium.Math.toRadians(-32),
        Math.max(260, sphere.radius * 3.2)),
      duration: dur(2), easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT });
  }
  function centerOnScreen() {
    const c = new Cesium.Cartesian2(scene.canvas.clientWidth / 2, scene.canvas.clientHeight / 2);
    const p = viewer.camera.pickEllipsoid(c);
    if (!p) return CENTER;
    const carto = Cesium.Cartographic.fromCartesian(p);
    return [Cesium.Math.toDegrees(carto.longitude), Cesium.Math.toDegrees(carto.latitude)];
  }
  function streetLevel() { const [lon, lat] = centerOnScreen(); flyToPoint(lon, lat, { range: 220, pitch: -16 }); }
  function topDown() {
    const [lon, lat] = centerOnScreen();
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(lon, lat, 2600),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-89.9), roll: 0 }, duration: dur(1.8),
      easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT });
  }
  function intro() {
    viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(CENTER[0] - 0.01, CENTER[1] - 0.09, 9000),
      orientation: { heading: Cesium.Math.toRadians(8), pitch: Cesium.Math.toRadians(-48), roll: 0 } });
  }

  // ---------------------------------------------------------------- picking
  const RANK = { pin: 0, road: 1, water: 2, unknown: 3 };
  const infoOf = (hit) => (hit && hit.id ? hit.id.cc || hit.id : null);
  function pickAt(pos, drill = true) {
    const hits = drill ? scene.drillPick(pos, 8, 9, 9) : [scene.pick(pos, 7, 7)];
    return hits.map(infoOf).filter((x) => x && RANK[x.kind] !== undefined)
      .sort((a, b) => RANK[a.kind] - RANK[b.kind])[0] || null;
  }
  const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  let onPick = () => {}; let onHover = () => {};
  handler.setInputAction((e) => onPick(pickAt(e.position)), Cesium.ScreenSpaceEventType.LEFT_CLICK);
  let hoverPos = null;
  handler.setInputAction((e) => { hoverPos = e.endPosition; }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
  let lastHoverKey = null;
  scene.postRender.addEventListener(() => {
    if (!hoverPos) return;
    const pos = hoverPos; hoverPos = null;
    const info = pickAt(pos, false);
    scene.canvas.style.cursor = info ? 'pointer' : '';
    const key = info ? `${info.kind}:${info.id || info.props?.osm_id || ''}` : null;
    if (key !== lastHoverKey) { lastHoverKey = key; setHover(info); onHover(info); }
  });

  return {
    viewer, addContext, addBuildings, addWater, addUnknown, addRoads, addPin, setLayer, setMode, select, setClosure, pulseRing,
    flyOverview, flyToPoint, flyToFeature, streetLevel, topDown, intro,
    // Orbit around the point at screen centre until north is up, keeping tilt and distance.
    resetNorth: () => {
      const [lon, lat] = centerOnScreen();
      const target = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
      const range = Cesium.Cartesian3.distance(viewer.camera.positionWC, target);
      viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(target, 1), {
        offset: new Cesium.HeadingPitchRange(0, viewer.camera.pitch, range), duration: dur(1),
        easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT });
    },
    hasPin: (id) => pins.has(id),
    removePin: (id) => {
      const g = pins.get(id);
      if (!g) return;
      g.ents.forEach((e) => viewer.entities.remove(e));
      layers.evidence = layers.evidence.filter((it) => !g.ents.includes(it.entity));
      pins.delete(id);
      if (selected && selected.kind === 'pin' && selected.id === id) selected = null;
    },
    pinInfo: (id) => { const g = pins.get(id); return g ? { kind: 'pin', id, feature: g.feature, tier: g.tier } : null; },
    onPick: (fn) => { onPick = fn; }, onHover: (fn) => { onHover = fn; },
    layerState: () => ({ ...layerOn }),
    mapMode: () => mode,
  };
}
