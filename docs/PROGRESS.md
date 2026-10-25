# Progress Tracker

Update this file at the end of every phase (the `implement-phase` skill does it).
Record only facts: what exists, what passed, real measured numbers.

| Phase | Name | Status | Tests | Notes |
|---|---|---|---|---|
| 1 | Project skeleton + text loader | ✅ done | yes | duplicate-content skipping added by Pranav |
| 2 | PDF loading + cleaning | ✅ done | yes | scanned PDFs yield no text (OCR out of scope) |
| 3 | Chunking with overlap | ✅ done | 5 | `tests/test_chunking.py` existed on disk but was never committed |
| 4 | Embeddings (MiniLM) | ✅ done | 4 | `tests/test_embedder.py` existed on disk but was never committed |
| 5 | FAISS vector store + search CLI | ✅ done (rebuilt in Phase 0) | 7 | code was missing from the repo; recreated `vector_store.py`, `build_index`, `search` |
| 0 | Audit + stabilise | ✅ done | 21 total | .gitignore, pinned requirements, .env.example, README stub |
| 6 | Local LLM answers + citations | ✅ done | 44 total (+23) | real run: grounded answer, but 1 invalid citation (p. 2 instead of p. 1) caught by validator |
| 7 | FastAPI backend | ✅ done | 75 total (+31) | /health, /ask, /documents (GET/POST), /index/rebuild; upload allow-list, 10 MB limit, path-traversal safe |
| 8 | Streamlit UI | ✅ done | 91 total (+16) | one-file UI over HTTP; all error states checked in the browser; bound to localhost; Markdown images stripped |
| 9 | Evaluation | ⬜ | | |
| 10 | Docker, CI, README | ⬜ | | |
| 11 | Interview prep pack | ⬜ | | |

## Environment facts
- macOS, Python 3.11.7, `.venv`
- Chip / RAM: Apple M1 (arm64), 8 GB RAM (`sysctl hw.memsize` = 8589934592)
- Ollama 0.40.4 (Homebrew, run with `ollama serve`), model `llama3.2:3b`, digest a80c4f17acd5, 1.9 GB on disk

## Measured numbers (only real ones)
Phase 0 run (2026-10-23), docs = `fastapi-path-params.pdf` + `active.txt`:
- `build_index`: 14 documents (pages/files) → 35 chunks (500/100), 2.6 s total.
- `search "How do I declare a path parameter with a type?"`: top-3 =
  0.555 [fastapi-path-params.pdf, p. 6], 0.470 [p. 1], 0.468 [p. 12].
  505 ms, which includes loading MiniLM on the first query (not warm latency).
Phase 6 run (2026-10-23), Ollama NOT running:
- `ask "What is the capital of France?"`: abstained without calling the LLM; best score 0.120 < MIN_SCORE 0.30.
  retrieve=3836 ms (includes first-time MiniLM load), generate=0 ms, total=3839 ms.
- `ask "How do I declare a path parameter with a type?"`: `LLM error: Cannot reach Ollama ... Is it running?` (graceful failure).

Phase 6 run (2026-10-24), Ollama running, llama3.2:3b, prompt v1:
- `ask "How do I declare a path parameter with a type?"`: cold generate=14076 ms (total 15144 ms); warm generate=1465 ms (total 2842 ms).
  Retrieve 1066–1375 ms, mostly MiniLM loading in a new process.
- Answer text came from p. 1 but cited `[fastapi-path-params.pdf, p. 2]`, which was not retrieved → reported in `invalid_citations`.
  Same answer and same wrong citation in an earlier run on 2026-10-23 (Ollama 0.40.9 app). Suspected cause: prompt's example tag `[guide.pdf, p. 2]` (untested).
- `ask "What is the capital of France?"`: abstained, best score 0.120, LLM not called, total=1369 ms.
- Note: the p. 1 chunk is arguably the best answer but ranks 2nd — a reason to measure retrieval in Phase 9.

