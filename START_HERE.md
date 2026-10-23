# Start Here — using Claude Code on this project

## 1. Put the kit into your repo
Unzip so the files land at your repo root:

```
ai-knowledge-assistant/
├── CLAUDE.md                     ← project brain, auto-loaded every session
├── START_HERE.md                 ← this file
├── .claude/skills/               ← 5 project skills
│   ├── implement-phase/          the build procedure for every phase
│   ├── explain-like-five/        writes your learning notes
│   ├── verify-pipeline/          rebuild index + smoke tests
│   ├── run-evaluation/           honest metrics (Phase 9)
│   └── security-check/           pre-commit safety review
└── docs/
    ├── PROJECT_SPEC.md           full concept, architecture, design decisions
    ├── PROGRESS.md               tracker Claude Code keeps updated
    └── PHASE_PROMPTS.md          copy-paste prompt for every phase
```

Commit it: `git add CLAUDE.md START_HERE.md .claude docs && git commit -m "Add Claude Code project kit"`

## 2. Open Claude Code in the repo
Install/launch per the official docs: https://docs.claude.com/en/docs/claude-code/overview
Start it from the repo root (`~/Projects/AI Engineering/ai-knowledge-assistant`).
Check the skills are found by typing `/` — you should see the five skill names.

## 3. Run the phases in order
Open `docs/PHASE_PROMPTS.md`, copy **Phase 0**, paste, and let it finish.
Then Phase 6 → 7 → 8 → 9 → 10 → 11. One phase per session is a good rhythm.

After each phase:
1. Read `docs/learning/NN-*.md` it wrote for you.
2. Run the commands yourself once.
3. Commit.

## 4. Things only you can do
- Install Ollama (ollama.com) and `ollama pull` the model Claude Code recommends.
- Choose which documents go into `data/sample_docs/` (public docs you're allowed to use).
- Review and approve the evaluation questions in Phase 9 — you own the ground truth.
- Push to GitHub and record the demo video.

## 5. Keep it *your* project
Interviewers will ask "why did you do X?". Before moving on from a phase, make
sure you can answer the interview questions in its learning note. If anything
is unclear, ask Claude Code: "use explain-like-five on <file>".
