// dashboard_shots.mjs — 보고용 대시보드 사진 12장 + 워크스루 영상 + (08) 상태 보드 동기 녹화 (Playwright + 설치된 Edge, 1920×1080).
//   node tools/media/dashboard_shots.mjs <out_dashboard_dir> <out_video_dir> [base_url]      (dashboard/ 에서, PowerShell. 서버 `node serve.cjs` 4173 필요)
// 2026-10-26 (2차): 상태 보드가 "단순 보기"(상태·원인·조치) 기본으로 바뀐 뒤의 캡처. 원칙은 그대로 — 페이지 코드 변경 없음, 숫자는 전부 export JSON(엔진·LUT) 값,
//   네이티브 title 툴팁은 같은 문장을 DOM 오버레이로 그린다(캡션에 원문). 녹화는 시스템 ffmpeg gdigrab(헤드 창 (0,0)) — 녹화 중 다른 창을 앞으로 올리면 안 된다.
// 22 kW: 해설 화면(#/electrical, #/mechanical)은 이전 22 kW 녹화 영상을 재생하므로 찍지 않는다(excluded). 각 사진마다 "22 kW" 문구가 화면 안에 보이는지 기록한다.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");

const [outDir, videoDir, base = "http://127.0.0.1:4173"] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true }); mkdirSync(videoDir, { recursive: true });
const W = 1920, H = 1080;
const caps = [];
const excluded = [
  { name: "#/electrical · #/mechanical 해설 화면", reason: "이전 22 kW 녹화 영상(public/media/integrated_autoplay.mp4)을 재생 — 22 kW 자산 사용 금지. 상태 보드(단순 보기·전문가 보기)만 캡처" },
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
    box.style.cssText = `position:fixed;left:${Math.min(Math.max(r.left, 8), 1380)}px;top:${Math.min(r.bottom + 8, 960)}px;max-width:520px;background:#1e1e22;color:#fff;border:1px solid #ffb74d;border-radius:6px;padding:8px 10px;font:14px/1.5 'Malgun Gothic',sans-serif;z-index:99999;white-space:pre-wrap;box-shadow:0 4px 14px rgba(0,0,0,.5)`;
    el.style.outline = "2px solid #ffb74d"; el.setAttribute("data-tipped", "1"); document.body.appendChild(box); return t;
  }, [selector, label]);
}
async function clearOverlay(page) { await page.evaluate(() => { document.getElementById("__tip")?.remove(); document.querySelectorAll("[data-tipped]").forEach((e) => { e.style.outline = ""; e.removeAttribute("data-tipped"); }); }); }
async function shot(page, name, caption, extra = {}) {
  const p = join(outDir, `${name}.png`); await page.screenshot({ path: p, fullPage: false });
  const kw = await kw22Visible(page);
  caps.push({ file: `${name}.png`, caption, resolution: `${W}x${H}`, url: page.url().replace(base, ""), kw22_visible: kw, ...extra }); console.log("shot", name, kw ? "(22 kW 문구 보임)" : "");
}
async function clickChip(page, text) { await page.locator(".st-scenes .chip", { hasText: text }).first().click(); await sleep(1200); }

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

// ---- 사진 12장 (단순 보기 기본)
const { ctx, page } = await openWindowed(browser);
const go = async (hash, ms = 2500) => { await page.goto(`${base}/?r=${Date.now()}#/${hash}`, { waitUntil: "networkidle" }); await sleep(ms); };   // 쿼리를 바꿔 매번 새 문서로 — 해시만 바뀌면 보드가 ?drawer/?tab/?view 를 다시 읽지 않는다

