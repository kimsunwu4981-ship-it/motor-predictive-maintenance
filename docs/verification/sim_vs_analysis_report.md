# Isaac Sim 결함 시뮬레이션 ↔ Maxwell/등가회로 해석 결과 대조 검증 보고서

생성 2026-10-21 16:38 · 생성기 `motor_dt_viz/tools/verify/write_report.py` · 대조 `sim_vs_analysis.json`(2026-10-21 16:38:21) · 기준 `motor_dt_viz/data/electrical/analysis_reference.json`(2026-10-21 16:11:05) · 근거 사슬 `traceability.json`

> 새 계산·새 해석·설정 변경 없음. 시뮬은 기존 장면·엔진·LUT 로 돌렸고(Isaac Sim 헤드리스 자동 재생, `demo_integrated.py --verify_dir` 로깅 훅), 대조·그림·표는 스크립트가 로그와 해석 파일에서 읽어 만들었다(수기 숫자 없음). 기계 결함은 Maxwell 근거가 없어 출처만 표기한다.

## 1. 한 줄 결론

- 전기 결함 시나리오의 표시값(I₂/I₁ 결함분·I_f·단락 루프 손실·불평형)은 해석값(LUT v2 = MCCM 등가회로)과 **최대 0.48 %** 안에서 일치한다(허용 ±1 %, 손실 ±2 %). 합성 파형을 엔진과 무관하게 다시 계산한 I₂/I₁ 은 **최대 0.023 %** 차이(허용 ±0.5 %, 127 파형).
- 대조표 **89/89 PASS** — 전 항목 허용 안. D3(2026-10-21, 엔진 수정 승인): LUT 경로의 I₁ 을 LUT 정상분 RMS 에서 가져오도록 바꿔 결함분 I₂/I_n 이 LUT 와 같아졌고 r = I/I_n 이 결함 시 상승한다 — 전후 표 `d3_i1_from_lut.md`.
- 판정: 4턴은 주입 3 s 뒤 WARN(0.05 경계), 8·12·16턴은 3 s 뒤 DANGER(0.10), 저항성 4턴(R_f 1.0 Ω)은 SAFE 유지, 정상 구간 오경보 0건 — 임계값·지속 규칙과 일치.

| 시나리오 | 주입 [s] | 첫 WARN | 첫 DANGER | 지연 [s] | 장면 끝 | 원인 |
|---|---|---|---|---|---|---|
| healthy | 0.0 | — | — | — | SAFE | - |
| itsc_4turn | 20.0 | 23.01 | — | WARN 3.01 | WARN | i2i1 |
| itsc_8turn | 165.0 | — | 168.07 | DANGER 3.07 | DANGER | i2i1 |
| itsc_12turn | 45.0 | — | 48.07 | DANGER 3.07 | DANGER | i2i1 |
| itsc_16turn | 185.0 | — | — | — | DANGER | i2i1 |
| itsc_4turn_resistive | 205.0 | — | — | — | SAFE | - |
| itsc_4turn_halfload | 225.0 | 228.03 | — | WARN 3.03 | WARN | i2i1 |

## 2. 시나리오별 '무슨 일이 일어나는가' (비전공자용)

**healthy** — 세 상 전류가 거의 같다. 완전히 같지는 않은데(R상이 약간 큼), 이것은 정상 모터·전원에도 있는 '고유 비대칭' 0.027 을 일부러 넣었기 때문이다. I₂/I₁ 은 0.027 로 경고 경계 0.05 아래라 **안전** 이 유지된다.

**itsc_4turn** — 코일 한 개의 4턴(권선의 2.1 %)이 서로 붙었다. 붙은 고리에 큰 순환 전류 I_f ≈ 34 A 가 돌지만 바깥 선전류는 R상이 5.21 A 로 조금 커질 뿐이다. 대신 세 상의 '균형'을 재는 I₂/I₁ 이 0.027 → 0.073 으로 뛰어 경계 0.05 을 넘고, 3 s 지속 규칙 뒤 **경고**가 뜬다(주입 후 3.01 s). 단락 고리에서 158 W 가 더 발열해 권선이 천천히 데워진다(통합 모드 §3 열).

