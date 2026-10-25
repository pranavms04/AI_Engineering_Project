import logging
import time
from collections import Counter
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import AppState, get_state, lifespan
from app.api.schemas import (
    AskRequest,
    AskResponse,
    DocumentOut,
    ErrorOut,
    HealthOut,
    RebuildOut,
    UploadOut,
)
from app.api.uploads import UploadError, check_size, safe_filename, save_upload
from app.generation.llm_client import LLMResponseError, LLMUnavailableError
from app.services.indexing import rebuild_index
from app.services.rag_service import RAGService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# The Streamlit UI (Phase 8) runs on port 8501. Nothing else may call the API from a browser.
ALLOWED_ORIGINS = ["http://localhost:8501", "http://127.0.0.1:8501"]

app = FastAPI(title="AI Knowledge Assistant", version="0.7.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def log_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %d in %.1f ms", request.method, request.url.path, response.status_code, ms)
    return response


@app.get("/health", response_model=HealthOut)
def health(state: AppState = Depends(get_state)) -> HealthOut:
    index_loaded = state.store is not None
    llm_reachable = state.llm.is_reachable()
    return HealthOut(
        status="ok" if index_loaded and llm_reachable else "degraded",
        index_loaded=index_loaded,
        chunks=len(state.store) if index_loaded else 0,
        llm_reachable=llm_reachable,
        model=state.llm.model,
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    responses={502: {"model": ErrorOut}, 503: {"model": ErrorOut}},
)
def ask(request: AskRequest, state: AppState = Depends(get_state)) -> AskResponse:
    if state.store is None:
        raise HTTPException(503, "No index loaded. Upload documents, then POST /index/rebuild.")

    service = RAGService(state.store, state.llm, state.settings)
    try:
        result = service.answer(request.question, top_k=request.top_k)
    except LLMUnavailableError as exc:
        raise HTTPException(503, str(exc))
    except LLMResponseError as exc:
        raise HTTPException(502, str(exc))
    return AskResponse.model_validate(asdict(result))


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(state: AppState = Depends(get_state)) -> list[DocumentOut]:
    if state.store is None:
        return []
    counts = Counter(chunk.metadata["source"] for chunk in state.store.chunks)
    return [DocumentOut(source=source, chunks=n) for source, n in sorted(counts.items())]


@app.post(
    "/documents",
    response_model=UploadOut,
    status_code=201,
    responses={400: {"model": ErrorOut}, 409: {"model": ErrorOut}, 413: {"model": ErrorOut}, 415: {"model": ErrorOut}},
)
async def upload_document(file: UploadFile, state: AppState = Depends(get_state)) -> UploadOut:
    max_bytes = state.settings.max_upload_mb * 1024 * 1024
    try:
        name = safe_filename(file.filename)
        # Read one byte more than allowed: if we get it, the file is too big.
        content = await file.read(max_bytes + 1)
        check_size(content, max_bytes)
        save_upload(state.settings.docs_dir, name, content)
    except UploadError as exc:
        raise HTTPException(exc.status_code, exc.message)

    logger.info("Saved upload %s (%d bytes)", name, len(content))
    return UploadOut(filename=name, bytes=len(content), message="Saved. Run POST /index/rebuild to make it searchable.")


@app.post("/index/rebuild", response_model=RebuildOut, responses={400: {"model": ErrorOut}, 409: {"model": ErrorOut}})
def rebuild(state: AppState = Depends(get_state)) -> RebuildOut:
    # Synchronous: the request waits until the index is rebuilt. Fine for a demo;
    # a real app would run this as a background job and let the client poll.
    if not state.rebuild_lock.acquire(blocking=False):
        raise HTTPException(409, "A rebuild is already running. Try again shortly.")
    try:
        settings = state.settings
        store, stats = rebuild_index(settings.docs_dir, settings.index_dir, settings.chunk_size, settings.chunk_overlap)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        state.rebuild_lock.release()

    state.store = store
    return RebuildOut(**asdict(stats))
