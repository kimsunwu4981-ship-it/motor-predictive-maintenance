# -*- coding: utf-8 -*-
"""저전류 판정 규칙 변경(2026-10-21 승인, thresholds.yaml current_ratio.low_current_policy):
  (a) 세 상 함께 r < 0.50 + 불평형 < 0.05 + I₂/I₁ 경고 미만 → '경부하(참고)' advisory, 종합 미반영
  (b) 한 상만 저전류 / 저전류+불평형 ≥ 0.05 / 저전류+I₂/I₁ ≥ 위험 → 결상 의심 DANGER (기존)
  (c) 상한·히스테리시스·지속 3 s 불변
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import motor_library as ml  # noqa: E402
from engine.config_loader import load  # noqa: E402
from engine.thresholds import Judge  # noqa: E402


def cfg():
    return copy.deepcopy(load("thresholds"))


def test_policy_present_in_config():
    c = cfg()["current_ratio"]
    assert c["low_current_policy"] == {"light_load_advisory": True, "unbalance_gate": 0.05}
    assert (c["safe_low"], c["safe_high"], c["danger_over"], c["danger_under"]) == (0.85, 1.10, 1.25, 0.50)   # 경계 불변


def test_three_phase_light_load_is_advisory_only():
    j = Judge(cfg(), motor=ml.load_motor("M1"))
    v = j.stateless({"current_ratio": {"A": 0.339, "B": 0.326, "C": 0.326}, "i2i1": 0.027, "temperature": {"winding": 40.0}})
    assert v.status == "SAFE" and v.cause_signal == "-"
    adv = [s for s in v.advisory if s.kind == "current_ratio"]
    assert len(adv) == 3 and all(s.level == "SAFE" and s.raw_level == "DANGER" and s.note.startswith("경부하(참고)") for s in adv)
    assert all(s.advisory for s in adv)


def test_single_phase_low_is_danger():
    j = Judge(cfg(), motor=ml.load_motor("M1"))
    v = j.stateless({"current_ratio": {"A": 0.036, "B": 1.278, "C": 1.278}, "i2i1": 0.479})
    assert v.status == "DANGER" and v.cause_signal == "current_ratio" and not v.advisory


def test_low_with_unbalance_or_i2i1_danger_is_danger():
    j = Judge(cfg(), motor=ml.load_motor("M1"))
    v1 = j.stateless({"current_ratio": {"A": 0.30, "B": 0.40, "C": 0.45}, "i2i1": 0.027})          # 불평형 0.22 ≥ 0.05
    v2 = j.stateless({"current_ratio": {"A": 0.33, "B": 0.33, "C": 0.33}, "i2i1": 0.12})           # I₂/I₁ ≥ 위험
    v3 = j.stateless({"current_ratio": {"A": 0.33, "B": 0.33, "C": 0.33}, "i2i1": 0.06})           # I₂/I₁ 경고 이상 → 경부하 아님
    assert v1.status == "DANGER" and v2.status == "DANGER" and v3.status == "DANGER"
    assert all(v.cause_signal == "current_ratio" and not v.advisory for v in (v1, v2, v3))


def test_policy_off_restores_old_rule():
    c = cfg(); c["current_ratio"]["low_current_policy"]["light_load_advisory"] = False
    v = Judge(c, motor=ml.load_motor("M1")).stateless({"current_ratio": {"A": 0.339, "B": 0.326, "C": 0.326}, "i2i1": 0.027})
    assert v.status == "DANGER" and v.cause_signal == "current_ratio"


def test_persistence_and_upper_bound_unchanged():
    sig_hi = {"current_ratio": {"A": 1.30, "B": 1.30, "C": 1.30}, "i2i1": 0.027}
    j2 = Judge(cfg(), motor=ml.load_motor("M1"))
    j2.update(0.0, {"current_ratio": {"A": 1.0, "B": 1.0, "C": 1.0}, "i2i1": 0.027})
    assert j2.update(1.0, sig_hi).status == "SAFE"                           # 상향은 3 s 지속 뒤 (raw DANGER 시작 t=1.0)
    assert j2.update(3.5, sig_hi).status == "SAFE"                           # 2.5 s 경과 — 아직
    assert j2.update(4.1, sig_hi).status == "DANGER"                         # 3.1 s 경과 → 과전류 위험 (상한 규칙 불변)
    # 경부하 뒤 한 상이 끊기면 내부 상태(이미 DANGER)가 바로 드러난다
    j3 = Judge(cfg(), motor=ml.load_motor("M1"))
    for t in (0.0, 2.0, 4.0):
        v = j3.update(t, {"current_ratio": {"A": 0.33, "B": 0.33, "C": 0.33}, "i2i1": 0.027})
    assert v.status == "SAFE" and len(v.advisory) == 3
    v = j3.update(4.5, {"current_ratio": {"A": 0.33, "B": 0.80, "C": 0.80}, "i2i1": 0.027})
    assert v.status == "DANGER" and v.cause_signal == "current_ratio"
