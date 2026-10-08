# -*- coding: utf-8 -*-
"""extract_features.py — L2 Parquet → 파일·채널당 1행 특징 테이블 (TASK_AIHub_샘플 S2) + 참고용 그림·요약 (S3).

  python -I tools/aihub/extract_features.py --l2 data/aihub/sample/L2 --l3 data/aihub/sample/L3 [--plots docs/aihub_sample_plots] [--summary docs/aihub_sample_summary.md]

파라미터는 config/aihub_features.yaml 에서만 읽는다. 베어링 번호가 어노테이션에 없으므로 env_bpfo_ratio·env_bpfi_ratio 는 NaN,
bearing_known=False 다 — 우리 모터(M1~M5)의 베어링 값으로 대신 계산하지 않는다.

단위 변환 (vel_rms_mm_s):
  accel_unit = g      : a[m/s²] = x · 9.80665
  accel_unit = m/s2   : a = x
  accel_unit = mm/s   : 이미 속도 → 대역통과만
  속도 = 대역통과(10~1,000 Hz)한 가속도를 주파수 영역에서 적분 (A(f) / (j·2π·f)), m/s → ×1000 mm/s. 단위가 설명서로 확정되기 전까지 "g 추정" 라벨.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import yaml  # noqa: E402
from scipy import signal as sg  # noqa: E402
from scipy.stats import kurtosis  # noqa: E402

VIZ = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load(open(VIZ / "config" / "aihub_features.yaml", encoding="utf-8"))
FMT = yaml.safe_load(open(VIZ / "config" / "aihub_format.yaml", encoding="utf-8"))
BRG = yaml.safe_load(open(VIZ / "config" / "aihub_bearings.yaml", encoding="utf-8")) if (VIZ / "config" / "aihub_bearings.yaml").exists() else {"geometry": {}, "motors": {}}


def bearing_mults(motor_name: str, side: str = "de") -> tuple[float, float, str] | None:
    """가이드라인 표의 모터별 베어링 → (BPFO/fr, BPFI/fr, 호칭). 없으면 None (우리 M1~M5 값으로 대신하지 않는다)."""
    m = BRG["motors"].get(motor_name)
    if not m:
        return None
    g = BRG["geometry"].get(str(m[side]))
    if not g:
        return None
    import math
    k = g["ball_d_mm"] / g["pitch_d_mm"] * math.cos(math.radians(g.get("contact_deg", 0)))
    return g["n_balls"] / 2 * (1 - k), g["n_balls"] / 2 * (1 + k), str(m[side])


def envelope_ratio(f: np.ndarray, amp: np.ndarray, f0: float) -> float:
    """포락선 스펙트럼에서 f0 ±tol 피크 ÷ 주변(±noise_window, 피크 영역 제외) 중앙값."""
    tol = CFG.get("envelope_peak_tolerance", 0.03); w = CFG.get("envelope_noise_window_hz", 25)
    pk = (f >= f0 * (1 - tol)) & (f <= f0 * (1 + tol))
    nb = (f >= f0 - w) & (f <= f0 + w) & ~pk
    if not pk.any() or nb.sum() < 5:
        return float("nan")
    floor = float(np.median(amp[nb]))
    return float(amp[pk].max() / floor) if floor > 0 else float("nan")


# ------------------------------------------------------------------ 신호 처리
def amplitude_spectrum(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Hann 창 진폭 스펙트럼 (사인 진폭 복원 스케일)."""
    n = len(x)
    w = np.hanning(n)
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(n, 1 / fs)
    return f, np.abs(X) * 2 / w.sum()


def bandpass(x: np.ndarray, fs: float, lo: float, hi: float | None, order: int = 4) -> np.ndarray:
    nyq = fs / 2
    hi = min(hi if hi else nyq * 0.98, nyq * 0.98)
    lo = max(lo, 0.5)
    sos = sg.butter(order, [lo / nyq, hi / nyq], btype="band", output="sos")
    return sg.sosfiltfilt(sos, x - x.mean())


