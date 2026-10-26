# SESSION_LOG.md — 권상 모터 디지털 트윈 작업 이력 및 산출물 색인 (2026-08-28 ~ 09-22)

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
- 영상 `dashboard/public/media/integrated_autoplay.mp4` (1456×938, 30 fps, 172 s, 16.6 MB — 2026-10-08 R·S·T HUD·타임코드 없음으로 재녹화, 이전 판 `media/integrated_backup_phA/`)
- 메타 `motor_dt_viz/logs/integrated/recording_integrated_autoplay.json` (`video_offset_s` = 2.004; 2021-09 판은 2.006)
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

## 10. 기계/전기 결함 분리 (2026-09-21 ~ 22, 완료)

기계적 결함(열)과 전기적 결함(전류)을 **완전히 독립된 두 결과물**로 나누는 작업.
심사위원이 한 번에 한 가지 결함 유형만 보게 하는 것이 목적이다. 지시서는 일회성 작업 문서로
받았고, 통합 결과물은 지우지 않고 그대로 둔다.

### 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| S0 | 현황 파악, 분리 계획 | **완료** (사용자 승인) |
| S1 | 시뮬레이션·시나리오 분리 | **완료** (전환 잔상 4장 검증 포함, 9-22) |
| S2 | 모드별 재녹화, 장면 클립, 바탕화면 정리 | **완료** (9-22) |
| S3 | 대시보드 2화면 분리 | **완료** (9-22) |

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
| 모드 전환 잔상 없음 | **확인** — 통합(가열)→전기→기계→통합 4장 캡처 (`sw_t056/072/092/112`) |
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

### S1 마무리에서 겪은 것 (9-22)

- 전환 검증 캡처가 어제 빈 이미지였던 이유: 데모 창을 `-WindowStyle Minimized` 로 띄웠다.
  최소화된 창은 좌표가 화면 밖(-32000)이라 캡처가 빈 비트맵이 된다. **창은 항상 Normal.**
- 로그 기록 조건을 "마지막 기록 후 0.25 s"로 바꿨더니 모드 전환에서 `t_real` 이 0 으로 돌아가
  62초 동안 기록이 멈췄다. → 절대 리셋하지 않는 `t_session` 시계를 두고 기록·`--max_s`·`--switch_seq`
  의 기준을 그쪽으로 옮겼다.
- 전환 테스트 경로(`--switch_seq`)도 제어 패널 버튼과 같은 `_set_mode` 를 타게 해, 전기로 넘어갈 때
  기계 결함이 해제되는 동작이 시연과 테스트에서 동일하다.

### S2 결과 — 모드별 재녹화

| 모드 | 시나리오 | 영상 | 로그 끝 | 동기 오차 (22 s / 중간 / 끝) |
|---|---|---|---|---|
| 기계 | 180 s | 187.5 s, 6.7 MB | 184.9 s | +0.08 / +0.08 / +0.07 s |
| 전기 | 165 s | 172.5 s, 13.3 MB | 169.9 s | +0.04 / +0.05 / +0.05 s |

- 도구: `tools/record_mode.ps1`(녹화 → 동기 검증 프레임 → 클립, `-SkipRecord` 로 후처리만),
  `tools/split_clips.py`(시나리오 duration + 오프셋으로 장면 클립 절단, `clips_index.json`),
  `tools/publish_desktop.ps1`(바탕화면 `1_기계적결함/2_전기적결함/3_통합` + MD5, `-Verify`)
- 산출: `dashboard/public/media/{mechanical,electrical}/` (전체 + `clips/` 7개씩),
  `motor_dt_viz/logs/{mechanical,electrical}/`, 바탕화면 17개 파일 MD5 전부 일치 (OneDrive 동기화 경로 안)
- 겪은 것: PowerShell 5.1 이 UTF-8 JSON 을 ANSI 로 읽어 한글 경로가 깨지며 `ConvertFrom-Json` 이
  실패했다. **`Get-Content -Raw -Encoding UTF8`** 을 명시해야 한다 (BOM 문제와 같은 계열, 이번엔 읽는 쪽).

### S3 결과 — 대시보드 2화면 분리 (`dashboard/`)

- 스택: Vite 5 + React 18 + TypeScript + ECharts 5 (번들), CSS 변수 테마(다크 기본·라이트 토글).
  외부 폰트·CDN 없음. `--host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE localhost"` 로 인터넷을 차단한
  헤드리스 Edge 에서 6장 캡처 성공 → 오프라인 동작 실증.
- 라우팅: 해시(`#/mechanical`, `#/electrical`), 첫 화면은 선택 화면. `?t=초` 로 시각, `?tab=` 로 하단 탭 지정.
- 데이터: `dashboard/tools/export_dashboard_data.py` 가 `engine/` 을 재사용해
  `public/data/<mode>/{thresholds,scenarios,timeseries,faults}.json` 생성. `dashboard/tests/test_export.py`
  17건이 config·로그와 대조(정격·비율×정격·부품별 임계값·색상·챕터 구간·시계열·FEM 표기 금지).
- 동기화: 영상 `currentTime` 이 단일 시간 소스, `t_real = currentTime − video_offset_s`. 차트 클릭 → seek.
  seek 직후 영상 시각이 목표에 닿기 전까지는 상태를 덮어쓰지 않는 `pending` 처리(없으면 커서가 0 으로 튄다).
- 리드 타임: 기계 = 주의 진입(경보) → 위험 진입 = **1.5 s (시뮬레이션 약 3.0 분)**.
  전기 = I₂/I₁ ≥ 0.104(4턴 목표) → 위험 과전류 = **0 s** — 해석식 모델이 ITSC 를 크기 불평형으로
  등가 표현해 두 신호가 동시에 변하기 때문. 화면에 "동시 — 해석식 모델의 한계"로 표기.
- 콘텐츠: `src/content/{mechanical,electrical}.ts` — 챕터별 3문장(무엇이 보이나/왜/현장에서는),
  결함 도감 5+5 카드(클릭 → 해당 장면), 용어 풀이(전기: 저전압→과전류 등 전압-전류 관계 포함).
  숫자는 전부 JSON 참조. 색각 대응으로 상태에 ●◐▲■ / ▲▼ 아이콘 병기.
- 실행: `run_dashboard_mechanical.bat` / `run_dashboard_electrical.bat` → `node serve.cjs --open <mode>`
  (Range 요청 지원 정적 서버, 의존성 없음). 경로 공백·한글 대응으로 `cd /d "%~dp0"` 만 쓴다.
- 스크린샷: `dashboard/docs/screenshots/` — 1920×1080·1366×768 × 기계/전기 + 결함 도감 + 용어 풀이.
  헤드리스에서는 영상 프레임이 검게 나온다(브라우저 제약) — 실제 화면에서는 재생됨.
- 동기 검증 절차: `dashboard/docs/sync_check.md`.

### 아직 남은 것

- `electrical.yaml` 과부하 이중 적용(182 %) — 확인 대기. 화면에는 비율 숫자를 쓰지 않았다.
- 발표용 최종 영상은 `record_mode.ps1 -NoTimecode` 로 다시 뜰 수 있다(오프셋은 확정값 사용).
- GitHub: https://github.com/kimsunwu4981-ship-it/motor-predictive-maintenance (비공개, 설명 "모터 예지보전").
  한글 리포명은 GitHub 이 `---` 로 깎아 버리므로 영문 이름을 쓰고 한글은 설명에 둔다.
  실수로 생긴 빈 리포 `zz-empty-delete-me` 는 토큰에 delete_repo 범위가 없어 삭제하지 못했다 — GitHub 설정에서 지울 것.


## 11. 기계적 결함 실시간 해설 대시보드 (2026-09-22, M0~M5 완료)

`#/mechanical` 을 "영상 + 표"에서 **영상과 같은 순간에 해설·자막·그래프·단면도가 함께 움직이는 화면**으로 확장했다.
전기 대시보드(`#/electrical`)는 손대지 않았다. 지시서 `TASK_기계실시간해설` 의 M0~M5 를 단계마다 보고·승인하며 진행했다.
커밋: M1 `e0ee627`, M2 `c1dcf0c`, M3 `22b6469`, M4 `c8340d6`, M5 `dc301a2`.

### 11.1 구조

```
dashboard/
├── tools/export_mechanical_extras.py    # 엔진 재실행(손실열·배속·시뮬 경과) + 이벤트 자동 추출 + 해설 치환 변수
├── public/content/mechanical/           # 문구 (런타임에 읽음 — 새로고침만으로 반영)
│   ├── narration.yaml                   #   장면별 제목·지문·주목 부품·열 경로·reveal_timing·왜/보이나/그래서·멘트·인과 카드
│   ├── event_templates.yaml             #   사건 → 자막 문장 템플릿
│   └── qa.yaml                          #   예상 질문과 답 (Q 서랍)
├── public/data/mechanical/              # export 산출 (git 제외): thresholds/scenarios/timeseries/faults + events.json + narration_values.json
├── src/mech/                            # 기계 전용 화면 요소
│   ├── data.ts        (MechData 타입, YAML 로더, fill/fillParts, liveValues = {부품}_now 실시간 변수)
│   ├── captions.ts    (사건 묶음·우선순위·자막 유지·reveal 시각·이력 목록)
│   ├── colormap.ts    (viz/colormap.py 포팅 — 단면도 색 = 영상 색)
│   ├── HUDLive / LiveNarration / CaptionBar / MotorSchematic(+MiniMotor) / TempChart / VibChart / CausePanel / QaDrawer
│   ├── broadcast.ts   (메인 ↔ 발표자 화면 BroadcastChannel)
│   └── schematic.css, presenter.css
├── src/pages/MechanicalLive.tsx         # 조립·키보드·모드·채널
├── src/pages/PresenterView.tsx          # #/mechanical/presenter
├── tools/record_dashboard.ps1           # 대시보드 자동 재생 화면 녹화 (Edge 앱 창 + gdigrab)
├── tests/test_mechanical_extras.py      # 16건 (재실행 오차, 손실=config, 이벤트=로그, 변수 정의, PDF 18숫자=로그, 컬러맵 원본, 템플릿 변수)
└── docs/narration_review.md · first_viewer_check.md · electrical_apply_notes.md · sync_check.md(확장)
```

화면(1920×1080): 상단 바(장면 n/7·지문·주목 부품 등급 뱃지·**시간 압축**·정직성 라벨) / 영상+자막 띠 ‖ 실시간 해설(단계별 공개 + 이력) ·
모터 단면도 / 온도 차트 · 진동 차트 · 원인 패널(인과 카드 + 손실열 막대 + 결함 지문 미니맵). 1366×768 은 세로 스크롤.

### 11.2 숫자 출처 (규칙 1)

- 온도·진동·등급·시각: `logs/mechanical/demo_*.csv` (정본). 손실열은 로그에 없어 **엔진을 같은 시나리오로 재실행**해 얻었다.
  손실은 결함·부하만의 함수(온도 무관)라 재실행값이 정확값이고, 재실행 온도는 검증에만 쓴다(장면 경계 ±1 s 제외 최대 2.28 °C, 허용 2.5).
- 임계값·컬러맵·ISO 진동 경계·열 경로·정격 손실: `config/*.yaml` → `thresholds.json`.
- 사건(등급 변화·진동 등급·투시·장면 전환·정상 복귀) 49건: export 가 로그에서 뽑는다. 사람이 시각을 넣지 않는다.
- 해설의 `{변수}`: `narration_values.json`(장면 종료 값) + 화면이 채우는 `_now`(재생 시각 값).
- 해설 PDF 의 숫자 18개는 `test_guide_pdf_numbers_match_log` 가 로그와 대조한다(허용 0.15 °C). **재녹화하면 이 테스트를 먼저 본다.**

### 11.3 문구 수정 방법

`public/content/mechanical/*.yaml` 을 고치고 브라우저 새로고침. 빌드 불필요. 숫자는 쓰지 말고 파일 머리의 변수 목록을 쓴다.
멘트(`presenter_line`)는 발표자 화면에만 나간다. 변수 오타·미정의는 `pytest tests` 가 잡는다. PDF↔화면 대응표는 `docs/narration_review.md`.

### 11.4 조작

`F` 발표 모드 · `Space` · `←/→` · `1~7` · `C` 자막 · `N` 다음 해설 단계(발표자 모드) · `Q` 예상 질문. 상단 버튼: 자동 해설/발표자 모드, 발표자 ↗(새 창).
주소: `#/mechanical?t=27`(장면 바로 열기), `&qa=1`, `&autoplay=1&delay=6`(녹화용), `#/mechanical/presenter?t=40`(발표자 화면 연습).

### 11.5 겪은 문제와 해결

- **결함 누적으로 483 °C** → 장면마다 결함 하나만 켠다(시나리오 재구성, PDF 도 그 기준).
- **재실행 온도가 장면 경계에서 5.4 °C 어긋남** → 프레임 정렬 차이. 경계 ±1 s 를 검증에서 제외하고 안쪽 2.5 °C 허용(사용자 승인).
- **`narration.yaml` 을 빌드에 넣으면 문구 수정마다 빌드** → `public/` 에 두고 런타임 fetch(캐시 무력화 쿼리).
- **한 줄 자막(nowrap)이 CSS 그리드 열을 넓혀 영상 열이 눌림** → `minmax(0, …)` 과 `min-width: 0`.
- **이력 항목 class 가 `narr` 로 패널 class 와 충돌**(flex column 이 되어 3줄로 깨짐) → `k-narr` 로 접두.
- **자막을 영상 위에 겹치면 Isaac Sim HUD 글자와 겹쳐 둘 다 안 읽힘** → 영상 바로 아래 고정 높이 띠.
- **헤드리스 스크린샷은 CSS 전환·애니메이션이 멈춘 채 찍힘** → 손실 막대 길이·페이드가 실제와 다를 수 있다. 실제 모습은 녹화 프레임.
- **헤드리스 `--screenshot` 에 한글·공백 경로를 주면 종료 코드 13** → `C:\Temp` 에 찍고 복사.
- **Bash 도구의 긴 heredoc(≈8 KB 이상)은 잘려 "unexpected EOF"** → 큰 파일은 Write 도구, 작은 수정은 python 치환.
- **화면 녹화: 첫 시도는 Space 키 주입이 다른 창(VS Code)에 들어갈 뻔했고 그 창이 앞을 가림** → 키 주입 제거, `?autoplay=1&delay=6` 으로
  페이지가 스스로 재생, 창은 topmost, Edge 앱 창의 제목줄 31 px 만큼 아래에서 crop, `-draw_mouse 0`.
- **HUD 버튼이 6개가 되자 1920 에서 두 줄** → 버튼 문구 축약·패딩 축소, 1366 은 테마 버튼·지문 숨김.
- **발표자 화면이 정지 중 "연결 없음"** → 메인이 1 s 심장박동을 보낸다.
- **`run_dashboard_mechanical.bat` 를 cmd /c 로 돌리면 못 찾음** → Start-Process 로 배치 파일을 직접 실행(더블클릭과 같음).

### 11.6 산출물

- 녹화: `모터결함_애니메이션/08_기계_실시간해설_대시보드_1920x1080.mp4` (7장면 자동 해설 192 s, git 제외; 타임코드가 있던 영상 기준)
- 발표용 재녹화(-NoTimecode, 09-22 17:45): 로그 `logs/mechanical/demo_20260922_174529.csv`, 오프셋 2.008 s, 재export 후 33건 통과
  (PDF 숫자 모두 0.15 °C 이내), 리드 타임 1.55 s. 타임코드 판은 `public/media/mechanical_backup_timecode/` 에 보관.
- 스크린샷: `dashboard/docs/screenshots/m2_*`, `m3_*`, `m4_*`, `m5_*`
- 한계: 헤드리스로는 영상 프레임 동기를 못 본다(실제 창에서 `?t=27.5` 로 눈 확인, `docs/sync_check.md`). 발표자 화면은 같은 브라우저
  프로필 창끼리만 동기. 전기 적용 메모는 `docs/electrical_apply_notes.md`.


## 12. 전기적 결함 실시간 해설 대시보드 (2026-09-22 밤, E0~E5 완료) + 상 표기 R·S·T 통일

`#/electrical` 을 기계(11장)와 같은 실시간 해설 화면으로 확장했다. 지시서 `TASK_전기실시간해설` 의 E0~E5 를 단계마다 보고하며 진행했고,
기계 작업의 공통 부분을 `src/live/` 로 빼내 두 대시보드가 같은 코드를 쓴다. 커밋: E1 `3f5fd68`, E2 `91e6b64`, E3 `d8034db`, E4 `c835d5c`,
R·S·T `58c7249`, 마무리 (아래).

### 12.1 구조

```
dashboard/
├── src/live/                  # 공통 (기계·전기)
│   ├── types.ts     LiveData(mode, scenarios, events, values, content, live(t), timeNote(t)), fill/fillParts
│   ├── load.ts      JSON/YAML 로더 (문구는 런타임에 읽음)
│   ├── captions.ts  사건 묶음(1 s, 우선순위)·자막 유지·reveal_timing·이력 목록 — 전기 사건은 export 가 붙인 tpl 키를 그대로 씀
│   ├── CaptionBar / LiveNarration / QaDrawer(+용어 풀이) / broadcast.ts(채널 vigent-<mode>)
├── src/elec/                  # 전기 전용
│   ├── data.ts        ElecData(ratio·phase_rms·phasor_deg·case·matrix·waveforms·phase_labels), liveValues({a|b|c}_rms_now…), ampere(basis)
│   ├── HUDElec        주목 상 뱃지 · 슬로모션 60배 표시 · 선/상전류 토글(L)
│   ├── CurrentBars + CurrentTrend   상별 막대(config 5구간 배경, 상태색, ▲▲/●/▼▼) + 추세(미래 숨김, 리드 타임 0 s 표시)
│   ├── I2I1Panel      게이지(정상/4턴/12턴 눈금) + 추세(눈금 통과·균형만 무너짐 마커)
│   ├── PhasorPanel    페이저도 SVG (정격 원, 120° 기준선, 상태색 화살표), P 확대
│   ├── CircuitSchematic  Δ결선 회로도 SVG — 케이블(선전류)·권선(상전류), 교류 진동 입자(1 Hz = 60 Hz/60), 단락 루프·끊김·전압 정성 표기
│   └── Panels.tsx     인과 카드 + 결함 판별 매트릭스(세로 크기 × 가로 균형 √눈금, 7장면 점 + 실시간 ◉, 판별 규칙 줄)
├── src/pages/ElectricalLive.tsx · PresenterView.tsx(mode 매개변수) · App.tsx(#/electrical/presenter, #/electrical/classic)
├── tools/export_electrical_extras.py   엔진 재계산(비율·상전류·위상), 사건 추출, 해설 변수, 매트릭스 좌표, 파형, phase_labels
├── public/content/electrical/ narration.yaml · event_templates.yaml · qa.yaml · glossary.yaml
├── tests/test_electrical_extras.py     16건 (재계산=로그, 로그 RMS+위상→I₂/I₁, 페이저 기하, 임계 암페어=config, 사건=로그, 리드 0 s,
│                                        균형만 무너짐, 템플릿 변수, 해설 변수, 매트릭스, PDF 3장 8줄·1장 암페어 5개, qa/glossary 변수)
└── docs/narration_review_electrical.md · first_viewer_check_electrical.md · sync_check.md(전기 절)
```

