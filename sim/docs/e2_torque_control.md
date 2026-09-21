# E2 — 토크 제어 루프 전환 및 수렴 검증

구현: `sim/scripts/motor_torque_model.py` (`InductionMotorTorque`, `ConstantLoad`), 루프 러너 `sim/scripts/e_run.py`
검증 런: `sim/output/e2_check/baseline_rated_20260828.npz/.json`

## 루프 (매 physics step, dt = 1/2560 s)
```
ω ← 조인트 각속도 (PhysX)         s ← (ω_sync − ω)/ω_sync        fr ← ω/2π
T_motor ← clip(T_rated·s/s_rated, ±T_max)     # 선형 근사 + 토크 제한(직입 기동 근사)
T_ripple ← FaultInjector(t, s, fr, θ)           # 정상이면 0
T_load ← −k·T_rated (k = 0.5 / 1.0)             # 권상 정격 환산 일정 토크
T_fric ← −b·ω                                    # 기계 감쇠
apply_joint_effort(T_motor + T_ripple + T_load + T_fric);  PhysX simulate(dt)
I_abc(t) ← CurrentGenerator(t, s, fr)           # 전류 채널(해석), 동일 s·fr 공유
```
- PhysX 드라이브: stiffness = 0, **damping = 0**(속도 지령 비활성, 런타임 확인 kp = kd = 0). 기계 감쇠는 루프에서 −b·ω로 인가 — b = 0.015 N·m·s/rad `미확인(추정: 베어링·풍손 ≈ 정격출력 1 %)`.
- 기동 구간: 램프 기동 대신 **토크 제한 T_max = 449 N·m**(기동토크비 2.5, EST). Kloss 근사는 s_max(브레이크다운 슬립) 미확인이라 채택하지 않음 — 정격점 부근 선형은 IEC 정격점 정의만으로 성립(출처 최소).

## 수렴 검증 (정격부하 179.6 N·m)
| 항목 | 이론/기대 | 시뮬 | 판정 |
|---|---|---|---|
| 정속 rpm | 1170 (정격) / 모델 해석해 1169.69 (마찰 1.8 N·m 포함) | **1169.69** (정격 대비 −0.026 %) | ✅ ±1 % |
| 역산 슬립 | 0.025 (정격) / 0.02526 (모델) | **0.02526** | ✅ |
| 기동 t90 | J·0.9ω/(T_max − T_load) = 0.192 s | 0.192 s | ✅ |
| 토크 상한 | 449 N·m | `T_measured` 최대 449.0 | ✅ |
| 정속 표준편차 | — | 5e−13 rpm (결함 없음 → 완전 정속) | ✅ |

**게이트 판정: 통과.** 이후 생성 데이터부터 학습용으로 유효(규칙 5).
