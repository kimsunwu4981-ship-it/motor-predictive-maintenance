# 검증 요약 (verification summary) — 발표·문서가 인용할 단 하나의 출처

생성 2026-10-21 23:25:58 · `motor_dt_viz/tools/docs/verification_summary.py` · 수기 숫자 없음(입력: analysis_reference.json, sim_vs_analysis.json, M1.yaml, thresholds.yaml, baselines, aihub_spec_check.md, housing_params.yaml). 핵심값 JSON: `docs/verification_summary.json`.

## 1. 항목별 출처 등급

| 항목 | 등급 | 근거 |
|---|---|---|
| 정격 성능 (4.73 A · pf 0.79 · η 0.895 · 1760 rpm · 100L · F종/B) | **카탈로그 확정** | M1.yaml source=catalog(현대 SSEN HLP-2.2/4 P2P2TC276 (380 V)); RMxprt v2m2 정합 I 4.670 A·pf 0.791·η 89.6 % |
| 결선 (Y, 상전류 = 선전류) | **현장확인 대기** | M1.yaml connection source=assumed, verify_on_site=True — 380 V 전용형 내부 결선은 카탈로그에 없음. RMxprt·LUT 모델(상전압 219.4 V)과 일치시킴 |
| 기동 특성 (잠김 전류·토크비) | **2D FEM(보정) / 카탈로그** | 카탈로그 6.5×/2.1× · RMxprt 8.24×/3.09× · FEM+F2 7.43×/2.34× (IEC I_st ≤ 7.8) |
| 등가회로 상수 (R1·R2′·X1·X2′·Xm·Z₂) | **RMxprt 정합 / 2D FEM** | R1 1.24388/1.60973 Ω(20/95 °C), Xm RMxprt 97.6 vs FEM X_total 95.6 Ω, Z₂ 앵커 7.136 vs FEM 5.33/5.97 Ω |
| ITSC 전류 곡선 (I₂/I₁·I_f·손실 LUT) | **등가회로 (2D FEM 검증, provisional)** | 등가회로(RMxprt v2m2+MCCM) + 2D 와전류 검증(단순화 기하, 학생판 lite) · status provisional · FEM 검증 2D-eddy-lite (I_f ±3 %, Xm −3.7 %, locked-rotor IEC 안) · I_f 4턴 MCCM 34.35 vs FEM 35.16 A (+2.4 %) |
| 3D 형상 (하우징·내부) | **카탈로그 + 시각 추정 (Maxwell 체적 ±2 % 검증)** | 카탈로그 치수 19+7개(KS 치수표 100L), visual_estimate 23개(핀·엔드쉴드·팬커버·단자함), 내부 체적 vs Maxwell geometry_check ±2 % PASS (확인) |
| 열 모델 (9노드 집중정수) | **가정 (22 kW 보정값 스케일)** | thermal.yaml 22 kW 보정값을 손실비·치수비로 스케일 — 실측 온도 없음, M1 에서 낙관적일 수 있음(정격 상승 ≈21 K vs B종 80 K) |
| 진동·베어링 임계값 | **표준 / 참고 데이터셋** | 진동 ISO 10816-1 Class I (< 15 kW, 강성 지지) 경고 1.8 / 위험 4.5 mm/s(표준); 베어링 kurtosis·고주파 배율 = AI Hub 참고(provisional) |
| 전류 임계값 (I₂/I₁ 0.05/0.10, 전류/정격) | **참고 데이터셋 (provisional)** | reference_dataset/provisional, mode absolute, reference_baseline 0.1005(AI Hub 기계시설물 고장 예지 센서 L-SF-04 정상), 정책 simulation=include_with_label / live=advisory_only |

등급 정의: 카탈로그 확정(제조사 카탈로그 값) · RMxprt 정합(카탈로그 정격에 맞춘 해석적 해) · 등가회로(MCCM/LUT) · 2D FEM(학생판 lite, 단순화 기하) · 표준(IEC/ISO) · 가정 · 현장확인 대기(명판·실측 전).

## 2. 핵심 숫자

