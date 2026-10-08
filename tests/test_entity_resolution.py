from pathlib import Path

from app.extraction.pdf_extractor import PageText
from app.knowledge_graph.entity_resolution import canonical_id, normalize_entity_value
from app.knowledge_graph.graph_builder import GraphBuilder


class FakeClient:
    def __init__(self):
        self.calls = []

    def execute_write(self, query, **parameters):
        self.calls.append((query, parameters))


def build(document, entity_type, name):
    client = FakeClient()
    GraphBuilder(client).add_document(
        Path(document), [PageText(1, name, "text_layer", None, 100, 100)],
        [{"name": name, "entity_type": entity_type, "page_number": 1, "source": "spacy"}], [],
    )
    return client


def test_first_mention_creates_canonical_entity():
    client = build("document-a.pdf", "Organization", "ABC Corporation")
    query, parameters = client.calls[-1]
    assert "EntityMention" in query and "CanonicalOrganization" in query
    assert parameters["canonical_id"] == canonical_id("Organization", "abc corporation")


def test_exact_normalized_value_resolves_to_same_canonical_id():
    first = build("document-a.pdf", "Organization", "ABC Corporation")
    second = build("document-b.pdf", "Organization", "ABC-Corporation")
    assert first.calls[-1][1]["canonical_id"] == second.calls[-1][1]["canonical_id"]
    assert first.calls[-1][1]["mention_id"] != second.calls[-1][1]["mention_id"]


def test_entity_types_do_not_share_canonical_label_or_identity():
    organization = build("document-a.pdf", "Organization", "ABC Corporation")
    person = build("document-b.pdf", "Person", "ABC Corporation")
    assert organization.calls[-1][1]["canonical_id"] != person.calls[-1][1]["canonical_id"]
    assert "CanonicalOrganization" in organization.calls[-1][0]
    assert "CanonicalPerson" in person.calls[-1][0]


def test_different_values_do_not_merge():
    first = build("document-a.pdf", "Organization", "ABC Corporation")
    second = build("document-b.pdf", "Organization", "ABC Industries")
    assert first.calls[-1][1]["canonical_id"] != second.calls[-1][1]["canonical_id"]


def test_normalization_is_deterministic_and_unicode_aware():
    assert normalize_entity_value("ABC-Corporation") == "abc corporation"
    assert normalize_entity_value("ＡＢＣ Corporation") == "abc corporation"