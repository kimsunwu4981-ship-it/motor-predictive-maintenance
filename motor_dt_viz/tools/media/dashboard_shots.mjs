// dashboard_shots.mjs — 보고용 대시보드 사진 12장 + 워크스루 영상 + (08) 상태 보드 동기 녹화 (Playwright + 설치된 Edge, 1920×1080).
//   node tools/media/dashboard_shots.mjs <out_dashboard_dir> <out_video_dir> [base_url]      (dashboard/ 에서, 서버 `node serve.cjs` 4173 필요)
// 원칙: 페이지 코드 변경 없음. 숫자는 전부 대시보드가 읽는 JSON(엔진·LUT) 값. 네이티브 title 툴팁은 스크린샷에 안 찍히므로 같은 문장을 DOM 오버레이로 그린다(캡션에 원문).
// 브라우저: 설치된 Edge(channel msedge) — Playwright 번들 Chromium/ffmpeg 다운로드가 이 PC 에서 멈춰서(1.3 MB 에서 정지) recordVideo 대신 시스템 ffmpeg gdigrab 으로 창 영역을 녹화한다(헤드 모드, 창 (0,0)).
// 22 kW: 해설 화면(#/electrical, #/mechanical)은 이전 22 kW 녹화 영상을 재생하므로 찍지 않고 상태 보드 장면으로 대체한다(excluded 에 사유). 각 사진마다 "22 kW" 문구가 화면 안에 보이는지 기록한다.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");   // dashboard/ 의 node_modules (cwd 기준) — 스크립트는 motor_dt_viz/tools/media 에 있다

const [outDir, videoDir, base = "http://127.0.0.1:4173"] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true }); mkdirSync(videoDir, { recursive: true });
const W = 1920, H = 1080;
const caps = [];
const excluded = [
  { name: "04_elec_panel_4turn / 05_elec_panel_12turn (#/electrical)", reason: "해설 화면은 이전 22 kW 녹화 영상(public/media/integrated_autoplay.mp4)을 재생 — 22 kW 자산 사용 금지. 상태 보드 전기 모드 장면(04·05)으로 대체" },
  { name: "09_narration_mech_bearing / 10_narration_elec_itsc (#/mechanical, #/electrical)", reason: "같은 이유. 상태 보드 기계 모드(09)·추세 차트(10)로 대체" },
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function kw22Visible(page) {
  return page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n; const vh = window.innerHeight, vw = window.innerWidth;
    while ((n = walker.nextNode())) {
      if (!/22\s?kW/.test(n.nodeValue)) continue;
      const el = n.parentElement; if (!el) continue; const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw) return n.nodeValue.trim().slice(0, 120);
    }
    return null;
  });
}
async function overlayTitle(page, selector, label) {
  return page.evaluate(([sel, lab]) => {
    const el = document.querySelector(sel); if (!el) return null;
    const t = el.getAttribute("title") || ""; const r = el.getBoundingClientRect();
    const box = document.createElement("div"); box.id = "__tip";
    const tag = document.createElement("div"); tag.textContent = `툴팁(title) — ${lab}`; tag.style.cssText = "color:#ffb74d;font-weight:bold;margin-bottom:4px";
    const body = document.createElement("div"); body.textContent = t; box.append(tag, body);
    box.style.cssText = `position:fixed;left:${Math.min(Math.max(r.left, 8), 1400)}px;top:${Math.min(r.bottom + 8, 980)}px;max-width:500px;background:#1e1e22;color:#fff;border:1px solid #ffb74d;border-radius:6px;padding:8px 10px;font:13px/1.5 'Malgun Gothic',sans-serif;z-index:99999;white-space:pre-wrap;box-shadow:0 4px 14px rgba(0,0,0,.5)`;
    el.style.outline = "2px solid #ffb74d"; el.setAttribute("data-tipped", "1"); document.body.appendChild(box); return t;
  }, [selector, label]);
}
async function clearOverlay(page) { await page.evaluate(() => { document.getElementById("__tip")?.remove(); document.querySelectorAll("[data-tipped]").forEach((e) => { e.style.outline = ""; e.removeAttribute("data-tipped"); }); }); }
async function scrollTo(page, sel, block = "center") { await page.evaluate(([s, b]) => document.querySelector(s)?.scrollIntoView({ block: b }), [sel, block]); await sleep(400); }
async function shot(page, name, caption, extra = {}) {
  const p = join(outDir, `${name}.png`); await page.screenshot({ path: p, fullPage: false });
  const kw = await kw22Visible(page);
  caps.push({ file: `${name}.png`, caption, resolution: `${W}x${H}`, url: page.url().replace(base, ""), kw22_visible: kw, ...extra }); console.log("shot", name, kw ? "(22 kW 문구 보임)" : "");
}
async function clickChip(page, text) { await page.locator(".st-scenes .chip", { hasText: text }).first().click(); await sleep(1200); }

