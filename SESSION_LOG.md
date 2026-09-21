# SESSION_LOG.md — 권상 모터 디지털 트윈 작업 이력 및 산출물 색인 (2026-08-28 ~ 09-21)

프로젝트 루트: `디지털 트윈/크레인 퀀선 모터 모델링/`
대상: 정원크레인 10 t × 19 m 천장크레인 권상 모터 (JW-01-HTO-00, 22 kW × 6P, 1170 rpm, 285 kg)

## 1. Fusion 360 모델링 (M0~M8)
- Fusion 허브 `Default Project` 문서 **`Hoist_Motor_22kW6P_v01`** (파라메트릭, User Parameters 58개, 컴포넌트 12개, 조인트 11개, 간섭 0)
- 로컬: `export/Hoist_Motor_22kW6P_v01.f3d`, `export/Hoist_Motor_22kW6P_v01.step`(AP214), `export/step_parts/*.step` ×12, `export/mesh/HM_*.obj` ×12 (**cm 단위**)
- 문서: `dimensions.md`(치수·출처, 형상 전부 미확인(추정: IEC 200L)), `verify_parts.md`(23항목 실측 0 오차), `export_notes.md`
- 좌표 규약: 축선 +X, 상방 +Z, 원점 = DE 축단 끝면 중심

## 2. Blender 렌더링
- `export/blender/hoist_motor_render.blend` — 사진 기반 사실화 씬(환경 프록시 포함), 최종 렌더 `export/render/hoist_motor_render_final.png`
- `export/blender/hoist_motor_only.blend` — 모터 단독 + 사진 색상 재질 + `USD_Export` 컬렉션, 렌더 `export/render/hoist_motor_only_photocolor.png`
- `export/blender/build_scene.py` — 씬 재구축 스크립트

## 3. Isaac Sim v1 (S0~S8, 속도 드라이브)
- `sim/usd/hoist_motor_v01.usd`(Blender USD), `sim/usd/hoist_motor_physics_v01.usd`(강체·조인트·씬)
- `sim/output/dataset_v01/` 44런 (속도 드라이브 기반 — v2 학습용 아님, 참고 보관)
- 문서: `sim/docs/s0_env_check.md`, `s1_import_check.md`, `s2_physics_params.md`, `s4_baseline_report.md`, `s6_batch_report.md`, `s7_verification_report.md`, `README_simulation.md`

## 4. Isaac Sim v2 (E0~E8, 토크 제어 루프 + 전류 채널)
- 스크립트: `sim/scripts/e0_scene_audit.py`, `e_run.py`(러너), `motor_torque_model.py`, `fault_injector.py`(+`s5_fault_injector.py`), `current_generator.py`, `e5_selftest.py`, `e6_run_batch.py`, `e7_verify.py`, `s9_gui_demo.py`(GUI 확인용)
- 데이터셋: **`sim/output/dataset_v03/`** 76런 · 139 MB · `manifest.json` (정직성 라벨 `analytic_injection`); `dataset_v02/`는 PhysX θ float32 오차로 무효·보관
- 문서: `sim/docs/e0_scene_audit.md`, `e1_physics_params.md`, `e2_torque_control.md`, `e3_sampling_design.md`, `e5_injector_report.md`, `e6_batch_report.md`, `e7_verification_report.md`(70/72 + 원인 확인 2), `README_dataset.md`(한계 명시), `params_sources.md`(출처·미확인 목록)
- 설정: `sim/config/motor.yaml`(전 파라미터·출처), `sim/config/cad_mass_properties.json`

## 5. 환경 실행 메모
- Isaac Sim 4.5 `C:\issac sim` → 공백 때문에 **`C:\ISSACS~1\python.bat`** 로 실행; 인스턴스는 한 번에 하나만
- `World.step(render=False)`는 1/60 s 스텝 → PhysX `simulate/fetch_results` 직접 스텝 사용
- PhysX 조인트 위치는 누적각 >600 rad에서 float32 오차 → 위상은 ω 적분 사용
- `print`는 종료 시 유실 → 결과는 파일로 기록
- Blender MCP: `blender_autostart.py`로 애드온 자동 접속; Fusion MCP 브리지는 `mcp<2` 고정

