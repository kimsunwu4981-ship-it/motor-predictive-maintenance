# M1 전체 3D 모델 (현대 HLP-2.2/4, 100L) — 출처·검증·사용법

생성 2026-10-21 17:10 · `tools/cad/write_model_doc.py`. 입력은 `assets/motors/M1/inputs/`(PROVENANCE.md)뿐, Maxwell 폴더 쓰기 0. **새 계산 없음** — 모델은 치수를 그리는 것이고 화면값은 상태 JSON 에서 온다.

## 1. 무엇이 카탈로그·데이터시트이고 무엇이 시각 추정인가

| 부품 | 치수 | 출처 | 값 |
|---|---|---|---|
| Stator_Core | D_so/D_si/L, 슬롯 수 | 데이터시트 §3·§4 (표준·계산·설계선택) | 155/98/135 mm, 36 |
| Stator_Core 슬롯 프로파일 | Hs0/Hs1/Hs2/Bs0/Bs1/Bs2 | Maxwell 채택 치수(rmxprt_v2m2 inputs = 시트 §5 + RMxprt v2 오버라이드) | 0.5/1.5/10.8103/2.0/4.86197/7.39398 |
| Coil_01…36 | 단면적 | geometry_check 'coil solid section (CoilTerm area)' (Maxwell 코일 단면 측정) | 21.1525 mm² |
| Coil_01…36 | 피치·층 | 시트 §4 (피치 8/9, 2층) + 권선 배치표 | 피치 8 슬롯 |
| Coil 엔드턴 | 경로 길이·돌출 | **visual_estimate** — 길이는 geometry_check 코일 체적 10234.005 / 단면 21.1525 / 2 − L = 106.91 mm (정본, 2026-10-21 결정; 시트 l_end 121.53 mm 는 참고) 에 맞춤, 형상(호·부풀림)은 추정 | 경로 106.9 mm, 축 돌출 28.3 mm |
| Coil_01_short | 분할 | Maxwell 과 같은 균일 오프셋 셸(ITSC 분할비 0.25) | 오프셋 0.307 mm → 체적비 25.00 % |
| Rotor_Core | D_ro/축경/L, 슬롯 수 | 데이터시트 §3·§4 | 97.4/36/135 mm, 28 |
| Bar_01…28 | 프로파일·스큐 | Maxwell 채택 치수(Hs0 0.8 Bs1 4.5 Bs2 2.4 Hs2 19.8), 스큐 시트 §8 | 10° 기계각 |
| EndRing_DE/NDE | D_er/h_er/w_er | 데이터시트 §7 (설계선택·계산) | 77.4/20/12 mm |
| Shaft | 로터부 Ø, 축단 D×E, 키 | 시트 §3 D_shaft, 카탈로그 D/E/키 | 36 / 28×60 / 8x7x45 |
| Shaft 베어링부·NDE | Ø | 6206 내경(표준) / NDE visual_estimate | 30.0 / 25.0 |
| Bearing_DE/NDE | 6206 내경·외경·폭 | 규격(표준), 위치 visual_estimate | 30/62/16, x ±108.0 |
| 하우징 Foot | H·A·AB·HA·B·BB·C·K | 카탈로그 KS 형식 치수표 100L | H 100, A 160, AB 196, HA 13, B1 140, BB 166, C 63, K 12 |
| 하우징 EndShield_DE 플랜지 | M·N·P·n·S·LA·T | 카탈로그 KS 플랜지 치수표 100L (B35 옵션으로 포함) | M 215, N 180, P 250, n 4, S 15, LA 13, T 4 |
| 하우징 전장·높이 | L·HC·HD·O·PF | 카탈로그 | L 370, HC 211, HD 247, O 28, PF 0.75 |
| 하우징 AD | 끝면도 전체 폭(프레임 측면~단자함 끝) | 카탈로그 (치수선 정의 확인) | 328 (플랜지형 175) — 모델 전체 폭 ≤ AD 구속 |
| 하우징 나머지 | AC·핀·엔드쉴드 두께·팬 커버·단자함 크기·위치·아이볼트 링·배치(어깨 x 125, 베어링 x ±108) | **visual_estimate** (housing_params.yaml) | AC_frame_od_mm 196.0, frame_body_od_mm 172.0, frame_len_mm 200.0, fin_count 28, fin_h_mm 12.0, fin_t_mm 3.0 … |

## 2. 체적 검증 (geometry_check_v2.json = Maxwell M1_3D_full 측정값, ±2 %)

