# R1 — Isaac Sim 쪽 LiveBridge (송신·수신·하트비트·`--live`) + Judge 한 곳 판정

지시서 §4 R1 + 사용자 추가 3건(2026-10-09): ① Judge 를 루프에 넣고 HUD 색도 Judge 등급으로(열 모델 4단계는 세부 라벨), M5 자동 재생 로그 회귀 확인
② `select_motor` 는 "재시작 필요" ack 로 거부(전환 방식은 R3) ③ 실제 state 로 FPS·지연 재측정. 숫자는 `docs/live_r1/`(실측 사본)·config 에서만.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `config/live.yaml` | 바인드 `0.0.0.0:8765`, state 10 Hz, heartbeat 1 Hz, perf 5 s, max 8 클라이언트, 대시보드 포트 4173, **허용 명령·인자 범위**(inject_fault 결함/케이스·별칭, set_load 0~150, set_time_scale 1~600, set_slowmo 1~240, set_mode, play_scenario, stop_scenario, reset, select_motor `runtime: false`) |
| `app/live_bridge.py` | `LiveBridge`: 별도 스레드 asyncio + websockets 서버. `publish(state)` 최신 1건만 보관(백프레셔), 10 Hz 방송(바뀐 것만), 1 Hz heartbeat(클라이언트 없어도), 명령 검증(허용 목록·범위·별칭 정규화) → 통과분만 메인 루프 큐, `ack()` 는 모든 클라이언트에 방송(마지막 명령이 이김). perf 스레드(psutil RSS, nvidia-smi VRAM 5 s). `lan_ip()` 로 접속 주소 |
| `app/demo_integrated.py` | `--live`(없으면 기존과 동일), `--live_port`. **Judge 루프 투입**(fleet 배치와 같은 신호·반올림, `t_session` 기준 지속·히스테리시스), 10 Hz 로 판정·`state_dict`·publish, 명령 큐 적용 `apply_command()`(DemoState 만 바꿈, 패널과 같은 경로), 리셋·모드 전환·재생 시 `judge.reset()`, `play_scenario {scene:n}` 장면 점프, CSV 끝 4열 `status, cause_signal, cause_component, cause_value`, `narration_key.reveal`(대시보드 narration.yaml 의 reveal_timing 평가) |
| `viz/hud.py` | 온도·전류·진동 행 색 = **Judge 등급**(thresholds.yaml colors), 4단계 stage·과/저전류·ISO 구역은 괄호 세부 라벨. `STATUS <등급> <원인>` 행, `LIVE ws://IP:8765 clients N` 행. 창 높이 790→840 |
| `engine/fault_injector.py` | `bearing_signals()` 이동(run_fleet 과 데모가 같은 함수) |
| `tests/test_live_bridge.py` | Isaac 없이 왕복·거부·별칭·두 클라이언트·주소 (4개) |
| `tools/compare_demo_logs.py` | 자동 재생 로그 회귀 비교(장면 끝 −0.3 s + 0.5 s 격자) |
| `tools/firewall_rules.ps1`, README "라이브 모드" | 방화벽 인바운드 8765·4173(개인·도메인 프로필), 맥북 접속 절차·점검 순서 |

판정은 한 곳: HUD 색, CSV 판정 열, 라이브 `status` 가 모두 `engine/thresholds.py Judge` 결과다. 3D 부품 색(머티리얼 컬러맵·발광)은 그대로 온도 기반이다(영상의 시각 효과, 등급 표기가 아님).

## 2. 실행·확인

```bat
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode mechanical --live
```
콘솔: `[live] WebSocket ws://172.30.1.37:8765 (bind 0.0.0.0:8765, state 10 Hz, heartbeat 1 Hz)` / `[live] dashboard http://172.30.1.37:4173/#/status?live=ws://172.30.1.37:8765`.
클라이언트: `python tools/r0_proto/ws_client.py ws://172.30.1.37:8765 60` (websockets 설치된 아무 파이썬).
HUD 스크린샷(장면 3 축 정렬 불량, 회귀 실행 중): `docs/live_r1/hud_live_mech_scene3.png` — `STATUS WARN vibration 3.6`, `DE bearing 81.6 C WARN (caution)`, `VIBRATION 3.6 mm/s WARN (ISO 20816-3 plan)`, `LIVE ws://172.30.1.37:8765 clients 0`(클라이언트 60 s 측정 뒤 종료 시점).

## 3. 회귀 — M5 자동 재생 로그 (Judge·브리지 추가 전 9-22 로그 ↔ `--live` 실행)

`docs/live_r1/regression_mechanical.md`, `regression_electrical.md` (`tools/compare_demo_logs.py`).

| 모드 | 장면 끝(−0.3 s) 최대 차이 | 허용 | 0.5 s 격자 전 구간 최대 | 판정 |
|---|---|---|---|---|
| 기계 (7 장면, 180 s) | 온도 0.1 °C(DE 베어링 0.1, 권선 0.1), 진동 0.00 | 2.5 °C / 0.05 mm/s | 온도 2.2 °C, 진동 2.4 mm/s — 장면 전환 순간의 시각 흔들림(±0.25 s) | **통과** |
| 전기 (7 장면, 195 s) | 전류 0.000 A, I₂/I₁ 0.000 | 0.06 A / 0.002 | 전류 30 A, I₂/I₁ 0.165 — 케이스 전환 순간 | **통과** |

