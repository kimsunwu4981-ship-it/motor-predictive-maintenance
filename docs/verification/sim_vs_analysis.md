# 시뮬 ↔ 해석 대조표 (자동 생성)

생성 2026-10-21 23:25:51 · `motor_dt_viz/tools/verify/sim_vs_analysis.py` · 기준 `motor_dt_viz/data/electrical/analysis_reference.json` · **PASS 89/89**

| 항목 | 시나리오 | 시뮬(로그) | 해석 기준 | 허용 | 편차 | 판정 | 비고 | 출처 |
|---|---|---|---|---|---|---|---|---|
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | healthy | 0 % | 1 |  |  | PASS | n=88 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | healthy | 0 | 0 | ±1 % |  | PASS | 합성 0.02700 ∠0.0°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | healthy | 0.027 | 0.027~0.027 |  |  | PASS | 기대(각도 0°) 0.027 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | healthy | 0.027 | 0.027 | ±1 % | +0.000 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | healthy | 0 | 0 | ±1 % |  | PASS | 시뮬 I₁ 4.6946 A (LUT 정상분 RMS, D3), LUT I₁ 4.69464 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | healthy | 4.6946 A | 4.6946 | ±1 % | +0.000 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | healthy | 0.0268 | 0.026798 | ±1 % | +0.007 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | healthy | 2.6806 % | 2.681 | ±2 % | -0.015 % | PASS | LUT 자체 0.0 % (LUT I₁ 기준) | LUT + inherent |
| 판정 (장면 끝 종합 상태) vs 예상 | healthy | SAFE | SAFE |  |  | PASS | 원인 - 0.0 · i2i1 예상 SAFE | thresholds.yaml |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn | 0 % | 1 |  |  | PASS | n=87 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn | 0.048965 | 0.048815 | ±1 % | +0.307 % | PASS | 합성 0.07262 ∠23.2°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn | 0.07262 | 0.021815~0.075815 |  |  | PASS | 기대(각도 0°) 0.072474 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn | 0.07262 | 0.072474 | ±1 % | +0.201 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn | 0.05059 | 0.050428 | ±1 % | +0.321 % | PASS | 시뮬 I₁ 4.8870 A (LUT 정상분 RMS, D3), LUT I₁ 4.88627 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn | 4.887 A | 4.8863 | ±1 % | +0.014 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn | 0.07503 | 0.074868 | ±1 % | +0.216 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn | 6.572 % | 6.5603 | ±2 % | +0.178 % | PASS | LUT 자체 4.4846 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn | 34.381 A | 34.347 | ±1 % | +0.098 % | PASS | FEM(F1 보정) 35.16 A 참고 | mccm_results.json |
| I_f [A] vs 2D FEM(F1 보정) — 참고 열 | itsc_4turn | 34.381 A | 35.155 | ±5 % | -2.202 % | PASS | 참고(±5 % MCCM↔FEM 정합 범위) | f2_corrections.json F1 |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn | 158.1 W | 157.54 | ±2 % | +0.356 % | PASS | 공식(루프 저항항만) 157.5 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn | WARN | WARN |  |  | PASS | 원인 i2i1 0.0726 · i2i1 예상 WARN | thresholds.yaml |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_4turn | 2.98 s | 3 | ±20 % | -0.667 % | PASS | 첫 WARN | thresholds.yaml persistence_s |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_12turn | 0 % | 1 |  |  | PASS | n=86 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_12turn | 0.24552 | 0.24551 | ±1 % | +0.001 % | PASS | 합성 0.26958 ∠25.6°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_12turn | 0.26958 | 0.21851~0.27251 |  |  | PASS | 기대(각도 0°) 0.269578 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_12turn | 0.26958 | 0.26958 | ±1 % | +0.001 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_12turn | 0.30745 | 0.30745 | ±1 % | +0.001 % | PASS | 시뮬 I₁ 5.9233 A (LUT 정상분 RMS, D3), LUT I₁ 5.92325 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_12turn | 5.9233 A | 5.9233 | ±1 % | +0.000 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_12turn | 0.33759 | 0.33759 | ±1 % | +0.001 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_12turn | 22.546 % | 22.546 | ±2 % | +0.001 % | PASS | LUT 자체 21.067 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_12turn | 69.803 A | 69.803 | ±1 % | +0.000 % | PASS |  | mccm_results.json |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_12turn | 977.46 W | 977.46 | ±2 % | -0.000 % | PASS | 공식(루프 저항항만) 977.5 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_12turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.2696 · i2i1 예상 DANGER | thresholds.yaml |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_12turn | 3.03 s | 3 | ±20 % | +1.000 % | PASS | 첫 DANGER | thresholds.yaml persistence_s |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | overload | 0 % | 1 |  |  | PASS | n=86 | state.csv |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | voltage_unbalance | 0 % | 1 |  |  | PASS | n=91 | state.csv |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | single_phasing | 0 % | 1 |  |  | PASS | n=89 | state.csv |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | no_load | 0 % | 1 |  |  | PASS | n=87 | state.csv |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_8turn | 0 % | 1 |  |  | PASS | n=88 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_8turn | 0.1441 | 0.14425 | ±1 % | -0.107 % | PASS | 합성 0.16757 ∠27.2°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_8turn | 0.16757 | 0.11725~0.17125 |  |  | PASS | 기대(각도 0°) 0.167724 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_8turn | 0.16757 | 0.16772 | ±1 % | -0.092 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_8turn | 0.16227 | 0.16247 | ±1 % | -0.120 % | PASS | 시뮬 I₁ 5.3266 A (LUT 정상분 RMS, D3), LUT I₁ 5.32735 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_8turn | 5.3266 A | 5.3274 | ±1 % | -0.013 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_8turn | 0.18871 | 0.18891 | ±1 % | -0.104 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_8turn | 14.341 % | 14.353 | ±2 % | -0.081 % | PASS | LUT 자체 12.9454 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_8turn | 510.91 W | 511.47 | ±2 % | -0.110 % | PASS | 공식(루프 저항항만) 511.5 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_8turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.1676 · i2i1 예상 DANGER | thresholds.yaml |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_8turn | 2.95 s | 3 | ±20 % | -1.667 % | PASS | 첫 DANGER | thresholds.yaml persistence_s |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_16turn | 0 % | 1 |  |  | PASS | n=87 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_16turn | 0.33785 | 0.33774 | ±1 % | +0.033 % | PASS | 합성 0.36253 ∠23.1°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_16turn | 0.36253 | 0.31074~0.36474 |  |  | PASS | 기대(각도 0°) 0.362417 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_16turn | 0.36253 | 0.36242 | ±1 % | +0.031 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_16turn | 0.47377 | 0.47352 | ±1 % | +0.054 % | PASS | 시뮬 I₁ 6.6329 A (LUT 정상분 RMS, D3), LUT I₁ 6.63155 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_16turn | 6.6329 A | 6.6315 | ±1 % | +0.020 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_16turn | 0.50838 | 0.50811 | ±1 % | +0.052 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_16turn | 29.547 % | 29.539 | ±2 % | +0.026 % | PASS | LUT 자체 27.5857 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_16turn | 80.643 A | 80.631 | ±1 % | +0.016 % | PASS |  | mccm_results.json |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_16turn | 1523.3 W | 1522.2 | ±2 % | +0.067 % | PASS | 공식(루프 저항항만) 1522.2 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_16turn | DANGER | DANGER |  |  | PASS | 원인 i2i1 0.3625 · i2i1 예상 DANGER | thresholds.yaml |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn_resistive | 0 % | 1 |  |  | PASS | n=86 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn_resistive | 0.006542 | 0.006511 | ±1 % | +0.476 % | PASS | 합성 0.03244 ∠7.0°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn_resistive | 0.03244 | 0.020489~0.033511 |  |  | PASS | 기대(각도 0°) 0.032413 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn_resistive | 0.03244 | 0.032413 | ±1 % | +0.083 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn_resistive | 0.006527 | 0.006496 | ±1 % | +0.477 % | PASS | 시뮬 I₁ 4.7191 A (LUT 정상분 RMS, D3), LUT I₁ 4.719 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn_resistive | 4.7191 A | 4.719 | ±1 % | +0.002 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn_resistive | 0.03236 | 0.032338 | ±1 % | +0.068 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn_resistive | 3.1933 % | 3.1903 | ±2 % | +0.094 % | PASS | LUT 자체 0.6019 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn_resistive | 4.431 A | 4.4244 | ±1 % | +0.149 % | PASS | FEM(F1 보정) 4.56 A 참고 | mccm_results.json |
| I_f [A] vs 2D FEM(F1 보정) — 참고 열 | itsc_4turn_resistive | 4.431 A | 4.5647 | ±5 % | -2.930 % | PASS | 참고(±5 % MCCM↔FEM 정합 범위) | f2_corrections.json F1 |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn_resistive | 20.32 W | 20.232 | ±2 % | +0.435 % | PASS | 공식(루프 저항항만) 20.2 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn_resistive | SAFE | SAFE |  |  | PASS | 원인 - 0.0 · i2i1 예상 SAFE | thresholds.yaml |
| 정상 상태 (I₂/I₁ 마지막 5 s 표준편차 < 1 %) | itsc_4turn_halfload | 0 % | 1 |  |  | PASS | n=87 | state.csv |
| I₂/I₁ 결함분 (합성 − 고유 비대칭 페이저) | itsc_4turn_halfload | 0.074726 | 0.074507 | ±1 % | +0.294 % | PASS | 합성 0.09529 ∠34.8°, 고유 0.027 ∠0° | LUT v2 격자 (mccm_results) |
| I₂/I₁ 합성값 (범위 |r−h| ~ r+h) | itsc_4turn_halfload | 0.09529 | 0.047507~0.10151 |  |  | PASS | 기대(각도 0°) 0.095076 | LUT + inherent |
| I₂/I₁ 합성값 vs 기대(각도 0°) | itsc_4turn_halfload | 0.09529 | 0.095076 | ±1 % | +0.225 % | PASS |  | LUT + inherent |
| I₂/I_n 결함분 (I₂_fault/I_n, 시뮬 I₁ 기준) vs LUT I₂/I_n | itsc_4turn_halfload | 0.050586 | 0.050428 | ±1 % | +0.313 % | PASS | 시뮬 I₁ 3.2020 A (LUT 정상분 RMS, D3), LUT I₁ 3.20136 A | LUT v2 |
| I₁ 정상분 [A] vs LUT I₁ | itsc_4turn_halfload | 3.202 A | 3.2014 | ±1 % | +0.019 % | PASS | D3: 결함 시 상승(격자 보간) | LUT v2 |
| I₂/I_n 표시값 vs 시뮬 기대(합성×부하) | itsc_4turn_halfload | 0.06451 | 0.064349 | ±1 % | +0.250 % | PASS | 표시값 자체의 일관성 | LUT + inherent |
| 상 불평형 max dev [%] vs LUT 합성 기대 | itsc_4turn_halfload | 8.7364 % | 8.7152 | ±2 % | +0.243 % | PASS | LUT 자체 7.3601 % (LUT I₁ 기준) | LUT + inherent |
| 단락 루프 전류 I_f [A] vs MCCM | itsc_4turn_halfload | 34.381 A | 34.347 | ±1 % | +0.098 % | PASS |  | mccm_results.json |
| 단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM) | itsc_4turn_halfload | 158.1 W | 157.54 | ±2 % | +0.356 % | PASS | 공식(루프 저항항만) 157.5 W | mccm_results.json |
| 판정 (장면 끝 종합 상태) vs 예상 | itsc_4turn_halfload | WARN | WARN |  |  | PASS | 원인 i2i1 0.0953 · i2i1 예상 WARN | thresholds.yaml |
| 탐지 지연 [s] (주입 → 첫 상향, 지속 3 s 규칙) | itsc_4turn_halfload | 3.02 s | 3 | ±20 % | +0.667 % | PASS | 첫 WARN | thresholds.yaml persistence_s |
| 정상 시나리오 오경보 건수 (SAFE 유지) | healthy | 0 건 | 0 |  |  | PASS | 353 행 | state.csv |
| 합성 파형 독립 재계산 I₂/I₁ (최대 편차, 전 파형) | all | 0.0226 % | 0 | 0.005 |  | PASS | 213 파형, 기본파 외 고조파 0 | recompute_i2i1.py |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_4turn | 45.622 °C | 45.622 | ±5 % | +0.000 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 158.1 W | thermal.yaml + LUT P_loop (모델 자기 일관성) |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_12turn | 174.36 °C | 174.37 | ±5 % | -0.001 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 977.46 W | thermal.yaml + LUT P_loop (모델 자기 일관성) |
| 권선 온도 상승 ΔT [°C] 주입 후 정상 상태 vs 열 모델 에너지 수지 역산 | itsc_16turn | 261.94 °C | 261.95 | ±5 % | -0.001 % | PASS | 시뮬 시간 300 분 후 (τ 권선 ≈ 36 분), 루프 손실 1523.26 W | thermal.yaml + LUT P_loop (모델 자기 일관성) |

