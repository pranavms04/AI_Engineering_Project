import { api } from "./api.js";
import { KnowledgeMap, webglAvailable } from "./map.js";
import { el, extractCitations, renderAnswer, shortTag } from "./render.js";

// Questions measured in evaluation/ against the sample PDF. Shown only when that PDF is indexed.
const SAMPLE_DOC = "fastapi-path-params.pdf";
const EXAMPLES = [
  "Which tool provides FastAPI's alternative API documentation, and at what URL?",
  "How do I declare a path parameter with a type?",
  "What is the capital of France?",
];

const $ = (id) => document.getElementById(id);
const ui = {
  status: $("status"),
  statusText: document.querySelector("#status .status-text"),
  model: $("fact-model"),
  chunks: $("fact-chunks"),
  messages: $("messages"),
  welcome: $("welcome"),
  examples: $("examples"),
  exampleList: $("example-list"),
  announcer: $("announcer"),
  form: $("composer"),
  question: $("question"),
  ask: $("ask"),
  legend: $("legend"),
  mapNote: $("map-note"),
  mapSummary: $("map-summary"),
  tooltip: $("tooltip"),
  mapFallback: $("map-fallback"),
  dialog: $("docs-dialog"),
  docList: $("doc-list"),
  dropzone: $("dropzone"),
  file: $("file"),
  uploadMsg: $("upload-msg"),
  rebuild: $("rebuild"),
  rebuildMsg: $("rebuild-msg"),
};

const state = { health: null, map: null, busy: false };

const ICONS = {
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  cross: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7.5v5.5M12 16.5v.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
  info: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v5.5M12 7.6v.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4 4M8.5 11h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  book: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M9 8.5h9.5a3 3 0 0 1 3 3V24H12a3 3 0 0 1-3-3z" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
};
// Our own fixed SVG strings only, never text from the model or a document.
const icon = (name) => {
  const span = el("span", "icon");
  span.innerHTML = ICONS[name];
  return span.firstChild;
};

// ---------- status ----------

async function refreshStatus() {
  const result = await api.health();
  if (!result.ok) {
    setStatus("down", "API offline");
    ui.model.textContent = "–";
    ui.chunks.textContent = "–";
    state.health = null;
    return;
  }
  const h = (state.health = result.data);
  ui.model.textContent = h.model;
  ui.chunks.textContent = String(h.chunks);
  if (!h.index_loaded) setStatus("warn", "No index yet");
  else if (!h.llm_reachable) setStatus("warn", "Ollama offline");
  else setStatus("ok", "Ready");
}

function setStatus(kind, words) {
  ui.status.dataset.state = kind;
  ui.statusText.textContent = words;
}

// ---------- map ----------

function setupMap() {
  if (!webglAvailable()) {
    ui.mapFallback.hidden = false;
    return;
  }
  state.map = new KnowledgeMap($("map"), { onHover: showTooltip });
  $("reset-view").addEventListener("click", () => state.map.resetView());
}

async function refreshMap() {
  const result = await api.map();
  if (!result.ok) return;
  const { points, explained_variance: explained } = result.data;
  if (state.map) state.map.setPoints(points);

  ui.legend.replaceChildren();
  const sources = [...new Set(points.map((p) => p.source))];
  for (const source of sources) {
    const li = el("li");
    const dot = el("span", "swatch");
    if (state.map) dot.style.background = state.map.colorFor(source);
    li.append(dot, source);
    ui.legend.append(li);
  }
  ui.legend.hidden = sources.length === 0;

  const kept = Math.round(explained.reduce((a, b) => a + b, 0) * 100);
  ui.mapNote.textContent = points.length
    ? `${points.length} passages. Each passage's meaning is 384 numbers; this 3D view keeps about ${kept}% of how they differ, so distances here are a rough guide. The search itself uses all 384.`
    : "No passages yet. Add documents and rebuild the index.";
  ui.mapSummary.textContent = `Knowledge map with ${points.length} passages from ${sources.length} documents.`;
  showExamples(sources.includes(SAMPLE_DOC));
}

