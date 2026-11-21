/* global Cesium */
// Google Photorealistic 3D Tiles plus replay overlays aligned to lidar ground samples.
// This renderer is lazy-loaded and shares the command center's data and selection contracts.

import { pinId } from './data.js';
import { pinTier, roadTier } from './scene.js';

const C = (css, alpha = 1) => Cesium.Color.fromCssColorString(css).withAlpha(alpha);
const FALLBACK_OFFSET_M = -27;
const ROAD_COLORS = {
  likely: '#0891b2', possible: '#f59e0b', bridge: '#f59e0b', none: '#64748b', unknown: '#64748b',
};
const PIN_COLORS = { observed: '#06b6d4', critical: '#e11d48', uncertain: '#f59e0b', confirmed: '#06b6d4', rejected: '#64748b' };

function hierarchy(rings) {
  const ring = (points) => Cesium.Cartesian3.fromDegreesArray(points.slice(0, -1).flat());
  return new Cesium.PolygonHierarchy(ring(rings[0]), rings.slice(1).map((points) => new Cesium.PolygonHierarchy(ring(points))));
}

async function alignToLidar(viewer, samples) {
  if (!Array.isArray(samples) || samples.length < 10) {
    return { offset: FALLBACK_OFFSET_M, how: 'approximate: ground samples unavailable' };
  }
  const points = samples.map((sample) => Cesium.Cartographic.fromDegrees(sample.lon, sample.lat));
  const sampled = await viewer.scene.sampleHeightMostDetailed(points);
  const differences = sampled
    .map((point, index) => point && Number.isFinite(point.height) ? point.height - samples[index].ground_m : null)
    .filter((value) => value !== null)
    .sort((a, b) => a - b);
  if (differences.length < 10) {
    return { offset: FALLBACK_OFFSET_M, how: `approximate: ${differences.length} of ${samples.length} alignment points matched` };
  }
  const measured = differences[Math.floor(differences.length * 0.25)];
  if (measured < -35 || measured > -18) {
    return { offset: FALLBACK_OFFSET_M, how: `approximate: measured offset ${measured.toFixed(1)} m was outside the expected range` };
  }
  return { offset: measured, how: `aligned using ${differences.length} road points` };
}

function setItemsVisible(items, visible) {
  for (const item of items) item.show = visible;
}