// 헤드 모드 창: 뷰포트(innerWidth×innerHeight)가 정확히 1920×1080 이 되도록 창 크기를 맞추고, 화면 좌표의 뷰포트 영역을 돌려준다 (gdigrab 용)
async function openWindowed(browser) {
  const ctx = await browser.newContext({ viewport: null, locale: "ko-KR", acceptDownloads: true });
  const page = await ctx.newPage();
  await page.goto(`${base}/#/status?m=M1&t=0`, { waitUntil: "networkidle" });
  const cdp = await ctx.newCDPSession(page);
  const { windowId } = await cdp.send("Browser.getWindowForTarget");
  await cdp.send("Browser.setWindowBounds", { windowId, bounds: { windowState: "normal", left: 0, top: 0, width: W + 16, height: H + 120 } }); await sleep(600);
  let m = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight, ow: outerWidth, oh: outerHeight, sx: screenX, sy: screenY }));
  await cdp.send("Browser.setWindowBounds", { windowId, bounds: { left: 0, top: 0, width: W + (m.ow - m.iw), height: H + (m.oh - m.ih) } }); await sleep(600);
  m = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight, ow: outerWidth, oh: outerHeight, sx: screenX, sy: screenY }));
  const rect = { x: m.sx + Math.round((m.ow - m.iw) / 2), y: m.sy + (m.oh - m.ih), w: m.iw & ~1, h: m.ih & ~1 };
  console.log("window", JSON.stringify(m), "viewport rect", JSON.stringify(rect));
  return { ctx, page, rect };
}
function startRec(path, rect) {
  const p = spawn("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30", "-offset_x", String(rect.x), "-offset_y", String(rect.y), "-video_size", `${rect.w}x${rect.h}`, "-i", "desktop",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", path], { stdio: ["pipe", "inherit", "inherit"] });
  return { p, t0: Date.now() };
}
async function stopRec(r) { return new Promise((res) => { r.p.on("exit", () => res(Date.now())); r.p.stdin.write("q"); r.p.stdin.end(); }); }

let browser;
try { browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", `--window-size=${W + 16},${H + 120}`] }); console.log("browser: msedge (headed)"); }
catch (e) { console.log("msedge 없음 → 번들 chromium", String(e).slice(0, 80)); browser = await chromium.launch({ headless: false }); }

// ---- 사진 12장 (헤드 창, 뷰포트 1920×1080)
const { ctx, page } = await openWindowed(browser);
const go = async (hash, ms = 2500) => { await page.goto(`${base}/#/${hash}`, { waitUntil: "networkidle" }); await sleep(ms); };

await go("status?m=M1&t=40");
await shot(page, "01_status_board_home", "상태 보드 첫 화면 — M1 카드·시나리오 칩·정직성 4줄 (전기 모드 40 s, 4턴 경고 구간)");
const connTip = await overlayTitle(page, ".st-spec span:nth-child(3) .st-src", "전원·결선 출처");
await shot(page, "02_motor_card_sources", "모터 상세 출처 아이콘 — 결선(Y) 항목의 출처 툴팁을 오버레이로 표시 (현장 확인 필요 표시)", { tooltip: connTip });
await clearOverlay(page);
await scrollTo(page, ".st-gauges");
await shot(page, "03_gauges_m1", "게이지 — 진동(ISO 10816-1 Class I)·전류/정격·I₂/I₁·온도, 4턴 경고 시각 40 s");
await clickChip(page, "과부하 위험"); await scrollTo(page, ".st-gauges");
await shot(page, "04_gauges_overload", "(대체) 상태 보드 전기 모드 과부하 장면(85 s) 게이지 — 전류/정격 상한 위험");
await clickChip(page, "12턴 위험"); await scrollTo(page, ".st-gauges");
await shot(page, "05_gauges_12turn", "(대체) 상태 보드 전기 모드 12턴 위험(60 s) 게이지 — I₂/I₁ 위험, R상 과전류");
await scrollTo(page, ".st-aref-p");
await shot(page, "06_analysis_ref_panel", "④ 해석 근거 비교 — 시뮬 | 해석 기준값 | 차이 % | 출처 배지 (12턴, 60 s)");
await page.getByRole("button", { name: /근거 보기/ }).click(); await sleep(800); await scrollTo(page, ".st-aref-trace", "start");
await shot(page, "07_evidence_drawer", "'근거 보기' 서랍 — 표시량 → 엔진 → 파일(sha) → 해석 단계 → 등급 + 한계");
await go("status?m=M1&t=40");
await page.getByRole("button", { name: "임계값 기준표" }).click(); await sleep(600); await scrollTo(page, ".tabs", "start");
await shot(page, "08_thresholds_tab", "임계값 기준표 탭 — 신호별 안전/경고/위험 경계와 근거(source·status)");
await go("status?m=M1&t=40");
await clickChip(page, "DE 베어링 경고"); await scrollTo(page, ".st-gauges");
await shot(page, "09_status_mech_bearing", "(대체) 상태 보드 기계 모드 DE 베어링 경고 장면(27.5 s) — 베어링 온도·진동 게이지");
await go("status?m=M1&t=40");
await page.locator(".chips:not(.st-scenes) .chip", { hasText: /I₂\/I₁|I2\/I1|불평형/ }).first().click().catch(() => {}); await sleep(800);
await scrollTo(page, ".st-trend, .trend, .st-gauges", "center");
await shot(page, "10_trend_i2i1", "(대체) 상태 보드 추세 차트 — I₂/I₁ 시계열과 임계선 (전기 모드 40 s)");
await go("status?m=M1&t=40"); await scrollTo(page, ".st-gauges");
const badgeTip = await overlayTitle(page, ".g-prov", "참고 · 임시 기준");
await shot(page, "11_badge_tooltip", "게이지 '참고 · 임시 기준' 배지 툴팁 — 실측 기준선 미확보(provisional) 문장을 오버레이로 표시", { tooltip: badgeTip });
await clearOverlay(page);
await go("status?m=M1&t=40"); await scrollTo(page, ".st-aref-p");
let dlName = "";
try {
  const btn = page.getByRole("button", { name: "비교 내보내기" });
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), btn.click({ timeout: 10000 })]);
  dlName = dl.suggestedFilename(); await dl.saveAs(join(outDir, dlName));
} catch (e) { console.log("download failed", String(e).slice(0, 160)); }
await page.evaluate((n) => { const b = document.createElement("div"); b.id = "__tip"; b.textContent = n ? `다운로드됨: ${n}` : "비교 내보내기 클릭"; b.style.cssText = "position:fixed;right:24px;bottom:24px;background:#1b5e20;color:#fff;padding:10px 14px;border-radius:8px;font:14px 'Malgun Gothic';z-index:99999"; document.body.appendChild(b); }, dlName);
await shot(page, "12_export_csv", `'비교 내보내기' 직후 — 다운로드 파일 ${dlName || "(다운로드 이벤트 없음)"} (V2 형식 CSV, 4턴 40 s)`, { download: dlName });
await clearOverlay(page);
await ctx.close();

