// cdp_shot.mjs — 헤드리스 Edge 를 CDP 로 띄워 URL 을 열고 실제 시간으로 기다린 뒤 스크린샷 (라이브 모드 확인용 — WebSocket 수신이 실시간이라
// --virtual-time-budget 스크린샷으로는 볼 수 없다). Node 22 의 전역 WebSocket/fetch 만 쓴다 (의존성 없음).
//   node tools/cdp_shot.mjs "<url>" <wait_ms> <out.png> [width] [height] [port]
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, waitMs = "5000", out = "shot.png", width = "1600", height = "1200", port = "9333"] = process.argv.slice(2);
const EDGE = process.env.EDGE || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const profile = mkdtempSync(join(tmpdir(), "edge-cdp-"));
const edge = spawn(EDGE, [`--headless=new`, `--disable-gpu`, `--hide-scrollbars`, `--window-size=${width},${height}`, `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function target() {
  for (let i = 0; i < 50; i++) {
    try { const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const p = list.find((x) => x.type === "page"); if (p) return p; } catch { /* */ }
    await sleep(200);
  }
  throw new Error("CDP 타깃 없음");
}
try {
  const page = await target();
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let id = 0; const waiting = new Map();
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } };
  const call = (method, params = {}) => new Promise((res) => { const i = ++id; waiting.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  await call("Emulation.setDeviceMetricsOverride", { width: Number(width), height: Number(height), deviceScaleFactor: 1, mobile: false });
  await call("Page.enable");
  await call("Page.navigate", { url });
  await sleep(Number(waitMs));
  const shot = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(out, Buffer.from(shot.result.data, "base64"));
  console.log("saved", out);
  ws.close();
} finally {
  edge.kill();
}
