# S2/S3 — 물리 속성 · 아티큘레이션 · 드라이브 파라미터

스크립트: `sim/scripts/s2_setup_physics.py` → `sim/usd/hoist_motor_physics_v01.usd`, `sim/output/s2_report.json`
CAD 물성 원본: `sim/config/cad_mass_properties.json` (Fusion 360 physicalProperties, 원점 = DE 축단 중심, 축선 X)

## 1. 강체 구성 (2강체 + Revolute 1조인트)

| 링크 | 구성 파트 | 질량 kg | 출처 | 질량중심 (m) | 관성 kg·m² (Ixx, Iyy, Izz) |
|---|---|---|---|---|---|
| `HM_Frame_Assy` (고정) | 프레임·엔드실드 DE/NDE·팬커버·단자함·아이볼트·베어링 DE/NDE | **192.05** | 명판 285 kg(MFR) − 회전부 CAD 질량 92.95 → 배분 (CAD 합계는 169.5 kg, 권선·절연물 생략분을 프레임에 귀속) | (0.425, 0, 0) | 근사값 — FixedJoint 고정이라 동역학 무관 |
| `HM_Rotor_Assy` (회전) | 샤프트·로터 코어·팬 | **92.95** | CAD 물성(강철/AISI1045/알루미늄), 형상 `미확인(추정: IEC 200L)` | (0.4254, 0, 0) | **Ixx = 0.4681** (샤프트 0.0180 + 로터 0.4443 + 팬 0.0057), Iyy = Izz = 1.850 (질량중심 기준 환산) |

- 회전부 축방향 관성 **J = 0.468 kg·m²** — 기동 과도응답 지배 파라미터. 참고: 22 kW 6P 유도전동기 로터 GD² 전형값 ≈ 1.3~2.0 kg·m² → J ≈ 0.33~0.5 kg·m² 범위와 부합(문헌, EST).
- 명판 285 kg 대비 CAD 총질량 262.4 kg(−7.9 %)의 차이는 고정부에 귀속(회전부는 CAD값 유지 — 관성 산출 일관성).

## 2. 충돌 프록시 (`purpose = guide`, 시각 메시에는 충돌 미지정)

| 프림 | 형상 | 치수 (m) | 위치 |
|---|---|---|---|
| `collision_frame_body` | Cylinder(X) | r 0.20 × h 0.78 | x 0.11~0.89 (엔드실드~팬커버) |
| `collision_frame_feet` | Cube | 0.40 × 0.395 × 0.20 | 풋/웹 (z −0.2~0) |
| `collision_tbox` | Cube | 0.25 × 0.20 × 0.15 | 단자함 |
| `collision_rotor_shaft` | Cylinder(X) | r 0.0275 × h 0.85 | 축 전장 |
| `collision_rotor_core` | Cylinder(X) | r 0.109 × h 0.26 | 로터 코어 |

프레임↔로터 충돌 쌍은 `FilteredPairsAPI`로 제외(베어링 지지 가정, 접촉 계산 불필요).

## 3. PhysicsScene

| 항목 | 값 | 근거 |
|---|---|---|
| GPU dynamics | **off** (`cudaDevice = −1`) | 규칙 3 |
| Solver / Broadphase | TGS / MBP | 안정성 |
| timeStepsPerSecond | **2560** | 분석 대역 1 kHz × 2.56 |
| 중력 | −Z 9.81 | Stage upAxis Z |
| Articulation solver iterations | 32 (position) | 고강성 드라이브 안정화 |

## 4. 조인트 · 드라이브 (S3)

| 항목 | 값 | 산정 근거 |
|---|---|---|
| Joint | `JT_Frame_Rotor_Rev` RevoluteJoint, body0 = Frame, body1 = Rotor | 2강체 최소 구성 |
| 축 / 원점 | **X** / (0.425, 0, 0) — 베어링 중심선(축선) 위 | 좌표 규약 |
| 프레임 고정 | `JT_World_Frame_Fixed` (FixedJoint → 월드) | 진동 전파 확장 전까지 고정 |
| Drive type | force, **velocity 모드** (stiffness = 0) | §4 S3 |
| damping | **7.33 N·m·s/rad** | 5 × T_rated/ω_rated = 5 × 179.6 / 122.52 — 20 % 속도 오차에서 정격 토크 발생하도록 (초기값, S4 검증으로 튜닝) |
| targetVelocity | **1170 rpm** (= 7020 deg/s) | 슬립 반영 정격 rpm (MFR), 동기 1200 rpm 아님 |
| maxForce | **449 N·m** | T_rated × 기동토크비 2.5 `미확인(추정: 크레인용 6P 2.0~2.8 문헌 범위)` |
| armature | 0 | 감속기/드럼 미포함(모터 단독) |

정격 토크 179.6 N·m = 9550 × 22 / 1170 (CALC; 22 kW·1170 rpm은 도면 MFR).