**itsc_8turn** — 8턴(4.2 %)이 붙으면 I₂/I₁ 이 0.168 으로 위험 경계 0.1 를 넘어 3 s 뒤 **위험**이다. 손실 511 W 로 권선 온도 상승이 뚜렷하다.

**itsc_12turn** — 12턴(6.3 %)에서는 I₂/I₁ 0.270, 순환 전류 70 A, 손실 977 W. 권선 온도가 F종 한계를 넘는 방향으로 간다(통합 모드에서 권선 ΔT 역산 174 °C). **위험**.

**itsc_16turn** — 코일 전체 16턴이 붙은 경우. I₂/I₁ 0.363, R상 선전류도 8.89 A(정격의 188 %)로 과전류 위험 영역(>125 %)에 들어간다. 손실 1523 W. **DANGER**.

**itsc_4turn_resistive** — 4턴이 붙었지만 접촉 저항이 1.0 Ω 으로 크면 순환 전류가 4.4 A 에 그쳐 I₂/I₁ 은 0.032 — 경계 0.05 아래라 **안전** 으로 남는다. '턴 수'가 아니라 '얼마나 세게 붙었나'가 탐지를 가른다는 뜻이다.

**itsc_4turn_halfload** — 같은 4턴 단락을 부하 50 % 에서 보면 I₂/I₁ 은 0.095 으로 100 % 부하(0.072)보다 커 보인다(분모 I₁ 이 작아져서). 그래서 부하 무관 지표 I₂/I_n 을 같이 본다. 세 상 전류가 정격의 62~73 % 라 '저전류 경고' 규칙에도 걸리고, 장면 끝 종합은 **WARN**(원인 i2i1)이다. (D3 전에는 I₁ 을 정격×0.5 로 고정해 T상이 0.46 으로 '결상 의심' 위험이었다 — docs/verification/d3_i1_from_lut.md)

## 3. 대조표 (허용 안 = PASS)

