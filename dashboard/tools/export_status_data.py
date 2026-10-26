# -*- coding: utf-8 -*-
"""export_status_data.py — 상태 보드(#/status) 데이터 export (TASK_다중모터 §7).

  <python> dashboard/tools/export_status_data.py

입력 (전부 config·로그·엔진 — 숫자를 여기서 만들지 않는다):
  motor_dt_viz/config/motors/<id>.yaml, config/thresholds.yaml, config/status_demo.yaml
  motor_dt_viz/logs/fleet/<id>/<mode>/demo_fleet.csv + status_fleet.csv   (tools/run_fleet.py 가 만든 엔진 배치 로그, 판정 포함)
  dashboard/public/data/<mode>/{scenarios,thresholds,narration_values}.json (장면 경계·부품 이름·M5 해설 변수)
출력:
  dashboard/public/data/fleet/index.json          모터 5종 사양·임계값·데모 위치·시나리오·정직성 라벨
  dashboard/public/data/fleet/<id>_<mode>.json    시계열(온도·전류·I₂/I₁·진동·베어링 kurtosis·고주파 배율) + 판정(status/cause) + 장면 변수

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
from engine.current_model import CurrentModel  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402
from engine.thresholds import bearing_level  # noqa: E402
from run_fleet import bearing_signals  # noqa: E402

FLEET = os.path.join(VIZ, "logs", "fleet")
OUT = os.path.join(DASH, "public", "data", "fleet")
MODES = ("mechanical", "electrical")
NODES = ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "endshield_de", "endshield_nde", "frame")
SIGNALS = {
    "temperature": {"label": "온도", "unit": "°C"},
    "current_ratio": {"label": "전류 (정격 대비)", "unit": "×"},
    "i2i1": {"label": "I₂/I₁ (역상 전류비)", "unit": ""},
    "vibration": {"label": "진동 속도 RMS", "unit": "mm/s"},
    "bearing_kurtosis": {"label": "베어링 kurtosis", "unit": ""},
    "bearing_hf_ratio": {"label": "베어링 고주파 RMS (정상 대비)", "unit": "배"},
}
BEARING_COMBINED = {"label": "베어링 종합 (둘 중 나쁜 쪽)", "unit": ""}
HONESTY_LINES = ["카탈로그 사양(출처 아이콘 참조, 결선은 현장 확인)", "외형·내부는 카탈로그·데이터 시트 재구성(Maxwell 체적 ±2 % 검증)",
                 "열회로 계수는 22 kW 기준 스케일 — M1에서 낙관적일 수 있음", "ITSC 곡선은 등가회로 LUT + 2D 와전류 검증, 실측 기준선 전 참고"]
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


def case_extras(cm: CurrentModel, cases: list[str]) -> dict:
    """단순 보기(2026-10-26) 근거 서랍 비교표의 '지금 표시값' — 엔진이 이미 계산하는 케이스별 값을 그대로 옮긴다 (새 계산 없음).
    i2i1_fault: LUT 결함분 r (고유 비대칭 제외) · i2_over_in: 엔진 analyze 의 I₂/I_n · i_f_A / p_loop_total_W: LUT 단락 루프 전류·총손실. LUT 를 쓰지 않는 케이스는 None."""
    out = {}
    for c in cases:
        if c in out:
            continue
        if not cm.case_uses_lut(c):
            out[c] = {"i2i1_fault": None, "i2_over_in": None, "i_f_A": None, "p_loop_total_W": None}
            continue
        q = cm.lut_point(c) or {}
        st = cm.evaluate_case(c)
        loop = cm.short_loop(c) or {}
        out[c] = {"i2i1_fault": None if q.get("i2_over_i1") is None else round(float(q["i2_over_i1"]), 6),
                  "i2_over_in": None if st.i2_over_in is None else round(float(st.i2_over_in), 5),
                  "i_f_A": None if loop.get("I_f_A") is None else round(float(loop["I_f_A"]), 4),
                  "p_loop_total_W": round(float(cm.loop_loss_W(c)), 2)}
    return out


def export_motor(motor: ml.Motor, mode: str, th_mode: dict, sc_mode: dict, nv_mode: dict, th_cfg: dict, cm: CurrentModel | None = None) -> dict:
    d = rows(os.path.join(FLEET, motor.id, mode, "demo_fleet.csv"))
    s = rows(os.path.join(FLEET, motor.id, mode, "status_fleet.csv"))
    assert len(d) == len(s), f"{motor.id} {mode}: demo/status 행 수 불일치"
    i_line = motor.rated_line_current_a
    steps = sc_mode["steps"]
    scale = {st["id"]: f(st["time_scale"]) for st in steps}
    extras = case_extras(cm, sorted({r["case"] for r in d})) if cm is not None else {}
    t_amb = f(d[0]["T_winding"]) if d else None          # 권선 ΔT 기준 = 첫 샘플(주위 온도와 같은 초기값). 전기 모드는 열 적분이 없어 0 → null 로 둔다
    thermal_on = any(abs(f(r["T_winding"]) - t_amb) > 1e-6 for r in d) if d else False
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
        "bearing_kurtosis": [bearing_signals(th_cfg, [x for x in r["faults"].split(";") if x])["bearing_kurtosis"] for r in d],
        "bearing_hf_ratio": [bearing_signals(th_cfg, [x for x in r["faults"].split(";") if x])["bearing_hf_ratio"] for r in d],
        "bearing_site_hint": None,                      # 결함 부위 추정(포락선 BPFO/BPFI)은 실측 전용 — 시뮬레이션은 없음
        "status": [r["status"] for r in s],
        "cause_signal": [r["cause_signal"] for r in s],
        "cause_component": [r["cause_component"] for r in s],
        "cause_value": [f(r["value"]) for r in s],
        "cause_threshold": [r["threshold"] for r in s],
        "levels": {**{k: [r[k] for r in s] for k in SIGNALS},
                   "bearing": [r.get("bearing") or bearing_level({"bearing_kurtosis": r["bearing_kurtosis"], "bearing_hf_ratio": r["bearing_hf_ratio"]}) for r in s]},
        "scene_values": scene_values(motor, mode, d, nv_mode.get("scenes", {}), steps, th_mode),
        # ---- 단순 보기 근거 서랍용 (2026-10-26, 필드 추가만): 케이스별 엔진 값. 값이 없으면 null + 사유(extras_note)
        "i2i1_fault": [extras.get(r["case"], {}).get("i2i1_fault") for r in d],
        "i2_over_in": [extras.get(r["case"], {}).get("i2_over_in") for r in d],
        "i_f_A": [extras.get(r["case"], {}).get("i_f_A") for r in d],
        "p_loop_total_W": [extras.get(r["case"], {}).get("p_loop_total_W") for r in d],
        "winding_dT_C": [round(f(r["T_winding"]) - t_amb, 2) for r in d] if thermal_on else None,
        "extras_note": {
            "i2i1_fault": "LUT 결함분 r (고유 비대칭 제외) — engine.CurrentModel.lut_point; LUT 밖 케이스(정상·과부하·불평형·결상·무부하)는 null",
            "i2_over_in": "I₂/I_n (electrical.yaml 정격 기준) — engine.CurrentModel.analyze; LUT 케이스만",
            "i_f_A": "단락 루프 전류 [A] — engine.CurrentModel.short_loop (LUT); 단락 케이스만",
            "p_loop_total_W": "단락 루프 총손실 [W] — engine.CurrentModel.loop_loss_W (LUT, coupling_to_thermal); 단락 케이스만",
            "winding_dT_C": "권선 온도 − 첫 샘플 [°C]" + ("" if thermal_on else " — 이 모드(전기)는 열 모델을 돌리지 않아 null (통합·기계 모드에서만)"),
        },
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
    from engine.scenario_player import ScenarioPlayer
    raw_sub = {m: {s["id"]: s["subtitle"] for s in ScenarioPlayer.for_mode(m).steps} for m in MODES}
    motors = []
    for mid in ml.list_ids():
        m = ml.load_motor(mid)
        th_cfg = ml.thermal_cfg(m)
        ss = ThermalModel(th_cfg).steady_state(1.0, [])
        try:
            cm = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m))      # 근거 서랍 값(LUT 결함분·I₂/I_n·I_f·P_loop) — 엔진 그대로
        except Exception as e:  # noqa: BLE001
            print(f"[status] {mid}: CurrentModel 생성 실패 → extras null ({e})"); cm = None
        files = {}
        for mode in MODES:
            data = export_motor(m, mode, th[mode], sc[mode], nv[mode], th_cfg, cm)
            name = f"{mid}_{mode}.json"
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            files[mode] = name
            print(f"[status] {mid} {mode}: {data['n']} 샘플 → {name}")
        pos = demo_cfg["positions"][mid]
        motors.append({
            "id": mid, "name": m.name, "tags": dict(m.tags or {}),
            "spec": {k: getattr(m, k) for k in SPEC_KEYS},
            "spec_source": m.field_sources,     # 키별 출처 (catalog ✓ / assumed 🔴 …) — 래퍼로 적힌 키만
            "derived": {"slip": round(m.slip, 4), "rotor_freq_hz": round(m.rotor_freq_hz, 3), "torque_nm": round(m.torque_nm, 1),
                        "bpfo_hz": round(m.bpfo_hz(), 1), "bpfi_hz": round(m.bpfi_hz(), 1), "loss_w": round(m.loss_w)},
            "bearing_hf_baseline": m.bearing_hf_baseline,
            "vibration": m.vib_thresholds,
            "steady_C": {k: round(v, 1) for k, v in ss.items()},
            "thermal_scaled_from": th_cfg.get("scaled_from"),
            "demo": {"mode": pos["mode"], "t_s": f(pos["t_s"]), "expect": pos.get("expect"), "why": pos.get("why", "")},
            "files": files,
        })
    index = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "config/motors/*.yaml · config/thresholds.yaml · config/status_demo.yaml · logs/fleet (engine batch)",
        "honesty": {"label": "카탈로그 사양 기반 시뮬레이션 추정값 (Simulation-based)", "lines": HONESTY_LINES,
                    "itsc_note": "I₂/I₁ 은 M1 등가회로 LUT(RMxprt v2m2+MCCM, 2D 와전류 정합) + 고유 비대칭 0.027 — 실측 기준선 전 참고"},
        "scene_map": demo_cfg.get("scene_map", []),
        "levels": list(thr["levels"]), "labels_ko": thr["labels_ko"], "icons": thr["icons"], "colors": thr["colors"],
        "signals": SIGNALS, "bearing_combined": BEARING_COMBINED, "node_labels": node_labels,
        "phase_labels": th["electrical"]["electrical"].get("phase_labels", {"A": "A", "B": "B", "C": "C"}),
        "thresholds": {
            "temperature": {k: thr["temperature"][k] for k in ("bearing", "winding", "rotor", "default", "component_class")},
            "current_ratio": thr["current_ratio"], "i2i1": thr["i2i1"], "bearing": thr["bearing"],
            "hysteresis_fraction": thr["hysteresis"]["fraction"], "persistence_s": thr["persistence_s"],
            "vibration_split_kw": ml.VIB_STANDARD_SPLIT_KW,
            # P1 (2026-10-21): 지표별 출처·상태·정책 — 참고 배지·툴팁은 이 메타만 본다 (판정 규칙·값은 엔진·thresholds.yaml 그대로)
            "meta": {
                "current_ratio": {k: thr["current"]["rated_ratio"].get(k) for k in ("source", "status", "i_rated_ref")},
                "i2i1": {**{k: thr["current"]["negative_sequence"].get(k) for k in ("source", "status", "mode", "warn", "danger", "warn_multiple", "danger_multiple", "baseline")},
                         "reference_baseline": thr["current"]["negative_sequence"].get("reference_baseline")},
                "temperature": {k: thr["temperature"].get(k) for k in ("source", "status")},
                "vibration": {k: thr["vibration"].get(k) for k in ("source", "status")},
                "bearing": {k: thr["bearing"].get(k) for k in ("source", "status")},
                "policy": thr.get("judgment", {}).get("provisional_policy"),
                "stream": "simulation",          # 상태 보드 = 엔진 배치(합성 신호) → include_with_label ("임시 기준")
                "thermal_scaling_note": "열회로 계수는 22 kW(M5) 기준 스케일 — M1 정격 권선 상승 ≈25 K vs 카탈로그 B종 한도 80 K·IE3 2.2 kW 통상 50~70 K: M1 온도 판정은 낙관적일 수 있음 (실측 전 보정 불가, docs/thermal_scaling.md)",
            },
        },
        "scenarios": {m: {"total_duration_s": sc[m]["total_duration_s"],
                          "steps": [{**{k: st[k] for k in ("n", "id", "label", "subtitle", "t_start", "t_end", "time_scale", "load", "faults", "electrical_case")},
                                     "subtitle": raw_sub[m].get(st["id"], st["subtitle"])}          # 변수 포함 원문 — 보드가 모터별 scene_values 로 채운다 (D-1 ②)
                                    for st in sc[m]["steps"]]}
                      for m in MODES},
        "demo_note": demo_cfg.get("note", ""),
        "motors": motors,
    }
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=1)
    print(f"[status] index.json: {len(motors)} 모터 → {OUT}")


if __name__ == "__main__":
    main()
