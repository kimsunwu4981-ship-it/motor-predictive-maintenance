# 용어집 (DT 저장소 루트 — 3D 자산·장면)

| 용어 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| **USD variant (variantSet)** | 한 prim 아래에 여러 "변형"을 넣어 두고 선택(variantSelection)으로 바꾸는 USD 기능. 변형마다 참조·가시성·속성 오피니언이 다르다. | `assets/motors/M1/M1.usd` 의 `/M1` 에 variantSet `view` = `full` / `cutaway`(하우징·고정자를 1/4 절단 메시로 교체) / `windings_only`(코어·하우징 숨김). 장면에서 `--view` 또는 `M1Model.set_view()` 로 전환, 런타임 섹션 기능에 의존하지 않는다. |
| **불리언 절단 (boolean cut)** | 솔리드에서 다른 솔리드(절단 박스)와 겹치는 부분을 빼는 CAD 연산. 잘린 면이 새 면으로 생긴다. | `tools/cad/m1_common.quarter_cutter()` — θ −45~+45°(+Z 슬롯 1 중심, 축 기준 90°) 사분면 박스로 하우징·고정자 코어·코일을 잘라 `*_cutaway.obj/.glb` 를 만든다. 로터·베어링은 자르지 않는다. 체적 검증은 절단 전 모델로 한다. |
| **로프트/스윕 (loft / sweep)** | 단면을 경로를 따라 끌어(스윕) 또는 여러 단면을 이어(로프트) 솔리드를 만드는 CAD 연산. | 코일 엔드턴: 슬롯 안 사다리꼴 단면을 3D 스플라인 경로(적층 끝 → 축방향 돌출 → 이웃 슬롯)로 스윕. 경로 길이는 데이터시트 엔드권선 도체 길이 l_end 에 맞추고 형상은 시각 추정(`visual_estimate`). 분할 수 `--end-segments`. |

### P1 — 실측 기준선 체계 (2026-10-21)

| 용어 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| **참고 지표 (provisional / advisory)** | 기준값의 출처가 명판·카탈로그·실측 기준선이 아니어서 아직 확정(confirmed)되지 않은 지표. | `config/thresholds.yaml` `status: provisional`. 시뮬레이션(합성 신호)에서는 "임시 기준" 라벨로 종합 판정에 포함, 실측 스트림에서는 worst-of 에서 빠져 `Verdict.advisory` 로만 나온다(`judgment.provisional_policy`). |
| **기준선 배수 (baseline_multiple)** | 임계값을 절대값이 아니라 그 모터의 정상 실측 기준선 × 배수로 두는 방식. | `current.negative_sequence.mode: baseline_multiple` 이면 경고 = baseline.value × warn_multiple(2.0), 위험 = × danger_multiple(4.0). baseline 은 실모터 실측 후에만 채운다. |
| **p95** | 95 % 분위수 — 창(1 s) 값들 중 95 %가 이 값 이하. | `tools/baseline_capture.py` 가 I₂/I₁ 의 중앙값·p95·표준편차를 내고, 참고 데이터셋(AI Hub L-SF-04)의 p95 를 `reference_baseline.value` 에 기록한다. |
| **전압 불평형 보정** | 공급 전압의 역상비 V₂/V₁ 가 만드는 전류 역상분을 빼서 모터 자체(권선)의 불평형만 보는 것. | `voltage_unbalance_compensation.enabled` 이고 입력에 `v2_v1` 이 있을 때만 I₂/I₁ − k·V₂/V₁; 전압 채널이 없으면 `compensated: false`. AI Hub 데이터에는 전압 채널이 없다. |
