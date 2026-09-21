# -*- coding: utf-8 -*-
"""config_loader.py — config/*.yaml 로더 (Isaac Sim 비의존).

CLAUDE.md Hard Rule 4: 모든 수치는 config 에서 읽는다. 코드에 하드코딩 금지.
YAML 의 {value:, source:, note:} 래퍼는 val() 로 벗겨서 쓴다.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))


def val(x: Any) -> Any:
    """{value:, source:, note:} 래퍼면 value 를, 아니면 그대로 반환."""
    if isinstance(x, dict) and "value" in x:
        return x["value"]
    return x


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """config/<name>.yaml 로드 (캐시)."""
    path = os.path.join(CONFIG_DIR, f"{name}.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def reload_all() -> None:
    load.cache_clear()


class MotorSpec:
    """motor.yaml 을 속성으로 노출 (단위는 YAML 주석 참조)."""

    def __init__(self, cfg: dict | None = None):
        c = cfg or load("motor")
        r, cur, brg, mech = c["rating"], c["current"], c["bearing"], c["mechanics"]
        self.power_kW = val(r["power_kW"])
        self.poles = int(val(r["poles"]))
        self.voltage_LL = val(r["voltage_LL_V"])
        self.frequency = val(r["frequency_Hz"])
        self.connection = val(r["connection"])
        self.sync_rpm = val(r["sync_rpm"])
        self.rated_rpm = val(r["rated_rpm"])
        self.slip = val(r["slip"])
        self.torque_Nm = val(r["torque_Nm"])
        self.mass_kg = val(r["mass_kg"])
        self.efficiency = val(cur["efficiency"])
        self.power_factor = val(cur["power_factor"])
        self.rated_line_A = val(cur["rated_line_A"])
        self.rated_phase_A = val(cur["rated_phase_A"])
        self.bearing_name = val(brg["designation"])
        self.bpfo_mult = val(brg["bpfo_mult"])
        self.bpfi_mult = val(brg["bpfi_mult"])
        self.rotor_inertia = val(mech["rotor_inertia_kgm2"])

    @property
    def rotor_freq_Hz(self) -> float:
        """정격 회전 주파수 fr [Hz]."""
        return self.rated_rpm / 60.0

    def bpfo_Hz(self, rpm: float | None = None) -> float:
        return self.bpfo_mult * ((rpm or self.rated_rpm) / 60.0)

    def bpfi_Hz(self, rpm: float | None = None) -> float:
        return self.bpfi_mult * ((rpm or self.rated_rpm) / 60.0)

    def rated_current(self, basis: str) -> float:
        """basis: 'rated_line_A' | 'rated_phase_A' — Δ결선 기준 혼용 방지."""
        if basis == "rated_line_A":
            return self.rated_line_A
        if basis == "rated_phase_A":
            return self.rated_phase_A
        raise ValueError(f"알 수 없는 전류 기준: {basis}")
