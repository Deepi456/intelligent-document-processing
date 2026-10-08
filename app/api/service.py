import re
import unicodedata
from typing import Any

from app.knowledge_graph.neo4j_client import Neo4jClient
from app.nlp.layout_analyzer import _is_plausible_value


class DocumentNotFound(Exception):
    pass


class EntityNotFound(Exception):
    pass


class DocumentQueryService:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def list_documents(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """
        List documents, optionally filtered by user_id.
        Legacy documents without user_id are included for backward compatibility.
        """
        if user_id is not None:
            rows = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "AND (d.user_id IS NULL OR d.user_id = $user_id) "
                "RETURN d.document_id AS document_id, d.filename AS filename, "
                "d.file_name AS file_name, d.document_type AS document_type, d.source AS source "
                "ORDER BY d.filename",
                user_id=user_id,
            )
        else:
            rows = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "RETURN d.document_id AS document_id, d.filename AS filename, "
                "d.file_name AS file_name, d.document_type AS document_type, d.source AS source "
                "ORDER BY d.filename"
            )
        return rows

    def get_document(self, document_id: str, user_id: int | None = None) -> dict[str, Any]:
        """
        Get a document by ID, optionally checking user ownership.
        """
        query = "MATCH (d:Document {document_id: $document_id}) "
        if user_id is not None:
            query += "WHERE d.user_id IS NULL OR d.user_id = $user_id "
        query += (
            "RETURN d.document_id AS document_id, d.filename AS filename, "
            "d.file_name AS file_name, d.document_type AS document_type, d.source AS source, "
            "d.user_id AS user_id"
        )
        parameters = {"document_id": document_id}
        if user_id is not None:
            parameters["user_id"] = user_id
        rows = self.client.execute_read(query, **parameters)
        if not rows:
            raise DocumentNotFound(document_id)

        return rows[0]

    def get_entities(self, document_id: str) -> list[dict[str, Any]]:
        self.get_document(document_id)
        return self.client.execute_read(
            "MATCH (d:Document {document_id: $document_id})-[:CONTAINS]->(m:EntityMention) "
            "OPTIONAL MATCH (m)-[:RESOLVED_TO]->(c) "
            "OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(ev:Evidence) "
            "RETURN d.document_id AS document_id, m.mention_id AS mention_id, "
            "c.canonical_id AS canonical_id, ev.evidence_id AS evidence_id, "
            "c.canonical_name AS canonical_name, m.normalized_text AS normalized_text, "
            "m.entity_type AS entity_type, m.page_number AS page_number, "
            "m.confidence AS confidence, m.extraction_method AS extraction_method, "
            "m.raw_text AS name "
            "ORDER BY m.page_number, m.mention_id",
            document_id=document_id,
        )

    def get_relationships(self, document_id: str) -> list[dict[str, Any]]:
        self.get_document(document_id)
        rows = self.client.execute_read(
            "MATCH (source)-[r]->(target) "
            "WHERE r.source_document_id = $document_id "
            "AND r.evidence_id IS NOT NULL "
            "RETURN r.source_document_id AS source_document_id, "
            "type(r) AS relationship_type, r.relationship_type AS extracted_relationship_type, "
            "{entity_id: coalesce(source.canonical_id, source.entity_id), "
            "name: coalesce(source.canonical_name, source.name), "
            "entity_type: source.entity_type} AS source_entity, "
            "{entity_id: coalesce(target.canonical_id, target.entity_id), "
            "name: coalesce(target.canonical_name, target.name), "
            "entity_type: target.entity_type} AS target_entity, "
            "r.page_number AS page_number, r.evidence_id AS evidence_id, "
            "r.confidence AS confidence, r.extraction_method AS extraction_method "
            "ORDER BY r.page_number, relationship_type",
            document_id=document_id,
        )
        return [_with_extracted_relationship_type(row) for row in rows]

    def get_evidence(self, document_id: str) -> list[dict[str, Any]]:
        self.get_document(document_id)
        return self.client.execute_read(
            "MATCH (d:Document {document_id: $document_id})-[:HAS_PAGE]->(p:DocumentPage)-[:HAS_EVIDENCE]->(e:Evidence) "
            "RETURN d.document_id AS document_id, e.evidence_id AS evidence_id, p.page_number AS page, "
            "e.raw_text AS raw_text, e.confidence AS confidence, "
            "e.extraction_method AS extraction_method, e.bbox AS bbox, "
            "e.normalized_bbox AS normalized_bbox "
            "ORDER BY page, evidence_id",
            document_id=document_id,
        )

    def get_graph_overview(self, document_id: str | None = None, user_id: int | None = None) -> dict[str, list[dict[str, Any]]]:
        """
        Get graph overview, optionally filtered by user's documents.
        """
        entities = {}
        if document_id is not None:
            self.get_document(document_id, user_id=user_id)
            entity_rows = self.client.execute_read(
                "MATCH (d:Document {document_id: $document_id})-[:CONTAINS]->(m:EntityMention) "
                "OPTIONAL MATCH (m)-[:RESOLVED_TO]->(c) "
                "RETURN coalesce(c.canonical_id, m.mention_id) AS entity_id, "
                "coalesce(c.canonical_name, m.raw_text) AS name, "
                "m.entity_type AS entity_type",
                document_id=document_id,
            )
            rows = self.client.execute_read(
                "MATCH (source)-[r]->(target) "
                "WHERE r.evidence_id IS NOT NULL "
                "AND r.source_document_id = $document_id "
                "AND coalesce(source.canonical_id, source.entity_id) IS NOT NULL "
                "AND coalesce(target.canonical_id, target.entity_id) IS NOT NULL "
                "RETURN {entity_id: coalesce(source.canonical_id, source.entity_id), "
                "name: coalesce(source.canonical_name, source.name), "
                "entity_type: source.entity_type} AS source_entity, "
                "{entity_id: coalesce(target.canonical_id, target.entity_id), "
                "name: coalesce(target.canonical_name, target.name), "
                "entity_type: target.entity_type} AS target_entity, "
                "type(r) AS relationship_type, r.relationship_type AS extracted_relationship_type, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
                document_id=document_id,
            )
            entities = {row["entity_id"]: {
                "entity_id": row["entity_id"], "name": row.get("name"), "entity_type": row.get("entity_type")
            } for row in entity_rows}
        elif user_id is not None:
            # Get documents for this user (including legacy docs)
            user_docs = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "AND (d.user_id IS NULL OR d.user_id = $user_id) "
                "RETURN d.document_id AS document_id",
                user_id=user_id,
            )
            user_doc_ids = [doc["document_id"] for doc in user_docs]

            if not user_doc_ids:
                return {"entities": [], "relationships": []}

            rows = self.client.execute_read(
                "MATCH (source)-[r]->(target) "
                "WHERE r.evidence_id IS NOT NULL "
                "AND r.source_document_id IN $document_ids "
                "AND coalesce(source.canonical_id, source.entity_id) IS NOT NULL "
                "AND coalesce(target.canonical_id, target.entity_id) IS NOT NULL "
                "RETURN {entity_id: coalesce(source.canonical_id, source.entity_id), "
                "name: coalesce(source.canonical_name, source.name), "
                "entity_type: source.entity_type} AS source_entity, "
                "{entity_id: coalesce(target.canonical_id, target.entity_id), "
                "name: coalesce(target.canonical_name, target.name), "
                "entity_type: target.entity_type} AS target_entity, "
                "type(r) AS relationship_type, r.relationship_type AS extracted_relationship_type, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
                document_ids=user_doc_ids,
            )
        elif document_id is not None:
            rows = self.client.execute_read(
                "MATCH (source)-[r]->(target) "
                "WHERE r.evidence_id IS NOT NULL "
                "AND r.source_document_id = $document_id "
                "AND coalesce(source.canonical_id, source.entity_id) IS NOT NULL "
                "AND coalesce(target.canonical_id, target.entity_id) IS NOT NULL "
                "RETURN {entity_id: coalesce(source.canonical_id, source.entity_id), "
                "name: coalesce(source.canonical_name, source.name), "
                "entity_type: source.entity_type} AS source_entity, "
                "{entity_id: coalesce(target.canonical_id, target.entity_id), "
                "name: coalesce(target.canonical_name, target.name), "
                "entity_type: target.entity_type} AS target_entity, "
                "type(r) AS relationship_type, r.relationship_type AS extracted_relationship_type, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
                document_id=document_id,
            )
        else:
            rows = self.client.execute_read(
                "MATCH (source)-[r]->(target) "
                "WHERE r.evidence_id IS NOT NULL "
                "AND coalesce(source.canonical_id, source.entity_id) IS NOT NULL "
                "AND coalesce(target.canonical_id, target.entity_id) IS NOT NULL "
                "RETURN {entity_id: coalesce(source.canonical_id, source.entity_id), "
                "name: coalesce(source.canonical_name, source.name), "
                "entity_type: source.entity_type} AS source_entity, "
                "{entity_id: coalesce(target.canonical_id, target.entity_id), "
                "name: coalesce(target.canonical_name, target.name), "
                "entity_type: target.entity_type} AS target_entity, "
                "type(r) AS relationship_type, r.relationship_type AS extracted_relationship_type, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
            )

        relationships = []
        for row in rows:
            source = row["source_entity"]
            target = row["target_entity"]
            entities[source["entity_id"]] = source
            entities[target["entity_id"]] = target
            relationships.append({key: row.get(key) for key in (
                "relationship_type", "source_document_id", "source_entity", "target_entity", "page_number",
                "evidence_id", "confidence", "extraction_method",
            )})
            relationships[-1]["relationship_type"] = row.get("extracted_relationship_type") or row.get("relationship_type")
        return {"entities": list(entities.values()), "relationships": relationships}

    def get_analytics(self, user_id: int | None = None) -> dict[str, int]:
        """
        Get analytics, optionally filtered by user's documents.
        """
        if user_id is not None:
            # Get document count for user (including legacy docs)
            doc_count_result = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "AND (d.user_id IS NULL OR d.user_id = $user_id) "
                "RETURN count(d) AS document_count",
                user_id=user_id,
            )
            document_count = doc_count_result[0]["document_count"] if doc_count_result else 0

            # Get entity, evidence, relationship counts for user's documents.
            # Each CALL subquery must import the outer variable `d` (Cypher
            # scoping rule) and return its own row, aggregated with sum().
            other_counts = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "AND (d.user_id IS NULL OR d.user_id = $user_id) "
                "CALL { WITH d MATCH (doc)-[:CONTAINS]->(m:EntityMention) WHERE doc = d "
                "RETURN count(m) AS entity_count } "
                "CALL { WITH d MATCH (doc)-[:HAS_PAGE]->(p:DocumentPage)-[:HAS_EVIDENCE]->(e:Evidence) WHERE doc = d "
                "RETURN count(e) AS evidence_count } "
                "CALL { WITH d MATCH (source)-[r]->(target) WHERE r.source_document_id = d.document_id "
                "AND r.evidence_id IS NOT NULL RETURN count(r) AS relationship_count } "
                "RETURN sum(entity_count) AS entity_count, sum(evidence_count) AS evidence_count, "
                "sum(relationship_count) AS relationship_count",
                user_id=user_id,
            )
            if other_counts:
                return {
                    "document_count": document_count,
                    "entity_count": other_counts[0]["entity_count"],
                    "evidence_count": other_counts[0]["evidence_count"],
                    "relationship_count": other_counts[0]["relationship_count"],
                }
            return {
                "document_count": document_count,
                "entity_count": 0,
                "evidence_count": 0,
                "relationship_count": 0,
            }
        else:
            counts = self.client.execute_read(
                "CALL { MATCH (d:Document) RETURN count(d) AS document_count } "
                "CALL { MATCH (m:EntityMention) RETURN count(m) AS entity_count } "
                "CALL { MATCH (e:Evidence) RETURN count(e) AS evidence_count } "
                "CALL { MATCH ()-[r]->() WHERE r.evidence_id IS NOT NULL "
                "RETURN count(r) AS relationship_count } "
                "RETURN document_count, entity_count, evidence_count, relationship_count"
            )
            return counts[0] if counts else {
                "document_count": 0,
                "entity_count": 0,
                "evidence_count": 0,
                "relationship_count": 0,
            }

    def get_graph(self, entity_id: str, user_id: int | None = None) -> dict[str, Any]:
        """
        Get graph for an entity, optionally filtered by user's documents.
        """
        # First get the entity to check if it exists
        entity_rows = self.client.execute_read(
            "MATCH (entity {canonical_id: $entity_id}) "
            "RETURN entity.canonical_id AS canonical_id, entity.canonical_name AS canonical_name, "
            "entity.entity_type AS entity_type",
            entity_id=entity_id,
        )
        if not entity_rows:
            raise EntityNotFound(entity_id)

        entity = entity_rows[0]

        # Build the query based on whether we're filtering by user
        if user_id is not None:
            # Get documents for this user
            user_docs = self.client.execute_read(
                "MATCH (d:Document) WHERE d.document_id IS NOT NULL "
                "AND (d.user_id IS NULL OR d.user_id = $user_id) "
                "RETURN d.document_id AS document_id",
                user_id=user_id,
            )
            user_doc_ids = [doc["document_id"] for doc in user_docs]

            if not user_doc_ids:
                return {
                    "entity": {
                        "entity_id": entity["canonical_id"],
                        "name": entity.get("canonical_name"),
                        "entity_type": entity.get("entity_type"),
                    },
                    "relationships": [],
                }

            rows = self.client.execute_read(
                "MATCH (entity {canonical_id: $entity_id}) "
                "OPTIONAL MATCH (entity)-[r]-(connected) "
                "WHERE r.evidence_id IS NOT NULL "
                "AND r.source_document_id IN $document_ids "
                "AND connected.canonical_id IS NOT NULL "
                "RETURN entity.canonical_id AS entity_id, entity.canonical_name AS name, "
                "entity.entity_type AS entity_type, type(r) AS relationship_type, "
                "r.relationship_type AS extracted_relationship_type, "
                "{entity_id: startNode(r).canonical_id, name: startNode(r).canonical_name, "
                "entity_type: startNode(r).entity_type} AS source_entity, "
                "{entity_id: endNode(r).canonical_id, name: endNode(r).canonical_name, "
                "entity_type: endNode(r).entity_type} AS target_entity, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
                entity_id=entity_id,
                document_ids=user_doc_ids,
            )
        else:
            rows = self.client.execute_read(
                "MATCH (entity {canonical_id: $entity_id}) "
                "OPTIONAL MATCH (entity)-[r]-(connected) "
                "WHERE r.evidence_id IS NOT NULL AND connected.canonical_id IS NOT NULL "
                "RETURN entity.canonical_id AS entity_id, entity.canonical_name AS name, "
                "entity.entity_type AS entity_type, type(r) AS relationship_type, "
                "r.relationship_type AS extracted_relationship_type, "
                "{entity_id: startNode(r).canonical_id, name: startNode(r).canonical_name, "
                "entity_type: startNode(r).entity_type} AS source_entity, "
                "{entity_id: endNode(r).canonical_id, name: endNode(r).canonical_name, "
                "entity_type: endNode(r).entity_type} AS target_entity, "
                "r.source_document_id AS source_document_id, r.page_number AS page_number, "
                "r.evidence_id AS evidence_id, r.confidence AS confidence, "
                "r.extraction_method AS extraction_method",
                entity_id=entity_id,
            )

        if not rows:
            raise EntityNotFound(entity_id)

        first = rows[0]
        relationships = [
            {key: row.get(key) for key in (
                "relationship_type", "source_document_id", "source_entity", "target_entity", "page_number",
                "evidence_id", "confidence", "extraction_method",
            )}
            for row in rows
            if row.get("relationship_type") is not None
        ]
        for relationship in relationships:
            source_row = next(row for row in rows if row.get("evidence_id") == relationship.get("evidence_id"))
            relationship["relationship_type"] = source_row.get("extracted_relationship_type") or relationship["relationship_type"]
        return {
            "entity": {
                "entity_id": first["entity_id"],
                "name": first.get("name"),
                "entity_type": first.get("entity_type"),
            },
            "relationships": relationships,
        }

    def answer_question(self, question: str, document_id: str | None = None, user_id: int | None = None) -> dict[str, Any]:
        """Retrieve deterministic, evidence-backed graph facts strictly scoped to a document or across documents."""
        doc: dict[str, Any] | None = None
        if document_id is not None:
            doc = self.get_document(document_id, user_id=user_id)

        clean_q = question.strip()
        terms = _query_terms(clean_q)

        result = self._dispatch_structured_answer(clean_q, terms, document_id, doc, user_id=user_id)

        # Full-text evidence fallback: runs only once every structured answer path
        # (count/page/relationship-list/entity-list/attribute/specific) has genuinely
        # failed to find anything, and only when scoped to a single, isolated document.
        if document_id and terms and result.get("answer") == _NO_MATCH_ANSWER:
            fallback = self._answer_fulltext_fallback(clean_q, terms, document_id, doc)
            if fallback is not None:
                return fallback

        return result

    def _dispatch_structured_answer(
        self,
        clean_q: str,
        terms: list[str],
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        # 1. Count intent (e.g. "How many people are mentioned?", "How many entities are there?")
        is_count, count_target = _detect_count_intent(clean_q)
        if is_count and count_target:
            return self._answer_count_question(clean_q, count_target, document_id=document_id, doc=doc, user_id=user_id)

        # 2. Page intent (e.g. "Which page mentions X?", "Where is X mentioned?")
        if _detect_page_intent(clean_q):
            return self._answer_page_question(clean_q, terms, document_id=document_id, doc=doc, user_id=user_id)

        # 3. Relationship listing intent (e.g. "What relationships are present?")
        if _detect_relationship_list_intent(clean_q):
            return self._answer_relationship_list_question(clean_q, document_id=document_id, doc=doc, user_id=user_id)

        # 4. Entity listing intent (e.g. "What entities are mentioned?", "Who is mentioned?", "Which organizations are mentioned?")
        is_entity_list, entity_type = _detect_entity_list_intent(clean_q)
        if is_entity_list:
            return self._answer_entity_list_question(clean_q, entity_type=entity_type, document_id=document_id, doc=doc, user_id=user_id)

        # 5. Generic attribute intent
        if document_id:
            attribute = _detect_attribute_intent(clean_q)
            if attribute:
                attr_result = self._answer_attribute_question(clean_q, attribute, document_id, doc, user_id=user_id)
                if attr_result:
                    return attr_result

        # 6. Specific entity, relationship, fact, or attribute lookup
        if not terms:
            return _empty_answer(
                clean_q,
                "Please include a specific entity, relationship, or value in your question.",
                document_id=document_id,
                document=doc,
            )

        return self._answer_specific_question(clean_q, terms, document_id=document_id, doc=doc, user_id=user_id)

    def _answer_count_question(
        self,
        question: str,
        target: str,
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        if target == "Relationship":
            rel_result = self._get_scoped_relationships(document_id=document_id)
            relationships = rel_result["relationships"]
            count = len(relationships)
            facts = rel_result["facts"]
            if count == 0:
                answer = "There are no relationships present in this document." if document_id else "There are no relationships present in the processed documents."
            elif count == 1:
                answer = f"There is 1 relationship present in this document: {facts[0]}." if document_id else f"There is 1 relationship present: {facts[0]}."
            else:
                fact_summary = "; ".join(facts[:5])
                if count > 5:
                    fact_summary += f", and {count - 5} more"
                answer = f"There are {count} relationships present in this document: {fact_summary}." if document_id else f"There are {count} relationships present: {fact_summary}."
            return {
                "question": question,
                "answer": answer,
                "document_id": document_id,
                "document": doc,
                "matched_entities": rel_result["entities"],
                "matched_relationships": relationships,
                "evidence": rel_result["evidence"],
            }

        # Count entities (by type or all)
        filter_type = target if target in _TYPE_MAPPINGS else None
        entities, evidence = self._get_scoped_entity_mentions(document_id=document_id, entity_type=filter_type)
        count = len(entities)

        if filter_type:
            meta = _TYPE_MAPPINGS[filter_type]
            singular, plural = meta["singular"], meta["plural"]
            if count == 0:
                answer = f"There are no {plural} mentioned in this document." if document_id else f"There are no {plural} mentioned in the processed documents."
            elif count == 1:
                answer = f"There is 1 {singular} mentioned in this document: {entities[0]['name']}." if document_id else f"There is 1 {singular} mentioned: {entities[0]['name']}."
            else:
                names = ", ".join(e["name"] or e["entity_id"] for e in entities)
                answer = f"There are {count} {plural} mentioned in this document: {names}." if document_id else f"There are {count} {plural} mentioned: {names}."
        else:
            if count == 0:
                answer = "There are no entities mentioned in this document." if document_id else "There are no entities mentioned in the processed documents."
            elif count == 1:
                answer = f"There is 1 entity mentioned in this document: {entities[0]['name']}." if document_id else f"There is 1 entity mentioned: {entities[0]['name']}."
            else:
                names = ", ".join(e["name"] or e["entity_id"] for e in entities[:10])
                suffix = f": {names}." if count <= 10 else f" including: {names}, among others."
                answer = f"There are {count} entities mentioned in this document{suffix}" if document_id else f"There are {count} entities mentioned{suffix}"

        return {
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "document": doc,
            "matched_entities": entities,
            "matched_relationships": [],
            "evidence": evidence,
        }

    def _answer_page_question(
        self,
        question: str,
        terms: list[str],
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        # Filter terms to subjects
        subject_terms = [t for t in terms if t not in _PAGE_TERMS and t not in _STOP_WORDS]
        if not subject_terms:
            return _empty_answer(question, document_id=document_id, document=doc)

        # 1. Search entity mentions
        entities, evidence = self._get_scoped_entity_mentions(document_id=document_id, terms=subject_terms)
        if entities and evidence:
            pages = sorted({ev["page"] for ev in evidence if ev.get("page") is not None})
            page_str = _format_page_list(pages)
            subject_name = entities[0]["name"] or entities[0]["entity_id"]
            scope_str = " in this document" if document_id else ""
            return {
                "question": question,
                "answer": f"{subject_name} is mentioned on {page_str}{scope_str}.",
                "document_id": document_id,
                "document": doc,
                "matched_entities": entities,
                "matched_relationships": [],
                "evidence": evidence,
            }

        # 2. Search relationships
        rel_result = self._get_scoped_relationships(document_id=document_id, terms=subject_terms)
        if rel_result["relationships"] and rel_result["evidence"]:
            pages = sorted({ev["page"] for ev in rel_result["evidence"] if ev.get("page") is not None})
            page_str = _format_page_list(pages)
            subject_name = rel_result["facts"][0] if rel_result["facts"] else "The requested information"
            scope_str = " in this document" if document_id else ""
            return {
                "question": question,
                "answer": f"{subject_name} is found on {page_str}{scope_str}.",
                "document_id": document_id,
                "document": doc,
                "matched_entities": rel_result["entities"],
                "matched_relationships": rel_result["relationships"],
                "evidence": rel_result["evidence"],
            }

        return _empty_answer(question, document_id=document_id, document=doc)

    def _answer_relationship_list_question(
        self,
        question: str,
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        rel_result = self._get_scoped_relationships(document_id=document_id)
        relationships = rel_result["relationships"]
        facts = rel_result["facts"]
        if not relationships:
            answer = "No relationships were found in this document." if document_id else "No relationships were found in the processed documents."
            return _empty_answer(question, answer=answer, document_id=document_id, document=doc)

        facts_text = "; ".join(facts)
        answer = f"The relationships present in this document are: {facts_text}." if document_id else f"The relationships present are: {facts_text}."
        return {
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "document": doc,
            "matched_entities": rel_result["entities"],
            "matched_relationships": relationships,
            "evidence": rel_result["evidence"],
        }

    def _answer_entity_list_question(
        self,
        question: str,
        entity_type: str | None,
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        entities, evidence = self._get_scoped_entity_mentions(document_id=document_id, entity_type=entity_type)
        if not entities:
            if entity_type and entity_type in _TYPE_MAPPINGS:
                plural = _TYPE_MAPPINGS[entity_type]["plural"]
                msg = f"I couldn't find any {plural} mentioned in this document." if document_id else f"No {plural} were found in the processed documents."
            else:
                msg = "I couldn't find any entities mentioned in this document." if document_id else "No entities were found in the processed documents."
            return _empty_answer(question, answer=msg, document_id=document_id, document=doc)

        names = ", ".join(entity["name"] or entity["entity_id"] for entity in entities)
        if entity_type and entity_type in _TYPE_MAPPINGS:
            plural = _TYPE_MAPPINGS[entity_type]["plural"]
            answer = f"The mentioned {plural} are: {names}."
        else:
            answer = f"The mentioned entities are: {names}."

        return {
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "document": doc,
            "matched_entities": entities,
            "matched_relationships": [],
            "evidence": evidence,
        }

    def _answer_attribute_question(
        self,
        question: str,
        attribute: str,
        document_id: str,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        rows = self.client.execute_read(
            "MATCH (d:Document {document_id: $document_id})-[:CONTAINS]->(m:EntityMention) "
            "OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(ev:Evidence) "
            "RETURN m.entity_type AS entity_type, m.raw_text AS value, m.mention_id AS entity_id, "
            "m.confidence AS confidence, m.page_number AS page, "
            "ev.evidence_id AS evidence_id, ev.raw_text AS raw_text, ev.extraction_method AS extraction_method, "
            "d.filename AS filename, d.document_id AS document_id",
            document_id=document_id,
        )
        
        target = _normalize_label(attribute)
        matched_row = None
        
        for row in rows:
            et = _normalize_label(row.get("entity_type") or "")
            name_alias = target in {"name", "person"} and et in {"name", "person"}
            if name_alias or target == et or target.replace(" ", "") == et.replace(" ", ""):
                matched_row = row
                break
                
        if not matched_row:
            target_words = set(w for w in target.split() if w not in _STOP_WORDS)
            matched_rows = []
            for row in rows:
                et = _normalize_label(row.get("entity_type") or "")
                if et:
                    et_words = set(w for w in et.split() if w not in _STOP_WORDS)
                    identifier_query = bool(target_words & {"number", "id", "identifier", "registration"})
                    identifier_type = et in {"number", "id", "identifier", "registration number"}
                    if target_words and (
                        target_words.issubset(et_words)
                        or (et_words and et_words.issubset(target_words))
                        or (identifier_query and identifier_type)
                    ):
                        matched_rows.append(row)
            if matched_rows:
                matched_row = _pick_attribute_row(matched_rows)

        if not matched_row:
            target_words = [w for w in target.split() if w not in _STOP_WORDS]
            for row in rows:
                et = _normalize_label(row.get("entity_type") or "")
                if et:
                    if target in et:
                        matched_row = row
                        break
                    et_words = [w for w in et.split() if w not in _STOP_WORDS]
                    acronym = "".join(w[0] for w in et_words if w)
                    if any(len(tw) >= 2 and tw in acronym for tw in target_words):
                        matched_row = row
                        break

        if not matched_row:
            return None
            
        key = matched_row.get("entity_type") or ""
        value = (matched_row.get("value") or "").strip()
        
        clean_value = _clean_attribute_value(key, value)
        
        if not clean_value:
            clean_value = value
            
        evidence = []
        if matched_row.get("evidence_id"):
            evidence.append({
                "document_id": matched_row["document_id"],
                "filename": matched_row["filename"],
                "page": matched_row["page"],
                "evidence_id": matched_row["evidence_id"],
                "raw_text": matched_row["raw_text"],
                "confidence": matched_row["confidence"],
                "extraction_method": matched_row["extraction_method"]
            })
            
        return {
            "question": question,
            "answer": clean_value,
            "document_id": document_id,
            "document": doc,
            "matched_entities": [{
                "entity_id": matched_row["entity_id"],
                "name": matched_row["value"],
                "entity_type": key
            }],
            "matched_relationships": [],
            "evidence": evidence
        }

    def _answer_specific_question(
        self,
        question: str,
        terms: list[str],
        document_id: str | None,
        doc: dict[str, Any] | None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        # 1. Search relationships matching terms
        rows = self.client.execute_read(
            "MATCH (source)-[r]->(target) "
            "WHERE r.evidence_id IS NOT NULL "
            "AND ($document_id IS NULL OR r.source_document_id = $document_id) "
            "WITH source, r, target, "
            "toLower(coalesce(source.canonical_name, source.name, '') + ' ' + "
            "coalesce(target.canonical_name, target.name, '') + ' ' + type(r)) AS searchable "
            "WHERE any(term IN $terms WHERE searchable CONTAINS term) "
            "OPTIONAL MATCH (d:Document {document_id: r.source_document_id})-[:HAS_PAGE]->(:DocumentPage {page_number: r.page_number})-[:HAS_EVIDENCE]->(e:Evidence {evidence_id: r.evidence_id}) "
            "RETURN coalesce(source.canonical_name, source.name) AS source_name, type(r) AS relationship_type, "
            "coalesce(source.canonical_id, source.entity_id) AS source_entity_id, "
            "source.entity_type AS source_entity_type, "
            "coalesce(target.canonical_id, target.entity_id) AS target_entity_id, "
            "target.entity_type AS target_entity_type, "
            "coalesce(target.canonical_name, target.name) AS target_name, r.source_document_id AS document_id, "
            "d.filename AS filename, r.page_number AS page, r.evidence_id AS evidence_id, "
            "e.raw_text AS raw_text, coalesce(e.confidence, r.confidence) AS confidence, "
            "coalesce(e.extraction_method, r.extraction_method) AS extraction_method, e.bbox AS bbox, "
            "e.normalized_bbox AS normalized_bbox, "
            "reduce(score = 0, term IN $terms | score + CASE WHEN searchable CONTAINS term THEN 1 ELSE 0 END) AS score "
            "ORDER BY score DESC, confidence DESC LIMIT 5",
            document_id=document_id,
            terms=terms,
        )
        rows = [row for row in rows if _relationship_matches_question(row, terms)]

        if rows:
            facts = []
            matched_relationships = []
            evidence = []
            for row in rows:
                fact = f"{row['source_name']} {row['relationship_type'].replace('_', ' ').lower()} {row['target_name']}"
                if fact not in facts:
                    facts.append(fact)
                matched_relationships.append({
                    "relationship_type": row["relationship_type"],
                    "source_entity": {"entity_id": row.get("source_entity_id") or row.get("source_name"), "name": row.get("source_name"), "entity_type": row.get("source_entity_type")},
                    "target_entity": {"entity_id": row.get("target_entity_id") or row.get("target_name"), "name": row.get("target_name"), "entity_type": row.get("target_entity_type")},
                    "page_number": row.get("page"),
                    "evidence_id": row.get("evidence_id"),
                    "confidence": row.get("confidence"),
                    "extraction_method": row.get("extraction_method"),
                })
                evidence.append({key: row.get(key) for key in (
                    "document_id", "filename", "page", "evidence_id", "raw_text", "confidence",
                    "extraction_method", "bbox", "normalized_bbox",
                )})
            return {
                "question": question,
                "answer": "; ".join(facts) + ".",
                "document_id": document_id,
                "document": doc,
                "matched_entities": _relationship_entities(matched_relationships),
                "matched_relationships": matched_relationships,
                "evidence": evidence,
            }

        # 2. Search entity mentions matching terms
        entities, evidence = self._get_scoped_entity_mentions(document_id=document_id, terms=terms)
        if entities:
            if len(entities) == 1:
                ent = entities[0]
                ev_page = evidence[0].get("page") if evidence else None
                page_suffix = f" on page {ev_page}" if ev_page is not None else ""
                type_suffix = f" as a {ent['entity_type']}" if ent.get("entity_type") else ""
                scope_suffix = " in this document" if document_id else ""
                answer = f"{ent['name']} is mentioned{type_suffix}{page_suffix}{scope_suffix}."
            else:
                names = ", ".join(e["name"] or e["entity_id"] for e in entities[:5])
                answer = f"The matching entities found are: {names}."

            return {
                "question": question,
                "answer": answer,
                "document_id": document_id,
                "document": doc,
                "matched_entities": entities,
                "matched_relationships": [],
                "evidence": evidence,
            }

        return _empty_answer(question, document_id=document_id, document=doc)

    def _get_scoped_entity_mentions(
        self,
        document_id: str | None = None,
        entity_type: str | None = None,
        terms: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self.client.execute_read(
            "MATCH (d:Document)-[:CONTAINS]->(m:EntityMention) "
            "WHERE ($document_id IS NULL OR d.document_id = $document_id) "
            "AND ($entity_type IS NULL OR toLower(m.entity_type) = toLower($entity_type)) "
            "OPTIONAL MATCH (m)-[:RESOLVED_TO]->(c) "
            "RETURN coalesce(c.canonical_id, m.mention_id) AS entity_id, "
            "coalesce(c.canonical_name, m.raw_text, m.normalized_text) AS name, "
            "m.entity_type AS entity_type, d.document_id AS document_id, "
            "d.filename AS filename, m.page_number AS page, "
            "m.mention_id AS evidence_id, m.raw_text AS raw_text, "
            "m.confidence AS confidence, m.extraction_method AS extraction_method "
            "ORDER BY d.filename, page, name LIMIT 50",
            document_id=document_id,
            entity_type=entity_type,
            terms=terms or [],
        )
        if terms:
            filtered_rows = []
            for row in rows:
                searchable = f"{row.get('name') or ''} {row.get('raw_text') or ''} {row.get('entity_type') or ''}".casefold()
                if any(t in searchable for t in terms):
                    filtered_rows.append(row)
            rows = filtered_rows

        entities = []
        evidence = []
        seen_entity_keys = set()
        for row in rows:
            entity_name = row.get("name") or row["entity_id"]
            key = (entity_name.casefold(), (row.get("entity_type") or "").casefold())
            if key not in seen_entity_keys:
                seen_entity_keys.add(key)
                entities.append({
                    "entity_id": row["entity_id"],
                    "name": entity_name,
                    "entity_type": row.get("entity_type"),
                })
            evidence.append({key: row.get(key) for key in (
                "document_id", "filename", "page", "evidence_id", "raw_text", "confidence", "extraction_method",
            )})
        return entities, evidence

    def _get_scoped_relationships(
        self,
        document_id: str | None = None,
        terms: list[str] | None = None,
    ) -> dict[str, Any]:
        rows = self.client.execute_read(
            "MATCH (source)-[r]->(target) "
            "WHERE r.evidence_id IS NOT NULL "
            "AND ($document_id IS NULL OR r.source_document_id = $document_id) "
            "OPTIONAL MATCH (d:Document {document_id: r.source_document_id}) "
            "OPTIONAL MATCH (d)-[:HAS_PAGE]->(:DocumentPage {page_number: r.page_number})-[:HAS_EVIDENCE]->(e:Evidence {evidence_id: r.evidence_id}) "
            "RETURN coalesce(source.canonical_name, source.name) AS source_name, "
            "coalesce(r.relationship_type, type(r)) AS relationship_type, "
            "coalesce(source.canonical_id, source.entity_id) AS source_entity_id, "
            "source.entity_type AS source_entity_type, "
            "coalesce(target.canonical_id, target.entity_id) AS target_entity_id, "
            "target.entity_type AS target_entity_type, "
            "coalesce(target.canonical_name, target.name) AS target_name, r.source_document_id AS document_id, "
            "d.filename AS filename, r.page_number AS page, r.evidence_id AS evidence_id, "
            "coalesce(e.raw_text, r.relationship_type) AS raw_text, coalesce(e.confidence, r.confidence) AS confidence, "
            "coalesce(e.extraction_method, r.extraction_method) AS extraction_method, e.bbox AS bbox, "
            "e.normalized_bbox AS normalized_bbox "
            "ORDER BY r.page_number, source_name",
            document_id=document_id,
            terms=terms or [],
        )
        if terms:
            filtered_rows = []
            for row in rows:
                searchable = f"{row.get('source_name') or ''} {row.get('relationship_type') or ''} {row.get('target_name') or ''}".casefold()
                if any(t in searchable for t in terms):
                    filtered_rows.append(row)
            rows = filtered_rows

        facts = []
        relationships = []
        evidence = []
        seen_facts = set()
        for row in rows:
            fact = f"{row['source_name']} {str(row['relationship_type']).replace('_', ' ').lower()} {row['target_name']}"
            if fact not in seen_facts:
                seen_facts.add(fact)
                facts.append(fact)
            relationships.append({
                "relationship_type": row["relationship_type"],
                "source_entity": {"entity_id": row.get("source_entity_id") or row.get("source_name"), "name": row.get("source_name"), "entity_type": row.get("source_entity_type")},
                "target_entity": {"entity_id": row.get("target_entity_id") or row.get("target_name"), "name": row.get("target_name"), "entity_type": row.get("target_entity_type")},
                "page_number": row.get("page"),
                "evidence_id": row.get("evidence_id"),
                "confidence": row.get("confidence"),
                "extraction_method": row.get("extraction_method"),
            })
            evidence.append({key: row.get(key) for key in (
                "document_id", "filename", "page", "evidence_id", "raw_text", "confidence",
                "extraction_method", "bbox", "normalized_bbox",
            )})
        return {
            "facts": facts,
            "entities": _relationship_entities(relationships),
            "relationships": relationships,
            "evidence": evidence,
        }

    def _answer_fulltext_fallback(
        self,
        question: str,
        terms: list[str],
        document_id: str,
        doc: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Fall back to the document's stored evidence text when no structured fact matches.

        This is a generic, domain-independent last resort: it only searches Evidence rows
        that belong to the selected document and returns verbatim page text as the answer.
        """
        meaningful_terms = [term for term in terms if term not in _STOP_WORDS]
        if not meaningful_terms:
            return None

        rows = self.client.execute_read(
            "MATCH (d:Document {document_id: $document_id})-[:HAS_PAGE]->(p:DocumentPage)"
            "-[:HAS_EVIDENCE]->(e:Evidence) "
            "WHERE e.raw_text IS NOT NULL "
            "RETURN d.document_id AS document_id, d.filename AS filename, "
            "p.page_number AS page, e.evidence_id AS evidence_id, e.raw_text AS raw_text, "
            "e.confidence AS confidence, e.extraction_method AS extraction_method, "
            "e.bbox AS bbox, e.normalized_bbox AS normalized_bbox "
            "ORDER BY page, evidence_id",
            document_id=document_id,
        )

        best_row: dict[str, Any] | None = None
        best_fragment: str | None = None
        best_score = 0
        for row in rows:
            text = str(row.get("raw_text") or "")
            for fragment in _split_fragments(text):
                searchable = fragment.casefold()
                score = sum(1 for term in meaningful_terms if term in searchable)
                if score == 0:
                    continue
                if score > best_score or (score == best_score and best_fragment is not None and len(fragment) < len(best_fragment)):
                    best_score = score
                    best_row = row
                    best_fragment = fragment

        if best_row is None or not best_fragment:
            return None

        page = best_row.get("page")
        page_suffix = f" on page {page}" if page is not None else ""
        answer = f'The document states{page_suffix}: "{best_fragment}"'
        return {
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "document": doc,
            "matched_entities": [],
            "matched_relationships": [],
            "evidence": [{
                "document_id": best_row.get("document_id") or document_id,
                "filename": best_row.get("filename"),
                "page": page,
                "evidence_id": best_row.get("evidence_id"),
                "raw_text": best_row.get("raw_text"),
                "confidence": best_row.get("confidence"),
                "extraction_method": best_row.get("extraction_method"),
                "bbox": best_row.get("bbox"),
                "normalized_bbox": best_row.get("normalized_bbox"),
            }],
        }


_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "about", "by", "did", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "show", "tell", "the", "there", "this", "that", "to",
    "what", "when", "where", "which", "who", "with", "document", "documents", "mentioned",
    "present", "available", "information", "detail", "details", "list", "give", "many",
    "person", "person's",
})
_RELATIONSHIP_TERMS = frozenset({"buy", "bought", "purchase", "purchased", "supply", "supplied", "provide", "provided", "sell", "sold", "works", "work", "relate", "related", "create", "created"})
_GENERIC_ENTITY_TERMS = frozenset({"company", "companies", "entity", "entities", "product", "products", "thing", "things"})
_PAGE_TERMS = frozenset({"page", "pages", "where", "which", "what", "on", "find", "located", "number"})

_TYPE_MAPPINGS: dict[str, dict[str, Any]] = {
    "Person": {
        "singular": "person",
        "plural": "people",
        "pattern": r"\b(who|person|people|individual|individuals|author|authors|creator|creators|user|users)\b",
    },
    "Organization": {
        "singular": "organization",
        "plural": "organizations",
        "pattern": r"\b(organization|organizations|org|orgs|company|companies|vendor|vendors|merchant|merchants|business|businesses|store|stores|institution|institutions)\b",
    },
    "Product": {
        "singular": "product",
        "plural": "products",
        "pattern": r"\b(product|products|item|items|goods|merchandise)\b",
    },
    "Location": {
        "singular": "location",
        "plural": "locations",
        "pattern": r"\b(location|locations|place|places|address|addresses|city|cities|country|countries|state|states)\b",
    },
    "Date": {
        "singular": "date",
        "plural": "dates",
        "pattern": r"\b(date|dates|when|time|times|year|years|month|months|day|days)\b",
    },
    "Amount": {
        "singular": "amount",
        "plural": "amounts",
        "pattern": r"\b(amount|amounts|price|prices|cost|costs|total|totals|fee|fees|money|sum|sums|subtotal|subtotals)\b",
    },
}


_NO_MATCH_ANSWER = "I couldn't find enough information in this document to answer that question."
_NO_MATCH_ANSWER_GLOBAL = "No matching evidence was found in the processed documents."


def _empty_answer(
    question: str,
    answer: str | None = None,
    document_id: str | None = None,
    document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if answer is None:
        answer = _NO_MATCH_ANSWER if document_id else _NO_MATCH_ANSWER_GLOBAL
    return {
        "question": question,
        "answer": answer,
        "document_id": document_id,
        "document": document,
        "matched_entities": [],
        "matched_relationships": [],
        "evidence": [],
    }


def _detect_attribute_intent(question: str) -> str | None:
    q = question.casefold().strip(" ?.")
    m = re.match(r"^(?:what is the value of|what is the|what is|tell me the|tell me|which|what)\s+(.+?)(?:\s+is mentioned|\s+are mentioned)?$", q)
    if m:
        attr = m.group(1).strip()
        attr = re.sub(r"['’]s\b", "", attr)
        if attr.startswith("name of the "):
            attr = attr[len("name of the "):]
        elif attr.startswith("name of "):
            attr = attr[len("name of "):]
        if attr.endswith(" value"):
            attr = attr[:-len(" value")]
        attr = attr.strip()
        if attr in {"name", "person"}:
            return "name"
        if attr and attr not in _STOP_WORDS:
            return " ".join(attr.split())
    return None


def _attribute_match_score(row: dict[str, Any]) -> tuple:
    """Prefer OCR/pattern evidence over malformed layout_value guesses."""
    method = str(row.get("extraction_method") or "").casefold()
    entity_type = _normalize_label(row.get("entity_type") or "")
    value = str(row.get("value") or "")
    plausible = 1 if _is_plausible_value(value) else 0
    if method in {"generic_pattern", "spacy_ner", "heuristic", "regex_kv"}:
        source_rank = 3
    elif method in {"layout_value", "layout_vertical"}:
        source_rank = 1
    else:
        source_rank = 2
    if entity_type in {"identifier", "id"}:
        type_rank = 2
    elif entity_type == "number":
        type_rank = 0
    else:
        type_rank = 1
    return (plausible, source_rank, type_rank)


def _pick_attribute_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    plausible_rows = [row for row in rows if _is_plausible_value(str(row.get("value") or ""))]
    ranked = sorted(plausible_rows or rows, key=_attribute_match_score, reverse=True)
    best_score = _attribute_match_score(ranked[0])
    tied = [row for row in ranked if _attribute_match_score(row) == best_score]
    best_row = tied[0]
    for row in tied:
        val = row.get("value") or ""
        best_val = best_row.get("value") or ""
        if val in best_val and len(val) < len(best_val):
            best_row = row
    return best_row


def _normalize_label(value: str) -> str:
    """Normalize document labels and question wording for generic field matching."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"['’]s\b", "", normalized)
    normalized = "".join(" " if unicodedata.category(char).startswith("P") else char for char in normalized)
    words = normalized.split()
    words = [word[:-1] if len(word) > 3 and word.endswith("s") else word for word in words]
    return " ".join(words)


def _clean_attribute_value(key: str, value: str) -> str:
    clean_value = value.strip()
    prefix = re.compile(r"^" + re.escape(key) + r"\s*[:=\-]?\s*", re.IGNORECASE)
    clean_value = prefix.sub("", clean_value).strip()
    if not clean_value:
        return clean_value
    # Keep one value when overlapping OCR/layout candidates repeat it in the same field.
    parts = [part for part in re.split(r"\s{2,}|\s*[,;|]\s*", clean_value) if part]
    if len(parts) > 1 and all(part.casefold() == parts[0].casefold() for part in parts):
        clean_value = parts[0].strip()
    return clean_value


def _detect_count_intent(question: str) -> tuple[bool, str | None]:
    q = question.casefold()
    if not re.search(r"\b(how many|count of|number of|total number of)\b", q):
        return False, None
    if re.search(r"\b(relationship|relationships|relation|relations|connection|connections)\b", q):
        return True, "Relationship"
    for entity_type, meta in _TYPE_MAPPINGS.items():
        if re.search(meta["pattern"], q):
            return True, entity_type
    return True, "Entity"


def _detect_page_intent(question: str) -> bool:
    q = question.casefold()
    return bool(re.search(r"\b(which page|what page|on what page|where is|where are|page number|find page)\b", q))


def _detect_relationship_list_intent(question: str) -> bool:
    q = question.casefold()
    return bool(re.search(r"\b(what relationships|which relationships|list relationships|show relationships|all relationships|relationships present|relationships are in|relationships are present)\b", q))


def _detect_entity_list_intent(question: str) -> tuple[bool, str | None]:
    q = question.casefold()
    if _detect_count_intent(question)[0] or _detect_page_intent(question) or _detect_relationship_list_intent(question):
        return False, None

    # Check general entity list
    if bool(re.search(r"\b(what entities|which entities|list entities|show entities|entities are mentioned|entities mentioned|entities are present|entities in this document)\b", q)):
        return True, None

    # Check "who is mentioned / who are mentioned / who is in this document"
    if bool(re.search(r"\bwho (is|are) (mentioned|in|present)\b|\bwho is in this document\b", q)) or q.strip(" ?") == "who is mentioned":
        return True, "Person"

    # Check if there is an explicit action verb (e.g. "Who purchased...", "What did X buy..."), which indicates a specific fact query
    if bool(re.search(r"\b(did|does|do|works|work|created|create|purchased|purchase|bought|buy|sold|sell|supplied|supply|contain|contains|relate|related)\b", q)):
        return False, None

    # Check type-specific list patterns e.g. "which people are mentioned", "what organizations are mentioned", "list products", etc.
    for entity_type, meta in _TYPE_MAPPINGS.items():
        pattern = meta["pattern"]
        if re.search(r"\b(which|what|list|show|all)\s+" + pattern, q):
            return True, entity_type

    return False, None



def _format_page_list(pages: list[int]) -> str:
    if not pages:
        return "an unspecified page"
    if len(pages) == 1:
        return f"page {pages[0]}"
    if len(pages) == 2:
        return f"pages {pages[0]} and {pages[1]}"
    return f"pages {', '.join(map(str, pages[:-1]))} and {pages[-1]}"


def _relationship_entities(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities_by_key = {}
    for relationship in relationships:
        for entity in (relationship["source_entity"], relationship["target_entity"]):
            key = (entity.get("name") or entity["entity_id"]).casefold()
            existing = entities_by_key.get(key)
            if existing is None or existing.get("entity_type") is None and entity.get("entity_type") is not None:
                entities_by_key[key] = entity
    return list(entities_by_key.values())


def _relationship_matches_question(row: dict[str, Any], terms: list[str]) -> bool:
    entity_terms = [term for term in terms if term not in _RELATIONSHIP_TERMS and term not in _GENERIC_ENTITY_TERMS]
    if not entity_terms:
        return True
    searchable = " ".join((row.get("source_name") or "", row.get("target_name") or "")).casefold()
    return any(term in searchable for term in entity_terms)


def _with_extracted_relationship_type(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["relationship_type"] = result.get("extracted_relationship_type") or result.get("relationship_type")
    result.pop("extracted_relationship_type", None)
    return result


def _query_terms(question: str) -> list[str]:
    """Keep meaningful, safely parameterized terms for graph retrieval."""
    return list(dict.fromkeys(
        term for term in re.findall(r"[\w.-]+", question.casefold())
        if len(term) > 1 and term not in _STOP_WORDS
    ))[:12]


def _split_fragments(text: str) -> list[str]:
    """Break stored page text into line/sentence fragments for generic keyword retrieval."""
    fragments: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        fragments.append(line)
        for piece in re.split(r"(?<=[.!?;])\s+", line):
            piece = piece.strip()
            if piece and piece != line:
                fragments.append(piece)
    return fragments

