# 베어링 지표 교체 전후 fleet 판정 비교 (M1~M5 × 기계·전기)

- 전: `logs\fleet_before` (bearing_index = 베어링 결함 손실 배율 대체값, 경고 2배 / 위험 5배)
- 후: `logs\fleet` (bearing_kurtosis 3.5/4.0 + bearing_hf_ratio 1.5/2.5, 종합 = 둘 중 나쁜 쪽; 시뮬레이션 등가값은 config/thermal.yaml)
- 두 로그 모두 `tools/run_fleet.py`(엔진 배치)·`engine/thresholds.py` 판정. 온도·전류·진동 수치는 바뀌지 않았고 베어링 신호와 그에 따른 종합·원인만 다르다.
- 숫자는 전부 두 로그의 `status_fleet.csv`·`meta.json`에서 왔다 (tools/fleet_compare.py).

## 기계 모드 — 장면 끝 상태 (원인 신호 값)

| 모터 | 장면 | 전 | 후 | 변화 |
|---|---|---|---|---|
| M1 | normal | 안전 (-) | 안전 (-) | — |
| M1 | bearing_fault | 위험 (vibration 4.8) | 위험 (bearing_kurtosis 50) | **변경** |
| M1 | misalignment | 경고 (vibration 3.6) | 경고 (vibration 3.6) | — |
| M1 | fan_failure | 안전 (-) | 안전 (-) | — |
| M1 | brake_drag | 경고 (vibration 2) | 경고 (vibration 2) | — |
| M1 | overload | 경고 (vibration 2.2) | 경고 (vibration 2.2) | — |
| M1 | cooldown | 안전 (-) | 안전 (-) | — |
| M2 | normal | 안전 (-) | 안전 (-) | — |
| M2 | bearing_fault | 위험 (vibration 4.8) | 위험 (bearing_kurtosis 50) | **변경** |
| M2 | misalignment | 경고 (vibration 3.6) | 경고 (vibration 3.6) | — |
| M2 | fan_failure | 안전 (-) | 안전 (-) | — |
| M2 | brake_drag | 경고 (vibration 2) | 경고 (vibration 2) | — |
| M2 | overload | 경고 (vibration 2.2) | 경고 (vibration 2.2) | — |
| M2 | cooldown | 안전 (-) | 안전 (-) | — |
| M3 | normal | 안전 (-) | 안전 (-) | — |
| M3 | bearing_fault | 위험 (temperature/bearing_de 114.9) | 위험 (bearing_kurtosis 50) | **변경** |
| M3 | misalignment | 경고 (vibration 3.6) | 경고 (vibration 3.6) | — |
| M3 | fan_failure | 경고 (temperature/stator_core 75.1) | 경고 (temperature/stator_core 75.1) | — |
| M3 | brake_drag | 경고 (temperature/shaft 104.4) | 경고 (temperature/shaft 104.4) | — |
| M3 | overload | 경고 (vibration 2.2) | 경고 (vibration 2.2) | — |
| M3 | cooldown | 경고 (temperature/shaft 71.6) | 경고 (temperature/shaft 71.6) | — |
| M4 | normal | 안전 (-) | 안전 (-) | — |
| M4 | bearing_fault | 위험 (temperature/bearing_de 122.2) | 위험 (bearing_kurtosis 50) | **변경** |
| M4 | misalignment | 경고 (vibration 3.6) | 경고 (vibration 3.6) | — |
| M4 | fan_failure | 경고 (temperature/stator_core 79.1) | 경고 (temperature/stator_core 79.1) | — |
| M4 | brake_drag | 경고 (temperature/shaft 109.9) | 경고 (temperature/shaft 109.9) | — |
| M4 | overload | 경고 (vibration 2.2) | 경고 (vibration 2.2) | — |
| M4 | cooldown | 경고 (temperature/shaft 78.4) | 경고 (temperature/shaft 78.4) | — |
| M5 | normal | 안전 (-) | 안전 (-) | — |
| M5 | bearing_fault | 위험 (temperature/bearing_de 135.7) | 위험 (bearing_kurtosis 50) | **변경** |
| M5 | misalignment | 경고 (vibration 3.6) | 경고 (vibration 3.6) | — |
| M5 | fan_failure | 경고 (temperature/stator_core 86.6) | 경고 (temperature/stator_core 86.6) | — |
| M5 | brake_drag | 위험 (temperature/shaft 121.1) | 위험 (temperature/shaft 121.1) | — |
| M5 | overload | 경고 (vibration 2.2) | 경고 (vibration 2.2) | — |
| M5 | cooldown | 경고 (temperature/shaft 88) | 경고 (temperature/shaft 88) | — |

