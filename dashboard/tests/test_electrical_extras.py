# -*- coding: utf-8 -*-
"""전기 실시간 해설 대시보드 데이터 검증 — 엔진 재계산이 로그와 맞고, 로그의 I₂/I₁ 이 로그 RMS 로 다시 계산되며,
사건·해설 변수·판별 매트릭스 좌표가 로그와 일치하고, 해설 PDF 3장의 숫자가 로그와 같은지 확인한다."""
from __future__ import annotations

import csv
import glob
import io
import json
import math
import os
import re
import sys

import numpy as np
import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)
from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel, symmetrical_components  # noqa: E402

DATA = os.path.join(DASH, "public", "data", "electrical")
CONTENT = os.path.join(DASH, "public", "content", "electrical")
PH = ("A", "B", "C")
# 화면이 재생 시각의 로그 값으로 채우는 실시간 변수 (src/mech/data.ts 전기 liveValues 와 같은 목록)
LIVE_VARS = {"i2i1_now", "i2i1_x_normal_now"} | {f"{p}_{k}_now" for p in "abc" for k in ("rms", "pct", "status", "phase_rms")}


def _j(name):
    p = os.path.join(DATA, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{p} 없음 — export --mode electrical 먼저")
    return json.load(open(p, encoding="utf-8"))


def _log_rows():
    files = sorted(glob.glob(os.path.join(VIZ, "logs", "electrical", "demo_*.csv")))
    return list(csv.DictReader(open(files[-1], encoding="utf-8", newline="")))


# ---------------------------------------------------------------- 엔진 재계산 ↔ 로그
def test_recompute_matches_log():
    rc = _j("timeseries")["recompute_check"]
    assert rc["pass"], rc
    assert rc["max_rms_diff_A"] <= 0.1 and rc["max_i2i1_diff"] <= 0.002


def test_i2i1_recomputed_from_log_rms_and_config_phase():
    """로그의 상별 RMS 크기 + config 위상(페이저 각)으로 대칭좌표를 계산하면 기록된 I₂/I₁ 이 나와야 한다."""
    ts = _j("timeseries")
    worst = 0.0
    for i in range(ts["n"]):
        ph = [ts["current_rms_A"][p][i] * np.exp(1j * math.radians(ts["phasor_deg"][p][i])) for p in PH]
        i1, i2, _ = symmetrical_components(*ph)
        worst = max(worst, abs(abs(i2) / abs(i1) - ts["i2_over_i1"][i]))
    assert worst <= 0.004, worst


def test_ratio_and_phase_current_consistent():
    """정격 대비 비율 = 선전류/정격 선전류, 상전류 = 비율 × 정격 상전류 (Δ결선, 모델의 판정 방식과 동일)."""
    ts, th = _j("timeseries"), _j("thresholds")["electrical"]
    for i in range(0, ts["n"], 7):
        for p in PH:
            assert ts["ratio"][p][i] == pytest.approx(ts["current_rms_A"][p][i] / th["rated_line_A"], abs=0.003)
            assert ts["phase_rms_A"][p][i] == pytest.approx(ts["ratio"][p][i] * th["rated_phase_A"], abs=0.06)


def test_phasor_geometry_normal_and_single_phasing():
    """정상 장면: 세 화살표 길이 차 ≤ 2 %, 간격 120° ± 0.5°. 결상 장면: A상 화살표가 정격의 5 % 미만."""
    ts, sc = _j("timeseries"), _j("scenarios")
    t = ts["t_real_s"]
    i1 = max(j for j, x in enumerate(t) if x <= sc["steps"][0]["t_end"] - 0.3)
    r = [ts["ratio"][p][i1] for p in PH]
    assert max(r) - min(r) <= 0.02
    d = [ts["phasor_deg"][p][i1] for p in PH]
    gaps = sorted(((d[k] - d[(k + 1) % 3]) % 360) for k in range(3))
    assert all(abs(g - 120) <= 0.5 for g in gaps), gaps
    s6 = next(s for s in sc["steps"] if s["electrical_case"] == "single_phasing")
    i6 = max(j for j, x in enumerate(t) if x <= s6["t_end"] - 0.3)
    assert ts["ratio"]["A"][i6] < 0.05 and ts["ratio"]["B"][i6] > 1.0


def test_threshold_amperes_from_config():
    th = _j("thresholds")["electrical"]
    motor, elec = load("motor"), load("electrical")
    i_line = float(motor["rated_line_A"]["value"]) if isinstance(motor.get("rated_line_A"), dict) else th["rated_line_A"]
    assert th["rated_line_A"] == pytest.approx(i_line)
    rows = {r["status"]: r for r in th["rows"]}
    assert rows["over_danger"]["line_A"] == pytest.approx(elec["thresholds"]["over_danger"] * th["rated_line_A"], abs=0.06)
    assert rows["under_danger"]["phase_A"] == pytest.approx(elec["thresholds"]["under_danger"] * th["rated_phase_A"], abs=0.06)
    assert th["slowmo_x"] == round(1 / float(elec["slowmo"]["factor"]))


# ---------------------------------------------------------------- 이벤트
def test_events_status_changes_match_log():
    ts, ev = _j("timeseries"), _j("events")
    t = ts["t_real_s"]
    n = 0
    for e in ev["events"]:
        if e["type"] != "status":
            continue
        i = t.index(e["t"])
        phases = list(PH) if e["phase"] == "ABC" else [e["phase"]]
        assert all(ts["current_status"][p][i] == e["to"] for p in phases), e
        assert any(ts["current_status"][p][i - 1] != e["to"] for p in phases), e
        p0 = phases[0]
        assert e["rms_A"] == pytest.approx(ts["current_rms_A"][p0][i])
        n += 1
    assert n >= 6


def test_events_i2i1_marks_and_lead_time_zero():
    ev, th, sc = _j("events"), _j("thresholds")["electrical"], _j("scenarios")
    marks = {m["case"]: m["value"] for m in th["i2i1_marks"]}
    ups = [e for e in ev["events"] if e["type"] == "i2i1" and e["up"]]
    assert ups and all(e["level"] in marks.values() for e in ups)
    first_4turn = min(e["t"] for e in ups if e["mark"] == "itsc_4turn")
    first_danger = min(e["t"] for e in ev["events"] if e["type"] == "status" and e["to"] == "over_danger")
    assert first_4turn == pytest.approx(first_danger, abs=0.01)         # 리드 타임 0 s (해석식 등가 표현의 한계)
    assert sc["lead_time"]["lead_s"] == pytest.approx(0.0, abs=0.01)


def test_events_balance_only_in_voltage_unbalance_scene():
    ev, sc = _j("events"), _j("scenarios")
    bo = [e for e in ev["events"] if e["type"] == "balance_only"]
    assert len(bo) == 1
    s5 = next(s for s in sc["steps"] if s["electrical_case"] == "voltage_unbalance")
    assert bo[0]["scene"] == s5["n"] and bo[0]["x_normal"] >= 5


def test_events_have_scene_markers_and_unique_ids():
    ev, sc = _j("events"), _j("scenarios")
    assert [e["scene"] for e in ev["events"] if e["type"] == "scene"] == [s["n"] for s in sc["steps"]]
    ids = [e["id"] for e in ev["events"]]
    assert ids == list(range(len(ids)))
    assert all(ev["events"][i]["t"] <= ev["events"][i + 1]["t"] for i in range(len(ids) - 1))


def test_event_templates_cover_all_events():
    tpl = yaml.safe_load(open(os.path.join(CONTENT, "event_templates.yaml"), encoding="utf-8"))
    for e in _j("events")["events"]:
        g = tpl.get(e["type"])
        assert g, f"{e['type']} 템플릿 없음"
        text = g.get(e["tpl"]) or g.get("default")
        assert text, f"{e['type']}/{e['tpl']} 템플릿 없음"
        for var in re.findall(r"\{([a-zA-Z0-9_]+)\}", text):
            assert e.get(var) is not None, f"사건 {e['id']} ({e['type']}/{e['tpl']}): {{{var}}} 값 없음"


# ---------------------------------------------------------------- 해설 변수 · 콘텐츠
def test_narration_values_match_log_scene_end():
    vals, sc = _j("narration_values")["scenes"], _j("scenarios")
    rows = _log_rows()
    for s in sc["steps"]:
        r = max((r for r in rows if float(r["t_real_s"]) <= s["t_end"] - 0.3), key=lambda r: float(r["t_real_s"]))
        v = vals[s["id"]]
        for p, col in (("a", "Ia_rms"), ("b", "Ib_rms"), ("c", "Ic_rms")):
            assert v[f"{p}_rms_end"] == pytest.approx(float(r[col]), abs=0.06)
        assert v["i2i1_end"] == pytest.approx(float(r["i2_over_i1"]), abs=0.0006)


def test_narration_yaml_variables_all_resolvable():
    cfg = yaml.safe_load(open(os.path.join(CONTENT, "narration.yaml"), encoding="utf-8"))
    vals = _j("narration_values")["scenes"]
    sc = _j("scenarios")
    assert list(cfg["scenes"].keys()) == [s["id"] for s in sc["steps"]]
    for sid, s in cfg["scenes"].items():
        texts = [s.get(k, "") for k in ("why", "visible", "result", "presenter_line", "data_source_note")] + list(s.get("cause_chain", {}).values())
        for txt in texts:
            for var in re.findall(r"\{([a-zA-Z0-9_]+)\}", txt):
                assert var in vals[sid] and vals[sid][var] is not None or var in LIVE_VARS, f"{sid}: {{{var}}} 미정의"
        rt = s["reveal_timing"]
        assert 0.0 <= rt["why"] <= rt["visible"] <= rt["result"] <= 1.0
        assert set(s.get("focus_phases") or []) <= set(PH)


def test_matrix_points_from_log():
    th, ts, sc = _j("thresholds")["electrical"], _j("timeseries"), _j("scenarios")
    t = ts["t_real_s"]
    pts = {m["id"]: m for m in th["matrix"]}
    assert len(pts) == len(sc["steps"])
    for s in sc["steps"]:
        i = max(j for j, x in enumerate(t) if x <= s["t_end"] - 0.3)
        m = pts[s["id"]]
        assert m["x_i2i1"] == pytest.approx(ts["i2_over_i1"][i])
        assert m["y_ratio_max"] == pytest.approx(max(ts["ratio"][p][i] for p in PH), abs=0.002)


# ---------------------------------------------------------------- 해설 PDF ↔ 로그 (3장)
def test_guide_pdf_electrical_numbers_match_log():
    md = io.open(os.path.join(VIZ, "docs", "animation_guide.md"), encoding="utf-8").read()
    rows = _log_rows()

    def log_at(t):
        return max((r for r in rows if float(r["t_real_s"]) <= t), key=lambda r: float(r["t_real_s"]))
    checks = [
        ("A 44.5 / B 43.7 / C 43.7 A, I₂/I₁ 0.006", [("Ia_rms", 44.5), ("Ib_rms", 43.7), ("i2_over_i1", 0.006)], 20),
        ("A 57.8 A(정격의 132 %, 위험 과전류), B·C 는 그대로 43.7 A. I₂/I₁ 0.104", [("Ia_rms", 57.8), ("Ib_rms", 43.7), ("i2_over_i1", 0.104)], 45),
        ("A 88.0 A(201 %), I₂/I₁ 0.269", [("Ia_rms", 88.0), ("i2_over_i1", 0.269)], 75),
        ("A·B·C 모두 79.6 A", [("Ia_rms", 79.6), ("Ic_rms", 79.6)], 95),
        ("A 47.2 / B 41.1 / C 42.8 A", [("Ia_rms", 47.2), ("Ib_rms", 41.1), ("Ic_rms", 42.8)], 120),
        ("I₂/I₁ 만 0.060", [("i2_over_i1", 0.060)], 120),
        ("1.6 A), B·C 는 빨강(55.8 A, 128 %). I₂/I₁ 0.479", [("Ia_rms", 1.6), ("Ib_rms", 55.8), ("i2_over_i1", 0.479)], 145),
        ("14.4 A(정격의 33 %)", [("Ia_rms", 14.4)], 165),
    ]
    bad = []
    for txt, cols, te in checks:
        assert txt in md, f"PDF 원문에서 '{txt}' 를 찾지 못함 (문구가 바뀌었으면 검사표도 갱신)"
        r = log_at(te - 0.3)
        for col, pdfv in cols:
            tol = 0.0006 if col == "i2_over_i1" else 0.06
            if abs(pdfv - float(r[col])) > tol:
                bad.append((txt, col, pdfv, float(r[col])))
    assert not bad, f"PDF ↔ 로그 불일치: {bad}"


def test_guide_pdf_threshold_amperes_match_config():
    md = io.open(os.path.join(VIZ, "docs", "animation_guide.md"), encoding="utf-8").read()
    th = _j("thresholds")["electrical"]
    rows = {r["status"]: r for r in th["rows"]}
    for txt, val in (("54.6 A 초과", rows["over_danger"]["line_A"]), ("48.1 A 초과", rows["over_caution"]["line_A"]),
                     ("21.9 A 미만", rows["under_danger"]["line_A"]), ("31.5 A 초과", rows["over_danger"]["phase_A"]),
                     ("12.6 A 미만", rows["under_danger"]["phase_A"])):
        assert txt in md
        assert float(txt.split()[0]) == pytest.approx(val, abs=0.06)


def test_qa_and_glossary_variables_resolvable():
    vals = _j("narration_values")["scenes"]
    first = next(iter(vals))
    for name, key in (("qa.yaml", "items"), ("glossary.yaml", "items")):
        cfg = yaml.safe_load(open(os.path.join(CONTENT, name), encoding="utf-8"))
        for item in cfg[key]:
            v = vals[item.get("scene", first)]
            txt = item.get("q", "") + item.get("a", "") + item.get("text", "")
            for var in re.findall(r"\{([a-zA-Z0-9_]+)\}", txt):
                assert (var in v and v[var] is not None) or var in LIVE_VARS, f"{name}: {{{var}}} 미정의"