| 항목 | 시나리오 | 시뮬(로그) | 해석 기준 | 허용 | 편차 | 판정 | 비고 |
|---|---|---|---|---|---|---|---|
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | healthy | 0 | 1 |  |  | PASS | n=89 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | healthy | 0 | 0 | ±1 % |  | PASS | 합성 0.02700 ∠0.0°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | healthy | 0.027 | [0.027, 0.027] |  |  | PASS | 기대(각도 0°) 0.027 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | healthy | 0.027 | 0.027 | ±1 % | +0.00 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | healthy | 0 | 0 | ±1 % |  | PASS | 시뮬 I₁ 4.6946 A (LUT 정상분 RMS, D3), LUT I₁ 4.69464 A |
| I₁ 정상분 [A] vs LUT I₁ | healthy | 4.6946 | 4.6946 | ±1 % | +0.00 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | healthy | 0.0268 | 0.026798 | ±1 % | +0.01 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | healthy | 2.6806 | 2.681 | ±2 % | -0.01 % | PASS | LUT 자체 0.0 % (LUT I₁ 기준) |
| 판정 (장면 끝 종합 상태) vs 예상 | healthy | SAFE | SAFE |  |  | PASS | 원인 - 0.0 · i2i1 예상 SAFE |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn | 0 | 1 |  |  | PASS | n=89 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn | 0.048965 | 0.048815 | ±1 % | +0.31 % | PASS | 합성 0.07262 ∠23.2°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn | 0.07262 | [0.021815, 0.075815] |  |  | PASS | 기대(각도 0°) 0.072474 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn | 0.07262 | 0.072474 | ±1 % | +0.20 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn | 0.05059 | 0.050428 | ±1 % | +0.32 % | PASS | 시뮬 I₁ 4.8870 A (LUT 정상분 RMS, D3), LUT I₁ 4.88627 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn | 4.887 | 4.8863 | ±1 % | +0.01 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn | 0.07503 | 0.074868 | ±1 % | +0.22 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn | 6.572 | 6.5603 | ±2 % | +0.18 % | PASS | LUT 자체 4.4846 % (LUT I₁ 기준) |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn | 34.381 | 34.347 | ±1 % | +0.10 % | PASS | FEM(F1 보정) 35.16 A 참고 |
| I_f [A] vs 2D FEM(F1 보정) — 참고 열 | itsc_4turn | 34.381 | 35.155 | ±5 % | -2.20 % | PASS | 참고(±5 % MCCM↔FEM 정합 범위) |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn | 158.1 | 157.54 | ±2 % | +0.36 % | PASS | 공식(루프 저항항만) 157.5 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn | WARN | WARN |  |  | PASS | 원인 i2i1 0.0726 · i2i1 예상 WARN |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_4turn | 3.01 | 3 | ±20 % | +0.33 % | PASS | 첫 WARN |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_12turn | 0 | 1 |  |  | PASS | n=87 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_12turn | 0.24552 | 0.24551 | ±1 % | +0.00 % | PASS | 합성 0.26958 ∠25.6°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_12turn | 0.26958 | [0.218513, 0.272513] |  |  | PASS | 기대(각도 0°) 0.269578 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_12turn | 0.26958 | 0.26958 | ±1 % | +0.00 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_12turn | 0.30745 | 0.30745 | ±1 % | +0.00 % | PASS | 시뮬 I₁ 5.9233 A (LUT 정상분 RMS, D3), LUT I₁ 5.92325 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_12turn | 5.9233 | 5.9233 | ±1 % | +0.00 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_12turn | 0.33759 | 0.33759 | ±1 % | +0.00 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_12turn | 22.546 | 22.546 | ±2 % | +0.00 % | PASS | LUT 자체 21.067 % (LUT I₁ 기준) |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_12turn | 69.803 | 69.803 | ±1 % | +0.00 % | PASS |  |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_12turn | 977.46 | 977.46 | ±2 % | -0.00 % | PASS | 공식(루프 저항항만) 977.5 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_12turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.2696 · i2i1 예상 DANGER |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_12turn | 3.07 | 3 | ±20 % | +2.33 % | PASS | 첫 DANGER |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | overload | 0 | 1 |  |  | PASS | n=88 |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | voltage_unbalance | 0 | 1 |  |  | PASS | n=89 |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | single_phasing | 0 | 1 |  |  | PASS | n=88 |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | no_load | 0 | 1 |  |  | PASS | n=89 |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_8turn | 0 | 1 |  |  | PASS | n=88 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_8turn | 0.1441 | 0.14425 | ±1 % | -0.11 % | PASS | 합성 0.16757 ∠27.2°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_8turn | 0.16757 | [0.11725, 0.17125] |  |  | PASS | 기대(각도 0°) 0.167724 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_8turn | 0.16757 | 0.16772 | ±1 % | -0.09 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_8turn | 0.16227 | 0.16247 | ±1 % | -0.12 % | PASS | 시뮬 I₁ 5.3266 A (LUT 정상분 RMS, D3), LUT I₁ 5.32735 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_8turn | 5.3266 | 5.3274 | ±1 % | -0.01 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_8turn | 0.18871 | 0.18891 | ±1 % | -0.10 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_8turn | 14.341 | 14.353 | ±2 % | -0.08 % | PASS | LUT 자체 12.9454 % (LUT I₁ 기준) |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_8turn | 510.91 | 511.47 | ±2 % | -0.11 % | PASS | 공식(루프 저항항만) 511.5 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_8turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.1676 · i2i1 예상 DANGER |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_8turn | 3.07 | 3 | ±20 % | +2.33 % | PASS | 첫 DANGER |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_16turn | 0 | 1 |  |  | PASS | n=89 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_16turn | 0.33785 | 0.33774 | ±1 % | +0.03 % | PASS | 합성 0.36253 ∠23.1°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_16turn | 0.36253 | [0.31074, 0.36474] |  |  | PASS | 기대(각도 0°) 0.362417 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_16turn | 0.36253 | 0.36242 | ±1 % | +0.03 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_16turn | 0.47377 | 0.47352 | ±1 % | +0.05 % | PASS | 시뮬 I₁ 6.6329 A (LUT 정상분 RMS, D3), LUT I₁ 6.63155 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_16turn | 6.6329 | 6.6315 | ±1 % | +0.02 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_16turn | 0.50838 | 0.50811 | ±1 % | +0.05 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_16turn | 29.547 | 29.539 | ±2 % | +0.03 % | PASS | LUT 자체 27.5857 % (LUT I₁ 기준) |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_16turn | 80.643 | 80.631 | ±1 % | +0.02 % | PASS |  |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_16turn | 1523.3 | 1522.2 | ±2 % | +0.07 % | PASS | 공식(루프 저항항만) 1522.2 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_16turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.3625 · i2i1 예상 DANGER |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn_resistive | 0 | 1 |  |  | PASS | n=90 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn_resistive | 0.006542 | 0.006511 | ±1 % | +0.48 % | PASS | 합성 0.03244 ∠7.0°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn_resistive | 0.03244 | [0.020489, 0.033511] |  |  | PASS | 기대(각도 0°) 0.032413 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn_resistive | 0.03244 | 0.032413 | ±1 % | +0.08 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn_resistive | 0.006527 | 0.006496 | ±1 % | +0.48 % | PASS | 시뮬 I₁ 4.7191 A (LUT 정상분 RMS, D3), LUT I₁ 4.719 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn_resistive | 4.7191 | 4.719 | ±1 % | +0.00 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn_resistive | 0.03236 | 0.032338 | ±1 % | +0.07 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn_resistive | 3.1933 | 3.1903 | ±2 % | +0.09 % | PASS | LUT 자체 0.6019 % (LUT I₁ 기준) |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn_resistive | 4.431 | 4.4244 | ±1 % | +0.15 % | PASS | FEM(F1 보정) 4.56 A 참고 |
| I_f [A] vs 2D FEM(F1 보정) — 참고 열 | itsc_4turn_resistive | 4.431 | 4.5647 | ±5 % | -2.93 % | PASS | 참고(±5 % MCCM↔FEM 정합 범위) |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn_resistive | 20.32 | 20.232 | ±2 % | +0.43 % | PASS | 공식(루프 저항항만) 20.2 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn_resistive | SAFE | SAFE |  |  | PASS | 원인 - 0.0 · i2i1 예상 SAFE |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn_halfload | 0 | 1 |  |  | PASS | n=88 |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn_halfload | 0.074726 | 0.074507 | ±1 % | +0.29 % | PASS | 합성 0.09529 ∠34.8°, 고유 0.027 ∠0° |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn_halfload | 0.09529 | [0.047507, 0.101507] |  |  | PASS | 기대(각도 0°) 0.095076 |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn_halfload | 0.09529 | 0.095076 | ±1 % | +0.23 % | PASS |  |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn_halfload | 0.050586 | 0.050428 | ±1 % | +0.31 % | PASS | 시뮬 I₁ 3.2020 A (LUT 정상분 RMS, D3), LUT I₁ 3.20136 A |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn_halfload | 3.202 | 3.2014 | ±1 % | +0.02 % | PASS | D3: 결함 시 상승(격자 보간) |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn_halfload | 0.06451 | 0.064349 | ±1 % | +0.25 % | PASS | 표시값 자체의 일관성 |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn_halfload | 8.7364 | 8.7152 | ±2 % | +0.24 % | PASS | LUT 자체 7.3601 % (LUT I₁ 기준) |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn_halfload | 34.381 | 34.347 | ±1 % | +0.10 % | PASS |  |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn_halfload | 158.1 | 157.54 | ±2 % | +0.36 % | PASS | 공식(루프 저항항만) 157.5 W |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn_halfload | WARN | WARN |  |  | PASS | 원인 i2i1 0.0953 · i2i1 예상 WARN |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_4turn_halfload | 3.03 | 3 | ±20 % | +1.00 % | PASS | 첫 WARN |
| 정상 시나리오 오경보 건수 (SAFE 유지) | healthy | 0 | 0 |  |  | PASS | 356 행 |
| 합성 파형 독립 재계산 I₂/I₁ (최대 편차, 전 파형) | all | 0.0226 | 0 | 0.005 |  | PASS | 127 파형, 기본파 외 고조파 0 |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_4turn | 45.622 | 45.622 | ±5 % | +0.00 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 158.1 W |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_12turn | 174.36 | 174.37 | ±5 % | -0.00 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 977.46 W |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_16turn | 261.94 | 261.95 | ±5 % | -0.00 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 1523.26 W |

