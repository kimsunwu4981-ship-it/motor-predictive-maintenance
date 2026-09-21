# export_notes.md — 좌표계·단위·후속 파이프라인 주의사항 (M8)

## 산출 파일

| 파일 | 내용 |
|---|---|
| `export/Hoist_Motor_22kW6P_v01.f3d` | Fusion 아카이브(파라메트릭 타임라인·User Parameters·조인트 포함) |
| `export/Hoist_Motor_22kW6P_v01.step` | 전체 어셈블리 STEP — **AP214** (`AUTOMOTIVE_DESIGN`, Fusion API가 AP242 선택을 노출하지 않음; AP242가 필수면 Fusion UI 내보내기 또는 변환 필요), 컴포넌트 계층 유지 |
| `export/step_parts/HM_<Part>_v01.step` ×12 | 컴포넌트별 개별 STEP |

### Blender 렌더링 산출물 (추가)

| 파일 | 내용 |
|---|---|
| `export/mesh/HM_*.obj` ×12 | Fusion OBJ 내보내기 (**단위 cm**, +Z up — Blender 임포트 시 `global_scale=0.01`, `forward_axis='Y', up_axis='Z'`) |
| `export/blender/build_scene.py` | 씬 자동 구축 스크립트(임포트·재질·환경·조명·카메라·렌더 설정) — `blender --python build_scene.py` |
| `export/blender/hoist_motor_render.blend` | 구축된 렌더 씬 (Cycles, 1600×1200, 96 samples, CPU) |
| `export/render/hoist_motor_render_final.png` | **최종 사실적 렌더** (v1~v4는 조정 이력) |

사진 기반 사실화 요소(Blender에서 추가, 도면 치수 아님 — 프록시): 밝은 회청색 도장 + 상면 먼지, 둥근 팬 커버 + 확장메탈 그릴, 단자함 뚜껑·나사·측면 박스·글랜드·플렉시블 콘듀트 2본, 아이볼트 2개, 명판, 풋 볼트, 플랜지 커플링(볼트 8개), 브레이크 드럼·슈·암·스러스터·레버·베이스, 와이어 드럼(플랜지·볼트·기름 로프 코일), 노란 확장메탈 가드, 타코/리밋스위치, 노란 거더·트롤리 프레임·페데스탈, 녹슨 무늬강판. Fusion 원본 12개 파트는 `HoistMotor` 컬렉션에 그대로 유지(팬 커버 원본은 렌더 숨김).

## 좌표계 규약 (모든 파트 공통)

| 항목 | 값 |
|---|---|
| 단위 | **mm** (STEP 내부 단위 mm) |
| 모터 축선 | **+X** (DE → NDE 방향이 +X) |
| 연직 상방 | **+Z** (풋 하면 z = −200, 단자함·아이볼트는 +Z 측) |
| 원점 | **DE(부하측) 축단 끝면 중심** (0, 0, 0) |
| Fusion 뷰포트 | 기본 Y-up 표시라 화면에서는 풋이 옆으로 보이지만 모델 좌표는 위 규약대로임 |

### 축 방향 배치 (x, mm)

| 구간 | x 범위 |
|---|---|
| DE 축단 (Ø55, 키 16×10) | 0 → 110 |
| DE 엔드실드 (+인로우) | 110 → 206 |
| 프레임 본체 | 200 → 650 |
| 로터 코어 | 295 → 555 |
| NDE 엔드실드 | 644 → 740 |
| 팬 / NDE 축단 (Ø48) | 745 → 785 / 740 → 850 |
| 팬 커버 | 740 → 890 |
| 풋 볼트 구멍 중심 | x = 243, 548 / y = ±159 (A×B = 318×305, Ø19) |

## 물성 (M7)

- 모터 합계(마운트 참조 제외): **262.45 kg**, 질량중심 (429.1, 0.0, 13.9) mm
- 도면 명판 중량 285 kg 대비 **−7.9 %** (권선·절연물·내부 상세 생략 및 프레임 강철 대체에 기인)
- 마운트 플레이트 포함: 288.85 kg, COM (426.0, 0.0, −6.5)

## 조인트 / 자유도

- 그라운드: `HM_Frame`
- `JT_Shaft_Frame_Rev` — **Revolute**, 축 벡터 (1, 0, 0), 축선 원점 (55, 0, 0) → Isaac Sim의 RevoluteJoint axis = **X**
- 샤프트와 함께 회전: `HM_Rotor_Core`, `HM_Fan` (Rigid to Shaft)
- 정지 그룹(Rigid to Frame): 엔드실드 DE/NDE, 베어링 DE/NDE(외륜 기준), 팬 커버, 단자함, 아이볼트, 마운트 인터페이스
- 간섭 검사: **0건** (12 바디)

## 후속 파이프라인 절차

### Blender
1. STEP 직접 임포트 불가 → FreeCAD 또는 Fusion에서 **OBJ/FBX/glTF** 재내보내기 권장 (Fusion: 파일 → 내보내기 → OBJ, 단위 mm).
2. Blender는 Z-up이므로 본 모델 규약과 동일. 임포트 시 스케일 0.001(mm → m) 적용.
3. 회전 파트(`HM_Shaft`, `HM_Rotor_Core`, `HM_Fan`)를 하나의 Empty(원점 (0,0,0), 축 X) 아래로 페어런팅하면 애니메이션 가능.

### Isaac Sim (USD)
1. glTF/OBJ → USD 변환(Isaac Sim Asset Importer) 또는 Blender USD Export. 단위: `metersPerUnit = 1` 로 변환(0.001 스케일).
2. 링크 구성: `frame_link`(정지 그룹 전부 병합) / `rotor_link`(Shaft+Rotor_Core+Fan 병합).
3. `PhysicsRevoluteJoint`: body0 = frame_link, body1 = rotor_link, **axis = "X"**, localPos0 = localPos1 = (0.055, 0, 0) m(축선 위 임의점; DE 축단 기준). 회전 방향 부호는 정격 회전 방향(도면 미기재 → 미확인)에 맞춰 조정.
4. 질량: rotor_link ≈ 26.0 + 65.9 + 1.0 = **92.9 kg**, frame_link ≈ 169.5 kg (본 모델 기준). 명판 285 kg에 맞추려면 frame_link 질량을 192 kg로 오버라이드.

### ANSYS
- STEP(어셈블리) 직접 임포트 가능. 재질: 프레임/엔드실드는 도면 미확인으로 강철 적용 → 해석 시 **주철(GG25 등)** 로 교체 권장.
- 베어링은 링 일체 간략 모델 → 접촉 정의 시 내륜/외륜 분리 필요하면 `HM_Bearing_*` 재모델링.

## 미확인 항목 최종 목록

모터가 도면상 구매품(PUR)이라 형상 치수 **전부 미확인(추정: IEC 200L)** 이다. 상세는 `dimensions.md` 각 표의 확인상태 열과 Fusion User Parameters 코멘트에 기록됨. 확정 필요 우선순위:
1. 모터 제조사·모델·프레임 번호(명판) → 200L 여부 확정
2. 축단 규격(D×E, 키) → 커플링 정합
3. 베어링 형번(6313/6311 추정)
4. 프레임 재질(주철 추정), 풋 위치(C=133 추정)
5. 470/514 배치 치수의 기준점 해석
