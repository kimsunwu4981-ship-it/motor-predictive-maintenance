# R3 — 양방향 제어 패널 (L2) · 모터 전환 자동 재시작 · 데모 대본

지시서 §7 + 사용자 결정(2026-10-09): 모터 전환은 **자동 재시작** — `select_motor` 를 받으면 Isaac 이 현재 모터를 정리하고 새 모터로 재기동, 대시보드는 "모터 전환 중 (약 N초)" 띠 후 재접속 대기. 재시작 시간 실측 보고.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `config/live.yaml` | `select_motor: {runtime: restart, restart_eta_s, restart_timeout_s}`, `server.bind_retry_s`(재기동 인스턴스가 이전 포트 해제를 기다리는 시간) |
| `app/live_bridge.py` | 접속 직후 **`hello`**(허용 명령·범위·모터 목록·eta — 제어 패널의 단일 출처) 전송, `select_motor` 검증(라이브러리 모터만), 포트 재바인딩 재시도 |
| `app/demo_integrated.py` | `select_motor` → ack `{restart, motor_id, from, eta_s}` → HUD "RESTARTING -> M1" → 루프 종료 → 브리지 정지(포트 해제) → `restart_args()`(원 인자에서 `--motor/--autoplay/--max_s/--record/--switch_seq/--no_timecode` 제거 + `--motor <id>`)로 **kit.exe 재기동**(python.bat 환경 상속, 표준 출력은 `logs/live_restart_<id>.log`) → 앱 종료 |
| `dashboard/src/live/ControlPanel.tsx` | 서랍(K 키 · `☐ 제어 K` · `&ctl=1`): 결함 토글(모드별 열 결함 6 / 전류 케이스 6), 부하·배속·슬로모션 슬라이더(놓을 때 전송), 모드, 시나리오 재생·장면 번호·정지, 리셋, 모터 M1~M5. 버튼 상태는 state 로 확정, 거부는 "최근 명령" 토스트에 이유 |
| `session.ts`·`LiveToggle.tsx` | `hello` 보관, `restarting`(select_motor ack → 띠 "모터 전환 중 (M1, 약 60초) · 경과 n초", 새 모터 첫 state 오면 해제, 2×eta 지나면 일반 끊김) |
| `tools/live_restart_measure.py` | 전환 시간 실측 (ack → 끊김 → 재접속 → 새 모터 첫 state) |
| `tools/live_demo_drive.py`, `tools/record_live_demo.ps1`, `docs/live_demo_script.md` | 5단계 데모 자동 구동(--fast 리허설) · 데스크톱 녹화 · 대본 |

## 2. 모터 전환 시간 실측 (RTX 3070 Ti 8 GB, `--mode integrated --live`, 2026-10-09)

| 전환 | ack 까지 | ack→소켓 끊김 | ack→새 모터 첫 state | 재접속 시도 | 비고 |
|---|---|---|---|---|---|
| M5 → M1 | 9 ms | 0.33 s | **133.4 s** | 51회 | 다른 Isaac 인스턴스(사용자 8765, 5.7 GB)가 **동시에 떠 있는** 상태 — GPU·디스크 경합, 이전 인스턴스 FPS 50 |
| M1 → M3 | 14 ms | 0.34 s | **46.5 s** | 18회 | 같은 조건에서 두 번째 — 셰이더·확장 캐시가 따뜻함 |

- 끊김은 즉시(0.3 s)라 띠가 바로 뜬다. 재기동 시간의 대부분은 Isaac 기동(단독 기동 실측 48~55 s "port up")이다. **단독 실행 기준 약 45~60 s, Isaac 두 개 동시면 2 분 이상.** 발표 때는 Isaac 하나만 띄운다.
- `restart_eta_s` 는 60 으로 두었다(띠 문구). `restart_timeout_s` 120 — 넘으면 일반 끊김 띠로 바뀌고 재접속은 계속한다.
- 첫 시도 실패 기록: 콘솔 없이(DETACHED) 띄운 자식은 `sys.stderr` 가 None 이라 `SimulationApp` 의 `faulthandler.enable()` 에서 죽었다 → 표준 출력을 로그 파일로 넘겨 해결(`logs/live_restart_<id>.log`).

## 3. 기능 검증 (자동 구동 `live_demo_drive.py --fast`, 내 인스턴스 8766)

