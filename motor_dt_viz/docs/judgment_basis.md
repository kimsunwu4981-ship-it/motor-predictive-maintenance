# 판정 근거 노트 — 전기(전류) 신호 (TASK A D4/D6, 2026-10-17)

이 문서는 **판정 임계값과 판정 코드를 바꾸지 않는다.** 전류 결함 신호가 어디서 왔고(근거 등급), 임계값과 어떻게 만나며,
바꿔야 할 것이 보이면 "제안"으로만 적는다 (TASK A 승인 범위: `config/electrical.yaml` 구조와 결함 신호 생성 코드만).

## 1. 전류 결함 신호의 근거 (method: lut)

| 항목 | 값 | 출처 |
|---|---|---|
| 방식 | `config/electrical.yaml` `method: lut` (되돌리기 `legacy`) | D2 |
| LUT | `data/electrical/M1_mccm_lut_v1.json` (160점: 턴 비율 8 × R_f 4 × 부하 5), sha256 `2383158…` | `tools/electrical/import_lut.py` ← 권상모터_3D모델링 `maxwell/results/mccm_lut.json` |
| 근거 등급 | **등가회로(RMxprt v2 + MCCM 다중결합 회로)** · status `provisional` · `fem_verified: false` | provenance |
| 모터 | M1 전용. 상당 턴수 192, I_n 4.73 A (카탈로그 HLP-2.2/4) | `transfer_to_other_motors: false` → 다른 모터는 legacy |
| 고유 비대칭 | I₂/I₁ 0.027, 위상 0° 가정 (근거 없음 → 범위로 기록) | AI Hub 2.2 kW 정상 2대 중앙값 (docs/aihub_spec_check.md) |
| 합성 | I₂ = I₁·(r_LUT·e^{jθ_LUT} + 0.027) → Ia/Ib/Ic 페이저 → 기본파 정현파 (샘플링·창·출력 형식은 legacy 와 같음) | `engine/current_model.py` |

케이스별 설계값 (정격 부하, R_f 0.1 Ω):

| 케이스 | 근거 | LUT I₂/I₁ (위상) | 고유 비대칭 포함 범위 | 설계값(합성) | I₂/I_n | I_f | 단락 루프 총손실 |
|---|---|---|---|---|---|---|---|
| 정상 | LUT 0 % 행 | 0 | 0.027 | 0.027 | 0.029 | — | — |
| ITSC 4턴 (2.08 %) | LUT | 0.0476 (37.5°) | 0.021 ~ 0.075 | 0.071 | 0.075 | 34.4 A | 158 W (R_f 118 W + 단락 턴 동손 40 W) |
| ITSC 12턴 (6.25 %) | LUT | 0.2405 (30.0°) | 0.214 ~ 0.268 | 0.264 | 0.279 | 69.8 A | 977 W (R_f 487 W + 490 W) |
| (참고) 8턴 (4.17 %) | LUT | 0.141 | 0.114 ~ 0.168 | — | 0.163 | — | — |
| 과부하·전압 불평형·결상·무부하 | legacy 규칙 (LUT 범위 밖) | — | — | 0.027 / 0.060 / 0.479 / 0.027 | — | — | — |

legacy(해석식 역산) 와의 차이: 4턴 0.104 → 0.071 (−32 %), 12턴 0.269 → 0.264 (−2 %). legacy 는 고장상 크기 배율만으로 목표값을 맞췼고
(A상 +35 %/+110 %), LUT 는 단락 루프 순환전류가 지배하고 선전류 불평형은 작은 물리를 따른다 (4턴에서 A상 +7 %, C상 −6 %).

## 2. 임계값(`config/thresholds.yaml` i2i1 0.03 / 0.10)과의 만남 — 기록만

