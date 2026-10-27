# One Dockerfile, two images:
#   docker build --target api -t ai-knowledge-assistant-api .
#   docker build --target ui  -t ai-knowledge-assistant-ui  .
# Usually run both with docker-compose.yml. Ollama is NOT in here: it runs on the host.

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# Never run the app as root inside the container.
RUN useradd --create-home --uid 10001 app
WORKDIR /app


# ---------- API: retrieval, embeddings, RAG service ----------
FROM base AS api
# CPU-only PyTorch first (official CPU wheel index). Otherwise sentence-transformers
# pulls the default build with GPU libraries, which is several GB larger.
ARG TORCH_VERSION=2.14.1
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}"
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

USER app
ENV HF_HOME=/home/app/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false
# Download MiniLM at build time, then forbid downloads at run time: the container runs offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1

COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
# The 3D web app (static files, three.js vendored). The API serves it at http://localhost:8000/.
COPY --chown=app:app web ./web
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------- UI: Streamlit only (it talks to the API over HTTP, never imports app/) ----------
FROM base AS ui
COPY requirements-ui.txt .
RUN pip install -r requirements-ui.txt

USER app
COPY --chown=app:app ui ./ui
COPY --chown=app:app .streamlit ./.streamlit
EXPOSE 8501
# Inside the container Streamlit must listen on all interfaces; docker-compose publishes
# the port on 127.0.0.1 only, so it is still reachable from this computer alone.
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