### 열 (통합 모드, 주입 후 권선 온도 — 모델 자기 일관성 ±5 %)

| 시나리오 | 주입 전 [°C] | 끝 [°C] | ΔT 시뮬 | ΔT 에너지 수지 역산 | 편차 | 시뮬 분 | P_loop [W] |
|---|---|---|---|---|---|---|---|
| itsc_4turn | 42.205 | 70.622 | 45.622 | 45.622 | +0.00 % | 300.0 | 158.1 |
| itsc_12turn | 42.211 | 199.364 | 174.364 | 174.366 | -0.00 % | 300.0 | 977.46 |
| itsc_16turn | 42.205 | 286.944 | 261.944 | 261.947 | -0.00 % | 299.9 | 1523.26 |

### 민감도

고유 비대칭 각도 0/90/180° — 4턴 합성 I₂/I₁ 과 판정:

| 각도 | 시나리오 | 합성 I₂/I₁ | 기대 | i2i1 등급 | 종합 |
|---|---|---|---|---|---|
| 0° | itsc_4turn | 0.0726 | 0.0725 | WARN | WARN |
| 0° | itsc_4turn_resistive | 0.0324 | 0.0324 | SAFE | SAFE |
| 0° | healthy | 0.0270 | 0.0270 | SAFE | SAFE |
| 90° | itsc_4turn | 0.0683 | 0.0682 | WARN | WARN |
| 90° | itsc_4turn_resistive | 0.0314 | 0.0314 | SAFE | SAFE |
| 90° | healthy | 0.0270 | 0.0270 | SAFE | SAFE |
| 180° | itsc_4turn | 0.0313 | 0.0312 | SAFE | SAFE |
| 180° | itsc_4turn_resistive | 0.0222 | 0.0222 | SAFE | SAFE |
| 180° | healthy | 0.0270 | 0.0270 | SAFE | SAFE |