## 판정 이벤트·탐지 지연

| 시나리오 | 주입 [s] | 첫 WARN [s] | 첫 DANGER [s] | 지연 [s] | 장면 끝 | 원인 | i2i1 예상 |
|---|---|---|---|---|---|---|---|
| healthy | 0.0 |  |  | {} | SAFE | - | SAFE |
| itsc_4turn | 20.0 | 22.982 |  | {'WARN': 2.98} | WARN | i2i1 | WARN |
| itsc_12turn | 45.0 |  | 48.029 | {'DANGER': 3.03} | DANGER | i2i1 | DANGER |
| itsc_8turn | 165.0 |  | 167.95 | {'DANGER': 2.95} | DANGER | i2i1 | DANGER |
| itsc_16turn | 185.0 |  |  | {} | DANGER | i2i1 | DANGER |
| itsc_4turn_resistive | 205.0 |  |  | {} | SAFE | - | SAFE |
| itsc_4turn_halfload | 225.0 | 228.02 |  | {'WARN': 3.02} | WARN | i2i1 | WARN |
| itsc_4turn (integrated thermal) | 20.0 | 23.0→WARN(i2i1) | | | WARN | i2i1 | |
| itsc_12turn (integrated thermal) | 20.0 | 21.6→WARN(temperature); 23.1→DANGER(i2i1) | | | DANGER | i2i1 | |
| itsc_16turn (integrated thermal) | 20.0 | 20.8→WARN(temperature); 22.2→DANGER(temperature); 23.1→DANGER(i2i1) | | | DANGER | i2i1 | |

