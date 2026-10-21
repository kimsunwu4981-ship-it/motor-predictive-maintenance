# -*- coding: utf-8 -*-
"""baseline_table.py — AI Hub 샘플의 전류 파일이 있는 모터 전부(2.2 kW 4대 + 55 kW 2대)에 창별 정상성 게이트(baseline_capture 와 같은 규칙)를 적용해
I₂/I₁·불평형 분포와 상별 RMS 비(R:S:T) 표를 만든다 (D 후속 4, 2026-10-21). 원본은 저장소 밖(읽기 전용), 산출 요약만 커밋.
  py -3.12 -X utf8 tools/aihub/baseline_table.py [--root <sample/current>] → docs/aihub_baseline_gated.md + .json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(VIZ, "tools"))
from baseline_capture import read_aihub, stats, window_features  # noqa: E402

ROOT_DEFAULT = r"C:\Users\sunwu\OneDrive\바탕 화면\프로젝트\디지털 트윈\2020-02-125.기계시설물고장예지_sample\current"


def gate_windows(feats, files, i1_dev=0.05, fund_min=0.95, ratio=(0.8, 1.25)):
    med = float(np.median([f["I1_A"] for f in feats])) if feats else 0.0
    kept, excl, by_reason = [], [], defaultdict(int)
    for k, f in enumerate(feats):
        why = []
        if med > 0 and abs(f["I1_A"] - med) / med > i1_dev:
            why.append("I1_dev")
        if f["fund_over_rms"] < fund_min:
            why.append("fund_over_rms")
        if any(not (ratio[0] <= x <= ratio[1]) for x in f["phase_ratio"]):
            why.append("phase_ratio")
        if why:
            for w in why:
                by_reason[w] += 1
            excl.append({"file": os.path.basename(files[k]), "reasons": why, "I1_A": round(f["I1_A"], 3), "fund_over_rms": round(f["fund_over_rms"], 3), "phase_ratio": [round(x, 3) for x in f["phase_ratio"]]})
        else:
            kept.append(f)
    return kept, excl, dict(by_reason), med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT_DEFAULT); ap.add_argument("--max-files", type=int, default=700)
    a = ap.parse_args()
    dirs = sorted(glob.glob(os.path.join(a.root, "*", "*", "정상")))
    if not dirs:
        raise SystemExit(f"정상 폴더 없음: {a.root}")
    rows = []
    for d in dirs:
        kw = Path(d).parts[-3]; motor = Path(d).parts[-2]
        files = sorted(glob.glob(os.path.join(d, "*.csv")))[: a.max_files]
        feats, dates = [], defaultdict(list)
        for p in files:
            meta, fs, chs = read_aihub(Path(p))
            f = window_features(chs, fs, 60.0); feats.append(f)
            date = (meta.get("Date") or [""])[0][:10]
            dates[date].append(f["phase_ratio"])
        kept, excl, by_reason, med = gate_windows(feats, files)
        r = stats([f["i2_over_i1"] for f in kept]); unb = stats([f["unbalance"] for f in kept]); i1 = stats([f["I1_A"] for f in kept])
        pr = [round(float(np.median([f["phase_ratio"][k] for f in kept])), 3) for k in range(3)] if kept else None
        pr_by_date = {dt: [round(float(np.median([x[k] for x in v])), 3) for k in range(3)] for dt, v in sorted(dates.items())}
        pr_spread = [round(float(np.std([f["phase_ratio"][k] for f in kept])), 4) for k in range(3)] if kept else None
        rows.append({"motor": motor, "kw": kw, "n_files": len(files), "n_kept": len(kept), "n_excluded": len(excl), "excluded_by_reason": by_reason, "I1_median_all": round(med, 3),
                     "I1": {k: round(v, 3) for k, v in i1.items() if isinstance(v, (int, float))} if kept else None,
                     "i2i1": {k: round(v, 4) for k, v in r.items() if isinstance(v, (int, float))} if kept else None,
                     "unbalance": {k: round(v, 4) for k, v in unb.items() if isinstance(v, (int, float))} if kept else None,
                     "phase_ratio_median_RST": pr, "phase_ratio_std_RST": pr_spread, "phase_ratio_by_date": pr_by_date,
                     "excluded_examples": excl[:5]})
    doc = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "generator": "motor_dt_viz/tools/aihub/baseline_table.py", "source": a.root,
           "gate": {"I1_dev_max": 0.05, "fund_over_rms_min": 0.95, "phase_ratio_range": [0.8, 1.25]}, "rows": rows,
           "note": "샘플 zip 범위(전체 Training zip 미다운로드). 게이트는 baseline_capture.py 창별 정상성과 같은 규칙. 상별 RMS 비가 날짜별로 일정하면 '센서 게인 차이' 가설, 변동하면 '공급 불평형' 가설 — 가설로만, 보정 없음."}
    out_json = os.path.join(VIZ, "docs", "aihub_baseline_gated.json"); json.dump(doc, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["# AI Hub 건전 모터 I₂/I₁ 분포 — 창별 정상성 게이트 적용 (D 후속 4, 2026-10-21)", "",
         f"생성 {doc['generated']} · `{doc['generator']}` · 원본 `{a.root}`(저장소 밖, 읽기 전용) · 게이트: 창 I₁ 이 중앙값 ±5 % 안, 기본파/전체 RMS ≥ 0.95, 상별 RMS/평균 0.8~1.25.", "",
         "| 모터 | 파일 | 통과 창 | 제외 창 (사유) | I₁ 중앙값 [A] | I₂/I₁ 중앙값 / p95 / 최대 | 불평형 중앙값 / p95 | 상별 RMS 비 R:S:T (중앙값) | 비 표준편차 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ex = ", ".join(f"{k} {v}" for k, v in r["excluded_by_reason"].items()) or "—"
        L.append(f"| {r['motor']} ({r['kw']}) | {r['n_files']} | {r['n_kept']} | {r['n_excluded']} ({ex}) | {r['I1']['median'] if r['I1'] else '—'} | "
                 f"{r['i2i1']['median'] if r['i2i1'] else '—'} / {r['i2i1']['p95'] if r['i2i1'] else '—'} / {r['i2i1']['max'] if r['i2i1'] else '—'} | {r['unbalance']['median'] if r['unbalance'] else '—'} / {r['unbalance']['p95'] if r['unbalance'] else '—'} | "
                 f"{' : '.join(str(x) for x in r['phase_ratio_median_RST']) if r['phase_ratio_median_RST'] else '—'} | {' / '.join(str(x) for x in r['phase_ratio_std_RST']) if r['phase_ratio_std_RST'] else '—'} |")
    L += ["", "## 상별 RMS 비 — 날짜별 (R : S : T, 창 중앙값)", "", "| 모터 | 날짜 | R | S | T |", "|---|---|---|---|---|"]
    for r in rows:
        for dt, v in r["phase_ratio_by_date"].items():
            L.append(f"| {r['motor']} | {dt} | {v[0]} | {v[1]} | {v[2]} |")
    lsf = next((r for r in rows if r["motor"] == "L-SF-04"), None)
    if lsf and lsf["phase_ratio_by_date"]:
        s_vals = [v[1] for v in lsf["phase_ratio_by_date"].values()]
        L += ["", f"L-SF-04 의 S상 비는 날짜별 {min(s_vals)}~{max(s_vals)}(창 표준편차 {lsf['phase_ratio_std_RST'][1]}) — 전 구간에서 거의 일정하면 **센서 채널 게인 차이 가설**, 날짜·시간대에 따라 움직이면 **공급 불평형 가설**. 전압 채널이 없어 결론은 가설로만 두고 보정하지 않는다(게인 보정은 가정)."]
    L += ["", "## 제외 창 예시 (모터별 최대 5)", ""]
    for r in rows:
        for e in r["excluded_examples"]:
            L.append(f"- {r['motor']} `{e['file']}`: {', '.join(e['reasons'])} (I₁ {e['I1_A']} A, 기본파비 {e['fund_over_rms']}, 상비 {e['phase_ratio']})")
    out_md = os.path.join(VIZ, "docs", "aihub_baseline_gated.md"); open(out_md, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"→ {out_md} ({len(rows)} 모터) ; " + "; ".join(f"{r['motor']} {r['n_kept']}/{r['n_files']} i2i1 {r['i2i1']['median'] if r['i2i1'] else '—'}" for r in rows))


if __name__ == "__main__":
    main()
