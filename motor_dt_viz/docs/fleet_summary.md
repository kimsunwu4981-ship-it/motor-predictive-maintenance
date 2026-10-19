# 5종 모터 배치 시뮬레이션 비교표 (엔진 기반, `tools/run_fleet.py`)

로그: `logs/fleet/<id>/<mode>/demo_fleet.csv`(데모와 같은 컬럼), `status_fleet.csv`(판정 엔진 결과). 시나리오·결함 파라미터는 공통,
결과 온도·전류는 모터별 config(`config/motors/<id>.yaml` + M5 기준 열회로 스케일)로 달라진다. 시각은 **재생 시간(s)** 이고 괄호는
그 장면의 배속을 곱한 **시뮬레이션 시간(분)** 이다. 판정은 히스테리시스 5 %·지속 3 s 가 적용된 값이다.

## M5 회귀 (엔진 로그 ↔ 기존 Isaac 로그, 장면 종료 시점)

| 모드 | 최대 차이 | 허용 | 결과 | 대조 로그 |
|---|---|---|---|---|
| mechanical | 0.1 | 2.5 | PASS | demo_20260922_174529.csv |
| electrical | 0.0 | 0.06 | PASS | demo_20260922_231908.csv |

## 정상 운전 수렴 온도 (정격 100 % 연속, 엔진 정상상태 해, °C)

| ID | 모터 | 권선 | 코어 | 로터 | 축 | DE 베어링 | 프레임 | 진동 규격 (경고/위험 mm/s) |
|---|---|---|---|---|---|---|---|---|
| M1 | 1톤 호이스트 권상 모터 (2.2 kW 4극) | 46.4 | 41.6 | 44.3 | 41.7 | 39.6 | 35.9 | ISO 20816-3 Group 2 (1.4/4.5) |
| M2 | 2.8톤 호이스트 권상 모터 (5.5 kW 4극) | 64.2 | 55.4 | 60.4 | 55.6 | 51.7 | 45.0 | ISO 20816-3 Group 2 (1.4/4.5) |
| M3 | 5톤 호이스트 권상 모터 (7.5 kW 4극) | 73.7 | 62.8 | 69.0 | 63.1 | 58.3 | 49.8 | ISO 20816-3 Group 2 (1.4/4.5) |
| M4 | 10톤 호이스트 권상 모터 (15.0 kW 6극) | 79.0 | 66.9 | 73.8 | 67.2 | 61.8 | 52.5 | ISO 20816-3 Group 2 (1.4/4.5) |
| M5 | 15~20톤 호이스트 권상 모터 (22 kW 6극) | 87.6 | 73.6 | 81.6 | 73.9 | 67.7 | 56.9 | ISO 20816-3 Group 2 (1.4/4.5) |

## 기계 결함 장면별 도달 시각 (status_fleet.csv · demo_fleet.csv)

장면은 이어서 재생되므로 `0.0 s` 는 이전 장면에서 넘어온 상태다. '온도 위험' 은 온도 신호만으로 위험에 닿은 시각,
'리드 타임' 은 원시값 기준 진동 경고(규격 watch 이상) → 온도 경고(부품 안전 상한 이상) 간격이다 (판정 상태에는 진동 지속 3 s 가 더해진다).

