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
