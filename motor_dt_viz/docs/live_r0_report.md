# R0 — 실시간(라이브) 연동 현황 파악 (코드 수정 전)

지시서 `TASK: Isaac Sim 실시간 연동 디지털 트윈 대시보드` §3. 사용자 확정 조건(2026-10-09): 10장(5.1 마이그레이션) 제외, **이 데스크탑(RTX 3070 Ti 8 GB)에서 Isaac Sim + 맥북(같은 Wi-Fi)에서 대시보드**,
WebSocket·대시보드 서버 **0.0.0.0** 바인드, 윈도우 방화벽 인바운드 규칙 절차 README, 데스크탑 IP 를 HUD 에 표시, 렌더 프리셋 1280×720 RTX Real-Time.
이 문서의 숫자는 전부 프로토타입 실측(`docs/live_r0/<케이스>/` 에 요약 JSON·성능 샘플 사본, 원본은 `logs/r0_proto_*`)·기존 로그·config 에서 왔다. 앱·엔진·대시보드 코드는 바꾸지 않았다(프로토타입 스크립트는 `tools/r0_proto/`, 기존 데모를 `runpy` 로 감싸 실행).

## 1. 대시보드 데이터 소스 추상화 — 현황과 리팩터링 범위

| 화면 | 시간 소스 | 데이터 소스 | 추상화 |
|---|---|---|---|
| `#/status` 상태 보드 | `useClockPlayback`(벽시계, 영상 없음) | `src/status/source.ts` **`StatusSource` 인터페이스** — `ReplaySource`(logs/fleet JSON) 동작, `LiveSource`(HTTP+SSE 계약) 자리만 | **있음** (P5 에서 미리 만듦). `appendSample()` 로 시계열 끝에 샘플을 붙이는 경로까지 있음 |
| `#/mechanical`, `#/electrical` (+presenter) | `usePlaybackController` — **영상 `currentTime` 이 단일 시간 소스** (`t_real = video.currentTime − video_offset_s`) | `loadModeData()` 가 `public/data/<mode>/{timeseries,scenarios,thresholds,faults}.json` 을 통째로 읽고, 패널은 `timeseries` 에서 `idx(ts, t)` 로 값을 뽑음 (`liveValues(data, t)`) | **없음**. 데이터는 "완성된 시계열 + 시각 t" 모델. 사건 자막은 export 가 로그에서 미리 만든 `events.json`, 장면 해설 공개는 `reveal_timing`(장면 진행률) |

리팩터링 범위(R2 에서 할 것, 녹화 모드 동일 동작 보장):
1. `src/state/source.ts`(신규, 상태 보드의 `StatusSource` 를 일반화): `DataSource { kind, loadMode(mode) → ModeData, subscribe?(onState) }`. `RecordedSource` = 지금의 `loadModeData` + `usePlaybackController`. `LiveSource` = WebSocket 수신 → **같은 `Timeseries` 모양의 성장하는 버퍼**(최근 N 초, config) + 벽시계 재생기(`useClockPlayback` 재사용, t = 버퍼 끝).
2. 패널은 그대로: `idx(ts, t)` 가 버퍼 끝을 가리키면 라이브다. `events.json` 대신 라이브에서는 **state 의 `status`·stage 변화**를 감지해 사건을 만든다(`captions.ts buildClusters` 입력만 바꿈). 장면 해설은 `narration_key`(§5) 로 직접 고른다.
3. `VideoPanel` 은 소스가 라이브면 안내 문구/스냅샷으로 교체(§6 영상 영역 옵션). 재생 바는 "최근 N 초" 창.
4. 상태 보드는 `StatusSource` 에 WebSocket 구현만 추가(`LiveSource` 를 SSE 계약에서 WebSocket 으로 바꿈). 판정 열(`status/cause/levels`)은 state 의 것을 그대로 넣는다(§5.2 한 곳 판정).
5. 녹화 모드 회귀 확인: 기존 테스트 63개 + `#/mechanical?t=`·`#/electrical?t=`·`#/status?m=&t=` 스크린샷 비교.

## 2. Isaac Sim 자동 재생 스크립트 — 메인 루프 구조 (`app/demo_integrated.py`)

