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
| 6 | Local LLM answers + citations | ⏭ next | | |
| 7 | FastAPI backend | ⬜ | | |
| 8 | Streamlit UI | ⬜ | | |
| 9 | Evaluation | ⬜ | | |
| 10 | Docker, CI, README | ⬜ | | |
| 11 | Interview prep pack | ⬜ | | |

## Environment facts
- macOS, Python 3.11.7, `.venv`
- Chip / RAM: Apple M1 (arm64), 8 GB RAM (`sysctl hw.memsize` = 8589934592)
- Ollama model: _chosen in Phase 6_

## Measured numbers (only real ones)
Phase 0 run (2026-10-23), docs = `fastapi-path-params.pdf` + `active.txt`:
- `build_index`: 14 documents (pages/files) → 35 chunks (500/100), 2.6 s total.
- `search "How do I declare a path parameter with a type?"`: top-3 =
  0.555 [fastapi-path-params.pdf, p. 6], 0.470 [p. 1], 0.468 [p. 12].
  505 ms, which includes loading MiniLM on the first query (not warm latency).
- Note: the p. 1 chunk is arguably the best answer but ranks 2nd — a reason to measure retrieval in Phase 9.

## Bugs fixed (learning log)
- Stale test import after renaming `load_document` → `load_file`.
- Missing `app/ingestion/chunking.py` caused `ModuleNotFoundError`.
- pytest collected only 5 tests: missing `test_*.py` files.
- Phase 0: Stage 5 code (`app/retrieval/vector_store.py`, `scripts/build_index.py`, `scripts/search.py`) was not in the repo; recreated with 7 tests.
- Phase 0: a personal PDF (`abouv-certificate_copy.pdf`) and `active.txt` were tracked in Git and pushed to GitHub; `.gitignore` now excludes `data/sample_docs/*` and `storage/`.
