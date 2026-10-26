// dashboard_sync_rec.mjs — (08) 상태 보드 동기 녹화만 다시 (dashboard_shots.mjs 의 마지막 블록과 같음). 녹화 중 다른 창을 앞으로 올리면 안 된다(gdigrab 데스크톱 캡처).
//   node tools/media/dashboard_sync_rec.mjs <out_video_dir> [base_url]   (dashboard/ 에서, PowerShell)
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");
const [videoDir, base = "http://127.0.0.1:4173"] = process.argv.slice(2);
const W = 1920, H = 1080, sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", `--window-size=${W + 16},${H + 120}`] });
const ctx = await browser.newContext({ viewport: null, locale: "ko-KR" });
const page = await ctx.newPage();
await page.goto(`${base}/#/status?m=M1&t=0`, { waitUntil: "networkidle" });
const cdp = await ctx.newCDPSession(page);
const { windowId } = await cdp.send("Browser.getWindowForTarget");
await cdp.send("Browser.setWindowBounds", { windowId, bounds: { windowState: "normal", left: 0, top: 0, width: W + 16, height: H + 120 } }); await sleep(600);
let m = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight, ow: outerWidth, oh: outerHeight, sx: screenX, sy: screenY }));
await cdp.send("Browser.setWindowBounds", { windowId, bounds: { left: 0, top: 0, width: W + (m.ow - m.iw), height: H + (m.oh - m.ih) } }); await sleep(600);
m = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight, ow: outerWidth, oh: outerHeight, sx: screenX, sy: screenY }));
const rect = { x: m.sx + Math.round((m.ow - m.iw) / 2), y: m.sy + (m.oh - m.ih), w: m.iw & ~1, h: m.ih & ~1 };
console.log("viewport rect", JSON.stringify(rect));
const t0 = 0.0;   // ▶ 재생은 ?t 와 무관하게 0 s 부터 시작(실측) — 클릭 순간이 대시보드 t 0
await page.goto(`${base}/#/status?m=M1&t=${t0}`, { waitUntil: "networkidle" }); await sleep(2000);
await page.evaluate(() => document.querySelector(".st-gauges")?.scrollIntoView({ block: "center" })); await sleep(500);
await page.bringToFront();
const out = join(videoDir, "08_dashboard_sync.mp4");
const p = spawn("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30", "-offset_x", String(rect.x), "-offset_y", String(rect.y), "-video_size", `${rect.w}x${rect.h}`, "-i", "desktop",
  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out], { stdio: ["pipe", "inherit", "inherit"] });
const t_rec_start_ms = Date.now(); await sleep(2000);
const t_play_ms = Date.now();
await page.locator(".sv2-top button").first()   /* 단순 보기 1b: 재생 버튼은 상태 띠 첫 버튼(아이콘만) */.click();
await sleep(62000);
const t_close_ms = await new Promise((res) => { p.on("exit", () => res(Date.now())); p.stdin.write("q"); p.stdin.end(); });
writeFileSync(join(videoDir, "08_dashboard_sync.json"), JSON.stringify({ dash_t0_s: t0, t_rec_start_ms, t_play_ms, t_close_ms, play_offset_s: (t_play_ms - t_rec_start_ms) / 1000, note: "ffmpeg gdigrab 시작 벽시계 → 재생 클릭까지의 초가 영상에서 대시보드 t0 가 되는 위치 (ffmpeg 기동 지연 ≈0.3 s 미보정)" }, null, 1));
await browser.close(); console.log("sync rec done", out);
