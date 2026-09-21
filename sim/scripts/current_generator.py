# -*- coding: utf-8 -*-
"""current_generator.py — 고정자 전류(MCSA) 채널 해석 생성기 (E5). 시뮬레이션 실측 슬립 s·회전주파수 fr 공유.
generation: "analytic" — PhysX 산출물이 아님.

기본파: I1·sin(2π fs t + φ_k) (3상, φ_k = 0, −120°, +120°) + 정상 고조파(5차, 7차: −40 dB 미확인(추정: 인버터 없는 상용전원 전형값))
결함별 측대파 (진폭은 기본파 대비 dB, 심각도별 — 전부 미확인(추정: 문헌 전형 범위)):
  brb        : fs(1 ± 2ks), k=1,2  — Thomson & Fenger, IEEE Ind. Appl. Mag. 2001 (기억 기반 인용 — 원문 확인 전 미확인)
  ecc_static : fs ± k·fr (k=1,2)   — 〃 (혼합 편심 측대파)
  ecc_dynamic: fs ± k·fr (k=1,2,3) + 슬롯 고조파 측대파 생략
  itsc       : 3차 고조파(3fs) 증가 + fs ± 2fr 성분 + 상간 불평형(고장상 진폭 +δ%) — Thomson 2001, Sharifi & Ebrahimi 2011 (기억 기반 — 미확인)
  bpfo/bpfi  : fs ± k·f_brg (k=1,2) 미세 측대파 — Schoen et al., IEEE Trans. IA 1995 (기억 기반 — 미확인)
  unbalance  : fs ± fr (기계 결함 대조군; 편심과 주파수 중첩 → 진폭·고조파 수로만 구분, 미확인)
편심 vs 턴간 단락 구분 규칙: 편심 = fs±k·fr 열(k≥1), 턴간 단락 = 3fs 증가 + fs±2fr + 상 불평형. 출처가 기억 기반이므로 `미확인` — 두 클래스의 분류 성능 주장 금지.
"""
import math
import numpy as np

DB = lambda db: 10 ** (db / 20)
# 심각도별 측대파 진폭 (기본파 대비 dB) — 미확인(추정: 문헌 전형 범위; 정상 노이즈 플로어 ≈ −55 dB 가정)
SIDEBAND_DB = {
    "brb":        {"incipient": -48, "moderate": -40, "severe": -32},
    "ecc_static": {"e10": -50, "e20": -44, "e30": -38},
    "ecc_dynamic":{"e10": -50, "e20": -44, "e30": -38},
    "itsc":       {"t2": -46, "t5": -38, "t10": -30},
    "bpfo":       {"incipient": -58, "moderate": -50, "severe": -42},
    "bpfi":       {"incipient": -58, "moderate": -50, "severe": -42},
    "unbalance":  {"G6.3": -52, "G16": -46, "G40": -40},
}
ITSC_UNBALANCE_PCT = {"t2": 1.0, "t5": 2.5, "t10": 5.0}   # 고장상(A상) 진폭 증가 % — 미확인(추정)

class CurrentGenerator:
    def __init__(self, mode, severity, cfg, seed=0, bearing=None):
        V = lambda d: d["value"] if isinstance(d, dict) else d
        m = cfg["motor"]; self.fs = float(V(m["supply_Hz"])); self.mode = mode; self.sev = severity
        self.I1 = float(V(cfg["current"]["rated_current_A"])); self.harm_db = float(V(cfg["current"]["harmonics_db"]))
        self.noise_db = float(V(cfg["current"]["noise_floor_db"])); self.rng = np.random.default_rng(seed)
        self.A_sb = DB(SIDEBAND_DB[mode][severity]) * self.I1 if mode != "none" else 0.0
        self.brg = bearing   # (Z, Bd, Pd, alpha)
        self.phase = [0.0, -2 * math.pi / 3, 2 * math.pi / 3]
        self._ph_sb = self.rng.uniform(0, 2 * math.pi, 8)
    def _bearing_f(self, fr):
        Z, Bd, Pd, al = self.brg; r = Bd / Pd * math.cos(math.radians(al))
        return {"bpfo": Z / 2 * fr * (1 - r), "bpfi": Z / 2 * fr * (1 + r)}
    def sideband_freqs(self, s, fr):
        fs = self.fs; m = self.mode
        if m == "brb": return [fs * (1 - 2 * s), fs * (1 + 2 * s), fs * (1 - 4 * s), fs * (1 + 4 * s)]
        if m == "ecc_static": return [fs - fr, fs + fr, fs - 2 * fr, fs + 2 * fr]
        if m == "ecc_dynamic": return [fs - fr, fs + fr, fs - 2 * fr, fs + 2 * fr, fs - 3 * fr, fs + 3 * fr]
        if m == "itsc": return [3 * fs, fs - 2 * fr, fs + 2 * fr]
        if m in ("bpfo", "bpfi"):
            fb = self._bearing_f(fr)[m]; return [abs(fs - fb), fs + fb, abs(fs - 2 * fb), fs + 2 * fb]   # |fs ± k·f_brg| (음수 → 절댓값)
        if m == "unbalance": return [fs - fr, fs + fr]
        return []
    def sample(self, t, s, fr):
        """3상 전류 (A) — t: 시각, s: 실측 슬립, fr: 실측 회전주파수(Hz)"""
        fs = self.fs; w = 2 * math.pi
        out = np.zeros(3)
        sbf = self.sideband_freqs(max(s, 0.0), fr); weights = [1.0, 1.0, 0.4, 0.4, 0.2, 0.2][: len(sbf)]
        if self.mode == "itsc": weights = [1.0, 0.6, 0.6]
        for k in range(3):
            ph = self.phase[k]; i = self.I1 * math.sin(w * fs * t + ph)
            i += self.I1 * DB(self.harm_db) * (math.sin(w * 5 * fs * t + 5 * ph) + math.sin(w * 7 * fs * t + 7 * ph))
            for j, f in enumerate(sbf):
                i += self.A_sb * weights[j] * math.sin(w * f * t + ph + self._ph_sb[j % 8])
            if self.mode == "itsc" and k == 0: i *= 1 + ITSC_UNBALANCE_PCT[self.sev] / 100
            out[k] = i
        out += self.I1 * DB(self.noise_db) * self.rng.standard_normal(3)
        return out
    def describe(self):
        return {"channel": "current", "generation": "analytic", "mode": self.mode, "severity": self.sev, "I1_A": self.I1,
                "sideband_db": SIDEBAND_DB[self.mode][self.sev] if self.mode != "none" else None, "harmonics_db": self.harm_db, "noise_floor_db": self.noise_db,
                "label": "미확인(추정: 측대파 dB는 문헌 전형 범위 — 기억 기반 인용, 원문 확인 전)"}
