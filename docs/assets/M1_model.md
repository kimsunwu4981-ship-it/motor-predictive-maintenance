# M1 전체 3D 모델 (현대 HLP-2.2/4, 100L) — 출처·검증·사용법

생성 2026-10-21 11:17 · `tools/cad/write_model_doc.py`. 입력은 `assets/motors/M1/inputs/`(PROVENANCE.md)뿐, Maxwell 폴더 쓰기 0. **새 계산 없음** — 모델은 치수를 그리는 것이고 화면값은 상태 JSON 에서 온다.

## 1. 무엇이 카탈로그·데이터시트이고 무엇이 시각 추정인가

| 부품 | 치수 | 출처 | 값 |
|---|---|---|---|
| Stator_Core | D_so/D_si/L, 슬롯 수 | 데이터시트 §3·§4 (표준·계산·설계선택) | 155/98/135 mm, 36 |
| Stator_Core 슬롯 프로파일 | Hs0/Hs1/Hs2/Bs0/Bs1/Bs2 | Maxwell 채택 치수(rmxprt_v2m2 inputs = 시트 §5 + RMxprt v2 오버라이드) | 0.5/1.5/10.8103/2.0/4.86197/7.39398 |
| Coil_01…36 | 단면적 | geometry_check 'coil solid section (CoilTerm area)' (Maxwell 코일 단면 측정) | 21.1525 mm² |
| Coil_01…36 | 피치·층 | 시트 §4 (피치 8/9, 2층) + 권선 배치표 | 피치 8 슬롯 |
| Coil 엔드턴 | 경로 길이·돌출 | **visual_estimate** — 길이는 시트 l_end 121.53 mm (설계값 §6 엔드권선 도체 길이, 편측) 에 맞춤, 형상(호·부풀림)은 추정 | 경로 121.5 mm, 축 돌출 39.6 mm |
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
| 하우징 AD | — | **verify** | 발 장착 표 328 / 플랜지 표 175 (정의 다름 — 아래 §5) |
| 하우징 나머지 | AC·핀·엔드쉴드 두께·팬 커버·단자함 크기·위치·아이볼트 링·배치(어깨 x 125, 베어링 x ±108) | **visual_estimate** (housing_params.yaml) | AC_frame_od_mm 196.0, frame_body_od_mm 172.0, frame_len_mm 200.0, fin_count 28, fin_h_mm 12.0, fin_t_mm 3.0 … |

## 2. 체적 검증 (geometry_check_v2.json = Maxwell M1_3D_full 측정값, ±2 %)

| 항목 | 모델 | 기준 | 기준 출처 | 편차 | 판정 |
|---|---|---|---|---|---|
| 치+요크 Stator_Core [mm³] | 1,072,843 | 1,077,645 | geometry_check teeth_yoke.V_core | -0.45 % | PASS |
| 케이지 (바 28 + 엔드링 2) [mm³] | 413,538 | 409,740 | geometry_check cage.volume_after | +0.93 % | PASS |
| 코일 합 (코일 36개) vs geometry_check [mm³] | 389,003 | 368,424 | geometry_check coil_volume_mm3 × 36 (RMxprt 자동 엔드코일) | +5.59 % | FAIL (참고 — 현재 규칙 아님) |
| 코일 합 vs 시트 규칙 2·A·(L+l_end)·36 [mm³] | 389,003 | 390,692 | coil area 21.1525 × 2 × (L 135 + l_end 121.53) × 36 | -0.43 % | PASS |

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

- 내부 106,708 삼각형 (cutaway 84,348) · 하우징 4,964 (cutaway 3,584) · 합 111,672 ≤ 300k. 엔드턴 스플라인 분할 `--end-segments`(기본 10), 메시 허용오차는 스크립트 `tol/ang`.
- `assets/motors/M1/`: internals.step(보관, 27 MB) · internals.obj/.glb · internals_cutaway.obj/.glb · internals_parts.json(재질·체적·삼각형) · housing_100L.step · housing.obj/.glb · housing_cutaway.* · housing_parts.json · housing_params.yaml
- USD: M1_internals.usd / M1_internals_cutaway.usd / M1_housing.usd / M1_housing_cutaway.usd (omni.kit.asset_converter) → M1.usd 조립 (prim 105, 메시 {'int_full': 72, 'int_cut': 72, 'hou_full': 7, 'hou_cut': 7})

## 5. 결정 대기·한계

