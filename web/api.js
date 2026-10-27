// Talks to the FastAPI backend. Same origin (the API serves this page), so no CORS and no API URL setting.
// Every function resolves to { ok, status, data, error } and never throws, so the UI never crashes on a network error.

const ASK_TIMEOUT_MS = 180_000; // longer than the API's own LLM timeout (120 s)
const DEFAULT_TIMEOUT_MS = 10_000;
const REBUILD_TIMEOUT_MS = 300_000;

function errorText(status, body) {
  const detail = body && body.detail;
  if (Array.isArray(detail)) {
    // 422 from Pydantic: [{ loc: ["body", "question"], msg: "..." }]
    return detail
      .map((item) => `${(item.loc || []).slice(1).join(".") || "request"}: ${item.msg || "invalid"}`)
      .join("; ");
  }
  return detail ? String(detail) : `HTTP ${status}`;
}

async function request(method, path, { json, form, timeout = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const options = { method, signal: controller.signal, headers: {} };
  if (json !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(json);
  } else if (form) {
    options.body = form;
  }
  try {
    const response = await fetch(path, options);
    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (response.ok) return { ok: true, status: response.status, data: body, error: "" };
    return { ok: false, status: response.status, data: null, error: errorText(response.status, body) };
  } catch (err) {
    const error =
      err.name === "AbortError"
        ? `The API did not answer within ${Math.round(timeout / 1000)} s.`
        : "Cannot reach the API. Start it with: uvicorn app.api.main:app --reload";
    return { ok: false, status: null, data: null, error };
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request("GET", "/health"),
  documents: () => request("GET", "/documents"),
  map: () => request("GET", "/index/map"),
  ask: (question) => request("POST", "/ask", { json: { question }, timeout: ASK_TIMEOUT_MS }),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("POST", "/documents", { form });
  },
  rebuild: () => request("POST", "/index/rebuild", { timeout: REBUILD_TIMEOUT_MS }),
};