## 6. 미확인 항목 (전 단계 공통)
모터 제조사/모델/프레임(200L 추정), 기동토크비 2.5, 베어링 6313/6311, 베어링 공진 800 Hz, 결함 진폭 스케일, 전류 η·pf, 측대파 dB, 편심/턴간단락 부여 규칙 출처, 회전 방향 — 상세 `sim/docs/params_sources.md`

---

# 2차 작업 (2026-09-21) — 결함 시각화 MVP · 설명 대시보드

## 7. 결함 시각화 MVP (`motor_dt_viz/`) — Phase 0~5 완료

소셜벤처 경진대회 발표용. 심사위원이 화면만 보고 "어디서, 왜 고장이 나는지" 알게 하는 것이 목표다.
두 모듈을 한 화면에서 돌린다.
- **모듈 A (기계적 결함)**: 부하 누적 발열 → 부품 색 (정상=원래 재질 → 주황 → 빨강 발광)
- **모듈 B (전기적 결함)**: 3상 전류 입자 흐름 (과전류=빨강 / 정상=초록 / 저전류=파랑)
- **통합 모드**: 모듈 B 의 상전류가 모듈 A 의 권선 동손(I²R) 입력이 된다
  → ITSC 발생 → A상 과전류 → 수십 초 뒤 권선 과열 (발표의 핵심 연쇄)

### 구조 (엔진과 시각화 분리)
- `config/` — 모든 수치의 단일 출처: `motor.yaml`(22 kW 6P, 선전류 43.7 A / 상전류 25.2 A),
  `thermal.yaml`(9노드 열회로·부품별 임계값), `electrical.yaml`(7케이스·ITSC 역산),
  `colors.yaml`(정규화 컬러맵), `scenario.yaml`(5단계 165초, 한/영 자막), `prim_map.yaml`
- `engine/` — **Isaac Sim 비의존** (pytest 가능): `thermal_model.py`(RK4 집중정수),
  `current_model.py`(대칭좌표 I₂/I₁, ITSC 위상 포함 2차식 역산), `fault_injector.py`,
  `scenario_player.py`, `config_loader.py`
- `viz/` — USD: `colormap.py`, `material_driver.py`(prim 전용 OmniPBR), `current_paths.py`,
  `current_particles.py`(Points 1개), `hud.py`
- `ui/control_panel.py` — omni.ui 제어 패널 / `app/demo_thermal|current|integrated.py`
- `tools/` — `build_parts_usd.py`, `build_physics_usd.py`, `capture_demo.ps1`, `plot_engine.py`
- `assets/motor_parts.usd`(부품 11개), `assets/motor_physics.usd`
- `tests/` — 56 passed

### 왜 USD 를 새로 만들었나
기존 USD 는 메시가 2개로 병합돼 있고 `GeomSubset` 은 머티리얼 단위라 DE/NDE 베어링을 따로
칠할 수 없었다. 파트별 OBJ 12개(`export/mesh/HM_*.obj`)로 **부품별 독립 prim USD** 를 재구성했다.
원본 에셋은 읽기 전용으로 취급한다.

### 실행
```
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay
```
플래그: `--low`(저사양) `--profile`(구간 측정) `--max_s N` `--record MP4` `--no_timecode`

### 검증 결과
- 자동 재생 5단계 실측: I₂/I₁ 0.006 → 0.104 → 0.269, DE 베어링 154.4 °C(위험),
  권선 130.6 °C(경고) — 핵심 연쇄가 화면에서 재현됨
- 성능(RTX 4060, `--profile`): 렌더 8.93 / 물리 2.61 / 입자 0.85 / 나머지 1.26 ms = 13.66 ms,
  평균 68.9 fps. **병목은 렌더링(65 %)이고 앱 코드는 4.7 ms 뿐이라 별도 최적화를 하지 않았다.**
  엔진 계산은 전부 합쳐 0.25 ms (예산의 1.5 %)
- 문서: `README.md`(실행·구조·성능·모델의 한계), `docs/record_demo.md`(녹화 절차)

### 의도적으로 하지 않은 것
부품 내부 온도 **그라디언트**. 열 모델이 부품당 노드 1개인 집중정수라, 그라디언트를 그리면
모델에 없는 분포를 화면이 지어내는 셈이 된다(추정값을 측정값처럼 보이게 만드는 일).

## 8. 설명 대시보드 (`dashboard/`) — Phase D0 완료

