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

## 상태 보드 (모터 5종)

`dashboard/run_dashboard_status.bat` 더블클릭 → `http://localhost:4173/#/status`. 키 1~5 모터, Space 재생, ←→ 장면, M 기계/전기, F 발표.
데이터는 `logs/fleet`(엔진 배치) 와 config 에서만 온다. 자세한 것은 `dashboard/README.md`, 결과 비교표는 `docs/fleet_summary.md`.

## AI Hub 실측 데이터 (전체 데이터 도착 후 실행 순서)

1. 분할 원본은 외장 드라이브의 별도 폴더에 두고 설명서 PDF 2종을 `data/aihub/docs/` 에 넣는다 (`docs/aihub_structure.md` 의 "설명서에 없음" 보강).
2. `TASK_AIHub_데이터선별` D0: 목록·패턴 (`config/aihub_select.yaml`) → 승인 → D1 선별 추출(용량·라벨 단위).
3. 변환: `python -I tools/aihub/convert_parquet.py --src <L1 단위 폴더> --out data/aihub/L2 --verify 20` (6.9 ms/파일, CSV ×0.40).
4. 특징: `python -I tools/aihub/extract_features.py --l2 data/aihub/L2 --l3 data/aihub/L3` → `docs/aihub_feature_summary.md` (5.4 ms/파일).
5. 검증: `pytest tests/test_aihub_convert.py tests/test_aihub_features.py -q`. 임계값 보정은 별도 지시로 — 샘플 수치(`docs/aihub_sample_summary.md`)는 참고용.

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
