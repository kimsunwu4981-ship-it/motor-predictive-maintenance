# R2 — 대시보드 LiveSource · 녹화/LIVE 토글 · 폴백 · 실시간 추세·해설

지시서 §6. 녹화 모드와 라이브 모드는 **같은 화면·같은 컴포넌트**를 쓰고 데이터 소스만 다르다. 숫자·주기는 `dashboard/public/content/live.yaml` 에만.
확인 스크린샷은 `docs/live_r2/`(헤드리스 Edge + CDP, `dashboard/tools/cdp_shot.mjs` — WebSocket 수신은 실시간이라 가상 시간 스크린샷으로는 안 보인다).

## 1. 구조

| 파일 | 역할 |
|---|---|
| `src/live/feed.ts` `LiveFeed` | WebSocket 클라이언트. state/heartbeat/ack 수신, `send(name,args)`→ack Promise, 하트비트 감시(`heartbeat_timeout_s` 3 s → `lost`), `reconnect_s` 마다 재접속. 판정하지 않는다 — state.status(Isaac 쪽 Judge)를 그대로 쓴다 |
| `src/live/session.ts` `useLiveSession` | 토글 상태(녹화/LIVE)·주소(localStorage `vigent-live`, `?live=ws://…` 로도 켜짐)·피드·**수신 버퍼**(`LiveBuffer`, 최근 `window_s` 300 s / `buffer_max_n`)·`active`(연결 살아 있고 샘플 ≥2)·`fallback`(LIVE 켰는데 끊김) |
| `src/live/LiveToggle.tsx` | 상단 `녹화 / LIVE` 스위치 + 주소 입력(마지막 값 기억) + 뱃지(초록 LIVE · 노랑 연결 중 · 주황 끊김→녹화) + `LiveBanner`(노란 띠 "라이브 연결 끊김 — 녹화 재생 중") |
| `src/live/livedata.ts` | 버퍼 → 기존 데이터 모양: `toMotorSeries`(상태 보드), `toMechData`/`toElecData`(기계·전기, 성장 시계열 + 관찰된 장면 전환 = `liveSteps` + 등급 변화 사건 = `liveEvents`), `useLivePlayback`(t = 버퍼 끝을 따라감, 일시정지 = 최근 기록 보기, ←/→·챕터 클릭 = `play_scenario` 명령) |
| `src/live/LiveVideoPanel.tsx` | 영상 자리 옵션 1 "Isaac Sim 창을 보세요" + 모터·모드·장면·결함·부하·FPS·VRAM + 최근 N 분 바 + 관찰된 장면 챕터 |
| 차트 4개 (`TempChart`·`VibChart`·`CurrentTrend`·`I2I1Panel`) + `status/TrendChart` | x축 `min: sc.t_min ?? 0` — 라이브에서는 [버퍼 끝−창, 버퍼 끝] 로 **오른쪽으로 흐른다**. 녹화에서는 t_min 이 없어 이전과 동일 |
| `pages/StatusBoard.tsx`·`MechanicalLive.tsx`·`ElectricalLive.tsx` | `useLiveSession()` → `live.active` 면 라이브 데이터·라이브 재생기, 아니면 기존 데이터·기존 재생기 (훅은 둘 다 항상 호출, 선택만 바뀐다). HUD 에 토글·띠 슬롯(`extra`·`banner`) |
| `status/source.ts pickSource` | `?live=http…`(HTTP+SSE 계약)만 옛 LiveSource, `ws://` 는 세션이 맡는다 |

폴백 규칙(§1.3): LIVE 를 켠 상태에서 3 s 동안 메시지가 없으면 `active=false` → 모든 화면이 **즉시 녹화 데이터로** 돌아가고(재생기도 녹화용으로), 상단 뱃지 "끊김 → 녹화" + 노란 띠. 2 s 마다 재접속해 state 가 다시 오면 자동으로 LIVE 로 복귀한다. 사용자 조작 없음.

## 2. 화면별 라이브 동작

