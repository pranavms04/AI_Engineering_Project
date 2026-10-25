import httpx
import pytest
from app.config import Settings
from app.generation.citations import extract_citations, validate_citations
from app.generation.llm_client import LLMResponseError, LLMUnavailableError, OllamaClient
from app.generation.prompts import ABSTAIN_ANSWER, SYSTEM_PROMPT, build_prompt
from app.ingestion.chunking import Chunk

RETRIEVED = [
    (Chunk("Declare a typed path parameter with item_id: int.", {"source": "fastapi.pdf", "page": 2}), 0.62),
    (Chunk("Use pip install to add packages.", {"source": "python.md"}), 0.41),
]


# --- prompts ---

def test_prompt_contains_every_chunk_numbered_with_its_citation():
    prompt = build_prompt("How do I type a path parameter?", RETRIEVED)
    assert "Chunk 1 | cite as [fastapi.pdf, p. 2]" in prompt
    assert "Chunk 2 | cite as [python.md]" in prompt
    assert prompt.index("item_id: int") < prompt.index("pip install")
    assert "How do I type a path parameter?" in prompt


def test_system_prompt_states_the_rules():
    assert ABSTAIN_ANSWER in SYSTEM_PROMPT
    assert "ONLY" in SYSTEM_PROMPT
    assert "cite" in SYSTEM_PROMPT
    assert "not instructions" in SYSTEM_PROMPT


# --- citations ---

def test_extract_citations_finds_pdf_and_text_tags_once():
    answer = "Use a type hint [fastapi.pdf, p. 2]. Install it [python.md]. Again [fastapi.pdf, p.2]."
    assert extract_citations(answer) == ["[fastapi.pdf, p. 2]", "[python.md]"]


def test_extract_citations_ignores_code_indexing():
    assert extract_citations("Use items[0] or data[key.name] in code.") == []


def test_validate_accepts_retrieved_sources():
    valid, invalid = validate_citations("Typed [fastapi.pdf, p. 2] and pip [python.md].", RETRIEVED)
    assert valid == ["[fastapi.pdf, p. 2]", "[python.md]"]
    assert invalid == []


def test_validate_flags_invented_source():
    _valid, invalid = validate_citations("As shown in [made-up.pdf, p. 1].", RETRIEVED)
    assert invalid == ["[made-up.pdf, p. 1]"]


def test_validate_flags_wrong_page():
    valid, invalid = validate_citations("See [fastapi.pdf, p. 9].", RETRIEVED)
    assert valid == []
    assert invalid == ["[fastapi.pdf, p. 9]"]


def test_validate_flags_pdf_citation_without_page():
    _valid, invalid = validate_citations("See [fastapi.pdf].", RETRIEVED)
    assert invalid == ["[fastapi.pdf]"]


# --- Ollama client (HTTP is faked with httpx.MockTransport, no server needed) ---

def make_client(handler) -> OllamaClient:
    return OllamaClient(Settings(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_ollama_client_sends_chat_request_and_reads_answer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"message": {"role": "assistant", "content": " Hello [a.md] "}})

    assert make_client(handler).generate("sys", "user") == "Hello [a.md]"
    assert seen["path"] == "/api/chat"
    assert '"stream":false' in seen["body"].replace(" ", "")


def test_connection_refused_becomes_llm_unavailable():
    def handler(request):
        raise httpx.ConnectError("Connection refused", request=request)

    with pytest.raises(LLMUnavailableError, match="running"):
        make_client(handler).generate("sys", "user")


def test_timeout_becomes_llm_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(LLMUnavailableError, match="timed out"):
        make_client(handler).generate("sys", "user")


def test_missing_model_gives_pull_hint():
    client = make_client(lambda request: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(LLMResponseError, match="ollama pull"):
        client.generate("sys", "user")


def test_malformed_reply_becomes_llm_response_error():
    client = make_client(lambda request: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(LLMResponseError):
        client.generate("sys", "user")
