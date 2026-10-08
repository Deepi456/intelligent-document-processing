# Intelligent Document Processing System using OCR, NLP & Knowledge Graphs

Unstructured documents contain valuable information that is difficult to search, connect, and interpret manually. This domain-independent document intelligence system extracts structured knowledge from documents and builds an interconnected, provenance-aware Knowledge Graph to enable accurate, deterministic question-answering.

## Core Pipeline

The system processes documents through the following pipeline:

1. **Document Upload**: Users upload documents via the dashboard. Supported formats are PDF, JPG, JPEG, and PNG.
2. **Text Extraction & OCR**: Native text extraction is attempted first. For scanned documents or images, the configured OCR backend is used.
3. **NLP (Named Entity Recognition)**: Domain-neutral entities (Persons, Organizations, Locations, Dates, Amounts, etc.) are extracted.
4. **Relationship Extraction**: Contextual relationships between extracted entities are identified.
5. **Entity Resolution**: Entities are deduplicated into a canonical form across the document and the global graph.
6. **Knowledge Graph Construction**: Extracted entities and relationships are stored in Neo4j.
7. **Evidence & Provenance Tracking**: Every extraction is firmly linked back to its source document, page number, bounding box, and raw text snippet.
8. **Document-Specific Q&A**: Users can query a selected document. Answers are returned *only* using facts extracted from that specific document.
9. **Graph Visualization**: Interactive canvas to explore nodes, relationships, and their source evidence.

## Architecture & Provenance

The system maintains a strict hierarchy to ensure transparency and accountability for every extracted fact:

- `Document` → `DocumentPage` → `Evidence` → `EntityMention`
- `EntityMention` → `RESOLVED_TO` → `Canonical Entity`

Every relationship (`Entity` → `Relationship` → `Entity`) maintains an `evidence_id` property pointing directly to the specific text snippet that justifies its existence.

## Capabilities

Currently implemented features include:
- PDF and image (JPG, PNG) text extraction.
- Scanned-document OCR using the configured OCR backend.
- Generic, domain-neutral entity and relationship extraction.
- Document-scoped graph storage in Neo4j.
- Evidence and provenance tracking.
- Document-specific deterministic Q&A that strictly isolates context to the selected document.
- Interactive graph visualization and entity/relationship inspection.

## Honest Limitations

- **Extraction Dependency**: The quality of the knowledge graph is strictly bound by the accuracy of the underlying OCR and NLP engines.
- **Deterministic Q&A**: The system answers questions using predefined structural queries (e.g., entity counts, page locations, relationship listings) rather than unrestricted natural language or generative AI.
- **Complex Structures**: Complex tables, figures, and charts are not yet fully semantically interpreted.
- **Entity Resolution**: Canonical resolution is currently conservative to prevent false merges.
- **Graph Density**: Very large graphs may require filtering or clustering for optimal visualization.
- **No LLM/RAG**: This system does not use generative LLMs or vector-based RAG frameworks. All answers are deterministically retrieved from the Knowledge Graph.

## Benchmark Dataset (SROIE)

The system includes support for the **SROIE2019** dataset (scanned receipts) strictly as an optional benchmark and evaluation dataset to measure extraction accuracy. SROIE is *not* the core definition of the application, and the upload pipeline accepts any generic document.

## Setup Instructions

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Configure Neo4j
# Copy .env.example to .env and configure your Neo4j URI, user, and password.
```

### Running the System

```bash
# Verify the environment and Neo4j connection
python scripts/verify_environment.py

# Start the FastAPI backend
uvicorn app.api.main:app --reload --port 8000

# Start the React frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```