- 루프: `while simulation_app.is_running()` 한 번 = 한 프레임. 순서: 실제 경과 시간 → 예약 모드 전환 → 패널 요청(`request_reset/play/mode_reset`) → 시나리오 진행(`player.advance`) → **전류**(`cm.analyze`) → **열**(`tm.step`) → 물리(관절 토크) → 머티리얼·경로·입자 → **HUD** → `world.render()` → 로깅(`LOG_PERIOD_S` 마다 CSV 1행 + `status.json`).
- **state 는 한 dict 로 모이지 않는다.** 프레임마다 `state`(DemoState: mode/load/time_scale/slowmo/thermal_faults/electrical_case/playing_scenario), `th`(ThermalState: temperature_C/stage/vibration_mms), `st_line`(전류: rms_A/i2_over_i1), `frame`(시나리오 스텝), `zone`, `fps` 가 지역 변수로 흩어져 있고 로깅 블록에서만 한 행으로 합친다 → R1 에서 **로깅 블록 바로 앞에 `state_dict = {...}` 를 만들어 CSV 로깅과 LiveBridge 큐가 같은 dict 를 쓰게** 한다(컬럼 이름 동일 보장).
- **런타임 변경 가능**: 결함 주입(`state.thermal_faults` 목록, `ControlPanel._toggle_fault` 와 같은 경로), 전기 케이스(`state.electrical_case`), 부하(`state.load` 0~1.5), 배속(`state.time_scale` 1~600), 슬로모션, 모드 전환(`request_mode_reset` — 잔상 제거 포함), 리셋, 시나리오 재생 시작. 모두 `DemoState` 필드만 바꾸면 다음 프레임에 반영되므로 **명령 큐 → DemoState 적용**은 그대로 얹힌다. 시나리오 재생 중에는 매 프레임 `frame` 이 state 를 덮어쓰므로 명령은 재생을 멈추거나(`playing_scenario=False`) 재생 중엔 거부해야 한다.
- **모터 전환은 런타임 불가**: `MOTOR = ml.load_motor(args.motor)` 는 기동 시 한 번, 열회로(`tm`)·전류 모델(`cm`)·카메라 거리(`GEOM_SCALE`)·HUD 문구가 그 값으로 만들어진다. `select_motor` 명령은 **거부 + "재시작 필요"** ack(§5.3). 재시작 없이 하려면 tm/cm/카메라/HUD 재생성 경로를 새로 짜야 한다(R3 범위 밖, 선택).
- 판정 엔진(`engine/thresholds.py Judge`)은 **데모 루프에 아직 없다**(HUD 는 열 모델의 4단계 stage 색을 쓴다). R1 에서 루프에 `Judge(motor=MOTOR)` 를 두고 fleet 배치와 같은 신호(`temperature/current_ratio/i2i1/vibration/bearing_kurtosis/bearing_hf_ratio`)로 매 로깅 주기 판정 → `status` 로 송신. HUD 색은 지금처럼 stage, 상태 보드 색은 Judge — 어긋남을 막으려면 HUD 에도 Judge 종합 등급 한 줄을 추가한다(R1).
- 서버 스레드와 메인 루프의 통신: 송신은 `queue.Queue(maxsize=1)` 에 최신 dict 만(가득 차면 버리고 교체), 수신은 `queue.Queue()` 를 매 프레임 비운다. `omni.kit.async_engine` 은 이 Isaac 파이썬에서 import 되지 않았다 → **표준 `threading` + `asyncio` 루프**로 간다(§3 에서 검증).

## 3. WebSocket 프로토타입 (Isaac Sim 프로세스 안, 별도 스레드)

- Isaac Sim 4.5 파이썬(3.10.15): `websockets 12.0`, `aiohttp 3.9.4`, `psutil 5.9.8`, `tornado` **내장** — 설치 불필요. `pynvml` 없음(VRAM 은 `nvidia-smi` 또는 `carb` 통계).
- 프로토타입(스크래치 `ws_proto_server.py`, 저장소 밖): 서버 스레드(asyncio 루프, `websockets.serve(0.0.0.0:8765)`)가 10 Hz 로 `{"type":"state", n, t_wall, status: <demo 의 status.json>}` + 1 Hz heartbeat 를 보내고, 명령은 echo-ack. 그 뒤 **기존 `demo_integrated.py` 를 그대로 실행**(`runpy`, `--gui --autoplay --mode mechanical --max_s 90`). 클라이언트(`ws_client.py`, 다른 프로세스)가 60 s 동안 수신 주기·지연을 잰다.
- 결과: §3.1 표.

### 3.1 측정 (각 90 s, 기계 시나리오 자동 재생, GUI)

| 케이스 | 해상도 | 서버 | FPS 평균 / 중앙값 / 최소 (기동 5행 제외) | 클라이언트 수신 | VRAM 최대 (GPU 전체) | GPU 사용률 평균 |
|---|---|---|---|---|---|---|
| 기준 `r0_proto_base` | 1600×900 | 없음 | **86.5 / 89.3 / 36.3** | — | 3,071 MiB | 54 % |
| 서버 `r0_proto_ws` | 1600×900 | 스레드, 클라이언트 1 | **83.6 / 86.1 / 37.7** (−3.4 % 평균, −3.6 % 중앙값) | 60 s 동안 state 590건 = **9.82 Hz**, 간격 중앙 100.9 ms(최대 357), 지연 중앙 0.8 ms(최대 9.0), heartbeat 59건, ack 수신 | 3,073 MiB | 60 % |
| `--low`+서버 `r0_proto_low_ws` | **1280×720** | 스레드, 클라이언트 1 | **90.3 / 90.5 / 51.3** | state 592건 = 9.85 Hz, 간격 최대 238 ms, 지연 최대 16 ms | 2,922 MiB | 52 % |
| RAM 재측정 `r0_proto_ram` | 1600×900 | 스레드 | (50 s) | — | — | — |

