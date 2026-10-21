# -*- coding: utf-8 -*-
"""검증 도구 테스트 (V1~V6, 2026-10-21): 독립 재계산의 정확성, 해석 근거 파일의 sha 일관성·수기 숫자 없음, 대조 스크립트의 판정 규칙. Isaac 비의존."""
from __future__ import annotations

import csv
import json
import math
import os
import sys

import numpy as np
import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ); sys.path.insert(0, os.path.join(VIZ, "tools", "verify"))
from recompute_i2i1 import analyze, symmetrical, fundamental_phasor  # noqa: E402


def synth(tmp_path, i1=4.73, r=0.05, theta_deg=30.0, fs=2000.0, f0=60.0, dur=1.0):
    """알려진 대칭 성분으로 3상 파형을 만든다 (엔진 비의존): Ia = I1 + I2, Ib = a²I1 + aI2, Ic = aI1 + a²I2 (피크 기준 복소)."""
    a_op = np.exp(2j * np.pi / 3)
    I1 = math.sqrt(2) * i1; I2 = I1 * r * np.exp(1j * math.radians(theta_deg))
    ph = [I1 + I2, a_op ** 2 * I1 + a_op * I2, a_op * I1 + a_op ** 2 * I2]
    t = np.arange(0, dur, 1 / fs); w = 2 * np.pi * f0 * t
    p = tmp_path / "wf.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["t_s", "ia_A", "ib_A", "ic_A"])
        for k in range(len(t)):
            wr.writerow([f"{t[k]:.5f}"] + [f"{abs(x) * math.sin(w[k] + np.angle(x)):.6f}" for x in ph])
    return str(p)


def test_recompute_recovers_known_components(tmp_path):
    p = synth(tmp_path, r=0.0726, theta_deg=23.17)
    out = analyze(p, 60.0, 4.73)
    assert out["i2_over_i1"] == pytest.approx(0.0726, rel=1e-3)
    assert out["i2_angle_deg_vs_i1"] == pytest.approx(23.17, abs=0.2)
    assert out["i1_A_rms"] == pytest.approx(4.73, rel=1e-3) and out["i2_over_in"] == pytest.approx(0.0726, rel=1e-3)
    assert out["harmonics_A"]["h3_over_h1"] < 0.01 and out["fs_hz"] == pytest.approx(2000, rel=1e-3)
    p0 = synth(tmp_path, r=0.0)
    assert analyze(p0, 60.0)["i2_over_i1"] < 1e-6                      # 완전 균형 → 0


def test_symmetrical_components_definition():
    a_op = np.exp(2j * np.pi / 3)
    i1, i2, i0 = symmetrical(1 + 0j, a_op ** 2, a_op)                 # 정상분만
    assert abs(i1 - 1) < 1e-12 and abs(i2) < 1e-12 and abs(i0) < 1e-12
    i1, i2, i0 = symmetrical(1 + 0j, a_op, a_op ** 2)                 # 역상분만
    assert abs(i1) < 1e-12 and abs(i2 - 1) < 1e-12
    x = np.sin(2 * np.pi * 60 * np.arange(0, 1, 1 / 2000) + 0.3)
    ph = fundamental_phasor(x, 2000.0, 60.0)
    assert abs(ph) == pytest.approx(1.0, rel=2e-3) and np.angle(ph) == pytest.approx(0.3 - np.pi / 2, abs=0.01)   # sin = cos(φ − π/2) 규약


@pytest.fixture(scope="module")
def ref():
    p = os.path.join(VIZ, "data", "electrical", "analysis_reference.json")
    if not os.path.exists(p):
        pytest.skip("analysis_reference.json 없음 (tools/verify/build_analysis_reference.py)")
    return json.load(open(p, encoding="utf-8"))


