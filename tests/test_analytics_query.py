"""Regression tests for the user-scoped analytics Cypher (GET /analytics).

The original query referenced the outer variable `d` inside CALL subqueries
without importing it, which Neo4j rejects with CypherSyntaxError
("Variable `d` not defined") at runtime. That surfaced to the dashboard as
503 "Neo4j is unavailable" even with a healthy database. These tests pin the
required Cypher structure so the bug cannot silently return.
"""
import os
import sys
import uuid

import pytest

# Make the repository root importable when running the bare `pytest` console
# script (same bootstrap as tests/test_api.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a unique test database for each test run (set before importing the app).
test_db_path = f"./test_analytics_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

from fastapi.testclient import TestClient  # noqa: E402

import app.auth.database as auth_db  # noqa: E402
from app.api.main import app, get_neo4j_client  # noqa: E402
from app.api.service import DocumentQueryService  # noqa: E402
from app.auth.auth_service import create_access_token  # noqa: E402
from app.auth.database import Base, User, get_db  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

ANALYTICS_SESSION_LOCAL = auth_db.SessionLocal

Base.metadata.create_all(bind=auth_db.engine)

db = ANALYTICS_SESSION_LOCAL()
try:
    if not db.query(User).filter(User.id == 7).first():
        db.add(User(
            id=7,
            email="analytics-regression@example.com",
            full_name="Analytics Regression",
            password_hash="$2b$12$wGvnYZouwpFYOinJKffxZ.bhYNU0n5sl6fs1rFGtNllz16fS3q2q6",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
finally:
    db.close()

TOKEN = create_access_token({"sub": 7, "email": "analytics-regression@example.com"})
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def override_analytics_db():
    db = ANALYTICS_SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def analytics_database_override():
    app.dependency_overrides[get_db] = override_analytics_db
    yield
    app.dependency_overrides.pop(get_db, None)


class RecordingClient:
    """Fake Neo4j client that records queries and returns plausible rows."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute_read(self, query: str, **parameters):
        self.queries.append(query)
        if "count(d) AS document_count" in query:
            return [{"document_count": 2}]
        return [{"entity_count": 5, "evidence_count": 4, "relationship_count": 1}]

    def execute_write(self, query: str, **parameters) -> None:
        self.queries.append(query)

    def close(self) -> None:
        pass


def _captured_queries(monkeypatch) -> list[str]:
    client = RecordingClient()

    def override_client():
        yield client

    monkeypatch.setitem(app.dependency_overrides, get_neo4j_client, override_client)
    response = TestClient(app).get("/analytics", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "document_count": 2,
        "entity_count": 5,
        "evidence_count": 4,
        "relationship_count": 1,
    }
    return client.queries


def test_analytics_user_scoped_subqueries_import_outer_variable(monkeypatch):
    """Every CALL subquery over `d` must import it (WITH d / CALL (d))."""
    import re

    queries = _captured_queries(monkeypatch)
    scoped = [q for q in queries if "CALL {" in q and "user_id" in q]
    assert scoped, "expected the user-scoped analytics query to use CALL subqueries"
    for query in scoped:
        for subquery in re.findall(r"CALL\s*\{(.*?)\}", query, flags=re.DOTALL):
            if "(doc)-[:CONTAINS]" in subquery or "(doc)-[:HAS_PAGE]" in subquery:
                assert "WITH d" in subquery, (
                    "CALL subquery must import the outer variable `d`; "
                    f"missing import caused CypherSyntaxError in production: {subquery!r}"
                )


def test_analytics_relationship_subquery_uses_imported_document(monkeypatch):
    """The relationship subquery must reference d.document_id via the import."""
    queries = _captured_queries(monkeypatch)
    scoped = [q for q in queries if "relationship_count" in q and "CALL {" in q]
    assert scoped
    for query in scoped:
        assert "WITH d MATCH (source)-[r]->(target)" in query
        assert "r.source_document_id = d.document_id" in query
        # Aggregation must yield exactly one row (sum over per-document rows).
        assert "sum(entity_count) AS entity_count" in query
        assert "sum(evidence_count) AS evidence_count" in query
        assert "sum(relationship_count) AS relationship_count" in query


def test_analytics_endpoint_contract_unchanged(monkeypatch):
    """The endpoint still returns the AnalyticsResponse contract."""
    response = TestClient(app).get("/analytics", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"document_count", "entity_count", "evidence_count", "relationship_count"}
