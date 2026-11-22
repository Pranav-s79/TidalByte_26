// Adaptive render quality: lighter while the camera moves, full quality once it stops.
//
// While the camera moves (drag, scroll, fly-to, the guided demo orbit):
//   - render at CSS-pixel density instead of the screen's (a quarter of the pixels on a Retina screen;
//     no change on a 1x screen or projector),
//   - hard instead of soft shadows.
// 3D Tiles detail is NOT lowered: coarser photorealistic tiles are less accurate in height and poke
// through the flood surface (patchy water in the guided demo orbit), so the geometry stays as set.
// Cesium raises camera.moveEnd once the camera has been still for 0.5 s; the saved settings then come
// back, so the stationary look is exactly the one set in scene.js and photorealistic.js.
//
// URL flags: ?fps shows Cesium's frame counter (and exposes window.cesiumViewer for measuring);
//            ?adaptive=0 turns this off, to compare against the original settings.

export function setupAdaptiveQuality(viewer) {
  const params = new URLSearchParams(window.location.search);
  const scene = viewer.scene;
  if (params.has('fps')) {
    scene.debugShowFramesPerSecond = true;
    window.cesiumViewer = viewer;
  }
  const state = { enabled: params.get('adaptive') !== '0', moving: false, saved: null };
  window.adaptiveQuality = state;
  if (!state.enabled) return state;

  function lighten() {
    if (state.moving) return;
    state.moving = true;
    state.saved = {
      resolution: viewer.resolutionScale,
      soft: scene.shadowMap.softShadows,
    };
    viewer.resolutionScale = Math.min(viewer.resolutionScale, 1 / (window.devicePixelRatio || 1));
    scene.shadowMap.softShadows = false;
  }

  function restore() {
    if (!state.moving) return;
    const s = state.saved;
    state.moving = false;
    state.saved = null;
    viewer.resolutionScale = s.resolution;
    scene.shadowMap.softShadows = s.soft;
    scene.requestRender();
  }

  scene.camera.moveStart.addEventListener(lighten);
  scene.camera.moveEnd.addEventListener(restore);
  return state;
}
