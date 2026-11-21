"""PyTorch object detector for flood frames (Lane B).

Pretrained torchvision Faster R-CNN (ResNet-50 FPN v2, COCO weights). No training. It finds
the vehicles, people and signs that Super VL reads the waterline against, cuts out the two
largest for a close-up look, and can draw its boxes on a copy of the frame for the demo.

Runs on CPU. On a Linux CPU machine (e.g. Brev), install the CPU-only wheels first:
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

MODEL_NAME = "torchvision fasterrcnn_resnet50_fpn_v2 (COCO, pretrained)"
KEEP = {"car", "truck", "bus", "motorcycle", "person", "stop sign", "fire hydrant"}
MIN_SCORE = 0.6
PAD = 0.2      # crop padding on every side, as a fraction of the box
N_CROPS = 2    # largest objects sent to Super VL as close-ups

_model = None  # (model, preprocess, categories) once loaded


def load():
    """Load the model once (the first call downloads ~170 MB of weights to ~/.cache/torch)."""
    global _model
    if _model is None:
        from torchvision.models.detection import FasterRCNN_ResNet50_FPN_V2_Weights, fasterrcnn_resnet50_fpn_v2

        weights = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        model = fasterrcnn_resnet50_fpn_v2(weights=weights).eval()  # stays on CPU
        _model = (model, weights.transforms(), weights.meta["categories"])
    return _model


def _open(image):
    """A path or PIL image -> upright RGB PIL image (phone photos carry their rotation in EXIF)."""
    img = image if isinstance(image, Image.Image) else Image.open(image)
    return ImageOps.exif_transpose(img).convert("RGB")


def keep(boxes, labels, scores, categories):
    """Raw model output -> kept objects with pixel boxes [x1, y1, x2, y2], best score first."""
    out = [{"label": categories[int(label)], "score": round(float(score), 2), "box": [round(float(v)) for v in box]}
           for box, label, score in zip(boxes, labels, scores)
           if categories[int(label)] in KEEP and score >= MIN_SCORE]
    return sorted(out, key=lambda o: -o["score"])


def padded_box(box, width, height, pad=PAD):
    """Grow a box by `pad` of its size on every side, clipped to the image."""
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    return [max(0, round(x1 - dx)), max(0, round(y1 - dy)), min(width, round(x2 + dx)), min(height, round(y2 + dy))]


def make_crops(image, detections, crop_dir=None, n=N_CROPS):
    """Crop every detection with padding (saved to crop_dir if given); return the n largest, biggest first.

    Each crop is {label, score, box, crop_box, jpeg (bytes), path (if saved)}.
    """
    crops = []
    for i, d in enumerate(detections):
        crop_box = padded_box(d["box"], *image.size)
        crop = image.crop(crop_box)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=90)
        c = {"label": d["label"], "score": d["score"], "box": d["box"], "crop_box": crop_box, "jpeg": buf.getvalue()}
        if crop_dir:
            os.makedirs(crop_dir, exist_ok=True)
            c["path"] = os.path.join(crop_dir, f"{i:02d}-{d['label'].replace(' ', '_')}.jpg")
            with open(c["path"], "wb") as f:
                f.write(c["jpeg"])
        crops.append(c)
    area = lambda c: (c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1])  # noqa: E731
    return sorted(crops, key=area, reverse=True)[:n]


def detect(image, crop_dir=None):
    """Find reference objects in one frame (a path or PIL image).

    Returns (detections, crops):
      detections: [{label, score, box: [x1, y1, x2, y2]}] in pixels, best score first
      crops: the 2 largest objects cut out with 20% padding (see make_crops)
    """
    import torch

    model, preprocess, categories = load()
    img = _open(image)
    with torch.inference_mode():
        out = model([preprocess(img)])[0]
    detections = keep(out["boxes"].tolist(), out["labels"].tolist(), out["scores"].tolist(), categories)
    return detections, make_crops(img, detections, crop_dir)


def debug_draw(image, detections, out_path):
    """Save a copy of the frame with every box and its label and score drawn on it, for the demo."""
    img = _open(image).copy()
    draw = ImageDraw.Draw(img)
    line = max(2, round(min(img.size) / 250))
    try:
        font = ImageFont.load_default(size=max(14, round(img.size[1] / 40)))
    except TypeError:  # Pillow < 10.1 has one fixed-size default font
        font = ImageFont.load_default()
    for d in detections:
        x1, y1, x2, y2 = d["box"]
        draw.rectangle([x1, y1, x2, y2], outline=(255, 196, 0), width=line)
        text = f"{d['label']} {d['score']:.2f}"
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        ty = max(0, y1 - (bottom - top) - 6)
        draw.rectangle([x1, ty, x1 + (right - left) + 8, ty + (bottom - top) + 6], fill=(255, 196, 0))
        draw.text((x1 + 4, ty + 3 - top), text, fill=(0, 0, 0), font=font)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path)
    return out_path


detect.model_name = MODEL_NAME
