# -*- coding: utf-8 -*-
"""diag_dt.py — 실제 물리 스텝 간격 진단"""
import sys, os, json, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb): open(os.path.join(OUT, "diagdt_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
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
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); open_stage(USD)
dt = 1 / 2560
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage(); BASE = "/World/HoistMotor/HoistMotor"
rep = {}
pc = world.get_physics_context()
rep["physics_dt_reported"] = pc.get_physics_dt()
sc = PhysxSchema.PhysxSceneAPI(stage.GetPrimAtPath("/physicsScene")); rep["scene_timeStepsPerSecond"] = sc.GetTimeStepsPerSecondAttr().Get()
world.reset()
art = SingleArticulation(prim_path=BASE, name="m"); art.initialize(); av = art._articulation_view; ctrl = art.get_articulation_controller()
def measure(tag, steps=100):
    ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0])); av.set_joint_velocities(np.array([[0.0]]))
    t0 = world.current_time; vs = []
    for i in range(steps):
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([100.0]))); world.step(render=False); vs.append(float(art.get_joint_velocities()[0]))
    t1 = world.current_time; elapsed = t1 - t0
    dv = vs[-1] - vs[49]; alpha_by_step = dv / (50 * dt); alpha_by_time = dv / (elapsed * 50 / steps) if elapsed else None
    rep[tag] = {"current_time_elapsed_s": elapsed, "dt_per_step_from_clock": elapsed / steps, "J_if_dt_1_2560": 100 / alpha_by_step, "J_if_dt_clock": (100 / alpha_by_time) if alpha_by_time else None, "physics_dt_reported": pc.get_physics_dt()}
measure("A_default")
pc.set_physics_dt(dt=dt, substeps=1); rep["after_set_physics_dt"] = pc.get_physics_dt(); rep["scene_tsps_after"] = sc.GetTimeStepsPerSecondAttr().Get()
measure("B_after_set_physics_dt")
# 설정 키 확인
s = carb.settings.get_settings()
rep["settings"] = {k: s.get(k) for k in ("/app/runLoops/main/rateLimitFrequency", "/persistent/simulation/minFrameRate", "/physics/timeStepsPerSecond", "/app/player/useFixedTimeStepping", "/physics/updateRate")}
json.dump(rep, open(os.path.join(OUT, "diag_dt.json"), "w", encoding="utf-8"), indent=2)
simulation_app.close()