| 항목 | 모델 | 기준 | 기준 출처 | 편차 | 판정 |
|---|---|---|---|---|---|
| 치+요크 Stator_Core [mm³] | 1,072,843 | 1,077,645 | geometry_check teeth_yoke.V_core | -0.45 % | PASS |
| 케이지 (바 28 + 엔드링 2) [mm³] | 413,538 | 409,740 | geometry_check cage.volume_after | +0.93 % | PASS |
| 코일 합 (코일 36개) vs geometry_check [mm³] | 368,952 | 368,424 | geometry_check coil_volume_mm3 × 36 (RMxprt 자동 엔드코일) | +0.14 % | PASS |
| 코일 합 vs 시트 규칙 2·A·(L+l_end)·36 [mm³] | 368,952 | 390,692 | coil area 21.1525 × 2 × (L 135 + l_end 121.53) × 36 | -5.56 % | FAIL (시트 추정 — 참고) |

| 검사 | 모델 | 기준 | 판정 |
|---|---|---|---|
| 슬롯(코일) 수 | 36 | 36 | PASS |
| 바 수 | 28 | 28 | PASS |
| 스큐 각 [°] (Bar_01 양 끝단 중심각 차, GLB 재판독) | 10.000 | 10 | PASS |
| Coil_01_short 체적비 [%] | 24.997 | 25.0 | PASS |

## 3. 하우징 치수 (STEP 재판독 vs 카탈로그, ±0.5 mm)

| 치수 | STEP 재판독 | 카탈로그 | 판정 |
|---|---|---|---|
| H (축 중심 높이) | 100.00 | 100.0 | PASS |
| A (발 구멍 간격, 폭) | 160.00 | 160.0 | PASS |
| B (발 구멍 간격, 축방향) | 140.00 | 140.0 | PASS |
| C (축 어깨~첫 구멍) | 63.00 | 63.0 | PASS |
| D (축단 지름) | 28.00 | 28.0 | PASS |
| E (축단 길이) | 60.00 | 60.0 | PASS |
| L (전장: 축단~팬커버) | 370.00 | 370.0 | PASS |

## 4. 폴리곤 수·파일

- 내부 127,908 삼각형 (cutaway 97,204) · 하우징 5,276 (cutaway 2,904) · 합 133,184 ≤ 300k. 엔드턴 스플라인 분할 `--end-segments`(기본 10), 메시 허용오차는 스크립트 `tol/ang`.
- `assets/motors/M1/`: internals.step(보관, 27 MB) · internals.obj/.glb · internals_cutaway.obj/.glb · internals_parts.json(재질·체적·삼각형) · housing_100L.step · housing.obj/.glb · housing_cutaway.* · housing_parts.json · housing_params.yaml
- USD: M1_internals.usd / M1_internals_cutaway.usd / M1_housing.usd / M1_housing_cutaway.usd (omni.kit.asset_converter) → M1.usd 조립 (prim 110, 메시 {'int_full': 72, 'int_cut': 72, 'hou_full': 8, 'hou_cut': 6, 'hou_half_top': 12, 'hou_half_front': 14, 'int_half_top': 2, 'int_half_front': 2})

## 4b. view variant 4+1종 · 반절 반투명 (H1~H3, 2026-10-21)

| variant | 하우징·고정자 코어 | 그 밖(권선·로터·축·베어링) | 메시 파일 | 용도 |
|---|---|---|---|---|
| `full` | 원형 | 원형 | housing.obj / internals.obj | 외형 |
| `cutaway` | θ −45~+45° 1/4 절단 | 원형 | *_cutaway.obj | 슬롯 1·Coil_01 노출 |
| `windings_only` | 숨김 | 코일만 | internals.obj | 권선 배치 |
| `half_translucent` | 위 반(`_T`, Z > 축 중심) 반투명 / 아래 반(`_B`) 불투명 | 원형(불투명) | housing_half_top.obj / internals_half_top.obj | 외형 유지 + 내부 비침 (기본) |
| `half_translucent_front` | 카메라 쪽 반(`_F`, Y < 0) 반투명 / 반대(`_R`) 불투명 | 원형(불투명) | *_half_front.obj | 측면 카메라용 |

