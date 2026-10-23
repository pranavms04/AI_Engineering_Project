import json
import logging
from dataclasses import asdict
from pathlib import Path

import faiss

from app.ingestion.chunking import Chunk
from app.retrieval.embedder import MODEL_NAME, embed_query, embed_texts

logger = logging.getLogger(__name__)

INDEX_FILE = "index.faiss"
CHUNKS_FILE = "chunks.json"


class VectorStore:
    def __init__(self, index: faiss.Index, chunks: list[Chunk], model_name: str = MODEL_NAME):
        if index.ntotal != len(chunks):
            raise ValueError(f"Index has {index.ntotal} vectors but there are {len(chunks)} chunks")
        self.index = index
        self.chunks = chunks
        self.model_name = model_name

    @classmethod
    def build(cls, chunks: list[Chunk]) -> "VectorStore":
        vectors = embed_texts([c.text for c in chunks])
        # Vectors are normalized, so inner product == cosine similarity.
        index = faiss.IndexFlatIP(vectors.shape[1])
        if len(chunks):
            index.add(vectors)
        logger.info("Built index with %d chunks", index.ntotal)
        return cls(index, chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        k = min(k, len(self.chunks))
        query_vector = embed_query(query).reshape(1, -1)
        scores, ids = self.index.search(query_vector, k)
        return [(self.chunks[i], float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(folder / INDEX_FILE))
        payload = {
            "model_name": self.model_name,
            "chunks": [asdict(c) for c in self.chunks],
        }
        (folder / CHUNKS_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved %d chunks to %s", len(self.chunks), folder)

    @classmethod
    def load(cls, folder: Path) -> "VectorStore":
        index_path = folder / INDEX_FILE
        chunks_path = folder / CHUNKS_FILE
        if not index_path.exists() or not chunks_path.exists():
            raise FileNotFoundError(f"No index in {folder}. Run: python -m scripts.build_index")

        payload = json.loads(chunks_path.read_text(encoding="utf-8"))
        if payload.get("model_name") != MODEL_NAME:
            raise ValueError(
                f"Index was built with {payload.get('model_name')!r}, "
                f"but the embedder uses {MODEL_NAME!r}. Rebuild the index."
            )

        chunks = [Chunk(text=c["text"], metadata=c["metadata"]) for c in payload["chunks"]]
        index = faiss.read_index(str(index_path))
        return cls(index, chunks)
