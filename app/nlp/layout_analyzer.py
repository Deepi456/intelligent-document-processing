from dataclasses import dataclass
import re
from typing import Iterable

from app.ocr.ocr_engine import _clamp_confidence


DATE_PATTERN = re.compile(r"\b(?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b")
NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+[.,]?)+%?$")
EMAIL_VALUE_PATTERN = re.compile(r"^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$")
URL_VALUE_PATTERN = re.compile(r"^https?://\S+$", re.I)


@dataclass(frozen=True)
class LayoutBox:
    text: str
    confidence: float | None
    left: float
    top: float
    width: float
    height: float
    normalized_bbox: list[float]

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


def normalize_boxes(boxes: Iterable[dict], image_width: float, image_height: float) -> list[LayoutBox]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    valid_boxes = [box for box in boxes if str(box.get("text", "")).strip() and all(
        box.get(key) is not None for key in ("left", "top", "width", "height")
    )]
    return [LayoutBox(
        text=str(box.get("text", "")), confidence=box.get("confidence"),
        left=float(box["left"]), top=float(box["top"]),
        width=float(box["width"]), height=float(box["height"]),
        normalized_bbox=[
            float(box["left"]) / image_width, float(box["top"]) / image_height,
            float(box["width"]) / image_width, float(box["height"]) / image_height,
        ],
    ) for box in valid_boxes]


def sort_reading_order(boxes: Iterable[LayoutBox], y_tolerance: float = 0.5) -> list[LayoutBox]:
    box_list = list(boxes)
    if not box_list:
        return []
    
    # Detect 90-degree rotation (vertical text strips)
    v_boxes = sum(1 for b in box_list if b.height > b.width * 1.5)
    h_boxes = sum(1 for b in box_list if b.width > b.height * 1.5)
    
    if v_boxes > h_boxes:
        # Rotated 90 deg clockwise.
        # Logical left (line number) is actual top. Logical top (position in line) is actual right (max_x - left).
        # Wait, if rotated clockwise, true left-to-right is unrotated top-to-bottom.
        max_left = max(b.left for b in box_list)
        ordered = sorted(box_list, key=lambda box: (max_left - box.left, box.top))
        
        lines: list[list[LayoutBox]] = []
        for box in ordered:
            center = max_left - box.left
            for line in lines:
                line_center = sum(max_left - item.left for item in line) / len(line)
                if abs(center - line_center) <= max(y_tolerance, box.width * 0.6):
                    line.append(box)
                    break
            else:
                lines.append([box])
        return [box for line in sorted(lines, key=lambda group: min(max_left - item.left for item in group)) for box in sorted(line, key=lambda item: item.top)]
    
    ordered = sorted(box_list, key=lambda box: (box.top, box.left))
    lines: list[list[LayoutBox]] = []
    for box in ordered:
        center = box.top + box.height / 2
        for line in lines:
            line_center = sum(item.top + item.height / 2 for item in line) / len(line)
            if abs(center - line_center) <= max(y_tolerance, box.height * 0.6):
                line.append(box)
                break
        else:
            lines.append([box])
    return [box for line in sorted(lines, key=lambda group: min(item.top for item in group)) for box in sorted(line, key=lambda item: item.left)]


def group_lines(boxes: Iterable[LayoutBox], y_tolerance: float = 0.5) -> list[list[LayoutBox]]:
    ordered = sort_reading_order(boxes, y_tolerance)
    lines: list[list[LayoutBox]] = []
    for box in ordered:
        center = box.top + box.height / 2
        if lines:
            previous = lines[-1]
            previous_center = sum(item.top + item.height / 2 for item in previous) / len(previous)
            if abs(center - previous_center) <= max(y_tolerance, box.height * 0.6):
                previous.append(box)
                continue
        lines.append([box])
    return lines


def identify_regions(lines: list[list[LayoutBox]]) -> dict[str, list[list[LayoutBox]]]:
    """Group lines by neutral vertical position."""
    regions = {"upper": [], "middle": [], "lower": []}
    for line in lines:
        position = min(box.normalized_bbox[1] for box in line)
        region = "upper" if position < 0.33 else "middle" if position < 0.66 else "lower"
        regions[region].append(line)
    return regions