| 케이스 | 최소 | 설계값 | 최대 | 판정 범위 |
|---|---|---|---|---|
| 정상 | 0.027 | 0.027 | 0.027 | SAFE (경계 0.03 에 근접 — 여유 0.003) |
| 4턴 | 0.021 SAFE | 0.071 WARN | 0.075 WARN | **SAFE~WARN** — 고유 비대칭 위상에 따라 놓칠 수 있음 |
| 8턴 | 0.114 DANGER | 0.141 DANGER | 0.168 DANGER | DANGER (확실 탐지 시작) |
| 12턴 | 0.214 DANGER | 0.264 DANGER | 0.268 DANGER | DANGER |

- 정상 설계값 0.027 이 safe_below 0.03 바로 아래다. 고유 비대칭 실측이 0.028 (L-EF-04) 이면 정상 운전이 WARN 으로 뜬다.
- 4턴은 현재 경계로 "확실히" 잡히지 않는다 — 확실 탐지는 8턴부터 (분석 보고 표 G 와 일치).

### 제안 (적용 안 함)
1. **I₂/I_n 병기 지표** — 부하 50→100 % 에서 I₂/I₁ 은 +47 % 흔들리지만 I₂/I_n 은 0.0 % (I₂ 가 전압 구동이라 부하 무관). 경계 후보: 정상 0.029 / 4턴 0.075 / 8턴 0.163 → safe_below 0.05, danger_from 0.12 급. 지금은 **표시만** (state `i2_over_in`, HUD·대시보드 보조 줄).
2. **safe_below 0.03 → 모터별 정상 중앙값 × k** — 고유 비대칭이 0.027 인 모터에 0.03 공통 경계는 여유가 없다 (AI Hub 4대 정상 중앙값 0.026~0.088 편차). 실측 기준선(TASK_실측기준선)이 들어오면 `source/status/mode` 필드와 함께 재검토.
3. **저항성 결함(R_f ≥ 0.3 Ω)은 전류 지표로 탐지 불가** — 4턴 R_f 1.0 Ω 의 LUT I₂/I₁ 은 0.006 수준. 온도·진동 등 다른 지표가 필요하다 (proposal yaml 과 같음).

## 3. 단락 루프 손실 → 열 모델 (D4 연결)

> **2026-10-19 결정**: `loop_loss_to_winding: true` 유지. HUD 근거 줄에 "hotspot not modeled (winding mean node)" 표기. `winding_hotspot` 노드는 아래 제안으로만 둔다. 정격 전류는 카탈로그 4.73 A 로 통일 — 결정 (A): M1.yaml 5항목(선·상전류 4.73 A, `connection: star`(assumed, 현장 확인), η 0.895, pf 0.79)을 카탈로그 기준 래퍼 `{value, source, doc, note}` 로 바꿈. 로더 검증 규칙은 그대로. I₂/I_n 분모와 파형 기준이 일치.

- `coupling_to_thermal.loop_loss_to_winding: true` 일 때 통합 모드에서 LUT `P_loop_total_W` = I_f²(R_f + μ·R1_hot) 를 **권선 노드 추가 손실**로 넣는다
  (`ThermalModel.step(extra_loss_W={"winding": W})`, D4). 4턴 158 W, 12턴 977 W. M1 권선 정격 동손은 90 W(M5 855 W 의 손실비 P·(1−η)/η 스케일; η 0.85 때 136 W → 카탈로그 η 0.895 로 258 W/388 W 만큼 줄었다)이므로
  12턴은 정격 동손의 11배 — 권선 평균 온도가 빠르게 F종 한계를 넘는다 (의도: "ITSC → 권선 과열" 연쇄가 등가회로 값으로 재현됨).
- **핫스팟 제안**: 열회로에 권선 노드가 하나라 손실이 권선 전체 평균으로 퍼진다. 실제로는 단락 턴 몇 개에 집중된다.
  제안: `thermal.yaml` 에 `winding_hotspot` 노드(질량 = 단락 턴 구리 질량 ≈ 권선 질량 × μ, 권선 노드와 R_ij 결합)를 추가하고
  P_loop_total 을 그 노드로 보낸다. 지금은 열 config 를 건드리지 않고 권선 노드로 보내며, 끄려면 `loop_loss_to_winding: false`.
