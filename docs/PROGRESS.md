# 진행 현황 요약 (2026-10-26 기준)

크레인 권상 모터(현대 SSEN HLP-2.2/4, 2.2 kW 4극) 디지털 트윈 — Isaac Sim 결함 시뮬레이션, 판정 엔진, 대시보드, Maxwell 해석 연동까지 지금까지 한 일을 한 장으로 정리한다.
상세 기록은 `SESSION_LOG.md`(26장), 변경 이력은 `CHANGELOG.md`, 재현 절차는 `docs/REPRODUCE.md`.

- 저장소: [motor-predictive-maintenance](https://github.com/kimsunwu4981-ship-it/motor-predictive-maintenance) (이 저장소) · Maxwell 해석 저장소 `hoist-motor-maxwell`
- 릴리스 태그: `v1.0-m1` (2026-10-21, 두 저장소 공통) · 최신 커밋 `41acba4`
- 테스트: `motor_dt_viz/tests` 151 passed · 1 skipped

## 1. 한눈에 — 지금 무엇이 되어 있나

| 영역 | 상태 | 어디 |
|---|---|---|
| 모터 3D 모델 (M1 전체: 100L 하우징 + 권선·로터·베어링 내부) | 완료 (절단·권선만·반절 반투명 뷰 포함) | `motor_dt_viz/assets/motors/M1/`, `tools/cad/` |
| Isaac Sim 결함 시뮬레이션 (기계 7장면 · 전기 11장면 · 통합 5장면) | 완료, 실시간 재생·HUD·녹화 | `motor_dt_viz/app/demo_integrated.py`, `config/scenarios_M1.yaml` |
| 판정 엔진 (안전/경고/위험, 히스테리시스·지속 3 s, 경부하 참고 규칙) | 완료 | `motor_dt_viz/engine/thresholds.py`, `config/thresholds.yaml` |
| 전기 결함 신호 (등가회로 LUT, Maxwell RMxprt+MCCM, 2D 와전류 검증) | 완료, 시뮬 ↔ 해석 대조 89/89 | `data/electrical/M1_mccm_lut_v2.json`, `docs/verification/` |
| 라이브 모드 (Isaac ↔ 대시보드 WebSocket, 양방향 제어) | 완료 (R0~R4) | `app/live_bridge.py`, `dashboard/src/live/` |
| 대시보드 — 상태 보드 `#/status` | **단순 보기(상태·원인·조치) 기본 + 전문가 보기** | `dashboard/src/status/SimpleView.tsx`, `docs/dashboard_simple_view.md` |
| 대시보드 — 기계/전기 해설 화면 | 완료 (값은 M1, 영상은 이전 22 kW 녹화 — 이력) | `dashboard/src/pages/*Live.tsx` |
| AI Hub 실측 데이터 기준선 (베어링 kurtosis·고주파 배율, 정상 I₂/I₁ 중앙값) | 샘플 기준 완료, 전체 zip 미보유 | `motor_dt_viz/docs/aihub_*`, `motor_dt_viz/tools/aihub/` |
| 검증 문서 (대조 보고서, 비교표 엑셀, 역추정, 민감도, 검증 요약) | 완료 | `docs/verification/`, `docs/verification_summary.md` |
| 보고용 미디어 팩 (사진 57장 · 영상 8편 + GIF 2) | 완료 (바탕화면 사본 `M1_미디어팩_20261026`) | `docs/media/20261026/` |

## 2. 시간순 진행 (SESSION_LOG 장 번호)

### 9월 — 모델링과 시각화 기반
1. **Fusion 360 모델링 → Blender 렌더링** (1~2장): 22 kW 권상 모터 도면(JW-01-HTO-00) 기준 3D 모델.
2. **Isaac Sim v1/v2** (3~4장): 속도 드라이브 → 토크 제어 루프 + 전류 채널.
3. **결함 시각화 MVP** `motor_dt_viz/` (7장): 9노드 열회로(온도 색), 3상 전류 입자(과전류 빨강·저전류 파랑), 통합 자동 재생 시나리오.
4. **설명 대시보드** `dashboard/` (8장): Vite+React+ECharts, export 스크립트(config·로그 → JSON), 영상 ↔ 차트 동기(오차 ≤ 0.07 s).
5. **기계/전기 결함 분리 + 실시간 해설 대시보드** (10~12장): `#/mechanical`, `#/electrical`, 발표자 화면, 상 표기 R·S·T 통일.

### 10월 초 — 다중 모터·실측 데이터·라이브
6. **5종 모터 상태 보드** (13장) → 이후 **단일 모터 M1 로 전환**(18장, 라이브러리 퇴역).
7. **AI Hub 「기계시설물 고장 예지」 진동 데이터** (14·16·17·23장): 다운로드·선별·특징 추출, 베어링 지표를 kurtosis(3.5/4.0) + 고주파 대역 RMS 배율(1.5/2.5)로 교체.
8. **라이브 모드 R0~R4** (18~22장): Isaac `--live` WebSocket 브리지(10 Hz), 대시보드 녹화/LIVE 토글·폴백, 양방향 제어 패널(결함 주입·부하·배속), 핫 모터 스위치, 장애 테스트 6종, 맥북 Wi-Fi 끊김 테스트.

### 10월 중순 — Maxwell 해석 연동
9. **전기 트랙 D1~D6** (24장): Maxwell 경로 B 등가회로 LUT(RMxprt v2m2 + MCCM)를 전류 결함 신호에 연동(`method: lut`), M1 카탈로그 정격(4.73 A, Y, η 0.895, pf 0.79).
10. **LUT v2 + 2D 와전류 검증**: 단락 루프 전류 FEM 정합(I_f ±3 %), Xm −3.7 %, 기동 특성 IEC 허용차 안.

### 10월 21일 — M1 전체 모델·검증·릴리스
11. **M1 전체 3D 모델 (P4)** (15~16장): 카탈로그·데이터시트 재구성(Maxwell 체적 ±2 %), 100L 하우징, 36슬롯 2층 권선·Coil_01 단락 분할, 로터 케이지, Isaac 연결, 절단/권선만 뷰, fault_focus 카메라.
12. **P1 실측 기준선 체계** (17장): provisional 지표·배지, 기준선 모드, AI Hub 참고 기준선.
13. **반절 반투명 뷰** (19장).
14. **시뮬 ↔ 해석 대조 검증** (20~21장): 증거 보고서 89/89 PASS(LUT ≤ 0.48 %, 재계산 ≤ 0.023 %), 실시간 비교 패널, 엔진 I₁ = LUT 정상분 RMS(승인).
15. **마무리 D** (22~23장): 깨끗한 clone 재현 확인, 태그 `v1.0-m1`, CHANGELOG, HUD 합성 스크린샷, 검증 요약, 저전류 **경부하(참고) 규칙**(승인) 등 후속 6건.
16. **시뮬 vs Maxwell 비교표** (24장): 엑셀 9시트 + 한 장 요약, 결함 크기 역추정 18/18 ±1턴, FEM 불확실성 민감도(판정 변화 1건).

### 10월 26일 — 보고용 산출물·대시보드 단순화
17. **보고용 미디어 팩** (25장): Isaac 사진 13(3장 2560×1440)·HUD 합성 9(state.csv 대조 9/9)·대시보드 12·영상 8 + GIF 2·해석 그림 23, `index.md`·`meta.json`(커밋·시드·배속)·`README.md`(수동 캡처 체크리스트)·`contact_sheet.png`.
18. **상태 보드 단순화** (26장): 첫 화면 = 상태·원인·조치(영웅·왜?·무엇을?·신호 칩·흐름), 근거 서랍·시트, 쉬운 말 사전, export 필드 추가(엔진 값 그대로, 기존 필드 diff 0), 전문가 보기 토글 유지. 미디어 팩 대시보드 사진·영상 재캡처.

## 3. 핵심 숫자 (전부 config·로그·해석 산출물에서, 수기 없음)

| 항목 | 값 | 출처 |
|---|---|---|
| 정격 선전류 / 결선 | 4.73 A / Y (현장 확인 필요) | `config/motors/M1.yaml` (카탈로그) |
| I₂/I₁ 임계 | 안전 < 0.05 · 위험 ≥ 0.10, 지속 3 s | `config/thresholds.yaml` |
| 정상 I₂/I₁ (고유 비대칭) | 0.027 | AI Hub 정상 중앙값 |
| 4턴 / 12턴 단락 I₂/I₁ (합성) | 0.0726 / 0.2696 | 엔진(LUT) · 해석 기준 0.0725 / 0.2696 |
| 단락 루프 전류 4턴 | 34.4 A (MCCM 34.35, 2D FEM 35.2) | LUT / Maxwell |
| 시뮬 ↔ 해석 대조 | 89/89 PASS, 역추정 18/18 ±1턴 | `docs/verification/` |
| 베어링 지표 | kurtosis 3.5/4.0 · 고주파 배율 1.5/2.5 | `config/thresholds.yaml`, AI Hub |
| 진동 규격 | ISO 10816-1 Class I 1.8/4.5 mm/s | `config/motors/M1.yaml` |

## 4. 정직성 표기 (화면·문서 공통)

- 모든 수치는 **시뮬레이션 기반 추정값**(카탈로그 사양 + 등가회로 LUT + 2D 와전류 검증). 실측 기준선 확보 전까지 I₂/I₁·전류 비율·베어링 지표는 *provisional*(화면에 "임시" 태그).
- 열회로 계수는 22 kW 보정값을 스케일한 것이라 M1 온도 판정은 낙관적일 수 있다(`motor_dt_viz/docs/thermal_scaling.md`).
- 해설 화면(`#/electrical`, `#/mechanical`)의 영상은 이전 22 kW 녹화(이력). M1 수치는 상태 보드에서 본다.

## 5. 남은 일 / 다음 단계

| 항목 | 상태 | 필요한 것 |
|---|---|---|
| 현장 명판 확인 → 결선·정격 `confirmed` 승격 | 대기 | 명판 사진 (미디어 팩 README 수동 체크리스트 5) |
| 실측 기준선 (정상 운전 전류·진동) | 대기 | 현장 측정 또는 AI Hub 전체 zip(88~112 GB) |
| 산출 문서 4종 M1 갱신 (E) | 보류 | 원본 `docs/deliverables/_v22kW/` 필요 |
| Maxwell GUI 자속밀도·전류밀도·메시 캡처, 라이브 모드 화면, 실물 사진 | 수동 | 미디어 팩 README 체크리스트 |
| 해설 화면 narration 문장 M1 기준 재작성 (지금은 22 kW 기준 "Δ권선" 문구) | 보류 | 문구 결정 |
| 단순 보기 "상 불평형" 칩 유지 여부 | 판단 대기 | 표시용 보조값 — 뺄지 결정 |

## 6. 실행 방법 (요약)

```
# 대시보드 (오프라인)
cd dashboard && node serve.cjs            # http://localhost:4173/#/status
# Isaac Sim 데모 (PowerShell, motor_dt_viz 에서)
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --view cutaway
# 테스트
cd motor_dt_viz && py -3.12 -X utf8 -m pytest tests -q
```

환경 함정(Isaac 은 PowerShell 에서만, gdigrab 녹화 중 창 가리지 말 것, Playwright 는 Edge 채널 등)은 루트 `CLAUDE.md` "환경 함정" 절에 있다.
