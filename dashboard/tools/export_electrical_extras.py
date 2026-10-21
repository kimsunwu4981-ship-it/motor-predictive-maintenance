# -*- coding: utf-8 -*-
"""export_electrical_extras.py — 전기 대시보드(실시간 해설)용 추가 데이터. export_dashboard_data.py 가 호출한다.

  timeseries.json  + ratio(정격 대비), phase_rms_A(상전류), phasor_deg(기본파 위상), case, recompute_check
  events.json        로그에서 자동 추출한 사건 (상별 상태 변화, I₂/I₁ 눈금 통과, 균형만 무너짐, 단락 루프 표시, 장면 전환)
  narration_values.json  장면별 해설 치환 변수 — 문구는 content/electrical/narration.yaml, 숫자는 여기서
  waveforms.json     케이스별 한 주기 순시 전류 (pu) — 회로도 입자·슬로모션 파형용
  thresholds.json  + electrical.slowmo_x, phase_colors, matrix(장면별 좌표)

로그에는 상별 선전류 RMS 와 I₂/I₁ 만 있다. 위상·상전류·정격 대비 비율은 **엔진(engine/current_model.py)으로
재계산**한다. 전류 모델은 해석식·결정론적(케이스별 크기·위상만의 함수, 시간·온도 무관)이라 재계산값이 곧 정확값이고,
재계산 RMS 가 로그와 다르면 config 가 바뀐 것이다 (E0 실측: 최대 0.05 A).

⚠ 전압은 모델 입력이 아니다. 장면 5(공급전압 불평형)는 전류 불평형을 직접 넣은 것이라 전압 숫자는 없다.
⚠ ITSC 는 목표 I₂/I₁ 을 A상 크기 불평형으로 재현한 등가 표현이다. 단락 루프 순환전류는 모델에 없다.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)

import yaml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel, phasors_from_waveform, symmetrical_components  # noqa: E402

PH = ("A", "B", "C")
_LAB = dict(load("electrical").get("phase_labels") or {"A": "A", "B": "B", "C": "C"})   # 표시 이름 (R/S/T) — 내부 키는 A/B/C
PH_KO = {p: f"{_LAB[p]}상" for p in PH} | {"ABC": "세 상"}
STATUS = ("under_danger", "under_caution", "normal", "over_caution", "over_danger")
STATUS_KO = {"over_danger": "위험 과전류", "over_caution": "주의 과전류", "normal": "정상",
             "under_caution": "주의 저전류", "under_danger": "위험 저전류(결상 의심)"}
RMS_TOL_A = 0.1            # 재계산 RMS 허용 오차 (로그는 소수 1자리)
I2I1_TOL = 0.002           # 로그 RMS + config 위상으로 계산한 I₂/I₁ 과 기록값의 허용 오차
BALANCE_ONLY_FACTOR = 5.0  # 세 상 모두 정상인데 I₂/I₁ 이 정상 목표값의 이 배수를 넘으면 "균형만 무너짐" 사건 (장면 5 = 9.9배)
WAVE_SAMPLES = 64
CONTENT_DIR = os.path.join(DASH, "public", "content", "electrical")


def _narration_cfg() -> dict:
    p = os.path.join(CONTENT_DIR, "narration.yaml")
    if not os.path.exists(p):
        return {"scenes": {}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"scenes": {}}


# ----------------------------------------------------------------- 엔진 재계산
ENGINE = {"tm": None, "cm": None}      # export_dashboard_data 가 --source fleet 이면 M1 라이브러리 엔진(LUT)을 주입한다 (D 후속 2, 2026-10-21)


class CaseTable:
    """케이스별 정확값 (엔진 1회 계산, 캐시)."""

    def __init__(self):
        self.cm = ENGINE["cm"] or CurrentModel()
        self.i_line = self.cm.motor.rated_current("rated_line_A")
        self.i_phase = self.cm.motor.rated_current("rated_phase_A")
        self.f0 = self.cm.f0
        self.fs = self.f0 * 256
        self.rows: dict[str, dict] = {}
        for case in self.cm.cases:
            t = np.arange(0, 4 / self.f0, 1 / self.fs)
            I = self.cm.waveform(t, case, "rated_line_A")
            st = self.cm.analyze(t, I, case, "rated_line_A")
            n = int(round(self.fs / self.f0))
            ph = [phasors_from_waveform(I[k][-n:], self.fs, self.f0) for k in range(3)]
            one = np.linspace(0, 1 / self.f0, WAVE_SAMPLES, endpoint=False)
            w = self.cm.waveform(one, case, "rated_line_A") / (math.sqrt(2) * self.i_line)
            self.rows[case] = {
                "rms": [float(x) for x in st.rms_A],
                "ratio": [float(x) for x in st.ratio],
                "status": list(st.status),
                "phase_rms": [float(x) * self.i_phase for x in st.ratio],   # Δ결선: 권선 판정과 같은 비율 × 상전류 정격
                "deg": [float(math.degrees(np.angle(p))) for p in ph],
                "i2i1": float(st.i2_over_i1),
                "wave_pu": [[round(float(v), 4) for v in w[k]] for k in range(3)],
                "wave_deg": [round(float(d), 2) for d in (one * self.f0 * 360.0)],
                "short_loop": self.cm.short_loop(case),
                "load": float(self.cm.cases[case].get("load", 1.0)),
                "phase_shift_deg": [float(x) for x in self.cm.cases[case]["phase_shift_deg"]],
            }


def recompute(ts: dict, sc: dict, tab: CaseTable) -> dict:
    """로그 행마다 케이스 정확값을 붙이고 로그와 대조한다."""
    t = ts["t_real_s"]
    case_of_step = {s["id"]: s["electrical_case"] for s in sc["steps"]}
    ratio = {p: [] for p in PH}
    prms = {p: [] for p in PH}
    deg = {p: [] for p in PH}
    cases = []
    max_rms, max_i2 = 0.0, 0.0
    max_i2_sym = 0.0
    for i, step in enumerate(ts["step"]):
        # 시나리오가 끝난 뒤의 행(step=manual)은 마지막 케이스를 이어 쓴다 (로그 끝 5 s 여유분)
        case = case_of_step.get(step) or (cases[-1] if cases else "healthy")
        r = tab.rows[case]
        cases.append(case)
        for k, p in enumerate(PH):
            ratio[p].append(round(r["ratio"][k], 4))
            prms[p].append(round(r["phase_rms"][k], 2))
            deg[p].append(round(r["deg"][k], 1))
            max_rms = max(max_rms, abs(r["rms"][k] - ts["current_rms_A"][p][i]))
        max_i2 = max(max_i2, abs(r["i2i1"] - ts["i2_over_i1"][i]))
        # 로그의 RMS 크기 + config 위상으로 대칭좌표 계산 → 기록된 I₂/I₁ 과 대조 (로그 자체의 일관성)
        ph = [ts["current_rms_A"][p][i] * np.exp(1j * math.radians(r["deg"][k])) for k, p in enumerate(PH)]
        i1, i2, _ = symmetrical_components(*ph)
        v = abs(i2) / abs(i1) if abs(i1) > 1e-9 else 0.0
        max_i2_sym = max(max_i2_sym, abs(v - ts["i2_over_i1"][i]))
    return {
        "ratio": ratio, "phase_rms_A": prms, "phasor_deg": deg, "case": cases,
        "recompute_check": {
            "method": f"engine CurrentModel per case, rms_tol_A={RMS_TOL_A}, i2i1_tol={I2I1_TOL}",
            "max_rms_diff_A": round(float(max_rms), 3), "max_i2i1_diff": round(float(max_i2), 4),
            "max_i2i1_diff_from_log_rms": round(float(max_i2_sym), 4),
            # 로그 RMS 는 0.1 A 로 반올림돼 있다 → 그 값으로 다시 계산한 I₂/I₁ 의 오차 한계 ≈ 0.05 A / I₁ (M1 4.7 A 면 0.011; 22 kW 43 A 면 0.001). 허용은 이 반올림 한계를 더한다 (D 후속 2)
            "log_rms_rounding_bound": round(0.05 / max(float(tab.i_line), 1e-9), 4),
            "pass": bool(max_rms <= RMS_TOL_A and max_i2 <= I2I1_TOL and max_i2_sym <= I2I1_TOL * 2 + 0.05 / max(float(tab.i_line), 1e-9)),
        },
    }


# ----------------------------------------------------------------- 이벤트 추출
def _boundary_A(frm: str, to: str, eth: dict, i_line: float) -> float:
    """넘은 경계의 암페어. 오를 때는 새 상태의 하한, 내릴 때는 옛 상태의 하한 (정상 복귀는 정상 구간의 해당 경계)."""
    up = STATUS.index(to) > STATUS.index(frm)
    key = to if up else frm
    ratio = {"over_danger": eth["over_danger"], "over_caution": eth["over_caution"],
             "under_caution": eth["under_caution"], "under_danger": eth["under_danger"]}.get(key)
    if ratio is None:   # normal 로/에서: 어느 쪽 경계인지
        other = frm if up else to
        ratio = eth["under_caution"] if other in ("under_caution", "under_danger") else eth["over_caution"]
    return round(ratio * i_line, 1)


def extract_events(ts: dict, th: dict, sc: dict, tab: CaseTable, focus: dict) -> list[dict]:
    t = ts["t_real_s"]
    eth = th["electrical"]["ratio_thresholds"]
    i_line = th["electrical"]["rated_line_A"]
    marks = {m["case"]: m["value"] for m in th["electrical"]["i2i1_marks"]}
    normal_level = marks.get("healthy", 0.0)
    events: list[dict] = []

    def scene_at(tt: float) -> dict:
        return next((s for s in sc["steps"] if tt < s["t_end"]), sc["steps"][-1])

    by_id = {s["id"]: s for s in sc["steps"]}

    def scene_of_row(i: int) -> dict:
        # 케이스 전환이 장면 경계보다 한 로그 스텝 먼저 찍히므로(실측 119.918 s vs 120.0 s) 행의 step 으로 장면을 정한다
        return by_id.get(ts["step"][i]) or scene_at(t[i])

    def prio(sn: dict, phase: str | None, is_i2i1: bool) -> int:
        f = focus.get(sn["id"], {})
        fp = set(f.get("focus_phases") or [])
        if phase == "ABC":
            return 1 if fp >= {"A", "B", "C"} else 2
        if phase in fp or (is_i2i1 and f.get("focus_i2i1")):
            return 1
        if phase in PH:
            return 2
        return 3

    for s in sc["steps"]:
        events.append({"type": "scene", "t": s["t_start"], "scene": s["n"], "scene_id": s["id"], "label": s["label"],
                       "case": s["electrical_case"], "slowmo_x": th["electrical"]["slowmo_x"], "priority": 0, "tpl": "default"})

    st = ts["current_status"]
    for i in range(1, len(t)):
        changed = [p for p in PH if st[p][i] != st[p][i - 1]]
        if not changed:
            continue
        sn = scene_of_row(i)
        pct = {p: round(ts["current_rms_A"][p][i] / i_line * 100) for p in PH}
        rms = {p: ts["current_rms_A"][p][i] for p in PH}
        # 바뀐 뒤 세 상이 같은 상태이고 둘 이상이 바뀌었으면 "세 상" 사건 하나로 (과부하·무부하·정상 복귀)
        same_to = len(changed) >= 2 and len({st[p][i] for p in PH}) == 1
        groups = [("ABC", list(PH))] if same_to else [(p, [p]) for p in changed]
        rng = (lambda d: f"{min(d.values())}" if min(d.values()) == max(d.values()) else f"{min(d.values())}~{max(d.values())}")
        for phase, members in groups:
            p0 = members[0]
            frm, to = st[p0][i - 1], st[p0][i]
            others = [q for q in PH if q not in members]
            others_over = bool(others) and all(st[q][i] in ("over_caution", "over_danger") for q in others)
            if phase == "ABC":
                tpl = f"all_{to}"
            elif to == "under_danger" and others_over:
                tpl = "phase_loss"
            elif to == "normal":
                tpl = "normal_return"
            else:
                tpl = to
            ev = {"type": "status", "t": t[i], "scene": sn["n"], "phase": phase, "phase_label": PH_KO[phase],
                  "from": frm, "to": to, "from_ko": STATUS_KO[frm], "to_ko": STATUS_KO[to],
                  "rms_A": rms[p0], "pct": pct[p0], "threshold_A": _boundary_A(frm, to, eth, i_line),
                  "rms_range": rng(rms), "pct_range": rng(pct),
                  "others": "·".join(_LAB[q] for q in others), "others_rms_A": rms[others[0]] if others else None,
                  "others_pct": pct[others[0]] if others else None,
                  "is_focus": phase in (focus.get(sn["id"], {}).get("focus_phases") or []) or phase == "ABC",
                  "priority": prio(sn, phase, False), "tpl": tpl}
            events.append(ev)

    # I₂/I₁ 눈금 통과 (config 의 target_i2i1 눈금: 4턴·12턴)
    z = ts["i2_over_i1"]
    for case, level in marks.items():
        if case == "healthy":
            continue
        for i in range(1, len(t)):
            a, b = z[i - 1], z[i]
            if (a < level <= b) or (b < level <= a):
                up = b >= level
                sn = scene_of_row(i)
                events.append({"type": "i2i1", "t": t[i], "scene": sn["n"], "mark": case, "level": level,
                               "mark_label": next(m["label"] for m in th["electrical"]["i2i1_marks"] if m["case"] == case),
                               "value": b, "prev": a, "x_normal": round(b / normal_level, 1) if normal_level else None,
                               "up": up, "priority": prio(sn, None, True), "tpl": "up" if up else "down"})

    # 균형만 무너짐: 세 상 모두 정상인데 I₂/I₁ 이 정상 목표값의 BALANCE_ONLY_FACTOR 배를 넘는 순간
    on = False
    for i in range(len(t)):
        all_normal = all(st[p][i] == "normal" for p in PH)
        now = all_normal and normal_level > 0 and z[i] > normal_level * BALANCE_ONLY_FACTOR
        if now and not on:
            sn = scene_of_row(i)
            events.append({"type": "balance_only", "t": t[i], "scene": sn["n"], "value": z[i],
                           "x_normal": round(z[i] / normal_level, 1), "normal_level": normal_level,
                           "priority": prio(sn, None, True), "tpl": "default"})
        on = now

    # 단락 루프 표시 (케이스에 short_loop 가 있는 구간) — 시각적 표시임을 자막이 말한다
    prev = None
    for i, case in enumerate(ts["case"]):
        sl = tab.rows[case]["short_loop"]
        cur = sl["turns"] if sl else None
        if cur != prev:
            sn = scene_of_row(i)
            if cur is not None:
                events.append({"type": "short_loop_on", "t": t[i], "scene": sn["n"], "turns": cur, "phase": "A",
                               "phase_label": PH_KO["A"], "priority": 3, "tpl": "default"})
            elif prev is not None:
                events.append({"type": "short_loop_off", "t": t[i], "scene": sn["n"], "priority": 3, "tpl": "default"})
            prev = cur

    # 한 스텝에 눈금을 여럿 지나면(0.269→0) 오를 때는 가장 높은 눈금, 내릴 때는 가장 낮은 눈금만 남긴다
    keep = {}
    for e in events:
        if e["type"] != "i2i1":
            continue
        k = (e["t"], e["up"])
        if k not in keep or (e["level"] > keep[k]["level"] if e["up"] else e["level"] < keep[k]["level"]):
            keep[k] = e
    events = [e for e in events if e["type"] != "i2i1" or keep[(e["t"], e["up"])] is e]
    events.sort(key=lambda e: (e["t"], e["priority"]))
    for n, e in enumerate(events):
        e["id"] = n
    return events


# ----------------------------------------------------------------- 해설 치환 변수
def narration_values(ts: dict, th: dict, sc: dict, tab: CaseTable) -> dict:
    t = ts["t_real_s"]
    el = th["electrical"]
    eth = el["ratio_thresholds"]
    i_line, i_phase = el["rated_line_A"], el["rated_phase_A"]
    marks = {m["case"]: m["value"] for m in el["i2i1_marks"]}
    lt = sc["lead_time"]
    out = {}

    def idx_at(tt: float) -> int:
        return max(j for j, x in enumerate(t) if x <= tt)

    common = {
        "rated_line_A": i_line, "rated_phase_A": i_phase,
        "line_over_danger_A": round(eth["over_danger"] * i_line, 1), "line_over_caution_A": round(eth["over_caution"] * i_line, 1),
        "line_under_caution_A": round(eth["under_caution"] * i_line, 1), "line_under_danger_A": round(eth["under_danger"] * i_line, 1),
        "phase_over_danger_A": round(eth["over_danger"] * i_phase, 1), "phase_over_caution_A": round(eth["over_caution"] * i_phase, 1),
        "phase_under_caution_A": round(eth["under_caution"] * i_phase, 1), "phase_under_danger_A": round(eth["under_danger"] * i_phase, 1),
        "over_danger_pct": round(eth["over_danger"] * 100), "over_caution_pct": round(eth["over_caution"] * 100),
        "under_caution_pct": round(eth["under_caution"] * 100), "under_danger_pct": round(eth["under_danger"] * 100),
        "i2i1_normal": marks.get("healthy"), "i2i1_4turn": marks.get("itsc_4turn"), "i2i1_12turn": marks.get("itsc_12turn"),
        "slowmo_x": el["slowmo_x"], "lead_s": lt.get("lead_s"), "lead_alarm_t": lt.get("alarm_t"), "lead_danger_t": lt.get("danger_t"),
        "line_phase_factor": round(i_line / i_phase, 3),
        "ph_a": _LAB["A"], "ph_b": _LAB["B"], "ph_c": _LAB["C"],
    }
    for s in sc["steps"]:
        i_end, i_start = idx_at(s["t_end"] - 0.3), idx_at(s["t_start"] + 0.05)
        case = s["electrical_case"]
        r = tab.rows[case]
        v = dict(common)
        v.update({"scene": s["n"], "scene_label": s["label"], "case": case, "t_start": s["t_start"], "t_end": s["t_end"],
                  "load_pct": round(s["load"] * 100), "short_turns": (r["short_loop"] or {}).get("turns"),
                  "phase_shift_a_deg": r["phase_shift_deg"][0]})
        for k, p in enumerate(PH):
            lp = p.lower()
            for tag, i in (("end", i_end), ("start", i_start)):
                rms = ts["current_rms_A"][p][i]
                v[f"{lp}_rms_{tag}"] = rms
                v[f"{lp}_pct_{tag}"] = round(rms / i_line * 100)
                v[f"{lp}_status_{tag}"] = STATUS_KO[ts["current_status"][p][i]]
                v[f"{lp}_phase_rms_{tag}"] = round(rms / i_line * i_phase, 1)
        v["i2i1_end"], v["i2i1_start"] = ts["i2_over_i1"][i_end], ts["i2_over_i1"][i_start]
        nl = marks.get("healthy") or 0.0
        v["i2i1_x_normal_end"] = round(ts["i2_over_i1"][i_end] / nl, 1) if nl else None
        v["max_pct_end"] = max(v[f"{p.lower()}_pct_end"] for p in PH)
        v["min_pct_end"] = min(v[f"{p.lower()}_pct_end"] for p in PH)
        v["bc_rms_end"] = ts["current_rms_A"]["B"][i_end]
        v["bc_pct_end"] = round(ts["current_rms_A"]["B"][i_end] / i_line * 100)
        out[s["id"]] = v
    return out


# ----------------------------------------------------------------- 판별 매트릭스 좌표
def matrix_points(ts: dict, sc: dict, th: dict, cfg: dict) -> list[dict]:
    """가로 = I₂/I₁(균형), 세로 = 세 상 중 가장 큰 정격 대비 비율(크기). 장면 종료 시점 값, 로그에서."""
    t = ts["t_real_s"]
    i_line = th["electrical"]["rated_line_A"]
    pts = []
    for s in sc["steps"]:
        i = max(j for j, x in enumerate(t) if x <= s["t_end"] - 0.3)
        ratios = [ts["current_rms_A"][p][i] / i_line for p in PH]
        scene = (cfg.get("scenes") or {}).get(s["id"], {})
        pts.append({"scene": s["n"], "id": s["id"], "label": scene.get("matrix_label") or s["label"],
                    "x_i2i1": ts["i2_over_i1"][i], "y_ratio_max": round(max(ratios), 3), "y_ratio_mean": round(sum(ratios) / 3, 3),
                    "y_ratio_min": round(min(ratios), 3)})
    return pts


# ----------------------------------------------------------------- 진입점
def apply_extras(th: dict, ts: dict, sc: dict, faults: dict) -> tuple[list[dict], dict, dict]:
    elec, colors = load("electrical"), load("colors")
    tab = CaseTable()
    th["electrical"]["phase_labels"] = _LAB
    th["electrical"]["slowmo_x"] = int(round(1.0 / float(elec["slowmo"]["factor"])))
    th["electrical"]["slowmo_label"] = elec["slowmo"]["label"]
    th["electrical"]["phase_colors"] = {k: [float(x) for x in (v["color"] if isinstance(v, dict) else v)] for k, v in (colors.get("phases") or {}).items()}
    th["electrical"]["status_rgb"] = {k: [float(x) for x in colors["electrical"][k]["color"]] for k in STATUS}
    th["electrical"]["short_loop"] = {"rgb": [float(x) for x in colors["electrical"]["short_loop"]["color"]],
                                      "pulse_hz": float(colors["electrical"]["short_loop"]["pulse_hz"])}
    th["electrical"]["model_note"] = ("전류는 해석식 3상 모델 (FEM·실측 아님). 턴간 단락은 목표 I₂/I₁ 을 크기 불평형으로 재현한 등가 표현이며 "
                                     "단락 루프 순환전류는 모델에 없다. 공급전압은 모델 입력이 아니다.")
    extras = recompute(ts, sc, tab)
    ts.update(extras)
    cfg = _narration_cfg()
    focus = {sid: {"focus_phases": (s or {}).get("focus_phases"), "focus_i2i1": (s or {}).get("focus_i2i1", False)}
             for sid, s in (cfg.get("scenes") or {}).items()}
    events = extract_events(ts, th, sc, tab, focus)
    values = narration_values(ts, th, sc, tab)
    th["electrical"]["matrix"] = matrix_points(ts, sc, th, cfg)
    waves = {"mode": "electrical", "f0_Hz": tab.f0, "samples": WAVE_SAMPLES, "unit": "pu of sqrt2*rated_line_A",
             "deg": tab.rows["healthy"]["wave_deg"],
             "cases": {case: {"A": r["wave_pu"][0], "B": r["wave_pu"][1], "C": r["wave_pu"][2], "deg": r["deg"], "ratio": r["ratio"]}
                       for case, r in tab.rows.items()}}
    return events, values, waves