## 독립 재계산 (합성 파형 1 s · 2 kHz, 엔진 비의존 대칭 성분)

| 실행 | 파일 | 케이스 | 재계산 I₂/I₁ | 엔진 | 편차 | 고조파 h3/h1 | 판정 |
|---|---|---|---|---|---|---|---|
| a0 | waveform_0000.00_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0000.01_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0000.07_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0000.08_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0020.00_post_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0020.00_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0020.04_post_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0020.04_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0020.05_post_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0020.05_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0045.02_post_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0045.02_pre_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0045.03_post_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0045.03_pre_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0045.06_post_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0045.06_pre_itsc_4turn.csv | itsc_4turn | 0.072623 | 0.07262 | +0.0041 % | 0.001107 | PASS |
| a0 | waveform_0075.01_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0075.01_pre_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0075.04_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0075.04_pre_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0075.06_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0075.06_pre_itsc_12turn.csv | itsc_12turn | 0.269578 | 0.26958 | -0.0007 % | 0.000933 | PASS |
| a0 | waveform_0095.00_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0095.00_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0095.01_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0095.01_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0095.04_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0095.04_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0120.02_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0120.02_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0120.03_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0120.03_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0120.06_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0120.06_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a0 | waveform_0145.00_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0145.00_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0145.01_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0145.01_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0145.03_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0145.03_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0145.05_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0145.05_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a0 | waveform_0165.03_post_itsc_8turn.csv | itsc_8turn | 0.167573 | 0.16757 | +0.0018 % | 0.001003 | PASS |
| a0 | waveform_0165.03_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0165.04_post_itsc_8turn.csv | itsc_8turn | 0.167573 | 0.16757 | +0.0018 % | 0.001003 | PASS |
| a0 | waveform_0165.04_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0165.05_post_itsc_8turn.csv | itsc_8turn | 0.167573 | 0.16757 | +0.0018 % | 0.001003 | PASS |
| a0 | waveform_0165.05_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a0 | waveform_0185.02_post_itsc_16turn.csv | itsc_16turn | 0.362533 | 0.36253 | +0.0008 % | 0.000901 | PASS |
| a0 | waveform_0185.02_pre_itsc_8turn.csv | itsc_8turn | 0.167573 | 0.16757 | +0.0018 % | 0.001003 | PASS |
| a0 | waveform_0205.00_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0205.00_pre_itsc_16turn.csv | itsc_16turn | 0.362533 | 0.36253 | +0.0008 % | 0.000901 | PASS |
| a0 | waveform_0205.01_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0205.01_pre_itsc_16turn.csv | itsc_16turn | 0.362533 | 0.36253 | +0.0008 % | 0.000901 | PASS |
| a0 | waveform_0205.05_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0205.05_pre_itsc_16turn.csv | itsc_16turn | 0.362533 | 0.36253 | +0.0008 % | 0.000901 | PASS |
| a0 | waveform_0205.06_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0205.06_pre_itsc_16turn.csv | itsc_16turn | 0.362533 | 0.36253 | +0.0008 % | 0.000901 | PASS |
| a0 | waveform_0225.01_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0225.01_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0225.02_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0225.02_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0225.03_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0225.03_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0225.06_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0225.06_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.032438 | 0.03244 | -0.0062 % | 0.001166 | PASS |
| a0 | waveform_0245.01_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.01_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.02_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.02_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.03_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.03_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.04_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a0 | waveform_0245.04_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.095294 | 0.09529 | +0.0042 % | 0.001046 | PASS |
| a90 | waveform_0000.00_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0000.01_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0000.07_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0000.09_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0020.01_post_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0020.01_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0020.04_post_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0020.04_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0020.06_post_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0020.06_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0045.01_post_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0045.01_pre_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0045.04_post_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0045.04_pre_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0045.05_post_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0045.05_pre_itsc_4turn.csv | itsc_4turn | 0.068337 | 0.06834 | -0.0044 % | 0.001038 | PASS |
| a90 | waveform_0075.01_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0075.01_pre_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0075.03_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0075.03_pre_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0075.04_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0075.04_pre_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0075.05_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0075.05_pre_itsc_12turn.csv | itsc_12turn | 0.259428 | 0.25943 | -0.0008 % | 0.000871 | PASS |
| a90 | waveform_0095.02_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0095.02_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0095.04_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0095.04_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0095.05_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0095.05_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0120.01_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a90 | waveform_0120.01_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0120.03_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a90 | waveform_0120.03_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0120.05_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a90 | waveform_0120.05_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a90 | waveform_0145.00_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0145.00_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a90 | waveform_0145.03_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0145.03_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a90 | waveform_0165.00_post_itsc_8turn.csv | itsc_8turn | 0.160109 | 0.16011 | -0.0006 % | 0.000937 | PASS |
| a90 | waveform_0165.00_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0165.03_post_itsc_8turn.csv | itsc_8turn | 0.160109 | 0.16011 | -0.0006 % | 0.000937 | PASS |
| a90 | waveform_0165.03_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0165.08_post_itsc_8turn.csv | itsc_8turn | 0.160109 | 0.16011 | -0.0006 % | 0.000937 | PASS |
| a90 | waveform_0165.08_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001106 | PASS |
| a90 | waveform_0185.01_post_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0185.01_pre_itsc_8turn.csv | itsc_8turn | 0.160109 | 0.16011 | -0.0006 % | 0.000937 | PASS |
| a90 | waveform_0185.03_post_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0185.03_pre_itsc_8turn.csv | itsc_8turn | 0.160109 | 0.16011 | -0.0006 % | 0.000937 | PASS |
| a90 | waveform_0205.03_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0205.03_pre_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0205.04_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0205.04_pre_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0205.05_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0205.05_pre_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0205.06_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0205.06_pre_itsc_16turn.csv | itsc_16turn | 0.350064 | 0.35006 | +0.0011 % | 0.000842 | PASS |
| a90 | waveform_0225.03_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0225.03_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0225.05_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0225.05_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.031407 | 0.03141 | -0.0096 % | 0.001096 | PASS |
| a90 | waveform_0245.03_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.03_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.04_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.04_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.05_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.05_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.07_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a90 | waveform_0245.07_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.096180 | 0.09618 | +0.0000 % | 0.000976 | PASS |
| a180 | waveform_0000.00_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0000.07_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0000.08_post_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0020.00_post_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0020.00_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0020.02_post_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0020.02_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0020.03_post_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0020.03_pre_healthy.csv | healthy | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0045.01_post_itsc_12turn.csv | itsc_12turn | 0.222124 | 0.22212 | +0.0018 % | 0.000922 | PASS |
| a180 | waveform_0045.01_pre_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0045.02_post_itsc_12turn.csv | itsc_12turn | 0.222124 | 0.22212 | +0.0018 % | 0.000922 | PASS |
| a180 | waveform_0045.02_pre_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0045.05_post_itsc_12turn.csv | itsc_12turn | 0.222124 | 0.22212 | +0.0018 % | 0.000922 | PASS |
| a180 | waveform_0045.05_pre_itsc_4turn.csv | itsc_4turn | 0.031298 | 0.03130 | -0.0064 % | 0.001103 | PASS |
| a180 | waveform_0075.02_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0075.02_pre_itsc_12turn.csv | itsc_12turn | 0.222124 | 0.22212 | +0.0018 % | 0.000922 | PASS |
| a180 | waveform_0075.05_post_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0075.05_pre_itsc_12turn.csv | itsc_12turn | 0.222124 | 0.22212 | +0.0018 % | 0.000922 | PASS |
| a180 | waveform_0095.02_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0095.02_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0095.03_post_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0095.03_pre_overload.csv | overload | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0120.00_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0120.00_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0120.03_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0120.03_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0120.04_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0120.04_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0120.05_post_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0120.05_pre_voltage_unbalance.csv | voltage_unbalance | 0.059508 | 0.05951 | -0.0034 % | 0.001086 | PASS |
| a180 | waveform_0145.02_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0145.02_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0145.04_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0145.04_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0145.05_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0145.05_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0145.06_post_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0145.06_pre_single_phasing.csv | single_phasing | 0.479167 | 0.47917 | -0.0006 % | 0.001175 | PASS |
| a180 | waveform_0165.01_post_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0165.01_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0165.03_post_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0165.03_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0165.04_post_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0165.04_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0165.06_post_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0165.06_pre_no_load.csv | no_load | 0.027000 | 0.02700 | +0.0000 % | 0.001176 | PASS |
| a180 | waveform_0185.03_post_itsc_16turn.csv | itsc_16turn | 0.313563 | 0.31356 | +0.0010 % | 0.000889 | PASS |
| a180 | waveform_0185.03_pre_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0185.05_post_itsc_16turn.csv | itsc_16turn | 0.313563 | 0.31356 | +0.0010 % | 0.000889 | PASS |
| a180 | waveform_0185.05_pre_itsc_8turn.csv | itsc_8turn | 0.122089 | 0.12209 | -0.0008 % | 0.000995 | PASS |
| a180 | waveform_0205.00_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0205.00_pre_itsc_16turn.csv | itsc_16turn | 0.313563 | 0.31356 | +0.0010 % | 0.000889 | PASS |
| a180 | waveform_0205.02_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0205.02_pre_itsc_16turn.csv | itsc_16turn | 0.313563 | 0.31356 | +0.0010 % | 0.000889 | PASS |
| a180 | waveform_0205.04_post_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0205.04_pre_itsc_16turn.csv | itsc_16turn | 0.313563 | 0.31356 | +0.0010 % | 0.000889 | PASS |
| a180 | waveform_0225.00_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0225.00_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0225.02_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0225.02_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0225.03_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0225.03_pre_itsc_4turn_resistive.csv | itsc_4turn_resistive | 0.022165 | 0.02217 | -0.0226 % | 0.001165 | PASS |
| a180 | waveform_0245.02_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0245.02_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0245.04_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0245.04_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0245.05_post_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |
| a180 | waveform_0245.05_pre_itsc_4turn_halfload.csv | itsc_4turn_halfload | 0.059550 | 0.05955 | +0.0000 % | 0.001039 | PASS |

