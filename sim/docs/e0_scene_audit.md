# E0 — 현재 씬 상태 감사

Stage: `sim/usd/hoist_motor_physics_v01.usd` (headless 조회, `sim/scripts/e0_scene_audit.py` → `sim/output/e0_scene_audit.json`)

| 항목 | 현재값 | 목표값(v2.0) | 판정 / 조치 |
|---|---|---|---|
| metersPerUnit / kilogramsPerUnit / upAxis | 1.0 / 1.0 / Z | 1.0 / 1.0 / Z | ✅ |
| 고정부 `HM_Frame_Assy` | RigidBody, 192.05 kg, 월드에 FixedJoint | 고정 | ✅ |
| 회전부 `HM_Rotor_Assy` | RigidBody, 92.95 kg, I = (0.468, 1.850, 1.850), principalAxes (1,0,0,0), COM (0.4254,0,0) | 명판 배분 + CAD 관성 | ✅ |
| 충돌 메시 | Cylinder ×3, Cube ×2 (purpose guide), 시각 메시(9 214 / 3 202 pts)에는 충돌 없음 | 프록시 | ✅ |
| Revolute `JT_Frame_Rotor_Rev` | 축 X, localPos (0.425,0,0), body0 Frame / body1 Rotor, maxJointVelocity 1e6 deg/s, armature 0, friction 0 | 축 +X, 베어링 중심선 | ✅ |
| 드라이브 (USD) | type force, stiffness 0, **damping 7.33**, targetVelocity 0, maxForce 449 | stiffness 0, **damping = 기계 감쇠 최솟값**, 속도 지령 비활성 | ⚠️ USD값은 v1 잔재(런타임엔 API로 57.2 적용했음) → **E2에서 API로 damping 0.015 N·m·s/rad(EST) 설정, 토크 제어 루프로 전환** |
| 회전부 maxAngularVelocity | 1e6 deg/s | 상한 없음 | ✅ |
| PhysicsScene | CPU(GPU off), TGS, MBP, 2560 Hz, g = 9.81 −Z | 동일 | ✅ |
| 스텝 방식 | `World.step`은 1/60 s로 스텝하는 문제 → PhysX 직접 스텝 사용(v1 확인) | 2560 Hz 고정 스텝 | ✅ (러너에 반영) |

수정 필요 항목: (1) 드라이브 → 토크 제어 루프 전환(E2), (2) 부하 토크 모델 50 %/100 % 추가(E2), (3) 전류 채널 생성기 추가(E5).
