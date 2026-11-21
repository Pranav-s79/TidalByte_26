"""PyTorch second look at a flood photo (Lane B).

A pretrained torchvision Faster R-CNN (COCO classes, no training) boxes the people,
vehicles and signs in a photo. Nemotron gets those boxes in its prompt so it reads the
waterline against objects that are really there, and read_photo cross-checks the
reference object Nemotron names against what the detector found.

Needs `pip install -r requirements-detector.txt`. Without torch the reader still works;
it just skips this step. Weights (~170 MB) download on first use to ~/.cache/torch.
"""

MODEL_NAME = "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)"
REFERENCE_CLASSES = {"person", "bicycle", "car", "motorcycle", "bus", "truck",
                     "traffic light", "fire hydrant", "stop sign", "parking meter", "bench"}
MIN_SCORE = 0.5
MAX_OBJECTS = 12

_loaded = None  # (model, preprocess, categories) after the first call


def _load():
    global _loaded
    if _loaded is None:
        from torchvision.models.detection import FasterRCNN_ResNet50_FPN_V2_Weights, fasterrcnn_resnet50_fpn_v2

        weights = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        model = fasterrcnn_resnet50_fpn_v2(weights=weights, box_score_thresh=MIN_SCORE).eval()
        _loaded = (model, weights.transforms(), weights.meta["categories"])
    return _loaded


def to_objects(boxes, labels, scores, categories, width, height, min_score=MIN_SCORE):
    """Raw detector output -> reference objects, boxes as [left, top, right, bottom] fractions, best first."""
    out = []
    for (x1, y1, x2, y2), label, score in zip(boxes, labels, scores):
        name = categories[int(label)]
        if name in REFERENCE_CLASSES and score >= min_score:
            out.append({"label": name, "score": round(float(score), 2),
                        "box": [round(x1 / width, 3), round(y1 / height, 3),
                                round(x2 / width, 3), round(y2 / height, 3)]})
    out.sort(key=lambda o: -o["score"])
    return out[:MAX_OBJECTS]


def detect(photo_path):
    """Boxes for the people, vehicles and signs in one photo (CPU, a few seconds)."""
    import torch
    from torchvision.io import ImageReadMode, read_image

    model, preprocess, categories = _load()
    image = read_image(photo_path, mode=ImageReadMode.RGB)
    _, height, width = image.shape
    with torch.inference_mode():
        result = model([preprocess(image)])[0]
    return to_objects(result["boxes"].tolist(), result["labels"].tolist(), result["scores"].tolist(),
                      categories, width, height)


detect.model_name = MODEL_NAME