### 기계 모드 — 상태 시간 점유율·변경 행

| 모터 | 행 | 종합 상태 점유율 전 | 종합 상태 점유율 후 | 종합 변경 행 | 원인 변경 행 | 베어링 등급 전 (bearing_index) | 베어링 종합 후 | 후 kurtosis | 후 고주파 배율 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 741 | 안전 43 % / 경고 39 % / 위험 17 % | 안전 43 % / 경고 39 % / 위험 17 % | 0 | 128 | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % |
| M2 | 741 | 안전 36 % / 경고 47 % / 위험 17 % | 안전 36 % / 경고 47 % / 위험 17 % | 0 | 128 | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % |
| M3 | 741 | 안전 14 % / 경고 68 % / 위험 18 % | 안전 14 % / 경고 68 % / 위험 18 % | 0 | 128 | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % |
| M4 | 741 | 안전 14 % / 경고 68 % / 위험 18 % | 안전 14 % / 경고 68 % / 위험 18 % | 0 | 128 | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % |
| M5 | 741 | 안전 14 % / 경고 59 % / 위험 27 % | 안전 14 % / 경고 59 % / 위험 27 % | 0 | 128 | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % | 안전 69 % / 경고 13 % / 위험 17 % |

## 전기 모드 — 장면 끝 상태 (원인 신호 값)

| 모터 | 장면 | 전 | 후 | 변화 |
|---|---|---|---|---|
| M1 | healthy | 안전 (-) | 안전 (-) | — |
| M1 | itsc_4turn | 위험 (current_ratio/A 1.32) | 위험 (current_ratio/A 1.32) | — |
| M1 | itsc_12turn | 위험 (i2i1 0.269) | 위험 (i2i1 0.269) | — |
| M1 | overload | 위험 (current_ratio/A 1.36) | 위험 (current_ratio/A 1.36) | — |
| M1 | voltage_unbalance | 경고 (i2i1 0.0595) | 경고 (i2i1 0.0595) | — |
| M1 | single_phasing | 위험 (current_ratio/A 0.04) | 위험 (current_ratio/A 0.04) | — |
| M1 | no_load | 위험 (current_ratio/A 0.34) | 위험 (current_ratio/A 0.34) | — |
| M2 | healthy | 안전 (-) | 안전 (-) | — |
| M2 | itsc_4turn | 위험 (current_ratio/A 1.325) | 위험 (current_ratio/A 1.325) | — |
| M2 | itsc_12turn | 위험 (i2i1 0.269) | 위험 (i2i1 0.269) | — |
| M2 | overload | 위험 (current_ratio/A 1.35) | 위험 (current_ratio/A 1.35) | — |
| M2 | voltage_unbalance | 경고 (i2i1 0.0595) | 경고 (i2i1 0.0595) | — |
| M2 | single_phasing | 위험 (current_ratio/A 0.0333) | 위험 (current_ratio/A 0.0333) | — |
| M2 | no_load | 위험 (current_ratio/A 0.3333) | 위험 (current_ratio/A 0.3333) | — |
| M3 | healthy | 안전 (-) | 안전 (-) | — |
| M3 | itsc_4turn | 위험 (current_ratio/A 1.325) | 위험 (current_ratio/A 1.325) | — |
| M3 | itsc_12turn | 위험 (i2i1 0.269) | 위험 (i2i1 0.269) | — |
| M3 | overload | 위험 (current_ratio/A 1.35) | 위험 (current_ratio/A 1.35) | — |
| M3 | voltage_unbalance | 경고 (i2i1 0.0595) | 경고 (i2i1 0.0595) | — |
| M3 | single_phasing | 위험 (current_ratio/A 0.0375) | 위험 (current_ratio/A 0.0375) | — |
| M3 | no_load | 위험 (current_ratio/A 0.3312) | 위험 (current_ratio/A 0.3312) | — |
| M4 | healthy | 안전 (-) | 안전 (-) | — |
| M4 | itsc_4turn | 위험 (current_ratio/A 1.3226) | 위험 (current_ratio/A 1.3226) | — |
| M4 | itsc_12turn | 위험 (i2i1 0.269) | 위험 (i2i1 0.269) | — |
| M4 | overload | 위험 (current_ratio/A 1.3516) | 위험 (current_ratio/A 1.3516) | — |
| M4 | voltage_unbalance | 경고 (i2i1 0.0595) | 경고 (i2i1 0.0595) | — |
| M4 | single_phasing | 위험 (current_ratio/A 0.0355) | 위험 (current_ratio/A 0.0355) | — |
| M4 | no_load | 위험 (current_ratio/A 0.329) | 위험 (current_ratio/A 0.329) | — |
| M5 | healthy | 안전 (-) | 안전 (-) | — |
| M5 | itsc_4turn | 위험 (current_ratio/A 1.3227) | 위험 (current_ratio/A 1.3227) | — |
| M5 | itsc_12turn | 위험 (i2i1 0.269) | 위험 (i2i1 0.269) | — |
| M5 | overload | 위험 (current_ratio/A 1.3501) | 위험 (current_ratio/A 1.3501) | — |
| M5 | voltage_unbalance | 경고 (i2i1 0.0595) | 경고 (i2i1 0.0595) | — |
| M5 | single_phasing | 위험 (current_ratio/A 0.0366) | 위험 (current_ratio/A 0.0366) | — |
| M5 | no_load | 위험 (current_ratio/A 0.3295) | 위험 (current_ratio/A 0.3295) | — |

