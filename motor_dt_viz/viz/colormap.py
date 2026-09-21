# -*- coding: utf-8 -*-
"""colormap.py — 값(온도·전류) → 색/발광 매핑. USD 비의존(순수 계산)이라 단위 테스트 가능.

CLAUDE.md §5.2: 정상은 원래 재질 유지(blend 0), 주의는 주황 블렌딩, 경고/위험은 빨강 + 발광,
위험 단계는 0.5~1 Hz 맥동.
"""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config_loader import load  # noqa: E402

Color = tuple[float, float, float]


class ThermalColormap:
    """온도 → (표시색, 발광색, 발광강도)."""

    def __init__(self, cfg: dict | None = None):
        c = cfg or load("colors")
        self.stops = sorted(c["thermal"]["stops"], key=lambda s: s["pos"])
        self.pulse_cfg = c["thermal"]["pulse"]
        self.norm = c["thermal"]["normalize"]
        self.base_materials = c.get("base_materials", {})

    # --------------------------------------------------------------- 정규화
    def position(self, t_C: float, thresholds: dict | None = None) -> float:
        """온도를 부품별 임계값 기준 0~1 위치로 정규화한다.

        절대 온도로 색을 정하면 "로터 80 °C(정상)"와 "베어링 80 °C(주의)"가 같은 색이 되어
        오해를 부른다. 각 부품의 허용 온도 대비 얼마나 뜨거운지를 색으로 표현한다.
        """
        if not thresholds:
            thresholds = {"normal": 70.0, "caution": 90.0, "warning": 110.0}
        n, c, w = float(thresholds["normal"]), float(thresholds["caution"]), float(thresholds["warning"])
        p_c, p_w = float(self.norm["caution_pos"]), float(self.norm["warning_pos"])
        span = float(self.norm["danger_span_C"])
        if t_C <= n:
            return 0.0
        if t_C <= c:
            return p_c * (t_C - n) / max(c - n, 1e-6)
        if t_C <= w:
            return p_c + (p_w - p_c) * (t_C - c) / max(w - c, 1e-6)
        return min(1.0, p_w + (1.0 - p_w) * (t_C - w) / span)

    # --------------------------------------------------------------- 보간
    def _interp(self, pos: float) -> dict:
        st = self.stops
        if pos <= st[0]["pos"]:
            return dict(st[0])
        if pos >= st[-1]["pos"]:
            return dict(st[-1])
        for a, b in zip(st, st[1:]):
            if a["pos"] <= pos <= b["pos"]:
                f = (pos - a["pos"]) / max(b["pos"] - a["pos"], 1e-9)
                lerp = lambda p, q: p + (q - p) * f  # noqa: E731
                return {
                    "color": tuple(lerp(x, y) for x, y in zip(a["color"], b["color"])),
                    "blend": lerp(a["blend"], b["blend"]),
                    "emissive": tuple(lerp(x, y) for x, y in zip(a["emissive"], b["emissive"])),
                    "intensity": lerp(a["intensity"], b["intensity"]),
                }
        return dict(st[-1])

    def base_color(self, part_key: str) -> Color:
        m = self.base_materials.get(part_key)
        return tuple(m["color"]) if m else (0.5, 0.5, 0.5)

    def base_material(self, part_key: str) -> dict:
        return self.base_materials.get(part_key, {"color": [0.5, 0.5, 0.5], "roughness": 0.5, "metallic": 0.0})

    def sample(self, t_C: float, part_key: str | None = None, stage: str = "normal",
               time_s: float = 0.0, thresholds: dict | None = None) -> dict:
        """온도에서 최종 표시 속성을 만든다.

        thresholds: 해당 부품의 {normal, caution, warning} 임계값 (ThermalModel.thresholds()).
                    넘기지 않으면 기본 임계값을 쓴다.
        반환: {diffuse, emissive, intensity, blend, pos}
          diffuse   = 원래 재질색과 열색을 blend 비율로 섞은 값 (정상이면 원래 색 그대로)
          intensity = 발광 강도 (경고 단계부터 맥동 적용)
        """
        pos = self.position(t_C, thresholds)
        s = self._interp(pos)
        base = self.base_color(part_key) if part_key else s["color"]
        b = s["blend"]
        diffuse = tuple(base[i] * (1 - b) + s["color"][i] * b for i in range(3))

        intensity = s["intensity"]
        if self.pulse_cfg.get("enabled", False) and self._pulse_active(stage):
            hz = float(self.pulse_cfg["hz"])
            depth = float(self.pulse_cfg["depth"])
            intensity *= 1.0 + depth * math.sin(2 * math.pi * hz * time_s)
        return {"diffuse": diffuse, "emissive": tuple(s["emissive"]), "intensity": max(intensity, 0.0),
                "blend": b, "pos": pos}

    def _pulse_active(self, stage: str) -> bool:
        order = ("normal", "caution", "warning", "danger")
        start = self.pulse_cfg.get("start_stage", "warning")
        try:
            return order.index(stage) >= order.index(start)
        except ValueError:
            return False


class ElectricalColormap:
    """전류 상태 → 색/발광. 상태 문자열은 CurrentModel.classify() 와 동일하다."""

    def __init__(self, cfg: dict | None = None):
        c = cfg or load("colors")
        self.map = c["electrical"]
        self.phase_colors = c["phases"]
        self.status_colors = c["status"]

    def sample(self, status: str, time_s: float = 0.0) -> dict:
        e = self.map.get(status, self.map["normal"])
        intensity = float(e["intensity"])
        hz = e.get("pulse_hz")
        if hz:
            intensity *= 1.0 + 0.35 * math.sin(2 * math.pi * float(hz) * time_s)
        return {"diffuse": tuple(e["color"]), "emissive": tuple(e["emissive"]),
                "intensity": max(intensity, 0.0)}

    def phase_color(self, phase: str) -> Color:
        return tuple(self.phase_colors[phase])

    def status_color(self, grade: str) -> Color:
        return tuple(self.status_colors.get(grade, [1, 1, 1]))


def blend(a: Color, b: Color, f: float) -> Color:
    """두 색 선형 보간 (경계에서 부드럽게)."""
    f = max(0.0, min(1.0, f))
    return tuple(a[i] * (1 - f) + b[i] * f for i in range(3))
