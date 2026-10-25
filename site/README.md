# Project page

A static landing page for the AI Knowledge Assistant. Open it through any static
file server (it also works from GitHub Pages):

```bash
python -m http.server 4501 --directory site
```

Then visit http://localhost:4501.

## Where the content comes from

Nothing on the page is typed in by hand. Every answer, score and number comes from
a real run:

| File | What it holds | Made by |
|---|---|---|
| `data/recorded.json` | Three answers recorded from the real `RAGService` (llama3.2:3b), with the retrieved chunks | `tools/record.py` |
| `data/eval.json` | Numbers copied from `evaluation/results/*.json` (Phase 9) | `tools/metrics.py` |
| `data/page-data.js` | The two files above, combined for the page | `tools/build-data.mjs` |
| `assets/app-answer.jpg`, `assets/app-recording.mp4` | A screenshot and a screen recording of the real Streamlit app | `tools/app-capture.mjs`, then ffmpeg |

The citation check and the threshold panel run in the browser (`page.js`). The
citation pattern is a port of `app/generation/citations.py`.

To refresh after a new evaluation run (from the repo root, with Ollama running for `record.py`):

```bash
PYTHONPATH=. .venv/bin/python site/tools/record.py
python3 site/tools/metrics.py      # edit the file names at the top first
cd site && node tools/build-data.mjs
```

## Credits

- Scroll engine (`scrollcraft.js`, `scrollcraft.css`): scroll-craft by Nate Herk, MIT, see `LICENSE-scrollcraft-engine.txt`.
- Fonts: Geist and Geist Mono by Vercel, SIL Open Font License, see `fonts/OFL-Geist.txt`.
- Page design: built with the scroll-craft skill. Brief and design decisions are in the
  local, git-ignored `scrollcraft/builds/knowledge-assistant/BRIEF.md`.