온도·전류·진동 수치는 바뀌지 않았다(엔진 호출 경로 무변경). 새 열 4개는 끝에 덧붙어 기존 독자(export·대시보드)는 영향 없음.

## 4. 성능 — 실제 state (약 3.0 KB) 10 Hz

| 실행 | FPS 평균 / 중앙값(t≤130 s) | 수신 | 지연 | VRAM(GPU 전체) | Isaac RAM |
|---|---|---|---|---|---|
| R0 기준(서버 없음, 판정 없음, 90 s) | 86.5 / 89.2 | — | — | 3,071 MiB | 5.1 GB |
| R0 프로토(57 B) | 83.6 / 86.0 | 9.82 Hz | 0.8 ms | 3,073 MiB | — |
| **R1 기계 `--live` 180 s, 판정 매 프레임** | 77.7 / 81.6 (**−8.5 %** vs 기준) | 612건 / 60 s = **10.19 Hz**, 간격 중앙 94.5 ms(최대 385) | 중앙 **1.0 ms**, 최대 7.1 ms, 3.0 KB/건 | 3,116 MiB | 5.6 GB |
| R1 전기 `--live` 195 s | 77.2 / 78.4 | 606건 = 10.1 Hz, 간격 최대 114 ms | 중앙 1.0 ms, 최대 4.1 ms, 2.95 KB/건 | 3,397 MiB | 5.6 GB |
| R1 기계, 판정·state 10 Hz 로 제한(재측정 130 s) | 79.3 / 82.0 | 553건 = 9.21 Hz (판정 틱과 송신 틱이 어긋나 빠짐) | 중앙 1.0 ms, 최대 4.6 ms | 3,383 MiB | 5.6 GB |
| **R1 기계, + HUD 스타일 캐시·판정 20 Hz (최종, 130 s)** | **86.2 / 89.1** (기준 대비 중앙값 −0.1 %) | 605건 = **10.07 Hz**, 간격 중앙 94.3 ms(최대 112) | 중앙 **1.0 ms**, 최대 3.2 ms, 3.0 KB/건 | 3,371 MiB | 5.6 GB |

- 처음 구현(판정·state dict·HUD 스타일을 매 프레임)은 −8.5 % 였다. 판정·state 를 10 Hz 로 제한해도 거의 그대로(82.0)였고, **HUD 라벨 `style` 객체를 매 프레임 새로 주던 것이 원인** — 등급이 바뀔 때만 style 을 다시 주게 하니(`MotorHUD._restyle`) 기준과 같은 89.1 로 돌아왔다. 판정 주기는 송신 주기의 2배(20 Hz)로 두어 브리지가 매 틱 새 state 를 보낸다(같은 10 Hz 면 9.2 Hz 로 빠졌다).
- 장면별 FPS(기계): 정상 70→ 베어링 81 → 축정렬 84 → 팬 83 → 브레이크 79 → 과부하 75 → 냉각 73 — 뒤 장면이 낮은 것은 발광·입자 누적과 측정 중 다른 앱(브라우저) 영향이 섞여 있어 기준 실행(90 s)과 같은 구간(t≤130 s)으로만 비교했다.
- 간격 최대 385 ms 는 1건(장면 전환 때 메인 루프 스파이크) — 10 Hz 중앙값은 유지. 지연 1 ms 는 같은 PC 값, 맥북은 Wi-Fi 왕복(보통 2~10 ms)이 더해진다.
- 완료 기준(FPS 저하 10 % 이내): 통과 (최종 −0.1 %, 측정 간 변동 범위). 클라이언트로 state·heartbeat·ack 수신 확인(`noop` 명령은 허용 목록 밖이라 `ok:false, reason: command not allowed` — 의도대로).

## 5. 명령 적용 규칙 (apply_command)

- `inject_fault {fault, on}`: 시나리오 재생 중이면 거부("stop_scenario first"). 열 결함은 기계·통합 모드, 전기 케이스는 전기·통합 모드에서만 적용(둘 다 아니면 거부). 별칭 `bearing→bearing_de_fault` 등은 브리지가 정규화. 제어 패널 체크박스도 같이 갱신.
- `set_load pct` → `state.load=pct/100`, `set_time_scale x`, `set_slowmo x` → `1/x`, `set_mode` → 패널 `_set_mode` 경로(잔상 제거·무관 결함 해제), `play_scenario {scene}` → `request_play` + 장면 시작으로 점프, `stop_scenario`, `reset` → 패널 `_reset`.
- `select_motor` → 브리지에서 거부 `restart required: run demo_integrated.py --motor <id> (전환 방식은 R3 에서 결정)` — 메인 루프에 가지 않는다.
- 명령 하나가 예외를 내도 루프는 계속(ack `error: …`).

## 6. 한계·다음

- 맥북 실접속은 사용자가 확인(방화벽 규칙 `tools/firewall_rules.ps1` 관리자 실행 → 네트워크 프로필 '개인' → `ws_client.py ws://172.30.1.37:8765`). 대시보드 LiveSource·모드 토글·폴백은 R2.
- HUD 범례는 3D 부품 색(4단계)을 설명하므로 그대로 두었다. HUD 행 색만 Judge 3단계.
- `perf.vram_mb` 는 nvidia-smi 5 s 샘플(GPU 전체), `ram_mb` 는 Isaac 프로세스 RSS.
- 모터 전환은 재시작(R3 결정). 통합 모드의 `overload` 는 열 결함과 전류 케이스 둘 다 켠다(config note).