| 장면 | ID | 첫 경고 | 첫 위험 | 원인(위험 시점) | 온도 위험 | 장면 끝 상태 (원인 값) | 리드 타임 진동→온도 |
|---|---|---|---|---|---|---|---|
| 1. 정상 운전 | M1 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| 1. 정상 운전 | M2 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| 1. 정상 운전 | M3 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| 1. 정상 운전 | M4 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| 1. 정상 운전 | M5 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| | | | | | | | |
| 2. DE 베어링 열화 | M1 | 3.2 s (6.5 분) | 3.2 s (6.5 분) | bearing_kurtosis 50.0 | 없음 | DANGER (bearing_kurtosis 50.0) | 온도 경고 없음 |
| 2. DE 베어링 열화 | M2 | 1.8 s (3.5 분) | 3.2 s (6.5 분) | bearing_kurtosis 50.0 | 25.2 s (50.5 분) | DANGER (bearing_kurtosis 50.0) | 1.50 s |
| 2. DE 베어링 열화 | M3 | 1.0 s (2.0 분) | 3.2 s (6.5 분) | bearing_kurtosis 50.0 | 4.0 s (8.0 분) | DANGER (bearing_kurtosis 50.0) | 0.75 s |
| 2. DE 베어링 열화 | M4 | 1.2 s (2.5 분) | 3.2 s (6.5 분) | bearing_kurtosis 50.0 | 3.5 s (7.0 분) | DANGER (bearing_kurtosis 50.0) | 1.00 s |
| 2. DE 베어링 열화 | M5 | 1.0 s (2.0 분) | 2.5 s (5.0 분) | temperature/bearing_de 95.4 | 2.5 s (5.0 분) | DANGER (bearing_kurtosis 50.0) | 0.75 s |
| | | | | | | | |
| 3. 축 정렬 불량 | M1 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | bearing_kurtosis 50.0 | 없음 | WARN (vibration 3.6) | 온도 경고 없음 |
| 3. 축 정렬 불량 | M2 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | bearing_kurtosis 50.0 | 0.0 s (0.0 분) | WARN (vibration 3.6) | 이전 장면부터 온도 경고 |
| 3. 축 정렬 불량 | M3 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | bearing_kurtosis 50.0 | 0.0 s (0.0 분) | WARN (vibration 3.6) | 이전 장면부터 온도 경고 |
| 3. 축 정렬 불량 | M4 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | bearing_kurtosis 50.0 | 0.0 s (0.0 분) | WARN (vibration 3.6) | 이전 장면부터 온도 경고 |
| 3. 축 정렬 불량 | M5 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | bearing_kurtosis 50.0 | 0.0 s (0.0 분) | WARN (vibration 3.6) | 이전 장면부터 온도 경고 |
| | | | | | | | |
| 4. 냉각팬 고장 | M1 | 0.0 s (0.0 분) | 없음 | - | 없음 | SAFE (-) | 온도 경고 없음 |
| 4. 냉각팬 고장 | M2 | 0.0 s (0.0 분) | 없음 | - | 없음 | SAFE (-) | 온도 경고 없음 |
| 4. 냉각팬 고장 | M3 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/stator_core 75.1) | 이전 장면부터 온도 경고 |
| 4. 냉각팬 고장 | M4 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/stator_core 79.1) | 이전 장면부터 온도 경고 |
| 4. 냉각팬 고장 | M5 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/stator_core 86.6) | 이전 장면부터 온도 경고 |
| | | | | | | | |
| 5. 브레이크 끌림 | M1 | 3.2 s (6.5 분) | 없음 | - | 없음 | WARN (vibration 2.0) | 온도 경고 없음 |
| 5. 브레이크 끌림 | M2 | 2.0 s (4.0 분) | 없음 | - | 없음 | WARN (vibration 2.0) | 1.75 s |
| 5. 브레이크 끌림 | M3 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/shaft 104.4) | 이전 장면부터 온도 경고 |
| 5. 브레이크 끌림 | M4 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/shaft 109.9) | 이전 장면부터 온도 경고 |
| 5. 브레이크 끌림 | M5 | 0.0 s (0.0 분) | 9.0 s (18.0 분) | temperature/shaft 110.0 | 9.0 s (18.0 분) | DANGER (temperature/shaft 121.1) | 이전 장면부터 온도 경고 |
| | | | | | | | |
| 6. 과부하 운전 (열 관점) | M1 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (vibration 2.2) | 온도 경고 없음 |
| 6. 과부하 운전 (열 관점) | M2 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (vibration 2.2) | 이전 장면부터 온도 경고 |
| 6. 과부하 운전 (열 관점) | M3 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (vibration 2.2) | 이전 장면부터 온도 경고 |
| 6. 과부하 운전 (열 관점) | M4 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | temperature/shaft 110.1 | 0.0 s (0.0 분) | WARN (vibration 2.2) | 이전 장면부터 온도 경고 |
| 6. 과부하 운전 (열 관점) | M5 | 0.0 s (0.0 분) | 0.0 s (0.0 분) | temperature/shaft 121.2 | 0.0 s (0.0 분) | WARN (vibration 2.2) | 이전 장면부터 온도 경고 |
| | | | | | | | |
| 7. 결함 해제 후 냉각 | M1 | 없음 | 없음 | - | 없음 | SAFE (-) | - |
| 7. 결함 해제 후 냉각 | M2 | 0.0 s (0.0 분) | 없음 | - | 없음 | SAFE (-) | - |
| 7. 결함 해제 후 냉각 | M3 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/shaft 71.6) | - |
| 7. 결함 해제 후 냉각 | M4 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/shaft 78.4) | - |
| 7. 결함 해제 후 냉각 | M5 | 0.0 s (0.0 분) | 없음 | - | 없음 | WARN (temperature/shaft 88.0) | - |
| | | | | | | | |

