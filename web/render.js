// Turns model text into DOM safely. Never uses innerHTML for anything the model or a document wrote:
// a document could carry hidden instructions, and the model could repeat them as HTML.

// Same rule as app/generation/citations.py: [file.pdf] or [file.pdf, p. 3], only indexable file types.
const CITATION = /(?<![\w\]])\[([^[\],]+\.(?:md|pdf|txt))(?:,\s*p\.\s*(\d+))?\]/gi;
// Markdown image: the browser would fetch the URL without a click, so images are dropped.
const IMAGE = /!\[[^\]]*\]\([^)]*\)/g;

export function citationTag(source, page) {
  return page ? `[${source.trim()}, p. ${page}]` : `[${source.trim()}]`;
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Inline pieces: `code`, **bold**, and citation chips. Everything else is plain text.
function inline(text, onCitation) {
  const frag = document.createDocumentFragment();
  const pattern = new RegExp(`${CITATION.source}|\`([^\`]+)\`|\\*\\*([^*]+)\\*\\*`, "gi");
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    if (m.index > last) frag.append(text.slice(last, m.index));
    if (m[1]) frag.append(onCitation(citationTag(m[1], m[2])));
    else if (m[3]) frag.append(el("code", null, m[3]));
    else if (m[4]) frag.append(el("strong", null, m[4]));
    last = m.index + m[0].length;
  }
  if (last < text.length) frag.append(text.slice(last));
  return frag;
}

// Block pieces: ``` code fences, "- " lists, and paragraphs.
export function renderAnswer(text, onCitation) {
  const root = el("div", "answer-text");
  const clean = text.replace(IMAGE, "[image removed]");
  const parts = clean.split(/```[\w-]*\n?([\s\S]*?)```/g);
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const pre = el("pre");
      pre.append(el("code", null, part.replace(/\n$/, "")));
      root.append(pre);
      return;
    }
    for (const block of part.split(/\n{2,}/)) {
      const lines = block.split("\n").filter((l) => l.trim());
      if (!lines.length) continue;
      if (lines.every((l) => /^\s*([-*]|\d+\.)\s+/.test(l))) {
        const list = el(/^\s*\d+\./.test(lines[0]) ? "ol" : "ul");
        for (const line of lines) {
          const item = el("li");
          item.append(inline(line.replace(/^\s*([-*]|\d+\.)\s+/, ""), onCitation));
          list.append(item);
        }
        root.append(list);
      } else {
        const p = el("p");
        lines.forEach((line, n) => {
          if (n) p.append(document.createElement("br"));
          p.append(inline(line, onCitation));
        });
        root.append(p);
      }
    }
  });
  return root;
}

export function extractCitations(text) {
  const tags = [];
  for (const m of text.matchAll(CITATION)) {
    const tag = citationTag(m[1], m[2]);
    if (!tags.includes(tag)) tags.push(tag);
  }
  return tags;
}

export function shortTag(tag) {
  // "[fastapi-path-params.pdf, p. 2]" -> "p. 2" when the file is obvious from context
  const m = tag.match(/,\s*(p\.\s*\d+)\]$/);
  return m ? m[1] : tag.slice(1, -1);
}
