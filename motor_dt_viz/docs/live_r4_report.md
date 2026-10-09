# R4 — 안정화·성능: 데모 프리셋 · 핫 모터 스위치 · 장애 테스트 · 체크리스트

사용자 추가(2026-10-09): ① 모터 전환 공백을 설명 시간으로(왜 재시작하는지 + 비교 안내), 가능하면 전환 시간 단축(USD 재로드 생략 등) ② 체크리스트에 백업 영상 경로와 라이브 실패 시 전환 절차 ③ 맥북 Wi-Fi 끄기 테스트는 사용자가.

## 1. 모터 전환 — 재기동 대신 핫 스위치 (①)

R3 의 자동 재시작(45~130 s)은 Isaac 프로세스 기동이 대부분이었다. USD 스테이지·물리 바디·머티리얼은 모터와 무관하고(외형은 카메라 거리로 프레임 비례 표현), 모터에 따라 달라지는 것은 **열회로·전류 모델·결함 주입기·판정·정격·물리 상수·카메라 거리·HUD 문구**뿐이라 이것만 프로세스 안에서 재생성한다(`demo_integrated.py hot_switch_motor`).

| 항목 | 재시작 (R3) | 핫 스위치 (R4 기본) |
|---|---|---|
| 끊김 | 소켓 close → 재접속 | 없음 (같은 소켓으로 새 모터 state) |
| ack → 새 모터 첫 state | 23~133 s (단독 ~47 s) | **0.11 s** (switch 자체 5~14 ms, 실측 `docs/live_r4/fault_tests.json` D) |
| 상태 | 수동 모드로 재기동, 조작값 초기화 | 결함·케이스 해제, 열 상태 초기화, 부하·배속은 유지 |
| 설정 | `config/live.yaml select_motor.switch_mode: restart` | `switch_mode: hot` (기본), `switch_banner_min_s: 10` |

대시보드 띠(`LiveBanner`): ack 의 `hot/restart`·`from`·`switch_ms` 와 직전 state(원인·DE 베어링 온도·진동)를 받아 **최소 `switch_banner_min_s`(10 s)** 동안 두 줄을 보여준다 — 문구는 `dashboard/public/content/live.yaml` 의 `switch_why_hot / switch_why_restart / switch_compare` 템플릿(변수 to_id·to_name·to_kw·to_poles·from_id·from_kw·ratio·from_summary·eta·switch_ms, 숫자는 index.json 과 마지막 state).
예) "모터 전환 완료 → M1 · Isaac Sim 안에서 모터 라이브러리(M1)의 열회로·전류 모델·판정 임계값·카메라 거리만 바꿨습니다 — 재기동 없음, 14 ms." / "M1 은(는) 1톤 호이스트 권상 모터 (2.2 kW 4극) — 2.2 kW 4극, 출력은 M5(22 kW)의 10 %. 같은 결함을 넣어 열용량이 작은 모터가 얼마나 빨리/늦게 반응하는지 비교해 보세요. 직전 M5: 위험 (bearing_kurtosis 50) · DE 베어링 143.4 °C · 진동 4.8 mm/s". 스크린샷 `docs/live_r4/switch_banner_status.png`.
재시작 모드에서는 "왜 재기동하는지"(모터별 모델을 기동 때 만든다) + 같은 비교 안내 + 경과 초.

## 2. 데모 프리셋 (`config/render_demo.yaml`, `--preset demo`)

1280×720, RTX Real-Time(`/rtx/rendermode = RaytracedLighting`), 물리 서브스텝 2, 입자 12/경로, 뷰포트 1개(추가 창 숨김), `fps_warn_below 30`, `perf_log_after_s 8`. `--low` 보다 우선. 기동 성능 로그 `[perf] start: {...}` → `logs/<subdir>/perf_start.json`, 이후 5 s 마다 FPS 가 30 아래면 `[perf] WARNING`.

| 실행 | FPS(기동 8 s) | VRAM(GPU 전체) | Isaac RAM | 비고 |
|---|---|---|---|---|
| `--preset demo`, 통합 모드 M5 | 58.5 (기동 직후, 셰이더 워밍업 중) → 정상 구간 80~90 (R1 `--low` 측정 90.3) | 3,271 MiB | 4,860 MB | 다른 Isaac 없음 |

## 3. 장애 테스트 (`tools/live_fault_tests.py ws://127.0.0.1:8766 --kill`, 결과 `docs/live_r4/fault_tests.json`)

| 상황 | 방법 | 대시보드/서버 반응 | 결과 |
|---|---|---|---|
| 범위 밖 명령 | `set_load 500` | ack `ok:false, reason "pct out of range 0~150: 500"`, 메인 루프에 안 감 | 통과 |
| 허용 목록 밖 명령 | `run_code` | ack `ok:false, "command not allowed: run_code"`, 로그 `[live] 거부` | 통과 |
| 두 클라이언트 동시 명령 | A `set_load 50`, 50 ms 뒤 B `set_load 120` | 둘 다 ack ok(모든 클라이언트에 방송), 최종 state.load **1.2 = 마지막이 이김** | 통과 |
| 모터 전환(핫) | `select_motor M3` | 소켓 유지, ack 0.056 s, 새 모터 첫 state **+0.11 s**, switch 6 ms | 통과 |
| Isaac 강제 종료 | `Stop-Process kit.exe -Force` | 클라이언트 close 감지 **+1.7 s** (마지막 state +1.46 s) → 대시보드 뱃지 "끊김 → 녹화" + 노란 띠, 2 s 마다 재접속 | 통과 (3 s 기준 안) |
| 대시보드 새로고침 | 브라우저 F5 | LIVE 토글·주소가 localStorage 에 있어 새로고침 즉시 재접속(연결 중 → LIVE 1~2 s), 버퍼는 비워졌다가 다시 찬다 | 통과 (R2 확인) |
| 네트워크 끊기 | **맥북 Wi-Fi 끄기 → 30 s 뒤 켜기** (사용자) | 예상: 끈 뒤 ≤3 s 에 "끊김 → 녹화" 띠, 켠 뒤 ≤2 s + 재접속으로 LIVE 복귀 | 사용자 실행(2026-10-09 17시경, 맥북) — 전환·복귀 초 수와 띠 문구는 **수치 보고 대기** (받는 대로 여기에 기입) |

## 4. 체크리스트 (②)
`docs/live_demo_checklist.md`: 전날 점검(빌드·테스트·방화벽·백업 영상 재생 확인·리허설), 시작 순서(Isaac `--live --preset demo` → 대시보드 → 접속·hello 확인 → 리셋 → 백업 영상 미리 열어 두기), **라이브 실패 시 15 초 안에 전환하는 절차**(말·백업 영상 `모터결함_애니메이션/10_라이브_양방향_데모_1920x1080.mp4` 타임라인·복구), 데모 중 키, 끝나고 기록.

## 5. 남은 것
- 영상 자리 옵션 2·3(스냅샷·WebRTC), 실측 센서 입력, 카메라 명령 — R5(지시 시).
- 프리셋의 `disable_extensions` 는 비워 두었다(끌 확장을 정하면 config 에 추가).
