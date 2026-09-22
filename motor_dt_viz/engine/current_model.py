# -*- coding: utf-8 -*-
"""current_model.py — 모듈 B: 3상 전류 생성·분석. Isaac Sim 비의존.

기능:
  1) 해석식 3상 전류 생성 (케이스별 크기·위상 불평형)
  2) npz 파형 재생 (sim/output/dataset_v03 — 해석식 생성 데이터, FEM 아님)
  3) 슬라이딩 윈도우 RMS
  4) 대칭좌표법 I₁·I₂ 와 I₂/I₁ 계산
  5) 상태 판정 (과전류 빨강 / 정상 초록 / 저전류 파랑)

Δ결선 주의 (CLAUDE.md §1.1): 케이블 경로는 선전류, 권선 오버레이는 상전류를 각각의
정격 기준으로 판정한다. 두 기준을 섞지 않는다.

단순화 가정:
  · ITSC 를 고장상 크기 불평형으로 등가 표현한다. 실제로는 단락 루프 순환전류가 지배적이며
    선전류 불평형은 더 작다. 본 MVP 는 목표 I₂/I₁(0.104 / 0.269)을 화면에 재현하기 위한 역산이다.
  · 과도(기동) 현상, 고조파 왜형은 모사하지 않는다 (정상상태 기본파 + 소량 고조파).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

from .config_loader import MotorSpec, load, val

A_OP = np.exp(2j * np.pi / 3.0)        # a = e^(j120°)


@dataclass
class CurrentState:
    """한 시점의 전류 상태."""
    time_s: float
    instantaneous_A: tuple[float, float, float]
    rms_A: tuple[float, float, float]
    ratio: tuple[float, float, float]        # r = I_rms / I_rated
    status: tuple[str, str, str]             # over_danger | over_caution | normal | under_caution | under_danger
    i1_A: float
    i2_A: float
    i2_over_i1: float
    case: str
    basis: str                                # 판정에 쓴 정격 기준


def symmetrical_components(ia: complex, ib: complex, ic: complex) -> tuple[complex, complex, complex]:
    """대칭좌표법. 반환 (정상분 I₁, 역상분 I₂, 영상분 I₀)."""
    a, a2 = A_OP, A_OP ** 2
    i1 = (ia + a * ib + a2 * ic) / 3.0
    i2 = (ia + a2 * ib + a * ic) / 3.0
    i0 = (ia + ib + ic) / 3.0
    return i1, i2, i0


def phasors_from_waveform(sig: np.ndarray, fs: float, f0: float) -> complex:
    """1주기 DFT 로 기본파 페이저를 추출한다 (진폭 = 피크값)."""
    n = int(round(fs / f0))
    if n < 2 or len(sig) < n:
        n = len(sig)
    w = sig[-n:]
    k = np.exp(-2j * np.pi * f0 * np.arange(n) / fs)
    return 2.0 * np.sum(w * k) / n


def unbalance_scale_for_ratio(ratio: float, phase_deg: float = 0.0) -> float:
    """목표 I₂/I₁ 을 만드는 고장상(내부 키 A, 화면 표시 R상) 크기 배율 k 를 역산한다.

    Ia = k·I·e^(jφ), Ib = I∠−120°, Ic = I∠+120° 일 때
        I₁ = I(k·e^(jφ) + 2)/3,  I₂ = I(k·e^(jφ) − 1)/3
        |I₂/I₁| = r  →  k²(1−r²) − 2k·cosφ(1+2r²) + (1−4r²) = 0
    위상 shift 가 0 이면 k = (1+2r)/(1−r) 로 환원된다.
    """
    if not 0.0 <= ratio < 1.0:
        raise ValueError("ratio 는 0 이상 1 미만이어야 한다")
    r2 = ratio * ratio
    cos_p = math.cos(math.radians(phase_deg))
    A = 1.0 - r2
    B = -2.0 * cos_p * (1.0 + 2.0 * r2)
    C = 1.0 - 4.0 * r2
    disc = B * B - 4.0 * A * C
    if disc < 0 or A <= 0:
        raise ValueError(f"해를 구할 수 없다 (ratio={ratio}, phase={phase_deg})")
    return (-B + math.sqrt(disc)) / (2.0 * A)


class CurrentModel:
    """해석식 3상 전류 생성기 + 분석기."""

    def __init__(self, cfg: dict | None = None, motor: MotorSpec | None = None):
        self.cfg = cfg or load("electrical")
        self.motor = motor or MotorSpec()
        self.f0 = self.motor.frequency
        self.cases = self.cfg["cases"]
        th = self.cfg["thresholds"]
        self.th_over_danger = float(th["over_danger"])
        self.th_over_caution = float(th["over_caution"])
        self.th_under_caution = float(th["under_caution"])
        self.th_under_danger = float(th["under_danger"])
        self.window_cycles = float(self.cfg["rms"]["window_cycles"])
        self._buf: dict[str, list[float]] = {"a": [], "b": [], "c": [], "t": []}
        self._npz = None
        self._calibrate_targets()

    def _calibrate_targets(self) -> None:
        """target_i2i1 이 지정된 케이스는 고장상 배율을 위상까지 고려해 정확히 역산한다.

        config 의 phase_scale[0] 은 참고값이며, 목표 I₂/I₁ 이 있으면 이 값으로 덮어쓴다.
        (config 를 손으로 고칠 때 위상과 배율이 어긋나는 것을 방지)
        """
        self.calibration: dict[str, dict] = {}
        for name, c in self.cases.items():
            target = c.get("target_i2i1")
            if target is None:
                continue
            phase = float(c["phase_shift_deg"][0])
            k = unbalance_scale_for_ratio(float(target), phase)
            self.calibration[name] = {"config_scale": float(c["phase_scale"][0]),
                                      "calibrated_scale": k, "phase_deg": phase, "target": float(target)}
            c["phase_scale"] = [k] + list(c["phase_scale"][1:])

    # ------------------------------------------------------------- 파형 생성
    def waveform(self, t: np.ndarray, case: str = "healthy", basis: str = "rated_line_A") -> np.ndarray:
        """시각 배열 t [s] 에 대한 3상 순시 전류 [A]. 반환 shape (3, len(t))."""
        c = self.cases[case]
        i_rated = self.motor.rated_current(basis)
        scale = np.asarray(c["phase_scale"], dtype=float)
        shift = np.deg2rad(np.asarray(c["phase_shift_deg"], dtype=float))
        base_phase = np.array([0.0, -2 * np.pi / 3, 2 * np.pi / 3])
        load = float(c.get("load", 1.0))
        amp = math.sqrt(2.0) * i_rated * scale * max(load, 0.0 if load == 0 else load)
        if load == 0.0:      # 무부하: 자화전류만 (phase_scale 이 이미 0.33 반영)
            amp = math.sqrt(2.0) * i_rated * scale
        out = np.empty((3, len(t)), dtype=float)
        for k in range(3):
            out[k] = amp[k] * np.sin(2 * np.pi * self.f0 * t + base_phase[k] + shift[k])
        return out

    def sample(self, t: float, case: str = "healthy", basis: str = "rated_line_A") -> tuple[float, float, float]:
        """단일 시각의 3상 순시 전류."""
        w = self.waveform(np.array([t]), case, basis)
        return float(w[0, 0]), float(w[1, 0]), float(w[2, 0])

    # ------------------------------------------------------------- npz 재생
    def load_npz(self, path: str) -> dict:
        """기존 Isaac 데이터셋 npz 재생 (Ia/Ib/Ic). FEM 아님 — 해석식 생성 데이터."""
        d = np.load(path)
        missing = [k for k in ("t", "Ia", "Ib", "Ic") if k not in d.files]
        if missing:
            raise KeyError(f"npz 에 필요한 키가 없다: {missing}")
        self._npz = {"t": d["t"], "I": np.vstack([d["Ia"], d["Ib"], d["Ic"]]), "path": path}
        return {"samples": len(d["t"]), "fs_Hz": 1.0 / float(d["t"][1] - d["t"][0]), "path": path}

    def npz_window(self, t_start: float, duration_s: float) -> tuple[np.ndarray, np.ndarray]:
        if self._npz is None:
            raise RuntimeError("load_npz 를 먼저 호출해야 한다")
        t = self._npz["t"]
        m = (t >= t_start) & (t < t_start + duration_s)
        return t[m], self._npz["I"][:, m]

    # ------------------------------------------------------------- 분석
    def analyze(self, t: np.ndarray, I: np.ndarray, case: str = "healthy",
                basis: str = "rated_line_A") -> CurrentState:
        """파형 구간으로부터 RMS·대칭분·상태를 계산한다. I shape (3, N)."""
        if I.shape[0] != 3:
            raise ValueError("I 는 (3, N) 이어야 한다")
        fs = 1.0 / float(t[1] - t[0]) if len(t) > 1 else self.f0 * 64
        n_win = max(int(round(self.window_cycles * fs / self.f0)), 2)
        seg = I[:, -n_win:] if I.shape[1] >= n_win else I
        rms = np.sqrt(np.mean(seg ** 2, axis=1))

        ph = [phasors_from_waveform(seg[k], fs, self.f0) for k in range(3)]
        i1, i2, _ = symmetrical_components(*ph)
        a1, a2 = abs(i1), abs(i2)
        ratio_i2i1 = (a2 / a1) if a1 > 1e-12 else 0.0

        i_rated = self.motor.rated_current(basis)
        r = tuple(float(x / i_rated) for x in rms)
        status = tuple(self.classify(x) for x in r)
        return CurrentState(
            time_s=float(t[-1]),
            instantaneous_A=(float(I[0, -1]), float(I[1, -1]), float(I[2, -1])),
            rms_A=(float(rms[0]), float(rms[1]), float(rms[2])),
            ratio=r,
            status=status,
            i1_A=float(a1 / math.sqrt(2)),      # 페이저 피크 → RMS 환산
            i2_A=float(a2 / math.sqrt(2)),
            i2_over_i1=float(ratio_i2i1),
            case=case,
            basis=basis,
        )

    def classify(self, r: float) -> str:
        if r > self.th_over_danger:
            return "over_danger"
        if r > self.th_over_caution:
            return "over_caution"
        if r < self.th_under_danger:
            return "under_danger"
        if r < self.th_under_caution:
            return "under_caution"
        return "normal"

    def evaluate_case(self, case: str, basis: str = "rated_line_A", cycles: int = 4) -> CurrentState:
        """케이스를 지정 주기만큼 생성해 바로 분석한다 (테스트·HUD 초기값용)."""
        fs = self.f0 * 256
        t = np.arange(0, cycles / self.f0, 1.0 / fs)
        I = self.waveform(t, case, basis)
        return self.analyze(t, I, case, basis)

    # ------------------------------------------------------------- 연동
    def winding_current_pu(self, state: CurrentState) -> float:
        """모듈 A 권선 동손 입력용 전류비 (3상 RMS 의 제곱평균 → 등가 1상 pu)."""
        r = np.asarray(state.ratio, dtype=float)
        return float(np.sqrt(np.mean(r ** 2)))

    def short_loop(self, case: str) -> dict | None:
        """ITSC 단락 루프 파라미터 (없으면 None)."""
        return self.cases.get(case, {}).get("short_loop")

    @property
    def honesty_label(self) -> str:
        return self.cfg["source"]["honesty_label"]

    @property
    def honesty_sub(self) -> str:
        return self.cfg["source"]["honesty_sub"]
