"""Copy real numbers from evaluation/results into data/eval.json for the landing page.

Run from repo root: python3 scrollcraft/builds/knowledge-assistant/capture/metrics.py
Only copies values; every number keeps the name of the results file it came from.
"""
import json
from pathlib import Path

RESULTS = Path("evaluation/results")
RETRIEVAL = "20261025-221343-retrieval-c500o100.json"
LLM_RUNS = [
    "20261025-220558-llm-c500o100.json",
    "20261025-220910-llm-c500o100.json",
    "20261025-221228-llm-c500o100.json",
]
OUT = Path(__file__).resolve().parent.parent / "data" / "eval.json"

retrieval = json.loads((RESULTS / RETRIEVAL).read_text())
answerable = [q for q in retrieval["questions"] if not q["should_abstain"]]
hits_at_4 = sum(1 for q in answerable if q["first_hit_rank"] is not None and q["first_hit_rank"] <= 4)

ABSTAIN_ANSWER = "I couldn't find this in the documents."


def is_clean_abstain(answer: str) -> bool:
    """Same rule as evaluation/run_eval.py: the answer must be ONLY the refusal sentence.

    The app's own check also counts an invented answer that ends with the sentence,
    which over-counted run 1. Recomputed from the rows so every run uses the strict rule.
    """
    return answer.strip().rstrip(".").lower() == ABSTAIN_ANSWER.rstrip(".").lower()


runs = []
for name in LLM_RUNS:
    result = json.loads((RESULTS / name).read_text())
    s = result["summary"]["llm"]
    should = [q for q in result["questions"] if q["should_abstain"] and "answer" in q]
    missed = [q["question"] for q in should if not is_clean_abstain(q["answer"])]
    runs.append({
        "file": name,
        "citation_accuracy": s["citation_accuracy"],
        "answers_with_invalid_citation": s["answers_with_invalid_citation"],
        "abstention_true_positives": len(should) - len(missed),
        "abstention_missed": missed,
        "generate_p50_ms": s["latency_ms"]["generate"]["p50"],
        "total_p50_ms": s["latency_ms"]["total"]["p50"],
        "total_p95_ms": s["latency_ms"]["total"]["p95"],
    })

payload = {
    "retrieval_file": RETRIEVAL,
    "config": {k: retrieval["config"][k] for k in ("date", "chunk_size", "chunk_overlap", "top_k", "min_score", "embedding_model", "chunks_in_index")},
    "questions_total": len(retrieval["questions"]),
    "answerable": len(answerable),
    "should_abstain": sum(q["should_abstain"] for q in retrieval["questions"]),
    "hits_at_4": hits_at_4,
    "mrr_at_10": retrieval["summary"]["mrr@10"],
    "questions": [
        {"id": q["id"], "question": q["question"], "should_abstain": q["should_abstain"], "best_score": q["best_score"]}
        for q in retrieval["questions"]
    ],
    "llm_runs": runs,
}
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: v for k, v in payload.items() if k != "questions"}, indent=1))
print("best scores:", sorted((q["best_score"], q["should_abstain"]) for q in payload["questions"]))
