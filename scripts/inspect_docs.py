import logging
from pathlib import Path

from app.ingestion.loader import load_directory

SAMPLE_DOCS = Path("data/sample_docs")


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    docs = load_directory(SAMPLE_DOCS)
    print(f"Loaded {len(docs)} documents")
    for doc in docs[:3]:
        print(doc.metadata)
        print(doc.text[:200], "\n---")


if __name__ == "__main__":
    main()
