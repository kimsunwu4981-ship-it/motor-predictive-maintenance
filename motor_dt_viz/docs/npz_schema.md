# npz_schema.md — 전류 파형 데이터 소스 조사 (Phase 0)

## 1. 결론 먼저: **CLAUDE.md §1.3 의 "Maxwell 2D Transient 72개 케이스 npz" 는 이 저장소에 존재하지 않는다**

전체 탐색 결과(`디지털 트윈/` 이하 전체, `.venv` 제외):

| 확인 항목 | 결과 |
|---|---|
| Maxwell 결과 npz | **0개** |
| `ansys/maxwell/` 폴더 내용 | `brb_2d.py` **스크립트 1개뿐**, 결과·exports 폴더 없음 |
| `brb_2d.py` 헤더 주석 | `⚠️ 실행 조건: AEDT(Maxwell) 라이선스 필요 — ANSYS Student 에는 포함되지 않는다` / `본 스크립트는 라이선스 확보 후 '야간 배치'로 실행한다` → **미실행 상태** |
| `brb_2d.py` 출력 계획 형식 | `ansys/maxwell/exports/<case>_stator_current.csv` → **npz 아닌 CSV** |
| `brb_2d.py` 케이스 구성 | 정상 / 1바 / 2바 / 3바 / 인접2바 = **5 케이스 (BRB)**, 72 케이스 아님. **ITSC 케이스 없음** |
| I₂/I₁ = 0.006 / 0.104 / 0.269 출처 파일 | 저장소 내에서 **발견되지 않음** |
| `ansys/results/` 실제 산출물 | `modal_drum.json`, `static_drum.json`, PNG 2개 — **Mechanical(드럼 구조해석) 결과이며 전류 데이터 아님** |

→ **모듈 B 의 "1순위: Maxwell npz 파형" 경로는 현재 사용 불가.** 데이터 소스 결정을 확인받아야 한다(§4).

## 2. 실제로 존재하는 npz: Isaac Sim 결함 데이터셋 (해석식 주입)

경로: `sim/output/dataset_v03/` (그 외 `dataset_v01`, `dataset_v02` = 구버전·무효 보관)

| 항목 | 값 |
|---|---|
| 파일 수 | **76** (`*.npz` + 동명 `*.json` 메타) |
| 샘플링 | dt = 390.625 µs → **fs = 2,560 Hz**, 런당 33,280 샘플 (13 s) |
| 명명 규칙 | `baseline_{load}_{seed}.npz` / `fault_{mode}_{severity}_{load}_{seed}.npz` |
| 결함 모드 | `brb`, `ecc_static`, `ecc_dynamic`, `itsc`, `bpfo`, `bpfi` (각 3 심각도) |
| ITSC 심각도 | `t2` / `t5` / `t10` (단락 턴 비율 2 / 5 / 10 %) — **4-turn·12-turn 과 직접 대응하지 않음** |
| 부하 | `half`(50 %), `rated`(100 %) |

### npz 키 구조 (14채널, float64)

| 키 | 단위 | 내용 |
|---|---|---|
| `t` | s | 시각 |
| `omega`, `alpha` | rad/s, rad/s² | 조인트 각속도·각가속도 (PhysX 산출) |
| `slip` | — | 실시간 역산 슬립 |
| `theta` | rad | 회전 위상(ω 의 float64 적분) |
| `T_motor`, `T_fault`, `T_load`, `T_fric`, `T_applied` | N·m | 토크 성분 |
| `T_measured` | N·m | PhysX 조인트 반력 |
| **`Ia`, `Ib`, `Ic`** | **A** | **3상 전류 — 해석 생성(analytic)** |

### 메타 JSON 의 정직성 라벨 (그대로 인용)

```json
"generation": {
  "speed_torque_channel": "physx_torque_control",
  "current_channel": "analytic",
  "fault_signature": "analytic_injection",
  "caveat": "주입 시그니처의 재생산 — FEM/실측 유도 데이터 아님"
}
```

⚠️ **이 전류 채널은 FEM 이 아니라 해석식(기본파 + 결함별 측대파)으로 생성된 것이다.**
CLAUDE.md §1.3 이 기대하는 "Maxwell FEM 유도 파형"과는 성격이 다르므로, 그대로 쓸 경우
HUD·문서에 `해석식 생성(analytic)` 표기를 유지해야 한다.

### 현재 전류 파라미터 (`sim/config/motor.yaml`)

| 항목 | 값 | 출처 |
|---|---|---|
| 정격 전류 | **43.7 A** | CALC: 22 kW/(√3·380·η0.9·pf0.85) — η·pf 는 추정 |
| 기본파 | 60 Hz | 도면 |
| 5·7차 고조파 | −40 dB | 추정 |
| 노이즈 플로어 | −60 dB | 추정 |
| ITSC 측대파 | 3fs 증가 + fs±2fr + 고장상 진폭 +1/2.5/5 % | 문헌 기억 기반 인용 — **미확인** |

→ **I₂/I₁ 은 현재 데이터에 계산·저장되어 있지 않다.** 대칭좌표법 계산은 Phase 1 `engine/current_model.py` 에서 새로 구현해야 한다.
현 ITSC 생성 로직은 **상 불평형을 고장상 진폭 가산(+1/2.5/5 %)으로만** 표현하므로,
그대로 계산하면 I₂/I₁ 이 대략 0.003 / 0.008 / 0.017 수준에 그쳐 **목표값 0.104 / 0.269 와 자릿수가 다르다.**
목표값을 화면에 띄우려면 생성기의 불평형 모델을 I₂/I₁ 기준으로 재보정해야 한다(Phase 1 과제).

## 3. 2.2 kW 테스트 리그 vs 22 kW 크레인 모터

CLAUDE.md §1.1 은 **2.2 kW·4극·1,740 rpm·정격 4.7 A** 를 기준으로 하지만,
이 저장소의 3D 모델·물리 시뮬레이션·기존 npz 는 모두 **22 kW·6극·1,170 rpm·43.7 A**
(도면 JW-01-HTO-00, 정원크레인 10 t 천장크레인 권상 모터) 기준이다.
`ansys/maxwell/brb_2d.py` 의 `RATED` 딕셔너리도 22 kW·6극·1170 rpm 으로 작성되어 있다.

→ 어느 쪽을 MVP 기준으로 삼을지 확인 필요(§4).

## 4. 확인 요청 사항

1. **Maxwell npz 72 케이스**: 다른 PC·외장 드라이브 등 저장소 밖에 있는가? 있다면 경로를 알려달라.
   없다면 모듈 B 의 전류 소스를 무엇으로 할지 선택이 필요하다.
2. **I₂/I₁ 0.006 / 0.104 / 0.269**: 어느 해석·문헌에서 나온 값인가? (발표 시 근거 질의 대비)
3. **모터 기준**: 2.2 kW 테스트 리그 / 22 kW 크레인 모터 중 어느 쪽인가?