### 전기 모드 — 상태 시간 점유율·변경 행

| 모터 | 행 | 종합 상태 점유율 전 | 종합 상태 점유율 후 | 종합 변경 행 | 원인 변경 행 | 베어링 등급 전 (bearing_index) | 베어링 종합 후 | 후 kurtosis | 후 고주파 배율 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 681 | 안전 15 % / 경고 15 % / 위험 70 % | 안전 15 % / 경고 15 % / 위험 70 % | 0 | 0 | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % |
| M2 | 681 | 안전 15 % / 경고 15 % / 위험 70 % | 안전 15 % / 경고 15 % / 위험 70 % | 0 | 0 | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % |
| M3 | 681 | 안전 15 % / 경고 15 % / 위험 70 % | 안전 15 % / 경고 15 % / 위험 70 % | 0 | 0 | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % |
| M4 | 681 | 안전 15 % / 경고 15 % / 위험 70 % | 안전 15 % / 경고 15 % / 위험 70 % | 0 | 0 | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % |
| M5 | 681 | 안전 15 % / 경고 15 % / 위험 70 % | 안전 15 % / 경고 15 % / 위험 70 % | 0 | 0 | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % | 안전 100 % / 경고 0 % / 위험 0 % |

## 읽는 법

- 기계 모드 베어링 결함 장면: 전에는 손실 배율 5.0(≥5배)으로 베어링 지표가 위험이었고, 후에는 소손형 등가값(kurtosis·고주파 모두 위험 경계 초과)으로 위험이다. 원인 신호는 초과 비율이 가장 큰 신호를 고르므로 진동(4.8/4.5)이 아니라 bearing_kurtosis 로 바뀐다 — 종합 등급은 같다.
- 축정렬불량 장면: 전에는 손실 배율 2.5(경고), 후에는 M2 실측 등가값(kurtosis 3.7·고주파 ×2.2)으로 둘 다 경고 — 종합 등급은 같다.
- 냉각팬·브레이크·과부하·전기 모드: 베어링 신호가 정상값(kurtosis 3.0·×1.0)이라 전후 모두 베어링은 안전, 종합·원인 변화 없음.
- 종합 상태가 달라진 행: 전체 0 행 (0 이면 등급은 그대로이고 원인 신호 표기만 바뀐 것).