부하 50/100 % (4턴): I₂/I₁ 은 부하에 따라 흔들리고 I₂/I_n 은 덜 흔들린다 —

- itsc_4turn (부하 1.0): 시뮬 I₂/I₁ 0.0726, 시뮬 I₂/I_n 0.0750 · LUT 결함분 0.048815, LUT I₂/I_n 0.050428
- itsc_4turn_halfload (부하 0.5): 시뮬 I₂/I₁ 0.0953, 시뮬 I₂/I_n 0.0645 · LUT 결함분 0.074507, LUT I₂/I_n 0.050428

그림: `img/i2i1_timeseries.png`(시계열·판정 띠·주입 시각), `img/sim_vs_analysis_bars.png`(결함 4종 막대), `img/winding_temperature.png`(권선 온도), `img/waveform_spectrum.png`(합성 파형·스펙트럼 — 기본파만, RSH 없음), `img/hud_0*.png`(HUD 합성 4장).

## 4. 근거 사슬 (표시량 → 엔진 → 입력 파일 → 해석 단계 → 등급)

| 표시량 | 엔진 | 입력(sha) | 해석 단계 | 등급 |
|---|---|---|---|---|
| I₂/I₁ (HUD I2/I1, 상태 보드 게이지, 대시보드 추세) | `engine/current_model.CurrentModel.waveform→analyze (phasors_from_wavef…` | M1_mccm_lut_v2.json (c6898c6e8d80); electrical.yaml (296249cc9133) | mccm.py: RMxprt v2m2 등가회로 상수(M400-50A_user60, 철손 데이터시트) → 다중결합 회로(Z₂ 카탈로그 앵커 7.136 Ω, 단락 루프 R_f + μR1) → 격자 160점 LUT; 2D 와전류 FEM(F1) 단락 루프 전… | **등가회로 LUT + 2D FEM 검증 (provisional, fem_verified false) + 고유 비대칭(참고 데이터셋)** |
| I₂/I_n (HUD I2/In, 부하 무관 보조 지표) | `CurrentModel.analyze → i2_over_in = |I₂|/I_n (I_n = electrical.yaml ra…` | M1_mccm_lut_v2.json (c6898c6e8d80); electrical.yaml (296249cc9133); M1.yaml (2d8ca5614eaf) | mccm.py: RMxprt v2m2 등가회로 상수(M400-50A_user60, 철손 데이터시트) → 다중결합 회로(Z₂ 카탈로그 앵커 7.136 Ω, 단락 루프 R_f + μR1) → 격자 160점 LUT; 2D 와전류 FEM(F1) 단락 루프 전… | **등가회로 LUT (표시 전용, 판정 없음)** |
| 상별 RMS Ia/Ib/Ic·전류/정격 비율·상태색 | `CurrentModel._phasors (I₁ 피크 = √2·I_n·부하, I₂ = I₁·(r·e^{jθ}+h)) → wave…` | M1_mccm_lut_v2.json (c6898c6e8d80); M1.yaml (2d8ca5614eaf); electrical.yaml (296249cc9133) | LUT 의 I₂/I₁·위상(θ vs I₁) 만 쓰고 크기는 정격 규약 — LUT 자체 I_a/I_b/I_c(결함 시 I₁ 상승)와는 다름… | **등가회로 LUT + 카탈로그 정격** |
| 단락 루프 전류 I_f (Coil_01_short 발광·입자, 상태 short_loop) | `CurrentModel.short_loop → LUT i_f_A (lut.query 3축 보간)…` | M1_mccm_lut_v2.json (c6898c6e8d80) | mccm.py: RMxprt v2m2 등가회로 상수(M400-50A_user60, 철손 데이터시트) → 다중결합 회로(Z₂ 카탈로그 앵커 7.136 Ω, 단락 루프 R_f + μR1) → 격자 160점 LUT; 2D 와전류 FEM(F1) 단락 루프 전… | **등가회로 MCCM (FEM ±5 % 정합)** |
| 단락 루프 총손실 P_loop_total (권선 노드 추가 손실, HUD basis 줄) | `CurrentModel.loop_loss_W → LUT p_loop_total_W → ThermalModel.step(extr…` | M1_mccm_lut_v2.json (c6898c6e8d80); electrical.yaml (296249cc9133) | I_f²·(R_f + μ·R1_hot) + 단락 턴 동손 (MCCM)… | **등가회로 MCCM** |
| 권선·로터·베어링·프레임 온도(색·HUD·게이지) | `engine/thermal_model.ThermalModel.step (RK4, 9노드 집중정수, losses: copper_…` | thermal.yaml (fe1e7d4e4c2a); M1.yaml (2d8ca5614eaf) | 22 kW 보정값을 손실비 P(1−η)/η·프레임 치수비로 스케일(engine/motor_library.thermal_cfg, thermal.yaml reference) — Maxwell 근거 아님… | **열회로 모델(낙관 가능성, 실측 전 보정 불가)** |
| 판정 SAFE/WARN/DANGER·원인 신호·advisory | `engine/thresholds.Judge.update (worst-of, 히스테리시스 5 %, 지속 3 s, provisio…` | thresholds.yaml (9158581eb3d8) | I₂/I₁ 0.05/0.10(참고 데이터셋 provisional), 전류/정격 0.85~1.10/1.25·0.50, 온도 F종·그리스, 진동 ISO 10816-1 Class I… | **임계값(표준·참고 데이터셋) — 해석값 아님** |
| 정격점(카탈로그 4.73 A·pf 0.79·η 0.895·1760 rpm) — 모터 모델 근거 표 | `config/motors/M1.yaml (motor_library.motor_spec)…` | M1.yaml (2d8ca5614eaf); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_v2m2.json (07736423faa1); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\eddy2d\summary.json (0fb986f232d1); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\f7_iec_tolerance.json (f99af4b76654) | RMxprt v2m2 정합 4.670 A·0.791·89.58 % / 2D FEM lite 4.90 A·0.740 / IEC 60034-1 허용차… | **카탈로그 (RMxprt 정합·FEM 참고)** |
| 기동 특성(잠김 전류·토크비) — 근거 표 | `표시 전용 (엔진 미사용)…` | M1.yaml (2d8ca5614eaf); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_v2m2.json (07736423faa1); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\f2_corrections.json (5e21ad5b5d91) | 카탈로그 6.5×/2.1× ↔ RMxprt 8.24×/3.09× ↔ 2D FEM + F2 스큐 보정 7.43×/2.34×… | **카탈로그 / RMxprt / 2D FEM 보정** |
| 등가회로 상수(R1·R2′·X1·X2′·Xm·Z₂) — 근거 표 | `표시 전용…` | C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_v2m2.json (07736423faa1); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\rmxprt_temp_sweep.json (21fe315328ce); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\magnetizing_curve_2d.json (b0f93df33e1b); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\eddy2d\summary.json (0fb986f232d1); C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링\maxwell\results\inductance_matrix_2d.json (a36126216cd3) | RMxprt v2m2 (R1 20/95 °C 온도 스윕) ↔ 2D FEM X_total 95.6 Ω(자화 곡선 k=1) ↔ 역상 Z₂ 5.33(FEM)/5.97(보정) vs 앵커 7.136… | **RMxprt 정합 / 2D FEM** |
| 기계 결함(DE 베어링·오정렬·팬·브레이크·과부하) 진동·kurtosis·고주파 지표 | `engine/fault_injector (결함별 상수) + thermal.yaml faults(손실 배율·열저항)…` | thermal.yaml (fe1e7d4e4c2a); thresholds.yaml (9158581eb3d8) | Maxwell 근거 없음 — 진동 상수(시나리오), ISO 10816-1 Class I(표준), 베어링 지표 AI Hub 참고 데이터셋… | **표준 / 참고 데이터셋 / 시나리오 상수 (해석값 아님)** |

