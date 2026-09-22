# record_dashboard.ps1 — 기계 실시간 해설 대시보드를 실제 브라우저(Edge)에서 끝까지 자동 재생하며 화면 녹화한다.
#
#   .\tools\record_dashboard.ps1                      # 1920×1080, 7장면 전체(약 3분 6초), 결과는 프로젝트의 모터결함_애니메이션 폴더
#   .\tools\record_dashboard.ps1 -Width 1366 -Height 768 -Out C:\Temp\dash_1366.mp4
#
# 방법: Edge 를 앱 창(--app)으로 띄우고 클라이언트 영역이 정확히 Width×Height 가 되게 창 크기를 맞춘 뒤,
#       ffmpeg gdigrab 으로 그 화면 영역만 잘라 녹화한다 (`-i title=` 은 쓰지 않는다 — SESSION_LOG 9장).
#       재생은 주소의 autoplay=1&delay=N 으로 페이지가 스스로 시작한다 (키 입력을 보내지 않는다 — 다른 창에 들어갈 수 있다).
#       녹화 중 창은 항상 위(topmost)에 둔다. 녹화 길이는 -Seconds 로 끊는다 (ffmpeg -t).
#       Edge 앱 창은 제목줄(31 px)을 클라이언트 영역 안에 그리므로 그만큼 아래에서 잘라낸다.
# 헤드리스 브라우저로는 영상 프레임이 그려지지 않아 이 검증은 실제 창으로만 할 수 있다 (docs/sync_check.md).
param(
  [int]$Width = 1920,
  [int]$Height = 1080,
  [int]$Seconds = 192,
  [int]$Delay = 6,
  [int]$TitleBar = 31,
  [string]$Url = "http://localhost:4173/#/mechanical?t=0&autoplay=1",
  [string]$Out = "",
  [switch]$KeepBrowser
)
$ErrorActionPreference = "Stop"
$dash = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if ($Out -eq "") { $Out = Join-Path (Split-Path -Parent $dash) "모터결함_애니메이션\08_기계_실시간해설_대시보드_${Width}x${Height}.mp4" }
$outDir = Split-Path -Parent $Out
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }

# ---- ffmpeg ----
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  $cand = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cand) { $env:PATH += ";" + $cand.DirectoryName } else { throw "ffmpeg 를 찾지 못했다" }
}

# ---- 로컬 서버 (없으면 띄운다) ----
$listen = Get-NetTCPConnection -LocalPort 4173 -State Listen -ErrorAction SilentlyContinue
if (-not $listen) {
  $env:PATH += ";C:\Program Files\nodejs"
  Start-Process -FilePath "node" -ArgumentList "serve.cjs" -WorkingDirectory $dash -WindowStyle Hidden | Out-Null
  Start-Sleep -Seconds 2
}

# ---- Win32 ----
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win32R {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
}
"@

# ---- Edge 앱 창 ----
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) { $edge = "C:\Program Files\Microsoft\Edge\Application\msedge.exe" }
$profile = "C:\Temp\dashrec_profile"
$edgeArgs = @("--app=$Url&delay=$Delay", "--window-size=$Width,$($Height + 60)", "--window-position=0,0", "--user-data-dir=$profile",
              "--no-first-run", "--disable-features=TranslateUI,msEdgeSidebar", "--autoplay-policy=no-user-gesture-required")
Start-Process -FilePath $edge -ArgumentList $edgeArgs | Out-Null
$hwnd = [IntPtr]::Zero
for ($i = 0; $i -lt 60 -and $hwnd -eq [IntPtr]::Zero; $i++) {
  Start-Sleep -Milliseconds 500
  $cands = Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object { $_.CommandLine -like "*dashrec_profile*" }
  foreach ($c in $cands) {
    $pr = Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue
    if ($pr -and $pr.MainWindowHandle -ne 0) { $hwnd = $pr.MainWindowHandle; break }
  }
}
if ($hwnd -eq [IntPtr]::Zero) { throw "Edge 앱 창을 찾지 못했다" }
[Win32R]::ShowWindow($hwnd, 9) | Out-Null   # SW_RESTORE

# 클라이언트 영역을 정확히 Width×Height 로 맞춘다
$wr = New-Object Win32R+RECT; $cr = New-Object Win32R+RECT
[Win32R]::GetWindowRect($hwnd, [ref]$wr) | Out-Null; [Win32R]::GetClientRect($hwnd, [ref]$cr) | Out-Null
$dw = ($wr.R - $wr.L) - ($cr.R - $cr.L); $dh = ($wr.B - $wr.T) - ($cr.B - $cr.T)
[Win32R]::MoveWindow($hwnd, 0, 0, $Width + $dw, $Height + $TitleBar + $dh, $true) | Out-Null
[Win32R]::SetWindowPos($hwnd, [IntPtr](-1), 0, 0, 0, 0, 0x0003) | Out-Null   # HWND_TOPMOST, NOMOVE|NOSIZE
Start-Sleep -Milliseconds 800
[Win32R]::GetClientRect($hwnd, [ref]$cr) | Out-Null
$pt = New-Object Win32R+POINT; [Win32R]::ClientToScreen($hwnd, [ref]$pt) | Out-Null
$cw = $cr.R - $cr.L; $ch = ($cr.B - $cr.T) - $TitleBar; $oy = $pt.Y + $TitleBar
Write-Host ("녹화 영역: {0}x{1} at ({2},{3}) (제목줄 {4} px 제외)" -f $cw, $ch, $pt.X, $oy, $TitleBar)
if ($cw -ne $Width -or $ch -ne $Height) { Write-Warning "요청한 크기와 다르다 — 화면 해상도가 작거나 DPI 배율 때문일 수 있다" }

# ---- 녹화 시작 → Space 로 재생 ----
if (Test-Path $Out) { [System.IO.File]::Delete($Out) }
$ff = Start-Process -FilePath "ffmpeg" -PassThru -WindowStyle Hidden -ArgumentList @(
  "-y", "-loglevel", "error", "-f", "gdigrab", "-draw_mouse", "0", "-framerate", "30", "-offset_x", $pt.X, "-offset_y", $oy,
  "-video_size", "${cw}x${ch}", "-i", "desktop", "-t", $Seconds,
  "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "`"$Out`"")
[Win32R]::SetForegroundWindow($hwnd) | Out-Null
$t0 = Get-Date
Write-Host ("녹화 시작 {0:HH:mm:ss} — 페이지는 로드 후 {1}초 뒤에 스스로 재생, {2}초 녹화 (창을 가리지 마세요)" -f $t0, $Delay, $Seconds)
$ff.WaitForExit()
if (-not $KeepBrowser) {
  Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object { $_.CommandLine -like "*dashrec_profile*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
$info = & ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of default=nw=1 "$Out"
Write-Host "저장: $Out"
Write-Host ($info -join " | ")
Write-Host ("크기: {0:N1} MB" -f ((Get-Item $Out).Length / 1MB))
