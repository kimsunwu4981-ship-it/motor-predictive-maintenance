# docs/media/20261026 — 보고용 미디어 팩

## 규격
- 영상: 1920×1080 · 30 fps · H.264 mp4 · 무음 · 60 MB 이하 (초과분은 `.gitignore`, 경로는 `docs/media/README.md`) · 배속 1×(실시간)
- 사진: 1920×1080 PNG (isaac_01·04·08 은 2560×1440) · 파일명 ASCII · 한글은 `index.md` 캡션
- 숫자: 전부 엔진 출력(state.csv)·검증 산출물·LUT. 연출용 숫자 없음. 22 kW 자산 미사용(22 kW 문구가 보이는 화면은 `index.md` 에 표시·제외 사유 기록)

## 재현 (motor_dt_viz 에서, PowerShell)
```
py -3.12 -X utf8 tools\media\capture_all.py plan
cmd /c logs\media\run_isaac.cmd          # Isaac 사진 2회 + 영상 4회 (~20 분, 창을 가리지 말 것 — gdigrab 데스크톱 캡처)
py -3.12 -X utf8 tools\media\capture_all.py isaac
py -3.12 -X utf8 tools\media\capture_all.py hud
cd ..\dashboard; node serve.cjs      # 다른 창
py -3.12 -X utf8 tools\media\capture_all.py dashboard
py -3.12 -X utf8 tools\media\capture_all.py video
py -3.12 -X utf8 tools\media\capture_all.py figures
py -3.12 -X utf8 tools\media\capture_all.py index
```
Isaac 은 PowerShell/cmd 에서만 (Git Bash 자식은 Startup 직후 조용히 종료). 카메라 프리셋은 `tools/media/cameras.yaml` = `viz/m1_model.py` 의 값, 캡처용 인자는 `--res W H`·`--cam_plan`·`--shot_plan`(파일명 `@WxH`).

## 한계
- Isaac 뷰포트 캡처(`capture_viewport_to_file`)에는 omni.ui HUD 가 찍히지 않는다 → `hud/` 는 같은 시각 state.csv 값을 합성한 것(`check_vs_state.json` 으로 1회 대조). 영상(`--record`)은 데스크톱 창 캡처라 HUD 가 그대로 들어간다.
- 대시보드 네이티브 title 툴팁은 스크린샷에 안 찍혀 같은 문장을 DOM 오버레이로 그렸다(페이지 코드 변경 없음, 캡션에 원문).
- 해설 화면(#/electrical, #/mechanical)은 이전 22 kW 녹화 영상을 재생하므로 제외했다 — 상태 보드(#/status) 기준으로 대체.
- 대시보드 사진·영상은 상태 보드 **단순 보기**(2026-10-26 `dashboard: simple view (3-layer IA)` 이후) 기준이다. 전문가 보기는 10번 사진 한 장. 22 kW 문구는 근거 서랍·전문가 보기의 정직성 주석에만 보인다(index.md 표시).
- 영상의 창 캡처는 창 테두리를 포함할 수 있어 1920×1080 으로 scale/pad 했다(검은 여백 가능).

## 수동 캡처 체크리스트 (자동화 불가 — 사람이 찍어 이 폴더에 넣고 index.md 에 한 줄 추가)

| # | 항목 | 어디서 | 파일명(ASCII) | 규격 | 비고 |
|---|---|---|---|---|---|
| 1 | Maxwell 2D 자속밀도(B) 컬러맵 — 정상 / 4턴 R_f 0.1 Ω | Ansys Electronics Desktop → 2D 설계 → Field Overlays → Mag_B, 같은 스케일 | `manual_01_maxwell_B_healthy.png`, `manual_02_maxwell_B_itsc4.png` | 1920×1080 PNG | Student 에디션은 Export 금지 → 화면 캡처(Win+Shift+S). 범례 포함 |
| 2 | Maxwell 전류밀도(J) 단락 루프 | 같은 곳, Field Overlays → Jz | `manual_03_maxwell_J_itsc4.png` | 1920×1080 PNG | |
| 3 | Maxwell 메시·3D 형상 | Mesh → Plot | `manual_04_maxwell_mesh.png` | 1920×1080 PNG | |
| 4 | 라이브 모드 화면 (Isaac `--live` + 대시보드 `#/status?live=ws://…`) | Isaac 창과 브라우저를 한 화면에 | `manual_05_live_mode.png` | 1920×1080 PNG | 포트·live.yaml 은 바꾸지 않는다. 라이브 세션 중 HUD 와 보드 시각이 같은지 보이게 |
| 5 | 실물 모터 사진 (현장) — 명판·DE 축단·전체 | 현장 | `manual_06_photo_nameplate.jpg`, `manual_07_photo_shaft_de.jpg`, `manual_08_photo_overall.jpg` | 원본 해상도 | 명판은 글자가 읽히게. 결선(Y)·정격 전류 확인용 |
| 6 | (선택) 발표장 화면 — 대시보드 + Isaac 동시 투사 | 발표 리허설 | `manual_09_stage.jpg` | 원본 | |