## 민감도

### 고유 비대칭 각도 0/90/180° (4턴·저항성 4턴·정상)

| 각도 | 시나리오 | 합성 I₂/I₁ | 기대 | 편차 | i2i1 등급 | 종합 | 원인 |
|---|---|---|---|---|---|---|---|
| 0° | itsc_4turn | 0.07262 | 0.072474 | 0.201 % | WARN | WARN | i2i1 |
| 0° | itsc_4turn_resistive | 0.03244 | 0.032413 | 0.083 % | SAFE | SAFE | - |
| 0° | healthy | 0.02700 | 0.027 | 0 % | SAFE | SAFE | - |
| 90° | itsc_4turn | 0.06834 | 0.068193 | 0.216 % | WARN | WARN | i2i1 |
| 90° | itsc_4turn_resistive | 0.03141 | 0.031386 | 0.076 % | SAFE | SAFE | - |
| 90° | healthy | 0.02700 | 0.027 | 0 % | SAFE | SAFE | - |
| 180° | itsc_4turn | 0.03130 | 0.031167 | 0.427 % | SAFE | SAFE | - |
| 180° | itsc_4turn_resistive | 0.02217 | 0.022185 | -0.068 % | SAFE | SAFE | - |
| 180° | healthy | 0.02700 | 0.027 | 0 % | SAFE | SAFE | - |

