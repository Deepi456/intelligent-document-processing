from dataclasses import dataclass
import re
import unicodedata

import spacy

from app.nlp.layout_analyzer import analyze_layout, entity_layout
from app.ocr.ocr_engine import _clamp_confidence


@dataclass(frozen=True)
class Entity:
    name: str
    entity_type: str
    page_number: int
    source: str
    raw_text: str | None = None
    normalized_text: str | None = None
    confidence: float | None = None
    bbox: list[float] | None = None
    normalized_bbox: list[float] | None = None


LABEL_MAP = {
    "ORG": "Organization", "PERSON": "Person", "DATE": "Date", "MONEY": "Amount",
    "GPE": "Location", "LOC": "Location", "FAC": "Facility", "EVENT": "Event",
    "WORK_OF_ART": "WorkOfArt", "LAW": "Law", "LANGUAGE": "Language", "NORP": "Group",
    "PRODUCT": "Product", "TIME": "Time", "PERCENT": "Percent", "QUANTITY": "Quantity",
    "CARDINAL": "Number", "ORDINAL": "Ordinal",
}

EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
URL_PATTERN = re.compile(r"\bhttps?://[^\s<>()]+", re.I)
IDENTIFIER_PATTERN = re.compile(r"\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{5,20}\b")


def extract_entities(pages: list[object], model_name: str = "en_core_web_sm") -> list[dict]:
    nlp = spacy.load(model_name)
    extracted: list[dict] = []
    for page in pages:
        boxes = getattr(page, "bounding_boxes", None) or []
        layout_entities = analyze_layout(
            boxes, getattr(page, "image_width", None) or 0,
            getattr(page, "image_height", None) or 0, page.page_number,
        ) if boxes and getattr(page, "image_width", None) and getattr(page, "image_height", None) else []
        extracted.extend(layout_entities)
        doc = nlp(page.text)
        for item in doc.ents:
            name = item.text.strip()
            if name:
                extracted.append(_entity_record(
                    name, LABEL_MAP.get(item.label_, item.label_), page.page_number, "spacy_ner",
                    entity_layout(name, boxes, page.image_width, page.image_height),
                ))
        for pattern, entity_type in ((EMAIL_PATTERN, "Email"), (URL_PATTERN, "URL"), (IDENTIFIER_PATTERN, "Identifier")):
            for match in pattern.finditer(page.text):
                name = match.group(0).rstrip(".,;")
                extracted.append(_entity_record(name, entity_type, page.page_number, "generic_pattern", entity_layout(name, boxes, page.image_width, page.image_height)))
                
        # Fallback for standalone names (Person) missed by SpaCy
        lines = page.text.split("\n") if "\n" in page.text else page.text.split("  ")
        if len(lines) == 1:
            lines = [t.strip() for t in re.split(r"(?<=[A-Z])\s+(?=[A-Z][a-z])|(?<=[a-z])\s+(?=[A-Z]{2,})", page.text)]
        
        # Fallback for flat string Key-Value pairs without bounding box layout
        for m in re.finditer(r"\b([A-Z][A-Za-z\'\s]+?)\s*[:=\-]?\s*\n+\s*([A-Z]{3,}(?:\s+[A-Z]{1,})*)\b", page.text):
            extracted.append(_entity_record(m.group(2).strip(), m.group(1).strip(), page.page_number, "regex_kv", entity_layout(m.group(2).strip(), boxes, page.image_width, page.image_height)))

        for line in lines:
            line = line.strip()
            if not line:
                continue

            words = line.split()
            if 1 < len(words) <= 3 and all(w.isalpha() or w in (".", "-") for w in words):
                if line.isupper() or line.istitle():
                    if line.lower() not in ("income tax", "department", "father's name", "date of birth", "account number"):
                        extracted.append(_entity_record(line, "Person", page.page_number, "heuristic", entity_layout(line, boxes, page.image_width, page.image_height)))
    return _deduplicate(extracted)


def _entity_record(name: str, entity_type: str, page_number: int, source: str, layout: dict | None) -> dict:
    record = {
        "name": name, "entity_type": entity_type, "page_number": page_number, "source": source,
        "raw_text": name, "normalized_text": _normalize(name),
        "confidence": _clamp_confidence(layout.get("confidence") if layout else 0.85),
    }
    if layout:
        record.update({"bbox": layout["bbox"], "normalized_bbox": layout["normalized_bbox"]})
    return record


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _deduplicate(entities: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, int]] = set()
    result = []
    for entity in entities:
        key = (_normalize(entity["name"]), entity["entity_type"], entity.get("page_number", 1))
        if key not in seen:
            seen.add(key)
            result.append(entity)
    return result
