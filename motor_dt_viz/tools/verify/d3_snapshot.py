# -*- coding: utf-8 -*-
"""d3_snapshot.py — 엔진(현재 코드)으로 M1 전기 시나리오 7종의 I₁·상별 RMS·r·I₂/I₁·I₂/I_n·권선 전류 pu·정상 상태 권선 ΔT 를 찍는다 (D3 I₁ 변경 전후 표용).
  py -3.12 -X utf8 tools/verify/d3_snapshot.py <out.json>  |  --table before.json after.json > md
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, VIZ)
CASES = ["healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload", "overload", "voltage_unbalance", "single_phasing", "no_load"]


def snapshot() -> dict:
    from engine import motor_library as ml
    from engine.current_model import CurrentModel
    from engine.thermal_model import ThermalModel
    from engine.thresholds import Judge
    from viz.m1_model import M1Model
    m = ml.load_motor("M1"); cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m)); M1Model.register_extra_cases(cm, VIZ)
    tm = ThermalModel(ml.thermal_cfg(m)); judge = Judge(motor=m); I_n = cm.rated_current_A
    out = {}
    for c in CASES:
        if c not in cm.cases:
            continue
        st = cm.evaluate_case(c, "rated_line_A"); sp = cm.evaluate_case(c, "rated_phase_A")
        pu = cm.winding_current_pu(sp); load = float(cm.cases[c].get("load", 1.0))
        P = tm.losses(load, [], pu, {"winding": cm.loop_loss_W(c)} if cm.loop_loss_W(c) > 0 else None)
        R = tm.r_ambient([]); G = tm.conductance([]); L = np.diag(G.sum(axis=1)) - G
        dT = np.linalg.solve(np.diag(1.0 / R) + L, P)
        v = judge.stateless({"current_ratio": {p: st.rms_A[k] / I_n for k, p in enumerate("ABC")}, "i2i1": st.i2_over_i1})
        out[c] = {"method": st.source.get("case_method"), "i1_A": round(st.i1_A, 4), "rms_A": [round(x, 4) for x in st.rms_A], "r": [round(x / I_n, 4) for x in st.rms_A],
                  "i2_over_i1": round(st.i2_over_i1, 5), "i2_over_in": None if st.i2_over_in is None else round(st.i2_over_in, 5), "winding_pu": round(pu, 4),
                  "dT_winding_C": round(float(dT[tm.index["winding"]]), 2), "status": v.status, "cause": v.cause_signal,
                  "levels": {s.kind + ("/" + s.component if s.component not in ("-", "") else ""): s.level for s in v.signals}}
    return out


def table(before: dict, after: dict) -> str:
    L = ["| 시나리오 | 방식 | I₁ [A] 전→후 | r=I/I_n (R/S/T) 전 → 후 | I₂/I₁ 전→후 | I₂/I_n 전→후 | 권선 pu 전→후 | 권선 ΔT [°C] 전→후 | 판정 전→후 |", "|---|---|---|---|---|---|---|---|---|"]
    for c, a in after.items():
        b = before.get(c, a)
        chg = "" if b["status"] == a["status"] and b["cause"] == a["cause"] else " **(변경)**"
        L.append(f"| {c} | {a['method']} | {b['i1_A']} → {a['i1_A']} | {'/'.join(f'{x:.3f}' for x in b['r'])} → {'/'.join(f'{x:.3f}' for x in a['r'])} | {b['i2_over_i1']} → {a['i2_over_i1']} | {b['i2_over_in']} → {a['i2_over_in']} | "
                 f"{b['winding_pu']} → {a['winding_pu']} | {b['dT_winding_C']} → {a['dT_winding_C']} | {b['status']}({b['cause']}) → {a['status']}({a['cause']}){chg} |")
    return "\n".join(L)


if __name__ == "__main__":
    if sys.argv[1] == "--table":
        print(table(json.load(open(sys.argv[2], encoding="utf-8")), json.load(open(sys.argv[3], encoding="utf-8"))))
    else:
        json.dump(snapshot(), open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("→", sys.argv[1])
