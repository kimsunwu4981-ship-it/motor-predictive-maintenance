# 산출 문서 4종 M1 기준 갱신 (E, 2026-10-21) — 상태: **원본 미제공으로 전부 건너뜀**

대상 문서(저장소 밖에서 만들어진 것, 사용자가 `_v22kW/` 에 넣어 두기로 함): ① 애니메이션 해설 PDF ② 실증 가이드라인(docx/md) ③ 센서 설치 가이드 PDF(+ `sensor_layout_*.svg`, `sensor_mount_detail.svg`) ④ 실모터 구매 목록 xlsx.

2026-10-21 현재 `docs/deliverables/_v22kW/` 가 비어 있어(폴더 없음 → 빈 폴더 생성) **4종 모두 건너뛰었다**(지시: 파일이 없으면 그 문서는 건너뛰고 보고). 재생성에 필요한 패키지도 미설치다(python-docx·weasyprint·reportlab — `docs/REPRODUCE.md` §0).

## 원본이 들어오면 할 일 (E1~E3)
1. 추출: PDF → `pdfplumber`(표 보존), docx → `python-docx`. 원본은 `_v22kW/` 그대로.
2. 값 대응: `motor_dt_viz/docs/m1_migration_notes.md` §1 표가 기준, `docs/verification_summary.json` 과 `config/motors/M1.yaml` 로 검증(테스트 `motor_dt_viz/tests/test_deliverables_values.py`). 대응표에 없는 22 kW 고유 문장은 `CHANGES_M1.md` "판단 보류" 목록으로.
3. 센서 배치 SVG 가 180L 치수 기반이면 `assets/motors/M1/housing_params.yaml`(100L) 치수로 재생성(센서 종류·위치 규칙 유지), 아니면 라벨만.
4. 재생성: 소스 `src/*.md` → `out/01_애니메이션_해설_M1.pdf`, `02_실증_가이드라인_M1.md(+docx)`, `03_센서_설치_가이드_M1.pdf`, `04_실모터_구매목록_M1.xlsx`(openpyxl, 수식 유지; 모터 품목 HLP-2.2/4 P2P2TC276, CT 정격 5~10 A 급·분해능 0.01 A, 진동 센서 대역 ≥ 800 Hz 확인 표기). PDF 빌드 `tools/docs/build_pdf.py`(weasyprint 또는 reportlab, 한글 폰트 임베드).
5. `CHANGES_M1.md` 문서별 전/후 표 + 판단 보류, 첫 페이지 PNG, 테스트 통과, 커밋 `docs: deliverables regenerated for M1`.

지금 쓸 수 있는 M1 기준 문장·값 목록은 `motor_dt_viz/docs/m1_migration_notes.md`(§2 문서별 바꿀 문장, §3 저장소 안 22 kW 잔존값)에 있다.
