# prim_inventory.md — USD 스테이지 prim 트리 및 머티리얼 바인딩 현황

> Phase 0 산출물. 생성 스크립트: `motor_dt_viz/tools/dump_prims.py` (읽기 전용, 원본 USD 무수정)

## 스테이지 정보

| 항목 | 값 |
|---|---|
| 파일 | `c:\Users\sunwu\OneDrive\바탕 화면\프로젝트\디지털 트윈\크레인 퀀선 모터 모델링\sim\usd\hoist_motor_physics_v01.usd` |
| upAxis | Z |
| metersPerUnit | 1.0 |
| kilogramsPerUnit | 1.0 |
| 총 prim 수 | 49 |

## prim 트리

```
Render <>
  OmniverseKit <>
    HydraTextures <>
      omni_kit_widget_viewport_ViewportTexture_0 <RenderProduct>
  Vars <>
    LdrColor <RenderVar>
physicsScene <PhysicsScene>
World <>
  HoistMotor <Xform>
    HoistMotor <Xform>  [ArticulationRoot]
      HM_Frame_Assy <Xform>  [RigidBody,Mass]
        visual_frame <Xform>
          visual_frame_mesh_001 <Mesh>  [9214pts]
            Paint_PhotoGrayBlue <GeomSubset>
            Paint_PhotoCover <GeomSubset>
            Bearing_Steel <GeomSubset>
            Mount_Yellow <GeomSubset>
        collision_frame_body <Cylinder>  [Collision | purpose=guide]
        collision_frame_feet <Cube>  [Collision | purpose=guide]
        collision_tbox <Cube>  [Collision | purpose=guide]
      HM_Rotor_Assy <Xform>  [RigidBody,Mass]
        visual_rotor <Xform>
          visual_rotor_mesh_001 <Mesh>  [3202pts]
            Shaft_RustyDark <GeomSubset>
            Rotor_Iron <GeomSubset>
            Fan_Alu <GeomSubset>
        collision_rotor_shaft <Cylinder>  [Collision | purpose=guide]
        collision_rotor_core <Cylinder>  [Collision | purpose=guide]
      JT_World_Frame_Fixed <PhysicsFixedJoint>  [Joint:PhysicsFixedJoint]
      JT_Frame_Rotor_Rev <PhysicsRevoluteJoint>  [Joint:PhysicsRevoluteJoint]
    _materials <Scope>
      Paint_PhotoGrayBlue <Material>
        Principled_BSDF <Shader>
      Paint_PhotoCover <Material>
        Principled_BSDF <Shader>
      Bearing_Steel <Material>
        Principled_BSDF <Shader>
      Mount_Yellow <Material>
        Principled_BSDF <Shader>
      Shaft_RustyDark <Material>
        Principled_BSDF <Shader>
      Rotor_Iron <Material>
        Principled_BSDF <Shader>
      Fan_Alu <Material>
        Principled_BSDF <Shader>
OmniverseKit_Persp <Camera>
OmniverseKit_Front <Camera>
OmniverseKit_Top <Camera>
OmniverseKit_Right <Camera>
```

## 지오메트리 prim 과 머티리얼 바인딩

| prim 경로 | 타입 | 포인트 | bbox(m) X | Y | Z | 바인딩 머티리얼 | 공유 수 |
|---|---|---|---|---|---|---|---|
| `/World/HoistMotor/HoistMotor/HM_Frame_Assy/visual_frame/visual_frame_mesh_001` | Mesh | 9214 | 0.110~0.890 | -0.209~0.209 | -0.220~0.350 | `/World/HoistMotor/_materials/Paint_PhotoGrayBlue` | 1 |
| `/World/HoistMotor/HoistMotor/HM_Frame_Assy/collision_frame_body` | Cylinder | - | 0.110~0.890 | -0.200~0.200 | -0.200~0.200 | `(없음)` | 0 |
| `/World/HoistMotor/HoistMotor/HM_Frame_Assy/collision_frame_feet` | Cube | - | 0.225~0.625 | -0.198~0.198 | -0.200~0.000 | `(없음)` | 0 |
| `/World/HoistMotor/HoistMotor/HM_Frame_Assy/collision_tbox` | Cube | - | 0.300~0.550 | -0.100~0.100 | 0.200~0.350 | `(없음)` | 0 |
| `/World/HoistMotor/HoistMotor/HM_Rotor_Assy/visual_rotor/visual_rotor_mesh_001` | Mesh | 3202 | 0.000~0.850 | -0.165~0.165 | -0.157~0.157 | `/World/HoistMotor/_materials/Shaft_RustyDark` | 1 |
| `/World/HoistMotor/HoistMotor/HM_Rotor_Assy/collision_rotor_shaft` | Cylinder | - | -0.000~0.850 | -0.028~0.028 | -0.028~0.028 | `(없음)` | 0 |
| `/World/HoistMotor/HoistMotor/HM_Rotor_Assy/collision_rotor_core` | Cylinder | - | 0.295~0.555 | -0.109~0.109 | -0.109~0.109 | `(없음)` | 0 |

## 머티리얼 공유 현황 (Hard Rule 3 — 공유 머티리얼 직접 수정 금지)

