# -*- coding: utf-8 -*-
"""current_model.py — 모듈 B: 3상 전류 생성·분석. Isaac Sim 비의존.

기능:
  1) 3상 전류 생성 — 두 방식 (config/electrical.yaml method, TASK A D3)
       lut    : ITSC 결함의 I₂/I₁·I₂ 위상을 Maxwell 경로 B 등가회로 LUT(RMxprt v2+MCCM, engine/lut_source.py)에서 읽어
                정상분 I₁ + (결함 I₂ + 고유 비대칭 I₂) 페이저를 합성한다. M1 전용(transfer_to_other_motors false).
       legacy : 해석식 — 목표 I₂/I₁ 을 고장상 크기 배율로 역산(기존 MVP 방식). 되돌리기용으로 그대로 둔다.
  2) npz 파형 재생 (sim/output/dataset_v03 — 해석식 생성 데이터, FEM 아님)
  3) 슬라이딩 윈도우 RMS
  4) 대칭좌표법 I₁·I₂ 와 I₂/I₁, I₂/I_n(부하 무관 보조 지표, 판정에는 쓰지 않음)
  5) 상태 판정 (과전류 빨강 / 정상 초록 / 저전류 파랑)

Δ결선 주의 (CLAUDE.md §1.1): 케이블 경로는 선전류, 권선 오버레이는 상전류를 각각의
정격 기준으로 판정한다. 두 기준을 섞지 않는다.

단순화 가정:
  · legacy: ITSC 를 고장상 크기 불평형으로 등가 표현한다. 실제로는 단락 루프 순환전류가 지배적이며
    선전류 불평형은 더 작다 (0.104 / 0.269 는 화면 재현용 역산).
  · lut: 단일 주파수 등가회로 — 포화·시간 고조파·RSH 없음, FEM 미검증(provisional). 파형은 기본파만.
  · 과도(기동) 현상, 고조파 왜형은 모사하지 않는다.
"""
from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field

import numpy as np

from .config_loader import MotorSpec, load, val

A_OP = np.exp(2j * np.pi / 3.0)        # a = e^(j120°)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEGACY_GRADE = "해석식 역산(legacy)"


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
    i2_over_in: float | None = None           # I₂ / I_n (electrical.yaml rated_current_A, 선전류 기준에서만). 판정 불사용 (D4)
    i2_angle_deg: float | None = None         # I₂ 위상 (I₁ 기준)
    source: dict = field(default_factory=dict)   # 근거 (method/grade/status/fem_verified/lut_version …)


def symmetrical_components(ia: complex, ib: complex, ic: complex) -> tuple[complex, complex, complex]:
    """대칭좌표법. 반환 (정상분 I₁, 역상분 I₂, 영상분 I₀)."""
    a, a2 = A_OP, A_OP ** 2
    i1 = (ia + a * ib + a2 * ic) / 3.0
    i2 = (ia + a2 * ib + a * ic) / 3.0
    i0 = (ia + ib + ic) / 3.0
    return i1, i2, i0


def phases_from_components(i1: complex, i2: complex, i0: complex = 0j) -> tuple[complex, complex, complex]:
    """대칭분 → 상 페이저 (symmetrical_components 의 역변환)."""
    a, a2 = A_OP, A_OP ** 2
    return i0 + i1 + i2, i0 + a2 * i1 + a * i2, i0 + a * i1 + a2 * i2


def phasors_from_waveform(sig: np.ndarray, fs: float, f0: float) -> complex:
    """1주기 DFT 로 기본파 페이저를 추출한다 (진폭 = 피크값)."""
    n = int(round(fs / f0))
    if n < 2 or len(sig) < n:
        n = len(sig)
    w = sig[-n:]
    k = np.exp(-2j * np.pi * f0 * np.arange(n) / fs)
    return 2.0 * np.sum(w * k) / n


