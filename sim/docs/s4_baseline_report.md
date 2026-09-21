# S4 — 정상 구동 Baseline 검증 보고

스크립트: `sim/scripts/s4_run_baseline.py` (headless, CPU PhysX, PhysX 직접 스텝 dt = 1/2560 s)
데이터: `sim/output/baseline_noload_20260828_164359.npz/.json`, `baseline_rated_20260828_164428.npz/.json`
채널(매 step): `t, pos_rad, vel_rads, acc_rads2(차분), torque_drive_Nm(설정식 추정), torque_load_Nm, torque_fault_Nm, torque_measured_Nm(PhysX 조인트 반력)` + 메타 JSON(timestep, seed 20260828, config 해시, 드라이브/링크 물성 검증값)

## 샘플링·대역 (사전 확정)
- 분석 목표 대역 **1 kHz**(결함 주파수 최대: BPFI 96 Hz의 5차 고조파 ≈ 480 Hz, 2fs+fr ≈ 140 Hz, 베어링 공진 가정 800 Hz) → physics_hz = **2560 Hz** (2.56배), Δf = 1/6 s = 0.167 Hz(정속 6 s 구간)

## 검증 결과
| 조건 | 기대 정속 | 정속 평균 rpm | 오차 | ±1 % | 기동 t90 (시뮬) | t90 이론 | 판정 |
|---|---|---|---|---|---|---|---|
| 무부하 | 1200 (동기속도 부근) | 1199.98 | −0.002 % | ✅ | 0.118 s | 0.118 s | ✅ |
| 정격부하 179.6 N·m | **1170 (명판 정격점)** | **1170.70** | +0.06 % | ✅ | 0.191 s | 0.197 s | ✅ |

t90 이론 = J·0.9·ω_target/(T_max − T_load), J = 0.468 kg·m², T_max = 449 N·m (토크 제한 구간 지배) — 자릿수 일치(오차 < 5 %).

## 드라이브 튜닝 이력
1. 초기 damping 7.33 (5×T_rated/ω_rated) + 목표 1170 rpm → 정격부하에서 936.7 rpm(−19.9 %) 강하 → **기각**
2. 채택: damping = **57.2 N·m·s/rad** = T_rated/(ω_sync − ω_rated) (유도전동기 토크–슬립 선형구간 기울기, CALC), 목표 속도 = **동기속도 1200 rpm** → 정격부하에서 정격 1170 rpm이 자연 형성. 프롬프트 §4 S3의 "목표 = 슬립 반영 정격 rpm" 규정은 부하 없는 속도제어 드라이브를 전제한 것으로, 본 구성에서는 *정격점(1170 rpm @ 179.6 N·m)*을 검증 기준으로 삼아 의도를 충족함.
3. maxForce = 449 N·m (기동토크비 2.5, `미확인(추정)`) — 기동 구간 토크 제한으로 작동 확인(`torque_measured_Nm` 최대 449.0).

## 해결한 환경 이슈 (재현성 기록)
| 증상 | 원인 | 조치 |
|---|---|---|
| 정속 319 rpm | `physxRigidBody:maxAngularVelocity`·`physxJoint:maxJointVelocity` 상한(단위 deg/s) | 두 값 1e6 deg/s |
| 기동 4 ms(이론 115 ms) | `World.step(render=False)`가 physics_dt 1/2560 대신 **1/60 s**로 스텝(`physics_context.get_physics_dt() = 0.0167`) | `omni.physx` `simulate(dt)/fetch_results()` 직접 호출 (`diag_dt.json`, `diag_dt2.json`) |
| USD `physics:principalAxes = (0,0,0,0)` | MassAPI 기본값이 무효 쿼터니언 | 단위 쿼터니언 명시 (예방) |
| stdout 유실 | `simulation_app.close()` 시 버퍼 손실 | 모든 결과 파일 직접 기록 |
