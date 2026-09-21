# S1 — USD 변환 및 임포트 검증

- 변환: Blender 5.2 **USD Exporter**(`bpy.ops.wm.usd_export`, `convert_orientation=False`, 머티리얼 포함) → `sim/usd/hoist_motor_v01.usd` (1.34 MB)
- 계층: 고정부 `HM_Frame_Assy/visual_frame`(프레임·엔드실드×2·팬커버·단자함·아이볼트·베어링×2·마운트 병합, 9 214 pts / 18 524 faces), 회전부 `HM_Rotor_Assy/visual_rotor`(샤프트·로터·팬 병합, 3 202 pts / 6 400 faces)
- 검증 스크립트: `sim/scripts/s1_import_check.py` (headless) → `sim/output/s1_report.json`

| 체크 | 기준 | 결과 | 판정 |
|---|---|---|---|
| Stage 단위 | metersPerUnit = 1 | 참조 레이어 1.0 / Stage 1.0 | ✅ |
| 스케일 | 프레임 외곽 Ø400 → y ±0.200 m; 축 전장 850 → x 0~0.85 | 회전부 bbox x [0.000, 0.850], 고정부 y [−0.209, 0.209] (마운트 플레이트 폭 418 포함), z [−0.22, 0.35] (마운트 하면 −220 ~ 단자함 상면 +350) — 도면/CAD값과 일치 | ✅ |
| 축 방향 | 축선 +X, 상방 +Z | 참조·Stage upAxis = Z, 회전부 길이 방향 = X | ✅ |
| 계층 분리 | 고정부/회전부 프림 분리 | `/World/HoistMotor/HoistMotor/HM_Frame_Assy`, `/…/HM_Rotor_Assy` | ✅ |
| 머티리얼 | USD Preview Surface 바인딩 | `_materials/Paint_PhotoGrayBlue`(고정부), `Shaft_RustyDark`(회전부) 바인딩 확인 — 병합 메시라 첫 슬롯 재질만 전체 바인딩 | ✅(시각 전용) |
| 충돌 프록시 | 단순 형상 분리 | Blender `hide_render` 오브젝트가 USD에 미포함 → **S2에서 UsdGeom Cylinder/Cube로 직접 생성** (purpose=guide) | ↪ S2 |
| 스크린샷 | headless 캡처 | `capture_viewport_to_file` 비동기 저장이 `close()` 전 완료되지 않아 파일 미생성. 머티리얼은 API 바인딩으로 확인 | ⚠️ 비차단 |

결론: 스케일·축·계층 모두 일치 → S2 진행 가능.
