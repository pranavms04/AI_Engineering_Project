import argparse
import time
from pathlib import Path

from app.retrieval.vector_store import VectorStore

INDEX_DIR = Path("storage/index")


def citation_tag(metadata: dict) -> str:
    if "page" in metadata:
        return f"[{metadata['source']}, p. {metadata['page']}]"
    return f"[{metadata['source']}]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the FAISS index (retrieval only, no LLM).")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--index", type=Path, default=INDEX_DIR)
    args = parser.parse_args()

    store = VectorStore.load(args.index)

    start = time.perf_counter()
    results = store.search(args.question, args.k)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"Question: {args.question}")
    print(f"Searched {len(store)} chunks in {elapsed_ms:.0f} ms\n")
    for rank, (chunk, score) in enumerate(results, start=1):
        preview = chunk.text[:200].replace("\n", " ")
        print(f"{rank}. score={score:.3f}  {citation_tag(chunk.metadata)}  chunk={chunk.metadata['chunk_index']}")
        print(f"   {preview}\n")


if __name__ == "__main__":
    main()
