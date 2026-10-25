import logging
import time
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.chunking import chunk_documents
from app.ingestion.loader import load_directory
from app.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    documents: int
    chunks: int
    sources: list[str]
    seconds: float


def rebuild_index(
    docs_dir: Path, index_dir: Path, chunk_size: int = 500, overlap: int = 100
) -> tuple[VectorStore, IndexStats]:
    """Load every document in docs_dir, chunk, embed, and save the index to index_dir."""
    start = time.perf_counter()
    if not docs_dir.is_dir():
        raise ValueError(f"Documents folder {docs_dir} does not exist. Add .pdf/.md/.txt files first.")
    docs = load_directory(docs_dir)
    chunks = chunk_documents(docs, chunk_size, overlap)
    if not chunks:
        raise ValueError(f"No text found in {docs_dir}. Add .pdf/.md/.txt files first.")

    store = VectorStore.build(chunks)
    store.save(index_dir)

    stats = IndexStats(
        documents=len(docs),
        chunks=len(chunks),
        sources=sorted({c.metadata["source"] for c in chunks}),
        seconds=round(time.perf_counter() - start, 2),
    )
    logger.info("Rebuilt index: %d documents, %d chunks in %.2fs", stats.documents, stats.chunks, stats.seconds)
    return store, stats
