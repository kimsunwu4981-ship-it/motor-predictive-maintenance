# 전기적 결함 대시보드에 같은 구조를 적용하기 위한 메모

기계 실시간 해설 대시보드(`#/mechanical`)는 **공통 부분**과 **기계 전용 부분**으로 나뉘어 있다. 전기 대시보드(`#/electrical`,
지금은 `ModeDashboard`)를 같은 구조로 바꿀 때 무엇을 그대로 쓰고 무엇을 새로 만들지 적어 둔다.

## 그대로 쓰는 것 (공통)

| 파일 | 역할 | 전기에서 바꿀 것 |
|---|---|---|
| `state/playback.ts` | 영상 currentTime 단일 시간 소스, `?t=`, `?autoplay=1&delay=N`, seek 가드 | 없음 |
| `components/VideoPanel.tsx` | 영상·챕터·`overlay`(자막 띠) | 없음 (`overlay` 만 넘기면 됨) |
| `mech/captions.ts` | 사건 묶음(1 s, 우선순위), 자막 유지 시간, `reveal_timing`, 이력 목록 | 파일 이름만 일반화(`live/captions.ts`). 사건 타입 문자열만 다름 |
| `mech/CaptionBar.tsx`, `LiveNarration.tsx`, `QaDrawer.tsx`, `HUDLive.tsx`(시간 압축 부분 제외), `broadcast.ts`, `pages/PresenterView.tsx` | 화면 요소 | 데이터 타입을 `MechData` → 공통 `LiveData` 로. 문구는 전부 content YAML 이라 코드 수정 없음 |
| `mech/data.ts` 의 `fill`, `fillParts`, `fmtSim`, `loadMechData` 의 YAML 로더 | 치환·로더 | `liveValues` 만 모드별로 다르게(아래) |
| `tools/export_dashboard_data.py` | 기본 JSON | 없음 |
| `tests/test_mechanical_extras.py` 의 이벤트·템플릿·변수 검사 | 검증 | 모드 매개변수화 |
| `tools/record_dashboard.ps1` | 화면 녹화 | `-Url` 만 `#/electrical` |

## 새로 만들어야 하는 것 (전기 전용)

1. **`tools/export_electrical_extras.py`** — `export_mechanical_extras.py` 와 같은 자리.
   - 사건 추출: 상별 전류 상태 변화(`current_status` A/B/C: normal ↔ over/under caution/danger), I₂/I₁ 경계 통과(4턴·12턴 수준),
     결상(한 상 under_danger), 장면 전환. 우선순위: 주목 상(결함이 걸린 상) 1 › I₂/I₁ 2 › 기타 3.
   - 해설 변수: `{phase}_rms_end/_now`, `{phase}_status_end/_now`, `i2i1_end/_now`, `i2i1_4turn`, `i2i1_12turn`,
     `line_over_caution_A` 등 임계 암페어(config × 정격), `lead_s`(전기는 현재 0 s — 해석식 모델 한계, 정직하게 표시).
   - 재실행 검증: 전기 모델은 해석식이라 재실행값 = 로그값이어야 한다(허용 오차 0.05 A).
2. **`public/content/electrical/narration.yaml`, `event_templates.yaml`, `qa.yaml`** — 해설 PDF 3장·6.3절(전압↔전류 관계)에서.
   `focus_component` 대신 `focus_phase`(A/B/C) 또는 `focus_signal`(rms / i2i1).
3. **차트**: `TempChart` → `CurrentChart`(상별 RMS, 주목 상만 임계 띠, 나머지는 상태색 선), `VibChart` → `I2I1Chart`(케이스 눈금 배경).
   미래 숨김·마커·커서 로직은 `TempChart` 의 것을 그대로 복사한다.
4. **위치 안내**: 단면도 대신 **Δ결선 회로도 SVG**(세 상 권선 + 케이블). 색은 `colors.yaml` 전기 컬러맵(과전류 빨강/저전류 파랑 두 방향)을
   `mech/colormap.ts` 처럼 포팅. ITSC 는 단락 루프를 따로 그린다(`short_loop_color`).
5. **원인 패널**: 손실 막대 대신 **상별 전류 대 정격 막대**(±방향)와 **I₂/I₁ 게이지**. 지문 미니맵은 회로도 아이콘 7개.
6. **시간 압축 HUD**: 전기는 열 배속이 아니라 슬로모션(`slowmo_factor`)이므로 "화면 1초 = 실제 1/60초" 로 뒤집어 쓴다.

## 순서 제안

M1(export + 테스트) → M2(레이아웃, 기계 페이지 복사 후 데이터 타입 교체) → M3(전류·I₂/I₁ 차트 + 회로도) → M4(해설·자막·원인) → M5(발표자·Q). 기계와 같은 5단계, 콘텐츠 원문은 PDF 3장.

## 주의

- 전기 리드 타임이 0 s 인 이유(해석식 모델에는 시간 지연이 없음)를 화면에 그대로 적는다. 숫자를 만들지 않는다.
- `electrical.yaml` 의 과부하 이중 적용(182 %) 미결 사항을 먼저 정리해야 해설 숫자가 확정된다.
