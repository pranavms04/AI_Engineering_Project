# Evaluation

How good is the assistant? This folder answers that with numbers you can re-run.

```bash
python -m evaluation.run_eval                                   # retrieval only (no LLM)
python -m evaluation.run_eval --with-llm                        # full RAG (needs `ollama serve`)
python -m evaluation.run_eval --chunk-size 300 --overlap 100    # one-variable experiment
python -m evaluation.run_eval --sweep-min-score 0.15,0.2,0.3    # re-score the abstain gate
python -m evaluation.run_eval --min-score 0.2 --with-llm        # full run with another threshold
```

Every run rebuilds the index **in memory** from `DOCS_DIR` with the settings under test
(`storage/index` is never touched) and writes `results/<timestamp>-<mode>-c<size>o<overlap>.json`
with the config, git commit, per-question results and totals. `--with-llm` runs also write a
`*.review.md` table for human faithfulness marking.

## Files

| File | What it is |
|---|---|
| `dataset.jsonl` | 30 questions about `fastapi-path-params.pdf` (13 pages). 24 answerable (17 direct, 4 paraphrases with few shared words, 3 needing several pages), 6 that should abstain (2 close to the topic, 3 about FastAPI but not covered, 1 off-topic). Written by Claude from the page text, reviewed and approved by Pranav. |
| `metrics.py` | Pure metric functions, unit tested in `tests/test_metrics.py`. |
| `run_eval.py` | Runs the dataset, saves results, prints a Markdown table. Tested in `tests/test_run_eval.py`. |
| `results/` | One JSON per run (+ `.review.md` for LLM runs). |

## Metrics

| Metric | Meaning | Objective? |
|---|---|---|
| **Recall@k** | Share of answerable questions where **any** expected page is in the top-k retrieved chunks. | Yes |
| **MRR@10** | Average of 1/rank of the first correct page in the top 10 (0 if missing). Rewards ranking the right page first. | Yes |
| **Gate abstention precision / recall** | The score gate refuses when the best chunk scores below `MIN_SCORE`. Precision: of gate refusals, how many should have refused. Recall: of should-abstain questions, how many the gate refused. | Yes |
| **Final abstention precision / recall** | Same, after the LLM: uses the app's `abstained` flag (gate **or** the answer contains the refusal sentence). | Yes, but see the flaw below |
| **Strict abstention** | Abstained only if the answer is **exactly** the refusal sentence. Added because the app's check counts an invented answer that ends with "I couldn't find this in the documents." as a refusal. | Yes |
| **Citation accuracy** | Valid citations / all citations. Valid = the cited `[file, p. N]` was among the retrieved chunks. | Yes |
| **Keyword coverage** | Share of expected keywords found in the answer (case-insensitive). | Rough proxy only — a wrong answer can contain the keyword; a right one can use other words. |
| **Latency p50 / p95** | Median and 95th percentile of retrieve / generate / total ms (linear interpolation). | Yes, but machine-dependent |
| **Faithfulness / correctness** | Does the answer say what the cited page says? | **No — human judgment.** Mark it in `*.review.md`. Not in any automatic number. |