- **FPS 저하 3~4 %** (완료 기준 10 % 이내 통과). 최소값 36~38 은 기동 직후 과도 구간(5행 제외 후에도 첫 장면 전환 때 한 번) — 전 케이스 동일.
- 서버 스레드의 asyncio 루프 지연(`sleep(0.1)` 초과분) 중앙 9.6 ms / 최대 9.8 ms → GIL 경합이 보이지만 10 Hz 유지. 메인 루프와 통신은 큐만 쓰면 된다.
- **RAM**: Isaac Sim(kit.exe) 워킹셋 최대 **5,132 MB**, 프라이빗 커밋 7,597 MB (PowerShell `Get-Process`, 5 s 샘플). RAM 64 GB(지시서 PC)·이 PC 모두 여유.
- **VRAM**: 1600×900 약 3.07 GB, 1280×720 약 2.92 GB (GPU 전체 사용량, 유휴 0.9 GB 포함) → 8 GB 카드에서 여유 5 GB. 1280×720 프리셋이 FPS·VRAM 모두 유리.
- 브라우저 접속: 서버는 `0.0.0.0:8765` 바인드. 같은 PC `ws://127.0.0.1:8765` 로 확인했고 LAN 주소는 `ws://172.30.1.37:8765` (맥북 접속은 방화벽 규칙 뒤 R1 에서 확인).
- 프로토타입 한계: payload 가 57 B(실제 state 1 KB 미포함 — demo 의 상태 파일이 `logs/demo_integrated_status.json` 에 쓰여 경로가 어긋남). 1 KB × 10 Hz 도 10 KB/s 라 결과는 같다고 본다. R1 에서 실측 다시.

## 4. 기준 성능 (변경 전)

- 기존 녹화 로그(2026-09-22, 1600×900): 기계 `demo_20260922_174529.csv` fps 중앙값 62.2 (p10 51.4), 전기 `demo_20260922_231908.csv` 62.4 (p10 57.4). 프로파일(SESSION_LOG 3장): render 8.9 ms / physics 2.6 ms / 앱 코드 2.1 ms.
- 이번 측정(§3.1 기준 행, 2026-10-09, RTX 3070 Ti 8 GB, 녹화 없음): **FPS 86.5 평균, VRAM 3.07 GB(GPU 전체, 유휴 0.9 GB 포함), Isaac 워킹셋 5.1 GB**. 9-22 로그(62 fps)는 gdigrab 녹화 중 값이라 더 낮다.
- 네트워크: 데스크탑 유선 `172.30.1.37`(사설, 공유기 LAN). 맥북은 같은 공유기의 Wi-Fi 로 붙으면 같은 서브넷이다. 방화벽 인바운드 규칙은 **8765(WebSocket)·4173(대시보드)** 두 개(R1/R2 README).

## 5. 스트림 state 스키마 초안 (키 = 기존 CSV 컬럼)

기존 `demo_*.csv` 컬럼: `t_s, t_real_s, mode, step, case, faults, load, rpm, T_<node>×9, Ia_rms, Ib_rms, Ic_rms, i2_over_i1, vibration_mms, iso_zone, fps`.
fleet `status_fleet.csv`: `status, label, cause_signal, cause_component, value, threshold, temperature, current_ratio, i2i1, vibration, bearing_kurtosis, bearing_hf_ratio, bearing`.

