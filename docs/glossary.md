# 용어집 (DT 저장소 루트 — 3D 자산·장면)

| 용어 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| **USD variant (variantSet)** | 한 prim 아래에 여러 "변형"을 넣어 두고 선택(variantSelection)으로 바꾸는 USD 기능. 변형마다 참조·가시성·속성 오피니언이 다르다. | `assets/motors/M1/M1.usd` 의 `/M1` 에 variantSet `view` = `full` / `cutaway`(하우징·고정자를 1/4 절단 메시로 교체) / `windings_only`(코어·하우징 숨김). 장면에서 `--view` 또는 `M1Model.set_view()` 로 전환, 런타임 섹션 기능에 의존하지 않는다. |
| **불리언 절단 (boolean cut)** | 솔리드에서 다른 솔리드(절단 박스)와 겹치는 부분을 빼는 CAD 연산. 잘린 면이 새 면으로 생긴다. | `tools/cad/m1_common.quarter_cutter()` — Y>0 ∧ Z>0 사분면(축 기준 90°) 박스로 하우징·고정자 코어·코일을 잘라 `*_cutaway.obj/.glb` 를 만든다. 로터·베어링은 자르지 않는다. 체적 검증은 절단 전 모델로 한다. |
| **로프트/스윕 (loft / sweep)** | 단면을 경로를 따라 끌어(스윕) 또는 여러 단면을 이어(로프트) 솔리드를 만드는 CAD 연산. | 코일 엔드턴: 슬롯 안 사다리꼴 단면을 3D 스플라인 경로(적층 끝 → 축방향 돌출 → 이웃 슬롯)로 스윕. 경로 길이는 데이터시트 엔드권선 도체 길이 l_end 에 맞추고 형상은 시각 추정(`visual_estimate`). 분할 수 `--end-segments`. |