- **코일 엔드턴 길이**: 시트 l_end 121.53 mm(설계값 §6)로 맞추면 코일 1개 10,806 mm³ 로 Maxwell(RMxprt 자동 엔드코일) 10,234 보다 +5.59 % 크다. 지시서 규칙(시트 길이)과 검증 기준(geometry_check ±2 %)이 동시에 만족되지 않아 기본은 시트 규칙, `--end-path geometry_check` 로 바꾸면 경로 106.9 mm 로 Maxwell 체적에 맞는다. 어느 쪽을 정본으로 할지 결정 필요.
- **AD**: 발 장착(IM B3) 표의 AD 328 은 그림 B(90–200Fr) 끝면도에서 프레임 측면~단자함 끝까지의 전체 폭 치수로 그려져 있다(축 중심~단자함 상면이 아님). 플랜지(FF215) 표의 AD 175 는 플랜지 그림 기준으로 정의가 다르다. 두 값 모두 카탈로그 원문 그대로 보관하고, 하우징 모델은 HD 247(단자함 상면 높이)만 구속으로 쓴다.
- 플랜지 FF215 는 발 장착(IM B3) 카탈로그 행의 모터에는 없고 B35 옵션 치수다. 지시서가 플랜지 치수를 구속으로 주어 DE 엔드쉴드에 포함했다(P 250 > 2H 200 이라 발 바닥 아래 25 mm 까지 내려옴 — B35 실물과 같음). 뺄 수 있다.
- 엔드턴·핀·단자함·팬 커버·아이볼트는 시각 추정이며 어떤 계산에도 쓰지 않는다. 베어링은 6206 규격 치수를 그린 시각 모델이다.
- 슬롯 안 코일 단면은 Maxwell 과 같은 21.15 mm² 사다리꼴(슬롯 라이너 0.3 mm 가정)로 층 중앙에 두었다(층 중심 r 54.7/61.9 mm).

## 5b. 장면 확인 (assets/motors/M1/scene_check.json — tools/cad/check_m1_scene.py)

- 전기 시나리오 7 장면 HUD 값(장면 끝 Ia/Ib/Ic·I₂/I₁·판정) ↔ 대시보드 fleet 로그: **7/7 일치** (`motor_dt_viz\logs\m1_model\demo_20261021_110742.csv` vs `motor_dt_viz/logs/fleet/M1/electrical/demo_fleet.csv`)

| 장면 | 케이스 | 장면 Ia/Ib/Ic [A] | fleet Ia/Ib/Ic | I₂/I₁ 장면/fleet | I₂/I_n | 판정 장면/fleet | 일치 |
|---|---|---|---|---|---|---|---|
| healthy | healthy | 4.9/4.7/4.7 | 4.9/4.7/4.7 | 0.0270/0.0270 | 0.027 | SAFE/SAFE | ✓ |
| itsc_4turn | itsc_4turn | 5.0/4.7/4.5 | 5.0/4.7/4.5 | 0.0726/0.0726 | 0.0726 | WARN/WARN | ✓ |
| itsc_12turn | itsc_12turn | 5.9/4.8/3.7 | 5.9/4.8/3.7 | 0.2696/0.2696 | 0.2696 | DANGER/DANGER | ✓ |
| overload | overload | 6.6/6.3/6.3 | 6.6/6.3/6.3 | 0.0270/0.0270 | 0.0364 | DANGER/DANGER | ✓ |
| voltage_unbalance | voltage_unbalance | 5.1/4.4/4.6 | 5.1/4.4/4.6 | 0.0595/0.0595 | 0.0595 | WARN/WARN | ✓ |
| single_phasing | single_phasing | 0.2/6.0/6.0 | 0.2/6.0/6.0 | 0.4792/0.4792 | 0.414 | DANGER/DANGER | ✓ |
| no_load | no_load | 1.6/1.5/1.5 | 1.6/1.5/1.5 | 0.0270/0.0270 | 0.0089 | DANGER/DANGER | ✓ |

- FPS (1600×900, RTX 실시간): 평균 58.4 · 최소 47.2 · full 50.3 / cutaway 56.5 / windings_only 58.5 / full(후반) 60.1 — 30 FPS 기준 충족

## 6. 반입 경로·장면 사용법

1. `py -3.12 -X utf8 tools/cad/datasheet_to_yaml.py` → `py -3.12 -X utf8 tools/cad/build_internals_M1.py` → `py -3.12 -X utf8 tools/cad/build_housing_100L.py`
2. `py -3.12 -X utf8 -m pytest tests/test_m1_model.py -q` (체적·치수·개수·삼각형)
3. `C:\ISSACS~1\python.bat tools\cad\build_usd_M1.py` (저장소 루트에서, 상대 경로) → `assets/motors/M1/M1.usd`
4. 장면: `cd motor_dt_viz ; C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --m1_model [--view cutaway|windings_only]` — 22 kW 물리 모델은 숨긴 채 rpm·온도·전류 상태만 M1 USD 에 매핑한다(`motor_dt_viz/config` 변경 없음, 매핑은 `assets/motors/M1/prim_map_M1.yaml`).
5. USD 계층: /M1(스케일 0.001 = mm→m) /Housing /Stator(Core, Coils/Coil_01…36, Coils/Coil_01_short) /Rotor(xformOp:rotateX 회전 대상: Core, Bars, EndRing_DE/NDE, Shaft) /Bearings(DE, NDE) /Looks. variantSet `view` = full | cutaway | windings_only.
