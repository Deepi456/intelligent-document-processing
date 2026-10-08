from pathlib import Path
import re

from app.knowledge_graph.entity_resolution import (
    canonical_id,
    canonical_label,
    entity_label,
    mention_id,
    normalize_entity_value,
    relationship_label,
)
from app.knowledge_graph.neo4j_client import Neo4jClient
from app.ocr.ocr_engine import _clamp_confidence


class GraphBuilder:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
            "CREATE CONSTRAINT page_identity_unique IF NOT EXISTS FOR (p:DocumentPage) REQUIRE (p.document_id, p.page_number) IS UNIQUE",
            "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
            "CREATE CONSTRAINT entity_mention_id_unique IF NOT EXISTS FOR (m:EntityMention) REQUIRE m.mention_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_organization_id_unique IF NOT EXISTS FOR (e:CanonicalOrganization) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_person_id_unique IF NOT EXISTS FOR (e:CanonicalPerson) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_product_id_unique IF NOT EXISTS FOR (e:CanonicalProduct) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_location_id_unique IF NOT EXISTS FOR (e:CanonicalLocation) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_date_id_unique IF NOT EXISTS FOR (e:CanonicalDate) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE CONSTRAINT canonical_amount_id_unique IF NOT EXISTS FOR (e:CanonicalAmount) REQUIRE e.canonical_id IS UNIQUE",
            "CREATE INDEX entity_mention_normalized_index IF NOT EXISTS FOR (m:EntityMention) ON (m.normalized_text)",
            "CREATE INDEX organization_name_index IF NOT EXISTS FOR (o:Organization) ON (o.name)",
            "CREATE INDEX person_name_index IF NOT EXISTS FOR (p:Person) ON (p.name)",
            "CREATE INDEX amount_name_index IF NOT EXISTS FOR (a:Amount) ON (a.name)",
            "CREATE INDEX date_name_index IF NOT EXISTS FOR (d:Date) ON (d.name)",
            "CREATE INDEX location_name_index IF NOT EXISTS FOR (l:Location) ON (l.name)",
        ]
        for statement in statements:
            self.client.execute_write(statement)

    def add_document(self, file_path: str | Path, pages: list[object], entities: list[dict], relationships: list[dict]) -> None:
        path = Path(file_path).resolve()
        document_id = str(path)
        self.client.execute_write(
            "MERGE (d:Document {document_id: $document_id}) "
            "SET d.source = $source, d.filename = $filename, d.file_name = $filename, d.document_type = $document_type",
            document_id=document_id, source=document_id, filename=path.name,
            document_type=path.suffix.lower().lstrip("."),
        )
        for page in pages:
            self.client.execute_write(
                "MATCH (d:Document {document_id: $document_id}) "
                "MERGE (p:DocumentPage {document_id: $document_id, page_number: $page_number}) "
                "SET p.width = $width, p.height = $height "
                "MERGE (d)-[:HAS_PAGE]->(p)",
                document_id=document_id, page_number=page.page_number,
                width=page.image_width, height=page.image_height,
            )
            self.client.execute_write(
                "MATCH (p:DocumentPage {document_id: $document_id, page_number: $page}) "
                "MERGE (ev:Evidence {evidence_id: $evidence_id}) "
                "SET ev.raw_text = $raw_text, ev.extraction_method = $method, "
                "ev.confidence = $confidence, ev.bbox = $bbox, ev.normalized_bbox = $normalized_bbox, "
                "ev.page_number = $page "
                "MERGE (p)-[:HAS_EVIDENCE]->(ev)",
                document_id=document_id, page=page.page_number,
                evidence_id=_page_evidence_id(document_id, page.page_number),
                raw_text=page.text, method=page.source,
                confidence=_clamp_confidence(1.0) if page.source == "text_layer" else None,
                bbox=None, normalized_bbox=None,
            )
        for ordinal, entity in enumerate(entities):
            self._add_entity(document_id, ordinal, entity)
        for relation in relationships:
            self._add_relationship(document_id, relation)

    def _add_entity(self, document_id: str, ordinal: int, entity: dict) -> None:
        entity_type = str(entity.get("entity_type") or "Entity")
        entity_name = str(entity["name"])
        page_number = entity.get("page_number", 1)
        evidence_id = entity.get("evidence_id") or _evidence_id(document_id, entity_type, entity_name, page_number)
        normalized_name = normalize_entity_value(entity_name)
        mention_key = entity.get("mention_id") or mention_id(document_id, entity_type, normalized_name, ordinal)
        confidence = _clamp_confidence(entity.get("confidence"))
        node_label = entity_label(entity_type)
        canonical_node_label = canonical_label(entity_type)
        query = (
            "MATCH (d:Document {document_id: $document_id}) "
            "MERGE (e:`%s` {name: $name}) "
            "SET e.entity_id = coalesce(e.entity_id, $entity_id), e.entity_type = $entity_type "
            "MERGE (d)-[m:MENTIONS {page_number: $page}]->(e) "
            "SET m.source = $document_id "
            "MERGE (d)-[:CONTAINS {page_number: $page}]->(e) "
            "MERGE (p:DocumentPage {document_id: $document_id, page_number: $page}) "
            "MERGE (ev:Evidence {evidence_id: $evidence_id}) "
            "SET ev.raw_text = $raw_text, ev.extraction_method = $method, ev.confidence = $confidence, "
            "ev.bbox = $bbox, ev.normalized_bbox = $normalized_bbox, ev.page_number = $page "
            "MERGE (p)-[:HAS_EVIDENCE]->(ev) "
            "MERGE (ev)-[:SUPPORTS]->(e) "
            "MERGE (mention:EntityMention {mention_id: $mention_id}) "
            "SET mention.raw_text = $raw_text, mention.normalized_text = $normalized_name, "
            "mention.entity_type = $entity_type, mention.document_id = $document_id, "
            "mention.page_number = $page, mention.confidence = $confidence, mention.extraction_method = $method "
            "MERGE (d)-[:CONTAINS]->(mention) "
            "MERGE (mention)-[:SUPPORTED_BY]->(ev)" % node_label
        )
        if canonical_node_label:
            query += (
                " MERGE (c:`%s` {canonical_id: $canonical_id}) "
                "SET c.canonical_name = coalesce(c.canonical_name, $name), c.entity_type = $entity_type, "
                "c.resolution_status = coalesce(c.resolution_status, 'confirmed') "
                "MERGE (mention)-[:RESOLVED_TO]->(c)" % canonical_node_label
            )
        self.client.execute_write(
            query,
            document_id=document_id, name=entity_name,
            entity_id=_entity_id(entity_type, entity_name), entity_type=entity_type,
            normalized_name=normalized_name, mention_id=mention_key,
            canonical_id=canonical_id(entity_type, normalized_name), page=page_number,
            evidence_id=evidence_id, raw_text=entity.get("raw_text", entity_name),
            method=entity.get("source", "unknown"), confidence=confidence,
            bbox=entity.get("bbox"), normalized_bbox=entity.get("normalized_bbox"),
        )

    def _add_relationship(self, document_id: str, relation: dict) -> None:
        page_number = relation.get("page_number", 1)
        relation_type = str(relation.get("type") or "EXTRACTED_RELATION")
        relation_label = relationship_label(relation_type)
        source_name = str(relation["source"])
        target_name = str(relation["target"])
        source_type = str(relation.get("source_type") or "Entity")
        target_type = str(relation.get("target_type") or "Entity")
        confidence = _clamp_confidence(relation.get("confidence", 1.0))
        evidence_id = _evidence_id(document_id, relation_type, relation.get("evidence_id") or source_name + " " + target_name, page_number)
        query = (
            "MATCH (d:Document {document_id: $document_id}) "
            "MERGE (s:`%s` {name: $source_name}) "
            "MERGE (t:`%s` {name: $target_name}) "
            "SET s.entity_id = coalesce(s.entity_id, $source_entity_id), "
            "s.entity_type = $source_type, t.entity_id = coalesce(t.entity_id, $target_entity_id), "
            "t.entity_type = $target_type "
            "MERGE (d)-[:CONTAINS {page_number: $page}]->(s) "
            "MERGE (d)-[:CONTAINS {page_number: $page}]->(t) "
            "MERGE (s)-[r:`%s`]->(t) "
            "SET r.relationship_type = $relationship_type, r.source = $document_id, "
            "r.source_document_id = $document_id, r.page_number = $page, "
            "r.confidence = $confidence, r.extraction_method = $method, r.evidence_id = $evidence_id" % (
                entity_label(source_type), entity_label(target_type), relation_label,
            )
        )
        self.client.execute_write(
            query,
            document_id=document_id, source_name=source_name, target_name=target_name,
            source_entity_id=_entity_id(source_type, source_name),
            target_entity_id=_entity_id(target_type, target_name),
            source_type=source_type, target_type=target_type,
            relationship_type=relation_type, page=page_number, confidence=confidence,
            method=relation.get("extraction_method", "relationship_rule"), evidence_id=evidence_id,
        )
        source_canonical_label = canonical_label(source_type)
        target_canonical_label = canonical_label(target_type)
        if source_canonical_label and target_canonical_label:
            canonical_query = (
                "MATCH (d:Document {document_id: $document_id}) "
                "MERGE (source:`%s` {canonical_id: $source_canonical_id}) "
                "SET source.canonical_name = coalesce(source.canonical_name, $source_name), "
                "source.entity_type = $source_type, source.resolution_status = coalesce(source.resolution_status, 'confirmed') "
                "MERGE (target:`%s` {canonical_id: $target_canonical_id}) "
                "SET target.canonical_name = coalesce(target.canonical_name, $target_name), "
                "target.entity_type = $target_type, target.resolution_status = coalesce(target.resolution_status, 'confirmed') "
                "MERGE (d)-[:CONTAINS {page_number: $page}]->(source) "
                "MERGE (d)-[:CONTAINS {page_number: $page}]->(target) "
                "MERGE (source)-[r:`%s`]->(target) "
                "SET r.relationship_type = $relationship_type, r.source = $document_id, "
                "r.source_document_id = $document_id, r.page_number = $page, "
                "r.confidence = $confidence, r.extraction_method = $method, r.evidence_id = $evidence_id" % (
                    source_canonical_label, target_canonical_label, relation_label,
                )
            )
            self.client.execute_write(
                canonical_query,
                document_id=document_id,
                source_canonical_id=canonical_id(source_type, normalize_entity_value(source_name)),
                source_name=source_name, source_type=source_type,
                target_canonical_id=canonical_id(target_type, normalize_entity_value(target_name)),
                target_name=target_name, target_type=target_type,
                relationship_type=relation_type, page=page_number, confidence=confidence,
                method=relation.get("extraction_method", "relationship_rule"), evidence_id=evidence_id,
            )
        self.client.execute_write(
            "MATCH (p:DocumentPage {document_id: $document_id, page_number: $page}) "
            "MERGE (ev:Evidence {evidence_id: $evidence_id}) "
            "SET ev.raw_text = $raw_text, ev.extraction_method = $method, "
            "ev.confidence = $confidence, ev.page_number = $page "
            "MERGE (p)-[:HAS_EVIDENCE]->(ev)",
            document_id=document_id, page=page_number, evidence_id=evidence_id,
            raw_text=relation.get("raw_text", f"{source_name} {relation_type} {target_name}"),
            method=relation.get("extraction_method", "relationship_rule"), confidence=confidence,
        )


def _entity_id(entity_type: str, name: str) -> str:
    return f"{entity_type}:{' '.join(name.casefold().split())}"


def _evidence_id(document_id: str, kind: str, name: str, page_number: int) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", f"{document_id}-{kind}-{name}-{page_number}".casefold()).strip("-")
    return value[:180]


def _page_evidence_id(document_id: str, page_number: int) -> str:
    return _evidence_id(document_id, "page", str(page_number), page_number)
