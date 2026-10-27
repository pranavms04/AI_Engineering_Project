import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import AppState, get_state
from app.api.main import app
from app.config import Settings
from app.generation.llm_client import FakeLLMClient, LLMResponseError, LLMUnavailableError
from app.ingestion.chunking import Chunk
from app.retrieval.vector_store import VectorStore

# Invented sample text, not from any real document.
CHUNKS = [
    Chunk("Declare a typed path parameter in FastAPI with item_id: int.", {"source": "guide.pdf", "page": 1}),
    Chunk("FastAPI validates the path parameter and returns a 422 error for bad input.", {"source": "guide.pdf", "page": 2}),
    Chunk("Run the development server with uvicorn main:app --reload.", {"source": "notes.md"}),
]
GOOD_ANSWER = "Use item_id: int [guide.pdf, p. 1]."


class FailingLLM(FakeLLMClient):
    def __init__(self, error: Exception):
        super().__init__()
        self.error = error

    def generate(self, system: str, prompt: str) -> str:
        raise self.error


@pytest.fixture(scope="module")
def store() -> VectorStore:
    return VectorStore.build(CHUNKS)


@pytest.fixture
def make_client(store, tmp_path):
    """Build a TestClient whose AppState we control. No lifespan, so the real index and Ollama are never touched."""

    def _make(llm=None, with_store=True, **settings_overrides) -> tuple[TestClient, AppState]:
        settings = Settings(
            min_score=0.30,
            docs_dir=tmp_path / "docs",
            index_dir=tmp_path / "index",
            **settings_overrides,
        )
        state = AppState(settings=settings, llm=llm or FakeLLMClient(GOOD_ANSWER), store=store if with_store else None)
        app.dependency_overrides[get_state] = lambda: state
        return TestClient(app), state

    yield _make
    app.dependency_overrides.clear()


# ---------- /health ----------

def test_health_ok_when_index_loaded_and_llm_reachable(make_client):
    client, _ = make_client()
    body = client.get("/health").json()
    assert body == {"status": "ok", "index_loaded": True, "chunks": 3, "llm_reachable": True, "model": "fake-llm"}


def test_health_degraded_when_llm_down_and_no_index(make_client):
    client, _ = make_client(llm=FakeLLMClient(reachable=False), with_store=False)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["index_loaded"] is False
    assert body["chunks"] == 0
    assert body["llm_reachable"] is False


# ---------- /ask ----------

def test_ask_returns_cited_answer(make_client):
    client, state = make_client()
    response = client.post("/ask", json={"question": "How do I declare a typed path parameter?"})

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is False
    assert body["invalid_citations"] == []
    assert body["sources"][0]["citation"] == "[guide.pdf, p. 1]"
    assert len(state.llm.calls) == 1


def test_ask_top_k_limits_sources(make_client):
    client, _ = make_client()
    body = client.post("/ask", json={"question": "path parameter", "top_k": 2}).json()
    assert len(body["sources"]) == 2


def test_ask_off_topic_question_abstains_without_llm(make_client):
    client, state = make_client()
    body = client.post("/ask", json={"question": "What is the capital of France?"}).json()

    assert body["abstained"] is True
    assert state.llm.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 1001},
        {"question": "ok?", "top_k": 0},
        {"question": "ok?", "top_k": 11},
        {},
    ],
)
def test_ask_rejects_bad_input_with_422(make_client, payload):
    client, state = make_client()
    assert client.post("/ask", json=payload).status_code == 422
    assert state.llm.calls == []


def test_ask_returns_503_when_llm_unavailable(make_client):
    client, _ = make_client(llm=FailingLLM(LLMUnavailableError("Cannot reach Ollama. Is it running?")))
    response = client.post("/ask", json={"question": "How do I declare a typed path parameter?"})

    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_ask_returns_502_when_llm_replies_with_error(make_client):
    client, _ = make_client(llm=FailingLLM(LLMResponseError("Model 'x' not found")))
    response = client.post("/ask", json={"question": "How do I declare a typed path parameter?"})
    assert response.status_code == 502


def test_ask_returns_503_when_no_index(make_client):
    client, _ = make_client(with_store=False)
    response = client.post("/ask", json={"question": "anything"})
    assert response.status_code == 503
    assert "index" in response.json()["detail"].lower()


# ---------- /documents ----------

def test_list_documents_counts_chunks_per_source(make_client):
    client, _ = make_client()
    assert client.get("/documents").json() == [
        {"source": "guide.pdf", "chunks": 2},
        {"source": "notes.md", "chunks": 1},
    ]


def test_upload_saves_markdown_file(make_client):
    client, state = make_client()
    response = client.post("/documents", files={"file": ("new.md", b"# Hello\nSome text.", "text/markdown")})

    assert response.status_code == 201
    assert response.json()["filename"] == "new.md"
    assert (state.settings.docs_dir / "new.md").read_bytes() == b"# Hello\nSome text."


def test_upload_rejects_exe(make_client):
    client, state = make_client()
    response = client.post("/documents", files={"file": ("virus.exe", b"MZ...", "application/octet-stream")})

    assert response.status_code == 415
    assert not (state.settings.docs_dir / "virus.exe").exists()


def test_upload_rejects_oversize_file(make_client):
    client, state = make_client(max_upload_mb=1)
    too_big = b"a" * (1024 * 1024 + 1)
    response = client.post("/documents", files={"file": ("big.txt", too_big, "text/plain")})

    assert response.status_code == 413
    assert not (state.settings.docs_dir / "big.txt").exists()