### 12.2 숫자 출처

- 로그(`logs/electrical/demo_*.csv`)에는 상별 선전류 RMS 와 I₂/I₁ 만 있다. 정격 대비 비율·상전류(비율 × 25.2 A)·기본파 위상은
  **엔진(`engine/current_model.py`)으로 재계산**했다 — 해석식·결정론적이라 재계산값이 정확값이고, 로그와 최대 0.05 A 차이.
  로그 RMS + config 위상으로 대칭좌표를 다시 계산하면 기록된 I₂/I₁ 과 0.0004 안에서 같다.
- 전압은 모델 입력이 아니다. 장면 5(공급전압 불평형)는 전류 불평형(크기 1.08/0.94/0.98, 위상 +2/−3/+1°)을 직접 넣은 것. 화면에 전압 숫자는 없고
  회로도 전원 쪽에 "원인 · 모델 입력 아님"으로 정성 표기.
- 사건 23건: 상별 상태 변화(세 상이 같은 상태가 되면 하나로 묶음), I₂/I₁ 눈금(4턴·12턴) 통과(한 스텝에 여럿이면 가장 높은/낮은 눈금만),
  "균형만 무너짐"(세 상 정상인데 I₂/I₁ > 정상 목표값 × 5 — 장면 5 는 9.9배), 단락 루프 표시 on/off, 장면 전환. 케이스 전환이 장면 경계보다
  한 로그 스텝 먼저 찍히므로(119.918 vs 120.0 s) 사건의 장면은 행의 step 으로 정한다.
- 리드 타임 0 s(I₂/I₁ 4턴 도달 = R상 위험 과전류, 같은 행) 를 그대로 표시. 균형 지표의 가치는 장면 5로 말한다.
- 과부하 장면은 config 가 `phase_scale 1.35 × load 1.35` 를 곱해 **정격의 182 %**(79.6 A)였다. 사용자 승인으로 `phase_scale` 을 1.0 으로 고쳐
  135 %(59.0 A)로 바로잡고 전기 영상·대시보드 녹화·PDF 장면 4 를 다시 만들었다(23:30). 기계 리드 타임도 PDF 5장을 1.55 s / 3.1 분으로 고쳤다.

### 12.3 상 표기 R·S·T (2026-09-22 결정)

사용자가 "A·B·C 대신 R·S·T" 를 택했다(현장 관례). `config/electrical.yaml` 의 `phase_labels: {A: R, B: S, C: T}` 하나가 출처이고
Isaac HUD("Ph R")·데모 라벨·시나리오 자막·export(`phase_label`, `{ph_a}` 변수)·대시보드·해설 원문·PDF 가 모두 그것을 따른다.
**내부 키(로그 `Ia_rms`, config 순서, 엔진 변수)는 A/B/C 그대로** — 문구에 "A상"을 직접 쓰지 말고 `{ph_a}상` 을 쓴다.

### 12.4 조작

기계와 같음 + `L` 선/상전류 전환, `P` 페이저 확대. `#/electrical?t=30`, `&qa=1`, `#/electrical/presenter`. 이전 탭형 화면은 `#/electrical/classic`.

### 12.5 겪은 문제와 해결

- **numpy bool 이 JSON 에 안 들어감** → `bool()` 로 감싼다. **시나리오 끝의 `manual` 행** → 마지막 케이스를 이어 쓴다.
- **한 스텝에 I₂/I₁ 눈금 두 개 통과(0.269→0)** → 오를 때 최고, 내릴 때 최저 눈금만 사건으로.
- **ECharts 세로 markLine 라벨이 회전** → `position: "end", align: "left"` (기계 차트와 같은 방식).
- **막대 배경 띠 opacity 가 글자까지 흐리게** → rgba 배경으로.
- **화면 녹화가 다른 창을 찍음(3회)** — 브라우저(YouTube)·VS Code·bat 이 연 브라우저가 앞에 있었다. gdigrab 은 화면을 찍으므로 녹화 15분 동안
  화면을 비워야 한다. 사용자에게 알리고 "시작" 신호 뒤에 체인(Isaac → export → 빌드 → 대시보드 2건)으로 한 번에 돌렸다.
  `run_dashboard_*.bat` 를 검증 목적으로 돌리면 사용자 브라우저가 앞으로 나오므로 녹화 전에 하지 않는다.
- **재빌드·재export 뒤에도 브라우저에 옛 화면(A상, 오프셋 2.008)이 남음** — serve.cjs 가 캐시 헤더를 안 보내고 JSON·영상 요청에 캐시 무력화가 없었다
  → 서버 `Cache-Control: no-store`, JSON `?v=Date.now()`, 영상 `?v=<오프셋>`. 이미 캐시된 브라우저는 한 번 Ctrl+F5.
- **PDF 재생성 절차가 스크립트로 없었음** → `motor_dt_viz/tools/build_guide_pdf.ps1` (-Publish 로 산출물 폴더 복사).

### 12.6 산출물

- 영상: `모터결함_애니메이션/2_전기적결함/*.mp4` (R·S·T HUD, 과부하 135 %, 타임코드 없음, 오프셋 2.003 s, 23:18 재녹화), `09_전기_실시간해설_대시보드_1920x1080.mp4`,
  `08_기계_실시간해설_대시보드_1920x1080.mp4`(회귀 재녹화). 이전 타임코드 판은 `dashboard/public/media/electrical_backup_timecode/`.
- 스크린샷: `dashboard/docs/screenshots/e2_*`, `e3_*`, `e4_*`.
- 오프라인·bat: 번들에 외부 URL 없음, DNS 차단 브라우저로 스크린샷, 두 bat 모두 실행 확인.

## 13. 보편 크레인 권상 모터 5종 — 다중 모터 디지털 트윈 상태 대시보드 (2026-10-07, P0~P4 완료)

지시서 `TASK_다중모터`(VIGENT MVP). 모터 고유값을 라이브러리로 빼고, 판정 엔진을 만들고, 5종을 엔진만으로 배치 실행해 상태 보드(`#/status`)에 올렸다.
사용자 지시 "진행하고 앞으로 허가 없이 진행 계속해"(P3부터) 에 따라 단계 보고는 남기되 승인 대기 없이 이어서 진행했다.
커밋: P1 `21fa3d3`, P2 `2255975`, P3 `95af80d`, P4 (아래).

### 13.1 P0 현황 (보고만)

- 모터 고유값이 `motor.yaml`·`thermal.yaml`(노드 질량·손실)·`electrical.yaml`(honesty_sub)·시나리오 자막·`hud.py` 문자열·`qa.yaml` 에 흩어져 있었다.
- 엔진(`ThermalModel`, `CurrentModel`, `FaultInjector`)은 cfg 주입을 받으므로 라이브러리로 바꿔 끼울 수 있다. Isaac 은 headless 가능하지만 배치는 엔진만으로(결정적·정확).
- 사양 의문점(M5 1170 vs 1180 rpm, η/cosφ, geometry_scale 기준, 22220 치수, M4 15 kW 경계)은 보고했고 답이 없어 기본값으로 진행했다.

### 13.2 P1 모터 라이브러리 (`motor_dt_viz/config/motors/M1..M5.yaml`, `engine/motor_library.py`)

- 스키마 검증·파생값(슬립, BPFO/BPFI Hz, 토크, 손실)·`motor_spec()`·`electrical_cfg()`·`thermal_cfg()`.
- 열회로 스케일(M5 기준): 손실 ∝ P(1−η)/η, 대류 저항 ∝ 1/s², 열용량 ∝ s³ (s = 프레임 비례 geometry_scale). M5 는 원본과 동일(회귀).
- 진동 규격: 15 kW 미만 ISO 10816-1 Class I (1.8/4.5), 이상 ISO 20816-3 Group 2 (1.4/2.8/4.5). `docs/thermal_scaling.md` 에 5종 수렴 온도표.

### 13.3 P2 판정 엔진 (`engine/thresholds.py`, `config/thresholds.yaml`)

- SAFE/WARN/DANGER, 종합 = 최악 등급 + 원인 신호(초과 비율 최대), 히스테리시스 5 %, 지속 3 s(전류·진동·I₂/I₁·베어링 지표; 온도 0), 첫 호출 즉시, 4→3 대응.
- 규칙 모듈에 임계값 숫자가 없음을 테스트가 확인한다. 모두 SAFE 면 원인 "-" (P3 에서 추가).

### 13.4 P3 배치 (`tools/run_fleet.py`, `tools/fleet_summary.py`, `docs/fleet_summary.md`)

- 5종 × 기계·전기를 엔진만으로 1/60 s 적분, 4 Hz 로그 → `logs/fleet/<id>/<mode>/demo_fleet.csv`(데모 컬럼 동일) + `status_fleet.csv`(판정) + `meta.json`. 7 s.
- M5 회귀: 엔진 ↔ Isaac 로그 장면 끝 최대 차 0.1 °C / 0.0 A.
- 결과: 정상 수렴 권선 57.1/64.2/73.7/79.0/87.6 °C. 베어링 장면 온도만으로 위험 도달 M5 2.5 s, M4 3.5 s, M3 4.0 s, M2 25.5 s, M1 미도달(위험 판정은 진동 4.8 이 만든다).
  냉각 속도 M1 > … > M5 (물리 검사 이상 없음). 전기는 비율 기준이라 5종 등급 동일(암페어만 다름).
- 판정은 로그에 적힌 반올림 값으로 하도록 고쳐 로그만으로 재판정해도 행 단위로 같다 (대시보드 테스트 근거).

### 13.5 P4 상태 보드 (`dashboard/#/status`)

```
dashboard/
├── tools/export_status_data.py      logs/fleet + config → public/data/fleet/index.json, <id>_<mode>.json (판정 포함, 장면 변수 모터별 덮어쓰기)
├── src/status/data.ts               타입·로더·게이지 구간(모터별 진동 규격·정격 전류)·원인 한 줄
│   ├── Gauge.tsx                    구간 띠 + 마커(상별 3개) + 현재값 등급 + 판정 등급 태그
│   └── TrendChart.tsx               신호별 추세 (임계 띠·장면 띠·커서·클릭 이동)
├── src/pages/StatusBoard.tsx        카드 5 → 상세(사양·게이지 8) | 원인과 조치(머리글·cause_chain·해설 이동) → 재생 바(상태 색 띠)·추세 → 탭 3
├── src/state/playback.ts            useClockPlayback (영상 없는 시계 모드, 같은 Playback 인터페이스)
├── public/content/status/glossary.yaml · run_dashboard_status.bat · tests/test_status_export.py (10)
motor_dt_viz/config/status_demo.yaml 데모 위치 (M1 기계 15 s 안전 · M2 전기 110 s 경고 · M3 기계 27.5 s 경고 · M4 기계 10 s 안전 · M5 전기 60 s 위험)
```

- 정직성: 상단 상시 "대표 사양 기반 시뮬레이션 추정값" + 네 줄(대표 사양(명판 아님) · 외형은 프레임 비례 스케일 · 열회로 계수는 M5 기준 스케일 · ITSC는 해석식 등가 표현), 사양표 탭에도.
- 확인: `dashboard/docs/status_board_check.md`, 스크린샷 `s4_*`. 테스트 대시보드 63 · 엔진 100 통과.

### 13.6 겪은 문제와 해결

- **판정 재실행이 1행 어긋남** — run_fleet 가 풀 정밀도 온도로 판정하고 로그는 소수 1자리였다 → 로그에 적는 반올림 값으로 판정.
- **헤드리스 Edge 를 for 루프로 여러 번 부르면 스크린샷이 안 남음** — 한 명령씩 따로, `--user-data-dir` 분리.
- **`python` 별칭 없음** — Blender 파이썬 + `PYTHONPATH=C:\Temp\pymods` (yaml).
- **게이지가 1080p 에서 잘림** — 탭 19vh, 차트 150 px, 1366 에서는 게이지 3열.

### 13.7 해설 PDF "2.2 kW" 문구 제안 → 2026-10-08 "남은 작업 진행해" 지시로 적용 (PDF 재생성·qa.yaml 2곳)

현재(`animation_guide.md` §Q&A, `content/*/qa.yaml`): "이 프로젝트의 3D 모델·시뮬레이션은 도면(JW-01-HTO-00)의 22 kW 6극 크레인 권상 모터를 기준으로 합니다."
제안: **"이 프로젝트의 3D 모델·애니메이션·해설 대시보드는 모터 라이브러리 M1~M5(1톤 2.2 kW ~ 15~20톤 22 kW) 중 M5(22 kW 6극, 도면 JW-01-HTO-00)를 기준으로
만든 것입니다. 2.2 kW 급은 M1(1톤 호이스트)로 라이브러리에 있고, 상태 보드에서 같은 시나리오·같은 판정 기준으로 볼 수 있습니다. 정격 선전류 43.7 A·상전류 25.2 A 는 M5,
M1 은 5.0 A·2.9 A 입니다."** — 승인하면 세 곳(PDF 원고, 기계·전기 qa.yaml)을 바꾸고 PDF 를 재생성한다.

### 13.8 남은 결정·선택 과제

- M1 결함 배율(온도 위험 미도달) 별도 설정 여부, 사양 의문점 5건(13.1).
- P5(지시 시): 5종 애니메이션 재녹화, 상태 보드 라이브 입력(데이터 소스 추상화), 명판 입력 폼.

### 13.9 P5 선택 과제 중 소프트웨어 항목 (2026-10-08, "진행해")

- **데이터 소스 추상화** `dashboard/src/status/source.ts`: `StatusSource{kind, label, loadIndex, loadSeries, subscribe?}`. `ReplaySource`(엔진 배치 JSON, 기본)와
  `LiveSource`(`#/status?live=<url>` — 같은 JSON 계약 + SSE `<url>/events` 로 샘플 추가, `appendSample`). 보드는 인터페이스만 본다. 판정은 어느 소스든 서버(엔진) 몫.
- **명판값 입력 폼** `dashboard/src/status/nameplate.ts` + `StatusBoard` 의 `NameplateForm`(② 패널 "명판값 입력" 버튼, `?np=1`): 10개 항목 입력 → localStorage 저장 →
  그 모터 출처가 `nameplate`로 바뀌고 상단 정직성 줄·② 머리글·사양표 출처가 "명판값 (입력 YYYY-MM-DD)" 로 바뀐다. 전류 비율 게이지는 명판 정격으로 즉시 재계산,
  판정은 "배치 재실행 전" 표시. YAML 조각 복사 버튼 → `config/motors/<id>.yaml` 반영 후 `run_fleet → export_status_data → build`. 스크린샷 `s5_nameplate_M3_1920.png`.
- **임계값 보정 가능성 메모** `motor_dt_viz/docs/threshold_calibration_note.md`: 샘플(M1 한 용량, 베어링 번호 없음, 단위 미확정)로는 바꾸지 않는 근거와 조건. config 무변경.
- 통합 영상 재녹화 (2026-10-08 09:56, "진행해" 를 시작 신호로): `demo_integrated.py --mode integrated --record --no_timecode`, 172 s, 오프셋 2.004 s, HUD Ph R·S·T 확인(`s5_integrated_rst_110s.png`), `모터결함_애니메이션/3_통합/07_통합_자동재생.mp4` 교체. 이전 판은 `media/integrated_backup_phA/`.
- **5종 애니메이션 재녹화 (2026-10-08 10:12~10:39, "우선 재녹화 진행해")**: `demo_integrated.py --motor <id>` 추가 — 열회로(`thermal_cfg`)·전류(`electrical_cfg`+`motor_spec`)·진동 규격·회전 구동값·HUD 문구를
  라이브러리로 바꾸고, 외형은 **카메라 거리를 1/geometry_scale** 로 늘려 프레임 비례 크기로 보이게 했다 (USD·물리 바디를 스케일하면 관절·입자 경로가 깨지므로 원본 무수정).
  HUD: "2.2 kW 4-pole hoist motor (M1, representative spec, frame x0.56 of M5)", 진동 규격 이름(10816-1 Class I / 20816-3 Group 2), 자막의 규격 이름 치환.
  `tools/record_fleet.ps1` 로 M1~M4 × 기계·전기 8편 녹화(각 172/187 s, 오프셋 2.002~2.009 s, 평균 60 fps 이상) → `dashboard/public/media/fleet/<id>_<mode>.mp4`,
  발행 `모터결함_애니메이션/4_모터별/<id>_<기계|전기>_전체시나리오.mp4`. Isaac 로그 ↔ 엔진 배치 장면 끝 최대 차 0.1~0.2 °C/A (`docs/fleet_recording_summary.json`).
  확인 프레임 `s5_fleet_*.png`. 한계: 시나리오 자막(subtitle_en)의 숫자("88 A (201 %)")는 M5 기준 문장 그대로다 — HUD 전류 패널은 모터별 암페어로 맞다. M5 는 기존 영상 유지.

## 14. AI Hub 「기계시설물 고장 예지 센서」 경량 샘플로 파이프라인 준비 (2026-10-07, S0~S3 완료)

지시서 `TASK_AIHub_샘플`. 전체 데이터(약 500 GB) 도착 전에 샘플(4,674 CSV, 842 MB)로 구조를 확정하고 변환·특징 추출 코드를 검증했다.
`config/thresholds.yaml`·`config/motors/`·대시보드·엔진은 건드리지 않았다 (git diff 로 확인). 설명서 PDF 는 로그인 다운로드라 받지 못했고,
샘플 전수 스캔과 AI Hub 공개 페이지로 대신했다 — 받으면 `data/aihub/docs/` 에 넣고 "설명서에 없음" 항목을 보강한다.

### 14.1 구조 확정 (`docs/aihub_structure.md`)

