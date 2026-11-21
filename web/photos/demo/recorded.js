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
  "file": "houston-lot-2017-08-27-a.jpg",
  "title": "Cars in a flooded parking lot",
  "taken": "Aug 27, 2017, 08:09 (camera clock)",
  "lat": null,
  "lon": null,
  "credit": "R. Crap Mariner \u00b7 CC BY 2.0 \u00b7 resized",
  "url": "https://commons.wikimedia.org/wiki/File:Hurricane-Tropical_Storm_Harvey_in_Houston_-_August_27_2017_AM_(36032743313).jpg",
  "water_visible": true,
  "reference_object": "passenger car or small SUV tire, top of tire / passenger car or small SUV wheel, center of hub",
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": 0.18,
  "depth_m_high": 0.43,
  "obstacles": [
   {
    "type": "stalled_vehicle",
    "note": "white SUV"
   },
   {
    "type": "stalled_vehicle",
    "note": "beige sedan"
   },
   {
    "type": "stalled_vehicle",
    "note": "multiple cars submerged in floodwater blocking the road"
   },
   {
    "type": "stalled_vehicle",
    "note": "multiple cars submerged in street"
   }
  ],
  "confidence": "high",
  "reasoning": "Flood water covers the street, submerging the lower portions of multiple parked cars. The waterline on the front tire of the white SUV sits roughly one-third to halfway up the tire height.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.3,
    "fraction_high": 0.5,
    "depth_m_low": 0.18,
    "depth_m_high": 0.36,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "white SUV"
     },
     {
      "type": "stalled_vehicle",
      "note": "beige sedan"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the street, submerging the lower portions of multiple parked cars. The waterline on the front tire of the white SUV sits roughly one-third to halfway up the tire height.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "multiple cars submerged in floodwater blocking the road"
     }
    ],
    "confidence": "high",
    "reasoning": "Floodwater covers the street and submerges the lower portions of several parked cars. The waterline on the white SUV's front tire appears to align with the center of the wheel hub.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "multiple cars submerged in street"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the street surface. The waterline on the foreground car tires aligns with the center of the wheel hubs.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "car",
     "score": 1.0,
     "box": [
      357,
      497,
      507,
      563
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      579,
      528,
      981,
      699
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      206,
      501,
      387,
      573
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      480,
      488,
      618,
      554
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      1068,
      515,
      1302,
      635
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      1215,
      507,
      1436,
      570
     ]
    },
    {
     "label": "car",
     "score": 0.97,
     "box": [
      1295,
      473,
      1432,
      510
     ]
    },
    {
     "label": "car",
     "score": 0.96,
     "box": [
      809,
      492,
      1203,
      675
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/houston-lot-2017-08-27-a/07-car.jpg",
     "label": "car"
    },
    {
     "src": "demo/houston-lot-2017-08-27-a/01-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/houston-lot-2017-08-27-a-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:33:57+00:00",
  "elapsed_s": 40.3
 },
 {
  "file": "houston-lot-2017-08-27-b.jpg",
  "title": "Same lot, same minute, another angle",
  "taken": "Aug 27, 2017, 08:09 (camera clock)",
  "lat": null,
  "lon": null,
  "credit": "R. Crap Mariner \u00b7 CC BY 2.0 \u00b7 resized",
  "url": "https://commons.wikimedia.org/wiki/File:Hurricane-Tropical_Storm_Harvey_in_Houston_-_August_27_2017_AM_(36702214741).jpg",
  "water_visible": true,
  "reference_object": "passenger car or small SUV tire, top of tire",
  "fraction_low": 1.0,
  "fraction_high": 1.5,
  "depth_m_low": 0.6,
  "depth_m_high": 1.08,
  "obstacles": [
   {
    "type": "stalled_vehicle",
    "note": "submerged cars blocking the street"
   },
   {
    "type": "stalled_vehicle",
    "note": "multiple cars submerged in floodwater"
   }
  ],
  "confidence": "high",
  "reasoning": "Flood water covers the street and submerges the lower portions of multiple cars. The waterline on the visible sedans and SUVs is above the top of the tires, reaching up the lower body panels.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 1.0,
    "fraction_high": 1.5,
    "depth_m_low": 0.6,
    "depth_m_high": 1.08,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "submerged cars blocking the street"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the street and submerges the lower portions of multiple cars. The waterline on the visible sedans and SUVs is above the top of the tires, reaching up the lower body panels.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 1.0,
    "fraction_high": 1.5,
    "depth_m_low": 0.6,
    "depth_m_high": 1.08,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "multiple cars submerged in floodwater"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the street and submerges the tires of several parked cars, with the waterline sitting at or slightly above the top of the tires.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 1.1,
    "fraction_high": 1.4,
    "depth_m_low": 0.66,
    "depth_m_high": 1.01,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "submerged cars blocking the street"
     }
    ],
    "confidence": "high",
    "reasoning": "Floodwater covers the tires and reaches the lower body panels of the parked cars. The waterline is visibly above the top of the tires on the beige sedan and white SUV.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "car",
     "score": 1.0,
     "box": [
      92,
      198,
      267,
      270
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      355,
      214,
      762,
      373
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      229,
      184,
      386,
      261
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      845,
      194,
      1053,
      306
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      993,
      188,
      1170,
      243
     ]
    },
    {
     "label": "car",
     "score": 0.99,
     "box": [
      0,
      206,
      135,
      285
     ]
    },
    {
     "label": "car",
     "score": 0.94,
     "box": [
      587,
      179,
      973,
      349
     ]
    },
    {
     "label": "car",
     "score": 0.88,
     "box": [
      1081,
      157,
      1171,
      187
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/houston-lot-2017-08-27-b/06-car.jpg",
     "label": "car"
    },
    {
     "src": "demo/houston-lot-2017-08-27-b/01-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/houston-lot-2017-08-27-b-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:34:37+00:00",
  "elapsed_s": 40.5
 },
 {
  "file": "houston-fence-2017-08-27.jpg",
  "title": "Cars behind a fence",
  "taken": "Aug 27, 2017, 08:11 (camera clock)",
  "lat": null,
  "lon": null,
  "credit": "R. Crap Mariner \u00b7 CC BY 2.0 \u00b7 resized",
  "url": "https://commons.wikimedia.org/wiki/File:Hurricane-Tropical_Storm_Harvey_in_Houston_-_August_27_2017_AM_(36032737983).jpg",
  "water_visible": true,
  "reference_object": "passenger car or small SUV wheel, center of hub",
  "fraction_low": 0.8,
  "fraction_high": 1.2,
  "depth_m_low": 0.24,
  "depth_m_high": 0.43,
  "obstacles": [
   {
    "type": "stalled_vehicle",
    "note": "black sedan"
   },
   {
    "type": "stalled_vehicle",
    "note": "sedans submerged in floodwater"
   },
   {
    "type": "stalled_vehicle",
    "note": "dark sedan"
   },
   {
    "type": "stalled_vehicle",
    "note": "green minivan"
   }
  ],
  "confidence": "high",
  "reasoning": "Floodwater covers the street and reaches the center of the wheels on the parked cars. The waterline aligns with the hub center of the black sedan on the left.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.9,
    "fraction_high": 1.1,
    "depth_m_low": 0.27,
    "depth_m_high": 0.4,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "black sedan"
     }
    ],
    "confidence": "high",
    "reasoning": "Floodwater covers the street and reaches the center of the wheels on the parked cars. The waterline aligns with the hub center of the black sedan on the left.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [
     {
      "type": "stalled_vehicle",
      "note": "sedans submerged in floodwater"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water is clearly visible covering the street and submerging the lower portions of multiple cars. The waterline sits approximately at the center of the wheel hubs on the visible sedans.",
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
      "note": "black sedan"
     },
     {
      "type": "stalled_vehicle",
      "note": "dark sedan"
     },
     {
      "type": "stalled_vehicle",
      "note": "green minivan"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the street and submerges the tires and lower bodies of multiple cars, appearing deeper than the highest reference point in the table.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2
  ],
  "note": "2 of 3 reads agree; read 3: water, no depth",
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "car",
     "score": 1.0,
     "box": [
      800,
      323,
      1361,
      527
     ]
    },
    {
     "label": "car",
     "score": 1.0,
     "box": [
      197,
      344,
      692,
      623
     ]
    },
    {
     "label": "car",
     "score": 0.99,
     "box": [
      1246,
      296,
      1600,
      488
     ]
    },
    {
     "label": "truck",
     "score": 0.77,
     "box": [
      1532,
      202,
      1569,
      241
     ]
    },
    {
     "label": "car",
     "score": 0.66,
     "box": [
      1169,
      413,
      1348,
      535
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/houston-fence-2017-08-27/01-car.jpg",
     "label": "car"
    },
    {
     "src": "demo/houston-fence-2017-08-27/00-car.jpg",
     "label": "car"
    }
   ]
  },
  "boxes": "demo/houston-fence-2017-08-27-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:35:24+00:00",
  "elapsed_s": 46.6
 },
 {
  "file": "ike-cars-2008-09-13.jpg",
  "title": "Driving through floodwater (Hurricane Ike, 2008)",
  "taken": "Sep 13, 2008",
  "lat": null,
  "lon": null,
  "credit": "FEMA, Jocelyn Augustino \u00b7 public domain",
  "url": "https://commons.wikimedia.org/wiki/File:FEMA_-_38450_-_Cars_going_through_flood_water_in_Texas.jpg",
  "water_visible": true,
  "reference_object": "passenger car or small SUV wheel, center of hub / passenger car or small SUV tire, top of tire",
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": 0.24,
  "depth_m_high": 0.43,
  "obstacles": [],
  "confidence": "medium",
  "reasoning": "Flood water covers the street surface. The waterline sits at approximately the center of the wheel hubs on the red truck and black SUV.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "Flood water covers the street surface. The waterline sits at approximately the center of the wheel hubs on the red truck and black SUV.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water covers the street, reaching approximately the center of the wheels on the red truck and black SUV as they drive through.",
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
    "reasoning": "Flood water covers the street where vehicles are driving. The waterline on the tires appears to reach approximately halfway up the tire sidewall.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [
    {
     "label": "truck",
     "score": 0.99,
     "box": [
      253,
      495,
      764,
      668
     ]
    },
    {
     "label": "car",
     "score": 0.98,
     "box": [
      790,
      533,
      1278,
      743
     ]
    },
    {
     "label": "car",
     "score": 0.94,
     "box": [
      33,
      416,
      200,
      485
     ]
    }
   ],
   "crops": [
    {
     "src": "demo/ike-cars-2008-09-13/01-car.jpg",
     "label": "car"
    },
    {
     "src": "demo/ike-cars-2008-09-13/00-truck.jpg",
     "label": "truck"
    }
   ]
  },
  "boxes": "demo/ike-cars-2008-09-13-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:36:22+00:00",
  "elapsed_s": 58.5
 },
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
  "fraction_low": 0.8,
  "fraction_high": 1.2,
  "depth_m_low": 0.48,
  "depth_m_high": 0.86,
  "obstacles": [],
  "confidence": "medium",
  "reasoning": "The street is completely covered in floodwater. The waterline reaches the tires of the distant car, aligning with the top of the tire reference point.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV wheel, center of hub",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.24,
    "depth_m_high": 0.43,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The street is covered in floodwater. The waterline on the distant car appears to reach approximately the center of the wheels or hubs.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.48,
    "depth_m_high": 0.86,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The street is completely covered in floodwater. The waterline reaches the tires of the distant car, aligning with the top of the tire reference point.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.9,
    "fraction_high": 1.1,
    "depth_m_low": 0.54,
    "depth_m_high": 0.79,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The street is completely covered in floodwater. The waterline appears to reach the top of the tires on the vehicle in the distance.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   2,
   3
  ],
  "note": "2 of 3 reads agree; read 1: 0.24-0.43 m",
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
  "analyzed_at": "2026-11-21T21:36:49+00:00",
  "elapsed_s": 26.3
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
  "fraction_low": 0.8,
  "fraction_high": 1.4,
  "depth_m_low": 0.33,
  "depth_m_high": 0.76,
  "obstacles": [],
  "confidence": "medium",
  "reasoning": "Flood water covers the street. The waterline is visible on the standing adult's legs, appearing to be at or slightly above the kneecap level.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "standing adult, middle of kneecap",
    "fraction_low": 1.0,
    "fraction_high": 1.4,
    "depth_m_low": 0.41,
    "depth_m_high": 0.76,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water covers the street. The waterline is visible on the standing adult's legs, appearing to be at or slightly above the kneecap level.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "standing adult, middle of kneecap",
    "fraction_low": 0.9,
    "fraction_high": 1.3,
    "depth_m_low": 0.37,
    "depth_m_high": 0.7,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Flood water is visible surrounding a person standing on a walkway. The waterline appears to be at or slightly above the middle of the kneecap.",
    "status": "ai_proposed",
    "error": null
   },
   {
    "water_visible": true,
    "reference_object": "standing adult, middle of kneecap",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.33,
    "depth_m_high": 0.65,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "The floodwater covers the street and reaches up to the person's legs, with the waterline appearing to sit at the middle of the kneecap.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
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
  "analyzed_at": "2026-11-21T21:37:23+00:00",
  "elapsed_s": 34.3
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
  "obstacles": [
   {
    "type": "other",
    "note": "yellow diamond road sign partially submerged"
   },
   {
    "type": "other",
    "note": "submerged road sign"
   }
  ],
  "confidence": "high",
  "reasoning": "The street is completely covered by floodwater extending to the tree line. A yellow sign is partially submerged, but no reference objects from the table (curbs, tires, people) are visible to measure the water depth against.",
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
    "obstacles": [
     {
      "type": "other",
      "note": "yellow diamond road sign partially submerged"
     }
    ],
    "confidence": "high",
    "reasoning": "The street is completely covered by floodwater extending to the tree line. A yellow sign is partially submerged, but no reference objects from the table (curbs, tires, people) are visible to measure the water depth against.",
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
    "reasoning": "The street is completely covered by flood water. A yellow sign is partially submerged, but no reference objects from the table such as curbs, tires, or people are visible to measure the water depth.",
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
      "type": "other",
      "note": "submerged road sign"
     }
    ],
    "confidence": "high",
    "reasoning": "Flood water covers the entire street surface. A yellow road sign is partially submerged, but no reference objects from the table (tires, curbs, or people) are visible to measure the waterline against.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
  "detector": {
   "model": "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)",
   "objects": [],
   "crops": []
  },
  "boxes": "demo/huntsville-sign-2017-08-28-boxes.jpg",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "analyzed_at": "2026-11-21T21:37:36+00:00",
  "elapsed_s": 13.4
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
  "reference_object": null,
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [
   {
    "type": "stalled_vehicle",
    "note": "Cars stranded in flooded streets"
   }
  ],
  "confidence": "low",
  "reasoning": "Brown floodwater covers the residential streets and yards. The aerial view does not show a clear waterline on a reference object like a tire or curb to estimate depth.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": true,
    "reference_object": "passenger car or small SUV tire, top of tire",
    "fraction_low": 0.8,
    "fraction_high": 1.2,
    "depth_m_low": 0.48,
    "depth_m_high": 0.86,
    "obstacles": [],
    "confidence": "medium",
    "reasoning": "Aerial view shows extensive flooding covering streets and driveways. The waterline appears to reach approximately the top of the tires of the parked vehicles.",
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
      "note": "Cars stranded in flooded streets"
     }
    ],
    "confidence": "high",
    "reasoning": "Brown floodwater covers the residential streets and yards. The aerial view does not show a clear waterline on a reference object like a tire or curb to estimate depth.",
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
    "confidence": "low",
    "reasoning": "Flood water is clearly visible covering the streets and yards in this aerial view. The provided detector objects do not reliably show a waterline on a tire, curb, or hub suitable for measurement, as some boxes appear to target structures rather than vehicles.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   2,
   3
  ],
  "note": "2 of 3 reads agree; read 1: 0.48-0.86 m",
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
  "analyzed_at": "2026-11-21T21:38:27+00:00",
  "elapsed_s": 51.1
 },
 {
  "file": "refs/22840.jpg",
  "title": "Dry street near Brays Bayou (control)",
  "taken": "May 16, 2015",
  "lat": 29.69189,
  "lon": -95.442757,
  "credit": "Mapillary \u00b7 CC BY-SA 4.0",
  "url": "https://www.mapillary.com/app/?pKey=303316301368352",
  "water_visible": false,
  "reference_object": null,
  "fraction_low": null,
  "fraction_high": null,
  "depth_m_low": null,
  "depth_m_high": null,
  "obstacles": [],
  "confidence": "high",
  "reasoning": "The pavement is wet from rain, but there is no standing flood water visible on the street or driveway. No waterline contacts the car, curb, or any other reference object.",
  "status": "ai_proposed",
  "error": null,
  "readings": [
   {
    "water_visible": false,
    "reference_object": null,
    "fraction_low": null,
    "fraction_high": null,
    "depth_m_low": null,
    "depth_m_high": null,
    "obstacles": [],
    "confidence": "high",
    "reasoning": "The pavement is wet from rain, but there is no standing flood water visible on the street or driveway. No waterline contacts the car, curb, or any other reference object.",
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
    "reasoning": "The street surface appears wet but there is no standing flood water visible. No waterline contacts any reference object such as a tire or curb.",
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
    "reasoning": "No standing water or flood lines are visible on the street or driveway; the car is parked on dry pavement.",
    "status": "ai_proposed",
    "error": null
   }
  ],
  "agreeing": [
   1,
   2,
   3
  ],
  "note": null,
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
  "analyzed_at": "2026-11-21T21:38:37+00:00",
  "elapsed_s": 9.7
 }
];