def velocity_rms_mm_s(x: np.ndarray, fs: float) -> float:
    unit = CFG["accel_unit"]
    lo, hi = CFG["velocity_band_hz"]
    if unit == "mm/s":
        return float(np.sqrt(np.mean(bandpass(x, fs, lo, hi) ** 2)))
    a = x * (CFG["g_to_m_s2"] if unit == "g" else 1.0)
    a = bandpass(a, fs, lo, hi)
    n = len(a)
    A = np.fft.rfft(a)
    f = np.fft.rfftfreq(n, 1 / fs)
    V = np.zeros_like(A)
    m = (f >= lo) & (f <= hi)
    V[m] = A[m] / (1j * 2 * np.pi * f[m])
    v = np.fft.irfft(V, n)
    return float(np.sqrt(np.mean(v ** 2)) * 1000.0)


def peak_near(f: np.ndarray, amp: np.ndarray, f0: float, tol: float) -> float:
    m = (f >= f0 * (1 - tol)) & (f <= f0 * (1 + tol))
    return float(amp[m].max()) if m.any() else float("nan")


def envelope_spectrum(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = CFG["envelope_band_hz"]
    hi = min(hi, fs * CFG["envelope_max_fs_fraction"])
    b = bandpass(x, fs, lo, hi)
    env = np.abs(sg.hilbert(b))
    return amplitude_spectrum(env, fs)


def band_rms(x: np.ndarray, fs: float, lo: float, hi: float | None) -> float:
    f, P = sg.welch(x - x.mean(), fs, nperseg=min(len(x), 2048))
    hi = hi if hi else fs / 2
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(np.trapezoid(P[m], f[m]))) if m.sum() > 1 else float("nan")


def fundamental_phasors(chs: list[np.ndarray], fs: float, f0_nominal: float) -> tuple[list[complex], float]:
    """기본파 페이저: ch1 스펙트럼 피크(포물선 보간)로 실제 기본 주파수를 잡고, 그 주파수의 sin/cos 최소자승으로 각 채널 페이저를 구한다
    (1 s 창의 1 Hz 분해능에서 59.8 Hz 같은 어긋남이 FFT 빈 누설로 I₂/I₁ 을 망치지 않게)."""
    n = len(chs[0]); t = np.arange(n) / fs
    f = np.fft.rfftfreq(n, 1 / fs); X = np.abs(np.fft.rfft((chs[0] - chs[0].mean()) * np.hanning(n)))
    m = (f > 0.8 * f0_nominal) & (f < 1.2 * f0_nominal); k = int(np.argmax(np.where(m, X, 0)))
    if 0 < k < len(X) - 1:
        a, b, c = X[k - 1], X[k], X[k + 1]; d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    else:
        d = 0.0
    f0 = float(f[k] + d * (f[1] - f[0]))
    M = np.column_stack([np.cos(2 * np.pi * f0 * t), np.sin(2 * np.pi * f0 * t)])
    ph = []
    for c in chs:
        co, si = np.linalg.lstsq(M, c - c.mean(), rcond=None)[0]
        ph.append(complex(co, -si))                           # x = Re(P·e^{jωt}) 꼴의 페이저
    return ph, f0


def i2_over_i1(chs: list[np.ndarray], fs: float, f0: float) -> tuple[float, str, float]:
    """3상 전류의 역상/정상 성분비 (참고 계산, 2차 작업 범위 판단용). 채널 순서가 역상(ACB)이면 |I₂|>|I₁| 로 나오므로
    둘 중 큰 쪽을 정상분으로 보고 phase_sequence 에 'acb' 를 기록한다."""
    if len(chs) != 3:
        return float("nan"), "", float("nan")
    ph, f_est = fundamental_phasors(chs, fs, f0)
    a = np.exp(2j * np.pi / 3)
    i1 = (ph[0] + a * ph[1] + a * a * ph[2]) / 3
    i2 = (ph[0] + a * a * ph[1] + a * ph[2]) / 3
    seq = "abc" if abs(i1) >= abs(i2) else "acb"
    big, small = (abs(i1), abs(i2)) if seq == "abc" else (abs(i2), abs(i1))
    return (float(small / big) if big > 0 else float("nan")), seq, f_est