- 경로 `<signal>/<kW>kW/<모터명>/<라벨>/STFMK|STFCB-<설치일>-<센서ID>_<측정일>_<시각>_004|002.csv`. UTF-8, CRLF, 후행 쉼표, 헤더 9줄 뒤 바로 데이터.
- 진동 **1채널 4 kHz 3 s(12,000)**, 단위 설명서 없음(g 추정). 전류 **3채널(3상) 2 kHz 1 s(2,000)**, A. 두 신호는 다른 날 수집(동시 쌍 0).
- 어노테이션: Date, Filename(.dat), Data Label, Label_No(전류는 `Label No`), Motor Spec(모터명, rpm, kW, 정격 A), Period, Sample Rate, RMS(채널별), Data Length. 베어링 번호·센서 방향·부하 없음.
- 라벨 00 정상 / 01 베어링 / 02 불평형 / 03 축정렬 / 04 벨트. 샘플은 2.2 kW 4대(결함은 모터당 한 종류)·55 kW 2대뿐 — 5.5~22 kW 없음.
- 추가 발견: 55 kW 는 인버터 구동(기본파 49.6~57.5 Hz)이고 전류가 ±82 A 센서 범위에서 포화; 전류 채널 순서가 모터마다 다름(acb 2대); L-EF-04 는 센서ID 에 따라 Motor Spec 이 둘.

### 14.2 코드

- `config/aihub_select.yaml`(선별·motor_map), `aihub_format.yaml`(파서 형식), `aihub_features.yaml`(대역·단위 가정).
- `tools/aihub/convert_parquet.py`: 파일당 1 Parquet(float32·zstd) + `meta.parquet` + `convert_report.json`(검증·품질 목록). 6.9 ms/파일, 크기 ×0.40.
- `tools/aihub/extract_features.py`: 파일·채널당 1행 — rms/peak/crest/kurtosis, `vel_rms_mm_s`(10~1,000 Hz 주파수 영역 적분, g 가정), fr/1×2×3×(+`fr_peak_hz`),
  포락선(500~1,600 Hz, 베어링 번호 없어 배율 NaN), 대역 RMS, 클리핑·DC·NaN, 전류 I₂/I₁ 참고값(최소자승 페이저, 상순 자동). 그림 3장(제목에 "샘플 데이터, 참고용"), `docs/aihub_sample_summary.md`.
- 테스트 10건 (`tests/test_aihub_convert.py` 5, `tests/test_aihub_features.py` 5 — 합성 신호로 적분·고조파·대칭좌표 검증 포함).

### 14.3 겪은 문제와 해결

- `python -I` 는 PYTHONPATH 를 무시 → 스크립트가 `VIGENT_PYMODS` 또는 `C:\Temp\pymods` 를 sys.path 끝에 덧붙인다. Blender 파이썬에 yaml·pyarrow·pandas·scipy·matplotlib 없음 → pymods 에 설치.
- 텍스트 모드로 읽으면 CRLF 가 변환돼 `split("
")` 이 실패 → `splitlines()`.
- 클리핑 비율 정의(|x|≥0.995·max)는 사인파에서 6.4 % 가 자연값 → 의심 기준 10 %.
- I₂/I₁ 이 12~480 으로 나옴 → 채널 순서 역상(acb) + 1 Hz 빈 누설. 피크 보간 + 최소자승 페이저, 큰 성분을 정상분으로.
- 55 kW `fund_hz` 가 60 Hz 가 아니라 테스트 실패 → 인버터 구동 확인, 범위 40~65 Hz 로 두고 2.2 kW 만 60 Hz 를 요구.
- 한글·공백 경로: `pathlib` + `PYTHONIOENCODING=utf-8`. 콘솔의 한글 깨짐은 표시 문제일 뿐 파일은 정상.

### 14.4 전체 데이터 예상·남은 결정

- 233만 파일 × 6.9 ms ≈ 4.5 시간(단일 프로세스), 선별본(1/5) ≈ 0.9 시간; Parquet 전체 ≈ 200 GB, 선별본 ≈ 40 GB. 디스크: 원본 500 GB 는 외장 필요(C: 여유 243 GB), 병합 없이 가상 연결 파일로 읽는 방식 제안.
- 결정 필요: 진동 단위(설명서), 55 kW 인버터 여부·베어링 모델(설명서), 외장 드라이브 경로, 병합 없는 추출 방식 승인.

### 14.5 선별 파이프라인 D0~D3 를 샘플 zip 으로 실행 (`tools/aihub/run_pipeline.py`)

사용자 결정: 전체 500 GB 대신 바탕화면 샘플 zip 을 데이터셋으로 쓴다. 지시서 `TASK_AIHub_데이터선별` 의 흐름을 샘플 zip 에 그대로 적용했다.

