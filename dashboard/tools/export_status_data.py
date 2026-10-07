# -*- coding: utf-8 -*-
"""export_status_data.py — 상태 보드(#/status) 데이터 export (TASK_다중모터 §7).

  <python> dashboard/tools/export_status_data.py

입력 (전부 config·로그·엔진 — 숫자를 여기서 만들지 않는다):
  motor_dt_viz/config/motors/<id>.yaml, config/thresholds.yaml, config/status_demo.yaml
  motor_dt_viz/logs/fleet/<id>/<mode>/demo_fleet.csv + status_fleet.csv   (tools/run_fleet.py 가 만든 엔진 배치 로그, 판정 포함)
  dashboard/public/data/<mode>/{scenarios,thresholds,narration_values}.json (장면 경계·부품 이름·M5 해설 변수)
출력:
  dashboard/public/data/fleet/index.json          모터 5종 사양·임계값·데모 위치·시나리오·정직성 라벨
  dashboard/public/data/fleet/<id>_<mode>.json    시계열(온도·전류·I₂/I₁·진동·베어링 지표) + 판정(status/cause) + 장면 변수

판정은 status_fleet.csv(engine/thresholds.py 가 히스테리시스·지속 시간까지 적용한 결과)를 그대로 옮긴다 — 대시보드가 다시 판정하지 않는다.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(VIZ, "tools"))

import yaml  # noqa: E402

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402
from run_fleet import bearing_index  # noqa: E402

FLEET = os.path.join(VIZ, "logs", "fleet")
OUT = os.path.join(DASH, "public", "data", "fleet")
MODES = ("mechanical", "electrical")
NODES = ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "endshield_de", "endshield_nde", "frame")
SIGNALS = {
    "temperature": {"label": "온도", "unit": "°C"},
    "current_ratio": {"label": "전류 (정격 대비)", "unit": "×"},
    "i2i1": {"label": "I₂/I₁ (역상 전류비)", "unit": ""},
    "vibration": {"label": "진동 속도 RMS", "unit": "mm/s"},
    "bearing_index": {"label": "베어링 결함 지표", "unit": "배"},
}
HONESTY_LINES = ["대표 사양 (명판 아님)", "외형은 프레임 비례 스케일", "열회로 계수는 M5 기준 스케일", "ITSC는 해석식 등가 표현"]
SPEC_KEYS = ("rated_power_kw", "poles", "sync_rpm", "rated_rpm", "voltage_v", "frequency_hz", "connection", "efficiency", "power_factor",
             "rated_line_current_a", "rated_phase_current_a", "frame", "insulation_class", "duty", "bearing_de", "bearing_nde", "geometry_scale", "source")


def j(path):
    return json.load(open(path, encoding="utf-8"))


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", newline="")))


def f(x):
    return float(x)


def scene_values(motor: ml.Motor, mode: str, demo: list[dict], base: dict, steps: list[dict], th_mode: dict) -> dict:
    """M5 해설 변수(narration_values.json)를 바탕으로, 모터별로 달라지는 수치만 로그로 덮어쓴다 (cause_chain 치환용)."""
    out = {}
    e = th_mode.get("electrical", {})
    r = e.get("ratio_thresholds", {})
    labels = e.get("status_labels", {})
    i_line, i_ph = motor.rated_line_current_a, motor.rated_phase_current_a
    healthy_i2i1 = None
    for s in steps:
        v = dict(base.get(s["id"], {}))
        te = s["t_end"] - 0.3
        row = max((x for x in demo if f(x["t_real_s"]) <= te), key=lambda x: f(x["t_real_s"]))
        row0 = min((x for x in demo if f(x["t_real_s"]) >= s["t_start"]), key=lambda x: f(x["t_real_s"]))
        for n in NODES:
            v[f"{n}_end"] = round(f(row[f"T_{n}"]), 1)
            v[f"{n}_start"] = round(f(row0[f"T_{n}"]), 1)
        v["vib_end"] = round(f(row["vibration_mms"]), 1)
        if mode == "electrical":
            a, b, c = (f(row[k]) for k in ("Ia_rms", "Ib_rms", "Ic_rms"))
            i2 = f(row["i2_over_i1"])
            if healthy_i2i1 is None:
                healthy_i2i1 = i2
            v.update({"rated_line_A": i_line, "rated_phase_A": i_ph,
                      "a_rms_end": round(a, 1), "a_pct_end": round(a / i_line * 100), "a_phase_rms_end": round(a / 1.732, 1),
                      "bc_rms_end": round((b + c) / 2, 1), "bc_pct_end": round((b + c) / 2 / i_line * 100),
                      "i2i1_end": i2, "i2i1_x_normal_end": round(i2 / healthy_i2i1, 1) if healthy_i2i1 else None})
            for k, x in (("line_over_danger_A", "over_danger"), ("line_over_caution_A", "over_caution"), ("line_under_caution_A", "under_caution"), ("line_under_danger_A", "under_danger")):
                if x in r:
                    v[k] = round(i_line * f(r[x]), 1)
                    v[k.replace("line_", "phase_")] = round(i_ph * f(r[x]), 1)
            ra = a / i_line
            st = ("over_danger" if ra > f(r.get("over_danger", 1.25)) else "over_caution" if ra > f(r.get("over_caution", 1.10))
                  else "under_danger" if ra < f(r.get("under_danger", 0.5)) else "under_caution" if ra < f(r.get("under_caution", 0.85)) else "normal")
            v["a_status_end"] = labels.get(st, st)
        out[s["id"]] = v
    return out


def export_motor(motor: ml.Motor, mode: str, th_mode: dict, sc_mode: dict, nv_mode: dict, th_cfg: dict) -> dict:
    d = rows(os.path.join(FLEET, motor.id, mode, "demo_fleet.csv"))
    s = rows(os.path.join(FLEET, motor.id, mode, "status_fleet.csv"))
    assert len(d) == len(s), f"{motor.id} {mode}: demo/status 행 수 불일치"
    i_line = motor.rated_line_current_a
    steps = sc_mode["steps"]
    scale = {st["id"]: f(st["time_scale"]) for st in steps}
    out = {
        "motor": motor.id, "mode": mode, "n": len(d), "source": "logs/fleet (engine batch, tools/run_fleet.py) · 판정 engine/thresholds.py",
        "t": [round(f(r["t_real_s"]), 3) for r in d],
        "step": [r["step"] for r in d],
        "time_scale": [scale.get(r["step"], 1.0) if mode == "mechanical" else 1.0 for r in d],
        "temperature_C": {n: [f(r[f"T_{n}"]) for r in d] for n in NODES},
        "current_rms_A": {p: [f(r[f"I{p.lower()}_rms"]) for r in d] for p in ("A", "B", "C")},
        "current_ratio": {p: [round(f(r[f"I{p.lower()}_rms"]) / i_line, 4) for r in d] for p in ("A", "B", "C")},
        "i2i1": [f(r["i2_over_i1"]) for r in d],
        "vibration_mms": [f(r["vibration_mms"]) for r in d],
        "bearing_index": [bearing_index(th_cfg, [x for x in r["faults"].split(";") if x]) for r in d],
        "status": [r["status"] for r in s],
        "cause_signal": [r["cause_signal"] for r in s],
        "cause_component": [r["cause_component"] for r in s],
        "cause_value": [f(r["value"]) for r in s],
        "cause_threshold": [r["threshold"] for r in s],
        "levels": {k: [r[k] for r in s] for k in SIGNALS},
        "scene_values": scene_values(motor, mode, d, nv_mode.get("scenes", {}), steps, th_mode),
    }
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    thr = load("thresholds")
    demo_cfg = yaml.safe_load(open(os.path.join(VIZ, "config", "status_demo.yaml"), encoding="utf-8"))
    th = {m: j(os.path.join(DASH, "public", "data", m, "thresholds.json")) for m in MODES}
    sc = {m: j(os.path.join(DASH, "public", "data", m, "scenarios.json")) for m in MODES}
    nv = {m: j(os.path.join(DASH, "public", "data", m, "narration_values.json")) for m in MODES}
    node_labels = {p["key"]: p["label"] for p in th["mechanical"]["thermal"]["parts"]}
    motors = []
    for mid in ml.list_ids():
        m = ml.load_motor(mid)
        th_cfg = ml.thermal_cfg(m)
        ss = ThermalModel(th_cfg).steady_state(1.0, [])
        files = {}
        for mode in MODES:
            data = export_motor(m, mode, th[mode], sc[mode], nv[mode], th_cfg)
            name = f"{mid}_{mode}.json"
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            files[mode] = name
            print(f"[status] {mid} {mode}: {data['n']} 샘플 → {name}")
        pos = demo_cfg["positions"][mid]
        motors.append({
            "id": mid, "name": m.name, "tags": dict(m.tags or {}),
            "spec": {k: getattr(m, k) for k in SPEC_KEYS},
            "derived": {"slip": round(m.slip, 4), "rotor_freq_hz": round(m.rotor_freq_hz, 3), "torque_nm": round(m.torque_nm, 1),
                        "bpfo_hz": round(m.bpfo_hz(), 1), "bpfi_hz": round(m.bpfi_hz(), 1), "loss_w": round(m.loss_w)},
            "vibration": m.vib_thresholds,
            "steady_C": {k: round(v, 1) for k, v in ss.items()},
            "thermal_scaled_from": th_cfg.get("scaled_from"),
            "demo": {"mode": pos["mode"], "t_s": f(pos["t_s"]), "expect": pos.get("expect"), "why": pos.get("why", "")},
            "files": files,
        })
    index = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "config/motors/*.yaml · config/thresholds.yaml · config/status_demo.yaml · logs/fleet (engine batch)",
        "honesty": {"label": "대표 사양 기반 시뮬레이션 추정값 (Simulation-based)", "lines": HONESTY_LINES,
                    "itsc_note": "I₂/I₁ 목표값은 M5 기준 해석식 등가값을 전 모터에 적용 (TASK §4.3)"},
        "levels": list(thr["levels"]), "labels_ko": thr["labels_ko"], "icons": thr["icons"], "colors": thr["colors"],
        "signals": SIGNALS, "node_labels": node_labels,
        "phase_labels": th["electrical"]["electrical"].get("phase_labels", {"A": "A", "B": "B", "C": "C"}),
        "thresholds": {
            "temperature": {k: thr["temperature"][k] for k in ("bearing", "winding", "rotor", "default", "component_class")},
            "current_ratio": thr["current_ratio"], "i2i1": thr["i2i1"], "bearing_index": thr["bearing_index"],
            "hysteresis_fraction": thr["hysteresis"]["fraction"], "persistence_s": thr["persistence_s"],
            "vibration_split_kw": ml.VIB_STANDARD_SPLIT_KW,
        },
        "scenarios": {m: {"total_duration_s": sc[m]["total_duration_s"],
                          "steps": [{k: st[k] for k in ("n", "id", "label", "subtitle", "t_start", "t_end", "time_scale", "load", "faults", "electrical_case")} for st in sc[m]["steps"]]}
                      for m in MODES},
        "demo_note": demo_cfg.get("note", ""),
        "motors": motors,
    }
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    print(f"[status] index.json: {len(motors)} 모터 → {OUT}")


if __name__ == "__main__":
    main()
