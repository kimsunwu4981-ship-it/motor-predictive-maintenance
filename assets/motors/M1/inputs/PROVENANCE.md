# M1 모델 입력 파일 출처 (P4 D0, 2026-10-21)

Maxwell 저장소 `C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링` 는 **읽기 전용**이다. 아래 복사본만 쓰며, 이후 모든 생성(`tools/cad/*.py`)은 이 폴더 기준이라 Maxwell 폴더가 닫혀 있어도 재생성된다. 복사 시각 2026-10-21 10:39 (KST).

| 복사본 | 원본 경로 | sha256 | 비고 |
|---|---|---|---|
| `Maxwell_M1_HLP2.2-4_전체데이터시트_v4.xlsx` | `…\권상모터_3D모델링\maxwell\input\Maxwell_M1_HLP2.2-4_전체데이터시트_v4.xlsx` | `3e9298af7839477a9f1d05937e18dc5954e86f90f30fd25448e2e8e6c450dd62` | 내부 형상 치수의 유일한 출처. 지시서의 `datasheet_v4.yaml` 은 Maxwell 저장소에 **없고** 이 xlsx 가 v4 데이터시트다 → `tools/cad/datasheet_to_yaml.py` 가 xlsx 를 그대로 키로 풀어 `datasheet_v4.yaml` 을 만든다(숫자 수기 입력 없음) |
| `geometry_check_v2.json` | `…\maxwell\results\geometry_check_v2.json` | `c7685d5d2247179a900af54ddabfabe69c18017ee332ea7f92abdc03b14c3223` | Maxwell 3D(M1_3D_full) 체적 측정값 — 동일성 증명 기준 (치+요크 1,077,645 mm³, 케이지 409,740 mm³, 코일 1개 10,234 mm³, 분할비 0.25019) |
| `rmxprt_v2m2.json` | `…\maxwell\results\rmxprt_v2m2.json` | `07736423faa11165c2e64cad06a26db9e753dd5d6fc999dc86494256435cfc62` | **추가 입력(지시서 밖, 사유 기록)**: Maxwell 3D 모델이 실제로 쓴 슬롯·권선·스큐 치수는 데이터시트 §5·§7 기본값이 아니라 RMxprt v2 오버라이드(로터 브리지 0.8, 고정자 개구 2.0, 쐐기 1.5, 로터 바 19.8/4.5/2.4, N_c 16)를 반영한 값이다. geometry_check_v2.json 의 체적은 그 치수의 측정값이므로, 체적 ±2 % 동일성 검증은 이 스냅샷의 `inputs` 를 써야 맞는다. `datasheet_v4.yaml` 의 `maxwell_model` 절로 들어간다 |
| (복사 안 함) `현대_SSEN_카탈로그.pdf` | `…\권상모터_3D모델링\docs\sources\현대_SSEN_카탈로그.pdf` | `8afee7697616c713d42684a14c9cf9ddb1b3295c522b4aad3b6d3610f998e75a` | 6.9 MB 바이너리라 복사하지 않고 읽기만: KS 형식 치수표(카탈로그 9쪽 = PDF 5쪽, 발 장착 IM B3)와 KS 플랜지 치수표(10쪽 = PDF 6쪽) 의 100L 행을 `datasheet_v4.yaml` `catalog_frame_100L` 에 그대로 넣음 |

생성 파일: `datasheet_v4.yaml` (`py -3.12 -X utf8 tools/cad/datasheet_to_yaml.py`, 멱등). 절 구성: `design_sections`(설계값 §1~§10, 기호·값·단위·출처등급·근거), `design`(기호 → 첫 출현), `catalog_direct`, `winding_table`(36 슬롯), `itsc_cases`, `load_speed_table`, `catalog_frame_100L`(발 장착·플랜지 100L 행 + AD 주석), `maxwell_model`(rmxprt_v2m2 inputs).

AD 328 확인 결과: 카탈로그 원문(발 장착 표)에 100L AD = 328 로 인쇄돼 있다(90L 263, 112M 348 — 프레임 순으로 단조 증가). 같은 카탈로그의 플랜지 표는 100L AD = 175. 그림 B 끝면도에서 AD 는 프레임 측면에서 단자함 끝까지의 **전체 폭** 치수선으로 그려져 있어 "축 중심~단자함 상면"(통상 150~170)과 정의가 다르다. 단자함 상면 높이 HD 247·프레임 상면 HC 211 과 모순되지 않도록 하우징은 HD 만 구속으로 쓰고 AD 는 `verify` 로 둔다.
