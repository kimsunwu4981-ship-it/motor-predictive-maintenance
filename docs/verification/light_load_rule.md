# 저전류 판정 규칙 변경 — 경부하(참고) (2026-10-21 승인) 전후 표

생성 2026-10-21 17:41:58 · `tools/verify/judgment_before_after.py` · 설정 `current_ratio.low_current_policy` = {'light_load_advisory': True, 'unbalance_gate': 0.05} · 엔진 stateless(시뮬레이션 정책).

규칙: (a) 세 상 함께 r < 0.50 **이고** 상 불평형 < 0.05 **이고** I₂/I₁ < 경고(0.05) → '경부하(참고)' advisory, 종합 미반영 · (b) 한 상만 저전류 / 저전류+불평형 ≥ 0.05 / 저전류+I₂/I₁ ≥ 위험(0.10) → 결상 의심 DANGER(기존) · (c) 상한 1.10/1.25·히스테리시스 5 %·지속 3 s 불변.

| 시나리오 | r R/S/T | 불평형 | I₂/I₁ | 전 | 후 (원인) | advisory | 변경 |
|---|---|---|---|---|---|---|---|
| healthy | 1.019/0.979/0.979 | 0.027 | 0.027 | SAFE (-) | **SAFE** (-) | — | — |
| itsc_4turn | 1.103/1.027/0.974 | 0.066 | 0.0726 | WARN (i2i1) | **WARN** (i2i1) | — | — |
| itsc_8turn | 1.297/1.133/0.973 | 0.143 | 0.1676 | DANGER (i2i1) | **DANGER** (i2i1) | — | — |
| itsc_12turn | 1.563/1.272/0.992 | 0.226 | 0.2696 | DANGER (i2i1) | **DANGER** (i2i1) | — | — |
| itsc_16turn | 1.881/1.433/1.042 | 0.295 | 0.3625 | DANGER (i2i1) | **DANGER** (i2i1) | — | — |
| itsc_4turn_resistive | 1.030/0.986/0.979 | 0.032 | 0.0324 | SAFE (-) | **SAFE** (-) | — | — |
| itsc_4turn_halfload | 0.731/0.685/0.619 | 0.087 | 0.0953 | WARN (i2i1) | **WARN** (i2i1) | — | — |
| overload | 1.386/1.332/1.332 | 0.027 | 0.027 | DANGER (current_ratio) | **DANGER** (current_ratio) | — | — |
| voltage_unbalance | 1.080/0.940/0.980 | 0.080 | 0.0595 | WARN (i2i1) | **WARN** (i2i1) | — | — |
| single_phasing | 0.036/1.278/1.278 | 0.958 | 0.4792 | DANGER (current_ratio) | **DANGER** (current_ratio) | — | — |
| no_load | 0.339/0.326/0.326 | 0.027 | 0.027 | DANGER (current_ratio) | **SAFE** (-) | 경부하(참고) | **변경** |

변경된 시나리오: no_load. 사유: 호이스트는 무부하(권상 대기) 운전이 잦고 그때 자화 전류만 흘러 r ≈ 0.33~0.5 가 정상이다 — 세 상이 고르게 낮고 균형이면 결상이 아니다.
