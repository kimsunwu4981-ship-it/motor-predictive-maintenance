# 크레인 권상 모터 디지털 트윈 — 결함 시각화 MVP

**현대일렉트릭 SSEN HLP-2.2/4(M1, 1톤 호이스트 권상 모터 2.2 kW 4극 100L)** 한 대의 결함을 Isaac Sim 화면에서 보여주는
데모다 (2026-10-21 단일 모터 전환, 아래 "단일 모터 M1" 절. 이전 기준이던 22 kW 6극 천장크레인 모터(도면 JW-01-HTO-00)는 열회로 튜닝 기준·이력으로만 남는다). 심사위원이 설명 없이 화면만 보고 **어디서, 왜 고장이 나는지** 알아보게 하는 것이
목표이고, 두 가지를 동시에 그린다.

- **모듈 A — 기계적 결함**: 부하가 쌓이며 생기는 발열을 부품 색으로 보여준다. 정상이면 원래
  재질, 뜨거워지면 주황을 거쳐 빨강으로 발광한다.
- **모듈 B — 전기적 결함**: 3상 전류가 케이블과 권선을 따라 흐르는 것을 입자로 보여준다.
  과전류는 빨강, 정상은 초록, 저전류는 파랑이다.

통합 모드에서는 둘이 이어진다. 모듈 B 가 계산한 상전류가 모듈 A 의 권선 동손(I²R) 으로
들어가므로, **턴간 단락 → A상 과전류 → 수십 초 뒤 권선 과열**이 화면에서 연쇄로 일어난다.

화면의 모든 수치는 측정값이 아니라 시뮬레이션 추정값이고, HUD 에 항상 그렇게 표시된다.

---

## 빠르게 실행하기

결과물은 **기계적 결함 / 전기적 결함 / 통합** 세 모드로 나뉜다. 심사위원에게는 한 번에 한 가지만
보여주는 것이 원칙이라 기계·전기 전용 모드가 발표용이고, 통합 모드는 두 결함의 연쇄
(ITSC → 과전류 → 권선 과열)를 설명할 때만 쓴다.

| 모드 | 화면에 보이는 것 | 시나리오 |
|---|---|---|
| `--mode mechanical` | 부품 발열 색만 (전류 요소 없음) | 7단계 180초 — `config/scenario_mechanical.yaml` |
| `--mode electrical` | 전류 흐름만 (부품 색은 원래 재질 고정) | 7단계 165초 — `config/scenario_electrical.yaml` |
| `--mode integrated` (기본) | 둘 다, 전류가 권선 발열로 연결됨 | 5단계 165초 — `config/scenario.yaml` |

```powershell
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode mechanical
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode electrical
```

장면별 해설과 발표 멘트, 예상 질문은 [`docs/animation_guide.md`](docs/animation_guide.md) 에 있다.
제어 패널의 MODE 버튼으로 실행 중에도 바꿀 수 있다. 전환하면 이전 모드의 발열 색·입자·HUD 가
전부 리셋된다(잔상 없음, 실측 검증). 모드별 녹화와 장면 클립, 바탕화면 정리는 아래 "녹화" 절,
설명 대시보드는 [`../dashboard/README.md`](../dashboard/README.md) 를 본다.

Isaac Sim 4.5 가 필요하다. 경로에 공백이 있어 `C:\issac sim\python.bat` 은 인자가 깨지므로
8.3 형식을 쓴다.

```powershell
cd "C:\Users\sunwu\OneDrive\바탕 화면\프로젝트\디지털 트윈\크레인 퀀선 모터 모델링\motor_dt_viz"
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay
```

`--autoplay` 를 빼면 수동 모드로 뜨고, 제어 패널에서 직접 결함을 넣어볼 수 있다. 발표
녹화는 [`docs/record_demo.md`](docs/record_demo.md) 를 따른다.

| 플래그 | 뜻 |
|---|---|
| `--gui` | Isaac Sim 창을 띄운다. 빼면 headless (화면 캡처가 동작하지 않는다) |
| `--autoplay` | 기동 직후 165초 시나리오를 자동 재생한다 |
| `--low` | 저사양 PC 프리셋 — 해상도 1280×720, 입자 수·물리 서브스텝 절반 |
| `--max_s N` | N초 뒤 자동 종료 (캡처·측정용) |
| `--profile` | 구간별 소요 시간을 `logs/demo_integrated.json` 에 남긴다 |
| `--mode M` | `mechanical` / `electrical` / `integrated` 시작 모드 |
| `--record MP4` | ffmpeg 로 녹화하고 영상↔로그 오프셋을 기록한다 (경로는 상대 경로만) |
| `--no_timecode` | HUD 타임코드를 숨긴다 (발표용 녹화) |
| `--log_subdir D` | CSV·녹화 메타를 `logs/D/` 에 둔다 |
| `--switch_seq` | 모드 전환 잔상 검증용 (예: `electrical:62,mechanical:80`) |

Blender 가 떠 있으면 Isaac Sim 의 RTX 초기화가 실패한다. 한 번에 하나만 실행한다.

### 다른 데모

