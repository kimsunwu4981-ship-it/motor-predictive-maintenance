# firewall_rules.ps1 — 라이브 모드용 윈도우 방화벽 인바운드 규칙 (TCP 8765 WebSocket, 4173 대시보드). 관리자 PowerShell 에서 실행.
#   powershell -ExecutionPolicy Bypass -File tools\firewall_rules.ps1            # 추가 (개인·도메인 프로필만 — 공용 Wi-Fi 에서는 열지 않는다)
#   powershell -ExecutionPolicy Bypass -File tools\firewall_rules.ps1 -Remove    # 제거
#   powershell -ExecutionPolicy Bypass -File tools\firewall_rules.ps1 -Show      # 현재 규칙 확인
# 포트는 config/live.yaml (server.port, dashboard.port) 과 같아야 한다.
param([switch]$Remove, [switch]$Show, [int]$WsPort = 8765, [int]$DashPort = 4173)

$rules = @(
  @{ Name = "VIGENT Live WebSocket $WsPort"; Port = $WsPort },
  @{ Name = "VIGENT Dashboard $DashPort";   Port = $DashPort }
)
if ($Show) {
  foreach ($r in $rules) { netsh advfirewall firewall show rule name="$($r.Name)" }
  exit 0
}
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Host "관리자 PowerShell 에서 실행해야 한다 (시작 → PowerShell 우클릭 → 관리자 권한으로 실행)."; exit 1 }
foreach ($r in $rules) {
  if ($Remove) {
    netsh advfirewall firewall delete rule name="$($r.Name)" | Out-Null
    Write-Host "제거: $($r.Name)"
  } else {
    netsh advfirewall firewall delete rule name="$($r.Name)" 2>$null | Out-Null
    netsh advfirewall firewall add rule name="$($r.Name)" dir=in action=allow protocol=TCP localport=$($r.Port) profile=private,domain | Out-Null
    Write-Host "추가: $($r.Name) (TCP $($r.Port), 개인·도메인 프로필)"
  }
}
# 현재 네트워크가 '공용' 프로필이면 규칙이 적용되지 않는다 — 설정 → 네트워크 → 이더넷/Wi-Fi → 네트워크 프로필 '개인' 으로 바꾼다.
Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory | Format-Table -AutoSize
