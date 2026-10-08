from fastapi.testclient import TestClient
import os
import uuid
import sys

# Make the repository root importable when running the bare `pytest` console
# script (`python -m pytest` adds the CWD to sys.path; the script does not).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Use a unique test database for each test run
test_db_path = f"./test_app_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Now import everything after setting the environment variable
import app.api.main as api_main
from app.api.main import app, get_neo4j_client
from app.auth.auth_service import create_access_token
from app.auth.database import get_db, SessionLocal, User, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

# Create test engine
test_engine = create_engine(
    f"sqlite:///{test_db_path}",
    connect_args={"check_same_thread": False},
)

# Override SessionLocal in the database module
import app.auth.database as auth_db_module
auth_db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
auth_db_module.engine = test_engine

# Initialize database
Base.metadata.create_all(bind=test_engine)

# Create test user with a pre-computed bcrypt hash
TEST_PASSWORD_HASH = "$2b$12$wGvnYZouwpFYOinJKffxZ.bhYNU0n5sl6fs1rFGtNllz16fS3q2q6"

db = auth_db_module.SessionLocal()
try:
    # Check if user already exists
    existing = db.query(User).filter(User.id == 1).first()
    if not existing:
        test_user = User(
            id=1,
            email="test@example.com",
            full_name="Test User",
            password_hash=TEST_PASSWORD_HASH,
            created_at=datetime.now(timezone.utc),
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
    existing_other = db.query(User).filter(User.id == 2).first()
    if not existing_other:
        other_user = User(
            id=2,
            email="other@example.com",
            full_name="Other User",
            password_hash=TEST_PASSWORD_HASH,
            created_at=datetime.now(timezone.utc),
        )
        db.add(other_user)
        db.commit()
finally:
    db.close()

# Create auth token for testing
TEST_TOKEN = create_access_token({"sub": 1, "email": "test@example.com"})


DOCUMENT_ID = "C:/documents/invoice.pdf"
LEGACY_DOCUMENT_ID = "C:/documents/legacy.pdf"


class FakeClient:
    def execute_read(self, query, **parameters):
        # Query: analytics document count (user-scoped)
        # "MATCH (d:Document) WHERE d.document_id IS NOT NULL AND (d.user_id IS NULL OR d.user_id = $user_id) RETURN count(d) AS document_count"
        if "count(d) AS document_count" in query:
            return [{"document_count": 0}]

        # Query: analytics entity/evidence/relationship counts (user-scoped or global)
        # scoped: "... CALL { WITH d ... } RETURN sum(entity_count) AS entity_count, ..."
        # global: "... CALL { ... } RETURN document_count, entity_count, evidence_count, relationship_count"
        if "entity_count" in query and "evidence_count" in query:
            return [{"entity_count": 0, "evidence_count": 0, "relationship_count": 0}]

        # Query: list_documents with user_id filter
        # "MATCH (d:Document) WHERE d.document_id IS NOT NULL AND (d.user_id IS NULL OR d.user_id = $user_id) RETURN ..."
        if "MATCH (d:Document) WHERE d.document_id IS NOT NULL" in query and "user_id" in query:
            user_id = parameters.get("user_id")
            # Return mock document with user_id for ownership check
            return [{"document_id": DOCUMENT_ID, "filename": "invoice.pdf", "file_name": "invoice.pdf", 
                     "document_type": "pdf", "source": "upload", "user_id": user_id}]

        # Query: list_documents without user_id filter
        # "MATCH (d:Document) WHERE d.document_id IS NOT NULL RETURN ..."
        if "MATCH (d:Document) WHERE d.document_id IS NOT NULL" in query:
            return [{"document_id": DOCUMENT_ID, "filename": "invoice.pdf", "file_name": "invoice.pdf",
                     "document_type": "pdf", "source": "upload"}]

        if "d.user_id AS user_id" in query:
            doc_id = parameters.get("document_id")
            user_id = parameters.get("user_id")
            if doc_id == DOCUMENT_ID and user_id == 2:
                return []
            if doc_id == LEGACY_DOCUMENT_ID:
                return [{"document_id": LEGACY_DOCUMENT_ID, "filename": "legacy.pdf", "file_name": "legacy.pdf",
                         "document_type": "pdf", "source": "legacy", "user_id": None}]
            return [{"document_id": DOCUMENT_ID, "filename": "invoice.pdf", "file_name": "invoice.pdf",
                     "document_type": "pdf", "source": "upload", "user_id": 1}]

        # Query: get_graph entity existence check
        # "MATCH (entity {canonical_id: $entity_id}) RETURN entity.canonical_id AS canonical_id, ..."
        if "MATCH (entity {canonical_id:" in query and "OPTIONAL MATCH" not in query:
            return [{"canonical_id": parameters.get("entity_id"),
                     "canonical_name": "Acme Corp", "entity_type": "Organization"}]

        # Query: get_document (must not swallow the [:CONTAINS]/[:HAS_PAGE] traversals below)
        # "MATCH (d:Document {document_id: $document_id}) RETURN ..."
        if "MATCH (d:Document {document_id:" in query and "d.user_id AS user_id" not in query and "-[:CONTAINS]->" not in query and "-[:HAS_PAGE]->" not in query:
            doc_id = parameters.get("document_id")
            user_id = parameters.get("user_id")
            if doc_id == "missing" or (doc_id == DOCUMENT_ID and user_id == 2):
                return []
            if doc_id == LEGACY_DOCUMENT_ID:
                return [{"document_id": LEGACY_DOCUMENT_ID, "filename": "legacy.pdf", "file_name": "legacy.pdf",
                         "document_type": "pdf", "source": "legacy", "user_id": None}]
            return [{"document_id": DOCUMENT_ID, "filename": "invoice.pdf", "file_name": "invoice.pdf",
                     "document_type": "pdf", "source": "upload", "user_id": 1}]

        # Query: document-scoped graph entities, including entities without relationships
        if "coalesce(c.canonical_id, m.mention_id) AS entity_id" in query:
            return [
                {"entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization"},
                {"entity_id": "Product:standalone", "name": "Standalone Product", "entity_type": "Product"},
            ]

        # Query: get_entities
        # "MATCH (d:Document {document_id: $document_id})-[:CONTAINS]->(m:EntityMention) ..."
        if "[:CONTAINS]->(m:EntityMention)" in query:
            terms = [t.casefold() for t in (parameters.get("terms") or [])]
            searchable = "acme corp laptop organization"
            if terms and not any(t in searchable for t in terms):
                return []
            return [{
                "mention_id": "mention-1", "entity_id": "Organization:acme", "canonical_id": "Organization:acme",
                "canonical_name": "Acme Corp", "name": "Acme Corp", "entity_type": "Organization",
                "page_number": 1, "page": 1, "confidence": 0.9, "extraction_method": "receipt_rule",
                "document_id": DOCUMENT_ID, "filename": "invoice.pdf", "normalized_text": "Acme Corp",
                "raw_text": "Acme Corp purchased laptop", "evidence_id": "evidence-1",
            }]

        # Query: get_relationships (document endpoint)
        # "MATCH (source)-[r]->(target) WHERE r.source_document_id = $document_id AND r.evidence_id IS NOT NULL ..."
        if "WHERE r.source_document_id = $document_id" in query and "relationship_type" in query:
            return [{
                "source_document_id": DOCUMENT_ID,
                "relationship_type": "PURCHASED",
                "extracted_relationship_type": "PURCHASED",
                "source_entity": {"entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization"},
                "target_entity": {"entity_id": "Product:laptop", "name": "laptop", "entity_type": "Product"},
                "page_number": 1, "evidence_id": "evidence-1", "confidence": 1.0,
                "extraction_method": "relationship_rule",
            }]

        # Query: scoped relationship search used by the answer pipeline
        # "... WHERE r.evidence_id IS NOT NULL AND ($document_id IS NULL OR r.source_document_id = $document_id) ..."
        if "$document_id IS NULL OR r.source_document_id" in query:
            terms = [t.casefold() for t in (parameters.get("terms") or [])]
            searchable = "acme corp purchased laptop"
            if terms and not any(t in searchable for t in terms):
                return []
            return [{
                "relationship_type": "PURCHASED",
                "source_name": "Acme Corp", "target_name": "laptop",
                "source_entity_id": "Organization:acme", "source_entity_type": "Organization",
                "target_entity_id": "Product:laptop", "target_entity_type": "Product",
                "document_id": DOCUMENT_ID, "filename": "invoice.pdf", "page": 1,
                "evidence_id": "evidence-1", "raw_text": "Acme Corp purchased laptop",
                "confidence": 1.0, "extraction_method": "relationship_rule",
                "bbox": [1, 2, 3, 4], "normalized_bbox": [0.1, 0.2, 0.3, 0.4],
            }]

        # Query: get_evidence
        # "MATCH (d:Document {document_id: $document_id})-[:HAS_PAGE]->(p)-[:HAS_EVIDENCE]->(ev) ..."
        if "[:HAS_PAGE]->" in query and "[:HAS_EVIDENCE]->" in query:
            return [{
                "document_id": DOCUMENT_ID, "filename": "invoice.pdf",
                "evidence_id": "evidence-1", "page": 1, "raw_text": "Acme Corp purchased laptop",
                "confidence": 0.9, "extraction_method": "receipt_rule",
                "bbox": [1, 2, 3, 4], "normalized_bbox": [0.1, 0.2, 0.3, 0.4],
            }]

        # Query: get_graph relationship rows for an entity (user-scoped or not)
        # "MATCH (entity {canonical_id: $entity_id}) OPTIONAL MATCH (entity)-[r]-(connected) ..."
        if "MATCH (entity {canonical_id:" in query and "OPTIONAL MATCH" in query:
            return [{
                "entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization",
                "source_document_id": DOCUMENT_ID,
                "relationship_type": "PURCHASED",
                "extracted_relationship_type": "PURCHASED",
                "source_entity": {"entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization"},
                "target_entity": {"entity_id": "Product:laptop", "name": "laptop", "entity_type": "Product"},
                "page_number": 1, "evidence_id": "evidence-1", "confidence": 1.0,
                "extraction_method": "relationship_rule",
            }]

        # Query: get_graph_overview with user_id
        # "MATCH (source)-[r]->(target) WHERE r.evidence_id IS NOT NULL AND r.source_document_id IN $document_ids ..."
        if "r.source_document_id IN $" in query and "relationship_type" in query:
            return [{
                "entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization",
                "source_document_id": DOCUMENT_ID,
                "relationship_type": "PURCHASED",
                "extracted_relationship_type": "PURCHASED",
                "source_entity": {"entity_id": "Organization:acme", "name": "Acme Corp", "entity_type": "Organization"},
                "target_entity": {"entity_id": "Product:laptop", "name": "laptop", "entity_type": "Product"},
                "page_number": 1, "evidence_id": "evidence-1", "confidence": 1.0,
                "extraction_method": "relationship_rule",
            }]

    def execute_write(self, query, **parameters):
        pass

    def close(self):
        pass


def override_client():
    client = FakeClient()
    try:
        yield client
    finally:
        client.close()


app.dependency_overrides[get_neo4j_client] = override_client

# Create auth token for testing
TEST_TOKEN = create_access_token({"sub": 1, "email": "test@example.com"})
TEST_USER_B_TOKEN = create_access_token({"sub": 2, "email": "other@example.com"})

client = TestClient(app)


def test_health_and_document_endpoints():
    assert client.get("/health").json() == {"status": "ok"}
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    assert client.get("/documents", headers=headers).json()[0]["document_id"] == DOCUMENT_ID
    assert client.get(f"/documents/{DOCUMENT_ID}", headers=headers).json()["filename"] == "invoice.pdf"
    assert client.get(f"/documents/{DOCUMENT_ID}/entities", headers=headers).json()[0]["canonical_id"] == "Organization:acme"
    assert client.get(f"/documents/{DOCUMENT_ID}/relationships", headers=headers).json()[0]["evidence_id"] == "evidence-1"
    assert client.get(f"/documents/{DOCUMENT_ID}/evidence", headers=headers).json()[0]["normalized_bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert client.get("/graph/Organization:acme", headers=headers).json()["relationships"][0]["relationship_type"] == "PURCHASED"


def test_other_user_cannot_access_owned_document_resources():
    headers = {"Authorization": f"Bearer {TEST_USER_B_TOKEN}"}
    paths = (
        f"/documents/{DOCUMENT_ID}",
        f"/documents/{DOCUMENT_ID}/entities",
        f"/documents/{DOCUMENT_ID}/relationships",
        f"/documents/{DOCUMENT_ID}/evidence",
    )
    for path in paths:
        assert client.get(path, headers=headers).status_code == 404

    response = client.post(
        "/query",
        headers=headers,
        json={"question": "Who purchased laptop?", "document_id": DOCUMENT_ID},
    )
    assert response.status_code == 404


def test_legacy_document_remains_accessible_to_authenticated_user():
    headers = {"Authorization": f"Bearer {TEST_USER_B_TOKEN}"}
    response = client.get(f"/documents/{LEGACY_DOCUMENT_ID}", headers=headers)
    assert response.status_code == 200
    assert response.json()["document_id"] == LEGACY_DOCUMENT_ID


def test_graph_overview_and_analytics_endpoints():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    graph_response = client.get("/graph", headers=headers)
    analytics_response = client.get("/analytics", headers=headers)

    assert graph_response.status_code == 200
    assert graph_response.json()["entities"][0]["entity_id"] == "Organization:acme"
    assert graph_response.json()["relationships"][0]["relationship_type"] == "PURCHASED"
    assert analytics_response.status_code == 200
    assert analytics_response.json() == {
        "document_count": 0,
        "entity_count": 0,
        "evidence_count": 0,
        "relationship_count": 0,
    }


def test_document_scoped_graph_includes_only_selected_document_entities_and_relationships():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.get(f"/graph?document_id={DOCUMENT_ID}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert {entity["entity_id"] for entity in body["entities"]} == {
        "Organization:acme", "Product:standalone"
    }
    assert {relationship["source_document_id"] for relationship in body["relationships"]} == {DOCUMENT_ID}


def test_other_user_cannot_access_document_scoped_graph():
    headers = {"Authorization": f"Bearer {TEST_USER_B_TOKEN}"}
    response = client.get(f"/graph?document_id={DOCUMENT_ID}", headers=headers)
    assert response.status_code == 404


def test_legacy_document_can_be_used_as_document_graph_scope():
    headers = {"Authorization": f"Bearer {TEST_USER_B_TOKEN}"}
    response = client.get(f"/graph?document_id={LEGACY_DOCUMENT_ID}", headers=headers)
    assert response.status_code == 200


def test_missing_document_returns_not_found():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.get("/documents/missing", headers=headers)
    assert response.status_code == 404


def test_query_returns_answer_with_evidence():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.post("/query", headers=headers, json={"question": "Who purchased laptop?"})
    assert response.status_code == 200
    assert response.json()["question"] == "Who purchased laptop?"
    assert response.json()["answer"] == "Acme Corp purchased laptop."
    assert response.json()["matched_relationships"][0]["relationship_type"] == "PURCHASED"
    assert response.json()["matched_entities"][0]["name"] == "Acme Corp"
    assert response.json()["evidence"][0]["filename"] == "invoice.pdf"
    assert response.json()["evidence"][0]["page"] == 1
    assert response.json()["evidence"][0]["evidence_id"] == "evidence-1"


def test_entity_question_returns_entities_and_provenance():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.post("/query", headers=headers, json={"question": "What entities are mentioned in this document?"})
    assert response.status_code == 200
    assert response.json()["matched_entities"][0]["name"] == "Acme Corp"
    assert response.json()["matched_relationships"] == []
    assert response.json()["evidence"][0]["extraction_method"] == "receipt_rule"


def test_query_returns_clear_no_result_message():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.post("/query", headers=headers, json={"question": "What did the moon purchase?"})
    assert response.status_code == 200
    assert response.json()["answer"] == "No matching evidence was found in the processed documents."
    assert response.json()["matched_entities"] == []
    assert response.json()["matched_relationships"] == []
    assert response.json()["evidence"] == []


def test_upload_validates_and_returns_processing_result(monkeypatch):
    processed_paths = []

    def fake_process_document(path):
        processed_paths.append(path)
        assert path.parent.parent.name == "uploads"
        assert path.read_bytes() == b"not-real-processing-input"
        return {
            "document_id": str(path),
            "filename": path.name,
            "status": "processed",
            "pages": 1,
            "entities": 2,
            "relationships": 1,
        }

    monkeypatch.setattr(api_main, "process_document", fake_process_document)
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("upload.pdf", b"not-real-processing-input", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "upload.pdf"
    assert response.json()["status"] == "processed"
    assert len(processed_paths) == 1 


def test_upload_rejects_unsupported_file_type():
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("notes.txt", b"not supported", "text/plain")},
    )
    assert response.status_code == 415
