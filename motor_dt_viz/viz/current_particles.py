# -*- coding: utf-8 -*-
"""current_particles.py — 전류 입자 시각화 (UsdGeom.Points 한 prim 에 위치 배열 갱신).

CLAUDE.md §6.2: 입자마다 prim 을 만들지 말 것 (성능). 모든 경로의 입자를 하나의 Points prim 에 담고
매 갱신마다 points / displayColor 배열만 교체한다.

이동 규칙:
  · 속도 ∝ 순시 전류 크기, 방향 = 전류 부호 (교류 방향 반전이 눈에 보이게)
  · 60 Hz 는 육안으로 볼 수 없으므로 슬로모션 배속을 적용한다 (config electrical.slowmo)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pxr import Gf, UsdGeom, Vt

from engine.config_loader import load
from viz.colormap import ElectricalColormap

POINTS_PATH = "/World/CurrentPaths/Particles"


class CurrentParticles:
    """경로별 입자 묶음을 하나의 Points prim 으로 렌더한다."""

    def __init__(self, stage, builder, elec: dict | None = None, colors: dict | None = None,
                 per_path: int | None = None):
        """per_path: config 의 count_per_path 를 덮어쓴다 (저사양 PC 용 --low 프리셋)."""
        self.stage = stage
        self.builder = builder
        self.elec = elec or load("electrical")
        self.cmap = ElectricalColormap(colors)
        p = self.elec["particles"]
        self.per_path = int(per_path if per_path is not None else p["count_per_path"])
        self.size = float(p["size_m"])
        self.speed_gain = float(p["speed_gain"])
        self.slowmo = float(self.elec["slowmo"]["factor"])

        self.tracks: list[str] = []          # 입자를 태울 경로 이름
        self.offsets: dict[str, list[float]] = {}
        self.prim = UsdGeom.Points.Define(stage, POINTS_PATH)
        self.prim.CreatePointsAttr(Vt.Vec3fArray([]))
        self.prim.CreateWidthsAttr(Vt.FloatArray([]))
        self.prim.CreateDisplayColorAttr(Vt.Vec3fArray([]))
        # 입자마다 색이 다르므로 vertex 보간이어야 한다 (기본 constant 면 렌더러가 경고하고 첫 색만 쓴다)
        self.prim.GetDisplayColorPrimvar().SetInterpolation(UsdGeom.Tokens.vertex)
        self.prim.SetWidthsInterpolation(UsdGeom.Tokens.vertex)

    def attach(self, names: list[str]) -> None:
        """입자를 흘릴 경로를 등록한다 (경로별로 등간격 초기 위치)."""
        self.tracks = list(names)
        self.offsets = {n: [i / self.per_path for i in range(self.per_path)] for n in self.tracks}

    # ------------------------------------------------------------------ 갱신
    def update(self, dt_s: float, phase_current: dict[str, float], phase_status: dict[str, str],
               time_s: float, i_rated: dict[str, float]) -> int:
        """입자를 전진시키고 Points 배열을 교체한다.

        phase_current: 경로 이름 → 순시 전류 [A] (부호 포함)
        phase_status : 경로 이름 → 상태 문자열 (over_danger/normal/...)
        i_rated      : 경로 이름 → 해당 경로의 정격 전류 (선/상 기준을 섞지 않기 위해 경로별로 받는다)
        """
        pts: list[Gf.Vec3f] = []
        cols: list[Gf.Vec3f] = []
        widths: list[float] = []
        for name in self.tracks:
            i_now = phase_current.get(name, 0.0)
            rated = max(i_rated.get(name, 1.0), 1e-6)
            # 정규화 전류 → 이동 속도(경로 길이 비율 / 초).
            # 슬로모션은 호출자가 전류를 샘플링하는 시간축에 적용한다(i_now 가 이미 느려진 파형).
            # 입자는 실제 경과 시간으로 움직여야 화면에서 부드럽다.
            v = (i_now / rated) * self.speed_gain
            step = v * dt_s
            col = self.cmap.sample(phase_status.get(name, "normal"), time_s)
            c = Gf.Vec3f(*col["diffuse"])
            w = self.size * (1.0 + 0.6 * min(abs(i_now) / rated, 2.0))
            offs = self.offsets[name]
            for k in range(len(offs)):
                offs[k] = (offs[k] + step) % 1.0
                pts.append(Gf.Vec3f(*self.builder.sample(name, offs[k])))
                cols.append(c)
                widths.append(w)
        self.prim.GetPointsAttr().Set(Vt.Vec3fArray(pts))
        self.prim.GetDisplayColorAttr().Set(Vt.Vec3fArray(cols))
        self.prim.GetWidthsAttr().Set(Vt.FloatArray(widths))
        return len(pts)

    def set_visible(self, visible: bool) -> None:
        img = UsdGeom.Imageable(self.prim)
        img.MakeVisible() if visible else img.MakeInvisible()

    @property
    def count(self) -> int:
        return len(self.tracks) * self.per_path
