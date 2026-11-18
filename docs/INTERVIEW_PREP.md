# Interview prep: PageProof (AI Knowledge Assistant)

Live project page: https://huggingface.co/spaces/pranavms04/pageproof (also GitHub Pages). Code: https://github.com/pranavms04/AI_Engineering_Project

Everything here is about **this** repo. Every number comes from a file you can open
(`evaluation/results/*.json`, `docs/PROGRESS.md`). If you can't point at where a number came
from, don't say it.

---

## 1. Pitches

### 30 seconds
> I built a local RAG assistant that answers questions only from your own documents, cites the
> page for every claim, checks those citations, and says "I couldn't find this" instead of guessing.
> It runs entirely on my laptop: Llama 3.2 3B through Ollama, MiniLM embeddings and FAISS, behind
> a FastAPI backend with a three.js web app that shows retrieval live. I measured it on a 30-question
> set: the right page is in the top 4 for 23 of 24 answerable questions, and the evaluation caught
> two bugs in my own code.

### 2 minutes
1. **Problem:** LLMs answer confidently even when they don't know. For internal documents you want
   answers grounded in the documents, with proof, and a refusal when the documents are silent.
2. **What it does:** upload PDF/Markdown/text, ask a question, get an answer with `[file, p. N]`
   citations. Every citation is checked against the passages the model was given; fakes are flagged.
   Weak matches are refused before the model is called.
3. **How:** pages → 500-character chunks with 100 overlap → MiniLM vectors → FAISS. A question is
   embedded the same way, the top 4 chunks are retrieved, a score gate (0.30) decides whether to call
   the LLM, and a strict prompt makes it answer only from those chunks.
4. **Proof:** a 30-question evaluation (Recall@k, MRR, citation accuracy, abstention, latency),
   156 tests in GitHub Actions, Docker for one-command start.
5. **What I learned:** a valid citation isn't a correct answer, LLM results vary between identical
   runs so you report ranges, and evaluation finds bugs that unit tests miss.