def features_for_file(r: pd.Series, l2: Path) -> list[dict]:
    t = pq.read_table(l2 / "waveforms" / r["signal"] / f"{r['file_id']}.parquet").to_pandas()
    fs = float(r["sample_rate"])
    chans = [c for c in t.columns if c.startswith("ch")]
    chcfg = FMT["channels"][r["signal"]]
    unit = chcfg["unit"]
    fr = r["rated_rpm"] / 60.0 if np.isfinite(r["rated_rpm"]) and r["rated_rpm"] > 0 else float("nan")
    fr_source = "annotation_rpm"
    out = []
    i2i1, seq, f_fund = i2_over_i1([t[c].to_numpy(np.float64) for c in chans], fs, CFG["current_fundamental_hz"]) if r["signal"] == "current" else (float("nan"), "", float("nan"))
    for ci, c in enumerate(chans):
        x = t[c].to_numpy(np.float64)
        xc = x - x.mean()
        rms = float(np.sqrt(np.mean(xc ** 2)))
        peak = float(np.abs(xc).max())
        f, amp = amplitude_spectrum(x, fs)
        fr_use = fr
        if not np.isfinite(fr_use):
            lo, hi = CFG["fr_search_hz"]; m = (f >= lo) & (f <= hi); fr_use = float(f[m][np.argmax(amp[m])]); fr_source = "peak_search"
        tol = CFG["harmonic_tolerance"]
        # 베어링 포락선 배율: 가이드라인 표의 베어링(DE·NDE)이 있을 때만. 진동 신호만 (전류는 NaN)
        env_cols = {"env_bpfo_ratio": float("nan"), "env_bpfi_ratio": float("nan"), "env_bpfo_ratio_nde": float("nan"), "env_bpfi_ratio_nde": float("nan"),
                    "bearing_known": False, "bearing_de": "", "bearing_nde": "", "bpfo_hz": float("nan"), "bpfi_hz": float("nan"), "bearing_source": ""}
        bm = bearing_mults(str(r["aihub_motor_name"]), "de") if r["signal"] == "vibration" else None
        if bm and np.isfinite(fr):
            fe, ae = envelope_spectrum(x, fs)
            env_cols.update({"env_bpfo_ratio": envelope_ratio(fe, ae, bm[0] * fr), "env_bpfi_ratio": envelope_ratio(fe, ae, bm[1] * fr),
                             "bearing_known": True, "bearing_de": bm[2], "bpfo_hz": bm[0] * fr, "bpfi_hz": bm[1] * fr,
                             "bearing_source": "guideline table + catalog geometry (estimated)"})
            bn = bearing_mults(str(r["aihub_motor_name"]), "nde")
            if bn:
                env_cols.update({"env_bpfo_ratio_nde": envelope_ratio(fe, ae, bn[0] * fr), "env_bpfi_ratio_nde": envelope_ratio(fe, ae, bn[1] * fr), "bearing_nde": bn[2]})
        lo_s, hi_s = CFG["fr_search_hz"]; ms = (f >= lo_s) & (f <= hi_s)
        fr_peak = float(f[ms][np.argmax(amp[ms])]) if ms.any() else float("nan")   # 1× 피크 탐색값 — 어노테이션 rpm 과 다르면 인버터 구동 의심
        row = {
            "file_id": r["file_id"], "motor_id": r["motor_id"], "power_kw": r["power_kw"], "aihub_motor_name": r["aihub_motor_name"],
            "label": r["label"], "label_no": r["label_no"], "signal": r["signal"], "sensor_id": r["sensor_id"], "date": r["date"],
            "channel": c, "channel_dir": chcfg["dir"][ci], "unit": unit, "sample_rate": fs, "n_samples": len(x),
            "rms": rms, "peak": peak, "crest_factor": peak / rms if rms > 0 else float("nan"), "kurtosis": float(kurtosis(xc, fisher=False)),
            "vel_rms_mm_s": velocity_rms_mm_s(x, fs) if r["signal"] == "vibration" else float("nan"),
            "vel_unit_note": f"accel_unit={CFG['accel_unit']} (추정)" if r["signal"] == "vibration" else "",
            "fr_hz": fr_use, "fr_source": fr_source, "fr_peak_hz": fr_peak,
            "a_1x": peak_near(f, amp, fr_use, tol), "a_2x": peak_near(f, amp, 2 * fr_use, tol), "a_3x": peak_near(f, amp, 3 * fr_use, tol),
            **env_cols,
            "band_lo": band_rms(x, fs, *CFG["bands_hz"]["lo"]), "band_mid": band_rms(x, fs, *CFG["bands_hz"]["mid"]), "band_hi": band_rms(x, fs, *CFG["bands_hz"]["hi"]),
            "clipping_ratio": float(np.mean(np.abs(x) >= CFG["clipping_top_fraction"] * np.abs(x).max())) if np.abs(x).max() > 0 else 0.0,
            "dc_offset": float(x.mean()), "nan_count": int(np.isnan(x).sum()),
            "i2i1_ref": i2i1, "phase_sequence": seq, "fund_hz": f_fund,
            # 전류: 정격 대비 부하율과 운전 여부 (정지 상태 파일은 기본파·I₂/I₁ 이 잡음) — 진동은 NaN/True
            "load_ratio": (rms / r["rated_current"]) if (r["signal"] == "current" and np.isfinite(r["rated_current"]) and r["rated_current"] > 0) else float("nan"),
            "running": bool(rms / r["rated_current"] >= CFG.get("running_min_load_ratio", 0.1)) if (r["signal"] == "current" and np.isfinite(r["rated_current"]) and r["rated_current"] > 0) else True,
        }
        out.append(row)
    return out


