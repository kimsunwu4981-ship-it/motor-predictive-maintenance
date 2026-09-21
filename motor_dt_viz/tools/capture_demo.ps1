# capture_demo.ps1 — 통합 데모를 실행하며 시나리오 단계별 스크린샷을 남긴다.
#
# headless 뷰포트 캡처(capture_viewport_to_file)는 Isaac Sim 4.5 에서 동작하지 않아(실측),
# GUI 로 띄운 창을 화면 캡처한다. 단계 전환은 데모가 쓰는 status JSON 을 폴링해 동기화한다.
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File tools\capture_demo.ps1
#   powershell -ExecutionPolicy Bypass -File tools\capture_demo.ps1 -Prefix p5 -MaxS 200
# -Low  : 저사양 프리셋(--low)으로 데모를 띄운다
# -Mode : mechanical | electrical | integrated — 모드마다 시나리오 단계가 다르다
param(
    [string]$Prefix = "p4",
    [double]$MaxS = 175,
    [switch]$Low,
    [ValidateSet("mechanical", "electrical", "integrated")]
    [string]$Mode = "integrated"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing, System.Windows.Forms

$VIZ = Split-Path -Parent $PSScriptRoot
$OUT = Join-Path $VIZ "docs\screenshots"
$STATUS = Join-Path $VIZ "logs\demo_integrated_status.json"
$ISAAC = "C:\ISSACS~1\python.bat"          # 경로에 공백이 있어 8.3 이름을 쓴다
New-Item -ItemType Directory -Force -Path $OUT | Out-Null
if (Test-Path $STATUS) { Remove-Item $STATUS }

# 시나리오 단계 id → 파일 이름 (각 모드의 config/scenario_*.yaml steps 와 같은 순서)
$STEPS_BY_MODE = @{
    integrated = [ordered]@{
        normal = "01_normal"; bearing_fault = "02_bearing"; itsc_4turn = "03_itsc4"
        itsc_12turn = "04_itsc12"; conclusion = "05_conclusion"
    }
    mechanical = [ordered]@{
        normal = "01_normal"; bearing_fault = "02_bearing"; misalignment = "03_misalignment"
        fan_failure = "04_fan"; brake_drag = "05_brake"; overload = "06_overload"
        cooldown = "07_cooldown"
    }
    electrical = [ordered]@{
        healthy = "01_healthy"; itsc_4turn = "02_itsc4"; itsc_12turn = "03_itsc12"
        overload = "04_overload"; voltage_unbalance = "05_unbalance"
        single_phasing = "06_single_phasing"; no_load = "07_no_load"
    }
}
$STEPS = $STEPS_BY_MODE[$Mode]

# Isaac Sim 창 영역만 잘라 찍는다. 전체 화면을 찍으면 편집기·작업표시줄이 같이 들어간다.
if (-not ("Win32Rect" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public struct RECT { public int Left, Top, Right, Bottom; }
public class Win32Rect {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@
}

function Get-IsaacRect {
    # Isaac Sim 은 제목이 같은 작은 보조 창도 띄운다(실측 160x28). 가장 큰 창을 고른다.
    $best = $null; $bestArea = 0
    foreach ($p in Get-Process | Where-Object { $_.MainWindowTitle -like "Isaac Sim*" }) {
        $r = New-Object RECT
        if (-not [Win32Rect]::GetWindowRect($p.MainWindowHandle, [ref]$r)) { continue }
        $area = ($r.Right - $r.Left) * ($r.Bottom - $r.Top)
        if ($area -gt $bestArea) { $bestArea = $area; $best = $p }
    }
    if (-not $best -or $bestArea -lt 400 * 300) { return $null }
    [Win32Rect]::SetForegroundWindow($best.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 400
    $rect = New-Object RECT
    if (-not [Win32Rect]::GetWindowRect($best.MainWindowHandle, [ref]$rect)) { return $null }
    return $rect
}

function Save-Screen([string]$path) {
    # 창을 못 찾으면 찍지 않는다. 전체 화면으로 폴백하면 데모가 이미 끝난 뒤
    # 편집기 화면이 스크린샷으로 남는다.
    $rect = Get-IsaacRect
    if (-not $rect) {
        Write-Host "[capture] Isaac Sim 창을 찾지 못해 건너뛴다: $path"
        return $false
    }
    $x = $rect.Left; $y = $rect.Top
    $w = $rect.Right - $rect.Left; $h = $rect.Bottom - $rect.Top
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return $true
}

# 프로젝트 경로에 공백과 한글이 섞여 있어, .bat 에 절대 경로를 넘기면 인자가 깨진다.
# 작업 디렉터리를 motor_dt_viz 로 두고 상대 경로만 넘긴다.
Write-Host "[capture] 데모 기동 (autoplay, max ${MaxS}s)"
$stdout = Join-Path $VIZ "logs\capture_stdout.txt"
$stderr = Join-Path $VIZ "logs\capture_stderr.txt"
$demoArgs = @("app\demo_integrated.py", "--gui", "--autoplay", "--max_s", $MaxS, "--mode", $Mode)
if ($Low) { $demoArgs += "--low" }
$demo = Start-Process -FilePath $ISAAC -ArgumentList $demoArgs `
    -WorkingDirectory $VIZ -PassThru -WindowStyle Normal `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr

# 단계별로 '해당 단계에 들어간 뒤 중반쯤'에서 한 장씩 찍는다.
$done = @{}
$deadline = (Get-Date).AddSeconds($MaxS + 240)     # Isaac Sim 기동 시간 포함
while ((Get-Date) -lt $deadline -and $done.Count -lt $STEPS.Count) {
    Start-Sleep -Milliseconds 700
    if ($demo.HasExited -and -not (Test-Path $STATUS)) {
        Write-Host "[capture] 데모가 기동하지 못하고 종료했다 — logs\capture_stderr.txt 확인"
        break
    }
    if (-not (Test-Path $STATUS)) { continue }
    try { $s = Get-Content $STATUS -Raw | ConvertFrom-Json } catch { continue }
    $step = $s.step
    if (-not $step -or $done.ContainsKey($step) -or -not $STEPS.Contains($step)) { continue }
    # 단계 진입 직후는 색/온도가 아직 안 올라오므로 조금 기다렸다 찍는다
    Start-Sleep -Seconds 12
    $file = Join-Path $OUT ("{0}_{1}.png" -f $Prefix, $STEPS[$step])
    if (-not (Save-Screen $file)) { break }
    $done[$step] = $true
    Write-Host ("[capture] {0}  t={1}s  I2/I1={2}  brg={3}C({4})  wdg={5}C({6})  fps={7}" -f `
        $step, $s.t_real, $s.i2i1, $s.bearing_de, $s.stage_bearing, $s.winding, $s.stage_winding, $s.fps)
}

if (-not $demo.HasExited) { $demo.WaitForExit(120000) | Out-Null }
if (-not $demo.HasExited) { $demo.Kill() }
Write-Host ("[capture] 완료 — {0}/{1} 단계 캡처, 출력 {2}" -f $done.Count, $STEPS.Count, $OUT)
