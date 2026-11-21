/* global Cesium */
// Terrain-aware flood surface for the 3D views (written by `python -m flood.inundation`).
// web/data/flood3d.json (header) + flood3d.bin: int16 ground cm, int16 water-surface cm, uint8 class,
// on a ~6 m grid, heights in metres NAVD88. Row 0 is north. See docs/inundation.md.

export const CLS = { NODATA: 0, DRY: 1, PROFILE: 2, SHORELINE: 3, UNRESOLVED: 4 };
export const CLASS_LABEL = {
  1: 'Not in the mapped extent (not verified)',
  2: 'Estimated depth · measured reach',
  3: 'Estimated depth · lower confidence',
  4: 'Mapped flooded · depth not resolved',
};

export async function loadFlood3d() {
  const header = await (await fetch('data/flood3d.json', { cache: 'no-store' })).json();
  const res = await fetch('data/flood3d.bin', { cache: 'no-store' });
  if (!res.ok) throw new Error(`flood3d.bin: HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  const n = header.cols * header.rows;
  if (buf.byteLength !== n * 6 && buf.byteLength !== n * 5) throw new Error('flood3d.bin size does not match its header');
  const g16 = new Int16Array(buf, 0, n);
  const w16 = new Int16Array(buf, n * 2, n);
  const cls = new Uint8Array(buf, n * 4, n);
  // level codes: 255 = dry at the peak; k = still under water and connected to Brays Bayou with the
  // peak surface lowered by k * level_step_m (absent in older files: peak only)
  const level = buf.byteLength === n * 6 ? new Uint8Array(buf, n * 5, n) : new Uint8Array(n);
  const ground = new Float32Array(n);
  const wse = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    ground[i] = g16[i] === -32768 ? NaN : g16[i] / 100;
    wse[i] = w16[i] === -32768 ? NaN : w16[i] / 100;
  }
  return makeGrid(header, ground, wse, cls, level);
}

function makeGrid(header, ground, wse, cls, level) {
  const { cols, rows } = header;
  const [a, b, c, d, e, f] = header.affine; // lon = a*col + b*row + c ; lat = d*col + e*row + f
  const det = a * e - b * d;
  const toColRow = (lon, lat) => {
    const x = lon - c, y = lat - f;
    return [(e * x - b * y) / det, (-d * x + a * y) / det];
  };
  const lonlat = (col, row) => [a * col + b * row + c, d * col + e * row + f];
  const idx = (col, row) => row * cols + col;
  const inside = (col, row) => col >= 0 && row >= 0 && col <= cols - 1 && row <= rows - 1;
  const sorted = Array.from(ground).filter(Number.isFinite).sort((p, q) => p - q);
  const baseGround = sorted[Math.floor(sorted.length / 2)] || 15;

  // Bilinear sample; falls back to the nearest valid cell when a neighbour is missing.
  function sample(arr, lon, lat) {
    const [x, y] = toColRow(lon, lat);
    if (!inside(x, y)) return null;
    const c0 = Math.floor(x), r0 = Math.floor(y);
    const c1 = Math.min(c0 + 1, cols - 1), r1 = Math.min(r0 + 1, rows - 1);
    const tx = x - c0, ty = y - r0;
    const v00 = arr[idx(c0, r0)], v10 = arr[idx(c1, r0)], v01 = arr[idx(c0, r1)], v11 = arr[idx(c1, r1)];
    if ([v00, v10, v01, v11].every(Number.isFinite)) {
      return (v00 * (1 - tx) + v10 * tx) * (1 - ty) + (v01 * (1 - tx) + v11 * tx) * ty;
    }
    const v = arr[idx(Math.round(x), Math.round(y))];
    return Number.isFinite(v) ? v : null;
  }
  const classAt = (lon, lat) => {
    const [x, y] = toColRow(lon, lat);
    return inside(x, y) ? cls[idx(Math.round(x), Math.round(y))] : CLS.NODATA;
  };
  const groundAt = (lon, lat) => sample(ground, lon, lat);
  function pointInfo(lon, lat) {
    const k = classAt(lon, lat);
    const g = groundAt(lon, lat);
    const w = k === CLS.PROFILE || k === CLS.SHORELINE ? sample(wse, lon, lat) : null;
    const depth = w !== null && g !== null ? Math.max(0, w - g) : null;
    return { cls: k, ground: g, wse: w, depth, label: CLASS_LABEL[k] || 'Outside the analysis area' };
  }
  const bounds = (() => {
    const corners = [lonlat(0, 0), lonlat(cols - 1, 0), lonlat(0, rows - 1), lonlat(cols - 1, rows - 1)];
    const lons = corners.map((p) => p[0]), lats = corners.map((p) => p[1]);
    return { west: Math.min(...lons), east: Math.max(...lons), south: Math.min(...lats), north: Math.max(...lats) };
  })();
  return { header, cols, rows, ground, wse, cls, level, lonlat, toColRow, idx, groundAt, classAt, pointInfo,
    sampleWse: (lon, lat) => sample(wse, lon, lat), baseGround, bounds };
}

// Lidar ground as Cesium terrain (stylised view). Outside the grid the height eases from the nearest
// edge value to the median ground over FEATHER_M, so the analysis box never shows as a cliff.
const FEATHER_M = 450;
export function terrainProvider(grid) {
  const tilingScheme = new Cesium.GeographicTilingScheme();
  const size = 33;
  const cellM = grid.header.cell_m || 6;
  const heightAt = (lon, lat) => {
    const g = grid.groundAt(lon, lat);
    if (g !== null) return g;
    const [x, y] = grid.toColRow(lon, lat);
    const cx = Math.min(Math.max(x, 0), grid.cols - 1), cy = Math.min(Math.max(y, 0), grid.rows - 1);
    const edge = grid.ground[grid.idx(Math.round(cx), Math.round(cy))];
    const beyond = Math.hypot(x - cx, y - cy) * cellM;
    const t = Math.min(1, beyond / FEATHER_M);
    const s = t * t * (3 - 2 * t);
    return (Number.isFinite(edge) ? edge : grid.baseGround) * (1 - s) + grid.baseGround * s;
  };
  return new Cesium.CustomHeightmapTerrainProvider({
    width: size, height: size, tilingScheme,
    credit: new Cesium.Credit('Ground: USGS 3DEP lidar', false),
    callback: (x, y, level) => {
      const rect = tilingScheme.tileXYToRectangle(x, y, level);
      const west = Cesium.Math.toDegrees(rect.west), east = Cesium.Math.toDegrees(rect.east);
      const north = Cesium.Math.toDegrees(rect.north), south = Cesium.Math.toDegrees(rect.south);
      const out = new Float32Array(size * size);
      const pad = 0.006;
      const b = grid.bounds;
      if (east < b.west - pad || west > b.east + pad || north < b.south - pad || south > b.north + pad) {
        out.fill(grid.baseGround);
        return out;
      }
      for (let j = 0; j < size; j++) {
        const lat = north - ((north - south) * j) / (size - 1);
        for (let i = 0; i < size; i++) out[j * size + i] = heightAt(west + ((east - west) * i) / (size - 1), lat);
      }
      return out;
    },
  });
}

// One continuous water surface. Each vertex carries the estimated depth there, so colour and
// transparency vary smoothly (no banded patches) and the shoreline fades out instead of ending in a
// hard polygon edge. Vertices sit on cell centres at the computed water level (+ heightOffset for
// the photorealistic ellipsoid); the surface extends one cell past the mapped shoreline so the
// terrain, not the mesh edge, draws the waterline.
// drop: metres below the measured peak (0 = the peak). Below the peak only cells that stay under water
// and connected to Brays Bayou are drawn (level codes from flood/inundation.py).
const UNRESOLVED_DEPTH = 0.18; // drawn as shallow water: mapped flooded, depth not resolved
export function buildWaterGeometry(grid, { heightOffset = 0, drop = 0 } = {}) {
  const { cols, rows, ground, wse, cls, level, idx, lonlat } = grid;
  const n = cols * rows;
  const step = grid.header.level_step_m || 0.1;
  const need = Math.round(drop / step);
  const W = new Float32Array(n).fill(NaN);
  const D = new Float32Array(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    if (drop === 0) {
      if (cls[i] === CLS.UNRESOLVED) { W[i] = ground[i] + 0.06; D[i] = UNRESOLVED_DEPTH; }
      else if (cls[i] === CLS.PROFILE || cls[i] === CLS.SHORELINE) { W[i] = wse[i]; D[i] = wse[i] - ground[i]; }
    } else if (level[i] !== 255 && level[i] >= need) {
      W[i] = wse[i] - drop; D[i] = W[i] - ground[i];
    }
  }
  // extend one cell outward; the extension's depth is (surface - its own ground), usually < 0,
  // which the shader turns into a transparent edge
  const ext = new Float32Array(W), extD = new Float32Array(D);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const i = idx(c, r);
      if (Number.isFinite(W[i])) continue;
      let sum = 0, cnt = 0;
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        const cc = c + dc, rr = r + dr;
        if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue;
        const j = idx(cc, rr);
        if (Number.isFinite(W[j]) && cls[j] !== CLS.UNRESOLVED) { sum += W[j]; cnt += 1; }
      }
      if (cnt) {
        ext[i] = sum / cnt;
        extD[i] = Number.isFinite(ground[i]) ? Math.min(0, ext[i] - ground[i]) : 0;
      }
    }
  }
  const pos = [], st = [], dep = [], ind = [];
  const map = new Int32Array(n).fill(-1);
  const vertex = (i, col, row) => {
    if (map[i] >= 0) return map[i];
    const v = dep.length;
    const [lon, lat] = lonlat(col, row);
    const p = Cesium.Cartesian3.fromDegrees(lon, lat, ext[i] + heightOffset);
    pos.push(p.x, p.y, p.z);
    st.push(col / cols, 1 - row / rows);
    dep.push(extD[i]);
    map[i] = v;
    return v;
  };
  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const i00 = idx(c, r), i10 = idx(c + 1, r), i01 = idx(c, r + 1), i11 = idx(c + 1, r + 1);
      if (!(Number.isFinite(ext[i00]) && Number.isFinite(ext[i10]) && Number.isFinite(ext[i01]) && Number.isFinite(ext[i11]))) continue;
      const a = vertex(i00, c, r), b = vertex(i10, c + 1, r), d = vertex(i01, c, r + 1), e = vertex(i11, c + 1, r + 1);
      ind.push(a, d, b, b, d, e);
    }
  }
  if (!ind.length) return null;
  const positions = new Float64Array(pos);
  return new Cesium.Geometry({
    attributes: {
      position: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.DOUBLE, componentsPerAttribute: 3, values: positions }),
      st: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.FLOAT, componentsPerAttribute: 2, values: new Float32Array(st) }),
      waterDepth: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.FLOAT, componentsPerAttribute: 1, values: new Float32Array(dep) }),
    },
    indices: new Uint32Array(ind),
    primitiveType: Cesium.PrimitiveType.TRIANGLES,
    boundingSphere: Cesium.BoundingSphere.fromVertices(positions),
  });
}

// Water appearance: Cesium's Water material supplies the animated normal map and specular; this shader
// sets colour and opacity from the per-vertex depth, calms the ripples with distance (no shimmer in the
// overview) and adds a grazing-angle sheen so the surface reads as water, not paint.
const WATER_VS = `
in vec3 position3DHigh;
in vec3 position3DLow;
in vec2 st;
in float waterDepth;
in float batchId;
out vec3 v_positionMC;
out vec3 v_positionEC;
out vec2 v_st;
out float v_depth;
void main() {
  vec4 p = czm_computePosition();
  v_positionMC = position3DHigh + position3DLow;
  v_positionEC = (czm_modelViewRelativeToEye * p).xyz;
  v_st = st;
  v_depth = waterDepth;
  gl_Position = czm_modelViewProjectionRelativeToEye * p;
}`;
const waterFS = (pal) => `
in vec3 v_positionMC;
in vec3 v_positionEC;
in vec2 v_st;
in float v_depth;
void main() {
  vec3 positionToEyeEC = -v_positionEC;
  vec3 normalEC = normalize(czm_normal3D * czm_geodeticSurfaceNormal(v_positionMC, vec3(0.0), vec3(1.0)));
  czm_materialInput materialInput;
  materialInput.s = v_st.s;
  materialInput.st = v_st;
  materialInput.str = vec3(v_st, 0.0);
  materialInput.normalEC = normalEC;
  materialInput.tangentToEyeMatrix = czm_eastNorthUpToEyeCoordinates(v_positionMC, normalEC);
  materialInput.positionToEyeEC = positionToEyeEC;
  czm_material material = czm_getMaterial(materialInput);
  float dist = length(v_positionEC);
  material.normal = normalize(mix(material.normal, normalEC, smoothstep(350.0, 2200.0, dist)));
  float t = smoothstep(0.0, 2.2, v_depth);
  material.diffuse = mix(vec3(${pal.shallow}), vec3(${pal.deep}), t);
  float edge = smoothstep(-0.03, 0.28, v_depth);
  vec3 toEye = normalize(positionToEyeEC);
  float fres = pow(1.0 - clamp(dot(toEye, material.normal), 0.0, 1.0), 4.0);
  material.diffuse = mix(material.diffuse, vec3(${pal.sky}), fres * 0.55);
  material.alpha = edge * clamp(mix(${pal.alphaShallow}, ${pal.alphaDeep}, t) + fres * 0.25, 0.0, 0.95);
  out_FragColor = czm_phong(toEye, material, czm_lightDirectionEC);
}`;
const PALETTES = {
  // dark analysis view: teal shallows to deep navy
  analysis: { shallow: '0.22, 0.66, 0.76', deep: '0.04, 0.20, 0.40', sky: '0.55, 0.72, 0.86', alphaShallow: '0.40', alphaDeep: '0.86' },
  // photorealistic city: slightly brighter, so it reads against roofs and trees
  photo: { shallow: '0.30, 0.70, 0.82', deep: '0.07, 0.29, 0.52', sky: '0.70, 0.82, 0.92', alphaShallow: '0.48', alphaDeep: '0.88' },
};
function waterAppearance(palette) {
  const material = new Cesium.Material({ fabric: { type: 'Water', uniforms: {
    baseWaterColor: new Cesium.Color(0.1, 0.3, 0.5, 1.0), blendColor: new Cesium.Color(0.1, 0.3, 0.5, 1.0),
    normalMap: Cesium.buildModuleUrl('Assets/Textures/waterNormals.jpg'),
    frequency: 650.0, animationSpeed: 0.004, amplitude: 1.6, specularIntensity: 0.55,
  } } });
  return new Cesium.Appearance({
    material, translucent: true, closed: false,
    vertexShaderSource: WATER_VS, fragmentShaderSource: waterFS(PALETTES[palette] || PALETTES.analysis),
    renderState: Cesium.Appearance.getDefaultRenderState(true, false),
  });
}

// Road depth along a polyline from the grid (max over vertices and midpoints).
export function roadDepth(grid, coords) {
  let maxDepth = null, flooded = false, inExtent = false, unresolved = false, sampled = false;
  const pts = [];
  for (let k = 0; k < coords.length; k++) {
    pts.push(coords[k]);
    if (k + 1 < coords.length) pts.push([(coords[k][0] + coords[k + 1][0]) / 2, (coords[k][1] + coords[k + 1][1]) / 2]);
  }
  for (const [lon, lat] of pts) {
    const info = grid.pointInfo(lon, lat);
    if (info.cls === CLS.NODATA) continue;
    sampled = true;
    if (info.cls >= CLS.PROFILE) inExtent = true;
    if (info.cls === CLS.UNRESOLVED) unresolved = true;
    if (info.depth !== null && info.depth > 0.05) {
      flooded = true;
      maxDepth = Math.max(maxDepth ?? 0, info.depth);
    }
  }
  return { sampled, flooded, inExtent, unresolved, maxDepth };
}

// Cached water surfaces per level below the peak. Built lazily (only while visible), swapped instantly.
// Has a `show` property so it can sit in the scene's layer lists like a primitive.
export function createWaterLevels(viewer, grid, { heightOffset = 0, palette = 'analysis' } = {}) {
  const cache = new Map();
  let current = 0;
  let visible = true;
  const build = (drop) => {
    const geometry = buildWaterGeometry(grid, { heightOffset, drop });
    const prims = geometry ? [viewer.scene.primitives.add(new Cesium.Primitive({
      asynchronous: false, show: false, compressVertices: false,
      geometryInstances: new Cesium.GeometryInstance({ geometry, id: { kind: 'water', drop } }),
      appearance: waterAppearance(palette),
    }))] : [];
    cache.set(drop, prims);
    return prims;
  };
  const apply = () => { for (const [d, prims] of cache) for (const p of prims) p.show = visible && d === current; };
  const api = {
    setDrop(drop) {
      current = Math.max(0, Math.round(drop * 100) / 100);
      if (visible && !cache.has(current)) build(current);
      apply();
    },
    get drop() { return current; },
    get show() { return visible; },
    set show(v) { visible = !!v; if (visible && !cache.has(current)) build(current); apply(); },
    // Warm the cache during idle time so the slider and play button stay smooth.
    prebuild(drops) {
      const queue = drops.filter((d) => !cache.has(d));
      const next = () => {
        const d = queue.shift();
        if (d === undefined) return;
        if (!cache.has(d)) build(d);
        apply();
        (window.requestIdleCallback || ((f) => setTimeout(f, 60)))(next);
      };
      next();
    },
    cellsAt(drop) {
      const need = Math.round(drop / (grid.header.level_step_m || 0.1));
      let k = 0;
      for (let i = 0; i < grid.level.length; i++) if (grid.level[i] !== 255 && grid.level[i] >= need) k += 1;
      return k;
    },
  };
  api.setDrop(0);
  return api;
}