def analyze_layout(boxes: list[dict], image_width: float, image_height: float, page_number: int = 1) -> list[dict]:
    """Return generic key-value attributes found in a page layout."""
    if not boxes or image_width <= 0 or image_height <= 0:
        return []
    layout_boxes = normalize_boxes(boxes, image_width, image_height)
    entities = []
    grouped_lines = group_lines(layout_boxes)
    
    # Horizontal Key-Value pairing
    consumed_line_indices = set()
    for line_idx, line in enumerate(grouped_lines):
        if len(line) < 2:
            continue

        split_index = -1
        has_separator = False
        for i, box in enumerate(line[:-1]):
            text = box.text.strip()
            if text.endswith(":") or text.endswith("=") or text.endswith("-") or text in (":", "=", "-"):
                split_index = i
                has_separator = True
                break

        # Gap-based split: allow split without explicit separator when gap is
        # structurally significant (large relative to line height and image width)
        # and the first box is a plausible key. This avoids false positives like
        # "Name FDHPA3470H Account" where gaps are small.
        if split_index == -1:
            key_box = line[0]
            key_text = key_box.text.strip()
            if _is_plausible_key(key_text):
                max_gap = 0.0
                split_index = -1
                for i in range(len(line) - 1):
                    gap = line[i + 1].left - line[i].right
                    # Threshold: gap must be at least 2x line height, 0.5x key width, or 20px
                    needed = max(line[0].height * 2.0, line[i].width * 0.5, 20.0)
                    if gap > max_gap and gap >= needed:
                        max_gap = gap
                        split_index = i


        if split_index != -1:
            key_boxes = line[:split_index + 1]
            value_boxes = line[split_index + 1:]
            
            key = " ".join(b.text for b in key_boxes).strip().rstrip(":-=").strip()
            value = " ".join(b.text for b in value_boxes).strip()
            
            if (
                key and value and len(key) <= 60
                and _is_plausible_key(key) and _is_plausible_value(value)
            ):
                entities.append({
                    "name": value, "entity_type": key, "page_number": page_number,
                    "source": "layout_value", "raw_text": " ".join(box.text for box in line),
                    "normalized_text": value.casefold(), "confidence": _average_confidence(value_boxes),
                    "bbox": _bbox(line), "normalized_bbox": _normalized_bbox(line),
                })
                consumed_line_indices.add(line_idx)
                continue
                
        # Fallback for old explicit looks_like_value logic if not split
        value_box = line[-1]
        value = value_box.text.strip().strip(":-=")
        preceding = " ".join(box.text for box in line[:-1]).strip()
        if (
            _looks_like_value(value)
            and _is_plausible_value(value)
            and any(box.text.strip() != value for box in line[:-1])
            and (not preceding or _is_plausible_key(preceding.rstrip(":-=").strip()))
        ):
            entities.append({
                "name": value, "entity_type": _value_type(value), "page_number": page_number,
                "source": "layout_value", "raw_text": " ".join(box.text for box in line),
                "normalized_text": value.casefold(), "confidence": _clamp_confidence(value_box.confidence),
                "bbox": _bbox(line), "normalized_bbox": _normalized_bbox(line),
            })
            consumed_line_indices.add(line_idx)
            
    # Vertical Key-Value pairing
    for i in range(len(grouped_lines) - 1):
        if i in consumed_line_indices or (i + 1) in consumed_line_indices:
            continue
        line1 = grouped_lines[i]
        line2 = grouped_lines[i+1]
        key = " ".join(b.text for b in line1).strip().rstrip(":-=").strip()
        val = " ".join(b.text for b in line2).strip()
        
        if key.isupper() or len(key.split()) > 5 or not key:
            continue
            
        looks_like_val = val.isupper() or any(c.isdigit() for c in val)
        if (
            looks_like_val
            and len(val.split()) <= 4
            and _is_plausible_key(key)
            and _is_plausible_value(val)
        ):
            entities.append({
                "name": val, "entity_type": key, "page_number": page_number,
                "source": "layout_vertical", "raw_text": f"{key} {val}",
                "normalized_text": val.casefold(), "confidence": _average_confidence(line2),
                "bbox": _bbox(line1 + line2), "normalized_bbox": _normalized_bbox(line1 + line2),
            })

    return entities


def entity_layout(text: str, boxes: list[dict], image_width: float | None = None, image_height: float | None = None) -> dict | None:
    """Best-effort OCR box alignment for a semantic entity."""
    if not boxes or not text.strip():
        return None
    words = text.casefold().split()
    candidates = [box for box in boxes if any(word in str(box.get("text", "")).casefold() for word in words)]
    if not candidates:
        return None
    image_width = image_width or max(float(box["left"]) + float(box["width"]) for box in boxes)
    image_height = image_height or max(float(box["top"]) + float(box["height"]) for box in boxes)
    normalized = normalize_boxes(candidates, image_width, image_height)
    return {"confidence": _average_confidence(candidates), "bbox": _bbox(normalized), "normalized_bbox": _normalized_bbox(normalized)}


def _looks_like_value(value: str) -> bool:
    return bool(
        NUMBER_PATTERN.fullmatch(value)
        or DATE_PATTERN.fullmatch(value)
        or EMAIL_VALUE_PATTERN.fullmatch(value)
        or URL_VALUE_PATTERN.fullmatch(value)
    )


def _value_type(value: str) -> str:
    if EMAIL_VALUE_PATTERN.fullmatch(value):
        return "Email"
    if URL_VALUE_PATTERN.fullmatch(value):
        return "URL"
    if DATE_PATTERN.fullmatch(value):
        return "Date"
    return "Number"


def _alnum_ratio(value: str) -> float:
    text = value.strip()
    if not text:
        return 0.0
    return sum(char.isalnum() for char in text) / len(text)


def _is_plausible_key(key: str) -> bool:
    text = key.strip()
    return bool(text) and any(char.isalpha() for char in text) and _alnum_ratio(text) >= 0.5


def _is_plausible_value(value: str) -> bool:
    text = value.strip()
    if not text or _alnum_ratio(text) < 0.5:
        return False
    if "@" in text and not EMAIL_VALUE_PATTERN.search(text.replace(" ", "")):
        return False
    return True


def _average_confidence(boxes: Iterable[dict | LayoutBox]) -> float | None:
    values = [box.get("confidence") if isinstance(box, dict) else box.confidence for box in boxes]
    values = [_clamp_confidence(value) for value in values if value is not None]
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _bbox(boxes: Iterable[LayoutBox]) -> list[float]:
    left = min(box.left for box in boxes)
    top = min(box.top for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    return [left, top, right - left, bottom - top]


def _normalized_bbox(boxes: Iterable[LayoutBox]) -> list[float]:
    left = min(box.normalized_bbox[0] for box in boxes)
    top = min(box.normalized_bbox[1] for box in boxes)
    right = max(box.normalized_bbox[0] + box.normalized_bbox[2] for box in boxes)
    bottom = max(box.normalized_bbox[1] + box.normalized_bbox[3] for box in boxes)
    return [left, top, right - left, bottom - top]
