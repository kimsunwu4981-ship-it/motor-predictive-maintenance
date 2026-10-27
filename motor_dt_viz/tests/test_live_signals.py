# -*- coding: utf-8 -*-
"""app/live_signals.py — 라이브 state 에 덧붙이는 I₁·I₂·I₀·2주기 파형이 dashboard export(case_signals) 와 같은 값인지."""
from __future__ import annotations

import os
import sys

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, VIZ)
sys.path.insert(0, os.path.join(VIZ, "app"))
sys.path.insert(0, os.path.join(VIZ, "..", "dashboard", "tools"))

from engine import motor_library as ml  # noqa: E402
from engine.current_model import CurrentModel  # noqa: E402
from live_signals import CaseSignalCache, case_signal  # noqa: E402


def _cm() -> CurrentModel:
    m = ml.load_motor("M1")
    return CurrentModel(ml.electrical_cfg(m), ml.motor_spec(m))


def test_matches_export_case_signals():
    from export_status_data import case_signals  # dashboard/tools
    cm = _cm()
    cases = ["healthy", "itsc_4turn", "itsc_12turn", "overload"]
    exp = case_signals(cm, cases)
    for c in cases:
        got = case_signal(cm, c)
        assert got is not None
        assert got["sym_components_A"] == {"i1_A": exp[c]["i1_A"], "i2_A": exp[c]["i2_A"], "i0_A": exp[c]["i0_A"]}
        assert got["waveform_last_2cycles"] == exp[c]["waveform"]
        wf = got["waveform_last_2cycles"]
        assert wf["fs_Hz"] == 2000.0 and wf["cycles"] == 2 and len(wf["t_ms"]) == len(wf["A"]) == len(wf["B"]) == len(wf["C"])


def test_cache_and_unknown_case():
    cm = _cm()
    cache = CaseSignalCache(cm)
    a = cache.get("itsc_4turn"); b = cache.get("itsc_4turn")
    assert a is b and a["sym_components_A"]["i2_A"] > 0
    assert cache.get("no_such_case") is None
    i1, i2 = a["sym_components_A"]["i1_A"], a["sym_components_A"]["i2_A"]
    assert abs(i2 / i1 - cm.evaluate_case("itsc_4turn").i2_over_i1) < 2e-3        # I₂/I₁ 은 엔진 평가값과 일치 (반올림 차)
