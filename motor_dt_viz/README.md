# 크레인 권상 모터 디지털 트윈 — 결함 시각화 MVP

22 kW 6극 천장크레인 권상 모터(도면 JW-01-HTO-00)의 결함을 Isaac Sim 화면에서 보여주는
데모다. 심사위원이 설명 없이 화면만 보고 **어디서, 왜 고장이 나는지** 알아보게 하는 것이
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
  fault_injector.py     결함 주입, ISO 20816-3 진동 등급
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

## 모터 라이브러리 — 모터 추가는 YAML 한 장

`config/motors/<id>.yaml` 을 한 장 더 만들면 라이브러리·배치·상태 보드가 그 모터를 자동으로 포함한다 (스키마는 `M3.yaml` 을 복사해 수정).

```yaml
id: M6
name: "30톤 호이스트 권상 모터 (37 kW 6극)"
source: representative            # nameplate | representative  — 상태 보드 출처 라벨이 바뀐다
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
vibration: { standard: "ISO 20816-3 Group 2", watch_mms: 1.4, plan_mms: 2.8, act_mms: 4.5 }
```

- 검증: `python -m pytest tests/test_motor_library.py -q` (필수 키·범위·파생값).
- 배치·비교표·대시보드 갱신: `python tools/run_fleet.py` → `python tools/fleet_summary.py` → `python ../dashboard/tools/export_status_data.py` → `cd ../dashboard && npm run build`.
- 데모 첫 화면 위치: `config/status_demo.yaml` 에 그 모터의 `{mode, t_s, expect}` 를 추가한다 (테스트가 기대 상태와 판정을 대조).
- 열회로 계수는 M5 보정값을 출력비·프레임 비례로 스케일한다 (`docs/thermal_scaling.md`). 판정 임계값은 `config/thresholds.yaml` (모터 공통) + 모터 YAML 의 진동 규격.

## 모터별 애니메이션 녹화 (M1~M5)

`python app/demo_integrated.py --gui --autoplay --mode mechanical --motor M3` 처럼 `--motor` 를 주면 그 모터의 열회로·전류·진동 규격·HUD 로 돌고, 외형은 카메라 거리로 프레임 비례 크기가 된다.
일괄 녹화: `powershell -ExecutionPolicy Bypass -File tools
ecord_fleet.ps1 [-Motors M1,M2 -Modes mechanical]` → `dashboard/public/media/fleet/`, 산출물 `모터결함_애니메이션/4_모터별/`. 녹화 중 화면을 비워야 한다.

## 상태 보드 (모터 5종)

`dashboard/run_dashboard_status.bat` 더블클릭 → `http://localhost:4173/#/status`. 키 1~5 모터, Space 재생, ←→ 장면, M 기계/전기, F 발표.
데이터는 `logs/fleet`(엔진 배치) 와 config 에서만 온다. 자세한 것은 `dashboard/README.md`, 결과 비교표는 `docs/fleet_summary.md`.

베어링 지표(2026-10-08): 주 **kurtosis**(경고 3.5 / 위험 4.0, 모터 공통) + 보조 **고주파 대역 RMS 배율**(경고 1.5 / 위험 2.5, 기준선은 `config/motors/<id>.yaml bearing_hf_baseline`), 종합은 둘 중 나쁜 쪽. 포락선 BPFO/BPFI 는 판정 제외(결함 부위 추정 표시만). 시뮬레이션은 `config/thermal.yaml` 의 결함별 등가값 — 정의·근거 `docs/bearing_metric_definition.md`, 전후 비교 `docs/bearing_metric_change_comparison.md` (`python tools/fleet_compare.py`).

## 라이브 모드 — Isaac Sim ↔ 대시보드 실시간 연동 (R1: Isaac 쪽 LiveBridge)

녹화 모드는 그대로 남고, `--live` 를 주면 Isaac Sim 안에서 WebSocket 브리지(`app/live_bridge.py`, 설정 `config/live.yaml`)가
별도 스레드로 떠서 state 를 10 Hz 로 보내고 명령(결함 주입·부하·배속·모드·시나리오·리셋)을 받는다. `--live` 가 없으면 기존 동작과 완전히 같다.
판정은 한 곳(`engine/thresholds.py Judge`)에서만: HUD 색·CSV 끝 4열(`status, cause_signal, cause_component, cause_value`)·라이브 state 의 `status` 가 모두 같은 결과다
(열 모델 4단계 normal/caution/warning/danger 는 HUD 괄호 안 세부 라벨로만 남는다). 정의·스키마는 `docs/live_r0_report.md` §5, 실측은 `docs/live_r1_report.md`.

```bat
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --autoplay --mode mechanical --live            # 콘솔에 ws://<IP>:8765 와 대시보드 주소가 찍힌다
C:\ISSACS~1\python.bat app\demo_integrated.py --gui --mode mechanical --live --motor M3            # 모터는 기동 시에만 고른다 (select_motor 명령은 "재시작 필요" 로 거부)
```

HUD 에 `LIVE ws://<데스크탑 IP>:8765  clients N` 과 `STATUS <등급> <원인>` 행이 보인다. 간단 확인(아무 PC, websockets 설치된 파이썬):
`python tools/r0_proto/ws_client.py ws://<데스크탑 IP>:8765 10` → 10 s 동안 수신 건수·지연을 찍는다.
명령 예: `{"type":"command","id":"1","name":"inject_fault","args":{"fault":"bearing","on":true}}` → `{"type":"ack","id":"1","ok":true,"applied":{...}}`.
허용 목록·범위 밖은 `ok:false` 와 이유가 온다 (`config/live.yaml commands`). 시나리오 재생 중에는 결함 주입을 거부하므로 `stop_scenario` 를 먼저 보낸다.

### 대시보드에서 LIVE 켜기 (R2)

세 화면(`#/status`, `#/mechanical`, `#/electrical`) 상단의 **녹화 / LIVE** 스위치. LIVE 를 누르면 주소 입력(기본 `ws://localhost:8765`, 맥북이면 `ws://<데스크탑 IP>:8765`, 마지막 값 기억) → 연결되면 초록 `LIVE · M5 · n명` 뱃지.
주소로 바로 켜기: `http://<데스크탑 IP>:4173/#/status?live=ws://<데스크탑 IP>:8765`. 스트림이 3 s 끊기면 **자동으로 녹화 재생**으로 돌아가고 노란 띠("라이브 연결 끊김 — 녹화 재생 중")가 뜬다. 다시 붙으면 저절로 LIVE 복귀.
라이브에서 재생 바는 "최근 5 분" 창(`dashboard/public/content/live.yaml window_s`), `❚❚ 최근 기록 보기`로 버퍼 안을 돌려보고 `▶ LIVE 복귀`. ←/→·챕터 클릭은 Isaac 에 `play_scenario` 명령을 보낸다. 영상 자리는 "Isaac Sim 창을 보세요"(듀얼 모니터용). 자세한 것은 `docs/live_r2_report.md`.

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
- 열 모델은 집중정수 9노드다. 국부 열점(hot spot)은 표현하지 못한다. 부품 하나는 한 가지
  색으로 칠하며, 부품 안에서 온도가 번지는 그라디언트를 쓰지 않았다. 노드가 부품당 하나뿐이라
  그라디언트를 그리면 모델에 없는 분포를 화면이 지어내는 셈이 되고, 그건 추정값을 측정값처럼
  보이게 만드는 일이다.
- Δ결선이라 케이블은 선전류(정격 43.7 A), 권선은 상전류(정격 25.2 A) 기준이다. 두 기준을
  섞지 않도록 `config/motor.yaml` 에 나눠 두었다.
