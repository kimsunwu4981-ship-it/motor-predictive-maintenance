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

from engine import motor_library as ml
from engine.current_model import CurrentModel
from engine.thermal_model import ThermalModel
from engine.config_loader import load  # noqa: E402
from engine.thresholds import Judge  # noqa: E402
import run_fleet as rf  # noqa: E402

FLEET = os.path.join(VIZ, "logs", "fleet")


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8", newline="")))


def test_bearing_signals_from_fault_config():
    """시뮬레이션 베어링 지표 등가값은 thermal.yaml 에서만 온다 (결함 없음 = bearing_normal, 여럿이면 최댓값)."""
    th = ml.thermal_cfg(ml.load_motor("M1"))
    raw = th["faults"]
    assert rf.bearing_signals(th, []) == {"bearing_kurtosis": th["bearing_normal"]["kurtosis"], "bearing_hf_ratio": th["bearing_normal"]["hf_ratio"]}
    de = rf.bearing_signals(th, ["bearing_de_fault"])
    assert de == {"bearing_kurtosis": raw["bearing_de_fault"]["bearing_kurtosis"], "bearing_hf_ratio": raw["bearing_de_fault"]["bearing_hf_ratio"]}
    # 매핑 근거(소손형 수십 / 윤활 부족형은 kurtosis 유지·고주파만 상승 / 무관 결함은 정상값)가 config 에 그대로 있다
    thr = load("thresholds")["bearing"]
    assert de["bearing_kurtosis"] >= thr["kurtosis"]["danger_from"] and de["bearing_hf_ratio"] >= thr["hf_ratio"]["danger_from"]
    nde = rf.bearing_signals(th, ["bearing_nde_fault"])
    assert nde["bearing_kurtosis"] < thr["kurtosis"]["safe_below"] and thr["hf_ratio"]["safe_below"] <= nde["bearing_hf_ratio"] < thr["hf_ratio"]["danger_from"]
    for f in ("fan_failure", "brake_drag", "overload"):
        assert rf.bearing_signals(th, [f]) == rf.bearing_signals(th, [])
    both = rf.bearing_signals(th, ["bearing_nde_fault", "misalignment"])
    assert both["bearing_hf_ratio"] == max(raw["bearing_nde_fault"]["bearing_hf_ratio"], raw["misalignment"]["bearing_hf_ratio"])
    # 스케일된 모터(M1)도 등가값은 같다 (무차원 지표는 열회로 스케일과 무관)
    assert rf.bearing_signals(ml.thermal_cfg(ml.load_motor("M1")), ["bearing_de_fault"]) == de


def test_electrical_run_has_demo_columns_and_constant_temps(tmp_path):
    meta = rf.run_one(ml.load_motor("M1"), "electrical", str(tmp_path))
    d = rows(tmp_path / "demo_fleet.csv")
    assert list(d[0].keys()) == rf.COLS
    assert meta["rows"] == len(d) and len(d) >= meta["total_duration_s"] * rf.RATE_HZ
    assert all(r["T_winding"] == "25.0" and r["mode"] == "electrical" for r in d)
    s = rows(tmp_path / "status_fleet.csv")
    assert list(s[0].keys()) == rf.STATUS_COLS and len(s) == len(d)
    assert {r["status"] for r in s} <= {"SAFE", "WARN", "DANGER"}
    # 결상 장면: A(R)상 저전류 위험 — 배치 CSV 의 마지막 값이 전류 모델(M1, 정격 4.73 A)의 같은 케이스 계산값과 일치
    m = ml.load_motor("M1")
    lost = [r for r in d if r["case"] == "single_phasing"]
    expect = CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m)).evaluate_case("single_phasing").rms_A[0] / m.rated_line_current_a
    assert lost and expect < 0.1 and float(lost[-1]["Ia_rms"]) == round(expect * m.rated_line_current_a, 1)   # CSV 는 0.1 A 반올림 (0.17 A → 0.2)
    assert json.load(open(tmp_path / "meta.json", encoding="utf-8"))["motor"] == "M1"


def test_mechanical_small_motor_runs_cooler_than_reference(tmp_path):
    """M1(22 kW 기준 열회로를 손실비로 스케일)은 기준 열회로(thermal.yaml 원본 = 22 kW)보다 같은 결함에서 차갑다."""
    a = rf.run_one(ml.load_motor("M1"), "mechanical", str(tmp_path / "M1"))
    d1 = rows(tmp_path / "M1" / "demo_fleet.csv")
    e1 = [r for r in d1 if r["step"] == "bearing_fault"][-1]
    ref = ThermalModel().steady_state(1.0, ["bearing_de_fault"])["bearing_de"]       # 22 kW 기준 열회로의 같은 결함 수렴값
    assert float(e1["T_bearing_de"]) < ref - 20
    assert float(e1["T_bearing_de"]) > 25.0 + 10          # 그래도 결함으로 뜨거워지긴 한다
    assert e1["vibration_mms"] == "4.8" and a["rows"] == len(d1)
    s1 = rows(tmp_path / "M1" / "status_fleet.csv")
    # 진동 4.8 mm/s 는 위험(≥4.5). 2026-10-08 베어링 지표 교체 뒤에는 같은 장면에서 bearing_kurtosis(소손형 등가값)의 초과 비율이 더 커
    # 원인은 bearing_kurtosis 로 바뀐다 — 진동 자체의 등급은 여전히 DANGER (docs/bearing_metric_change_comparison.md)
    assert any(r["status"] == "DANGER" and r["vibration"] == "DANGER" for r in s1)
    assert any(r["status"] == "DANGER" and r["cause_signal"] == "bearing_kurtosis" and r["bearing"] == "DANGER" for r in s1)
    assert any(r["bearing_hf_ratio"] == "WARN" and r["bearing_kurtosis"] == "WARN" for r in s1)   # 축정렬불량 장면: 둘 다 경고 (M2 실측 등가값)
    assert not any(r["temperature"] == "DANGER" for r in s1)    # M1: 온도만으로는 위험 미도달 (docs/fleet_summary.md)


def test_safe_verdict_has_no_cause():
    v = Judge().update(0.0, {"temperature": {"winding": 40.0}, "vibration": 0.5})
    assert v.status == "SAFE" and v.cause_signal == "-" and v.cause_component == "-"


@pytest.mark.skipif(not os.path.exists(os.path.join(FLEET, "regression_M5.json")), reason="logs/fleet 없음 — tools/run_fleet.py 먼저")
def test_m5_regression_against_isaac_log():
    reg = json.load(open(os.path.join(FLEET, "regression_M5.json"), encoding="utf-8"))
    for mode in ("mechanical", "electrical"):
        assert reg[mode].get("pass", "skipped" in reg[mode]), reg[mode]


@pytest.mark.skipif(not os.path.exists(os.path.join(VIZ, "docs", "m1_summary.md")), reason="비교표 없음")
def test_fleet_summary_lists_all_motors():
    doc = open(os.path.join(VIZ, "docs", "m1_summary.md"), encoding="utf-8").read()
    for mid in ml.list_ids():
        assert f"| {mid} |" in doc
    assert "FAIL" not in doc
    for mid in ml.list_ids():
        assert os.path.exists(os.path.join(FLEET, mid, "mechanical", "status_fleet.csv"))
        assert os.path.exists(os.path.join(FLEET, mid, "electrical", "status_fleet.csv"))
