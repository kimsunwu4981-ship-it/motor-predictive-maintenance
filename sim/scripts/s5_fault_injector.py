# -*- coding: utf-8 -*-
"""s5_fault_injector.py — 결함 토크 리플 주입 모듈 (경로 A: 해석식 기반).
generation = "analytic_injection" — FEM 유도 데이터가 아니라 주입된 시그니처의 재생산임.

모든 진폭 스케일은 실측/문헌 기준값 확보 전까지 `미확인(추정)` — 심각도 단계는 파라미터 스윕용 상대값.
순수 numpy/math 만 사용 → Isaac Sim 없이도 단위 테스트 가능 (python s5_fault_injector.py --selftest).
"""
import math, json, sys
import numpy as np

def bearing_freqs(fr, Z, Bd, Pd, alpha_deg=0.0):
    c = math.cos(math.radians(alpha_deg)); r = Bd / Pd
    return {"BPFO": Z / 2 * fr * (1 - r * c), "BPFI": Z / 2 * fr * (1 + r * c),
            "BSF": Pd / (2 * Bd) * fr * (1 - (r * c) ** 2), "FTF": fr / 2 * (1 - r * c)}

# 심각도 → 진폭비(정격토크 대비) — 미확인(추정: 상대 스윕값)
SEV = {
    "brb":        {"incipient": 0.005, "moderate": 0.02, "severe": 0.05},          # 회전자 바 파손 (2sf 리플)
    "ecc_static": {"e10": 0.01, "e20": 0.02, "e30": 0.04},                          # 정적 편심 (2fs 리플)
    "ecc_dynamic":{"e10": 0.01, "e20": 0.02, "e30": 0.04},                          # 동적 편심 (fr 리플 + 2fs±fr)
    "itsc":       {"t2": 0.01, "t5": 0.025, "t10": 0.05},                           # 턴간 단락 (2fs 지배 + fs±fr)
    "bpfo":       {"incipient": 0.02, "moderate": 0.06, "severe": 0.15},            # 임펄스 피크 진폭비
    "bpfi":       {"incipient": 0.02, "moderate": 0.06, "severe": 0.15},
    "unbalance":  {"G6.3": 0.002, "G16": 0.006, "G40": 0.015},                      # 1×fr 정현 (등가 토크, 추정)
}

class FaultInjector:
    def __init__(self, mode="none", severity="none", cfg=None, seed=0, resonance_Hz=800.0, damping_ratio=0.05):
        self.mode = mode; self.sev = severity; self.cfg = cfg or {}; self.rng = np.random.default_rng(seed)
        m = self.cfg.get("motor", {}); V = lambda d: d["value"] if isinstance(d, dict) else d
        self.fs = float(V(m.get("supply_Hz", 60.0))); self.p = int(V(m.get("poles", 6)))
        self.T_rated = float(V(m.get("rated_torque_Nm", 179.6))); self.n_sync = float(V(m.get("sync_rpm", 1200.0)))
        b = self.cfg.get("bearings", {}).get("DE", {"Z": 8, "Bd_mm": 23.8125, "Pd_mm": 102.5, "contact_deg": 0})
        self.brg = (int(b["Z"]), float(b["Bd_mm"]), float(b["Pd_mm"]), float(b.get("contact_deg", 0)))
        self.A = 0.0 if mode == "none" else SEV[mode][severity] * self.T_rated
        self.fn = resonance_Hz; self.zeta = damping_ratio      # 베어링 임펄스 응답 공진 — 미확인(추정: 분석대역 1 kHz 내 800 Hz)
        self._next_imp = 0.0; self._imp_t0 = None; self._jitter = 0.003   # 임펄스 주기 지터 0.3 % — 미확인(추정: 전동체 미끄럼), 1 %는 2차 고조파를 Δf 이상 넓혀 축소
        self._ph = self.rng.uniform(0, 2 * math.pi, 4)
    # ---- 결함별 토크 리플 ----
    def torque(self, t, omega, theta):
        if self.mode == "none" or self.A == 0.0: return 0.0
        fr = max(omega, 0.0) / (2 * math.pi)                     # 축 회전 주파수 (Hz)
        n = fr * 60; s = max((self.n_sync - n) / self.n_sync, 0.0)
        A = self.A; fs = self.fs; two_pi = 2 * math.pi
        if self.mode == "brb":            # 2·s·fs 토크 리플 (전류 fs(1±2s) 측대파 대응)
            return A * math.sin(two_pi * 2 * s * fs * t + self._ph[0])
        if self.mode == "ecc_static":     # 2fs 리플
            return A * math.sin(two_pi * 2 * fs * t + self._ph[0])
        if self.mode == "ecc_dynamic":    # fr 리플 + (2fs ± fr) 측대파
            return A * (math.sin(theta + self._ph[0]) + 0.3 * math.sin(two_pi * (2 * fs) * t - theta) + 0.3 * math.sin(two_pi * (2 * fs) * t + theta))
        if self.mode == "itsc":           # 2fs 지배 + (fs ± fr) 약 성분
            return A * (math.sin(two_pi * 2 * fs * t + self._ph[0]) + 0.3 * math.sin(two_pi * fs * t - theta) + 0.3 * math.sin(two_pi * fs * t + theta))
        if self.mode == "unbalance":      # 1×fr 정현 (등가 토크)
            return A * math.sin(theta + self._ph[0])
        if self.mode in ("bpfo", "bpfi"):  # 임펄스 열 + 감쇠 정현 응답
            if fr < 1.0: return 0.0
            f = bearing_freqs(fr, *self.brg)[self.mode.upper()]
            if t >= self._next_imp:
                # 예약 시각 기준으로 다음 임펄스를 잡아 샘플 양자화 오차 누적 방지
                self._imp_t0 = self._next_imp if self._imp_t0 is not None else t
                self._next_imp = self._imp_t0 + (1.0 / f) * (1 + self._jitter * self.rng.standard_normal())
            if self._imp_t0 is None: return 0.0
            tau = t - self._imp_t0; wn = two_pi * self.fn
            env = math.exp(-self.zeta * wn * tau) * math.sin(wn * math.sqrt(1 - self.zeta ** 2) * tau)
            mod = (1 + 0.8 * math.sin(theta)) if self.mode == "bpfi" else 1.0     # 내륜: 하중영역 통과 1×fr 변조
            return A * mod * env
        return 0.0
    def theory_freqs(self, rpm):
        fr = rpm / 60; s = (self.n_sync - rpm) / self.n_sync; bf = bearing_freqs(fr, *self.brg)
        return {"fr": fr, "slip": s, "2sf": 2 * s * self.fs, "fs-fr": self.fs - fr, "fs+fr": self.fs + fr, "2fs": 2 * self.fs,
                "2fs-fr": 2 * self.fs - fr, "2fs+fr": 2 * self.fs + fr, **bf}
    def expected_peaks(self, rpm):
        f = self.theory_freqs(rpm)
        return {"none": [], "brb": [f["2sf"]], "ecc_static": [f["2fs"]], "ecc_dynamic": [f["fr"], f["2fs-fr"], f["2fs+fr"]],
                "itsc": [f["2fs"], f["fs-fr"], f["fs+fr"]], "unbalance": [f["fr"]], "bpfo": [f["BPFO"], 2 * f["BPFO"]], "bpfi": [f["BPFI"], f["BPFI"] - f["fr"], f["BPFI"] + f["fr"]]}[self.mode]
    def describe(self):
        return {"mode": self.mode, "severity": self.sev, "amplitude_Nm": self.A, "amplitude_ratio_T_rated": (self.A / self.T_rated if self.T_rated else 0),
                "bearing_DE": {"Z": self.brg[0], "Bd_mm": self.brg[1], "Pd_mm": self.brg[2]}, "resonance_Hz": self.fn, "zeta": self.zeta,
                "label": "미확인(추정: 진폭비는 상대 스윕값, 공진 800 Hz 가정)", "generation": "analytic_injection"}

