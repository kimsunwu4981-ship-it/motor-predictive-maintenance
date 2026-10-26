// dashboard_export_shot.mjs — 12_export_csv 한 장만 다시 (dashboard_shots.mjs 의 getByRole 이 '비교 내보내기' 버튼을 못 찾은 경우의 재시도).
//   node tools/media/dashboard_export_shot.mjs <out_dashboard_dir> [base_url]   (dashboard/ 에서)
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");
const [outDir, base = "http://127.0.0.1:4173"] = process.argv.slice(2);
const W = 1920, H = 1080, sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", `--window-size=${W + 24},${H + 92}`] });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, locale: "ko-KR", acceptDownloads: true });
const page = await ctx.newPage();
await page.goto(`${base}/#/status?m=M1&t=40`, { waitUntil: "networkidle" }); await sleep(3000);
await page.evaluate(() => document.querySelector(".st-aref-p")?.scrollIntoView({ block: "center" })); await sleep(500);
const btn = page.locator("button", { hasText: "비교 내보내기" }).first();
await btn.waitFor({ state: "visible", timeout: 15000 });
console.log("button disabled?", await btn.isDisabled());
let dlName = "";
try {
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), btn.click({ timeout: 10000, force: true })]);
  dlName = dl.suggestedFilename(); await dl.saveAs(join(outDir, dlName)); console.log("downloaded", dlName);
} catch (e) { console.log("download failed", String(e).slice(0, 200)); }
await page.evaluate((n) => { const b = document.createElement("div"); b.textContent = n ? `다운로드됨: ${n}` : "비교 내보내기 클릭 (다운로드 이벤트 없음)"; b.style.cssText = "position:fixed;right:24px;bottom:24px;background:#1b5e20;color:#fff;padding:10px 14px;border-radius:8px;font:14px 'Malgun Gothic';z-index:99999"; document.body.appendChild(b); }, dlName);
await page.screenshot({ path: join(outDir, "12_export_csv.png") });
const capsP = join(outDir, "captions.json"); const caps = JSON.parse(readFileSync(capsP, "utf-8"));
const c = caps.captions.find((x) => x.file === "12_export_csv.png");
if (c) { c.caption = `'비교 내보내기' 직후 — 다운로드 파일 ${dlName || "(다운로드 이벤트 없음)"} (V2 형식 CSV, 4턴 40 s)`; c.download = dlName; c.url = "/#/status?m=M1&t=40"; }
writeFileSync(capsP, JSON.stringify(caps, null, 1));
await browser.close(); console.log("done");
