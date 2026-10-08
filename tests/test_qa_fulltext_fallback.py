"""Focused tests for the generic full-text Evidence fallback in DocumentQueryService.

These tests use a fake Neo4j client so no live database is required. They cover:
A. A fact that only exists in stored evidence text (no structured entity/attribute/relationship)
   is still retrievable.
B. Document isolation is preserved (the same fact must not leak between documents).
C. A structured answer always takes precedence over the fallback.
D. A completely unrelated question still returns the no-answer response.
E. document_id=None keeps the existing global behavior (fallback is never attempted).
"""

import os
import sys

import pytest

# Make the repository root importable when running the bare `pytest` console
# script (same bootstrap as tests/test_api.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.service import DocumentQueryService, DocumentNotFound


DOC_A = "C:/documents/pan.pdf"
DOC_B = "C:/documents/other.pdf"
DOC_C = "C:/documents/invoice.pdf"

NO_MATCH_ANSWER = "I couldn't find enough information in this document to answer that question."
NO_MATCH_ANSWER_GLOBAL = "No matching evidence was found in the processed documents."

# Page evidence text for the target document. The blood group is only present as raw page text
# and is deliberately not modelled as a structured entity/attribute/relationship.
PAGE_TEXT_A = (
    "GOVERNMENT OF INDIA\n"
    "Name: TEST USER\n"
    "Blood Group: O+\n"
    "Address: 12 Some Street, Coimbatore\n"
)
PAGE_TEXT_B = (
    "SOME UNRELATED DOCUMENT\n"
    "Reference Code: ZX-900\n"
    "Handled By: Another Team\n"
)
PAGE_TEXT_C = "Acme Corp purchased laptop from the vendor."


class FakeClient:
    """Returns stored page Evidence for the fallback query and one structured relationship for doc C."""

    def __init__(self) -> None:
        self.evidence = {
            DOC_A: [{
                "document_id": DOC_A, "filename": "pan.pdf", "page": 1,
                "evidence_id": "page-1-evidence-a", "raw_text": PAGE_TEXT_A,
                "confidence": 1.0, "extraction_method": "ocr",
                "bbox": None, "normalized_bbox": None,
            }],
            DOC_B: [{
                "document_id": DOC_B, "filename": "other.pdf", "page": 1,
                "evidence_id": "page-1-evidence-b", "raw_text": PAGE_TEXT_B,
                "confidence": 1.0, "extraction_method": "ocr",
                "bbox": None, "normalized_bbox": None,
            }],
            DOC_C: [{
                "document_id": DOC_C, "filename": "invoice.pdf", "page": 1,
                "evidence_id": "page-1-evidence-c", "raw_text": PAGE_TEXT_C,
                "confidence": 1.0, "extraction_method": "text_layer",
                "bbox": None, "normalized_bbox": None,
            }],
        }

    def execute_read(self, query, **parameters):
        document_id = parameters.get("document_id")
        # Fallback-only query signature (page-level Evidence fetch for one document).
        if "-[:HAS_EVIDENCE]->(e:Evidence) WHERE e.raw_text IS NOT NULL" in query:
            return list(self.evidence.get(document_id, []))
        # Structured relationship search for document C only.
        if "reduce(score = 0" in query and document_id == DOC_C:
            return [{
                "source_name": "Acme Corp", "relationship_type": "PURCHASED", "target_name": "laptop",
                "source_entity_id": "Organization:acme corp", "source_entity_type": "Organization",
                "target_entity_id": "Product:laptop", "target_entity_type": "Product",
                "document_id": DOC_C, "filename": "invoice.pdf", "page": 1,
                "evidence_id": "relationship-evidence", "raw_text": "Acme Corp purchased laptop",
                "confidence": 0.9, "extraction_method": "generic_relation_rule",
                "bbox": [1, 2, 3, 4], "normalized_bbox": [0.1, 0.2, 0.3, 0.4], "score": 2,
            }]
        return []


class StubService(DocumentQueryService):
    def __init__(self, client, filenames):
        super().__init__(client)
        self._filenames = filenames

    def get_document(self, document_id, user_id: int | None = None):
        if document_id not in self._filenames:
            raise DocumentNotFound(document_id)
        return {"document_id": document_id, "filename": self._filenames[document_id]}


@pytest.fixture
def service():
    client = FakeClient()
    return StubService(client, {DOC_A: "pan.pdf", DOC_B: "other.pdf", DOC_C: "invoice.pdf"})


def test_fulltext_only_fact_is_retrieved(service):
    """A. A fact present only in stored page evidence text is answered from that text."""
    result = service.answer_question("What is the blood group?", DOC_A)

    assert "Blood Group: O+" in result["answer"]
    assert "page 1" in result["answer"]
    assert result["document_id"] == DOC_A
    assert result["matched_entities"] == []
    assert result["matched_relationships"] == []
    assert len(result["evidence"]) == 1
    evidence = result["evidence"][0]
    assert evidence["evidence_id"] == "page-1-evidence-a"
    assert evidence["page"] == 1
    assert evidence["extraction_method"] == "ocr"
    assert evidence["confidence"] == 1.0
    assert "Blood Group" in evidence["raw_text"]


def test_fulltext_fact_does_not_leak_across_documents(service):
    """B. The same question scoped to another document must not return the first document's fact."""
    result = service.answer_question("What is the blood group?", DOC_B)

    assert result["answer"] == NO_MATCH_ANSWER
    assert "O+" not in result["answer"]
    assert result["document_id"] == DOC_B
    assert result["evidence"] == []


def test_structured_answer_takes_precedence_over_fallback(service):
    """C. When a structured fact exists, the verbatim fallback never overrides it."""
    result = service.answer_question("Who purchased laptop?", DOC_C)

    assert result["answer"] == "Acme Corp purchased laptop."
    assert result["evidence"][0]["evidence_id"] == "relationship-evidence"
    assert result["matched_relationships"][0]["relationship_type"] == "PURCHASED"


def test_unrelated_question_returns_no_answer(service):
    """D. A question with no support in the document still returns the existing no-answer response."""
    result = service.answer_question("What is the quantum flux capacitor calibration?", DOC_A)

    assert result["answer"] == NO_MATCH_ANSWER
    assert result["matched_entities"] == []
    assert result["matched_relationships"] == []
    assert result["evidence"] == []


def test_global_question_without_document_id_is_unchanged(service):
    """E. Without a document_id the fallback is never attempted and global behavior is preserved."""
    result = service.answer_question("What is the blood group?")

    assert result["answer"] == NO_MATCH_ANSWER_GLOBAL
    assert result["document_id"] is None
    assert result["matched_entities"] == []
    assert result["matched_relationships"] == []
    assert result["evidence"] == []