Phase 7 run (2026-10-25), API via uvicorn on 127.0.0.1:8000, llama3.2:3b, prompt v1:
- `GET /health`: `{"status":"ok","index_loaded":true,"chunks":35,"llm_reachable":true,"model":"llama3.2:3b"}`.
- `POST /ask` path-parameter question: first request 12482 ms (cold Ollama + MiniLM, from middleware log);
  next 2649 ms total (retrieve 638.7, generate 2009.1); later run 3296 ms. Same p. 2 invalid citation as Phase 6.
- `POST /ask` France question: abstained, total 134.8 ms (retrieve warm: MiniLM stays loaded in the server).
- `POST /ask` blank question → 422 in 6.8 ms. `.exe` upload → 415. `../../wifi-notes.md` saved as `wifi-notes.md` in DOCS_DIR; re-upload → 409.
- `POST /index/rebuild` with one extra invented note: 15 documents → 36 chunks in 2.22 s; then `/ask` about it answered with a valid `[wifi-notes.md]` citation (top score 0.7545).
  Test note deleted and index rebuilt afterwards (14 documents, 35 chunks, 1.98 s).

Phase 8 run (2026-10-25), Streamlit UI on 127.0.0.1:8501 → API → Ollama, llama3.2:3b, prompt v1 (timings from the UI caption):
- Path-parameter question (cold): retrieve 3889 ms, generate 10430 ms, total 14320 ms. Same invalid p. 2 citation, shown as a yellow warning.
- "What happens if I send a string to a path parameter declared as int?": retrieve 629, generate 7076, total 7706 ms.
  Citation p. 2 is valid (retrieved, score 0.445), but the answer says FastAPI "will raise a ValueError"; p. 2 says it returns an HTTP error.
  → Unfaithful claim with a valid citation: citation validation cannot catch this. Needs a faithfulness check in Phase 9.
- "What is the capital of France?": abstained, retrieve 465, generate 0, total 466 ms (blue info box).
- Ollama stopped → red "assistant is unavailable" with the API's 503 message; API stopped → "API offline" page with start command.
- Rebuild from UI: 14 documents, 35 chunks in 2.94 s. Upload of an invented note → saved; second upload → "already exists" (409). Note deleted afterwards.
- Streamlit install added 20 packages (all Apache-2.0/MIT/BSD); largest: pyarrow 127 MB, pandas 82 MB, streamlit 35 MB.

## Bugs fixed (learning log)
- Stale test import after renaming `load_document` → `load_file`.
- Missing `app/ingestion/chunking.py` caused `ModuleNotFoundError`.
- pytest collected only 5 tests: missing `test_*.py` files.
- Phase 0: Stage 5 code (`app/retrieval/vector_store.py`, `scripts/build_index.py`, `scripts/search.py`) was not in the repo; recreated with 7 tests.
- Phase 6: first pull failed with `no space left on device`; later the Ollama app and models were removed, so Ollama was reinstalled with Homebrew. A network drop stalled the pull once; restarting it resumed.
- Phase 6: llama3.2:3b wrote a wrong page number in a citation; `validate_citations` caught it. Prompt fix not done yet.
- Phase 6: `ollama pull` was reported done but Ollama was not installed on this Mac; the CLI fails with a clear message instead of a stack trace.
- Phase 8: disk at 1.7 GB free again (Gradle cache regrew to 8.3 GB); cleared before installing Streamlit. First `pip install` hit a PyPI read timeout; retried with `--timeout 120 --retries 10`.
- Phase 8: security review found Streamlit listening on all interfaces by default → `server.address = "localhost"`; and LLM Markdown could load attacker image URLs → `remove_images()`.
- Phase 7: `POST /index/rebuild` returned 500 when DOCS_DIR did not exist (`FileNotFoundError` from `iterdir`); found by a test, fixed with an `is_dir()` check → 400.
- Phase 0: a personal PDF (`abouv-certificate_copy.pdf`) and `active.txt` were tracked in Git and pushed to GitHub; `.gitignore` now excludes `data/sample_docs/*` and `storage/`.
