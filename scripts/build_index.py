import argparse
import logging
import time
from pathlib import Path

from app.ingestion.chunking import chunk_documents
from app.ingestion.loader import load_directory
from app.retrieval.vector_store import VectorStore

DOCS_DIR = Path("data/sample_docs")
INDEX_DIR = Path("storage/index")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the FAISS index from a folder of documents.")
    parser.add_argument("--docs", type=Path, default=DOCS_DIR)
    parser.add_argument("--out", type=Path, default=INDEX_DIR)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    start = time.perf_counter()
    docs = load_directory(args.docs)
    chunks = chunk_documents(docs, args.chunk_size, args.overlap)
    if not chunks:
        raise SystemExit(f"No text found in {args.docs}. Add .pdf/.md/.txt files first.")

    store = VectorStore.build(chunks)
    store.save(args.out)
    elapsed = time.perf_counter() - start

    sources = sorted({c.metadata["source"] for c in chunks})
    print(f"Documents (pages/files): {len(docs)}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Chunks: {len(chunks)}  (size={args.chunk_size}, overlap={args.overlap})")
    print(f"Saved to: {args.out}")
    print(f"Took: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