- **상태 보드**: 스트림의 모터 카드에 `● LIVE`, 나머지 카드는 흐리게 "라이브 아님 · 배치 로그". 스트림이 붙으면 그 모터를 자동 선택. 게이지·원인과 조치·신호 칩은 state.status 의 등급·원인 그대로(판정 안 함). 재생 바는 "LIVE · 최근 5 분" 창, 색 띠는 버퍼의 판정 상태, 챕터는 관찰된 장면 전환. `❚❚ 최근 기록 보기` 로 버퍼 안을 돌려보고 `▶ LIVE 복귀`. M 키(모드 전환)는 라이브에서 무시(모드는 Isaac 이 정한다). 장면 해설(cause_chain)은 state.step 으로 고른다.
- **기계·전기 해설**: 영상 자리는 안내 패널, 차트는 흐르는 창, 해설 단계는 **Isaac 이 평가한 `narration_key.reveal`**(why/visible/result)로 공개(자동 해설 모드), 발표자 모드는 N 키 그대로. 사건 자막·이력은 state.status 의 등급 변화에서 생성(온도 stage_up/down·recovered, 진동 vib_zone, 전류 status, I₂/I₁ up/down)과 장면 전환·해설 공개. 수동 조작 구간(step=manual)은 해설 대신 안내 문구.
- 정직성 라벨: 라이브에서도 `대표 사양 기반 시뮬레이션 추정값` 그대로 + "· LIVE (Isaac Sim)". 모드 표시(녹화/LIVE)는 세 화면 상단에 항상.

## 3. 확인

| 항목 | 결과 | 스크린샷 |
|---|---|---|
| 녹화 모드 회귀 (상태 보드 M1 t=52 · 기계 t=52 · 전기 t=60) | 이전과 동일 렌더, 대시보드 테스트 63 통과 | `rec_status.png`, `rec_mechanical.png`, `rec_electrical.png` |
| 라이브 — 상태 보드 (`?live=ws://127.0.0.1:8765`, Isaac `--live` 수동 구간) | M5 카드 `● LIVE`, 샤프트 온도 경고, 나머지 카드 흐림, 자동 선택 | `live_status.png` |
| 라이브 — 기계 해설 | LIVE·M5 뱃지, 안내 패널(모터·모드·장면·결함·부하·FPS 79·VRAM 3.2 GB), 온도·진동 차트 흐름, 수동 구간 안내 | `live_mechanical.png` |
| 라이브 — 전기 해설 | 상별 전류 R 44.5 / S·T 43.7 A, I₂/I₁ 0.006, 페이저·매트릭스 | `live_electrical.png` |
| 폴백 (닫힌 포트 8799) | 노란 띠 "라이브 연결 끊김 — 녹화 재생 중 · 재연결 시도 중 (2 s 간격)", 뱃지 "끊김 → 녹화", 화면은 녹화 데이터로 정상 | `fallback_status.png`, `fallback_mechanical.png` |

동기 지연: state 10 Hz + 송신 지연 1 ms(같은 PC) → 화면 갱신은 0.1 s 단위(차트 20 Hz 커서). 맥북은 Wi-Fi 왕복이 더해지지만 1 s 이내 기준은 여유.
Isaac 강제 종료 → 3 s 안에 녹화 전환은 `heartbeat_timeout_s` 가 보장한다(끊김 감지는 소켓 close 즉시, 조용한 끊김은 3 s).

## 4. 한계·다음

- 영상 자리 옵션 2(스냅샷)·3(WebRTC)은 R5. 지금은 `video_panel: hint` 만.
- 라이브 모터가 M5 가 아니면 기계·전기 해설 화면의 정격·임계 표기(thresholds.json, M5 export)와 state 의 정격이 다를 수 있다 — 전류 비율은 state.rated_line_A 로 계산하지만 HUD 의 "정격 기준" 문구는 export 값. 상태 보드는 모터별 index 를 쓰므로 정확.
- `loss_W` 는 R2 에서 state 에 추가했다(데모 재시작 후 반영). 그 전 스트림은 손실 0 으로 표시.
- 제어 패널(결함 토글·슬라이더)은 R3. 지금은 ←/→·챕터 클릭(`play_scenario`)만 명령을 보낸다.
