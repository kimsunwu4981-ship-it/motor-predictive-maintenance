# record_mode.ps1 — 모드별 전체 시나리오를 녹화하고, 장면 클립을 자르고, 동기를 검증한다.
#
# 녹화 방식은 docs/record_demo.md 와 SESSION_LOG 9장의 검증된 방식 그대로다:
#   데모가 ffmpeg 를 직접 띄운다 (gdigrab -i desktop + 창 좌표 crop). `-i title=` 은 쓰지 않는다.
#   시간축은 t_real(벽시계) 기준이며 영상시각 = t_real + video_offset_s.
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File tools\record_mode.ps1 -Mode mechanical
#   powershell -ExecutionPolicy Bypass -File tools\record_mode.ps1 -Mode electrical
# -NoTimecode : HUD 타임코드 없이(발표용). 동기 검증은 타임코드가 있어야 하므로 기본은 켠다.
param(
    [ValidateSet("mechanical", "electrical")]
    [string]$Mode,
    [double]$MaxS = 0,
    [switch]$NoTimecode,
    [switch]$SkipRecord      # 이미 녹화된 영상으로 검증·클립만 다시 한다
)
$ErrorActionPreference = "Stop"

$VIZ = Split-Path -Parent $PSScriptRoot
$ISAAC = "C:\ISSACS~1\python.bat"          # 경로에 공백이 있어 8.3 이름
$PY = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
if (-not (Test-Path $PY)) { $PY = $ISAAC }
$FFDIR = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory -Filter "Gyan.FFmpeg*" |
    ForEach-Object { Get-ChildItem $_.FullName -Directory } | ForEach-Object { Join-Path $_.FullName "bin" } |
    Where-Object { Test-Path (Join-Path $_ "ffmpeg.exe") } | Select-Object -First 1
if ($FFDIR) { $env:PATH = "$FFDIR;$env:PATH" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "ffmpeg 를 찾지 못했다" }

# 시나리오 길이 + 5 s 여유 (yaml 의 총 duration)
if ($MaxS -le 0) {
    $MaxS = & $PY -c "import sys; sys.path.insert(0, r'$VIZ'); from engine.scenario_player import ScenarioPlayer; print(ScenarioPlayer.for_mode('$Mode').total_duration + 5)"
    $MaxS = [double]$MaxS
}

# 상대 경로만 쓴다 — .bat 에 공백·한글 절대 경로를 넘기면 인자가 깨진다
$relVideo = "..\dashboard\public\media\$Mode\${Mode}_full.mp4"
$mediaDir = Join-Path $VIZ "..\dashboard\public\media\$Mode"
$logDir = Join-Path $VIZ "logs\$Mode"
New-Item -ItemType Directory -Force -Path $mediaDir, $logDir | Out-Null
$statusFile = Join-Path $VIZ "logs\demo_integrated_status.json"
if (Test-Path $statusFile) { [System.IO.File]::Delete($statusFile) }

if (-not $SkipRecord) {
Write-Host "[record] $Mode 녹화 시작 (max ${MaxS}s)"
$demoArgs = @("app\demo_integrated.py", "--gui", "--autoplay", "--mode", $Mode, "--max_s", $MaxS,
              "--record", $relVideo, "--log_subdir", $Mode)
if ($NoTimecode) { $demoArgs += "--no_timecode" }
# 창은 반드시 Normal 로 띄운다. 최소화된 창은 좌표가 화면 밖이라 빈 영상이 된다.
$p = Start-Process -FilePath $ISAAC -ArgumentList $demoArgs -WorkingDirectory $VIZ -PassThru -WindowStyle Normal `
    -RedirectStandardOutput (Join-Path $logDir "record_stdout.txt") -RedirectStandardError (Join-Path $logDir "record_stderr.txt")
$p.WaitForExit([int](($MaxS + 300) * 1000)) | Out-Null
if (-not $p.HasExited) { $p.Kill(); throw "데모가 제한 시간 안에 끝나지 않았다" }
$errFile = Join-Path $VIZ "logs\demo_integrated_error.txt"
if (Test-Path $errFile) { Write-Host "=== 데모 오류 ==="; Get-Content $errFile -Tail 12; throw "데모 오류" }
}

# ---- 결과 확인 ----
# PS 5.1 은 -Encoding 을 주지 않으면 UTF-8 을 ANSI 로 읽어 한글 경로가 깨진다(실측: JSON 파싱 오류)
$meta = Get-Content (Join-Path $logDir "recording_${Mode}_full.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$video = Join-Path $mediaDir "${Mode}_full.mp4"
$csv = $meta.log_csv
$last = Get-Content $csv -Tail 1
$tReal = [double]($last -split ",")[1]
$expected = $MaxS - 5
Write-Host ("[record] 영상 {0:N1} MB, {1:N1} s / 오프셋 {2} s / 로그 t_real 끝 {3} s (시나리오 {4} s)" -f `
    ((Get-Item $video).Length / 1MB), $meta.duration_s, $meta.video_offset_s, $tReal, $expected)
if ($tReal -lt $expected) { Write-Host "[record] ⚠ 로그가 시나리오 길이보다 짧다" }

# ---- 동기 검증용 프레임 (타임코드 영역 crop) : 영상 22 / 중간 / 끝-15 초 ----
if (-not $NoTimecode) {
    $sync = Join-Path $logDir "sync_check"
    New-Item -ItemType Directory -Force -Path $sync | Out-Null
    Get-ChildItem "$sync\*.png" -ErrorAction SilentlyContinue | ForEach-Object { [System.IO.File]::Delete($_.FullName) }
    $mid = [math]::Floor($expected / 2) + 2
    $end = [math]::Floor($expected) - 13
    foreach ($t in @(22, $mid, $end)) {
        $exp = [math]::Round($t - $meta.video_offset_s, 2)
        & ffmpeg -y -loglevel error -ss $t -i $video -frames:v 1 -vf "crop=170:36:1300:124" (Join-Path $sync ("tc_v{0:000}_expect{1}.png" -f $t, $exp))
    }
    Write-Host "[record] 동기 검증 프레임 → $sync  (파일명의 expect 값과 화면 타임코드를 비교)"
}

# ---- 장면 클립 ----
Write-Host "[record] 장면 클립 분할"
Set-Location $VIZ
$env:PYTHONIOENCODING = "utf-8"
& $PY tools\split_clips.py --mode $Mode --video $relVideo
Write-Host "[record] 완료"
