# 모터 결함 설명 대시보드 (기계 / 전기 분리)

Isaac Sim 녹화 영상과 시뮬레이션 로그를 **동기 재생**하며, 심사위원이 "무엇이 보이는가 → 기준이
무엇인가 → 그래서 무엇이 좋은가"를 한 화면에서 이해하게 하는 발표용 대시보드다.
기계적 결함과 전기적 결함은 **완전히 별개의 화면**이고, 첫 화면에서 하나를 고른다.

- 완전 오프라인 (외부 폰트·CDN 없음, ECharts 는 번들에 포함)
- 모든 숫자는 `motor_dt_viz/config/*.yaml` 과 `logs/<mode>/*.csv` 에서 export 한 JSON 만 읽는다
- 화면에는 항상 `시뮬레이션 기반 추정값` 과 정격 기준(22 kW 6극, 도면 JW-01-HTO-00)이 표시된다

## 실행 (발표장, 더블클릭)

`run_dashboard_mechanical.bat` 또는 `run_dashboard_electrical.bat` 을 더블클릭한다.
Node.js 만 있으면 되고 인터넷은 필요 없다. 로컬 서버(`serve.cjs`, 포트 4173)가 뜨고 브라우저가
해당 화면으로 열린다. 창을 닫아도 서버 콘솔은 `Ctrl+C` 로 끝낸다.

| 키 | 동작 |
|---|---|
| `F` | 발표 모드 (전체화면, 글자 확대, 하단 탭 숨김) / `Esc` 해제 |
| `Space` | 재생 / 정지 |
| `←` `→` | 이전 / 다음 챕터 |
| `1`~`7` | 챕터 바로 이동 |
| `C` | 영상 아래 자막 켜기/끄기 |
| `N` | (발표자 모드) 해설 다음 단계 공개 |
| `Q` | 예상 질문과 답 서랍 + 용어 풀이 (`Esc` 닫기) |
| `L` | (전기) 선전류(케이블) ⇄ 상전류(권선) 기준 전환 |
| `P` | (전기) 페이저도 확대 보기 (`Esc` 닫기) |

주소로 특정 장면을 바로 열 수 있다: `#/mechanical?t=40`, `#/electrical?t=130&tab=faults`.

### 두 대시보드 공통: 자동 해설 / 발표자 모드 / 발표자 화면

- **자동 해설**(기본): 장면 해설의 세 단계(왜 → 무엇이 보이나 → 그래서)가 `reveal_timing` 에 따라 저절로 열린다.
  심사위원이 혼자 볼 때·부스 전시용.
- **발표자 모드**(상단 버튼): 해설 단계는 `N` 을 눌러야 열린다. 말하는 속도에 맞출 때.
- **발표자 화면** `#/mechanical/presenter`, `#/electrical/presenter` (상단 "발표자 ↗" 버튼): 발표자 노트북용. 멘트(PDF 원고)·다음 장면·
  다음 사건·경과 시간을 보여주고, 같은 브라우저의 메인 창과 재생 상태를 공유한다(BroadcastChannel, 오프라인).
  이 창의 `Space`/`←→`/`1~7`/`N` 은 메인 창을 조작한다. 멘트는 메인(심사위원) 화면에는 나오지 않는다.
  메인 창 없이 연습하려면 `#/mechanical/presenter?t=40` 처럼 연다.

### 전기 대시보드 (`#/electrical`)

상단 바(주목 상 기준 뱃지 · 슬로모션 60배 표시 · 선/상전류 토글), 영상+자막 띠 ‖ 실시간 해설 · Δ결선 회로도(입자·단락 루프·끊김),
하단: 상별 전류 막대+추세 · I₂/I₁ 게이지+추세 · 페이저도 · 인과 카드+결함 판별 매트릭스(크기 × 균형). 상 이름은 config
`electrical.yaml` 의 `phase_labels`(R·S·T)를 따른다. 이전 탭형 전기 대시보드(기준표·결함 도감·용어 풀이)는 `#/electrical/classic`.
전기 리드 타임은 0 s 로 정직하게 표시한다(해석식 등가 표현의 한계) — 균형 지표의 가치는 장면 5로 보여준다.

