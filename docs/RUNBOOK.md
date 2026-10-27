# Runbook

How to set up, run, rebuild and fix the AI Knowledge Assistant. Every problem in the
troubleshooting table actually happened while building this project.

## 1. First-time setup (local)

```bash
git clone https://github.com/pranavms04/AI_Engineering_Project.git
cd AI_Engineering_Project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install [Ollama](https://ollama.com) (the app, or `brew install ollama`), then:

```bash
ollama serve                 # leave running
ollama pull llama3.2:3b      # ~2 GB, once
```

Optional settings live in environment variables; see `.env.example` for every one and its default.

## 2. Add documents and build the index

```bash
cp ~/Documents/some-guide.pdf data/sample_docs/
python -m scripts.build_index
```

Rebuild after any change to the documents, `CHUNK_SIZE`/`CHUNK_OVERLAP`, or the embedding
model. The API can also rebuild: upload in the UI sidebar, then **Rebuild index**.

## 3. Run it

| What | Command | Where |
|---|---|---|
| LLM | `ollama serve` | 127.0.0.1:11434 |
| API | `uvicorn app.api.main:app` | http://127.0.0.1:8000 (API page at `/docs`) |
| UI | `streamlit run ui/streamlit_app.py` | http://localhost:8501 |
| One question, no UI | `python -m scripts.ask "question"` | terminal |
| Retrieval only | `python -m scripts.search "question" -k 3` | terminal |

Quick health check: `curl -s localhost:8000/health` → `"status":"ok"` when the index is
loaded and Ollama is reachable.

## 4. Run it with Docker

The API and UI run in containers; Ollama stays on the Mac (Docker cannot use the Apple GPU).

**Docker on a Mac without Docker Desktop** (free, open source):

```bash
brew install colima docker docker-compose
colima start --cpu 2 --memory 3 --disk 20
```

Then, with `ollama serve` running on the Mac:

```bash
docker-compose up --build        # Docker Desktop: docker compose up --build
```

- Images: `ai-knowledge-assistant-api` (CPU-only PyTorch, MiniLM baked in, runs offline)
  and `ai-knowledge-assistant-ui` (Streamlit only).
- `data/` and `storage/` are mounted from the host. Build the index first (section 2) or
  use **Rebuild index** in the UI.
- Ports are published on 127.0.0.1 only.
- Stop: `docker-compose down`. Free the VM: `colima stop`.

## 5. Tests and evaluation

```bash
python -m pytest -q                              # 123 tests, no Ollama needed
python -m evaluation.run_eval                    # retrieval metrics, ~10 s
python -m evaluation.run_eval --with-llm         # full answers, needs Ollama, a few minutes
python -m evaluation.rescore evaluation/results/<run>-llm-*.json   # re-score saved answers
```

Every run writes `evaluation/results/<timestamp>-*.json` with its config and git commit.

## 6. Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `LLM error: Cannot reach Ollama at http://localhost:11434/api/chat. Is it running?` / API 503 | Ollama not running | `ollama serve` |
| `Model 'llama3.2:3b' not found` / API 502 | Model not pulled | `ollama pull llama3.2:3b` |
| `zsh: command not found: ollama` | Ollama not installed, or the app was removed | Install it again (`brew install ollama`) |
| `no space left on device` during `ollama pull`, `pip install` or a Docker build | Disk full | Free space (on this Mac the Gradle cache `~/.gradle/caches` regrows to 8+ GB), then retry |
| `lookup ... no such host` in the Ollama log during a pull | Network dropped | Retry the pull; it resumes |
| `ReadTimeoutError ... files.pythonhosted.org` | Slow connection to PyPI | `pip install --timeout 120 --retries 10 -r requirements.txt` |
| `FileNotFoundError: No index in storage/index` / API 503 "No index loaded" | Index not built | `python -m scripts.build_index` or **Rebuild index** in the UI |
| `Index was built with ... Rebuild the index.` | Embedding model changed | Rebuild the index |
| `ModuleNotFoundError: No module named 'app'` | Run from the wrong folder, or as a plain script | Run from the repo root with `python -m ...` |
| UI shows "API offline" | API not running, or wrong `API_URL` | Start the API; check `API_URL` |
| `Address already in use` on 8000/8501 | An earlier server is still running | Stop it (`lsof -i :8000` to find it) |
| First answer takes 10-20 s | The model is loading into memory | Normal; later answers are faster |
| `docker: unknown command: docker compose` | Homebrew installs Compose as a separate command | Use `docker-compose` |
| A harmless `Redirects are currently not supported in MacOs` line | PyTorch on macOS | Ignore |
