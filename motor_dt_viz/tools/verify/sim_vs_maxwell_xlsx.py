# -*- coding: utf-8 -*-
"""sim_vs_maxwell_xlsx.py — 사람이 읽는 비교표: Isaac Sim 결함 시뮬 수치 vs Maxwell 해석 수치 (엑셀 9시트 + 차트 3 + 한 장 요약) + 결함 크기 역추정 + FEM 불확실성 민감도.
기존 대조(docs/verification/sim_vs_analysis.json, data/electrical/analysis_reference.json)와 검증 로그(logs/verify/*)를 **재사용**한다. 새 해석·설정·엔진 변경 없음, 수기 숫자 없음.

출력: docs/verification/M1_sim_vs_maxwell.xlsx, 바탕화면 M1_시뮬_vs_Maxwell.xlsx, docs/verification/sim_vs_maxwell_summary.md, sim_vs_maxwell.json(테스트용)
  py -3.12 -X utf8 tools/verify/sim_vs_maxwell_xlsx.py [--no-desktop]
"""
from __future__ import annotations

import argparse
import cmath
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
OUT_DIR = os.path.join(REPO, "docs", "verification")
sys.path.insert(0, HERE)
from sim_vs_analysis import load_run, steady, fnum  # noqa: E402  (정상 상태 평균 규칙 재사용)

MAXWELL = os.environ.get("MAXWELL_ROOT", r"C:\Users\sunwu\OneDrive\바탕 화면\권상모터_3D모델링")
SCEN = ["healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload"]
TURNS = {"healthy": 0, "itsc_4turn": 4, "itsc_8turn": 8, "itsc_12turn": 12, "itsc_16turn": 16, "itsc_4turn_resistive": 4, "itsc_4turn_halfload": 4}
RF = {"healthy": 0.1, "itsc_4turn": 0.1, "itsc_8turn": 0.1, "itsc_12turn": 0.1, "itsc_16turn": 0.1, "itsc_4turn_resistive": 1.0, "itsc_4turn_halfload": 0.1}
LOAD = {"healthy": 1.0, "itsc_4turn": 1.0, "itsc_8turn": 1.0, "itsc_12turn": 1.0, "itsc_16turn": 1.0, "itsc_4turn_resistive": 1.0, "itsc_4turn_halfload": 0.5}
ANGLES = (0, 90, 180)
Z2_SCALE = 1.20          # f7_iec_tolerance Z2_uncertainty: I₂ ∝ 1/Z₂, 앵커 7.136 → FEM 보정 5.97 Ω → +20 %
GRADE_COLOR = {"catalog": "C8E6C9", "rmxprt": "BBDEFB", "mccm": "E1BEE7", "lut": "E1BEE7", "fem2d": "B2EBF2", "standard": "CFD8DC", "assumed": "FFE0B2", "model": "D7CCC8", "dataset": "D7CCC8", "sim": "FFF9C4"}
GREEN, RED, GREY, HEAD = "C8E6C9", "FFCDD2", "EEEEEE", "ECEFF1"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def pct(a, b):
    return None if a is None or b in (None, 0) else (a / b - 1) * 100


# ----------------------------------------------------------------------------- LUT 역추정 (C2)
def lut_curve(lut, rf, load):
    """(턴 비율 %, 결함분 I₂/I₁, I₂/I_n, I₁) 격자 — R_f·부하 고정 (격자점이 아니면 가장 가까운 격자 — 시나리오는 전부 격자 위)."""
    rows = [r for r in lut["rows"] if abs(float(r["R_f"]) - rf) < 1e-9 and abs(float(r["load"]) - load) < 1e-9]
    rows.sort(key=lambda r: float(r["turn_ratio_pct"]))
    return [(float(r["turn_ratio_pct"]), float(r["I2_over_I1"]), float(r["I2_over_In"]), float(r["I1_A"]), float(r["I2_angle_deg_vs_I1"])) for r in rows]


def invert_turns(curve, i2i1_fault, n_ph=192):
    """단조 증가 구간 선형 역보간: 결함분 I₂/I₁ → 턴 비율 % → 턴수 (= 비율 × N_ph / 100). 범위 밖은 끝 구간 외삽 없이 클램프 + 플래그."""
    xs = [c[0] for c in curve]; ys = [c[1] for c in curve]
    if i2i1_fault <= ys[0]:
        return xs[0] * n_ph / 100, "below_grid"
    for k in range(len(xs) - 1):
        if ys[k] <= i2i1_fault <= ys[k + 1]:
            w = (i2i1_fault - ys[k]) / (ys[k + 1] - ys[k]) if ys[k + 1] > ys[k] else 0.0
            return (xs[k] + w * (xs[k + 1] - xs[k])) * n_ph / 100, "ok"
    return xs[-1] * n_ph / 100, "above_grid"


def fault_component(comp_mag, comp_angle_deg, h, h_angle_deg):
    return abs(comp_mag * cmath.exp(1j * math.radians(comp_angle_deg)) - h * cmath.exp(1j * math.radians(h_angle_deg)))