// ---- 07 워크스루 (~60 s, gdigrab)
{
  const { ctx: c2, page: vp, rect } = await openWindowed(browser);
  await vp.goto(`${base}/#/status?m=M1&t=15`, { waitUntil: "networkidle" }); await sleep(1500);
  const rec = startRec(join(videoDir, "07_dashboard_walkthrough.mp4"), rect); await sleep(1500);
  await sleep(5000);
  await vp.locator(".st-scenes .chip", { hasText: "4턴 경계" }).first().click(); await sleep(7000);
  await vp.evaluate(() => document.querySelector(".st-gauges")?.scrollIntoView({ block: "center", behavior: "smooth" })); await sleep(6000);
  await vp.evaluate(() => document.querySelector(".st-aref-p")?.scrollIntoView({ block: "center", behavior: "smooth" })); await sleep(8000);
  await vp.getByRole("button", { name: /근거 보기/ }).click(); await sleep(8000);
  await vp.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await sleep(2000);
  await vp.locator(".st-scenes .chip", { hasText: "12턴 위험" }).first().click(); await sleep(6000);
  await vp.evaluate(() => document.querySelector(".st-aref-p")?.scrollIntoView({ block: "center", behavior: "smooth" })); await sleep(6000);
  await vp.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await sleep(4000);
  await stopRec(rec); await c2.close();
  console.log("walkthrough done");
}
// ---- 08 동기 녹화: 상태 보드 전기 모드 15 s 에서 ▶ 재생 → 62 s. 녹화 시작·재생 클릭 벽시계를 json 에 남겨 Isaac 녹화와 맞춘다.
{
  const t0 = 0.0;   // ▶ 재생은 ?t 와 무관하게 0 s 부터 시작(실측) — 클릭 순간이 대시보드 t 0
  const { ctx: c3, page: vp, rect } = await openWindowed(browser);
  await vp.goto(`${base}/#/status?m=M1&t=${t0}`, { waitUntil: "networkidle" }); await sleep(2000);
  await vp.evaluate(() => document.querySelector(".st-gauges")?.scrollIntoView({ block: "center" })); await sleep(500);
  const rec = startRec(join(videoDir, "08_dashboard_sync.mp4"), rect); await sleep(2000);
  const t_play_ms = Date.now();
  await vp.getByRole("button", { name: /▶ 재생/ }).click();
  await sleep(62000);
  const t_close_ms = await stopRec(rec); await c3.close();
  writeFileSync(join(videoDir, "08_dashboard_sync.json"), JSON.stringify({ dash_t0_s: t0, t_rec_start_ms: rec.t0, t_play_ms, t_close_ms, play_offset_s: (t_play_ms - rec.t0) / 1000, note: "ffmpeg gdigrab 시작 벽시계 → 재생 클릭까지의 초가 영상에서 대시보드 t0 가 되는 위치 (ffmpeg 기동 지연 ≈0.3 s 미보정)" }, null, 1));
  console.log("sync rec done");
}
writeFileSync(join(outDir, "captions.json"), JSON.stringify({ captions: caps, excluded, missing: [] }, null, 1));
await browser.close();
console.log("done", caps.length);
