---
name: run-evaluation
description: Build, run and report the RAG evaluation (Recall@k, MRR, keyword coverage, citation accuracy, abstention, latency) with recorded configuration, and run controlled experiments against a saved baseline. Use for Phase 9, or whenever the user asks "how good is it", "measure", "evaluate", "benchmark", "compare settings" or wants numbers for the README.
---

# Run the evaluation honestly

## Principles
- Numbers come only from running `evaluation/run_eval.py` in this repo. Never estimate, invent, or round up.
- Change ONE variable per experiment. Same dataset, same machine, record the config.
- Always compare against the saved baseline in `evaluation/results/`.
- Say which metrics are objective (Recall@k, MRR, citation validity, abstention, latency) and which need human judgment (answer correctness, groundedness, helpfulness).

## Dataset (`evaluation/dataset.jsonl`)
One JSON object per line:
`{"id": "q01", "question": "...", "expected_sources": [{"source": "x.pdf", "page": 2}], "expected_answer_keywords": ["int", "type hint"], "should_abstain": false}`
- Draft questions by reading the indexed chunks; include paraphrases with little keyword overlap, multi-page questions, and ≥5 should-abstain questions.
- The user reviews and approves the dataset before it is used. They own the ground truth.

## Metrics (`evaluation/metrics.py`, unit tested)
- `recall_at_k`: fraction of questions where any expected (source, page) is in the top-k retrieved.
- `mrr`: mean of 1/rank of the first correct chunk (0 if none).
- `keyword_coverage`: fraction of expected keywords present in the answer (rough proxy, state its weakness).
- `citation_accuracy`: valid citations / all citations.
- Abstention: precision and recall of `abstained` vs `should_abstain`.
- Latency: p50 / p95 of retrieve, generate, total (ms).

## Running
- Retrieval-only (fast, no LLM): `python -m evaluation.run_eval`
- Full RAG (needs Ollama): `python -m evaluation.run_eval --with-llm`
- Each run writes `evaluation/results/<timestamp>.json` with: config (LLM model, embedding model, chunk_size, overlap, top_k, min_score, prompt_version), git commit hash, date, per-question results, aggregate metrics.

## Reporting
Print a markdown table. When comparing, show baseline vs new and the difference, plus failure examples (2–3 questions that got worse/better and why). Note dataset size and that results are indicative, not statistically strong.
