from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.services.rag_service import MAX_QUESTION_CHARS

MAX_TOP_K = 10

# strip_whitespace runs first, so "   " becomes "" and fails min_length -> 422.
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS)]


class AskRequest(BaseModel):
    question: Question
    top_k: int | None = Field(default=None, ge=1, le=MAX_TOP_K)


class SourceOut(BaseModel):
    citation: str
    source: str
    page: int | None
    score: float
    snippet: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    abstained: bool
    invalid_citations: list[str]
    prompt_version: str
    model: str
    timings_ms: dict[str, float]


class DocumentOut(BaseModel):
    source: str
    chunks: int


class UploadOut(BaseModel):
    filename: str
    bytes: int
    message: str


class RebuildOut(BaseModel):
    documents: int
    chunks: int
    sources: list[str]
    seconds: float


class HealthOut(BaseModel):
    status: str
    index_loaded: bool
    chunks: int
    llm_reachable: bool
    model: str


class ErrorOut(BaseModel):
    detail: str
