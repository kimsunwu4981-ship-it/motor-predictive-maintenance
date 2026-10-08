# 베어링 결함 지표 정의 (2026-10-08 결정) — kurtosis + 고주파 대역 RMS 배율

사용자 결정(2026-10-08 밤, `docs/aihub_bearing_metric_comparison.md` 를 보고): 포락선 BPFO/BPFI 피크비를 판정에서 빼고
**주 지표 kurtosis**, **보조 지표 고주파 대역 RMS 정상 대비 배율**로 바꾼다. 고조파 보정 포락선은 폐기.
숫자는 전부 `config/thresholds.yaml bearing`, `config/thermal.yaml`(시뮬레이션 등가값), `config/motors/<id>.yaml bearing_hf_baseline` 에만 있다.

## 1. 정의

| 항목 | 정의 | 경계 (config) | 비고 |
|---|---|---|---|
| 주 지표 `bearing_kurtosis` | 가속도 시계열(평균 제거)의 kurtosis (Pearson, 정규분포 = 3.0) | 경고 3.5 / 위험 4.0, **모터 공통** | 박리·소손의 충격 성분에 민감 |
| 보조 지표 `bearing_hf_ratio` | 고주파 대역(1 kHz ~ 나이퀴스트, 4 kHz 샘플이면 1~2 kHz) 가속도 RMS ÷ **모터별 정상 기준선** `bearing_hf_baseline.rms_g` | 경고 1.5배 / 위험 2.5배 | 윤활 부족처럼 kurtosis 가 안 오르는 결함을 받친다 |
| 베어링 종합 등급 | 둘 중 나쁜 쪽 (`combine: worst`) | — | `engine/thresholds.py bearing_level`, status CSV `bearing` 열 |
| 결함 부위 추정 (표시만) | 포락선(500~1,600 Hz 대역통과 → Hilbert) BPFO/BPFI 피크비 중 큰 쪽이 `envelope_hint_min_ratio`(2.0) 이상이면 "외륜 쪽"/"내륜 쪽" | 판정에 쓰지 않음 | 베어링 번호를 아는 모터에서만 (`bearing_known`). `Judge.bearing_site_hint` |

히스테리시스(5 %)·지속 시간(3 s)은 다른 신호와 같다. 종합 상태·원인 신호 선정 규칙(초과 비율이 가장 큰 신호)도 그대로다.

## 2. 실측 근거 (AI Hub 238 전체 진동 데이터 37.7만 파일, 동일 모터 정상 대비)

| 모터 (AI Hub 결함 모의) | kurtosis 정상 → 결함 중앙값 | 고주파 RMS 배율 중앙값 (5 % 분위) | 속도 RMS 중앙값 | 새 규칙 판정 (결함 파일) |
|---|---|---|---|---|
| M2 L-SF-02 5.5 kW **외륜 소손** | 2.7 → 93.8 (5 % 55) | ×12.7 (×9.9) | 0.09 → 0.52 mm/s | 위험 100 % |
| M4 R-CAHU-01S 15 kW **내륜 소손** | 3.0 → 103.3 (5 % 73) | ×18.0 (×16.3) | 0.25 → 3.86 mm/s | 위험 100 % |
| M1 L-SF-04 2.2 kW **그리스 제거** | 2.9 → 2.9 | ×0.95 | 0.16 → 0.21 mm/s | 안전 100 % (어느 지표로도 안 보임) |
| M3 L-PAC-01 7.5 kW **그리스 제거** | 2.7 → 2.7 | ×1.70 (×1.65) | 0.19 → 0.44 mm/s | 경고 100 % (고주파 배율만) |

정상 파일이 새 규칙으로 경고 이상이 되는 비율(같은 모터 정상 중앙값 기준선, 모터 ID별 전체 정상):

| 모터 ID | 정상 파일 | 경고 | 위험 | kurtosis 95 % 분위 | 고주파 배율 95 % 분위 | 주된 원인 |
|---|---|---|---|---|---|---|
| M1 2.2 kW (8대) | 129,311 | 18 % | 11 % | 4.8 | 2.33 | 충격성 정상 파일(kurtosis) + 대별 고주파 편차 |
| M2 5.5 kW (4대) | 57,599 | 4 % | 0 % | 2.9 | 1.39 | 고주파 배율 |
| M3 7.5 kW (3대) | 4,335 | 4 % | 9 % | 5.0 | 1.11 | 충격성 정상 파일(kurtosis) |
| M4 15 kW (3대) | 35,771 | 1 % | 0 % | 3.2 | 1.21 | — |
| M5 22 kW (3대) | 32,791 | 1 % | 0 % | 3.3 | 1.04 | — |

축정렬불량(참고): M2 만 kurtosis 3.7·고주파 ×2.2 로 경고(76 %)~위험(24 %), M1 kurtosis 중앙값 3.5(95 % 13.7)로 절반이 경고 이상, M3·M5 는 변화 없음.

