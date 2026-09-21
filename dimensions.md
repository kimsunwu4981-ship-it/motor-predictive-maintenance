# dimensions.md — 권상(Hoist) 모터 치수 추출표 (M1)

- 도면 세트: 정원크레인(주) / 삼영천장크레인학원 10TON × SPAN 19M OVERHEAD CRANE
- 핵심 시트: **JW-01-HTO-00 HOISTING ASSEMBLY (2008.10.01)**, 참조: JW-01-GA-01 GENERAL ASS'Y (2008.09.30)
- 입력 파일: `../권성 모터 도면/KakaoTalk_20260824_114829677_07.jpg` (HTO), `_03.jpg` (GA), `_00~_02.jpg` (현장 사진)
- 주의: 권상 모터는 BOM상 **구매품(PUR)** 으로 도면에 모터 자체의 상세 치수가 없다. 도면 확인값은 사양·중량·배치 치수뿐이며, 형상 치수는 전부 `미확인(추정)` 이다.
- 프레임 추정 근거: (a) 22kW 6P 유도전동기의 IEC 60072 표준 프레임 = **200L**, (b) 동축 브레이크 BOM 비고 "Fr.200", (c) HTO 상면도 스케일 역산(470/514 치수 기준 ≈0.90 px/mm)으로 프레임 외경≈400, 본체 길이≈450, 전장≈740 → 200L 표준값(AC≈400, L≈770)과 일치.
- 확인상태 범례: **확인** = 도면 기재값 / **미확인** = 추정값(근거 병기)

