# -*- coding: utf-8 -*-
"""demo_state.py — 패널과 메인 루프가 공유하는 상태 (패널 Q1, 2026-10-27 — 전기 결함 전용).

예전 ui/control_panel.py 의 DemoState 에서 모드 선택을 뺐다: mode 는 "electrical" 로 고정(필드는 state 송신·로그 호환을 위해 남긴다).
기계 결함 토글(thermal_faults)은 시나리오 프레임 호환용 빈 목록이다. 옛 패널은 _legacy/ui/control_panel.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MODE = "electrical"           # 전기 전용 — 바꾸지 않는다


@dataclass
class ManualFault:
    """패널(USD 속성)에서 온 수동 결함 사양. 값은 LUT 격자 안(턴·R_f)이고 계산은 엔진(CurrentModel lut)이 한다."""
    phase: str = "A"          # 내부 키 A|B|C (표시 이름은 config electrical.yaml phase_labels)
    coil: str = "Coil_01"     # USD 코일 프림 이름
    turns: int = 0            # 0 = 정상
    R_f_ohm: float = 0.1
    unbalance: float = 0.0    # 0 = 없음, >0 = config 의 voltage_unbalance 케이스(고정)

    def to_dict(self) -> dict:
        return {"phase": self.phase, "coil": self.coil, "turns": int(self.turns), "R_f_ohm": float(self.R_f_ohm), "unbalance": float(self.unbalance)}


@dataclass
class DemoState:
    mode: str = MODE
    load: float = 1.0
    time_scale: float = 120.0
    slowmo: float = 1.0 / 60.0
    thermal_faults: list[str] = field(default_factory=list)   # 전기 전용에선 항상 빈 목록 (시나리오 프레임 호환)
    electrical_case: str = "healthy"
    playing_scenario: bool = False
    request_reset: bool = False
    request_play: bool = False
    request_mode_reset: bool = False     # 핫 모터 스위치 뒤 잔상 제거 요청 (모드 전환은 없다)
    highlight_short_loop: bool = False
    housing_opacity: float = 0.68
    dirty: bool = True
    control_source: str = "scenario"     # "manual" | "scenario" — 마지막으로 결함을 정한 쪽
    manual: ManualFault = field(default_factory=ManualFault)
    fault_phase: str = "A"               # 현재 적용 중인 결함 상 (파형 상 순환 — 수동일 때만 A 가 아닐 수 있다)

    def snapshot(self) -> dict:
        return {"mode": self.mode, "load": self.load, "time_scale": self.time_scale,
                "case": self.electrical_case, "scenario": self.playing_scenario, "control_source": self.control_source, "manual": self.manual.to_dict()}
