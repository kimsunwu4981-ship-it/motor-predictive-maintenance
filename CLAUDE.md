# 크레인 권상 모터 디지털 트윈 (DT / Isaac Sim 저장소) — 작업 규칙

> 대화는 한국어. 이 파일은 **환경 함정과 경계**만 적는다. 작업 이력은 `SESSION_LOG.md`(장 번호), 실행 순서는 `motor_dt_viz/README.md`, 깨끗한 복제본 재현은 `docs/REPRODUCE.md`, 변경 이력은 `CHANGELOG.md`.

## 상태 (2026-10-21, 태그 `v1.0-m1`)
- 트윈은 **현대 HLP-2.2/4(M1) 단일 모터** 기준. 모터 라이브러리 코드 경로는 남아 있고 M2~M5 YAML 은 `motor_dt_viz/config/motors/_retired/`(로더 무시, 삭제 금지).
- 해석 근거: RMxprt v2m2 → MCCM/LUT v2 → 2D 와전류 FEM lite(학생판) 정합. 정본 요약은 `docs/verification_summary.md`, 대조 보고서는 `docs/verification/sim_vs_analysis_report.md`.

## 두 저장소 경계
- Maxwell 저장소 `C:\Users\sunwu\OneDrive\바탕 화면\모터\권상모터_3D모델링`(github `hoist-motor-maxwell`)은 **읽기 전용**. 위치는 환경변수 `MAXWELL_ROOT` 로 바꿀 수 있다(`import_lut.py`, `verify_lut_integration.py`, `build_analysis_reference.py`, `datasheet_to_yaml.py`).
- M1 입력 복사본 `assets/motors/M1/inputs/`(datasheet_v4.yaml·geometry_check_v2.json·rmxprt_v2m2.json·PROVENANCE.md)가 **DT 쪽 입력 정본**이다. 카탈로그 PDF 는 Maxwell `docs/sources/`(gitignore)에만 있으므로 PDF 없이 `datasheet_to_yaml.py` 를 돌려 `datasheet_v4.yaml` 을 덮어쓰지 말 것.
- 금지(승인 없이): `config/thresholds.yaml` 숫자, `config/motors/M1.yaml`, `config/electrical.yaml`, LUT(`data/electrical/*.json`), 판정 코드(`engine/thresholds.py`)·엔진 수치, 포트·방화벽(`config/live.yaml`), AI Hub 키.

## 환경 함정 (실측)
- **Isaac Sim 4.5**: `C:\ISSACS~1\python.bat`(8.3 경로, 공백 때문). `.bat` 에는 **상대 경로만**. 실행은 **PowerShell/cmd 에서** — Git Bash 에서 띄운 자식 Isaac 프로세스(예: `verify_lut_integration.py` V7)는 "Startup Complete" 직후 로그 없이 죽는다(7/8 로 보임).
- Isaac 뷰포트 캡처(`capture_viewport_to_file`)에는 **omni.ui HUD 가 찍히지 않는다** → HUD 가 필요한 스크린샷은 `motor_dt_viz/tools/viz/shot_with_hud.py`(뷰포트 + 같은 시각 `state.csv` 값 합성)로 만든다. 10장 정본은 `docs/assets/screenshots/M1_hud/`.
- Blender 가 떠 있으면 Isaac RTX 초기화가 실패한다. Isaac 두 인스턴스 동시 실행도 피한다(배치는 순차).
- USD 참조 자리 prim 은 타입 없는 `DefinePrim`(Xform.Define 이면 메시가 안 보인다). 전류 경로 `set_visible` 은 MakeVisible 이라 숨긴 조상이 되살아난다 → 매 프레임 재숨김.
- 한글 경로: 저장소 경로에 한글이 있어도 파이썬·Isaac 은 동작하지만 AEDT 는 안 된다(Maxwell 작업 프로젝트는 `C:\Users\sunwu\AEDT_work`). 새 clone 은 ASCII 경로에 두는 편이 안전하다.
- 테스트 전에 `tools/run_fleet.py`(→ `logs/fleet`, gitignore)를 먼저 돌린다. AI Hub 테스트는 L2/L3 산출물이 없으면 skip 이 정상.
- 대시보드 `public/data/`·`dist/` 는 gitignore → `export_dashboard_data.py --source fleet --mode all`(M1 배치 로그, `run_fleet` 선행) → `export_status_data.py` → `build_analysis_reference.py`·`traceability.py` → `npm run build`. 22 kW 녹화 기반 해설 데이터는 `docs/deliverables/_v22kW/dashboard_data_22kW/`(이력). 서버는 `node serve.cjs`(4173).
- 저전류 판정: 세 상 함께 r < 0.50·균형·I₂/I₁ < 0.05 는 '경부하(참고)' advisory(`current_ratio.low_current_policy`, 2026-10-21 승인) — 결상 의심은 한 상 저전류 또는 불평형·I₂/I₁ 동반 때만.
- AI Hub 원본은 저장소 밖(`…\디지털 트윈\2020-02-125.기계시설물고장예지_sample`), 전체 Training zip 은 미다운로드(88~112 GB). 산출 요약만 커밋.
- **보고용 미디어 팩(2026-10-26, `motor_dt_viz/tools/media/`)**: Isaac 영상은 `--record`(ffmpeg gdigrab **데스크톱 영역** 캡처)라 녹화 중 다른 창을 앞으로 올리면 그 창이 찍힌다 — 녹화 동안 PC 를 건드리지 않는다(실측: VS Code·탐색기가 덮인 영상 2편 재녹화). 캡처용 인자 `--res W H`·`--capture_layout`(창 클라이언트 1920×1080 + Kit 패널 숨김)·`--cam_plan`·`--shot_plan` 파일명 `@WxH`. 배치(.cmd)에서 `python.bat` 는 **`call`** 로 — 없으면 첫 실행 뒤 배치가 끝난다.
- Playwright: 번들 Chromium/ffmpeg 다운로드가 이 PC 에서 멈춤(1.3 MB 에서 정지) → `chromium.launch({channel: "msedge", headless: false})` + 시스템 ffmpeg gdigrab 으로 녹화. Edge 헤드 실행은 **PowerShell 에서**(Git Bash 에서는 "Target page… closed" 로 바로 종료). 대시보드 해설 화면(#/electrical, #/mechanical)은 22 kW 녹화 영상을 재생하므로 보고용 캡처에서 제외.
- `py -3.12 -X utf8`(`python` 별칭은 MS Store). 파일 쓰기 도구는 UTF-8(BOM 있는 파일 주의: `import_lut.py`).