function showTooltip(entry, at) {
  if (!entry || !at) {
    ui.tooltip.hidden = true;
    return;
  }
  ui.tooltip.replaceChildren(el("strong", null, entry.tag), el("span", null, `${entry.preview}…`));
  ui.tooltip.style.left = `${at.x}px`;
  ui.tooltip.style.top = `${at.y}px`;
  ui.tooltip.hidden = false;
}

function focusOnMap(source) {
  if (state.map) state.map.focus(source.source, source.page, source.chunk_index);
}

// ---------- asking ----------

function showExamples(show) {
  ui.examples.hidden = !show;
  if (!show || ui.exampleList.childElementCount) return;
  for (const q of EXAMPLES) {
    const button = el("button", "example", q);
    button.type = "button";
    button.addEventListener("click", () => submit(q));
    ui.exampleList.append(button);
  }
}

function addUserMessage(text) {
  ui.welcome.hidden = true;
  const msg = el("div", "msg msg-user", text);
  ui.messages.append(msg);
}

function addPending() {
  const card = el("div", "msg card pending");
  const dots = el("span", "pending-dots");
  dots.append(el("span"), el("span"), el("span"));
  const passages = state.health ? state.health.chunks : "your";
  const model = state.health ? state.health.model : "the local model";
  const label = el("span", null, `Searching ${passages} passages, then asking ${model}`);
  const elapsed = el("span", "elapsed", "0 s");
  card.append(dots, label, elapsed);
  ui.messages.append(card);
  const started = performance.now();
  const timer = setInterval(() => {
    elapsed.textContent = `${Math.floor((performance.now() - started) / 1000)} s`;
  }, 500);
  scrollToEnd();
  return { card, stop: () => clearInterval(timer) };
}

function scrollToEnd() {
  ui.messages.scrollTop = ui.messages.scrollHeight;
}

async function submit(text) {
  const question = text.trim();
  if (!question || state.busy) return;
  state.busy = true;
  ui.ask.disabled = true;
  ui.question.value = "";
  autosize();

  addUserMessage(question);
  const pending = addPending();
  if (state.map) state.map.startSearching();

  const result = await api.ask(question);
  pending.stop();
  pending.card.remove();

  if (result.ok) {
    ui.messages.append(answerCard(result.data, question));
    if (state.map) {
      state.map.showAnswer({
        point: result.data.question_point,
        sources: result.data.sources,
        invalid: result.data.invalid_citations,
        abstained: result.data.abstained,
      });
    }
    announce(result.data.abstained ? "No answer found in your documents." : `Answer: ${result.data.answer}`);
  } else {
    if (state.map) state.map.showAnswer({ point: null, sources: [] });
    ui.messages.append(errorCard(result, question));
    announce(`Problem: ${result.error}`);
    refreshStatus();
  }
  scrollToEnd();
  state.busy = false;
  ui.ask.disabled = false;
  ui.question.focus();
}

function announce(text) {
  ui.announcer.textContent = "";
  requestAnimationFrame(() => (ui.announcer.textContent = text));
}

// ---------- answer cards ----------

