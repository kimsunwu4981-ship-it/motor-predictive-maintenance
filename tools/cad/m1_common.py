# -*- coding: utf-8 -*-
"""m1_common.py — M1 CAD 생성 공통: 데이터시트 yaml 읽기(키 이름으로만), 좌표계, 내보내기(STEP·OBJ 그룹·GLB), 체적/삼각형 집계.

좌표계: 축 = +X, 적층 중심 = 원점, 단위 mm. 각도 θ 는 YZ 평면에서 +Z(위) 기준, X 축 둘레 회전(오른손).
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import cadquery as cq
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "assets" / "motors" / "M1"
INP = ASSET / "inputs"
DS = INP / "datasheet_v4.yaml"

MATERIALS = {"silicon_steel": {"color": (0.30, 0.31, 0.34)}, "copper": {"color": (0.72, 0.45, 0.20)}, "aluminum": {"color": (0.78, 0.79, 0.81)},
             "steel": {"color": (0.55, 0.56, 0.58)}, "cast_iron": {"color": (0.36, 0.40, 0.44)}}


def load_ds() -> dict:
    return yaml.safe_load(open(DS, encoding="utf-8"))


def dsv(ds: dict, symbol: str, section: str | None = None):
    """설계값 기호 → 값 (section 접두어로 §를 고른다; 없으면 첫 출현)."""
    if section:
        for sec, d in ds["design_sections"].items():
            if sec.startswith(section) and symbol in d:
                return d[symbol]["value"]
        raise KeyError(f"{section} {symbol}")
    return ds["design"][symbol]["value"]


def pol(r: float, theta_deg: float) -> tuple[float, float]:
    """(Y, Z) = 반지름 r, 각 θ(+Z 기준)."""
    t = math.radians(theta_deg)
    return (r * math.sin(t), r * math.cos(t))


def rot_x(shape, theta_deg: float):
    return shape.rotate((0, 0, 0), (1, 0, 0), theta_deg)


def solid_volume(wp) -> float:
    return sum(s.Volume() for s in wp.solids().vals())


# ----------------------------------------------------------------------------- 메시
def tessellate(wp, tol=0.08, ang=0.25):
    """Workplane/Shape → (vertices Nx3, faces Mx3) (여러 솔리드면 이어붙임)."""
    V, F = [], []
    shapes = wp.solids().vals() if hasattr(wp, "solids") else [wp]
    off = 0
    for s in shapes:
        verts, tris = s.tessellate(tol, ang)
        V.extend((v.x, v.y, v.z) for v in verts)
        F.extend((a + off, b + off, c + off) for a, b, c in tris)
        off += len(verts)
    return np.asarray(V, dtype=float), np.asarray(F, dtype=np.int64)


class PartSet:
    """이름 → {shape, material, group, volume, mesh}. 내보내기와 집계."""

    def __init__(self, tag: str):
        self.tag = tag
        self.parts: dict[str, dict] = {}
        self.t0 = time.time()

    def add(self, name: str, wp, material: str, group: str, note: str = "", tol=0.08, ang=0.25):
        V, F = tessellate(wp, tol, ang)
        vol = solid_volume(wp)
        self.parts[name] = {"shape": wp, "material": material, "group": group, "volume_mm3": vol, "V": V, "F": F, "note": note}
        return self.parts[name]

    def triangles(self) -> int:
        return int(sum(len(p["F"]) for p in self.parts.values()))

    def export_obj(self, path: Path, scale=1.0):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {self.tag} — M1 HLP-2.2/4, mm, axis +X, stack center origin\n")
            off = 1
            for name, p in self.parts.items():
                f.write(f"o {name}\nusemtl {p['material']}\n")
                for v in p["V"]:
                    f.write(f"v {v[0] * scale:.4f} {v[1] * scale:.4f} {v[2] * scale:.4f}\n")
                for a, b, c in p["F"]:
                    f.write(f"f {a + off} {b + off} {c + off}\n")
                off += len(p["V"])

    def export_glb(self, path: Path, scale=1.0):
        import trimesh
        scene = trimesh.Scene()
        for name, p in self.parts.items():
            m = trimesh.Trimesh(vertices=p["V"] * scale, faces=p["F"], process=False)
            col = MATERIALS[p["material"]]["color"]
            m.visual = trimesh.visual.ColorVisuals(m, face_colors=[int(c * 255) for c in col] + [255])
            m.metadata["material"] = p["material"]; m.metadata["group"] = p["group"]
            scene.add_geometry(m, node_name=name, geom_name=name)
        scene.export(path)

    def export_step(self, path: Path):
        asm = cq.Assembly(name=self.tag)
        for name, p in self.parts.items():
            asm.add(p["shape"], name=name)
        asm.export(str(path))

    def manifest(self, extra: dict | None = None) -> dict:
        return {"tag": self.tag, "units": "mm", "axis": "+X", "origin": "stack center", "generated_s": round(time.time() - self.t0, 1),
                "triangles_total": self.triangles(),
                "parts": {n: {"material": p["material"], "group": p["group"], "volume_mm3": round(p["volume_mm3"], 3), "triangles": int(len(p["F"])), "note": p["note"]}
                          for n, p in self.parts.items()}, **(extra or {})}


CUT_ROT_DEG = -45.0   # 절단 사분면 회전: Y<0∧Z>0 (θ −90~0°) 를 −45° 돌려 θ −45~+45° (슬롯 1 = +Z 가 절단면 가운데 노출, P4 후속 A4)


def quarter_cutter(size=400.0, rot_deg=CUT_ROT_DEG):
    """1/4 절단용 박스(각도 축 기준 90°): 기본 θ∈[−45°, +45°] — 슬롯 1(+Z)·Coil_01 이 노출된다. 축은 X."""
    box = cq.Workplane("XY").box(size * 2, size, size, centered=(True, False, False)).translate((0, -size, 0))
    return box.rotate((0, 0, 0), (1, 0, 0), rot_deg)


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
