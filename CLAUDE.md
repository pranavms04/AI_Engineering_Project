# CLAUDE.md — AI Knowledge Assistant

This file is read automatically at the start of every Claude Code session.
Read it fully before doing anything. Full design: `docs/PROJECT_SPEC.md`.
Current status: `docs/PROGRESS.md`. Phase prompts: `docs/PHASE_PROMPTS.md`.

## 1. What we are building

A **local, free, private RAG application**: users add technical documents
(PDF, Markdown, TXT), ask questions, and get answers grounded **only** in those
documents, with citations like `[fastapi-path-params.pdf, p. 2]`. If the
documents don't contain the answer, the app says so instead of guessing.

It is a **portfolio project for an entry-level AI Engineer job search** in India.
It must be honest, well-tested, measured, and explainable in an interview.

## 2. Who you are working with

- Owner: Pranav, a Flutter developer learning AI Engineering. Comfortable with
  Python, Pandas, scikit-learn and basic FastAPI; new to LLMs and RAG.
- Machine: macOS (Apple Mac), Python 3.11, virtual env at `.venv`.
  Anaconda `(base)` is also installed — always use `.venv/bin/python`.
- **This is a learning project.** Pranav must be able to explain every line in
  an interview. That shapes how you work (see §6).

## 3. Hard rules (never break these)

1. **Zero cost.** No paid APIs (no OpenAI/Anthropic/Gemini keys), no paid
   hosting, no services that need a credit card. Everything runs locally.
2. **Local LLM only, via Ollama** (HTTP API at `http://localhost:11434`).
3. **Never invent results.** No made-up metrics, benchmarks, latency numbers or
   evaluation scores — in code, docs, README or chat. Only report numbers you
   actually measured by running code in this repo.
4. **No secrets or personal data in Git.** `data/sample_docs/*`, `storage/`,
   `.env` stay git-ignored. Never commit PDFs from the user's documents.
