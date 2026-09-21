# E6 — 시나리오 배치 실행 보고

스크립트 `sim/scripts/e6_run_batch.py` (런당 `e_run.py` 독립 프로세스, headless 순차)

## 매트릭스
| 축 | 값 |
|---|---|
| 결함 | brb, ecc_static, ecc_dynamic, itsc, bpfo, bpfi (6종) + 정상 |
| 심각도 | 3단계/결함 (brb·bpfo·bpfi: incipient/moderate/severe, ecc: e10/e20/e30, itsc: t2/t5/t10) |
| 부하 | half (50 % = 89.8 N·m), rated (100 % = 179.6 N·m) |
| 반복 | 2 (시드 20260828/20260928 정상, +7 결함) |
| 총 런 | **76**, 런당 13 s @ 2560 Hz |

사전 산정(보고): 76 런 × ≈33 s ≈ 42 분, ≈ 91 MB.

## 실행 이력
| 데이터셋 | 결과 | 상태 |
|---|---|---|
| `dataset_v02` | 76/76 rc=0, 42 분 | **무효(보관)** — E7에서 진동 채널 θ 기반 성분(fr, fs±fr, BPFI±fr)이 0.5~0.8 % 편이. 원인: PhysX 조인트 위치 θ의 float32 누적 오차(누적각 > 600 rad, `diag_theta2.json`: dθ/dt 125.00 vs ω 124.06). 전류 채널·ω 기반 성분·baseline은 정상 |
| `dataset_v03` | 러너 수정(θ = ω의 float64 적분, 채널 `theta` 추가) 후 재실행 | E7 검증 대상 |

무부하 조건은 슬립 ≈ 0으로 BRB 시그니처가 물리적으로 소멸하므로 매트릭스에서 제외(E3).

## 정직성 라벨
`manifest.json` 및 모든 런 JSON: `generation = {speed_torque_channel: physx_torque_control, current_channel: analytic, fault_signature: analytic_injection, caveat: ...}`
