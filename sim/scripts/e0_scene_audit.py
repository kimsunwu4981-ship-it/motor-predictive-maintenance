# -*- coding: utf-8 -*-
"""e0_scene_audit.py — 현재 물리 USD Stage 감사 (headless, CPU PhysX). 결과: sim/output/e0_scene_audit.json"""
import sys, os, json, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb): open(os.path.join(OUT, "e0_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); open_stage(USD)
world = World(stage_units_in_meters=1.0, physics_dt=1 / 2560, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage()
rep = {"usd": USD, "metersPerUnit": UsdGeom.GetStageMetersPerUnit(stage), "kilogramsPerUnit": UsdPhysics.GetStageKilogramsPerUnit(stage), "upAxis": UsdGeom.GetStageUpAxis(stage), "rigid_bodies": [], "colliders": [], "joints": [], "scene": {}}
def attrs(p, prefixes):
    return {a.GetName(): (str(a.Get())) for a in p.GetAttributes() if any(a.GetName().startswith(x) for x in prefixes)}
bbc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy", "guide"])
for p in stage.Traverse():
    if p.HasAPI(UsdPhysics.RigidBodyAPI):
        bb = bbc.ComputeWorldBound(p).ComputeAlignedRange()
        rep["rigid_bodies"].append({"path": str(p.GetPath()), "mass_api": attrs(p, ["physics:mass", "physics:centerOfMass", "physics:diagonalInertia", "physics:principalAxes", "physics:kinematicEnabled"]),
                                    "physx": attrs(p, ["physxRigidBody:maxAngularVelocity", "physxRigidBody:angularDamping", "physxRigidBody:sleepThreshold"]),
                                    "bbox_min": [round(v, 4) for v in bb.GetMin()], "bbox_max": [round(v, 4) for v in bb.GetMax()]})
    if p.HasAPI(UsdPhysics.CollisionAPI):
        mesh_pts = len(UsdGeom.Mesh(p).GetPointsAttr().Get() or []) if p.IsA(UsdGeom.Mesh) else 0
        rep["colliders"].append({"path": str(p.GetPath()), "type": p.GetTypeName(), "purpose": str(UsdGeom.Imageable(p).GetPurposeAttr().Get()), "mesh_points": mesh_pts,
                                 "approx": str(p.GetAttribute("physics:approximation").Get()) if p.HasAttribute("physics:approximation") else None})
    if p.IsA(UsdPhysics.Joint):
        j = {"path": str(p.GetPath()), "type": p.GetTypeName(), "body0": [str(t) for t in UsdPhysics.Joint(p).GetBody0Rel().GetTargets()], "body1": [str(t) for t in UsdPhysics.Joint(p).GetBody1Rel().GetTargets()],
             "axis": str(p.GetAttribute("physics:axis").Get()) if p.HasAttribute("physics:axis") else None, "localPos0": str(p.GetAttribute("physics:localPos0").Get()), "localPos1": str(p.GetAttribute("physics:localPos1").Get()),
             "drive": attrs(p, ["drive:angular:physics:"]), "physx": attrs(p, ["physxJoint:"])}
        rep["joints"].append(j)
    if p.IsA(UsdPhysics.Scene):
        rep["scene"] = {"path": str(p.GetPath()), **attrs(p, ["physxScene:enableGPUDynamics", "physxScene:timeStepsPerSecond", "physxScene:solverType", "physxScene:broadphaseType", "physics:gravity"])}
    if p.HasAPI(UsdPhysics.ArticulationRootAPI): rep["articulation_root"] = str(p.GetPath())
# 시각 메시 규모
rep["visual_meshes"] = [{"path": str(p.GetPath()), "points": len(UsdGeom.Mesh(p).GetPointsAttr().Get() or []), "has_collision": p.HasAPI(UsdPhysics.CollisionAPI)} for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
json.dump(rep, open(os.path.join(OUT, "e0_scene_audit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
simulation_app.close()
