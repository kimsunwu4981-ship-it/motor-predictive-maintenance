// layout_a_shots.mjs — 레이아웃 A(실시간 전기 상태 보드) 스크린샷 (Playwright + 설치된 Edge, PowerShell 에서 실행). Isaac 이 --live 로 떠 있어야 한다.
//   node tools/layout_a_shots.mjs <out_dir> [base_url] [ws_url]
// 1920×1080 / 1366×768 × (정상·4턴·12턴) 6장 + 근거 서랍 1장 + 스트림 끊김 표시 1장(+ 임계값 탭). 장면 전환은 Isaac 의 기존 play_scenario 명령(8765)으로.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");
const [outDir = "../docs/dashboard_layout_a/img", base = "http://127.0.0.1:4173", wsUrl = "ws://127.0.0.1:8765"] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", "--window-size=1944,1172"] });

// Isaac 에 장면 점프 명령 (대시보드와 같은 경로). hello 의 scenes 에서 id → n
let scenes = null;
function wsCmd(name, args) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(wsUrl); const id = "shots-" + Date.now();
    const to = setTimeout(() => { ws.close(); rej(new Error("ack timeout")); }, 8000);
    ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.type === "hello") { scenes = m.scenes ?? scenes; ws.send(JSON.stringify({ type: "command", id, name, args })); } else if (m.type === "ack" && m.id === id) { clearTimeout(to); ws.close(); res(m); } };
    ws.onerror = () => { clearTimeout(to); rej(new Error("ws error")); };
  });
}
async function gotoScene(id) {
  if (!scenes) await wsCmd("stop_scenario", {});
  const n = scenes?.find((s) => s.id === id)?.n;
  if (!n) throw new Error(`scene ${id} not in hello.scenes: ${JSON.stringify(scenes?.map((s) => s.id))}`);
  const ack = await wsCmd("play_scenario", { scene: n });
  console.log("play_scenario", id, n, ack.ok ? "ok" : ack.reason);
}
async function shot(w, h, hash, name, pre, settle = 2500) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: "ko-KR" });
  const page = await ctx.newPage();
  await page.goto(`${base}/#/${hash}&r=${Date.now()}`, { waitUntil: "networkidle" }); await sleep(settle);
  if (pre) await pre(page);
  await page.screenshot({ path: join(outDir, `${name}.png`) }); console.log("shot", name, `${w}x${h}`);
  const txt = await page.evaluate(() => ({ status: document.querySelector(".sv2-status")?.textContent, cause: document.querySelector(".sv2-cause")?.textContent, big: [...document.querySelectorAll(".tile-h .big")].map((b) => b.textContent), isaac: document.querySelector(".tile-isaac .tile-h .dim")?.textContent, scene: document.querySelector(".sv2-scene")?.textContent }));
  await ctx.close();
  return txt;
}
const log = {};
for (const [id, wait] of [["healthy", 8000], ["itsc_4turn", 8000], ["itsc_12turn", 8000]]) {
  for (const [w, h] of [[1920, 1080], [1366, 768]]) {
    await gotoScene(id); await sleep(wait);                    // 사진마다 장면 처음으로 (3 s 지속 규칙 + 버퍼; 장면이 자동 진행되므로)
    log[`${id}_${w}`] = await shot(w, h, "status", `${id}_${w}`, null, 6000);
  }
}
log.drawer = await shot(1920, 1080, "status?drawer=1", "drawer_evidence_1920", null, 6000);
log.thr = await shot(1920, 1080, "status?drawer=1&tab=thr", "drawer_thresholds_1920", null, 6000);
// 스트림 끊김 표시: 닿지 않는 주소로 열면 state·스트림 모두 '끊김 — 재연결 중' (Isaac 을 끄지 않고 재현)
log.lost = await shot(1920, 1080, "status?live=ws://127.0.0.2:9", "stream_lost_1920", null, 6000);   // 127.0.0.2: state·스트림(127.0.0.1 전용) 둘 다 닿지 않음
writeFileSync(join(outDir, "shots_log.json"), JSON.stringify(log, null, 1));
await browser.close(); console.log("done", JSON.stringify(log));