- 정격: **4.73 A · pf 0.79 · η 89.5 % · 1760 rpm**(카탈로그). RMxprt v2m2 4.670 A / 0.791 / 89.58 %; 2D FEM lite 4.90 A / 0.740 / 91.5 %.
- 기동 전류: 카탈로그 6.5× → RMxprt 8.24× → **FEM+스큐 보정 7.43×** (IEC 60034-1 허용 ≤ 7.8). 기동 토크 FEM 보정 2.34× (카탈로그 2.1×).
- 역률: FEM lite **0.74** — IEC 하한 0.755 **미달(유일)**; RMxprt 0.791 은 통과. 진단: 2D lite 누설 과대(브리지 선형화·단순화 기하).
- I₂/I₁ (DT 합성 신호): 고유 비대칭 **0.027** = AI Hub 건전 모터 하한(L-EF-04 0.028 · R-EF-05 0.026 중앙값 — **L-SF-04 값이 아님**) / 4턴 **0.073**(경계, 각도 범위 0.022~0.076) / 8턴 **0.17**(확실) / 12턴 **0.27** / 16턴 0.36; 저항성 4턴(R_f 1.0 Ω) 결함분 **0.0065**(합성 0.032 — 전류로 탐지 불가).
- LUT 불확실성: Z₂ 앵커 7.136 Ω vs FEM 보정 5.97 Ω → I₂ **+20 %** 가능.
- 베어링 6206ZZC3(DE·NDE): BPFO 104.7 / BPFI 159.3 / BSF 67.8 / FTF 11.6 Hz @ 1760 rpm(규격 공식 추정). 진동 ISO 10816-1 Class I 경고 1.8 / 위험 4.5 mm/s.

## 3. P1 실측 기준선 결과 (그대로 기록)

- AI Hub L-SF-04 정상 **77창**(1 s·2 kHz, 전압·온도 채널 없음): I₂/I₁ 중앙값 **0.0879** · p95 **0.1005**(= 위험 경계 0.1) · 최대 0.105; 상 불평형 중앙값 0.065; I₁ 3.17 A(CV 0.7 %).
- S상 RMS 가 다른 상보다 약 +10 %(메타 RMS 3.10/3.46/3.16 A) → 전압 채널이 없어 **센서 채널 게인 차이인지 공급 불평형인지 구분 불가**.
- 품질 게이트 **부적합**(창 77 < 500) → `reference_baseline.value 0.1005` 는 **참고 등급**(판정 기준 아님), `baseline: null` 유지. 전체 AI Hub Training zip(88~112 GB)은 미다운로드라 보강 못 함(D5 건너뜀).
- 정책: 시뮬레이션 스트림 = provisional 지표 포함 + 라벨 / 실측(live) 스트림 = advisory(참고)만, 종합 판정은 confirmed 지표(온도·진동)로. 온도 채널 없음 → 열 모델(22 kW 스케일)은 M1 에서 낙관적일 수 있어 실측 전 보정 불가.

WARN 0.03 → **0.05** 적용 전후 판정(엔진 stateless, 시뮬레이션 정책; D3 I₁ 규약·경부하 참고 규칙(2026-10-21 승인, `docs/verification/light_load_rule.md`) 반영 — '종합 전' 열은 WARN 0.03 기준이되 현재 규칙):

| 케이스 | I₂/I₁ | I₁ [A] | r R상 | i2i1 전(0.03) | 후(0.05) | 종합 전 | 종합 후 (원인) |
|---|---|---|---|---|---|---|---|
| healthy | 0.027 | 4.695 | 1.019 | SAFE | SAFE | SAFE | SAFE (-) |
| itsc_4turn | 0.0726 | 4.887 | 1.103 | WARN | WARN | WARN | WARN (i2i1) |
| itsc_8turn | 0.1676 | 5.327 | 1.297 | DANGER | DANGER | DANGER | DANGER (i2i1) |
| itsc_12turn | 0.2696 | 5.923 | 1.563 | DANGER | DANGER | DANGER | DANGER (i2i1) |
| itsc_16turn | 0.3625 | 6.633 | 1.881 | DANGER | DANGER | DANGER | DANGER (i2i1) |
| itsc_4turn_resistive | 0.0324 | 4.719 | 1.03 | WARN | SAFE | WARN | SAFE (-) |
| itsc_4turn_halfload | 0.0953 | 3.202 | 0.731 | WARN | WARN | WARN | WARN (i2i1) |
| overload | 0.027 | 6.385 | 1.386 | SAFE | SAFE | DANGER | DANGER (current_ratio) |
| voltage_unbalance | 0.0595 | 4.727 | 1.08 | WARN | WARN | WARN | WARN (i2i1) |
| single_phasing | 0.4792 | 4.087 | 0.036 | DANGER | DANGER | DANGER | DANGER (current_ratio) |
| no_load | 0.027 | 1.561 | 0.339 | SAFE | SAFE | SAFE | SAFE (-) +경부하 참고 |

