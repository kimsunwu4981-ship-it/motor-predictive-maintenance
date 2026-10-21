# -*- coding: utf-8 -*-
"""write_prim_map_M1.py — assets/motors/M1/prim_map_M1.yaml: 열 노드(9개) ↔ M1.usd prim 그룹 매핑 + 기본 재질색 (코일은 권선 배치표의 상별 색).
config/prim_map.yaml 은 건드리지 않는다 — M1 매핑은 자산 폴더에 둔다.  py -3.12 -X utf8 tools/cad/write_prim_map_M1.py
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]; ASSET = ROOT / "assets" / "motors" / "M1"
ds = yaml.safe_load(open(ASSET / "inputs" / "datasheet_v4.yaml", encoding="utf-8"))
colors = yaml.safe_load(open(ROOT / "motor_dt_viz" / "config" / "colors.yaml", encoding="utf-8"))
phase_rgb = {p: list(v) for p, v in colors["phases"].items()}
phase_of = {w["coil"]: w["phase"] for w in ds["winding_table"]}
coils = {p: [f"/Stator/Coils/Coil_{k:02d}" for k in range(1, 37) if phase_of.get(k) == p] for p in "ABC"}
groups = {
    "winding_A": {"thermal": "winding", "prims": coils["A"], "base_color": phase_rgb["A"], "roughness": 0.4, "metallic": 0.6, "note": "A상 코일 (권선 배치표) — 권선 온도 색 램프"},
    "winding_B": {"thermal": "winding", "prims": coils["B"], "base_color": phase_rgb["B"], "roughness": 0.4, "metallic": 0.6},
    "winding_C": {"thermal": "winding", "prims": coils["C"], "base_color": phase_rgb["C"], "roughness": 0.4, "metallic": 0.6},
    "winding_short": {"thermal": "winding", "prims": ["/Stator/Coils/Coil_01_short"], "base_color": [1.0, 0.10, 0.05], "roughness": 0.4, "metallic": 0.6, "short_loop": True,
                      "note": "Coil_01_short 발광 = p_loop_total_W / p_loop(12턴)"},
    "stator_core": {"thermal": "stator_core", "prims": ["/Stator/Core"], "base_color": [0.30, 0.31, 0.34], "roughness": 0.6, "metallic": 0.3},
    "rotor_core": {"thermal": "rotor", "prims": ["/Rotor/Core"], "base_color": [0.30, 0.31, 0.34], "roughness": 0.6, "metallic": 0.3},
    "rotor_cage": {"thermal": "rotor", "prims": [f"/Rotor/Bars/Bar_{k:02d}" for k in range(1, 29)] + ["/Rotor/EndRing_DE", "/Rotor/EndRing_NDE"], "base_color": [0.80, 0.81, 0.83], "roughness": 0.4, "metallic": 0.9},
    "shaft": {"thermal": "shaft", "prims": ["/Rotor/Shaft"], "base_color": [0.58, 0.59, 0.61], "roughness": 0.35, "metallic": 0.9},
    "bearing_de": {"thermal": "bearing_de", "prims": ["/Bearings/DE"], "base_color": [0.62, 0.63, 0.65], "roughness": 0.3, "metallic": 0.9},
    "bearing_nde": {"thermal": "bearing_nde", "prims": ["/Bearings/NDE"], "base_color": [0.62, 0.63, 0.65], "roughness": 0.3, "metallic": 0.9},
    "endshield_de": {"thermal": "endshield_de", "prims": ["/Housing/EndShield_DE", "/Housing/EndShield_DE_B35"], "base_color": [0.36, 0.40, 0.44], "roughness": 0.7, "metallic": 0.3},
    "endshield_nde": {"thermal": "endshield_nde", "prims": ["/Housing/EndShield_NDE"], "base_color": [0.36, 0.40, 0.44], "roughness": 0.7, "metallic": 0.3},
    "frame": {"thermal": "frame", "prims": ["/Housing/Frame", "/Housing/Foot", "/Housing/TerminalBox", "/Housing/Eyebolt"], "base_color": [0.36, 0.40, 0.44], "roughness": 0.7, "metallic": 0.3},
    "fan_cover": {"thermal": "frame", "prims": ["/Housing/FanCover"], "base_color": [0.36, 0.40, 0.44], "roughness": 0.7, "metallic": 0.3,
                  "note": "냉각팬 고장 장면(파트 C S2): 팬 커버는 하우징(frame) 노드 온도로 색 — 열회로에 팬 노드가 없어 별도 온도는 없다"},
}
doc = {"meta": {"usd": "assets/motors/M1/M1.usd", "root_in_scene": "/World/M1", "rotor_xform": "/World/M1/Rotor xformOp:rotateX", "thermal_nodes": list(dict.fromkeys(g["thermal"] for g in groups.values())),
                "note": "값은 상태 JSON(T, stage, p_loop_total_W, rpm)에서만 온다. 색 램프는 config/colors.yaml ThermalColormap 그대로. 코일 상 배치는 datasheet_v4.yaml winding_table"},
       "groups": groups}
(ASSET / "prim_map_M1.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
print("prim_map_M1.yaml", {p: len(v) for p, v in coils.items()}, "groups", len(groups))