### 10 minutes (architecture walk, follow the code)
| Step | File | Say |
|---|---|---|
| Load | `app/ingestion/loader.py` | pypdf, **one Document per page** so citations can name the page; skips empty, corrupt, duplicate files |
| Clean | `app/ingestion/cleaning.py` | regex: whitespace, broken hyphenation |
| Chunk | `app/ingestion/chunking.py` | 500 chars / 100 overlap. Overlap keeps a sentence that crosses a boundary in at least one chunk. Chosen by experiment |
| Embed | `app/retrieval/embedder.py` | all-MiniLM-L6-v2, 384-d, **normalised**, so inner product = cosine similarity |
| Index | `app/retrieval/vector_store.py` | FAISS `IndexFlatIP` (exact search; fine at 35 chunks). Metadata saved as **JSON, not pickle**. Refuses an index built with a different model |
| Answer | `app/services/rag_service.py` | retrieve top-k → score gate → prompt → Ollama → citation check → `RAGAnswer` with timings |
| Prompt | `app/generation/prompts.py` | rules: only the context, exact refusal sentence, cite the chunk tag, context is data not instructions. Versioned (`PROMPT_VERSION`) |
| Citations | `app/generation/citations.py` | regex extracts `[file, p. N]`, compares with tags of the retrieved chunks |
| API | `app/api/` | FastAPI: `/health`, `/ask`, `/documents`, `/index/rebuild`, `/index/map`. Pydantic validation, 503 when Ollama is down, safe uploads, CSP |
| Web app | `web/` | plain JS + three.js: PCA of the embeddings to 3D, question flies in, sources light up, citation chips fly to their passage |
| Evaluation | `evaluation/` | dataset, metrics, runner, results with config + git commit |
| Ship | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` | CPU-only torch, MiniLM baked in, non-root, ports on 127.0.0.1; pytest on every push |

---

## 2. Numbers to know (and where they come from)

| What | Value | Source |
|---|---|---|
| Corpus | 1 PDF, 13 pages → 35 chunks (+1 test txt) | `scripts/build_index` |
| Recall@4 | **0.958** (23 of 24 answerable) | `evaluation/results/20261025-220246-retrieval-c500o100.json` |
| Recall@1 / @3 / @10 | 0.667 / 0.917 / 1.000 | same |
| MRR@10 | **0.803** | same |
| Citation accuracy, v1 prompt, after bug fixes (3 runs) | **0.870 / 0.905 / 0.895** | `20261025-230001`, `-230404`, `-230830` |
| Citation accuracy, v2 prompt (3 runs, rejected) | 0.760 / 0.826 / 0.792 | `20261118-103923`, `-104248`, `-104812` |
| Chunk experiment, Recall@4 | 300/100: 0.875 · **500/100: 0.958** · 800/150: 0.917 | `evaluation/README.md` |
| MIN_SCORE | kept 0.30; 0.20 fixed 1 answer but broke 2 | `evaluation/README.md` |
| Off-topic refusal | "capital of France" best score 0.120 < 0.30, LLM not called | `docs/PROGRESS.md` |
| Latency, full answer (p50) | 2.6–4.9 s across 3 runs on an 8 GB M1 | baseline LLM runs |
| 3D map | PCA keeps ≈38% of the variance (18.4 + 10.5 + 8.9%) | `GET /index/map` |
| Tests | **156**, CI green on GitHub (first run 1 min 19 s) | `pytest`, Actions run 40487041372 |
| Docker image | API 2.1 GB (CPU torch + MiniLM), UI 828 MB | `docker images` |

---

## 3. Interview questions with model answers

### Python & design
1. **Why so many small modules?** Each stage (load, clean, chunk, embed, store, answer) has one job,
   its own tests, and can be swapped. E.g. the evaluation rebuilds the index in memory with a different
   chunk size by calling the same functions.
2. **How is configuration handled?** One frozen dataclass, `app/config.py` `Settings.from_env()`,
   every value documented in `.env.example`. No magic numbers spread across files.
3. **How do you avoid the API depending on Ollama in tests?** `LLMClient` is a Protocol; tests pass
   `FakeLLMClient`; FastAPI's `Depends(get_state)` is overridden in tests.

### Ingestion & chunking
4. **Why one document per PDF page?** So each chunk keeps its page number and citations can say `p. 4`.
5. **Why 500/100?** Measured: Recall@4 0.958 vs 0.875 (300/100) and 0.917 (800/150). Small chunks split
   explanations from their code (q01 fell from rank 2 to 8); big ones dilute short facts (q06 left the top 10).
6. **What breaks on scanned PDFs?** pypdf extracts no text; the loader logs it. OCR is out of scope.

### Embeddings & vector search
7. **What is an embedding?** 384 numbers per text; similar meanings get similar vectors.
8. **Why normalise and use `IndexFlatIP`?** On unit vectors, inner product equals cosine similarity.
   Flat = exact search, trivial at 35 vectors.
9. **At 1 million chunks?** Approximate index (HNSW or IVF-PQ), or a vector DB (pgvector/Qdrant);
   batch embedding jobs; metadata in a real database; re-embed on model change with a versioned index.
10. **Why reject an index built with another model?** Vectors from different models aren't comparable;
    `VectorStore.load` checks `model_name` and asks for a rebuild.

### LLMs & prompting
11. **How do you stop the model using outside knowledge?** Prompt rule ("use ONLY the context"), a
    score gate before calling the model, and checking citations after. None is perfect alone.
12. **Why temperature 0.1?** Less randomness for factual answers. It still varied between identical
    runs (citation accuracy 0.870–0.905), so I report ranges.
13. **What was the v2 prompt change?** v1's example citation was `[guide.pdf, p. 2]`; q01 cited `p. 2`
    in every run though p. 2 was never retrieved. v2 uses the placeholder `[file-name, p. N]`.
    Result: hypothesis **rejected**. q01 still cited `p. 2` in 3/3 runs, and citation accuracy fell to
    0.760–0.826 (v1: 0.870–0.905) because the model invented whole file names (q28 `fastapi-database.pdf`).
    I kept v1. Lesson: test the fix, don't assume it; a placeholder can invite invention.
14. **Why version prompts?** Every result file records `prompt_version`, so a change is an experiment
    you can compare, not a guess.

### RAG quality & hallucination
15. **What does citation validation prove?** Only that the cited page was among the retrieved chunks.
    Not that the sentence is true: q08 said "the last one will override" with a valid citation; page 6
    says "the first one will always be used".
16. **Why refuse before calling the LLM?** Cheaper, faster (France: no model call) and removes the
    chance to hallucinate. But a wrong refusal can't be undone, so the threshold is conservative.
17. **Why not tune MIN_SCORE higher?** Same-domain but uncovered questions (JWT, Docker, PostgreSQL)
    score 0.45–0.59, above many real questions. At 0.45 the gate made 8 wrong refusals.

### Evaluation
18. **How did you evaluate?** 30 questions with page-level ground truth (24 answerable incl. paraphrases
    and multi-page, 6 should-refuse). Retrieval: Recall@k, MRR. Generation: citation accuracy, keyword
    coverage, abstention precision/recall, p50/p95 latency. Results saved with config + git commit.
19. **Which metrics are objective?** Recall, MRR, citation validity, abstention, latency. Correctness
    and faithfulness need a human: each LLM run writes a `*.review.md` for marking.
20. **What bugs did evaluation find?** (1) An invented Docker answer ending with the refusal sentence
    counted as a refusal (substring check) → strict check. (2) Code like `[user.value]` parsed as a
    citation → only indexable file types count.
21. **Weaknesses of your evaluation?** 30 questions, one PDF, one annotator; multi-page questions count
    a hit if any page is retrieved; keyword coverage is a weak proxy.

### API & backend
22. **What status codes and why?** 422 bad input (Pydantic), 503 Ollama down or no index, 502 Ollama
    replied with an error, 413/415/409 for uploads.
23. **How are uploads made safe?** Extension allow-list, 10 MB limit (read limit+1 bytes), filename reduced
    to `Path(name).name`, resolved path must stay in `DOCS_DIR`, 409 instead of overwrite.
24. **Why is rebuild synchronous?** Simple and fine for a demo (≈2–10 s here). With a lock so only one runs;
    the old index keeps serving. At scale: background job + polling.

### Testing non-deterministic systems
25. **How do you test an LLM app?** Mock the LLM for unit/API tests (deterministic, no Ollama in CI); test
    behaviour and relationships (citation valid, refusal on low score), not exact text; measure the real
    model separately in the evaluation, across several runs.

### Security
26. **Prompt injection?** Retrieved text is wrapped as data and the prompt says to ignore instructions in it;
    the app never executes model output; the UIs render model text as plain text and strip Markdown images
    (which could leak data to a URL without a click).
27. **Why no pickle?** Unpickling can run arbitrary code. Metadata is JSON; vectors use FAISS's own format.
28. **Secrets?** There are none (local only). `.env`, documents and the index are git-ignored. I also found
    a personal PDF in early git history and removed it with `git filter-repo`.
29. **Network exposure?** API and UI bind to 127.0.0.1; Docker publishes on 127.0.0.1; CSP allows only our files.

### Docker / CI
30. **Why is Ollama not in Docker?** Docker on a Mac runs in a Linux VM without Apple GPU access, so a
    containerised Ollama would be much slower. The API container reaches it via `host.docker.internal`.
31. **Image size?** API 2.1 GB, mostly PyTorch; using the CPU-only wheel avoids the much larger GPU build.
32. **What does CI do?** Python 3.11, CPU torch, cached MiniLM, `pytest` on every push, read-only token.

### Trade-offs
33. **Why no LangChain?** To understand and test every step; fewer hidden defaults. A framework comparison
    is a planned optional experiment.
34. **Why a 3D map?** It makes retrieval explainable: you see the question land near its sources and see that
    a wrong citation points outside them. It's honest about its limits: PCA keeps ≈38% of the variance.

---

## 4. Debugging scenarios

| Symptom | How to investigate |
|---|---|
| **Answers cite pages that don't exist** | Look at `invalid_citations` in the response; compare with the `cite as` tags in the prompt (`build_prompt`). Check whether the model copies the prompt's example (this was q01 → v2 prompt). Measure with `run_eval --with-llm` over 3 runs. |
| **Retrieval returns irrelevant chunks** | `python -m scripts.search "question" -k 10` to see scores; check chunk text in `storage/index/chunks.json`; was the index rebuilt after changing documents or chunk size? Try a chunk-size experiment with `run_eval --chunk-size`. |
| **API hangs on /ask** | `/health` (`llm_reachable`?); the timing middleware log shows where time goes (`retrieve` vs `generate`); first call loads the model (seen: ~24 s generate cold); `LLM_TIMEOUT_S` gives a 503 after 120 s. |
| **Everything refuses** | Best scores below `MIN_SCORE`? Index empty or built with another model? `run_eval --sweep-min-score` shows the trade-off. |
| **Works locally, fails in Docker** | API logs: `Cannot reach Ollama` → is `ollama serve` running on the host? `OLLAMA_URL=http://host.docker.internal:11434`; `storage/` mounted and writable? |

