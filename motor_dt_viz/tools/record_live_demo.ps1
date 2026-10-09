# record_live_demo.ps1 — 라이브 데모 5단계 화면 녹화 (Isaac Sim 창 + 대시보드 브라우저 창을 한 화면에, 데스크톱 캡처).
#   1) Isaac: C:\ISSACS~1\python.bat app\demo_integrated.py --gui --mode integrated --live --motor M5 --low   (이미 떠 있어야 한다)
#   2) 이 스크립트: 브라우저(Edge 앱 창)를 화면 오른쪽에 띄우고, ffmpeg 로 전체 화면을 녹화하면서 tools\live_demo_drive.py 로 5단계를 자동 전송한다.
#      모터 전환으로 새로 뜨는 Isaac 창도 왼쪽 위로 옮긴다(배경 감시 프로세스).
#   powershell -ExecutionPolicy Bypass -File tools\record_live_demo.ps1 -Ws ws://127.0.0.1:8765 -Out "..\모터결함_애니메이션\10_라이브_양방향_데모_1920x1080.mp4"
# 화면을 비워야 한다(다른 창·알림이 함께 찍힌다). 커서도 찍힌다. drive 스크립트가 끝나면 ffmpeg 에 q 를 보내 정상 종료한다.
param(
  [string]$Ws = "ws://127.0.0.1:8765",
  [string]$Out = "..\모터결함_애니메이션\10_라이브_양방향_데모_1920x1080.mp4",
  [string]$Dash = "http://localhost:4173/#/status?live=ws://127.0.0.1:8765&ctl=1",
  [switch]$Fast,
  [int]$ScreenW = 2560, [int]$ScreenH = 1440
)
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$viz = Split-Path -Parent $here
$py = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$isaacW = [int]($ScreenW / 2); $isaacH = [int]($ScreenH * 0.66)

$mover = @"
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class W { [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t); [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r); [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); public struct RECT { public int L, T, R, B; } }'
`$end = (Get-Date).AddSeconds(420)
while ((Get-Date) -lt `$end) {
  `$h = [IntPtr]::Zero; foreach (`$p in (Get-Process kit -ErrorAction SilentlyContinue)) { if (`$p.MainWindowHandle -ne 0) { `$h = `$p.MainWindowHandle; break } }
  if (`$h -ne [IntPtr]::Zero) { `$r = New-Object W+RECT; [W]::GetWindowRect(`$h, [ref]`$r) | Out-Null; if (`$r.L -ne 0 -or `$r.T -ne 0 -or (`$r.R - `$r.L) -ne $isaacW) { [W]::ShowWindow(`$h, 9) | Out-Null; [W]::MoveWindow(`$h, 0, 0, $isaacW, $isaacH, `$true) | Out-Null } }
  Start-Sleep -Milliseconds 1500
}
"@
$moverFile = Join-Path $env:TEMP "vigent_isaac_mover.ps1"
Set-Content -Path $moverFile -Value $mover -Encoding UTF8
$moverProc = Start-Process powershell -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $moverFile) -PassThru -WindowStyle Hidden

# 배경의 다른 창(VS Code·브라우저)이 찍히지 않도록 전부 최소화하고 Isaac 창만 되살린다. 끝나면 되돌린다.
$shell = New-Object -ComObject Shell.Application
$shell.MinimizeAll(); Start-Sleep 2
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class W2 { [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r); }'
$isaac = [IntPtr]::Zero; foreach ($p in (Get-Process kit -ErrorAction SilentlyContinue)) { if ($p.MainWindowHandle -ne 0) { $isaac = $p.MainWindowHandle; break } }
if ($isaac -ne [IntPtr]::Zero) { [W2]::ShowWindow($isaac, 9) | Out-Null; [W2]::MoveWindow($isaac, 0, 0, $isaacW, $isaacH, $true) | Out-Null } else { Write-Host "Isaac Sim 창 없음" }
Start-Sleep 1
$profile = Join-Path $env:TEMP "edge-livedemo"
Start-Process -FilePath $edge -ArgumentList @("--new-window", "--user-data-dir=$profile", "--window-position=$([int]($ScreenW/2)),0", "--window-size=$([int]($ScreenW/2)),$ScreenH", "--app=$Dash")
Start-Sleep 8

$outPath = Join-Path $viz $Out
New-Item -ItemType Directory -Force (Split-Path -Parent $outPath) | Out-Null
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "ffmpeg"
$psi.Arguments = "-y -f gdigrab -framerate 30 -video_size $($ScreenW)x$($ScreenH) -i desktop -vf scale=1920:-2 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p `"$outPath`""
$psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
$ff = [System.Diagnostics.Process]::Start($psi)
$null = $ff.StandardOutput.ReadToEndAsync(); $null = $ff.StandardError.ReadToEndAsync()
Write-Host "녹화 시작 → $outPath  ($(Get-Date -Format HH:mm:ss))"
Start-Sleep 3
$driveArgs = @("-X", "utf8", (Join-Path $here "live_demo_drive.py"), $Ws, "--out", (Join-Path $viz "docs\live_r3\demo_drive_log.json"))
if ($Fast) { $driveArgs += "--fast" }
& $py @driveArgs
Start-Sleep 4
try { $ff.StandardInput.Write("q"); $ff.StandardInput.Flush() } catch { }
if (-not $ff.WaitForExit(40000)) { Stop-Process -Id $ff.Id -Force }
try { Stop-Process -Id $moverProc.Id -Force } catch { }
try { $shell.UndoMinimizeALL() } catch { }
Write-Host "완료: $outPath  ($(Get-Date -Format HH:mm:ss))"