Isaac Sim 녹화 영상 + 로그 CSV 를 동기 재생하는 설명형 대시보드. 지침: `dashboard/CLAUDE.md`.

### D0 산출물
- 영상 `dashboard/public/media/integrated_autoplay.mp4` (1456×938, 30 fps, 172 s, 17.3 MB)
- 메타 `motor_dt_viz/logs/recording_integrated_autoplay.json` (`video_offset_s` = 2.006)
- 로그 `motor_dt_viz/logs/demo_20260921_163337.csv` (`t_real_s` 컬럼 포함)
- 바탕화면 사본 `바탕 화면/모터결함_애니메이션/07_통합_자동재생.mp4`
- Node.js 26.7.0 / npm 11.19.0 설치 완료 (Vite + React + TS 사용 승인됨)

### 시간축 동기화 (D0 완료 기준)
`영상시각 = t_real_s + 2.006`. 두 겹으로 보장한다.
1. 데모가 ffmpeg 를 직접 띄워 녹화 시작 ↔ 시나리오 시작의 시각 차이를 자동 기록
2. HUD 에 타임코드를 찍어 영상에서 눈으로 검증 (`--no_timecode` 로 끌 수 있음)

실측 오차: 영상 22 s → +0.066 / 62 s → +0.026 / 152 s → +0.046 초. **요구 0.2 s 이내, 드리프트 없음.**

### ⚠️ 확인 대기 중인 불일치
`dashboard/CLAUDE.md` 의 참고값이 실제 config 와 10배 다르다.

| 항목 | 지침서 | 실제 config |
|---|---|---|
| 모터 | 2.2 kW 범용 전동기 | **22 kW 6극 크레인 권상 모터** |
| 정격 선전류 | 4.7 A | **43.7 A** |
| 정격 상전류 | 2.7 A | **25.2 A** |

규칙 1(숫자는 config 단일 출처)에 따라 **실제 config 값으로 진행**하기로 했다.
정직성 라벨 문구도 `22 kW 6극 크레인 권상 모터 (도면 JW-01-HTO-00)` 으로 쓴다.

### 남은 일
- D1 export 스크립트(JSON 생성 + 스키마 문서 + 일치 테스트) ← 다음 단계
- 모듈 A·B 단독 데모는 **시계열 CSV 를 남기지 않는다.** 결함 도감에 차트를 붙이려면 로깅 추가 필요
- 모듈 B 를 케이스별 파일로 나누려면 `demo_current.py` 에 케이스 선택 옵션 추가 필요
- 발표용 최종 녹화는 오프셋 확정 후 `--no_timecode` 로 다시 뜰 것

## 9. 환경 실행 메모 (2차 작업에서 확인한 것)

- **경로에 공백·한글이 있으면 `.bat` 에 절대 경로를 넘기지 마라.** 인자가 깨진다.
  작업 디렉터리를 두고 **상대 경로**만 넘긴다. (`--record ..\dashboard\...` 형태)
- **ffmpeg `gdigrab -i title=` 은 Isaac Sim 에 쓸 수 없다.** Vulkan 으로 직접 그려서 창 DC 가
  갱신되지 않아 기동 직후 첫 화면만 반복해서 찍힌다(62초 지점에도 시나리오 미시작 화면).
  → `-i desktop` + `-offset_x/-offset_y/-video_size` 로 창 영역만 잘라낸다.
  종료는 stdin 에 `q` 를 보낸다(kill 하면 moov atom 이 없어 파일이 깨진다).
- **PowerShell 5.1 은 BOM 없는 UTF-8 을 ANSI(CP949)로 읽는다.** 한글 주석이 깨지면서
  `param()` 블록에서 파서 오류까지 난다. `.ps1` 은 **UTF-8 BOM** 으로 저장할 것.
- **omni.ui 기본 폰트에 한글 글리프가 없다.** `style={"font": <ttf>}` 지정도 4.5 에서는 미적용.
  → HUD·제어 패널은 영문 표기, 한국어는 편집 자막으로.
- **omni.ui 의 `style={"margin": N}` 은 VStack 자신이 아니라 모든 자식에 상속**되어 행 높이를
  부풀린다. 값이 크면 아래 내용(정직성 라벨 등)이 창 밖으로 밀려난다.