```json
{
  "type": "state", "schema": 1,
  "t_s": 123.4, "t_real_s": 118.2, "t_session_s": 130.0, "t_wall": 1759900000.123,
  "motor_id": "M5", "mode": "mechanical", "step": "bearing_fault", "case": "healthy",
  "scene": {"n": 2, "id": "bearing_fault", "label": "DE 베어링 열화", "elapsed_s": 12.3, "duration_s": 25.0, "time_scale": 120, "playing": true},
  "faults": ["bearing_de_fault"], "load": 1.0, "time_scale": 120, "slowmo": 0.0167, "rpm": 1764.2,
  "T": {"winding": 92.3, "stator_core": 80.1, "rotor": 70.4, "shaft": 66.0, "bearing_de": 88.1, "bearing_nde": 61.0, "endshield_de": 58.2, "endshield_nde": 50.1, "frame": 47.9},
  "stage": {"bearing_de": "warning", "winding": "caution", "...": "normal"},
  "Ia_rms": 43.5, "Ib_rms": 43.7, "Ic_rms": 43.6, "i2_over_i1": 0.006, "rated_line_A": 43.7,
  "vibration_mms": 2.9, "iso_zone": "B",
  "bearing_kurtosis": 50.0, "bearing_hf_ratio": 9.0,
  "status": {"status": "WARN", "label": "경고", "cause_signal": "temperature", "cause_component": "bearing_de", "value": 88.1,
             "threshold": "안전 <70 / 경고 70~95 / 위험 ≥95 °C",
             "levels": {"temperature": "WARN", "current_ratio": "SAFE", "i2i1": "SAFE", "vibration": "WARN", "bearing_kurtosis": "DANGER", "bearing_hf_ratio": "DANGER", "bearing": "DANGER"}},
  "narration_key": {"mode": "mechanical", "scene": "bearing_fault", "reveal": "visible"},
  "perf": {"fps": 58.2, "vram_mb": 6100, "ram_mb": 5200},
  "host": {"ip": "172.30.1.37", "ws": "ws://172.30.1.37:8765", "clients": 1}
}
```

- `status` 블록은 `engine/thresholds.py Verdict.as_dict()` + fleet CSV 의 신호별 등급(`levels`, `bearing` 종합 포함)과 같은 이름이다. 대시보드는 라이브에서 판정하지 않는다(§5.2).
- `narration_key` 는 `narration.yaml` 의 장면 id + `reveal_timing` 을 Isaac 쪽에서 평가한 단계(`why/visible/result`). 수동 조작(시나리오 아님)이면 `scene: null` 이고 대시보드는 결함 토글에 맞는 해설(`faults.json` 의 결함 설명)을 쓴다.
- `T`/`stage` 는 CSV 의 `T_<node>` 와 같은 노드 키. 상태 보드 JSON(`temperature_C`)과의 이름 차이는 `LiveSource` 가 한 줄로 맞춘다(`T_` 접두 ↔ `temperature_C`).
- `perf.vram_mb` 는 `nvidia-smi` 호출 비용이 커서 1 Hz 이하로만 갱신(없으면 null).

### 5.3 명령 허용 목록 초안 (`config/live.yaml`, R1)

| name | args | 범위/제약 | 적용 |
|---|---|---|---|
| `inject_fault` | `fault` ∈ thermal.yaml faults 키(bearing_de_fault, bearing_nde_fault, misalignment, fan_failure, brake_drag, overload) 또는 전기 케이스(itsc_4turn, itsc_12turn, overload, voltage_unbalance, single_phasing, no_load), `on` | 시나리오 재생 중이면 거부("stop scenario first") | `state.thermal_faults` / `state.electrical_case` |
| `set_load` | `pct` 0~150 | 패널 슬라이더와 같은 범위 | `state.load = pct/100` |
| `set_time_scale` | `x` 1~600 | | `state.time_scale` |
| `set_slowmo` | `x` 1~240 | 전기 모드 | `state.slowmo = 1/x` |
| `set_mode` | `mode` ∈ mechanical/electrical/integrated | 잔상 제거 경로(`request_mode_reset`) | |
| `play_scenario` | `scene` n 또는 없음 | 처음부터 재생; 특정 장면은 `player` 가 장면 시작 시각으로 점프(가능 여부 R1 확인) | `request_play` |
| `stop_scenario` | — | | `playing_scenario=False` |
| `reset` | — | | `request_reset` |
| `select_motor` | `motor_id` | **거부, "재시작 필요: --motor M3"** | — |

## 6. R1 이후 계획에 반영할 결정 사항

- 서버 바인드 `0.0.0.0:8765`, 대시보드 `serve.cjs` 도 `0.0.0.0:4173`(지금은 호스트 미지정 = 전체 바인드지만 안내 문구가 localhost 뿐) → 콘솔·HUD 에 `ws://<IP>:8765`, `http://<IP>:4173/#/status?live=ws://<IP>:8765` 표시.
- 렌더 프리셋 `config/render_demo.yaml`: 1280×720(지금의 `--low` 와 같음), RTX Real-Time(`/rtx/rendermode = RaytracedLighting`), 뷰포트 1개, 물리 서브스텝 2, 입자 12/경로. `--preset demo` 한 줄.
- 방화벽: `netsh advfirewall firewall add rule name="VIGENT WS 8765" dir=in action=allow protocol=TCP localport=8765 profile=private` 와 4173 동일 — README 에 GUI 절차와 함께. 공용 프로필(카페 Wi-Fi)에서는 열지 않는다.
