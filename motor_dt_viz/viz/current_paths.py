# -*- coding: utf-8 -*-
"""current_paths.py — 전류가 흐르는 경로를 BasisCurves 로 절차 생성 (USD 의존).

3D 모델에 전원 케이블과 고정자 권선이 없으므로(Phase 0 확인) 직접 만든다.
  1) 공급 케이블 3상 라인: 전원 → 단자함  (판정 기준 = 선전류)
  2) 고정자 권선 오버레이: 슬롯 위치를 따라 상 A/B/C 코일 (판정 기준 = 상전류)
  3) ITSC 단락 루프: 고장상 권선 일부를 감싸는 작은 루프

좌표 규약: 모터 축선 = +X, 원점 = DE 축단 끝면 중심 (prim_map.yaml meta).

단순화 가정:
  · 실제 6극 3상 권선은 36슬롯 분포권이지만, 여기서는 상당 3개 코일로 축약해 형태만 재현한다.
  · 코일 단면·절연·쐐기는 모사하지 않는다 (흐름을 보여주는 것이 목적).
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pxr import Gf, Sdf, UsdGeom, UsdShade, Vt

from engine.config_loader import load

PATHS_ROOT = "/World/CurrentPaths"
PHASES = ("A", "B", "C")


def _polyline(stage, path: str, points: list[tuple[float, float, float]], width: float,
              color=(0.5, 0.5, 0.5)) -> UsdGeom.BasisCurves:
    """열린 폴리라인 커브 하나를 만든다."""
    c = UsdGeom.BasisCurves.Define(stage, path)
    c.CreateTypeAttr("linear")
    c.CreateWrapAttr("nonperiodic")
    c.CreateCurveVertexCountsAttr([len(points)])
    c.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in points]))
    c.CreateWidthsAttr(Vt.FloatArray([width] * len(points)))
    c.SetWidthsInterpolation(UsdGeom.Tokens.vertex)
    c.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return c


class CurrentPathBuilder:
    """경로 지오메트리를 만들고, 경로를 따라 위치를 샘플링하는 기능을 제공한다."""

    def __init__(self, stage, prim_map: dict | None = None, elec: dict | None = None):
        self.stage = stage
        self.prim_map = prim_map or load("prim_map")
        self.elec = elec or load("electrical")
        self.paths: dict[str, dict] = {}     # name → {"prim", "pts", "kind", "phase", "basis"}
        UsdGeom.Scope.Define(stage, PATHS_ROOT)

    # ------------------------------------------------------------ 기하 파라미터
    def _winding_geometry(self) -> dict:
        hint = (self.prim_map.get("absent_parts", {}).get("stator_winding", {}) or {}).get("geometry_hint", {})
        r = float(hint.get("bore_radius_m", 0.170)) * 0.92     # 슬롯은 보어보다 약간 안쪽
        span = hint.get("axial_span_m", [0.295, 0.555])
        return {"radius": r, "x0": float(span[0]), "x1": float(span[1])}

    def _cable_entry(self) -> tuple[float, float, float]:
        p = (self.prim_map.get("absent_parts", {}).get("power_cable", {}) or {}).get("entry_point_m")
        return tuple(p) if p else (0.425, 0.0, 0.350)

    # ------------------------------------------------------------ 1) 공급 케이블
    def build_cables(self, width: float = 0.012) -> list[str]:
        """전원(왼쪽 위 바깥) → 단자함 상면. 3상을 나란히 배치한다."""
        ex, ey, ez = self._cable_entry()
        made = []
        for i, ph in enumerate(PHASES):
            dy = (i - 1) * 0.045                     # 3선 간격
            pts = [
                (ex - 0.95, ey + dy, ez + 0.62),     # 전원 측
                (ex - 0.62, ey + dy, ez + 0.52),
                (ex - 0.34, ey + dy, ez + 0.33),
                (ex - 0.16, ey + dy, ez + 0.14),
                (ex - 0.05, ey + dy, ez + 0.03),
                (ex, ey + dy, ez),                   # 단자함 진입
            ]
            path = f"{PATHS_ROOT}/cable_{ph}"
            prim = _polyline(self.stage, path, pts, width)
            self.paths[f"cable_{ph}"] = {"prim": prim, "pts": pts, "kind": "cable",
                                         "phase": ph, "basis": "rated_line_A"}
            made.append(path)
        return made

    # ------------------------------------------------------------ 2) 권선 오버레이
    def build_windings(self, coils_per_phase: int = 3, width: float = 0.010) -> list[str]:
        """상별 코일을 원주에 분산 배치한다 (6극 → 극 피치 60°)."""
        g = self._winding_geometry()
        r, x0, x1 = g["radius"], g["x0"], g["x1"]
        pole_pitch = math.radians(60.0)              # 6극
        made = []
        for i, ph in enumerate(PHASES):
            base = math.radians(120.0 * i / 3.0)     # 상간 40° 오프셋
            pts: list[tuple[float, float, float]] = []
            for k in range(coils_per_phase):
                a0 = base + k * math.radians(120.0)
                a1 = a0 + pole_pitch
                # 슬롯 A 에서 축방향 진행
                pts += [(x0, r * math.cos(a0), r * math.sin(a0)),
                        (x1, r * math.cos(a0), r * math.sin(a0))]
                # NDE 측 엔드와인딩 (원호)
                for t in range(1, 6):
                    a = a0 + (a1 - a0) * t / 5.0
                    pts.append((x1 + 0.045 * math.sin(math.pi * t / 5), r * math.cos(a), r * math.sin(a)))
                # 슬롯 B 에서 축방향 역진행
                pts += [(x1, r * math.cos(a1), r * math.sin(a1)),
                        (x0, r * math.cos(a1), r * math.sin(a1))]
                # DE 측 엔드와인딩으로 복귀
                for t in range(1, 6):
                    a = a1 + (a0 + math.radians(120.0) - a1) * t / 5.0
                    pts.append((x0 - 0.045 * math.sin(math.pi * t / 5), r * math.cos(a), r * math.sin(a)))
            path = f"{PATHS_ROOT}/winding_{ph}"
            prim = _polyline(self.stage, path, pts, width)
            self.paths[f"winding_{ph}"] = {"prim": prim, "pts": pts, "kind": "winding",
                                           "phase": ph, "basis": "rated_phase_A"}
            made.append(path)
        return made

    # ------------------------------------------------------------ 3) ITSC 단락 루프
    def build_short_loop(self, phase: str = "A", width: float = 0.014) -> str:
        """고장상 권선의 일부 턴을 감싸는 작은 닫힌 루프 (ITSC 연출용)."""
        g = self._winding_geometry()
        r, x0, x1 = g["radius"], g["x0"], g["x1"]
        i = PHASES.index(phase)
        a = math.radians(120.0 * i / 3.0) + math.radians(30.0)
        xc = (x0 + x1) / 2
        pts = []
        for t in range(25):                          # 축 주위를 감는 작은 타원 루프
            u = 2 * math.pi * t / 24
            da = math.radians(9.0) * math.cos(u)
            dx = 0.055 * math.sin(u)
            pts.append((xc + dx, (r + 0.012) * math.cos(a + da), (r + 0.012) * math.sin(a + da)))
        path = f"{PATHS_ROOT}/short_loop"
        prim = _polyline(self.stage, path, pts, width, color=(1.0, 0.05, 0.05))
        self.paths["short_loop"] = {"prim": prim, "pts": pts, "kind": "short_loop",
                                    "phase": phase, "basis": "rated_phase_A"}
        return path

    def build_all(self) -> dict:
        return {"cables": self.build_cables(), "windings": self.build_windings(),
                "short_loop": self.build_short_loop()}

    # ------------------------------------------------------------ 샘플링·색
    def sample(self, name: str, s: float) -> tuple[float, float, float]:
        """경로 파라미터 s∈[0,1] 위치의 좌표 (입자 이동용)."""
        pts = self.paths[name]["pts"]
        if len(pts) < 2:
            return pts[0]
        s = s % 1.0
        f = s * (len(pts) - 1)
        i = int(f)
        t = f - i
        a, b = pts[i], pts[min(i + 1, len(pts) - 1)]
        return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))

    def set_color(self, name: str, color: tuple[float, float, float]) -> None:
        info = self.paths.get(name)
        if info:
            info["prim"].GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))

    def set_visible(self, name: str, visible: bool) -> None:
        info = self.paths.get(name)
        if info:
            UsdGeom.Imageable(info["prim"]).MakeVisible() if visible else UsdGeom.Imageable(info["prim"]).MakeInvisible()

    def names(self, kind: str | None = None) -> list[str]:
        return [k for k, v in self.paths.items() if kind is None or v["kind"] == kind]