건전 모터 I₂/I₁ 분포 — **창별 정상성 게이트 적용**(창 I₁ 중앙값 ±5 %, 기본파/전체 RMS ≥ 0.95, 상별 RMS/평균 0.8~1.25; `docs/aihub_baseline_gated.md`, 샘플 zip 범위):

| 모터 | 파일 | 통과 창 | 제외 창 (사유) | I₁ 중앙값 [A] | I₂/I₁ 중앙값 / p95 / 최대 | 불평형 중앙값 | 상별 RMS 비 R:S:T |
|---|---|---|---|---|---|---|---|
| L-DSF-01 (2.2kW) | 97 | 80 | 17 (I1_dev 17, fund_over_rms 17, phase_ratio 14) | 2.255 | 0.0792 / 0.0835 / 0.0879 | 0.089 | 0.995 : 0.916 : 1.089 |
| L-EF-04 (2.2kW) | 667 | 415 | 252 (I1_dev 252, fund_over_rms 2) | 3.189 | 0.028 / 0.0393 / 0.042 | 0.0341 | 1.01 : 1.025 : 0.966 |
| L-SF-04 (2.2kW) | 77 | 77 | 0 (—) | 3.173 | 0.0879 / 0.1005 / 0.1052 | 0.0655 | 0.964 : 1.065 : 0.972 |
| R-EF-05 (2.2kW) | 65 | 63 | 2 (I1_dev 1, fund_over_rms 1) | 2.069 | 0.0263 / 0.0392 / 0.0396 | 0.0305 | 0.992 : 1.031 : 0.98 |
| L-PAHU-03S (55kW) | 97 | 0 | 97 (fund_over_rms 97, I1_dev 51) | — | — / — / — | — | — (60 Hz 게이트 전부 제외: 인버터 49.6 Hz) |
| R-PAHU-04S (55kW) | 59 | 59 | 0 (—) | 52.406 | 0.0054 / 0.0065 / 0.0071 | 0.0073 | 1.007 : 0.995 : 0.997 |

L-SF-04 S상 RMS 비 1.065(날짜별 1.05~1.069, 창 표준편차 0.0095) — 전 구간 일정 → **센서 채널 게인 차이 가설**이 우세하나 전압 채널이 없어 가설로만 둔다(보정 없음). 게이트 뒤에도 L-SF-04 는 77/77 통과, 값 불변.

## 4. 함의 (실증 가이드라인 '전압 센서 필수' 결정의 수치 근거)

절대 임계값 0.05/0.1 은 전압 불평형이 보정된 깨끗한 기준선을 전제한다. L-SF-04 처럼 건전 모터가 0.0879 을 보이는 현장에서는 (1) 전압 채널로 V₂/V₁ 보정(`voltage_unbalance_compensation`)을 켜거나 (2) 기준선 배수 모드(`mode: baseline_multiple`)로 가야 한다. 보정 없는 기준선 배수 모드에서는 경고 = p95 0.1005 × 2 = **0.201**, 위험 = × 4 = 0.402 이므로 4턴(합성 0.073)·8턴(0.168)급 결함은 구분되지 않고 **12턴(0.270)~16턴(0.363)급부터** 잡힌다 (판정: 4턴 SAFE, 8턴 SAFE, 12턴 WARN, 16턴 WARN).

