# AI Knowledge Assistant

A local, free, private RAG app: ask questions about your own technical documents
(PDF, Markdown, TXT) and get answers grounded only in those documents, with
citations like `[fastapi-path-params.pdf, p. 2]`.

> Work in progress. Retrieval (ingest → chunk → embed → FAISS search) works today.
> Answer generation with a local LLM (Ollama), an API, a UI and evaluation come next.
> See `docs/PROGRESS.md` for status and `docs/PROJECT_SPEC.md` for the design.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Put your own `.pdf` / `.md` / `.txt` files in `data/sample_docs/` (git-ignored), then:

```bash
python -m pytest -q                                   # run tests
python -m scripts.build_index                         # build storage/index
python -m scripts.search "How do I declare a path parameter with a type?" -k 3
```

Scanned PDFs without a text layer are skipped with a warning (OCR is not supported).
