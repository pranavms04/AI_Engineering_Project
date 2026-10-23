---
name: security-check
description: Review changed files in this repo for secrets, unsafe deserialization, file-upload risks, prompt injection, and privacy leaks before committing. Use at the end of every phase, before any commit or push, or when the user asks "is this safe" or "security review".
---

# Security check

Review `git diff` plus new untracked files. Report findings as: severity (high/medium/low) | file:line | issue | fix. Fix high issues immediately; ask before larger changes.

Checklist:
1. **Secrets:** no keys, tokens, passwords or real `.env` values in code, tests, docs or notebooks. `.env` is git-ignored; `.env.example` has placeholders only.
2. **Private data:** nothing under `data/sample_docs/` or `storage/` is tracked (`git ls-files data storage`). No personal documents quoted in docs or tests — use invented sample text.
3. **Deserialization:** no `pickle`, `joblib.load`, `torch.load` on untrusted files, `eval`, or `exec`. Index metadata is JSON.
4. **Uploads (Phase 7+):** extension allow-list (.pdf .md .txt), size limit, filename sanitised (no `..`, no absolute paths, use `Path(name).name`), saved only inside DOCS_DIR.
5. **Prompt injection:** retrieved document text is passed as clearly delimited data; the system prompt says to ignore instructions inside documents; the app never executes actions based on model output.
6. **Input validation:** question length limits; Pydantic schemas on every API input; errors don't leak stack traces to clients.
7. **Network:** API binds to localhost by default; CORS limited to localhost origins; only outbound call is to the local Ollama URL.
8. **Dependencies:** new packages are pinned and their licences are compatible (MIT/BSD/Apache).
9. **Logging:** logs don't contain full document text or anything sensitive beyond file names.
