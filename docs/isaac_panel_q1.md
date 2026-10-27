# 아이작심 컨트롤 패널 Q1 — 전기 결함 전용 · 모드 제거 · 실시간 수동 조작 (2026-10-27)

브랜치 `feat/isaac-panel-q1`. 목표: 아이작심 창 안의 옛 "VIGENT - Control" 패널에서 **모드(electrical/mechanical/integrated) 항목을 없애고**, 전기 결함 변수 4개(결함 상/코일 · 단락 턴수 · 접촉 저항 · 전압 불평형)를
시뮬 실행 중에 바꾸면 다음 스텝부터 코일 발광·판정·대시보드가 바로 바뀌게 한다. 대시보드는 받아서 표시만 한다.

## §2 사전 조사 — 모드 제거 안전성 (맨 앞)

조사 범위: `motor_dt_viz/{app,ui,viz,engine,tools,tests,config}` + `dashboard/{src,tools,tests,public/content}` (저장소 안의 옛 프로토타입 `.venv`·`_backup_*`·`_legacy`·`_retired`·생성물 제외).
`grep -rn -i "mechanical\|integrated"` 50 파일 220 줄 (원본 `docs/isaac_panel_q1/measure/mech_grep.txt`), `mode` 는 526 줄(`mode_grep.txt`).

