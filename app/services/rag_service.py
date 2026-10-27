import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

from app.config import Settings
from app.generation.citations import citation_tag, validate_citations
from app.generation.llm_client import LLMClient
from app.generation.prompts import ABSTAIN_ANSWER, PROMPT_VERSION, SYSTEM_PROMPT, build_prompt
from app.ingestion.chunking import Chunk

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000
SNIPPET_CHARS = 200


class Retriever(Protocol):
    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]: ...


@dataclass
class Source:
    citation: str
    source: str
    page: int | None
    score: float
    snippet: str
    # Which chunk of that page/file. With source and page it identifies the chunk on the knowledge map.
    chunk_index: int | None = None


@dataclass
class RAGAnswer:
    answer: str
    sources: list[Source]
    abstained: bool
    invalid_citations: list[str]
    prompt_version: str
    model: str
    timings_ms: dict[str, float] = field(default_factory=dict)


def validate_question(question: str) -> str:
    question = question.strip()
    if not question:
        raise ValueError("Question must not be empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"Question is too long ({len(question)} chars, max {MAX_QUESTION_CHARS})")
    return question


def _to_source(chunk: Chunk, score: float) -> Source:
    return Source(
        citation=citation_tag(chunk.metadata),
        source=chunk.metadata["source"],
        page=chunk.metadata.get("page"),
        score=round(score, 4),
        snippet=chunk.text[:SNIPPET_CHARS],
        chunk_index=chunk.metadata.get("chunk_index"),
    )


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower().rstrip(".")


def _is_abstain(answer: str) -> bool:
    # The whole answer must be the refusal. An invented answer that merely ends with
    # the refusal sentence (seen in evaluation, q29) is an answer, not a refusal.
    return _normalize(answer) == _normalize(ABSTAIN_ANSWER)


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


class RAGService:
    def __init__(self, store: Retriever, llm: LLMClient, settings: Settings):
        self.store = store
        self.llm = llm
        self.settings = settings

    def answer(self, question: str, top_k: int | None = None) -> RAGAnswer:
        question = validate_question(question)
        total_start = time.perf_counter()

        start = time.perf_counter()
        retrieved = self.store.search(question, top_k or self.settings.top_k)
        timings = {"retrieve": _ms(start), "generate": 0.0}
        sources = [_to_source(chunk, score) for chunk, score in retrieved]

        best_score = retrieved[0][1] if retrieved else 0.0
        if best_score < self.settings.min_score:
            logger.info("Abstaining: best score %.3f < min_score %.2f", best_score, self.settings.min_score)
            timings["total"] = _ms(total_start)
            return self._result(ABSTAIN_ANSWER, sources, True, [], timings)

        start = time.perf_counter()
        answer = self.llm.generate(SYSTEM_PROMPT, build_prompt(question, retrieved))
        timings["generate"] = _ms(start)

        _valid, invalid = validate_citations(answer, retrieved)
        if invalid:
            logger.warning("Answer cited sources that were not retrieved: %s", invalid)

        timings["total"] = _ms(total_start)
        logger.info("Answered in %s ms", timings)
        return self._result(answer, sources, _is_abstain(answer), invalid, timings)

    def _result(
        self, answer: str, sources: list[Source], abstained: bool, invalid: list[str], timings: dict[str, float]
    ) -> RAGAnswer:
        return RAGAnswer(
            answer=answer,
            sources=sources,
            abstained=abstained,
            invalid_citations=invalid,
            prompt_version=PROMPT_VERSION,
            model=self.llm.model,
            timings_ms=timings,
        )
