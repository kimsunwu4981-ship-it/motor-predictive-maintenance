# -*- coding: utf-8 -*-
"""dump_prims.py — Phase 0: USD 스테이지 prim 트리 + 머티리얼 바인딩 조사 (읽기 전용).

원본 USD 는 열기만 하고 절대 수정/저장하지 않는다 (Hard Rule 2).
Isaac Sim 4.5 headless 로 실행:
  C:\\ISSACS~1\\python.bat motor_dt_viz\\tools\\dump_prims.py --stage <usd> --out <md> --json <json>
"""
import sys, os, json, argparse, traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "docs")
os.makedirs(OUT_DIR, exist_ok=True)

def _hook(t, v, tb):
    with open(os.path.join(OUT_DIR, "dump_prims_error.txt"), "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook

ap = argparse.ArgumentParser()
ap.add_argument("--stage", required=True)
ap.add_argument("--out", default=os.path.join(OUT_DIR, "prim_inventory.md"))
ap.add_argument("--json", default=os.path.join(OUT_DIR, "prim_inventory.json"))
args = ap.parse_args()

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb
carb.settings.get_settings().set("/physics/cudaDevice", -1)

from isaacsim.core.utils.stage import open_stage, get_current_stage
from pxr import Usd, UsdGeom, UsdShade, UsdPhysics, PhysxSchema, Sdf

open_stage(os.path.abspath(args.stage))
stage = get_current_stage()

bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy", "guide"])

def bound_material(prim):
    """이 prim 에 실제 바인딩된 머티리얼 경로와, 그 머티리얼이 몇 개 prim 에 공유되는지."""
    try:
        mat, rel = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        return str(mat.GetPath()) if mat else None
    except Exception:
        return None

rows = []
mat_users = {}
for prim in stage.Traverse():
    path = str(prim.GetPath())
    t = prim.GetTypeName()
    entry = {
        "path": path,
        "type": t,
        "name": prim.GetName(),
        "kind": None,
        "purpose": None,
        "material": None,
        "is_gprim": bool(prim.IsA(UsdGeom.Gprim)),
        "is_mesh": bool(prim.IsA(UsdGeom.Mesh)),
        "points": None,
        "bbox_min": None,
        "bbox_max": None,
        "apis": [],
        "children": len(prim.GetChildren()),
    }
    # 적용된 스키마 API (물리 관련)
    for api, label in ((UsdPhysics.RigidBodyAPI, "RigidBody"), (UsdPhysics.CollisionAPI, "Collision"),
                       (UsdPhysics.MassAPI, "Mass"), (UsdPhysics.ArticulationRootAPI, "ArticulationRoot")):
        try:
            if prim.HasAPI(api):
                entry["apis"].append(label)
        except Exception:
            pass
    if prim.IsA(UsdPhysics.Joint):
        entry["apis"].append("Joint:" + t)
    if prim.IsA(UsdGeom.Imageable):
        try:
            entry["purpose"] = str(UsdGeom.Imageable(prim).GetPurposeAttr().Get())
        except Exception:
            pass
    if prim.IsA(UsdGeom.Mesh):
        pts = UsdGeom.Mesh(prim).GetPointsAttr().Get()
        entry["points"] = len(pts) if pts else 0
    if entry["is_gprim"]:
        m = bound_material(prim)
        entry["material"] = m
        if m:
            mat_users.setdefault(m, []).append(path)
        try:
            r = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
            mn, mx = r.GetMin(), r.GetMax()
            entry["bbox_min"] = [round(v, 4) for v in mn]
            entry["bbox_max"] = [round(v, 4) for v in mx]
        except Exception:
            pass
    rows.append(entry)

stage_info = {
    "stage": os.path.abspath(args.stage),
    "upAxis": UsdGeom.GetStageUpAxis(stage),
    "metersPerUnit": UsdGeom.GetStageMetersPerUnit(stage),
    "kilogramsPerUnit": UsdPhysics.GetStageKilogramsPerUnit(stage),
    "prim_count": len(rows),
    "material_shared": {m: len(u) for m, u in mat_users.items()},
}
with open(args.json, "w", encoding="utf-8") as f:
    json.dump({"stage_info": stage_info, "prims": rows, "material_users": mat_users}, f, ensure_ascii=False, indent=2)

# ---- 마크다운 리포트 ----
L = []
L.append("# prim_inventory.md — USD 스테이지 prim 트리 및 머티리얼 바인딩 현황")
L.append("")
L.append("> Phase 0 산출물. 생성 스크립트: `motor_dt_viz/tools/dump_prims.py` (읽기 전용, 원본 USD 무수정)")
L.append("")
L.append("## 스테이지 정보")
L.append("")
L.append("| 항목 | 값 |")
L.append("|---|---|")
L.append(f"| 파일 | `{stage_info['stage']}` |")
L.append(f"| upAxis | {stage_info['upAxis']} |")
L.append(f"| metersPerUnit | {stage_info['metersPerUnit']} |")
L.append(f"| kilogramsPerUnit | {stage_info['kilogramsPerUnit']} |")
L.append(f"| 총 prim 수 | {stage_info['prim_count']} |")
L.append("")
L.append("## prim 트리")
L.append("")
L.append("```")
for r in rows:
    depth = r["path"].count("/") - 1
    ind = "  " * max(depth, 0)
    extra = []
    if r["apis"]:
        extra.append(",".join(r["apis"]))
    if r["points"] is not None:
        extra.append(f"{r['points']}pts")
    if r["purpose"] and r["purpose"] != "default":
        extra.append(f"purpose={r['purpose']}")
    L.append(f"{ind}{r['name']} <{r['type']}>" + (("  [" + " | ".join(extra) + "]") if extra else ""))
L.append("```")
L.append("")
L.append("## 지오메트리 prim 과 머티리얼 바인딩")
L.append("")
L.append("| prim 경로 | 타입 | 포인트 | bbox(m) X | Y | Z | 바인딩 머티리얼 | 공유 수 |")
L.append("|---|---|---|---|---|---|---|---|")
for r in rows:
    if not r["is_gprim"]:
        continue
    mn, mx = r["bbox_min"], r["bbox_max"]
    fx = f"{mn[0]:.3f}~{mx[0]:.3f}" if mn else "-"
    fy = f"{mn[1]:.3f}~{mx[1]:.3f}" if mn else "-"
    fz = f"{mn[2]:.3f}~{mx[2]:.3f}" if mn else "-"
    mat = r["material"] or "(없음)"
    shared = stage_info["material_shared"].get(r["material"], 0) if r["material"] else 0
    warn = " ⚠️공유" if shared > 1 else ""
    L.append(f"| `{r['path']}` | {r['type']} | {r['points'] if r['points'] is not None else '-'} | {fx} | {fy} | {fz} | `{mat}`{warn} | {shared} |")
L.append("")
L.append("## 머티리얼 공유 현황 (Hard Rule 3 — 공유 머티리얼 직접 수정 금지)")
L.append("")
L.append("| 머티리얼 | 사용 prim 수 | 사용처 |")
L.append("|---|---|---|")
for m, users in sorted(mat_users.items(), key=lambda kv: -len(kv[1])):
    L.append(f"| `{m}` | {len(users)} | " + ", ".join(f"`{u}`" for u in users) + " |")
L.append("")

with open(args.out, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

print("DUMP_OK", args.out, stage_info["prim_count"])
simulation_app.close()
