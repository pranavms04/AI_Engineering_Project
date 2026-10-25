/* AI Knowledge Assistant landing page.
   Every panel computes its state from window.KA_DATA (data/page-data.js), which is
   generated from real recorded answers and real evaluation results. Nothing about
   which citation fails, or where a sentence came from, is written by hand here. */
(function () {
  "use strict";

  var D = window.KA_DATA;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var clamp01 = function (v) { return v < 0 ? 0 : v > 1 ? 1 : v; };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fill = function (key, text) { $$('[data-fill="' + key + '"]').forEach(function (el) { el.textContent = text; }); };
  var fillHTML = function (key, html) { $$('[data-fill="' + key + '"]').forEach(function (el) { el.innerHTML = html; }); };
  var f3 = function (n) { return Number(n).toFixed(3); };
  var dateOnly = function (iso) { return String(iso).slice(0, 10); };

  /* ---------- citations: a port of app/generation/citations.py ---------- */
  var CITATION = /(?<![\w\]])\[([^\[\],]+\.\w+)(?:,\s*p\.\s*(\d+))?\]/g;
  function citationTag(source, page) { return page == null ? "[" + source + "]" : "[" + source + ", p. " + page + "]"; }
  function extractCitations(answer) {
    var tags = [], m;
    CITATION.lastIndex = 0;
    while ((m = CITATION.exec(answer))) {
      var tag = m[2] ? "[" + m[1].trim() + ", p. " + m[2] + "]" : "[" + m[1].trim() + "]";
      if (tags.indexOf(tag) === -1) tags.push(tag);
    }
    return tags;
  }
  function validateCitations(answer, sources) {
    var allowed = sources.map(function (s) { return citationTag(s.source, s.page); });
    var valid = [], invalid = [];
    extractCitations(answer).forEach(function (t) { (allowed.indexOf(t) !== -1 ? valid : invalid).push(t); });
    return { valid: valid, invalid: invalid };
  }

  /* ---------- trace: find the answer's sentence in the retrieved text ---------- */
  function words(text) {
    var out = [], re = /\S+/g, m;
    while ((m = re.exec(text))) {
      var norm = m[0].toLowerCase().replace(/[^a-z0-9_]/g, "");
      if (norm) out.push({ w: norm, start: m.index, end: m.index + m[0].length });
    }
    return out;
  }
  // Longest run of consecutive words shared by the answer and one chunk (word-level longest common substring).
  function longestRun(a, b) {
    var best = { len: 0, aEnd: 0, bEnd: 0 }, prev = new Array(b.length + 1).fill(0);
    for (var i = 1; i <= a.length; i++) {
      var cur = new Array(b.length + 1).fill(0);
      for (var j = 1; j <= b.length; j++) {
        if (a[i - 1].w === b[j - 1].w) {
          cur[j] = prev[j - 1] + 1;
          if (cur[j] > best.len) best = { len: cur[j], aEnd: i, bEnd: j };
        }
      }
      prev = cur;
    }
    return best;
  }
  function traceAnswer(answer, sources) {
    var claim = words(answer.replace(CITATION, " "));
    var best = null;
    sources.forEach(function (s, idx) {
      var w = words(s.text || "");
      var run = longestRun(claim, w);
      if (!best || run.len > best.len) best = { len: run.len, idx: idx, words: w, bEnd: run.bEnd };
    });
    if (!best || best.len < 6) return null;
    var first = best.words[best.bEnd - best.len], last = best.words[best.bEnd - 1];
    return { source: sources[best.idx], index: best.idx, start: first.start, end: last.end, coverage: best.len / claim.length };
  }

  var answers = D.answers, rec = D.recording, ev = D.evaluation;
  var A0 = answers[0], A2 = answers[answers.length - 1];
  var audit0 = validateCitations(A0.answer, A0.sources);
  var tagsAll = extractCitations(A0.answer);
  var trace0 = traceAnswer(A0.answer, A0.sources);

  /* ---------- static fills ---------- */
  fill("model", rec.model);
  fill("chunks", String(rec.chunks_in_index));
  fill("q0", A0.question);
  fill("q2", A2.question);
  fill("a0full", A0.answer);
  fill("a2", A2.answer);
  fill("recorded", "Recorded run of the real app, " + dateOnly(rec.recorded_at) + ", " + rec.model + ". The check runs in your browser.");

  var origin = trace0 ? trace0.source : A0.sources[0];
  fill("nearTag", citationTag(origin.source, origin.page));
  fill("nearScore", "score " + f3(origin.score));
  fill("nearText", (origin.text || "").replace(/\s+/g, " ").slice(0, 150).trim() + "…");
  var sheetSrc = A0.sources.filter(function (s) { return s.page === origin.page; })[0] || origin;
  fillHTML("sheet", (sheetSrc.text || "").split(/\n+/).filter(Boolean).slice(0, 8).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join(""));

  /* ---------- 2 · the peak: state as a function of act progress ---------- */
  var check = $("#check"), stage = $(".check-stage", check);
  var typed = $(".answer__typed", check), answerEl = $(".answer", check);
  var list = $(".sources", check), statusEl = $(".status-line", check);
  var inspector = $(".inspector", check), auditEl = $(".audit", check);
  var traceEl = $(".trace", check), traceSrc = $(".trace__src", check), traceText = $(".trace__text", check);
  var verdictEl = $(".verdict", check);

  A0.sources.forEach(function (s) {
    var li = document.createElement("li");
    li.innerHTML = '<span class="mono">' + esc(citationTag(s.source, s.page)) + '</span><span class="score">score ' + f3(s.score) + "</span>";
    list.appendChild(li);
  });
  var rows = $$("li", list);

  tagsAll.forEach(function (t) {
    var bad = audit0.invalid.indexOf(t) !== -1;
    var li = document.createElement("li");
    li.className = bad ? "bad" : "ok";
    li.innerHTML = '<svg class="icon" aria-hidden="true"><use href="#' + (bad ? "i-alert" : "i-check") + '"/></svg><span><span class="mono">' + esc(t) + "</span> " +
      (bad ? "is not among the " + A0.sources.length + " sources the model was given." : "matches a source the model was given.") + "</span>";
    li.style.opacity = "0";
    auditEl.appendChild(li);
  });
  var auditRows = $$("li", auditEl);

  var traceWindow = "";
  if (trace0) {
    var t = trace0.source.text;
    var from = Math.max(0, trace0.start - 140), to = Math.min(t.length, trace0.end + 160);
    traceWindow = (from > 0 ? "…" : "") + esc(t.slice(from, trace0.start)) + "<mark>" + esc(t.slice(trace0.start, trace0.end)) + "</mark>" + esc(t.slice(trace0.end, to)) + (to < t.length ? "…" : "");
  }
  var verdictText = (function () {
    if (!audit0.invalid.length) return "Every citation points at a retrieved source.";
    var bad = audit0.invalid.join(", ");
    if (!trace0) return "The answer cites " + bad + ", which the model was never given.";
    var how = trace0.coverage >= 0.9 ? "word for word" : "almost word for word";
    return "The answer cites " + bad + ". The sentence is " + how + " on " + citationTag(trace0.source.source, trace0.source.page) +
      ", which the model was given (score " + f3(trace0.source.score) + "). It copied the text and wrote the wrong page.";
  })();

  // Answer text with each complete citation wrapped, so the bad one can light up.
  function renderTyped(n, showBad) {
    var s = A0.answer.slice(0, n), html = "", last = 0, m;
    CITATION.lastIndex = 0;
    while ((m = CITATION.exec(s))) {
      var tag = m[2] ? "[" + m[1].trim() + ", p. " + m[2] + "]" : "[" + m[1].trim() + "]";
      var bad = showBad && audit0.invalid.indexOf(tag) !== -1;
      html += esc(s.slice(last, m.index)) + '<span class="cite' + (bad ? " is-bad" : "") + '">' + esc(m[0]) + "</span>";
      last = m.index + m[0].length;
    }
    return html + esc(s.slice(last));
  }

  var lastSig = "";
  function renderCheck(p) {
    var nRows = 0;
    rows.forEach(function (r, i) { var on = p >= 0.05 + i * 0.03; r.classList.toggle("is-on", on); if (on) nRows++; });
    var chars = Math.round(A0.answer.length * clamp01((p - 0.16) / 0.32));
    var checking = p >= 0.52, auditOn = p >= 0.58, searching = p >= 0.66, found = p >= 0.76 && !!trace0;

    var html = renderTyped(chars, auditOn);
    if (typed.__html !== html) { typed.innerHTML = html; typed.__html = html; }
    answerEl.classList.toggle("is-writing", p > 0.15 && chars < A0.answer.length);

    var status;
    if (p < 0.05) status = "Searching " + rec.chunks_in_index + " chunks";
    else if (p < 0.16) status = "Retrieved " + nRows + " of " + rec.chunks_in_index + " chunks";
    else if (chars < A0.answer.length) status = "Writing with " + rec.model;
    else if (!checking) status = "Answer complete";
    else status = "Checked " + tagsAll.length + " citation" + (tagsAll.length === 1 ? "" : "s") + " against " + A0.sources.length + " sources";
    if (statusEl.textContent !== status) statusEl.textContent = status;

    inspector.classList.toggle("is-on", checking);
    auditRows.forEach(function (r) { r.style.opacity = auditOn ? "1" : "0"; });
    if (searching && trace0) {
      if (!traceText.__set) { traceText.innerHTML = traceWindow; traceText.__set = true; }
      var src = found ? citationTag(trace0.source.source, trace0.source.page) + " · score " + f3(trace0.source.score) : "Searching the " + A0.sources.length + " retrieved chunks";
      if (traceSrc.textContent !== src) traceSrc.textContent = src;
    } else if (traceText.__set) { traceText.innerHTML = ""; traceText.__set = false; traceSrc.textContent = ""; }
    traceEl.classList.toggle("is-found", found);
    if (trace0) rows[trace0.index].classList.toggle("is-origin", found);
    var v = found ? verdictText : "";
    if (verdictEl.textContent !== v) verdictEl.textContent = v;

    var sig = [nRows, chars, checking ? 1 : 0, auditOn ? 1 : 0, searching ? 1 : 0, found ? 1 : 0].join("|");
    if (sig !== lastSig) { stage.setAttribute("data-sc-verify-state", sig); lastSig = sig; }
  }

  /* ---------- 3 · refuse: the gate, from the recorded scores ---------- */
  (function () {
    var track = $(".gate__track");
    A2.sources.forEach(function (s) {
      var d = document.createElement("span");
      d.className = "gate__dot";
      d.style.left = (s.score * 100).toFixed(1) + "%";
      track.appendChild(d);
    });
    var line = document.createElement("span");
    line.className = "gate__line";
    line.style.left = (rec.min_score * 100) + "%";
    line.innerHTML = "<span>threshold " + rec.min_score.toFixed(2) + "</span>";
    track.appendChild(line);
    var best = Math.max.apply(null, A2.sources.map(function (s) { return s.score; }));
    $(".gate").setAttribute("aria-label", "Closest matches score " + A2.sources.map(function (s) { return f3(s.score); }).join(", ") + ". The refusal threshold is " + rec.min_score.toFixed(2) + ".");
    fill("refuseCap", "Recorded " + dateOnly(rec.recorded_at) + ". Best match " + f3(best) + ", below the threshold of " + rec.min_score.toFixed(2) + ", so the model was not called.");
  })();

  /* ---------- 4 · threshold: recomputed from the 30 real best scores ---------- */
  (function () {
    var qs = ev.questions, MIN = 0.05, MAX = 0.85;
    var strip = $(".strip"), line = $(".strip__line"), shade = $(".strip__shade");
    var input = $("#thr"), out = $("#thr-val");
    var x = function (v) { return ((v - MIN) / (MAX - MIN)) * 100; };
    [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8].forEach(function (v) {
      var t = document.createElement("span"); t.className = "strip__tick"; t.style.left = x(v) + "%"; t.textContent = v.toFixed(1); strip.appendChild(t);
    });
    // Lanes so dots with close scores stack instead of hiding each other.
    var lanes = [], dots = [];
    qs.slice().sort(function (a, b) { return a.best_score - b.best_score; }).forEach(function (q) {
      var pos = x(q.best_score), lane = 0;
      while (lanes[lane] != null && pos - lanes[lane] < 2.2) lane++;
      lanes[lane] = pos;
      var d = document.createElement("span");
      d.className = "strip__dot " + (q.should_abstain ? "is-abstain" : "is-answerable");
      d.style.left = pos + "%";
      d.style.bottom = "calc(1.25rem + " + (lane * 15 + 2) + "px)";
      d.title = q.question + " (best score " + f3(q.best_score) + ")";
      strip.appendChild(d);
      dots.push({ el: d, q: q });
    });
    var nAbstain = qs.filter(function (q) { return q.should_abstain; }).length;
    var nAnswer = qs.length - nAbstain;
    function update() {
      var t = parseFloat(input.value), tp = 0, fp = 0, fn = 0;
      dots.forEach(function (d) {
        var refused = d.q.best_score < t;
        d.el.classList.toggle("is-refused", refused);
        if (refused && d.q.should_abstain) tp++;
        else if (refused) fp++;
        else if (d.q.should_abstain) fn++;
      });
      out.textContent = t.toFixed(2);
      input.setAttribute("aria-valuetext", t.toFixed(2));
      line.style.left = x(t) + "%";
      shade.style.width = x(t) + "%";
      $('[data-out="tp"]').innerHTML = tp + " <small>of " + nAbstain + "</small>";
      $('[data-out="fp"]').innerHTML = fp + " <small>of " + nAnswer + "</small>";
      $('[data-out="fn"]').innerHTML = fn + " <small>of " + nAbstain + "</small>";
    }
    input.value = ev.config.min_score.toFixed(2);
    input.addEventListener("input", update);
    update();

    var abstain = qs.filter(function (q) { return q.should_abstain; }).sort(function (a, b) { return b.best_score - a.best_score; });
    var answerable = qs.filter(function (q) { return !q.should_abstain; }).sort(function (a, b) { return a.best_score - b.best_score; });
    var hi = abstain[0], lo = answerable[0];
    var below = answerable.filter(function (q) { return q.best_score < hi.best_score; }).length;
    var tps = ev.llm_runs.map(function (r) { return r.abstention_true_positives; });
    var sameEveryRun = tps.every(function (n) { return n === tps[0]; });
    var refusedText = sameEveryRun ? tps[0] + " of the " + nAbstain + " in each of " + tps.length + " full runs"
      : tps.slice(0, -1).join(", ") + " and " + tps[tps.length - 1] + " of the " + nAbstain + " in " + tps.length + " full runs";
    fill("tuneLede", "Each dot is one of the " + qs.length + " test questions, placed by how closely its best match in the PDF scores. Left of the line, the app refuses before asking the model. It ships at " + ev.config.min_score.toFixed(2) + ".");
    fill("finding", "No position separates them. “" + hi.question + "” is not in the PDF, yet it scores " + f3(hi.best_score) +
      ", higher than " + below + " of the " + nAnswer + " answerable questions. One answerable question scores only " + f3(lo.best_score) +
      ". So the score gate stops the obvious misses, and the model's own refusal is the second gate: the app refused " + refusedText + ".");
  })();

  /* ---------- 5 · numbers ---------- */
  (function () {
    var runs = ev.llm_runs;
    $('[data-count-fill="hits"]').setAttribute("data-sc-count", "0 " + ev.hits_at_4);
    $('[data-count-fill="hits"]').textContent = reduce ? String(ev.hits_at_4) : "0";
    fill("ofAnswerable", "of " + ev.answerable);
    var label = function (i) { return "<small>run " + (i + 1) + "</small>"; };
    fillHTML("citeRuns", runs.map(function (r, i) { return "<span>" + Math.round(r.citation_accuracy * 100) + "%" + label(i) + "</span>"; }).join(""));
    fillHTML("refuseRuns", runs.map(function (r, i) { return "<span>" + r.abstention_true_positives + " of " + ev.should_abstain + label(i) + "</span>"; }).join(""));
    // Name the miss if it was the same question in every run.
    var missed = runs.map(function (r) { return (r.abstention_missed || []).join("|"); });
    var refuseNote = "Score gate plus the model's own refusal, three runs. Counted only when the answer is the refusal and nothing else.";
    if (missed[0] && missed.every(function (m) { return m === missed[0]; }) && runs[0].abstention_missed.length === 1) {
      refuseNote += " The miss every time: “" + runs[0].abstention_missed[0] + "”, answered from the model's own knowledge.";
    }
    fill("refuseNote", refuseNote);
    fillHTML("timeRuns", runs.map(function (r, i) { return "<span>" + (r.total_p50_ms / 1000).toFixed(1) + " s" + label(i) + "</span>"; }).join(""));
    fill("numsLede", ev.questions_total + " questions (" + ev.answerable + " answerable, " + ev.should_abstain + " that should be refused), written from one 13-page FastAPI PDF and run against the real pipeline.");
    var c = ev.config;
    fillHTML("sourcesNote", "From <code>evaluation/results/</code> in the repo: <code>" + esc(ev.retrieval_file) + "</code> and <code>" +
      runs.map(function (r) { return esc(r.file); }).join("</code>, <code>") + "</code>. Settings: chunks " + c.chunk_size + "/" + c.chunk_overlap +
      " characters, top " + c.top_k + ", threshold " + c.min_score.toFixed(2) + ", " + esc(c.embedding_model.split("/").pop()) + ", " + esc(rec.model) +
      ", " + dateOnly(c.date) + ". One PDF and 30 questions written by one person: a fair check of this build, not a benchmark.");
  })();

  /* ---------- hero depth: three planes at three rates ---------- */
  (function () {
    var hero = $("#top"), planes = $$(".plane", hero);
    if (reduce) return;
    var tx = 0, ty = 0, mx = 0, my = 0, visible = true, raf = 0;
    if (finePointer) {
      hero.addEventListener("pointermove", function (e) {
        var r = hero.getBoundingClientRect();
        tx = (e.clientX - r.left) / r.width * 2 - 1;
        ty = (e.clientY - r.top) / r.height * 2 - 1;
        kick();
      });
      hero.addEventListener("pointerleave", function () { tx = 0; ty = 0; kick(); });
    }
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; if (visible) kick(); }).observe(hero);
    window.addEventListener("scroll", kick, { passive: true });
    function kick() { if (!raf && visible) raf = requestAnimationFrame(frame); }
    function frame() {
      raf = 0;
      mx += (tx - mx) * 0.12; my += (ty - my) * 0.12;
      var r = hero.getBoundingClientRect();
      var p = clamp01(-r.top / (r.height * 0.9));
      planes.forEach(function (el) {
        var d = parseFloat(el.getAttribute("data-depth"));
        var base = el.classList.contains("plane--far") ? " rotate(-2.5deg) scale(0.94)" : el.classList.contains("plane--near") ? " rotate(1.2deg)" : "";
        el.style.transform = "translate3d(" + (mx * d * 16).toFixed(2) + "px," + (my * d * 10 - p * d * 120).toFixed(2) + "px,0)" + base;
      });
      if (Math.abs(tx - mx) > 0.002 || Math.abs(ty - my) > 0.002) kick();
    }
    frame();
  })();

  /* ---------- chrome: menu, current section, copy ---------- */
  (function () {
    var side = $("#side"), btn = $(".topbar__menu"), scrim = $(".scrim-nav");
    function setOpen(open) {
      side.classList.toggle("is-open", open);
      scrim.classList.toggle("is-on", open);
      btn.setAttribute("aria-expanded", String(open));
      if (open) { var first = $(".nav a", side); if (first) first.focus(); } else if (document.activeElement && side.contains(document.activeElement)) btn.focus();
    }
    btn.addEventListener("click", function () { setOpen(!side.classList.contains("is-open")); });
    scrim.addEventListener("click", function () { setOpen(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && side.classList.contains("is-open")) setOpen(false); });
    $$("a", side).forEach(function (a) { a.addEventListener("click", function () { if (side.classList.contains("is-open")) setOpen(false); }); });

    var links = $$(".nav a");
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.setAttribute("aria-current", String(a.getAttribute("href") === "#" + e.target.id)); });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    $$("main > section[id]").forEach(function (s) { io.observe(s); });

    var toast = $(".copied"), timer = 0;
    $$("[data-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var text = $("pre", b.parentNode).textContent;
        var done = function () {
          b.setAttribute("data-done", "");
          b.lastChild.textContent = "Copied";
          toast.textContent = "Copied to clipboard";
          toast.classList.add("is-on");
          clearTimeout(timer);
          timer = setTimeout(function () { toast.classList.remove("is-on"); b.removeAttribute("data-done"); b.lastChild.textContent = "Copy"; }, 1600);
        };
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { toast.textContent = "Select the text to copy it"; toast.classList.add("is-on"); });
      });
    });
  })();

  /* ---------- engine, then the progress loop for the pinned surface ---------- */
  // Reduced motion: the finished state, in normal flow, with no pinned scroll to wade through.
  if (reduce) { check.setAttribute("data-sc-act", "flow"); check.removeAttribute("data-sc-span"); }
  ScrollCraft.mount(document.body);
  if (reduce) { renderCheck(1); return; }
  var lastP = -1;
  (function loop() {
    var p = parseFloat(check.style.getPropertyValue("--sc-p")) || 0;
    if (Math.abs(p - lastP) > 0.0005) { renderCheck(p); lastP = p; }
    requestAnimationFrame(loop);
  })();
  renderCheck(0);
})();
