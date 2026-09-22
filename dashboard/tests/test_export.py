# -*- coding: utf-8 -*-
"""대시보드 JSON 이 config·로그와 일치하는지 대조한다 (dashboard/CLAUDE.md §8: 숫자 불일치 = 발표 사고).

실행:  <python> -m pytest dashboard/tests -q      (motor_dt_viz 의 engine 을 임포트한다)
export 를 먼저 돌려 public/data/<mode>/*.json 이 있어야 한다.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, ".."))
VIZ = os.path.abspath(os.path.join(DASH, "..", "motor_dt_viz"))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(DASH, "tools"))

from engine.config_loader import load  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from engine.scenario_player import ScenarioPlayer  # noqa: E402
from engine.thermal_model import ThermalModel  # noqa: E402

MODES = ("mechanical", "electrical")


def _data(mode, name):
    p = os.path.join(DASH, "public", "data", mode, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{p} 없음 — export 먼저")
    return json.load(open(p, encoding="utf-8"))


@pytest.mark.parametrize("mode", MODES)
def test_rated_currents_match_config(mode):
    th = _data(mode, "thresholds")
    cm = CurrentModel()
    assert th["electrical"]["rated_line_A"] == pytest.approx(cm.motor.rated_current("rated_line_A"))
    assert th["electrical"]["rated_phase_A"] == pytest.approx(cm.motor.rated_current("rated_phase_A"))
    motor = load("motor")
    assert th["motor"]["power_kW"] == motor["rating"]["power_kW"]["value"]
    assert th["motor"]["poles"] == motor["rating"]["poles"]["value"]


@pytest.mark.parametrize("mode", MODES)
def test_electrical_rows_are_ratio_times_rated(mode):
    th = _data(mode, "thresholds")
    e = load("electrical")["thresholds"]
    i_line, i_phase = th["electrical"]["rated_line_A"], th["electrical"]["rated_phase_A"]
    rows = {r["status"]: r for r in th["electrical"]["rows"]}
    for st, key in (("over_danger", "over_danger"), ("over_caution", "over_caution"),
                    ("under_caution", "under_caution"), ("under_danger", "under_danger")):
        assert rows[st]["ratio"] == pytest.approx(e[key])
        assert rows[st]["line_A"] == pytest.approx(i_line * e[key], abs=0.06)
        assert rows[st]["phase_A"] == pytest.approx(i_phase * e[key], abs=0.06)


@pytest.mark.parametrize("mode", MODES)
def test_part_thresholds_match_thermal_yaml(mode):
    th = _data(mode, "thresholds")
    tm = ThermalModel()
    for p in th["thermal"]["parts"]:
        ref = tm.thresholds(p["key"])
        assert p["normal_max_C"] == ref["normal"]
        assert p["caution_max_C"] == ref["caution"]
        assert p["warning_max_C"] == ref["warning"]
    # 베어링과 권선은 임계값이 달라야 한다 (공통값으로 뭉뚱그리지 말 것)
    by = {p["key"]: p for p in th["thermal"]["parts"]}
    assert by["bearing_de"]["caution_max_C"] != by["winding"]["caution_max_C"]


@pytest.mark.parametrize("mode", MODES)
def test_colors_match_colors_yaml(mode):
    th = _data(mode, "thresholds")
    colors = load("colors")

    def hx(rgb):
        return "#" + "".join(f"{max(0, min(int(round(c * 255)), 255)):02x}" for c in rgb)
    for s in ("normal", "caution", "warning", "danger"):
        assert th["thermal"]["stage_colors"][s] == hx(colors["status"][s])
    for s in ("over_danger", "over_caution", "normal", "under_caution", "under_danger"):
        assert th["electrical"]["status_colors"][s] == hx(colors["electrical"][s]["color"])


@pytest.mark.parametrize("mode", MODES)
def test_scenario_steps_match_yaml(mode):
    sc = _data(mode, "scenarios")
    player = ScenarioPlayer.for_mode(mode)
    assert len(sc["steps"]) == len(player.steps)
    assert sc["total_duration_s"] == pytest.approx(player.total_duration)
    t0 = 0.0
    for s, y in zip(sc["steps"], player.steps):
        assert s["id"] == y["id"]
        assert s["label"] == y["label"]
        assert s["t_start"] == pytest.approx(t0)
        t0 += float(y["duration_s"])
        assert s["t_end"] == pytest.approx(t0)
        assert s["video_start"] == pytest.approx(s["t_start"] + sc["video_offset_s"])


@pytest.mark.parametrize("mode", MODES)
def test_timeseries_matches_log_csv(mode):
    ts = _data(mode, "timeseries")
    files = sorted(glob.glob(os.path.join(VIZ, "logs", mode, "demo_*.csv")))
    assert files, "로그 없음"
    rows = list(csv.DictReader(open(files[-1], encoding="utf-8", newline="")))
    # 첫 행과 마지막(리셋 전) 행이 그대로 들어 있어야 한다
    assert ts["t_real_s"][0] == pytest.approx(float(rows[0]["t_real_s"]), abs=1e-3)
    n = ts["n"]
    assert ts["temperature_C"]["winding"][n - 1] == pytest.approx(float(rows[n - 1]["T_winding"]), abs=0.01)
    assert ts["current_rms_A"]["A"][n - 1] == pytest.approx(float(rows[n - 1]["Ia_rms"]), abs=0.01)
    assert ts["i2_over_i1"][n - 1] == pytest.approx(float(rows[n - 1]["i2_over_i1"]), abs=1e-4)
    # 시간축은 단조 증가
    assert all(b > a for a, b in zip(ts["t_real_s"], ts["t_real_s"][1:]))


@pytest.mark.parametrize("mode", MODES)
def test_timeseries_covers_full_scenario(mode):
    ts, sc = _data(mode, "timeseries"), _data(mode, "scenarios")
    assert ts["t_real_s"][-1] >= sc["total_duration_s"] - 0.5


def test_mechanical_lead_time_is_positive():
    sc = _data("mechanical", "scenarios")
    lt = sc["lead_time"]
    assert lt["lead_s"] is not None and lt["lead_s"] > 0
    assert lt["alarm_t"] < lt["danger_t"]


def test_electrical_alarm_level_is_config_value():
    sc = _data("electrical", "scenarios")
    e = load("electrical")["cases"]["itsc_4turn"]["target_i2i1"]
    assert sc["lead_time"]["alarm_level_i2i1"] == pytest.approx(e)


def test_no_fem_claim_in_sources():
    for mode in MODES:
        sc = _data(mode, "scenarios")
        for s in sc["steps"]:
            assert "maxwell" not in s["source"].lower() and "fem" not in s["source"].lower(), s["id"]
