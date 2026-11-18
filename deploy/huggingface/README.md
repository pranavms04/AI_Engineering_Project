---
title: PageProof
emoji: 📄
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Answers from your documents, with the page to prove it
---

# PageProof: public demo

Ask questions about the sample document (FastAPI's "Path Parameters" tutorial). PageProof answers
**only** from that document, cites the page for every claim, checks each citation against the passages
the model was given, and says *"I couldn't find this in the documents."* instead of guessing.
A 3D map shows retrieval live: your question flies in and the passages it used light up.

Try:
- *Which tool provides FastAPI's alternative API documentation, and at what URL?*
- *How do I declare a path parameter with a type?* (watch the citation check)
- *What is the capital of France?* (it should refuse)

**This demo:** runs on a free CPU (no GPU), so answers are slower than on a laptop, and the first
question after the Space wakes up takes longest. Uploads and rebuilds are switched off because the link
is public. To use your own documents, run PageProof on your own computer; it is free and private.

- Code, evaluation and setup: https://github.com/pranavms04/AI_Engineering_Project
- Project page: https://pranavms04.github.io/AI_Engineering_Project/

**Stack:** Llama 3.2 3B via Ollama · all-MiniLM-L6-v2 · FAISS · FastAPI · three.js

**Licences:** PageProof code MIT. Llama 3.2: Llama 3.2 Community License (Meta). all-MiniLM-L6-v2:
Apache-2.0. Sample document: FastAPI documentation, © Sebastián Ramírez, MIT licence (https://github.com/fastapi/fastapi).
