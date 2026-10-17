# -*- coding: utf-8 -*-
"""lut_source.py — MCCM LUT(턴 비율 × R_f × 부하) 3축 보간 로더. numpy·json 만 사용 (Isaac Sim 파이썬에서도 import 가능).

보간: 턴 비율·부하 선형, R_f 는 log 축 선형. 격자점에서는 원값 그대로. 범위 밖은 끝값으로 클램프(clamped=True), 외삽 없음.
출처: data/electrical/M1_mccm_lut_v<N>.json (import_lut.py). grade 등가회로(RMxprt v2+MCCM), FEM 미검증, provisional.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

QUERY_KEYS = {
    "i2_over_i1": "I2_over_I1", "i2_A": "I2_A", "i2_over_in": "I2_over_In", "i1_A": "I1_A",
    "i2_angle_deg": "I2_angle_deg_vs_I1", "i2_angle_deg_vs_va": "I2_angle_deg_vs_Va",
    "i_f_A": "I_f", "p_loop_total_W": "P_loop_total_W", "p_fault_loop_W": "P_fault_loop_W",
    "ia_rms": "I_a", "ib_rms": "I_b", "ic_rms": "I_c", "unbalance_pct": "unbalance_max_dev_pct",
}


class LutSource:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        with open(self.path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.provenance = d.get("provenance", {})
        self.base_turns = int(d.get("N_ph") or self.provenance.get("base_turns_per_phase") or 192)
        self.rated_current_A = float(d.get("I_n") or self.provenance.get("rated_current_A") or 4.73)
        ax = d["axes"]
        self.fracs = np.array(sorted(float(x) / 100.0 for x in ax["turn_ratio_pct"]))
        self.rfs = np.array(sorted(float(x) for x in ax["R_f"]))
        self.loads = np.array(sorted(float(x) * 100.0 for x in ax["load"]))      # load_pct
        self.columns = [c for c in QUERY_KEYS.values() if c in d["columns"]]
        # 격자 (frac, rf, load) → 값
        self.grid = {c: np.full((len(self.fracs), len(self.rfs), len(self.loads)), np.nan) for c in self.columns}
        for r in d["rows"]:
            i = int(np.argmin(np.abs(self.fracs - float(r["turn_ratio_pct"]) / 100.0)))
            j = int(np.argmin(np.abs(self.rfs - float(r["R_f"]))))
            k = int(np.argmin(np.abs(self.loads - float(r["load"]) * 100.0)))
            for c in self.columns:
                self.grid[c][i, j, k] = float(r[c])
        for c in self.columns:
            if np.isnan(self.grid[c]).any():
                raise ValueError(f"LUT 격자에 빈 칸: {c}")
        self.version = os.path.basename(self.path)

    # ---------------------------------------------------------------- 유틸
    def turns_to_frac(self, turns: float) -> float:
        return float(turns) / self.base_turns

    @staticmethod
    def _locate(axis: np.ndarray, x: float):
        """축 위치 (i0, i1, w, clamped). 격자점이면 w=0, i0=i1."""
        clamped = False
        if x <= axis[0]:
            return 0, 0, 0.0, x < axis[0] - 1e-12
        if x >= axis[-1]:
            return len(axis) - 1, len(axis) - 1, 0.0, x > axis[-1] + 1e-12
        i1 = int(np.searchsorted(axis, x))
        i0 = i1 - 1
        if abs(axis[i0] - x) < 1e-12:
            return i0, i0, 0.0, False
        if abs(axis[i1] - x) < 1e-12:
            return i1, i1, 0.0, False
        return i0, i1, (x - axis[i0]) / (axis[i1] - axis[i0]), clamped

    def query(self, turn_frac: float, R_f_ohm: float | None, load_pct: float) -> dict:
        """(턴 비율, R_f[Ω], 부하[%]) → 보간값 dict. R_f=None 은 정상(턴 0)에서만 허용(첫 격자값 사용)."""
        if turn_frac <= 0.0:
            turn_frac = 0.0
        if R_f_ohm is None:
            if turn_frac > 0.0:
                raise ValueError("결함(턴 > 0)에는 R_f 가 필요하다")
            R_f_ohm = float(self.rfs[0])
        fi0, fi1, fw, fc = self._locate(self.fracs, float(turn_frac))
        ri0, ri1, rw, rc = self._locate(np.log(self.rfs), math.log(max(float(R_f_ohm), 1e-12)))
        li0, li1, lw, lc = self._locate(self.loads, float(load_pct))
        out = {"turn_frac": float(turn_frac), "turns": float(turn_frac) * self.base_turns, "R_f_ohm": float(R_f_ohm), "load_pct": float(load_pct),
               "clamped": bool(fc or rc or lc), "clamped_axes": [n for n, c in (("turn_frac", fc), ("R_f", rc), ("load", lc)) if c],
               "on_grid": bool(fw == 0 and rw == 0 and lw == 0)}
        for key, col in QUERY_KEYS.items():
            if col not in self.grid:
                continue
            g = self.grid[col]
            # 삼선형 보간 (각도 열은 선형 보간이 아닌 최근접 격자값 — 위상 랩 방지)
            if col.startswith("I2_angle") and not out["on_grid"]:
                i = fi1 if fw >= 0.5 else fi0; j = ri1 if rw >= 0.5 else ri0; k = li1 if lw >= 0.5 else li0
                out[key] = float(g[i, j, k]); continue
            c00 = g[fi0, ri0, li0] * (1 - lw) + g[fi0, ri0, li1] * lw
            c01 = g[fi0, ri1, li0] * (1 - lw) + g[fi0, ri1, li1] * lw
            c10 = g[fi1, ri0, li0] * (1 - lw) + g[fi1, ri0, li1] * lw
            c11 = g[fi1, ri1, li0] * (1 - lw) + g[fi1, ri1, li1] * lw
            c0 = c00 * (1 - rw) + c01 * rw
            c1 = c10 * (1 - rw) + c11 * rw
            out[key] = float(c0 * (1 - fw) + c1 * fw)
        out["source"] = {"grade": self.provenance.get("grade", "등가회로(RMxprt v2+MCCM)"), "status": self.provenance.get("status", "provisional"),
                         "fem_verified": bool(self.provenance.get("fem_verified", False)), "lut_version": self.version,
                         "lut_sha256": self.provenance.get("source_sha256", ""), "imported_at": self.provenance.get("imported_at", "")}
        return out


def default_lut_path(data_dir: str | None = None) -> str:
    """data/electrical 의 최신 버전 LUT 경로."""
    d = data_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "electrical")
    files = sorted([f for f in os.listdir(d) if f.startswith("M1_mccm_lut_v") and f.endswith(".json")], key=lambda s: int(s.split("_v")[1].split(".")[0]))
    if not files:
        raise FileNotFoundError("data/electrical 에 LUT 가 없다 — tools/electrical/import_lut.py 실행")
    return os.path.join(d, files[-1])
