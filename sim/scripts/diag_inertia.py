# -*- coding: utf-8 -*-
"""diag_inertia.py — 회전부 유효 관성 진단: 드라이브 off, 일정 토크 인가 → J_eff = T/α"""
import sys, os, json, traceback, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb): open(os.path.join(OUT, "diag_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
import numpy as np
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import UsdPhysics, PhysxSchema
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); open_stage(USD)
dt = 1 / 2560
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage(); BASE = "/World/HoistMotor/HoistMotor"
rep = {}
world.reset()
art = SingleArticulation(prim_path=BASE, name="m"); art.initialize()
ctrl = art.get_articulation_controller(); ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0]))
av = art._articulation_view
rep["masses"] = av.get_body_masses().tolist(); rep["inertias"] = av.get_body_inertias().tolist()
rep["dof_props"] = {}
try:
    rep["dof_props"]["max_efforts"] = av.get_max_efforts().tolist(); rep["dof_props"]["gains"] = [g.tolist() for g in av.get_gains()]
    rep["dof_props"]["armatures"] = av.get_armatures().tolist()
except Exception as e: rep["dof_props"]["err"] = repr(e)
def run_case(tag, T, steps=256):
    ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0]))
    av.set_joint_velocities(np.array([[0.0]])); av.set_joint_positions(np.array([[0.0]]))
    for _ in range(3): world.step(render=False)
    av.set_joint_velocities(np.array([[0.0]]))
    vs = []
    for i in range(steps):
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T])))
        world.step(render=False); vs.append(float(art.get_joint_velocities()[0]))
    vs = np.array(vs); alpha = (vs[-1] - vs[len(vs)//2]) / (dt * (len(vs) - len(vs)//2))
    rep[tag] = {"T": T, "v_end": float(vs[-1]), "alpha": float(alpha), "J_eff": float(T / alpha) if alpha else None, "v_first5": vs[:5].tolist()}
run_case("effort_100", 100.0)
run_case("effort_10", 10.0)
J_target = 0.468093; J_eff = rep["effort_100"]["J_eff"]; arm = J_target - J_eff
av.set_armatures(np.array([[arm]])); rep["armature_set"] = float(av.get_armatures()[0][0])
run_case("effort_100_armature", 100.0)
# world.reset 후에도 armature 유지되는지 확인
rep["armature_after_reset"] = float(av.get_armatures()[0][0])
# 반대로 관성 스케일링 시험: 관성을 42.33배로 설정하면 J_eff 가 0.468 이 되는가
I = av.get_body_inertias().copy(); I[0, 1, 0] = J_target * (J_target / J_eff); av.set_armatures(np.array([[0.0]])); av.set_body_inertias(I)
run_case("effort_100_scaled_inertia", 100.0); rep["scaled_inertia_Ixx"] = float(I[0, 1, 0])
# 드라이브 velocity 모드 재현: kd=7.33, max_effort=449 → 첫 5스텝 속도
world.reset(); art.initialize(); ctrl.set_gains(kps=np.array([0.0]), kds=np.array([7.33])); av.set_max_efforts(np.array([[449.0]]))
vs = []
for i in range(20):
    ctrl.apply_action(ArticulationAction(joint_velocities=np.array([122.52]))); world.step(render=False); vs.append(float(art.get_joint_velocities()[0]))
rep["drive_first20"] = vs
json.dump(rep, open(os.path.join(OUT, "diag_inertia.json"), "w", encoding="utf-8"), indent=2)
simulation_app.close()
