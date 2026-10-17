# -*- coding: utf-8 -*-
"""thermal_model.py — 모듈 A: 집중정수 열회로(Lumped Thermal RC) 모델. Isaac Sim 비의존.

모델:
    C_i · dT_i/dt = P_loss,i(t) − (T_i − T_amb)/R_i + Σ_j (T_j − T_i)/R_ij

모든 계수는 config/thermal.yaml 에서 읽는다 (Hard Rule 4).

단순화 가정 (심사 질의 대비):
  · 부품을 1개 노드로 집중(lumped)하여 내부 온도 분포를 무시한다.
  · 공극 복사·축방향 전도를 상수 R_ij 로 근사한다.
  · 손실 배분(동손 35 / 철손 25 / 회전자 20 / 기계 15 / 표유 5 %)은 일반 유도전동기 관행값이며
    실측 교정 전이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config_loader import load, val


@dataclass
class ThermalNode:
    key: str
    label: str
    capacitance: float        # C_i [J/K]
    r_ambient: float          # R_i [K/W]
    loss_rated_W: float
    loss_model: str
    prim_key: str | None = None


@dataclass
class ThermalState:
    """한 스텝의 결과."""
    time_s: float
    temperature_C: dict[str, float]
    display_C: dict[str, float]       # EMA 적용 표시 온도
    stage: dict[str, str]             # normal | caution | warning | danger
    loss_W: dict[str, float]
    load: float
    vibration_mms: float


class ThermalModel:
    """부품별 온도를 적분한다.

    사용:
        m = ThermalModel()
        st = m.step(dt_sim_s=1.0, load=1.0, faults=["bearing_de_fault"])
    """

    STAGE_ORDER = ("normal", "caution", "warning", "danger")

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or load("thermal")
        self.t_amb = float(self.cfg["ambient"]["temperature_C"])

        nodes_cfg = self.cfg["nodes"]
        self.nodes: list[ThermalNode] = []
        for key, n in nodes_cfg.items():
            self.nodes.append(
                ThermalNode(
                    key=key,
                    label=n["label"],
                    capacitance=float(n["mass_kg"]) * float(n["specific_heat"]),
                    r_ambient=float(n["R_amb"]),
                    loss_rated_W=float(n["loss_W_rated"]),
                    loss_model=n["loss_model"],
                    prim_key=n.get("prim_key"),
                )
            )
        self.index = {n.key: i for i, n in enumerate(self.nodes)}
        self.n = len(self.nodes)

        self.C = np.array([n.capacitance for n in self.nodes], dtype=float)
        self.R_amb0 = np.array([n.r_ambient for n in self.nodes], dtype=float)
        self.P_rated = np.array([n.loss_rated_W for n in self.nodes], dtype=float)

        # 커플링 컨덕턴스 행렬 G[i,j] = 1/R_ij
        self.G = np.zeros((self.n, self.n), dtype=float)
        for a, b, r in self.cfg["couplings"]:
            i, j = self.index[a], self.index[b]
            g = 1.0 / float(r)
            self.G[i, j] = g
            self.G[j, i] = g

        self.T = np.full(self.n, self.t_amb, dtype=float)
        self._disp = self.T.copy()
        self._stage = ["normal"] * self.n
        self.time_s = 0.0

        d = self.cfg["display"]
        self.ema_tau = float(d["ema_tau_s"])
        self.hysteresis = float(d["hysteresis_C"])
        self.max_dt = float(self.cfg["solver"]["max_dt_s"])
        self.method = self.cfg["solver"].get("method", "rk4")
        self._duty_t = 0.0

    # ------------------------------------------------------------------ 손실
    def losses(self, load: float, faults: list[str], winding_current_pu: float | None = None,
               extra_loss_W: dict[str, float] | None = None) -> np.ndarray:
        """부하율·결함·(통합모드) 전류로부터 부품별 손실 [W] 을 계산한다.

        winding_current_pu: 모듈 B 연동 시 권선 전류 비율(I/I_rated). None 이면 부하율로 근사.
        extra_loss_W: {노드: W} 외부 추가 손실 — 모듈 B 의 ITSC 단락 루프 총손실(LUT P_loop_total) 등 (TASK A D4).
        """
        fcfg = self.cfg["faults"]
        load_mult = 1.0
        for f in faults:
            load_mult *= float(fcfg.get(f, {}).get("load_multiplier", 1.0))
        eff_load = load * load_mult

        P = np.zeros(self.n, dtype=float)
        i_pu = winding_current_pu if winding_current_pu is not None else eff_load
        for i, nd in enumerate(self.nodes):
            m = nd.loss_model
            if m == "copper_i2r":
                # 동손 ∝ I². 무부하에서도 자화전류(약 33 %)가 흐른다.
                P[i] = nd.loss_rated_W * max(i_pu, 0.33) ** 2
            elif m == "iron_const":
                P[i] = nd.loss_rated_W                      # 철손: 전압·주파수 의존, 부하 무관
            elif m == "rotor_slip":
                P[i] = nd.loss_rated_W * eff_load ** 2      # 2차 동손 ∝ 슬립×토크 ≈ load²
            elif m == "bearing_friction":
                # 마찰손 ∝ 하중 × 회전속도. 회전속도 일정 → 하중(부하) 의존 부분만 변동
                P[i] = nd.loss_rated_W * (0.4 + 0.6 * eff_load)
            else:
                P[i] = 0.0

        # 결함별 손실 배율·추가 손실
        for f in faults:
            fc = fcfg.get(f)
            if not fc:
                continue
            tgt = fc.get("target")
            if tgt and "loss_multiplier" in fc:
                P[self.index[tgt]] *= float(fc["loss_multiplier"])
            for k, mul in (fc.get("also") or {}).items():
                P[self.index[k]] *= float(mul)
            if tgt and "extra_loss_W" in fc:
                P[self.index[tgt]] += float(fc["extra_loss_W"])
        for k, w in (extra_loss_W or {}).items():
            if k in self.index and w:
                P[self.index[k]] += float(w)
        return P

    def r_ambient(self, faults: list[str]) -> np.ndarray:
        """결함(냉각팬 고장 등)에 따른 대기 열저항."""
        R = self.R_amb0.copy()
        for f in faults:
            fc = self.cfg["faults"].get(f) or {}
            if "r_amb_multiplier" in fc:
                R[self.index[fc["target"]]] *= float(fc["r_amb_multiplier"])
        return R

    def conductance(self, faults: list[str]) -> np.ndarray:
        """결함에 따른 노드 간 컨덕턴스 G = 1/R_ij.

        베어링 결함 시 그리스 탄화·간극 변화로 축·하우징으로의 전도가 나빠진다
        (R_ij 증가 → 국부 발열이 더 크게 나타난다). config 의 coupling_multiplier 로 표현한다.
        """
        G = self.G.copy()
        for f in faults:
            fc = self.cfg["faults"].get(f) or {}
            for a, b, mul in (fc.get("coupling_multiplier") or []):
                i, j = self.index[a], self.index[b]
                g = G[i, j] / float(mul)          # R 이 mul 배 → G 는 1/mul 배
                G[i, j] = G[j, i] = g
        return G

    # ------------------------------------------------------------------ 적분
    def _deriv(self, T: np.ndarray, P: np.ndarray, R: np.ndarray, G: np.ndarray | None = None) -> np.ndarray:
        G = self.G if G is None else G
        amb = (T - self.t_amb) / R
        # Σ_j (T_j − T_i)/R_ij  →  G @ T − T * rowsum(G)
        inter = G @ T - T * G.sum(axis=1)
        return (P - amb + inter) / self.C

    def step(
        self,
        dt_sim_s: float,
        load: float = 1.0,
        faults: list[str] | None = None,
        winding_current_pu: float | None = None,
        use_duty_cycle: bool | None = None,
        extra_loss_W: dict[str, float] | None = None,
    ) -> ThermalState:
        """시뮬레이션 시간 dt_sim_s 만큼 전진한다 (시간 배속은 호출자가 곱해서 넘긴다). extra_loss_W: losses() 참조."""
        faults = faults or []
        if use_duty_cycle is None:
            use_duty_cycle = bool(self.cfg["duty_cycle"].get("enabled", False))

        remaining = float(dt_sim_s)
        eff_load = load
        # dt_sim_s = 0 (전기 전용 모드에서 열을 정지시킬 때)에도 손실과 상태를 보고해야 한다.
        # 루프를 돌지 않으면 P 가 None 으로 남아 ThermalState 생성에서 깨진다.
        P = self.losses(eff_load, faults, winding_current_pu, extra_loss_W)
        R = self.r_ambient(faults)
        while remaining > 1e-12:
            h = min(self.max_dt, remaining)
            eff_load = self._duty_load(load, h) if use_duty_cycle else load
            P = self.losses(eff_load, faults, winding_current_pu, extra_loss_W)
            R = self.r_ambient(faults)
            G = self.conductance(faults)
            if self.method == "euler":
                self.T = self.T + h * self._deriv(self.T, P, R, G)
            else:  # rk4
                k1 = self._deriv(self.T, P, R, G)
                k2 = self._deriv(self.T + 0.5 * h * k1, P, R, G)
                k3 = self._deriv(self.T + 0.5 * h * k2, P, R, G)
                k4 = self._deriv(self.T + h * k3, P, R, G)
                self.T = self.T + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
            self.time_s += h
            remaining -= h

        # 표시 온도 EMA (색 급변 방지)
        alpha = 1.0 - np.exp(-max(dt_sim_s, 1e-6) / max(self.ema_tau, 1e-6))
        self._disp = self._disp + alpha * (self.T - self._disp)
        self._update_stages()

        vib = self._vibration(faults)
        return ThermalState(
            time_s=self.time_s,
            temperature_C={n.key: float(self.T[i]) for i, n in enumerate(self.nodes)},
            display_C={n.key: float(self._disp[i]) for i, n in enumerate(self.nodes)},
            stage={n.key: self._stage[i] for i, n in enumerate(self.nodes)},
            loss_W={n.key: float(P[i]) for i, n in enumerate(self.nodes)},
            load=float(eff_load),
            vibration_mms=vib,
        )

    def _duty_load(self, base_load: float, h: float) -> float:
        """크레인 권상 듀티 사이클(lift→hold→lower→idle)에 따른 순시 부하율."""
        phases = self.cfg["duty_cycle"]["phases"]
        total = sum(float(p["duration_s"]) for p in phases)
        self._duty_t = (self._duty_t + h) % total
        acc = 0.0
        for p in phases:
            acc += float(p["duration_s"])
            if self._duty_t <= acc:
                return base_load * float(p["load"])
        return base_load

    # ------------------------------------------------------------------ 판정
    def thresholds(self, key: str) -> dict:
        s = self.cfg["stages"]
        if key in ("bearing_de", "bearing_nde"):
            return s["bearing"]
        if key == "winding":
            return s["winding"]
        if key == "rotor" and "rotor" in s:
            return s["rotor"]
        return s["default"]

    def _update_stages(self) -> None:
        """히스테리시스를 적용해 단계를 갱신한다 (경계에서 깜빡임 방지)."""
        for i, nd in enumerate(self.nodes):
            th = self.thresholds(nd.key)
            t = self._disp[i]
            cur = self._stage[i]
            hy = self.hysteresis
            if t >= th["warning"] + (0 if cur != "danger" else -hy):
                new = "danger"
            elif t >= th["caution"] + (0 if cur in ("normal", "caution") else -hy):
                new = "warning"
            elif t >= th["normal"] + (0 if cur == "normal" else -hy):
                new = "caution"
            else:
                new = "normal"
            self._stage[i] = new

    def _vibration(self, faults: list[str]) -> float:
        """ISO 20816-3 비교용 대표 진동 속도 [mm/s] (결함 중 최댓값)."""
        base = 1.0
        for f in faults:
            v = (self.cfg["faults"].get(f) or {}).get("vibration_mms")
            if v:
                base = max(base, float(v))
        return base

    # ------------------------------------------------------------------ 유틸
    def reset(self) -> None:
        self.T[:] = self.t_amb
        self._disp[:] = self.t_amb
        self._stage = ["normal"] * self.n
        self.time_s = 0.0
        self._duty_t = 0.0

    def steady_state(self, load: float = 1.0, faults: list[str] | None = None,
                     winding_current_pu: float | None = None) -> dict[str, float]:
        """정상상태 온도를 선형 연립방정식으로 직접 푼다 (튜닝·검증용).

        (diag(1/R) + L) · (T − T_amb) = P,  L = 라플라시안(커플링)
        """
        faults = faults or []
        P = self.losses(load, faults, winding_current_pu)
        R = self.r_ambient(faults)
        G = self.conductance(faults)
        L = np.diag(G.sum(axis=1)) - G
        A = np.diag(1.0 / R) + L
        dT = np.linalg.solve(A, P)
        return {n.key: float(self.t_amb + dT[i]) for i, n in enumerate(self.nodes)}

    @property
    def node_keys(self) -> list[str]:
        return [n.key for n in self.nodes]

    def prim_keys(self) -> dict[str, str]:
        """열 노드 → prim_map.yaml parts 키 (모델에 없는 노드는 제외)."""
        return {n.key: n.prim_key for n in self.nodes if n.prim_key}