| 파일 | 줄(건수) | 용도 | 처리 |
|---|---|---|---|
| `motor_dt_viz/app/demo_integrated.py` | 2,9,10,32,41,42… (30) | 분기·UI 선택·payload·로그 | UI 선택 제거, MODE 고정, 분기 _legacy 로 (demo_integrated_modes.py) |
| `motor_dt_viz/ui/control_panel.py` | 22,23,24,26,56,120… (9) | UI 선택(옛 패널) | _legacy/ui 로 이동 — 새 패널 fault_control_window.py |
| `motor_dt_viz/viz/hud.py` | 181,182,184,185 (4) | 분기(HUD 섹션) | set_mode 전기 전용으로 단순화 |
| `motor_dt_viz/viz/m1_model.py` | 4,169 (2) | 주석(온도 입력 설명) | update(mode) → thermal_on 플래그 |
| `motor_dt_viz/engine/scenario_player.py` | 67,69,123,145 (4) | 시나리오 파일 선택(for_mode)·프레임 mode 필드 | 유지 — 배치(run_fleet)·테스트가 기계 시나리오를 돌린다(엔진, 수정 금지 범위) |
| `motor_dt_viz/tools/compare_demo_logs.py` | 4,23,45 (3) | 로그 비교 --mode | 유지(tools) |
| `motor_dt_viz/tools/electrical/verify_lut_integration.py` | 11,205,230,250 (4) | V7 라이브 실행 명령 문자열 | 유지(--mode electrical) |
| `motor_dt_viz/tools/fleet_compare.py` | 73,76,87 (3) | 배치 비교 | 유지 |
| `motor_dt_viz/tools/fleet_summary.py` | 70,94,95,124,153 (5) | 배치 요약 | 유지 |
| `motor_dt_viz/tools/live_demo_drive.py` | 7 (1) | 주석(통합 모드 데모) | 유지(이력 주석) |
| `motor_dt_viz/tools/media/capture_all.py` | 70,87,92,97,98,106… (16) | 미디어 팩 모드별 캡처 계획 | 유지(tools) — 기계·통합 영상은 _legacy 데모로만 재현(문서 표기) |
| `motor_dt_viz/tools/r0_proto/ws_proto_server.py` | 3 (1) | (미분류) | 확인 |
| `motor_dt_viz/tools/run_fleet.py` | 4,8,65,67,112,135 (6) | 배치 엔진 모드 루프 | 유지 — index.json·검증 입력(Isaac 아님) |
| `motor_dt_viz/tools/split_clips.py` | 10,30,62 (3) | 영상 분할 --mode | 유지(tools, 이력) |
| `motor_dt_viz/tools/verify/build_analysis_reference.py` | 216 (1) | mechanical_note 문구 | 유지(해석 근거 JSON 필드) |
| `motor_dt_viz/tools/verify/hud_composite.py` | 6 (1) | 주석 | 유지 |
| `motor_dt_viz/tools/verify/scenario_itsc_12turn_thermal.yaml` | 5,7,8 (3) | 검증 시나리오(통합) | 유지 — 재현은 _legacy 데모 |
| `motor_dt_viz/tools/verify/scenario_itsc_16turn_thermal.yaml` | 5,7,8 (3) | 검증 시나리오(통합) | 유지 — 재현은 _legacy 데모 |
| `motor_dt_viz/tools/verify/scenario_itsc_4turn_thermal.yaml` | 5,7,8 (3) | 검증 시나리오(통합) | 유지 — 재현은 _legacy 데모(문서 표기) |
| `motor_dt_viz/tools/verify/sim_vs_analysis.py` | 225 (1) | 열 검증 로그 라벨 | 유지(기존 로그 대조) |
| `motor_dt_viz/tools/verify/write_report.py` | 38 (1) | (미분류) | 확인 |
| `motor_dt_viz/tools/viz/shot_with_hud.py` | 3,7,35,46,75,78… (9) | HUD 합성 모드 분기 | 유지(tools) — 기계 분기는 _legacy 데모 필요(문서 표기) |
| `motor_dt_viz/tests/test_dashboard_fleet_export.py` | 26 (1) | 테스트(export 모드별) | 유지 |
| `motor_dt_viz/tests/test_fleet.py` | 65,67,91,102 (4) | 테스트(배치) | 유지 |
| `motor_dt_viz/tests/test_live_bridge.py` | 66,155,156,159,160 (5) | 테스트(payload mode 값·restart_args) | 유지 — payload 필드 유지 |
| `motor_dt_viz/tests/test_scenario.py` | 124,131,133,136,149,166 (6) | 테스트(시나리오 모드별) | 유지 — 엔진·config 테스트 |
| `motor_dt_viz/tests/test_verify_tools.py` | 95,112 (2) | 테스트(검증 도구) | 유지 |
| `motor_dt_viz/config/live.yaml` | 1,26 (2) | 허용 명령 set_mode 목록 | 유지(config) — 앱이 electrical 외는 거부 ack |
| `motor_dt_viz/config/render_demo.yaml` | 1 (1) | (미분류) | 확인 |
| `motor_dt_viz/config/scenario.yaml` | 20,31,42,53,64,72 (6) | 통합 시나리오 config | 유지 — 배치·테스트 전용 |
| `motor_dt_viz/config/scenarios_M1.yaml` | 3,182,185,199,211,223… (18) | 시나리오 모드 절(mechanical/integrated) | 유지(config) — 전기 절만 로드 |
| `motor_dt_viz/config/scenario_mechanical.yaml` | 1,31,44,57,70,83… (9) | 기계 시나리오 config | 유지 — 배치 전용 |
| `motor_dt_viz/config/status_demo.yaml` | 13 (1) | scene_map 기계 칩 | 유지(상태 보드 export 입력) — 레이아웃 A 는 쓰지 않음 |
| `dashboard/src/App.tsx` | 3 (1) | 주석 | 유지 |
| `dashboard/src/data.ts` | 4,28 (2) | Mode 타입·주석 | 유지 — index.json 스키마(scenarios.mechanical 키) |
| `dashboard/src/live/feed.ts` | 33 (1) | payload 필드 타입 | 유지 — 필드 삭제 금지(값은 electrical) |
| `dashboard/src/live/livedata.ts` | 25,60,82,103,109,146… (7) | payload→Mode 변환·기계 변환 | 기계 변환(toMechData 등)은 _legacy/live/livedata_full.ts, pageMode 만 유지 |
| `dashboard/src/live/session.ts` | 7 (1) | 주석 | 유지 |
| `dashboard/src/live/types.ts` | 6 (1) | Mode 타입 | 유지(스키마) |
| `dashboard/src/mech/data.ts` | 1,35,44,45,46,47… (9) | 기계 해설 데이터 로더 | _legacy/mech 로 이동 |
| `dashboard/src/state/playback.ts` | 61 (1) | 주석(#/mechanical) | _legacy 로 이동(state_playback.ts) |
| `dashboard/src/status/AnalysisRef.tsx` | 33,110 (2) | analysis_reference.json 의 mechanical_note 필드 | 유지(스키마) |
| `dashboard/src/status/data.ts` | 124,129 (2) | narration 로더(기계 narration 포함) | 유지 — StatusContent.narration 스키마(Record<Mode>) |
| `dashboard/tools/export_dashboard_data.py` | 9,227,322,366,373,376… (8) | export --mode | 유지(배치 export) |
| `dashboard/tools/export_mechanical_extras.py` | 2,37,54,154 (4) | 기계 export | 유지(배치) |
| `dashboard/tools/export_status_data.py` | 41,164,207 (3) | export 모드 루프 | 유지 — index.json 생성 |
| `dashboard/tests/test_export.py` | 28,127,128 (3) | 테스트 | 유지 |
| `dashboard/tests/test_mechanical_extras.py` | 24,25,36 (3) | 테스트 | 유지 |
| `dashboard/tests/test_status_export.py` | 29,89,108 (3) | 테스트 | 유지 |
| `dashboard/public/content/mechanical/narration.yaml` | 5 (1) | 기계 해설 내용 | 유지(content) |

**원칙대로 처리한 것**
- UI 선택기만 제거: 옛 패널 `ui/control_panel.py` → `_legacy/ui/`, 새 패널 `ui/fault_control_window.py` 에는 모드 항목이 없다. 내부 상수 `MODE = "electrical"`(`ui/demo_state.py`).
- WebSocket 8765 payload 의 `mode` 필드는 그대로(값 `"electrical"` 고정). hello·state 스키마는 **필드 추가만**(`control_source`·`manual_fault`·`persistence`). 대시보드 `feed.ts` 타입도 필드 유지.
- `--mode` 인자는 유지하되 `electrical` 외 값이면 `[demo] WARNING … forcing electrical` 로그 뒤 강제. 도움말에 전기 전용 명시. `--switch_seq` 는 무시(로그).
- 기계/통합 분기 코드: 패치 전 `app/demo_integrated.py` 전체를 `_legacy/app/demo_integrated_modes.py` 로 복사해 두고, 활성 파일에서 열 적분·베어링 투시·HUD 열/진동·모드 전환·기계 샷 플랜을 제거. `viz/hud.set_mode` 는 전기 섹션만, `viz/m1_model.update(mode)` → `thermal_on` 플래그.
- 대시보드: `src/mech/data.ts`·`src/elec/data.ts`·`live/captions.ts`·`state/playback.ts`·`live/livedata.ts(전체본)` → `src/_legacy/`, 활성 `live/livedata.ts` 는 `liveSteps`·`toMotorSeries` 만.
- **잔여 참조(의도적 유지)**: Isaac 런타임 경로(`app/ui/viz`)에서 `mechanical|integrated` 문자열은 0건(파일명 `demo_integrated.py` 자체는 이력 호환으로 유지). 남는 곳은 ① 배치 엔진·export·테스트(`run_fleet`·`export_*`·`tests/*` — index.json·검증 입력, Isaac 아님) ② config(시나리오 파일·`live.yaml set_mode` 허용 목록 — 앱이 거부 ack) ③ 스키마 타입(`Mode`, `scenarios.mechanical` 키, `mechanical_note`) ④ 주석. 전부 위 표에 처리 열로 적었다.
- `set_mode` 명령은 `electrical` 이면 ok(no-op), 그 외 `ok:false "electrical-only build"`.
- 검증: `sim_vs_analysis` 재실행 **PASS 89/89** (기존 통합 모드 verify 로그 대조 — 로그는 그대로), pytest **157 passed · 1 skipped**, 기존 M1 로그 재생(export 테스트 `test_dashboard_fleet_export`·`test_status_export`) 통과.

## §3 패널 Q1 — `motor_dt_viz/ui/fault_control_window.py` + `app/fault_controller.py`

**한글 글리프 실측(`tools/live/ui_font_probe.py`)**: Isaac Sim 4.5 omni.ui 는 기본 폰트·`style font`·`--/app/font/file=malgun.ttf` 어느 것도 한글을 그리지 못한다(`??`). 그래서 라벨은 **PIL 로 맑은 고딕 비트맵(PNG)을 그려 `ui.Image` 로** 띄운다(`ui/ko_text.KoLabel`, 값이 바뀔 때만 다시 그림).
위젯 **안의** 글자(ComboBox 항목·창 제목)는 Kit 폰트라 ASCII(`R phase - Coil_01`, `0.1 (metal)`, `none / config case (fixed)`, 창 제목 `VIGENT - Electrical Fault Control`)이고 버튼은 한글 이미지 버튼(적용·정상으로·반투명·절단·권선만). 함정: 컨테이너 `style={"margin": n}` 을 주면 `ui.Image` 가 1/4 로 축소된다(실측, 1차 스크린샷 `img/panel_v1_tiny_labels.png`) — 여백은 Spacer 로.

### 구성 (위에서 아래, CollapsableFrame)
1. 헤더 `VIGENT 전기 결함 조작` + 우측 `● 실시간`(스트림 클라이언트 ≥ 1 초록 / 0 회색), 안내줄 `모드 항목 삭제됨 — 전기 결함 고정`(`--no_panel_notice` 로 숨김).
2. **결함 주입**: 결함 상/코일 ComboBox(상 표시는 config `phase_labels` R·S·T, 코일 이름은 USD 스테이지의 `prim_map_M1.yaml` 권선 그룹에서 읽음 — 기본 `R - Coil_01 / S - Coil_07 / T - Coil_04`) · 단락 턴수 IntSlider 0~**32**(LUT 격자 최대 turn_ratio 16.7 % × N_ph 192, `n / 32 턴`) · 접촉 저항 ComboBox(LUT 격자 값 `0.03 / 0.1 (metal) / 0.3 / 1.0`) · 전압 불평형 ComboBox(`none / config case (fixed)`) · 체크 `슬라이더를 놓으면 바로 적용`(기본 ON, 슬라이더 release = `add_end_edit_fn`) · **[적용]**(주황) **[정상으로]**(회색).
3. **실시간 판정(읽기 전용, 0.5 s)**: 전류 불균형 I₂/I₁ · 단락 전류 I_f · 발열 P_loop · 판정(안전/경고/위험 색) · 지속 카운터 `x.x / 3.0 s` · 운전 부하 `xx %` · 조작 주체(수동/시나리오) · 각주 `해석표(LUT v2) 기준 · 대시보드로 송신 중 (n 클라이언트)`. 전부 엔진 state_dict 값(지속 시계는 Judge 내부 `_since` 노출, 계산 없음).
4. **보기**: 반투명 / 절단 / 권선만 (`M1Model.set_view` 기존 variant).
5. **화면 송출 설정**(접힘): 포트(읽기 전용) · 해상도 1280×720/960×540 · JPEG 품질 60~90 — `ViewportStreamer.size/quality` 런타임만, `config/live.yaml` 에 쓰지 않음.

### 데이터 흐름
```
패널 위젯 ──write()──▶ /World/VigentFaultController (Xform, 기하 없음)  custom 속성 + 문서 문자열
                        vigent:faultPhase(token A|B|C) · vigent:faultCoil(string) · vigent:faultTurns(int) · vigent:contactResistance(float Ω) · vigent:voltageUnbalance(float)
     매 프레임 ──poll()(2 Hz 제한, 마지막 값 보장)──▶ apply(): 시나리오와 같은 길 = DemoState.electrical_case
                        turns>0 → 런타임 케이스 "manual_itsc" (electrical.yaml itsc_4turn 템플릿 복사 + lut{turns,R_f_ohm} + load — M1Model.register_runtime_case, extra_cases 와 같은 식)
                        turns=0 & unbalance>0 → config "voltage_unbalance" 케이스 / 둘 다 0 → "healthy"
     ──▶ 엔진 CurrentModel(lut 보간) ──▶ state(판정·I₂/I₁·I_f·P_loop) ──▶ Coil 발광(M1Model.set_short_coil) · WebSocket 8765 · 스트림 8766
```
- 결함 상 B/C: 엔진 파형의 상 순서를 `np.roll` 로 돌린다(대칭 성분 크기 불변, 새 수치 없음). state 의 파형·상별 RMS·판정 원인 상도 같이 돈다. 코일 발광은 선택 코일 프림에 단락 재질(`winding_short`)을 묶고 `Coil_01_short` 껍질은 숨긴다. 한 번에 한 코일.
- 시나리오 재생 중 패널을 만지면 `player.stop()` → `control_source: "manual"`. 대시보드 시나리오 ▾(`play_scenario`)·`inject_fault`·`reset` 은 `mark_scenario()` 로 수동 사양을 정상으로 되돌리고 `"scenario"`.
- [정상으로] = 턴 0 · 불평형 0 → `healthy` 케이스 → Judge 는 기존 persistence 경로(저전류 규칙 2cd8914 포함) 그대로 시계를 돌린다(별도 리셋 호출 없음 — 지속 카운터는 값이 정상이 되면 자연히 0).
- 시작 시 속성은 항상 정상으로 초기화(USD 에 저장돼 있어도).
- 단축키(선택 항목)는 **미완** — 시간 배분상 생략.

## §5 검증
| 항목 | 결과 | 근거 |
|---|---|---|
| 패널 턴수 0→4→12→0, 속성 변경 → 코일 glow → state 송신 지연 | **10회×3 (30건)**: 속성→적용 p50 0.8 ms · 속성→glow(머티리얼 emissive 갱신) **p50 7.3 / p95 9.4 / max 11.8 ms** · 속성→새 케이스 state 송신(대시보드 상태 띠가 받는 값) **p50 49.8 / p95 77.5 / max 102.3 ms** (목표 ≤ 300 ms). 느린 2차(hold 45 s, 6건) p50 62 / p95 65 ms | `measure/panel_selftest_10x.json`, `panel_selftest_hold45_2x.json` (`--panel_selftest`, 패널과 같은 USD 속성 경로) |
| 판정 등급 변화 | 값은 첫 state 부터 바뀌고(위 지연), 등급(경고/위험)은 config 지속 규칙 3 s 뒤 — 계산 변경 없음 | 패널 지속 카운터 `x.x / 3.0 s` |
| 패널 값 vs 대시보드 vs 엔진 state 3자 일치 | 정상 `0.027 / 0.027 / 0.027`, 4턴 `0.0726 / 0.073 / 0.0726` · I_f 34.4 A · R 5.22 A, 12턴 `0.2696 / 0.270 / 0.2696` · I_f 69.8 A · R 7.40 A — 턴수·R_f 0.1 Ω·R상 Coil_01 동일 | `img/isaac_{healthy,4turn,12turn}.png` · `img/dash_{healthy,4turn,12turn}.png` · `measure/state_{healthy,4turn,12turn}.json` |
| 시나리오 재생 중 패널 조작 → 수동 | 로그: `[live] play_scenario {'scene': 2} → ok` 직후 패널 쓰기 `apply #12 … manual_itsc` → state `control_source: manual`, 대시보드 시나리오 칸 "수동 조작 (아이작심 패널)" | `measure/state_12turn.json`, 대시보드 사진 |
| 시나리오 재선택 → 복귀 | `play_scenario 2` 뒤 4 s state: `control_source: scenario`, case `itsc_4turn`, 수동 사양은 속성에서도 정상으로 | `measure/state_after_play_scenario.json` |
| 2 Hz 제한 | 3 s 동안 **144회** 쓰기 → 적용 **7회**(≈2.3 Hz), 병합 132회, 마지막 값(2턴) 반영, 마지막 쓰기→적용 80 ms | `measure/panel_burst.json` (`--panel_burst`) |
| `sim_vs_analysis` | **PASS 89/89** (기존 통합 모드 verify 로그 대조, 재실행) | `docs/verification/sim_vs_analysis.md` |
| pytest | **157 passed · 1 skipped** | `py -3.12 -X utf8 -m pytest tests -q` |
| `npm run build`(tsc) | 통과 | dashboard |
| 금지 파일 diff | `thresholds.yaml`·`electrical.yaml`·`motors/*`·LUT·`engine/` **diff 0** (`git diff --stat HEAD -- …` 빈 출력) | |
| 모드 제거 후 참조 | Isaac 런타임(`app/ui/viz`) 0건(파일명 제외), 나머지는 §2 표(배치·config·스키마·테스트·주석) | `measure/mech_grep.txt` |
| 기존 M1 로그 재생 | export·상태 보드 테스트(`test_dashboard_fleet_export`·`test_status_export`) 통과, index.json 재생성 불필요 | pytest |
| hello/state 스키마 | 필드 추가만: state `control_source`·`manual_fault`·`persistence`, `Ia/Ib/Ic_rms` 정밀도 0.1→0.01 A(송신부) | `src/live/feed.ts` |
| Isaac FPS (패널 열림 + 스트림 1 클라이언트) | **p50 41.9 (min 41.3)** ≥ 30 · 스트림 30.0 fps · 지연 p50 33 ms | `measure/probe_30s_panel_open.json` |
| 라이브 vs V1 7 시나리오 (선전류 0.01 A) | 선전류 겉보기 편차 **≤ 0.094 %**(이전 0.1 A 반올림 때 1.3 %), I₂/I₁·I₂/I_n·I_f·P_loop ≤ 0.13 %, 판정 7/7, 전환 93~207 ms — 전부 PASS | `docs/dashboard_layout_a/v1_compare.md` |

스크린샷: 패널 3장 `img/isaac_{healthy,4turn,12turn}.png`(창 전체 — 패널·뷰포트 코일 발광·HUD 가 한 화면), 대시보드 3장 `img/dash_*.png`. 1차 패널(비트맵 축소 함정) `img/panel_v1_tiny_labels.png`, 글리프 실측 `img/font_probe_*.png`.

## 판단 사항·한계
- **U/V/W 대신 R·S·T**: 명세의 `U상 — 코일 01` 표기 대신 config `electrical.yaml phase_labels`(R·S·T, 2026-09 결정)를 썼다 — 대시보드·HUD·로그와 같은 이름이어야 해서. USD 속성 `vigent:faultPhase` 는 내부 키 A|B|C.
- **코일 번호**: 명세 예시(01·09·17) 대신 USD 스테이지의 상별 첫 코일(R Coil_01 · S Coil_07 · T Coil_04, `prim_map_M1.yaml` 권선 그룹 = datasheet 권선표)을 읽는다(하드코딩 금지). 콤보 항목은 상별 1개씩(한 번에 한 코일).
- **단락 턴수 0~32**: LUT 격자 최대(turn_ratio 16.7 % × N_ph 192 = 32턴)와 같다. 16턴 이상은 격자 끝 보간값(외삽 없음), `electrical_source.clamped` 로 표시.
- **전압 불평형**: 가변 % 는 phase_scale 을 새로 만드는 식이 필요해 금지 규칙에 걸린다 → config `voltage_unbalance` 케이스(고정) 켜기/끄기만. 속성은 float(0 = 없음). ITSC 와 동시 적용 불가(엔진 케이스 1개) — 턴수 > 0 이 우선.
- **결함 상 B/C**: 엔진은 결함을 내부 A상에 두므로, 파형의 상 순서를 `np.roll` 로 돌려 표현했다(새 수치 없음·대칭 성분 크기 불변). 엔진 수정 없이 가능한 유일한 방법 — 판단 사항.
- **한글**: omni.ui 글리프 한계로 위젯 안 글자(콤보 항목·창 제목)는 ASCII, 설명·값·버튼은 한글 비트맵. `style={"margin"}` 을 쓰면 비트맵이 축소되는 함정은 CLAUDE.md 에 기록.
- **단축키**(선택 항목) 미완 — 시간 배분. 발표 때 필요하면 `[`/`]`·U/V/W·R·0·H 를 `ui/fault_control_window.py` 에 추가하면 된다(뷰포트 포커스 조건 포함).
- 시작 시 첫 프레임이 속성을 '적용'으로 세어 자동 재생 시나리오를 멈추던 버그를 1차 실행에서 발견해 고쳤다(기준값을 생성 시점에 기록).
- 지속 카운터는 Judge 내부 시계(`_since`)를 읽어 보여준다(계산 없음). 값이 정상으로 돌아가면 0 이 되고, [정상으로] 는 별도 리셋 없이 같은 경로를 탄다.
- 로그 재생·export·배치는 기계 모드를 계속 지원한다(엔진·config 불변). 통합 열 검증 로그를 새로 만들 때는 `_legacy/app/demo_integrated_modes.py` 가 필요하다(REPRODUCE.md 표기).
