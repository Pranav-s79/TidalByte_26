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

// Lidar ground as Cesium terrain (stylised view). Outside the grid: flat at the median ground height.
export function terrainProvider(grid) {
  const tilingScheme = new Cesium.GeographicTilingScheme();
  const size = 33;
  return new Cesium.CustomHeightmapTerrainProvider({
    width: size, height: size, tilingScheme,
    credit: new Cesium.Credit('Ground: USGS 3DEP lidar', false),
    callback: (x, y, level) => {
      const rect = tilingScheme.tileXYToRectangle(x, y, level);
      const west = Cesium.Math.toDegrees(rect.west), east = Cesium.Math.toDegrees(rect.east);
      const north = Cesium.Math.toDegrees(rect.north), south = Cesium.Math.toDegrees(rect.south);
      const out = new Float32Array(size * size);
      const touches = !(east < grid.bounds.west || west > grid.bounds.east || north < grid.bounds.south || south > grid.bounds.north);
      if (!touches) { out.fill(grid.baseGround); return out; }
      for (let j = 0; j < size; j++) {
        const lat = north - ((north - south) * j) / (size - 1);
        for (let i = 0; i < size; i++) {
          const lon = west + ((east - west) * i) / (size - 1);
          const g = grid.groundAt(lon, lat);
          out[j * size + i] = g === null ? grid.baseGround : g;
        }
      }
      return out;
    },
  });
}

// Water style per bucket: measured-reach depth bands get the water ramp; lower-confidence water is a
// desaturated teal; "depth not resolved" is a faint sheen just above the ground.
// Colour shows depth only. Confidence (measured reach vs lower confidence) is shown by the reach
// outline and in the click panel, so the water itself stays continuous.
export const WATER_STYLE = [
  { key: 'b0', label: 'Estimated depth 0–0.3 m', base: '#40cde3', alpha: 0.5 },
  { key: 'b1', label: 'Estimated depth 0.3–0.6 m', base: '#22aad3', alpha: 0.58 },
  { key: 'b2', label: 'Estimated depth 0.6–1.2 m', base: '#1784c0', alpha: 0.66 },
  { key: 'b3', label: 'Estimated depth over 1.2 m', base: '#1d5aae', alpha: 0.74 },
  { key: 'sheen', label: 'Mapped flooded · depth not resolved', base: '#9cc3d6', alpha: 0.2 },
];
const bandOf = (depth) => (depth <= 0.3 ? 'b0' : depth <= 0.6 ? 'b1' : depth <= 1.2 ? 'b2' : 'b3');