| 머티리얼 | 사용 prim 수 | 사용처 |
|---|---|---|
| `/World/HoistMotor/_materials/Paint_PhotoGrayBlue` | 1 | `/World/HoistMotor/HoistMotor/HM_Frame_Assy/visual_frame/visual_frame_mesh_001` |
| `/World/HoistMotor/_materials/Shaft_RustyDark` | 1 | `/World/HoistMotor/HoistMotor/HM_Rotor_Assy/visual_rotor/visual_rotor_mesh_001` |

---

# 부품 ↔ prim 매핑 분석 (Phase 0 수작업 분석)

## ⚠️ 핵심 제약: 현재 USD 는 부품 단위로 분리되어 있지 않다

물리 USD(`hoist_motor_physics_v01.usd`)의 지오메트리는 **병합된 메시 2개**뿐이다.

| 메시 | 포인트 | 병합된 실제 부품 |
|---|---|---|
| `visual_frame_mesh_001` | 9,214 | 프레임, 엔드실드 DE, 엔드실드 NDE, 팬커버, 단자함, 아이볼트, 베어링 DE, 베어링 NDE, 마운트 |
| `visual_rotor_mesh_001` | 3,202 | 샤프트, 로터 코어, 냉각팬 |

하위 `GeomSubset` 7개는 **재질(material) 단위 면 그룹**이지 부품 단위가 아니다.
예: `Bearing_Steel` subset 에는 **DE 베어링과 NDE 베어링이 함께** 들어 있어 둘을 따로 칠할 수 없다.

→ **모듈 A 완료 기준("DE 베어링이 빨개지고 인접 하우징이 뒤따라 달아오름")을 현 USD 로는 달성 불가.**

## 해결안 (Phase 1 진입 전 승인 필요)

파트별 원본 메시 12개가 이미 존재한다: `export/mesh/HM_*.obj` (Fusion 내보내기, 월드 좌표, 단위 cm)
및 `export/step_parts/HM_*_v01.step`.

이를 **부품별 독립 prim 을 가진 새 시각화 USD**(`motor_dt_viz/layers/` 또는 `assets/`)로 재구성하면
부품 단위 머티리얼 바인딩·색상 변화가 가능해진다. 원본 USD·f3d 는 읽기 전용으로 유지된다 (Hard Rule 2).

## 요구 부품 ↔ 현황 매핑

| CLAUDE.md 요구 부품 | 현재 상태 | 대응 파트 메시 | 비고 |
|---|---|---|---|
| 로터 | 병합됨(`visual_rotor`) | `HM_Rotor_Core.obj` | 외형 실린더 간략화 |
| 샤프트 | 병합됨(`visual_rotor`) | `HM_Shaft.obj` | 키홈·베어링 시트 포함 |
| 고정자 코어 | **모델에 없음** | — | 프레임 내부 미모델링 |
| 고정자 권선 | **모델에 없음** | — | 모듈 B 에서 절차적 오버레이 생성 필요 |
| DE 베어링 | 병합됨(`visual_frame`) | `HM_Bearing_DE.obj` | 링 일체(구름체 생략) |
| NDE 베어링 | 병합됨(`visual_frame`) | `HM_Bearing_NDE.obj` | 〃 |
| 하우징(프레임) | 병합됨(`visual_frame`) | `HM_Frame.obj` | 냉각핀·풋 일체 |
| 엔드실드 DE/NDE | 병합됨(`visual_frame`) | `HM_Endshield_DE/NDE.obj` | CLAUDE.md 미기재, 하우징 계열 |
| 냉각팬 | 병합됨(`visual_rotor`) | `HM_Fan.obj` | |
| 팬 커버 | 병합됨(`visual_frame`) | `HM_Fan_Cover.obj` | |
| 단자함 | 병합됨(`visual_frame`) | `HM_Terminal_Box.obj` | 모듈 B 케이블 진입점 |
| 아이볼트 | 병합됨(`visual_frame`) | `HM_Eyebolt.obj` | 발열 무관 |
| 마운트 인터페이스 | 병합됨(`visual_frame`) | `HM_Mount_Interface.obj` | 참조 지오메트리(모터 부품 아님) |
| 브레이크 | **모델에 없음** | — | Blender 렌더 씬에만 프록시 존재 |
| 커플링 | **모델에 없음** | — | 〃 |
| 감속기 입력부 | **모델에 없음** | — | |
| 전원 케이블 | **모델에 없음** | — | 모듈 B 에서 BasisCurves 생성 필요 |

## 물리·구동 구조 (기존 시뮬레이션에서 확인)

| 항목 | 값 |
|---|---|
| 아티큘레이션 루트 | `/World/HoistMotor/HoistMotor` |
| 고정부 링크 | `HM_Frame_Assy` (RigidBody, 192.05 kg) — `JT_World_Frame_Fixed` 로 월드 고정 |
| 회전부 링크 | `HM_Rotor_Assy` (RigidBody, 92.95 kg, Ixx 0.468 kg·m²) |
| 회전 조인트 | `JT_Frame_Rotor_Rev` (Revolute, 축 **X**, 위치 (0.425, 0, 0)) |
| 충돌 | 프록시 5개 (`purpose=guide`, 시각 메시에는 충돌 미지정) |
| 좌표계 | upAxis Z, metersPerUnit 1.0, 모터 축선 = +X, 원점 = DE 축단 끝면 중심 |
