# README_simulation.md — 권상 모터 Isaac Sim 구동 시뮬레이션 재현 절차

## 1. 환경
- Isaac Sim **4.5.0** (`C:\issac sim` — 경로 공백 때문에 반드시 8.3 경로 **`C:\ISSACS~1\python.bat`** 로 호출)
- Python 3.10 (kit 내장), `isaacsim.*` 네임스페이스만 사용, PhysX **CPU** (`/physics/cudaDevice = -1`)
- Blender 5.2 (USD 내보내기), Fusion 360 (기하/물성 원본)
- 모든 스크립트 headless. `print`는 종료 시 유실되므로 결과는 파일(JSON/npz)로 기록됨.

## 2. 디렉터리
```
sim/
├── config/   motor.yaml(전 파라미터·출처), cad_mass_properties.json(Fusion 물성)
├── scripts/  s0_env_check.py, s1_import_check.py, s2_setup_physics.py(S2+S3),
│             s4_run_baseline.py(baseline·결함 공용 러너), s5_fault_injector.py,
│             s6_run_batch.py, s7_verify.py, diag_*.py(환경 이슈 진단)
├── usd/      hoist_motor_v01.usd(Blender 내보내기), hoist_motor_physics_v01.usd(물리·조인트 포함)
├── output/   s0~s2 리포트 JSON, baseline_*.npz/.json, dataset_v01/(배치 결과 + manifest.json)
└── docs/     s0~s7 보고서, params_sources.md, 본 문서
```

## 3. 실행 순서 (PowerShell)
```powershell
$P = "<프로젝트>\sim"; $env:PYTHONIOENCODING = "utf-8"
C:\ISSACS~1\python.bat $P\scripts\s0_env_check.py            # → output\s0_report.json
# (Blender) hoist_motor_only.blend 에서 USD_Export 컬렉션 내보내기 → usd\hoist_motor_v01.usd (build: 세션 스크립트 참조)
C:\ISSACS~1\python.bat $P\scripts\s1_import_check.py         # → output\s1_report.json
C:\ISSACS~1\python.bat $P\scripts\s2_setup_physics.py        # → usd\hoist_motor_physics_v01.usd, output\s2_report.json
C:\ISSACS~1\python.bat $P\scripts\s5_fault_injector.py --selftest   # → output\s5_selftest.json (ALL_OK True)
C:\ISSACS~1\python.bat $P\scripts\s4_run_baseline.py --load noload  # → output\baseline_noload_*.npz/.json
C:\ISSACS~1\python.bat $P\scripts\s4_run_baseline.py --load rated
C:\ISSACS~1\python.bat $P\scripts\s6_run_batch.py --dataset dataset_v01 --total_s 8   # 44 런, ~25 분
C:\ISSACS~1\python.bat $P\scripts\s7_verify.py --dataset dataset_v01                  # → docs\s7_verification_report.md
```
단일 결함 런: `s4_run_baseline.py --fault bpfo --severity severe --load rated --seed 7 --outdir <dir>`

## 4. 데이터 형식
- `*.npz`: `t, pos_rad, vel_rads, acc_rads2, torque_drive_Nm, torque_load_Nm, torque_fault_Nm, torque_measured_Nm` (float64, 2560 Hz)
- `*.json`: `generation`(`baseline_rigid_body` | **`analytic_injection`**), physics_hz/dt, seed, config 해시, 드라이브·링크 물성 검증값, 결함 파라미터(`fault_params`), 검증 결과(`verify`)
- `manifest.json`: 데이터셋 공통 메타 + 런별 항목(idx, fault, severity, load, seed, file, verify)

## 5. 물리 모델 요약
- 2강체(고정부 192.05 kg / 회전부 92.95 kg, Ixx 0.468 kg·m²) + Revolute(X) 1조인트, 고정부는 월드에 FixedJoint
- 드라이브: velocity 모드, damping 57.2 N·m·s/rad(토크–슬립 기울기), 목표 1200 rpm(동기), maxForce 449 N·m → 정격부하 179.6 N·m에서 1170 rpm
- 결함: `FaultInjector.torque(t, ω, θ)`가 매 step 추가 토크를 조인트 effort로 인가 (brb / ecc_static / ecc_dynamic / itsc / bpfo / bpfi / unbalance)

## 6. 후속 연계
- **AI 진단 모델 학습 입력**: `acc_rads2`(토크 리플 직접 반영) 또는 `torque_measured_Nm`; 라벨은 manifest의 `fault/severity/load`; 정속 구간(2~8 s)만 사용 권장. 반드시 `generation == analytic_injection` 을 데이터 카드에 표기(합성 시그니처 재생산, 진단 임계값 튜닝용 아님).
- **Maxwell(FEM) 연성 시 교체 지점**: `s5_fault_injector.FaultInjector.torque()` → FEM 토크 시계열 재생기(`torque(t)` 인터페이스 동일)로 교체. 나머지 파이프라인(러너·배치·검증) 무변경.
- **Isaac Sim 확장**: 진동 전파를 보려면 `JT_World_Frame_Fixed`를 마운트 강성(스프링-댐퍼 조인트)으로 교체하고 베어링을 개별 강체화.

## 7. 알려진 환경 이슈 (해결됨)
`World.step(render=False)`가 physics_dt를 1/60 s로 스텝 → PhysX 직접 스텝 사용. `maxAngularVelocity`/`maxJointVelocity` 단위 deg/s 상한 해제. `physics:principalAxes` 단위 쿼터니언 명시. 상세: `docs/s4_baseline_report.md`.
