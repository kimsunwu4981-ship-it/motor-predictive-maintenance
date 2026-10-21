# 깨끗한 복제본에서 재현하기 (REPRODUCE, D1 2026-10-21)

두 저장소를 새로 clone 해 README 의 명령만으로 끝까지 도는지 확인한 기록이다(2026-10-21, ASCII 임시 경로에서 실측). 결과 json·LUT 처럼 재생성에 AEDT 가 필요한 파일은 커밋돼 있다.

## 0. 요구 소프트웨어 (실측 버전)

| 항목 | 버전 | 용도 |
|---|---|---|
| Windows 11, Git | — | 두 저장소 clone (`hoist-motor-maxwell`, `motor-predictive-maintenance`) |
| Python | 3.12.10 (`py -3.12 -X utf8`; `python` 별칭은 MS Store 라 쓰지 않음) | 전 스크립트 |
| cadquery 2.8.0 · trimesh 5.1.1 · numpy 2.5.2 · matplotlib 3.11.1 · openpyxl 3.1.5 · PyYAML 6.0.3 · usd-core 26.8(pxr) · websockets 16.1.1 · psutil 7.2.2 · pypdf 6.21 · pdfplumber 0.11 · pymupdf | pip | CAD·테스트·문서·검증 |
| Isaac Sim | 4.5.0 (`C:\ISSACS~1\python.bat`, 8.3 경로) | USD 조립·장면·라이브 검증(V7)·스크린샷 |
| Node | v26.7 / npm 11.19 | 대시보드 빌드(`npm install`) |
| ffmpeg | 9.0 (PATH) | 녹화(선택) |
| ANSYS AEDT 2025 R2 **Student** + PyAEDT 1.9.0 | Maxwell 저장소의 RMxprt·2D 해석 **재실행 때만**(이 절차에서는 제외 — 결과 json 커밋본 사용) |
| 설치 안 됨 | python-docx · weasyprint · reportlab | 산출 문서(E) 재생성 때 필요 — 현재 미설치 |

## 1. Maxwell 저장소 (읽기·태그만) — 약 2분

```powershell
git clone https://github.com/kimsunwu4981-ship-it/hoist-motor-maxwell.git maxwell ; cd maxwell
py -3.12 -X utf8 tools\maxwell\mccm.py                     # 등가회로 160점 LUT (AEDT 불필요, rmxprt_v2m2.json 커밋본 입력)  ~10 s
py -3.12 -X utf8 tools\maxwell\e3_tables.py                # 표 A~G xlsx·analysis_report.md·그림                     ~20 s
py -3.12 -X utf8 tools\maxwell\x_numbers_xlsx.py --no-dt   # 해석 수치표 14 시트(검산 4)                               ~30 s
```

- RMxprt·2D 해석(m1~m6, s1~e2b, x1~x8)은 AEDT 학생판이 필요하고 `maxwell/*.aedt` 는 gitignore → **재실행 대상이 아니다**. 그 결과 `maxwell/results/*.json`, `eddy2d/*.json` 은 모두 커밋돼 있다(60 파일).
- 실측 결과: 세 스크립트 모두 통과. 재생성본은 커밋본과 **날짜·이미지 바이트만** 다르고 수치는 같다(`git status`: analysis_report.md·xlsx 2개·png 1개).
- **주의**: `e3_tables.py` 는 `docs/maxwell/analysis_report.md` 를 처음부터 다시 써서 뒤에 다른 스크립트가 덧붙인 절(F1~F6 보정 전/후, S1~S4 학생판 2D 검증, X 요약)이 사라지고, 그러면 `x_numbers_xlsx.py` 검산 3("보정 전/후 표")이 FAIL 로 나온다. 보고서 정본은 **커밋본**이므로 재생성 뒤 `git checkout docs/maxwell/analysis_report.md` 로 되돌리거나 e3_tables 를 다시 돌리지 않는다. 입력 PDF·STEP·AEDT 는 `docs/sources/`·`maxwell/input/`(gitignore, sha 는 `docs/sources/SOURCES.md`).
- 태그 `v1.0-m1`.

## 2. DT 저장소 — 약 25분 (Isaac 기동 포함)

