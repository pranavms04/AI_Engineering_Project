# PageProof public demo for a Hugging Face Space (Docker SDK, free CPU).
# Everything runs inside this one container: Ollama + llama3.2:3b, MiniLM, FAISS, the API and the 3D web app.
# DEMO_MODE=1 switches uploads and rebuilds off, because the link is public.
#
# The app code is cloned from the public GitHub repo; the sample PDF comes from this Space repo.

FROM ollama/ollama:0.40.4 AS ollama

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Ollama: the binary and its runtime libraries from the official image.
COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama /usr/lib/ollama

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs Space containers as user 1000.
RUN useradd --create-home --uid 1000 user
ENV HOME=/home/user OLLAMA_MODELS=/home/user/.ollama/models
WORKDIR /home/user/app

ARG REPO=https://github.com/pranavms04/AI_Engineering_Project.git
ARG REF=master
RUN git clone --depth 1 --branch "$REF" "$REPO" . && git log -1 --format="Building PageProof at %h %s" && rm -rf .git

# CPU-only PyTorch first (much smaller than the default build), then the API's pinned requirements.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.14.1" \
    && pip install -r requirements-api.txt

COPY --chown=user sample_docs/ data/sample_docs/
COPY --chown=user start.sh /home/user/start.sh
RUN chown -R user:user /home/user && chmod +x /home/user/start.sh
USER user

# Bake everything in at build time, so a visitor never waits for a download.
ENV HF_HOME=/home/user/.cache/huggingface TOKENIZERS_PARALLELISM=false
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1
RUN python -m scripts.build_index
RUN ollama serve > /tmp/ollama-build.log 2>&1 & \
    for i in $(seq 1 60); do ollama list > /dev/null 2>&1 && break; sleep 1; done; \
    ollama pull llama3.2:3b

ENV DEMO_MODE=1 \
    OLLAMA_URL=http://127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=24h \
    LLM_TIMEOUT_S=170
EXPOSE 7860
CMD ["/home/user/start.sh"]
