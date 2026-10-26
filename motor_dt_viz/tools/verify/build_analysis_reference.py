# -*- coding: utf-8 -*-
"""build_analysis_reference.py — 해석 근거값 모음 data/electrical/analysis_reference.json (V6, 2026-10-21). **수기 숫자 없음** — 전부 파일에서 읽고 입력 sha256 을 기록한다.

입력(읽기 전용):
  Maxwell 저장소 maxwell/results/: mccm_results.json(등가회로 케이스), mccm_lut.json(8턴 등 격자), f2_corrections.json(F1 FEM I_f·F2 스큐 보정), f7_iec_tolerance.json(IEC 허용차·Z₂ 불확실성),
                                   eddy2d/summary.json(2D FEM 정격·잠김·역상 Z₂), rmxprt_v2m2.json(RMxprt 정격·회로 상수), rmxprt_temp_sweep.json(R1 20/95 °C), magnetizing_curve_2d.json(FEM X_total),
                                   inductance_matrix_2d.json(단락 턴 인덕턴스)
  DT: config/electrical.yaml(고유 비대칭·LUT sha), data/electrical/M1_mccm_lut_v2.json(시나리오 격자점), config/thresholds.yaml(경계·지속), config/motors/M1.yaml(카탈로그), config/thermal.yaml + engine(열 모델 정상 상태 역산 — 모델 자기 일관성 기준)
출력: data/electrical/analysis_reference.json (+ dashboard/public/data/electrical/ 사본)

  py -3.12 -X utf8 tools/verify/build_analysis_reference.py [--maxwell <루트>]
"""
from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import os

def _maxwell_root() -> str:
    """Maxwell 저장소 위치: MAXWELL_ROOT 환경변수 → 바탕 화면\\권상모터_3D모델링 → 바탕 화면\\모터\\권상모터_3D모델링 (2026-10-26 바탕화면 정리로 이동)."""
    env = os.environ.get("MAXWELL_ROOT")
    if env:
        return env
    desk = os.path.join(os.path.expanduser("~"), "OneDrive", "바탕 화면")
    for c in (os.path.join(desk, "권상모터_3D모델링"), os.path.join(desk, "모터", "권상모터_3D모델링")):
        if os.path.isdir(c):
            return c
    return os.path.join(desk, "모터", "권상모터_3D모델링")
import shutil
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)
from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load, val  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

