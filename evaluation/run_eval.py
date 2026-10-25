"""Reproducible evaluation of retrieval (and optionally the full RAG answer).

    python -m evaluation.run_eval                      # retrieval only, no LLM (fast)
    python -m evaluation.run_eval --with-llm           # full RAG: needs Ollama running
    python -m evaluation.run_eval --chunk-size 300 --overlap 100
    python -m evaluation.run_eval --sweep-min-score 0.2,0.25,0.3,0.35,0.4

The index is always rebuilt in memory from DOCS_DIR with the chunk settings being
evaluated, so the recorded config is exactly what was measured. storage/index is never touched.
"""

import argparse
import json
import logging
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.generation.citations import extract_citations
from app.generation.llm_client import LLMClient, LLMResponseError, LLMUnavailableError, OllamaClient
from app.generation.prompts import ABSTAIN_ANSWER, PROMPT_VERSION
from app.ingestion.chunking import chunk_documents
from app.ingestion.loader import load_directory
from app.retrieval.embedder import MODEL_NAME
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import RAGService
from evaluation.metrics import (
    Page,
    abstention_scores,
    citation_accuracy,
    first_hit_rank,
    keyword_coverage,
    mrr,
    percentile,
    recall_at_k,
)

DATASET = Path("evaluation/dataset.jsonl")
RESULTS_DIR = Path("evaluation/results")
RETRIEVE_DEPTH = 10  # how many chunks we look at for Recall@10 and MRR
REQUIRED_KEYS = {"id", "question", "expected_sources", "expected_answer_keywords", "should_abstain"}

logger = logging.getLogger(__name__)


@dataclass
class EvalItem:
    id: str
    question: str
    expected: set[Page]
    keywords: list[str]
    should_abstain: bool


# ---------- loading ----------

def load_dataset(path: Path) -> list[EvalItem]:
    items = []
    seen_ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: not valid JSON ({exc.msg})") from exc
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            raise ValueError(f"{path}:{line_number}: missing keys {sorted(missing)}")
        if row["id"] in seen_ids:
            raise ValueError(f"{path}:{line_number}: duplicate id {row['id']!r}")
        if not row["should_abstain"] and not row["expected_sources"]:
            raise ValueError(f"{path}:{line_number}: answerable question needs expected_sources")
        seen_ids.add(row["id"])
        items.append(
            EvalItem(
                id=row["id"],
                question=row["question"],
                expected={(s["source"], s.get("page")) for s in row["expected_sources"]},
                keywords=row["expected_answer_keywords"],
                should_abstain=bool(row["should_abstain"]),
            )
        )
    if not items:
        raise ValueError(f"{path} has no questions")
    return items


def build_store(settings: Settings) -> VectorStore:
    """Build a fresh in-memory index from DOCS_DIR with the chunk settings under test."""
    docs = load_directory(settings.docs_dir)
    chunks = chunk_documents(docs, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError(f"No text found in {settings.docs_dir}")
    return VectorStore.build(chunks)


def git_commit() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}-dirty" if dirty else commit


# ---------- evaluation ----------

def evaluate_retrieval(items: list[EvalItem], store: VectorStore, settings: Settings) -> list[dict]:
    rows = []
    for item in items:
        retrieved = store.search(item.question, RETRIEVE_DEPTH)
        pages = [(chunk.metadata["source"], chunk.metadata.get("page")) for chunk, _ in retrieved]
        best_score = retrieved[0][1] if retrieved else 0.0
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "should_abstain": item.should_abstain,
                "expected": sorted([list(p) for p in item.expected], key=str),
                "retrieved": [[source, page, round(score, 4)] for (source, page), (_c, score) in zip(pages, retrieved)],
                "best_score": round(best_score, 4),
                "first_hit_rank": first_hit_rank(item.expected, pages) if not item.should_abstain else None,
                "gate_abstained": best_score < settings.min_score,
            }
        )
    return rows


def is_clean_abstain(answer: str) -> bool:
    """Stricter than the app's check: the answer must be ONLY the refusal sentence.

    The app counts any answer that contains the sentence, so an invented answer
    that ends with "I couldn't find this in the documents." still counts as abstained.
    """
    return answer.strip().rstrip(".").lower() == ABSTAIN_ANSWER.rstrip(".").lower()