읽는 법: 소손은 두 지표 모두 경계의 10배 이상이라 확실하다. 그리스 제거는 kurtosis 로는 못 보고 고주파 배율로 한 대만 보인다(윤활 부족은 베어링 온도가 주 신호).
M1·M3 의 정상 오탐은 kurtosis 경계 3.5/4.0 이 공조기 정상 데이터의 충격성 파일(크레인 권상 모터와 운전 조건이 다름)에 걸리는 것으로,
경계 수치 조정은 별도 지시 사항이다(현장 정상 운전 실측 후). 숫자 출처: `tools/aihub/bearing_metric_compare.py`, `C:\vigent_data\aihub\L3\features.parquet`.

## 3. 시뮬레이션 등가값 매핑 (config/thermal.yaml)

엔진은 가속도 파형을 만들지 않으므로 결함별 등가값을 둔다(옛 "손실 배율 대체값" 폐기). 매핑 규칙과 근거는 `config/thermal.yaml` 주석에도 같은 내용이 있다.

| 결함 | 유형 | bearing_kurtosis | bearing_hf_ratio | 근거 |
|---|---|---|---|---|
| 없음 (`bearing_normal`) | — | 3.0 | 1.0 | 정규분포 kurtosis, 정상 기준선 대비 1.0 (실측 정상 중앙값 2.5~3.0) |
| `bearing_de_fault` DE 베어링 결함 | 소손형 | 50.0 | 9.0 | 실측 소손 2대 5 % 분위(55·73 / ×9.9·×16.3) 중 작은 값을 내림 — "소손 시 수십". 초기 박리 등가, 게이지 범위 안 |
| `bearing_nde_fault` NDE 베어링 결함 | 윤활 부족형 | 3.0 | 1.7 | 그리스 제거 실측: kurtosis 2.7~2.9 유지, 고주파 ×1.70(M3) — "kurtosis 3~4 유지, 고주파만 상승". 마찰열(손실 ×5)은 그대로 |
| `misalignment` 축 정렬 불량 | — | 3.7 | 2.2 | 변화가 있었던 M2 실측 중앙값 (M1·M3·M5 는 변화 없음) |
| `fan_failure`·`brake_drag`·`overload` | — | 3.0 | 1.0 | 베어링과 무관 → 정상값 |

결함이 겹치면 각 지표의 최댓값(`tools/run_fleet.py bearing_signals`). 무차원이라 열회로 스케일(M1~M4)과 무관하게 같다.

## 4. 모터별 정상 기준선 (config/motors/<id>.yaml bearing_hf_baseline)

| 모터 | rms_g | 출처 |
|---|---|---|
| M1 2.2 kW | 0.0027 | AI Hub 2.2 kW 정상 8대 중앙값의 중앙값 (대별 0.0012~0.0049) |
| M2 5.5 kW | 0.0012 | 5.5 kW 정상 4대 (0.0009~0.0014) |
| M3 7.5 kW | 0.0027 | 7.5 kW 정상 3대 (0.0014~0.0069, Validation 분만) |
| M4 15 kW | 0.0050 | 15 kW 정상 3대 (0.0048~0.0055) |
| M5 22 kW | 0.0108 | 22 kW 정상 3대 (0.0090~0.0130) |

`source: aihub_normal_median` — 같은 용량대 공조 모터의 값이지 이 모터의 실측이 아니다. 현장 정상 운전 실측이 생기면 `measured` 로 바꾼다.
대별 편차가 2~5배라 기준선은 반드시 모터마다 잡아야 한다(M1 의 정상 오탐 12 %가 이 편차에서 온다).

## 5. 바뀐 곳

- `config/thresholds.yaml bearing` (kurtosis·hf_ratio·combine·envelope_hint), `persistence_s` 에 두 지표.
- `config/thermal.yaml bearing_normal` + 결함별 `bearing_type`·`bearing_kurtosis`·`bearing_hf_ratio`.
- `config/motors/M1~M5.yaml bearing_hf_baseline`; `engine/motor_library.py` 가 읽고 검증.
- `engine/thresholds.py`: KINDS 에 `bearing_kurtosis`·`bearing_hf_ratio`(`bearing_index` 폐기), `bearing_level`, `Judge.bearing_site_hint`.
- `tools/run_fleet.py bearing_signals`, status CSV 열 `bearing_kurtosis, bearing_hf_ratio, bearing`; `tools/fleet_compare.py`(전후 비교표).
- `dashboard/tools/export_status_data.py`, 상태 보드(`data.ts`·`StatusBoard.tsx`·`TrendChart.tsx`·`source.ts`): 게이지 2개(kurtosis·고주파 배율, 종합 등급 표기), 기준표 2행, 용어 풀이 3항.
- `tools/aihub/extract_features.py`: `hf_ratio`·`hf_baseline_g`·`bearing_site_hint` 열 추가 (포락선 열은 추정 표시용으로 유지).
- 영상: HUD 에 베어링 지표 이름이 나오지 않으므로 재녹화 없음.
- 변경 전후 fleet 판정: `docs/bearing_metric_change_comparison.md` — 종합 등급 변경 0행, 베어링 결함 장면의 원인 신호만 진동/온도 → `bearing_kurtosis`.
