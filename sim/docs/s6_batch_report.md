# S6 — 결함 시나리오 배치 실행 보고

- 스크립트: `sim/scripts/s6_run_batch.py --dataset dataset_v01 --total_s 8` (각 런은 `s4_run_baseline.py`를 독립 프로세스로 호출, headless 순차)
- 데이터셋: `sim/output/dataset_v01/` — 런 44개 × (`.npz` + `.json`) + `manifest.json` + 런별 로그, **20 MB**
- 소요: 런당 ≈ 27 s(앱 기동 포함), 총 ≈ 20 분
- 사전 산정(실행 전 보고): 44 런, 예상 22 분 / ≈ 40 MB → 실측 20 분 / 20 MB

## 시나리오 매트릭스
| 축 | 값 |
|---|---|
| 결함 모드 (7) | brb, ecc_static, ecc_dynamic, itsc, bpfo, bpfi, unbalance |
| 심각도 (3/모드) | brb·bpfo·bpfi: incipient/moderate/severe · ecc: e10/e20/e30 · itsc: t2/t5/t10 · unbalance: G6.3/G16/G40 |
| 부하 (2) | noload (0 N·m, ≈1200 rpm) / rated (179.6 N·m, 1170 rpm) |
| 반복 | 1 (시드 20260835; baseline 시드 20260828) |
| baseline | noload, rated 각 1 |

런 길이 8 s (기동 → 2 ~ 8 s 정속 유지 → 정지 지령 8 s), 2560 Hz, 20 480 샘플/런.

## 메타데이터 정직성 라벨
- `manifest.json.generation = "analytic_injection"`, 각 결함 런 JSON `generation = "analytic_injection"`, `fault_params.label = "미확인(추정: 진폭비는 상대 스윕값, 공진 800 Hz 가정)"`
- baseline 런은 `generation = "baseline_rigid_body"`

## 실행 결과
- 44/44 성공(rc = 0), 정속 검증: 전 런 `rpm_within_1pct = true` (결함 리플은 평균 rpm에 영향 없음)
- 상세 신호 검증은 `s7_verification_report.md`
