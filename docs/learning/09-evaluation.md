# Phase 9 — Evaluation

## 1. What we built and why

Until now we judged the assistant by asking a few questions and looking at the answers. That
doesn't scale and it isn't honest: you remember the good answers. Phase 9 adds a fixed set of
30 questions with known right pages, metric functions with unit tests, and one command that
measures retrieval and (optionally) full answers, saving every number with the exact settings
and git commit that produced it. We then used it to test two settings (chunk size, MIN_SCORE)
instead of guessing.

## 2. Explain like I'm five

It's a **school exam for the assistant**.
- The **question paper** is `dataset.jsonl`. You (the teacher) approved every question and its answer key.
- The **answer key** says which page holds the answer, and a few words a good answer should contain.
- Some questions are **trick questions**: the book doesn't cover them. The right answer is "I don't know".
- The **marking scheme** is `metrics.py`. Every rule is written down and tested.
- The **report card** is a JSON file in `results/`, stamped with the date and the exact study conditions.
- Some things the marking scheme can't judge — like whether an answer is actually *true*. A human teacher marks those (`*.review.md`).

## 3. Diagram

```mermaid
flowchart TD
    D[(dataset.jsonl<br/>30 questions)] -->|EvalItem: question, expected pages, keywords, should_abstain| L[load_dataset]
    S[(data/sample_docs)] -->|documents| B[build_store<br/>in memory, chunk size under test]
    L --> R[evaluate_retrieval]
    B -->|VectorStore| R
    R -->|per question: top-10 pages + scores, best score, first correct rank| Q{--with-llm?}
    Q -->|no| SUM[summarize]
    Q -->|yes| A[evaluate_answers<br/>RAGService + Ollama]
    A -->|answer, citations, invalid citations, abstained, timings| SUM
    SUM -->|recall@k, MRR, abstention P/R, citation accuracy, keyword coverage, p50/p95| OUT[results/TIMESTAMP.json<br/>+ review.md for humans]
    SUM --> T[Markdown table in terminal]
    R -->|best scores| SW[min_score_sweep<br/>re-score gate at other thresholds]
```

## 4. The real concepts

| Term | Plain meaning |
|---|---|
| **Ground truth** | The answers we decided are correct before running anything. Here: the expected pages for each question. |
| **Recall@k** | Out of the answerable questions, how many had a correct page somewhere in the top k chunks. |
| **MRR (Mean Reciprocal Rank)** | For each question, 1 ÷ (position of the first correct chunk); 0 if it never appears. Then average. 1.0 = always first. |
| **Precision / recall (abstention)** | Precision: when it said "I don't know", was that right? Recall: of the questions it should refuse, how many did it refuse? |
| **Gate abstention** | The refusal made by the score threshold (`MIN_SCORE`) before the LLM is called. |
| **Strict abstention** | Counting a refusal only when the answer is exactly the refusal sentence — added after we caught the app's loose check. |
| **Citation accuracy** | Valid citations ÷ all citations. Valid = the cited page was actually retrieved. |
| **Faithfulness** | Does the answer say what the source says? Needs a human. A valid citation does not prove it. |
| **p50 / p95 latency** | The median time, and the time 95% of questions finished under. p95 shows the slow tail. |
| **Controlled experiment** | Change one setting, keep everything else (dataset, model, machine) the same, compare with the baseline. |
| **Baseline** | The saved result for the current settings that every experiment is compared against. |
| **Non-determinism** | The LLM can answer differently on identical runs (temperature 0.1 is low, not zero). |

## 5. Code walkthrough

### [evaluation/dataset.jsonl](../../evaluation/dataset.jsonl) — the question paper

```json
{"id": "q01", "question": "How do I declare a path parameter with a type?",
 "expected_sources": [{"source": "fastapi-path-params.pdf", "page": 1}],
 "expected_answer_keywords": ["int", "type annotation"], "should_abstain": false}
```
- One JSON object per line (JSON Lines). Easy to add, edit, and diff in Git.
- Answerable questions must list pages; should-abstain questions list none.
- We grade at **page** level, not chunk level. Pages don't change when chunk size changes, so the same answer key works for every chunking experiment.

### [evaluation/metrics.py](../../evaluation/metrics.py) — the marking scheme (pure functions)

```python
def first_hit_rank(expected: set[Page], retrieved: list[Page]) -> int | None:
    for rank, page in enumerate(retrieved, start=1):
        if page in expected:
            return rank
    return None
```
- The building block of Recall@k and MRR. `Page` is `(source, page)`, e.g. `("fastapi-path-params.pdf", 2)`.