- 반 분할은 **자르지 않고 나눈다**: 조각 체적 합 = 원본 ±0.1 %(`tests/test_m1_model.py::test_half_split_volume_sums`). 대상은 Foot 을 뺀 하우징 전 부품 + Stator_Core. top: 하우징 4,976 + 코어 4,880 삼각형, 체적 편차 최대 0.0000 % · front: 하우징 5,160 + 코어 4,504 삼각형, 체적 편차 최대 0.0000 %. 빈 조각(top 분할의 아이볼트 `_B`)은 메시를 만들지 않는다.
- 재질: `/M1/Looks/translucent_housing`(주철 색, opacity 0.2) · `translucent_core`(규소강 색, opacity 0.35) — **UsdPreviewSurface `opacity`**(+ `opacityThreshold` 0) 채택. 기존 파이프라인이 UsdPreviewSurface 라 같은 방식이 가장 단순하고, RTX 실시간에서 부분 불투명도 설정만 켜면 블렌딩 순서 문제(겹침·검은 테두리) 없이 그려졌다. OmniGlass `thin_walled` 는 대안으로만 둔다(MDL 의존·굴절 없음).
- 렌더 설정 한 줄: `/rtx/raytracing/fractionalCutoutOpacity = true` — `viz/m1_model.M1Model.set_view()` 가 half_translucent* 선택 시 켜고 다른 variant 로 돌아가면 원래 값으로 복귀. Coil_01_short 발광은 반투명 껍질 너머로 보이도록 표시 세기 ×1.5(`HALF_GLOW`, 값 아님).
- 반투명 조각은 variant 안에서만 정의되는 형제 prim(`/M1/Housing/Frame_T` 등)이라 런타임 온도 색(그룹 재질, 불투명 반에 바인딩)의 영향을 받지 않는다. 분할선(평면 가장자리)은 그대로 둔다.
- 스크린샷 `docs/assets/screenshots/M1_half/`(정상 측면·등각, 4턴 fault_focus, DE 베어링), FPS 는 SESSION_LOG 해당 장.

## 5. 결정 대기·한계

- **코일 엔드턴 길이(결정 2026-10-21)**: 정본 = `--end-path geometry_check`(Maxwell RMxprt 자동 엔드코일 체적에서 역산한 경로 106.9 mm, 축 돌출 28.3 mm). 시트 l_end 121.53 mm 는 **시트 추정(참고)** — 그 규칙이면 코일 1개 10,853 mm³(+6.0 %).
- **AD 328(카탈로그)**: 카탈로그 치수선 정의 = 프레임 측면~단자함 끝 전체 폭(플랜지형 175). 모델 구속: 끝면도 전체 폭(프레임 왼쪽 끝~단자함 오른쪽 끝) ≤ AD — 현재 196 mm. AC(프레임 외경)는 visual_estimate 유지
- 플랜지: USD variant `mount` = B3(기본, 플랜지 없음) / B35(FF215, 카탈로그 B35 옵션 치수; P 250 > 2H 200 이라 발 바닥 아래 25 mm — 실물과 같음). {'B3': '기본 — EndShield_DE (플랜지 없음)', 'B35': 'EndShield_DE_B35 (FF215 플랜지, 카탈로그 B35 옵션 치수)'}
- 온도 색: 열 모델은 전기 전용 모드에서 적분하지 않는다(`demo_integrated` 가 `dt_sim_s=0` 으로 호출) → 온도 색은 **기계·통합 모드에서만** 적용되고 전기 모드는 상별 기본색이다.
- 엔드턴·핀·단자함·팬 커버·아이볼트는 시각 추정이며 어떤 계산에도 쓰지 않는다. 베어링은 6206 규격 치수를 그린 시각 모델이다.
- 슬롯 안 코일 단면은 Maxwell 과 같은 21.15 mm² 사다리꼴(슬롯 라이너 0.3 mm 가정)로 층 중앙에 두었다(층 중심 r 54.7/61.9 mm).

## 5b. 장면 확인 (assets/motors/M1/scene_check.json — tools/cad/check_m1_scene.py)

- 전기 시나리오 7 장면 HUD 값(장면 끝 Ia/Ib/Ic·I₂/I₁·판정) ↔ 대시보드 fleet 로그: **7/7 일치** (`motor_dt_viz\logs\m1_model\demo_20261021_170452.csv` vs `motor_dt_viz/logs/fleet/M1/electrical/demo_fleet.csv`)