```powershell
C:\ISSACS~1\python.bat app\demo_thermal.py --gui             # 모듈 A 단독 (발열 색상)
C:\ISSACS~1\python.bat app\demo_current.py --gui --quick     # 모듈 B 단독 (전류 케이스 순환)
```

둘 다 `--xray` 로 하우징을 반투명하게 만들어 내부를 볼 수 있다. `demo_current.py --quick` 은
케이스당 12초로 단축하고, `demo_thermal.py --opaque` 는 결함 시에도 엔드실드를 불투명하게
유지한다.

## 제어 패널

왼쪽 `VIGENT - Control` 창에서 조작한다. omni.ui 기본 폰트에 한글 글리프가 없어 라벨은
영문이다.

- **MODE** — `Mechanical (heat)` / `Electrical (current)` / `Integrated`
- **LOAD / SPEED** — 부하율 0~150 %, 열 시뮬레이션 배속, 전류 파형 슬로모션
- **MECHANICAL FAULTS** — DE·NDE 베어링 결함, 축 정렬 불량, 냉각팬 고장, 브레이크 끌림, 과부하
- **ELECTRICAL CASE** — 정상, 턴간 단락 4·12턴, 전압 불평형, 결상, 무부하, 과부하 135 %
- **RESET** / **AUTO-PLAY SCENARIO**

자동 재생 중에는 시나리오가 상태를 결정하며, 체크박스도 따라 움직인다.

## 구조

엔진과 시각화를 갈라 놓았다. `engine/` 은 Isaac Sim 없이 도는 순수 파이썬이라 pytest 로
검증할 수 있고, USD 를 건드리는 코드는 `viz/` 에만 있다.

```
config/     모든 수치 (정격·임계값·색상·시나리오). 코드에 하드코딩하지 않는다
engine/     물리 모델 — Isaac Sim 비의존
  thermal_model.py      집중정수 열회로 9노드, RK4 적분
  current_model.py      3상 전류 파형, 대칭좌표법 I₂/I₁, ITSC 역산
  fault_injector.py     결함 주입, 진동 등급(모터 규격: M1 ISO 10816-1 Class I)
  scenario_player.py    자동 재생 타임라인
viz/        USD 시각화
  colormap.py           부품별 임계값 기준 정규화 컬러맵
  material_driver.py    prim 전용 OmniPBR 머티리얼 생성·갱신
  current_paths.py      케이블·권선·단락루프 곡선
  current_particles.py  전류 입자 (Points prim 1개)
  hud.py                발표용 HUD
ui/         제어 패널 (omni.ui)
app/        실행 진입점
tools/      USD 빌드, 캡처, 그래프
assets/     motor_parts.usd (부품 11개), motor_physics.usd (물리 API 포함)
tests/      pytest 56건
```

### 왜 부품별 USD 를 새로 만들었나

원래 모델링 산출 USD 는 메시가 2개로 병합돼 있었다. USD 의 `GeomSubset` 은 머티리얼 단위라
DE 베어링과 NDE 베어링을 따로 칠할 수 없었다. 파트별 OBJ 12개(`export/mesh/HM_*.obj`)가 남아
있어, 이것을 부품별 독립 prim 으로 갖는 시각화 전용 USD 를 새로 만들었다
([`tools/build_parts_usd.py`](tools/build_parts_usd.py) → [`tools/build_physics_usd.py`](tools/build_physics_usd.py)).

원본 에셋은 읽기 전용으로 취급하며 직접 수정하지 않는다.

## 테스트

`engine/` 과 `viz/colormap.py` 만 쓰므로 Isaac Sim 없이 돈다. 필요한 것은 numpy, PyYAML,
pytest 가 있는 파이썬이다.

Isaac Sim 번들 파이썬에는 numpy 와 PyYAML 이 이미 있고 pytest 만 없다.

```powershell
C:\ISSACS~1\python.bat -m pip install pytest
C:\ISSACS~1\python.bat -m pytest tests -q
```