- legacy 방식은 이 손실을 넣지 않는다(기존과 같음: A상 과전류 → P_cu ∝ I² 만).

## 4. 남은 전제·한계

- 정격 전류: 2026-10-19 결정 (A)로 M1.yaml 을 카탈로그(현대일렉트릭 SSEN HLP-2.2/4 P2P2TC276, 380 V) 기준으로 통일 — 선전류 4.73 A(AI Hub L-SF-04 명판 4.7 A), 상전류 4.73 A(Y), `connection: star`(**assumed**: 380 V 전용형 내부 결선은 카탈로그에 없음, RMxprt·LUT 상전압 219.4 V 와 일치, `verify_on_site: true`), η 0.895, pf 0.79. 한 항목만 바꾸면 로더 규칙(상전류 = 선전류/√3 ±3 %, 선전류 = P/(√3·V·η·cosφ) ±5 %)에 걸려 함께 바꿨다. 열 모델 손실 스케일 P·(1−η)/η 가 388 → 258 W 로 줄어 M1 권선 정격 동손 136 → 90 W, 정상 운전 2 h 권선 온도 56.9 → 46.2 °C(연속 수렴 57.1 → 46.4 °C), 12턴 ITSC 2 h 201.7 → 190.6 °C(여전히 F종 한계 초과). 파형 RMS 는 5.4 % 감소, r·I₂/I₁ 은 불변, I₂/I_n 은 LUT 값 그대로(분모 일치).
- LUT 는 FEM 미검증(provisional). 정규 AEDT 라이선스에서 2D 과도 해석으로 I₂/I₁·I₂ 위상을 확인하면 `fem_verified: true` 로 올리고 `status` 를 바꾼다.
- Z₂ 앵커: LUT I₂ 불확실성 +20 %(FEM Z₂ 5.97 Ω 기준; I₂ ∝ 1/Z₂, 앵커 7.136 Ω 유지) (2026-10-19 F7, 수치 불변).
- 범위 밖(턴 > 16.7 %, R_f 밖, 부하 < 25 % 또는 > 115 %)은 끝값 클램프(`clamped` 플래그) — 외삽하지 않는다.
- 검증 보고: `docs/electrical/lut_integration_report.md` (`tools/electrical/verify_lut_integration.py`).

## 5. 실측 기준선 체계 (P1, 2026-10-21) — 원칙: 시뮬레이션 값은 실모터 판정 기준을 정하지 않는다

기준값은 명판·카탈로그·실측 기준선에서만 오고, 실측 기준선이 들어오기 전까지 전류 지표는 실측 스트림에서 "참고"다. 구조는 `config/thresholds.yaml`(`source/status/mode`, `judgment.provisional_policy`)에, 규칙은 `engine/thresholds.py` 에만 있다(worst-of·히스테리시스·지속 규칙은 바꾸지 않았다). §1~§4(ITSC 출처·Z₂ 불확실성)는 그대로.

### 5.1 지표별 출처·상태

