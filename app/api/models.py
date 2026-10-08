from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: str
    filename: str | None = None
    file_name: str | None = None
    document_type: str | None = None
    source: str | None = None


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    pages: int | None = None
    entities: int | None = None
    relationships: int | None = None
    error: str | None = None


class Entity(BaseModel):
    document_id: str | None = None
    mention_id: str | None = None
    canonical_id: str | None = None
    entity_id: str | None = None
    name: str | None = None
    canonical_name: str | None = None
    entity_type: str | None = None
    normalized_text: str | None = None
    page_number: int | None = None
    confidence: float | None = None
    extraction_method: str | None = None
    evidence_id: str | None = None


class Relationship(BaseModel):
    source_document_id: str | None = None
    relationship_type: str
    source_entity: dict[str, Any]
    target_entity: dict[str, Any]
    page_number: int | None = None
    evidence_id: str | None = None
    confidence: float | None = None
    extraction_method: str | None = None


class Evidence(BaseModel):
    document_id: str | None = None
    evidence_id: str
    page: int | None = None
    raw_text: str | None = None
    confidence: float | None = None
    extraction_method: str | None = None
    bbox: list[Any] | None = None
    normalized_bbox: list[Any] | None = None


class GraphEntity(BaseModel):
    entity_id: str
    name: str | None = None
    entity_type: str | None = None


class GraphResponse(BaseModel):
    entity: GraphEntity
    relationships: list[Relationship]


class GraphOverview(BaseModel):
    entities: list[GraphEntity]
    relationships: list[Relationship]


class AnalyticsResponse(BaseModel):
    document_count: int
    entity_count: int
    evidence_count: int
    relationship_count: int


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_id: str | None = None


class AnswerEvidence(BaseModel):
    document_id: str
    filename: str | None = None
    page: int | None = None
    evidence_id: str
    raw_text: str | None = None
    confidence: float | None = None
    extraction_method: str | None = None
    bbox: list[Any] | None = None
    normalized_bbox: list[Any] | None = None


class QuestionResponse(BaseModel):
    question: str
    answer: str
    document_id: str | None = None
    document: Document | None = None
    matched_entities: list[GraphEntity] = Field(default_factory=list)
    matched_relationships: list[Relationship] = Field(default_factory=list)
    evidence: list[AnswerEvidence] = Field(default_factory=list)

