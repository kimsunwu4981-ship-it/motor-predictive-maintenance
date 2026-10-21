# -*- coding: utf-8 -*-
"""judgment_before_after.py — 저전류 경부하 참고 규칙(2026-10-21 승인) 전후 11 시나리오 판정 표 → docs/verification/light_load_rule.md (+ .json).
'전' = low_current_policy.light_load_advisory 를 False 로 둔 같은 엔진, '후' = 현재 설정. 값은 엔진(stateless) 출력뿐.

  py -3.12 -X utf8 tools/verify/judgment_before_after.py
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)
from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.thresholds import Judge  # noqa: E402
from viz.m1_model import M1Model  # noqa: E402

CASES = ["healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload", "overload", "voltage_unbalance", "single_phasing", "no_load"]


def main():
    m = ml.load_motor("M1"); cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m)); M1Model.register_extra_cases(cm, VIZ)
    I_n = cm.rated_current_A
    c_new = copy.deepcopy(load("thresholds")); c_old = copy.deepcopy(c_new); c_old["current_ratio"]["low_current_policy"]["light_load_advisory"] = False
    rows = []
    for case in CASES:
        st = cm.evaluate_case(case)
        r = [x / I_n for x in st.rms_A]; mean = sum(r) / 3; unb = max(abs(x - mean) for x in r) / mean
        sig = {"current_ratio": {p: r[i] for i, p in enumerate("ABC")}, "i2i1": st.i2_over_i1}
        vo, vn = Judge(c_old, motor=m).stateless(sig), Judge(c_new, motor=m).stateless(sig)
        rows.append({"case": case, "r": [round(x, 3) for x in r], "unbalance": round(unb, 4), "i2i1": round(st.i2_over_i1, 4),
                     "before": vo.status, "before_cause": vo.cause_signal, "after": vn.status, "after_cause": vn.cause_signal,
                     "advisory": sorted({s.note.split(":")[0] for s in vn.advisory}), "changed": vo.status != vn.status})
    pol = c_new["current_ratio"]["low_current_policy"]
    doc = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "policy": pol, "rows": rows, "changed": [r["case"] for r in rows if r["changed"]]}
    out = os.path.join(REPO, "docs", "verification"); os.makedirs(out, exist_ok=True)
    json.dump(doc, open(os.path.join(out, "light_load_rule.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["# 저전류 판정 규칙 변경 — 경부하(참고) (2026-10-21 승인) 전후 표", "",
         f"생성 {doc['generated']} · `tools/verify/judgment_before_after.py` · 설정 `current_ratio.low_current_policy` = {pol} · 엔진 stateless(시뮬레이션 정책).", "",
         "규칙: (a) 세 상 함께 r < 0.50 **이고** 상 불평형 < 0.05 **이고** I₂/I₁ < 경고(0.05) → '경부하(참고)' advisory, 종합 미반영 · (b) 한 상만 저전류 / 저전류+불평형 ≥ 0.05 / 저전류+I₂/I₁ ≥ 위험(0.10) → 결상 의심 DANGER(기존) · (c) 상한 1.10/1.25·히스테리시스 5 %·지속 3 s 불변.", "",
         "| 시나리오 | r R/S/T | 불평형 | I₂/I₁ | 전 | 후 (원인) | advisory | 변경 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['case']} | {'/'.join(f'{x:.3f}' for x in r['r'])} | {r['unbalance']:.3f} | {r['i2i1']} | {r['before']} ({r['before_cause']}) | **{r['after']}** ({r['after_cause']}) | {', '.join(r['advisory']) or '—'} | {'**변경**' if r['changed'] else '—'} |")
    L += ["", f"변경된 시나리오: {', '.join(doc['changed']) or '없음'}. 사유: 호이스트는 무부하(권상 대기) 운전이 잦고 그때 자화 전류만 흘러 r ≈ 0.33~0.5 가 정상이다 — 세 상이 고르게 낮고 균형이면 결상이 아니다."]
    open(os.path.join(out, "light_load_rule.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"→ {out}/light_load_rule.md — 변경 {doc['changed']}")


if __name__ == "__main__":
    main()
