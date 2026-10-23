---
name: verify-pipeline
description: Rebuild the FAISS index from data/sample_docs and run smoke checks on ingestion, retrieval and (if available) the full RAG answer path. Use after changing loader, cleaning, chunking, embeddings, vector store, prompts or config, or when the user says "check it still works", "smoke test" or "rebuild".
---

# Verify the pipeline end to end

Run from the repo root with the venv active.

1. **Unit tests:** `.venv/bin/python -m pytest -q` → all must pass.
2. **Documents present:** list `data/sample_docs/`. If it has no text-based PDF/MD/TXT, stop and ask the user to add one (e.g. a docs page saved as PDF). Never download or commit documents yourself.
3. **Rebuild index:** `python -m scripts.build_index` → record chunk count and build time.
4. **Retrieval smoke test:** `python -m scripts.search "<a question answerable from the docs>" -k 3` → top result must come from the expected file; record top score and search ms.
5. **Abstain smoke test (Phase 6+):** `python -m scripts.ask "What is the capital of France?"` → must abstain.
6. **RAG smoke test (Phase 6+):** if `curl -s localhost:11434/api/tags` succeeds, run `python -m scripts.ask "<answerable question>"` → answer must contain at least one valid citation. If Ollama isn't running, say so and skip (don't fail the check).
7. **API smoke test (Phase 7+):** if the API is running, `curl -s localhost:8000/health`.

Report a short table: check | result | real numbers. Flag anything unexpected (e.g. top result from the wrong file, invalid citations, chunk count changed a lot).
