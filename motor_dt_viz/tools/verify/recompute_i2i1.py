# -*- coding: utf-8 -*-
"""recompute_i2i1.py — 합성 파형 CSV(t_s, ia_A, ib_A, ic_A)에서 대칭 성분을 **엔진과 무관하게** 다시 계산한다 (V2 독립 검증, Maxwell 쪽 e3_tables/negseq 후처리와 같은 정의).

정의 (Fortescue, a = e^{j120°}):
  페이저 X_k = (2/N)·Σ x[n]·e^{−j2π f0 n/fs}  (정수 주기 창 → 기본파 피크·복소), 규약 x(t) = |X| sin(ωt + arg X) 와 무관하게 비율은 같다
  I₁ = (Ia + a·Ib + a²·Ic)/3,  I₂ = (Ia + a²·Ib + a·Ic)/3,  I₀ = (Ia + Ib + Ic)/3
  I₂/I₁ = |I₂|/|I₁|,  상 불평형(max dev) = max_k |I_k − mean| / mean × 100 (RMS 기준)
엔진(engine/current_model.py)은 import 하지 않는다. numpy 만 쓴다.

  py -3.12 -X utf8 tools/verify/recompute_i2i1.py <waveform.csv> [--f0 60] [--rated 4.73]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

import numpy as np

A_OP = np.exp(2j * np.pi / 3)


def load_waveform(path: str) -> tuple[np.ndarray, np.ndarray]:
    t, I = [], [[], [], []]
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t.append(float(row["t_s"])); I[0].append(float(row["ia_A"])); I[1].append(float(row["ib_A"])); I[2].append(float(row["ic_A"]))
    return np.asarray(t), np.asarray(I)


def fundamental_phasor(x: np.ndarray, fs: float, f0: float) -> complex:
    """정수 주기 창의 기본파 복소 진폭 (피크). 창 길이는 fs/f0 의 정수배로 자른다 (2 kHz / 60 Hz = 33.33 → 3주기 100 샘플)."""
    n_cyc = int(round(fs / f0 * 3))                      # 3 주기(100 샘플)씩 — 누설 최소
    n_win = (len(x) // n_cyc) * n_cyc
    xs = x[:n_win]
    n = np.arange(n_win)
    return 2.0 / n_win * np.sum(xs * np.exp(-2j * np.pi * f0 * n / fs))


def symmetrical(ia: complex, ib: complex, ic: complex) -> tuple[complex, complex, complex]:
    i1 = (ia + A_OP * ib + A_OP ** 2 * ic) / 3
    i2 = (ia + A_OP ** 2 * ib + A_OP * ic) / 3
    i0 = (ia + ib + ic) / 3
    return i1, i2, i0


def analyze(path: str, f0: float = 60.0, rated_A: float | None = None) -> dict:
    t, I = load_waveform(path)
    fs = 1.0 / float(np.median(np.diff(t)))
    ph = [fundamental_phasor(I[k], fs, f0) for k in range(3)]
    i1, i2, i0 = symmetrical(*ph)
    rms = [float(np.sqrt(np.mean(I[k] ** 2))) for k in range(3)]
    mean = sum(rms) / 3
    out = {"file": path, "fs_hz": fs, "f0_hz": f0, "n_samples": int(len(t)),
           "rms_A": [round(v, 5) for v in rms], "rms_from_phasor_A": [round(abs(p) / math.sqrt(2), 5) for p in ph],
           "i1_A_rms": round(abs(i1) / math.sqrt(2), 5), "i2_A_rms": round(abs(i2) / math.sqrt(2), 5), "i0_A_rms": round(abs(i0) / math.sqrt(2), 6),
           "i2_over_i1": round(abs(i2) / abs(i1), 6) if abs(i1) > 0 else None,
           "i2_angle_deg_vs_i1": round(math.degrees(np.angle(i2) - np.angle(i1)), 3) if abs(i2) > 1e-12 else None,
           "unbalance_max_dev_pct": round(max(abs(v - mean) for v in rms) / mean * 100, 4) if mean > 0 else None,
           "spectrum_note": "합성 파형은 기본파 단일 성분 — 회전자 슬롯 고조파(RSH)·측대파 없음 (해석 파형이 아니라 엔진 페이저 합성)"}
    if rated_A:
        out["i2_over_in"] = round(abs(i2) / math.sqrt(2) / rated_A, 6)
    # 고조파 점검: 2·f0 … 5·f0 성분 비율 (기본파 대비) — 전부 ~0 이어야 한다
    harm = {}
    for h in (2, 3, 5):
        harm[f"h{h}_over_h1"] = round(abs(fundamental_phasor(I[0], fs, f0 * h)) / max(abs(ph[0]), 1e-12), 6)
    out["harmonics_A"] = harm
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--f0", type=float, default=60.0)
    ap.add_argument("--rated", type=float, default=None)
    a = ap.parse_args()
    print(json.dumps(analyze(a.csv, a.f0, a.rated), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