await go("status?m=M1&t=40");
await shot(page, "01_simple_home_4turn", "단순 보기 첫 화면 — 상태 띠(경고 · 전류 불균형 0.073) + 그림 타일 4(열·결함 지도 · 전류 파형 · 전류 성분 · 추세) + 하단 띠(왜/무엇을/근거) (전기 40 s, 턴간 단락 4턴)");
const heroTip = await overlayTitle(page, ".sv2-cause abbr", "상태 띠 원인 신호");
await shot(page, "02_hero_term_tooltip", "상태 띠 원인 신호 '전류 불균형' 의 툴팁(정식 용어 역상 전류비 I₂/I₁ + 설명)을 오버레이로 표시", { tooltip: heroTip });
await clearOverlay(page);
const chipTip = await overlayTitle(page, ".sv2-cause", "임계 구간 · 지속 규칙");
await shot(page, "03_threshold_tooltip", "상태 띠 원인 값 툴팁 — 임계 구간(안전·경고·위험)과 \"3초 이상 지속될 때만 경보\" 각주를 오버레이로 표시", { tooltip: chipTip });
await clearOverlay(page);
await go("status?m=M1&t=60");
await shot(page, "04_simple_12turn_danger", "단순 보기 — 위험 · 12턴 (60 s): 전류 불균형 0.270, R상 파형 굵게(1.56×), I₂ 막대 빨강, 단락 코일 발광 점 커짐");
await go("status?m=M1&t=15");
await shot(page, "05_simple_healthy", "단순 보기 — 안전 · 정상 (15 s): 기준선, 전류 불균형 0.027");
await go("status?m=M1&t=40&drawer=1", 3000);
await shot(page, "06_evidence_drawer_table", "근거 서랍 ① 정직성 4줄 ② 해석 근거 비교 — 시뮬값 있는 행만(결함분·I₂/I_n·I_f·P_loop 채워짐, — 1행 접힘)");
await page.evaluate(() => { const b = document.querySelector(".sv-drawer .body"); if (b) b.scrollTop = b.scrollHeight; }); await sleep(600);
await shot(page, "07_evidence_drawer_trace", "근거 서랍 ③ 근거 사슬(표시량 → 엔진 → 파일 sha → 해석 단계 → 등급) ④ 한계");
await go("status?m=M1&t=40&tab=thr", 3000);
await shot(page, "08_thresholds_sheet", "임계값 기준표 시트 — 안전/경고/위험 경계 + 근거 + 쉬운 설명 열");
await go("status?m=M1&t=40&mode=mechanical", 3000);
await shot(page, "09_simple_mech_bearing", "단순 보기 기계 모드 — DE 베어링 열화 장면(40 s): 열·결함 지도(온도 색), 진동 막대, 베어링 충격성·고주파 막대, 추세");
await go("status?m=M1&t=40&view=expert", 3000);
await shot(page, "10_expert_view", "전문가 보기(기존 보드) — 카드·게이지·원인과 조치·해석 근거 비교(엔진 값 채움)·추세·기준표");
await go("status?m=M1&t=40");
const tagTip = await overlayTitle(page, ".sv-tag", "임시 태그");
await shot(page, "11_provisional_tag_tooltip", "상태 띠 '임시' 태그 툴팁(실측 기준선 확보 전까지 참고 기준)을 오버레이로 표시", { tooltip: tagTip });
await clearOverlay(page);
await go("status?m=M1&t=40&drawer=1", 3000);
let dlName = "";
try {
  const btn = page.locator(".sv-drawer button", { hasText: "비교 내보내기" }).first();
  const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), btn.click({ timeout: 10000 })]);
  dlName = dl.suggestedFilename(); await dl.saveAs(join(outDir, dlName));
} catch (e) { console.log("download failed", String(e).slice(0, 160)); }
await page.evaluate((n) => { const b = document.createElement("div"); b.id = "__tip"; b.textContent = n ? `다운로드됨: ${n}` : "비교 내보내기 클릭 (다운로드 이벤트 없음)"; b.style.cssText = "position:fixed;left:24px;bottom:24px;background:#1b5e20;color:#fff;padding:10px 14px;border-radius:8px;font:14px 'Malgun Gothic';z-index:99999"; document.body.appendChild(b); }, dlName);
await shot(page, "12_export_csv", `근거 서랍 '비교 내보내기' 직후 — 다운로드 파일 ${dlName || "(다운로드 이벤트 없음)"} (V2 형식 CSV, 4턴 40 s)`, { download: dlName });
await clearOverlay(page);
await ctx.close();

