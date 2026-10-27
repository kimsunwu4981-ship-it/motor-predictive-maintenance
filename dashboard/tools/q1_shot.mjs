// q1_shot.mjs — 레이아웃 A 현재 라이브 상태를 그대로 한 장 (명령 없음). 패널 Q1 3자 대조·§4 전후 사진용 (PowerShell, Edge).
//   node tools/q1_shot.mjs <out.png> [hash] [w h] [settle_ms]
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");
const [out, hash = "status", w = "1920", h = "1080", settle = "6000", base = "http://127.0.0.1:4173"] = process.argv.slice(2);
mkdirSync(dirname(out), { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", `--window-size=${Number(w) + 24},${Number(h) + 92}`] });
const ctx = await browser.newContext({ viewport: { width: Number(w), height: Number(h) }, locale: "ko-KR" });
const page = await ctx.newPage();
await page.goto(`${base}/#/${hash}${hash.includes("?") ? "&" : "?"}r=${Date.now()}`, { waitUntil: "networkidle" }); await sleep(Number(settle));
await page.screenshot({ path: out });
const txt = await page.evaluate(() => ({ status: document.querySelector(".sv2-status")?.textContent, cause: document.querySelector(".sv2-cause")?.textContent, load: document.querySelector(".la-load")?.textContent,
  scene: document.querySelector(".sv2-scene")?.textContent, select: document.querySelector(".la-scene select")?.selectedOptions?.[0]?.textContent, big: [...document.querySelectorAll(".tile-h .big")].map((b) => b.textContent),
  why: document.querySelector(".la-foot .v")?.textContent, what: document.querySelectorAll(".la-foot .v")[1]?.textContent, trend: document.querySelector(".tile-trend")?.closest(".tile")?.querySelector(".tile-h .dim")?.textContent }));
console.log("shot", out, JSON.stringify(txt));
await browser.close();
