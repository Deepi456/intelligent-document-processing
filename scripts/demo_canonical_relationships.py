import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge_graph.neo4j_client import Neo4jClient


QUERY = """
MATCH (organization:CanonicalOrganization {canonical_name: $organization})-[relationship]->(target)
WHERE type(relationship) IN ["PURCHASED", "SUPPLIED_BY"]
OPTIONAL MATCH (document:Document {document_id: relationship.source_document_id})
OPTIONAL MATCH (page:DocumentPage {
    document_id: relationship.source_document_id,
    page_number: relationship.page_number
})
OPTIONAL MATCH (page)-[:HAS_EVIDENCE]->(evidence:Evidence {
    evidence_id: relationship.evidence_id
})
WITH organization, relationship, target,
     document, evidence,
     target.canonical_name AS target_name
RETURN organization.canonical_name AS organization,
       type(relationship) AS relationship,
       target_name AS target,
       relationship.source_document_id AS source_document_id,
       document.filename AS source_document,
       relationship.page_number AS page_number,
       relationship.evidence_id AS evidence_id,
       relationship.confidence AS confidence,
       relationship.extraction_method AS extraction_method,
       evidence.raw_text AS evidence_text
ORDER BY relationship, target_name
"""


def main() -> int:
    client = Neo4jClient()
    try:
        rows = client.execute_read(QUERY, organization="ABC Corporation")
        print("CANONICAL RELATIONSHIPS")
        print("=======================")
        if not rows:
            print("No canonical relationships found")
        for row in rows:
            print(row)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
