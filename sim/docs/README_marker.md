# README_marker.md — 샤프트 회전 마커

## 실행 (3줄)
1. `C:\ISSACS~1\python.bat sim\scripts\add_shaft_marker.py --save` → 스테이지 `sim/usd/hoist_motor_physics_v01.usd`에 마커 생성·검증 후 `hoist_motor_physics_v01_marker.usd`로 별도 저장(원본 무변경)
2. GUI 데모: `... add_shaft_marker.py --gui --demo_rpm 90` (창이 열리고 90 rpm으로 회전 — 시각화 전용, PdM 데이터 무관)
3. Script Editor: 스테이지를 연 뒤 파일 내용을 붙여 넣고 실행(마커만 생성, 시뮬 검증 생략). 재실행 시 기존 `RotMarker` 삭제 후 재생성(멱등)

## 생성 프림
`<샤프트>/RotMarker/Stripe`(빨강, emissive) · `<샤프트>/RotMarker/DirDot`(흰색, 원주상 90° — 회전 방향 인식용). 물리 API 없음, 부모(Revolute body1) 회전 상속.

## Movie Capture 권장 설정
- 해상도 1920×1080, 렌더러 **RTX Real-Time**(RTX 3070 Ti 8 GB — Path Tracing 비권장)
- 옵션 A: 데모 회전 90 rpm + **30 fps** 캡처 (프레임당 18°)
- 옵션 B: 실제 1170 rpm 유지 + **120 fps** 캡처 → 30 fps 타임라인에서 재생(4배 슬로모션, 프레임당 58.5°). 1170 rpm을 30 fps로 직접 찍으면 프레임당 234°라 회전이 보이지 않음(앨리어싱)
- 카메라는 변경하지 않음(기존 뷰 사용)
