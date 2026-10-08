import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge_graph.neo4j_client import Neo4jClient


QUERIES = {
    "DOCUMENTS_AND_MENTIONS": """
        MATCH (d:Document)-[:CONTAINS]->(m:EntityMention)
        RETURN d.filename AS document,
               m.mention_id AS mention_id,
               m.raw_text AS mention,
               m.entity_type AS entity_type,
               m.page_number AS page
        ORDER BY document, mention_id
    """,
    "MENTIONS_AND_CANONICAL_ENTITIES": """
        MATCH (m:EntityMention)-[:RESOLVED_TO]->(c)
        RETURN m.mention_id AS mention_id,
               m.raw_text AS mention,
               m.entity_type AS entity_type,
               c.canonical_id AS canonical_id,
               c.canonical_name AS canonical_name,
               c.resolution_status AS resolution_status
        ORDER BY mention_id
    """,
    "SHARED_CANONICAL_ENTITIES": """
        MATCH (m:EntityMention)-[:RESOLVED_TO]->(c)
        WITH c, collect(m) AS mentions
        WHERE size(mentions) > 1
        RETURN c.canonical_id AS canonical_id,
               c.canonical_name AS canonical_name,
               c.entity_type AS entity_type,
               size(mentions) AS mention_count
        ORDER BY mention_count DESC, canonical_id
    """,
    "DOCUMENTS_FOR_SHARED_ENTITIES": """
        MATCH (d:Document)-[:CONTAINS]->(m:EntityMention)-[:RESOLVED_TO]->(c)
        WITH c, collect(DISTINCT {
            document: d.filename,
            mention_id: m.mention_id,
            raw_text: m.raw_text,
            page: m.page_number
        }) AS mentions
        WHERE size(mentions) > 1
        RETURN c.canonical_id AS canonical_id,
               c.canonical_name AS canonical_name,
               mentions
        ORDER BY canonical_id
    """,
}


def main() -> int:
    client = Neo4jClient()
    try:
        for title, query in QUERIES.items():
            print(f"\n{title}")
            print("=" * len(title))
            rows = client.execute_read(query)
            if not rows:
                print("No results")
            for row in rows:
                print(row)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