| 장면 | 케이스 | 장면 Ia/Ib/Ic [A] | fleet Ia/Ib/Ic | I₂/I₁ 장면/fleet | I₂/I_n | 판정 장면/fleet | 일치 |
|---|---|---|---|---|---|---|---|
| healthy | healthy | 4.8/4.6/4.6 | 4.8/4.6/4.6 | 0.0270/0.0270 | 0.0268 | SAFE/SAFE | ✓ |
| itsc_4turn | itsc_4turn | 5.2/4.9/4.6 | 5.2/4.9/4.6 | 0.0726/0.0726 | 0.075 | WARN/WARN | ✓ |
| itsc_12turn | itsc_12turn | 7.4/6.0/4.7 | 7.4/6.0/4.7 | 0.2696/0.2696 | 0.3376 | DANGER/DANGER | ✓ |
| overload | overload | 6.6/6.3/6.3 | 6.6/6.3/6.3 | 0.0270/0.0270 | 0.0364 | DANGER/DANGER | ✓ |
| voltage_unbalance | voltage_unbalance | 5.1/4.4/4.6 | 5.1/4.4/4.6 | 0.0595/0.0595 | 0.0595 | WARN/WARN | ✓ |
| single_phasing | single_phasing | 0.2/6.0/6.0 | 0.2/6.0/6.0 | 0.4792/0.4792 | 0.414 | DANGER/DANGER | ✓ |
| no_load | no_load | 1.6/1.5/1.5 | 1.6/1.5/1.5 | 0.0270/0.0270 | 0.0089 | DANGER/DANGER | ✓ |
| itsc_8turn | itsc_8turn | 6.1 (A상) | 엔진 6.1 | 0.1676/0.1676 (엔진 설계값) | 0.1887 | DANGER / fleet 없음 | ✓ |
| itsc_16turn | itsc_16turn | 8.9 (A상) | 엔진 8.9 | 0.3625/0.3625 (엔진 설계값) | 0.5084 | DANGER / fleet 없음 | ✓ |
| itsc_4turn_resistive | itsc_4turn_resistive | 4.9 (A상) | 엔진 4.9 | 0.0324/0.0324 (엔진 설계값) | 0.0324 | SAFE / fleet 없음 | ✓ |
| itsc_4turn_halfload | itsc_4turn_halfload | 3.5 (A상) | 엔진 3.5 | 0.0953/0.0953 (엔진 설계값) | 0.0645 | WARN / fleet 없음 | ✓ |

- FPS (1600×900, RTX 실시간): 평균 47.6 · 최소 38.2 · full 39.2 / cutaway 43.5 / windings_only 46.0 / full(후반) 49.2 — 30 FPS 기준 충족

## 6. 반입 경로·장면 사용법

1. `py -3.12 -X utf8 tools/cad/datasheet_to_yaml.py` → `py -3.12 -X utf8 tools/cad/build_internals_M1.py` → `py -3.12 -X utf8 tools/cad/build_housing_100L.py`
2. `py -3.12 -X utf8 -m pytest tests/test_m1_model.py -q` (체적·치수·개수·삼각형)
3. `C:\ISSACS~1\python.bat tools\cad\build_usd_M1.py` (저장소 루트에서, 상대 경로) → `assets/motors/M1/M1.usd`
4. 장면: `cd motor_dt_viz ; C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --m1_model [--view cutaway|windings_only]` — 22 kW 물리 모델은 숨긴 채 rpm·온도·전류 상태만 M1 USD 에 매핑한다(`motor_dt_viz/config` 변경 없음, 매핑은 `assets/motors/M1/prim_map_M1.yaml`).
5. USD 계층: /M1(스케일 0.001 = mm→m) /Housing(EndShield_DE = B3, EndShield_DE_B35) /Stator(Core, Coils/Coil_01…36, Coils/Coil_01_short) /Rotor(xformOp:rotateX 회전 대상: Core, Bars, EndRing_DE/NDE, Shaft) /Bearings(DE, NDE) /Looks. variantSet `view` = full | cutaway(θ −45~+45° 절단, 슬롯 1 노출) | windings_only | half_translucent | half_translucent_front, `mount` = B3 | B35.
6. M1 전용 전기 시나리오 `motor_dt_viz/config/scenarios_M1.yaml`(기존 7 + 8턴·16턴·저항성 4턴 R_f 1.0·반부하 4턴 50 %): `--m1_model` 이면 자동 사용, 추가 케이스는 electrical.yaml 의 itsc_4turn 템플릿에 lut {turns, R_f_ohm}·load 만 바꿔 런타임 등록(electrical.yaml 불변). 카메라 프리셋 `fault_focus`(Coil_01_short 근접) — 스크린샷 03/04.
