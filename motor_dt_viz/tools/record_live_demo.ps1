# record_live_demo.ps1 — 라이브 데모 5단계 화면 녹화 (Isaac Sim 창 + 대시보드 브라우저 창을 한 화면에, 데스크톱 캡처).
#   1) Isaac: C:\ISSACS~1\python.bat app\demo_integrated.py --gui --mode integrated --live --motor M5 --low   (이미 떠 있어야 한다)
#   2) 이 스크립트: 브라우저(Edge)를 화면 오른쪽에 띄우고, ffmpeg 로 전체 화면을 녹화하면서 tools\live_demo_drive.py 로 5단계를 자동 전송한다.
#   powershell -ExecutionPolicy Bypass -File tools\record_live_demo.ps1 -Ws ws://127.0.0.1:8765 -Out "..\모터결함_애니메이션\10_라이브_양방향_데모_1920x1080.mp4"
# 화면을 비워야 한다(다른 창·알림이 함께 찍힌다). 커서도 찍힌다. 종료: drive 스크립트가 끝나면 ffmpeg 에 q 를 보낸다.
param(
  [string]$Ws = "ws://127.0.0.1:8765",
  [string]$Out = "..\모터결함_애니메이션\10_라이브_양방향_데모_1920x1080.mp4",
  [string]$Dash = "http://localhost:4173/#/status?live=ws://127.0.0.1:8765&ctl=1",
  [switch]$Fast,
  [int]$ScreenW = 2560, [int]$ScreenH = 1440
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$viz = Split-Path -Parent $here
$py = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Isaac 창을 왼쪽 위로, 브라우저를 오른쪽 절반으로
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
$isaac = [W]::FindWindow($null, "Isaac Sim Python 4.5.0")
if ($isaac -ne [IntPtr]::Zero) { [W]::MoveWindow($isaac, 0, 0, [int]($ScreenW/2), [int]($ScreenH*0.62), $true) | Out-Null }
else { Write-Host "Isaac Sim 창을 찾지 못했다 — --gui --live 로 먼저 실행" }
$profile = Join-Path $env:TEMP "edge-livedemo"
Start-Process -FilePath $edge -ArgumentList @("--new-window", "--user-data-dir=$profile", "--window-position=$([int]($ScreenW/2)),0", "--window-size=$([int]($ScreenW/2)),$ScreenH", "--app=$Dash")
Start-Sleep 6

$outPath = Join-Path $viz $Out
New-Item -ItemType Directory -Force (Split-Path -Parent $outPath) | Out-Null
$ff = Start-Process -FilePath ffmpeg -ArgumentList @("-y", "-f", "gdigrab", "-framerate", "30", "-video_size", "$($ScreenW)x$($ScreenH)", "-i", "desktop",
  "-vf", "scale=1920:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "`"$outPath`"") -PassThru -RedirectStandardInput "$env:TEMP\ff_in.txt" -NoNewWindow
Write-Host "녹화 시작 → $outPath"
Start-Sleep 3
$args = @("-X", "utf8", (Join-Path $here "live_demo_drive.py"), $Ws, "--out", (Join-Path $viz "docs\live_r3\demo_drive_log.json"))
if ($Fast) { $args += "--fast" }
& $py @args
Start-Sleep 3
# ffmpeg 정상 종료 (q) — moov atom 을 쓰게 한다
try { $ff.StandardInput.WriteLine("q") } catch { Stop-Process -Name ffmpeg -Force -ErrorAction SilentlyContinue }
Wait-Process -Id $ff.Id -Timeout 30 -ErrorAction SilentlyContinue
Write-Host "완료: $outPath"
