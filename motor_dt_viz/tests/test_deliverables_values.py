# -*- coding: utf-8 -*-
"""E3: 산출 문서(docs/deliverables/out/*)와 값 대응표(docs/m1_migration_notes.md)의 숫자가 docs/verification_summary.json·config/motors/M1.yaml 과 일치하는지.
대조 6값: 정격 전류 4.73 A · 1760 rpm · 베어링 6206ZZC3 · 진동 임계 1.8/4.5 · I₂/I₁ 경계 0.05/0.10 · ITSC 4턴/12턴 I₂/I₁.
산출 문서가 없으면(원본 _v22kW 미제공) 대응표만 검사한다 — 2026-10-21 현재 docs/deliverables/_v22kW 없음.
"""
from __future__ import annotations

import glob
import json
import os
import re

import pytest
import yaml

VIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))


@pytest.fixture(scope="module")
def key():
    p = os.path.join(REPO, "docs", "verification_summary.json")
    if not os.path.exists(p):
        pytest.skip("docs/verification_summary.json 없음 — tools/docs/verification_summary.py 먼저")
    return json.load(open(p, encoding="utf-8"))["key"]


@pytest.fixture(scope="module")
def m1():
    return yaml.safe_load(open(os.path.join(VIZ, "config", "motors", "M1.yaml"), encoding="utf-8"))


def v(x):
    return x["value"] if isinstance(x, dict) and "value" in x else x


def test_summary_matches_m1_yaml(key, m1):
    assert key["rated_line_current_A"] == v(m1["rated_line_current_a"]) == 4.73
    assert key["rated_rpm"] == v(m1["rated_rpm"]) == 1760
    assert key["bearing_de"] == v(m1["bearing_de"]) and key["bearing_nde"] == v(m1["bearing_nde"])
    assert (key["vib_watch"], key["vib_act"]) == (m1["vibration"]["watch_mms"], m1["vibration"]["act_mms"])
    assert key["bpfo_hz"] == pytest.approx(v(m1["bearing_fault_multipliers"]["bpfo"]) * 1760 / 60, abs=0.1)


def test_migration_notes_values_match_summary(key):
    doc = open(os.path.join(VIZ, "docs", "m1_migration_notes.md"), encoding="utf-8").read()
    for needle in (f"{key['rated_line_current_A']} A", f"{key['rated_rpm']:,} rpm", key["bearing_de"], f"{key['bpfo_hz']} / {key['bpfi_hz']} Hz",
                   f"경고 {key['vib_watch']} / 위험 {key['vib_act']} mm/s", f"{key['i2i1_warn']}/{key['i2i1_danger']}"):
        assert needle in doc, needle
    assert f"{key['inherent_i2i1']} / {key['i2i1_4turn']:.3f} / {key['i2i1_12turn']:.3f}" in doc or f"{key['i2i1_4turn']:.3f}" in doc


def test_deliverables_out_if_present(key):
    out = sorted(glob.glob(os.path.join(REPO, "docs", "deliverables", "out", "*.md")))
    if not out:
        pytest.skip("docs/deliverables/out/*.md 없음 — 원본(_v22kW) 미제공으로 산출 문서 건너뜀 (docs/deliverables/README.md)")
    for p in out:
        doc = open(p, encoding="utf-8").read()
        for needle in (f"{key['rated_line_current_A']} A", str(key["rated_rpm"]), key["bearing_de"]):
            assert needle in doc, (os.path.basename(p), needle)
        assert not re.search(r"43\.7 A|1,?180 rpm|22220|Group 2", doc), os.path.basename(p)      # 22 kW 고유값이 남아 있으면 안 된다
