# LUT 연동 검증 보고 (TASK A D6) — 2026-10-21 12:35

- electrical.yaml version 2 · method `lut` → M1 실제 동작 **lut** (LUT M1_mccm_lut_v2.json (등가회로(RMxprt v2+MCCM), provisional))
- LUT `data\electrical\M1_mccm_lut_v2.json` sha256 `c6898c6e8d80…` · 원본 mccm_lut sha `7d7b1ac5147a…` · grade 등가회로(RMxprt v2+MCCM) · status provisional · fem_verified False · R_fe 보정 physical
- 정격 전류: electrical.yaml rated_current_A **4.73 A** (LUT I_n) vs config/motors/M1.yaml rated_line_current_a **4.73 A** → 차이 +0.0 % (2026-10-19 결정 (A): M1.yaml 을 카탈로그 4.73 A·Y·η 0.895·pf 0.79 로 통일 → 0 % 여야 한다)
- 고유 비대칭 inherent: enabled True, I₂/I₁ 0.027, 위상 0.0° (AI Hub 정상 중앙값)

## 요약

| # | 검사 | 결과 | 비고 |
|---|---|---|---|
| V1 | LUT ↔ mccm_results ±1 % | PASS | 5 케이스 |
| V2 | 합성 파형 ↔ LUT ±1 % (inherent OFF) | PASS | healthy/4T/12T |
| V3 | inherent ON 범위 | PASS | h=0.027 |
| V4 | legacy 0.104/0.269 ±0.1 % | PASS | M1 legacy · 기본 · motor_id≠M1 |
| V5 | I₂/I_n 이 I₂/I₁ 보다 부하 의존 작음 (4턴) | PASS | I₂/I₁ +52.6 % vs I₂/I_n -0.0 % |
| V6 | thresholds 판정표 기록 | PASS | 8 행 |
| V7 | 라이브 10 s | PASS | 88 states, healthy 0.027, 4T 0.0726 |
| V8 | 금지 파일 무변경 | PASS | clean |

