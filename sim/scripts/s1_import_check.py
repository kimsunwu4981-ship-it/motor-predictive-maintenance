# -*- coding: utf-8 -*-
"""s1_import_check.py — USD 임포트 검증 (스케일/축/계층/머티리얼). headless, CPU PhysX."""
import sys, os, json, time, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb):
    open(os.path.join(OUT, "s1_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb
carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from pxr import Usd, UsdGeom, Gf, UsdShade

USD = os.path.join(ROOT, "usd", "hoist_motor_v01.usd")
world = World(stage_units_in_meters=1.0)
prim = add_reference_to_stage(usd_path=USD, prim_path="/World/HoistMotor")
stage = get_current_stage()
world.reset()

def bbox(path):
    p = stage.GetPrimAtPath(path)
    bb = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy", "guide"]).ComputeWorldBound(p).ComputeAlignedRange()
    mn, mx = bb.GetMin(), bb.GetMax()
    return [round(v, 4) for v in mn], [round(v, 4) for v in mx]

def tree(path, depth=4):
    out = []
    def rec(p, d):
        if d > depth: return
        out.append(("  " * d) + p.GetName() + " <" + p.GetTypeName() + ">")
        for c in p.GetChildren(): rec(c, d + 1)
    rec(stage.GetPrimAtPath(path), 0)
    return out

ref_layer = Usd.Stage.Open(USD)
rep = {
    "usd": USD, "file_bytes": os.path.getsize(USD),
    "ref_upAxis": UsdGeom.GetStageUpAxis(ref_layer), "ref_metersPerUnit": UsdGeom.GetStageMetersPerUnit(ref_layer),
    "stage_upAxis": UsdGeom.GetStageUpAxis(stage), "stage_metersPerUnit": UsdGeom.GetStageMetersPerUnit(stage),
    "hierarchy": tree("/World/HoistMotor"),
}
# 계층 탐색: visual/collision 프림 경로
paths = {}
for p in stage.Traverse():
    n = p.GetName()
    if n in ("HM_Frame_Assy", "HM_Rotor_Assy", "visual_frame", "visual_rotor") or n.startswith("collision_"):
        paths[n] = str(p.GetPath())
rep["prim_paths"] = paths
rep["bbox_frame_assy"] = bbox(paths["HM_Frame_Assy"]) if "HM_Frame_Assy" in paths else None
rep["bbox_rotor_assy"] = bbox(paths["HM_Rotor_Assy"]) if "HM_Rotor_Assy" in paths else None
rep["bbox_visual_frame"] = bbox(paths["visual_frame"]) if "visual_frame" in paths else None
rep["bbox_visual_rotor"] = bbox(paths["visual_rotor"]) if "visual_rotor" in paths else None
# 머티리얼 바인딩
mats = {}
for k in ("visual_frame", "visual_rotor"):
    if k in paths:
        for p in Usd.PrimRange(stage.GetPrimAtPath(paths[k])):
            if p.IsA(UsdGeom.Mesh):
                m, _ = UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()
                mats.setdefault(k, []).append(str(m.GetPath()) if m else None)
rep["materials"] = mats
# 메시 통계
stats = {}
for p in stage.Traverse():
    if p.IsA(UsdGeom.Mesh):
        m = UsdGeom.Mesh(p); stats[str(p.GetPath())] = {"points": len(m.GetPointsAttr().Get() or []), "faces": len(m.GetFaceVertexCountsAttr().Get() or [])}
rep["mesh_stats"] = stats
# 스크린샷(머티리얼 확인) — headless 렌더 캡처
try:
    from isaacsim.core.utils.viewports import set_camera_view
    import omni.kit.viewport.utility as vu
    from omni.kit.viewport.utility import capture_viewport_to_file
    set_camera_view(eye=[-0.6, -1.3, 0.8], target=[0.45, 0.0, 0.0])
    for _ in range(30): world.render()
    vp = vu.get_active_viewport()
    shot = os.path.join(OUT, "s1_viewport.png")
    capture_viewport_to_file(vp, shot)
    for _ in range(30): world.render()
    rep["screenshot"] = shot
except Exception as e:
    rep["screenshot_error"] = repr(e)
with open(os.path.join(OUT, "s1_report.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, ensure_ascii=False, indent=2)
simulation_app.close()