function answerCard(answer, question) {
  const card = el("article", "msg card");
  card.setAttribute("aria-label", `Answer to: ${question}`);

  if (answer.abstained) {
    card.classList.add("card-abstain");
    const label = el("p", "card-label");
    label.append(icon("search"), "Not in your documents");
    card.append(label, el("p", null, answer.answer));
    const best = answer.sources.length ? Math.max(...answer.sources.map((s) => s.score)) : 0;
    const why =
      answer.timings_ms.generate === 0
        ? `The closest passage scored ${best.toFixed(3)}, below the threshold, so nothing was sent to the model.`
        : "The model read the closest passages and found no answer in them.";
    card.append(el("p", "meta", why));
    if (answer.sources.length) card.append(sourceList(answer, new Set()));
    return card;
  }

  const invalid = new Set(answer.invalid_citations);
  const bySourceTag = new Map(answer.sources.map((s) => [s.citation, s]));

  const chip = (tag) => {
    const ok = !invalid.has(tag);
    const button = el("button", `chip ${ok ? "chip-ok" : "chip-bad"}`);
    button.type = "button";
    button.append(icon(ok ? "check" : "cross"), shortTag(tag));
    button.setAttribute(
      "aria-label",
      ok ? `${tag}, checked: given to the model. Show on map.` : `${tag}, not among the sources the model was given.`
    );
    button.addEventListener("click", () => {
      const source = bySourceTag.get(tag);
      if (source) {
        focusOnMap(source);
        highlightSource(card, source);
      } else {
        const [, file, page] = tag.match(/^\[(.+?)(?:,\s*p\.\s*(\d+))?\]$/) || [];
        if (state.map && file) state.map.focus(file, page ? Number(page) : null, null);
      }
    });
    return button;
  };

  card.append(renderAnswer(answer.answer, chip));

  const cited = extractCitations(answer.answer);
  const wrong = cited.filter((t) => invalid.has(t)).concat(answer.invalid_citations.filter((t) => !cited.includes(t)));
  const check = el("p", "check");
  if (!cited.length && !wrong.length) {
    check.classList.add("check-none");
    check.append(icon("info"), "This answer cites no source.");
  } else if (wrong.length) {
    check.classList.add("check-bad");
    const text = el("span");
    text.append(
      el("strong", null, `${wrong.length} of ${Math.max(cited.length, wrong.length)} citations failed the check. `),
      `${wrong.join(", ")} ${wrong.length === 1 ? "is" : "are"} not among the ${answer.sources.length} passages the model was given. Read those sentences with care.`
    );
    check.append(icon("cross"), text);
  } else {
    check.classList.add("check-ok");
    const what = cited.length === 1 ? "The citation points" : `All ${cited.length} citations point`;
    check.append(icon("check"), `${what} to passages the model was actually given.`);
  }
  card.append(check);

  const validCited = new Set(cited.filter((t) => !invalid.has(t)));
  card.append(sourceList(answer, validCited));
  card.append(el("p", "meta", details(answer)));
  return card;
}

function sourceList(answer, cited) {
  const details = el("details", "sources");
  const summary = el("summary", null, `Passages searched (${answer.sources.length})`);
  details.append(summary);
  const list = el("ol", "source-list");
  for (const source of answer.sources) {
    const li = el("li");
    const row = el("button", "source");
    row.type = "button";
    row.dataset.tag = source.citation;
    const swatch = el("span", "swatch");
    if (state.map) swatch.style.background = state.map.colorFor(source.source);
    const tag = el("span", "source-tag", source.citation);
    if (cited.has(source.citation)) tag.append(el("span", "source-cited", "cited"));
    const score = el("span", "score");
    const bar = el("span", "bar");
    const fill = el("span");
    bar.append(fill);
    score.append(bar, source.score.toFixed(3));
    requestAnimationFrame(() => (fill.style.width = `${Math.max(0, Math.min(1, source.score)) * 100}%`));
    const snippet = el("span", "snippet", source.snippet);
    snippet.hidden = true;
    row.append(swatch, tag, score, snippet);
    row.setAttribute("aria-expanded", "false");
    row.addEventListener("click", () => {
      snippet.hidden = !snippet.hidden;
      row.setAttribute("aria-expanded", String(!snippet.hidden));
      focusOnMap(source);
    });
    li.append(row);
    list.append(li);
  }
  details.append(list);
  return details;
}

function highlightSource(card, source) {
  const list = card.querySelector(".sources");
  if (!list) return;
  list.open = true;
  for (const row of list.querySelectorAll(".source")) {
    row.classList.toggle("is-active", row.dataset.tag === source.citation);
  }
}

function details(answer) {
  const t = answer.timings_ms || {};
  const ms = (v) => `${Math.round(v || 0)} ms`;
  return `${answer.model} · prompt ${answer.prompt_version} · search ${ms(t.retrieve)} · writing ${ms(t.generate)} · total ${ms(t.total)}`;
}