### 모터 상태 보드 (`#/status`) — 보편 권상 모터 5종

`run_dashboard_status.bat` 더블클릭. 첫 화면에 M1~M5 카드(안전/경고/위험 + 원인 한 줄)가 뜨고, 카드(또는 1~5 키)로 고르면
사양·게이지 8개(온도 4 · 전류 비율 · I₂/I₁ · 진동 · 베어링 지표)·원인과 조치·재생 바·추세가 그 모터로 바뀐다. 모터별 진동 규격(M1~M3 1.8/4.5, M4·M5 1.4/4.5)과
정격 전류가 게이지 구간에 자동 반영된다. 키: Space 재생 · ←→ 장면 · M 기계/전기 시나리오 · F 발표 · Esc.
"해설 대시보드에서 이 장면 보기" 는 기계·전기 해설 화면(M5 애니메이션 기준)으로 같은 시각에 연다.

데이터 갱신 (모터 YAML·임계값·시나리오가 바뀌었을 때):

```
cd motor_dt_viz
python tools/run_fleet.py                 # 5종 × 기계·전기 엔진 배치 → logs/fleet (판정 포함, 7 s)
python tools/fleet_summary.py             # docs/fleet_summary.md
python ../dashboard/tools/export_status_data.py   # public/data/fleet/*.json
cd ../dashboard && npm run build
```

"명판값 입력" 버튼으로 모터 명판값을 넣으면 그 모터의 출처가 명판값으로 바뀌고(이 브라우저에만 저장), YAML 조각을 복사해 `config/motors/<id>.yaml` 에 반영한 뒤 배치를 다시 돌리면 판정까지 바뀐다.
실측 스트림은 `#/status?live=<url>` 로 붙인다 (`src/status/source.ts` 의 JSON·SSE 계약). 첫 화면 데모 위치는 `motor_dt_viz/config/status_demo.yaml`, 용어 풀이는 `public/content/status/glossary.yaml`(런타임에 읽음).
검증: `pytest dashboard/tests/test_status_export.py -q` (JSON = config·로그, 판정 = thresholds.py 재실행). 확인 기록: `docs/status_board_check.md`.

## 화면 구성

위에서부터 상태 바(모드 · 현재 상태 뱃지 · 정직성 라벨), 영상 + 챕터 타임라인 ‖ 설명 패널
(무엇이 보이나 / 왜 그런가 / 현장에서는), 동기 차트, 하단 탭(색상 기준표 / 결함 도감 / 용어 풀이).

| | 기계적 결함 | 전기적 결함 |
|---|---|---|
| 영상 | `media/mechanical/mechanical_full.mp4` (180 s) | `media/electrical/electrical_full.mp4` (165 s) |
| 차트 | 부품별 온도 + 선택 부품의 임계 구간 배경색 | 상별 전류 RMS(임계 구간) + I₂/I₁ (케이스 눈금) |
| 리드 타임 | 주의 진입(경보) → 위험 진입 | I₂/I₁ ≥ 4턴 수준(경보) → 위험 과전류 |
| 결함 도감 | 베어링 · 오정렬 · 냉각팬 · 브레이크 · 과부하 | ITSC · 과부하 · 전압 불평형 · 결상 · 무부하 |
| 용어 풀이 | 발열 원인, 열이 번지는 원리, 부품별 기준 | 전압과 전류의 관계(저전압→과전류 등), I₂/I₁ |

영상 시각과 차트 커서는 `t_real = currentTime − video_offset_s` 로 묶여 있고, 차트를 클릭하면
영상이 그 시각으로 간다. 오프셋 검증은 [`docs/sync_check.md`](docs/sync_check.md).

