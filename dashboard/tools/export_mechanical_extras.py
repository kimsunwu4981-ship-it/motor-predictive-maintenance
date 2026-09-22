# -*- coding: utf-8 -*-
"""export_mechanical_extras.py — 기계 대시보드(실시간 해설)용 추가 데이터.

export_dashboard_data.py 가 만든 기본 dict 를 받아 다음을 덧붙인다. 전기 모드는 건드리지 않는다.

  timeseries.json  + loss_W(부품별 손실열 W), time_scale, sim_elapsed_s, step_elapsed_s, replay_check
  events.json        로그에서 자동 추출한 사건 (등급 변화, 진동 등급 변화, 투시 on/off, 장면 전환, 정상 복귀)
  narration_values.json  장면별 해설 치환 변수 ({bearing_de_end} 등) — 문구는 content YAML, 숫자는 여기서
  thresholds.json  + vibration_iso(ISO 20816-3 경계), thermal.couplings(열 경로), loss_rated_W

손실열은 로그에 없으므로 **엔진을 같은 시나리오로 재실행**해 얻는다. 손실은 결함·부하만의 함수라
(온도 무관) 재실행값이 곧 정확값이다. 온도는 로그를 정본으로 쓰고, 재실행 온도는 검증에만 쓴다
(M0 실측: 장면 경계 ±1 s 를 제외하면 최대 2.3 °C, 경계 안은 최대 5.4 °C — 프레임 정렬 차이).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)

import yaml  # noqa: E402  (engine 도 PyYAML 을 쓴다)
from engine.config_loader import load  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

STAGES = ("normal", "caution", "warning", "danger")
STAGE_KO = {"normal": "정상", "caution": "주의", "warning": "경고", "danger": "위험"}
ZONES = ("Normal", "Watch", "Plan", "Act")
ZONE_KO = {"Normal": "정상", "Watch": "주시", "Plan": "정비 계획", "Act": "즉시 조치"}
REPLAY_H = 1.0 / 60          # 데모 프레임 간격으로 적분해야 장면 경계가 맞는다
EDGE_S = 1.0                 # 장면 경계 ±1 s 는 프레임 정렬 차이로 오차가 커서 검증에서 제외
TOL_C = 2.5                  # 경계 밖 허용 오차 (M0 제안, 사용자 승인)
CONTENT_DIR = os.path.join(DASH, "public", "content", "mechanical")


def _narration_cfg() -> dict:
    p = os.path.join(CONTENT_DIR, "narration.yaml")
    if not os.path.exists(p):
        return {"scenes": {}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"scenes": {}}


# ----------------------------------------------------------------- 엔진 재실행
def replay(ts: dict) -> dict:
    """로그 시각마다 손실열·배속·누적 시뮬레이션 시간을 계산하고 온도 오차를 기록한다."""
    player = ScenarioPlayer.for_mode("mechanical")
    tm = ThermalModel()
    parts = list(ts["temperature_C"].keys())
    bounds, acc = [], 0.0
    for s in player.steps:
        acc += float(s["duration_s"])
        bounds.append(acc)

    loss = {k: [] for k in parts}
    time_scale, sim_elapsed, step_elapsed, step_n = [], [], [], []
    inner_err = {k: 0.0 for k in parts}
    edge_err = {k: 0.0 for k in parts}
    t = 0.0
    sim = 0.0
    st = tm.step(0.0, 1.0, [], winding_current_pu=None, use_duty_cycle=False)
    for i, tr in enumerate(ts["t_real_s"]):
        while t + REPLAY_H <= tr + 1e-9:
            f = player.frame_at(t + REPLAY_H)
            st = tm.step(REPLAY_H * f.time_scale, f.load, f.thermal_faults, winding_current_pu=None, use_duty_cycle=False)
            sim += REPLAY_H * f.time_scale
            t += REPLAY_H
        rem = tr - t
        if rem > 1e-6:
            f = player.frame_at(tr)
            st = tm.step(rem * f.time_scale, f.load, f.thermal_faults, winding_current_pu=None, use_duty_cycle=False)
            sim += rem * f.time_scale
            t = tr
        f = player.frame_at(tr)
        for k in parts:
            loss[k].append(round(float(st.loss_W[k]), 1))
            e = abs(st.temperature_C[k] - ts["temperature_C"][k][i])
            near = any(abs(tr - b) <= EDGE_S for b in bounds)
            d = edge_err if near else inner_err
            d[k] = max(d[k], e)
        time_scale.append(f.time_scale)
        sim_elapsed.append(round(sim, 1))
        step_elapsed.append(round(f.step_elapsed_s, 3))
        step_n.append(int(next(n for n, s in enumerate(player.steps, 1) if s["id"] == f.step_id)))
    return {
        "loss_W": loss, "time_scale": time_scale, "sim_elapsed_s": sim_elapsed,
        "step_elapsed_s": step_elapsed, "step_n": step_n,
        "replay_check": {
            "method": f"engine replay, h={REPLAY_H:.4f} s real, edge_excluded_s={EDGE_S}, tolerance_C={TOL_C}",
            "max_err_inner_C": {k: round(v, 2) for k, v in inner_err.items()},
            "max_err_edge_C": {k: round(v, 2) for k, v in edge_err.items()},
            "pass": max(inner_err.values()) <= TOL_C,
        },
    }


# ----------------------------------------------------------------- 이벤트 추출
def extract_events(ts: dict, th: dict, sc: dict, focus_by_scene: dict) -> list[dict]:
    t = ts["t_real_s"]
    parts = {p["key"]: p for p in th["thermal"]["parts"]}
    labels = {p["key"]: p["label"] for p in th["thermal"]["parts"]}
    iso = th["vibration_iso"]
    zone_thr = {"Watch": iso["watch_mms"], "Plan": iso["plan_mms"], "Act": iso["act_mms"], "Normal": 0.0}
    events: list[dict] = []

    def scene_at(tt: float) -> dict:
        return next((s for s in sc["steps"] if tt < s["t_end"]), sc["steps"][-1])

    # 장면 전환
    for s in sc["steps"]:
        events.append({"type": "scene", "t": s["t_start"], "scene": s["n"], "scene_id": s["id"],
                       "time_scale": s["time_scale"], "label": s["label"], "priority": 0})

    # 부품 등급 변화 (오르면 stage_up, 내리면 stage_down; 정상 복귀는 recovered)
    for k, arr in ts["stage"].items():
        for i in range(1, len(arr)):
            a, b = arr[i - 1], arr[i]
            if a == b:
                continue
            up = STAGES.index(b) > STAGES.index(a)
            p = parts[k]
            # 넘은 경계값: 오를 때는 b 단계의 하한, 내릴 때는 a 단계의 하한
            key = b if up else a
            thr = {"caution": p["normal_max_C"], "warning": p["caution_max_C"], "danger": p["warning_max_C"]}.get(key)
            sn = scene_at(t[i])
            focus = focus_by_scene.get(sn["id"])
            ev = {"type": "stage_up" if up else ("recovered" if b == "normal" else "stage_down"),
                  "t": t[i], "scene": sn["n"], "part": k, "part_label": labels[k],
                  "from": a, "to": b, "from_ko": STAGE_KO[a], "to_ko": STAGE_KO[b],
                  "threshold_C": thr, "temp_C": ts["temperature_C"][k][i],
                  "is_focus": k == focus, "priority": 1 if k == focus else 3}
            if k == focus and up and b == "caution":
                ev["note"] = "early_warning"          # VIGENT 조기 경보 시점
            events.append(ev)

    # 진동 등급 변화
    z = ts["iso_zone"]
    for i in range(1, len(z)):
        if z[i] != z[i - 1]:
            up = ZONES.index(z[i]) > ZONES.index(z[i - 1])
            sn = scene_at(t[i])
            events.append({"type": "vib_zone", "t": t[i], "scene": sn["n"], "from": z[i - 1], "to": z[i],
                           "from_ko": ZONE_KO[z[i - 1]], "to_ko": ZONE_KO[z[i]], "up": up,
                           "threshold_mms": zone_thr[z[i] if up else z[i - 1]],
                           "value_mms": ts["vibration_mms"][i], "priority": 2})

    # 투시(엔드실드 반투명): DE 베어링이 경고 이상이면 켜진다 (demo_integrated 의 xray_on 규칙)
    on = False
    for i, s in enumerate(ts["stage"]["bearing_de"]):
        now = s in ("warning", "danger")
        if now != on:
            sn = scene_at(t[i])
            events.append({"type": "xray_on" if now else "xray_off", "t": t[i], "scene": sn["n"],
                           "part": "bearing_de", "part_label": labels["bearing_de"], "priority": 3})
            on = now

    events.sort(key=lambda e: (e["t"], e["priority"]))
    for n, e in enumerate(events):
        e["id"] = n
    return events


# ----------------------------------------------------------------- 해설 치환 변수
def narration_values(ts: dict, th: dict, sc: dict, faults: dict, extras: dict) -> dict:
    """장면별 치환 변수. 문구는 content/narration.yaml, 숫자는 전부 여기서 온다."""
    t = ts["t_real_s"]
    parts = {p["key"]: p for p in th["thermal"]["parts"]}
    fitems = {f["key"]: f for f in faults["items"]}
    lt = sc["lead_time"]
    out = {}

    def idx_at(tt: float) -> int:
        i = max(j for j, x in enumerate(t) if x <= tt)
        return i

    for s in sc["steps"]:
        i_end = idx_at(s["t_end"] - 0.3)
        i_start = idx_at(s["t_start"] + 0.05)
        v: dict = {"scene": s["n"], "scene_label": s["label"], "time_scale": s["time_scale"],
                   "t_start": s["t_start"], "t_end": s["t_end"],
                   "sim_minutes": round((s["t_end"] - s["t_start"]) * s["time_scale"] / 60, 1),
                   "sim_elapsed_min_end": round(extras["sim_elapsed_s"][i_end] / 60, 1),
                   "vib_end": ts["vibration_mms"][i_end], "iso_end": ts["iso_zone"][i_end],
                   "iso_end_ko": ZONE_KO[ts["iso_zone"][i_end]],
                   "lead_s": lt.get("lead_s"), "lead_sim_min": round((lt.get("lead_sim_s") or 0) / 60, 1)}
        for k, p in parts.items():
            v[f"{k}_end"] = round(ts["temperature_C"][k][i_end], 1)
            v[f"{k}_start"] = round(ts["temperature_C"][k][i_start], 1)
            v[f"{k}_stage_end"] = STAGE_KO[ts["stage"][k][i_end]]
            v[f"{k}_normal"] = p["normal_max_C"]
            v[f"{k}_caution"] = p["caution_max_C"]
            v[f"{k}_warning"] = p["warning_max_C"]
            v[f"{k}_note"] = p.get("note", "")
            v[f"{k}_loss_end_W"] = round(extras["loss_W"][k][i_end])
        for fk in s["faults"]:
            f = fitems.get(fk, {})
            for key in ("loss_multiplier", "load_multiplier", "r_amb_multiplier", "extra_loss_W", "vibration_mms"):
                if f.get(key) is not None:
                    v[key] = f[key]
            if f.get("load_multiplier"):
                v["load_pct"] = round(f["load_multiplier"] * 100)
        out[s["id"]] = v
    return out


# ----------------------------------------------------------------- 진입점
def apply_extras(th: dict, ts: dict, sc: dict, faults: dict) -> tuple[list[dict], dict]:
    """기본 dict 들을 제자리에서 확장하고 (events, narration_values) 를 돌려준다."""
    motor, thermal = load("motor"), load("thermal")
    iso = motor["vibration_iso20816_3"]
    th["vibration_iso"] = {k: float(iso[f"{k}_mms"]["value"]) for k in ("watch", "plan", "act")}
    th["vibration_iso"] = {"watch_mms": th["vibration_iso"]["watch"], "plan_mms": th["vibration_iso"]["plan"],
                           "act_mms": th["vibration_iso"]["act"], "zone_labels": ZONE_KO,
                           "basis": "ISO 20816-3 Group 2 (15~300 kW, 강성 지지)"}
    th["thermal"]["couplings"] = [{"a": a, "b": b, "R_K_per_W": float(r)} for a, b, r in thermal["couplings"]]
    # 단면도가 영상과 같은 색을 내도록 컬러맵 원본(colors.yaml thermal) 을 그대로 넘긴다
    colors = load("colors")
    th["thermal"]["colormap"] = {
        "stops": [{"pos": float(x["pos"]), "color": list(map(float, x["color"])), "blend": float(x["blend"]),
                   "emissive": list(map(float, x["emissive"])), "intensity": float(x["intensity"])} for x in colors["thermal"]["stops"]],
        "normalize": {k: float(v) for k, v in colors["thermal"]["normalize"].items()},
        "pulse": {"enabled": bool(colors["thermal"]["pulse"]["enabled"]), "start_stage": colors["thermal"]["pulse"]["start_stage"],
                  "hz": float(colors["thermal"]["pulse"]["hz"]), "depth": float(colors["thermal"]["pulse"]["depth"])},
        "base_materials": {k: list(map(float, v["color"])) for k, v in colors["base_materials"].items()},
    }
    tm = ThermalModel()
    th["thermal"]["loss_rated_W"] = {n.key: float(n.loss_rated_W) for n in tm.nodes}
    th["thermal"]["loss_model"] = {n.key: n.loss_model for n in tm.nodes}

    extras = replay(ts)
    ts.update({k: extras[k] for k in ("loss_W", "time_scale", "sim_elapsed_s", "step_elapsed_s", "step_n", "replay_check")})

    cfg = _narration_cfg()
    focus = {sid: (scene or {}).get("focus_component") for sid, scene in (cfg.get("scenes") or {}).items()}
    events = extract_events(ts, th, sc, focus)
    values = narration_values(ts, th, sc, faults, extras)
    return events, values
