"""Re-score saved LLM runs with the current citation and refusal checks. No LLM calls.

    python -m evaluation.rescore evaluation/results/<run>-llm-*.json [...]

The answers are exactly the ones saved in each file; only the scoring changes. So any
difference from the saved summary comes from the code change, not from the model.
"""

import argparse
import json
from pathlib import Path

from app.generation.citations import citation_tag, extract_citations
from app.services.rag_service import _is_abstain
from evaluation.metrics import abstention_scores, citation_accuracy


def rescore(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    top_k = payload["config"]["top_k"]
    answered = [q for q in payload["questions"] if "answer" in q]

    valid_counts, total_counts, with_invalid = [], [], 0
    for q in answered:
        # The model only saw the top_k chunks, so only those are allowed citations.
        allowed = {citation_tag({"source": s} if p is None else {"source": s, "page": p}) for s, p, _ in q["retrieved"][:top_k]}
        tags = extract_citations(q["answer"])
        invalid = [t for t in tags if t not in allowed]
        valid_counts.append(len(tags) - len(invalid))
        total_counts.append(len(tags))
        with_invalid += bool(invalid)

    old = payload["summary"]["llm"]
    abstention = abstention_scores([_is_abstain(q["answer"]) for q in answered], [q["should_abstain"] for q in answered])
    return {
        "file": path.name,
        "citation_accuracy": (old["citation_accuracy"], citation_accuracy(valid_counts, total_counts)),
        "answers_with_invalid_citation": (old["answers_with_invalid_citation"], with_invalid),
        "abstention_precision": (old["abstention"]["precision"], abstention["precision"]),
        "abstention_recall": (old["abstention"]["recall"], abstention["recall"]),
        "abstention_true_positives": (old["abstention"]["true_positives"], abstention["true_positives"]),
    }


def fmt(value) -> str:
    return "n/a" if value is None else (f"{value:.3f}" if isinstance(value, float) else str(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score saved LLM runs with the current checks.")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    print("| Run | Metric | Saved | Re-scored |")
    print("|---|---|---|---|")
    for path in args.files:
        result = rescore(path)
        name = result.pop("file")
        for key, (before, after) in result.items():
            print(f"| {name[:15]} | {key} | {fmt(before)} | {fmt(after)} |")


if __name__ == "__main__":
    main()