- **Isaac Sim 은 본 창과 제목이 같은 작은 보조 창(160×28)을 함께 띄운다.** 창을 찾을 때는
  제목만 보지 말고 **면적이 가장 큰 것**을 고른다.
- `t_wall`(프레임 수 × 1/60)은 실제 시간이 아니다. 렌더가 70 fps 면 17 % 빨리 흐른다.
  시나리오·열 적분·영상 동기화는 **벽시계 dt** 를 써야 한다. (165초 시나리오가 141초에
  끝나던 버그의 원인)

---

## 10. 기계/전기 결함 분리 (2026-09-21, 진행 중)

기계적 결함(열)과 전기적 결함(전류)을 **완전히 독립된 두 결과물**로 나누는 작업.
심사위원이 한 번에 한 가지 결함 유형만 보게 하는 것이 목적이다. 지시서는 일회성 작업 문서로
받았고, 통합 결과물은 지우지 않고 그대로 둔다.

### 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| S0 | 현황 파악, 분리 계획 | **완료** (사용자 승인) |
| S1 | 시뮬레이션·시나리오 분리 | **거의 완료** — 모드 전환 잔상 시각 검증만 남음 |
| S2 | 모드별 재녹화, 장면 클립, 바탕화면 정리 | 미착수 |
| S3 | 대시보드 2화면 분리 | 미착수 |

### 백업
분리 전 상태를 `_backup_통합_20260921/` 로 복사해 두었다 (motor_dt_viz 107 파일 + dashboard,
25.3 MB). git 저장소가 아니어서 폴더 복사로 보존했다.

### S0 에서 확인한 것

통합 지점은 7곳이었고, 뼈대는 이미 절반쯤 나뉘어 있었다. `demo_integrated.py` 에
thermal/electrical/integrated 세 모드가 있었지만 **일부 계산만 끄는 수준**이라 화면에는
두 결함이 섞여 나왔다. 특히 전기 모드에서 `driver.update()` 를 호출하지 않을 뿐이라
직전 모드의 발열 색이 그대로 남았고, HUD 는 모드와 무관하게 전류·온도를 항상 모두 띄웠다.

전류 → 권선 발열 연결은 두 줄뿐이고(`demo_integrated.py:370,376`), 끊어도 안전하다.
`thermal_model.losses()` 가 `winding_current_pu` 가 None 이면 부하율로 대체하기 때문이다
(`i_pu = winding_current_pu if ... is not None else eff_load`). 잔상 제거에 쓸
`MaterialDriver.reset_to_base()` 도 이미 있었다.

**지시서와 실제가 어긋난 두 건을 보고하고 승인받았다.**

1. "gdigrab 사용 금지" → 실제로 못 쓰는 것은 `-i title=` 뿐이다. 지금 검증된 유일한 방법이
   `-i desktop` + 창 좌표 crop 이므로 그대로 쓴다.
2. "ITSC 장면은 Maxwell 2D 해석으로 표기" → **Maxwell 은 실행한 적이 없다**
   (AEDT 라이선스 부재, `electrical.yaml` 3~13행에 명시). 모든 전기 장면을 "해석식 모델"로
   표기하고, ITSC 에는 "목표 I₂/I₁ 을 재현한 등가 표현"을 덧붙인다.

### S1 산출물

- `config/scenario_mechanical.yaml` — 7단계 180초
  (정상 25 → 베어링 35 → 오정렬 25 → 냉각팬 25 → 브레이크 20 → 과부하 30 → 냉각 20)
- `config/scenario_electrical.yaml` — 7단계 165초
  (정상 20 → ITSC4 25 → ITSC12 30 → 과부하 20 → 불평형 25 → 결상 25 → 무부하 20)
- 두 파일 모두 장면마다 `source` / `source_en` (데이터 출처)를 갖는다 — 정직성 표기
- `engine/scenario_player.py` — `ScenarioPlayer.for_mode(mode)` 로 모드별 config 선택
- `viz/hud.py` — 섹션 단위 표시/숨김(`set_mode`), 온도 범례 추가, 출처 라벨 추가,
  정직성 문구를 모드별로 바꿔 쓰지 않은 모델을 적지 않게 함
