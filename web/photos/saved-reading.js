// Recorded server response for the offline photo demo.
const recordedReading = {
  "id": "obs-69f57e76cb",
  "lat": 29.749967,
  "lon": -95.523117,
  "taken_at": "2017-08-27T15:45:33Z",
  "photo": "piney-point-2017-08-27.jpg",
  "water_visible": true,
  "reference_object": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "low",
  "reasoning": "Flood water covers the entire road surface. The detected car is too distant and blurry to confirm the waterline touching the tire top or hub center required for depth estimation. No curb or standing adult is visible to use as a reference.",
  "status": "ai_proposed",
  "error": null,
  "detector": {
    "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
    "objects": [
      {
        "label": "car",
        "score": 0.98,
        "box": [
          367,
          405,
          452,
          458
        ]
      }
    ]
  },
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T19:37:58+00:00",
  "elapsed_s": 16.8
};
