# -*- coding: utf-8 -*-
"""AI Hub 샘플 특징 테이블(L3) 검증 (TASK_AIHub_샘플 S2): RMS ≥ 0, crest ≥ 1, fr_hz 가 동기속도의 90~100 %,
베어링 번호 없으면 NaN, 합성 신호로 속도 적분·1× 피크·I₂/I₁ 계산 자체를 검증."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

VIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIZ / "tools" / "aihub"))
for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

L3 = VIZ / "data" / "aihub" / "sample" / "L3" / "features.parquet"


# ---------------------------------------------------------------- 합성 신호 (데이터 없이도 돈다)
def test_velocity_integration_of_known_sine():
    import extract_features as ef
    fs, f0, A_g = 4000.0, 100.0, 0.1                       # 0.1 g 진폭 100 Hz 사인
    t = np.arange(0, 3, 1 / fs)
    x = A_g * np.sin(2 * np.pi * f0 * t)
    # 속도 진폭 = a/(2πf) = 0.1·9.80665/(2π·100) m/s = 1.5608 mm/s → RMS = /√2
    expect = 0.1 * 9.80665 / (2 * np.pi * f0) * 1000 / np.sqrt(2)
    assert ef.CFG["accel_unit"] == "g"
    assert ef.velocity_rms_mm_s(x, fs) == pytest.approx(expect, rel=0.03)


def test_harmonic_peaks_and_fr_search():
    import extract_features as ef
    fs = 4000.0; t = np.arange(0, 3, 1 / fs); fr = 29.0
    x = 1.0 * np.sin(2 * np.pi * fr * t) + 0.5 * np.sin(2 * np.pi * 2 * fr * t)
    f, amp = ef.amplitude_spectrum(x, fs)
    assert ef.peak_near(f, amp, fr, 0.03) == pytest.approx(1.0, rel=0.05)
    assert ef.peak_near(f, amp, 2 * fr, 0.03) == pytest.approx(0.5, rel=0.05)
    assert ef.peak_near(f, amp, 3 * fr, 0.03) < 0.05


def test_bearing_multipliers_from_guideline_map():
    import extract_features as ef
    bm = ef.bearing_mults("L-SF-04", "de")                   # 6206: 9볼, 9.525/46 → BPFO 3.57, BPFI 5.43
    assert bm and bm[2] == "6206" and bm[0] == pytest.approx(3.57, abs=0.02) and bm[1] == pytest.approx(5.43, abs=0.02)
    assert ef.bearing_mults("NO-SUCH-MOTOR") is None
    # 포락선 배율: 합성 충격열(BPFO 주기)에서 피크/바닥 비가 커야 한다
    fs, fr = 4000.0, 29.3; t = np.arange(0, 3, 1 / fs); bpfo = bm[0] * fr
    x = 0.002 * np.random.default_rng(0).standard_normal(len(t))
    for k in np.arange(0, 3, 1 / bpfo):
        dt = np.clip(t - k, 0, None)                           # 충격 전 구간은 0 (exp 오버플로 방지)
        x += np.where(t >= k, 0.05 * np.exp(-dt * 800) * np.sin(2 * np.pi * 1200 * dt), 0.0)
    fe, ae = ef.envelope_spectrum(x, fs)
    assert ef.envelope_ratio(fe, ae, bpfo) > 5


def test_i2i1_symmetrical_components():
    import extract_features as ef
    fs, f0 = 2000.0, 60.0; t = np.arange(0, 1, 1 / fs)
    bal = [np.sin(2 * np.pi * f0 * t - k * 2 * np.pi / 3) for k in range(3)]
    r, seq, f_est = ef.i2_over_i1(bal, fs, f0)
    assert r < 1e-6 and seq == "abc" and f_est == pytest.approx(f0, abs=0.05)
    unb = [1.3 * bal[0], bal[1], bal[2]]                     # 한 상 30 % 과전류 → I₂/I₁ = 0.1/1.1
    assert ef.i2_over_i1(unb, fs, f0)[0] == pytest.approx(0.1 / 1.1, abs=0.003)
    r2, seq2, _ = ef.i2_over_i1([unb[0], unb[2], unb[1]], fs, f0)   # 채널 순서가 역상이어도 같은 비율 + 'acb'
    assert r2 == pytest.approx(0.1 / 1.1, abs=0.003) and seq2 == "acb"
    # 59.7 Hz (1 Hz 빈 사이) 에서도 누설 없이 0
    off = [np.sin(2 * np.pi * 59.7 * t - k * 2 * np.pi / 3) for k in range(3)]
    assert ef.i2_over_i1(off, fs, f0)[0] < 1e-3


# ---------------------------------------------------------------- 실제 특징 테이블
@pytest.mark.skipif(not L3.exists(), reason="L3 없음 — tools/aihub/extract_features.py 먼저")
def test_feature_ranges():
    import pandas as pd
    f = pd.read_parquet(L3)
    assert (f["rms"] >= 0).all() and (f["crest_factor"] >= 1).all() and (f["vel_rms_mm_s"].dropna() >= 0).all()
    assert f["nan_count"].eq(0).all()
    v0 = f[f["signal"] == "vibration"]
    # 가이드라인 표에 베어링이 있는 모터는 배율이 계산되고, 전류 행·표에 없는 모터는 NaN + bearing_known False (M1~M5 값으로 대신하지 않는다)
    known = v0[v0["bearing_known"]]
    assert len(known) > 0 and known["env_bpfo_ratio"].notna().all() and (known["env_bpfo_ratio"] > 0).all() and known["bearing_source"].str.contains("guideline").all()
    assert (known["bpfo_hz"] < known["bpfi_hz"]).all() and (known["bpfo_hz"] > 2 * known["fr_hz"]).all()
    c0 = f[f["signal"] == "current"]
    assert c0["bearing_known"].eq(False).all() and c0["env_bpfo_ratio"].isna().all()
    assert set(f["fr_source"]) == {"annotation_rpm"}
    v = f[f["signal"] == "vibration"]
    assert v["vel_rms_mm_s"].notna().all() and v["channel"].eq("ch1").all()
    c = f[f["signal"] == "current"]
    assert set(c["channel"]) == {"ch1", "ch2", "ch3"} and c["i2i1_ref"].between(0, 1).all()
    assert (~c["running"]).sum() > 0 and c[~c["running"]]["load_ratio"].lt(0.1).all()     # 정지 파일이 표시된다
    run = c[c["running"]]
    assert set(run["phase_sequence"]) <= {"abc", "acb"} and run["fund_hz"].between(40, 65).all()   # 55 kW 는 인버터 구동 (49.6~57.5 Hz)
    low = run[run["power_kw"] == 2.2]["fund_hz"]
    assert low.median() == pytest.approx(60.0, abs=0.1) and low.between(59.0, 61.0).all()   # 상용 전원. 과도 상태 파일 1건이 59.4 Hz


@pytest.mark.skipif(not L3.exists(), reason="L3 없음")
def test_fr_within_90_100_percent_of_sync_speed():
    import pandas as pd
    f = pd.read_parquet(L3)
    # 4극 60 Hz 동기 30 Hz (1800 rpm), 2극이면 60 Hz — 어노테이션 rpm 으로 극수를 추정해 가장 가까운 동기속도와 비교
    for fr in f["fr_hz"].unique():
        sync = min((60.0 / p * 2 for p in (2, 4, 6, 8)), key=lambda s: abs(s - fr) if s >= fr else 1e9)
        assert 0.90 * sync <= fr <= 1.00 * sync, fr
