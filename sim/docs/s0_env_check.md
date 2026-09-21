# S0 — 환경 점검 보고

실행: `C:\ISSACS~1\python.bat sim\scripts\s0_env_check.py` (headless), 로그 `sim/output/s0_log.txt`, 결과 `sim/output/s0_report.json`

| 항목 | 값 | 판정 |
|---|---|---|
| Isaac Sim 버전 | **4.5.0** (`4.5.0-rc.36+release.19112`) | OK (규칙 1 충족) |
| 설치 경로 | `C:\issac sim` — 경로에 공백 → `python.bat` 내부 인용 오류. **8.3 경로 `C:\ISSACS~1\python.bat` 로 호출** | 우회 확정 |
| Python | 3.10.15 (kit 내장) | OK |
| `isaacsim.*` 임포트 | `isaacsim.SimulationApp`, `isaacsim.core.api.World`, `isaacsim.core.prims`, `isaacsim.core.utils.*` 정상 | OK (`omni.isaac.*` 미사용, 로그의 deprecated 경고는 Isaac 내부 확장 호환 레이어) |
| PhysX CPU 모드 | `/physics/cudaDevice = -1`, `enableGPUDynamics = False` | OK (규칙 3) |
| Broadphase / Solver | MBP / TGS | OK |
| physics_dt (시험) | 1/480 s | S4에서 분석 대역 확정 후 재설정 |
| Stage | upAxis = **Z**, metersPerUnit = **1.0** | OK (좌표 규약과 일치) |
| 10 step 실행 | 정상, 명시적 `simulation_app.close()` 종료 | OK |
| 기동 시간 | 15.9 s (앱 기동 포함) | — |

주의: `print()` 결과는 `close()` 시 유실될 수 있어 모든 스크립트는 결과를 **파일(JSON/npz)로 직접 기록**한다(S0에서 확인된 사항).

## 입력물(§2) 현황

| 항목 | 값 | 출처 |
|---|---|---|
| Blender 에셋 | `export/blender/hoist_motor_only.blend` (재질 완료, 모터 12파트) | 이전 단계 |
| Fusion STEP | `export/Hoist_Motor_22kW6P_v01.step` + `export/step_parts/*.step` | 이전 단계 |
| 좌표계 | 축선 +X, 상방 +Z, 원점 = DE 축단 끝면 중심, mm(Blender는 m) | Fusion 규약 승계 |
| 모터 사양 | 22 kW / 6P / AC 3φ 380 V 60 Hz / **정격 1170 rpm** | 도면 JW-01-HTO-00 SPEC·"ACTUAL SPEED 1170×…" 식 (MFR) |
| 동기속도 / 슬립 | 1200 rpm / s = 0.025 | CALC (120×60/6) |
| 명판 중량 | 285 kg | 도면 BOM #1 (MFR) |
| 정격 토크 | 179.6 N·m = 9550×22/1170 | CALC |
| 베어링 DE/NDE | **불일치**: Fusion 모델 = 6313/6311(추정), 기존 원장 `hoist_10t_jw.yaml` = 6309 플레이스홀더 | 둘 다 `미확인` — 사용자 결정 필요 |
| 결함 시그니처 표 | `권성모터 prototype/faults/fault_matrix.yaml`, `params/hoist_10t_jw.yaml` (pdm 섹션) — 단 BPFO 값이 문서 간 상이(73.89 Hz vs 59.21 Hz) | 기존 문서, 재계산 필요 |
| Isaac Sim | 4.5.0 / `C:\ISSACS~1` | 본 점검 |
| 결과 저장 경로 | `sim/output/` | §5 규약 |
