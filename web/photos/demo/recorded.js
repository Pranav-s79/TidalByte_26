// Written by python -m flood.photo_demo --record: real PyTorch detector and Nemotron output.
const referenceHeights = [
 {
  "name": "passenger car or small SUV tire, top of tire",
  "height_m_low": 0.6,
  "height_m_high": 0.72,
  "source": "Computed from tire size markings: overall diameter = rim + 2 x width x aspect ratio. 185/60R15 = 0.603 m, 195/65R15 = 0.635 m, 225/65R17 = 0.724 m. Check: https://tirewheelguide.com/calculator/195-65-15/"
 },
 {
  "name": "passenger car or small SUV wheel, center of hub",
  "height_m_low": 0.3,
  "height_m_high": 0.36,
  "source": "Half the tire diameters above (the hub sits at the wheel's center)."
 },
 {
  "name": "street curb, top of curb face",
  "height_m_low": 0.1,
  "height_m_high": 0.15,
  "source": "Iowa DOT Design Manual 3C-2: 4 in sloped, 6 in sloped and 6 in standard curbs. https://iowadot.gov/design-manual/chapter-3-cross-sections/3c-2-curbs . Houston curbs not yet checked."
 },
 {
  "name": "standing adult, middle of kneecap",
  "height_m_low": 0.41,
  "height_m_high": 0.54,
  "source": "ANSUR II public data, knee height (midpatella), barefoot: 5th percentile women 408 mm to 95th percentile men 536 mm (1,986 women, 4,082 men). Computed by us from https://www.openlab.psu.edu/ansur2/ . Shoes add a few cm."
 }
];
const recordedRuns = [
 {
  "file": "piney-point-2017-08-27.jpg",
  "title": "Buffalo Bayou at Piney Point",
  "taken": "Aug 27, 2017, 10:45 CDT",
  "lat": 29.749967,
  "lon": -95.523117,
  "credit": "USGS \u00b7 public domain",
  "url": "https://www.usgs.gov/media/images/hurricane-harvey-flooding-buffalo-bayou-piney-point",
  "water_visible": true,
  "reference_object": "passenger car or small SUV tire, top of tire",
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "medium",
  "reasoning": "The street is covered in flood water. The waterline on the detected car appears to sit about one-third of the way up from the ground to the top of the tire.",
  "status": "needs_review",
  "error": "3 reads disagree: 0.18-0.29 m, 0.24-0.43 m, 0.42-0.68 m",
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.3,
    "fraction_high": 0.4,
    "depth_m_low": 0.18,
    "depth_m_high": 0.29,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The street is covered in flood water. The waterline on the detected car appears to sit about one-third of the way up from the ground to the top of the tire.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.4,
    "fraction_high": 0.6,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The street is completely covered in floodwater. The waterline reaches approximately halfway up the tires of the distant car with flashing lights.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.7,
    "fraction_high": 0.95,
    "depth_m_low": 0.42,
    "depth_m_high": 0.68,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water covers the entire street surface. The waterline on the detected car reaches up to approximately the top of the tires.",
    "status": "ai_proposed",
    "error": null
   }
  ],
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
   ],
   "crops": [
    {
     "src": "demo/piney-point-2017-08-27/00-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/piney-point-2017-08-27-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:03:11+00:00",
  "elapsed_s": 97.0
 },
 {
  "file": "barker-reservoir-2017-08-29.jpg",
  "title": "Streamgage at Barker Reservoir",
  "taken": "Aug 29, 2017, 11:01 (camera clock)",
  "lat": 29.769803,
  "lon": -95.646583,
  "credit": "USGS \u00b7 public domain",
  "url": "https://www.usgs.gov/media/images/servicing-a-streamgage-barker-reservoir-following-hurricane-harvey",
  "water_visible": true,
  "reference_object": "standing adult, middle of kneecap",
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "medium",
  "reasoning": "Flood water covers the street. The water level is above the person's knees, exceeding the height of the available reference points in the table.",
  "status": "needs_review",
  "error": "3 reads disagree: water, no depth, 0.33-0.54 m, water, no depth",
  "readings": [
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the street. The water level is above the person's knees, exceeding the height of the available reference points in the table.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "standing adult, middle of kneecap",
    "fraction_low": 0.8,
    "fraction_high": 1.0,
    "depth_m_low": 0.33,
    "depth_m_high": 0.54,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water covers the street surface. The waterline on the standing person is near the kneecap level.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the street. The water level is above the person's knees, reaching mid-thigh. No reference object from the table is touched by the waterline.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "person",
     "score": 1.0,
     "box": [
      474,
      754,
      651,
      1116
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/barker-reservoir-2017-08-29/00-person.jpg",
     "label": "person"
    }
   ]
  },
  "boxes": "demo/barker-reservoir-2017-08-29-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:03:50+00:00",
  "elapsed_s": 39.3
 },
 {
  "file": "huntsville-sign-2017-08-28.jpg",
  "title": "Road sign near Huntsville",
  "taken": "Aug 28, 2017",
  "lat": null,
  "lon": null,
  "credit": "USGS, Mackenzie K. Mullins \u00b7 public domain",
  "url": "https://www.usgs.gov/media/images/hurricane-harvey-flooding-along-san-jacinto-river-1",
  "water_visible": true,
  "reference_object": null,
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "high",
  "reasoning": "The street is completely submerged under brown floodwater. A yellow sign is visible in the distance, but no reference objects from the table such as vehicles, curbs, or people are present to measure the waterline against.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "The street is completely submerged under brown floodwater. A yellow sign is visible in the distance, but no reference objects from the table such as vehicles, curbs, or people are present to measure the waterline against.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the street surface. No reference objects from the table such as tires, curbs, or adults are visible in the frame.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the entire street surface. No reference objects from the table, such as tires, curbs, or people, are visible or touched by the waterline to estimate depth.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [],
   "crops": []
  },
  "boxes": "demo/huntsville-sign-2017-08-28-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:04:06+00:00",
  "elapsed_s": 15.7
 },
 {
  "file": "houston-aerial-2017-08.jpg",
  "title": "Houston neighborhood from the air",
  "taken": "Aug 2017 (day not stated)",
  "lat": null,
  "lon": null,
  "credit": "USGS \u00b7 public domain",
  "url": "https://www.usgs.gov/media/images/houston-harvey-flood",
  "water_visible": true,
  "reference_object": "passenger car or small SUV tire, top of tire",
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [
   {
    "type": "stalled_vehicle",
    "note": "Multiple cars surrounded by floodwater on streets and driveways"
   }
  ],
  "confidence": "medium",
  "reasoning": "Flood water covers the street and surrounds vehicle tires. The waterline sits on the tires of the visible cars, roughly one-third to halfway up the tire height.",
  "status": "needs_review",
  "error": "3 reads disagree: 0.18-0.36 m, water, no depth, 0.48-0.72 m",
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.3,
    "fraction_high": 0.5,
    "depth_m_low": 0.18,
    "depth_m_high": 0.36,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water covers the street and surrounds vehicle tires. The waterline sits on the tires of the visible cars, roughly one-third to halfway up the tire height.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "Multiple cars surrounded by floodwater on streets and driveways"
     }
    ],
    "confidence": "medium",
    "reasoning": "Floodwater covers the residential street, submerging curbs and reaching the tires of parked cars. The waterline appears to be above the reference points listed in the table, such as the curb and wheel hub.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.8,
    "fraction_high": 1.0,
    "depth_m_low": 0.48,
    "depth_m_high": 0.72,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the streets and driveways in the aerial view. The waterline reaches the top of the tires on the parked passenger cars visible in the driveways.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "car",
     "score": 0.92,
     "box": [
      973,
      394,
      999,
      439
     ]
    },
    {
     "label": "car",
     "score": 0.82,
     "box": [
      1125,
      624,
      1162,
      672
     ]
    },
    {
     "label": "car",
     "score": 0.71,
     "box": [
      479,
      0,
      516,
      30
     ]
    },
    {
     "label": "bus",
     "score": 0.68,
     "box": [
      415,
      6,
      478,
      67
     ]
    },
    {
     "label": "truck",
     "score": 0.65,
     "box": [
      34,
      402,
      58,
      446
     ]
    },
    {
     "label": "car",
     "score": 0.6,
     "box": [
      939,
      366,
      1008,
      396
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/houston-aerial-2017-08/03-bus.jpg",
     "label": "bus"
    },
    {
     "src": "demo/houston-aerial-2017-08/05-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/houston-aerial-2017-08-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:05:48+00:00",
  "elapsed_s": 102.6
 },
 {
  "file": "refs/22840.jpg",
  "title": "Dry street near Brays Bayou (control)",
  "taken": "May 16, 2015",
  "lat": 29.69189,
  "lon": -95.442757,
  "credit": "Mapillary \u00b7 CC BY-SA 4.0",
  "url": "https://www.mapillary.com/app/?pKey=303316301368352",
  "water_visible": true,
  "reference_object": null,
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "low",
  "reasoning": "The street surface appears wet and reflective, indicating water presence, but the waterline does not clearly touch the detected car or a visible curb top to establish a depth fraction.",
  "status": "needs_review",
  "error": "3 reads disagree: water, no depth, no water, no water",
  "readings": [
   {
    "water_visible": true,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "low",
    "reasoning": "The street surface appears wet and reflective, indicating water presence, but the waterline does not clearly touch the detected car or a visible curb top to establish a depth fraction.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": false,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "No standing flood water is visible on the street or driveway. The pavement appears wet from rain, but no waterline touches the car tires, hubs, or curb.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": false,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "No standing flood water is visible on the street or driveway; the reference car's tires are fully visible and not touching any waterline.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "car",
     "score": 0.99,
     "box": [
      376,
      324,
      472,
      393
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/22840/00-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/22840-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:06:18+00:00",
  "elapsed_s": 29.7
 }
];
