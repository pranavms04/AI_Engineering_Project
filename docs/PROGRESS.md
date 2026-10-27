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
| 8 | Streamlit UI | ✅ done (restyled 2026-10-27, 135 tests total) | 91 total (+16) | one-file UI over HTTP; all error states checked in the browser; bound to localhost; Markdown images stripped |
| 9 | Evaluation | ✅ done | 123 total (+24, +8 follow-up) | 30-question set; recall@4 0.958, MRR@10 0.803; citation acc. 0.750–0.905 over 3 LLM runs; kept 500/100 and MIN_SCORE 0.30 after experiments |
| 10 | Docker, CI, README | ✅ done (CI to confirm on GitHub) | 123 total | `docker-compose up --build` verified with Ollama on the host; images: api 2.1 GB, ui 827 MB; non-root; ports on 127.0.0.1 |
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

Phase 9 evaluation (2026-10-25), `evaluation/dataset.jsonl` = 30 questions (24 answerable, 6 should abstain), all from fastapi-path-params.pdf.
Details and file names: `evaluation/README.md`. Config: chunk 500/100, top_k 4, MIN_SCORE 0.30, MiniLM, llama3.2:3b, prompt v1, temp 0.1.
- Retrieval (deterministic): recall@1 0.667, recall@3 0.917, recall@4 0.958, recall@10 1.000, MRR@10 0.803; gate abstention P 0.500 / R 0.333.
- Full RAG, 3 identical runs: keyword coverage 0.694 / 0.736 / 0.694; citation accuracy 0.750 / 0.826 / 0.905;
  answers with an invalid citation 5 / 4 / 2; final abstention P/R 0.600/1.000 (inflated, see bugs) / 0.625/0.833 / 0.556/0.833;
  total latency p50/p95 ms 4925/11759, 3420/8686, 2591/10927.
- Repeatable failures: q01 cites p. 2 (not retrieved) every run; q06 cites p. 4; q02 refused by the LLM; q18/q21 (paraphrases) refused by the gate;
  q29 (Docker, should abstain) gets an invented answer; q08 says "the last one will override" in all 5 runs (p. 6: "the first one will always be used").
- Chunk experiment (retrieval): 300/100 → R@4 0.875, MRR 0.794; 500/100 → 0.958, 0.803; 800/150 → 0.917, 0.779. Kept 500/100.
- MIN_SCORE sweep (gate): no threshold separates classes (q18 answerable and q25 should-abstain both 0.2778; q26–q29 score 0.45–0.59).
  Tested 0.20 with the LLM (2 runs): q21 fixed, but q18 became wrong and q25 invented. Kept 0.30.

Phase 9 follow-up (2026-10-25): `_is_abstain` and citation pattern fixed (see Bugs). 123 tests.
- Re-scored baseline answers (no LLM): citation accuracy 0.789 / 0.864 / 0.905; abstention TP 5 / 5 / 5 of 6.
- 3 fresh runs: citation accuracy 0.870 / 0.905 / 0.895; final abstention P/R = strict P/R in every run
  (0.625/0.833, 0.556/0.833, 0.625/0.833); remaining invalid citations are real wrong pages (q01 p. 2, q06 p. 4, q08 p. 7 once).
  Latency p50 5905 / 5173 / 7359 ms: not comparable to baseline (Mac also running a browser and a web server).

Phase 10 Docker check (2026-10-27, Colima 2 CPU / 3 GB, Docker 29.5.2):
- `docker-compose up --build -d`: exit 0 in 2 s (all layers cached); API container healthy.
- `/health` from the container: `llm_reachable: true` (Ollama on the host via host.docker.internal), 35 chunks.
- `/ask` path-parameter question: 9467.6 ms total (generate 8379.3, first question); same invalid p. 2 citation as Phase 9.
- `/ask` France: abstained, 70.6 ms. UI in browser: "Pydantic" for q06 with the known invalid p. 4 citation flagged, 3685 ms.
- Both containers run as uid 10001 (app); API image contains no data/, storage/, PDFs or .env.
- CI workflow parses; not yet run on GitHub (needs a push).

## Bugs fixed (learning log)
- UI restyle (2026-10-27): the empty-state guide stayed visible while the first answer loaded (drawn before `st.chat_input` was read); fixed by reading the input first.
- Stale test import after renaming `load_document` → `load_file`.
- Missing `app/ingestion/chunking.py` caused `ModuleNotFoundError`.
- pytest collected only 5 tests: missing `test_*.py` files.
- Phase 0: Stage 5 code (`app/retrieval/vector_store.py`, `scripts/build_index.py`, `scripts/search.py`) was not in the repo; recreated with 7 tests.
- Phase 6: first pull failed with `no space left on device`; later the Ollama app and models were removed, so Ollama was reinstalled with Homebrew. A network drop stalled the pull once; restarting it resumed.
- Phase 6: llama3.2:3b wrote a wrong page number in a citation; `validate_citations` caught it. Prompt fix not done yet.
- Phase 6: `ollama pull` was reported done but Ollama was not installed on this Mac; the CLI fails with a clear message instead of a stack trace.
- Phase 9: evaluation found the app's `_is_abstain` uses a substring match — an invented answer ending with the refusal sentence counts as abstained (q29). **Fixed (Phase 9 follow-up):** the whole answer must be the refusal sentence.
- Phase 9: citation regex matches code like `[user.value]` as a citation (q09). **Fixed (Phase 9 follow-up):** only `.pdf`/`.md`/`.txt` tags (from `SUPPORTED_SUFFIXES`) count. Re-scoring the saved baseline answers: run 1 citation accuracy 0.750 → 0.789 and refusals 6/6 → 5/6; run 2 0.826 → 0.864; run 3 unchanged (0.905).
- Phase 8: disk at 1.7 GB free again (Gradle cache regrew to 8.3 GB); cleared before installing Streamlit. First `pip install` hit a PyPI read timeout; retried with `--timeout 120 --retries 10`.
- Phase 8: security review found Streamlit listening on all interfaces by default → `server.address = "localhost"`; and LLM Markdown could load attacker image URLs → `remove_images()`.
- Phase 7: `POST /index/rebuild` returned 500 when DOCS_DIR did not exist (`FileNotFoundError` from `iterdir`); found by a test, fixed with an `is_dir()` check → 400.
- Phase 0: a personal PDF (`abouv-certificate_copy.pdf`) and `active.txt` were tracked in Git and pushed to GitHub; `.gitignore` now excludes `data/sample_docs/*` and `storage/`.
