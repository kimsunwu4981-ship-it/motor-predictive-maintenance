# -*- coding: utf-8 -*-
"""s9_gui_demo.py — 시각 확인용 GUI 실행 (v2 토크 제어 루프). 물리 USD 로드 → 토크 제어 구동 → 창이 닫힐 때까지 실시간 스텝.
사용: C:\ISSACS~1\python.bat s9_gui_demo.py [--load rated|half] [--fault MODE --severity S] [--slow N]
--slow N : 눈으로 회전 확인용 — 동기속도를 1/N 로 낮춘 가상 저속 운전(물리 파라미터는 비례 축소, 데이터 생성용 아님)
상태: sim/output/s9_status.txt (t, rpm, slip, T_motor) 를 1초마다 갱신
"""
import sys, os, math, argparse, json, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output"); sys.path.insert(0, os.path.dirname(__file__))
def _hook(t, v, tb): open(os.path.join(OUT, "s9_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
ap = argparse.ArgumentParser(); ap.add_argument("--load", default="rated"); ap.add_argument("--fault", default="none"); ap.add_argument("--severity", default="none"); ap.add_argument("--slow", type=float, default=1.0)
args = ap.parse_args()
import yaml, numpy as np
from motor_torque_model import InductionMotorTorque, ConstantLoad
from fault_injector import FaultInjector
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8")); V = lambda d: d["value"] if isinstance(d, dict) else d
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": False, "width": 1600, "height": 900})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from isaacsim.core.utils.viewports import set_camera_view
from omni.physx import get_physx_simulation_interface
from pxr import UsdLux, UsdGeom, Gf
dt = 1.0 / int(CFG["e_run"]["physics_hz"])
open_stage(os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"))
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage(); BASE = "/World/HoistMotor/HoistMotor"
dl = UsdLux.DomeLight.Define(stage, "/World/DomeLight"); dl.CreateIntensityAttr(1000.0)
sun = UsdLux.DistantLight.Define(stage, "/World/Sun"); sun.CreateIntensityAttr(3000.0); UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-45, 30, 0))
gp = UsdGeom.Cube.Define(stage, "/World/GroundVisual"); gp.CreateSizeAttr(1.0); xf = UsdGeom.Xformable(gp); xf.AddTranslateOp().Set(Gf.Vec3d(0.45, 0, -0.235)); xf.AddScaleOp().Set(Gf.Vec3f(2.0, 1.4, 0.03)); gp.CreateDisplayColorAttr([Gf.Vec3f(0.9, 0.65, 0.1)])
set_camera_view(eye=[-0.7, -1.4, 0.9], target=[0.45, 0.0, 0.0])
world.reset()
art = SingleArticulation(prim_path=BASE, name="hoist_motor"); art.initialize(); ctrl = art.get_articulation_controller(); av = art._articulation_view
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0])); av.set_max_efforts(np.array([[1.0e4]])); av.set_joint_velocities(np.array([[0.0]])); av.set_joint_positions(np.array([[0.0]]))
motor = InductionMotorTorque(CFG); load = ConstantLoad(motor.T_rated, float(CFG["torque_control"]["load_fractions"][args.load]))
if args.slow != 1.0:   # 가상 저속: 동기속도·정격속도를 1/N (토크–슬립 기울기 유지)
    motor.w_sync /= args.slow; motor.n_sync /= args.slow; motor.n_rated /= args.slow
fi = FaultInjector(args.fault, args.severity, CFG, seed=1)
sim = get_physx_simulation_interface(); t = 0.0; theta = 0.0; frame = 0
sub = int(round((1 / 60) / dt))
while simulation_app.is_running():
    for _ in range(sub):
        w = float(art.get_joint_velocities()[0]); theta += w * dt; s = motor.slip(w); fr = w / (2 * math.pi)
        T_m, _ = motor.torque(w); T = T_m + fi.torque_v2(t, s, fr, theta) + load.torque(w) + motor.friction(w)
        ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T]))); sim.simulate(dt, t); sim.fetch_results(); t += dt
    world.render(); frame += 1
    if frame % 60 == 0:
        w = float(art.get_joint_velocities()[0])
        open(os.path.join(OUT, "s9_status.txt"), "w", encoding="utf-8").write(json.dumps({"t": round(t, 1), "rpm": round(w * 60 / (2 * math.pi), 1), "slip": round(motor.slip(w), 5), "T_motor": round(motor.torque(w)[0], 1), "load": args.load, "fault": args.fault, "mode": "torque_control_v2"}))
simulation_app.close()
