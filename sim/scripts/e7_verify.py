# -*- coding: utf-8 -*-
"""e7_verify.py — 양 채널(진동 근사=각가속도 / 전류 Ia) FFT·포락선 검증 + 채널 간 슬립 정합 + baseline 이상 피크 부재 확인.
사용: python.bat e7_verify.py --dataset dataset_v02 → docs/e7_verification_report.md, output/<dataset>/e7_verify.json"""
import os, sys, json, argparse, math
import numpy as np, yaml
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
from fault_injector import FaultInjector
from current_generator import CurrentGenerator
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); args = ap.parse_args()
D = os.path.join(ROOT, "output", args.dataset); man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
b = CFG["bearings"]["DE"]; brg = (int(b["Z"]), float(b["Bd_mm"]), float(b["Pd_mm"]), float(b["contact_deg"]))
def spectrum(sig, hz, envelope=False):
    N = len(sig); x = sig - sig.mean()
    if envelope:
        X = np.fft.fft(x); h = np.zeros(N); h[0] = 1; h[1:N // 2] = 2; h[N // 2] = 1; x = np.abs(np.fft.ifft(X * h)); x -= x.mean()
    return np.fft.rfftfreq(N, 1 / hz), np.abs(np.fft.rfft(x * np.hanning(N)))
def check(freqs, spec, fe, df, mask_fs=False):
    if fe < 2 * df or (mask_fs and any(abs(fe - k * 60.0) < 3 * df for k in (1, 5, 7))):
        return {"theory_Hz": round(fe, 3), "ok": None, "note": "이론 < 2Δf 또는 기본파/고조파와 중첩 — 판정 제외"}
    mm = (freqs >= max(fe - 3 * df, df)) & (freqs <= fe + 3 * df); fpk = float(freqs[mm][np.argmax(spec[mm])]); err = abs(fpk - fe)
    bg = np.median(spec[(freqs > fe - 25) & (freqs < fe + 25)]) + 1e-12; prom = float(spec[mm].max() / bg)
    return {"theory_Hz": round(fe, 3), "detected_Hz": round(fpk, 3), "err_Hz": round(err, 4), "prominence": round(prom, 1), "ok": bool(err <= df * 1.001 and prom > 3)}
rows = []; base_rows = []; all_ok = True
for r in man["runs"]:
    if not r["file"]: continue
    meta = json.load(open(os.path.join(D, r["file"][:-4] + ".json"), encoding="utf-8")); d = np.load(os.path.join(D, r["file"]))
    hz = meta["physics_hz"]; tl = meta["timeline"]; t = d["t"]; m = (t >= tl["settle_s"]) & (t < tl["stop_s"]); df = 1 / tl["hold_s"]
    s_meas = float(d["slip"][m].mean()); fr = float(d["omega"][m].mean()) / (2 * math.pi); rpm = fr * 60
    if r["fault"] == "none":
        # baseline: 각가속도·전류에서 주입하지 않은 이상 피크 부재 (전류: 60·300·420 Hz 외 −50 dB 초과 피크 없음 / 가속도: 절대 피크 < 0.5 rad/s²)
        fq, sI = spectrum(d["Ia"][m], hz); ref = sI[np.argmin(abs(fq - 60))]
        spur = [round(float(f), 2) for f, v in zip(fq, sI) if v / ref > 10 ** (-50 / 20) and all(abs(f - k * 60) > 1.0 for k in (1, 5, 7)) and f > 2]
        acc_pk = float(np.abs(d["alpha"][m]).max())
        ok = (len(spur) == 0) and acc_pk < 0.5; all_ok &= ok
        base_rows.append({"load": r["load"], "seed": r["seed"], "rpm": round(rpm, 2), "slip": round(s_meas, 5), "current_spurious_Hz": spur[:10], "alpha_peak_rads2": acc_pk, "ok": ok}); continue
    fi = FaultInjector(r["fault"], r["severity"], CFG); cg = CurrentGenerator(r["fault"], r["severity"], CFG, bearing=brg)
    fq, sV = spectrum(d["alpha"][m], hz, envelope=r["fault"] in ("bpfo", "bpfi"))
    fqI, sI = spectrum(d["Ia"][m], hz)
    vib = [check(fq, sV, fe, df) for fe in fi.expected_peaks(rpm)]; cur = [check(fqI, sI, fe, df, mask_fs=True) for fe in cg.sideband_freqs(s_meas, fr)]
    # 채널 간 정합: 전류 측대파에서 역산한 슬립/fr 과 실측 비교 (brb: (fs − f_lo)/(2fs); ecc/unb: fs − f_lo = fr)
    cons = None
    if r["fault"] == "brb" and cur[0].get("detected_Hz"): cons = {"slip_from_current": (60 - cur[0]["detected_Hz"]) / 120, "slip_measured": s_meas}
    elif r["fault"] in ("ecc_static", "ecc_dynamic", "unbalance") and cur[0].get("detected_Hz"): cons = {"fr_from_current": 60 - cur[0]["detected_Hz"], "fr_measured": fr}
    if cons:
        a, bb = list(cons.values()); cons["ok"] = bool(abs(a - bb) <= (df / 120 if "slip_from_current" in cons else df) * 1.001); all_ok &= cons["ok"]
    ok_v = all(x["ok"] for x in vib if x["ok"] is not None); ok_c = all(x["ok"] for x in cur if x["ok"] is not None); all_ok &= ok_v and ok_c
    rows.append({"fault": r["fault"], "severity": r["severity"], "load": r["load"], "seed": r["seed"], "rpm": round(rpm, 2), "slip": round(s_meas, 5), "df": df, "vib": vib, "cur": cur, "consistency": cons, "ok": ok_v and ok_c and (cons is None or cons["ok"])})
json.dump({"dataset": args.dataset, "all_ok": all_ok, "baseline": base_rows, "faults": rows}, open(os.path.join(D, "e7_verify.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
L = ["# E7 — 신호 검증 보고 (양 채널 이론 vs 검출, 채널 간 슬립 정합)", "", f"- 데이터셋 `sim/output/{args.dataset}`, Δf = {rows[0]['df'] if rows else '-'} Hz (정속 10 s), 진동 근사 채널 = 조인트 각가속도(베어링은 포락선), 전류 채널 = Ia", "",
     "## Baseline (정상) — 주입하지 않은 이상 피크 부재", "", "| 부하 | seed | rpm | slip | 전류 −50 dB 초과 이상 피크 | α 피크 rad/s² | 판정 |", "|---|---|---|---|---|---|---|"]
for w in base_rows: L.append(f"| {w['load']} | {w['seed']} | {w['rpm']} | {w['slip']} | {w['current_spurious_Hz'] or '없음'} | {w['alpha_peak_rads2']:.2e} | {'✅' if w['ok'] else '❌'} |")
L += ["", "## 결함 런", "", "| 결함 | 심각도 | 부하 | seed | rpm | slip | 진동: 이론→검출 (Hz) | 전류: 이론→검출 (Hz) | 채널 정합 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|"]
fmt = lambda xs: "; ".join(f"{x['theory_Hz']}→{x.get('detected_Hz','—')}{'✓' if x['ok'] else ('N/A' if x['ok'] is None else '✗')}" for x in xs)
for w in rows:
    c = w["consistency"]; cs = "—" if not c else (f"s {c['slip_from_current']:.4f} vs {c['slip_measured']:.4f}" if "slip_from_current" in c else f"fr {c['fr_from_current']:.2f} vs {c['fr_measured']:.2f}") + (" ✓" if c["ok"] else " ✗")
    L.append(f"| {w['fault']} | {w['severity']} | {w['load']} | {w['seed']} | {w['rpm']} | {w['slip']} | {fmt(w['vib'])} | {fmt(w['cur'])} | {cs} | {'✅' if w['ok'] else '❌'} |")
n_ok = sum(1 for w in rows if w["ok"]); L += ["", f"**결함 런 {n_ok}/{len(rows)} 통과, baseline {sum(1 for w in base_rows if w['ok'])}/{len(base_rows)} 통과, 전체 = {'PASS' if all_ok else 'FAIL'}**",
                                              "", "불일치 시 추적 순서: 주입 로직 → 슬립 계산 → 샘플링."]
open(os.path.join(ROOT, "docs", "e7_verification_report.md"), "w", encoding="utf-8").write("\n".join(L))
print("E7", "PASS" if all_ok else "FAIL", n_ok, "/", len(rows), "baseline", sum(1 for w in base_rows if w["ok"]), "/", len(base_rows))
