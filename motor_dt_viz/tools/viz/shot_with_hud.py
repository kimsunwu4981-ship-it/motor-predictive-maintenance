# -*- coding: utf-8 -*-
"""shot_with_hud.py — HUD 합성 스크린샷 (D3, 2026-10-21): Isaac 뷰포트 캡처에는 omni.ui HUD 가 찍히지 않으므로, 같은 시각의 검증 로그(state.csv) 값으로
HUD 와 같은 내용(상태·I₂/I₁·I₂/I_n·전류·온도·판정·해석 기준 한 줄)을 오버레이로 합성한다. 새 계산 없음 — 값은 전부 demo_integrated 의 엔진 출력(state.csv)이다.

사용 (PowerShell/cmd, motor_dt_viz 에서):
  py -3.12 -X utf8 tools\\viz\\shot_with_hud.py run  --scenario electrical --view full    # Isaac 자동 재생 + 계획된 시각에 캡처 + state.csv → 합성
  py -3.12 -X utf8 tools\\viz\\shot_with_hud.py run  --scenario mechanical --view cutaway
  py -3.12 -X utf8 tools\\viz\\shot_with_hud.py compose --raw logs/hud_shots/electrical --state logs/hud_shots/electrical/state.csv   # 캡처만 있을 때 합성만
  py -3.12 -X utf8 tools\\viz\\shot_with_hud.py all                                        # 전기+기계 10장 → docs/assets/screenshots/M1_hud/ + captions.json
계획(10장): 정상·4턴 fault_focus·8턴·12턴·저항성·반부하 (전기), 베어링 DE·오정렬·과부하·냉각 저하(=팬 고장) (기계). 시각은 scenarios_M1.yaml 장면 중앙 근처.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIZ = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(VIZ, ".."))
sys.path.insert(0, VIZ)
ISAAC_PY = r"C:\ISSACS~1\python.bat"
OUT_DEFAULT = os.path.join(REPO, "docs", "assets", "screenshots", "M1_hud")

# (파일명, 모드, 시각 s, 카메라, 설명) — 시각은 scenarios_M1.yaml 의 장면 안쪽(판정 지속 3 s 뒤)
PLAN = {
    "electrical": [("01_healthy", 12.0, "wide", "정상 (3상 균형, 고유 비대칭만)"), ("02_itsc_4turn_fault_focus", 36.0, "fault_focus", "턴간 단락 4턴 — Coil_01_short 발광, I₂/I₁ 경계"),
                   ("03_itsc_8turn", 178.0, "fault_focus", "턴간 단락 8턴 — 확실 탐지"), ("04_itsc_12turn", 62.0, "fault_focus", "턴간 단락 12턴 — 위험"),
                   ("05_itsc_4turn_resistive", 218.0, "fault_focus", "저항성 4턴 (R_f 1.0 Ω) — 전류로 탐지 불가"), ("06_itsc_4turn_halfload", 238.0, "wide", "반부하 4턴 (50 %)")],
    "mechanical": [("07_bearing_de", 52.0, "bearing_de", "DE 베어링 열화 — kurtosis·진동"), ("08_misalignment", 78.0, "close", "축 정렬 불량 — 양쪽 베어링·축 온도"),
                   ("09_overload", 150.0, "wide", "과부하 (열 관점) — 권선 동손"), ("10_fan_failure", 102.0, "wide", "냉각 저하 (팬 고장) — 하우징·권선 온도")],
}
LEVEL_KO = {"SAFE": "안전", "WARN": "경고", "DANGER": "위험"}


def run(scenario: str, view: str, raw_dir: str, max_s: float | None = None) -> str:
    """Isaac 자동 재생 + --shot_plan 캡처 + --verify_dir 로그. 반환: raw_dir."""
    os.makedirs(raw_dir, exist_ok=True)
    plan = ";".join(f"{t}:{view}:{cam}:{name}_t{t:.1f}.png" for name, t, cam, _ in PLAN[scenario])
    t_end = max(t for _, t, _, _ in PLAN[scenario]) + 3.0 if max_s is None else max_s
    cmd = [ISAAC_PY, r"app\demo_integrated.py", "--gui", "--autoplay", "--mode", scenario, "--motor", "M1", "--view", view,
           "--m1_shots", os.path.relpath(raw_dir, VIZ), "--shot_plan", plan, "--verify_dir", os.path.relpath(raw_dir, VIZ), "--max_s", f"{t_end:.0f}", "--log_subdir", f"hud_{scenario}"]
    print("[shot] " + " ".join(cmd), flush=True)
    with open(os.path.join(raw_dir, "run.txt"), "w", encoding="utf-8", errors="replace") as logf:
        subprocess.run(" ".join(f'"{c}"' if " " in c or ";" in c else c for c in cmd), cwd=VIZ, shell=True, stdout=logf, stderr=subprocess.STDOUT)
    return raw_dir


def compose(raw_dir: str, state_csv: str, out_dir: str, scenario: str) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    rows = list(csv.DictReader(open(state_csv, encoding="utf-8")))
    ref_p = os.path.join(VIZ, "data", "electrical", "analysis_reference.json")
    ref = json.load(open(ref_p, encoding="utf-8")) if os.path.exists(ref_p) else None
    col = {"SAFE": "#26f259", "WARN": "#ff731a", "DANGER": "#ff140d"}
    os.makedirs(out_dir, exist_ok=True); caps = []
    desc = {n: d for n, _, _, d in PLAN[scenario]}
    for png in sorted(glob.glob(os.path.join(raw_dir, "*_t*.png"))):
        m = re.search(r"(\d\d_[a-z0-9_]+)_t([0-9.]+)\.png$", os.path.basename(png))
        if not m:
            continue
        name, t = m.group(1), float(m.group(2))
        r = min(rows, key=lambda x: abs(float(x["t_session_s"]) - t))
        st = r["status"]; mode = r["mode"]
        lines = [f"{LEVEL_KO.get(st, st)} {st}   원인 {r['cause_signal']} {r['cause_value']}   [{r['threshold']}]",
                 f"t = {float(r['t_session_s']):.1f} s   장면 {r['step']}   부하 {r['load']}   {r['rpm']} rpm"]
        if mode in ("electrical", "integrated"):
            lines += [f"I R/S/T = {float(r['Ia_rms']):.2f} / {float(r['Ib_rms']):.2f} / {float(r['Ic_rms']):.2f} A  (정격 4.73 A)   I₁ {float(r['i1_A']):.3f} A",
                      f"I₂/I₁ = {float(r['i2_over_i1']):.4f}   I₂/I_n = {r['i2_over_in'] or '-'}   I_f = {r['i_f_A'][:6] if r['i_f_A'] else '-'} A   P_loop = {r['p_loop_total_W']} W"]
        if mode in ("mechanical", "integrated"):
            lines += [f"온도 권선 {float(r['T_winding']):.1f} · DE 베어링 {float(r['T_bearing_de']):.1f} · 축 {float(r['T_shaft']):.1f} · 프레임 {float(r['T_frame']):.1f} °C   진동 {r['vibration_mms']} mm/s",
                      f"등급 온도 {r['lvl_temperature']} · 진동 {r['lvl_vibration']} · 베어링 {r['lvl_bearing']}"]
        if ref is not None:
            R = ref["scenarios"].get(r["case"])
            if mode == "mechanical":
                lines.append("근거: Maxwell 근거 없음 — 진동·베어링 상수(ISO 10816-1 / AI Hub 참고)")
            elif R:
                exp = R["i2_over_i1_composite"]["expected_by_angle"]["angle_0"]; dev = (float(r["i2_over_i1"]) / exp - 1) * 100 if exp else 0.0
                lines.append(f"근거: I₂/I₁ 해석 {exp:.4f} (표시 {float(r['i2_over_i1']):.4f}, {dev:+.2f} %)  I_f MCCM {R['i_f_A']['mccm'] or R['i_f_A']['lut']} A  — 등가회로 LUT + 2D FEM (provisional)")
            else:
                lines.append("근거: LUT 밖 장면(legacy 해석식) — 해석 기준 없음")
        img = mpimg.imread(png)
        fig = plt.figure(figsize=(12.8, 7.2)); ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(img); ax.axis("off")
        y = 0.97
        for k, ln in enumerate(lines):
            ax.text(0.015, y, ln, transform=ax.transAxes, fontsize=11.5, color=col.get(st, "white") if k == 0 else "white", va="top", family="Malgun Gothic", weight="bold" if k == 0 else "normal",
                    bbox=dict(boxstyle="round,pad=0.25", fc="black", ec="none", alpha=0.68)); y -= 0.046
        ax.text(0.985, 0.03, "HUD 합성 (뷰포트 캡처 + state.csv) — 시뮬레이션 기반 추정값, 실측 아님", transform=ax.transAxes, fontsize=9.5, color="#ffcc66", ha="right", va="bottom",
                bbox=dict(boxstyle="round,pad=0.25", fc="black", ec="none", alpha=0.6))
        out = os.path.join(out_dir, f"{name}.png"); fig.savefig(out, dpi=100); plt.close(fig)
        cap = {"file": f"{name}.png", "scenario": scenario, "step": r["step"], "case": r["case"], "t_session_s": float(r["t_session_s"]), "description": desc.get(name, ""),
               "values": {k: r[k] for k in ("status", "cause_signal", "cause_value", "Ia_rms", "Ib_rms", "Ic_rms", "i1_A", "i2_over_i1", "i2_over_in", "i_f_A", "p_loop_total_W", "T_winding", "T_bearing_de", "T_shaft", "T_frame", "vibration_mms", "lvl_temperature", "lvl_vibration", "lvl_bearing")},
               "source": "state.csv (engine) + analysis_reference.json"}
        caps.append(cap)
        open(os.path.join(out_dir, f"{name}.txt"), "w", encoding="utf-8").write("\n".join(lines) + f"\n\n{desc.get(name, '')}\n")
    return caps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "compose", "all"))
    ap.add_argument("--scenario", default="electrical", choices=("electrical", "mechanical"))
    ap.add_argument("--view", default="full", choices=("full", "cutaway", "windings_only", "half_translucent", "half_translucent_front"))
    ap.add_argument("--raw", default=None); ap.add_argument("--state", default=None); ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args()
    if a.cmd == "compose":
        caps = compose(a.raw, a.state or os.path.join(a.raw, "state.csv"), a.out, a.scenario)
        write_captions(a.out, caps); print(f"→ {len(caps)} 장 → {a.out}"); return
    scen = ("electrical", "mechanical") if a.cmd == "all" else (a.scenario,)
    all_caps = []
    for sc in scen:
        view = a.view if a.cmd != "all" else ("full" if sc == "electrical" else "cutaway")
        raw = a.raw or os.path.join(VIZ, "logs", "hud_shots", sc)
        run(sc, view, raw)
        all_caps += compose(raw, os.path.join(raw, "state.csv"), a.out, sc)
    write_captions(a.out, all_caps); print(f"→ {len(all_caps)} 장 합성, 캡션 {os.path.join(a.out, 'captions.json')}")


def write_captions(out_dir: str, caps: list[dict]) -> None:
    """captions.json 병합 저장 (파일명 키) — 장면·시각·표시값·출처."""
    cap_p = os.path.join(out_dir, "captions.json")
    old = json.load(open(cap_p, encoding="utf-8")) if os.path.exists(cap_p) else []
    merged = {c["file"]: c for c in old}; merged.update({c["file"]: c for c in caps})
    json.dump(sorted(merged.values(), key=lambda c: c["file"]), open(cap_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