Blender 5.2 를 설치했다면 그 번들 파이썬에는 셋 다 들어 있다.

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" -m pytest tests -q
```

56건이 통과해야 한다. 컬러맵 회귀 테스트가 들어 있는데, 로터 81.6 °C
(로터 기준으로는 정상)가 주황으로 보이던 문제 때문이다. 지금은 절대 온도가 아니라 부품별
허용 온도로 정규화해 색을 고른다.

## 성능

RTX 4060 기준 프레임당 실측값이다 (`--profile`).

| 구간 | 기본 (1600×900) | `--low` (1280×720) |
|---|---|---|
| 렌더링 | 8.93 | 8.60 |
| 물리 (PhysX 서브스텝 4 / 2) | 2.61 | 1.69 |
| 입자 (경로당 24 / 12개) | 0.85 | 0.62 |
| 전류·열·HUD·머티리얼 | 1.26 | 1.24 |
| **합계** | **13.66** | **12.15** |
| 평균 FPS | 68.9 | 74.4 |

60 fps 예산은 16.7 ms 다. 병목은 렌더링(65 %)이고 애플리케이션 코드는 4.7 ms 뿐이라 별도
최적화를 하지 않았다 — 엔진 계산은 전부 합쳐 0.25 ms 로 예산의 1.5 % 다.

`--low` 의 이득이 이 GPU 에서는 1.5 ms 로 작은데, 렌더링이 해상도가 아니라 장면 복잡도에
묶여 있기 때문이다. 내장 그래픽처럼 픽셀 처리량이 모자란 PC 에서는 해상도를 낮춘 만큼
렌더링 시간이 줄어들므로 효과가 더 크다.

## 녹화 (모드별)

```powershell
powershell -ExecutionPolicy Bypass -File tools\record_mode.ps1 -Mode mechanical   # 녹화 → 동기 검증 프레임 → 장면 클립
powershell -ExecutionPolicy Bypass -File tools\record_mode.ps1 -Mode electrical
powershell -ExecutionPolicy Bypass -File tools\publish_desktop.ps1                # 프로젝트 폴더\모터결함_애니메이션 (1_기계/2_전기/3_통합 + 해설 PDF) + MD5
```

영상은 `../dashboard/public/media/<mode>/`, 로그는 `logs/<mode>/` 에 남는다. 이미 찍은 영상으로
검증·클립만 다시 하려면 `-SkipRecord`. 녹화는 `gdigrab -i desktop` + 창 좌표 crop 만 동작한다
(`-i title=` 은 Vulkan 창이라 첫 프레임만 반복됨 — SESSION_LOG 9장).

## 모터 라이브러리 — 현재 등록 모터는 M1 한 대 (코드 경로는 유지)

**2026-10-21 결정**: 디지털트윈은 M1(현대 HLP-2.2/4) 한 대로 간다. 호이스트 4종 라이브러리(M2~M5, `source: representative`)는 만들지 않는다.
`config/motors/` 에는 `M1.yaml` 만 있고 M2~M5 는 `config/motors/_retired/` 에 보관한다(로더 `list_ids()` 가 읽지 않음, 삭제 금지, `_retired/README.md`).
`source` 는 `nameplate | catalog` 만 허용한다(`representative` 불허). 열회로 스케일 기준값(옛 M5 22 kW)은 `config/thermal.yaml reference` 절에 있다.
라이브러리 코드(`engine/motor_library.py`, run_fleet, 상태 보드 카드 목록)는 그대로라 실모터 명판이 확정되면 `config/motors/<id>.yaml` 한 장으로 다시 늘릴 수 있다 — 아래 예시는 그 스키마(이력).

```yaml
id: M6
name: "30톤 호이스트 권상 모터 (37 kW 6극)"
source: catalog                   # nameplate | catalog  — 상태 보드 출처 라벨이 바뀐다 (representative 는 2026-10-21 부터 불허)
rated_power_kw: 37
poles: 6
sync_rpm: 1200
rated_rpm: 1180
voltage_v: 380
frequency_hz: 60
connection: delta
efficiency: 0.90
power_factor: 0.83
rated_line_current_a: 75.0        # I = P / (√3·V·η·cosφ)
rated_phase_current_a: 43.3
frame: 225S
insulation_class: F
duty: "S3 40% ED"
bearing_de: "6313"
bearing_nde: "6313"
bearing_fault_multipliers: { bpfo: 3.6, bpfi: 5.4, source: estimated }
geometry_scale: 1.25              # M5(180L) = 1.0 기준 프레임(축 높이) 비례
thermal: { scale_rule: power_ratio }
vibration: { standard: "ISO 20816-3 Group 2", watch_mms: 1.4, plan_mms: 2.8, act_mms: 4.5 }   # < 15 kW 는 "ISO 10816-1 Class I" 1.8/4.5 (M1)
```

- 검증: `python -m pytest tests/test_motor_library.py -q` (필수 키·범위·파생값).
- 배치·비교표·대시보드 갱신: `python tools/run_fleet.py` → `python tools/fleet_summary.py` → `python ../dashboard/tools/export_status_data.py` → `cd ../dashboard && npm run build`.
- 데모 첫 화면 위치: `config/status_demo.yaml` 에 그 모터의 `{mode, t_s, expect}` 를 추가한다 (테스트가 기대 상태와 판정을 대조).
- 열회로 계수는 22 kW 기준값(`thermal.yaml reference`)을 출력비·프레임 비례로 스케일한다 (`docs/thermal_scaling.md`). 판정 임계값은 `config/thresholds.yaml` (모터 공통) + 모터 YAML 의 진동 규격.

## 모터별 애니메이션 녹화 (이력: M1~M5 → 현재 M1)

`python app/demo_integrated.py --gui --autoplay --mode mechanical --motor M1` — `--motor` 기본값이 M1 이고, M1 이면 전체 3D 모델(`assets/motors/M1/M1.usd`)이 자동으로 올라간다(`--no_m1_model` 이면 22 kW USD, 이력 비교용).
퇴역 모터는 `--motor M3` 처럼 불러도 로더가 거부한다. 22 kW 애니메이션 원본 영상·USD 는 지우지 않고 보관한다.
일괄 녹화: `powershell -ExecutionPolicy Bypass -File tools
ecord_fleet.ps1 [-Motors M1,M2 -Modes mechanical]` → `dashboard/public/media/fleet/`, 산출물 `모터결함_애니메이션/4_모터별/`. 녹화 중 화면을 비워야 한다.

## 상태 보드 (M1 단일)

`dashboard/run_dashboard_status.bat` 더블클릭 → `http://localhost:4173/#/status`. 첫 화면은 M1 카드 1장 + 상세 + 시나리오 재생 바(`config/status_demo.yaml scene_map` 칩: 정상·4턴 경계·12턴 위험·DE 베어링·과부하) + 원인·조치.
5장 카드 레이아웃 코드는 남아 있고 모터가 하나면 자동으로 1장이 된다. Space 재생, ←→ 장면, M 기계/전기, F 발표.
데이터는 `logs/fleet`(엔진 배치) 와 config 에서만 온다. 자세한 것은 `dashboard/README.md`, 결과 요약은 `docs/m1_summary.md`(5종 비교표 `docs/fleet_summary.md` 는 이력).

