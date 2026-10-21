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

### P2′ — 단일 모터 M1 전환 (2026-10-21)

| 용어 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| **퇴역 라이브러리 (`_retired/`)** | 더 이상 로더가 읽지 않지만 삭제하지 않고 보관하는 설정 파일 폴더. | `motor_dt_viz/config/motors/_retired/` 의 M2~M5.yaml 과 옛 `motor.yaml` 사본(`motor_M5_reference.yaml`). `engine/motor_library.list_ids()` 는 `config/motors/*.yaml` 만 읽는다. 라이브러리 **코드 경로는 그대로**라 YAML 한 장으로 다시 늘릴 수 있다. |
| **기준 열회로 (`thermal.yaml reference`)** | 열회로 튜닝 계수를 역산한 원래 모터의 출력·효율·프레임 비(= 스케일 분모). | 22 kW 6극(옛 M5): power_kW 22, efficiency 0.90, geometry_scale 1.0, loss_W 2,444. `thermal_cfg()` 가 M5 가 미등록이면 이 절로 손실비·치수비를 만든다. M1 은 손실비 0.11·scale 0.556. |
| **ISO 10816-1 Class I** | 15 kW 이하 소형 기계의 진동 속도 RMS 등급(강성 지지). 경고(C 구역 시작) 1.8 mm/s, 위험(D) 4.5 mm/s — 중간 '정비 계획' 경계가 없다. | `VIB_STANDARD_SPLIT_KW = 15.0`: 그 아래 출력이면 YAML `vibration.standard` 가 10816-1 이어야 로더 검증을 통과한다. M1 1.8/4.5(plan = act). `thresholds.yaml` 의 20816-3 Group 2(1.4/2.8/4.5)는 모터 미지정 fallback 값으로 불변. |
| **scene_map (상태 보드 시각 매핑)** | 시나리오 재생 바에서 "어느 장면·몇 초가 어떤 판정인지" 를 미리 적어 둔 표. | `config/status_demo.yaml scene_map`(정상 15 s SAFE / 4턴 40 s WARN / 12턴 60 s DANGER / DE 베어링 27.5 s WARN / 과부하 85 s DANGER) → `index.json` → 상태 보드 칩(클릭 시 그 모드·시각으로 이동). `positions.M1` 은 첫 화면 위치. |
| **USD 참조 자리(DefinePrim)** | 다른 USD 파일을 끌어오는 빈 prim. 타입을 주면(Xform.Define) 참조된 메시가 안 보이는 경우가 있어 타입 없이 만든다. | `viz/m1_model.py` 가 `/World/M1` 에 `assets/motors/M1/M1.usd` 를 참조하고, 22 kW `/World/Motor`·`/World/CurrentPaths` 는 숨긴다(매 프레임 재숨김 — MakeVisible 이 조상을 되살리므로). |

### H — 반절 반투명 뷰 (2026-10-21)

| 용어 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| **부분 불투명도 (Fractional Cutout Opacity)** | RTX 실시간 렌더에서 재질의 opacity 를 0/1 컷아웃이 아니라 0~1 비율 그대로 섞어 그리는 설정. Render Settings → Translucency. | carb 설정 `/rtx/raytracing/fractionalCutoutOpacity`. `viz/m1_model.M1Model.set_view("half_translucent*")` 가 켜고, 다른 variant 로 가면 원래 값으로 되돌린다. 반투명 재질은 `UsdPreviewSurface opacity`(하우징 0.20 / 코어 0.35, `opacityThreshold` 0). |
| **얇은 벽 유리 (OmniGlass `thin_walled`)** | 두께 없는 유리로 취급해 굴절 없이 투과만 하는 MDL 재질 옵션 — 블렌딩 순서 문제가 날 때의 대안. | 이번 뷰에서는 UsdPreviewSurface opacity 로 충분해 **채택하지 않음**(`docs/assets/M1_model.md` variant 절). |
| **반 분할 (half split)** | 자르지 않고 평면으로 두 조각으로 나누는 것 — 체적 합이 원본과 같아야 한다. | `tools/cad/m1_common.split_parts()`: `top`(Z = 축 중심, `_T/_B`) · `front`(Y = 0, `_F/_R`). 대상은 Foot 을 뺀 하우징 전 부품 + 고정자 코어. 테스트 `tests/test_m1_model.py::test_half_split_volume_sums`(±0.1 %). |
| **variant `half_translucent` / `_front`** | USD variantSet `view` 의 4·5번째 값. 반투명 조각은 variant 안에서만 정의되는 형제 prim(`/M1/Housing/Frame_T` 등). | 런타임 그룹 재질(온도 색)은 원 prim(불투명 반)에만 바인딩되므로 반투명 반은 색이 바뀌지 않는다 — 의도. `demo_integrated.py --view half_translucent`. |
