# README_dataset.md — 권상 모터 전기적 결함 시뮬레이션 데이터셋 (v2.0)

## 1. 한 줄 요약 (한계 먼저)
이 데이터셋은 **해석식으로 주입한 결함 시그니처의 재생산**이다. 속도/토크 채널은 Isaac Sim PhysX 강체 + 토크 제어 루프로 생성했고, 전류 채널은 동일 슬립을 공유하는 해석 생성기가 만들었다. **이 데이터로 학습한 모델의 분류 성능은 "주입 로직을 재확인"한 것이지 실기 진단 성능의 증명이 아니다.** 진단 임계값 튜닝·성능 주장에 사용하지 말 것.

## 2. 위치·구성
- `sim/output/dataset_v03/` — 런 76개 (v02는 PhysX θ float32 누적 오차로 무효·보관, `docs/e6_batch_report.md`) (`*.npz` + `*.json`) + `manifest.json` + 런별 로그
- 매트릭스: {정상 + brb, ecc_static, ecc_dynamic, itsc, bpfo, bpfi × 3 심각도} × {half(50 %), rated(100 %)} × 시드 2
- 런 길이 13 s @ 2560 Hz (기동 2 s → 정속 10 s → 정지 1 s), 33 280 샘플

## 3. 채널 (`*.npz`, float64)
| 채널 | 단위 | 생성 방식 |
|---|---|---|
| `t` | s | physics step 시각 |
| `omega`, `alpha` | rad/s, rad/s² | PhysX 조인트 각속도, 차분 가속도 (**진동 근사 채널** — 토크 리플이 직접 반영) |
| `slip` | — | (ω_sync − ω)/ω_sync 실시간 역산 |
| `theta` | rad | ω의 float64 적분(결함 위상 기준). PhysX 조인트 위치는 누적각 > 600 rad에서 float32 오차(0.8 %)로 미사용 |
| `T_motor`, `T_fault`, `T_load`, `T_fric`, `T_applied` | N·m | 토크 모델 / 결함 리플 / 부하 / 마찰 / 합(인가) |
| `T_measured` | N·m | PhysX 조인트 반력 |
| `Ia`, `Ib`, `Ic` | A | **해석 생성** 3상 전류(MCSA 채널), 동일 `slip`·fr 사용 |

메타 `*.json`: `generation`(정직성 라벨 §5), physics_hz/dt, seed, config 해시, `fault_params`, `current_params`, `torque_model`, `verify`(정속 rpm·슬립·t90), `timeline`.

## 4. 생성 방식
- 토크 제어 루프(E2): T = clip(T_rated·s/s_rated, ±449) + T_ripple(s, fr) − k·T_rated − b·ω → `apply_joint_effort`, PhysX 직접 스텝 1/2560 s. 드라이브 stiffness = damping = 0.
- 결함 토크 리플 / 전류 측대파: `docs/e5_injector_report.md` 표. 진폭 스케일은 전부 `미확인(추정)` — 심각도는 상대 스윕값.
- 편심 vs 턴간 단락: 부여 규칙이 기억 기반 문헌 인용(미확인) → **두 클래스 간 분류 성능 주장 금지**.

## 5. 정직성 라벨 (모든 JSON에 포함)
```json
"generation": {"speed_torque_channel": "physx_torque_control", "current_channel": "analytic",
               "fault_signature": "analytic_injection", "caveat": "주입 시그니처의 재생산 — FEM/실측 유도 데이터 아님"}
```

## 6. 재현 절차
```powershell
$P="<프로젝트>\sim"; $env:PYTHONIOENCODING="utf-8"
C:\ISSACS~1\python.bat $P\scripts\e0_scene_audit.py                       # E0
C:\ISSACS~1\python.bat $P\scripts\e_run.py --load rated --outdir $P\output\e2_check   # E2 수렴 검증
C:\ISSACS~1\python.bat $P\scripts\e5_selftest.py                          # E5 단위 테스트
C:\ISSACS~1\python.bat $P\scripts\e6_run_batch.py --dataset dataset_v03 --repeats 2   # E6 (≈45 분)
C:\ISSACS~1\python.bat $P\scripts\e7_verify.py --dataset dataset_v03      # E7
```
주의: Isaac Sim 인스턴스는 한 번에 하나만(GUI 실행 중 headless 기동 시 kvdb 잠금으로 정지).

## 7. 학습 투입 형식 제안
- 윈도우: 정속 구간(2~12 s)에서 1 s(2560 샘플) 슬라이딩, 50 % 겹침 → 런당 19 윈도우
- 입력: `alpha`(또는 `T_measured`) + `Ia` 2채널 스펙트럼(0~1 kHz) 또는 원파형; 라벨 = manifest `fault/severity/load`
- 분할: 시드 단위로 train/test 분리(같은 시드의 윈도우가 양쪽에 섞이지 않게)

## 8. 후속 연계
- **Paderborn 베어링 데이터 교차 검증**: 본 데이터의 bpfo/bpfi 포락선 스펙트럼 특징(주파수 정규화 f/fr)을 Paderborn 실측(진동·전류 동기 데이터셋)과 동일 전처리로 비교 → 합성 시그니처의 현실성 점검. 전류 채널 sideband dB 스케일을 실측 분포로 교정하는 것이 첫 과제.
- **Maxwell 연성 시 교체 지점**: `fault_injector.FaultInjector.torque_v2()` → FEM 전자기 토크 시계열 재생기(동일 시그니처), `current_generator.CurrentGenerator.sample()` → FEM 상전류 시계열. 러너·배치·검증 무변경.

## 9. 미확인 항목
`docs/params_sources.md` §6 참조 (모터 모델·기동토크비·베어링 형번·공진·결함 진폭·전류 η/pf·측대파 dB·회전 방향).