베어링 지표(2026-10-08): 주 **kurtosis**(경고 3.5 / 위험 4.0, 모터 공통) + 보조 **고주파 대역 RMS 배율**(경고 1.5 / 위험 2.5, 기준선은 `config/motors/<id>.yaml bearing_hf_baseline`), 종합은 둘 중 나쁜 쪽. 포락선 BPFO/BPFI 는 판정 제외(결함 부위 추정 표시만). 시뮬레이션은 `config/thermal.yaml` 의 결함별 등가값 — 정의·근거 `docs/bearing_metric_definition.md`, 전후 비교 `docs/bearing_metric_change_comparison.md` (`python tools/fleet_compare.py`).

## 라이브 모드 — Isaac Sim ↔ 대시보드 실시간 연동 (R1: Isaac 쪽 LiveBridge)

녹화 모드는 그대로 남고, `--live` 를 주면 Isaac Sim 안에서 WebSocket 브리지(`app/live_bridge.py`, 설정 `config/live.yaml`)가
별도 스레드로 떠서 state 를 10 Hz 로 보내고 명령(결함 주입·부하·배속·모드·시나리오·리셋)을 받는다. `--live` 가 없으면 기존 동작과 완전히 같다.
판정은 한 곳(`engine/thresholds.py Judge`)에서만: HUD 색·CSV 끝 4열(`status, cause_signal, cause_component, cause_value`)·라이브 state 의 `status` 가 모두 같은 결과다
(열 모델 4단계 normal/caution/warning/danger 는 HUD 괄호 안 세부 라벨로만 남는다). 정의·스키마는 `docs/live_r0_report.md` §5, 실측은 `docs/live_r1_report.md`.

```bat
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode mechanical --live            # 콘솔에 ws://<IP>:8765 와 대시보드 주소가 찍힌다
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --mode integrated --live --motor M1 --preset demo   # 발표용: 1280×720 RTX Real-Time, 물리 서브스텝 2, 입자 12, 뷰포트 1개 (config/render_demo.yaml). 등록 모터는 M1 하나
```

HUD 에 `LIVE ws://<데스크탑 IP>:8765  clients N` 과 `STATUS <등급> <원인>` 행이 보인다. 간단 확인(아무 PC, websockets 설치된 파이썬):
`python tools/r0_proto/ws_client.py ws://<데스크탑 IP>:8765 10` → 10 s 동안 수신 건수·지연을 찍는다.
명령 예: `{"type":"command","id":"1","name":"inject_fault","args":{"fault":"bearing","on":true}}` → `{"type":"ack","id":"1","ok":true,"applied":{...}}`.
허용 목록·범위 밖은 `ok:false` 와 이유가 온다 (`config/live.yaml commands`). 시나리오 재생 중에는 결함 주입을 거부하므로 `stop_scenario` 를 먼저 보낸다.

### 대시보드에서 LIVE 켜기 (R2)

세 화면(`#/status`, `#/mechanical`, `#/electrical`) 상단의 **녹화 / LIVE** 스위치. LIVE 를 누르면 주소 입력(기본 `ws://localhost:8765`, 맥북이면 `ws://<데스크탑 IP>:8765`, 마지막 값 기억) → 연결되면 초록 `LIVE · M1 · n명` 뱃지.
주소로 바로 켜기: `http://<데스크탑 IP>:4173/#/status?live=ws://<데스크탑 IP>:8765`. 스트림이 3 s 끊기면 **자동으로 녹화 재생**으로 돌아가고 노란 띠("라이브 연결 끊김 — 녹화 재생 중")가 뜬다. 다시 붙으면 저절로 LIVE 복귀.
라이브에서 재생 바는 "최근 5 분" 창(`dashboard/public/content/live.yaml window_s`), `❚❚ 최근 기록 보기`로 버퍼 안을 돌려보고 `▶ LIVE 복귀`. ←/→·챕터 클릭은 Isaac 에 `play_scenario` 명령을 보낸다. 영상 자리는 "Isaac Sim 창을 보세요"(듀얼 모니터용). 자세한 것은 `docs/live_r2_report.md`.

### 제어 패널 — 대시보드에서 Isaac 조작 (R3, L2)