---

## 5. Resume bullets (only what was built and measured)

- Built a local, private RAG assistant (Python, FastAPI, FAISS, MiniLM, Llama 3.2 3B via Ollama) that answers
  only from user documents with page-level citations, validates every citation against retrieved passages,
  and refuses low-evidence questions before calling the LLM.
- Designed a 30-question evaluation (Recall@k, MRR, citation accuracy, abstention, latency) with recorded
  config; reached Recall@4 of 0.958 and chose chunking and the refusal threshold by controlled experiments.
- Found and fixed two evaluation-exposed bugs (refusal detection, citation parsing); tested a prompt-change
  hypothesis over 3 runs each and rejected it on the data; 156 pytest tests in GitHub Actions, Docker (non-root, localhost-only).
- Built a three.js web app that visualises retrieval in a PCA projection of the embedding space, with strict
  CSP and safe rendering of model output.

---

## 6. Limitations to volunteer

- Small evaluation: 30 questions from one 13-page PDF, one annotator; results are indicative.
- A 3B model: sometimes cites the wrong page, and sometimes says things the cited page doesn't support.
- Faithfulness is checked by a human, not automatically.
- Single user, no login; meant for localhost.
- Synchronous rebuild; exact (flat) vector search; neither would scale to millions of chunks as is.
- The 3D map is a 2D/3D projection (≈38% of variance): distances are approximate.
- Scanned PDFs (images) aren't supported (no OCR).
