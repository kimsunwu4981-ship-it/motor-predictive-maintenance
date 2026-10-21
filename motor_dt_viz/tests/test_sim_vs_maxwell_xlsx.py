# -*- coding: utf-8 -*-
"""C4: 비교표(docs/verification/M1_sim_vs_maxwell.xlsx + sim_vs_maxwell.json)가 기존 대조·LUT 와 같은 숫자를 쓰는지, 역추정 함수가 격자점을 복원하는지, 바탕화면 사본이 있는지."""
from __future__ import annotations

import json
import os
import sys

import pytest

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
OUT = os.path.join(REPO, "docs", "verification")
sys.path.insert(0, os.path.join(VIZ, "tools", "verify"))
from sim_vs_maxwell_xlsx import invert_turns, lut_curve, fault_component  # noqa: E402


@pytest.fixture(scope="module")
def sm():
    p = os.path.join(OUT, "sim_vs_maxwell.json")
    if not os.path.exists(p):
        pytest.skip("sim_vs_maxwell.json 없음 — tools/verify/sim_vs_maxwell_xlsx.py 먼저")
    return json.load(open(p, encoding="utf-8"))


@pytest.fixture(scope="module")
def lut():
    return json.load(open(os.path.join(VIZ, "data", "electrical", "M1_mccm_lut_v2.json"), encoding="utf-8"))


def test_sheet1_sim_values_equal_sim_vs_analysis(sm):
    sva = json.load(open(os.path.join(OUT, "sim_vs_analysis.json"), encoding="utf-8"))
    rows = {(r["item"], r["scenario"]): r for r in sva["rows"]}
    pairs = {"I₂/I₁ 합성(표시값)": "I₂/I₁ 합성값 vs 기대(각도 0°)", "단락 루프 전류 I_f [A]": "단락 루프 전류 I_f [A] vs MCCM", "단락 루프 총손실 [W]": "단락 루프 총손실 [W] vs I_f²(R_f+μR1_hot)+단락턴 동손 (MCCM)"}
    n = 0
    for r in sm["sheet1"]:
        key = pairs.get(r["item"])
        if key and (key, r["scenario"]) in rows and r["sim"] is not None:
            assert float(r["sim"]) == pytest.approx(float(rows[(key, r["scenario"])]["sim"]), rel=1e-6), (r["item"], r["scenario"]); n += 1
    assert n >= 12
    assert not [r for r in sm["sheet1"] if r["judge"] == "FAIL"]


def test_lut_column_equals_lut_file(sm, lut):
    for r in sm["sheet1"]:
        if r["item"] == "I₂/I₁ 결함분" and r["turns"] > 0:
            row = next(x for x in lut["rows"] if int(x["turns"]) == r["turns"] and abs(float(x["R_f"]) - r["R_f"]) < 1e-9 and abs(float(x["load"]) - r["load"]) < 1e-9)
            assert float(r["lut"]) == pytest.approx(float(row["I2_over_I1"]), rel=1e-4), r["scenario"]      # analysis_reference 는 소수 6자리 반올림


def test_inversion_recovers_grid_points(lut):
    for rf, load in ((0.1, 1.0), (1.0, 1.0), (0.1, 0.5)):
        curve = lut_curve(lut, rf, load)
        assert len(curve) == 8 and all(curve[k][1] <= curve[k + 1][1] + 1e-12 for k in range(7))       # 단조
        for frac, i2, *_ in curve[1:]:
            est, flag = invert_turns(curve, i2)
            assert flag == "ok" and est == pytest.approx(frac * 192 / 100, abs=1e-6)
    curve = lut_curve(lut, 0.1, 1.0)
    mid = (curve[2][1] + curve[3][1]) / 2                                            # 4턴~8턴 사이 중간값 → 6턴 근처
    est, flag = invert_turns(curve, mid)
    assert flag == "ok" and abs(est - (curve[2][0] + curve[3][0]) / 2 * 1.92) < 1e-6
    assert fault_component(0.0726, 23.2, 0.027, 0.0) == pytest.approx(0.0490, abs=5e-4)              # 4턴 합성 → 결함분


def test_inversion_table_within_one_turn(sm):
    assert sm["inversion_n"] >= 6 and sm["inversion_pass"] == sm["inversion_n"]
    for r in sm["inversion"]:
        assert abs(r["err_turns"]) <= 1.0 and r["flag"] == "ok", r


def test_workbook_sheets_and_charts():
    import openpyxl
    p = os.path.join(OUT, "M1_sim_vs_maxwell.xlsx")
    if not os.path.exists(p):
        pytest.skip("엑셀 없음")
    wb = openpyxl.load_workbook(p)
    names = wb.sheetnames
    for want in ("0 요약", "1 시나리오 비교", "2 정격·기동", "3 결함 크기 역추정", "4 FEM 불확실성 민감도", "5 탐지 시각", "6 등가회로 대조", "7 근거 사슬", "8 한계"):
        assert want in names, want
    n_charts = sum(len(wb[n]._charts) for n in names)
    assert n_charts >= 3


def test_desktop_copy_exists(sm):
    p = sm.get("desktop_copy")
    if not p:
        pytest.skip("바탕화면 사본 생략(--no-desktop)")
    assert os.path.exists(p) and os.path.getsize(p) > 10_000
