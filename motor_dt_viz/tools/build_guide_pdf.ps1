# build_guide_pdf.ps1 — docs/animation_guide.md 를 PDF 로 만든다 (Markdown → HTML → Edge 헤드리스 인쇄).
#
#   powershell -ExecutionPolicy Bypass -File tools\build_guide_pdf.ps1          # docs/animation_guide.pdf 갱신
#   powershell -ExecutionPolicy Bypass -File tools\build_guide_pdf.ps1 -Publish # + 프로젝트 산출물 폴더(모터결함_애니메이션)에 복사
#
# 필요: Blender 파이썬 + C:\Temp\pymods 의 markdown 패키지, Edge. 이미지는 docs/screenshots/ 상대 경로를 file:// 로 바꿔 넣는다.
# 문구를 고쳤으면 dashboard/tests 의 PDF 대조 테스트를 먼저 돌린다 — 숫자가 로그와 다르면 발표 사고다.
param([switch]$Publish)
$ErrorActionPreference = "Stop"
$VIZ = Split-Path -Parent $PSScriptRoot
$ROOT = Split-Path -Parent $VIZ
$PY = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$env:PYTHONPATH = "C:\Temp\pymods"; $env:PYTHONIOENCODING = "utf-8"
$work = "C:\Temp\guidepdf"; New-Item -ItemType Directory -Force -Path $work | Out-Null
$script = @'
import io, os, re, pathlib, sys, markdown
docs = sys.argv[1]
md = io.open(os.path.join(docs, "animation_guide.md"), encoding="utf-8").read()
md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: f"![{m.group(1)}]({pathlib.Path(os.path.join(docs, m.group(2))).resolve().as_uri()})", md)
md = re.sub(r"\n(\*\*(왜|멘트)\.\*\*)", r"\n\n\1", md)     # 보이는 것 / 왜 / 멘트 를 각각 문단으로
body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
css = """@page{size:A4;margin:15mm 14mm}body{font-family:"Malgun Gothic","맑은 고딕","Noto Sans KR",sans-serif;font-size:10.5pt;line-height:1.5;color:#1a1f26}
h1{font-size:20pt;margin:0 0 6pt;border-bottom:2px solid #0e7fa8;padding-bottom:4pt}h2{font-size:15pt;color:#0e7fa8;margin:16pt 0 6pt;page-break-before:always}
h3{font-size:12pt;margin:12pt 0 4pt;page-break-after:avoid}p{margin:3pt 0}
img{display:block;max-width:100%;max-height:88mm;width:auto;height:auto;border:1px solid #ccd;border-radius:4px;margin:4pt 0;page-break-inside:avoid}
table{border-collapse:collapse;width:100%;font-size:9.5pt;margin:6pt 0;page-break-inside:avoid}th,td{border:1px solid #c9d1da;padding:3pt 5pt;text-align:left;vertical-align:top}th{background:#eef3f7}
blockquote{border-left:4px solid #ffaa33;background:#fff8ec;margin:6pt 0;padding:6pt 10pt;page-break-inside:avoid}
code{font-family:Consolas,"D2Coding",monospace;font-size:9pt;background:#f0f3f7;padding:0 3px}pre{background:#f0f3f7;padding:8pt;font-size:9pt;white-space:pre-wrap;border-radius:4px}
hr{display:none}strong{color:#0b3d57}.cover{font-size:9pt;color:#667;margin-bottom:10pt}"""
import datetime
today = datetime.date.today().isoformat()
html = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>모터 결함 애니메이션 해설</title><style>{css}</style></head><body><div class="cover">VIGENT · 크레인 권상 모터 디지털 트윈 · {today} · 시뮬레이션 기반 추정값</div>{body}</body></html>'
html = html.replace("<h2>1. 색을 읽는 법</h2>", '<h2 style="page-break-before:auto">1. 색을 읽는 법</h2>', 1)
io.open(r"C:\Temp\guidepdf\guide.html", "w", encoding="utf-8").write(html); print("HTML OK")
'@
$script | & $PY - (Join-Path $VIZ "docs")
$pdfTmp = "$work\guide.pdf"; if (Test-Path $pdfTmp) { [System.IO.File]::Delete($pdfTmp) }
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$proc = Start-Process -FilePath $edge -ArgumentList @("--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=C:\Temp\dashshot_profile", "--no-pdf-header-footer", "--print-to-pdf=$pdfTmp", "--virtual-time-budget=8000", "file:///C:/Temp/guidepdf/guide.html") -PassThru -WindowStyle Hidden
$proc.WaitForExit(90000) | Out-Null; if (-not $proc.HasExited) { $proc.Kill() }
if (-not (Test-Path $pdfTmp)) { throw "PDF 생성 실패" }
$dst = Join-Path $VIZ "docs\animation_guide.pdf"
Copy-Item $pdfTmp $dst -Force
"PDF {0:N0} bytes → {1}" -f (Get-Item $dst).Length, $dst
if ($Publish) {
  $pub = Join-Path $ROOT "모터결함_애니메이션\애니메이션_해설.pdf"
  Copy-Item $pdfTmp $pub -Force
  "복사: $pub"
}
