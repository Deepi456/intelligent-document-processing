import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.image_extractor import extract_image
from app.extraction.pdf_extractor import extract_pdf
from app.ingestion.file_handler import detect_file_type
from app.knowledge_graph.graph_builder import GraphBuilder
from app.knowledge_graph.neo4j_client import Neo4jClient
from app.nlp.entity_extractor import extract_entities
from app.nlp.relation_extractor import extract_relationships
from app.ocr.ocr_engine import OcrEngine
from app.utils.logger import get_logger


LOGGER = get_logger(__name__)


def process_document(file_path: str | Path) -> dict[str, object]:
    document = detect_file_type(file_path)
    ocr_engine = OcrEngine()
    pages = extract_pdf(document.path, ocr_engine) if document.file_type == "pdf" else extract_image(document.path, ocr_engine)
    entities = extract_entities(pages)
    relationships = extract_relationships(pages, entities)
    client = Neo4jClient()
    try:
        client.verify_connectivity()
        builder = GraphBuilder(client)
        builder.ensure_schema()
        builder.add_document(document.path, pages, entities, relationships)
    finally:
        client.close()

    return {
        "document_id": str(document.path),
        "filename": document.path.name,
        "status": "processed",
        "pages": len(pages),
        "entities": len(entities),
        "relationships": len(relationships),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a PDF or image into a Neo4j knowledge graph")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        result = process_document(args.file)
    except Exception as error:
        LOGGER.error("Document processing failed: %s", error)
        return 2
    print(
        f"Extracted {result['pages']} page(s), {result['entities']} entit(y/ies), "
        f"{result['relationships']} relationship(s)"
    )
    print("Neo4j: inserted document, mentions, and relationships")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())