LIVE 상태에서 상단 `☐ 제어 K` 버튼 또는 **K** 키(주소에 `&ctl=1` 이면 열린 채 시작). 결함 토글(열 결함 6 · 전류 케이스 6, 모드에 맞는 것만), 부하 0~150 %, 시간 배속 1~600, 슬로모션 1/1~240, 모드(기계/전기/통합), 시나리오 재생·장면 번호·정지, 리셋, **모터 선택**(목록은 Isaac 의 `hello.motors` = 라이브러리 등록 모터, 현재 M1 하나).
버튼 상태는 내가 누른 값이 아니라 Isaac 이 적용해 state 로 돌려준 값으로 확정되고, 거부되면 "최근 명령"에 이유가 뜬다(예: 시나리오 재생 중 결함 주입 → `stop_scenario` 먼저). 허용 목록·범위는 Isaac 이 접속 직후 보내는 `hello`(= `config/live.yaml commands`)에서 온다.
**모터 전환**: 기본은 **핫 스위치**(`config/live.yaml select_motor.switch_mode: hot`) — Isaac 프로세스 안에서 모터 라이브러리의 열회로·전류 모델·판정·정격·카메라 거리·HUD 문구만 새 모터로 재생성한다(USD·Isaac 재로드 없음, 1 s 미만). 대시보드 띠는 최소 `switch_banner_min_s`(10 s) 동안 "왜 바뀌는지 + 무엇을 비교할지"(문구는 `dashboard/public/content/live.yaml switch_*`)를 보여준다. `switch_mode: restart` 로 두면 R3 방식(현재 모터 정리 → 같은 인자로 재기동, 45~130 s, 로그 `logs/live_restart_<모터>.log`). 실측은 `docs/live_r3_report.md`·`live_r4_report.md`.
데모 대본 `docs/live_demo_script.md`(5단계), 자동 구동 `tools/live_demo_drive.py`, 녹화 `tools/record_live_demo.ps1`(화면을 비워야 한다).

### 아이작심 컨트롤 패널 Q1 — 전기 결함 전용 · 모드 제거 · 실시간 수동 조작 (2026-10-27, `v1.1-panel-q1`)

`demo_integrated.py` 는 **전기 전용**이다(`--mode` 는 `electrical` 외 값이면 경고 뒤 강제; 기계·통합 모드 코드는 `_legacy/app/demo_integrated_modes.py`). 아이작심 창 안의 옛 "VIGENT - Control" 패널(모드 선택·열 결함 토글) 대신
**"VIGENT 전기 결함 조작"** 패널(`ui/fault_control_window.py`)이 뜬다: 결함 상/코일(USD 코일 프림 이름, 표시 R·S·T) · 단락 턴수 0~32(LUT 격자) · 접촉 저항(0.03/0.1/0.3/1.0 Ω) · 전압 불평형(config 케이스 켜기/끄기) · [적용]/[정상으로] · 즉시 반영 체크 · 실시간 판정(읽기 전용, state 값) · 보기(반투명/절단/권선만) · 송출 설정(런타임).
값은 `/World/VigentFaultController` 의 USD 속성(`vigent:*`)으로 가고, 메인 루프가 2 Hz 로 읽어 시나리오와 같은 주입 경로(`DemoState.electrical_case` ← 런타임 케이스 `manual_itsc`)로 엔진 케이스를 바꾼다(`app/fault_controller.py`). 패널을 만지면 시나리오는 자동 정지(`control_source: manual`), 대시보드 시나리오 ▾ 를 고르면 복귀.
한글 라벨은 PIL 비트맵(`ui/ko_text.py`) — omni.ui 에 한글 글리프가 없다(실측). 측정·스크린샷: `--panel_selftest N [--panel_selftest_hold s] [--panel_burst]` → `logs/<subdir>/panel_selftest.json`·`panel_burst.json`; 창 캡처 `tools/live/window_shot.py`, state 한 건 `tools/live/state_snapshot.py`. 문서 `docs/isaac_panel_q1.md`.

### 레이아웃 A — 실시간 전용 전기 상태 보드 + 뷰포트 스트림 (2026-10-27)

대시보드(`#/status`)는 이제 **실시간 전용·전기 해석 전용** 한 화면이다: 헤더(LIVE 뱃지·시나리오 ▾) → 상태 띠 → 2×2[아이작심 실시간 | 전류 파형 / 전류 성분 | 추세] → 왜·무엇을 한 줄 → 근거 서랍(근거·임계값·사양·용어 탭).
녹화/LIVE 토글·전문가 보기·기계 해설·발표 모드(F)·제어 패널(K)·단축키는 UI 에서 뺐다(코드는 `dashboard/src/_legacy/`, 빌드 제외 — 삭제 아님). 위 R2·R3 절의 토글·패널 설명은 이력이다.

```bat
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --motor M1 --live --preset demo --cam side --judge_stream simulation   # state 8765 + 뷰포트 JPEG 스트림 8766 (--live 면 스트림 기본 켜짐, --no_stream 으로 끔). 전기 전용 — --mode 불필요
cd ..\dashboard && node serve.cjs                                                                                            # http://localhost:4173/#/status  (다른 PC: ?live=ws://<데스크탑 IP>:8765)
```

