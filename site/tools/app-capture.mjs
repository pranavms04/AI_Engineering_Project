// Captures the REAL Streamlit app (localhost:8501, backed by the real API and Ollama):
// one screenshot after a real answer, plus timestamped frames of asking it
// (stitched into a video by capture/encode-recording.sh with the system ffmpeg).
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve("capture/raw");
const FRAMES = path.join(OUT, "frames");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const QUESTION = "What happens if I send a string to a path parameter declared as int?";

fs.rmSync(FRAMES, { recursive: true, force: true });
fs.mkdirSync(FRAMES, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2, colorScheme: "dark" });
await page.goto("http://localhost:8501", { waitUntil: "networkidle" });
await page.getByText("API, index and LLM ready").waitFor({ timeout: 60000 });
await page.waitForTimeout(800);

// Frame grabber: CDP screencast pushes frames as the page repaints.
const cdp = await page.context().newCDPSession(page);
const log = [];
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const name = `${String(log.length).padStart(5, "0")}.jpg`;
  fs.writeFileSync(path.join(FRAMES, name), Buffer.from(data, "base64"));
  log.push({ name, t: metadata.timestamp });
  await cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: 1280, maxHeight: 800, everyNthFrame: 1 });

const box = page.getByPlaceholder("Ask a question about your documents");
await box.click();
await box.pressSequentially(QUESTION, { delay: 45 });
await page.keyboard.press("Enter");
await page.getByText("prompt v1").first().waitFor({ timeout: 180000 });
await page.waitForTimeout(2500);
await cdp.send("Page.stopScreencast");

await page.screenshot({ path: path.join(OUT, "app-answer.png") });
fs.writeFileSync(path.join(OUT, "frames.json"), JSON.stringify(log));
await browser.close();
console.log(`frames: ${log.length}, seconds: ${(log.at(-1).t - log[0].t).toFixed(1)}`);
