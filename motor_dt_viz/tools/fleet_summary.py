# -*- coding: utf-8 -*-
"""fleet_summary.py — logs/fleet 의 5종 결과를 비교표(docs/fleet_summary.md)로 만든다 (TASK_다중모터 §6).

  python tools/fleet_summary.py

표: 모터별 정상 수렴 온도, 결함 장면별 경고·위험 도달 시각(재생 초 / 시뮬레이션 분), 리드 타임(진동 경고 → 온도 경고),
전기 장면별 상태·원인. 물리적으로 이상한 결과(작은 모터가 큰 모터보다 느리게 식는 등)는 자동 검사해 표시한다.
"""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, VIZ)

from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

FLEET = os.path.join(VIZ, "logs", "fleet")
RANK = {"SAFE": 0, "WARN": 1, "DANGER": 2}


def read(mid, mode, name):
    return list(csv.DictReader(open(os.path.join(FLEET, mid, mode, name), encoding="utf-8", newline="")))


def fmt_t(t, scale):
    return f"{t:.1f} s ({t * scale / 60:.1f} 분)" if scale else f"{t:.1f} s"


def main():
    ids = ml.list_ids()
    out = ["# 5종 모터 배치 시뮬레이션 비교표 (엔진 기반, `tools/run_fleet.py`)", "",
           "로그: `logs/fleet/<id>/<mode>/demo_fleet.csv`(데모와 같은 컬럼), `status_fleet.csv`(판정 엔진 결과). 시나리오·결함 파라미터는 공통,",
           "결과 온도·전류는 모터별 config(`config/motors/<id>.yaml` + M5 기준 열회로 스케일)로 달라진다. 시각은 **재생 시간(s)** 이고 괄호는",
           "그 장면의 배속을 곱한 **시뮬레이션 시간(분)** 이다. 판정은 히스테리시스 5 %·지속 3 s 가 적용된 값이다.", ""]
    reg_p = os.path.join(FLEET, "regression_M5.json")
    if os.path.exists(reg_p):
        reg = json.load(open(reg_p, encoding="utf-8"))
        out += ["## M5 회귀 (엔진 로그 ↔ 기존 Isaac 로그, 장면 종료 시점)", "",
                "| 모드 | 최대 차이 | 허용 | 결과 | 대조 로그 |", "|---|---|---|---|---|"]
        for mode, r in reg.items():
            if "skipped" in r:
                out.append(f"| {mode} | - | - | 건너뜀 | {r['skipped']} |")
            else:
                out.append(f"| {mode} | {r['max_diff']} | {r['tolerance']} | {'PASS' if r['pass'] else 'FAIL'} | {r['isaac_log']} |")
        out.append("")

    # ---- 정상 수렴 온도
    out += ["## 정상 운전 수렴 온도 (정격 100 % 연속, 엔진 정상상태 해, °C)", "",
            "| ID | 모터 | 권선 | 코어 | 로터 | 축 | DE 베어링 | 프레임 | 진동 규격 (경고/위험 mm/s) |", "|---|---|---|---|---|---|---|---|---|"]
    for mid in ids:
        m = ml.load_motor(mid); ss = ThermalModel(ml.thermal_cfg(m)).steady_state(1.0, [])
        v = m.vib_thresholds
        out.append(f"| {mid} | {m.name} | {ss['winding']:.1f} | {ss['stator_core']:.1f} | {ss['rotor']:.1f} | {ss['shaft']:.1f} | {ss['bearing_de']:.1f} | {ss['frame']:.1f} | {v['standard'].split(' (')[0]} ({v['watch_mms']:g}/{v['act_mms']:g}) |")
    out.append("")

    # ---- 기계 결함 장면
    player = ScenarioPlayer.for_mode("mechanical")
    tcfg = load("thresholds")["temperature"]
    out += ["## 기계 결함 장면별 도달 시각 (status_fleet.csv · demo_fleet.csv)", "",
            "장면은 이어서 재생되므로 `0.0 s` 는 이전 장면에서 넘어온 상태다. '온도 위험' 은 온도 신호만으로 위험에 닿은 시각,",
            "'리드 타임' 은 원시값 기준 진동 경고(규격 watch 이상) → 온도 경고(부품 안전 상한 이상) 간격이다 (판정 상태에는 진동 지속 3 s 가 더해진다).", "",
            "| 장면 | ID | 첫 경고 | 첫 위험 | 원인(위험 시점) | 온도 위험 | 장면 끝 상태 (원인 값) | 리드 타임 진동→온도 |", "|---|---|---|---|---|---|---|---|"]
    flags = []
    cooldown_rate = {}

    def cause(r):
        c = r["cause_signal"] if r["cause_component"] in ("-", "") else f"{r['cause_signal']}/{r['cause_component']}"
        return f"{c} {float(r['value']):.1f}" if r["cause_signal"] != "-" else "-"

    def temp_warn_raw(d):
        for k in ("winding", "stator_core", "rotor", "shaft", "bearing_de", "bearing_nde", "endshield_de", "endshield_nde", "frame"):
            cls = tcfg["component_class"].get(k, "default")
            if float(d["T_" + k]) >= float(tcfg[cls]["safe_below"]):
                return True
        return False

    for s in player.steps:
        t0 = sum(float(x["duration_s"]) for x in player.steps[:player.steps.index(s)]); t1 = t0 + float(s["duration_s"]); sc = float(s.get("time_scale", 60))
        for mid in ids:
            m = ml.load_motor(mid)
            rows = [r for r in read(mid, "mechanical", "status_fleet.csv") if t0 <= float(r["t_real_s"]) < t1]
            demo = [r for r in read(mid, "mechanical", "demo_fleet.csv") if t0 <= float(r["t_real_s"]) < t1]
            warn = next((r for r in rows if RANK[r["status"]] >= 1), None)
            dang = next((r for r in rows if RANK[r["status"]] >= 2), None)
            tdang = next((r for r in rows if RANK[r["temperature"]] >= 2), None)
            vib_w = next((r for r in demo if float(r["vibration_mms"]) >= float(m.vib_thresholds["watch_mms"])), None)
            tmp_w = next((r for r in demo if temp_warn_raw(r)), None)
            if vib_w and tmp_w:
                lead = f"{float(tmp_w['t_real_s']) - float(vib_w['t_real_s']):.2f} s" if float(tmp_w["t_real_s"]) > t0 + 1e-6 else "이전 장면부터 온도 경고"
            else:
                lead = "온도 경고 없음" if vib_w else "-"
            end = rows[-1]
            out.append(f"| {s['label']} | {mid} | {fmt_t(float(warn['t_real_s']) - t0, sc) if warn else '없음'} | "
                       f"{fmt_t(float(dang['t_real_s']) - t0, sc) if dang else '없음'} | {cause(dang) if dang else '-'} | "
                       f"{fmt_t(float(tdang['t_real_s']) - t0, sc) if tdang else '없음'} | {end['status']} ({cause(end)}) | {lead} |")
            if s["id"] == "cooldown" and demo:
                d0, d1 = float(demo[0]["T_winding"]), float(demo[-1]["T_winding"])
                cooldown_rate[mid] = (d0 - d1) / max(d0 - 25.0, 1e-6)
        out.append("| | | | | | | | |")
    # 물리 타당성 검사
    if cooldown_rate:
        ids_sorted = sorted(cooldown_rate, key=lambda k: ml.load_motor(k).rated_power_kw)
        out += ["", "냉각 장면(7) 권선 초과온도 감소 비율 (큰 값 = 빨리 식음): " + ", ".join(f"{k} {cooldown_rate[k]:.2f}" for k in ids_sorted)]
        for a, b in zip(ids_sorted, ids_sorted[1:]):
            if cooldown_rate[a] < cooldown_rate[b] - 1e-6:
                flags.append(f"{a}({ml.load_motor(a).rated_power_kw} kW)가 {b}({ml.load_motor(b).rated_power_kw} kW)보다 느리게 식는다 — 시정수 스케일 확인 필요")
    # 결함 반응 순서: 큰 모터가 온도 위험에 더 빨리 닿아야 한다 (베어링 장면)
    bear = {}
    t0 = sum(float(x["duration_s"]) for x in player.steps[:[x["id"] for x in player.steps].index("bearing_fault")])
    for mid in ids:
        rows = [r for r in read(mid, "mechanical", "status_fleet.csv") if float(r["t_real_s"]) >= t0]
        td = next((float(r["t_real_s"]) for r in rows if RANK[r["temperature"]] >= 2), None)
        bear[mid] = td
    order = [k for k in sorted(bear, key=lambda k: ml.load_motor(k).rated_power_kw)]
    for a, b in zip(order, order[1:]):
        if bear[a] is not None and bear[b] is not None and bear[a] < bear[b] - 1e-6:
            flags.append(f"베어링 장면에서 {a}가 {b}보다 먼저 온도 위험에 닿는다 — 결함 스케일 확인 필요")
    # ---- 전기
    pe = ScenarioPlayer.for_mode("electrical")
    out += ["", "## 전기 장면별 상태 (장면 끝, status_fleet.csv)", "",
            "| 장면 | " + " | ".join(ids) + " |", "|---|" + "---|" * len(ids)]
    for s in pe.steps:
        t0 = sum(float(x["duration_s"]) for x in pe.steps[:pe.steps.index(s)]); t1 = t0 + float(s["duration_s"])
        cells = []
        for mid in ids:
            rows = [r for r in read(mid, "electrical", "status_fleet.csv") if t0 <= float(r["t_real_s"]) < t1]
            e = rows[-1]
            cells.append(f"{e['status']} ({cause(e)})")
        out.append(f"| {s['label']} | " + " | ".join(cells) + " |")
    out += ["", "전기 결과가 5종에서 같은 등급으로 나오는 것은 정상이다: 전류 모델은 정격 대비 비율(케이스 배율)로 정의되고 판정도 비율 기준이라 모터가 바뀌면 암페어만 바뀐다.",
            "I₂/I₁ 목표값(0.006/0.104/0.269)은 M5 기준 해석식 등가값을 전 모터에 적용한 것이다 (§4.3)."]
    out += ["", "## 물리 타당성 자동 검사", ""]
    out += [f"- ⚠ {f}" for f in flags] or ["- 이상 없음 (작은 모터일수록 빨리 식고, 결함 도달은 느리다)"]
    # M1 위험 미도달 등 눈에 띄는 점
    notes = []
    for mid in ids:
        rows = read(mid, "mechanical", "status_fleet.csv")
        if not any(r["temperature"] == "DANGER" for r in rows):
            notes.append(f"{mid}: 기계 시나리오 전체에서 **온도**만으로는 '위험'에 닿지 않는다 — 위험 판정은 진동(시나리오 공통 상수 4.8 mm/s)이 만든다 "
                         f"(결함 손실이 출력에 비례해 작음, docs/thermal_scaling.md). 작은 모터의 결함 배율을 따로 둘지는 사용자 결정 사항")
    notes.append("진동값(결함별 상수 mm/s)은 5종 공통이다 — 모터별로 다른 것은 규격(경고 1.8 vs 1.4)뿐. 실측 연결 전까지는 진동 기반 판정이 모터 크기에 거의 무관하다.")
    out += [f"- {n}" for n in notes]
    p = os.path.join(VIZ, "docs", "fleet_summary.md")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print("→", p)


if __name__ == "__main__":
    main()