- 스트림: `viz/stream_viewport.py` — `omni.kit.viewport.utility.capture_viewport_to_buffer`(RGBA readback, 추가 렌더 없음) → 인코더 스레드(cv2 JPEG q80, 1280×720) → WebSocket 바이너리(32 B 헤더 + JPEG) 를 `config/live.yaml server.stream_port`(8766, **127.0.0.1 바인딩**, 인증 없음 → 방화벽 열지 않음)로. 클라이언트가 없으면 캡처하지 않는다. 인자 `--stream_fps 30 --stream_size 1280 720 --stream_quality 80`, `--view`(스트림 때 기본 `half_translucent`), `--cam side`(카메라 프리셋).
- state(8765)에 덧붙인 필드: `sym_components_A{i1_A,i2_A,i0_A}`·`waveform_last_2cycles`(`app/live_signals.py`, export `case_signals` 와 같은 식), `perf.stream`, hello 의 `stream_ws`·`stream`·`scenes`(시나리오 ▾ = `play_scenario {scene:n}`).
- 측정: `py -3.12 -X utf8 tools/live/stream_probe.py --seconds 600 --out logs/stream_probe.json`(스트림 fps·지연 = 수신 − 캡처 벽시계, Isaac fps·encode/capture ms). 결과·화면은 `docs/dashboard_layout_a.md`.

### 다른 기기(맥북, 같은 Wi-Fi)에서 접속 — 윈도우 방화벽 인바운드 규칙

1. 데스크탑 IP 확인: HUD 의 `LIVE ws://…` 또는 `ipconfig`(이더넷/Wi-Fi 의 IPv4). 맥북은 같은 공유기에 붙어 있어야 한다(같은 서브넷).
2. 네트워크 프로필이 **개인(Private)** 인지 확인: 설정 → 네트워크 및 인터넷 → 이더넷(또는 Wi-Fi) → 네트워크 프로필 → "개인 네트워크". 공용이면 아래 규칙이 적용되지 않는다(공용 Wi-Fi 에서는 열지 않는다).
3. 규칙 추가 — 관리자 PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File toolsirewall_rules.ps1          # TCP 8765(WebSocket)·4173(대시보드) 인바운드 허용, 개인·도메인 프로필
   powershell -ExecutionPolicy Bypass -File toolsirewall_rules.ps1 -Show    # 확인   /  -Remove 제거
   ```
   GUI 로 하려면: Windows 보안 → 방화벽 및 네트워크 보호 → 고급 설정 → 인바운드 규칙 → 새 규칙 → 포트 → TCP, 특정 로컬 포트 `8765, 4173` → 연결 허용 → 프로필 "개인·도메인"만 체크 → 이름 `VIGENT Live`.
4. 대시보드 서버는 `dashboard/serve.cjs`(0.0.0.0:4173). 맥북 브라우저에서 `http://<데스크탑 IP>:4173/#/status?live=ws://<데스크탑 IP>:8765` (대시보드 쪽 LiveSource 는 R2).
5. 안 되면: 데스크탑에서 `netstat -an | findstr 8765` 로 LISTENING 확인 → 맥북에서 `nc -vz <IP> 8765` → 막히면 2·3번(프로필·규칙), 공유기의 "AP 격리/클라이언트 격리" 옵션 해제.

## AI Hub 실측 데이터 (전체 데이터 도착 후 실행 순서)

1. 다운로드: `AIHUB_API_KEY=<AI Hub 마이페이지 API 키> bash tools/aihub/download_full.sh` → 저장소 밖 `../aihub_full/` (진동 Training 78 GB + Validation 10 GB; 전류까지는 `AIHUB_FILEKEYS=44889,44890,44891,44815`). 파일 트리만 보려면 `--list`.
2. D0: `python -I tools/aihub/run_pipeline.py list --zip <a.zip.part1>` — 병합 없이 목록·선별 패턴(`config/aihub_select.yaml`)·`docs/aihub_selection.md`. 패턴 확인 후
3. D1+D2: `python -I tools/aihub/run_pipeline.py extract --zip <a.zip.part1>` — 단위별 추출 → Parquet(L2/full) → 검증 → L1 삭제 (6.9 ms/파일, CSV ×0.4~0.5). 이어서 `sample` (균형 샘플링).
4. D3: `python -I -X utf8 tools/aihub/run_pipeline.py features --workers 4` → `<DATA>/L3/features.parquet`(37.7만 파일 20분), `docs/aihub_feature_summary.md`, `docs/aihub_plots/`.
   산출물 폴더 `<DATA>` 는 `VIGENT_AIHUB_DATA`(기본 `C:\vigent_data\aihub`, OneDrive 밖). 잘린 zip(중앙 디렉터리 없음)도 `ScanZip` 이 순차 스캔으로 읽는다.
5. 검증: `pytest tests/test_aihub.py tests/test_aihub_convert.py tests/test_aihub_features.py -q`. 임계값 보정은 별도 지시로 — 샘플 수치(`docs/aihub_sample_summary.md`)는 참고용.

## 기록

실행하면 `logs/demo_<날짜>.csv` 에 매 프레임이 남는다 — 온도 9노드, 3상 RMS, I₂/I₁, 진동,
ISO 존, FPS. 발표 후 수치를 되짚거나 그래프를 그릴 때 쓴다.