export async function createPhotorealisticLayer(viewer, data, token) {
  if (!token) throw new Error('Cesium ion token is missing');
  if (!data.surface?.features || !Array.isArray(data.samples)) {
    throw new Error('Photorealistic overlay data is incomplete');
  }

  Cesium.Ion.defaultAccessToken = token;
  const tiles = await Cesium.createGooglePhotorealistic3DTileset();
  viewer.scene.primitives.add(tiles);
  const alignment = await alignToLidar(viewer, data.samples);
  const { offset } = alignment;
  const groups = { water: [], roads: [], evidence: [], unknown: [] };

  const waterByStatus = new Map();
  for (const feature of data.surface.features) {
    const status = feature.properties.status;
    if (!waterByStatus.has(status)) waterByStatus.set(status, []);
    waterByStatus.get(status).push(feature);
  }
  for (const [status, features] of waterByStatus) {
    const possible = status === 'possible';
    const instances = features.map((feature) => new Cesium.GeometryInstance({
      geometry: new Cesium.PolygonGeometry({
        polygonHierarchy: hierarchy(feature.geometry.coordinates),
        height: Number(feature.properties.level_m) + offset,
        vertexFormat: Cesium.EllipsoidSurfaceAppearance.VERTEX_FORMAT,
      }),
      id: { kind: 'water', props: feature.properties, feature },
    }));
    const material = possible
      ? Cesium.Material.fromType('Color', { color: C('#f59e0b', 0.28) })
      : new Cesium.Material({ fabric: { type: 'Water', uniforms: {
        baseWaterColor: C('#0e7490', 0.72), blendColor: C('#38bdf8', 0.55),
        normalMap: Cesium.buildModuleUrl('Assets/Textures/waterNormals.jpg'),
        frequency: 1800, animationSpeed: 0.006, amplitude: 2.5, specularIntensity: 0.45,
      } } });
    const primitive = viewer.scene.primitives.add(new Cesium.Primitive({
      geometryInstances: instances,
      appearance: new Cesium.EllipsoidSurfaceAppearance({ material, aboveGround: true, translucent: true }),
      asynchronous: true,
    }));
    groups.water.push(primitive);
  }

  for (const feature of data.roads.features) {
    const properties = feature.properties;
    const tier = roadTier(properties);
    const dashed = tier === 'possible' || tier === 'bridge' || tier === 'unknown';
    const info = { kind: 'road', props: properties, feature, tier };
    const entity = viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(feature.geometry.coordinates.flat()),
        clampToGround: true,
        width: tier === 'likely' ? 4 : 2.5,
        material: dashed
          ? new Cesium.PolylineDashMaterialProperty({ color: C(ROAD_COLORS[tier], tier === 'unknown' ? 0.55 : 0.9), dashLength: tier === 'bridge' ? 8 : 16 })
          : C(ROAD_COLORS[tier], tier === 'none' ? 0.55 : 0.88),
      },
    });
    entity.cc = info;
    groups.roads.push(entity);
  }

  for (const feature of data.unknown.features) {
    for (const ring of feature.geometry.coordinates.slice(1)) {
      const entity = viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(ring.flat()),
          clampToGround: true,
          width: 3,
          material: new Cesium.PolylineDashMaterialProperty({ color: C('#f8fafc', 0.82), dashLength: 20 }),
        },
      });
      entity.cc = { kind: 'unknown', props: feature.properties };
      groups.unknown.push(entity);
    }
  }

  for (const feature of data.pins.features) {
    const properties = feature.properties;
    if (!Number.isFinite(Number(properties.ground_m))) continue;
    const [lon, lat] = feature.geometry.coordinates;
    const tier = pinTier(properties);
    const color = C(PIN_COLORS[tier]);
    const depth = Number.isFinite(Number(properties.depth_m_low)) ? Number(properties.depth_m_low) : null;
    const baseHeight = Number(properties.ground_m) + offset;
    const topHeight = baseHeight + (depth ?? 0) + 0.8;
    const info = { kind: 'pin', id: pinId(properties), feature, tier };
    const pole = viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArrayHeights([lon, lat, baseHeight, lon, lat, topHeight]),
        width: 4,
        material: new Cesium.PolylineOutlineMaterialProperty({ color, outlineColor: C('#0f172a'), outlineWidth: 1 }),
      },
    });
    const marker = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat, topHeight),
      point: { pixelSize: 11, color, outlineColor: C('#ffffff'), outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      label: {
        text: depth === null ? 'Depth unknown' : `${depth.toFixed(2)} m`,
        font: '600 14px Segoe UI, sans-serif', fillColor: C('#ffffff'),
        showBackground: true, backgroundColor: C('#0f172a', 0.88), backgroundPadding: new Cesium.Cartesian2(8, 5),
        pixelOffset: new Cesium.Cartesian2(0, -19), distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2800),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    pole.cc = marker.cc = info;
    groups.evidence.push(pole, marker);
  }

  let visible = false;
  const layerState = { buildings: true, water: true, roads: true, evidence: true, unknown: true };
  const apply = () => {
    tiles.show = visible && layerState.buildings;
    for (const name of ['water', 'roads', 'evidence', 'unknown']) {
      setItemsVisible(groups[name], visible && layerState[name]);
    }
  };
  const setVisible = (next) => { visible = next; apply(); };
  const setLayer = (name, next) => { layerState[name] = next; apply(); };
  setVisible(false);

  return { tiles, alignment, setVisible, setLayer };
}
