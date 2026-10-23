---
name: implement-phase
description: Standard procedure for building one phase of the AI Knowledge Assistant (plan, implement, test, verify, document, update progress). Use whenever the user asks to start, build, implement or continue a phase, or pastes a prompt from docs/PHASE_PROMPTS.md.
---

# Implement a phase

Follow these steps in order. Do not skip steps or merge phases.

## 1. Load context
- Read `CLAUDE.md`, `docs/PROGRESS.md`, `docs/PROJECT_SPEC.md`.
- Read every file you will touch, plus the modules it imports. Never edit a file you have not read.
- Run `.venv/bin/python -m pytest -q` first and note the starting test count. If tests already fail, report it and fix that before new work.

## 2. Plan (show it, then wait)
Present a short plan:
- Files to create / modify (one line each, with purpose)
- New dependencies (name, why, licence, free?) — prefer none
- Tests you will add
- How the user will verify it manually
Wait for "go" unless the user already said to proceed without stopping.

## 3. Implement the simplest working version
- Extend existing code; don't rewrite working modules or rename public functions.
- Type hints, small functions, `logging` in `app/`, clear error messages.
- Config values come from `app/config.py`, never hard-coded in several places.
- If a new dependency is needed: pin it in `requirements.txt`.

## 4. Test
- Add tests for each new behaviour: happy path, edge cases, failure paths.
- The LLM is always mocked in tests (`FakeLLMClient`). Tests must pass without Ollama running.
- For AI outputs, assert relationships (A scores higher than B, citation is valid), not exact text.
- Run `.venv/bin/python -m pytest -q`. All tests must pass. Report the new count.

## 5. Verify for real
- Run the phase's manual check command(s) and paste the actual output.
- If something fails, debug it (use the `engineering:debug` approach: reproduce, isolate, fix, retest). Never claim success you didn't observe.
- Use `verify-pipeline` skill when the index or retrieval might be affected.

## 6. Security pass
Run the `security-check` skill on the files you changed.

## 7. Teach
Use the `explain-like-five` skill to write `docs/learning/NN-<phase>.md`.

## 8. Wrap up
- Update `docs/PROGRESS.md`: status, test count, real measured numbers, bugs fixed.
- Update `CLAUDE.md` §4/§7 if architecture or commands changed.
- Suggest a conventional commit message. Do not commit or push unless asked.
- End with: what was built (3–5 bullets), how to run it, what's next. Keep it short.
