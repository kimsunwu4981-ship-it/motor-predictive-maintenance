// serve.cjs — 의존성 없는 오프라인 정적 서버 (dist/ 를 그대로 서빙).
//
// 발표장에서 인터넷 없이 더블클릭으로 띄우기 위한 것이다. Node.js 만 있으면 된다.
//   node serve.cjs                 → http://localhost:4173/
//   node serve.cjs --open mechanical  → 브라우저를 #/mechanical 로 연다
// 영상은 Range 요청을 지원해야 <video> 탐색(seek)이 된다.
const http = require("http");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

const ROOT = path.join(__dirname, "dist");
const PORT = Number(process.env.PORT || 4173);
const args = process.argv.slice(2);
const openIdx = args.indexOf("--open");
const openRoute = openIdx >= 0 ? args[openIdx + 1] || "" : null;

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".mp4": "video/mp4", ".png": "image/png", ".svg": "image/svg+xml",
  ".woff2": "font/woff2", ".ico": "image/x-icon",
};

if (!fs.existsSync(path.join(ROOT, "index.html"))) {
  console.error("dist/index.html 이 없다. 먼저 `npm run build` 를 실행하라.");
  process.exit(1);
}

http.createServer((req, res) => {
  let url = decodeURIComponent(req.url.split("?")[0]);
  if (url === "/") url = "/index.html";
  const file = path.normalize(path.join(ROOT, url));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end("not found"); return;
  }
  const stat = fs.statSync(file);
  const type = MIME[path.extname(file).toLowerCase()] || "application/octet-stream";
  const range = req.headers.range;
  if (range) {
    const m = /bytes=(\d*)-(\d*)/.exec(range);
    const start = m[1] ? Number(m[1]) : 0;
    const end = m[2] ? Number(m[2]) : stat.size - 1;
    res.writeHead(206, {
      "Content-Type": type, "Accept-Ranges": "bytes",
      "Content-Range": `bytes ${start}-${end}/${stat.size}`, "Content-Length": end - start + 1,
    });
    fs.createReadStream(file, { start, end }).pipe(res);
  } else {
    res.writeHead(200, { "Content-Type": type, "Content-Length": stat.size, "Accept-Ranges": "bytes" });
    fs.createReadStream(file).pipe(res);
  }
}).listen(PORT, () => {
  const base = `http://localhost:${PORT}/`;
  console.log(`대시보드 서버: ${base}  (Ctrl+C 로 종료)`);
  if (openRoute !== null) {
    const target = openRoute ? `${base}#/${openRoute}` : base;
    exec(process.platform === "win32" ? `start "" "${target}"` : `xdg-open "${target}"`);
  }
});
