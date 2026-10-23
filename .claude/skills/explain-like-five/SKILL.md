---
name: explain-like-five
description: Write a beginner-friendly learning note for code that was just built in this repo — ELI5 analogy, Mermaid diagram, line-by-line walkthrough, common errors and interview Q&A — saved to docs/learning/. Use at the end of every phase, or when the user says "explain this", "I don't understand", or "teach me this part".
---

# Explain like I'm five

The reader is Pranav: a Flutter developer who knows Python basics, learning AI Engineering. He must be able to explain this code in an interview without notes.

Write `docs/learning/NN-<topic>.md` (NN = phase number) with exactly these sections:

1. **What we built and why** — 3–4 sentences. The real-world problem it solves.
2. **Explain like I'm five** — one everyday analogy (library, post office, kitchen…). Short.
3. **Diagram** — a Mermaid `flowchart` or `sequenceDiagram` showing data flowing through the new code. Label arrows with what data moves (e.g. "question: str", "top-k chunks").
4. **The real concepts** — define every new term (token, temperature, grounding, Pydantic model, middleware…) in one or two plain sentences each.
5. **Code walkthrough** — for each new file: its job in one line, then the 5–10 most important lines quoted and explained. Link to the file path.
6. **How to run and see it work** — exact commands and what the output should look like (use real output captured in this session).
7. **Common errors** — table: what you see | why | fix. Include errors actually hit during this phase.
8. **Security and limits** — what could go wrong, what we did about it, what's still a limitation.
9. **Interview questions** — 6–8 questions with short, correct model answers that reference this repo's actual code and numbers.
10. **Try it yourself** — 2 small optional exercises (e.g. "change TOP_K to 2 and see what changes").

Rules: simple English, short sentences, no hype, no invented numbers. Prefer tables and diagrams over long paragraphs.