MAXWELL_DEFAULT = _maxwell_root()   # D1: MAXWELL_ROOT 환경변수 (docs/REPRODUCE.md)
SCENARIOS = {   # 시나리오 → (턴, R_f, 부하, MCCM 케이스 이름)
    "healthy": (0, None, 1.0, "C0"), "itsc_4turn": (4, 0.1, 1.0, "C1"), "itsc_8turn": (8, 0.1, 1.0, None), "itsc_12turn": (12, 0.1, 1.0, "C3"),
    "itsc_16turn": (16, 0.1, 1.0, "C4"), "itsc_4turn_resistive": (4, 1.0, 1.0, "C1-R"), "itsc_4turn_halfload": (4, 0.1, 0.5, "C1-L"),
}
GRADE = {"catalog": "카탈로그", "rmxprt": "RMxprt v2m2 정합(등가회로 상수)", "mccm": "등가회로 MCCM(RMxprt v2m2 + 다중결합 회로, Z₂ 카탈로그 앵커)",
         "lut": "등가회로 LUT v2 (MCCM 격자, DT 등록)", "fem2d": "2D 와전류 FEM lite(학생판, 단순화 기하, F1/F2 보정)", "standard": "표준(IEC 60034-1 허용차)",
         "assumed": "가정", "model": "열회로 모델 자기 일관성(22 kW 기준 스케일 — 실측 아님)", "dataset": "참고 데이터셋(AI Hub 정상 중앙값)"}


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rel(p: str) -> str:
    return os.path.relpath(p, REPO).replace("\\", "/") if p.startswith(REPO) else p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maxwell", default=MAXWELL_DEFAULT)
    ap.add_argument("--out", default=os.path.join(VIZ, "data", "electrical", "analysis_reference.json"))
    a = ap.parse_args()
    MR = os.path.join(a.maxwell, "maxwell", "results")
    files = {"mccm_results": os.path.join(MR, "mccm_results.json"), "mccm_lut": os.path.join(MR, "mccm_lut.json"), "f2": os.path.join(MR, "f2_corrections.json"),
             "f7": os.path.join(MR, "f7_iec_tolerance.json"), "eddy_summary": os.path.join(MR, "eddy2d", "summary.json"), "rmxprt": os.path.join(MR, "rmxprt_v2m2.json"),
             "temp_sweep": os.path.join(MR, "rmxprt_temp_sweep.json"), "magcurve": os.path.join(MR, "magnetizing_curve_2d.json"), "inductance": os.path.join(MR, "inductance_matrix_2d.json"),
             "analysis_tables_xlsx": os.path.join(MR, "analysis_tables.xlsx"),
             "electrical_yaml": os.path.join(VIZ, "config", "electrical.yaml"), "lut_dt": os.path.join(VIZ, "data", "electrical", "M1_mccm_lut_v2.json"),
             "thresholds_yaml": os.path.join(VIZ, "config", "thresholds.yaml"), "m1_yaml": os.path.join(VIZ, "config", "motors", "M1.yaml"), "thermal_yaml": os.path.join(VIZ, "config", "thermal.yaml"),
             "lut_report": os.path.join(VIZ, "docs", "electrical", "lut_integration_report.md")}
    missing = [k for k, p in files.items() if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"입력 없음: {missing}")
    J = {k: json.load(open(p, encoding="utf-8")) for k, p in files.items() if p.endswith(".json")}
    el = yaml.safe_load(open(files["electrical_yaml"], encoding="utf-8")); th = yaml.safe_load(open(files["thresholds_yaml"], encoding="utf-8"))
    m1y = yaml.safe_load(open(files["m1_yaml"], encoding="utf-8"))
    inputs = {k: {"path": rel(p), "sha256": sha(p)} for k, p in files.items()}
    src = lambda key, grade, note="": {"file": inputs[key]["path"], "sha256": inputs[key]["sha256"][:12], "grade": GRADE[grade], "grade_key": grade, **({"note": note} if note else {})}   # noqa: E731

    # ---------------- 공통 상수
    h = float(el["inherent"]["i2i1"]) if el["inherent"].get("enabled") else 0.0
    h_angle = float(el["inherent"].get("angle_deg") or 0.0)
    I_n = float(el["rated_current_A"]); N_ph = int(el["base_turns_per_phase"])
    ns = th["current"]["negative_sequence"]; rr = th["current_ratio"]                      # 판정 엔진(engine/thresholds.py)과 같은 키: safe_low/safe_high/danger_over/danger_under
    warn, danger = float(ns["warn"]), float(ns["danger"])
    persist = float(th["persistence_s"]["i2i1"])
    rp = J["mccm_results"]["params_after"]; R1_hot = float(rp["R1_hot"])
    lut_rows = J["lut_dt"]["rows"]; mx_rows = J["mccm_lut"]["rows"] if isinstance(J["mccm_lut"], dict) and "rows" in J["mccm_lut"] else None

    def lut_row(turns, rf, load):
        for r in lut_rows:
            if int(r["turns"]) == turns and r["load"] == load and (turns == 0 or abs(float(r["R_f"]) - rf) < 1e-9):
                return r
        return None

    sl, sh, do, du = (float(rr[k]) for k in ("safe_low", "safe_high", "danger_over", "danger_under"))

    def ratio_levels(ia, ib, ic):
        lv = []
        for i in (ia, ib, ic):
            r = i / I_n
            lv.append("DANGER" if (r > do or r < du) else "WARN" if (r > sh or r < sl) else "SAFE")
        return lv

    A_OP = cmath.exp(2j * math.pi / 3)

    def sim_phases(fault, theta_deg, i1_lut, ang_deg):
        """엔진 규약 재현(독립 수식, D3 2026-10-21): I₁ = LUT 정상분 RMS(격자값), I₂ = I₁·(r·e^{jθ} + h·e^{jφ}) → Ia = I₁+I₂, Ib = a²I₁ + aI₂, Ic = aI₁ + a²I₂ (RMS 크기)."""
        i1 = i1_lut; i2 = i1 * (fault * cmath.exp(1j * math.radians(theta_deg)) + h * cmath.exp(1j * math.radians(ang_deg)))
        ph = [i1 + i2, A_OP ** 2 * i1 + A_OP * i2, A_OP * i1 + A_OP ** 2 * i2]
        rms = [abs(x) for x in ph]; mean = sum(rms) / 3
        return [round(x, 5) for x in rms], round(max(abs(x - mean) for x in rms) / mean * 100, 4)

    def i2i1_level(v):
        return "DANGER" if v >= danger else "WARN" if v >= warn else "SAFE"

    # ---------------- 열 모델(자기 일관성 기준): 정상 상태 ΔT_winding — 엔진 손실·열저항으로 선형 해
    motor = ml.load_motor("M1"); tm = ThermalModel(ml.thermal_cfg(motor)); cm = CurrentModel(ml.electrical_cfg(motor), ml.motor_spec(motor))
    from viz.m1_model import M1Model                       # 8턴·16턴·저항성·반부하 케이스는 데모와 같은 경로로 런타임 등록 (scenarios_M1.yaml extra_cases, electrical.yaml 불변)
    M1Model.register_extra_cases(cm, VIZ)
    import numpy as np

    def steady_dT(case, load):
        st_ph = cm.evaluate_case(case, "rated_phase_A")
        pu = cm.winding_current_pu(st_ph)
        P = tm.losses(load, [], pu, {"winding": cm.loop_loss_W(case)} if cm.loop_loss_W(case) > 0 else None)
        R = tm.r_ambient([]); G = tm.conductance([]); L = np.diag(G.sum(axis=1)) - G
        dT = np.linalg.solve(np.diag(1.0 / R) + L, P)
        return {k: round(float(dT[tm.index[k]]), 3) for k in ("winding", "stator_core", "rotor", "bearing_de", "frame")}, round(float(pu), 5), [round(float(x), 2) for x in P]

    # ---------------- 시나리오별
    scen = {}
    for sid, (turns, rf, load_, cname) in SCENARIOS.items():
        r = lut_row(turns, rf if rf is not None else 0.03, load_)
        if r is None:
            raise SystemExit(f"LUT 격자 없음 {sid}")
        rf_used = float(r["R_f"]) if turns else None
        fault = float(r["I2_over_I1"]); theta = float(r["I2_angle_deg_vs_I1"])
        comp = {f"angle_{ang}": round(abs(fault * cmath.exp(1j * math.radians(theta)) + h * cmath.exp(1j * math.radians(ang))), 6) for ang in (0, 90, 180)}
        comp_range = [round(abs(fault - h), 6), round(fault + h, 6)]
        mu = turns / N_ph
        p_loop_formula = float(r["I_f"]) ** 2 * ((rf_used or 0.0) + mu * R1_hot) if turns else 0.0
        mc = J["mccm_results"]["cases"].get(cname) if cname else None
        fem = None
        if turns == 4 and load_ == 1.0 and rf_used in (0.1, 1.0):
            k = "0.1" if rf_used == 0.1 else "1.0"
            fem = {"I_f_A": float(J["f2"]["F1"][k]["I_f_after"]), "I_abc_A": J["f2"]["F1"][k]["I_abc_after"], "dev_vs_mccm_pct": float(J["f2"]["F1"][k]["dev_after_pct"]),
                   "pass_5pct": bool(J["f2"]["F1"][k]["pass_5pct"]), **src("f2", "fem2d", "F1: FaultLoop 에 단락 턴 저항 포함(2D lite, 학생판)")}
        dT, pu, P = steady_dT(sid, load_)
        i1_lut = float(r["I1_A"])                                   # D3: 시뮬 I₁ = LUT 정상분 RMS (격자값)
        sim_rms, sim_unb = sim_phases(fault, theta, i1_lut, h_angle)
        lv_ratio = ratio_levels(*sim_rms); lv_i2 = i2i1_level(comp["angle_0"])
        order = {"SAFE": 0, "WARN": 1, "DANGER": 2}
        overall = max([lv_i2] + lv_ratio, key=lambda x: order[x])
        # 엔진 규약(D3): I₁ = LUT 정상분 RMS(결함 시 상승), I₂ = I₁·(결함 + 고유) → 시뮬 I₂/I_n = 합성 I₂/I₁ × I₁_LUT / I_n (결함분만이면 LUT I₂/I_n 과 같다)
        sim_i2_over_in_expected = round(comp["angle_0"] * i1_lut / I_n, 6)
        scen[sid] = {
            "turns": turns, "turn_ratio_pct": round(mu * 100, 3), "R_f_ohm": rf_used, "load": load_, "mccm_case": cname,
            "i2_over_i1_fault": {"value": round(fault, 6), "angle_deg_vs_i1": round(theta, 3), **src("lut_dt", "lut"), "maxwell_grid": src("mccm_lut", "mccm")},
            "i2_over_i1_composite": {"inherent": h, "inherent_angle_deg": h_angle, "range": comp_range, "expected_by_angle": comp, "tolerance": "범위 |r−h| ~ r+h 안",
                                     "source_inherent": {"file": inputs["electrical_yaml"]["path"], "sha256": inputs["electrical_yaml"]["sha256"][:12], "grade": GRADE["dataset"], "grade_key": "dataset", "note": el["inherent"].get("source", "")}},
            "i2_over_in": {"lut": round(float(r["I2_over_In"]), 6), "lut_I1_A": round(float(r["I1_A"]), 5), "sim_expected": sim_i2_over_in_expected,
                           "note": "D3(2026-10-21): 시뮬 I₁ = LUT 정상분 RMS → 결함분 I₂/I_n 이 LUT 와 같고, 표시값(합성)은 고유 비대칭만큼 더 크다", **src("lut_dt", "lut")},
            "unbalance_max_dev_pct": {"lut": round(float(r["unbalance_max_dev_pct"]), 4), "lut_I_abc_A": [round(float(r[k]), 5) for k in ("I_a", "I_b", "I_c")],
                                      "sim_expected": sim_unb, "sim_expected_I_abc_A": sim_rms, "note": "sim_expected = 엔진 규약(D3: I₁ = LUT 정상분 RMS, 결함 I₂ + 고유 비대칭 합성)으로 독립 계산한 RMS 의 불평형", **src("lut_dt", "lut")},
            "i_f_A": {"mccm": round(float(mc["I_f"]), 4) if mc else None, "lut": round(float(r["I_f"]), 4), "fem_corrected": fem, **src("mccm_results", "mccm")},
            "p_loop_total_W": {"lut": round(float(r["P_loop_total_W"]), 3), "mccm": round(float(mc["P_loop_total_W"]), 3) if mc else None,
                               "formula": "I_f²·(R_f + μ·R1_hot), μ = turns/N_ph", "formula_value": round(p_loop_formula, 3), "R1_hot_ohm": R1_hot, "N_ph": N_ph, **src("mccm_results", "mccm")},
            "winding_dT_steady_C": {"model": dT, "winding_current_pu": pu, "loss_W_nodes": P, "tolerance_pct": 5.0, "grade": GRADE["model"], "grade_key": "model",
                                    "file": inputs["thermal_yaml"]["path"], "sha256": inputs["thermal_yaml"]["sha256"][:12],
                                    "note": "열회로(22 kW 기준 손실비 스케일) + 단락 루프 손실 → 권선 노드. 실측 아님, M1 에서 낙관적일 수 있음"},
            "expected_judgment": {"i2i1_level": lv_i2, "current_ratio_levels": lv_ratio, "current_ratio_levels_lut_I_abc": ratio_levels(float(r["I_a"]), float(r["I_b"]), float(r["I_c"])),
                                  "overall_expected": overall, "overall_note": "시뮬레이션 정책: provisional(i2i1·current_ratio) 포함, worst-of. 온도·진동은 전기 모드에서 상수(SAFE)",
                                  "thresholds": {"warn": warn, "danger": danger, "persistence_s": persist, "policy": th["judgment"]["provisional_policy"]["simulation"]},
                                  "detection_delay_expected_s": persist if i2i1_level(comp["angle_0"]) != "SAFE" else None,
                                  "file": inputs["thresholds_yaml"]["path"], "sha256": inputs["thresholds_yaml"]["sha256"][:12], "grade": "임계값(참고 데이터셋 provisional)", "grade_key": "dataset"},
            "z2_uncertainty": {"i2_uncertainty_pct": round(float(J["f7"]["Z2_uncertainty"]["I2_uncertainty_pct"]), 2), "sentence": J["f7"]["Z2_uncertainty"]["sentence"], **src("f7", "fem2d")},
        }
    # ---------------- 정격점·기동 (f7 표 + 카탈로그 + 2D FEM)
    f7t = {r["item"]: r for r in J["f7"]["table"]}
    rated = {"catalog": {"I_A": val(m1y["rated_line_current_a"]), "pf": val(m1y["power_factor"]), "eff": val(m1y["efficiency"]), "rpm": val(m1y["rated_rpm"]), **src("m1_yaml", "catalog")},
             "rmxprt_v2m2": {"I_A": J["rmxprt"]["results"]["I_rated"], "pf": J["rmxprt"]["results"]["pf"], "eff": J["rmxprt"]["results"]["eff"] / 100, "rpm": J["rmxprt"]["results"]["rpm"], "slip": J["rmxprt"]["results"]["slip"], **src("rmxprt", "rmxprt")},
             "mccm_calibrated": {"I_A": J["mccm_results"]["calibration"]["I"], "pf": J["mccm_results"]["calibration"]["pf"], "P_in_W": J["mccm_results"]["calibration"]["P_in_W"], **src("mccm_results", "mccm")},
             "fem_lite": {"I_A": J["eddy_summary"]["rated"]["I_rms_mean_A"], "pf": J["eddy_summary"]["rated"]["pf"], "eff": J["eddy_summary"]["rated"]["eff"], "T_Nm": J["eddy_summary"]["rated"]["T_Nm"], **src("eddy_summary", "fem2d")},
             "iec_tolerance": {"limits": J["f7"]["limits"], "table": J["f7"]["table"], **src("f7", "standard")}}
    starting = {"catalog": {"I_st_ratio": val(m1y["starting_current_pct"]) / 100, "T_st_ratio": val(m1y["starting_torque_pct"]) / 100, "T_max_ratio": val(m1y["max_torque_pct"]) / 100, **src("m1_yaml", "catalog")},
                "rmxprt_v2m2": {"I_st_ratio": J["rmxprt"]["results"]["I_st_ratio"], "T_st_ratio": J["rmxprt"]["results"]["T_st_ratio"], "T_max_ratio": J["rmxprt"]["results"]["T_max_ratio"], **src("rmxprt", "rmxprt")},
                "fem_corrected": {"I_st_ratio": J["f2"]["F2"]["I_st_corr"], "T_st_ratio": J["f2"]["F2"]["T_st_corr"], "I_st_2D_uncorrected": J["f2"]["F2"]["I_st_2D"], "T_st_2D_uncorrected": J["f2"]["F2"]["T_st_2D"],
                                  "correction": "F2 스큐·엔드링 누설 리액턴스 보정 (dX " + f"{J['f2']['F2']['dX_ohm']:.3f} Ω)", **src("f2", "fem2d")}}
    # ---------------- 등가회로
    ts = {r["T_C"]: r for r in J["temp_sweep"]["rows"]}
    mag = next((c for c in J["magcurve"]["magnetizing_curve"] if c.get("k") == 1.0), None)
    Lm = (J["inductance"].get("lite_q_s2") or {}).get("L_matrix_source_level_H") or {}
    circuit = {"R1_ohm": {"20C": ts[20]["R1"], "95C": ts[95]["R1"], "used_hot": R1_hot, **src("temp_sweep", "rmxprt")},
               "R2p_ohm": {"rmxprt_95C": ts[95]["R2p"], "mccm_hot_calibrated": rp["R2p"], **src("mccm_results", "mccm", "물리 보정: 기계출력 2,236 W 맞춤")},
               "X1_ohm": {"rmxprt": rp["X1"], **src("rmxprt", "rmxprt")}, "X2p_ohm": {"rmxprt": rp["X2p"], **src("rmxprt", "rmxprt")},
               "Xm_ohm": {"rmxprt": rp["Xm"], "fem_X_total_at_rated_Im": mag["X_total_ohm"] if mag else None, "fem_I_m_rms_A": mag["I_rms_A"] if mag else None, **src("magcurve", "fem2d")},
               "Z2_ohm": {"anchor_catalog": rp["Z_sc"], "fem_negseq": J["eddy_summary"]["negseq"]["Z2_fem_ohm"], "fem_corrected": J["f2"]["F2"]["Z2_corr"][-1], "dev_pct": J["f2"]["F2"]["Z2_dev_pct"], **src("eddy_summary", "fem2d")},
               "short_turn_inductance_H": {"fem_self_top": Lm.get("I_Coil_01_top_short,I_Coil_01_top_short"), "fem_self_bot": Lm.get("I_Coil_01_bot_short,I_Coil_01_bot_short"),
                                           "fem_mutual_top_main": Lm.get("I_Coil_01_top_main,I_Coil_01_top_short"), "mccm_assumption": "LUT note: 단락 턴 누설 9.5 mΩ (2D lite 파라미터로 재계산한 v3 와 7 케이스 < 0.6 %)", **src("inductance", "fem2d")},
               "Rfe_ohm": {"mccm_physical": rp["Rfe"], "rmxprt": J["rmxprt"]["results"]["Rfe"], **src("mccm_results", "mccm")}}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "generator": "motor_dt_viz/tools/verify/build_analysis_reference.py", "no_manual_numbers": True,
           "motor": "M1 현대 HLP-2.2/4", "I_n_A": I_n, "N_ph": N_ph, "inherent_i2i1": h, "thresholds": {"i2i1_warn": warn, "i2i1_danger": danger, "persistence_s": persist, "current_ratio": {k: float(rr[k]) for k in ("safe_low", "safe_high", "danger_over", "danger_under")}},
           "lut": {"dt_file": inputs["lut_dt"]["path"], "dt_sha256": inputs["lut_dt"]["sha256"], "sha_in_electrical_yaml": el["source"].get("lut_sha256"), "sha_match": el["source"].get("lut_sha256") == inputs["lut_dt"]["sha256"],
                   "maxwell_source_sha256": J["lut_dt"]["provenance"].get("source_sha256"), "grade": el["source"].get("grade"), "status": el["source"].get("status"), "fem_verified": el["source"].get("fem_verified")},
           "grades": GRADE, "inputs": inputs, "scenarios": scen, "rated_point": rated, "starting": starting, "equivalent_circuit": circuit,
           "limitations": ["합성 신호(엔진 페이저 합성) — 실측 아님", f"고유 비대칭 {h} 은 건전 하한 가정(AI Hub L-EF-04·R-EF-05 중앙값; L-SF-04 실측 p95 0.1005 는 품질 부적합)", "Z₂ 카탈로그 앵커 7.136 Ω vs FEM 5.97 Ω → LUT I₂ 불확실성 +20 %",
                           "2D lite: 무스큐·분산 결함·단순화 기하(학생판), 시간 파형·RSH 없음", "열 모델은 22 kW 기준 스케일 — M1 에서 낙관적일 수 있음(실측 전 보정 불가)", "기계 결함(베어링·오정렬·팬·브레이크)은 Maxwell 근거 없음 — 진동·베어링 상수(표준/AI Hub 참고)"],
           "mechanical_note": "Maxwell 근거 없음 — 진동·베어링 상수(ISO 10816-1 Class I 표준 / AI Hub 참고 데이터셋)"}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    dash = os.path.join(REPO, "dashboard", "public", "data", "electrical", "analysis_reference.json")
    if os.path.isdir(os.path.dirname(dash)):
        shutil.copyfile(a.out, dash)
    print(f"→ {a.out} (시나리오 {len(scen)}, 입력 {len(inputs)}, LUT sha 일치 {out['lut']['sha_match']})" + (f" + {dash}" if os.path.exists(dash) else ""))


if __name__ == "__main__":
    main()