- `SplitFile`: `*.zip.part1..N` 을 이어 붙인 것처럼 읽는 가상 파일 → 병합 zip 없이 `zipfile` 로 목록·부분 추출 (테스트: zip 을 3조각으로 쪼개 검증).
- D0 `list`: 목록 4,674 → `data/aihub/filelist.txt`, 선별 패턴 3개(`select_patterns.txt`: vibration/2.2kW/*/{정상,베어링불량,축정렬불량}), 1,127 파일 293 MB (전체의 35 %), `docs/aihub_selection.md` 자동 생성(받은 것·버린 것·이유).
- D1+D2 `extract`: 단위(용량·라벨)별 추출 → Parquet(L2/full) → 무작위 20개 원본 대조 → L1 단위 삭제. 3단위 22 s. manifest 1,127 행 = 목록 예상. L2/full 138 MB (CSV ×0.47).
- D2 `sample`: 모터·라벨 조합당 상한 2,000 → 샘플은 전부 상한 이하라 1,127 그대로 L2/sampled.
- D3 `features`: 1,127 파일 11 s → `data/aihub/L3/features.parquet`, `docs/aihub_feature_summary.md`(용량·라벨별 속도 RMS 평균·중앙값·95 %, 정상의 ISO 위치, 정상 vs 베어링 지표비), `docs/aihub_plots/label_box_vel_bandhi.png`. 포락선 BPFO 배율은 베어링 번호가 없어 NaN — 대신 고주파 대역 RMS·kurtosis 비교.
- 디스크: 작업 전 348 MB(sample) → 후 632 MB (L2/full 142 + sampled 142 + L3 <1, L1 0). 피크 = 가장 큰 단위 L1 177 MB. Parquet 는 <L2>/waveforms/<signal>/ 구조로 바로 써서 extract_features 와 같은 배치(중복 복사 없음).
- 테스트 `tests/test_aihub.py` 4건 (분할 zip, 메타 스키마·샘플 수, 선별 = config·manifest = 목록·샘플링 상한, 특징 범위). 전체 114건 통과.
- 전체 데이터가 오면: `run_pipeline.py list --zip <part1>` → 패턴 확인 → `extract` → `sample` → `features`. 코드 변경 없이 같은 명령.

### 14.6 설명서 2종 반영 (2026-10-08) — "설명서에 없음" 항목 확정

사용자가 가이드라인 v2.4 와 테크니컬 리포트 PDF 를 보내 `data/aihub/docs/` 에 두었다. `docs/aihub_structure.md` §11 에 항목별로 정리.

- 확정: 진동 단위 **g**(검수 기준 0.12 g), **단축 vertical**, 전류 R·S·T 3상, 기본 4 kHz·3 s(헤더가 정본), 37/55 kW **VVVF 인버터**(샘플 기본파 49.6~57.5 Hz 와 일치),
  계획 운전(1시간 10분), 라벨은 **인위 고장 모의 장비 + 모터별 RMS 임계**로 부여, 정상 검수 기준 진동 RMS ≤ 0.12 g·전류 정격 ±2 %, 전체 용량 **약 50 GB**(사용자 추정 500 GB 와 10배 차이 — 페이지 재확인 필요).
- **베어링 호칭이 가이드라인 "고장모의 현황" 표에 모터별로 있다** → `config/aihub_bearings.yaml`(호칭 = 가이드라인, 기하 = 카탈로그 추정, 24개 모터). `extract_features.py` 가
  포락선 BPFO/BPFI 피크 ÷ 주변 바닥 비를 계산하고 `bearing_known=True`, `bearing_source` 를 남긴다 (DE·NDE 둘 다). 우리 M1~M5 값은 쓰지 않는다.
- 결과(샘플): L-SF-04 정상 BPFO 배율 2.85 → 베어링불량 4.68 (×1.6) 로 속도 RMS(×1.07)보다 훨씬 잘 갈린다. 단 R-EF-05 정상이 5.05 로 높아(BPFO ≈ 3.57 fr 이 3×·4× 고조파 사이)
  경계(2/5배)를 이 표본으로 옮기지는 않는다 — `docs/threshold_calibration_note.md` §2b.
- L-EF-04 는 갑천역·대전역에 각각 있는 **동명이기** — Motor Spec 이 둘인 이유. `sensor_id` 로 구분. 일부 모터는 라벨링 기준상 "정상이 고장보다 RMS 가 높다"(라벨이 모터·시기별 경계).
- 테스트 갱신(bearing_known·배율 양수·합성 충격열 검증) — 엔진 스위트 통과. 그림 `01_envelope_normal_vs_bearing.png` 에 BPFO/BPFI 선, `label_box_vel_bpfo.png`.

## 15. 사용자 결정 일괄 적용 (2026-10-08)

사용자 답: A-1~A-5 ① 유지(M5 1170 rpm, η/cosφ 0.90/0.85, 축 높이 비 스케일, 22220 베어링, M4 는 B-1 로 통일), B-1 ②, B-2 ①, B-3 ②, C-1 ②, C-2 ①, D-1 ②, D-2 대표 사양 유지.
"B-1·D-1 둘 다 반영한 뒤 M1~M4 재녹화는 한 번만", "가이드라인이 유연 지지 4.5 를 썼다는 것은 docs 에 기록".

### 15.1 B-1 ② 진동 규격 5종 통일
- `config/motors/M1~M3.yaml` vibration → ISO 20816-3 Group 2 강성 지지 1.4/2.8/4.5 (M4·M5 와 동일). `motor_library` 규칙 4 를 `VIB_STANDARD_REQUIRED="ISO 20816-3"`, `VIB_STANDARD_SPLIT_KW=0` 으로.
- `config/thresholds.yaml` 주석에 결정 근거와 **AI Hub 가이드라인의 유연 지지 B/C 4.5 mm/s(강성 2.8) 기준** 기록. 용어 풀이·AI Hub 요약 문구·테스트(엔진 3건, 대시보드 1건) 갱신.
- 영향: 배치 재실행(M1~M3 진동 경고 1.4 부터), 상태 보드 게이지, 영상 HUD 규격 이름.

### 15.2 B-3 ② 베어링 지표 정의 확정 (수치 유지)
- `thresholds.yaml bearing_index` 주석에 실측 정의: 대역통과(500~1,600 Hz @4 kHz) → Hilbert 포락선 → BPFO ±3 % 피크 ÷ 주변 ±25 Hz 중앙값. 경고 2 / 위험 5배. 시뮬레이션은 손실 배율 대체.

### 15.3 D-1 ② 자막 변수화
- `scenario_electrical.yaml` 의 "43.7 A", "88 A (201 %)" → `{rated_line_A}`, `{a_rms_end}`, `{a_pct_end}`. `engine.scenario_player.fill_vars` 로 채운다:
  데모 HUD(모터별 전류 모델 값), `export_dashboard_data`(M5 해설 변수), 상태 보드(원문 export → 보드가 모터별 `scene_values` 로 채움).
- M1~M4 재녹화 1회 (B-1 과 함께): `tools/record_fleet.ps1`, 12:00 경 시작.

### 15.4 C-1 ② 전체 데이터 다운로드
- `tools/aihub/aihubshell`(AI Hub 공개 CLI v0.6) + `download_full.sh`. 파일 트리(키 없이 조회): Training vibration 78 GB · current 21 GB, Validation vibration 10 GB · current 3 GB.
  가이드라인의 "약 50 GB" 와 사용자 추정 500 GB 사이의 실제 값은 **112 GB(진동만 88 GB)**. C: 여유 241 GB 로 진동만이면 충분.
- **다운로드는 사용자의 AI Hub API 키가 있어야 시작된다** (`AIHUB_API_KEY=<키> bash tools/aihub/download_full.sh`). 키는 저장소에 두지 않는다. 받은 뒤 `run_pipeline.py list/extract/sample/features` 를 zip 두 개(Training·Validation)에 차례로 돌린다.

### 15.5 M1~M4 재녹화 (B-1·D-1 반영, 2026-10-08 13:38~14:20)

- 1차(11:59~12:10, M1 기계·전기, M2 기계)와 M3 기계(13:43)는 녹화 중 다른 창(VS Code·유튜브·카카오톡 로그인)이 앞에 떠서 폐기. 사용자 "녹화중지하고 대기해" → "시작해" 신호 뒤 4편 재녹화(14:07~14:20) 로 8편 완성.
- 8편 모두 프레임 확인: HUD 규격 "ISO 20816-3 Group 2", 자막 변수(M1 전기 12턴 "10.1 A (201 %)", M2 24.2 A) 채워짐, 다른 창 없음. Isaac 로그 ↔ 엔진 배치 장면 끝 최대 차 0.0~0.2, 평균 62~72 fps.
  `docs/fleet_recording_summary.json`, 확인 프레임 `s6_fleet_*.png`. 산출물 `모터결함_애니메이션/4_모터별/` 8편 교체.
- 교훈: `record_fleet.ps1` 을 `powershell -File` 로 부를 때 `-Motors M3,M4` 는 문자열 하나로 들어온다 → 스크립트에서 쉼표 분할. 녹화 전 알림 앱(카카오톡) 종료 필요.

## 16. AI Hub 전체 진동 데이터 — 다운로드·선별·변환·특징 (2026-10-08 저녁, 완료)

- 사용자가 API 키로 `download_full.sh` 실행(14:45~18:20, 평균 4.2 MB/s). aihubshell 이 tar 를 풀어 `1.Training/vibration.zip`, `2._Validation/vibration.zip` 두 파일로 남김.
- **Training zip 이 잘렸다**: 66.8 GiB(목록 78 GB), 끝 1 MB 에 중앙 디렉터리 없음 → `zipfile` 은 "not a zip". 로컬 헤더를 순차 스캔하니(83 s) data descriptor 없이 크기가 다 있어
  **875,070개 항목이 완전**하고 마지막 완전 항목이 `55kW/L-PAHU-03S/정상/…154843` — 알파벳 순서 끝인 **7.5 kW 폴더 전체와 55 kW 뒷부분이 누락**. `run_pipeline.py` 에 `ScanZip`(순차 스캔 색인, `<zip>.scanindex.json` 캐시, 완전 항목만)을 넣어 `open_zip` 이 자동 전환.
  로컬 헤더 이름은 **cp949**(utf-8 플래그 없음, 중앙 디렉터리는 utf-8) → 디코딩 분기. 선별 327,543 파일(85 GB CSV, 37 %).
- Validation zip 은 온전(126,712개): 선별 49,778 파일 12.9 GB → 13단위 추출·변환·검증(20/20) 완료, L2/full 6.1 GB(×0.47). 7.5 kW(M3) 실측은 이 분만 있다.
- **OneDrive 함정**: 저장소가 바탕 화면(OneDrive) 아래라 5만 파일을 쓰는 동안 OneDrive 가 동기화(2.3 GB 메모리) → 파일당 38 ms(샘플 때 7 ms). 산출물·zip 을 `C:igent_data\{aihub,aihub_full}` 로 옮기고
  `run_pipeline.py`/`tests/test_aihub.py` 가 `VIGENT_AIHUB_DATA`(기본 `C:\vigent_data\aihub`) 를 우선 보게 했다. 경로 문자열에 `\v`·`\a` 이스케이프가 들어가 한 번 실패 → chr(92) 로 재작성.
- L1 단위 폴더가 모터명 대신 라벨명으로 생기던 경로 버그 수정(`parts[-3]/<file>`).
- ScanZip 의 `open()` 이 이름을 선형 탐색해 파일당 130 ms → 사전 색인 + 파일 핸들 재사용으로 0.8 ms. Training 추출 20:38~22:44 (10단위, 각 20/20 검증, L1 단위 삭제):
  327,543 파일 83 GB CSV → Parquet, **L2/full 합계 377,321 파일 46.3 GB**(file_id 중복 0). 모터별: M1 정상 129,311·베어링 21,558·축정렬 18,583 / M2 57,599·19,750·18,001 /
  M3 4,398·2,401·2,001(Validation 만) / M4 35,771·21,601(축정렬 없음) / M5 32,791·축정렬 13,556(베어링 없음).
- `features --workers 4`(ProcessPoolExecutor, 샘플 검증 4.8 ms/파일) 추가. 22:45 `sample`(조합당 2,000 → 26,000 파일) → `features` 377,321 파일 1,169 s(**3.1 ms/파일**) → `L3/features.parquet`,
  `docs/aihub_feature_summary.md`(모터·라벨별 속도 RMS·포락선 배율·kurtosis), `docs/aihub_plots/label_box_vel_bpfo.png`, `docs/threshold_calibration_note.md` 전체 데이터판.
- **전체 데이터가 말하는 것**: 정상 속도 RMS 중앙값 M1 0.16 / M2 0.09 / M3 0.19 / M4 0.25 / M5 0.29 mm/s(95 % ≤ 0.72) — 경고 1.4 의 7~21 %. 외륜·내륜 소손(M2 L-SF-02, M4 R-CAHU-01S)은
  속도 ×3.9/×24(M4 3.9 mm/s), kurtosis 2.8→94 / 3.1→103, 포락선 BPFO ×15 / BPFI ×4.4 로 또렷. 그리스 제거(M1 L-SF-04, M3 L-PAC-01)는 모든 지표에서 거의 안 보임(×1.04~1.5).
  포락선 BPFO 배율은 정상에서도 M4 7, M5 15~37 (기하 추정 BPFO 가 고조파와 겹침) → 임계값으로 부적합, kurtosis 가 깨끗. 축정렬은 속도 RMS 로 안 갈림(2× 성분으로). M3 L-SF-01 정상 63개는 정지 상태(진동 running 판정 필요).
- 결정 B-3 ② 대로 config 무변경. 제안(§4): 진동 1.4/2.8/4.5 유지, 베어링 지표 정의를 kurtosis 또는 고조파 보정 포락선으로.
- 테스트: `test_aihub.py` 가 외부 DATA(두 zip 합산 선별 수 = manifest = meta 377,321)로 통과, 엔진 115·대시보드 63.
- 디스크: C:\vigent_data — zip 82 GB + L2/full 46.3 GB + sampled 3.2 GB + L3 0.3 GB. L1 은 비어 있다.

### 16.1 베어링 지표 후보 비교 (사용자 결정 1번 자료, 23:27)

`tools/aihub/bearing_metric_compare.py` → `docs/aihub_bearing_metric_comparison.md`, `docs/aihub_plots/bearing_metric_compare.png`. 같은 모터의 정상 vs 베어링불량 4대, 모터·라벨당 ≤2,000개(15,647 파일).
소손 2대는 현재 포락선 배율(AUC 1.00/0.90)·kurtosis(1.00/1.00) 모두 잡지만 현재 배율은 M4 정상 100 %가 경고·87 %가 위험으로 오탐. 그리스 제거 2대는 어느 지표로도 안 갈림.
고조파 보정 포락선(k·fr ±2 % 제외)은 오탐을 못 줄이고 M4 에서 BPFO≈3×fr 겹침으로 무너짐(AUC 0.19). 내륜 소손은 BPFI 배율이 맞음(1.00). 고주파 대역 RMS 가 M3 그리스 제거에도 반응(1.00, ×1.7). 결정 대기.


## 17. 베어링 지표 교체 — kurtosis + 고주파 대역 RMS 배율 (2026-10-08 밤 ~ 10-09 새벽, 완료)

사용자 결정(16.1 비교표를 보고): 주 지표 kurtosis(경고 3.5 / 위험 4.0, 모터 공통), 보조 고주파 대역 RMS 정상 대비 배율(경고 1.5 / 위험 2.5, 기준선은 모터별 config),
종합은 둘 중 나쁜 쪽. 포락선 BPFO·BPFI 는 판정 제외(베어링 번호 아는 모터에서 "결함 부위 추정" 표시만), 고조파 보정 포락선 폐기. 2번(Training 재다운로드)·3번(전류 2차)은 계속 보류.

- **실측 근거 재계산** (`C:\vigent_data\aihub\L3\features.parquet`, 동일 모터 정상 중앙값 기준선): 소손 2대 kurtosis 94·103(5 % 55·73)·고주파 ×12.7·×18.0(5 % ×9.9·×16.3) → 새 규칙으로 위험 100 %.
  그리스 제거 2대 kurtosis 2.7~2.9 유지, 고주파 ×0.95(M1, 안 보임)·×1.70(M3, 경고 100 %). 정상 오탐: M1 29 %(경고 18 + 위험 11, kurtosis 95 % 4.8·대별 고주파 편차), M3 13 %, M2 4 %, M4 1 %, M5 1 %.
  축정렬불량은 M2 만 kurtosis 3.7·고주파 ×2.2. 용량대 정상 고주파 기준선(대별 중앙값의 중앙값, g): M1 0.0027 / M2 0.0012 / M3 0.0027 / M4 0.0050 / M5 0.0108.
- **config**: `thresholds.yaml bearing{kurtosis, hf_ratio, combine: worst, envelope_hint, envelope_hint_min_ratio 2.0}` + persistence 두 지표(`bearing_index` 삭제).
  `thermal.yaml bearing_normal{3.0, 1.0}` + 결함별 `bearing_type/bearing_kurtosis/bearing_hf_ratio`: DE 베어링 결함 = 소손형 50 / 9.0(실측 5 % 분위 중 작은 값 내림), NDE 베어링 결함 = 윤활 부족형 3.0 / 1.7(그리스 제거 실측),
  축정렬불량 3.7 / 2.2(M2 실측), 팬·브레이크·과부하 = 정상값. 매핑 근거는 주석과 `docs/bearing_metric_definition.md` §3. `motors/M1~M5.yaml bearing_hf_baseline{rms_g, band_hz, source: aihub_normal_median, note}`.
- **엔진**: `thresholds.py` KINDS → `bearing_kurtosis`·`bearing_hf_ratio`, `bearing_level()`(종합), `Judge.bearing_site_hint()`(외륜 쪽/내륜 쪽/-, 판정 아님); `motor_library.py` 기준선 검증(`_hf_baseline`).
  `run_fleet.py bearing_signals()`(옛 `bearing_index` 손실 배율 대체값 폐기), status CSV 열 `bearing_kurtosis, bearing_hf_ratio, bearing`. 새 `tools/fleet_compare.py`(전후 비교표).
- **상태 보드**: export `SIGNALS` 두 지표 + `bearing_combined`, `levels.bearing`, `bearing_site_hint: null`(시뮬레이션), index `thresholds.bearing`, 모터 `bearing_hf_baseline`.
  게이지 9개(베어링 kurtosis 카드 제목에 종합 등급, 고주파 배율 카드에 기준선·출처), 추세 차트 두 지표, 기준표 2행, 용어 풀이 3항(kurtosis·고주파 배율·종합 등급). `source.ts LiveSample` 두 지표 + 선택 `bearing_site_hint`.
- **실측 파이프라인**: `extract_features.py` 에 `hf_ratio`(band_hi ÷ 용량대 모터 config 기준선)·`hf_baseline_g`·`bearing_site_hint` 열, 포락선 열은 추정 표시용으로 유지. 샘플 L3 재추출(4,674 파일), 전체 L3 재추출(백그라운드).
- **전후 비교** (`docs/bearing_metric_change_comparison.md`, `logs/fleet_before` ↔ `logs/fleet`): 종합 상태 변경 **0 행**. 기계 모드 베어링 결함 장면의 원인 신호만 vibration 4.8(M1·M2)·DE 베어링 온도(M3~M5) → `bearing_kurtosis 50`(초과 비율 12.5 가 가장 큼)로 바뀜(모터당 128 행). 축정렬불량 장면은 전후 모두 경고(원인 vibration 3.6). 전기 모드 변화 없음.
- **영상**: HUD·자막에 베어링 지표 이름이 없어 재녹화 없음. **테스트**: 엔진 117(베어링 경계·종합·부위 추정·등가값 테스트 추가, fleet 테스트는 원인 신호 변경 반영), 대시보드 63, AI Hub 특징 6.
- 문서: `docs/bearing_metric_definition.md`(정의·실측 근거·등가값·기준선), `threshold_calibration_note.md`·`aihub_bearing_metric_comparison.md` 후속 메모, README 상태 보드 절.
- 남은 판단(사용자): M1·M3 정상 오탐(kurtosis 경계 3.5/4.0 이 공조기 충격성 정상 파일에 걸림)은 현장 정상 운전 실측 후 경계 조정 여부. 기준선은 용량대 대표값이라 현장값으로 교체 필요.

### 17.1 마무리·다음 작업 (2026-10-09 00:40, 커밋 48dc65a)

- 사용자 결정: 베어링 kurtosis 경계 3.5/4.0 **유지**. 근거(오탐 수치, 벨트 구동 공조기의 충격성, 권상 모터 베이스라인 실측 T1 후 조정, 3초 지속 조건으로 단발 충격은 경고 안 뜸)는 `docs/bearing_metric_definition.md` §2.1.
- 전체 데이터 L3 재추출 완료(377,321 파일, `hf_ratio`·`hf_baseline_g`·`bearing_site_hint` 열) → 같은 문서 §6, `docs/aihub_feature_summary.md` 갱신.
- **다음**: `TASK_실시간_디지털트윈_대시보드.md` **R0** 시작 — 지시서 파일이 디스크에 없어 사용자가 본문/위치를 줘야 한다. 확정 조건: 10장(마이그레이션) 제외,
  데스크탑 Isaac Sim + 맥북(같은 Wi-Fi) 대시보드, WebSocket·대시보드 서버 0.0.0.0 바인드, 윈도우 방화벽 인바운드 규칙 절차 README, 데스크탑 IP 를 HUD 에 표시,
  렌더 프리셋 3070 Ti 8 GB 기준 1280×720 RTX Real-Time. 추정 약 4 h (맥북 실접속 확인은 사용자).
- 보류 유지: 2번(Training zip 재다운로드, filekey 44890), 3번(전류 2차). `logs/fleet_before`(비교용 변경 전 로그)는 저장소 밖 로컬에만 있다.

## 18. Isaac Sim 실시간 연동 디지털 트윈 대시보드 — R0 현황 파악 (2026-10-09 낮, 완료)

지시서 `TASK: Isaac Sim 실시간 연동 디지털 트윈 대시보드`(라이브 모드, L1 스트림 + L2 제어). 사용자 조건: 10장 제외, 이 데스크탑(3070 Ti 8 GB) Isaac Sim + 맥북(같은 Wi-Fi) 대시보드,
0.0.0.0 바인드, 방화벽 인바운드 절차 README, 데스크탑 IP HUD 표시, 프리셋 1280×720 RTX Real-Time. 보고서 `motor_dt_viz/docs/live_r0_report.md`.

- 데이터 소스 추상화: 상태 보드는 `StatusSource`(Replay/Live 자리) 있음, 기계·전기 화면은 영상 currentTime 단일 시간 소스 + 완성 시계열 모델이라 **없음** → R2 에서 `DataSource` 일반화(성장 버퍼 + 벽시계 재생기) 범위 정리.
- 데모 루프: state 가 한 dict 로 안 모임(로깅 블록에서만 합침) → R1 에서 `state_dict` 로 통일. 결함·부하·배속·모드·리셋·재생은 `DemoState` 로 런타임 변경 가능, **모터 전환은 재시작 필요**(기동 시 tm/cm/카메라/HUD 고정). 판정 엔진은 루프에 아직 없음(HUD 는 stage 색) → R1 에서 Judge 추가.
- Isaac 파이썬(3.10.15)에 websockets 12.0·aiohttp·psutil 내장. `omni.kit.async_engine` 없음 → threading + asyncio.
- 프로토타입(`tools/r0_proto/`, 기존 demo 를 runpy 로 감싸 서버 스레드만 추가): FPS 기준 86.5 → 서버 83.6(−3.4 %), `--low` 1280×720 + 서버 90.3. 10 Hz 수신 9.82 Hz, 지연 중앙 0.8 ms, VRAM 3.07/2.92 GB, Isaac 워킹셋 5.1 GB. 완료 기준(10 % 이내) 통과.
- 삽질: cmd 인자로 한글 경로를 넘기면 깨짐 → ASCII 경로 JSON 으로 인자 전달; MSYS 가 `/FI` 를 경로로 바꿔 tasklist 필터 실패 → PowerShell Get-Process 로 RAM 측정.
- state 스키마 초안(CSV 컬럼 이름 유지 + `status` = Verdict + fleet levels + bearing 종합, `narration_key`, `host.ip`), 명령 허용 목록 초안(`select_motor` 는 거부+재시작 안내). 네트워크: 데스크탑 유선 172.30.1.37, 포트 8765/4173.

## 19. 라이브 모드 R1 — Isaac 쪽 LiveBridge + Judge 한 곳 판정 (2026-10-09 오후, 완료)

사용자 추가 3건: ① Judge 를 루프에 넣고 HUD 색도 Judge 등급(열 모델 4단계는 세부 라벨), M5 로그 회귀 ② select_motor 는 재시작 필요 ack(전환은 R3) ③ 실제 state 로 FPS·지연 재측정. 보고서 `motor_dt_viz/docs/live_r1_report.md`.

- `config/live.yaml`(0.0.0.0:8765, 10 Hz, heartbeat 1 Hz, 허용 명령·범위·별칭), `app/live_bridge.py`(스레드 asyncio+websockets, 최신 1건 publish, 명령 검증→큐→ack 방송, perf 스레드, lan_ip), `demo_integrated.py --live`(없으면 기존 동일): Judge 루프 투입(fleet 과 같은 신호), state_dict(키=CSV 컬럼)·CSV 끝 4열 판정, apply_command, play_scenario 장면 점프, narration reveal 평가. `viz/hud.py` 행 색 = Judge, STATUS·LIVE 행. `bearing_signals` 는 `engine/fault_injector.py` 로.
- 회귀(`tools/compare_demo_logs.py`, 9-22 로그 ↔ --live 180/195 s): 장면 끝 온도 차 ≤0.1 °C, 전류 0.000 A → 통과. 격자 최대 차이는 장면 전환 순간뿐.
- 성능(실제 state 3.0 KB): 처음 −8.5 %(77.7/81.6) → 판정 10 Hz 제한은 효과 없음(82.0) → **HUD style 객체 매 프레임 생성이 원인**, 바뀔 때만 주게 하니 89.1(기준 89.2). 수신 10.07 Hz, 지연 중앙 1.0 ms(최대 3.2), VRAM 3.4 GB, Isaac RAM 5.6 GB. 판정 주기는 송신의 2배(20 Hz) — 같은 10 Hz 면 9.2 Hz 로 빠짐.
- README "라이브 모드" 절(실행·확인·맥북 접속·방화벽 인바운드 절차), `tools/firewall_rules.ps1`(8765·4173, 개인·도메인 프로필). 테스트 `tests/test_live_bridge.py` 4개(엔진 121·대시보드 63 통과).
- 삽질: websockets 17 클라이언트에서 `time.sleep` 으로 기다리면 송신이 flush 안 됨 → 테스트는 `asyncio.sleep`; 130 s 짧은 실행을 전체 시나리오 기준표와 비교하면 뒤 장면이 '행 없음'으로 실패 — 회귀 문서는 180 s 실행 것.
- 다음 R2: 대시보드 `LiveSource`(WebSocket 수신→성장 버퍼), 녹화/LIVE 토글, 3 s 폴백, 실시간 추세, serve.cjs 주소 표시. 맥북 실접속 확인은 사용자(방화벽 스크립트 관리자 실행 후).

## 20. 라이브 모드 R2 — 대시보드 LiveSource·녹화/LIVE 토글·폴백·실시간 추세 (2026-10-09 오후, 완료)

사용자: 맥북에서 `http://172.30.1.37:4173` 열림 확인(네트워크 OK) → R2 진행. 보고서 `motor_dt_viz/docs/live_r2_report.md`, 스크린샷 `docs/live_r2/`.

- 공통: `src/live/feed.ts`(WebSocket, 하트비트 3 s 감시, 재접속 2 s, send→ack), `session.ts`(`useLiveSession`: 토글·주소 localStorage·`?live=ws://`, 수신 버퍼 300 s, active/fallback), `LiveToggle.tsx`(스위치·뱃지·노란 띠), `livedata.ts`(버퍼→MotorSeries/MechData/ElecData, 관찰된 장면 전환·등급 변화 사건, `useLivePlayback`), `LiveVideoPanel.tsx`(영상 자리 안내), `public/content/live.yaml`.
- 화면: 세 페이지가 `live.active` 면 라이브 데이터·라이브 재생기, 아니면 기존 그대로(훅은 항상 둘 다 호출). 차트 x축 `min: sc.t_min ?? 0` 로 흐르는 창. 상태 보드는 스트림 모터 자동 선택·`● LIVE`·나머지 카드 흐림, M 키 무시. 해설 단계는 state.narration_key.reveal, 사건 자막은 status 등급 변화. 끊김 띠는 HUD 패널 안에 넣어 grid 행이 밀리지 않게.
- `dashboard/serve.cjs` 0.0.0.0 명시 + LAN 주소 출력. `status/source.ts pickSource` 는 http(s) 만 옛 LiveSource. 데모 state 에 `loss_W` 추가(원인 패널 손실열). `tools/cdp_shot.mjs`(헤드리스 Edge+CDP 실시간 스크린샷).
- 확인: 녹화 모드 3화면 회귀 동일, 라이브 3화면(사용자가 띄워 둔 Isaac `--live` M5 수동 구간에 접속: LIVE·M5 뱃지, 게이지·차트·페이저 갱신, FPS 79·VRAM 3.2 GB 표시), 폴백(닫힌 포트: 띠+"끊김 → 녹화"+녹화 데이터 정상). 테스트 대시보드 63·엔진 121.
- 삽질: `?live=ws://` 가 옛 HTTP LiveSource 에 걸려 index.json fetch 실패 → 스킴으로 분기. 띠를 grid 자식으로 두니 카드 행이 밀림 → HUD 안으로. 라이브 모터 자동 선택이 재생기를 pause 시킴 → 선택 효과에서 라이브 모터 제외. 사용자가 켜 둔 kit.exe(13:54, --live)가 8765 를 점유 → 내 검증 실행은 포트 충돌(그 인스턴스를 그대로 검증에 사용). cp949 콘솔에 em dash 출력 불가 → ASCII 메시지.
- 남은 것: R3 제어 패널(결함 토글·슬라이더·리셋·시나리오, ack 확정·거부 토스트)과 데모 시나리오 녹화, R4 프리셋·장애 표·체크리스트. 영상 자리 옵션 2·3 은 R5.

## 21. 라이브 모드 R3 — 양방향 제어 패널 · 모터 전환 자동 재시작 (2026-10-09 오후, 녹화 제외 완료)

사용자: 맥북 라이브(연결·결함 토글·종료 폴백) 확인 → R3. 모터 전환은 자동 재시작(select_motor → Isaac 재기동, 대시보드 "모터 전환 중 (약 N초)" 띠 후 재접속), 재시작 시간 실측 보고, 녹화 전 화면 비우기 안내. 보고서 `motor_dt_viz/docs/live_r3_report.md`.

- Isaac: `live.yaml select_motor {runtime: restart, restart_eta_s 60, restart_timeout_s 120}`, `server.bind_retry_s 90`; 브리지 `hello`(허용 명령·모터 목록, 접속 직후)·select_motor 검증·포트 재바인딩 재시도; 데모 `select_motor` → ack{restart} → HUD RESTARTING → 루프 종료 → 브리지 정지 → `restart_args()` 로 kit.exe 재기동(stdout → `logs/live_restart_<id>.log`). 첫 시도는 DETACHED 자식의 `sys.stderr=None` 으로 SimulationApp 이 죽음 → 로그 파일 핸들로 해결.
- 대시보드: `ControlPanel.tsx` 서랍(K·`&ctl=1`): 결함 토글(모드별), 부하/배속/슬로모션 슬라이더, 모드, 시나리오 재생·장면·정지, 리셋, 모터 M1~M5; 상태는 state 로 확정, 거부는 토스트. `session.restarting` + 띠 "모터 전환 중 (M1, 약 60초) · 경과 n초", 옛 인스턴스(hello 없음) 안내.
- 실측(3070 Ti, 통합 모드): M5→M1 133 s(사용자 Isaac 인스턴스 동시 실행, FPS 50), M1→M3 46.5 s, 자동 구동 M5→M1 47.2 s. 끊김은 ack 뒤 0.3 s. 단독 실행 45~60 s, Isaac 두 개면 2 분+ → 발표 때 하나만.
- 자동 구동 `tools/live_demo_drive.py --fast`: 5단계 모두 ack ok — 베어링 결함 8 s 뒤 DANGER(bearing_kurtosis 50, DE 121 °C), ITSC 4턴 R상 57.8 A·I₂/I₁ 0.104, 리셋 SAFE, M1 전환 47 s, M1 같은 결함 71.6 °C(M5 121 °C) — "작은 모터는 늦게 뜨거워진다" 확인.
- 대본 `docs/live_demo_script.md`, 녹화 `tools/record_live_demo.ps1`(Isaac 왼쪽·Edge 오른쪽, 데스크톱 캡처 1920 폭). **녹화는 화면을 비운 뒤** 사용자 신호로 진행(미완).
- 테스트: 브리지 6(hello·select_motor·restart_args 추가), 대시보드 63, 엔진 전체 통과. 커밋 후 R4(프리셋·장애 표·체크리스트).
- (16:07) **데모 녹화 완료** `모터결함_애니메이션/10_라이브_양방향_데모_1920x1080.mp4`(207 s, 10.3 MB): 5단계 모두 담김, M1 전환 23 s. 시도 4회 — too many clients(max_clients 8→32), VS Code 배경, Isaac 창 제목 탐색 실패(프로세스 핸들로) 뒤 성공. 확인 프레임 docs/live_r3/demo_frame_*.png. 녹화 스크립트는 창 전체 최소화·복원까지 자동.

## 22. 라이브 모드 R4 — 핫 모터 스위치·데모 프리셋·장애 테스트·체크리스트 (2026-10-09 오후, Wi-Fi 테스트만 남음)

사용자 추가: ① 전환 공백을 설명 시간으로 + 전환 시간 단축 ② 체크리스트에 백업 영상 경로·실패 시 전환 절차 ③ 맥북 Wi-Fi 끄기는 사용자. 보고서 `motor_dt_viz/docs/live_r4_report.md`.

- **핫 스위치**(`demo_integrated.py hot_switch_motor`, `live.yaml select_motor.switch_mode: hot` 기본): 프로세스 안에서 열회로·전류 모델·결함 주입기·판정·정격·물리 상수·카메라 거리·HUD 만 재생성 — USD·Isaac 재로드 없음. 실측 switch 5~14 ms, ack→새 모터 첫 state 0.11 s, 소켓 유지. 재시작 방식은 `switch_mode: restart` 로 남김.
- 띠: ack 의 hot/from/switch_ms + 직전 state 요약을 받아 최소 `switch_banner_min_s`(10 s) 동안 "왜 바뀌는지"(hot/restart 문구) + "무엇을 비교할지"(모터 사양·출력비·직전 상태) 두 줄 — 템플릿 `dashboard/public/content/live.yaml switch_*`. 스크린샷 `docs/live_r4/switch_banner_status.png`.
- 프리셋 `config/render_demo.yaml` `--preset demo`(1280×720, RTX Real-Time, 서브스텝 2, 입자 12, 뷰포트 1개) + 기동 `[perf] start` 로그(`perf_start.json`: fps 48~58 @8 s 워밍업, VRAM 3.3 GB, RAM 4.9 GB) + FPS<30 경고.
- 장애 테스트 `tools/live_fault_tests.py`(`docs/live_r4/fault_tests.json`): 범위 밖·목록 밖 거부, 동시 명령 마지막 승(1.2), 핫 스위치 0.11 s, 강제 종료 close 감지 1.7 s. 새로고침은 localStorage 로 즉시 재접속(R2). 삽질: kill 대상 명령줄 패턴 불일치 + state 가 계속 와서 무한 대기 → `--kill-match`·60 s 상한.
- 체크리스트 `docs/live_demo_checklist.md`(전날·시작 순서·**라이브 실패 시 15 초 전환 절차와 백업 영상 경로**·데모 중·끝나고), README 핫 스위치·`--preset demo`.
- (17:00) 맥북 Wi-Fi 끄기 테스트(사용자): 끊김→녹화 **3 s**, 복귀 **8 s**(Wi-Fi 재연결 포함), 끊긴 동안 게이지는 녹화 데이터로 움직임, 띠 "라이브 연결 끊김 — 녹화 재생 중", 특이사항 없음 → 장애 표 6종 전부 통과. **R0~R4 MVP 완료.** 테스트 Isaac 인스턴스 종료.
- (17:15) 사용자 요청으로 Isaac Sim 기계 모드 라이브(`--mode mechanical --live --motor M5 --preset demo`, 로그 `logs/live_mech/`)를 띄우고 데스크탑 브라우저에 `#/status?live=ws://127.0.0.1:8765&ctl=1` 을 열어 둠. 대시보드 서버는 4173 에서 계속 실행 중. 저장 시점: R0~R4 MVP 완료, 커밋 b50a3a5 까지 푸시됨.

## 23. AI Hub 사양·전류 구조 확인 (2026-10-14, 확인만 — config/engine/dashboard 무변경)

지시: 정상 데이터가 있는 2.2 kW 8대의 모터 사양·전류 구조·I₂/I₁ 참고 분포를 확인만 하고 `docs/aihub_spec_check.md` 로 보고. `python -I` 읽기 전용.

- 사양: 어노테이션은 CSV 헤더뿐(JSON 없음) — 모터명·rpm·kW·A 만. 극수·전압·결선·제조사·효율·역률·마운트 = **없음**(헤더·설명서 모두). 베어링은 설명서 p.27 표(이미지)의 고장 모의 5대만(6206/6205·6206). 센서: 가속도 단축, 모터 외부 부착, 3상 전류센서(인버터 연결). 4 kHz·3 s / 전류 2 kHz·1 s.
- 4.7 A vs 8.6 A: (1760 rpm, 4.7 A) 6대 / (1730 rpm, 8.6 A) 시청역 2대 → 기종 차이로 읽히나 근거 키 없음. **전류 파일 헤더는 같은 모터에 다른 값**(L-EF-04 8.2 A, R-EF-05 14 A) → 헤더 사양값 신뢰도 낮음. L-EF-04 는 갑천·대전 동명이기.
- 전류: 샘플에만(2.2 kW 4대 정상 906파일 + 55 kW 2대), 전체 전류 zip 미다운로드. **3상**(R·S·T), 전압 채널 없음, 2 kHz·1 s, 단위 A, 기동 구간은 L-DSF-01 일부 파일만.
- I₂/I₁ 정상 분포(≤500/모터): L-EF-04 0.028(95 % 0.039, 경고 이상 31 %), R-EF-05 0.026(23 %), L-SF-04 0.088(100 %, S상 10 % 큼), L-DSF-01 0.08(95 % 0.59 — 채널 탈락 파일 섞임), 55 kW 0.034/0.005. 상 불평형 경고(0.05) 이상: L-EF-04·R-EF-05 0~1.5 %, L-SF-04 88 %, L-DSF-01 100 %.
- 결론: 3상이라 계산 가능하나 샘플 4대 한정·모터별 편차 커서 "모터별 정상 중앙값 대비"로만 참고 가능, 공통 경계 0.03 은 이 데이터로 정당화되지 않음. M1 이 지시서대로 3.5 kW 면 전체 zip 의 3.7 kW 급 5대(진동만, 미추출)가 더 가까운 후보.
- `git diff -- motor_dt_viz/config motor_dt_viz/engine dashboard` = 0 줄 확인. 계산 스크립트는 스크래치에만.

## 24. 전기 트랙 마무리 — Maxwell 경로 B LUT 를 디지털트윈에 연동 (2026-10-17, D0~D6 완료 · 정격 전류 결정 대기)

지시(TASK A): 단계 0(M-fix, 권상모터_3D모델링 쪽) 뒤 D0 조사 → D1 LUT 가져오기·로더 → D2 electrical.yaml v2 → D3 신호 생성 교체(legacy 유지) → D4 I₂/I_n·손실 연결 → D5 대시보드 배지 → D6 검증 보고.
승인 범위는 electrical.yaml 구조와 결함 신호 생성 코드만. thresholds.yaml·motors/*.yaml·판정 코드·포트·방화벽은 무변경(V8 git diff 로 확인).

- **D0**: `target_i2i1` 은 `CurrentModel._calibrate_targets` 가 고장상 배율로 역산(고정 파형 아님) → 멈춤 조건 아님. 열 모델에 핫스팟 입력 없음(`extra_loss_W` 만). thresholds i2i1 에 source/status/mode 없음. 계산은 Isaac 안 `demo_integrated` 가 직접.
- **D1**: `tools/electrical/import_lut.py`(sha256·provenance·멱등, `data/electrical/LUT_INDEX.md`), `engine/lut_source.py` LutSource(3축 보간, R_f log, 클램프 플래그, 각도는 최근접), `tests/test_lut_source.py` 6건.
- **D2**: `config/electrical.yaml` v2 — `version 2, method lut, motor M1, rated_current_A 4.73, base_turns_per_phase 192, source{grade,status,fem_verified,lut,lut_sha256}, inherent{0.027, 0°}, transfer_to_other_motors false`, 7 케이스에 `lut:{turns,R_f_ohm}` 추가(legacy 필드 그대로). **rated_current_A 4.73 ≠ M1.yaml 5.0 (+5.7 %)** → 지시대로 보고(파형 크기 5.0 기준, I₂/I_n 분모 4.73 로 두고 진행).
- **D3**: `engine/current_model.py` — `_phasors()` 가 lut 케이스는 I₁ + I₁(r·e^{jθ} + 0.027) 페이저 합성, 나머지·legacy 는 기존 식 그대로(위상 규약 동일). M1 외 모터·sha 불일치·파일 없음은 legacy 로 내려가고 이유 기록. legacy 회귀 0.104/0.269 ±0.1 % 통과(기본·M5·M1 legacy).
- **D4**: `CurrentState.i2_over_in`(lut 일 때만)·`i2_angle_deg`·`source`; state JSON 에 `i2_over_in, electrical_source(+cases 7), p_loop_total_W, i2i1_marks` 덧붙임(schema 1 유지), CSV 끝에 `i2_over_in, electrical_method`. `ThermalModel.step/losses(extra_loss_W)` 훅 → 통합 모드에서 LUT P_loop_total(4턴 158 W, 12턴 977 W)을 권선 노드로. HUD 에 I2/In 줄·근거 줄(영문).
- **D5**: 대시보드 `feed.ts`(선택 키 타입) · `livedata.ts toElecData`(눈금 덮어쓰기·source·i2_over_in 열) · `HUDElec`(근거 배지 "등가회로 LUT · provisional · FEM 미검증") · `I2I1Panel`(I₂/I_n 줄·7 케이스 근거 표) · `content/electrical.ts`(LUT 일 때 ITSC 두 장면 why/see/act 3줄) · elec.css. `npm run build` 통과, dist 갱신. WebSocket 구조 불변.
- **D6**: `tools/electrical/verify_lut_integration.py` → `docs/electrical/lut_integration_report.md` (V1 LUT↔mccm ±1 %, V2 합성↔LUT ±1 %/±1°, V3 고유 비대칭 범위 4턴 0.021~0.075, V4 legacy, V5 부하 50 vs 100 %: I₂/I₁ +47 % vs I₂/I_n 0 %, V6 thresholds 판정표(4턴 SAFE~WARN, 8턴부터 DANGER), V7 라이브 10 s, V8 금지 파일 clean). `docs/judgment_basis.md` 신설(근거·임계값 만남·I₂/I_n 제안·핫스팟 노드 제안). 테스트: 엔진 113, 대시보드 63 통과.
- 삽질: bash heredoc 으로 긴 파이썬 파일 쓰기 실패(따옴표 파싱) → Write 도구; LUT 0 % 행의 1e-10 잔차가 ±1 % 검사에서 +199 % 로 나와 0 처리; 12턴 P_loop_total 977 W 는 지시문의 "≈590 W" 보다 크다(R_f 손실 487 W + 단락 턴 동손 490 W 합 — μ·R1_hot 항 포함).
- 결정 대기: ① rated_current_A 4.73(LUT) vs M1.yaml 5.0 — 어느 쪽을 I₂/I_n 분모·파형 기준으로 쓸지 ② 12턴 손실 977 W 를 권선 노드에 그대로 넣을지(끄기 `loop_loss_to_winding: false`) ③ safe_below 0.03 과 정상 0.027 의 여유 0.003 (제안만).

## 15. M1(현대 HLP-2.2/4) 전체 3D 모델 — 100L 하우징 + 내부 재구성 → Isaac Sim 연결 (P4, 2026-10-21)

지시: Maxwell 저장소(읽기 전용)의 데이터시트·geometry_check 로 M1 내부(고정자·권선·로터)와 100L 하우징을 CadQuery 로 재구성, 검증(체적 ±2 %·치수 ±0.5 mm·분할비·삼각형), USD 조립(variant 3종), M1 전용 장면에서 회전·발광·온도 색을 상태 JSON 값으로만 표시. 승인 범위 `tools/cad/`, `assets/motors/M1/`, `tests/`, M1 장면·경로 매핑 추가. `config/`·`engine/`·판정 코드·22 kW USD 불변, 새 계산 없음.

### D0 환경
- Python 3.12 + CadQuery 2.8.0(기존) + trimesh 5.1.1(설치). Isaac Sim 4.5 headless 로 `omni.kit.asset_converter` OBJ→USD 성공; `omni.kit.converter.cad`(STEP)는 서비스형이라 스크립트 직접 호출 불가 → OBJ 경로 채택.
- 기존 장면: 회전 = `/World/Motor` 아티큘레이션 토크 루프(`demo_integrated.py` 709~715행, rpm = 조인트 속도), 색 = `viz/material_driver.MaterialDriver.update` + `viz/colormap.ThermalColormap`, 상태 JSON 826~845행(`rpm`, `T{9노드}`, `stage`, `i2_over_i1`, `i2_over_in`, `p_loop_total_W`).
- 입력 복사 `assets/motors/M1/inputs/` + `PROVENANCE.md`(sha256). **지시서의 `datasheet_v4.yaml` 은 Maxwell 저장소에 없다** — v4 데이터시트는 xlsx 라 `tools/cad/datasheet_to_yaml.py` 가 키 이름으로 풀어 yaml 을 만든다(165 기호, 숫자 수기 입력 없음). Maxwell 3D 는 RMxprt v2 오버라이드 치수(로터 브리지 0.8, 개구 2.0, 쐐기 1.5, 바 19.8/4.5/2.4, N_c 16)로 만들어졌으므로 `rmxprt_v2m2.json` 을 4번째 입력으로 복사(yaml `maxwell_model` 절) — 체적 동일성 기준.
- 카탈로그 PDF 치수표(KS 형식·플랜지, 100L 행)를 pypdf 로 읽어 yaml 에 그대로 넣음. **AD 328 확인**: 발 장착 표에 328 로 인쇄(90L 263 → 112M 348), 플랜지 표는 175. 그림 B 끝면도에서 AD 는 프레임 측면~단자함 끝 전체 폭 치수선이라 정의가 통상(축 중심~단자함 상면)과 다름 → HD 247·HC 211 만 구속, AD 는 `verify`.

### ① 내부 `tools/cad/build_internals_M1.py`
- 좌표 축 +X, 적층 중심 원점, mm. Stator_Core(치+요크 단일, RMxprt type 2 슬롯 36 컷), Coil_01…36(슬롯 안 사다리꼴 21.1525 mm² = Maxwell CoilTerm 단면, 피치 8, 엔드턴 = 3D 스플라인 스윕 `visual_estimate`, 경로 길이 = 시트 l_end 121.53 mm 에 맞춤 → 축 돌출 39.65 mm), Coil_01_short(안쪽 균일 오프셋 0.307 mm 셸, 체적비 25.00 %), Rotor_Core(닫힌 슬롯 28, 브리지 0.8), Bar_01…28(twistExtrude 10°), EndRing_DE/NDE(D_er 77.4, 20×12), Shaft(Ø36 → Ø30 베어링부 → DE Ø28×60 + 키홈 8×7×45, NDE Ø25), Bearing_DE/NDE(6206). 재질 태그 json. 출력 STEP(27 MB, `.gitignore` *.step 이라 미추적 — 스크립트로 재생성)·OBJ(그룹=부품)·GLB·cutaway(Y>0∧Z>0 사분면 절단, 고정자·하우징만). 삼각형 106,708(cutaway 80,694), 11.7 s.
- 체적: 치+요크 1,072,843 vs 1,077,645 (−0.45 %), 케이지 413,538 vs 409,740 (+0.93 %) — ±2 % 안. **코일 1개 10,806 vs 10,234 (+5.6 %)**: 지시 규칙(시트 엔드권선 길이)과 검증 기준(Maxwell RMxprt 자동 엔드코일 체적)이 동시에 만족되지 않음 → 기본은 시트 규칙, `--end-path geometry_check`(경로 106.9 mm)면 Maxwell 체적에 맞음. 결정 대기(docs/assets/M1_model.md §5).

### ② 하우징 `tools/cad/build_housing_100L.py`
- 카탈로그 구속: H A AA AB HA B1 BB C K HC HD L D E F GE 키 O PF + FF215(M N P n S LA T, B35 옵션으로 DE 엔드쉴드에 포함 — P 250 > 2H 라 발 바닥 아래 25 mm). visual_estimate: AC 196, 핀 28, 엔드쉴드 25, 팬커버 Ø190×60, 단자함 96×96(상면 HD 247), 아이볼트(상단 HC 211), 배치(어깨 x 125, 베어링 x ±108). `housing_params.yaml` 항목마다 source. 삼각형 4,956.

### ③ 검증 `tests/test_m1_model.py` — 6 passed, 1 skipped
- 체적(코어·케이지) PASS, 코일 합(시트 규칙 기준) PASS / geometry_check 기준은 skip(+5.59 %, 결정 대기), 슬롯 36·바 28·스큐 10.00°(GLB 양 끝단 중심각)·분할비 25.00 % PASS, 하우징 7치수 STEP 재판독(H 100·A 160·B 140·C 63·D 28·E 60·L 370) 모두 ±0.5 mm PASS, 삼각형 111,664 ≤ 300k PASS. 결과 표 `docs/assets/M1_model.md`(`tools/cad/write_model_doc.py`).
- 삽질: cadquery importStep 은 이름을 잃는다 → 발은 "두께 < 30 인 가장 낮은 솔리드", 축 어깨는 DE 엔드쉴드의 +X 평면 중 바깥에서 두 번째(스피곳 T 4 제외)로 찾음.

### ④ USD `tools/cad/build_usd_M1.py` (Isaac python)
- OBJ 4개 → M1_internals(_cutaway).usd(메시 72)·M1_housing(_cutaway).usd(7) → `M1.usd` 조립 105 prim: /M1(스케일 0.001) /Housing /Stator(Core, Coils/Coil_01…36, Coil_01_short) /Rotor(xformOp:rotateX; Core, Bars, EndRing, Shaft) /Bearings /Looks(재질 9종: 구리·알루미늄·규소강·주철·강·상 A/B/C·단락). variantSet `view` full/cutaway/windings_only(참조 교체·가시성). 적층 중심 x 0, 축 z 100 mm.
- 삽질(중요): 참조 대상이 Mesh 인데 자리 prim 을 `UsdGeom.Xform.Define` 으로 만들면 로컬 typeName(Xform)이 이겨 **메시가 렌더되지 않는다** → 타입 없는 `DefinePrim` 으로 바꿔 해결.

### ⑤ 장면 `motor_dt_viz/viz/m1_model.py` + `demo_integrated.py --m1_model [--view] [--m1_shots DIR]`
- /World/M1 에 M1.usd 참조, 22 kW 모델(/World/Motor)·전류 경로(/World/CurrentPaths)는 숨김(물리 조인트는 그대로 rpm 생성). 회전 = ω 적분 → /World/M1/Rotor rotateX. 색 = `assets/motors/M1/prim_map_M1.yaml`(열 노드 9개 ↔ prim 그룹 13, 코일은 권선 배치표 상별 색) × 기존 ThermalColormap. Coil_01_short 발광 = p_loop_total_W / p_loop(12턴 LUT). `config/prim_map.yaml` 불변.
- 7 장면 HUD ↔ 대시보드 fleet 로그: 장면 끝 Ia/Ib/Ic·I₂/I₁·판정 **7/7 일치**(같은 엔진·LUT; `tools/cad/check_m1_scene.py` → `assets/motors/M1/scene_check.json`). FPS: 1600×900 평균 58.4, 최소 47.2 (full 50 / cutaway 57 / windings_only 59) — 30 FPS 충족, 엔드턴 분할 수 조정 불필요.
- 제한: 전기 시나리오의 7 장면은 DT 의 정상·4턴·12턴·과부하·불평형·결상·무부하이고, 지시서의 8·16턴·저항성·반부하는 `config/electrical.yaml` 케이스가 아니라(config 불변) 장면에서 재생할 수 없다 — LUT 격자값은 Maxwell 수치표(시트 5)에 있음. 전류 입자·케이블은 22 kW 기하 전용이라 M1 장면에서 숨긴다(HUD 숫자는 그대로).

### ⑥ 산출
- 스크린샷 6장 `docs/assets/screenshots/M1/`(외형, cutaway 정상, cutaway 4턴 발광, cutaway 12턴, windings_only, 축단), `docs/assets/M1_model.md`, `docs/glossary.md`(USD variant·불리언 절단·로프트/스윕), `motor_dt_viz/README.md` 실행 3줄, 커밋 `assets: M1 full 3D model (housing + internals) + Isaac Sim scene`.

## 16. P4 후속 (파트 A, 2026-10-21) — 엔드턴 정본·AD·M1 시나리오 4장면·fault_focus·mount variant

- 엔드턴 정본 = `--end-path geometry_check`(기본값; RMxprt 자동 엔드코일 체적에서 역산한 경로 106.9 mm, 축 돌출 28.3 mm) → 코일 1개 10,234 mm³ = Maxwell(0.00 %), 코일 체적 테스트 ±2 % 복귀(6 passed). 시트 l_end 121.5 mm 는 `docs/assets/M1_model.md` 에 "시트 추정(참고)".
- AD 328: `housing_params.yaml` `source: catalog`, note "치수선 정의 = 프레임 측면~단자함 끝 전체 폭(플랜지형 175)". 끝면도 전체 폭(196) ≤ AD 구속을 스크립트가 assert. AC 는 visual_estimate 유지.
- `motor_dt_viz/config/scenarios_M1.yaml`(신규): 기존 7 장면 + 8턴·16턴·저항성(4턴 R_f 1.0)·반부하(4턴 50 %). 추가 케이스는 electrical.yaml 의 itsc_4turn 템플릿을 런타임에 복사해 lut {turns, R_f_ohm}·load 만 바꿔 등록(`M1Model.register_extra_cases`) — electrical.yaml·LUT 불변. 장면 HUD 값 = 엔진 설계값(LUT + 고유 0.027): 8턴 0.1676, 16턴 0.3625, 저항성 0.0324, 반부하 0.0953(I₂/I_n 0.0476) — 11 장면 모두 일치(`check_m1_scene`).
- cutaway 절단면을 θ −45~+45°(슬롯 1 = +Z 노출)로 회전, 카메라 프리셋 `fault_focus`(Coil_01_short DE 엔드턴 근접) → 03/04 스크린샷 재촬영. 단락 코일 발광은 UsdPreviewSurface emissiveColor 로 세기를 줘(×6) 표현 — 화면에서는 작게 보인다.
- 온도 색: 열 모델이 전기 전용 모드에서는 dt=0 으로 돌지 않아 **기계·통합 모드에서만** 적용 — 문서화.
- 플랜지: USD variant `mount` = B3(기본, EndShield_DE 플랜지 없음) / B35(EndShield_DE_B35, FF215). `--mount` 인자. 절단으로 형상이 사라진 부품(아이볼트)은 cutaway variant 에서 숨김 처리(USD 빌더).
- FPS(11 장면, 스크린샷 포함 실행): 평균 46 · 최소 39 — 30 FPS 충족.

## 17. P1 실측 기준선 체계 (파트 B, 2026-10-21)

원칙(코드·설정에 박음): 시뮬레이션 값은 실모터 판정 기준을 정하지 않는다. 기존 judgment_basis·근거 배지·electrical.yaml v2·M1.yaml 카탈로그 5항목·출처 아이콘은 덮어쓰지 않고 합쳤다.

- **P1-0 조사**: thresholds.yaml 전류 계열 = `current_ratio`(0.85/1.10/1.25/0.50)·`i2i1`(0.03/0.10), source/status/mode 없음. worst-of = `engine/thresholds.Judge._combine`, 스트림 플래그 없음(라이브 여부는 `demo_integrated` 의 `bridge`). AI Hub L-SF-04 전류 = 경량 샘플 `…\2020-02-125.기계시설물고장예지_sample\current\2.2kW\L-SF-04\정상` 77 파일(1 s·2 kHz, 메타 9줄 + 시간·ch1·ch2·ch3 = R·S·T, 전압·온도 채널 없음; 전체 zip 은 진동만). 배지 자리 = 상태 보드 게이지(`status/Gauge.tsx`)·전기 HUD(`elec/HUDElec.tsx` basis-badge)·모터 카드(`spec_source` 아이콘).
- **P1-1** `config/thresholds.yaml`: `current.{rated_ratio, negative_sequence, negative_sequence_rated, phase_unbalance}` + `judgment.provisional_policy`(simulation include_with_label / live advisory_only) + 온도·진동·베어링 source/status. 값 변경은 **두 개뿐**(git diff: `i2i1.safe_below 0.03 → 0.05` = `negative_sequence.warn 0.05`, `reference_baseline.value null → 0.1005`). 베어링은 reference_dataset/provisional(실모터 기준선 전 참고).
- **P1-2** `config/motors/M1.yaml`(기존 5항목 불변, 값은 datasheet_v4.yaml 카탈로그 직접값·MCSA 시트에서 스크립트로): model/catalog_no, rated_power_kw/poles/frame, rated_rpm 1730 → **1760**(카탈로그), efficiency_partial 75/50 % 0.894/0.880, 기동 전류·토크·최대 토크 650/210/250 %, GD² 0.008·중량 41·소음 60, 베어링 DE/NDE **6206ZZC3/6206ZZC3**(이전 6206/6205), 절연 F·온도상승 B·SF 1.15, duty **S1**(호이스트 S3 40 % ED 는 `duty_scenario`), BPFO/BPFI/BSF/FTF 3.568/5.432/2.311/0.396(= Hz ÷ 29.333, NDE 도 6206 으로 통일), 허용 진동 2.8(참고), reference_dataset. 로더 규칙 불변(배율 source 는 허용값 estimated 로 두고 basis 에 standard 근거; 래퍼 val() 확장만). 아이콘: catalog ✓ / nameplate·measured ✓✓ / assumed·estimated·calculated·verify_on_site 🔴.
- **P1-3** `engine/thresholds.py`: `Judge(stream=)`·`set_stream`, `kind_meta`, `i2i1_bounds`(absolute | baseline_multiple = baseline × 배수), `compensate_i2i1`(enabled + v2_v1 있을 때만), `_combine` 은 live+advisory_only 때 provisional 을 `Verdict.advisory` 로 분리(규칙 불변). `tools/baseline_capture.py`(1 s 창 페이저·I₁·I₂·불평형·V₂/V₁, 중앙값·p95·CV, 품질 게이트, diff 출력, `--apply-reference` 는 참고 등급만). 테스트 `tests/test_thresholds_provisional.py` 5종 통과(전체 134 passed).
- **참고 기준선 결과(주의)**: L-SF-04 정상 77 창 → I₂/I₁ 중앙값 0.0879 / **p95 0.1005**(= 위험 경계) / 최대 0.105, 불평형 0.066, I₁ 3.17 A(CV 0.7 %). 품질 게이트 **부적합(창 77 < 500)**. S상 RMS 가 10 % 커서 센서 채널 게인 차이인지 공급 불평형인지 구분 불가(전압 채널 없음) → 지시서의 "M1 참고 기준선 ≈0.027" 은 L-EF-04·R-EF-05 값이고 L-SF-04 는 아니다. 참고 등급이라 값은 기록했지만 판정 기준으로 쓰지 않는다(judgment_basis §5.4).
- **P1-4**: AI Hub 에 온도 채널 없음 → `docs/thermal_scaling.md` 절 + 상태 보드 온도 게이지 툴팁("M1 정격 상승 ≈21 K vs B종 80 K — 낙관적일 수 있음, 실측 전 보정 불가"). 스케일·임계값 불변.
- **P1-5**: 상태 보드 게이지 "참고 · 임시 기준" 회색 배지(전류/정격·I₂/I₁·베어링) + 툴팁(출처·모드·참고 기준선 p95), 전기 HUD 배지, 출처 아이콘 확장, index.json `thresholds.meta`. `npm run build` 통과. judgment_basis §5(출처·상태 표, 두 정책, 전후 표, 참고 기준선, 측정 절차, yaml 필드 경로 목록), README 기준선 2줄, glossary 4 용어.
- 삽질: M1.yaml 에 `source: reference_dataset` 래퍼를 넣자 P4 때 만든 `FIELD_SOURCES` 화이트리스트에 막혀 데모가 기동 실패 → 목록 확장(표시용 라벨, 검증 규칙 아님).

## 18. P2′ 단일 모터(M1) 전환 (파트 C, 2026-10-21)

사용자 결정(확정): 디지털트윈은 **현대 HLP-2.2/4(M1) 한 대**로 간다. 4종 호이스트 라이브러리는 만들지 않는다. 원칙: 모터 라이브러리 **코드 경로는 지우지 않는다**(YAML 한 장으로 되돌릴 수 있음). `thresholds.yaml` 숫자·판정 규칙·LUT·`electrical.yaml`·포트·발표 자료는 손대지 않았다(금지 파일 diff 0).

- **S1 설정**: `config/motors/` 는 `M1.yaml`(source **catalog**, 진동 `ISO 10816-1 Class I` 1.8/4.5)만. M2~M5 는 `git mv` 로 `config/motors/_retired/`(+ 옛 `motor.yaml` 사본 `motor_M5_reference.yaml`, README) — 로더 `list_ids()` 가 `_retired` 를 읽지 않고, `source: representative` 는 검증에서 **불허**. `config/motor.yaml` 을 M1 값(`library_default: M1`, Y 결선 4.73/4.73 A, 1760 rpm, 6206ZZC3 3.568/5.432, 질량 41, GD² 0.008)으로 재작성. 열회로 스케일 기준은 `config/thermal.yaml reference`(22 kW, η 0.90, 손실 2,444 W, scale 1.0 — 튜닝 계수 불변; M5 미등록이면 이 절 사용). `VIB_STANDARD_SPLIT_KW = 15` 규칙(< 15 kW → 10816-1). `config/status_demo.yaml`: `positions.M1`(electrical 40 s WARN) + `scene_map`(정상 15 SAFE / 4턴 40 WARN / 12턴 60 DANGER / DE 베어링 27.5 WARN / 과부하 85 DANGER). 테스트 5종 가정 → M1 단일로 갱신(IDS=["M1"], `_retired` 무시, representative 거부, M1 숫자 fr 29.333·BPFO 104.7 Hz, reference 절 ↔ 퇴역 M5 대조, Y 결선 기준 혼용 테스트 분기, iso_zone 1.8/4.5, live hello.motors == list_ids()) → **pytest 128 passed**.
- **S2 Isaac**: 기계 7 장면·통합 5 장면의 M1 자막을 `config/scenarios_M1.yaml` 에 추가(장면·배속·결함은 공용 `scenario_mechanical.yaml`/`scenario.yaml` 과 동일 — 스크립트로 대조). HUD 자막 변수 `{i2i1}`(그 케이스의 LUT 값) 추가. 시각 매핑은 `assets/motors/M1/prim_map_M1.yaml`(생성기 `tools/cad/write_prim_map_M1.py`): bearing_de/nde → `/M1/Bearings/DE·NDE`, shaft → `/M1/Rotor/Shaft`, **팬 커버를 별도 그룹 `fan_cover`(`/M1/Housing/FanCover`, 열 노드 frame)** 로 분리(14 그룹·80 prim 바인딩). 22 kW `/World/Motor`·전류 경로·입자는 M1 장면에서 숨김(기하가 22 kW 전용, 매 프레임 재숨김). 스크린샷 계획을 모드별로(`_SHOT_PLANS` mechanical 5장 / integrated 4장 / electrical 6장, 카메라 `bearing_de` 추가). 실행: 기계 `--mode mechanical --motor M1 --m1_shots … --max_s 183` FPS 평균 79/최저 66; 통합 `--mode integrated --record logs\m1_integrated\m1_integrated.mp4 --max_s 168` → mp4 **30 fps**(ffprobe r_frame_rate 30/1, 1456×938, 170.6 s, 오프셋 2.008 s, 타임코드 번인), 실행 FPS 평균 42/최저 32(녹화 중, 경고 0건). 장면 끝 값(통합): 정상 권선 42.4 °C·I₂/I₁ 0.027 SAFE → DE 베어링 65.9 °C·진동 4.8 DANGER(kurtosis) → 4턴 0.0726 → 12턴 권선 192.4 °C·0.2696 DANGER. 기계: 베어링 장면 DE 65.5 °C(온도 '정상' 70 °C 아래라 색 불변 — 위험 판정은 kurtosis·진동), 오정렬 축 44.3 °C·진동 3.6 Watch, 팬 고장 프레임 42.7 °C, 브레이크 축 61.3 °C, 과부하 권선 58.8 °C. 스크린샷 `docs/assets/screenshots/P2/isaac/`(기계 5·통합 4; 뷰포트 캡처라 HUD 는 안 찍힘). mp4 는 gitignore.
- **S3 상태 보드**: 모터 카드 1장(`.st-cards` grid `auto-fit`, 1장이면 max-width 520 px — 5장 코드 유지), `scene_map` 칩(클릭 → 모드·시각 이동, 기대 등급 색점), 정직성 라벨 4줄 교체("카탈로그 사양(출처 아이콘 참조, 결선은 현장 확인)" / "외형·내부는 카탈로그·데이터 시트 재구성(Maxwell 체적 ±2 % 검증)" / "열회로 계수는 22 kW 기준 스케일 — M1에서 낙관적일 수 있음" / "ITSC 곡선은 등가회로 LUT + 2D 와전류 검증, 실측 기준선 전 참고"), 게이지 M1 규격(정격 4.73 A, 진동 1.8/4.5). `npm run build` 통과, 오프라인 `node serve.cjs`(4173)에서 스크린샷 `docs/assets/screenshots/P2/status_board_m1.png`.
- **S4 문서**: README(머리말 M1, 라이브러리 절 "현재 M1 한 대·코드 유지", 녹화·상태 보드·라이브 M5 문구, Δ결선 한계 → Y, "단일 모터 M1 전환" 절), `docs/judgment_basis.md`(§5.1 진동 출처 10816-1, **§6** 전환 표 — 규칙·임계값·LUT 불변), `docs/thermal_scaling.md`(머리말: reference 절, 5종 표는 이력), `tools/fleet_summary.py`(단일 모터면 `docs/m1_summary.md` + M1 문구, M5 회귀 절은 다중일 때만) → `docs/m1_summary.md` 재생성, `dashboard/README.md`(상태 보드 M1 단일), **`docs/m1_migration_notes.md`**(해설 PDF·가이드라인·센서 가이드·구매 목록에서 바꿀 문장 목록 + 값 대응표 22 kW → M1; 이 파일들은 저장소에 없어 본문 미수정), 루트 `docs/glossary.md` P2′ 5 용어. `tools/electrical/verify_lut_integration.py` V4 는 M5 대신 motor_id≠M1 설정으로 같은 규칙 검증.
- **하지 않은 것**: 임계값·판정 규칙·LUT 변경, 라이브러리 코드 삭제, 퇴역 yaml 삭제, 해설 PDF·가이드라인 본문 재작성, 발표 자료, 22 kW 애니메이션 원본 영상·USD 삭제.
- **한계**: 열회로는 22 kW 보정값 스케일(M1 낙관적 가능, 실측 전 보정 불가). M1 기계 장면은 온도만으로 '위험'에 닿지 않는다(위험은 kurtosis·진동 상수). 베어링 색은 열 노드 단계 색이라 65 °C 에선 기본색. 결선 Y 는 카탈로그 기준 가정(`verify_on_site`). 통합 녹화 중 FPS 32~42(녹화 없이 63~79).
- **S5 검증**: pytest 134 passed(viz 128 + M1 모델 6), `verify_lut_integration.py` **8/8**(V7 라이브 88 states, healthy 0.027 / 4T 0.0726; V8 금지 파일 clean). 삽질: 같은 verify 를 Git Bash 에서 띄우면 V7 의 Isaac 자식 프로세스가 "Startup Complete" 직후 로그 없이 종료해 접속 실패(7/8) — PowerShell/cmd 에서 실행하면 통과한다(README 의 실행 예와 같음). 커밋 `9723c61 motor: single-motor M1 (HLP-2.2/4), library retired` + 보고서 후속 커밋, 푸시.

## 19. M1 "반절 반투명" 뷰 — 자르지 않고 한쪽 반을 투명하게 (H0~H4, 2026-10-21)

목적: 외형을 유지한 채 한쪽 반을 반투명으로 두어 권선·로터·베어링이 비쳐 보이게. 새 계산 없음(시각만). `config/`·`engine/`·판정·LUT·기존 variant 3종·22 kW 자산 불변(금지 diff 0, full/cutaway 메시 git 불변).

- **H0**: 렌더 RTX Real-Time(`render_demo.yaml render_mode: RaytracedLighting`), 기준 FPS 기계 79/최저 66·통합 42/32(녹화 중, 18장). 절단 코드 = `tools/cad/m1_common.quarter_cutter`(하우징 line 129, 내부 line 267). 부분 불투명도 = carb `/rtx/raytracing/fractionalCutoutOpacity`.
- **H1 기하**: `m1_common.half_cutters/split_parts`(top: Z = 축 중심 → `_T/_B`, front: Y = 0 → `_F/_R`), `build_housing_100L.py --half-split`(Foot 제외 7부품), `build_internals_M1.py --half-split`(Stator_Core 만). 체적 합 편차 **최대 0.0000 %**(테스트 ±0.1 %). 빈 조각: top 의 TerminalBox·Eyebolt `_B`(전부 축 위) → 메시 없음. 삼각형: 하우징 half top 4,976 / front 5,160, 코어 top 4,880 / front 4,504; 전체(full 133,184 + half 쌍) ≤ 300k.
- **H2 재질·variant**: `/M1/Looks/translucent_housing`(주철 색, opacity 0.20) · `translucent_core`(규소강 색, 0.35) — **UsdPreviewSurface opacity + opacityThreshold 0 채택**(기존 파이프라인과 같은 셰이더, RTX 실시간에서 fractionalCutoutOpacity 만 켜면 블렌딩 순서 문제 없음; OmniGlass thin_walled 는 미채택). variantSet `view` += `half_translucent`(top) · `half_translucent_front`. 반투명 조각은 variant 안에서만 정의되는 형제 prim(`/M1/Housing/Frame_T` …, 8개/variant)이라 런타임 그룹 재질(온도 색, strongerThanDescendants)의 영향을 받지 않는다. mount variant 는 `_T/_F` 조각도 함께 숨긴다. `viz/m1_model.set_view()` 가 half 선택 시 fractionalCutoutOpacity 를 켜고 다른 variant 로 가면 원래 값 복귀; `HALF_GLOW` 1.5(단락 발광 표시 세기). `demo_integrated --view half_translucent|half_translucent_front`, half 뷰에서는 베어링 경고 시 cutaway 로 바꾸지 않는다. 분할선은 그대로(띠 재질 옵션 미구현).
- **H3 동작·검증**: 통합 정상·DE 베어링·4턴 재생(half_translucent): 로터 회전·온도 색(불투명 반)·Coil_01_short 발광이 반투명 껍질 너머로 보임(03_half_itsc_4turn 주황 발광). FPS **통합 평균 39.3 / 최저 37.4, 기계 평균 59.9 / 최저 57.6**(1600×900, ≥ 30 충족 — 코어 불투명 되돌림 불필요). 스크린샷 `docs/assets/screenshots/M1_half/` 4장(정상 측면·등각, 4턴 fault_focus, DE 베어링; 뷰포트 캡처라 HUD 없음 — `tools/viz/shot_with_hud.py` 는 저장소에 없음). 테스트 `tests/test_m1_model.py` +4(체적 합, GLB 조각 이름, USD variant 5종·재질 opacity·불투명 부품 유지, 삼각형) → 10 passed.
- **H4 문서**: `docs/assets/M1_model.md` §4b(variant 표·재질값·렌더 설정·채택 이유, `write_model_doc.py` 생성), `docs/glossary.md` 4 용어.
- **한계**: 반투명 반은 내부 조명이 없어 비치는 정도가 은은하다(측면 뷰에서는 코일 윤곽만, 근접·발광 장면에서 뚜렷) — opacity 를 더 낮추거나 내부 광원을 두는 것은 값 결정 사항이라 보류. `half_translucent_front` 는 USD 테스트로만 확인(Isaac 재생은 top 만). 반투명 반에는 온도 색이 적용되지 않는다(의도).

## 20. Isaac Sim 결함 시뮬레이션 ↔ Maxwell/등가회로 해석 대조 검증 — 증거 보고서 + 실시간 비교 패널 (V0~V6, 2026-10-21)

목적: M1 전기 결함 시나리오를 Isaac Sim 에서 실제로 돌려 결함이 언제·어떻게 잡히는지 기록하고, 화면·HUD 의 숫자가 해석 결과(RMxprt v2m2 → MCCM/LUT v2 → 2D FEM F1 정합)에서 어떻게 나왔는지 수치 대조·근거 사슬로 보인다. **새 계산·해석·설정 변경 없음**(`config/`·`engine/`·LUT diff 0). Maxwell 저장소는 읽기만.

- **V0 현황**: 전기 11 장면(정상·4·12턴·과부하·불평형·결상·무부하·8·16턴·저항성 4턴·반부하 4턴, 245 s), 상태 JSON 10 Hz. 빠진 필드(I₁·I₂·I₂ 위상·I_f·판정 이벤트·파형)는 **로깅 훅만** 추가: `demo_integrated.py --verify_dir`(state.csv 전 필드 10 Hz·events.csv·waveform_<t>_<pre|post>_<case>.csv 1 s·2 kHz·meta.json 에 LUT/yaml sha), `--inherent_angle_deg`(그 실행의 메모리만), `--scenario_yaml`(검증 전용 시나리오). 난수 없음 — 재현성은 설정 각도. 해석 파일 sha 는 `analysis_reference.json inputs`(16 파일).
- **V1 배치(Isaac 헤드리스, PowerShell)**: 전기 전부 × 고유 비대칭 각도 0/90/180° (3회, 각 4,400 행) + 통합 열 4·12·16턴(`tools/verify/scenario_itsc_*_thermal.yaml`: 정상 20 s + ITSC 200 s × 배속 90 = 300 분, 3회). 정상 상태: 모든 장면 I₂/I₁ 마지막 5 s 표준편차 0 %(합성 신호라 과도 없음). `logs/verify/`(gitignore).
- **V2 대조** `tools/verify/sim_vs_analysis.py` → `docs/verification/sim_vs_analysis.{json,md,xlsx(수식 판정)}`, `logs/verify/export_<시각>.csv`. **77/82 PASS**: I₂/I₁ 결함분(합성 − 고유 비대칭 페이저) vs LUT 최대 **0.48 %**(허용 ±1 %), 합성값 범위 안, 불평형 ±0.25 %, I_f vs MCCM ≤ 0.15 %(FEM F1 35.2/4.56 A 참고 열 −2.2/−2.9 %), 손실 ≤ 0.44 %(허용 ±2 %), 권선 ΔT 정상 상태 vs 에너지 수지 역산 **0.00 %**(4턴 44.7 / 12턴 166.3 / 16턴 247.4 °C, 300 분), 판정 예상 일치(4턴 WARN 3.06 s, 12턴 DANGER 3.03 s, 8턴 3.09 s, 저항성 SAFE), 정상 오경보 0, **독립 재계산**(`recompute_i2i1.py`, 엔진 비의존 Fortescue·DFT) 69 파형 최대 **0.023 %**(허용 ±0.5 %). FAIL 5건은 한 가지 규약 차이: 엔진은 I₁ 을 정격×부하로 고정하고 LUT 의 I₂/I_n 은 결함 시 상승한 LUT 자체 I₁ 기준 → 시뮬 'I₂/I_n' 표시값 = I₂/I₁×부하(4턴 −2.9 %, 16턴 −29 %). 엔진 수치 변경 금지 범위라 보고만.
- **민감도**: 고유 비대칭 각도 0/90/180° 에서 4턴 합성 I₂/I₁ 0.0726 / 0.0683 / **0.0313** → 180°(결함 I₂ 와 반대 방향)이면 경계 0.05 아래라 **4턴 경고가 사라진다**(저항성 4턴·정상은 변화 없음). 부하 50/100 %: I₂/I₁ 0.0953/0.0726 로 흔들리고 I₂/I_n(결함분) 0.0374/0.0490 — 부하 무관 지표도 엔진 규약 때문에 완전 무관하지 않음(보고).
- **V3 근거 사슬** `tools/verify/traceability.py` → `docs/verification/traceability.{json,md}`(11 행: 표시량 → 엔진 함수 → 파일(sha) → 해석 단계 → 등급) + 한계 6건. 기계 결함은 "Maxwell 근거 없음 — 진동·베어링 상수(표준/AI Hub 참고)".
- **V4 그림** `docs/verification/img/`: i2i1_timeseries(판정 띠·주입 점선·0.05/0.10), sim_vs_analysis_bars(결함 4종 × I₂/I₁·I_f·손실), winding_temperature(4·12·16턴, 점선 = 역산), waveform_spectrum(기본파 단일 — RSH 없음 명시), HUD 합성 4장(`hud_composite.py`: 뷰포트 캡처 + state.csv 값 — Isaac 캡처에 omni.ui HUD 가 안 찍혀 합성), 상태 보드 2장(4턴 WARN·12턴 DANGER, V6 패널 포함).
- **V5 보고서** `docs/verification/sim_vs_analysis_report.md`(`write_report.py`): 한 줄 결론·시나리오별 서술(비전공자용)·대조표·열·민감도·근거 사슬·한계·증명하는 것/않는 것.
- **V6 실시간 패널**: `tools/verify/build_analysis_reference.py` → `data/electrical/analysis_reference.json`(+ dashboard public 사본; 수기 숫자 없음, 입력 sha 16개, LUT sha 일치 확인): 정격점(카탈로그/RMxprt/FEM lite/IEC), 기동(6.5× → RMxprt 8.24× → FEM+F2 7.43×), 시나리오별 LUT 결함분·합성 범위·I₂/I_n·MCCM I_f·FEM I_f·손실·열 모델 ΔT·예상 판정·Z₂ +20 %, 등가회로(R1 20/95 °C, R2′, X1, X2′, Xm 97.6 vs FEM X_total 95.6, Z₂ 7.136 vs 5.33/5.97, 단락 턴 L). 상태 보드 `④ 해석 근거 비교` 전용 행(`src/status/AnalysisRef.tsx`): 지금 표시값 | 해석 기준값 | 차이 % | 출처 배지, 허용 안 초록/밖 주황+ⓘ 사유, "모터 모델 근거" 접이식 표, "근거 보기" 서랍(traceability.json + 한계), "비교 내보내기"(V2 형식 CSV 다운로드 `export_<시각>.csv`), 기계 모드 "Maxwell 근거 없음". Isaac HUD 한 줄 `ref: I2/I1 … (shown …, ±%) | I_f | P_loop | LUT v2 + 2D FEM`(`hud.update_reference`). `npm run build` 통과, 포트·WebSocket 불변.
- **검증**: pytest 144 passed(+6 `tests/test_verify_tools.py`: 합성 파형 재계산 정확성, 기준 파일 sha·출처, 판정 규칙, 검증 시나리오 타이밍). 금지 파일 diff 0.
- **한계·주의**: 합성 신호(과도 없음, RSH 없음)라 탐지 지연 = 지속 3 s 규칙뿐. 고유 비대칭 각도는 근거 없는 가정(0°)이고 180° 면 4턴을 놓친다 — 실측 기준선 전까지 provisional. 열 ΔT 대조는 같은 모델의 자기 일관성. 브라우저 패널의 CSV 내보내기는 다운로드(Isaac 쪽 `logs/verify/export_*.csv` 는 sim_vs_analysis.py). Isaac 실행은 PowerShell/cmd 에서(Git Bash 자식 프로세스 조용히 종료).

## 21. 엔진 수정(이 건에 한함): LUT 경로 I₁ = LUT 정상분 RMS — D3 원 사양 (2026-10-21)

사용자 승인: `current_model` lut 경로에서 정상분 크기 I₁ 을 "정격 × 부하" 고정이 아니라 LUT 의 상별 RMS(턴 비율·R_f·부하 격자/보간)에서 가져온다. thresholds·LUT·장면 불변.

- **변경** `engine/current_model.CurrentModel._phasors`: `i1 = √2 · q["i1_A"] · (i_rated / rated_current_A)` (LUT 는 선전류 I_n 기준, Y = 배율 1); LUT 에 I₁ 이 없을 때만 이전 규약. 결과: I₂/I_n 표시값이 LUT 정의와 같아짐(결함분), r = I/I_n 이 결함 시 상승, 열 모델 pu 가 실제 전류 기준. 정상 I₁ 4.73 → 4.695 A(MCCM 물리 보정 전류).
- **전후 표** `docs/verification/d3_i1_from_lut.md`(`tools/verify/d3_snapshot.py`): 4턴 I₁ 4.73 → 4.887, r R상 1.067 → 1.103, I₂/I_n 0.0726 → 0.0750, ΔT 44.7 → 45.6 °C; 12턴 I₁ 5.923, r 1.563(과전류 위험 구간), ΔT 166.3 → 174.4; 16턴 I₁ 6.633, r 1.881, ΔT 247.4 → 261.9. **판정이 바뀐 시나리오 1건**: 반부하 4턴 DANGER(current_ratio, T상 0.457 결상 의심) → WARN(i2i1 0.095; 세 상 0.62~0.73 저전류 경고). legacy 케이스(과부하·불평형·결상·무부하) 불변. status_demo 기대 상태(15/40/60/85 s) 불변.
- **재검증**: verify_lut 8/8, Isaac 배치 6회 + HUD 재실행 → `sim_vs_analysis` **89/89 PASS**(이전 77/82 의 I₂/I_n FAIL 5건 해소, I₁ vs LUT 행 7개 추가 ≤ 0.02 %), 권선 ΔT 역산 편차 ≤ 0.001 %, 독립 재계산 127 파형 ≤ 0.023 %. `analysis_reference.json`(sim_expected 를 LUT I₁ 기준으로)·보고서·HUD 합성·상태 보드 스크린샷·fleet 로그·`m1_summary.md`·대시보드 데이터 재생성. 테스트 144 passed(`test_m1_current_model_default_equals_library` 를 D3 기대값으로: 정상 I₁ 4.6946, 12턴 I₁ > 5.5).
- 한계: `scene_check.json`(P4 §5b 표, 이전 I₁ 규약 값)은 재실행하지 않음 — 수치는 `docs/verification/`이 정본. 민감도(각도 180° 면 4턴 경고 소실)는 그대로.

## 22. 마무리 D — 재현성·릴리스·검증 요약 (D1~D5, 2026-10-21)

- **D1 깨끗한 복제본 재현**(ASCII 임시 경로에 두 저장소 clone): Maxwell `mccm.py → e3_tables.py → x_numbers_xlsx.py --no-dt` 통과(AEDT 불필요, 결과 json 60개 커밋본). DT `import_lut.py`(sha 동일) → `run_fleet` → pytest **135 passed·8 skipped**(AI Hub L2/L3 없음) → `build_internals_M1 → build_housing_100L → build_usd_M1`(Isaac, prims 110) → `build_analysis_reference`(MAXWELL_ROOT 환경변수) → `export_status_data` → `npm install·build` → `verify_lut_integration` **8/8**. 막힌 것과 조치: ① 하드코딩된 Maxwell 경로 4곳 → `MAXWELL_ROOT` 환경변수(`import_lut`, `verify_lut_integration`, `build_analysis_reference`, `datasheet_to_yaml`); ② `test_fleet` 는 `run_fleet` 선행 필요(REPRODUCE 순서); ③ 해설 대시보드 데이터(`public/data/{mechanical,electrical}`, 22 kW 녹화 로그에서만 생성)가 gitignore 라 `export_status_data` 가 죽음 → **동결 커밋**(824 KB, `.gitignore` 예외); ④ `datasheet_to_yaml` 은 카탈로그 PDF(저장소 밖) 없이 돌리면 치수표가 빠진 yaml 로 덮어씀 → 돌리지 말 것; ⑤ Maxwell `e3_tables.py` 는 `analysis_report.md` 뒤 절(F·S·X)을 지워 `x_numbers` 검산 3 FAIL → 커밋본이 정본(REPRODUCE §1 주의); ⑥ `test_reference_has_sha…` 가 재생성되는 `lut_integration_report.md` sha 까지 비교해 clone 에서 실패 → 그 키 제외. `docs/REPRODUCE.md`(요구 소프트웨어 버전, 순서, 예상 시간, 실패 시 확인 9건).
- **D2**: 태그 `v1.0-m1` 두 저장소("M1 단일 모터 트윈, 학생판 2D 검증 완료"). `CHANGELOG.md` ← `tools/docs/changelog_from_log.py`(SESSION_LOG 장 제목 + 같은 날 git 커밋, 31 장). DT 루트 `CLAUDE.md` 신설(환경 함정: V7 은 PowerShell/cmd, Isaac 캡처 HUD 미포함 → `shot_with_hud.py`, 입력 복사본 `assets/motors/M1/inputs/` 기준, Blender 동시 실행 금지, run_fleet 선행, 동결 데이터).
- **D3 HUD 합성 스크린샷** `tools/viz/shot_with_hud.py`(`run|compose|all`, 시나리오·뷰 인자; `demo_integrated --shot_plan` 추가): 뷰포트 캡처 + 같은 시각 state.csv(엔진 값) 오버레이(상태·원인·I R/S/T·I₁·I₂/I₁·I₂/I_n·I_f·P_loop·온도·진동·등급·해석 기준 한 줄). `docs/assets/screenshots/M1_hud/` 10장(전기 6: 정상·4턴 fault_focus·8턴·12턴·저항성·반부하 / 기계 4: 베어링 DE·오정렬·과부하·냉각 저하) + `*.txt` 캡션 + `captions.json`(장면·시각·표시값·출처). 삽질: `all` 로 연속 실행 시 두 번째 Isaac(기계)이 기동 직후 조용히 종료 → 기계는 cmd 에서 직접 재실행 후 `compose`.
- **D4** `docs/verification_summary.md`(+`.json`) ← `tools/docs/verification_summary.py`(수기 없음): 출처 등급 9항목, 핵심 숫자(정격 4.73 A·0.79·89.5 %, 기동 FEM 7.43× ≤ IEC 7.8, 역률 FEM 0.740 유일 미달, I₂/I₁ 0.027/0.073/0.17/0.27, 저항성 결함분 0.0065, Z₂ +20 %), P1 결과 그대로(L-SF-04 77창 중앙값 0.0879·p95 0.1005·불평형 0.065·S상 +10 %·게이트 부적합·참고 등급), WARN 0.03→0.05 전후 11행(D3 I₁ 규약), 건전 모터 분포 6대, **함의 절**(기준선 배수 보정 없음: 경고 0.201/위험 0.402 → 4·8턴 SAFE, 12턴 WARN, 16턴 WARN — 12~16턴급부터), 대조 89/89·≤0.48 %·≤0.023 %·지연 3.01/3.07 s, 한계, 입력 sha 16개. `scene_check.json` 을 D3 I₁ 규약으로 재실행(§5b 표 갱신).
- **D5 AI Hub 전체 zip**: 디스크에 샘플 zip(261 MB)만 있고 Training 전체 zip(88~112 GB)은 미다운로드 → **건너뜀**(사유 기록). 샘플 기반 건전 모터 분포(4대 2.2 kW + 55 kW 2대)만 D4 에 반영, `reference_baseline` 불변.
- **E 산출 문서 4종**: `docs/deliverables/_v22kW/` 에 원본 없음 → 4종 모두 건너뜀(`docs/deliverables/README.md` 절차·`CHANGES_M1.md` 빈 표). 값 대조 테스트 `tests/test_deliverables_values.py`(대응표 ↔ verification_summary.json ↔ M1.yaml 6값, 산출 문서는 있을 때만) 추가. python-docx·weasyprint·reportlab 미설치.

## 23. D 후속 — e3 마커·해설 데이터 M1 전환·fem_verified 문구·창별 게이트·저전류 경부하 규칙(승인)·E 준비 (2026-10-21)

1. **Maxwell `e3_tables.py`**: `analysis_report.md` 를 통째로 쓰지 않고 `<!-- e3:begin -->…<!-- e3:end -->` 사이만 갱신(`_write_report_between_markers`). 커밋본 보고서를 제목 / F1~F6·S1~S4·X1~X5 절 / 마커[E3 본문] 구조로 한 번 재배치. 재실행 뒤 F·S·X 절 보존 확인, `x_numbers_xlsx.py` 검산 3 **PASS 복귀**(4/4). Maxwell 커밋 `3c4e22e`.
2. **해설 대시보드 데이터 ← M1 배치 로그**: `export_dashboard_data.py --source fleet [--motor M1]`(fleet CSV 는 데모 로그와 같은 컬럼; thresholds 의 I₂/I₁ 눈금은 LUT 설계값 0.027/0.0726/0.2696, 정직성 문구 M1 카탈로그, 영상 없음). 확장 모듈(`export_mechanical_extras`·`export_electrical_extras`)에 엔진 주입(`ENGINE`)으로 재실행 검증 **PASS**(기계 경계 밖 최대 0.10 °C ≤ 2.5; 전기 RMS 0.046 A, 로그 RMS 반올림 한계 0.05/I_n 을 허용에 더함). 22 kW 녹화 기반 동결본은 `docs/deliverables/_v22kW/dashboard_data_22kW/` 로 이동(보관), `.gitignore` 원복. 테스트 `tests/test_dashboard_fleet_export.py`(timeseries 25 지점 ↔ fleet 로그 일치, 재검증 PASS, 눈금 M1).
3. **`electrical.yaml source.fem_verified`** = "2D-eddy-lite (I_f ±3 %, Xm −3.7 %, locked-rotor IEC 안)"(값·LUT 불변). `current_model.electrical_source` 가 문자열을 우선 전달, Isaac HUD(`FEM: …`)·전기 해설 배지(`2D FEM lite 검증`)·`feed.ts`/`AnalysisRef` 타입·traceability 문구 갱신.
4. **`baseline_capture.py` 창별 정상성 게이트**: 창 I₁ 이 중앙값 ±5 % 안, 기본파/전체 RMS ≥ 0.95, 상별 RMS/평균 0.8~1.25(`--gate-*`, `--no-window-gate`); `window_gate`(제외 창 수·사유·목록)·`phase_rms_ratio` 기록. `tools/aihub/baseline_table.py` → `docs/aihub_baseline_gated.md/.json`(샘플 6대): L-EF-04 415/667, R-EF-05 63/65, L-DSF-01 80/97, L-SF-04 77/77(값 불변 0.0879/0.1005), L-PAHU-03S 0/97(인버터 49.6 Hz → 60 Hz 게이트 전부 제외), R-PAHU-04S 59/59. L-SF-04 S상 비 1.066 이 날짜별로 일정 → **센서 게인 차이 가설** 우세(가설로만, 보정 없음). `verification_summary` §3 표 교체, `reference_baseline` 참고 등급 그대로.
5. **저전류 판정 규칙 변경(승인)**: `thresholds.yaml current_ratio.low_current_policy {light_load_advisory: true, unbalance_gate: 0.05}`(source/status·경계 불변), `engine/thresholds.Judge._light_load_policy`(_combine 앞): 세 상 함께 r < 0.50 + 불평형 < 0.05 + I₂/I₁ < 경고 → '경부하(참고)' advisory(level SAFE, raw DANGER 보존), 종합 미반영; 한 상 저전류·불평형·I₂/I₁ 동반은 기존 DANGER; 상한·히스테리시스·지속 불변(경부하 동안 내부 상태 SAFE·지속 시계 리셋 → 경부하 뒤 상향도 3 s 규칙; 처음 구현의 '즉시 DANGER' 는 검증 배치에서 8턴 장면이 지속 없이 위험으로 찍혀 수정). 전후 표 `docs/verification/light_load_rule.md`(`tools/verify/judgment_before_after.py`): **no_load DANGER(current_ratio) → SAFE(+경부하 참고)**, single_phasing·overload DANGER 유지, 나머지 불변. 테스트 `tests/test_light_load_rule.py` 6종. `judgment_basis.md` §8, `verification_summary` §3 표에 advisory 표기.
6. **E 준비**: `pip install reportlab python-docx`(reportlab 5.0.1), 맑은 고딕 TTF 임베드 확인(`MalgunGothic`/`Bold` 서브셋 임베드, 한글 추출 OK). `_v22kW/` 원본 들어오면 E 실행.
- 테스트 155 passed·1 skipped. 금지 파일: thresholds.yaml 은 승인된 `low_current_policy` 블록만, electrical.yaml 은 fem_verified 문구만, LUT·M1.yaml·엔진 수치 불변.

## 24. 시뮬 vs Maxwell 비교표(엑셀 9시트 + 한 장 요약) + 결함 크기 역추정 + FEM 불확실성 민감도 (C0~C4, 2026-10-21)

- **C0**: 검증 로그가 경부하 규칙 전 실행본이라 전기 3각도 배치 재실행(meta.json 에 `git_commit` 기록 훅 추가). 첫 재실행에서 **8턴 장면이 지속 없이 즉시 DANGER** — 무부하 장면에서 넘겨받은 내부 DANGER 상태가 원인 → `_light_load_policy` 가 경부하 동안 세 상 내부 상태를 SAFE 로 두고 지속 시계를 리셋하도록 수정(`2cd8914`, 테스트 j3/j4) → 재실행(커밋 2cd8914, 23:16~23:25): `sim_vs_analysis` **89/89**(8턴 DANGER 2.95 s, 4턴 WARN 2.98 s, 12턴 3.03 s).
- **C1** `tools/verify/sim_vs_maxwell_xlsx.py` → `docs/verification/M1_sim_vs_maxwell.xlsx`(0 요약 · 1 시나리오 비교 7×11 양: 시뮬|RMxprt|MCCM/LUT|2D FEM|카탈로그|오차 수식|허용|판정|등급|쉬운 설명 · 2 정격·기동 · 3 결함 크기 역추정 · 4 FEM 불확실성 민감도 · 5 탐지 시각(+5b 시계열) · 6 등가회로 대조 · 7 근거 사슬 · 8 한계; 차트 3: I₂/I₁ 막대(시뮬·LUT·FEM-민감도), 주입 vs 추정 턴 산점(대각선), 4·12턴 시계열) + 바탕화면 `M1_시뮬_vs_Maxwell.xlsx` + `sim_vs_maxwell_summary.md` + `sim_vs_maxwell.json`. 기존 대조·로그·LUT 재사용, 수기 없음, 입력 sha 각 시트 하단.
- **C2 역추정**: 결함분 = |합성 페이저 − 0.027∠시드각|, LUT(턴 비율 축, 해당 R_f·부하 격자) 단조 구간 선형 역보간 × 192. 결과 **18/18 ±1턴**(각도 0/90/180° × 6 시나리오, 오차 0.00 — 엔진이 같은 LUT 를 쓰므로 당연한 결과이며 "분리 규칙이 올바르다"는 뜻). 합성값(분리 전)으로 역추정하면 각도에 따라 **−3.4~+5.1턴**(4턴 4.99/4.81/2.98, 저항성 4턴은 9.1/8.9/7.4턴) — 현장에서 고유 비대칭을 모를 때의 오차.
- **FEM 민감도**: Z₂ 앵커 7.136 → FEM 보정 5.97 Ω(I₂ ×1.20): 4턴 0.0725→0.082(WARN 유지), 8턴 0.168→0.197, 12턴 0.270→0.319, 16턴 0.362→0.430(DANGER 유지), 저항성 SAFE 유지, **반부하 4턴 0.095→0.110 WARN→DANGER(판정 변화 1건)**.
- **결론 한 줄**: 시뮬 전기 수치는 LUT 와 ≤ 0.47 %, 2D FEM 보정 I_f 와 ≤ 4.3 %, 역추정 ±1턴 18/18, FEM 불확실성 판정 변화 1건. 테스트 `tests/test_sim_vs_maxwell_xlsx.py` 6종(시트1 시뮬값 = sim_vs_analysis, LUT 열 = LUT 파일, 격자점 복원, ±1턴, 시트·차트 수, 바탕화면 사본). 전체 161 passed.

## 25. 보고용 미디어 팩 — 모터 구동·결함 장면·대시보드 영상과 사진 (M0~M6, 2026-10-26)

- **산출** `docs/media/20261026/`(84 MB, 60 MB 초과 영상 없음) + 바탕화면 사본 `~/OneDrive/바탕 화면/M1_미디어팩_20261026/`: `isaac/` 13장(01·04·08 은 2560×1440, 나머지 1920×1080 — 뷰포트 텍스처 해상도를 캡처 때만 바꿈), `hud/` 9장(뷰포트 캡처 + 같은 시각 state.csv 합성, `check_vs_state.json` 독립 재판독 **9/9 PASS**), `dashboard/` 12장(Edge 1920×1080, title 툴팁은 DOM 오버레이·캡션에 원문, CSV 내보내기 다운로드 `export_20261026_152811.csv` 포함), `video/` 10편(01 외형 궤도·02 절단 궤도·03 전기 76 s·04 반투명 궤도·05 기계 75 s·06 통합 166 s·07 대시보드 워크스루 54 s·08 Isaac↔상태 보드 side-by-side 60 s + GIF 2), `figures/` 23장(Maxwell 17 + 검증 6, ASCII 이름), `index.md`·`meta.json`(커밋 DT 75bd475 / Maxwell 3c4e22e, 시드 없음=결정적, 배속 1×)·`README.md`(규격·재현·한계·수동 캡처 체크리스트 6항목)·`contact_sheet.png`(57장).
- **도구** `tools/media/capture_all.py`(`plan|isaac|hud|video|figures|dashboard|index|desktop`, `--skip/--retake/--only`), `dashboard_shots.mjs`·`dashboard_sync_rec.mjs`·`dashboard_export_shot.mjs`(Playwright + 설치된 Edge, 시스템 ffmpeg gdigrab 녹화), `cameras.yaml`(iso/side/front_shaft/fault_focus/bearing_de/close/rotor_closeup/orbit = `m1_model` 값). demo 캡처 전용 인자: `--res W H`, `--cam_plan "t:view:cam;…"`(orbit 20 s/360°), `--capture_layout`(창 클라이언트 1920×1080 at (0,0) + Kit 패널 숨김 + HUD 패널 오른쪽), `--shot_plan` 파일명 `@WxH`. 장면·엔진·대시보드 코드·config 불변.
- **실측 함정**: ① 배치에서 `python.bat` 는 `call` 필요(없으면 첫 실행 뒤 종료). ② `--res` 만으로는 Kit 창이 1456×938 — Win32 MoveWindow 로 클라이언트 영역을 맞춤. ③ Kit 기본 레이아웃(Stage·Content·'Isaac Sim Assets [Beta]')이 뷰포트를 1/3 로 줄여 `--capture_layout` 추가. ④ gdigrab 은 데스크톱 캡처라 녹화 중 VS Code·탐색기가 앞으로 오면 그 화면이 찍힘 → 궤도·대시보드 동기 2편 재녹화. ⑤ Playwright 번들 Chromium/ffmpeg 다운로드 정지(1.3 MB) → Edge 채널 + 헤드 모드(PowerShell 에서만 기동). ⑥ 상태 보드 ▶ 재생은 `?t=` 와 무관하게 0 s 부터 → side-by-side 동기 원점 0 s. ⑦ front_shaft 1.05 m 는 너무 멀어 0.62 m 로, orbit 0.95/0.45 → 0.78/0.36.
- **22 kW 문구**: 해설 화면(#/electrical·#/mechanical)은 22 kW 녹화 영상을 재생하므로 제외하고 상태 보드 장면 4장으로 대체. 상태 보드 전 화면 상단의 정직성 한 줄("열회로 계수는 22 kW 기준 스케일 — M1에서 낙관적일 수 있음")은 M1 이행 주석이라 **포함하고 index 에 표시**(제외 여부는 사용자 판단).
- 못 찍은 것: 없음(수동 항목 6개 — Maxwell GUI 자속밀도·전류밀도·메시, 라이브 모드 화면, 실물 사진 — 은 README 체크리스트). 테스트 151 passed·1 skipped(캡처 인자 추가 뒤).

## 26. 상태 보드 단순화 — 첫 화면은 "상태 · 원인 · 조치" (3단 정보 구조, 2026-10-26)

- **무엇**: `#/status` 기본 화면을 `SimpleView.tsx`(영웅·왜?·무엇을?·신호 칩·흐름)로 바꾸고, 기존 화면은 헤더 토글 **전문가**로 유지(삭제 없음, 세션 안에서만 기억). 2층 = 하단 칩 → 시트(임계값 기준표 + "쉬운 설명" 열·사양·용어), 3층 = `시뮬레이션 추정값 · 근거 보기 ›` → `EvidenceDrawer.tsx`(정직성 4줄·해석 근거 비교(시뮬값 행만 기본)·근거 사슬·한계). 발표 모드(F)는 영웅·원인조치·흐름만 + 글자 1.25배, 숫자 키 1~5 = 장면 칩.
- **쉬운 말 사전** `public/content/status/labels_plain.yaml`(signals/replace/notes/thresholds_easy, 런타임 로드) — 역상 전류비 I₂/I₁ → 전류 불균형, kurtosis → 충격성(첨도), 히스테리시스·지속 → "3초 이상 지속될 때만 경보가 올라갑니다"(초 수는 config), 참고·임시 기준 → 임시 태그. 본문 치환은 `<abbr title>` 로 원문 보존. 옛 라벨("1톤"·"권상 7 m/min") 제거 → `현대 SSEN HLP-2.2/4 · 2.2 kW 4극 · 해석 기준 모터`.
- **export 필드 추가만** (`export_status_data.py`, 값은 `engine.CurrentModel` 그대로): `i2i1_fault`·`i2_over_in`·`i_f_A`·`p_loop_total_W`·`winding_dT_C`·`extras_note`. HEAD 스크립트를 임시 폴더로 실행해 diff — 기존 필드 변화 0. 서랍 비교표 시뮬값 행 5 + 판정 1 (4턴: 결함분 +0.31 %, I₂/I_n +0.22 %, I_f +0.10 %, P_loop +0.36 %). 전문가 보기 비교 패널에도 같은 값.
- **검수**: 첫 화면 표 0·게이지 0·섹션 4, I₂/I₁ 영웅 1곳(+추세; 신호 띠는 `↖ 위`), 전기 모드 온도 칩 대신 "이 모드에서는 계산하지 않음", 옛 라벨 grep 0, `npm run build`(tsc) 통과, 테스트 151 passed·1 skipped, 1920×1080/1366×768·다크/라이트·전후 비교 스크린샷(`docs/dashboard_simple_view/img/`, `tools/simple_view_shots.mjs`). 문서 `docs/dashboard_simple_view.md`.
- **한계**: 전기 모드 `winding_dT_C` null(열 모델 미실행), 조치 문장의 현장 용어(서지·절연저항)는 그대로, 해설 화면 22 kW 영상은 범위 밖. 다음: 미디어 팩 대시보드 사진·영상을 단순 보기로 다시 캡처.
- **미디어 팩 2차(같은 날)**: 단순 보기 기준으로 대시보드 사진 12장(첫 화면·툴팁 오버레이 2·12턴·정상·근거 서랍 2·임계값 시트·기계 베어링·전문가 보기·임시 태그·CSV 내보내기)과 영상 2편(07 워크스루 60 s: 정상→4턴→12턴→서랍→시트→전문가↔단순, 08 side-by-side: Isaac 30.0 s ↔ 보드 0:29) 재캡처. 22 kW 정직성 문구는 근거 서랍·전문가 보기 4장에만 보임(index.md 표시). 캡처 스크립트는 사진마다 새 문서로 열어야 ?t/?drawer/?tab 이 적용된다(해시만 바꾸면 보드가 다시 읽지 않음 — 실측).
- **§1b 비주얼 우선 재구성(같은 날)**: 첫 화면을 상태 띠(72 px) + 그림 타일 2×2 + 하단 띠(왜/무엇을/근거 ›)로 교체. ① 모터 열·결함 지도(측단면 SVG, 영상과 같은 열 컬러맵, 전기 모드는 회색 + "온도 미계산", 단락 코일은 P_loop 비례 발광 점, 기계 모드 결함 베어링 맥동) ② 3상 전류 파형(최근 2주기 2 kHz, 결함상 굵게, 정격 진폭 점선, 큰 숫자 = 결함상 r) ③ 전류 성분(I₁·I₂·I₀ 막대, I₂ 위 큰 숫자 I₂/I₁, 눈금 0.05·0.10) ④ 추세(임계 띠·주입 시각 세로선·장면 띠). 기계 모드는 ②③ 이 진동 막대·베어링 충격성/고주파 막대. export 필드 추가 `case_signals`(케이스별 I₁·I₂·I₀ RMS + 파형 — engine.symmetrical_components / CurrentModel.waveform 그대로; 기존 필드 변화 0, extras_note 에 설명 키만 추가). 신호 띠는 제거(§1 → §1b). 실측 버그: 12턴 장면에서 원인 성분 "-" 를 상 이름으로 써 toFixed 예외 → 전류 비율 원인일 때만 상 이름 사용.
- **미디어 팩 3차 + 경로 정리(같은 날 저녁)**: §1b 타일 화면으로 대시보드 사진 12장·워크스루·side-by-side 재캡처(동기 녹화는 다른 창이 덮여 두 번 재녹화 — 녹화 중 PC 사용 금지). 사용자가 바탕화면을 정리해 Maxwell 저장소·미디어팩 사본·엑셀 사본이 `바탕 화면\모터\` 아래로 이동 → 도구 기본 경로를 `_maxwell_root()`(MAXWELL_ROOT → 옛 경로 → 모터/) 로, 테스트(`test_lut_source`·`test_desktop_copy_exists`)도 같은 규칙(없으면 skip), 미디어팩 바탕화면 사본은 옮겨진 폴더에 동기화. 테스트 151 passed·1 skipped.