냉각 장면(7) 권선 초과온도 감소 비율 (큰 값 = 빨리 식음): M1 0.33, M2 0.31, M3 0.31, M4 0.30, M5 0.29

## 전기 장면별 상태 (장면 끝, status_fleet.csv)

| 장면 | M1 | M2 | M3 | M4 | M5 |
|---|---|---|---|---|---|
| 1. 정상 (3상 균형) | SAFE (-) | SAFE (-) | SAFE (-) | SAFE (-) | SAFE (-) |
| 2. 턴간 단락 초기 (4턴) | WARN (i2i1 0.1) | DANGER (current_ratio/A 1.3) | DANGER (current_ratio/A 1.3) | DANGER (current_ratio/A 1.3) | DANGER (current_ratio/A 1.3) |
| 3. 턴간 단락 진행 (12턴) | DANGER (i2i1 0.3) | DANGER (i2i1 0.3) | DANGER (i2i1 0.3) | DANGER (i2i1 0.3) | DANGER (i2i1 0.3) |
| 4. 과부하 운전 | DANGER (current_ratio/A 1.4) | DANGER (current_ratio/A 1.4) | DANGER (current_ratio/A 1.4) | DANGER (current_ratio/A 1.4) | DANGER (current_ratio/A 1.4) |
| 5. 공급전압 불평형 | WARN (i2i1 0.1) | WARN (i2i1 0.1) | WARN (i2i1 0.1) | WARN (i2i1 0.1) | WARN (i2i1 0.1) |
| 6. 결상 (R상 끊김) | DANGER (current_ratio/A 0.0) | DANGER (current_ratio/A 0.0) | DANGER (current_ratio/A 0.0) | DANGER (current_ratio/A 0.0) | DANGER (current_ratio/A 0.0) |
| 7. 무부하 (저전류) | DANGER (current_ratio/B 0.3) | DANGER (current_ratio/A 0.3) | DANGER (current_ratio/A 0.3) | DANGER (current_ratio/A 0.3) | DANGER (current_ratio/A 0.3) |

전기 결과가 5종에서 같은 등급으로 나오는 것은 정상이다: 전류 모델은 정격 대비 비율(케이스 배율)로 정의되고 판정도 비율 기준이라 모터가 바뀌면 암페어만 바뀐다.
I₂/I₁ 목표값(0.006/0.104/0.269)은 M5 기준 해석식 등가값을 전 모터에 적용한 것이다 (§4.3).

## 물리 타당성 자동 검사

- 이상 없음 (작은 모터일수록 빨리 식고, 결함 도달은 느리다)
- M1: 기계 시나리오 전체에서 **온도**만으로는 '위험'에 닿지 않는다 — 위험 판정은 진동(시나리오 공통 상수 4.8 mm/s)이 만든다 (결함 손실이 출력에 비례해 작음, docs/thermal_scaling.md). 작은 모터의 결함 배율을 따로 둘지는 사용자 결정 사항
- 진동값(결함별 상수 mm/s)은 5종 공통이다 — 모터별로 다른 것은 규격(경고 1.8 vs 1.4)뿐. 실측 연결 전까지는 진동 기반 판정이 모터 크기에 거의 무관하다.