- `ui/control_panel.py` — 모드 3버튼(기계/전기/통합), 모드별 토글 숨김, 전환 시 리셋 요청
- `app/demo_integrated.py` — `--mode`, `--switch_seq`(전환 검증용), 모드 전환 시
  `reset_to_base()` + 입자·경로 숨김 + HUD 모드 전환 + 열 모델 리셋
- `tools/capture_demo.ps1` — `-Mode` 인자, 모드별 단계 맵
- 테스트 56 → **63개** (모드별 시나리오 6건 + dt=0 회귀 1건)

### 검증 결과

| 완료 기준 | 결과 |
|---|---|
| 기계 전용에서 전류 요소 0개 | **확인** (7단계 캡처) |
| 전기 전용에서 발열 색 불변 | **확인** (온도 25 °C 고정, 원래 재질) |
| 모드 전환 잔상 없음 | 로그로는 확인(전기 25 °C ↔ 기계 144.7 °C), **시각 검증 미완** |
| 30 FPS 이상 | 기계 98.2 / 전기 80 fps |

기계 시나리오 실측(엔진 드라이런): 정상 권선 63.9 → 베어링 결함 135.8 °C(danger) →
오정렬(축 78.1) → 냉각팬(하우징 72.6) → 브레이크(축 121.2 danger) → 과부하(권선 122.4
warning) → 냉각(권선 94.2). 결함마다 **다른 부품**이 달아오른다.

전기 시나리오 실측: 정상 I₂/I₁ 0.006 → ITSC4 0.104 → ITSC12 0.269 → 과부하 0.000(균형 유지)
→ 불평형 0.0595 → 결상 0.4792 → 무부하 0.000.

### 이번에 찾아 고친 문제

1. **결함 누적으로 베어링 483 °C.** 기계 시나리오에서 결함을 쌓았더니 `loss_multiplier` 가
   곱해져(베어링 5.0 × 오정렬 2.5 = 12.5배) 물리적으로 불가능한 값이 나왔다.
   → 단계마다 **그 결함만** 켠다. 최고 135.8 °C 로 정상화됐고, 어느 결함이 어느 부품을
   달구는지가 오히려 명확해졌다.
2. **`dt_sim_s=0` 에서 `thermal_model.step()` 이 TypeError.** 전기 전용 모드는 열을 dt=0 으로
   멈추는데, 적분 루프를 돌지 않아 손실 배열이 None 으로 남았다. 이 경로는 **한 번도 실행된
   적이 없었다**(통합 모드로만 테스트했기 때문). → 루프 전에 손실을 한 번 계산한다. 회귀 테스트 추가.
3. **전압 불평형 자막이 사실과 달랐다.** "특정 상만 색이 바뀐다"고 썼지만 실제로는 세 상 모두
   정상 범위(47.2/41.1/42.8 A)라 색이 안 바뀐다. → "색은 아직 정상이지만 I₂/I₁ 이 열 배 오른다"로
   고쳤다. 크기보다 균형이 먼저 무너진다는 점이 오히려 좋은 설명이 된다.

### ⚠️ 확인 대기: 과부하 케이스 이중 적용

`config/electrical.yaml` 의 `overload` 는 `phase_scale: [1.35,1.35,1.35]` 와 `load: 1.35` 를
둘 다 갖고 있고, `current_model.waveform()` 이 **둘을 곱한다**(131행)
→ 실제 전류는 43.7 × 1.82 = **79.6 A (182 %)** 인데 라벨은 "과부하 135 %" 였다.

작업 원칙 3(수치 결정은 이 작업에서 하지 않는다)에 따라 config 는 건드리지 않고,
화면에 확인되지 않은 숫자가 나오지 않도록 **라벨에서 "135 %" 만 뺐다**.
고치려면 `phase_scale` 이나 `load` 중 하나를 1.0 으로 두면 된다.

### 다음에 할 일 (내일)

1. S1 마무리 — 모드 전환 잔상 시각 검증 (`--switch_seq` 로 재실행, 캡처 타이밍 주의)
2. S2 — 기계·전기 재녹화, 장면별 클립 분할, 바탕화면 폴더를 `1_기계적결함/2_전기적결함/3_통합/`
   으로 정리 후 MD5 대조
3. S3 — 대시보드 2화면 분리 (Vite + React + TS, `#/mechanical` · `#/electrical`)

예상 소요: S1 마무리 15분 + S2 40분 + S3 2.5~3시간 + 마무리 20분.
