import pytest
from app.config import Settings
from app.generation.llm_client import FakeLLMClient, LLMUnavailableError
from app.generation.prompts import ABSTAIN_ANSWER
from app.ingestion.chunking import Chunk
from app.services.rag_service import MAX_QUESTION_CHARS, RAGService

CHUNK = Chunk("Declare a typed path parameter with item_id: int.", {"source": "fastapi.pdf", "page": 2})


class FakeStore:
    """In-memory retriever that returns fixed results with a fixed score."""

    def __init__(self, score: float):
        self.score = score
        self.last_k = None

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        self.last_k = k
        return [(CHUNK, self.score)]


def make_service(score: float, answer: str = "Use item_id: int [fastapi.pdf, p. 2]."):
    llm = FakeLLMClient(answer)
    return RAGService(FakeStore(score), llm, Settings(min_score=0.30, top_k=4)), llm


def test_good_evidence_calls_llm_and_returns_cited_answer():
    service, llm = make_service(score=0.6)
    result = service.answer("How do I type a path parameter?")

    assert len(llm.calls) == 1
    _system, prompt = llm.calls[0]
    assert "item_id: int" in prompt
    assert result.abstained is False
    assert result.invalid_citations == []
    assert result.sources[0].citation == "[fastapi.pdf, p. 2]"
    assert result.model == "fake-llm"
    assert result.prompt_version == "v1"
    assert set(result.timings_ms) == {"retrieve", "generate", "total"}
    assert result.timings_ms["total"] >= result.timings_ms["generate"]


def test_low_score_abstains_without_calling_llm():
    service, llm = make_service(score=0.1)
    result = service.answer("What is the capital of France?")

    assert llm.calls == []
    assert result.abstained is True
    assert result.answer == ABSTAIN_ANSWER
    assert result.timings_ms["generate"] == 0.0
    assert result.sources, "sources are still returned so the user can see why"


def test_llm_saying_it_cannot_answer_is_marked_abstained():
    service, _llm = make_service(score=0.6, answer=ABSTAIN_ANSWER)
    assert service.answer("Something tangential?").abstained is True


def test_invented_citation_is_reported():
    service, _llm = make_service(score=0.6, answer="It is in [other.pdf, p. 5].")
    assert service.answer("Where is it?").invalid_citations == ["[other.pdf, p. 5]"]


def test_top_k_override_is_passed_to_store():
    service, _llm = make_service(score=0.6)
    service.answer("question", top_k=2)
    assert service.store.last_k == 2


@pytest.mark.parametrize("question", ["", "   ", "x" * (MAX_QUESTION_CHARS + 1)])
def test_empty_or_too_long_question_is_rejected(question):
    service, llm = make_service(score=0.6)
    with pytest.raises(ValueError):
        service.answer(question)
    assert llm.calls == []


def test_llm_unavailable_propagates():
    class DownLLM(FakeLLMClient):
        def generate(self, system, prompt):
            raise LLMUnavailableError("down")

    service = RAGService(FakeStore(0.6), DownLLM(), Settings())
    with pytest.raises(LLMUnavailableError):
        service.answer("question")


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("TOP_K", "7")
    monkeypatch.setenv("MIN_SCORE", "0.45")
    monkeypatch.setenv("OLLAMA_URL", "http://example.test:11434/")
    settings = Settings.from_env()
    assert (settings.top_k, settings.min_score) == (7, 0.45)
    assert settings.ollama_url == "http://example.test:11434"