## 1. 사양 (도면 확인)

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| rated_power_kw | 22 kW | HTO SPEC / GA SPEC / HTO BOM #1 | 확인 |
| poles | 6P | HTO SPEC / GA SPEC | 확인 |
| power_source | AC 3φ 380V 60Hz | GA SPEC | 확인 |
| motor_mass_kg | 285 kg | HTO BOM #1 TOTAL | 확인 |
| crane_rated_load | 10 TON (프롬프트 15톤과 상이 — 도면 우선) | GA/HTO SPEC | 확인 |
| brake_frame | Fr.200 (AC-DC MAG' BRAKE) | HTO BOM #4 | 확인 |
| brake_drum | BWC 150, FCD450 | HTO BOM #5 | 확인 |
| layout_reducer_to_brake | 470 mm | HTO 상면도 | 확인 (기준점: 감속기 출력측 ~ 브레이크 드럼 중심으로 판독, 단면 미확인) |
| layout_brake_to_motor_ref | 514 mm | HTO 상면도 | 확인 (끝점이 모터 본체 내부 수직선 = 모터 풋 볼트 중심으로 판독, 미확인) |
| motor_maker_model | — | 도면 미기재 | **미확인** (사용자 회신 필요) |

## 2. 프레임 / 하우징 `HM_Frame`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| shaft_height_h | 200 mm | IEC 200L H | 미확인(추정: IEC 200L) |
| frame_od (핀 외경) | 400 mm | IEC 200L AC / 스케일 역산 ≈400 | 미확인(추정) |
| frame_core_od (핀 뿌리 외경) | 360 mm | frame_od − 2×fin_h | 미확인(추정) |
| frame_len (본체 원통 길이) | 450 mm | 스케일 역산 ≈450 | 미확인(추정) |
| fin_h / fin_t / fin_pitch | 20 / 4 / 14 mm | 일반 TEFC 주철 프레임 관행 | 미확인(추정) |
| fin_count | 48 | 원주 등분 | 미확인(추정) |
| foot_a (좌우 볼트 간격) | 318 mm | IEC 200L A | 미확인(추정) |
| foot_b (전후 볼트 간격) | 305 mm | IEC 200L B | 미확인(추정) |
| foot_c (DE 축단 어깨 → 첫 볼트) | 133 mm | IEC 200L C | 미확인(추정) |
| foot_k (볼트 구멍 지름) | 19 mm | IEC 200L K | 미확인(추정) |
| foot_w / foot_l / foot_t (풋 폭·길이·두께) | 60 / 400 / 25 mm | 스케일·관행 | 미확인(추정) |
| foot_ab (풋 전체 폭) | 395 mm | IEC 200L AB | 미확인(추정) |
| spigot_d (엔드실드 인로우 지름) | 340 mm | 스테이터 코어 외경 기준 | 미확인(추정) |
| endshield_bolt_pcd / n | 370 mm / 8×M12 | 관행 | 미확인(추정) |

## 3. 엔드실드 `HM_Endshield_DE` / `HM_Endshield_NDE`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| es_od | 400 mm | frame_od 동일 | 미확인(추정) |
| es_thk (플랜지 두께) | 25 mm | 관행 | 미확인(추정) |
| es_len (전체 깊이) | 90 mm | 스케일 역산 | 미확인(추정) |
| es_bearing_housing_bore_de | 140 mm | 베어링 DE 외경 | 미확인(추정: 6313) |
| es_bearing_housing_bore_nde | 120 mm | 베어링 NDE 외경 | 미확인(추정: 6311) |

## 4. 샤프트 `HM_Shaft`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| shaft_de_dia (D) | 55 mm | IEC 200L D | 미확인(추정) |
| shaft_de_len (E) | 110 mm | IEC 200L E | 미확인(추정) |
| shaft_de_key (F×GD×키홈 길이) | 16 × 10 × 90 mm | IEC 200L (키 16×10) | 미확인(추정) |
| shaft_nde_dia / len | 48 / 110 mm | 스케일 역산(약 115) / 관행 | 미확인(추정) |
| shaft_nde_key | 14 × 9 × 80 mm | 관행 | 미확인(추정) |
| shaft_seat_de_dia (베어링 시트) | 65 mm | 6313 내경 | 미확인(추정) |
| shaft_seat_nde_dia | 55 mm | 6311 내경 | 미확인(추정) |
| shaft_core_dia (로터 코어 시트) | 80 mm | 관행 | 미확인(추정) |
| shaft_total_len | 820 mm (수식: de_len + 2×es_len + frame_len + nde_len + 여유) | 파생 | 미확인(추정) |

## 5. 로터 코어 `HM_Rotor_Core` (간략)

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| rotor_od | 218 mm | 200L 6P 일반 | 미확인(추정, 외형 실린더 간략화) |
| rotor_len | 260 mm | 관행 | 미확인(추정) |

## 6. 베어링 `HM_Bearing_DE` / `HM_Bearing_NDE`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| bearing_de | 6313 (d65 × D140 × B33) | 200L 표준 조합 | 미확인(추정: 6313 카탈로그) |
| bearing_nde | 6311 (d55 × D120 × B29) | 200L 표준 조합 | 미확인(추정: 6311 카탈로그) |

## 7. 팬 / 팬 커버 `HM_Fan` / `HM_Fan_Cover`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| fan_od / fan_hub_d / fan_t / blade_n | 330 / 100 / 40 / 10 | 관행 | 미확인(추정) |
| fancover_od | 400 mm | 스케일 역산(프레임 외경과 동일) | 미확인(추정) |
| fancover_len | 150 mm | 스케일 역산 | 미확인(추정) |
| fancover_t | 1.5 mm (판금) | 관행 | 미확인(추정) |

## 8. 단자함 `HM_Terminal_Box`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| tbox_w × tbox_l × tbox_h | 200 × 250 × 150 mm | 현장 사진·스케일 | 미확인(추정) |
| tbox_pos (프레임 상부, DE측 오프셋) | 프레임 중앙 상단 | 현장 사진 _00~_02 | 미확인(추정) |

## 9. 아이볼트 `HM_Eyebolt`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| eyebolt | M20 (DIN 580) | 현장 사진 상부 1개 확인 | 미확인(추정: 크기) |

## 10. 마운팅 인터페이스 `HM_Mount_Interface`

| 치수명 | 값 | 출처 | 확인상태 |
|---|---|---|---|
| 볼트 패턴 | 4 × Ø19, 318 × 305 mm | IEC 200L A×B | 미확인(추정) |
| 커플링면 | DE 축단 끝면(원점) | §5 좌표계 규약 | — |

## 11. 사용자 질문 목록 (게이트 항목)

1. **모터 제조사/모델명** — 명판 사진이 있으면 프레임 번호(200L 추정)와 축단 규격을 확정할 수 있습니다.
2. 470/514 배치 치수의 기준점 판독(감속기→브레이크 중심, 브레이크 중심→모터 풋 중심)이 맞는지.
3. 베어링 형번(6313/6311 추정) — 확정값이 있으면 회신.
4. HTO 시트 외에 모터 외형도(제조사 카탈로그 도면)가 별도로 있는지.
5. 위 추정값으로 진행해도 되는지(승인 시 M2 파라미터 등록으로 진행). 진행 모드: 단계별 승인 / 연속 실행.
