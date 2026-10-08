# -*- coding: utf-8 -*-
"""export_dashboard_data.py — config + logs → 대시보드용 JSON.

대시보드는 이 스크립트가 만든 JSON 만 읽는다 (dashboard/CLAUDE.md 규칙 1).
숫자는 전부 motor_dt_viz/config/*.yaml 과 logs/<mode>/*.csv 에서 오고,
계산(임계값 정규화, 상태 판정, 정격 환산)은 motor_dt_viz/engine 을 재사용한다.

사용:
  python tools/export_dashboard_data.py --mode mechanical
  python tools/export_dashboard_data.py --mode electrical
  python tools/export_dashboard_data.py --mode all

출력: public/data/<mode>/
  thresholds.json  부품별 온도 단계 / 전류 비율·암페어 / 색상 / 정직성 라벨
  scenarios.json   영상·오프셋·챕터(단계) 구간·클립·자막·출처 / 리드 타임
  timeseries.json  로그 CSV 를 t_real 축으로 정리 (온도·전류·I2/I1·진동·상태)
  faults.json      결함별 config 수치 (도감 카드가 숫자를 참조)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)

from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

STAGES = ("normal", "caution", "warning", "danger")
STAGE_KO = {"normal": "정상", "caution": "주의", "warning": "경고", "danger": "위험"}
ELEC_STATUS = ("over_danger", "over_caution", "normal", "under_caution", "under_danger")
ELEC_STATUS_KO = {"over_danger": "위험 과전류", "over_caution": "주의 과전류", "normal": "정상",
                  "under_caution": "주의 저전류", "under_danger": "위험 저전류(결상 의심)"}
# 대시보드 온도 차트·기준표에 올릴 부품 (HUD 와 같은 순서 + 나머지)
PART_ORDER = ["bearing_de", "bearing_nde", "winding", "rotor", "shaft", "stator_core",
              "endshield_de", "endshield_nde", "frame"]
PART_HUD = ["bearing_de", "winding", "rotor", "frame"]


def V(d):
    return d["value"] if isinstance(d, dict) and "value" in d else d


def hexcolor(rgb) -> str:
    r, g, b = (max(0, min(int(round(c * 255)), 255)) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def stage_of(t: float, th: dict) -> str:
    if t <= th["normal"]:
        return "normal"
    if t <= th["caution"]:
        return "caution"
    if t <= th["warning"]:
        return "warning"
    return "danger"


def elec_status(ratio: float, th: dict) -> str:
    if ratio > th["over_danger"]:
        return "over_danger"
    if ratio > th["over_caution"]:
        return "over_caution"
    if ratio < th["under_danger"]:
        return "under_danger"
    if ratio < th["under_caution"]:
        return "under_caution"
    return "normal"


# ----------------------------------------------------------------- thresholds
def build_thresholds(mode: str) -> dict:
    motor, elec, colors, thermal = load("motor"), load("electrical"), load("colors"), load("thermal")
    tm = ThermalModel()
    cm = CurrentModel()
    i_line = cm.motor.rated_current("rated_line_A")
    i_phase = cm.motor.rated_current("rated_phase_A")
    labels = {n.key: n.label for n in tm.nodes}

    parts = []
    for key in PART_ORDER:
        if key not in labels:
            continue
        th = tm.thresholds(key)
        parts.append({
            "key": key, "label": labels[key], "hud": key in PART_HUD,
            "normal_max_C": th["normal"], "caution_max_C": th["caution"], "warning_max_C": th["warning"],
            "note": th.get("note", ""),
        })

    eth = elec["thresholds"]
    rows = []
    for st, ratio_txt, cond in (
        ("over_danger", f"r > {eth['over_danger']}", lambda: eth["over_danger"]),
        ("over_caution", f"r > {eth['over_caution']}", lambda: eth["over_caution"]),
        ("normal", f"{eth['under_caution']} ≤ r ≤ {eth['over_caution']}", None),
        ("under_caution", f"r < {eth['under_caution']}", lambda: eth["under_caution"]),
        ("under_danger", f"r < {eth['under_danger']}", lambda: eth["under_danger"]),
    ):
        r = cond() if cond else None
        rows.append({
            "status": st, "label": ELEC_STATUS_KO[st], "ratio_text": ratio_txt, "ratio": r,
            "line_A": round(i_line * r, 1) if r else None,
            "phase_A": round(i_phase * r, 1) if r else None,
            "line_range_A": [round(i_line * eth["under_caution"], 1), round(i_line * eth["over_caution"], 1)] if st == "normal" else None,
            "phase_range_A": [round(i_phase * eth["under_caution"], 1), round(i_phase * eth["over_caution"], 1)] if st == "normal" else None,
            "color": hexcolor(colors["electrical"][st]["color"]),
        })

    i2i1_marks = []
    for case_key in ("healthy", "itsc_4turn", "itsc_12turn"):
        c = elec["cases"][case_key]
        if c.get("target_i2i1") is not None:
            i2i1_marks.append({"case": case_key, "label": c["label"], "value": float(c["target_i2i1"])})

    rating = motor["rating"]
    meta = motor.get("meta", {})
    return {
        "mode": mode,
        "motor": {
            "power_kW": V(rating["power_kW"]), "poles": V(rating["poles"]),
            "voltage_LL_V": V(rating["voltage_LL_V"]), "frequency_Hz": V(rating["frequency_Hz"]),
            "rated_rpm": V(rating["rated_rpm"]), "connection": V(rating["connection"]),
            "rated_line_A": i_line, "rated_phase_A": i_phase,
            "drawing": meta.get("drawing", ""), "target": meta.get("target", ""),
            "current_source": motor["current"].get("source", ""),
        },
        "honesty": {
            "label": elec["source"]["honesty_label"] if "source" in elec and "honesty_label" in elec["source"] else "시뮬레이션 기반 추정값 (Simulation-based)",
            "rating_basis": f"정격 기준: {V(rating['power_kW']):g} kW {V(rating['poles'])}극 크레인 권상 모터 (도면 {meta.get('drawing', '').split(' (')[0]})",
            "current_note": "전류는 해석식 3상 모델로 생성 (FEM·실측 아님)",
            "thermal_note": "온도는 집중정수 열회로 9노드 모델 (측정값 아님)",
        },
        "thermal": {
            "parts": parts,
            "stage_colors": {s: hexcolor(colors["status"][s]) for s in STAGES},
            "stage_labels": STAGE_KO,
            "base_material": hexcolor(colors["thermal"]["stops"][0]["color"]),
            "pulse_hz": colors["thermal"]["pulse"]["hz"],
            "pulse_from_stage": colors["thermal"]["pulse"]["start_stage"],
        },
        "electrical": {
            "rated_line_A": i_line, "rated_phase_A": i_phase,
            "ratio_thresholds": {k: float(eth[k]) for k in ("over_danger", "over_caution", "under_caution", "under_danger")},
            "rows": rows,
            "status_colors": {s: hexcolor(colors["electrical"][s]["color"]) for s in ELEC_STATUS},
            "status_labels": ELEC_STATUS_KO,
            "short_loop_color": hexcolor(colors["electrical"]["short_loop"]["color"]),
            "i2i1_marks": i2i1_marks,
            "slowmo_factor": float(elec["slowmo"]["factor"]),
        },
    }


# ----------------------------------------------------------------- timeseries
def latest_csv(mode: str) -> str:
    files = sorted(glob.glob(os.path.join(VIZ, "logs", mode, "demo_*.csv")))
    if not files:
        raise FileNotFoundError(f"logs/{mode}/demo_*.csv 가 없다 — tools/record_mode.ps1 -Mode {mode} 먼저")
    return files[-1]


def build_timeseries(mode: str, csv_path: str, th_json: dict) -> dict:
    tm = ThermalModel()
    eth = th_json["electrical"]["ratio_thresholds"]
    i_line = th_json["electrical"]["rated_line_A"]
    part_keys = [p["key"] for p in th_json["thermal"]["parts"]]
    thr = {k: tm.thresholds(k) for k in part_keys}

    t, step, temps, stages = [], [], {k: [] for k in part_keys}, {k: [] for k in part_keys}
    ia, ib, ic, i2i1, vib, zone, status = [], [], [], [], [], [], {"A": [], "B": [], "C": []}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tr = float(row["t_real_s"])
            if t and tr < t[-1]:          # 재생 리셋 이후는 버린다
                break
            t.append(round(tr, 3))
            step.append(row["step"])
            for k in part_keys:
                v = float(row[f"T_{k}"])
                temps[k].append(round(v, 2))
                stages[k].append(stage_of(v, thr[k]))
            a, b, c = float(row["Ia_rms"]), float(row["Ib_rms"]), float(row["Ic_rms"])
            ia.append(round(a, 2)); ib.append(round(b, 2)); ic.append(round(c, 2))
            for ph, val in (("A", a), ("B", b), ("C", c)):
                status[ph].append(elec_status(val / i_line, eth))
            i2i1.append(round(float(row["i2_over_i1"]), 4))
            vib.append(round(float(row["vibration_mms"]), 2))
            zone.append(row["iso_zone"])
    return {
        "mode": mode, "source_csv": os.path.basename(csv_path), "n": len(t), "t_real_s": t, "step": step,
        "temperature_C": temps, "stage": stages,
        "current_rms_A": {"A": ia, "B": ib, "C": ic}, "current_status": status,
        "i2_over_i1": i2i1, "vibration_mms": vib, "iso_zone": zone,
    }


# ----------------------------------------------------------------- scenarios
def lead_time(mode: str, ts: dict, th_json: dict) -> dict:
    """VIGENT 조기 경보 시점과 위험 도달 시점의 차이. 기준은 전부 config 값."""
    t = ts["t_real_s"]
    if mode == "mechanical":
        # 경보 = 어느 부품이든 '주의' 진입, 위험 = 어느 부품이든 '위험' 진입 (부품별 config 임계값)
        def first(stage_name):
            best = None
            for k, arr in ts["stage"].items():
                order = STAGES.index(stage_name)
                for i, s in enumerate(arr):
                    if STAGES.index(s) >= order:
                        if best is None or t[i] < best[0]:
                            best = (t[i], k)
                        break
            return best
        a, d = first("caution"), first("danger")
        return {
            "basis": "온도 — 부품별 주의 임계값 진입(경보) vs 위험 임계값 진입",
            "alarm_t": a[0] if a else None, "alarm_part": a[1] if a else None,
            "danger_t": d[0] if d else None, "danger_part": d[1] if d else None,
            "lead_s": round(d[0] - a[0], 2) if a and d else None,
        }
    # electrical: 경보 = I2/I1 이 4턴 ITSC 목표값 이상, 위험 = 어느 상이든 over_danger
    marks = {m["case"]: m["value"] for m in th_json["electrical"]["i2i1_marks"]}
    alarm_level = marks.get("itsc_4turn")
    a = next((t[i] for i, v in enumerate(ts["i2_over_i1"]) if alarm_level is not None and v >= alarm_level), None)
    d = next((t[i] for i in range(len(t)) if any(ts["current_status"][p][i] == "over_danger" for p in "ABC")), None)
    return {
        "basis": f"전류 — I₂/I₁ ≥ {alarm_level} (4턴 ITSC 수준, 경보) vs 어느 상이든 정격의 {th_json['electrical']['ratio_thresholds']['over_danger']}배 초과(위험)",
        "alarm_t": a, "alarm_level_i2i1": alarm_level, "danger_t": d,
        "lead_s": round(d - a, 2) if a is not None and d is not None else None,
    }


def sim_seconds_between(player: ScenarioPlayer, t_a: float, t_b: float) -> float:
    """벽시계 [t_a, t_b] 구간을 각 단계의 time_scale 로 적분한 시뮬레이션 시간 [s]."""
    total, t0 = 0.0, 0.0
    for s in player.steps:
        d, ts_ = float(s["duration_s"]), float(s.get("time_scale", 60.0))
        lo, hi = max(t_a, t0), min(t_b, t0 + d)
        if hi > lo:
            total += (hi - lo) * ts_
        t0 += d
    return total


def build_scenarios(mode: str, ts: dict, th_json: dict) -> dict:
    player = ScenarioPlayer.for_mode(mode)
    log_dir = os.path.join(VIZ, "logs", mode)
    media_dir = os.path.join(DASH, "public", "media", mode)
    meta_path = os.path.join(log_dir, f"recording_{mode}_full.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    idx_path = os.path.join(media_dir, "clips", "clips_index.json")
    clips = {c["step_id"]: c for c in json.load(open(idx_path, encoding="utf-8"))["clips"]} if os.path.exists(idx_path) else {}
    offset = float(meta.get("video_offset_s", 0.0))

    steps, t0 = [], 0.0
    for i, s in enumerate(player.steps, start=1):
        d = float(s["duration_s"])
        c = clips.get(s["id"], {})
        steps.append({
            "n": i, "id": s["id"], "label": s["label"], "subtitle": s.get("subtitle", ""),
            "source": s.get("source", ""), "t_start": round(t0, 3), "t_end": round(t0 + d, 3),
            "video_start": round(t0 + offset, 3), "video_end": round(t0 + d + offset, 3),
            "electrical_case": s.get("electrical_case", "healthy"), "faults": list(s.get("faults", [])),
            "load": float(s.get("load", 1.0)), "time_scale": float(s.get("time_scale", 60.0)),
            "highlight": bool(s.get("highlight", False)),
            "clip": f"media/{mode}/clips/{c['file']}" if c else None,
        })
        t0 += d
    return {
        "mode": mode,
        "video": f"media/{mode}/{mode}_full.mp4",
        "video_offset_s": offset,
        "video_duration_s": meta.get("duration_s"),
        "recording_meta": os.path.basename(meta_path) if meta else None,
        "total_duration_s": player.total_duration,
        "steps": steps,
        "lead_time": _with_sim(lead_time(mode, ts, th_json), player),
    }


def _with_sim(lt: dict, player: ScenarioPlayer) -> dict:
    if lt.get("alarm_t") is not None and lt.get("danger_t") is not None:
        lt["lead_sim_s"] = round(sim_seconds_between(player, lt["alarm_t"], lt["danger_t"]), 1)
    else:
        lt["lead_sim_s"] = None
    return lt


# ----------------------------------------------------------------- faults
def build_faults(mode: str) -> dict:
    thermal, elec = load("thermal"), load("electrical")
    cm = CurrentModel()
    i_line = cm.motor.rated_current("rated_line_A")
    out = {"mode": mode, "items": []}
    if mode == "mechanical":
        for key, f in thermal["faults"].items():
            out["items"].append({
                "key": key, "label": f["label"], "target": f.get("target"),
                "loss_multiplier": f.get("loss_multiplier"), "load_multiplier": f.get("load_multiplier"),
                "r_amb_multiplier": f.get("r_amb_multiplier"), "extra_loss_W": f.get("extra_loss_W"),
                "vibration_mms": f.get("vibration_mms"),
            })
    else:
        import numpy as np
        t_win = np.arange(0, 4 / cm.f0, 1 / (cm.f0 * 256))
        for key, c in elec["cases"].items():
            st = cm.analyze(t_win, cm.waveform(t_win, key, "rated_line_A"), key, "rated_line_A")
            out["items"].append({
                "key": key, "label": c["label"], "phase_scale": list(c["phase_scale"]),
                "load": float(c.get("load", 1.0)), "target_i2i1": c.get("target_i2i1"),
                "rms_A": [round(float(x), 1) for x in st.rms_A],
                "ratio": [round(float(x) / i_line, 3) for x in st.rms_A],
                "status": list(st.status), "i2_over_i1": round(float(st.i2_over_i1), 4),
            })
    return out


# ----------------------------------------------------------------- main
def _fill_subtitles(sc: dict, values: dict) -> None:
    """시나리오 자막의 {변수}(정격 전류, 장면 끝 R상 전류 등)를 해설 변수로 채운다 — 이 export 는 M5 기준 (D-1 ②)."""
    from engine.scenario_player import fill_vars
    for st in sc["steps"]:
        st["subtitle"] = fill_vars(st.get("subtitle", ""), values.get(st["id"]))


def export(mode: str) -> dict:
    out_dir = os.path.join(DASH, "public", "data", mode)
    os.makedirs(out_dir, exist_ok=True)
    th = build_thresholds(mode)
    ts = build_timeseries(mode, latest_csv(mode), th)
    sc = build_scenarios(mode, ts, th)
    fa = build_faults(mode)
    files = [("thresholds", th), ("timeseries", ts), ("scenarios", sc), ("faults", fa)]
    if mode == "mechanical":
        # 실시간 해설 대시보드용 확장 (손실열·이벤트·해설 치환 변수). 전기 모드는 그대로.
        sys.path.insert(0, HERE)
        from export_mechanical_extras import apply_extras
        events, values = apply_extras(th, ts, sc, fa)
        _fill_subtitles(sc, values)
        files += [("events", {"mode": mode, "n": len(events), "events": events}),
                  ("narration_values", {"mode": mode, "scenes": values})]
        rc = ts["replay_check"]
        print(f"[{mode}] 재실행 검증: 경계 밖 최대 {max(rc['max_err_inner_C'].values()):.2f} °C "
              f"(허용 {rc['method'].split('tolerance_C=')[1]}) → {'PASS' if rc['pass'] else 'FAIL'}, 이벤트 {len(events)}개")
    else:
        # 전기 실시간 해설 대시보드용 확장 (재계산 비율·위상·이벤트·변수·매트릭스·파형). 기계 모드는 그대로.
        sys.path.insert(0, HERE)
        from export_electrical_extras import apply_extras as apply_elec
        events, values, waves = apply_elec(th, ts, sc, fa)
        _fill_subtitles(sc, values)
        files += [("events", {"mode": mode, "n": len(events), "events": events}),
                  ("narration_values", {"mode": mode, "scenes": values}), ("waveforms", waves)]
        rc = ts["recompute_check"]
        print(f"[{mode}] 엔진 재계산 검증: RMS 최대 {rc['max_rms_diff_A']} A, I₂/I₁ 최대 {rc['max_i2i1_diff']} "
              f"(로그 RMS 로 계산 {rc['max_i2i1_diff_from_log_rms']}) → {'PASS' if rc['pass'] else 'FAIL'}, 이벤트 {len(events)}개")
    for name, obj in files:
        with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    lt = sc["lead_time"]
    print(f"[{mode}] {ts['n']} 샘플, {len(sc['steps'])} 챕터, 오프셋 {sc['video_offset_s']} s, "
          f"리드 타임 {lt.get('lead_s')} s (경보 {lt.get('alarm_t')} → 위험 {lt.get('danger_t')})  → {out_dir}")
    return {"thresholds": th, "timeseries": ts, "scenarios": sc, "faults": fa}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=("mechanical", "electrical", "all"))
    a = ap.parse_args()
    for m in (("mechanical", "electrical") if a.mode == "all" else (a.mode,)):
        export(m)
