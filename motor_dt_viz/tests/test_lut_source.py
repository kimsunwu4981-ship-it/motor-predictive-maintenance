# -*- coding: utf-8 -*-
"""test_lut_source.py — LUT 로더: 격자점 복원, 턴 비율 단조, 0 % 에서 I₂/I₁=0, 범위 밖 클램프, mccm_results ±1 %."""
import json
import os

import numpy as np
import pytest

from engine.lut_source import LutSource, default_lut_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DESK = os.path.join(os.path.expanduser("~"), "OneDrive", "바탕 화면")
_MAXWELL = os.environ.get("MAXWELL_ROOT") or next((c for c in (os.path.join(_DESK, "권상모터_3D모델링"), os.path.join(_DESK, "모터", "권상모터_3D모델링")) if os.path.isdir(c)), os.path.join(_DESK, "모터", "권상모터_3D모델링"))
MCCM_RESULTS = os.path.join(_MAXWELL, "maxwell", "results", "mccm_results.json")   # 2026-10-26: 바탕화면 정리로 모터/ 아래로 이동 — 환경변수 → 옛 경로 → 새 경로


@pytest.fixture(scope="module")
def lut():
    return LutSource(default_lut_path())


def test_grid_points_exact(lut):
    raw = json.load(open(lut.path, encoding="utf-8"))
    for r in raw["rows"][::7]:
        q = lut.query(r["turn_ratio_pct"] / 100.0, r["R_f"], r["load"] * 100.0)
        assert q["on_grid"] and not q["clamped"]
        assert q["i2_over_i1"] == pytest.approx(r["I2_over_I1"], abs=1e-12)
        assert q["i_f_A"] == pytest.approx(r["I_f"], abs=1e-12)
        assert q["p_loop_total_W"] == pytest.approx(r["P_loop_total_W"], abs=1e-9)


def test_monotonic_in_turn_fraction(lut):
    for rf in (0.03, 0.1, 0.3, 1.0):
        vals = [lut.query(f, rf, 100.0)["i2_over_i1"] for f in np.linspace(0.0, lut.fracs[-1], 25)]
        assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))


def test_zero_turns_is_zero(lut):
    for load in (25, 50, 75, 100, 115):
        q = lut.query(0.0, None, load)
        assert q["i2_over_i1"] == pytest.approx(0.0, abs=1e-9)
        assert q["i_f_A"] == pytest.approx(0.0, abs=1e-9)


def test_clamp_flags(lut):
    q = lut.query(0.5, 0.1, 100.0)          # 턴 비율 50 % > 16.7 %
    assert q["clamped"] and "turn_frac" in q["clamped_axes"]
    assert q["i2_over_i1"] == pytest.approx(lut.query(lut.fracs[-1], 0.1, 100.0)["i2_over_i1"])
    q2 = lut.query(0.0208, 10.0, 100.0)      # R_f 10 Ω > 1 Ω
    assert q2["clamped"] and "R_f" in q2["clamped_axes"]
    q3 = lut.query(0.0208, 0.1, 10.0)        # 부하 10 % < 25 %
    assert q3["clamped"] and "load" in q3["clamped_axes"]
    assert not lut.query(0.03, 0.2, 60.0)["clamped"]


def test_interpolation_between_grid(lut):
    a = lut.query(0.0208, 0.1, 100.0)["i2_over_i1"]; b = lut.query(0.0417, 0.1, 100.0)["i2_over_i1"]
    m = lut.query((0.0208 + 0.0417) / 2, 0.1, 100.0)["i2_over_i1"]
    assert min(a, b) < m < max(a, b)


@pytest.mark.skipif(not os.path.exists(MCCM_RESULTS), reason="mccm_results.json 없음")
def test_matches_mccm_results(lut):
    res = json.load(open(MCCM_RESULTS, encoding="utf-8"))["cases"]
    cases = {"C1": (4, 0.1, 100), "C3": (12, 0.1, 100), "C4": (16, 0.1, 100), "C1-R": (4, 1.0, 100), "C1-L": (4, 0.1, 50)}
    for name, (turns, rf, load) in cases.items():
        q = lut.query(lut.turns_to_frac(turns), rf, load)
        assert q["i2_over_i1"] == pytest.approx(res[name]["I2_over_I1"], rel=0.01), name
        assert q["i2_over_in"] == pytest.approx(res[name]["I2"] / lut.rated_current_A, rel=0.01), name
        assert q["i_f_A"] == pytest.approx(res[name]["I_f"], rel=0.01), name