전체 문장은 `traceability.md`. 해석 파일 sha256 은 `analysis_reference.json inputs` 에 있다(LUT sha 일치: True).

## 5. 한계

- 합성 신호(엔진 페이저 합성) — 실측 아님
- 고유 비대칭 0.027 은 건전 하한 가정(AI Hub L-EF-04·R-EF-05 중앙값; L-SF-04 실측 p95 0.1005 는 품질 부적합)
- Z₂ 카탈로그 앵커 7.136 Ω vs FEM 5.97 Ω → LUT I₂ 불확실성 +20 %
- 2D lite: 무스큐·분산 결함·단순화 기하(학생판), 시간 파형·RSH 없음
- 열 모델은 22 kW 기준 스케일 — M1 에서 낙관적일 수 있음(실측 전 보정 불가)
- 기계 결함(베어링·오정렬·팬·브레이크)은 Maxwell 근거 없음 — 진동·베어링 상수(표준/AI Hub 참고)
- 합성 신호라 전류 과도가 없다: 판정 지연은 오직 '3 s 지속 규칙'이다. 실모터에서는 창 길이·필터·돌입이 더해진다.
- 열 ΔT 대조는 '같은 모델의 정상 상태 해'와의 자기 일관성이다(22 kW 보정값 스케일, 실측 아님).

