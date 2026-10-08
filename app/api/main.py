import logging
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j.exceptions import DriverError, Neo4jError
from sqlalchemy.orm import Session

from app.api.models import AnalyticsResponse, Document, Entity, Evidence, GraphOverview, GraphResponse, QuestionRequest, QuestionResponse, Relationship, UploadResponse
from app.api.service import DocumentNotFound, DocumentQueryService, EntityNotFound
from app.auth import routes as auth_routes
from app.auth.auth_service import create_access_token, create_user_response
from app.auth.database import User, get_db, init_db
from app.auth.dependencies import get_current_user_dependency
from app.ingestion.file_handler import SUPPORTED_EXTENSIONS
from app.knowledge_graph.neo4j_client import Neo4jClient
from scripts.process_document import process_document


logger = logging.getLogger(__name__)
app = FastAPI(title="Intelligent Document Processing API", version="1.0.0")
app.include_router(auth_routes.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "Authorization"],
)


@app.on_event("startup")
def startup():
    """Initialize database tables on startup."""
    init_db()


@app.exception_handler(DriverError)
@app.exception_handler(Neo4jError)
async def neo4j_error_handler(_, error: Exception) -> JSONResponse:
    logger.exception("Neo4j request failed: %s", error)
    return JSONResponse(status_code=503, content={"detail": "Neo4j is unavailable"})


def get_neo4j_client() -> Generator[Neo4jClient, None, None]:
    client = Neo4jClient()
    try:
        yield client
    finally:
        client.close()


def query_service(client: Neo4jClient = Depends(get_neo4j_client)) -> DocumentQueryService:
    return DocumentQueryService(client)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_dependency),
) -> UploadResponse:
    """
    Upload and process a document.
    Documents are associated with the authenticated user.
    """
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use PDF, JPG, JPEG, or PNG.")

    upload_root = (Path(__file__).resolve().parents[2] / "data" / "uploads").resolve()
    upload_path = upload_root / uuid4().hex / filename
    try:
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        with upload_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                destination.write(chunk)
        result = process_document(upload_path)

        # Store document ownership in Neo4j
        try:
            with Neo4jClient() as neo4j_client:
                neo4j_client.execute_write(
                    """MERGE (d:Document {document_id: $document_id})
                       SET d.user_id = $user_id, d.username = $username, d.email = $email""",
                    document_id=result["document_id"],
                    user_id=current_user.id,
                    username=current_user.full_name,
                    email=current_user.email,
                )
        except Exception:
            # Don't fail the upload if Neo4j update fails
            pass

        return UploadResponse(**result)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail="Document processing failed") from error
    finally:
        await file.close()


@app.get("/documents", response_model=list[Document])
def documents(
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> list[dict]:
    """
    List documents for the authenticated user.
    Includes legacy documents (without owner) for backward compatibility.
    """
    return service.list_documents(user_id=current_user.id)


@app.get("/documents/{document_id:path}/entities", response_model=list[Entity])
def entities(
    document_id: str,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> list[dict]:
    """
    Get entities for a document.
    Validates document ownership before returning data.
    """
    try:
        # Check document ownership
        doc = service.get_document(document_id, user_id=current_user.id)
        return service.get_entities(document_id)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail="Document not found") from error


@app.get("/documents/{document_id:path}/relationships", response_model=list[Relationship])
def relationships(
    document_id: str,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> list[dict]:
    """
    Get relationships for a document.
    Validates document ownership before returning data.
    """
    try:
        # Check document ownership
        doc = service.get_document(document_id, user_id=current_user.id)
        return service.get_relationships(document_id)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail="Document not found") from error


@app.get("/documents/{document_id:path}/evidence", response_model=list[Evidence])
def evidence(
    document_id: str,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> list[dict]:
    """
    Get evidence for a document.
    Validates document ownership before returning data.
    """
    try:
        # Check document ownership
        doc = service.get_document(document_id, user_id=current_user.id)
        return service.get_evidence(document_id)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail="Document not found") from error


@app.get("/documents/{document_id:path}", response_model=Document)
def document(
    document_id: str,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Get a specific document.
    Validates document ownership before returning data.
    """
    try:
        return service.get_document(document_id, user_id=current_user.id)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail="Document not found") from error


@app.get("/graph/{entity_id}", response_model=GraphResponse)
def graph(
    entity_id: str,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Get graph for an entity.
    Only returns data from user's own documents.
    """
    try:
        return service.get_graph(entity_id, user_id=current_user.id)
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail="Entity not found") from error


@app.get("/graph", response_model=GraphOverview)
def graph_overview(
    document_id: str | None = Query(default=None),
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Get graph overview.
    Only includes data from user's own documents.
    """
    return service.get_graph_overview(document_id=document_id, user_id=current_user.id)


@app.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Get analytics for the authenticated user.
    Only includes data from user's own documents.
    """
    return service.get_analytics(user_id=current_user.id)


@app.post("/query", response_model=QuestionResponse)
def query(
    request: QuestionRequest,
    service: DocumentQueryService = Depends(query_service),
    current_user: User = Depends(get_current_user_dependency),
) -> dict:
    """
    Ask a question about documents.
    Only searches within user's own documents.
    """
    try:
        return service.answer_question(
            request.question,
            document_id=request.document_id,
            user_id=current_user.id,
        )
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail="Document not found") from error