# ------------------------------------------------------------------ 그림·요약 (참고용)
def make_plots(feat: pd.DataFrame, meta: pd.DataFrame, l2: Path, plots: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    plots.mkdir(parents=True, exist_ok=True)
    made = []
    vib = meta[meta["signal"] == "vibration"]
    TAG = "샘플 데이터, 참고용"

    def mean_spec(rows: pd.DataFrame, fn, n=20):
        acc = None
        for _, r in rows.head(n).iterrows():
            x = pq.read_table(l2 / "waveforms" / r["signal"] / f"{r['file_id']}.parquet").to_pandas()["ch1"].to_numpy(np.float64)
            f, a = fn(x, float(r["sample_rate"]))
            acc = a if acc is None else acc + a
        return f, acc / min(n, len(rows))

    # ① 정상 vs 베어링불량 포락선 스펙트럼 (같은 모터)
    brg = vib[vib["label_no"] == "01"]
    if len(brg):
        m = brg["aihub_motor_name"].iloc[0]
        nor = vib[(vib["aihub_motor_name"] == m) & (vib["label_no"] == "00")]
        fig, ax = plt.subplots(figsize=(10, 4))
        for rows, lab in ((nor, "정상"), (brg, "베어링불량")):
            if len(rows):
                f, a = mean_spec(rows, envelope_spectrum); ax.plot(f, a, lw=.9, label=f"{lab} (n={min(20, len(rows))} 평균)")
        fr = brg["rated_rpm"].iloc[0] / 60
        for k in (1, 2, 3): ax.axvline(k * fr, color="gray", ls=":", lw=.8)
        ax.set_xlim(0, 400); ax.set_xlabel("Hz"); ax.set_ylabel("포락선 진폭 (원 단위)"); ax.legend()
        bm = bearing_mults(str(m), "de")
        if bm:
            for mult, nm in ((bm[0], "BPFO"), (bm[1], "BPFI")):
                ax.axvline(mult * fr, color="crimson", ls="--", lw=.9); ax.text(mult * fr, ax.get_ylim()[1] * .85, f"{nm} {mult*fr:.0f} Hz", color="crimson", fontsize=8)
        ax.set_title(f"① 포락선 스펙트럼 — {m} ({brg['power_kw'].iloc[0]} kW) 정상 vs 베어링불량 · 대역 {CFG['envelope_band_hz']} Hz · 베어링 {bm[2] if bm else '미상'} (가이드라인 표) — {TAG}")
        p = plots / "01_envelope_normal_vs_bearing.png"; fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig); made.append(p.name)
    # ② 정상 vs 축정렬불량 속도 스펙트럼 1×·2×
    mis = vib[vib["label_no"] == "03"]
    if len(mis):
        m = mis["aihub_motor_name"].iloc[0]
        nor = vib[(vib["aihub_motor_name"] == m) & (vib["label_no"] == "00")]
        fig, ax = plt.subplots(figsize=(10, 4))

        def vel_spec(x, fs):
            a = x * (CFG["g_to_m_s2"] if CFG["accel_unit"] == "g" else 1.0)
            f, A = amplitude_spectrum(a, fs)
            with np.errstate(divide="ignore"):
                V = np.where(f > 0, A / (2 * np.pi * np.maximum(f, 1e-9)) * 1000, 0.0)
            return f, V
        for rows, lab in ((nor, "정상"), (mis, "축정렬불량")):
            if len(rows):
                f, a = mean_spec(rows, vel_spec); ax.plot(f, a, lw=.9, label=f"{lab} (n={min(20, len(rows))} 평균)")
        fr = mis["rated_rpm"].iloc[0] / 60
        for k, nm in ((1, "1×"), (2, "2×"), (3, "3×")): ax.axvline(k * fr, color="gray", ls=":", lw=.8); ax.text(k * fr, ax.get_ylim()[1] * .9, nm, color="gray")
        ax.set_xlim(5, 200); ax.set_xlabel("Hz"); ax.set_ylabel("속도 진폭 mm/s (가속도 g 추정 → 적분)"); ax.legend()
        ax.set_title(f"② 속도 스펙트럼 1×·2× — {m} 정상 vs 축정렬불량 (fr={fr:.1f} Hz) — {TAG}")
        p = plots / "02_velocity_spectrum_normal_vs_misalignment.png"; fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig); made.append(p.name)
    # ③ 용량·라벨별 vel_rms 박스플롯
    fv = feat[feat["signal"] == "vibration"].copy()
    if len(fv):
        fv["grp"] = fv["power_kw"].astype(str) + " kW · " + fv["label"]
        order = sorted(fv["grp"].unique())
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.boxplot([fv[fv["grp"] == g]["vel_rms_mm_s"].dropna() for g in order], tick_labels=order, showfliers=True)
        for y, lab in ((1.8, "10816-1 Class I 경고 1.8"), (1.4, "20816-3 경고 1.4"), (4.5, "위험 4.5")):
            ax.axhline(y, ls="--", lw=.8, color="gray"); ax.text(0.5, y, lab, fontsize=8, color="gray", va="bottom")
        ax.set_ylabel("속도 RMS mm/s (10~1000 Hz, g 추정)"); ax.tick_params(axis="x", labelsize=8)
        ax.set_title(f"③ 용량·라벨별 속도 RMS — {TAG} (단위 미확정, 임계값 보정에 쓰지 않음)")
        p = plots / "03_vel_rms_box_by_power_label.png"; fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig); made.append(p.name)
    return made