// One continuous water-surface mesh per style bucket. Vertices sit on cell centres at the computed
// water-surface height (+ heightOffset for the photorealistic ellipsoid). The surface is extended one
// cell past the mapped shoreline so the terrain, not a polygon edge, draws the waterline.
// drop: metres below the measured peak (0 = the peak). Below the peak only cells that stay under water
// and connected to Brays Bayou are drawn (level codes from flood/inundation.py).
export function buildWaterGeometries(grid, { heightOffset = 0, drop = 0 } = {}) {
  const { cols, rows, ground, wse, cls, level, idx, lonlat } = grid;
  const n = cols * rows;
  const step = grid.header.level_step_m || 0.1;
  const need = Math.round(drop / step);
  const W = new Float32Array(n).fill(NaN);  // water surface used for vertices
  const K = new Uint8Array(n);              // class used for bucketing
  for (let i = 0; i < n; i++) {
    if (drop === 0) {
      K[i] = cls[i];
      if (cls[i] === CLS.UNRESOLVED) W[i] = ground[i] + 0.06; // sheen just above ground
      else if (cls[i] === CLS.PROFILE || cls[i] === CLS.SHORELINE) W[i] = wse[i];
    } else if (level[i] !== 255 && level[i] >= need) {
      K[i] = cls[i];
      W[i] = wse[i] - drop;
    }
  }
  // extend one cell outward
  const ext = new Float32Array(W);
  const extK = new Uint8Array(K);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const i = idx(c, r);
      if (Number.isFinite(W[i])) continue;
      let sum = 0, cnt = 0, kk = 0;
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        const cc = c + dc, rr = r + dr;
        if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue;
        const j = idx(cc, rr);
        if (Number.isFinite(W[j]) && K[j] !== CLS.UNRESOLVED) { sum += W[j]; cnt += 1; kk = K[j]; }
      }
      if (cnt) { ext[i] = sum / cnt; extK[i] = kk; }
    }
  }
  const buckets = new Map(WATER_STYLE.map((s) => [s.key, { pos: [], st: [], ind: [], map: new Map() }]));
  const vertex = (bk, i, col, row) => {
    let v = bk.map.get(i);
    if (v !== undefined) return v;
    v = bk.pos.length / 3;
    const [lon, lat] = lonlat(col, row);
    const p = Cesium.Cartesian3.fromDegrees(lon, lat, ext[i] + heightOffset);
    bk.pos.push(p.x, p.y, p.z);
    bk.st.push(col / cols, 1 - row / rows);
    bk.map.set(i, v);
    return v;
  };
  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const i00 = idx(c, r), i10 = idx(c + 1, r), i01 = idx(c, r + 1), i11 = idx(c + 1, r + 1);
      if (!(Number.isFinite(ext[i00]) && Number.isFinite(ext[i10]) && Number.isFinite(ext[i01]) && Number.isFinite(ext[i11]))) continue;
      const ks = [extK[i00], extK[i10], extK[i01], extK[i11]];
      let key;
      if (ks.every((k) => k === CLS.UNRESOLVED)) key = 'sheen';
      else {
        const g = (ground[i00] + ground[i10] + ground[i01] + ground[i11]) / 4;
        const w = (ext[i00] + ext[i10] + ext[i01] + ext[i11]) / 4;
        key = bandOf(Math.max(0, w - g));
      }
      const bk = buckets.get(key);
      const a = vertex(bk, i00, c, r), b = vertex(bk, i10, c + 1, r), d = vertex(bk, i01, c, r + 1), e = vertex(bk, i11, c + 1, r + 1);
      bk.ind.push(a, d, b, b, d, e);
    }
  }
  const out = [];
  for (const style of WATER_STYLE) {
    const bk = buckets.get(style.key);
    if (!bk.ind.length) continue;
    const positions = new Float64Array(bk.pos);
    out.push({ style, triangles: bk.ind.length / 3, geometry: new Cesium.Geometry({
      attributes: {
        position: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.DOUBLE, componentsPerAttribute: 3, values: positions }),
        st: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.FLOAT, componentsPerAttribute: 2, values: new Float32Array(bk.st) }),
      },
      indices: new Uint32Array(bk.ind),
      primitiveType: Cesium.PrimitiveType.TRIANGLES,
      boundingSphere: Cesium.BoundingSphere.fromVertices(positions),
    }) });
  }
  return out;
}

export function waterMaterial(style) {
  const base = Cesium.Color.fromCssColorString(style.base);
  if (style.key === 'sheen') return Cesium.Material.fromType('Color', { color: base.withAlpha(style.alpha) });
  return new Cesium.Material({ fabric: { type: 'Water', uniforms: {
    baseWaterColor: base.withAlpha(style.alpha),
    blendColor: Cesium.Color.fromCssColorString('#7dd3fc').withAlpha(style.alpha * 0.55),
    normalMap: Cesium.buildModuleUrl('Assets/Textures/waterNormals.jpg'),
    frequency: 1400.0, animationSpeed: 0.006, amplitude: 2.2, specularIntensity: 0.55,
  } } });
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
export function createWaterLevels(viewer, grid, { heightOffset = 0 } = {}) {
  const cache = new Map();
  let current = 0;
  let visible = true;
  const build = (drop) => {
    const prims = buildWaterGeometries(grid, { heightOffset, drop }).map(({ style, geometry }) => viewer.scene.primitives.add(
      new Cesium.Primitive({
        asynchronous: false, show: false,
        geometryInstances: new Cesium.GeometryInstance({ geometry, id: { kind: 'water', style: style.key, drop } }),
        appearance: new Cesium.EllipsoidSurfaceAppearance({ material: waterMaterial(style), aboveGround: true, translucent: true }),
      })));
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
