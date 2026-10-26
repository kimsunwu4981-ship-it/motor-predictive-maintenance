// simple_view_shots.mjs — 상태 보드 단순 보기 전/후 스크린샷 (Playwright + 설치된 Edge, PowerShell 에서 실행).
//   node tools/simple_view_shots.mjs <before|after> <out_dir> [base_url]
// before: 현재 서버가 서빙하는 화면을 ?view=expert 없이 그대로(구 빌드면 전문가 화면 = 기존 보드). after: 단순 보기(기본)·전문가·발표·서랍·라이트·1366×768.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
const { chromium } = createRequire(join(process.cwd(), "package.json"))("playwright");
const [phase = "after", outDir = "../docs/dashboard_simple_view/img", base = "http://127.0.0.1:4173"] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ channel: "msedge", headless: false, args: ["--window-position=0,0", "--window-size=1944,1172"] });

async function shot(w, h, hash, name, pre) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: "ko-KR" });
  const page = await ctx.newPage();
  await page.goto(`${base}/#/${hash}`, { waitUntil: "networkidle" }); await sleep(2200);
  if (pre) await pre(page);
  await page.screenshot({ path: join(outDir, `${name}.png`) }); console.log("shot", name, `${w}x${h}`);
  await ctx.close();
}
const light = async (p) => { await p.evaluate(() => document.documentElement.setAttribute("data-theme", "light")); await sleep(500); };
if (phase === "before") {
  await shot(1920, 1080, "status?m=M1&t=40", "before_1920_dark");
  await shot(1366, 768, "status?m=M1&t=40", "before_1366_dark");
  await shot(1920, 1080, "status?m=M1&t=40", "before_1920_light", light);
} else {
  await shot(1920, 1080, "status?m=M1&t=40", "after_1920_dark");
  await shot(1366, 768, "status?m=M1&t=40", "after_1366_dark");
  await shot(1920, 1080, "status?m=M1&t=40", "after_1920_light", light);
  await shot(1920, 1080, "status?m=M1&t=60", "after_1920_12turn_danger");
  await shot(1920, 1080, "status?m=M1&t=15", "after_1920_healthy");
  await shot(1920, 1080, "status?m=M1&t=40&drawer=1", "after_1920_drawer");
  await shot(1920, 1080, "status?m=M1&t=40", "after_1920_present", async (p) => { await p.keyboard.press("f"); await sleep(600); });
  await shot(1920, 1080, "status?m=M1&t=40&view=expert", "after_1920_expert");
  await shot(1920, 1080, "status?m=M1&t=40&tab=thr", "after_1920_thresholds");
  await shot(1920, 1080, "status?m=M1&t=27.5&mode=mechanical", "after_1920_mech_bearing");
}
await browser.close(); console.log("done");
