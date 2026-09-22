# -*- coding: utf-8 -*-
"""기계 실시간 해설 대시보드 데이터 검증 — 이벤트 시각·수치가 로그와 일치하고, 손실열이 config 와 맞고,
엔진 재실행 온도가 허용 오차 안이며, 해설 PDF 의 숫자가 로그와 같은지 확인한다."""
from __future__ import annotations

import csv
import glob
import io
import json
import os
import re
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)
from engine.config_loader import load  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

DATA = os.path.join(DASH, "public", "data", "mechanical")
CONTENT = os.path.join(DASH, "public", "content", "mechanical")


def _j(name):
    p = os.path.join(DATA, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{p} 없음 — export 먼저")
    return json.load(open(p, encoding="utf-8"))


def _log_rows():
    files = sorted(glob.glob(os.path.join(VIZ, "logs", "mechanical", "demo_*.csv")))
    return list(csv.DictReader(open(files[-1], encoding="utf-8", newline="")))


# ---------------------------------------------------------------- 재실행·손실열
def test_replay_temperature_within_tolerance():
    rc = _j("timeseries")["replay_check"]
    assert rc["pass"], rc
    assert max(rc["max_err_inner_C"].values()) <= 2.5


def test_loss_matches_config_multipliers():
    """손실열은 온도와 무관하게 결함·부하만의 함수 — config 배율로 직접 계산한 값과 같아야 한다."""
    ts, sc = _j("timeseries"), _j("scenarios")
    tm = ThermalModel()
    t = ts["t_real_s"]
    for s in sc["steps"]:
        mid = (s["t_start"] + s["t_end"]) / 2
        i = max(j for j, x in enumerate(t) if x <= mid)
        P = tm.losses(s["load"], s["faults"], None)
        for n, node in enumerate(tm.nodes):
            assert ts["loss_W"][node.key][i] == pytest.approx(float(P[n]), abs=0.6), (s["id"], node.key)


def test_loss_examples_against_rated():
    """장면 2 베어링 = 정격 × loss_multiplier, 장면 6 권선 = 정격 × load_multiplier² (동손 ∝ I²)."""
    ts, th, fa = _j("timeseries"), _j("thresholds"), _j("faults")
    rated = th["thermal"]["loss_rated_W"]
    f = {x["key"]: x for x in fa["items"]}
    t = ts["t_real_s"]
    i2 = max(j for j, x in enumerate(t) if x <= 45.0)
    assert ts["loss_W"]["bearing_de"][i2] == pytest.approx(rated["bearing_de"] * f["bearing_de_fault"]["loss_multiplier"], abs=0.6)
    i6 = max(j for j, x in enumerate(t) if x <= 145.0)
    assert ts["loss_W"]["winding"][i6] == pytest.approx(rated["winding"] * f["overload"]["load_multiplier"] ** 2, abs=0.6)


def test_sim_elapsed_matches_scenario_integral():
    ts, sc = _j("timeseries"), _j("scenarios")
    total = sum((s["t_end"] - s["t_start"]) * s["time_scale"] for s in sc["steps"])
    i = max(j for j, x in enumerate(ts["t_real_s"]) if x <= sc["total_duration_s"])
    assert ts["sim_elapsed_s"][i] == pytest.approx(total, abs=2.0 * max(s["time_scale"] for s in sc["steps"]))


# ---------------------------------------------------------------- 이벤트
def test_events_stage_crossings_match_log():
    ts, ev = _j("timeseries"), _j("events")
    t = ts["t_real_s"]
    n_stage = 0
    for e in ev["events"]:
        if e["type"] not in ("stage_up", "stage_down", "recovered"):
            continue
        n_stage += 1
        i = t.index(e["t"])
        before, now = ts["temperature_C"][e["part"]][i - 1], ts["temperature_C"][e["part"]][i]
        thr = e["threshold_C"]
        if e["type"] == "stage_up":
            assert before <= thr < now or (before <= thr and now > thr), e
        else:
            assert now <= thr < before or (now <= thr and before > thr), e
        assert e["temp_C"] == pytest.approx(now)
    assert n_stage >= 10


def test_events_vibration_thresholds_from_config():
    ev, th = _j("events"), _j("thresholds")
    iso = load("motor")["vibration_iso20816_3"]
    assert th["vibration_iso"]["watch_mms"] == iso["watch_mms"]["value"]
    assert th["vibration_iso"]["act_mms"] == iso["act_mms"]["value"]
    vib = [e for e in ev["events"] if e["type"] == "vib_zone"]
    assert vib, "진동 등급 변화 이벤트 없음"
    for e in vib:
        assert e["threshold_mms"] in (iso["watch_mms"]["value"], iso["plan_mms"]["value"], iso["act_mms"]["value"], 0.0)


def test_events_have_scene_markers_and_early_warning():
    ev, sc = _j("events"), _j("scenarios")
    scenes = [e for e in ev["events"] if e["type"] == "scene"]
    assert [e["scene"] for e in scenes] == [s["n"] for s in sc["steps"]]
    ew = [e for e in ev["events"] if e.get("note") == "early_warning"]
    assert ew and ew[0]["part"] == "bearing_de" and ew[0]["scene"] == 2
    assert ew[0]["t"] == pytest.approx(sc["lead_time"]["alarm_t"], abs=0.3)


def test_events_sorted_and_unique_ids():
    ev = _j("events")["events"]
    assert [e["id"] for e in ev] == list(range(len(ev)))
    assert all(ev[i]["t"] <= ev[i + 1]["t"] for i in range(len(ev) - 1))


# ---------------------------------------------------------------- 해설 변수·콘텐츠
def test_narration_values_match_log_scene_end():
    vals, sc = _j("narration_values")["scenes"], _j("scenarios")
    rows = _log_rows()
    for s in sc["steps"]:
        r = max((r for r in rows if float(r["t_real_s"]) <= s["t_end"] - 0.3), key=lambda r: float(r["t_real_s"]))
        v = vals[s["id"]]
        assert v["bearing_de_end"] == pytest.approx(float(r["T_bearing_de"]), abs=0.06)
        assert v["winding_end"] == pytest.approx(float(r["T_winding"]), abs=0.06)
        assert v["vib_end"] == pytest.approx(float(r["vibration_mms"]), abs=0.06)
        assert v["time_scale"] == s["time_scale"]


def test_narration_yaml_variables_all_resolvable():
    """문구의 {변수} 가 전부 narration_values 에 존재해야 한다 (오타·미정의 변수 방지)."""
    cfg = yaml.safe_load(open(os.path.join(CONTENT, "narration.yaml"), encoding="utf-8"))
    vals = _j("narration_values")["scenes"]
    for sid, sc in cfg["scenes"].items():
        assert sid in vals, sid
        texts = [sc.get(k, "") for k in ("why", "visible", "result", "presenter_line")] + list(sc.get("cause_chain", {}).values())
        for txt in texts:
            for var in re.findall(r"\{([a-zA-Z0-9_]+)\}", txt):
                assert var in vals[sid], f"{sid}: {{{var}}} 미정의"
        assert sc["focus_component"] in vals[sid].get("scene_label", "") or f"{sc['focus_component']}_end" in vals[sid]


def test_narration_scene_ids_match_scenario():
    cfg = yaml.safe_load(open(os.path.join(CONTENT, "narration.yaml"), encoding="utf-8"))
    sc = _j("scenarios")
    assert list(cfg["scenes"].keys()) == [s["id"] for s in sc["steps"]]


# ---------------------------------------------------------------- 해설 PDF ↔ 로그
def test_guide_pdf_numbers_match_log():
    """animation_guide.md(= 해설 PDF 원문)의 장면별 수치가 로그 장면 종료 시점 값과 같다. 다르면 발표 원고와 화면이 어긋난다."""
    md = io.open(os.path.join(VIZ, "docs", "animation_guide.md"), encoding="utf-8").read()
    rows = _log_rows()

    def log_at(t):
        return max((r for r in rows if float(r["t_real_s"]) <= t), key=lambda r: float(r["t_real_s"]))
    checks = [
        ("권선 63.6", "T_winding", 25), ("베어링 41.2", "T_bearing_de", 25), ("진동 1.0", "vibration_mms", 25),
        ("베어링 135.7", "T_bearing_de", 60), ("진동 4.8", "vibration_mms", 60), ("권선은 85.0", "T_winding", 60),
        ("베어링 열은 81.7", "T_bearing_de", 85), ("축(78.0", "T_shaft", 85), ("진동 3.6", "vibration_mms", 85),
        ("하우징(72.5", "T_frame", 110), ("권선(99.4", "T_winding", 110),
        ("축이 먼저 붉어지고(120.9", "T_shaft", 130), ("로터(111.0", "T_rotor", 130),
        ("권선이 가장 먼저 경고에 닿는다(122.4", "T_winding", 160), ("축 102.9", "T_shaft", 160), ("로터 117.4", "T_rotor", 160),
        ("권선 94.3", "T_winding", 180), ("베어링 77.4", "T_bearing_de", 180),
    ]
    bad = []
    for txt, col, te in checks:
        assert txt in md, f"PDF 원문에서 '{txt}' 를 찾지 못함 (문구가 바뀌었으면 검사표도 갱신)"
        pdfv = float(re.findall(r"\d+\.\d+", txt)[-1])
        logv = float(log_at(te - 0.3)[col])
        if abs(pdfv - logv) > 0.15:
            bad.append((txt, pdfv, logv))
    assert not bad, f"PDF ↔ 로그 불일치: {bad}"