| 지표 (엔진 kind) | yaml 경로 | source | status | mode | 경계 | 비고 |
|---|---|---|---|---|---|---|
| 전류/정격 r (`current_ratio`) | `current.rated_ratio` | catalog (`motors.M1.rated_line_current_a` 4.73 A) | provisional | — | 0.85~1.10 안전 / 1.25·0.50 위험 (값 불변) | 명판 확인 → M1.yaml `source: nameplate` → confirmed |
| I₂/I₁ (`i2i1`) | `current.negative_sequence` | reference_dataset | provisional | absolute | **경고 0.05**(0.03 → 0.05 변경) / 위험 0.10 유지 | 근거: AI Hub 2.2 kW 건전 8대 0.026~0.088 — 기존 0.03 은 건전 바닥(0.027) 바로 위. `baseline` null(실측 전) |
| I₂/I_n (`negative_sequence_rated`) | `current.negative_sequence_rated` | simulation | provisional | — | 표시 전용 | 판정 없음 |
| 상 불평형 (`phase_unbalance`) | `current.phase_unbalance` | simulation | provisional | absolute | 표시 전용 | 엔진 kind 없음 |
| 온도 | `temperature` | standard (F종·그리스 수명) | confirmed | — | 값 불변 | 22 kW 기준 열회로 스케일이라 M1 에서 낙관적일 수 있음(§5.5) |
| 진동 | `vibration` | motor_library (ISO 20816-3) | confirmed | — | 값 불변 | |
| 베어링 kurtosis·고주파 배율 | `bearing` | reference_dataset (AI Hub 238) | provisional | — | 값 불변 | 실모터 정상 기준선(bearing_hf_baseline 실측) 전까지 참고 |

### 5.2 두 정책 (`judgment.provisional_policy`)

- `simulation: include_with_label` — DT 시나리오(합성 신호): provisional 지표도 종합 판정에 들어가고 `Verdict.provisional_in_status`·`SignalVerdict.status` 로 "임시 기준" 라벨.
- `live: advisory_only` — 실측 스트림(라이브 브리지 연결, `Judge(stream="live")` / `demo_integrated --live` 가 자동 설정): provisional 지표는 worst-of 에서 빠지고 `Verdict.advisory` 에 따로 나온다(화면: 회색 "참고" 배지).
- 테스트 `tests/test_thresholds_provisional.py` 5종: live 정책(provisional DANGER 여도 종합은 온도로만) / simulation 포함+라벨 / baseline_multiple 전환(yaml 만) / 전압 보정 on·off / M1 7 시나리오 전후 표.

### 5.3 M1 7 시나리오 — 변경 전(0.03)/후(0.05)

| 케이스 | I₂/I₁ | i2i1 전 | 후 | 종합 전 | 후 |
|---|---|---|---|---|---|
| healthy | 0.027 | SAFE | SAFE | SAFE | SAFE |
| itsc_4turn | 0.0726 | WARN | WARN | WARN | WARN |
| itsc_12turn | 0.2696 | DANGER | DANGER | DANGER | DANGER |
| overload | 0.027 | SAFE | SAFE | DANGER(r) | DANGER(r) |
| voltage_unbalance | 0.0595 | WARN | WARN | WARN | WARN |
| single_phasing | 0.4792 | DANGER | DANGER | DANGER | DANGER |
| no_load | 0.027 | SAFE | SAFE | DANGER(r) | DANGER(r) |

4턴(0.0726)은 새 경계 0.05 바로 위라 WARN 유지 — 고유 비대칭 위상에 따라 0.022~0.076 이므로 여전히 SAFE~WARN 사이(§2). 정상(0.027)은 경계에서 0.023 여유(이전 0.003).

### 5.4 참고 기준선 (AI Hub L-SF-04, `config/baselines/M1_AIHUB_LSF04_REFERENCE.yaml`)

