# -*- coding: utf-8 -*-
"""s0_env_check.py — Isaac Sim 환경 점검 (headless, CPU PhysX). isaacsim.* 네임스페이스만 사용."""
import sys, time, json, platform
t0 = time.time()
import traceback, os
def _hook(t, v, tb):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "s0_error.txt"), "w", encoding="utf-8") as f: f.write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb, omni.kit.app
from isaacsim.core.api import World
from isaacsim.core.utils.stage import get_current_stage
from pxr import UsdPhysics, PhysxSchema, UsdGeom
import isaacsim.core.prims, isaacsim.core.utils.types  # 네임스페이스 존재 확인
ver = omni.kit.app.get_app().get_app_version()
settings = carb.settings.get_settings()
settings.set("/physics/cudaDevice", -1)
world = World(stage_units_in_meters=1.0, physics_dt=1.0/480.0, rendering_dt=1.0/60.0)
stage = get_current_stage()
scene_path = "/physicsScene"
scene = None
for p in stage.Traverse():
    if p.IsA(UsdPhysics.Scene): scene = p; scene_path = str(p.GetPath()); break
if scene is None:
    scene = UsdPhysics.Scene.Define(stage, scene_path).GetPrim()
physx = PhysxSchema.PhysxSceneAPI.Apply(scene)
physx.CreateEnableGPUDynamicsAttr(False); physx.CreateBroadphaseTypeAttr("MBP"); physx.CreateSolverTypeAttr("TGS")
world.reset()
for _ in range(10): world.step(render=False)
report = {
    "isaac_sim_version": ver, "python": sys.version.split()[0], "platform": platform.platform(),
    "physics_scene": scene_path, "gpu_dynamics": physx.GetEnableGPUDynamicsAttr().Get(),
    "cuda_device_setting": settings.get("/physics/cudaDevice"), "broadphase": physx.GetBroadphaseTypeAttr().Get(),
    "solver": physx.GetSolverTypeAttr().Get(), "physics_dt": world.get_physics_dt(), "steps_ok": 10,
    "up_axis": UsdGeom.GetStageUpAxis(stage), "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
    "elapsed_s": round(time.time()-t0, 1),
}
import os, io
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "s0_report.json")
with io.open(out, "w", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
print("S0_REPORT " + json.dumps(report), flush=True)
simulation_app.close()
