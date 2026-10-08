from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None
    bounding_boxes: list[dict]


@dataclass(frozen=True)
class EngineComparison:
    """Internal comparison of both OCR engines on the same image plus fused pick."""

    tesseract: OcrResult | None
    paddle: OcrResult | None
    fused: OcrResult


class OcrEngine:
    def __init__(self, backend: str | None = None, tesseract_cmd: str | None = None) -> None:
        self.backend = (backend or os.getenv("OCR_BACKEND", "tesseract")).lower()
        if self.backend not in {"tesseract", "paddle"}:
            raise ValueError("OCR backend must be 'tesseract' or 'paddle'")
        self._ocr: Any = None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        elif os.getenv("TESSERACT_CMD"):
            pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

    @property
    def ocr(self) -> Any:
        if self._ocr is None:
            if self.backend == "tesseract":
                pytesseract.get_tesseract_version()
                self._ocr = pytesseract
            else:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(lang="en")
        return self._ocr

    def extract_file(self, file_path: str | Path) -> OcrResult:
        if self.backend == "tesseract":
            with Image.open(file_path) as image:
                return self._extract_tesseract(image)
        return self._paddle_result(self.ocr.predict(str(file_path)))

    def extract_pixmap(self, pixmap: Any) -> OcrResult:
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )[:, :, :3]
        if self.backend == "tesseract":
            return self._extract_tesseract(Image.fromarray(image))
        return self._paddle_result(self.ocr.predict(image))

    def _paddle_on_image(self, image: Any) -> OcrResult | None:
        """Run the existing PaddleOCR backend on an in-memory image."""
        try:
            from paddleocr import PaddleOCR

            predictor = PaddleOCR(lang="en")
            payload: Any = image
            try:
                payload = np.array(image.convert("RGB"))
            except Exception:
                pass
            return self._paddle_result(predictor.predict(payload))
        except Exception:
            return None

    def compare_image(self, image: Any) -> EngineComparison:
        """Run Tesseract + PaddleOCR on the same image and fuse generically."""
        tesseract_result = self._extract_tesseract(image)
        paddle_result = self._paddle_on_image(image)
        fused = _fuse_engine_results(tesseract_result, paddle_result)
        return EngineComparison(
            tesseract=tesseract_result, paddle=paddle_result, fused=fused
        )

    def compare_file(self, file_path: str | Path) -> EngineComparison:
        """Run Tesseract + PaddleOCR on the same scanned image file."""
        with Image.open(file_path) as image:
            loaded = image.convert("RGB")
            return self.compare_image(loaded)

    @staticmethod
    def _paddle_result(results: Any) -> OcrResult:
        texts: list[str] = []
        boxes: list[dict] = []
        for result in results:
            data = result.json if hasattr(result, "json") else result
            if callable(data):
                data = data()
            if isinstance(data, str):
                data = json.loads(data)
            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])
            rec_boxes = data.get("rec_polys", data.get("rec_boxes", []))
            for index, value in enumerate(rec_texts):
                if value:
                    score = rec_scores[index] if index < len(rec_scores) else None
                    confidence = _clamp_confidence(score)
                    box = rec_boxes[index] if index < len(rec_boxes) else None
                    left, top, width, height = _paddle_box_bounds(box)
                    texts.append(str(value))
                    boxes.append({"text": str(value), "confidence": confidence, "left": left, "top": top, "width": width, "height": height, "engine": "paddle"})
        confidences = [box["confidence"] for box in boxes if box["confidence"] is not None]
        return OcrResult("\n".join(texts).strip(), _clamp_confidence(sum(confidences) / len(confidences)) if confidences else None, boxes)

    @staticmethod
    def _extract_tesseract(image: Any) -> OcrResult:
        # Tesseract wrapper that tries multiple preprocessing approaches and keeps the best.
        import cv2
        import numpy as np
        
        # Convert PIL to cv2 for preprocessing
        img_cv = np.array(image.convert("RGB"))
        img_cv = img_cv[:, :, ::-1].copy()
        
        # OSD Auto-rotation
        angle = 0
        try:
            import re
            osd = pytesseract.image_to_osd(img_cv)
            match = re.search(r'(?<=Rotate: )\d+', osd)
            if match:
                angle = int(match.group(0))
                if angle == 90:
                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
                elif angle == 180:
                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_180)
                elif angle == 270:
                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
        except Exception:
            pass

        try:
            from PIL import Image
            rotated_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        except Exception:
            rotated_pil = image
            
        attempts = []
        
        # 1. Original image, PSM 3 (auto page segmentation) - better for complex layouts
        attempts.append({"img": rotated_pil, "scale": 1.0, "psm": 3})
        
        # 2. Original image, PSM 6 (uniform block) - good for basic documents
        attempts.append({"img": rotated_pil, "scale": 1.0, "psm": 6})
        
        # 3. Preprocessed image (Large Gray), PSM 3
        try:
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            # Upscale for better OCR on small fonts
            height, width = gray.shape
            if height < 2000 and width < 2000:
                large = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                large_pil = Image.fromarray(large)
                attempts.append({"img": large_pil, "scale": 2.0, "psm": 3})
                attempts.append({"img": large_pil, "scale": 2.0, "psm": 6})
        except Exception:
            pass # Fallback to original if cv2 fails

        results: list[tuple[OcrResult, float]] = []
        
        for attempt in attempts:
            try:
                psm = attempt["psm"]
                scale = attempt["scale"]
                test_img = attempt["img"]
                
                text = pytesseract.image_to_string(test_img, lang="eng", config=f"--psm {psm}").strip()
                data = pytesseract.image_to_data(test_img, lang="eng", config=f"--psm {psm}", output_type=Output.DICT)
                
                boxes = []
                confidences = []
                
                for index, value in enumerate(data["text"]):
                    value = value.strip()
                    if not value:
                        continue
                    confidence = float(data["conf"][index])
                    if confidence >= 0:
                        confidences.append(confidence)
                    
                    left = int(data["left"][index] / scale)
                    top = int(data["top"][index] / scale)
                    width = int(data["width"][index] / scale)
                    height = int(data["height"][index] / scale)
                    
                    # Unrotate coordinates to match original image
                    orig_width, orig_height = image.size
                    if angle == 90:
                        # Image was rotated 90 CW. To unrotate, rotate 90 CCW.
                        new_left = top
                        new_top = orig_width - left - width
                        left, top, width, height = new_left, new_top, height, width
                    elif angle == 180:
                        # Image was rotated 180. To unrotate, rotate 180.
                        left = orig_width - left - width
                        top = orig_height - top - height
                    elif angle == 270:
                        # Image was rotated 90 CCW. To unrotate, rotate 90 CW.
                        new_left = orig_width - top - height
                        new_top = left
                        left, top, width, height = new_left, new_top, height, width

                    boxes.append({
                        "text": value,
                        "confidence": _clamp_confidence(confidence),
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                        "engine": "tesseract",
                    })
                
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                total_chars = sum(len(b["text"]) for b in boxes)
                
                # Score factors in both average confidence and total text length
                score = avg_conf * (total_chars ** 0.3) if total_chars > 0 else 0.0
                
                result = OcrResult(text, _clamp_confidence(avg_conf) if confidences else None, boxes)
                results.append((result, score))
                    
                # If we get a very high confidence and reasonable amount of text, stop early
                if avg_conf > 85.0 and total_chars > 20:
                    break
            except Exception:
                continue
                
        if not results:
            return OcrResult("", None, [])
        return _fuse_results(results)