def unbalance_scale_for_ratio(ratio: float, phase_deg: float = 0.0) -> float:
    """목표 I₂/I₁ 을 만드는 고장상(내부 키 A, 화면 표시 R상) 크기 배율 k 를 역산한다 (legacy).

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


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class CurrentModel:
    """3상 전류 생성기 + 분석기 (method: lut | legacy)."""

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
        # --- v2 (D2/D3) ---
        self.version = int(self.cfg.get("version", 1))
        self.method_requested = str(self.cfg.get("method", "legacy"))
        self.method = "legacy"                      # 실제 동작 방식
        self.method_reason = "method: legacy"
        self.lut = None
        self.lut_sha256 = ""
        rc = self.cfg.get("rated_current_A")
        self.rated_current_A: float | None = float(rc) if rc is not None else None
        self.rated_current_mismatch_pct: float | None = None
        if self.rated_current_A:
            self.rated_current_mismatch_pct = (self.motor.rated_line_A / self.rated_current_A - 1.0) * 100.0
        inh = dict(self.cfg.get("inherent") or {})
        self.inherent_enabled = bool(inh.get("enabled", False)) and inh.get("i2i1") is not None
        self.inherent_i2i1 = float(inh.get("i2i1") or 0.0)
        self.inherent_angle_deg = float(inh.get("angle_deg") or 0.0)
        self._lut_cache: dict[str, dict] = {}
        self._calibrate_targets()
        if self.method_requested == "lut":
            self._init_lut()

    # ------------------------------------------------------------- 초기화
    def _calibrate_targets(self) -> None:
        """(legacy) target_i2i1 이 지정된 케이스는 고장상 배율을 위상까지 고려해 정확히 역산한다.

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

    def _init_lut(self) -> None:
        """method: lut 요청 — 모터 일치·파일·sha256 을 확인하고 LutSource 를 연다. 실패하면 legacy 로 남고 이유를 적는다."""
        target = str(self.cfg.get("motor", "M1"))
        mid = self.cfg.get("motor_id")             # motor_library.electrical_cfg 가 넣는다. 없으면 기준 모터(config/motor.yaml)
        if mid != target and not bool(self.cfg.get("transfer_to_other_motors", False)):
            self.method_reason = (f"LUT 는 {target} 전용 — 현재 모터 {mid or '기준(motor.yaml)'} 에는 legacy 유지 "
                                  f"(transfer_to_other_motors: false)")
            return
        src = self.cfg.get("source") or {}
        rel = src.get("lut")
        if not rel:
            self.method_reason = "source.lut 경로 없음 → legacy"
            return
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.exists(path):
            self.method_reason = f"LUT 파일 없음 ({rel}) → legacy. tools/electrical/import_lut.py 실행"
            print("[current_model] " + self.method_reason, flush=True)
            return
        digest = _sha256(path)
        want = str(src.get("lut_sha256") or "").lower()
        if want and digest.lower() != want:
            self.method_reason = (f"LUT sha256 불일치 ({digest[:12]} != config {want[:12]}) → legacy. "
                                  f"electrical.yaml source.lut_sha256 갱신 필요")
            print("[current_model] " + self.method_reason, flush=True)
            return
        from .lut_source import LutSource
        self.lut = LutSource(path)
        self.lut_sha256 = digest
        self.method = "lut"
        self.method_reason = f"LUT {self.lut.version} ({self.lut.provenance.get('grade', '')}, {self.lut.provenance.get('status', '')})"

    # ------------------------------------------------------------- LUT 조회
    def case_uses_lut(self, case: str) -> bool:
        return self.method == "lut" and isinstance(self.cases.get(case, {}).get("lut"), dict)

    def lut_point(self, case: str) -> dict | None:
        """케이스의 LUT 조회 결과 (캐시). lut 를 쓰지 않는 케이스는 None."""
        if not self.case_uses_lut(case):
            return None
        if case not in self._lut_cache:
            c = self.cases[case]
            spec = c["lut"]
            turns = float(spec.get("turns", 0))
            rf = spec.get("R_f_ohm")
            load = float(c.get("load", 1.0))
            self._lut_cache[case] = self.lut.query(self.lut.turns_to_frac(turns), None if turns <= 0 else float(rf), load * 100.0)
        return self._lut_cache[case]

    def _inherent_phasor(self) -> complex:
        """고유 비대칭 I₂/I₁ 페이저 (I₁ 기준 단위)."""
        if not self.inherent_enabled:
            return 0j
        return self.inherent_i2i1 * np.exp(1j * math.radians(self.inherent_angle_deg))

    def _phasors(self, case: str, i_rated: float) -> np.ndarray:
        """케이스의 3상 기본파 페이저 (피크, 복소). x(t) = |X|·sin(ωt + arg X) 규약 — 모든 상에 같은 규약이라 대칭분이 보존된다."""
        c = self.cases[case]
        load = float(c.get("load", 1.0))
        base_phase = np.array([0.0, -2 * np.pi / 3, 2 * np.pi / 3])
        if self.case_uses_lut(case):
            q = self.lut_point(case)
            r = float(q["i2_over_i1"])
            theta = math.radians(float(q.get("i2_angle_deg") or 0.0))
            i1_lut = float(q.get("i1_A") or 0.0)
            if i1_lut > 0.0 and self.rated_current_A:
                # D3 원 사양 (2026-10-21 승인, 이 건에 한함): 정상분 크기 = LUT 정상분 RMS (상별 RMS 의 대칭 성분, 턴 비율·R_f·부하 격자 보간).
                # 결함 시 I₁ 이 LUT 대로 상승 → r = I/I_n 상승, I₂/I_n 이 LUT 와 일치, 열 모델 pu 가 실제 전류 기준. LUT 는 선전류 I_n 기준이라 기준(선/상) 환산 배율을 곱한다 (Y = 1).
                i1 = math.sqrt(2.0) * i1_lut * (i_rated / float(self.rated_current_A))
            else:
                i1 = math.sqrt(2.0) * i_rated * load                      # LUT 에 I₁ 이 없을 때만 이전 규약 (정격×부하)
            i2 = i1 * (r * np.exp(1j * theta) + self._inherent_phasor())  # 결함 I₂ + 고유 비대칭 (페이저 합)
            return np.array(phases_from_components(i1, i2), dtype=complex)
        # ---- legacy 규칙 (크기 배율 + 위상 shift)
        scale = np.asarray(c["phase_scale"], dtype=float)
        shift = np.deg2rad(np.asarray(c["phase_shift_deg"], dtype=float))
        amp = math.sqrt(2.0) * i_rated * scale * max(load, 0.0 if load == 0 else load)
        if load == 0.0:      # 무부하: 자화전류만 (phase_scale 이 이미 0.33 반영)
            amp = math.sqrt(2.0) * i_rated * scale
        ph = amp * np.exp(1j * (base_phase + shift))
        if self.method == "lut" and c.get("inherent") and self.inherent_enabled:
            i1, i2, i0 = symmetrical_components(*ph)
            ph = np.array(phases_from_components(i1, i2 + i1 * self._inherent_phasor(), i0), dtype=complex)
        return ph

    # ------------------------------------------------------------- 파형 생성
    def waveform(self, t: np.ndarray, case: str = "healthy", basis: str = "rated_line_A") -> np.ndarray:
        """시각 배열 t [s] 에 대한 3상 순시 전류 [A]. 반환 shape (3, len(t))."""
        i_rated = self.motor.rated_current(basis)
        ph = self._phasors(case, i_rated)
        out = np.empty((3, len(t)), dtype=float)
        w = 2 * np.pi * self.f0 * t
        for k in range(3):
            out[k] = abs(ph[k]) * np.sin(w + np.angle(ph[k]))
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
        ang = float(np.degrees(np.angle(i2) - np.angle(i1))) if a1 > 1e-12 and a2 > 1e-12 else None
        if ang is not None:
            ang = (ang + 180.0) % 360.0 - 180.0

        i_rated = self.motor.rated_current(basis)
        r = tuple(float(x / i_rated) for x in rms)
        status = tuple(self.classify(x) for x in r)
        i2_rms = float(a2 / math.sqrt(2))
        i2_in = (i2_rms / self.rated_current_A) if (self.method == "lut" and self.rated_current_A and basis == "rated_line_A") else None
        return CurrentState(
            time_s=float(t[-1]),
            instantaneous_A=(float(I[0, -1]), float(I[1, -1]), float(I[2, -1])),
            rms_A=(float(rms[0]), float(rms[1]), float(rms[2])),
            ratio=r,
            status=status,
            i1_A=float(a1 / math.sqrt(2)),      # 페이저 피크 → RMS 환산
            i2_A=i2_rms,
            i2_over_i1=float(ratio_i2i1),
            case=case,
            basis=basis,
            i2_over_in=i2_in,
            i2_angle_deg=ang,
            source=self.electrical_source(case),
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

    # ------------------------------------------------------------- 근거·요약 (D4/D5)
    def expected_i2i1(self, case: str) -> float | None:
        """케이스의 설계 I₂/I₁ (lut: |결함 I₂ + 고유 I₂|, legacy: target_i2i1). 없으면 None."""
        if self.case_uses_lut(case):
            q = self.lut_point(case)
            z = float(q["i2_over_i1"]) * np.exp(1j * math.radians(float(q.get("i2_angle_deg") or 0.0))) + self._inherent_phasor()
            return float(abs(z))
        t = self.cases[case].get("target_i2i1")
        return float(t) if t is not None else None

    def i2i1_marks(self) -> list[dict]:
        """대시보드 게이지 눈금 (정상/4턴/12턴) — 현재 방식의 설계값."""
        out = []
        for key in ("healthy", "itsc_4turn", "itsc_12turn"):
            if key in self.cases:
                v = self.expected_i2i1(key)
                if v is not None:
                    out.append({"case": key, "label": self.cases[key].get("label", key), "value": round(v, 4)})
        return out

    def electrical_source(self, case: str | None = None) -> dict:
        """근거 배지용 요약. case 를 주면 그 케이스의 LUT 점(턴·R_f·I_f·손실·클램프)도 넣는다."""
        if self.method == "lut":
            prov = self.lut.provenance
            d = {"method": "lut", "grade": prov.get("grade", "등가회로(RMxprt v2+MCCM)"), "status": prov.get("status", "provisional"),
                 "fem_verified": bool(prov.get("fem_verified", False)), "lut_version": self.lut.version, "lut_sha256": self.lut_sha256[:12],
                 "motor": str(self.cfg.get("motor", "M1")), "base_turns_per_phase": self.lut.base_turns,
                 "inherent_i2i1": self.inherent_i2i1 if self.inherent_enabled else 0.0}
        else:
            d = {"method": "legacy", "grade": LEGACY_GRADE, "status": "legacy", "fem_verified": False, "lut_version": None, "lut_sha256": None,
                 "motor": self.cfg.get("motor_id") or "reference", "base_turns_per_phase": None, "inherent_i2i1": 0.0}
        d["reason"] = self.method_reason
        d["rated_current_A"] = self.rated_current_A
        if case is not None:
            d["case"] = case
            d["case_method"] = "lut" if self.case_uses_lut(case) else "legacy"
            d["expected_i2i1"] = self.expected_i2i1(case)
            q = self.lut_point(case)
            if q:
                d.update({"turns": q["turns"], "turn_frac": q["turn_frac"], "R_f_ohm": q["R_f_ohm"], "load_pct": q["load_pct"],
                          "lut_i2_over_i1": q["i2_over_i1"], "lut_i2_over_in": q["i2_over_in"], "lut_i2_angle_deg": q["i2_angle_deg"],
                          "i_f_A": q["i_f_A"], "p_loop_total_W": q["p_loop_total_W"], "clamped": q["clamped"]})
        return d

    def cases_summary(self) -> list[dict]:
        """7 케이스의 근거 요약 (대시보드 케이스 표)."""
        out = []
        for key, c in self.cases.items():
            q = self.lut_point(key)
            out.append({"key": key, "label": c.get("label", key), "method": "lut" if q else "legacy",
                        "expected_i2i1": self.expected_i2i1(key),
                        "turns": (q or {}).get("turns"), "R_f_ohm": (q or {}).get("R_f_ohm"), "load": c.get("load", 1.0)})
        return out

    # ------------------------------------------------------------- 연동
    def winding_current_pu(self, state: CurrentState) -> float:
        """모듈 A 권선 동손 입력용 전류비 (3상 RMS 의 제곱평균 → 등가 1상 pu)."""
        r = np.asarray(state.ratio, dtype=float)
        return float(np.sqrt(np.mean(r ** 2)))

    def loop_loss_W(self, case: str) -> float:
        """ITSC 단락 루프 총손실 P_loop_total [W] (lut 방식 + coupling_to_thermal.loop_loss_to_winding 일 때). 아니면 0."""
        q = self.lut_point(case)
        if not q or not (self.cfg.get("coupling_to_thermal") or {}).get("loop_loss_to_winding", False):
            return 0.0
        return float(q.get("p_loop_total_W") or 0.0)

    def short_loop(self, case: str) -> dict | None:
        """ITSC 단락 루프 파라미터 (없으면 None). lut 방식이면 current_pu 를 LUT I_f / 정격 상전류로 바꾼다."""
        loop = self.cases.get(case, {}).get("short_loop")
        if loop is None:
            return None
        q = self.lut_point(case)
        if q and q.get("i_f_A") is not None:
            loop = dict(loop)
            i_ph = self.motor.rated_current("rated_phase_A")
            loop.update({"current_pu": float(q["i_f_A"]) / i_ph if i_ph else loop.get("current_pu"),
                         "I_f_A": float(q["i_f_A"]), "P_loop_total_W": float(q["p_loop_total_W"]), "R_f_ohm": q["R_f_ohm"]})
        return loop

    @property
    def honesty_label(self) -> str:
        return self.cfg["source"]["honesty_label"]

    @property
    def honesty_sub(self) -> str:
        sub = self.cfg["source"]["honesty_sub"]
        if self.method == "lut":
            sub = sub.replace("전류는 해석식 생성", f"전류는 등가회로 LUT 합성 ({self.lut.provenance.get('grade', '')}, FEM 미검증)")
        return sub