def write_summary(feat: pd.DataFrame, meta: pd.DataFrame, report: dict, path: Path, plots: list[str]):
    fv = feat[feat["signal"] == "vibration"]
    fc = feat[feat["signal"] == "current"]
    L = ["# AI Hub 경량 샘플 특징 요약 (S3) — 참고용", "",
         "**경량 샘플 기준 참고값. 표본이 적고 원본과 다를 수 있어 임계값 보정에 사용하지 않는다.** "
         "진동 단위 g 는 가이드라인 v2.4 로 확정. 베어링 배율은 가이드라인 표의 베어링 호칭 + 카탈로그 기하(추정)로 계산한 값이다.", "",
         f"- 입력: L2 {len(meta)} 파일 (진동 {int((meta['signal']=='vibration').sum())}, 전류 {int((meta['signal']=='current').sum())}), 특징 {len(feat)} 행(파일·채널). "
         f"변환 {report.get('s_per_file', 0)*1000:.1f} ms/파일, CSV→Parquet 크기비 ×{report.get('size_ratio', 0)}.", ""]
    L += ["## 1. 용량·라벨별 파일 수와 속도 RMS (진동, mm/s, g 추정)", "",
          "| 용량 | 모터 | 라벨 | 파일 | vel_rms 중앙값 | 최소~최대 | 95 % | 가속도 RMS 중앙값 (원 단위) | crest 중앙값 | 포락선 배율 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for (kw, m, lab), g in fv.groupby(["power_kw", "aihub_motor_name", "label"]):
        v = g["vel_rms_mm_s"]
        eb = g["env_bpfo_ratio"]
        L.append(f"| {kw} | {m} | {lab} | {len(g)} | {v.median():.2f} | {v.min():.2f}~{v.max():.2f} | {v.quantile(.95):.2f} | {g['rms'].median():.4f} | {g['crest_factor'].median():.1f} | " + (f"BPFO {eb.median():.1f} / BPFI {g['env_bpfi_ratio'].median():.1f} ({g['bearing_de'].iloc[0]})" if eb.notna().any() else "베어링 미상") + " |")
    # ISO 위치
    L += ["", "## 2. 현재 임계값과의 대략적 위치 (참고)", ""]
    for kw, g in fv[fv["label_no"] == "00"].groupby("power_kw"):
        med = g["vel_rms_mm_s"].median(); q95 = g["vel_rms_mm_s"].quantile(.95)
        std = "ISO 10816-1 Class I (경고 1.8 / 위험 4.5)" if kw < 15 else "ISO 20816-3 Group 2 (경고 1.4 / 위험 4.5)"
        lim = 1.8 if kw < 15 else 1.4
        L.append(f"- {kw} kW 정상 속도 RMS 중앙값 {med:.2f} mm/s (95 % {q95:.2f}) — 우리 기준 {std} 에서 **대략** 경고 하한의 {med/lim*100:.0f} % 위치 (g 단위 가정).")
    # 1x 2x
    L += ["", "## 3. 회전 성분 (1×·2×, 가속도 원 단위, 모터별 중앙값)", "", "| 모터 | 라벨 | 파일 | fr Hz | a_1x | a_2x | a_2x/a_1x | kurtosis |", "|---|---|---|---|---|---|---|---|"]
    for (m, lab), g in fv.groupby(["aihub_motor_name", "label"]):
        L.append(f"| {m} | {lab} | {len(g)} | {g['fr_hz'].median():.1f} | {g['a_1x'].median():.5f} | {g['a_2x'].median():.5f} | {(g['a_2x']/g['a_1x']).median():.2f} | {g['kurtosis'].median():.1f} |")
    # 전류
    L += ["", "## 4. 전류 (3상 확인 → 2차 작업 범위)", "", "- 3채널 = 3상이므로 I₂/I₁(역상 전류비)·상별 RMS 비율·MCSA 스펙트럼 전부 가능하다. 다만 진동과 동시 측정이 아니라 두 신호를 한 순간으로 묶지는 못한다.", "",
          "| 용량 | 모터 | 라벨 | 파일 | 상 RMS 중앙값 (A, ch1/ch2/ch3) | 정격 대비 | I₂/I₁ 중앙값 (참고) | 채널 상순 | 기본파 Hz |", "|---|---|---|---|---|---|---|---|---|"]
    for (kw, m, lab), g in fc.groupby(["power_kw", "aihub_motor_name", "label"]):
        r = [g[g["channel"] == c]["rms"].median() for c in ("ch1", "ch2", "ch3")]
        rated = meta[meta["aihub_motor_name"] == m]["rated_current"].median()
        L.append(f"| {kw} | {m} | {lab} | {len(g)//3} | {r[0]:.2f} / {r[1]:.2f} / {r[2]:.2f} | {np.mean(r)/rated*100:.0f} % | {g['i2i1_ref'].median():.3f} | {g['phase_sequence'].mode().iloc[0]} | {g['fund_hz'].median():.2f} |")
    n_full = 2_333_172
    L += ["", "## 5. 전체 데이터 도착 시 예상", "",
          f"- 전체 233만 파일 × {report.get('s_per_file', 0)*1000:.1f} ms = 약 {n_full*report.get('s_per_file', 0)/3600:.1f} 시간 (단일 프로세스, SSD). 선별(용량 5종·라벨 3종·진동만, 약 1/5)이면 약 {n_full/5*report.get('s_per_file', 0)/3600:.1f} 시간.",
          f"- Parquet 크기: CSV 대비 ×{report.get('size_ratio', 0)}. 원본 500 GB 가정 시 전체 {500*report.get('size_ratio', 0):.0f} GB, 선별본 약 {100*report.get('size_ratio', 0):.0f} GB.",
          "- 특징 추출은 파일당 수 ms(아래 실측)라 변환보다 짧다.", "",
          "## 6. 발견한 문제·전체 데이터에서 주의할 점", "",
          f"- 길이 불일치 {len(report.get('length_mismatch_files', []))}건, NaN {len(report.get('nan_files', []))}건, 클리핑 의심 {len(report.get('clipping_suspect_files', []))}건, 헤더·폴더 불일치 {len(report.get('header_folder_mismatch', []))}건 (convert_report.json).",
          "- 진동 crest factor > 10 파일이 축정렬불량·불평형에 몰려 있다 — 충격성 성분인지 센서 글리치인지 전체 데이터에서 포락선으로 재확인.",
          "- `L-EF-04` 는 센서ID 에 따라 Motor Spec(rpm·정격전류)이 둘이다. 전체 데이터에서 같은 모터명 아래 사양이 바뀌는 경우를 메타에서 센서ID 로 구분해야 한다.",
          "- 결함 라벨이 모터당 한 종류라 정상 vs 결함 비교는 같은 모터의 정상과만 한다. 학습/검증 분할은 모터 단위로.",
          "- 진동은 1축 vertical(가이드라인). 베어링 호칭은 헤더에 없고 가이드라인 표(모터별)에서 가져왔으며 기하는 카탈로그 추정 → 배율은 참고값.",
          "- 전류 DC 오프셋(−0.02~−0.26 A)은 특징 추출에서 제거했고 dc_offset 열에 남겼다.",
          "- **55 kW 두 대는 인버터 구동**이다 (전류 기본파 49.6 / 57.5 / 50.8 Hz, 모터·라벨마다 다름). 어노테이션 rpm(1760)은 명판값이라 실제 회전수와 다르므로 55 kW 의 fr_hz·a_1x 는 신뢰하지 않는다 — `fr_peak_hz` 열(1× 피크 탐색)과 비교. 2.2 kW 네 대는 60.00 Hz 상용 전원이다.",
          "- **55 kW 전류는 센서 범위 ±82 A 에서 포화**된다 (최대값 81.995 A 가 파일마다 반복, 평탄 구간 최대 17 %). RMS 58 A 면 피크 82 A 를 넘으므로 파형이 잘린다 → 55 kW 전류 특징(THD·고조파)은 쓰지 말 것. 2.2 kW 는 포화 없음.",
          f"- 전류 파일 중 **정지·극저부하(정격의 10 % 미만) {int((~fc[fc['channel']=='ch1']['running']).sum())}건**이 '정상' 라벨로 들어 있다 (L-DSF-01, RMS 0.01~0.75 A). `running=False` 로 표시했고 요약·학습에서 제외해야 한다.",
          "- 전류 채널 순서가 모터마다 다르다 (L-DSF-01·R-EF-05 는 역상 acb). I₂/I₁ 은 큰 성분을 정상분으로 보고 계산했고 `phase_sequence` 열에 남겼다.", "",
          "## 그림 (docs/aihub_sample_plots/)", ""] + [f"- {p}" for p in plots]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l2", default=str(VIZ / "data" / "aihub" / "sample" / "L2"))
    ap.add_argument("--l3", default=str(VIZ / "data" / "aihub" / "sample" / "L3"))
    ap.add_argument("--plots", default=str(VIZ / "docs" / "aihub_sample_plots"))
    ap.add_argument("--summary", default=str(VIZ / "docs" / "aihub_sample_summary.md"))
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args()
    l2, l3 = Path(a.l2), Path(a.l3)
    meta = pd.read_parquet(l2 / "meta.parquet")
    import time
    t0 = time.time()
    rows = []
    for i, (_, r) in enumerate(meta.iterrows()):
        rows.extend(features_for_file(r, l2))
        if (i + 1) % 500 == 0:
            print(f"[features] {i + 1}/{len(meta)}  {time.time() - t0:.1f} s")
    dt = time.time() - t0
    feat = pd.DataFrame(rows)
    l3.mkdir(parents=True, exist_ok=True)
    feat.to_parquet(l3 / "features.parquet", index=False, compression="zstd")
    miss = feat.isna().mean().round(4).to_dict()
    rep_p = l2 / "convert_report.json"
    report = json.load(open(rep_p, encoding="utf-8")) if rep_p.exists() else {}
    json.dump({"rows": len(feat), "files": len(meta), "elapsed_s": round(dt, 1), "s_per_file": round(dt / max(len(meta), 1), 4), "missing_rate": miss},
              open(l3 / "features_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[features] {len(feat)} 행 / {len(meta)} 파일, {dt:.1f} s ({dt / max(len(meta), 1) * 1000:.1f} ms/파일) → {l3 / 'features.parquet'}")
    plots = [] if a.no_plots else make_plots(feat, meta, l2, Path(a.plots))
    write_summary(feat, meta, report, Path(a.summary), plots)
    print(f"[features] 요약 → {a.summary}, 그림 {plots}")


if __name__ == "__main__":
    main()
