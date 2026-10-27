import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, Request

from app.config import Settings
from app.generation.llm_client import LLMClient, OllamaClient
from app.retrieval.projection import Projection, fit_projection
from app.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Everything the endpoints share. Created once at startup."""

    settings: Settings
    llm: LLMClient
    store: VectorStore | None
    # Only one rebuild at a time. /ask keeps working with the old store until the new one is swapped in.
    rebuild_lock: threading.Lock = field(default_factory=threading.Lock)
    # 3-d projection for the knowledge map. Built on first use, cleared when the store is replaced.
    projection: Projection | None = None

    def get_projection(self) -> Projection | None:
        if self.store is None or len(self.store) == 0:
            return None
        if self.projection is None:
            vectors = self.store.index.reconstruct_n(0, self.store.index.ntotal)
            self.projection = fit_projection(vectors)
        return self.projection

    def replace_store(self, store: VectorStore) -> None:
        self.store = store
        self.projection = None


def load_store(settings: Settings) -> VectorStore | None:
    try:
        return VectorStore.load(settings.index_dir)
    except (FileNotFoundError, ValueError) as exc:
        # The API still starts; /health reports index_loaded=false and /ask returns 503.
        logger.warning("Index not loaded: %s", exc)
        return None


def create_state(settings: Settings) -> AppState:
    return AppState(settings=settings, llm=OllamaClient(settings), store=load_store(settings))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag = create_state(Settings.from_env())
    logger.info("API ready (index loaded: %s)", app.state.rag.store is not None)
    yield


def get_state(request: Request) -> AppState:
    """Endpoints ask for this with Depends(get_state). Tests replace it with dependency_overrides."""
    return request.app.state.rag