def _clamp_confidence(value: object) -> float | None:
    """Clamp any OCR confidence scale to the 0-100 display range."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN guard
        return None
    if 0.0 <= number <= 1.0:
        # A probability-scale confidence (e.g. PaddleOCR) becomes a percentage.
        number *= 100.0
    return max(0.0, min(100.0, number))


def _paddle_box_bounds(box: Any) -> tuple[float | None, float | None, float | None, float | None]:
    """Derive an axis-aligned rect from a PaddleOCR polygon/box payload."""
    try:
        points = [[float(coord) for coord in point] for point in box]
        flat: list[float] = []
        for point in points:
            flat.extend(point)
        if len(flat) < 4:
            return (None, None, None, None)
        xs = flat[0::2]
        ys = flat[1::2]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        return (left, top, max(0.0, right - left), max(0.0, bottom - top))
    except Exception:
        return (None, None, None, None)


def _tagged_result(result: OcrResult, engine: str) -> OcrResult:
    boxes = []
    for box in result.bounding_boxes:
        tagged = dict(box)
        tagged.setdefault("engine", engine)
        tagged["confidence"] = _clamp_confidence(tagged.get("confidence"))
        boxes.append(tagged)
    return OcrResult(result.text, _clamp_confidence(result.confidence), boxes)


def _engine_score(result: OcrResult) -> float:
    """Generic engine-level score: confidence weighted by text completeness."""
    confidence = _clamp_confidence(result.confidence) or 0.0
    total_chars = sum(len(str(box.get("text", ""))) for box in result.bounding_boxes)
    words = len(result.text.split())
    return confidence * (total_chars**0.3) + min(words, 50) * 0.5 if total_chars > 0 else 0.0


def _fuse_engine_results(
    tesseract: OcrResult | None, paddle: OcrResult | None
) -> OcrResult:
    """Compare Tesseract + PaddleOCR on the same image and fuse generically."""
    available = [
        (_tagged_result(result, engine), engine)
        for result, engine in ((tesseract, "tesseract"), (paddle, "paddle"))
        if result is not None
    ]
    if not available:
        return OcrResult("", None, [])
    if len(available) == 1:
        only, _ = available[0]
        return _fuse_results([(only, max(_engine_score(only), 0.0))])
    scored = [(result, _engine_score(result)) for result, _ in available]
    return _fuse_results(scored)


def _coord(box: dict, key: str) -> float:
    try:
        value = box.get(key, 0)
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fuse_results(results: list[tuple[OcrResult, float]]) -> OcrResult:
    """Fuse overlapping word candidates while retaining the strongest page pass."""
    selected, _ = max(results, key=lambda item: item[1])
    fused_boxes = []
    for box in selected.bounding_boxes:
        candidates = [box]
        for result, _ in results:
            for candidate in result.bounding_boxes:
                if candidate is box or _overlap(box, candidate) >= 0.15:
                    candidates.append(candidate)
        fused_boxes.append(_select_candidate(candidates))

    unique_boxes = []
    seen = set()
    for box in fused_boxes:
        key = (
            box.get("text", "").casefold(),
            round(_coord(box, "left"), 1),
            round(_coord(box, "top"), 1),
        )
        if key not in seen:
            seen.add(key)
            unique_boxes.append(box)

    ordered = sorted(unique_boxes, key=lambda box: (_coord(box, "top"), _coord(box, "left")))
    lines: list[list[dict]] = []
    for box in ordered:
        center = _coord(box, "top") + _coord(box, "height") / 2
        if lines:
            previous = lines[-1]
            previous_center = sum(_coord(item, "top") + _coord(item, "height") / 2 for item in previous) / len(previous)
            if abs(center - previous_center) <= max(5.0, _coord(box, "height") * 0.6):
                previous.append(box)
                continue
        lines.append([box])
    text = "\n".join(" ".join(box["text"] for box in sorted(line, key=lambda item: _coord(item, "left"))) for line in lines)
    confidences = [_clamp_confidence(box["confidence"]) for box in unique_boxes if box.get("confidence") is not None]
    confidences = [value for value in confidences if value is not None and value >= 0]
    return OcrResult(text.strip(), sum(confidences) / len(confidences) if confidences else _clamp_confidence(selected.confidence), unique_boxes)


def _normalized_token(text: str) -> str:
    return "".join(char.lower() for char in str(text) if char.isalnum())


def _is_fuller_version(longer: str, shorter: str) -> bool:
    """Generic check: longer text plausibly contains the shorter read."""
    norm_longer = _normalized_token(longer)
    norm_shorter = _normalized_token(shorter)
    if len(norm_shorter) < 3 or len(norm_longer) <= len(norm_shorter):
        return False
    if norm_shorter in norm_longer:
        return True
    import difflib

    return difflib.SequenceMatcher(None, norm_longer, norm_shorter).ratio() >= 0.8


def _select_candidate(candidates: list[dict]) -> dict:
    best = max(candidates, key=_candidate_score)
    best_text = str(best.get("text", ""))
    challengers: list[dict] = []
    for candidate in candidates:
        if candidate is best:
            continue
        text = str(candidate.get("text", ""))
        if not _is_fuller_version(text, best_text):
            continue
        if _overlap(candidate, best) < 0.4:
            continue
        confidence = candidate.get("confidence")
        if confidence is not None:
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                continue
            if not (confidence_value >= 0):
                continue
        alpha_ratio = sum(c.isalnum() for c in text) / max(1, len(text))
        if alpha_ratio < 0.5:
            continue
        challengers.append(candidate)
    if challengers:
        return max(challengers, key=_candidate_score)
    return best


def _candidate_score(box: dict) -> tuple[float, int]:
    text = str(box.get("text", "")).strip()
    confidence = _clamp_confidence(box.get("confidence")) or 0.0
    area = max(0.0, _coord(box, "width") * _coord(box, "height"))
    coverage = math.sqrt(area)
    alpha_ratio = sum(char.isalnum() for char in text) / max(1, len(text))
    return (alpha_ratio, coverage + confidence * 0.25, len(text))


def _overlap(first: dict, second: dict) -> float:
    left = max(_coord(first, "left"), _coord(second, "left"))
    top = max(_coord(first, "top"), _coord(second, "top"))
    right = min(_coord(first, "left") + _coord(first, "width"), _coord(second, "left") + _coord(second, "width"))
    bottom = min(_coord(first, "top") + _coord(first, "height"), _coord(second, "top") + _coord(second, "height"))
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(1.0, _coord(first, "width") * _coord(first, "height"))
    second_area = max(1.0, _coord(second, "width") * _coord(second, "height"))
    return intersection / min(first_area, second_area)