function errorCard(result, question) {
  const card = el("article", "msg card card-error");
  const label = el("p", "card-label");
  const title =
    result.status === 503 ? "The assistant is unavailable" :
    result.status === 502 ? "The language model returned an error" :
    result.status === 422 ? "Please change your question" :
    "Something went wrong";
  label.append(icon("cross"), title);
  card.append(label, el("p", null, result.error));
  if (result.status !== 422) {
    const retry = el("button", "btn btn-small", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => {
      card.remove();
      submit(question);
    });
    card.append(retry);
  }
  return card;
}

// ---------- documents ----------

async function refreshDocuments() {
  const result = await api.documents();
  ui.docList.replaceChildren();
  if (!result.ok || !result.data.length) {
    ui.docList.append(el("li", "doc-empty", result.ok ? "No documents indexed yet." : result.error));
    return;
  }
  for (const doc of result.data) {
    const li = el("li");
    const dot = el("span", "swatch");
    if (state.map) dot.style.background = state.map.colorFor(doc.source);
    li.append(dot, doc.source, el("span", "count", `${doc.chunks} ${doc.chunks === 1 ? "passage" : "passages"}`));
    ui.docList.append(li);
  }
}

function setMsg(node, kind, text) {
  node.dataset.kind = kind;
  node.textContent = text;
}

async function uploadFile(file) {
  if (!file) return;
  setMsg(ui.uploadMsg, "info", `Uploading ${file.name}…`);
  const result = await api.upload(file);
  if (result.ok) {
    setMsg(ui.uploadMsg, "ok", `Saved ${result.data.filename}. Rebuild the index to make it searchable.`);
    ui.rebuild.focus();
  } else {
    setMsg(ui.uploadMsg, "bad", `Not uploaded: ${result.error}`);
  }
  ui.file.value = "";
}

async function rebuildIndex() {
  ui.rebuild.disabled = true;
  setMsg(ui.rebuildMsg, "info", "Rebuilding: reading, chunking and embedding every document…");
  const result = await api.rebuild();
  ui.rebuild.disabled = false;
  if (result.ok) {
    const d = result.data;
    setMsg(ui.rebuildMsg, "ok", `Done: ${d.documents} pages/files, ${d.chunks} passages in ${d.seconds} s.`);
    await Promise.all([refreshStatus(), refreshMap()]);
    refreshDocuments();
  } else {
    setMsg(ui.rebuildMsg, "bad", `Rebuild failed: ${result.error}`);
  }
}

function setupDocuments() {
  $("open-docs").addEventListener("click", () => {
    refreshDocuments();
    setMsg(ui.uploadMsg, "info", "");
    setMsg(ui.rebuildMsg, "info", "");
    ui.dialog.showModal();
  });
  $("close-docs").addEventListener("click", () => ui.dialog.close());
  ui.dialog.addEventListener("click", (e) => {
    if (e.target === ui.dialog) ui.dialog.close(); // click on the backdrop
  });
  ui.file.addEventListener("change", () => uploadFile(ui.file.files[0]));
  for (const type of ["dragenter", "dragover"]) {
    ui.dropzone.addEventListener(type, (e) => {
      e.preventDefault();
      ui.dropzone.classList.add("is-over");
    });
  }
  for (const type of ["dragleave", "drop"]) {
    ui.dropzone.addEventListener(type, () => ui.dropzone.classList.remove("is-over"));
  }
  ui.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadFile(e.dataTransfer.files[0]);
  });
  ui.rebuild.addEventListener("click", rebuildIndex);
}

// ---------- composer ----------

function autosize() {
  ui.question.style.height = "auto";
  ui.question.style.height = `${Math.min(ui.question.scrollHeight, 180)}px`;
  // Only show a scrollbar once the text is taller than the box can grow.
  ui.question.style.overflowY = ui.question.scrollHeight > 180 ? "auto" : "hidden";
}

function setupComposer() {
  ui.form.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(ui.question.value);
  });
  ui.question.addEventListener("input", autosize);
  ui.question.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      submit(ui.question.value);
    }
  });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing && !ui.dialog.open) {
      e.preventDefault();
      ui.question.focus();
    }
  });
}

// ---------- start ----------

setupMap();
setupComposer();
setupDocuments();
refreshStatus().then(refreshMap);
setInterval(refreshStatus, 15000);
ui.question.focus();

