# E5 — FaultInjector · CurrentGenerator 구현 및 단위 테스트

파일: `sim/scripts/fault_injector.py`(v2 래퍼, 구현은 `s5_fault_injector.py` 공유), `sim/scripts/current_generator.py`, 테스트 `sim/scripts/e5_selftest.py` → `sim/output/e5_selftest.json`

## 토크 리플 (진동 근사 채널 원인) — 매 step `torque_v2(t, s, fr, θ)`
| 결함 | 성분 | 파라미터 | 출처 |
|---|---|---|---|
| brb | sin(2π·2s·fs·t) | 진폭비 0.5/2/5 % T_rated, s 실시간 | 성분: 표준 MCSA 이론 / 진폭: **EST** |
| ecc_static | 2fs | 1/2/4 % | 〃 |
| ecc_dynamic | fr + 0.3×(2fs ± fr) | 1/2/4 % | 〃 |
| itsc | 2fs + 0.3×(fs ± fr) | 1/2.5/5 % | 〃 |
| bpfo / bpfi | 임펄스열(주기 1/BPFO·BPFI, 지터 0.3 %) × 감쇠정현(800 Hz, ζ 0.05), bpfi는 (1+0.8 sinθ) 변조 | 피크 2/6/15 % | 주파수식: 표준 / 공진·진폭: **EST** |
| unbalance | sin θ (1×fr) | 0.2/0.6/1.5 % | 기계 대조군, **EST** |

## 전류 채널 (해석 생성, 3상, 동일 s·fr 공유)
기본파 43.7 A(CALC: 22 kW/(√3·380·η0.9·pf0.85), η·pf EST) + 5·7차(−40 dB, EST) + 노이즈 −60 dB
| 결함 | 측대파 | 심각도 dB(기본파 대비) | 출처 |
|---|---|---|---|
| brb | fs(1±2ks), k = 1, 2 | −48/−40/−32 | Thomson & Fenger 2001 (기억 기반, **미확인**) |
| ecc_static / dynamic | fs ± k·fr (k ≤ 2 / ≤ 3) | −50/−44/−38 | 〃 |
| itsc | 3fs 증가 + fs ± 2fr + 고장상(A) 진폭 +1/2.5/5 % | −46/−38/−30 | Thomson 2001; Sharifi & Ebrahimi 2011 (기억 기반, **미확인**) |
| bpfo / bpfi | \|fs ± k·f_brg\| | −58/−50/−42 | Schoen et al. 1995 (기억 기반, **미확인**) |
| unbalance | fs ± fr | −52/−46/−40 | 편심과 주파수 중첩 — **미확인** |

**편심 vs 턴간 단락 구분 규칙**: 편심 = fs ± k·fr 측대파 열, 턴간 단락 = 3fs 증가 + fs ± 2fr + 상 불평형. 출처가 기억 기반 인용이라 `미확인` → **두 클래스 간 분류 성능은 주장하지 않는다**(README에 명시).

## 단위 테스트 결과 (정격점 고정 슬립, T = 10 s, Δf = 0.1 Hz)
- 토크 채널: 7 모드 전 피크 검출 ✅ (베어링은 포락선)
- 전류 채널: 7 모드 전 측대파 검출 ✅; 판정 제외 2건 — bpfo |fs − BPFO| = 0.12 Hz(< 2Δf), |fs − 2·BPFO| = 59.76 Hz(기본파와 3Δf 내 중첩 → 물리적으로 분리 불가)
- 정상 전류: 60/300/420 Hz 외 −50 dB 초과 이상 피크 **없음** ✅
- 수정 이력: 베어링 임펄스 지터 1 % → 0.3 %(2차 고조파 폭 Δf 초과 해소), 음의 측대파는 |·| 처리

**판정: ALL_OK**