// ---- 07 워크스루 (~60 s, gdigrab): 첫 화면(정상) → 4턴 칩 → 12턴 칩 → 근거 서랍 → 닫기 → 임계값 시트 → 닫기 → 전문가 보기 → 단순  (PHOTOS_ONLY=1 이면 녹화 두 편 생략)
if (!process.env.PHOTOS_ONLY) {
  const { ctx: c2, page: vp, rect } = await openWindowed(browser);
  await vp.goto(`${base}/#/status?m=M1&t=15`, { waitUntil: "networkidle" }); await sleep(1500);
  const rec = startRec(join(videoDir, "07_dashboard_walkthrough.mp4"), rect); await sleep(1500);
  await sleep(5000);
  await vp.locator(".st-scenes .chip", { hasText: "4턴 경계" }).first().click(); await sleep(7000);
  await vp.locator(".st-scenes .chip", { hasText: "12턴 위험" }).first().click(); await sleep(6000);
  await vp.locator(".sv-honesty").click(); await sleep(7000);
  await vp.evaluate(() => { const b = document.querySelector(".sv-drawer .body"); if (b) b.scrollTo({ top: b.scrollHeight, behavior: "smooth" }); }); await sleep(6000);
  await vp.keyboard.press("Escape"); await sleep(2000);
  await vp.locator(".sv2-foot .sv-chip", { hasText: "임계값" }).click(); await sleep(6000);
  await vp.keyboard.press("Escape"); await sleep(2000);
  await vp.locator(".view-seg button", { hasText: "전문가" }).click(); await sleep(7000);
  await vp.locator(".view-seg button", { hasText: "단순" }).click(); await sleep(5000);
  await stopRec(rec); await c2.close();
  console.log("walkthrough done");
}
// ---- 08 동기 녹화: 단순 보기 전기 모드 ▶ 재생(0 s 부터) → 62 s. 녹화 시작·재생 클릭 벽시계를 json 에.
if (!process.env.PHOTOS_ONLY) {
  const t0 = 0.0;   // ▶ 재생은 ?t 와 무관하게 0 s 부터 시작(실측) — 클릭 순간이 대시보드 t 0
  const { ctx: c3, page: vp, rect } = await openWindowed(browser);
  await vp.goto(`${base}/#/status?m=M1&t=${t0}`, { waitUntil: "networkidle" }); await sleep(2000);
  await vp.bringToFront();
  const rec = startRec(join(videoDir, "08_dashboard_sync.mp4"), rect); await sleep(2000);
  const t_play_ms = Date.now();
  await vp.locator(".sv2-top button").first()   /* 단순 보기 1b: 재생 버튼은 상태 띠 첫 버튼(아이콘만) */.click();
  await sleep(62000);
  const t_close_ms = await stopRec(rec); await c3.close();
  writeFileSync(join(videoDir, "08_dashboard_sync.json"), JSON.stringify({ dash_t0_s: t0, t_rec_start_ms: rec.t0, t_play_ms, t_close_ms, play_offset_s: (t_play_ms - rec.t0) / 1000, note: "단순 보기. ffmpeg gdigrab 시작 벽시계 → 재생 클릭까지의 초가 영상에서 대시보드 t0 가 되는 위치 (ffmpeg 기동 지연 ≈0.3 s 미보정)" }, null, 1));
  console.log("sync rec done");
}
writeFileSync(join(outDir, "captions.json"), JSON.stringify({ captions: caps, excluded, missing: [] }, null, 1));
await browser.close();
console.log("done", caps.length);