## 6. 이 보고서가 증명하는 것 / 증명하지 않는 것

**증명하는 것**
- 화면·HUD·로그의 전기 결함 숫자가 해석 파일(RMxprt v2m2 → MCCM/LUT v2 → 2D FEM F1 정합)에서 어떻게 나왔는지 — 같은 파일 sha 로 추적되고, 값이 ±1 %(손실 ±2 %) 안에서 재현된다.
- 엔진의 대칭 성분 계산이 독립 구현(엔진 비의존 Fortescue·DFT)과 ±0.5 % 안에서 같다.
- 임계값·지속 규칙이 설정대로 동작한다(예상 판정·탐지 지연 일치, 정상 오경보 0).
- 열 모델이 자기 일관적이다(주입 후 정상 상태 ΔT ↔ 손실·열저항 역산).
**증명하지 않는 것**
- 실모터와의 일치. 고유 비대칭 0.027·임계값 0.05/0.10 은 참고 데이터셋 가정이고, 실측 기준선(P1 `tools/baseline_capture.py`) 전까지 provisional 이다.
- 2D lite FEM 의 절대 정확도(학생판·단순화 기하·무스큐), Z₂ 앵커 불확실성(+20 %), 열 모델의 M1 절대 온도.
- 기계 결함(베어링·오정렬·팬·브레이크)의 해석 근거 — 없다. 진동·베어링 상수와 표준·참고 데이터셋 출처만 표기한다.