- `tools/baseline_capture.py --grade reference --aihub-dir …/current/2.2kW/L-SF-04/정상 --apply-reference`: 창 77(1 s 파일 77개), I₁ 중앙값 3.173 A(변동계수 0.0065), **I₂/I₁ 중앙값 0.0879 / p95 0.1005 / 최대 0.1052**, 상 불평형 중앙값 0.0655, 기본파 60.00 Hz, 상 순서 abc. 열 매핑: 메타 9줄 뒤 시간·ch1·ch2·ch3 = R·S·T(가이드라인 §1.3.2; 대칭분은 순서 무관). 2 kHz 샘플은 60 Hz 대칭 성분에 충분(나이퀴스트 1 kHz).
- **품질 게이트 부적합**(창 77 < 500) — 참고 등급이라 `reference_baseline.value = 0.1005` 로 기록했지만 판정 기준이 아니다. 더 중요한 점: L-SF-04 의 I₂/I₁ 은 **S상 RMS 가 10 % 커서 0.088 수준(p95 0.10 = 위험 경계)** 이다 — 공급 불평형인지 전류센서 채널 게인 차이인지 데이터로 구분이 안 된다(전압 채널 없음, docs/aihub_spec_check.md). 따라서 L-SF-04 는 "건전 바닥 0.027" 의 근거가 아니고(그 근거는 L-EF-04·R-EF-05), M1 참고 기준선으로도 신뢰도가 낮다. 전압 보정은 `enabled: false` 유지.
- 온도 채널 없음 → §5.5.

### 5.5 열 모델 M1 (P1-4, 수치 변경 없음)

M1 연속 정격 권선 46.4 °C(상승 ≈ 21 K)는 카탈로그 B종 한도 80 K·IE3 2.2 kW 통상 50~70 K 보다 낮다 — 22 kW 기준 열회로 스케일이 M1 에서 낙관적일 가능성. AI Hub 에 온도 채널이 없어 실측 비교 불가 → `docs/thermal_scaling.md` 절과 온도 게이지 툴팁에 같은 문장. 스케일 규칙·임계값은 바꾸지 않는다.

### 5.6 기준선 측정 절차 (실모터)

1. 정상 운전(정격 부하 근방, 기동 제외) 3상 전류(+가능하면 전압) ≥ 500 s 녹화 → CSV `t, ia, ib, ic[, va, vb, vc]` (2 kHz 이상).
2. `py -3.12 -X utf8 tools/baseline_capture.py --motor M1 --tag SITE_<날짜> --csv <파일> --fs <Hz>` → `config/baselines/M1_SITE_<날짜>.yaml`, 품질 게이트(창 ≥ 500, I₁ CV ≤ 10 %) 통과 확인, diff 출력 확인.
3. 사람이 yaml 에 옮긴다(자동 반영 없음) — 아래 5.7.

### 5.7 명판·기준선이 들어오면 바꿀 yaml 필드 경로

| 들어오는 것 | 바꿀 곳 | 결과 |
|---|---|---|
| 명판 정격 전류·결선 | `config/motors/M1.yaml` `rated_line_current_a/rated_phase_current_a/connection` 의 `source: nameplate`(값은 명판) | `current.rated_ratio` 는 M1.yaml 출처를 따라가므로 `config/thresholds.yaml current.rated_ratio.source: nameplate, status: confirmed` 로 올림 |
| 실측 I₂/I₁ 기준선 | `config/thresholds.yaml current.negative_sequence.baseline: {value, measured_at, n_windows, p95, v2_v1_mean}`, `mode: baseline_multiple`, `status: confirmed`, `source: baseline` | 경고 = value×2.0, 위험 = value×4.0 (`warn_multiple/danger_multiple`) — 코드 변경 없음 |
| 전압 채널 확보 | `current.negative_sequence.voltage_unbalance_compensation.enabled: true` (입력에 `v2_v1`) | I₂/I₁ − k·V₂/V₁ 로 판정, `compensated: true` |
| 실측 상 불평형 기준선 | `current.phase_unbalance.baseline`, `mode: baseline_multiple` | 표시 전용(엔진 kind 추가는 별도) |
| 실모터 베어링 정상 고주파 RMS | `config/motors/M1.yaml bearing_hf_baseline` (`source: measured`), `thresholds.yaml bearing.status: confirmed` | 베어링 보조 지표 참고 배지 해제 |
| 실측 권선·프레임 온도 | 열회로 재보정은 별도 작업(스케일 규칙 변경 금지) — `docs/thermal_scaling.md` | |