## 모델의 한계

발표에서 질문이 나올 수 있는 단순화다.

- 턴간 단락(ITSC)은 실제로는 단락 루프의 순환 전류가 지배하고 선전류 불평형은 더 작다. 이
  MVP 는 화면에 목표 I₂/I₁ 을 재현하기 위해 크기 불평형으로 등가 표현했다.
- 전류는 해석식 모델이다. Maxwell 2D 전자계 해석 결과를 쓰지 않았다 (AEDT 라이선스 부재).
- **(2026-10-17) M1 의 ITSC 전류 신호는 등가회로 LUT 로 바꿨다**: `config/electrical.yaml` `method: lut` (되돌리기 `legacy`), LUT `data/electrical/M1_mccm_lut_v1.json`
  (RMxprt v2 + 다중결합 회로, FEM 미검증 provisional — 4턴 I₂/I₁ 0.071, 12턴 0.264, 고유 비대칭 0.027 포함). 가져오기 `py -3.12 tools/electrical/import_lut.py`,
  검증 `py -3.12 tools/electrical/verify_lut_integration.py` → `docs/electrical/lut_integration_report.md`. 근거·제안은 `docs/judgment_basis.md`. 다른 모터는 legacy 그대로.
- 열 모델은 집중정수 9노드다. 국부 열점(hot spot)은 표현하지 못한다. 부품 하나는 한 가지
  색으로 칠하며, 부품 안에서 온도가 번지는 그라디언트를 쓰지 않았다. 노드가 부품당 하나뿐이라
  그라디언트를 그리면 모델에 없는 분포를 화면이 지어내는 셈이 되고, 그건 추정값을 측정값처럼
  보이게 만드는 일이다.
- 케이블은 선전류, 권선은 상전류 기준이고 두 기준은 `config/motor.yaml` 에 나눠 두었다. M1 은 Y결선(카탈로그 기준, 현장 확인)이라 둘 다 정격 4.73 A 로 같다
  (이전 기준 22 kW Δ결선은 선 43.7 A / 상 25.2 A — 이력).

## M1 전체 3D 모델 (100L 하우징 + 내부) — P4, 2026-10-21

1. `py -3.12 -X utf8 tools/cad/datasheet_to_yaml.py && py -3.12 -X utf8 tools/cad/build_internals_M1.py && py -3.12 -X utf8 tools/cad/build_housing_100L.py` (저장소 루트, CadQuery) → `assets/motors/M1/*.step|.obj|.glb`
2. `py -3.12 -X utf8 -m pytest tests/test_m1_model.py -q` → `py -3.12 -X utf8 tools/cad/write_model_doc.py` (`docs/assets/M1_model.md`)
3. `C:\ISSACS~1\python.bat tools\cad\build_usd_M1.py` (USD 반입·조립) → `cd motor_dt_viz ; C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode electrical --motor M1 --m1_model [--view cutaway]`

## 단일 모터 M1 전환 (P2′, 2026-10-21)

- 설정: `config/motors/M1.yaml`(catalog) 하나, `config/motor.yaml` = M1 값(`library_default: M1`), 퇴역 `config/motors/_retired/`(M2~M5 + 옛 motor.yaml 사본 `motor_M5_reference.yaml`), `config/thermal.yaml reference`(22 kW 기준 손실 2,444 W·scale 1.0 — 튜닝 계수 불변), `config/status_demo.yaml scene_map`.
- 진동 규격: < 15 kW 는 ISO 10816-1 Class I(경고 1.8 / 위험 4.5 mm/s, `engine/motor_library.VIB_STANDARD_SPLIT_KW`). `thresholds.yaml` 의 숫자·판정 규칙·LUT 는 바꾸지 않았다.
- Isaac: `C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode mechanical|integrated|electrical --motor M1 [--m1_shots DIR] [--record logs\x.mp4]` — 기계 7 장면·통합 5 장면의 M1 자막은 `config/scenarios_M1.yaml`(장면·배속·결함은 공용 파일과 동일), 시각 매핑은 `assets/motors/M1/prim_map_M1.yaml`(베어링 `/M1/Bearings/DE·NDE`, 축 `/M1/Rotor/Shaft`, 팬 커버 `/M1/Housing/FanCover`, 프레임 `/M1/Housing/Frame`). 22 kW 기하 전용 전류 경로·입자는 M1 장면에서 숨긴다.
- 문서: `docs/m1_summary.md`(배치 요약), `docs/m1_migration_notes.md`(해설 PDF·가이드라인·센서 가이드·구매 목록에서 바꿀 문장 목록 — 본문은 미수정), `docs/thermal_scaling.md`·`docs/judgment_basis.md` §6.
- 검증: `py -3.12 -X utf8 -m pytest tests -q`(128 passed) · `py -3.12 tools/electrical/verify_lut_integration.py`.

## 실측 기준선 (P1, 2026-10-21)

