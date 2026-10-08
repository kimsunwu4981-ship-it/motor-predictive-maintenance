# -*- coding: utf-8 -*-
"""scenario_player.py — 자동 재생 시나리오 진행기. Isaac Sim 비의존.

config/scenario.yaml 의 steps 를 벽시계 시간에 따라 진행하며,
각 시점의 (모드, 부하, 시간배속, 전기 케이스, 열 결함, 자막)을 돌려준다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config_loader import load
from .fault_injector import FaultState


@dataclass
class ScenarioFrame:
    step_id: str
    label: str
    subtitle: str
    subtitle_en: str
    source: str
    source_en: str
    mode: str
    load: float
    time_scale: float
    electrical_case: str
    thermal_faults: list[str]
    step_elapsed_s: float
    step_duration_s: float
    total_elapsed_s: float
    total_duration_s: float
    finished: bool
    highlight: bool = False

    @property
    def step_progress(self) -> float:
        return min(self.step_elapsed_s / self.step_duration_s, 1.0) if self.step_duration_s > 0 else 1.0

    @property
    def total_progress(self) -> float:
        return min(self.total_elapsed_s / self.total_duration_s, 1.0) if self.total_duration_s > 0 else 1.0

    def to_fault_state(self) -> FaultState:
        return FaultState(list(self.thermal_faults), self.electrical_case, self.load)


def fill_vars(text: str, values: dict | None) -> str:
    """자막의 {변수} 를 채운다. 없는 변수는 그대로 둔다 (테스트가 잡는다). 숫자는 정수면 그대로, 아니면 소수 1자리."""
    if not text or not values:
        return text
    def one(m):
        v = values.get(m.group(1))
        if v is None:
            return m.group(0)
        if isinstance(v, float):
            return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:.1f}"
        return str(v)
    return re.sub(r"\{([a-zA-Z0-9_]+)\}", one, text)


class ScenarioPlayer:
    """벽시계 시간을 누적해 현재 단계를 결정한다."""

    # 모드별 시나리오 파일. 기계/전기 전용은 각자 config 를 갖는다.
    CONFIG_BY_MODE = {
        "mechanical": "scenario_mechanical",
        "electrical": "scenario_electrical",
        "integrated": "scenario",
    }

    def __init__(self, cfg: dict | None = None, name: str = "scenario"):
        """name: config/<name>.yaml — 또는 for_mode() 로 모드에서 고른다."""
        self.name = name
        self.cfg = cfg or load(name)
        self.steps = self.cfg["steps"]
        self.total_duration = sum(float(s["duration_s"]) for s in self.steps)
        self.elapsed = 0.0
        self.playing = False

    @classmethod
    def for_mode(cls, mode: str) -> "ScenarioPlayer":
        """모드에 맞는 시나리오 파일로 플레이어를 만든다."""
        return cls(name=cls.CONFIG_BY_MODE.get(mode, "scenario"))

    def start(self) -> None:
        self.elapsed = 0.0
        self.playing = True

    def stop(self) -> None:
        self.playing = False

    def reset(self) -> None:
        self.elapsed = 0.0
        self.playing = False

    def advance(self, dt_wall_s: float) -> ScenarioFrame:
        """벽시계 dt 만큼 진행하고 현재 프레임을 반환한다."""
        if self.playing:
            self.elapsed = min(self.elapsed + float(dt_wall_s), self.total_duration)
        return self.frame_at(self.elapsed)

    def frame_at(self, t: float) -> ScenarioFrame:
        t = max(0.0, min(float(t), self.total_duration))
        acc = 0.0
        step = self.steps[-1]
        step_elapsed = float(step["duration_s"])
        for s in self.steps:
            d = float(s["duration_s"])
            if t < acc + d or s is self.steps[-1]:
                step = s
                step_elapsed = t - acc
                break
            acc += d
        finished = t >= self.total_duration
        return ScenarioFrame(
            step_id=step["id"],
            label=step["label"],
            subtitle=step["subtitle"],
            subtitle_en=step.get("subtitle_en", step["subtitle"]),
            source=step.get("source", ""),
            source_en=step.get("source_en", step.get("source", "")),
            mode=step.get("mode", "integrated"),
            load=float(step.get("load", 1.0)),
            time_scale=float(step.get("time_scale", 60.0)),
            electrical_case=step.get("electrical_case", "healthy"),
            thermal_faults=list(step.get("faults", [])),
            step_elapsed_s=max(step_elapsed, 0.0),
            step_duration_s=float(step["duration_s"]),
            total_elapsed_s=t,
            total_duration_s=self.total_duration,
            finished=finished,
            highlight=bool(step.get("highlight", False)),
        )

    def manual_defaults(self) -> ScenarioFrame:
        d = self.cfg["manual_defaults"]
        return ScenarioFrame(
            step_id="manual",
            label="수동 모드",
            subtitle="",
            subtitle_en="",
            source="",
            source_en="",
            mode=d.get("mode", "integrated"),
            load=float(d.get("load", 1.0)),
            time_scale=float(d.get("time_scale", 60.0)),
            electrical_case=d.get("electrical_case", "healthy"),
            thermal_faults=list(d.get("faults", [])),
            step_elapsed_s=0.0,
            step_duration_s=0.0,
            total_elapsed_s=0.0,
            total_duration_s=0.0,
            finished=False,
        )