def test_reference_has_sha_for_every_input_and_matches_lut(ref):
    import hashlib
    assert ref["no_manual_numbers"] is True
    for k, inp in ref["inputs"].items():
        p = inp["path"] if os.path.isabs(inp["path"]) else os.path.join(REPO, inp["path"])
        if os.path.exists(p):                                           # Maxwell 저장소(읽기 전용)가 없는 환경이면 건너뛴다
            assert hashlib.sha256(open(p, "rb").read()).hexdigest() == inp["sha256"], k
    assert ref["lut"]["sha_match"] is True
    S = ref["scenarios"]
    assert set(S) == {"healthy", "itsc_4turn", "itsc_8turn", "itsc_12turn", "itsc_16turn", "itsc_4turn_resistive", "itsc_4turn_halfload"}
    for sid, x in S.items():
        for key in ("i2_over_i1_fault", "i2_over_in", "i_f_A", "p_loop_total_W"):
            assert x[key]["file"] and x[key]["sha256"] and x[key]["grade"], (sid, key)   # 값마다 출처·sha
        lo, hi = x["i2_over_i1_composite"]["range"]
        for ang, v in x["i2_over_i1_composite"]["expected_by_angle"].items():
            assert lo - 1e-9 <= v <= hi + 1e-9, (sid, ang)
    # 4턴: MCCM I_f 와 FEM 보정 I_f 가 ±5 % 안 (F1)
    f4 = S["itsc_4turn"]["i_f_A"]
    assert abs(f4["fem_corrected"]["I_f_A"] / f4["mccm"] - 1) <= 0.05 and f4["fem_corrected"]["pass_5pct"]
    # 손실 공식 I_f²(R_f + μR1_hot) 은 루프 저항항만이라 MCCM 총손실(단락 턴 동손 포함)보다 작거나 같다
    for sid in ("itsc_4turn", "itsc_12turn", "itsc_16turn"):
        pl = S[sid]["p_loop_total_W"]; assert pl["formula_value"] <= pl["mccm"] * 1.0001 and pl["formula_value"] >= pl["mccm"] * 0.5


def test_reference_rated_point_and_tolerances(ref):
    rp = ref["rated_point"]
    assert rp["catalog"]["I_A"] == pytest.approx(4.73) and rp["rmxprt_v2m2"]["I_A"] == pytest.approx(4.67, abs=0.01)
    assert rp["iec_tolerance"]["limits"]["pf_min"] <= rp["rmxprt_v2m2"]["pf"]
    assert ref["starting"]["fem_corrected"]["I_st_ratio"] < ref["starting"]["rmxprt_v2m2"]["I_st_ratio"]           # 스큐 보정으로 내려간다
    assert ref["mechanical_note"].startswith("Maxwell 근거 없음")


def test_sim_vs_analysis_row_rules():
    from sim_vs_analysis import row
    assert row("x", "s", 1.005, 1.0, 0.01)["pass"] and not row("x", "s", 1.02, 1.0, 0.01)["pass"]
    assert row("x", "s", 0.0, 0.0, 0.01)["pass"] and not row("x", "s", 0.01, 0.0, 0.01)["pass"]               # 기준 0 은 절대값
    assert row("x", "s", 0.05, [0.02, 0.07], None, kind="range")["pass"] and not row("x", "s", 0.08, [0.02, 0.07], None, kind="range")["pass"]
    assert row("x", "s", "WARN", "WARN", None, kind="match")["pass"] and not row("x", "s", "SAFE", "WARN", None, kind="match")["pass"]


def test_verify_scenarios_match_shared_timing():
    """검증 전용 열 시나리오(tools/verify/*.yaml)는 정상 20 s + ITSC 200 s, 배속 90, 기존 장면 파일 불변."""
    import yaml
    for T in (4, 12, 16):
        c = yaml.safe_load(open(os.path.join(VIZ, "tools", "verify", f"scenario_itsc_{T}turn_thermal.yaml"), encoding="utf-8"))
        assert [s["id"] for s in c["steps"]] == ["normal", f"itsc_{T}turn"] and sum(s["duration_s"] for s in c["steps"]) == 220
        assert all(s["time_scale"] == 90 and s["mode"] == "integrated" for s in c["steps"])