- `py -3.12 -X utf8 tools/baseline_capture.py --motor M1 --tag SITE_<날짜> --csv <3상 전류 CSV: t,ia,ib,ic[,va,vb,vc]> --fs 2000` → `config/baselines/M1_SITE_<날짜>.yaml` + thresholds.yaml 반영 제안(diff) 출력. 품질 게이트(창 ≥ 500, I₁ 변동계수 ≤ 10 %) 통과 시 사람이 `current.negative_sequence.baseline`·`mode: baseline_multiple` 로 옮긴다(자동 반영 없음).
- 참고 데이터셋: `--grade reference --aihub-dir "<AI Hub current/2.2kW/L-SF-04/정상>" --tag AIHUB_LSF04_REFERENCE --apply-reference` → `reference_baseline.value`(p95)만 기록(판정 기준 아님).

## 시뮬 ↔ 해석 대조 검증 (V0~V6, 2026-10-21)

`docs/verification/sim_vs_analysis_report.md` — Isaac Sim 전기 결함 시나리오의 표시값이 해석 결과(RMxprt v2m2 → MCCM/LUT v2 → 2D FEM)에서 어떻게 나왔는지 수치 대조·근거 사슬로 보이는 보고서. 수기 숫자 없음.

1. 해석 근거값: `py -3.12 -X utf8 tools/verify/build_analysis_reference.py` → `data/electrical/analysis_reference.json`(+ dashboard public 사본, 입력 sha 포함; Maxwell 저장소 읽기 전용) · `py -3.12 -X utf8 tools/verify/traceability.py` → `docs/verification/traceability.{json,md}`
2. 배치(PowerShell/cmd): `C:\ISSACS~1\python.bat app\demo_integrated.py --autoplay --mode electrical --motor M1 --inherent_angle_deg 0 --verify_dir logs\verify\electrical_a0 --max_s 250` (각도 0/90/180), 열 `--mode integrated --scenario_yaml tools\verify\scenario_itsc_4turn_thermal.yaml --verify_dir logs\verify\thermal_itsc_4turn --max_s 222` (4/12/16). `--verify_dir` 는 로깅 훅(state.csv 10 Hz·events.csv·waveform 1 s 2 kHz·meta.json)만 추가하고 값은 기존 엔진이다.
3. 대조·그림·보고서: `py -3.12 -X utf8 tools/verify/sim_vs_analysis.py` → `docs/verification/sim_vs_analysis.{json,md,xlsx}` + `img/` · HUD 합성 `tools/verify/hud_composite.py --shots logs/verify/hud_raw --state logs/verify/hud_shots/state.csv` · `py -3.12 -X utf8 tools/verify/write_report.py`
4. 실시간 패널: 상태 보드 `④ 해석 근거 비교`(`dashboard/src/status/AnalysisRef.tsx` — 1단계 산출물을 읽는다, `npm run build`), Isaac HUD `ref:` 한 줄. 기계 시나리오는 "Maxwell 근거 없음".
- 독립 재계산 `tools/verify/recompute_i2i1.py <waveform.csv>` 는 엔진을 import 하지 않는다. 테스트 `tests/test_verify_tools.py`.

## 재현·릴리스·검증 요약 (D, 2026-10-21)

- 깨끗한 clone 에서 끝까지 도는 순서·예상 시간·실패 시 확인: `../docs/REPRODUCE.md`. Maxwell 저장소 위치는 환경변수 `MAXWELL_ROOT`.
- 변경 이력 `../CHANGELOG.md`(`tools/docs/changelog_from_log.py` 가 SESSION_LOG 장 제목 + git log 에서 생성), 태그 `v1.0-m1`(두 저장소), 환경 함정 `../CLAUDE.md`.
- 발표·문서가 인용할 단 하나의 검증 요약: `../docs/verification_summary.md`(+ `.json`, `tools/docs/verification_summary.py` — 수기 숫자 없음).
- HUD 합성 스크린샷 10장(Isaac 캡처에는 HUD 가 안 찍힘): `tools/viz/shot_with_hud.py all` → `../docs/assets/screenshots/M1_hud/` + 캡션(`captions.json`, `*.txt`).
- 산출 문서 4종 M1 갱신(E)은 원본이 `../docs/deliverables/_v22kW/` 에 들어오면 `../docs/deliverables/README.md` 절차대로.
- 해설 대시보드(기계·전기 해설 화면) 데이터는 `py -3.12 -X utf8 ../dashboard/tools/export_dashboard_data.py --source fleet --mode all` 로 M1 배치 로그에서 만든다(영상 없음, 재실행·재계산 검증 포함; 테스트 `tests/test_dashboard_fleet_export.py`). 22 kW 녹화 기반 동결본은 `../docs/deliverables/_v22kW/dashboard_data_22kW/`.
- 저전류 판정 규칙(2026-10-21 승인): 세 상이 함께 r < 0.50 이고 균형(불평형 < 0.05)이며 I₂/I₁ < 0.05 면 '경부하(참고)' advisory — `config/thresholds.yaml current_ratio.low_current_policy`, 전후 표 `../docs/verification/light_load_rule.md`.
- AI Hub 샘플 창별 정상성 게이트 분포표: `py -3.12 -X utf8 tools/aihub/baseline_table.py` → `docs/aihub_baseline_gated.md`(`baseline_capture.py --gate-*` 와 같은 규칙).