# ---- 자가 검증: 주입 주파수가 FFT/포락선에서 검출되는지 ----
def selftest(hz=2560, T=8.0, rpm=1170.0, verbose=True):
    import yaml, os
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "config", "motor.yaml"), encoding="utf-8"))
    N = int(hz * T); t = np.arange(N) / hz; omega = rpm * 2 * math.pi / 60; theta = omega * t
    df = 1.0 / T; results = {}; ok_all = True
    for mode, sevs in SEV.items():
        sev = list(sevs)[1]
        fi = FaultInjector(mode, sev, cfg, seed=1)
        x = np.array([fi.torque(t[i], omega, theta[i]) for i in range(N)])
        if mode in ("bpfo", "bpfi"):   # 포락선 (해석신호 절대값) 스펙트럼
            from numpy.fft import fft, ifft
            X = fft(x); h = np.zeros(N); h[0] = 1; h[1:N // 2] = 2; h[N // 2] = 1
            env = np.abs(ifft(X * h)); env -= env.mean(); spec = np.abs(np.fft.rfft(env * np.hanning(N)))
        else:
            spec = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(N)))
        freqs = np.fft.rfftfreq(N, 1 / hz)
        exp = fi.expected_peaks(rpm); found = []
        for fe in exp:
            lo, hi = fe - 3 * df, fe + 3 * df; m = (freqs >= max(lo, df)) & (freqs <= hi)
            fpk = float(freqs[m][np.argmax(spec[m])]) if m.any() else None
            err = abs(fpk - fe) if fpk is not None else None
            # 피크가 국소 최대이며 주변 대비 충분히 큰지
            bg = np.median(spec[(freqs > fe - 20) & (freqs < fe + 20)]) + 1e-12
            prom = float(spec[m].max() / bg); okp = err is not None and err <= df and prom > 3
            found.append({"theory_Hz": round(fe, 3), "detected_Hz": fpk, "err_Hz": err, "prominence": round(prom, 1), "ok": okp}); ok_all &= okp
        results[mode] = {"severity": sev, "peaks": found}
        if verbose: print(mode, json.dumps(found))
    results["_all_ok"] = ok_all; results["_df_Hz"] = df; results["_hz"] = hz
    return results

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        r = selftest(); print("ALL_OK", r["_all_ok"])
        import os; json.dump(r, open(os.path.join(os.path.dirname(__file__), "..", "output", "s5_selftest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
