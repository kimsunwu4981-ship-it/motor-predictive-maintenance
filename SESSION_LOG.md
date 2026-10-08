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

## 16. AI Hub 전체 진동 데이터 — 다운로드·선별·변환 (2026-10-08 저녁, 진행 중)

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
- `features --workers 4`(ProcessPoolExecutor, 샘플 검증 4.8 ms/파일) 추가. 22:45 `sample` → `features` 시작.
