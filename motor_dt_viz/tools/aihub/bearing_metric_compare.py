# -*- coding: utf-8 -*-
"""bearing_metric_compare.py — 베어링 지표 후보 3종 비교 (사용자 결정 1번 자료, 2026-10-08).

  python -I -X utf8 tools/aihub/bearing_metric_compare.py [--per-group 2000]

같은 모터에 정상·베어링불량이 모두 있는 4대(M1 L-SF-04, M2 L-SF-02, M3 L-PAC-01, M4 R-CAHU-01S)에서, 모터별 최대 N개씩 뽑아
  (a) env_bpfo_ratio  현재 정의: 포락선 스펙트럼 BPFO ±3 % 피크 ÷ 주변 ±25 Hz 바닥(중앙값)
  (b) kurtosis         가속도 시계열 첨도 (정상 ≈3)
  (c) env_bpfo_corr    고조파 보정: 포락선 스펙트럼에서 회전 주파수 고조파 k·fr(±2 %)와 전원 2f(120 Hz) 고조파 빈을 제외한 뒤
                       BPFO ±3 % 피크 ÷ 같은 제외 적용 바닥. BPFO 창 전체가 고조파에 겹치면 NaN. BPFO 2× 창도 보고 큰 쪽을 쓴다.
를 계산해 분포(중앙값·95 %), ROC AUC(정상 0 / 불량 1, Mann-Whitney), 현재 경계(경고 2배 / 위험 5배) 기준 오탐(정상이 경고 이상)·미탐(불량이 경고 미만)률을
docs/aihub_bearing_metric_comparison.md 와 docs/aihub_plots/bearing_metric_compare.png 로 낸다. config 는 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

for _p in (os.environ.get("VIGENT_PYMODS"), r"C:\Temp\pymods"):
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

import extract_features as ef  # noqa: E402
import run_pipeline as rp  # noqa: E402

VIZ = Path(__file__).resolve().parents[2]
FAULT_MOTORS = {"M1": "L-SF-04", "M2": "L-SF-02", "M3": "L-PAC-01", "M4": "R-CAHU-01S"}   # 가이드라인: 그리스 제거 / 외륜 소손 / 그리스 제거 / 내륜 소손
FAULT_SIM = {"L-SF-04": "그리스 제거", "L-SF-02": "외륜 소손", "L-PAC-01": "그리스 제거", "R-CAHU-01S": "내륜 소손"}
WARN, DANGER = 2.0, 5.0            # config/thresholds.yaml bearing_index (읽기만)


def auc_mw(neg: np.ndarray, pos: np.ndarray) -> float:
    """ROC AUC = Mann-Whitney U / (n0·n1)."""
    x = np.concatenate([neg, pos]); r = rankdata(x)
    return float((r[len(neg):].sum() - len(pos) * (len(pos) + 1) / 2) / (len(neg) * len(pos)))


def env_corr(x: np.ndarray, fs: float, fr: float, bpfo_mult: float, line_hz: float = 60.0) -> float:
    f, a = ef.envelope_spectrum(x, fs)
    mask = np.ones_like(f, dtype=bool)
    for k in range(1, 40):                                   # 회전 고조파 ±2 %
        mask &= ~((f >= k * fr * 0.98) & (f <= k * fr * 1.02))
    for k in range(1, 10):                                   # 전원 2f 고조파 (120, 240 …) ±1 Hz
        mask &= ~(np.abs(f - 2 * line_hz * k) <= 1.0)
    best = float("nan")
    for mult in (1, 2):
        f0 = mult * bpfo_mult * fr
        pk = (f >= f0 * 0.97) & (f <= f0 * 1.03) & mask
        nb = (f >= f0 - 25) & (f <= f0 + 25) & ~((f >= f0 * 0.97) & (f <= f0 * 1.03)) & mask
        if not pk.any() or nb.sum() < 5:
            continue
        floor = float(np.median(a[nb]))
        v = float(a[pk].max() / floor) if floor > 0 else float("nan")
        best = v if np.isnan(best) else max(best, v)
    return best


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--per-group", type=int, default=2000); a = ap.parse_args()
    DATA = rp.DATA
    feat = pd.read_parquet(DATA / "L3" / "features.parquet", columns=["file_id", "motor_id", "aihub_motor_name", "label", "label_no", "signal", "sample_rate", "fr_hz", "rms", "kurtosis", "env_bpfo_ratio", "vel_rms_mm_s"])
    feat = feat[feat["signal"] == "vibration"]
    rng = np.random.default_rng(42)
    rows = []
    t0 = time.time()
    for mid, fm in FAULT_MOTORS.items():
        bm = ef.bearing_mults(fm, "de")
        sub = feat[(feat["aihub_motor_name"] == fm) & (feat["label_no"].isin(["00", "01"]))]
        for lab, g in sub.groupby("label_no"):
            take = g.sample(n=min(a.per_group, len(g)), random_state=int(rng.integers(1e6)))
            for r in take.itertuples():
                t = pq.read_table(DATA / "L2" / "full" / "waveforms" / "vibration" / f"{r.file_id}.parquet").to_pandas()
                x = t["ch1"].to_numpy(np.float64)
                rows.append({"motor_id": mid, "motor": fm, "label_no": lab, "file_id": r.file_id, "rms": r.rms,
                             "env_bpfo_ratio": r.env_bpfo_ratio, "kurtosis": r.kurtosis,
                             "env_bpfo_corr": env_corr(x, float(r.sample_rate), float(r.fr_hz), bm[0]) if bm else float("nan")})
        print(f"[compare] {mid} {fm}: {len(sub)} 후보 → {sum(1 for q in rows if q['motor'] == fm)}  {time.time() - t0:.0f} s", flush=True)
    d = pd.DataFrame(rows)
    d = d[d["rms"] > 0.0005]                                  # 정지 상태 파일 제외
    out = DATA / "L3" / "bearing_metric_compare.parquet"; d.to_parquet(out, index=False)

    metrics = [("env_bpfo_ratio", "현재 포락선 배율"), ("kurtosis", "kurtosis"), ("env_bpfo_corr", "고조파 보정 포락선 배율")]
    L = ["# 베어링 지표 후보 비교 — 정상 vs 베어링불량 (같은 모터, AI Hub 전체 데이터)", "",
         f"- 파일: 모터·라벨당 최대 {a.per_group}개 무작위(시드 42), 정지 상태(가속도 RMS ≤ 0.0005 g) 제외. 총 {len(d):,}개. 산출: `{out}`.",
         "- 결함 모의(가이드라인): L-SF-04·L-PAC-01 **그리스 제거**, L-SF-02 **외륜 소손**, R-CAHU-01S **내륜 소손**. 포락선 배율은 BPFO(외륜) 기준이라 내륜 소손(R-CAHU-01S)은 BPFI 가 더 맞는 지표인데, 비교의 일관성을 위해 세 지표 모두 같은 정의로 냈다.",
         "- 현재 경계(`config/thresholds.yaml bearing_index`): 경고 2배 / 위험 5배. 오탐 = 정상 파일 중 경고 이상(≥2) 또는 위험(≥5) 비율, 미탐 = 불량 파일 중 경고 미만(<2) 비율. kurtosis 는 경계가 없어 같은 숫자(2/5)를 적용하면 의미가 없으므로 **정상 95 % 값을 경고, 99 % 값을 위험으로 둔 가상 경계**로 같이 냈다.",
         "- AUC: 정상 0 / 불량 1 의 ROC AUC (Mann-Whitney). 0.5 = 구분 못 함, 1.0 = 완전 분리.", ""]
    L += ["## 1. 분포 (중앙값 / 95 %)", "", "| 모터 | n 정상/불량 | " + " | ".join(f"{nm} 정상 → 불량" for _, nm in metrics) + " |", "|---|---|" + "---|" * len(metrics)]
    for mid, fm in FAULT_MOTORS.items():
        g = d[d["motor"] == fm]; n0 = g[g["label_no"] == "00"]; n1 = g[g["label_no"] == "01"]
        cells = []
        for col, _ in metrics:
            x0, x1 = n0[col].dropna(), n1[col].dropna()
            cells.append(f"{x0.median():.2f} ({x0.quantile(.95):.2f}) → {x1.median():.2f} ({x1.quantile(.95):.2f})")
        L.append(f"| {mid} {fm} ({FAULT_SIM[fm]}) | {len(n0)}/{len(n1)} | " + " | ".join(cells) + " |")
    L += ["", "## 2. AUC", "", "| 모터 | " + " | ".join(nm for _, nm in metrics) + " |", "|---|" + "---|" * len(metrics)]
    aucs = {}
    for mid, fm in FAULT_MOTORS.items():
        g = d[d["motor"] == fm]; cells = []
        for col, _ in metrics:
            x0 = g[(g["label_no"] == "00")][col].dropna().to_numpy(); x1 = g[(g["label_no"] == "01")][col].dropna().to_numpy()
            v = auc_mw(x0, x1) if len(x0) and len(x1) else float("nan"); aucs[(fm, col)] = v
            cells.append(f"{v:.3f}")
        L.append(f"| {mid} {fm} ({FAULT_SIM[fm]}) | " + " | ".join(cells) + " |")
    g0 = d[d["label_no"] == "00"]; g1 = d[d["label_no"] == "01"]
    L.append("| 4대 합산 | " + " | ".join(f"{auc_mw(g0[c].dropna().to_numpy(), g1[c].dropna().to_numpy()):.3f}" for c, _ in metrics) + " |")
    L += ["", "## 3. 현재 경계(경고 2배 / 위험 5배) 기준 오탐·미탐 — 포락선 배율 2종", "",
          "| 모터 | 지표 | 정상 ≥2 (오탐, 경고) | 정상 ≥5 (오탐, 위험) | 불량 <2 (미탐) | 불량 ≥5 (위험 탐지) |", "|---|---|---|---|---|---|"]
    for mid, fm in FAULT_MOTORS.items():
        g = d[d["motor"] == fm]; n0 = g[g["label_no"] == "00"]; n1 = g[g["label_no"] == "01"]
        for col, nm in metrics:
            if col == "kurtosis": continue
            x0, x1 = n0[col].dropna(), n1[col].dropna()
            L.append(f"| {mid} {fm} | {nm} | {(x0 >= WARN).mean():.0%} | {(x0 >= DANGER).mean():.0%} | {(x1 < WARN).mean():.0%} | {(x1 >= DANGER).mean():.0%} |")
    L += ["", "## 4. kurtosis — 정상 95 %/99 % 를 경계로 둘 때 (가상 경계)", "",
          "| 모터 | 정상 95 % (경고 가정) | 정상 99 % (위험 가정) | 정상 오탐(≥95 %) | 불량 미탐(<95 %) | 불량 ≥99 % | 참고: kurtosis 4 고정 시 오탐 / 미탐 |", "|---|---|---|---|---|---|---|"]
    for mid, fm in FAULT_MOTORS.items():
        g = d[d["motor"] == fm]; x0 = g[g["label_no"] == "00"]["kurtosis"].dropna(); x1 = g[g["label_no"] == "01"]["kurtosis"].dropna()
        q95, q99 = x0.quantile(.95), x0.quantile(.99)
        L.append(f"| {mid} {fm} | {q95:.2f} | {q99:.2f} | {(x0 >= q95).mean():.0%} | {(x1 < q95).mean():.0%} | {(x1 >= q99).mean():.0%} | {(x0 >= 4).mean():.0%} / {(x1 < 4).mean():.0%} |")
    L += ["", "## 5. 읽는 법", "",
          "- 소손(L-SF-02, R-CAHU-01S)은 세 지표 모두 AUC ≈ 1 에 가깝다 — 어느 정의든 잡힌다. 차이는 **정상에서의 오탐**이다: 현재 포락선 배율은 정상에서도 2배를 자주 넘는다.",
          "- 그리스 제거(L-SF-04, L-PAC-01)는 AUC 가 0.5~0.7 에 머문다 — 진동 지표로는 거의 구분되지 않는다 (가이드라인 라벨 자체가 모터별 RMS 경계로 붙은 것).",
          "- 고조파 보정은 '정상 오탐' 을 얼마나 줄이는지로 본다. 줄지 않으면 BPFO 기하(카탈로그 추정)가 틀렸거나 포락선 대역(500~1,600 Hz)이 이 센서·팬에 맞지 않는 것이다.",
          "", "그림: `docs/aihub_plots/bearing_metric_compare.png` (모터별 정상/불량 분포, 로그축)"]
    (VIZ / "docs" / "aihub_bearing_metric_comparison.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    for ax, (col, nm) in zip(axes, metrics):
        data, labels = [], []
        for mid, fm in FAULT_MOTORS.items():
            g = d[d["motor"] == fm]
            for lab, tag in (("00", "정상"), ("01", "불량")):
                data.append(g[g["label_no"] == lab][col].dropna().clip(lower=1e-3)); labels.append(f"{mid}\n{tag}")
        ax.boxplot(data, tick_labels=labels, showfliers=False); ax.set_yscale("log"); ax.set_title(nm); ax.tick_params(axis="x", labelsize=8)
        if col != "kurtosis":
            ax.axhline(WARN, ls="--", lw=.8, color="orange"); ax.axhline(DANGER, ls="--", lw=.8, color="red")
    fig.suptitle("베어링 지표 후보 — 같은 모터의 정상 vs 베어링불량 (AI Hub 전체 데이터, 모터·라벨당 ≤2,000개, 로그축; 점선 = 현재 경계 2/5배)")
    fig.tight_layout(); fig.savefig(VIZ / "docs" / "aihub_plots" / "bearing_metric_compare.png", dpi=110); plt.close(fig)
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
