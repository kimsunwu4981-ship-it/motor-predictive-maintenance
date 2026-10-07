# -*- coding: utf-8 -*-
"""배치 시뮬레이션(tools/run_fleet.py) 테스트 (TASK_다중모터 §6): 로그 형식, 베어링 지표, 모터별 차이, M5 회귀, 비교표."""
import csv
import json
import os
import sys

import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(VIZ, "tools"))

from engine import motor_library as ml  # noqa: E402
from engine.thresholds import Judge  # noqa: E402
import run_fleet as rf  # noqa: E402

FLEET = os.path.join(VIZ, "logs", "fleet")


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", newline="")))


def test_bearing_index_from_fault_config():
    th = ml.thermal_cfg(ml.load_motor("M5"))
    assert rf.bearing_index(th, []) == 1.0
    assert rf.bearing_index(th, ["bearing_de_fault"]) == 5.0
    assert rf.bearing_index(th, ["misalignment"]) == 2.5
    assert rf.bearing_index(th, ["fan_failure"]) == 1.0 and rf.bearing_index(th, ["brake_drag"]) == 1.0


def test_electrical_run_has_demo_columns_and_constant_temps(tmp_path):
    meta = rf.run_one(ml.load_motor("M3"), "electrical", str(tmp_path))
    d = rows(tmp_path / "demo_fleet.csv")
    assert list(d[0].keys()) == rf.COLS
    assert meta["rows"] == len(d) and len(d) >= meta["total_duration_s"] * rf.RATE_HZ
    assert all(r["T_winding"] == "25.0" and r["mode"] == "electrical" for r in d)
    s = rows(tmp_path / "status_fleet.csv")
    assert list(s[0].keys()) == rf.STATUS_COLS and len(s) == len(d)
    assert {r["status"] for r in s} <= {"SAFE", "WARN", "DANGER"}
    # 결상 장면: A(R)상 저전류 위험, 정격 대비 비율은 모터 무관 (M3 정격 15.9 A 기준 암페어만 다름)
    lost = [r for r in d if r["case"] == "single_phasing"]
    assert lost and float(lost[-1]["Ia_rms"]) / ml.load_motor("M3").rated_line_current_a == pytest.approx(0.036, abs=0.005)
    assert json.load(open(tmp_path / "meta.json", encoding="utf-8"))["motor"] == "M3"


def test_mechanical_small_motor_runs_cooler_than_reference(tmp_path):
    a = rf.run_one(ml.load_motor("M1"), "mechanical", str(tmp_path / "M1"))
    b = rf.run_one(ml.load_motor("M5"), "mechanical", str(tmp_path / "M5"))
    assert a["rows"] == b["rows"]
    d1, d5 = rows(tmp_path / "M1" / "demo_fleet.csv"), rows(tmp_path / "M5" / "demo_fleet.csv")
    # 베어링 결함 장면 끝: M1 DE 베어링 < M5 (결함 손실이 출력에 비례)
    e1 = [r for r in d1 if r["step"] == "bearing_fault"][-1]; e5 = [r for r in d5 if r["step"] == "bearing_fault"][-1]
    assert float(e1["T_bearing_de"]) < float(e5["T_bearing_de"]) - 20
    assert float(e1["T_bearing_de"]) > 25.0 + 10          # 그래도 결함으로 뜨거워지긴 한다
    # 진동·ISO 구역은 시나리오 상수라 같다, 규격만 다르다
    assert e1["vibration_mms"] == e5["vibration_mms"] == "4.8" and e1["iso_zone"] == e5["iso_zone"]
    s1 = rows(tmp_path / "M1" / "status_fleet.csv")
    assert any(r["status"] == "DANGER" and r["cause_signal"] == "vibration" for r in s1)
    assert not any(r["temperature"] == "DANGER" for r in s1)    # M1: 온도만으로는 위험 미도달 (docs/fleet_summary.md)


def test_safe_verdict_has_no_cause():
    v = Judge().update(0.0, {"temperature": {"winding": 40.0}, "vibration": 0.5})
    assert v.status == "SAFE" and v.cause_signal == "-" and v.cause_component == "-"


@pytest.mark.skipif(not os.path.exists(os.path.join(FLEET, "regression_M5.json")), reason="logs/fleet 없음 — tools/run_fleet.py 먼저")
def test_m5_regression_against_isaac_log():
    reg = json.load(open(os.path.join(FLEET, "regression_M5.json"), encoding="utf-8"))
    for mode in ("mechanical", "electrical"):
        assert reg[mode].get("pass", "skipped" in reg[mode]), reg[mode]


@pytest.mark.skipif(not os.path.exists(os.path.join(VIZ, "docs", "fleet_summary.md")), reason="비교표 없음")
def test_fleet_summary_lists_all_motors():
    doc = open(os.path.join(VIZ, "docs", "fleet_summary.md"), encoding="utf-8").read()
    for mid in ml.list_ids():
        assert f"| {mid} |" in doc
    assert "M5 회귀" in doc and "PASS" in doc and "FAIL" not in doc
    for mid in ml.list_ids():
        assert os.path.exists(os.path.join(FLEET, mid, "mechanical", "status_fleet.csv"))
        assert os.path.exists(os.path.join(FLEET, mid, "electrical", "status_fleet.csv"))
