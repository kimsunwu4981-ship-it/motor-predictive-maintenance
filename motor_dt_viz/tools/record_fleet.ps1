# record_fleet.ps1 — 모터 라이브러리(M1~M5)별로 기계·전기 시나리오를 녹화한다 (TASK_다중모터 P5 "5종 모터 애니메이션 재녹화").
#
# 데모를 --motor <id> 로 띄우면 열회로·전류 모델·진동 규격·HUD 문구가 그 모터로 바뀌고, 외형은 카메라 거리를 1/geometry_scale 로
# 늘려 프레임 비례 크기로 보인다 (원본 USD·물리 바디는 손대지 않는다). 녹화 방식은 record_mode.ps1 과 같다 (gdigrab, 창 좌표 crop).
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File tools\record_fleet.ps1                 # M1~M4 × mechanical,electrical (M5 는 기존 영상)
#   powershell -ExecutionPolicy Bypass -File tools\record_fleet.ps1 -Motors M1,M3 -Modes electrical
# 녹화 동안 화면을 비워야 한다 (다른 창이 앞에 오면 그 창이 찍힌다).
param(
    [string[]]$Motors = @("M1", "M2", "M3", "M4"),
    [string[]]$Modes = @("mechanical", "electrical"),
    [switch]$NoPublish
)
$ErrorActionPreference = "Stop"
# powershell -File 로 부르면 -Motors M3,M4 가 문자열 하나로 들어온다 → 쉼표로 나눈다 (실측: "config/motors/M3,M4.yaml 이 없다")
$Motors = @($Motors | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$Modes = @($Modes | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$VIZ = Split-Path -Parent $PSScriptRoot
$ROOT = Split-Path -Parent $VIZ
$ISAAC = "C:\ISSACS~1\python.bat"
$PY = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$FFDIR = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory -Filter "Gyan.FFmpeg*" |
    ForEach-Object { Get-ChildItem $_.FullName -Directory } | ForEach-Object { Join-Path $_.FullName "bin" } |
    Where-Object { Test-Path (Join-Path $_ "ffmpeg.exe") } | Select-Object -First 1
if ($FFDIR) { $env:PATH = "$FFDIR;$env:PATH" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw "ffmpeg 를 찾지 못했다" }
$modeKo = @{ mechanical = "기계"; electrical = "전기" }
$pub = Join-Path $ROOT "모터결함_애니메이션\4_모터별"
$results = @()
Set-Location $VIZ
foreach ($m in $Motors) {
    foreach ($mode in $Modes) {
        $maxS = & $PY -c "import sys; sys.path.insert(0, r'$VIZ'); from engine.scenario_player import ScenarioPlayer; print(ScenarioPlayer.for_mode('$mode').total_duration + 5)"
        $maxS = [double]$maxS
        $relVideo = "..\dashboard\public\media\fleet\${m}_${mode}.mp4"
        $logSub = "fleet_rec\$m\$mode"
        $logDir = Join-Path $VIZ "logs\$logSub"
        New-Item -ItemType Directory -Force -Path (Join-Path $VIZ "..\dashboard\public\media\fleet"), $logDir | Out-Null
        foreach ($f in @("logs\demo_integrated_status.json", "logs\demo_integrated_error.txt")) { $pf = Join-Path $VIZ $f; if (Test-Path $pf) { Remove-Item $pf -Force } }
        Write-Host ("[fleet] {0} {1} 녹화 시작 {2} (max {3}s)" -f $m, $mode, (Get-Date -Format HH:mm:ss), $maxS)
        $demoArgs = @("app\demo_integrated.py", "--gui", "--autoplay", "--mode", $mode, "--motor", $m, "--max_s", $maxS,
                      "--record", $relVideo, "--log_subdir", $logSub, "--no_timecode")
        $p = Start-Process -FilePath $ISAAC -ArgumentList $demoArgs -WorkingDirectory $VIZ -PassThru -WindowStyle Normal `
            -RedirectStandardOutput (Join-Path $logDir "record_stdout.txt") -RedirectStandardError (Join-Path $logDir "record_stderr.txt")
        $p.WaitForExit([int](($maxS + 300) * 1000)) | Out-Null
        if (-not $p.HasExited) { $p.Kill(); throw "$m $mode : 데모가 제한 시간 안에 끝나지 않았다" }
        $errFile = Join-Path $VIZ "logs\demo_integrated_error.txt"
        if (Test-Path $errFile) { Write-Host "=== 데모 오류 ==="; Get-Content $errFile -Tail 12; throw "$m $mode : 데모 오류" }
        $meta = Get-Content (Join-Path $logDir "recording_${m}_${mode}.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        $video = Join-Path $VIZ $relVideo
        $last = Get-Content $meta.log_csv -Tail 1
        $tReal = [double]($last -split ",")[1]
        $mb = [math]::Round((Get-Item $video).Length / 1MB, 1)
        Write-Host ("[fleet] {0} {1}: {2} MB, {3} s, 오프셋 {4} s, 로그 끝 {5} s" -f $m, $mode, $mb, $meta.duration_s, $meta.video_offset_s, $tReal)
        $results += [pscustomobject]@{ motor = $m; mode = $mode; MB = $mb; duration_s = $meta.duration_s; offset_s = $meta.video_offset_s; log_end_s = $tReal; video = $video; log_csv = $meta.log_csv }
        if (-not $NoPublish) {
            New-Item -ItemType Directory -Force -Path $pub | Out-Null
            Copy-Item $video (Join-Path $pub ("{0}_{1}_전체시나리오.mp4" -f $m, $modeKo[$mode])) -Force
        }
    }
}
$results | ConvertTo-Json | Out-File (Join-Path $VIZ "logs\fleet_rec\summary.json") -Encoding utf8
$results | Format-Table -AutoSize
Write-Host "[fleet] 완료"
