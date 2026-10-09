# -*- coding: utf-8 -*-
"""compare_demo_logs.py — 자동 재생 로그 두 개(기준 ↔ 새 실행)의 회귀 비교 (R1: Judge·LiveBridge 추가 뒤 M5 로그가 같은지).

  <python> tools/compare_demo_logs.py --mode mechanical --ref logs/mechanical/demo_20260922_174529.csv --new logs/r1_live_mech/demo_*.csv

비교: 장면 끝(−0.3 s) 시점 값 (tools/run_fleet.py regression_m5 와 같은 방식) + 같은 t_real 격자(0.5 s)에서의 최대 차이.
허용: 기계 온도 2.5 °C · 진동 0.05 mm/s, 전기 전류 0.06 A · I₂/I₁ 0.002 (엔진 ↔ Isaac 로그 차이 실측 범위, SESSION_LOG 13장).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, VIZ)
from engine.scenario_player import ScenarioPlayer  # noqa: E402

COLS = {"mechanical": (["T_winding", "T_stator_core", "T_rotor", "T_shaft", "T_bearing_de", "T_bearing_nde", "T_frame", "vibration_mms"],
                       {"T_": 2.5, "vibration_mms": 0.05}),
        "electrical": (["Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1"], {"I": 0.06, "i2_over_i1": 0.002})}


def tol_for(col: str, tols: dict) -> float:
    for k, v in tols.items():
        if col.startswith(k):
            return v
    return 1e9


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", newline="")))


def at(rs, t):
    return max((r for r in rs if float(r["t_real_s"]) <= t), key=lambda r: float(r["t_real_s"]), default=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=("mechanical", "electrical"))
    ap.add_argument("--ref", required=True)
    ap.add_argument("--new", required=True, help="glob 가능 — 가장 최근 파일")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    new = sorted(glob.glob(a.new))[-1]
    R, N = rows(a.ref), rows(new)
    cols, tols = COLS[a.mode]
    player = ScenarioPlayer.for_mode(a.mode)
    L = [f"# 자동 재생 로그 회귀 비교 ({a.mode})", "", f"- 기준: `{os.path.relpath(a.ref, VIZ)}` ({len(R)} 행)", f"- 새 실행: `{os.path.relpath(new, VIZ)}` ({len(N)} 행)", "",
         "## 장면 끝 (−0.3 s)", "", "| 장면 | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    worst = {c: 0.0 for c in cols}
    acc = 0.0
    for s in player.steps:
        acc += float(s["duration_s"]); te = acc - 0.3
        r, n = at(R, te), at(N, te)
        if r is None or n is None:
            L.append(f"| {s['id']} | (행 없음) |"); continue
        cells = []
        for c in cols:
            d = float(n[c]) - float(r[c]); worst[c] = max(worst[c], abs(d))
            cells.append(f"{float(r[c]):g} → {float(n[c]):g} ({d:+.2f})")
        L.append(f"| {s['id']} | " + " | ".join(cells) + " |")
    # 0.5 s 격자 전 구간
    grid_worst = {c: 0.0 for c in cols}
    t = 0.0
    tmax = min(float(R[-1]["t_real_s"]), float(N[-1]["t_real_s"]))
    while t <= tmax:
        r, n = at(R, t), at(N, t)
        if r and n:
            for c in cols:
                grid_worst[c] = max(grid_worst[c], abs(float(n[c]) - float(r[c])))
        t += 0.5
    ok = all(worst[c] <= tol_for(c, tols) for c in cols)
    L += ["", "## 최대 차이", "", "| 열 | 장면 끝 최대 | 0.5 s 격자 전 구간 최대 | 허용 | 판정 |", "|---|---|---|---|---|"]
    for c in cols:
        L.append(f"| {c} | {worst[c]:.3f} | {grid_worst[c]:.3f} | {tol_for(c, tols):g} | {'통과' if worst[c] <= tol_for(c, tols) else '**초과**'} |")
    extra = [c for c in N[0].keys() if c not in R[0].keys()]
    L += ["", f"- 새 로그에만 있는 열: {extra} (끝에 덧붙인 판정 열 — 기존 독자는 이름으로 읽으므로 영향 없음)" if extra else "- 열 구성 동일",
          f"- **회귀 판정: {'통과' if ok else '실패'}** (장면 끝 기준, 허용값은 엔진↔Isaac 로그 실측 차이 범위)"]
    txt = "\n".join(L)
    print(txt)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt + "\n")
    json.dump({"pass": ok, "worst": worst, "grid_worst": grid_worst, "ref": a.ref, "new": new}, open(os.path.splitext(a.out or new)[0] + "_regression.json", "w"), indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