@pytest.mark.parametrize("evil_name", ["../../x.md", "..\\..\\x.md", "/etc/x.md"])
def test_upload_strips_folders_from_filename(make_client, tmp_path, evil_name):
    client, state = make_client()
    response = client.post("/documents", files={"file": (evil_name, b"text", "text/markdown")})

    assert response.status_code == 201
    assert response.json()["filename"] == "x.md"
    assert (state.settings.docs_dir / "x.md").exists()
    assert not (tmp_path.parent / "x.md").exists()


def test_upload_rejects_duplicate_name(make_client):
    client, _ = make_client()
    file = {"file": ("same.md", b"one", "text/markdown")}
    assert client.post("/documents", files=file).status_code == 201
    assert client.post("/documents", files=file).status_code == 409


@pytest.mark.parametrize("bad_name", [".env.md", "..", ""])
def test_upload_rejects_hidden_or_empty_names(make_client, bad_name):
    client, _ = make_client()
    response = client.post("/documents", files={"file": (bad_name, b"text", "text/markdown")})
    assert response.status_code in (400, 422)


def test_upload_rejects_empty_file(make_client):
    client, _ = make_client()
    response = client.post("/documents", files={"file": ("empty.md", b"", "text/markdown")})
    assert response.status_code == 400


# ---------- /index/rebuild ----------

def test_rebuild_indexes_uploaded_document_and_swaps_store(make_client):
    client, state = make_client()
    text = b"Ollama runs language models locally on your own computer. It listens on port 11434."
    client.post("/documents", files={"file": ("ollama.md", text, "text/markdown")})

    response = client.post("/index/rebuild")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 1
    assert body["chunks"] >= 1
    assert body["sources"] == ["ollama.md"]
    assert (state.settings.index_dir / "chunks.json").exists()

    assert client.get("/documents").json() == [{"source": "ollama.md", "chunks": body["chunks"]}]
    answer = client.post("/ask", json={"question": "Which port does Ollama listen on?"}).json()
    assert answer["sources"][0]["source"] == "ollama.md"


def test_rebuild_with_no_documents_returns_400_and_keeps_old_store(make_client, store):
    client, state = make_client()
    response = client.post("/index/rebuild")

    assert response.status_code == 400
    assert state.store is store


# ---------- CORS ----------

def test_cors_allows_streamlit_origin_only(make_client):
    client, _ = make_client()
    allowed = client.get("/health", headers={"Origin": "http://localhost:8501"})
    blocked = client.get("/health", headers={"Origin": "http://evil.example"})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-origin" not in blocked.headers


# ---------- knowledge map + web app ----------

def test_index_map_returns_one_point_per_chunk(make_client):
    client, _ = make_client()
    body = client.get("/index/map").json()

    assert len(body["points"]) == 3
    assert [p["id"] for p in body["points"]] == [0, 1, 2]
    assert {p["source"] for p in body["points"]} == {"guide.pdf", "notes.md"}
    assert all(-1.0001 <= p[axis] <= 1.0001 for p in body["points"] for axis in "xyz")
    assert len(body["explained_variance"]) == 3
    assert all(p["preview"] for p in body["points"])


def test_index_map_is_stable_between_calls(make_client):
    client, _ = make_client()
    assert client.get("/index/map").json() == client.get("/index/map").json()


def test_index_map_is_empty_without_index(make_client):
    client, _ = make_client(with_store=False)
    body = client.get("/index/map").json()
    assert body["points"] == []


def test_ask_returns_question_point_and_chunk_ids(make_client):
    client, _ = make_client()
    body = client.post("/ask", json={"question": "How do I declare a typed path parameter?"}).json()

    assert len(body["question_point"]) == 3
    assert all(isinstance(v, float) for v in body["question_point"])
    # The hand-made test chunks have no chunk_index; real ones do (see the rebuild test below).
    assert "chunk_index" in body["sources"][0]


def test_question_lands_nearer_its_best_source_than_an_unrelated_chunk(make_client):
    client, _ = make_client()
    points = {(p["source"], p["page"]): p for p in client.get("/index/map").json()["points"]}
    body = client.post("/ask", json={"question": "How do I run the development server with uvicorn?"}).json()

    q = body["question_point"]
    def dist(p):
        return sum((q[i] - p[axis]) ** 2 for i, axis in enumerate("xyz")) ** 0.5
    assert body["sources"][0]["source"] == "notes.md"
    assert dist(points[("notes.md", None)]) < dist(points[("guide.pdf", 1)])


def test_rebuild_clears_the_cached_map(make_client):
    client, state = make_client()
    client.get("/index/map")
    assert state.projection is not None
    client.post("/documents", files={"file": ("ollama.md", b"Ollama listens on port 11434.", "text/markdown")})
    client.post("/index/rebuild")
    assert state.projection is None
    assert [p["source"] for p in client.get("/index/map").json()["points"]] == ["ollama.md"]
    answer = client.post("/ask", json={"question": "Which port does Ollama use?"}).json()
    assert answer["sources"][0]["chunk_index"] == 0  # real chunks carry their index


def test_web_app_is_served_with_strict_security_policy(make_client):
    client, _ = make_client()
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "connect-src 'self'" in csp
    assert page.headers["x-content-type-options"] == "nosniff"
    assert client.get("/app.js").status_code == 200


def test_api_docs_page_is_not_blocked_by_the_web_policy(make_client):
    client, _ = make_client()
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers


def test_api_routes_still_win_over_the_web_mount(make_client):
    client, _ = make_client()
    assert client.get("/health").json()["status"] == "ok"
