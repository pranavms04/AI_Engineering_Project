import argparse
import logging
from pathlib import Path

from app.config import Settings
from app.services.indexing import rebuild_index


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Build the FAISS index from a folder of documents.")
    parser.add_argument("--docs", type=Path, default=settings.docs_dir)
    parser.add_argument("--out", type=Path, default=settings.index_dir)
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--overlap", type=int, default=settings.chunk_overlap)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        _store, stats = rebuild_index(args.docs, args.out, args.chunk_size, args.overlap)
    except ValueError as exc:
        raise SystemExit(str(exc))

    print(f"Documents (pages/files): {stats.documents}")
    print(f"Sources: {', '.join(stats.sources)}")
    print(f"Chunks: {stats.chunks}  (size={args.chunk_size}, overlap={args.overlap})")
    print(f"Saved to: {args.out}")
    print(f"Took: {stats.seconds:.1f}s")


if __name__ == "__main__":
    main()
