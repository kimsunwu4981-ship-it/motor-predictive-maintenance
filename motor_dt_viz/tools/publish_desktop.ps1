# publish_desktop.ps1 — 녹화 영상을 바탕화면 `모터결함_애니메이션` 폴더로 정리해 복사하고 MD5 로 대조한다.
#
#   모터결함_애니메이션/
#   ├── 1_기계적결함/   01_기계_전체시나리오.mp4, 02_기계_….mp4 (장면 클립)
#   ├── 2_전기적결함/   01_전기_전체시나리오.mp4, 02_전기_….mp4
#   └── 3_통합/         07_통합_자동재생.mp4 (기존 통합 영상, 복사본)
#
# 복사만 한다. dashboard/public/media 의 원본은 그대로 둔다.
# 바탕화면 경로는 추측하지 않고 OS 에서 조회한다 (OneDrive 리디렉션 대응).
param([switch]$Verify)      # -Verify : 복사하지 않고 존재·MD5 만 다시 확인

$ErrorActionPreference = "Stop"
$VIZ = Split-Path -Parent $PSScriptRoot
$MEDIA = Join-Path $VIZ "..\dashboard\public\media"
$desk = [Environment]::GetFolderPath('Desktop')
$dst = Join-Path $desk "모터결함_애니메이션"

Write-Host "바탕화면 경로: $desk"
Write-Host ("OneDrive 동기화 경로 안: {0}" -f ($desk -like "*OneDrive*"))

$plan = @()   # (원본, 대상)
function Add-Plan([string]$src, [string]$dstPath) { $script:plan += [PSCustomObject]@{ Src = $src; Dst = $dstPath } }

$modes = @(
    @{ key = "mechanical"; ko = "기계"; dir = "1_기계적결함" },
    @{ key = "electrical"; ko = "전기"; dir = "2_전기적결함" }
)
foreach ($m in $modes) {
    $full = Join-Path $MEDIA "$($m.key)\$($m.key)_full.mp4"
    if (Test-Path $full) { Add-Plan $full (Join-Path $dst "$($m.dir)\01_$($m.ko)_전체시나리오.mp4") }
    $clips = Join-Path $MEDIA "$($m.key)\clips"
    if (Test-Path $clips) {
        Get-ChildItem $clips -Filter *.mp4 | ForEach-Object { Add-Plan $_.FullName (Join-Path $dst "$($m.dir)\$($_.Name)") }
    }
}
$integ = Join-Path $MEDIA "integrated_autoplay.mp4"
if (Test-Path $integ) { Add-Plan $integ (Join-Path $dst "3_통합\07_통합_자동재생.mp4") }

if (-not $Verify) {
    foreach ($e in $plan) {
        New-Item -ItemType Directory -Force -Path (Split-Path $e.Dst) | Out-Null
        Copy-Item $e.Src $e.Dst -Force
    }
}

Write-Host "`n=== $dst ==="
$bad = 0
foreach ($e in $plan) {
    $rel = $e.Dst.Substring($dst.Length + 1)
    if (-not (Test-Path $e.Dst)) { "  ✗ 없음  $rel"; $bad++; continue }
    $a = (Get-FileHash $e.Src -Algorithm MD5).Hash
    $b = (Get-FileHash $e.Dst -Algorithm MD5).Hash
    $ok = $a -eq $b
    if (-not $ok) { $bad++ }
    "  {0} {1,-46} {2,10:N0} bytes  MD5 {3}" -f $(if ($ok) { "✓" } else { "✗" }), $rel, (Get-Item $e.Dst).Length, $b.Substring(0, 8)
}
Write-Host ("`n{0} 개 파일, 불일치 {1} 개" -f $plan.Count, $bad)
if ($bad -gt 0) { exit 1 }
