# -*- coding: utf-8 -*-
"""check_m1_scene.py — M1 장면 실행 로그(logs/m1_model/demo_*.csv) ↔ 대시보드 fleet 로그(logs/fleet/M1/electrical/demo_fleet.csv) 비교 + FPS 집계 → assets/motors/M1/scene_check.json

HUD 숫자(I₂/I₁·전류·상태)는 같은 엔진·같은 LUT 에서 나오므로 장면 끝 시점 값이 같아야 한다. 새 계산 없음 — 로그를 읽어 비교만 한다.
  py -3.12 -X utf8 tools/cad/check_m1_scene.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIZ = ROOT / "motor_dt_viz"


def rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8", newline="")))


def main():
    # 전체 시나리오(245 s, 4 Hz ≈ 980 행)를 덮은 실행 중 **가장 최근** 것 (D4 2026-10-21: 예전엔 '가장 긴' 실행이라 옛 I₁ 규약 로그를 집었다)
    cands = [(p, sum(1 for _ in open(p, encoding="utf-8"))) for p in glob.glob(str(VIZ / "logs" / "m1_model" / "demo_*.csv"))]
    full = [p for p, n in cands if n >= 900] or [p for p, _ in sorted(cands, key=lambda x: x[1])[-1:]]
    runs = sorted(full, key=os.path.getmtime)
    if not runs:
        raise SystemExit("logs/m1_model/demo_*.csv 없음 — 먼저 --m1_model --log_subdir m1_model 로 실행")
    run = rows(runs[-1]); fleet = rows(VIZ / "logs" / "fleet" / "M1" / "electrical" / "demo_fleet.csv")
    fleet_status = rows(VIZ / "logs" / "fleet" / "M1" / "electrical" / "status_fleet.csv")      # 판정은 status_fleet.csv 에 있다 (t_real_s 로 맞춤)
    st_by_t = {round(float(r["t_real_s"]), 2): r["status"] for r in fleet_status}
    for r in fleet:
        r["status"] = st_by_t.get(round(float(r["t_real_s"]), 2)) or r.get("status")
    def last_per_step(rs):
        out = {}
        for r in rs:
            if r["step"] != "manual":
                out[r["step"]] = r
        return out
    a, b = last_per_step(run), last_per_step(fleet)
    # fleet 로그에 없는 M1 전용 장면(8턴·16턴·저항성·반부하)은 엔진 설계값(expected_i2i1 = LUT + 고유 비대칭)과 비교
    sys.path.insert(0, str(VIZ))
    from engine import motor_library as ml
    from engine.current_model import CurrentModel
    from viz.m1_model import M1Model
    m = ml.load_motor("M1"); cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m)); M1Model.register_extra_cases(cm, str(VIZ))
    extra = []
    for step, ra in a.items():
        if step in b or ra["case"] not in cm.cases:
            continue
        exp = cm.expected_i2i1(ra["case"]); st = cm.evaluate_case(ra["case"])
        d = {"step": step, "case": ra["case"], "t_run": float(ra["t_real_s"]), "i2_over_i1": [float(ra["i2_over_i1"]), round(exp, 4), abs(float(ra["i2_over_i1"]) - exp)],
             "Ia_rms": [float(ra["Ia_rms"]), round(st.rms_A[0], 1), abs(float(ra["Ia_rms"]) - st.rms_A[0])], "i2_over_in": [ra.get("i2_over_in"), round(st.i2_over_in, 4) if st.i2_over_in is not None else None],
             "status": [ra.get("status"), "(엔진 설계값, fleet 없음)"], "ref": "engine expected_i2i1 (LUT v2 + inherent)"}
        d["match"] = d["i2_over_i1"][2] <= 0.0006 and d["Ia_rms"][2] <= 0.15
        extra.append(d)
    table = []
    for step in a:
        if step not in b:
            continue
        ra, rb = a[step], b[step]
        d = {"step": step, "case": ra["case"], "t_run": float(ra["t_real_s"]), "t_fleet": float(rb["t_real_s"])}
        for k in ("Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1", "rpm"):
            va, vb = float(ra[k]), float(rb[k]); d[k] = [va, vb, abs(va - vb)]
        d["i2_over_in"] = [ra.get("i2_over_in"), rb.get("i2_over_in")]
        d["status"] = [ra.get("status"), rb.get("status")]
        d["match"] = all(d[k][2] <= (0.0006 if k == "i2_over_i1" else 0.15 if k != "rpm" else 30.0) for k in ("Ia_rms", "Ib_rms", "Ic_rms", "i2_over_i1", "rpm")) and d["status"][0] == d["status"][1]
        table.append(d)
    fps = [float(r["fps"]) for r in run if float(r["fps"]) > 0 and float(r["t_s"]) > 5]
    # 변형별(스크린샷 계획: 0~12 full, 12~66 cutaway, 66~70 windings_only, 70~ full)
    def seg(lo, hi):
        v = [float(r["fps"]) for r in run if lo <= float(r["t_real_s"]) < hi and float(r["fps"]) > 0]
        return round(statistics.mean(v), 1) if v else None
    out = {"run_csv": os.path.relpath(runs[-1], ROOT), "fleet_csv": "motor_dt_viz/logs/fleet/M1/electrical/demo_fleet.csv", "steps": table, "extra_steps": extra,
           "all_match": all(d["match"] for d in table + extra), "n_steps": len(table), "n_extra": len(extra),
           "fps": {"mean": round(statistics.mean(fps), 1) if fps else None, "min": round(min(fps), 1) if fps else None, "full_0_12s": seg(6, 12), "cutaway_12_66s": seg(14, 66), "windings_only_66_70s": seg(66, 70), "full_70s_": seg(70, 1e9)}}
    (ROOT / "assets" / "motors" / "M1" / "scene_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for d in extra:
        print(f"{d['step']:22s} run/engine Ia {d['Ia_rms'][0]:.1f}/{d['Ia_rms'][1]:.1f} I2/I1 {d['i2_over_i1'][0]:.4f}/{d['i2_over_i1'][1]:.4f} I2/In {d['i2_over_in'][0]}/{d['i2_over_in'][1]} {'✓' if d['match'] else '✗'}")
    for d in table:
        print(f"{d['step']:18s} run/fleet Ia {d['Ia_rms'][0]:.1f}/{d['Ia_rms'][1]:.1f} I2/I1 {d['i2_over_i1'][0]:.4f}/{d['i2_over_i1'][1]:.4f} status {d['status'][0]}/{d['status'][1]} {'✓' if d['match'] else '✗'}")
    print("fps", out["fps"], "all_match", out["all_match"])


if __name__ == "__main__":
    main()
