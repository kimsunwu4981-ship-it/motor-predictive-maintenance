# -*- coding: utf-8 -*-
"""fault_injector.py — 결함 주입 상태 관리. Isaac Sim 비의존.

모듈 A(열)의 결함 토글과 모듈 B(전류)의 케이스 선택을 한곳에서 관리해
제어 패널·시나리오 플레이어가 동일한 인터페이스를 쓰게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config_loader import load


@dataclass
class FaultState:
    thermal_faults: list[str] = field(default_factory=list)
    electrical_case: str = "healthy"
    load: float = 1.0

    def copy(self) -> "FaultState":
        return FaultState(list(self.thermal_faults), self.electrical_case, self.load)


class FaultInjector:
    """결함 토글·케이스 선택을 검증하고 상태로 보관한다."""

    def __init__(self, thermal_cfg: dict | None = None, electrical_cfg: dict | None = None):
        self.thermal_cfg = thermal_cfg or load("thermal")
        self.electrical_cfg = electrical_cfg or load("electrical")
        self.available_thermal = list(self.thermal_cfg["faults"].keys())
        self.available_cases = list(self.electrical_cfg["cases"].keys())
        self.state = FaultState()

    # ------------------------------------------------------------ 열 결함
    def toggle(self, name: str, on: bool | None = None) -> list[str]:
        """열 결함 토글. on=None 이면 반전."""
        if name not in self.available_thermal:
            raise KeyError(f"알 수 없는 결함: {name} (가능: {self.available_thermal})")
        cur = name in self.state.thermal_faults
        want = (not cur) if on is None else bool(on)
        if want and not cur:
            self.state.thermal_faults.append(name)
        elif not want and cur:
            self.state.thermal_faults.remove(name)
        return list(self.state.thermal_faults)

    def set_thermal_faults(self, names: list[str]) -> list[str]:
        for n in names:
            if n not in self.available_thermal:
                raise KeyError(f"알 수 없는 결함: {n}")
        self.state.thermal_faults = list(names)
        return list(self.state.thermal_faults)

    # ------------------------------------------------------------ 전기 케이스
    def set_case(self, case: str) -> str:
        if case not in self.available_cases:
            raise KeyError(f"알 수 없는 케이스: {case} (가능: {self.available_cases})")
        self.state.electrical_case = case
        return case

    def set_load(self, load: float) -> float:
        self.state.load = max(0.0, min(float(load), 1.5))   # 제어 패널 슬라이더 0~150 %
        return self.state.load

    def reset(self) -> FaultState:
        self.state = FaultState()
        return self.state

    # ------------------------------------------------------------ 조회
    def label(self, name: str) -> str:
        if name in self.thermal_cfg["faults"]:
            return self.thermal_cfg["faults"][name].get("label", name)
        if name in self.electrical_cfg["cases"]:
            return self.electrical_cfg["cases"][name].get("label", name)
        return name

    def active_labels(self) -> list[str]:
        out = [self.label(f) for f in self.state.thermal_faults]
        if self.state.electrical_case != "healthy":
            out.append(self.label(self.state.electrical_case))
        return out

    def vibration_mms(self) -> float:
        """활성 열 결함 중 최대 진동 속도 [mm/s]."""
        v = 1.0
        for f in self.state.thermal_faults:
            fv = (self.thermal_cfg["faults"].get(f) or {}).get("vibration_mms")
            if fv:
                v = max(v, float(fv))
        return v

    def iso_zone(self, vib_mms: float | None = None) -> str:
        """ISO 20816-3 Group 2 판정: A/B(정상) → Watch → Plan → Act."""
        v = self.vibration_mms() if vib_mms is None else vib_mms
        m = load("motor")["vibration_iso20816_3"]
        if v >= float(m["act_mms"]["value"]):
            return "Act"
        if v >= float(m["plan_mms"]["value"]):
            return "Plan"
        if v >= float(m["watch_mms"]["value"]):
            return "Watch"
        return "Normal"
