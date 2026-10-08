import re
import unicodedata


CANONICAL_LABELS = {
    "Organization": "CanonicalOrganization",
    "Person": "CanonicalPerson",
    "Product": "CanonicalProduct",
    "Location": "CanonicalLocation",
    "Date": "CanonicalDate",
    "Amount": "CanonicalAmount",
}

SAFE_ENTITY_LABELS = frozenset({
    "Organization", "Person", "Product", "Location", "Date", "Amount",
    "Facility", "Event", "WorkOfArt", "Law", "Language", "Group",
    "Time", "Percent", "Quantity", "Number", "Ordinal", "Email", "URL",
})


def normalize_entity_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(" " if unicodedata.category(char).startswith("P") else char for char in normalized)
    return " ".join(normalized.split())


def canonical_label(entity_type: str) -> str | None:
    return CANONICAL_LABELS.get(entity_type)


def entity_label(entity_type: str) -> str:
    """Return a fixed safe label while retaining the original type as a property."""
    return entity_type if entity_type in SAFE_ENTITY_LABELS else "Entity"


def relationship_label(relationship_type: str) -> str:
    """Return a safe Neo4j relationship label for an extracted type."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relationship_type or ""):
        return relationship_type
    return "EXTRACTED_RELATION"


def canonical_id(entity_type: str, normalized_value: str) -> str:
    return f"{entity_type}:{normalized_value}"


def mention_id(document_id: str, entity_type: str, normalized_value: str, ordinal: int) -> str:
    raw = f"{document_id}:{entity_type}:{normalized_value}:{ordinal}"
    return re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-")[:180]