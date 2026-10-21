# -*- coding: utf-8 -*-
"""hud_composite.py — Isaac 뷰포트 스크린샷(HUD 미포함)에 검증 로그(state.csv)의 그 시각 HUD 값을 합성한다 (V4 'HUD 합성 스크린샷').
값은 state.csv(엔진 값)와 analysis_reference.json(해석 기준)에서만 온다. 수기 숫자 없음.

  py -3.12 -X utf8 tools/verify/hud_composite.py --shots <PNG 폴더> --state logs/verify/electrical_a0/state.csv --out docs/verification/img
  PNG 이름 규칙: hud_<nn>_<태그>_t<초>.png (demo_integrated --m1_shots + --verify_dir 의 verify 계획)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", required=True); ap.add_argument("--state", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "verification", "img"))
    a = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    rows = list(csv.DictReader(open(a.state, encoding="utf-8")))
    ref = json.load(open(os.path.join(VIZ, "data", "electrical", "analysis_reference.json"), encoding="utf-8"))
    col = {"SAFE": "#26f259", "WARN": "#ff731a", "DANGER": "#ff140d"}
    os.makedirs(a.out, exist_ok=True); made = []
    for png in sorted(glob.glob(os.path.join(a.shots, "hud_*.png"))):
        m = re.search(r"hud_(\d+)_([a-z_]+)_t([0-9.]+)\.png$", os.path.basename(png))
        if not m:
            continue
        t = float(m.group(3)); tag = m.group(2)
        r = min(rows, key=lambda x: abs(float(x["t_session_s"]) - t))
        R = ref["scenarios"].get(r["case"])
        img = mpimg.imread(png)
        fig = plt.figure(figsize=(12.8, 7.2)); ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(img); ax.axis("off")
        lines = [f"t = {float(r['t_session_s']):.1f} s   scene {r['step']}   case {r['case']}   load {r['load']}",
                 f"I_R/S/T = {float(r['Ia_rms']):.2f} / {float(r['Ib_rms']):.2f} / {float(r['Ic_rms']):.2f} A   (rated 4.73 A)",
                 f"I2/I1 = {float(r['i2_over_i1']):.4f}   I2/In = {r['i2_over_in']}   I_f = {r['i_f_A'][:6] if r['i_f_A'] else '-'} A   P_loop = {r['p_loop_total_W']} W",
                 f"STATUS {r['status']}  cause {r['cause_signal']} {r['cause_value']}  [{r['threshold']}]",
                 f"T winding {float(r['T_winding']):.1f} °C   bearing DE {float(r['T_bearing_de']):.1f} °C   vib {r['vibration_mms']} mm/s"]
        if R:
            exp = R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]; dev = (float(r["i2_over_i1"]) / exp - 1) * 100 if exp else 0.0
            lines.append(f"ref: I2/I1 {exp:.4f} (shown {float(r['i2_over_i1']):.4f}, {dev:+.2f} %)  I_f MCCM {R['i_f_A']['mccm'] or R['i_f_A']['lut']} A  P_loop {R['p_loop_total_W']['lut']} W  — 등가회로 LUT + 2D FEM (provisional)")
        else:
            lines.append("ref: LUT 밖 장면(legacy 해석식) — 해석 기준 없음")
        y = 0.97
        for k, ln in enumerate(lines):
            c = col.get(r["status"], "white") if k == 3 else "white"
            ax.text(0.015, y, ln, transform=ax.transAxes, fontsize=11, color=c, va="top", family="Malgun Gothic",   # 한글 글리프(임계값 문구) — 고정폭 대신
                    bbox=dict(boxstyle="round,pad=0.25", fc="black", ec="none", alpha=0.65))
            y -= 0.045
        ax.text(0.985, 0.03, f"HUD composite from state.csv ({tag}) — SIMULATION-BASED ESTIMATE (not measured)", transform=ax.transAxes, fontsize=9, color="#ffcc66", ha="right", va="bottom",
                bbox=dict(boxstyle="round,pad=0.25", fc="black", ec="none", alpha=0.6))
        out = os.path.join(a.out, f"hud_{m.group(1)}_{tag}.png"); fig.savefig(out, dpi=100); plt.close(fig); made.append(out)
    print(f"→ {len(made)} 장: " + ", ".join(os.path.basename(x) for x in made))


if __name__ == "__main__":
    sys.exit(main())
