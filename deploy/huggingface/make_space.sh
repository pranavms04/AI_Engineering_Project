#!/bin/sh
# Assemble the Hugging Face Space folder (hf-space/, git-ignored) from this recipe plus the sample PDF.
# The PDF is public FastAPI documentation (MIT), but documents never go into this GitHub repo,
# so it is copied here only, for pushing to the Space.
set -e
cd "$(dirname "$0")/../.."

PDF="data/sample_docs/fastapi-path-params.pdf"
[ -f "$PDF" ] || { echo "Missing $PDF"; exit 1; }

rm -rf hf-space/sample_docs
mkdir -p hf-space/sample_docs
cp deploy/huggingface/Dockerfile deploy/huggingface/start.sh deploy/huggingface/README.md hf-space/
cp "$PDF" hf-space/sample_docs/
chmod +x hf-space/start.sh
echo "Space folder ready:"
ls -la hf-space hf-space/sample_docs