```python
def recall_at_k(cases, k):
    ...
        rank = first_hit_rank(expected, retrieved[:k])
```
- Only the first k retrieved pages count. A correct page at position 5 doesn't help recall@4.

```python
precision = true_pos / (true_pos + false_pos) if true_pos + false_pos else None
```
- `None` instead of crashing or pretending 0 when the metric is undefined (e.g. it never refused).

```python
return float(np.percentile(values, p))
```
- Linear interpolation, the numpy default. Written down so the method is clear.

### [evaluation/run_eval.py](../../evaluation/run_eval.py) — the exam room

```python
def build_store(settings: Settings) -> VectorStore:
    docs = load_directory(settings.docs_dir)
    chunks = chunk_documents(docs, settings.chunk_size, settings.chunk_overlap)
    return VectorStore.build(chunks)
```
- Always a fresh in-memory index with the settings being tested. So the recorded config is exactly what was measured, and `storage/index` is never overwritten by an experiment.

```python
"gate_abstained": best_score < settings.min_score,
```
- We can measure the threshold's refusals without the LLM — that is why the MIN_SCORE sweep runs in seconds.

```python
def is_clean_abstain(answer: str) -> bool:
    return answer.strip().rstrip(".").lower() == ABSTAIN_ANSWER.rstrip(".").lower()
```
- Added during this phase. The app marks an answer as abstained if the refusal sentence appears **anywhere**. In one run, q29 (Docker) produced an invented answer and then the refusal sentence — and was counted as a correct refusal.

```python
config = {"git_commit": git_commit(), "chunk_size": ..., "min_score": ..., "prompt_version": PROMPT_VERSION, ...}
```
- Every result says exactly what produced it. `-dirty` in the commit means there were uncommitted changes.

```python
def min_score_sweep(rows, thresholds):
    predicted = [r["best_score"] < threshold for r in rows]
```
- Best scores don't depend on the threshold, so we re-score one retrieval run at many thresholds.

### Config change: [app/config.py](../../app/config.py)
`CHUNK_SIZE=500` and `CHUNK_OVERLAP=100` moved into `Settings` (and `.env.example`). The API rebuild and
`scripts/build_index.py` now read them, so one setting controls chunking everywhere and the results can record it.

## 6. How to run and see it work

```bash
python -m evaluation.run_eval                    # retrieval only, no LLM
ollama serve                                     # other terminal
python -m evaluation.run_eval --with-llm         # full RAG, asks the LLM all 30 questions
```

Real baseline output (2026-10-25, chunk 500/100, top_k 4, MIN_SCORE 0.30, llama3.2:3b, prompt v1):

```
| recall@1 | 0.667 |
| recall@3 | 0.917 |
| recall@4 | 0.958 |
| recall@10 | 1.000 |
| mrr@10 | 0.803 |
| gate abstention precision | 0.500 |
| gate abstention recall | 0.333 |
```

Full RAG over 3 identical runs (all real):

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| keyword coverage | 0.694 | 0.736 | 0.694 |
| citation accuracy | 0.750 | 0.826 | 0.905 |
| answers with an invalid citation | 5 | 4 | 2 |
| final abstention precision / recall | 0.600 / 1.000 | 0.625 / 0.833 | 0.556 / 0.833 |
| total latency p50 / p95 ms | 4925 / 11759 | 3420 / 8686 | 2591 / 10927 |

Run 1's recall of 1.000 was inflated by the q29 bug above.

**Experiment 1 — chunk size (retrieval):**

| | recall@1 | recall@3 | recall@4 | MRR@10 |
|---|---|---|---|---|
| 300/100 | 0.708 | 0.833 | 0.875 | 0.794 |
| **500/100** | 0.667 | **0.917** | **0.958** | **0.803** |
| 800/150 | 0.708 | 0.833 | 0.917 | 0.779 |

Kept 500/100.

**Experiment 2 — MIN_SCORE:** no threshold separates answerable from should-abstain questions
(q18 answerable and q25 should-abstain both score 0.2778). Lowering to 0.20 was tested with the LLM
(2 runs): q21 became correct, but q18 became a wrong answer and q25 an invented one. Kept 0.30.

Full tables and file names: [evaluation/README.md](../../evaluation/README.md).

