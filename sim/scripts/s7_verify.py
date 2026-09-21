# -*- coding: utf-8 -*-
"""s7_verify.py — 신호 검증: 데이터셋의 각 결함 파일에 FFT/포락선 분석 → 이론 주파수와 대조 (Δf 이내 판정)
사용: python.bat s7_verify.py --dataset NAME  → sim/docs/s7_verification_report.md, sim/output/NAME/s7_verify.json
분석 신호: 조인트 각가속도(acc_rads2, = 순 토크/J)  — 토크 리플이 직접 반영되는 채널
"""
import os, sys, json, argparse, math
import numpy as np, yaml
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
from s5_fault_injector import FaultInjector
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); args = ap.parse_args()
D = os.path.join(ROOT, "output", args.dataset); man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
rows = []; all_ok = True
for r in man["runs"]:
    if not r["file"] or r["fault"] == "none": continue
    meta = json.load(open(os.path.join(D, r["file"][:-4] + ".json"), encoding="utf-8")); d = np.load(os.path.join(D, r["file"]))
    hz = meta["physics_hz"]; t = d["t"]; stop = meta["drive"]["stop_at_s"]; hold = float(CFG["baseline"]["ramp_hold_s"])
    m = (t >= stop - hold) & (t < stop); x = d["acc_rads2"][m]; N = len(x); T = N / hz; df = 1.0 / T
    rpm = float(np.mean(d["vel_rads"][m]) * 60 / (2 * math.pi))
    fi = FaultInjector(r["fault"], r["severity"], CFG); exp = fi.expected_peaks(rpm)
    if r["fault"] in ("bpfo", "bpfi"):
        X = np.fft.fft(x - x.mean()); h = np.zeros(N); h[0] = 1; h[1:N // 2] = 2; h[N // 2] = 1
        env = np.abs(np.fft.ifft(X * h)); sig = env - env.mean(); kind = "envelope"
    else:
        sig = x - x.mean(); kind = "fft"
    spec = np.abs(np.fft.rfft(sig * np.hanning(N))); freqs = np.fft.rfftfreq(N, 1 / hz)
    for fe in exp:
        if fe < 2 * df:   # 이론 주파수가 분해능 이하(예: 무부하 슬립≈0 → 2sf≈0): 물리적으로 미검출이 정답 → 해당 없음
            rows.append({"fault": r["fault"], "severity": r["severity"], "load": r["load"], "rpm": round(rpm, 2), "analysis": kind, "theory_Hz": round(fe, 3), "detected_Hz": None, "err_Hz": None, "df_Hz": round(df, 4), "prominence": None, "ok": None, "note": "이론 주파수 < 2Δf (무부하 슬립≈0) — 검출 불가, 판정 제외"})
            continue
        mm = (freqs >= max(fe - 3 * df, df)) & (freqs <= fe + 3 * df)
        fpk = float(freqs[mm][np.argmax(spec[mm])]); err = abs(fpk - fe)
        bg = np.median(spec[(freqs > fe - 25) & (freqs < fe + 25)]) + 1e-12; prom = float(spec[mm].max() / bg)
        ok = bool(err <= df * 1.001 and prom > 3.0); all_ok &= ok      # 허용 오차 = 1 bin(Δf), 부동소수 여유 0.1%
        rows.append({"fault": r["fault"], "severity": r["severity"], "load": r["load"], "rpm": round(rpm, 2), "analysis": kind, "theory_Hz": round(fe, 3), "detected_Hz": round(fpk, 3), "err_Hz": round(err, 4), "df_Hz": round(df, 4), "prominence": round(prom, 1), "ok": ok})
json.dump({"dataset": args.dataset, "all_ok": all_ok, "rows": rows}, open(os.path.join(D, "s7_verify.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
lines = ["# S7 — 신호 검증 보고 (이론 vs 검출 주파수)", "", f"- 데이터셋: `sim/output/{args.dataset}` (`generation: analytic_injection`)", f"- 분석 채널: 조인트 각가속도(정속 구간 {hold:.0f} s, 분해능 Δf = {rows[0]['df_Hz'] if rows else '-'} Hz), 베어링 결함은 힐베르트 포락선 스펙트럼", "- 판정: |검출 − 이론| ≤ Δf 이고 피크 두드러짐(주변 중앙값 대비) > 3", "", "| 결함 | 심각도 | 부하 | rpm | 분석 | 이론 Hz | 검출 Hz | 오차 Hz | 두드러짐 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|"]
for w in rows: lines.append(f"| {w['fault']} | {w['severity']} | {w['load']} | {w['rpm']} | {w['analysis']} | {w['theory_Hz']} | {w['detected_Hz'] if w['detected_Hz'] is not None else '—'} | {w['err_Hz'] if w['err_Hz'] is not None else '—'} | {w['prominence'] if w['prominence'] is not None else '—'} | {'✅' if w['ok'] else ('N/A' if w['ok'] is None else '❌')} |")
n_ok = sum(1 for w in rows if w["ok"]); n_na = sum(1 for w in rows if w["ok"] is None); n_eval = len(rows) - n_na
lines += ["", f"**결과: {n_ok}/{n_eval} 통과 (판정 제외 {n_na}건: 이론 주파수 < 2Δf), 전체 판정 = {'PASS' if all_ok else 'FAIL'}**", "", "판정 제외 근거: 무부하(≈동기속도) 조건에서는 슬립 s≈0 이므로 회전자 바 파손의 2sf 성분이 0 Hz로 수렴 — 실제 모터에서도 무부하 MCSA로는 BRB를 검출할 수 없다(부하 시험 필요)는 문헌 결론과 일치."]
open(os.path.join(ROOT, "docs", "s7_verification_report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("S7", "PASS" if all_ok else "FAIL", n_ok, "/", len(rows))
