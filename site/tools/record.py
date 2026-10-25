"""Record real answers from the actual RAG pipeline for the landing page.

Run from repo root: .venv/bin/python scrollcraft/builds/knowledge-assistant/capture/record.py
Writes data/recorded.json next to this folder. Nothing here is edited by hand.
"""
import json
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.generation.citations import extract_citations
from app.generation.llm_client import OllamaClient
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import RAGService

# Only text from these documents may be published on the page. Other sources keep their
# name and score, but their text is removed (your own documents stay private).
PUBLIC_SOURCES = {"fastapi-path-params.pdf"}

QUESTIONS = [
    "How do I declare a path parameter with a type?",
    "What happens if I send a string to a path parameter declared as int?",
    "What is the capital of France?",
]
OUT = Path(__file__).resolve().parent.parent / "data" / "recorded.json"

settings = Settings.from_env()
store = VectorStore.load(settings.index_dir)
service = RAGService(store, OllamaClient(settings), settings)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

answers = []
for question in QUESTIONS:
    result = service.answer(question)
    record = asdict(result)
    record["question"] = question
    record["citations"] = extract_citations(result.answer)
    # Full text of the same retrieved chunks (the search is deterministic), so the page can
    # look for the answer's sentence in what the model was actually given.
    record["retrieved_texts"] = [
        chunk.text if chunk.metadata["source"] in PUBLIC_SOURCES else None
        for chunk, _score in store.search(question, settings.top_k)
    ]
    for source in record["sources"]:
        if source["source"] not in PUBLIC_SOURCES:
            source["snippet"] = None
    answers.append(record)

payload = {
    "recorded_at": datetime.now().isoformat(timespec="seconds"),
    "git_commit": commit,
    "model": settings.ollama_model,
    "min_score": settings.min_score,
    "top_k": settings.top_k,
    "chunks_in_index": len(store),
    "answers": answers,
}
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT}")
for a in answers:
    print("\n", a["question"], "\n ->", a["answer"][:300], "\n citations", a["citations"], "invalid", a["invalid_citations"], "abstained", a["abstained"], a["timings_ms"])
