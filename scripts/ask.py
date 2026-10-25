import argparse
import logging

from app.config import Settings
from app.generation.llm_client import LLMResponseError, LLMUnavailableError, OllamaClient
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import RAGService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question and get a cited answer from your documents.")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=None, help="chunks to retrieve (default: TOP_K)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show log messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    settings = Settings.from_env()
    store = VectorStore.load(settings.index_dir)
    service = RAGService(store, OllamaClient(settings), settings)

    try:
        result = service.answer(args.question, top_k=args.k)
    except (LLMUnavailableError, LLMResponseError) as exc:
        raise SystemExit(f"LLM error: {exc}")
    except ValueError as exc:
        raise SystemExit(f"Invalid question: {exc}")

    print(f"Question: {args.question}\n")
    print(result.answer)
    print()
    if result.abstained:
        print("(abstained — not enough evidence in the documents)")
    if result.invalid_citations:
        print(f"WARNING invalid citations: {', '.join(result.invalid_citations)}")

    print("\nRetrieved sources:")
    print(f"  {'score':>6}  citation")
    for source in result.sources:
        print(f"  {source.score:>6.3f}  {source.citation}")

    t = result.timings_ms
    print(
        f"\nmodel={result.model}  prompt={result.prompt_version}  "
        f"retrieve={t['retrieve']:.0f} ms  generate={t['generate']:.0f} ms  total={t['total']:.0f} ms"
    )


if __name__ == "__main__":
    main()
