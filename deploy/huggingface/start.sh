#!/bin/sh
# Start Ollama, wait until it answers, warm the model up in the background, then serve PageProof on port 7860.
set -e

ollama serve > /tmp/ollama.log 2>&1 &

python - <<'EOF'
import time, urllib.request
for _ in range(120):
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        print("Ollama is up")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Ollama did not start; see /tmp/ollama.log")
EOF

# Load the model into memory now, so the first visitor doesn't pay for it. Runs in the background.
python - <<'EOF' &
import json, urllib.request
body = json.dumps({"model": "llama3.2:3b", "prompt": "Hi", "stream": False, "options": {"num_predict": 1}}).encode()
try:
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate", body, {"Content-Type": "application/json"}), timeout=300)
    print("Model warmed up")
except Exception as exc:
    print("Warm-up skipped:", exc)
EOF

exec uvicorn app.api.main:app --host 0.0.0.0 --port 7860