Tests: `python -m pytest -q` → **115 passed** (91 before + 24 new: 12 metrics, 12 run_eval).

## 7. Common errors

| What you see | Why | Fix |
|---|---|---|
| `Evaluation failed: Ollama is not reachable ... Start it with: ollama serve` | `--with-llm` without Ollama | `ollama serve` |
| `dataset.jsonl:7: missing keys [...]` | A line lacks a field | Fix that line; the message gives the line number |
| `answerable question needs expected_sources` | Forgot the answer key | Add pages, or set `should_abstain: true` |
| Different numbers on identical runs (**hit in this phase**: citation accuracy 0.750 → 0.826 → 0.905) | LLM randomness | Run several times; report the range |
| Abstention recall 1.000 that looked too good (**hit in this phase**) | App counts any answer *containing* the refusal sentence | Use the strict abstention row; fix `_is_abstain` (follow-up) |
| `[user.value]` reported as an invalid citation (**hit in this phase**) | Citation regex matches `[name.ext]`, so Python code looks like a file citation | Mentally subtract; tighten the regex (follow-up) |
| `for cfg in "300 100" ...; set -- $cfg` did nothing (**hit in this phase**) | zsh doesn't split words like bash | Run each command separately |

## 8. Security and limits

| Topic | Status |
|---|---|
| Results contain answers and page numbers | Fine for public FastAPI docs. **Don't commit `evaluation/results/` for personal documents.** |
| `git` called from Python | Fixed argument list, no shell; failures give `"unknown"` |
| `storage/index` | Never touched — experiments build in memory |
| Dataset size | 30 questions, 24 answerable: one question moves recall by 0.042 |
| Annotator | One author (Claude), one reviewer (Pranav) |
| Multi-page questions | A hit if **any** expected page is retrieved |
| Keyword coverage | Weak proxy; q04 scored 0 while giving a wrong URL, others score 1.0 while being wrong |
| Faithfulness | Not automated. Example: q08 says "the last one will override" in all 5 runs; page 6 says "the first one will always be used". Mark these in `*.review.md` |

## 9. Interview questions

1. **How did you evaluate your RAG system?**
   A 30-question set (24 answerable incl. paraphrases and multi-page, 6 should-abstain) with page-level ground truth. Retrieval: recall@4 0.958, MRR@10 0.803. Full RAG over 3 runs: citation accuracy 0.750–0.905. Every result file records the config and git commit.

2. **Why evaluate retrieval separately from generation?**
   It's deterministic, fast (no LLM calls) and isolates where errors come from. If the right page isn't retrieved, no prompt can fix it. Here retrieval is strong (recall@10 = 1.000); most errors are in generation.

3. **What did the chunk-size experiment show?**
   500/100 was best for recall@3, recall@4 and MRR. 300 split explanations from their code (q01 fell from rank 2 to 8); 800 diluted a short Pydantic sentence inside a long section (q06 dropped out of the top 10). One variable changed, same dataset.

4. **Why not just raise MIN_SCORE to refuse more?**
   Off-topic-but-same-domain questions (JWT, Docker, PostgreSQL) score 0.45–0.59, above many real questions. Raising the threshold mainly refuses real questions — at 0.45, 8 wrong refusals. A wrong refusal at the gate can't be recovered; the LLM catches some of the rest.

5. **Why is a valid citation not enough?**
   It only proves the page was retrieved. q08 cited a retrieved page and still said the opposite of the PDF. That needs human review (faithfulness), which we keep separate from automatic numbers.

6. **How did evaluation find bugs?**
   It showed abstention recall 1.000 in one run; inspecting q29 revealed an invented answer ending with the refusal sentence, counted as a refusal by a substring check. It also showed `[user.value]` from code being parsed as a citation.

7. **How do you handle LLM non-determinism?**
   Run identical configs several times and report the range (citation accuracy 0.750–0.905 over 3 runs); never claim an improvement smaller than that spread.

8. **What would you improve next?**
   A v2 prompt whose citation example isn't a real-looking page (the model copies `[guide.pdf, p. 2]` → q01 cites p. 2 every run); fix the abstain check and the citation regex; grow the dataset with a second annotator.

## 10. Try it yourself

1. Add two questions of your own to `dataset.jsonl` (one answerable, one should-abstain), run `python -m evaluation.run_eval`, and check their rows in the new results file.
2. Run `python -m evaluation.run_eval --with-llm` twice and compare citation accuracy. Is the difference bigger than you expected?