## 5. 시뮬 ↔ 해석 대조 결과 (`docs/verification/sim_vs_analysis_report.md`)

- 대조표 **89/89 PASS**; I₂/I₁ 결함분 vs LUT ≤ **0.48 %**; 엔진 비의존 재계산 ≤ **0.023 %**(213 파형); 탐지 지연 4턴 WARN **2.98 s** · 12턴 DANGER **3.03 s**(지속 3 s 규칙) · 정상 오경보 0.
- I₁ 규약 정정(D3: LUT 상별 RMS) 후 결함상 r = I/I_n: 4턴 **1.1** / 8턴 **1.3** / 12턴 **1.56** / 16턴 **1.88**; 반부하 4턴 I₁ **3.2 A**(정격의 68 %) — 가짜 결상 경보 해소(DANGER→WARN).
- 고유 비대칭 각도 180° 에서 4턴 합성 I₂/I₁ **0.0313** → 경고 소실(0.05 아래). 각도는 근거 없는 가정(0°)이다.
- 권선 ΔT 정상 상태 vs 열 모델 에너지 수지 역산 편차 ≤ 0.001 %(모델 자기 일관성). `scene_check.json`(P4 장면표)은 새 규약으로 재실행해 정본과 맞춘다.

## 6. 한계

- 합성 신호(엔진 페이저 합성) — 실측 아님
- 고유 비대칭 0.027 은 건전 하한 가정(AI Hub L-EF-04·R-EF-05 중앙값; L-SF-04 실측 p95 0.1005 는 품질 부적합)
- Z₂ 카탈로그 앵커 7.136 Ω vs FEM 5.97 Ω → LUT I₂ 불확실성 +20 %
- 2D lite: 무스큐·분산 결함·단순화 기하(학생판), 시간 파형·RSH 없음
- 열 모델은 22 kW 기준 스케일 — M1 에서 낙관적일 수 있음(실측 전 보정 불가)
- 기계 결함(베어링·오정렬·팬·브레이크)은 Maxwell 근거 없음 — 진동·베어링 상수(표준/AI Hub 참고)
- 2D lite: 무스큐·분산 결함(1/16)·브리지 선형화 → 역률 0.740(미달)·I_st 보정 의존.
- 결선 Y 는 카탈로그 기준 가정 — 명판·현장 확인 전까지 `verify_on_site`.

## 7. 입력 파일 sha256

| 키 | 경로 | sha256 (앞 16) |
|---|---|---|
| mccm_results | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\mccm_results.json` | `4e2a832bd6c9c17f` |
| mccm_lut | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\mccm_lut.json` | `7d7b1ac5147a1e4a` |
| f2 | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\f2_corrections.json` | `5e21ad5b5d91fda9` |
| f7 | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\f7_iec_tolerance.json` | `f99af4b76654c2fc` |
| eddy_summary | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\eddy2d\summary.json` | `0fb986f232d14d4e` |
| rmxprt | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_v2m2.json` | `07736423faa11165` |
| temp_sweep | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_temp_sweep.json` | `21fe315328ce824e` |
| magcurve | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\magnetizing_curve_2d.json` | `b0f93df33e1b6605` |
| inductance | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\inductance_matrix_2d.json` | `a36126216cd3ec6c` |
| analysis_tables_xlsx | `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\analysis_tables.xlsx` | `cfda1af0f9b13b4d` |
| electrical_yaml | `motor_dt_viz/config/electrical.yaml` | `69266c21fed85b6c` |
| lut_dt | `motor_dt_viz/data/electrical/M1_mccm_lut_v2.json` | `c6898c6e8d801f49` |
| thresholds_yaml | `motor_dt_viz/config/thresholds.yaml` | `92a7e9fb6043903e` |
| m1_yaml | `motor_dt_viz/config/motors/M1.yaml` | `2d8ca5614eaf3e17` |
| thermal_yaml | `motor_dt_viz/config/thermal.yaml` | `fe1e7d4e4c2a848f` |
| lut_report | `motor_dt_viz/docs/electrical/lut_integration_report.md` | `29f1e11329955caf` |