def evaluate_answers(items: list[EvalItem], rows: list[dict], service: RAGService) -> None:
    """Ask the full RAG pipeline every question and add answer fields to each row."""
    for item, row in zip(items, rows):
        try:
            result = service.answer(item.question)
        except (LLMUnavailableError, LLMResponseError) as exc:
            row["llm_error"] = str(exc)
            continue
        cited = extract_citations(result.answer)
        row.update(
            {
                "answer": result.answer,
                "abstained": result.abstained,
                "clean_abstained": is_clean_abstain(result.answer),
                "citations": cited,
                "invalid_citations": result.invalid_citations,
                "keyword_coverage": None if item.should_abstain else keyword_coverage(result.answer, item.keywords),
                "timings_ms": result.timings_ms,
            }
        )


def summarize(rows: list[dict], top_k: int) -> dict:
    answerable = [r for r in rows if not r["should_abstain"]]
    cases = [({tuple(p) for p in r["expected"]}, [(s, pg) for s, pg, _ in r["retrieved"]]) for r in answerable]
    truth = [r["should_abstain"] for r in rows]

    summary = {
        "questions": len(rows),
        "answerable": len(answerable),
        "should_abstain": sum(truth),
        "recall@1": recall_at_k(cases, 1),
        "recall@3": recall_at_k(cases, 3),
        f"recall@{top_k}": recall_at_k(cases, top_k),
        f"recall@{RETRIEVE_DEPTH}": recall_at_k(cases, RETRIEVE_DEPTH),
        f"mrr@{RETRIEVE_DEPTH}": mrr(cases),
        "gate_abstention": abstention_scores([r["gate_abstained"] for r in rows], truth),
    }

    answered = [r for r in rows if "answer" in r]
    if answered:
        coverage = [r["keyword_coverage"] for r in answered if r["keyword_coverage"] is not None]
        summary["llm"] = {
            "answered": len(answered),
            "llm_errors": sum(1 for r in rows if "llm_error" in r),
            "keyword_coverage": sum(coverage) / len(coverage) if coverage else None,
            "citation_accuracy": citation_accuracy(
                [len(r["citations"]) - len(r["invalid_citations"]) for r in answered],
                [len(r["citations"]) for r in answered],
            ),
            "answers_with_invalid_citation": sum(1 for r in answered if r["invalid_citations"]),
            "abstention": abstention_scores([r["abstained"] for r in answered], [r["should_abstain"] for r in answered]),
            "strict_abstention": abstention_scores(
                [r["clean_abstained"] for r in answered], [r["should_abstain"] for r in answered]
            ),
            "latency_ms": {
                name: {
                    "p50": percentile([r["timings_ms"][name] for r in answered], 50),
                    "p95": percentile([r["timings_ms"][name] for r in answered], 95),
                }
                for name in ("retrieve", "generate", "total")
            },
        }
    return summary


def min_score_sweep(rows: list[dict], thresholds: list[float]) -> list[dict]:
    """Re-score the retrieval gate at other MIN_SCORE values. Best scores don't depend on the threshold."""
    truth = [r["should_abstain"] for r in rows]
    table = []
    for threshold in thresholds:
        predicted = [r["best_score"] < threshold for r in rows]
        scores = abstention_scores(predicted, truth)
        table.append({"min_score": threshold, **scores})
    return table


# ---------- output ----------

def fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def markdown_report(config: dict, summary: dict) -> str:
    lines = [
        f"Config: chunk {config['chunk_size']}/{config['chunk_overlap']}, top_k {config['top_k']}, "
        f"min_score {config['min_score']}, embed {config['embedding_model'].split('/')[-1]}, "
        f"llm {config['llm_model'] or '-'}, prompt {config['prompt_version']}, commit {config['git_commit']}",
        f"Questions: {summary['questions']} ({summary['answerable']} answerable, {summary['should_abstain']} should abstain)",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key in ("recall@1", "recall@3", f"recall@{config['top_k']}", f"recall@{RETRIEVE_DEPTH}", f"mrr@{RETRIEVE_DEPTH}"):
        lines.append(f"| {key} | {fmt(summary[key])} |")
    gate = summary["gate_abstention"]
    lines.append(f"| gate abstention precision | {fmt(gate['precision'])} |")
    lines.append(f"| gate abstention recall | {fmt(gate['recall'])} |")
    llm = summary.get("llm")
    if llm:
        lines += [
            f"| LLM errors | {llm['llm_errors']} |",
            f"| keyword coverage (answerable) | {fmt(llm['keyword_coverage'])} |",
            f"| citation accuracy | {fmt(llm['citation_accuracy'])} |",
            f"| answers with an invalid citation | {llm['answers_with_invalid_citation']} |",
            f"| final abstention precision | {fmt(llm['abstention']['precision'])} |",
            f"| final abstention recall | {fmt(llm['abstention']['recall'])} |",
            f"| strict abstention precision (answer is only the refusal) | {fmt(llm['strict_abstention']['precision'])} |",
            f"| strict abstention recall (answer is only the refusal) | {fmt(llm['strict_abstention']['recall'])} |",
        ]
        for name, values in llm["latency_ms"].items():
            lines.append(f"| {name} latency p50 / p95 (ms) | {fmt(values['p50'])} / {fmt(values['p95'])} |")
    return "\n".join(lines)


def review_markdown(rows: list[dict]) -> str:
    """A table for a human to mark each answer as faithful to its sources or not."""
    lines = [
        "# Faithfulness review (human judgment)",
        "",
        "For each answered question, open the cited pages and mark **Faithful?** as `yes`, `partly` or `no`.",
        "",
        "| id | Question | Answer | Cited | Faithful? | Note |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "answer" not in r or r["abstained"]:
            continue
        answer = r["answer"].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {r['id']} | {r['question']} | {answer} | {', '.join(r['citations']) or '-'} |  |  |")
    return "\n".join(lines) + "\n"


def save_results(config: dict, summary: dict, rows: list[dict], sweep: list[dict] | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "llm" if config["with_llm"] else "retrieval"
    path = out_dir / f"{stamp}-{mode}-c{config['chunk_size']}o{config['chunk_overlap']}.json"
    payload = {"config": config, "summary": summary, "min_score_sweep": sweep, "questions": rows}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if config["with_llm"]:
        path.with_suffix(".review.md").write_text(review_markdown(rows), encoding="utf-8")
    return path


def run(
    settings: Settings, dataset: Path, with_llm: bool, llm: LLMClient | None = None,
    sweep_thresholds: list[float] | None = None, out_dir: Path | None = RESULTS_DIR,
) -> tuple[dict, dict, list[dict], Path | None]:
    items = load_dataset(dataset)
    store = build_store(settings)
    rows = evaluate_retrieval(items, store, settings)

    llm_model = None
    if with_llm:
        llm = llm or OllamaClient(settings)
        if not llm.is_reachable():
            raise LLMUnavailableError(f"Ollama is not reachable at {settings.ollama_url}. Start it with: ollama serve")
        llm_model = llm.model
        evaluate_answers(items, rows, RAGService(store, llm, settings))

    config = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "with_llm": with_llm,
        "llm_model": llm_model,
        "embedding_model": MODEL_NAME,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "min_score": settings.min_score,
        "prompt_version": PROMPT_VERSION,
        "temperature": settings.temperature if with_llm else None,
        "dataset": str(dataset),
        "chunks_in_index": len(store),
        "sources": sorted({c.metadata["source"] for c in store.chunks}),
    }
    summary = summarize(rows, settings.top_k)
    sweep = min_score_sweep(rows, sweep_thresholds) if sweep_thresholds else None
    path = save_results(config, summary, rows, sweep, out_dir) if out_dir else None
    return config, summary, rows, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval (and optionally full RAG answers).")
    parser.add_argument("--with-llm", action="store_true", help="also ask the LLM (needs Ollama)")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--chunk-size", type=int, help="override CHUNK_SIZE for this run")
    parser.add_argument("--overlap", type=int, help="override CHUNK_OVERLAP for this run")
    parser.add_argument("--min-score", type=float, help="override MIN_SCORE for this run")
    parser.add_argument("--sweep-min-score", help="comma-separated thresholds, e.g. 0.2,0.25,0.3")
    parser.add_argument("--no-save", action="store_true", help="print only, don't write results")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = Settings.from_env()
    overrides = {
        "chunk_size": args.chunk_size, "chunk_overlap": args.overlap, "min_score": args.min_score,
    }
    settings = replace(settings, **{k: v for k, v in overrides.items() if v is not None})
    thresholds = [float(t) for t in args.sweep_min_score.split(",")] if args.sweep_min_score else None

    try:
        config, summary, _rows, path = run(
            settings, args.dataset, args.with_llm, sweep_thresholds=thresholds,
            out_dir=None if args.no_save else RESULTS_DIR,
        )
    except (ValueError, LLMUnavailableError) as exc:
        raise SystemExit(f"Evaluation failed: {exc}")

    print(markdown_report(config, summary))
    if thresholds:
        print("\nMIN_SCORE sweep (retrieval gate only):\n")
        print("| min_score | abstain precision | abstain recall | correct refusals | wrong refusals | missed refusals |")
        print("|---|---|---|---|---|---|")
        for row in min_score_sweep(_rows, thresholds):
            print(
                f"| {row['min_score']:.2f} | {fmt(row['precision'])} | {fmt(row['recall'])} | "
                f"{row['true_positives']} | {row['false_positives']} | {row['false_negatives']} |"
            )
    if path:
        print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