5. **No pickle** for persisted data. Use JSON (+ FAISS's own index format).
6. **Don't rewrite working code.** Stages 1–5 work and are tested. Extend them;
   refactor only when a phase prompt asks, and keep all existing tests passing.
7. **Keep it simple.** No LangChain/LlamaIndex/agents in the core pipeline unless
   a phase prompt explicitly asks (a framework comparison comes late, as a demo).
8. **Small steps.** One phase at a time. Don't start the next phase unasked.

## 4. Current architecture (Stages 1–9 are built)

```
INGESTION (scripts/build_index.py)          QUERY
data/sample_docs/*.pdf|md|txt               question
  → app/ingestion/loader.py   (pypdf,        → app/retrieval/embedder.py (embed_query)
       one Document per PDF page)            → app/retrieval/vector_store.py (FAISS search)
  → app/ingestion/cleaning.py (regex)        → top-k Chunks with source/page metadata
  → app/ingestion/chunking.py (500/100)      → app/services/rag_service.py: score gate (MIN_SCORE)
                                                → app/generation/prompts.py → llm_client.py (Ollama)
                                                → app/generation/citations.py (validate) → RAGAnswer
  → app/retrieval/embedder.py (MiniLM)
  → app/retrieval/vector_store.py
       storage/index/index.faiss + chunks.json
```

Existing public APIs (do not break):
- `loader.Document(text, metadata)`, `load_file(path) -> list[Document]`,
  `load_directory(folder) -> list[Document]` (skips empty, bad UTF-8, corrupt
  PDFs, duplicate content; logs warnings).
- `cleaning.clean_text(text) -> str`
- `chunking.Chunk(text, metadata)`, `split_text(text, chunk_size=500, overlap=100)`,
  `chunk_documents(docs, ...)` — metadata gains `chunk_index`, `char_count`.
- `embedder.MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"` (384-d,
  normalized float32), `get_model()`, `embed_texts()`, `embed_query()`.
- `config.Settings.from_env()`; `llm_client.LLMClient` / `OllamaClient` / `FakeLLMClient`,
  `LLMUnavailableError`, `LLMResponseError`; `citations.citation_tag/extract_citations/validate_citations`;
  `RAGService(store, llm, settings).answer(question, top_k=None) -> RAGAnswer`;
  `LLMClient.is_reachable()`; `indexing.rebuild_index(docs_dir, index_dir) -> (VectorStore, IndexStats)`.
- API (`app/api/`): `main.app` with GET /health, POST /ask, GET+POST /documents, POST /index/rebuild;
  shared `AppState` via `Depends(get_state)` (tests override it); CORS only localhost:8501.
- Evaluation (`evaluation/`): `dataset.jsonl` (30 questions, page-level ground truth, user-approved),
  `metrics.py` (recall_at_k, mrr, keyword_coverage, citation_accuracy, abstention_scores, percentile),
  `run_eval.py` (builds the index in memory, writes `results/*.json` with config + git commit). See `evaluation/README.md`.
- `Settings` also has `chunk_size`/`chunk_overlap` (CHUNK_SIZE/CHUNK_OVERLAP, 500/100), used by API rebuild and build_index.
- UI (`ui/streamlit_app.py`): calls the API over HTTP only (`API_URL`); helpers `call_api` → `ApiResult`,
  `remove_images()` before rendering LLM Markdown; `.streamlit/config.toml` binds to localhost.
- `vector_store.VectorStore.build(chunks)`, `.search(query, k) -> [(Chunk, score)]`,
  `.save(folder)`, `.load(folder)` (rejects index built with another model).

Metadata keys on a chunk: `source`, `type`, `page` (PDFs only), `chunk_index`, `char_count`.

## 5. Tech stack (all free, local)

| Concern | Tool |
|---|---|
| Language | Python 3.11 |
| PDF parsing | pypdf |
| Embeddings | sentence-transformers, all-MiniLM-L6-v2 (Apache-2.0) |
| Vector search | faiss-cpu, `IndexFlatIP` on normalized vectors |
| LLM | Ollama + a small open model chosen for this Mac's RAM |
| HTTP client | httpx |
| API | FastAPI + Pydantic + uvicorn |
| UI | Streamlit (calls the API, never imports app internals) |
| Config | pydantic-settings or plain env vars, documented in `.env.example` |
| Tests | pytest (+ FastAPI TestClient) |
| Packaging/CI | Docker + docker compose, GitHub Actions (public repo, standard runner) |

Before adding ANY new dependency: say why, confirm its licence and that it is
free, then add it to `requirements.txt`.

## 6. How to work in this repo

For every phase, use the `implement-phase` skill. In short:
1. Read this file, `docs/PROGRESS.md`, and the relevant code before editing.
2. Present a short plan (files to create/change, tests to add). Wait for "go"
   unless the user already said to proceed.
3. Implement the **simplest working version** first, with tests.
4. Run `.venv/bin/python -m pytest -q` — everything must pass.
5. Run the phase's manual check (e.g. a script) and show the real output.
6. Write the learner notes via the `explain-like-five` skill
   (`docs/learning/NN-<phase>.md`: ELI5, Mermaid diagram, code walkthrough,
   common errors, interview Q&A).
7. Update `docs/PROGRESS.md`. Suggest a commit message; don't push.

Code style: type hints, small pure functions, `logging` not `print` in `app/`,
clear error messages, no clever one-liners a beginner can't read.

Testing style: tests must not require Ollama to be running — mock the LLM
client. Embedding tests may use the real MiniLM model (it's cached locally).
Test **behaviour/relationships** for AI outputs, not exact strings.

## 7. Commands

```bash
source .venv/bin/activate                       # always
python -m pytest -q                             # all tests
python -m scripts.build_index                   # rebuild FAISS index
python -m scripts.search "question" -k 3        # retrieval only
python -m scripts.ask "question"                # full RAG answer (needs Ollama running)
ollama serve                                    # terminal 1: local LLM
uvicorn app.api.main:app --reload               # terminal 2: API on 127.0.0.1:8000, docs at /docs
streamlit run ui/streamlit_app.py               # terminal 3: UI on http://localhost:8501
python -m evaluation.run_eval                   # retrieval metrics (no LLM)
python -m evaluation.run_eval --with-llm        # full RAG metrics + latency (needs Ollama)
python -m evaluation.run_eval --chunk-size 300 --overlap 100   # one-variable experiment
python -m evaluation.run_eval --sweep-min-score 0.2,0.3,0.4    # abstain-gate sweep
python -m evaluation.rescore evaluation/results/<run>-llm-*.json   # re-score saved answers, no LLM
colima start --cpu 2 --memory 3 --disk 20       # Docker VM on this Mac (Colima, not Docker Desktop)
docker-compose up --build                       # API + UI containers; Ollama stays on the host
```

Packaging: `Dockerfile` has two targets (`api`: CPU-only torch 2.14.1 + MiniLM baked in,
offline; `ui`: Streamlit only). `requirements.txt` = `requirements-api.txt` +
`requirements-ui.txt` + pytest. CI: `.github/workflows/ci.yml` runs pytest on every push.
Runbook: `docs/RUNBOOK.md`.

## 8. Known gotchas

- `ModuleNotFoundError: app...` → run from repo root with `python -m ...`.
- Rebuild the index after any change to documents, chunking or embedding model.
- `export TOKENIZERS_PARALLELISM=false` silences a harmless warning.
- `export HF_HUB_OFFLINE=1` once the MiniLM model is cached.
- The PyTorch "Redirects are currently not supported in MacOs" line is harmless.
