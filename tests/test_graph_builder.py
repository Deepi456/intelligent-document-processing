from pathlib import Path

from app.extraction.pdf_extractor import PageText
from app.knowledge_graph.graph_builder import GraphBuilder


class FakeClient:
    def __init__(self):
        self.calls = []

    def execute_write(self, query, **parameters):
        self.calls.append((query, parameters))


def test_provenance_graph_writes_document_page_evidence_and_relationship():
    client = FakeClient()
    builder = GraphBuilder(client)
    pages = [PageText(1, "ABC Corporation purchased 20 laptops from Dell Technologies.", "ocr", [{"text": "ABC Corporation"}], 100, 200)]
    entities = [
        {"name": "ABC Corporation", "entity_type": "Organization", "page_number": 1, "source": "receipt_rule", "confidence": 0.9, "bbox": [1, 2, 3, 4], "normalized_bbox": [0.01, 0.01, 0.03, 0.02]}
    ]
    relationships = [{"source": "ABC Corporation", "source_type": "Organization", "type": "PURCHASED", "target": "laptops", "target_type": "Product", "page_number": 1}]
    builder.add_document(Path("invoice.pdf"), pages, entities, relationships)
    queries = " ".join(query for query, _ in client.calls)
    assert "DocumentPage" in queries
    assert "Evidence" in queries
    assert "HAS_EVIDENCE" in queries
    assert "SUPPORTS" in queries
    assert "MENTIONS" in queries
    relationship_params = client.calls[-2][1]
    assert relationship_params["evidence_id"]
    assert "page" in relationship_params


def test_schema_constraints_are_scoped_to_created_nodes():
    client = FakeClient()
    GraphBuilder(client).ensure_schema()
    queries = " ".join(query for query, _ in client.calls)
    assert "document_id_unique" in queries
    assert "page_identity_unique" in queries
    assert "evidence_id_unique" in queries


def test_relationship_uses_canonical_endpoints_and_provenance():
    client = FakeClient()
    GraphBuilder(client).add_document(
        Path("invoice.pdf"),
        [PageText(1, "ABC Corporation purchased laptops from Dell Technologies.", "ocr", None, 100, 100)],
        [],
        [
            {"source": "ABC Corporation", "source_type": "Organization", "type": "PURCHASED", "target": "laptops", "target_type": "Product", "page_number": 1},
            {"source": "ABC Corporation", "source_type": "Organization", "type": "SUPPLIED_BY", "target": "Dell Technologies", "target_type": "Organization", "page_number": 1},
        ],
    )
    relationship_query = " ".join(query for query, _ in client.calls)
    assert "CanonicalOrganization" in relationship_query
    assert "CanonicalProduct" in relationship_query
    assert "PURCHASED" in relationship_query
    assert "SUPPLIED_BY" in relationship_query
    canonical_parameters = client.calls[-3][1]
    assert canonical_parameters["evidence_id"]
    assert canonical_parameters["confidence"] == 100.0
    assert canonical_parameters["method"] == "relationship_rule"