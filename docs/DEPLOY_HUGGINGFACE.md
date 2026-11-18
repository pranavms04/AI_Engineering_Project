# Deploy to Hugging Face Spaces

> **Update 2026-11-18: Docker and Gradio Spaces now require a paid plan (PRO).** Hugging Face's docs:
> "Static Spaces are free for everyone. Gradio and Docker Spaces run on compute and require a paid plan".
> To stay at ₹0, PageProof uses a **free Static Space** for the project page (below). The Docker recipe in
> `deploy/huggingface/` (live LLM, `DEMO_MODE=1`) is kept for anyone with a paid plan, but is **not deployed**.

## Free: Static Space (project page)
1. https://huggingface.co/new-space → Space name `pageproof` → SDK **Static** → template **Blank** → **Public** → Create.
2. Build the folder (git-ignored): copy `site/` without `tools/`, plus a Space card (`sdk: static`):
   it is already in `hf-static/`.
3. On the Space: **Files → + Contribute → Upload files**, drag in everything inside `hf-static/`
   (files and the `assets/`, `data/`, `fonts/` folders), commit. The page is live at
   `https://huggingface.co/spaces/<user>/pageproof`.

---

# Paid option: live demo (Docker Space)

With a paid plan, a Docker Space on CPU Basic hardware (2 vCPU, 16 GB RAM, no GPU) can run PageProof in one
container: Ollama + llama3.2:3b, MiniLM, FAISS, the API and the 3D web app on port 7860.

It would be hosted and public, so it runs in **demo mode** (`DEMO_MODE=1`):
uploads and rebuilds return 403 and are hidden in the web app. Only the sample FastAPI PDF is served.

## Files
| File | Purpose |
|---|---|
| `deploy/huggingface/Dockerfile` | Space image: Ollama binary from `ollama/ollama:0.40.4`, Python 3.11, CPU torch, app cloned from the public GitHub repo, MiniLM + index + llama3.2:3b baked in at build time, runs as uid 1000 |
| `deploy/huggingface/start.sh` | Starts Ollama, waits for it, warms the model up in the background, runs uvicorn on 7860 |
| `deploy/huggingface/README.md` | The Space card (YAML header: `sdk: docker`, `app_port: 7860`), credits and licences |
| `deploy/huggingface/make_space.sh` | Builds `hf-space/` (git-ignored): the three files above + `sample_docs/fastapi-path-params.pdf` |

The PDF never goes into the GitHub repo (CLAUDE.md §3.4); it is copied into `hf-space/` and pushed to the Space only.
It is FastAPI documentation, MIT licence, credited in the Space card.

## Steps (yours: accounts and tokens stay with you)
1. **Push this repo to GitHub first.** The Space clones `master` at build time, so demo mode must be on GitHub.
2. Create a free account at https://huggingface.co.
3. **New Space** → name `pageproof` → SDK **Docker** → template **Blank** → hardware **CPU basic (free)** → **Public**.
4. Create an access token with **Write** permission: Settings → Access Tokens.
5. Assemble and push the Space (use your HF username; paste the token when git asks for a password):
   ```bash
   sh deploy/huggingface/make_space.sh
   cd hf-space && git init -b main && git add . && git commit -m "PageProof demo"
   git remote add origin https://huggingface.co/spaces/<your-username>/pageproof
   git push -u origin main
   ```
6. Watch **Logs → Build** on the Space page. When it says Running, open the **App** tab.

## Updating
Push to GitHub, then on the Space: **Settings → Factory rebuild** (re-clones `master`).
If you change the Space recipe, run `make_space.sh` again and push `hf-space/`.

## Troubleshooting
| What you see | Why | Fix |
|---|---|---|
| Build log: `COPY failed: sample_docs` | `hf-space/` assembled without the PDF | Put the PDF in `data/sample_docs/`, rerun `make_space.sh` |
| App shows "Ollama offline" | Ollama crashed (often memory) | Check Logs; restart the Space |
| First answer very slow | Model loading into RAM after the Space woke up | Wait; later answers are faster |
| Space sleeps | Free Spaces sleep after inactivity | The next visitor wakes it (build is not repeated) |
| Upload button missing | Demo mode, by design | Run locally for your own documents |
