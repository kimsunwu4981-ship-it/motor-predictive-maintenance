# -*- coding: utf-8 -*-
"""diag_inertia2.py — 관성 축소 원인 추적: kilogramsPerUnit, 질량 스케일 의존성, PhysX 실제 적용값 질의"""
import sys, os, json, traceback, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb): open(os.path.join(OUT, "diag2_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
import numpy as np
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import UsdPhysics, PhysxSchema, UsdGeom, Usd
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); open_stage(USD)
dt = 1 / 2560
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage(); BASE = "/World/HoistMotor/HoistMotor"; ROTOR = BASE + "/HM_Rotor_Assy"
rep = {"kilogramsPerUnit": UsdPhysics.GetStageKilogramsPerUnit(stage), "metersPerUnit": UsdGeom.GetStageMetersPerUnit(stage)}
# 프림 xform 스케일 확인
for path in ("/World", "/World/HoistMotor", BASE, ROTOR, BASE + "/HM_Frame_Assy"):
    p = stage.GetPrimAtPath(path); xf = UsdGeom.Xformable(p)
    rep["xform_" + path.split("/")[-1]] = [str(op.GetOpName()) + "=" + str(op.Get()) for op in xf.GetOrderedXformOps()] if p.IsValid() else None
rp = stage.GetPrimAtPath(ROTOR)
rep["rotor_massapi"] = {a.GetName(): str(a.Get()) for a in rp.GetAttributes() if a.GetName().startswith("physics:") or a.GetName().startswith("physxRigidBody")}
world.reset()
art = SingleArticulation(prim_path=BASE, name="m"); art.initialize(); av = art._articulation_view; ctrl = art.get_articulation_controller()
# PhysX 실제 적용값 질의
try:
    from omni.physx import get_physx_property_query_interface
    from omni.physx.bindings._physx import PhysxPropertyQueryRigidBodyResponse, PhysxPropertyQueryResult
    import omni.usd
    res = {}
    def cb(r):
        res["result"] = str(r.result); res["mass"] = r.mass; res["inertia"] = list(r.inertia); res["com"] = list(r.center_of_mass)
    pid = omni.usd.get_context().get_stage_id()
    from pxr import PhysicsSchemaTools
    get_physx_property_query_interface().query_prim(stage_id=pid, prim_id=PhysicsSchemaTools.sdfPathToInt(ROTOR), rigid_body_fn=cb)
    for _ in range(3): world.step(render=False)
    rep["physx_query_rotor"] = res
except Exception as e:
    rep["physx_query_err"] = repr(e)
def measure(T=100.0, steps=200):
    ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0]))
    av.set_joint_velocities(np.array([[0.0]])); av.set_joint_positions(np.array([[0.0]]))
    for _ in range(3): world.step(render=False)
    av.set_joint_velocities(np.array([[0.0]])); vs = []
    for i in range(steps):
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T]))); world.step(render=False); vs.append(float(art.get_joint_velocities()[0]))
    vs = np.array(vs); alpha = (vs[-1] - vs[100]) / (dt * (steps - 100)); return float(T / alpha)
rep["J_eff_base"] = measure()
m = av.get_body_masses().copy(); m[0, 1] *= 10; av.set_body_masses(m); rep["J_eff_mass_x10"] = measure()
m[0, 1] /= 10; av.set_body_masses(m)
# 관성 텐서 전체(9성분) 재설정 후
I = av.get_body_inertias().copy(); rep["I_read"] = I[0, 1].tolist()
# 구동축을 잘못 잡았을 가능성: Iyy/Izz 를 크게 바꿔 영향 확인
I2 = I.copy(); I2[0, 1, 4] *= 100; I2[0, 1, 8] *= 100; av.set_body_inertias(I2); rep["J_eff_IyyIzz_x100"] = measure(); av.set_body_inertias(I)
I3 = I.copy(); I3[0, 1, 0] *= 10; av.set_body_inertias(I3); rep["J_eff_Ixx_x10"] = measure(); av.set_body_inertias(I)
json.dump(rep, open(os.path.join(OUT, "diag_inertia2.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
simulation_app.close()