```powershell
git clone https://github.com/kimsunwu4981-ship-it/motor-predictive-maintenance.git dt ; cd dt
$env:MAXWELL_ROOT = "<maxwell clone 절대경로>"            # 생략하면 바탕 화면 기본 경로
cd motor_dt_viz
py -3.12 -X utf8 tools\electrical\import_lut.py            # Maxwell mccm_lut.json → data/electrical/M1_mccm_lut_v2.json (같은 sha 면 유지)   ~1 s
py -3.12 -X utf8 tools\run_fleet.py                        # logs/fleet (gitignore) — 테스트·상태 보드 전제                                   ~2 s
py -3.12 -X utf8 tools\fleet_summary.py                    # docs/m1_summary.md
cd .. ; py -3.12 -X utf8 -m pytest motor_dt_viz\tests tests -q      # 135 passed, 8 skipped(AI Hub L2/L3 없음 = 정상), ~20 s
py -3.12 -X utf8 tools\cad\build_internals_M1.py           # CadQuery, ~15 s (코일 36개 스윕)
py -3.12 -X utf8 tools\cad\build_housing_100L.py           # ~3 s
C:\ISSACS~1\python.bat tools\cad\build_usd_M1.py           # Isaac 헤드리스, USD 반입·조립 ~1 분 (저장소 루트에서, 상대 경로)
cd motor_dt_viz
py -3.12 -X utf8 tools\verify\build_analysis_reference.py  # data/electrical/analysis_reference.json (+ dashboard public 사본)
py -3.12 -X utf8 tools\verify\traceability.py
py -3.12 -X utf8 ..\dashboard\tools\export_dashboard_data.py --source fleet --mode all   # 해설 데이터 mechanical/electrical ← M1 배치 로그 (D 후속 2)
py -3.12 -X utf8 ..\dashboard\tools\export_status_data.py  # public/data/fleet
cd ..\dashboard ; npm install ; npm run build              # ~2 분 + 7 s
cd ..\motor_dt_viz ; py -3.12 -X utf8 tools\electrical\verify_lut_integration.py   # 8/8 (V7 은 Isaac 라이브 45 s 기동)  ~3 분  ← PowerShell/cmd 에서
py -3.12 -X utf8 tools\docs\verification_summary.py        # docs/verification_summary.md
```

- 실측: 위 순서대로 전부 통과(LUT sha 동일 `c6898c6e8d80`, pytest 135 passed·8 skipped, USD prims 110, 대시보드 빌드, verify 8/8).
- `datasheet_to_yaml.py` 는 **돌리지 않는다**: 카탈로그 PDF(Maxwell `docs/sources`, gitignore)가 없으면 치수표가 빠진 `datasheet_v4.yaml` 로 덮어써 하우징 빌드가 깨진다. `assets/motors/M1/inputs/` 커밋본이 입력 정본(PROVENANCE.md).
- 검증 대조·스크린샷(`tools/verify/sim_vs_analysis.py`, `tools/viz/shot_with_hud.py`)은 Isaac 배치 로그(`logs/verify`, ~30 분)가 필요 — 산출물은 `docs/verification/`·`docs/assets/screenshots/` 커밋본.

## 3. 실패 시 확인

| 증상 | 원인·조치 |
|---|---|
| `verify_lut_integration.py` V7 "접속 실패 (기동 시간 초과)" 7/8 | **Git Bash 에서 실행** → Isaac 자식 프로세스가 Startup 직후 조용히 종료. PowerShell/cmd 에서 실행 |
| Isaac 기동 실패 / RTX 초기화 실패 | Blender 가 떠 있음, 또는 Isaac 두 인스턴스 동시 실행. 하나만 |
| AEDT 스크립트 멈춤·라이선스 | 잔여 `ansysedtsv.exe` 인스턴스 종료 후 재실행(Maxwell CLAUDE.md). 학생판 메시 상한·Transient 미지원 |
| `.bat` 인자 깨짐 | `C:\issac sim\python.bat` 공백 경로 → `C:\ISSACS~1\python.bat`, `.bat` 에는 상대 경로만 |
| 한글 경로 | 파이썬·Isaac 은 동작하나 AEDT 작업 프로젝트는 ASCII(`C:\Users\sunwu\AEDT_work`). 새 clone 은 ASCII 경로 권장 |
| `test_fleet` FAIL / skip | `tools/run_fleet.py` 먼저(logs/fleet gitignore). AI Hub 테스트 skip 은 L2/L3 산출물 없음 — 정상 |
| `export_status_data.py` FileNotFoundError `public/data/mechanical/thresholds.json` | 먼저 `export_dashboard_data.py --source fleet --mode all`(M1 배치 로그, `run_fleet` 선행). 22 kW 녹화 기반 동결본은 `docs/deliverables/_v22kW/dashboard_data_22kW/`(이력) |
| `import_lut.py` 경로 없음 | `MAXWELL_ROOT` 환경변수 또는 `--src` |
| `ast`/인코딩 오류 (`import_lut.py` BOM) | 파일이 UTF-8 BOM — 편집 도구가 BOM 을 지우지 않도록 |
| `x_numbers_xlsx.py` 검산 3 FAIL | 위 §1 주의(e3_tables 가 analysis_report.md 뒤 절을 지움) |