`tools/live_demo_drive.py ws://127.0.0.1:8766 --fast --motor2 M1` (대기 시간 1/6, 통합 모드 M5, 15:03). 모든 명령 ack ok, 거부 0건.

| 단계 | 명령 → ack | 몇 초 뒤 state |
|---|---|---|
| 2 DE 베어링 결함 | `inject_fault bearing_de_fault` → ok `thermal_faults=[bearing_de_fault]` | 8 s: **DANGER**, 원인 `bearing_kurtosis 50`, DE 베어링 121.3 °C(배속 120), 진동 4.8 mm/s |
| 3 턴간 단락 4턴 | `inject_fault itsc_4turn` → ok `electrical_case=itsc_4turn` | 5 s: DANGER, R상 57.8 A(132 %), I₂/I₁ 0.104 |
| 4 리셋 | `reset` → ok | 5 s: SAFE, DE 베어링 34.6 °C |
| 5 M1 전환 | `select_motor M1` → ok `{restart, eta 60}` → 끊김 → 재접속 | **M1 첫 state +47.2 s** (ack 기준) |
| 5' M1 에 같은 결함 | `inject_fault bearing_de_fault` → ok | 8 s: DANGER, DE 베어링 **71.6 °C** (M5 는 같은 시간에 121.3 °C — 작은 모터가 늦게 뜨거워진다) |

스크린샷: `docs/live_r3/ctl_status_fault.png`(상태 보드 + 제어 패널, hello 로 채워진 결함·모터 버튼, 리셋 직후), `ctl_mechanical.png`(기계 화면 + 패널, 전환 중), `ctl_status.png`(옛 인스턴스 — hello 없음 안내).
결함 토글 반응·Isaac 종료 폴백은 사용자가 맥북에서 별도 확인(2026-10-09 15시 전).

## 4. 데모 대본 · 녹화

`docs/live_demo_script.md` 5단계(정상 → 베어링 결함 → 턴간 단락 4턴 → 리셋 → M1 전환 후 같은 결함). 녹화 `tools/record_live_demo.ps1`: 다른 창 전부 최소화 → Isaac 창(프로세스 핸들로 찾음)을 왼쪽 위 1280×950 → Edge 앱 창을 오른쪽 절반 → ffmpeg 데스크톱 캡처(1920 폭) + `live_demo_drive.py` 자동 전송 → 끝나면 창 복원.

**결과 영상** `모터결함_애니메이션/10_라이브_양방향_데모_1920x1080.mp4` — 2026-10-09 16:03~16:07 녹화, **207 s, 10.3 MB**, 1920×1080 30 fps. 확인 프레임 `docs/live_r3/demo_frame_{25,70,100,150,190}s.png`:
25 s 정상(전부 초록) · 70 s 베어링 결함+단락(Isaac HUD `Inter-turn short (4 turns)` STATUS DANGER, 보드 위험·R상 132 %·I₂/I₁ 0.104·kurtosis 50) · 100 s 리셋 후 식는 중 · 150 s 띠 "모터 전환 중 (M1, 약 60초) · 경과 21초" + Isaac 재기동 화면 · 190 s M1 `● LIVE` 베어링 결함(DE 85 °C 경고, M5 는 같은 시점 143 °C 위험). 전환은 **23.1 s**(ack→M1 첫 state).

녹화 시도 기록: ① 접속 클라이언트 8명 초과(`too many clients`, 맥북·데스크탑 탭) → `max_clients 32` ② VS Code 창이 Isaac 뒤로 찍힘 → 녹화 전 전체 최소화 ③ Isaac 창을 제목으로 못 찾아 최소화된 채 녹화 → `Get-Process kit` MainWindowHandle ④ 성공.

## 5. 한계
- 재기동 중에는 Isaac 창이 사라졌다 다시 뜬다(약 1 분). 발표 흐름상 "모터 전환" 은 마지막 단계에 두었다.
- 전환 전 조작값(부하·배속·결함)은 넘어가지 않는다(수동 모드, 정격 부하로 시작). 필요하면 재기동 뒤 다시 보낸다.
- 옛 코드 인스턴스(hello 없음)에 붙으면 제어 패널이 안내 문구만 보여준다 — Isaac 재실행 필요.
