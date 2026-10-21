# -*- coding: utf-8 -*-
"""D 후속 2: 해설 대시보드 데이터(public/data/<mode>/timeseries.json, --source fleet)가 M1 배치 로그(logs/fleet/M1/<mode>/demo_fleet.csv)와 일치하는지.
산출물이 없으면 skip (export_dashboard_data.py --source fleet / run_fleet 먼저)."""
from __future__ import annotations

import csv
import json
import os

import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DASH = os.path.join(VIZ, "..", "dashboard", "public", "data")


def _load(mode):
    ts_p = os.path.join(DASH, mode, "timeseries.json"); csv_p = os.path.join(VIZ, "logs", "fleet", "M1", mode, "demo_fleet.csv")
    if not (os.path.exists(ts_p) and os.path.exists(csv_p)):
        pytest.skip(f"{mode}: timeseries.json 또는 fleet 로그 없음")
    ts = json.load(open(ts_p, encoding="utf-8")); rows = list(csv.DictReader(open(csv_p, encoding="utf-8", newline="")))
    if ts.get("source_csv") != "demo_fleet.csv":
        pytest.skip(f"{mode}: timeseries 가 fleet 로그가 아님({ts.get('source_csv')}) — --source fleet 로 다시 내보내기")
    return ts, rows


@pytest.mark.parametrize("mode", ["electrical", "mechanical"])
def test_timeseries_equals_fleet_log(mode):
    ts, rows = _load(mode)
    by_t = {round(float(r["t_real_s"]), 3): r for r in rows}
    n = len(ts["t_real_s"]); assert n >= 500
    for i in range(0, n, max(1, n // 25)):                                   # 25 지점 + 마지막
        t = ts["t_real_s"][i]; r = by_t[round(t, 3)]
        assert ts["step"][i] == r["step"]
        for ph, col in (("A", "Ia_rms"), ("B", "Ib_rms"), ("C", "Ic_rms")):
            assert ts["current_rms_A"][ph][i] == pytest.approx(float(r[col]), abs=1e-6)
        assert ts["i2_over_i1"][i] == pytest.approx(float(r["i2_over_i1"]), abs=1e-6)
        assert ts["temperature_C"]["winding"][i] == pytest.approx(float(r["T_winding"]), abs=1e-6)
        assert ts["vibration_mms"][i] == pytest.approx(float(r["vibration_mms"]), abs=1e-6)
    if mode == "electrical":
        assert ts["recompute_check"]["pass"], ts["recompute_check"]
    else:
        assert ts["replay_check"]["pass"], ts["replay_check"]


def test_electrical_marks_are_m1_lut_values():
    p = os.path.join(DASH, "electrical", "thresholds.json")
    if not os.path.exists(p):
        pytest.skip("thresholds.json 없음")
    th = json.load(open(p, encoding="utf-8"))
    marks = {m["case"]: m["value"] for m in th["electrical"]["i2i1_marks"]}
    if "M1" not in th["honesty"]["rating_basis"]:
        pytest.skip("22 kW 녹화 기반 데이터 — fleet 소스가 아님")
    assert marks["healthy"] == pytest.approx(0.027, abs=1e-3) and 0.07 <= marks["itsc_4turn"] <= 0.075 and 0.26 <= marks["itsc_12turn"] <= 0.275
    assert th["electrical"]["rated_line_A"] == pytest.approx(4.73)
