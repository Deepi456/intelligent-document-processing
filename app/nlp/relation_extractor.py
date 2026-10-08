import hashlib
import re

from app.ocr.ocr_engine import _clamp_confidence


CUE_PATTERNS = (
    ("LOCATED_IN", re.compile(r"\b(?:is\s+)?located\s+in\b|\blives\s+in\b", re.I)),
    ("PART_OF", re.compile(r"\bis\s+part\s+of\b|\bpart\s+of\b", re.I)),
    ("RELATED_TO", re.compile(r"\bis\s+related\s+to\b|\brelated\s+to\b|\bconnected\s+to\b", re.I)),
    ("USED_BY", re.compile(r"\bis\s+used\s+by\b|\bused\s+by\b", re.I)),
    ("CREATED_BY", re.compile(r"\bcreated\s+by\b|\bauthored\s+by\b|\bwritten\s+by\b", re.I)),
    ("WORKS_AT", re.compile(r"\bworks\s+(?:at|for)\b", re.I)),
    ("CONTAINS", re.compile(r"\bcontains\b|\bincludes\b", re.I)),
    ("USES", re.compile(r"\buses\b|\butilizes\b", re.I)),
    ("HAS", re.compile(r"\bhas\b|\bhave\b", re.I)),
)


def extract_relationships(pages: list[object], entities: list[dict]) -> list[dict]:
    """Extract only explicit, sentence-local relationships between known entities."""
    relationships = []
    entities_by_page: dict[int, list[dict]] = {}
    for entity in entities:
        entities_by_page.setdefault(entity.get("page_number", 1), []).append(entity)

    for page in pages:
        page_entities = sorted(entities_by_page.get(page.page_number, []), key=lambda entity: len(entity["name"]), reverse=True)
        for sentence in _sentences(page.text):
            mentions = _mentions(sentence, page_entities)
            for source, target, between in _entity_pairs(mentions, sentence):
                relation_type = _relation_type(between)
                if relation_type is None or source["name"] == target["name"]:
                    continue
                raw_text = sentence.strip()
                relationships.append({
                    "source": source["name"], "source_type": source["entity_type"],
                    "target": target["name"], "target_type": target["entity_type"],
                    "type": relation_type, "confidence": _clamp_confidence(0.75),
                    "extraction_method": "generic_relation_rule", "page_number": page.page_number,
                    "raw_text": raw_text, "evidence_id": _evidence_id(page.page_number, raw_text),
                })
    return _deduplicate(relationships)


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip()]


def _mentions(sentence: str, entities: list[dict]) -> list[tuple[int, int, dict]]:
    mentions = []
    for entity in entities:
        for match in re.finditer(re.escape(entity["name"]), sentence, re.I):
            mentions.append((match.start(), match.end(), entity))
    return sorted(mentions, key=lambda item: (item[0], -(item[1] - item[0])))


def _entity_pairs(mentions: list[tuple[int, int, dict]], sentence: str) -> list[tuple[dict, dict, str]]:
    pairs = []
    for index, (_, source_end, source) in enumerate(mentions):
        for target_start, _, target in mentions[index + 1:]:
            if target_start <= source_end or target["name"] == source["name"]:
                continue
            pairs.append((source, target, sentence[source_end:target_start]))
            break
    return pairs


def _relation_type(between: str) -> str | None:
    for relation_type, pattern in CUE_PATTERNS:
        if pattern.search(between):
            return relation_type
    return None


def _evidence_id(page_number: int, raw_text: str) -> str:
    digest = hashlib.sha1(raw_text.encode("utf-8")).hexdigest()[:16]
    return f"page-{page_number}-relation-{digest}"


def _deduplicate(relationships: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for relationship in relationships:
        key = (relationship["source"], relationship["target"], relationship["type"], relationship["page_number"])
        if key not in seen:
            seen.add(key)
            result.append(relationship)
    return result