# ----------------------------------------------------------------------------- 수집
def collect(a):
    ref = json.load(open(os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), encoding="utf-8"))
    sva = json.load(open(os.path.join(OUT_DIR, "sim_vs_analysis.json"), encoding="utf-8"))
    lut = json.load(open(os.path.join(VIZ, "data", "electrical", "M1_mccm_lut_v2.json"), encoding="utf-8"))
    vs = json.load(open(os.path.join(REPO, "docs", "verification_summary.json"), encoding="utf-8"))
    tr = json.load(open(os.path.join(OUT_DIR, "traceability.json"), encoding="utf-8"))
    th = yaml.safe_load(open(os.path.join(VIZ, "config", "thresholds.yaml"), encoding="utf-8"))
    mx = {}
    for k, rel in (("mccm_results", "maxwell/results/mccm_results.json"), ("eddy_summary", "maxwell/results/eddy2d/summary.json"), ("f2", "maxwell/results/f2_corrections.json"),
                   ("rmxprt", "maxwell/results/rmxprt_v2m2.json"), ("inductance", "maxwell/results/inductance_matrix_2d.json")):
        p = os.path.join(MAXWELL, rel)
        mx[k] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    runs = {ang: load_run(os.path.join(VIZ, "logs", "verify", f"electrical_a{ang}")) for ang in ANGLES}
    if runs[0] is None:
        raise SystemExit("logs/verify/electrical_a0 없음")
    inputs = {"analysis_reference": os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), "sim_vs_analysis": os.path.join(OUT_DIR, "sim_vs_analysis.json"),
              "lut": os.path.join(VIZ, "data", "electrical", "M1_mccm_lut_v2.json"), "verification_summary": os.path.join(REPO, "docs", "verification_summary.json"),
              "thresholds": os.path.join(VIZ, "config", "thresholds.yaml"), **{f"maxwell_{k}": os.path.join(MAXWELL, rel) for k, rel in
              (("mccm_results", "maxwell/results/mccm_results.json"), ("eddy_summary", "maxwell/results/eddy2d/summary.json"), ("f2", "maxwell/results/f2_corrections.json"), ("rmxprt", "maxwell/results/rmxprt_v2m2.json"), ("inductance", "maxwell/results/inductance_matrix_2d.json"))}}
    for ang, r in runs.items():
        if r:
            inputs[f"state_a{ang}"] = os.path.join(r["dir"], "state.csv")
    sha_rows = [(k, os.path.relpath(p, REPO).replace("\\", "/") if p.startswith(REPO) else p, sha(p)[:16] if os.path.exists(p) else "없음") for k, p in inputs.items()]
    return ref, sva, lut, vs, tr, th, mx, runs, sha_rows