### 부하 50 % / 100 % (4턴): I₂/I₁ 은 부하에 흔들리고 I₂/I_n 은 덜 흔들린다

| 시나리오 | 부하 | 시뮬 I₂/I₁(합성) | 시뮬 I₂/I_n | LUT 결함분 I₂/I₁ | LUT I₂/I_n |
|---|---|---|---|---|---|
| itsc_4turn | 1.0 | 0.07262 | 0.07503 | 0.048815 | 0.050428 |
| itsc_4turn_halfload | 0.5 | 0.09529 | 0.06451 | 0.074507 | 0.050428 |

## 열 (통합 모드, 주입 후 권선 온도)

| 시나리오 | 주입 전 [°C] | 끝 [°C] | ΔT 시뮬 | ΔT 정상 상태 역산 | 편차 | 시뮬 분 | P_loop [W] | 끝 상태 |
|---|---|---|---|---|---|---|---|---|
| itsc_4turn | 42.205 | 70.622 | 45.622 | 45.622 | +0.00 % | 300.0 | 158.1 | WARN (i2i1) |
| itsc_12turn | 42.211 | 199.364 | 174.364 | 174.366 | -0.00 % | 300.0 | 977.46 | DANGER (i2i1) |
| itsc_16turn | 42.205 | 286.944 | 261.944 | 261.947 | -0.00 % | 299.9 | 1523.26 | DANGER (i2i1) |