**8/8 통과.** 변경 파일: config/electrical.yaml(v2), engine/current_model.py, engine/lut_source.py, engine/thermal_model.py(extra_loss_W 훅), app/demo_integrated.py(state 키 추가·열 연동·CSV 열), viz/hud.py, tools/electrical/*, tests/test_lut_source.py, data/electrical/*, dashboard(src 5개·css·dist 빌드). WebSocket 포트·스키마 번호·명령 목록은 그대로 (state 에 키만 덧붙임).

## V1. LUT 격자 ↔ mccm_results 케이스 (±1 %)

| 케이스 | 턴 | R_f Ω | 부하 % | mccm I₂/I₁ | LUT | Δ | mccm I₂/I_n | LUT | Δ | I_f A | P_loop_total W | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 4 | 0.1 | 100 | 0.0488 | 0.0490 | +0.31 % | 0.0504 | 0.0506 | +0.35 % | 34.38 | 158.1 | ✓ |
| C3 | 12 | 0.1 | 100 | 0.2455 | 0.2455 | +0.00 % | 0.3074 | 0.3074 | +0.00 % | 69.80 | 977.5 | ✓ |
| C4 | 16 | 0.1 | 100 | 0.3377 | 0.3379 | +0.03 % | 0.4735 | 0.4738 | +0.06 % | 80.64 | 1523.3 | ✓ |
| C1-R | 4 | 1.0 | 100 | 0.0065 | 0.0065 | +0.45 % | 0.0065 | 0.0065 | +0.46 % | 4.43 | 20.3 | ✓ |
| C1-L | 4 | 0.1 | 50 | 0.0745 | 0.0747 | +0.30 % | 0.0504 | 0.0506 | +0.35 % | 34.38 | 158.1 | ✓ |

## V2·V3. M1 합성 파형의 I₂/I₁ — 고유 비대칭 OFF (LUT 재현 ±1 %) / ON (범위 [|r−h|, r+h])

| 케이스 | 턴 | LUT I₂/I₁ | LUT 위상° | 합성(OFF) | Δ | 위상차° | V2 | 최소 |r−h| | 합성(ON) | 최대 r+h | 설계값 | I₂/I_n(ON) | 위상(ON)° | V3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy | 0.0 | 0.0000 | 0.0 | 0.0000 | 0 | 0.00 | ✓ | 0.0270 | 0.0270 | 0.0270 | 0.0270 | 0.0270 | 0.0 | ✓ |
| itsc_4turn | 4.0 | 0.0490 | 35.7 | 0.0490 | +0.00 % | 0.00 | ✓ | 0.0220 | 0.0726 | 0.0760 | 0.0726 | 0.0726 | 23.2 | ✓ |
| itsc_12turn | 12.0 | 0.2455 | 28.4 | 0.2455 | +0.00 % | 0.00 | ✓ | 0.2185 | 0.2696 | 0.2725 | 0.2696 | 0.2696 | 25.6 | ✓ |

4턴 고유 비대칭 범위: **0.0220 ~ 0.0760** (위상 0° 가정 합성값 0.0726; LUT I₂ 위상 35.7° 라 최대값보다 조금 작다)

## V4. legacy 회귀 (±0.1 %)

| 모델 | method | 케이스 | 목표 | 값 | Δ | 판정 |
|---|---|---|---|---|---|---|
| M1 method:legacy | legacy | healthy | 0.006 | 0.0060 | +0.000 % | ✓ |
| M1 method:legacy | legacy | itsc_4turn | 0.104 | 0.1040 | +0.000 % | ✓ |
| M1 method:legacy | legacy | itsc_12turn | 0.269 | 0.2690 | +0.000 % | ✓ |
| 기본 CurrentModel() | legacy | healthy | 0.006 | 0.0060 | +0.000 % | ✓ |
| 기본 CurrentModel() | legacy | itsc_4turn | 0.104 | 0.1040 | +0.000 % | ✓ |
| 기본 CurrentModel() | legacy | itsc_12turn | 0.269 | 0.2690 | +0.000 % | ✓ |
| motor_id≠M1 (transfer false) | legacy | healthy | 0.006 | 0.0060 | +0.000 % | ✓ |
| motor_id≠M1 (transfer false) | legacy | itsc_4turn | 0.104 | 0.1040 | +0.000 % | ✓ |
| motor_id≠M1 (transfer false) | legacy | itsc_12turn | 0.269 | 0.2690 | +0.000 % | ✓ |

## V5. 부하 50 % vs 100 % (4턴 · R_f 0.1 Ω) — I₂/I₁ 은 부하에 따라 흔들리고 I₂/I_n 은 덜 흔들린다

| 턴 | I₂/I₁ 50 % | 100 % | 115 % | 50 vs 100 | I₂/I_n 50 % | 100 % | 115 % | 50 vs 100 |
|---|---|---|---|---|---|---|---|---|
| 4 | 0.0747 | 0.0490 | 0.0439 | +52.6 % | 0.0506 | 0.0506 | 0.0506 | -0.0 % |
| 8 | 0.2140 | 0.1441 | 0.1302 | +48.5 % | 0.1623 | 0.1623 | 0.1623 | -0.0 % |
| 12 | 0.3513 | 0.2455 | 0.2238 | +43.1 % | 0.3074 | 0.3074 | 0.3074 | -0.0 % |

## V6. config/thresholds.yaml i2i1 (safe_below 0.05, danger_from 0.1) 로 본 케이스 판정 — 임계값·판정 코드 무변경, 기록만

| 케이스 | 근거 | 최소 | 판정 | 설계값 | 판정 | 최대 | 판정 | LUT I₂/I_n |
|---|---|---|---|---|---|---|---|---|
| 정상 운전 | LUT 0T/0.03Ω | 0.0270 | SAFE | 0.0270 | SAFE | 0.0270 | SAFE | 0.0000 |
| 턴간 단락 4턴 (초기) | LUT 4T/0.1Ω | 0.0220 | SAFE | 0.0726 | WARN | 0.0760 | WARN | 0.0506 |
| 턴간 단락 12턴 (진행) | LUT 12T/0.1Ω | 0.2185 | DANGER | 0.2696 | DANGER | 0.2725 | DANGER | 0.3074 |
| 과부하 135 % | legacy | — | — | 0.0270 | SAFE | — | — | — |
| 공급전압 불평형 | legacy | — | — | 0.0595 | WARN | — | — | — |
| 결상 (R상 상실) | legacy | — | — | 0.4792 | DANGER | — | — | — |
| 무부하 | legacy | — | — | 0.0270 | SAFE | — | — | — |
| (참고) 8턴 R_f 0.1 | LUT | 0.1171 | DANGER | 0.1441 | DANGER | 0.1711 | DANGER | 0.1623 |

해석: 4턴은 고유 비대칭 위상에 따라 SAFE~WARN(최소 0.018)·WARN(설계 0.071) 사이, 12턴은 모든 위상에서 DANGER. 확실한 탐지(최소값 ≥ danger_from)는 8턴부터 — 분석 보고(권상모터_3D모델링/docs/maxwell/analysis_report.md 표 G)와 같다. 임계값 변경은 제안으로만(docs/judgment_basis.md).

## V7. 라이브 10 s (Isaac Sim `demo_integrated --live --motor M1 --mode electrical`, 검증 포트)

- 접속까지 16.3 s
- state 88 건 / 10 s (schema 1, motor M1, mode electrical), ack 1 건
- 새 키 존재: ✓ (i2_over_in, electrical_source, i2i1_marks, p_loop_total_W)
- electrical_source: method lut · grade 등가회로(RMxprt v2+MCCM) · status provisional · fem_verified False · M1_mccm_lut_v2.json · cases 11
- healthy: I₂/I₁ 0.027 (설계 0.0270) · I₂/I_n 0.027 → ✓
- itsc_4turn 주입 ack ✓: I₂/I₁ 0.0726 (설계 0.0726) · I₂/I_n 0.0726 · P_loop_total 158.1 W · Ia/Ib/Ic [5.0, 4.7, 4.5] → ✓
- i2i1_marks: [{'case': 'healthy', 'label': '정상 운전', 'value': 0.027}, {'case': 'itsc_4turn', 'label': '턴간 단락 4턴 (초기)', 'value': 0.0726}, {'case': 'itsc_12turn', 'label': '턴간 단락 12턴 (진행)', 'value': 0.2696}]
- 로그: logs\verify_lut\demo_stdout.log

## V8. 금지 파일 변경 없음 (git diff --stat)

```
(변경 없음)
```
대상: `motor_dt_viz/config/thresholds.yaml`, `motor_dt_viz/config/motors`, `motor_dt_viz/engine/thresholds.py`, `motor_dt_viz/config/live.yaml`, `motor_dt_viz/tools/firewall_rules.ps1`