## 데이터 갱신 (config 나 로그가 바뀌었을 때)

```powershell
cd dashboard
& "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" tools\export_dashboard_data.py --mode all
& "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" -m pytest tests -q   # JSON ↔ config·로그 일치 33건 (기계 확장 16건 포함)
npm run build
```

export 는 `motor_dt_viz/engine` 을 그대로 재사용하며 계산 로직을 복제하지 않는다. 테스트가 하나라도
실패하면 화면의 숫자와 애니메이션의 숫자가 다르다는 뜻이므로 발표에 쓰면 안 된다.

## 설명 문구 고치기

- **기계·전기 실시간 해설**: `public/content/<mode>/narration.yaml`(장면 해설·멘트·인과 카드), `event_templates.yaml`(자막),
  전기는 `glossary.yaml`(용어 풀이)도. 검토표 [`docs/narration_review_electrical.md`](docs/narration_review_electrical.md),
  체크리스트 [`docs/first_viewer_check_electrical.md`](docs/first_viewer_check_electrical.md). 상 이름은 `{ph_a}` 같은 변수로.
  `qa.yaml`(예상 질문). 고치고 **새로고침만** 하면 된다(빌드 불필요). 숫자는 쓰지 말고 파일 머리의 `{변수}` 를 쓴다.
  PDF 원문과의 대응은 [`docs/narration_review.md`](docs/narration_review.md), 검토 체크리스트는
  [`docs/first_viewer_check.md`](docs/first_viewer_check.md), 전기 대시보드에 같은 구조를 적용하는 메모는
  [`docs/electrical_apply_notes.md`](docs/electrical_apply_notes.md).
- **이전 전기 대시보드(classic)**: `src/content/electrical.ts` 에 챕터 문구·결함 카드·용어 풀이가 있다. 문장 안의 숫자는
  `d.thresholds...` 처럼 JSON 을 참조하므로 그대로 두고 문장만 바꾼다. 고친 뒤 `npm run build`.

## 대시보드 화면 녹화

```powershell
powershell -ExecutionPolicy Bypass -File tools
ecord_dashboard.ps1            # 1920×1080, 7장면 자동 해설 192초
```
Edge 앱 창을 띄워 페이지가 스스로 재생하게 하고 그 영역만 ffmpeg 로 잡는다. 3분 동안 화면을 가리지 않는다.
결과는 프로젝트의 `모터결함_애니메이션/08_기계_실시간해설_대시보드_1920x1080.mp4`. 전기는
`-Url "http://localhost:4173/#/electrical?t=0&autoplay=1" -Seconds 178 -Out ... 9_전기_실시간해설_대시보드_1920x1080.mp4`.
녹화 중 다른 창(브라우저·편집기)을 앞으로 가져오면 그 창이 찍힌다 — 끝날 때까지 손대지 않는다.

## 개발

```powershell
npm install        # 최초 1회 (인터넷 필요)
npm run dev        # http://localhost:5173
npm run build      # dist/ 생성 → run_dashboard_*.bat 이 이것을 서빙
```

## 알려진 한계

- 전기 모드의 리드 타임은 0 이다. 해석식 모델이 ITSC 를 크기 불평형으로 등가 표현하기 때문에 I₂/I₁ 과
  전류 크기가 같은 순간에 변한다. 화면에도 그렇게 적어 두었다. 대신 전압 불평형 장면에서
  "색은 정상인데 I₂/I₁ 만 열 배"가 되는 것이 균형 지표의 가치를 보여준다.
- 헤드리스 브라우저 스크린샷에는 영상 프레임이 검게 나온다(브라우저 제약). 실제 화면에서는 재생된다.
- 과부하 케이스는 `electrical.yaml` 의 `phase_scale` 과 `load` 가 둘 다 곱해져 실제 전류가 정격의
  182 % 다. 확인 대기 중이라 화면에는 비율 숫자를 쓰지 않았다.