A **valid citation does not mean a correct answer.** Example: in all 5 LLM runs, q08 ("What
happens if I define the same path operation twice?") answers "the last one will override the
previous one" — page 6 says "The first one will always be used". Only a human review catches this.

## Baseline (2026-10-25, commit `5abc21e` + uncommitted Phase 9 files)

Config: chunk 500/100, top_k 4, MIN_SCORE 0.30, all-MiniLM-L6-v2, llama3.2:3b, prompt v1, temperature 0.1.
M1, 8 GB RAM.

**Retrieval** (`results/20261025-220246-retrieval-c500o100.json`, deterministic):

| recall@1 | recall@3 | recall@4 | recall@10 | MRR@10 | gate abst. precision | gate abst. recall |
|---|---|---|---|---|---|---|
| 0.667 | 0.917 | 0.958 | 1.000 | 0.803 | 0.500 | 0.333 |

**Full RAG, 3 identical runs** (the LLM is not deterministic, so all three are shown):

| Run (results file) | keyword cov. | citation acc. | answers w/ invalid citation | final abst. P / R | strict abst. P / R | total p50 / p95 ms |
|---|---|---|---|---|---|---|
| `20261025-220558` | 0.694 | 0.750 | 5 | 0.600 / 1.000 | (not measured yet) | 4925 / 11759 |
| `20261025-220910` | 0.736 | 0.826 | 4 | 0.625 / 0.833 | 0.625 / 0.833 | 3420 / 8686 |
| `20261025-221228` | 0.694 | 0.905 | 2 | 0.556 / 0.833 | 0.556 / 0.833 | 2591 / 10927 |

Run 1's abstention recall of 1.000 is inflated: q29 (Docker) got an invented answer that ended with
the refusal sentence and was counted as a refusal. The strict check was added after spotting this.

Consistent in all 3 runs: q01 cites p. 2 (not retrieved; text is from p. 1), q06 cites p. 4 (not
retrieved), q02 is refused by the LLM although p. 2 answers it, q18 and q21 are refused by the gate,
q29 gets an invented Docker answer, q25–q28 and q30 are refused. One "invalid citation" in runs 1–2
(`[user.value]` in q09) is code, not a citation — the citation regex matches `[name.ext]`.

## Experiment 1 — chunk size (retrieval only, same dataset)

| Chunks | recall@1 | recall@3 | recall@4 | recall@10 | MRR@10 | results file |
|---|---|---|---|---|---|---|
| 300/100 (61 chunks) | 0.708 | 0.833 | 0.875 | 1.000 | 0.794 | `20261025-221308-retrieval-c300o100.json` |
| **500/100 (35 chunks, baseline)** | 0.667 | **0.917** | **0.958** | 1.000 | **0.803** | `20261025-220246-retrieval-c500o100.json` |
| 800/150 (22 chunks) | 0.708 | 0.833 | 0.917 | 0.958 | 0.779 | `20261025-221318-retrieval-c800o150.json` |

Examples (rank of the first correct page):
- **q01** "How do I declare a path parameter with a type?": 300 → 8, 500 → 2, 800 → 4. Small chunks split
  the sentence about type annotations from the code that shows `item_id: int`.
- **q06** "Which library performs the data validation?": 300 → 5, 500 → 4, 800 → not in top 10. At 800 the
  short Pydantic sentence shares one vector with the long "Order matters" section, so the vector no
  longer points at "validation library" (our reading of the cause, not measured directly).
- **q22** "What two documentation interfaces…": 300 → 1, 500 → 2, 800 → 1. One case where both other sizes rank better.

**Decision: keep 500/100.** It is best at recall@3, recall@4 (what the LLM actually sees, top_k = 4) and MRR.
300 and 800 only win recall@1 by one question.

## Experiment 2 — MIN_SCORE (abstain gate)

Gate only, re-scored from the baseline retrieval (`results/20261025-221343-retrieval-c500o100.json`):

| MIN_SCORE | correct refusals | wrong refusals | missed refusals |
|---|---|---|---|
| 0.15 | 1 | 0 | 5 |
| 0.20 | 1 | 0 | 5 |
| 0.25 | 1 | 1 | 5 |
| **0.30 (current)** | 2 | 2 | 4 |
| 0.35 | 2 | 3 | 4 |
| 0.40 | 2 | 4 | 4 |
| 0.45 | 2 | 8 | 4 |

No threshold separates the classes. Answerable q18 and should-abstain q25 have the **same** best score
(0.2778), and the FastAPI-but-not-covered questions q26–q29 score 0.45–0.59 — higher than most answerable
questions. A similarity threshold can only catch clearly off-topic questions (q30, 0.120).

The trade-off: a **wrong refusal at the gate cannot be undone** (the LLM never sees the question); a
**missed refusal** can still be caught by the LLM (it refused q26–q28 in every run). So a lower threshold
looked attractive. Measured with the LLM at MIN_SCORE 0.20 (2 runs: `20261025-221851`, `20261025-222247`):

- gained: q21 answered correctly ("Pydantic [p. 5]");
- lost: q18 now answered **wrongly** (invents a `Path`/`Regex` approach; the PDF uses an Enum);
- lost: q25 (should abstain) now gets an **invented** query-parameter answer.

**Decision: keep MIN_SCORE = 0.30.** 0.20 trades one correct answer for two wrong ones on this dataset.

## Limitations

- **Small:** 30 questions, one 13-page PDF. One question = 0.042 of recall@k (24 answerable). Results are
  indicative, not statistically strong.
- **Single annotator:** questions, expected pages and keywords were drafted by Claude and approved by one person.
- **Multi-page questions** count as a hit if **any** expected page is retrieved, not all.
- **Keyword coverage** is a weak proxy (see table).
- **LLM randomness:** temperature 0.1 still changed results between identical runs (citation accuracy
  0.750–0.905 over 3 runs). Compare runs, not single numbers.
- **Latency** depends on what else the Mac is doing; p95 over 30 questions is driven by 1–2 slow answers.
- **Abstention flag in the app** is loose (substring match). Strict abstention is reported alongside it.

## Privacy

Results files contain questions, answers and retrieved page numbers/scores; review files contain
answers. That is fine for the public FastAPI docs used here. **If you evaluate on personal documents,
do not commit `evaluation/results/`.**