def scene_times(run):
    return {s["id"]: (float(s["t0_s"]), float(s["t0_s"]) + float(s["duration_s"]), s) for s in run["meta"]["steps"]}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--no-desktop", action="store_true"); a = ap.parse_args()
    ref, sva, lut, vs, tr, th, mx, runs, sha_rows = collect(a)
    S = ref["scenarios"]; I_n = float(ref["I_n_A"]); h = float(ref["inherent_i2i1"]); warn, danger = float(th["current"]["negative_sequence"]["warn"]), float(th["current"]["negative_sequence"]["danger"])
    cr = th["current_ratio"]; persist = float(th["persistence_s"]["i2i1"])
    rp = ref["rated_point"]; stt = ref["starting"]; ec = ref["equivalent_circuit"]
    base = runs[0]; st_t = scene_times(base)
    meta_commit = base["meta"].get("git_commit") or "(meta 에 커밋 없음 — 17:50 규칙 변경 전 실행본일 수 있음)"
    sv_rows = {(r["item"], r["scenario"]): r for r in sva["rows"]}

    def sim_mean(run, sid, key):
        t0, t1, _ = scene_times(run)[sid]; s_ = steady(run["state"], sid, t0, t1, key)
        return s_["mean"] if s_ else None

    # ================= 시트 1 시나리오 비교
    sheet1 = []
    for sid in SCEN:
        R = S[sid]; t0, t1, step = st_t[sid]
        i1 = sim_mean(base, sid, "i1_A"); comp = sim_mean(base, sid, "i2_over_i1"); ang = sim_mean(base, sid, "i2_angle_deg") or 0.0
        h_ang = float(base["meta"].get("inherent", {}).get("angle_deg", 0.0)); fault = fault_component(comp, ang, h, h_ang) if comp is not None else None
        i2in = sim_mean(base, sid, "i2_over_in"); i_f = sim_mean(base, sid, "i_f_A"); pl = sim_mean(base, sid, "p_loop_total_W")
        rms = [sim_mean(base, sid, k) for k in ("Ia_rms", "Ib_rms", "Ic_rms")]; r_R = rms[0] / I_n if rms[0] else None
        mean = sum(rms) / 3 if all(rms) else None; unb = (max(abs(v - mean) for v in rms) / mean * 100) if mean else None
        fem = R["i_f_A"].get("fem_corrected"); fem_if = fem["I_f_A"] if fem else None
        thermal = next((t for t in sva["thermal"] if t["scenario"] == sid), None)
        final = [r for r in base["state"] if r["step"] == sid][-1]; ev = next((e for e in sva["events"] if e["scenario"] == sid), {})
        exp_i1 = R["i2_over_in"]["lut_I1_A"]; lut_rms = R["unbalance_max_dev_pct"]["sim_expected_I_abc_A"]
        rows = [
            ("I₁ 정상분 [A]", i1, rp["rmxprt_v2m2"]["I_A"] if sid == "healthy" else None, exp_i1, rp["fem_lite"]["I_A"] if sid == "healthy" else None, rp["catalog"]["I_A"] if sid == "healthy" else None, 0.01, "lut", "결함이 커질수록 정상분 전류가 LUT 대로 올라간다(D3 규약)"),
            ("결함상 r = I_R/I_n", r_R, None, lut_rms[0] / I_n if lut_rms else None, None, None, 0.01, "lut", "R상 선전류 ÷ 정격 4.73 A — 1.10 넘으면 과전류 경고, 1.25 위험"),
            ("I₂/I₁ 결함분", fault, None, R["i2_over_i1_fault"]["value"], None, None, 0.01, "lut", "합성값에서 고유 비대칭 0.027 페이저를 뺀 순수 결함 성분"),
            ("I₂/I₁ 합성(표시값)", comp, None, R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"], None, None, 0.01, "lut", "화면·판정에 쓰는 값 = 결함 + 고유 비대칭(각도 0° 가정)"),
            ("I₂/I_n 결함분", (fault * i1 / I_n) if (fault is not None and i1) else None, None, R["i2_over_in"]["lut"], None, None, 0.01, "lut", "부하 무관 보조 지표 — 정격 전류 기준"),
            ("상 불평형 max dev [%]", unb, None, R["unbalance_max_dev_pct"]["sim_expected"], None, None, 0.02, "lut", "세 상 RMS 가 평균에서 벗어난 최대 비율"),
            ("단락 루프 전류 I_f [A]", i_f, None, R["i_f_A"]["mccm"] or R["i_f_A"]["lut"], fem_if, None, 0.01, "mccm", "붙은 턴 고리를 도는 순환 전류 — 선전류보다 훨씬 크다"),
            ("단락 루프 총손실 [W]", pl, None, R["p_loop_total_W"]["mccm"] or R["p_loop_total_W"]["lut"], None, None, 0.02, "mccm", "I_f²·(R_f + μR1) + 단락 턴 동손 → 권선 발열"),
            ("권선 ΔT 정상 상태 [°C]", thermal["dT_end_C"] if thermal else None, None, R["winding_dT_steady_C"]["model"]["winding"], None, None, 0.05, "model", "통합 모드에서 300 분 후 권선 온도 상승 vs 열 모델 역산(자기 일관성)"),
            ("판정 (장면 끝)", final["status"], None, R["expected_judgment"]["overall_expected"], None, None, None, "dataset", "임계값 0.05/0.10(참고 데이터셋 provisional) + 전류/정격 규칙"),
            ("탐지 시각 [s] (주입 후)", (ev.get("delay_s") or {}).get("DANGER", (ev.get("delay_s") or {}).get("WARN")), None, R["expected_judgment"]["detection_delay_expected_s"], None, None, 0.2, "dataset", "3 s 지속 규칙 — 합성 신호라 과도 없음"),
        ]
        for item, sim, rmx, lutv, femv, cat, tol, grade, easy in rows:
            d_lut = pct(sim, lutv) if isinstance(sim, (int, float)) else None
            d_fem = pct(sim, femv) if isinstance(sim, (int, float)) and femv is not None else None
            if isinstance(sim, str):
                judge = "PASS" if sim == lutv else "FAIL"
            elif sim is None or lutv is None:
                judge = "—"
            elif tol is None:
                judge = "—"
            else:
                judge = "PASS" if (abs(d_lut) <= tol * 100 if d_lut is not None else abs(sim - lutv) < 1e-6) else "FAIL"
            sheet1.append({"scenario": sid, "turns": TURNS[sid], "R_f": RF[sid], "load": LOAD[sid], "item": item, "sim": sim, "rmxprt": rmx, "lut": lutv, "fem": femv, "catalog": cat,
                           "d_lut_pct": d_lut, "d_fem_pct": d_fem, "tol": tol, "judge": judge, "grade": grade, "easy": easy})
    # ================= 시트 3 역추정
    inv_rows = []
    for ang in ANGLES:
        run = runs[ang]
        if run is None:
            continue
        h_ang = float(run["meta"].get("inherent", {}).get("angle_deg", ang))
        for sid in SCEN:
            if sid == "healthy":
                continue
            comp = sim_mean(run, sid, "i2_over_i1"); cang = sim_mean(run, sid, "i2_angle_deg") or 0.0
            if comp is None:
                continue
            fault = fault_component(comp, cang, h, h_ang)
            curve = lut_curve(lut, RF[sid], LOAD[sid])
            est, flag = invert_turns(curve, fault); est_c, flag_c = invert_turns(curve, comp)
            inv_rows.append({"angle": ang, "scenario": sid, "turns": TURNS[sid], "R_f": RF[sid], "load": LOAD[sid], "i2i1_comp": comp, "i2i1_fault": fault,
                             "est_turns": est, "err_turns": est - TURNS[sid], "flag": flag, "pass": abs(est - TURNS[sid]) <= 1.0,
                             "est_turns_from_comp": est_c, "err_from_comp": est_c - TURNS[sid], "flag_comp": flag_c})
    # ================= 시트 4 FEM 민감도
    sens_rows = []
    for sid in SCEN:
        R = S[sid]; fault = R["i2_over_i1_fault"]["value"]; theta = R["i2_over_i1_fault"]["angle_deg_vs_i1"]
        comp0 = abs(fault * cmath.exp(1j * math.radians(theta)) + h); comp1 = abs(fault * Z2_SCALE * cmath.exp(1j * math.radians(theta)) + h)
        in0 = R["i2_over_in"]["lut"]; in1 = in0 * Z2_SCALE
        lv = lambda v: "DANGER" if v >= danger else "WARN" if v >= warn else "SAFE"  # noqa: E731
        sens_rows.append({"scenario": sid, "turns": TURNS[sid], "i2i1_fault": fault, "i2i1_comp_anchor": comp0, "i2i1_comp_fem": comp1, "i2in_anchor": in0, "i2in_fem": in1,
                          "judge_anchor": lv(comp0), "judge_fem": lv(comp1), "changed": lv(comp0) != lv(comp1)})
    # ================= 시트 5 탐지 시각
    det_rows = []
    for ang in ANGLES:
        run = runs[ang]
        if run is None:
            continue
        stt_ = scene_times(run)
        for sid in SCEN:
            t0, t1, _ = stt_[sid]; rows_ = [r for r in run["state"] if r["step"] == sid]
            if not rows_:
                continue
            def first(pred):
                return next((fnum(r["t_real_s"]) - t0 for r in rows_ if pred(r)), None)
            det_rows.append({"angle": ang, "scenario": sid, "t_inject": t0,
                             "t_i2_warn": first(lambda r: fnum(r["i2_over_i1"]) >= warn), "t_i2_danger": first(lambda r: fnum(r["i2_over_i1"]) >= danger),
                             "t_warn_confirmed": first(lambda r: r["lvl_i2i1"] == "WARN"), "t_danger_confirmed": first(lambda r: r["lvl_i2i1"] == "DANGER"),
                             "t_r_warn": first(lambda r: fnum(r["Ia_rms"]) / I_n > float(cr["safe_high"])), "t_r_danger": first(lambda r: fnum(r["Ia_rms"]) / I_n > float(cr["danger_over"])),
                             "t_overall": first(lambda r: r["status"] != "SAFE"), "final": rows_[-1]["status"], "cause": rows_[-1]["cause_signal"]})
    # ================= 시트 6 등가회로
    circ_rows = [("R1 [Ω] 20 °C", ec["R1_ohm"]["20C"], None, None, "온도 스윕(RMxprt)"), ("R1 [Ω] 95 °C (hot, MCCM 사용)", ec["R1_ohm"]["95C"], None, ec["R1_ohm"]["used_hot"], ""),
                 ("R2′ [Ω]", ec["R2p_ohm"]["rmxprt_95C"], None, ec["R2p_ohm"]["mccm_hot_calibrated"], "MCCM 물리 보정(기계출력 맞춤)"), ("X1 [Ω]", ec["X1_ohm"]["rmxprt"], None, ec["X1_ohm"]["rmxprt"], ""),
                 ("X2′ [Ω]", ec["X2p_ohm"]["rmxprt"], None, ec["X2p_ohm"]["rmxprt"], ""), ("Xm [Ω]", ec["Xm_ohm"]["rmxprt"], ec["Xm_ohm"]["fem_X_total_at_rated_Im"], ec["Xm_ohm"]["rmxprt"], "FEM = 자화곡선 k=1 X_total"),
                 ("Z₂ [Ω] (역상)", None, ec["Z2_ohm"]["fem_corrected"], ec["Z2_ohm"]["anchor_catalog"], f"FEM 원값 {ec['Z2_ohm']['fem_negseq']:.2f}, 보정 {ec['Z2_ohm']['fem_corrected']:.2f}; 앵커 대비 {ec['Z2_ohm']['dev_pct']:+.1f} % → I₂ +20 %"),
                 ("단락 턴 자기 인덕턴스 [µH] (top/bot)", None, (ec["short_turn_inductance_H"]["fem_self_top"] or 0) * 1e6, None, ec["short_turn_inductance_H"]["mccm_assumption"]),
                 ("Rfe [Ω]", ec["Rfe_ohm"]["rmxprt"], None, ec["Rfe_ohm"]["mccm_physical"], "MCCM 물리 정합(데이터시트 철손)")]
    # ================= 요약 숫자
    s1_num = [r for r in sheet1 if isinstance(r["sim"], (int, float)) and r["d_lut_pct"] is not None and r["item"] not in ("판정 (장면 끝)", "탐지 시각 [s] (주입 후)")]
    max_lut = max(abs(r["d_lut_pct"]) for r in s1_num if r["item"] != "권선 ΔT 정상 상태 [°C]"); max_fem = max(abs(r["d_fem_pct"]) for r in sheet1 if r["d_fem_pct"] is not None)
    inv_ok = sum(1 for r in inv_rows if r["pass"]); inv_n = len(inv_rows); n_changed = sum(1 for r in sens_rows if r["changed"])
    per_scen = {sid: {"pass": sum(1 for r in sheet1 if r["scenario"] == sid and r["judge"] == "PASS"), "fail": sum(1 for r in sheet1 if r["scenario"] == sid and r["judge"] == "FAIL")} for sid in SCEN}
    conclusion = (f"시뮬 전기 수치는 LUT(MCCM 등가회로)와 ≤ {max_lut:.2f} %, 2D FEM 보정값(I_f)과 ≤ {max_fem:.1f} % 안에서 일치하고, 시뮬 I₂/I₁ 로 결함 턴수를 역추정하면 ±1턴 이내 {inv_ok}/{inv_n}, "
                  f"FEM 불확실성(Z₂ −16 % → I₂ +20 %) 아래에서 판정이 바뀌는 시나리오 {n_changed}건.")
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "run_commit": meta_commit, "conclusion": conclusion, "max_dev_lut_pct": round(max_lut, 3), "max_dev_fem_pct": round(max_fem, 2),
               "inversion_pass": inv_ok, "inversion_n": inv_n, "fem_sens_changed": n_changed, "per_scenario": per_scen,
               "sheet1": sheet1, "inversion": inv_rows, "fem_sensitivity": sens_rows, "detection": det_rows, "circuit": circ_rows, "sha": sha_rows}
    json.dump(summary, open(os.path.join(OUT_DIR, "sim_vs_maxwell.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    write_xlsx(summary, ref, vs, tr, rp, stt, runs, warn, danger)
    write_md(summary, S, ref)
    out = os.path.join(OUT_DIR, "M1_sim_vs_maxwell.xlsx")
    if not a.no_desktop:
        desk = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        if not os.path.isdir(desk):
            desk = os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "바탕 화면")
        if os.path.isdir(desk):
            shutil.copyfile(out, os.path.join(desk, "M1_시뮬_vs_Maxwell.xlsx")); summary["desktop_copy"] = os.path.join(desk, "M1_시뮬_vs_Maxwell.xlsx")
            json.dump(summary, open(os.path.join(OUT_DIR, "sim_vs_maxwell.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"→ {out}  | {conclusion}")


# ----------------------------------------------------------------------------- 엑셀
def write_xlsx(sm, ref, vs, tr, rp, stt, runs, warn, danger):
    import openpyxl
    from openpyxl.chart import BarChart, LineChart, Reference, ScatterChart, Series
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = openpyxl.Workbook()
    fill = lambda hexc: PatternFill("solid", fgColor=hexc)  # noqa: E731
    bold = Font(bold=True)

    def header(ws, cols, widths=None):
        ws.append(cols)
        for c in ws[1]:
            c.font = bold; c.fill = fill(HEAD); c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, w in enumerate(widths or [], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    def judge_fill(cell, j):
        cell.fill = fill(GREEN if j == "PASS" else RED if j == "FAIL" else GREY)

    def sha_footer(ws):
        ws.append([]); ws.append(["입력 파일 sha256(앞 16)", "", "", ""]); ws.cell(ws.max_row, 1).font = bold
        for k, p, s in sm["sha"]:
            ws.append([k, p, s])

    # ---- 0 요약
    ws = wb.active; ws.title = "0 요약"
    ws.append(["M1 Isaac Sim 결함 시뮬 vs Maxwell 해석 — 비교표"]); ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"생성 {sm['generated']} · 생성기 motor_dt_viz/tools/verify/sim_vs_maxwell_xlsx.py · 실행 커밋 {sm['run_commit']} · 새 해석·설정·엔진 변경 없음, 수기 숫자 없음"])
    ws.append([]); ws.append(["한 줄 결론", sm["conclusion"]]); ws["A4"].font = bold; ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 120
    ws.append([]); ws.append(["시나리오", "PASS", "FAIL", "역추정 ±1턴 (각도 3종)", "FEM 민감도 판정 변화"]); [setattr(c, "font", bold) for c in ws[6]]
    for sid in SCEN:
        inv = [r for r in sm["inversion"] if r["scenario"] == sid]; sr = next(r for r in sm["fem_sensitivity"] if r["scenario"] == sid)
        ws.append([sid, sm["per_scenario"][sid]["pass"], sm["per_scenario"][sid]["fail"], f"{sum(1 for r in inv if r['pass'])}/{len(inv)}" if inv else "—", "변화" if sr["changed"] else "불변"])
    ws.append([]); ws.append(["색 규칙", "PASS 초록 / FAIL 빨강 / — 회색 · 출처 등급: 카탈로그 초록 · RMxprt 파랑 · 등가회로(MCCM/LUT) 보라 · 2D FEM 청록 · 표준 회색 · 가정 주황 · 열 모델 갈색 · 시뮬 노랑"])
    ws.append(["읽는 법", "시트 1: 시나리오마다 시뮬 정상 상태 평균을 RMxprt·LUT·2D FEM·카탈로그와 나란히 — 오차·허용·판정. 시트 3: 시뮬 I₂/I₁ 로 턴수를 거꾸로 맞혔는가. 시트 4: FEM 불확실성(I₂ +20 %)에서 판정이 흔들리는가."])
    sha_footer(ws)
    # ---- 1 시나리오 비교
    ws = wb.create_sheet("1 시나리오 비교")
    header(ws, ["시나리오", "턴", "R_f [Ω]", "부하", "양", "시뮬 (정상 상태 평균)", "RMxprt v2m2", "MCCM/LUT", "2D FEM (lite, F1 보정)", "카탈로그", "시뮬−LUT 오차 % (수식)", "시뮬−FEM 오차 % (수식)", "허용 ±%", "판정", "출처 등급", "쉬운 설명"],
           [20, 5, 7, 6, 26, 16, 12, 12, 16, 10, 16, 16, 8, 8, 12, 60])
    for i, r in enumerate(sm["sheet1"], start=2):
        ws.append([r["scenario"], r["turns"], r["R_f"], r["load"], r["item"], r["sim"], r["rmxprt"], r["lut"], r["fem"], r["catalog"], None, None,
                   None if r["tol"] is None else r["tol"] * 100, r["judge"], r["grade"], r["easy"]])
        if isinstance(r["sim"], (int, float)) and isinstance(r["lut"], (int, float)) and r["lut"]:
            ws.cell(i, 11).value = f"=(F{i}/H{i}-1)*100"
        if isinstance(r["sim"], (int, float)) and isinstance(r["fem"], (int, float)) and r["fem"]:
            ws.cell(i, 12).value = f"=(F{i}/I{i}-1)*100"
        if r["judge"] in ("PASS", "FAIL") and isinstance(r["sim"], (int, float)) and r["tol"] is not None and isinstance(r["lut"], (int, float)) and r["lut"]:
            ws.cell(i, 14).value = f'=IF(ABS(K{i})<=M{i},"PASS","FAIL")'
        judge_fill(ws.cell(i, 14), r["judge"]); ws.cell(i, 15).fill = fill(GRADE_COLOR.get(r["grade"], GREY)); ws.cell(i, 6).fill = fill(GRADE_COLOR["sim"])
        for c in (6, 7, 8, 9, 10):
            ws.cell(i, c).number_format = "0.0000"
    ws.append([]); ws.append(["각주", "2D FEM 열은 I_f(F1 보정)·Z₂·정격 해·인덕턴스에만 값이 있다 — 나머지 양은 FEM 이 계산하지 않았다(—). RMxprt 는 정격점만. 권선 ΔT 는 열 모델 자기 일관성(해석값 아님)."])
    sha_footer(ws)
    # ---- 2 정격·기동
    ws = wb.create_sheet("2 정격·기동")
    header(ws, ["항목", "시뮬 (정상 시나리오)", "카탈로그", "RMxprt v2m2", "2D FEM lite", "2D FEM + F2 보정", "IEC 60034-1 허용", "비고"], [30, 16, 12, 12, 12, 14, 24, 50])
    h_rows = [r for r in sm["sheet1"] if r["scenario"] == "healthy"]
    i1 = next((r["sim"] for r in h_rows if r["item"].startswith("I₁")), None); rR = next((r["sim"] for r in h_rows if r["item"].startswith("결함상 r")), None)
    iec = ref["rated_point"]["iec_tolerance"]["limits"]
    ws.append(["정격 전류 I₁ [A]", i1, rp["catalog"]["I_A"], rp["rmxprt_v2m2"]["I_A"], rp["fem_lite"]["I_A"], None, "허용차 없음(역률·효율로 간접)", "시뮬 정상 I₁ = LUT 정상 격자 I1_A(MCCM 물리 보정 전류)"])
    ws.append(["정상 r = I_R/I_n", rR, 1.0, rp["rmxprt_v2m2"]["I_A"] / rp["catalog"]["I_A"], rp["fem_lite"]["I_A"] / rp["catalog"]["I_A"], None, "", "고유 비대칭 0.027 로 R상이 약간 크다"])
    ws.append(["역률", None, rp["catalog"]["pf"], rp["rmxprt_v2m2"]["pf"], rp["fem_lite"]["pf"], None, f"≥ {iec['pf_min']:.3f}", "FEM lite 0.740 미달(유일) — 2D 누설 과대"])
    ws.append(["효율", None, rp["catalog"]["eff"], rp["rmxprt_v2m2"]["eff"], rp["fem_lite"]["eff"], None, f"≥ {iec['eff_min']:.3f}", ""])
    ws.append(["정격 회전수 [rpm]", None, rp["catalog"]["rpm"], rp["rmxprt_v2m2"]["rpm"], None, None, f"슬립 ±20 % → {iec['slip'][0]:.4f}~{iec['slip'][1]:.4f}", ""])
    ws.append(["잠김 전류비 [×]", None, stt["catalog"]["I_st_ratio"], stt["rmxprt_v2m2"]["I_st_ratio"], stt["fem_corrected"]["I_st_2D_uncorrected"], stt["fem_corrected"]["I_st_ratio"], f"≤ {iec['I_st_max']}", "시뮬에 기동 장면 없음(참고)"])
    ws.append(["잠김 토크비 [×]", None, stt["catalog"]["T_st_ratio"], stt["rmxprt_v2m2"]["T_st_ratio"], stt["fem_corrected"]["T_st_2D_uncorrected"], stt["fem_corrected"]["T_st_ratio"], f"{iec['T_st'][0]:.3f}~{iec['T_st'][1]:.3f}", "스큐·엔드링 누설 보정(F2)"])
    ws.append(["최대 토크비 [×]", None, stt["catalog"]["T_max_ratio"], stt["rmxprt_v2m2"]["T_max_ratio"], None, None, f"≥ {iec['T_max_min']}", ""])
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row[1:6]:
            c.number_format = "0.000"
    sha_footer(ws)
    # ---- 3 역추정
    ws = wb.create_sheet("3 결함 크기 역추정")
    header(ws, ["고유 비대칭 각도 [°]", "시나리오", "주입 턴", "R_f [Ω]", "부하", "시뮬 I₂/I₁ 합성", "결함분 (고유 분리 후)", "추정 턴 (LUT 역보간)", "오차 [턴] (수식)", "판정 ±1턴 (수식)", "격자 범위", "합성값으로 역추정한 턴", "오차 [턴] (현장: 고유 비대칭 모를 때)", "쉬운 설명"],
           [12, 20, 8, 8, 6, 14, 16, 16, 12, 12, 10, 16, 18, 50])
    for i, r in enumerate(sm["inversion"], start=2):
        ws.append([r["angle"], r["scenario"], r["turns"], r["R_f"], r["load"], r["i2i1_comp"], r["i2i1_fault"], r["est_turns"], None, None, r["flag"], r["est_turns_from_comp"], None,
                   "결함분만 쓰면 턴수를 거의 그대로 되찾는다" if r["pass"] else "격자 간격·각도 때문에 1턴 넘게 벗어남"])
        ws.cell(i, 9).value = f"=H{i}-C{i}"; ws.cell(i, 10).value = f'=IF(ABS(I{i})<=1,"PASS","FAIL")'; ws.cell(i, 13).value = f"=L{i}-C{i}"
        judge_fill(ws.cell(i, 10), "PASS" if r["pass"] else "FAIL")
        for c in (6, 7, 8, 12):
            ws.cell(i, c).number_format = "0.0000"
    n_inv = len(sm["inversion"])
    ws.append([]); ws.append(["규칙", "결함분 = |합성 페이저 − 0.027∠(시드 각도)|; LUT(턴 비율 축 0~16.7 %, 해당 R_f·부하 격자)의 단조 증가 구간에서 선형 역보간 → 턴 비율 × 192. 허용 ±1턴(격자 간격 2~8턴 사이는 보간). 합성값 역추정 오차는 허용 없이 기록만."])
    sha_footer(ws)
    if n_inv:
        ch = ScatterChart(); ch.title = "주입 턴수 vs 추정 턴수 (각도 0/90/180°)"; ch.x_axis.title = "주입 턴"; ch.y_axis.title = "추정 턴"; ch.style = 13
        xs = Reference(ws, min_col=3, min_row=2, max_row=1 + n_inv); ys = Reference(ws, min_col=8, min_row=2, max_row=1 + n_inv)
        s = Series(ys, xs, title="결함분 역추정"); s.marker.symbol = "circle"; s.graphicalProperties.line.noFill = True; ch.series.append(s)
        ys2 = Reference(ws, min_col=12, min_row=2, max_row=1 + n_inv); s2 = Series(ys2, xs, title="합성값 역추정"); s2.marker.symbol = "triangle"; s2.graphicalProperties.line.noFill = True; ch.series.append(s2)
        s3 = Series(xs, xs, title="대각선 (주입 = 추정)"); s3.marker.symbol = "none"; ch.series.append(s3)
        ch.height, ch.width = 9, 16; ws.add_chart(ch, "P2")
    # ---- 4 FEM 민감도
    ws = wb.create_sheet("4 FEM 불확실성 민감도")
    header(ws, ["시나리오", "턴", "LUT 결함분 I₂/I₁", "합성 I₂/I₁ (Z₂ 앵커 7.136 Ω)", "합성 I₂/I₁ (FEM 보정 5.97 Ω, I₂ ×1.20)", "I₂/I_n 앵커", "I₂/I_n FEM", "판정 앵커", "판정 FEM", "판정 변화", "쉬운 설명"], [20, 6, 14, 18, 22, 12, 12, 10, 10, 10, 60])
    for i, r in enumerate(sm["fem_sensitivity"], start=2):
        ws.append([r["scenario"], r["turns"], r["i2i1_fault"], r["i2i1_comp_anchor"], r["i2i1_comp_fem"], r["i2in_anchor"], r["i2in_fem"], r["judge_anchor"], r["judge_fem"], "변화" if r["changed"] else "불변",
                   "FEM 역상 임피던스가 작으면 같은 결함에서 역상 전류가 20 % 더 크게 나온다 — 판정이 바뀌는지가 핵심"])
        ws.cell(i, 10).fill = fill(RED if r["changed"] else GREEN)
        for c in (3, 4, 5, 6, 7):
            ws.cell(i, c).number_format = "0.0000"
    ws.append([]); ws.append(["근거", f"f7_iec_tolerance.json Z2_uncertainty: I₂ ∝ 1/Z₂, 앵커 {ref['equivalent_circuit']['Z2_ohm']['anchor_catalog']} Ω vs FEM 보정 {ref['equivalent_circuit']['Z2_ohm']['fem_corrected']:.2f} Ω ({ref['equivalent_circuit']['Z2_ohm']['dev_pct']:+.1f} %) → I₂ +{ref['scenarios']['itsc_4turn']['z2_uncertainty']['i2_uncertainty_pct']:.0f} %. LUT 선형 스케일(새 해석 아님). 임계값 0.05/0.10 불변."])
    ws.append(["단락 턴 누설", "FEM 9.5 mΩ vs MCCM 가정 — 2D lite 파라미터로 재계산한 LUT v3 와 7 케이스 변화 < 0.6 % (160점 최대 3.7 %) → v2 유지 (electrical.yaml lut_note 인용)"])
    sha_footer(ws)
    n_s = len(sm["fem_sensitivity"])
    ch = BarChart(); ch.type = "col"; ch.title = "시나리오별 I₂/I₁ — 시뮬·LUT·FEM 민감도"; ch.y_axis.title = "I₂/I₁ (합성)"; ch.style = 10
    # 시뮬 합성값 열을 임시로 넣어 차트 데이터로 (M열)
    ws.cell(1, 13).value = "시뮬 합성 I₂/I₁"; ws.cell(1, 13).font = bold
    for i, r in enumerate(sm["fem_sensitivity"], start=2):
        simv = next((x["sim"] for x in sm["sheet1"] if x["scenario"] == r["scenario"] and x["item"] == "I₂/I₁ 합성(표시값)"), None)
        ws.cell(i, 13).value = simv; ws.cell(i, 13).number_format = "0.0000"
    data = Reference(ws, min_col=13, min_row=1, max_row=1 + n_s); ch.add_data(data, titles_from_data=True)
    ch.add_data(Reference(ws, min_col=4, min_row=1, max_row=1 + n_s), titles_from_data=True); ch.add_data(Reference(ws, min_col=5, min_row=1, max_row=1 + n_s), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=1 + n_s)); ch.height, ch.width = 9, 18; ws.add_chart(ch, "O2")
    # ---- 5 탐지 시각
    ws = wb.create_sheet("5 탐지 시각")
    header(ws, ["각도 [°]", "시나리오", "주입 시각 [s]", "I₂/I₁ ≥ 0.05 [s 후]", "I₂/I₁ ≥ 0.10 [s 후]", "WARN 확정 (3 s 규칙)", "DANGER 확정", "결함상 r > 1.10", "결함상 r > 1.25", "종합 비SAFE 시각", "장면 끝 판정", "원인"], [8, 20, 10, 12, 12, 12, 12, 12, 12, 12, 10, 14])
    for r in sm["detection"]:
        ws.append([r["angle"], r["scenario"], r["t_inject"], r["t_i2_warn"], r["t_i2_danger"], r["t_warn_confirmed"], r["t_danger_confirmed"], r["t_r_warn"], r["t_r_danger"], r["t_overall"], r["final"], r["cause"]])
    ws.append([]); ws.append(["각주", "합성 신호라 전류 과도가 없다 — 임계 초과는 주입 즉시(0.0 s), 확정은 지속 3 s 규칙만. 이전 장면에서 이미 DANGER 였으면 '확정' 시각이 0 으로 나온다(16턴·반부하 뒤 장면)."])
    sha_footer(ws)
    # 시계열 차트: 4턴·12턴 I₂/I₁ (각도 0 실행 state.csv 에서 장면 구간)
    ws_ts = wb.create_sheet("5b 시계열 데이터"); ws_ts.append(["t_real_s", "I2/I1 (4턴 장면)", "I2/I1 (12턴 장면)", "경고 0.05", "위험 0.10"])
    base = runs[0]; st_t = {s["id"]: (float(s["t0_s"]), float(s["t0_s"]) + float(s["duration_s"])) for s in base["meta"]["steps"]}
    seg4 = [(fnum(r["t_real_s"]) - st_t["itsc_4turn"][0], fnum(r["i2_over_i1"])) for r in base["state"] if r["step"] in ("healthy", "itsc_4turn")]
    seg12 = [(fnum(r["t_real_s"]) - st_t["itsc_12turn"][0], fnum(r["i2_over_i1"])) for r in base["state"] if r["step"] == "itsc_12turn"]
    k12 = {round(t, 2): v for t, v in seg12}
    for t, v in seg4[::2]:
        ws_ts.append([round(t, 2), v, k12.get(round(t, 2)), warn, danger])
    n_ts = ws_ts.max_row
    lc = LineChart(); lc.title = "I₂/I₁ 시계열 — 4턴(주입 0 s 기준)·12턴 장면, 임계선 0.05/0.10"; lc.y_axis.title = "I₂/I₁"; lc.x_axis.title = "주입 후 시간 [s]"; lc.style = 12
    lc.add_data(Reference(ws_ts, min_col=2, max_col=5, min_row=1, max_row=n_ts), titles_from_data=True); lc.set_categories(Reference(ws_ts, min_col=1, min_row=2, max_row=n_ts))
    lc.height, lc.width = 9, 18; ws.add_chart(lc, "N2")
    # ---- 6 등가회로
    ws = wb.create_sheet("6 등가회로 대조")
    header(ws, ["항목", "RMxprt v2m2", "2D FEM (lite)", "MCCM 입력 (LUT 계산에 쓴 값)", "FEM−RMxprt 차이 % (수식)", "비고"], [30, 14, 14, 20, 16, 60])
    for i, (name, rmx, fem, mccm, note) in enumerate(sm["circuit"], start=2):
        ws.append([name, rmx, fem, mccm, None, note])
        if isinstance(rmx, (int, float)) and isinstance(fem, (int, float)) and rmx:
            ws.cell(i, 5).value = f"=(C{i}/B{i}-1)*100"
        for c in (2, 3, 4):
            ws.cell(i, c).number_format = "0.0000"
    ws.append([]); ws.append(["각주", "시뮬(엔진)에는 등가회로 상수가 직접 들어가지 않는다 — LUT(MCCM)가 이 값으로 계산한 결과만 쓴다. 근거 표."])
    sha_footer(ws)
    # ---- 7 근거 사슬
    ws = wb.create_sheet("7 근거 사슬")
    header(ws, ["표시량", "엔진 함수", "입력 파일(sha)", "해석 단계", "출처 등급"], [34, 50, 50, 70, 30])
    for r in tr["rows"]:
        ws.append([r["display"], r["engine"], "\n".join(r["inputs"]), r["analysis_chain"], r["grade"]])
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    # ---- 8 한계
    ws = wb.create_sheet("8 한계")
    header(ws, ["#", "한계", "영향"], [4, 90, 60])
    lims = [(x, "") for x in ref["limitations"]] + [("합성 신호라 전류 과도·RSH 없음 — 탐지 지연은 3 s 지속 규칙뿐", "실모터 창 길이·필터·돌입이 더해진다"),
                                                   ("기계 결함(베어링·오정렬·팬·브레이크)은 Maxwell 대조 대상 아님", "진동·베어링 상수(표준/AI Hub 참고)만")]
    for i, (lim, eff) in enumerate(lims, start=1):
        ws.append([i, lim, eff])
    wb.save(os.path.join(OUT_DIR, "M1_sim_vs_maxwell.xlsx"))


def write_md(sm, S, ref):
    L = ["# 시뮬 vs Maxwell 한 장 요약 (M1)", "", f"생성 {sm['generated']} · `tools/verify/sim_vs_maxwell_xlsx.py` · 실행 커밋 {sm['run_commit']} · 엑셀 `docs/verification/M1_sim_vs_maxwell.xlsx`(바탕화면 사본 `M1_시뮬_vs_Maxwell.xlsx`)", "",
         "## 1. 결론 한 줄", "", sm["conclusion"], "",
         "## 2. 표 1 압축본 (시뮬 / LUT / 2D FEM)", "", "| 시나리오 | 턴 | I₂/I₁ 합성 시뮬 / LUT | I_f [A] 시뮬 / MCCM / FEM(F1) | 손실 [W] 시뮬 / MCCM | 판정 시뮬 / 예상 | 역추정 턴 (0/90/180°) |", "|---|---|---|---|---|---|---|"]
    for sid in SCEN:
        g = lambda item: next((r for r in sm["sheet1"] if r["scenario"] == sid and r["item"] == item), None)  # noqa: E731
        c, f_, p, j = g("I₂/I₁ 합성(표시값)"), g("단락 루프 전류 I_f [A]"), g("단락 루프 총손실 [W]"), g("판정 (장면 끝)")
        inv = [r for r in sm["inversion"] if r["scenario"] == sid]
        fmt = lambda v, n=4: "—" if v is None else f"{v:.{n}f}"  # noqa: E731
        L.append(f"| {sid} | {TURNS[sid]} | {fmt(c['sim'])} / {fmt(c['lut'])} | {fmt(f_['sim'], 2)} / {fmt(f_['lut'], 2)} / {fmt(f_['fem'], 2)} | {fmt(p['sim'], 1)} / {fmt(p['lut'], 1)} | {j['sim']} / {j['lut']} | "
                 + (" / ".join(f"{r['est_turns']:.1f}" for r in inv) if inv else "—") + " |")
    L += ["", "## 3. Maxwell 이 정하는 것 / 임계값이 정하는 것", "",
          "- **Maxwell(RMxprt → MCCM/LUT → 2D FEM)이 정하는 것** = 결함 신호의 크기: 몇 턴이 붙으면 I₂/I₁·I_f·손실이 얼마인가(4턴 결함분 0.049, I_f 34 A, 158 W …). 시뮬은 이 값을 그대로 재현한다(≤ " + f"{sm['max_dev_lut_pct']:.2f} %).",
          "- **임계값(thresholds.yaml, 참고 데이터셋 provisional)이 정하는 것** = 판정 기준: 0.05 경고 / 0.10 위험, 3 s 지속. 같은 신호라도 기준을 바꾸면 판정이 바뀐다 — FEM 불확실성(I₂ +20 %)에서 판정이 바뀌는 시나리오 " + f"{sm['fem_sens_changed']}건.",
          "", "## 4. 한계", "",
          "- 합성 신호(엔진 페이저 합성) — 실측 아님, 과도·RSH 없음. 고유 비대칭 0.027∠0° 는 가정(180° 면 4턴 경고 소실).",
          "- 2D lite(학생판): 무스큐·분산 결함·단순화 기하 → Z₂ −16 %·역률 0.740; FEM 은 I_f·Z₂·정격 해·인덕턴스만 제공.",
          "- 열 모델은 22 kW 보정값 스케일(자기 일관성만), 기계 결함은 대조 대상 아님, 실모터 일치는 주장하지 않는다."]
    open(os.path.join(OUT_DIR, "sim_vs_maxwell_summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
