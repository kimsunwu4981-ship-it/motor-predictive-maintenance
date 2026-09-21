# -*- coding: utf-8 -*-
"""e5_selftest.py — FaultInjector(토크) + CurrentGenerator(전류) 단위 테스트: 이론 주파수가 각 채널 FFT에서 Δf 이내 검출되는지.
정격 운전점(1170 rpm, s = 0.025) 고정 슬립으로 T = 10 s 신호 생성 (Isaac 불필요)."""
import os, sys, json, math
import numpy as np, yaml
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); sys.path.insert(0, os.path.dirname(__file__))
from fault_injector import FaultInjector, SEV
from current_generator import CurrentGenerator, SIDEBAND_DB
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
hz = 2560; T = 10.0; N = int(hz * T); t = np.arange(N) / hz; df = 1 / T
rpm = 1170.0; fr = rpm / 60; s = 0.025; omega = 2 * math.pi * fr; theta = omega * t
b = CFG["bearings"]["DE"]; brg = (int(b["Z"]), float(b["Bd_mm"]), float(b["Pd_mm"]), float(b["contact_deg"]))
FS = 60.0
def masked_by_fundamental(fe):
    return any(abs(fe - k * FS) < 3 * df for k in (1, 5, 7))
def peak_check(freqs, spec, fe, mask_fs=False):
    if fe < 2 * df or (mask_fs and masked_by_fundamental(fe)): return {"theory_Hz": round(fe, 3), "detected_Hz": None, "err_Hz": None, "prominence": None, "ok": None, "note": "이론 < 2Δf 또는 기본파/고조파와 3Δf 내 중첩 — 분리 불가, 판정 제외"}
    mm = (freqs >= max(fe - 3 * df, df)) & (freqs <= fe + 3 * df); fpk = float(freqs[mm][np.argmax(spec[mm])]); err = abs(fpk - fe)
    bg = np.median(spec[(freqs > fe - 20) & (freqs < fe + 20)]) + 1e-12; prom = float(spec[mm].max() / bg)
    return {"theory_Hz": round(fe, 3), "detected_Hz": round(fpk, 3), "err_Hz": round(err, 4), "prominence": round(prom, 1), "ok": bool(err <= df * 1.001 and prom > 3)}
res = {"df_Hz": df, "torque": {}, "current": {}}; ok_all = True
for mode, sevs in SEV.items():
    sev = list(sevs)[-1]
    fi = FaultInjector(mode, sev, CFG, seed=1); x = np.array([fi.torque_v2(t[i], s, fr, theta[i]) for i in range(N)])
    if mode in ("bpfo", "bpfi"):
        X = np.fft.fft(x - x.mean()); h = np.zeros(N); h[0] = 1; h[1:N // 2] = 2; h[N // 2] = 1; sig = np.abs(np.fft.ifft(X * h)); sig -= sig.mean()
    else: sig = x - x.mean()
    spec = np.abs(np.fft.rfft(sig * np.hanning(N))); freqs = np.fft.rfftfreq(N, 1 / hz)
    rows = [peak_check(freqs, spec, fe) for fe in fi.expected_peaks(rpm)]; res["torque"][mode] = {"severity": sev, "peaks": rows}; ok_all &= all(r["ok"] for r in rows if r["ok"] is not None)
    cg = CurrentGenerator(mode, sev, CFG, seed=2, bearing=brg); I = np.array([cg.sample(t[i], s, fr) for i in range(N)])[:, 0]
    specI = np.abs(np.fft.rfft((I - I.mean()) * np.hanning(N)))
    rowsI = [peak_check(freqs, specI, fe, mask_fs=True) for fe in cg.sideband_freqs(s, fr)]; res["current"][mode] = {"severity": sev, "peaks": rowsI}; ok_all &= all(r["ok"] for r in rowsI if r["ok"] is not None)
# 정상 전류: 기본파·5·7차 외 이상 피크 없음 확인 (−50 dB 이상 피크 개수)
cg0 = CurrentGenerator("none", "none", CFG, seed=3, bearing=brg); I0 = np.array([cg0.sample(t[i], s, fr) for i in range(N)])[:, 0]
S0 = np.abs(np.fft.rfft((I0 - I0.mean()) * np.hanning(N))); freqs = np.fft.rfftfreq(N, 1 / hz); ref = S0[np.argmin(abs(freqs - 60))]
spur = [(round(float(f), 2), round(20 * math.log10(v / ref), 1)) for f, v in zip(freqs, S0) if v / ref > 10 ** (-50 / 20) and all(abs(f - k * 60) > 1.0 for k in (1, 5, 7)) and f > 2]
res["normal_current_spurious_peaks_above_-50dB"] = spur; ok_all &= len(spur) == 0
res["all_ok"] = ok_all
json.dump(res, open(os.path.join(ROOT, "output", "e5_selftest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("E5_SELFTEST", "ALL_OK" if ok_all else "FAIL")
for ch in ("torque", "current"):
    for mode, r in res[ch].items(): print(ch, mode, [(p["theory_Hz"], p["detected_Hz"], p["ok"]) for p in r["peaks"]])
print("spurious:", spur)
