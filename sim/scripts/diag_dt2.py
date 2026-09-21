# -*- coding: utf-8 -*-
"""diag_dt2.py — PhysX 직접 스텝(simulate/fetch_results)으로 dt=1/2560 적용 검증"""
import sys, os, json, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb): open(os.path.join(OUT, "diagdt2_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
import numpy as np
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import PhysxSchema, UsdPhysics
from omni.physx import get_physx_simulation_interface
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); open_stage(USD)
dt = 1 / 2560
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage(); BASE = "/World/HoistMotor/HoistMotor"; rep = {}
rep["scene_prims"] = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
pc = world.get_physics_context(); rep["pc_prim_path"] = pc.prim_path; rep["pc_dt"] = pc.get_physics_dt()
world.reset()
art = SingleArticulation(prim_path=BASE, name="m"); art.initialize(); av = art._articulation_view; ctrl = art.get_articulation_controller()
sim = get_physx_simulation_interface()
def measure(tag, stepper, steps=200):
    ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0])); av.set_joint_velocities(np.array([[0.0]]))
    vs = []; tcur = 0.0
    for i in range(steps):
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([100.0])))
        tcur = stepper(tcur); vs.append(float(art.get_joint_velocities()[0]))
    dv = vs[-1] - vs[99]; alpha = dv / (100 * dt); rep[tag] = {"J_if_dt_1_2560": 100 / alpha, "v_end": vs[-1]}
def step_physx(tcur):
    sim.simulate(dt, tcur); sim.fetch_results(); return tcur + dt
measure("physx_direct", step_physx)
# 드라이브 velocity 모드 + 직접 스텝: 기동 90% 시간
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([7.33])); av.set_max_efforts(np.array([[449.0]])); av.set_joint_velocities(np.array([[0.0]]))
tcur = 0.0; t90 = None
for i in range(2560):
    ctrl.apply_action(ArticulationAction(joint_velocities=np.array([122.52]))); tcur = step_physx(tcur)
    v = float(art.get_joint_velocities()[0])
    if t90 is None and v >= 0.9 * 122.52: t90 = tcur
rep["drive_t90_s"] = t90; rep["drive_v_end"] = v; rep["t90_theory"] = 0.468093 * 122.52 * 0.9 / 449.0
json.dump(rep, open(os.path.join(OUT, "diag_dt2.json"), "w", encoding="utf-8"), indent=2)
simulation_app.close()
