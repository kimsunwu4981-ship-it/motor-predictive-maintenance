# -*- coding: utf-8 -*-
"""plot_engine.py — Phase 1 검증 그래프 생성 (Isaac Sim 불필요).

실행:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\5.2\\python\\bin\\python.exe" tools/plot_engine.py
출력: docs/screenshots/p1_thermal.png, p1_current.png, p1_scenario.png
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

from engine.current_model import CurrentModel          # noqa: E402
from engine.scenario_player import ScenarioPlayer      # noqa: E402
from engine.thermal_model import ThermalModel          # noqa: E402

# 한글 폰트 (Windows 기본)
for font in ("Malgun Gothic", "맑은 고딕", "Gulim"):
    try:
        matplotlib.rcParams["font.family"] = font
        break
    except Exception:
        continue
matplotlib.rcParams["axes.unicode_minus"] = False

STAGE_COLOR = {"normal": "#2ecc71", "caution": "#f1c40f", "warning": "#e67e22", "danger": "#e74c3c"}


def plot_thermal() -> str:
    """정상 운전 → 베어링 결함 주입 → 해제 시나리오의 부품 온도."""
    m = ThermalModel()
    dt, total_min = 2.0, 120
    t_hist, T_hist = [], []
    keys = ["winding", "rotor", "bearing_de", "bearing_nde", "endshield_de", "frame"]
    fault_on, fault_off = 40 * 60, 80 * 60      # 40분에 주입, 80분에 해제

    t = 0.0
    while t < total_min * 60:
        faults = ["bearing_de_fault"] if fault_on <= t < fault_off else []
        st = m.step(dt_sim_s=dt, load=1.0, faults=faults, use_duty_cycle=False)
        t_hist.append(t / 60.0)
        T_hist.append([st.temperature_C[k] for k in keys])
        t += dt
    T = np.array(T_hist)

    fig, ax = plt.subplots(figsize=(11, 6))
    for i, k in enumerate(keys):
        ax.plot(t_hist, T[:, i], label=f"{m.nodes[m.index[k]].label} ({k})", lw=2)
    ax.axvspan(fault_on / 60, fault_off / 60, color="#e74c3c", alpha=0.08)
    ax.annotate("DE 베어링 결함 주입", xy=(fault_on / 60, 150), xytext=(fault_on / 60 + 3, 158),
                arrowprops=dict(arrowstyle="->", color="#c0392b"), color="#c0392b", fontsize=10)
    ax.annotate("결함 해제", xy=(fault_off / 60, 150), xytext=(fault_off / 60 + 3, 158),
                arrowprops=dict(arrowstyle="->", color="#27ae60"), color="#27ae60", fontsize=10)
    th = m.thresholds("bearing_de")
    ax.axhline(th["caution"], color="#f39c12", ls="--", lw=1, alpha=0.7)
    ax.axhline(th["warning"], color="#e74c3c", ls="--", lw=1, alpha=0.7)
    ax.text(1, th["caution"] + 1.5, "베어링 주의 85°C", color="#f39c12", fontsize=9)
    ax.text(1, th["warning"] + 1.5, "베어링 경고 95°C", color="#e74c3c", fontsize=9)
    ax.set_xlabel("시뮬레이션 시간 [분]")
    ax.set_ylabel("온도 [°C]")
    ax.set_title("모듈 A — 부품별 온도: 정상 운전 → DE 베어링 결함 → 해제 (22 kW 6극, 정격 부하)")
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.grid(alpha=0.3)
    ax.set_ylim(20, 170)
    fig.tight_layout()
    path = os.path.join(OUT, "p1_thermal.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_current() -> str:
    """정상 / ITSC 4턴 / ITSC 12턴 파형과 I₂/I₁."""
    cm = CurrentModel()
    cases = ["healthy", "itsc_4turn", "itsc_12turn"]
    fs = cm.f0 * 512
    t = np.arange(0, 2 / cm.f0, 1 / fs)

    fig, axes = plt.subplots(1, 4, figsize=(17, 4.2), gridspec_kw={"width_ratios": [3, 3, 3, 2]})
    for ax, case in zip(axes[:3], cases):
        I = cm.waveform(t, case)
        st = cm.analyze(t, I, case)
        for k, (lbl, col) in enumerate(zip("ABC", ["#f1c40f", "#3498db", "#9b59b6"])):
            ax.plot(t * 1000, I[k], color=col, lw=1.6, label=f"{lbl}상 {st.rms_A[k]:.1f}A")
        ax.set_title(f"{cm.cases[case]['label']}\nI₂/I₁ = {st.i2_over_i1:.4f}", fontsize=11)
        ax.set_xlabel("시간 [ms]")
        ax.set_ylabel("전류 [A]")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
        ax.set_ylim(-150, 150)

    ax = axes[3]
    vals = [cm.evaluate_case(c).i2_over_i1 for c in cases]
    targets = [cm.cases[c]["target_i2i1"] for c in cases]
    x = np.arange(len(cases))
    ax.bar(x - 0.18, vals, 0.36, label="모델 계산", color="#e74c3c")
    ax.bar(x + 0.18, targets, 0.36, label="기준값", color="#34495e", alpha=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(["정상", "ITSC 4턴", "ITSC 12턴"], fontsize=9)
    ax.set_ylabel("I₂ / I₁")
    ax.set_title("역상/정상 전류비 검증", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    for xi, v in zip(x, vals):
        ax.text(xi - 0.18, v + 0.008, f"{v:.3f}", ha="center", fontsize=8)

    fig.suptitle("모듈 B — 3상 전류와 대칭좌표 (해석식 생성 · 시뮬레이션 기반 추정값)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = os.path.join(OUT, "p1_current.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_scenario() -> str:
    """자동 재생 시나리오 전 구간: 온도 + I₂/I₁ + 단계 자막."""
    sp, cm, tm = ScenarioPlayer(), CurrentModel(), ThermalModel()
    sp.start()
    dt_wall = 1.0 / 15.0
    rec = {"t": [], "bearing_de": [], "winding": [], "frame": [], "i2i1": [], "step": []}
    while True:
        f = sp.advance(dt_wall)
        cs = cm.evaluate_case(f.electrical_case)
        pu = cm.winding_current_pu(cs)
        st = tm.step(dt_wall * f.time_scale, f.load, f.thermal_faults, winding_current_pu=pu)
        rec["t"].append(f.total_elapsed_s)
        rec["bearing_de"].append(st.temperature_C["bearing_de"])
        rec["winding"].append(st.temperature_C["winding"])
        rec["frame"].append(st.temperature_C["frame"])
        rec["i2i1"].append(cs.i2_over_i1)
        rec["step"].append(f.step_id)
        if f.finished:
            break

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(rec["t"], rec["bearing_de"], label="DE 베어링", color="#e74c3c", lw=2)
    ax1.plot(rec["t"], rec["winding"], label="고정자 권선", color="#e67e22", lw=2)
    ax1.plot(rec["t"], rec["frame"], label="하우징", color="#3498db", lw=2)
    ax1.axhline(95, color="#e74c3c", ls="--", lw=1, alpha=0.6)
    ax1.axhline(120, color="#8e44ad", ls="--", lw=1, alpha=0.6)
    ax1.text(1, 97, "베어링 경고 95°C", color="#e74c3c", fontsize=8)
    ax1.text(1, 122, "권선 주의 120°C", color="#8e44ad", fontsize=8)
    ax1.set_ylabel("온도 [°C]")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(alpha=0.3)
    ax1.set_title("자동 재생 시나리오 (2분 45초) — 발표용 타임라인", fontsize=12)

    ax2.plot(rec["t"], rec["i2i1"], color="#c0392b", lw=2)
    ax2.set_ylabel("I₂ / I₁")
    ax2.set_xlabel("발표 경과 시간 [초]")
    ax2.grid(alpha=0.3)

    # 단계 경계와 라벨
    bounds, prev = [], None
    for t_, s_ in zip(rec["t"], rec["step"]):
        if s_ != prev:
            bounds.append((t_, s_))
            prev = s_
    for i, (tb, sid) in enumerate(bounds):
        for ax in (ax1, ax2):
            ax.axvline(tb, color="#7f8c8d", ls=":", lw=1)
        label = next(s["label"] for s in sp.steps if s["id"] == sid)
        ax1.text(tb + 1, ax1.get_ylim()[1] * 0.93, label, fontsize=8, color="#2c3e50", rotation=0)

    fig.tight_layout()
    path = os.path.join(OUT, "p1_scenario.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


if __name__ == "__main__":
    for fn in (plot_thermal, plot_current, plot_scenario):
        p = fn()
        print("saved:", p, os.path.getsize(p), "bytes")
