import sys, os, json, math, traceback
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output"); sys.path.insert(0, os.path.dirname(__file__))
def _hook(t, v, tb): open(os.path.join(OUT, "diagth_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
import numpy as np, yaml
from motor_torque_model import InductionMotorTorque, ConstantLoad
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from omni.physx import get_physx_simulation_interface
open_stage(os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd")); dt = 1/2560
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1/60, physics_prim_path="/physicsScene"); world.reset()
art = SingleArticulation(prim_path="/World/HoistMotor/HoistMotor", name="m"); art.initialize(); av = art._articulation_view; ctrl = art.get_articulation_controller()
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([0.0])); av.set_max_efforts(np.array([[1e4]])); av.set_joint_velocities(np.array([[0.0]])); av.set_joint_positions(np.array([[0.0]]))
motor = InductionMotorTorque(CFG); load = ConstantLoad(motor.T_rated, 0.5); sim = get_physx_simulation_interface()
N = int(5 * 2560); th = np.zeros(N); om = np.zeros(N); thr = np.zeros(N)
for i in range(N):
    w = float(art.get_joint_velocities()[0]); p = float(art.get_joint_positions()[0]); th[i] = p; om[i] = w
    rp = av.get_joint_positions()[0][0]; thr[i] = rp
    T, _ = motor.torque(w); ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T + load.torque(w) + motor.friction(w)])))
    sim.simulate(dt, i * dt); sim.fetch_results()
m = slice(int(2.5 * 2560), N)
thu = np.unwrap(th); slope = np.polyfit(np.arange(N)[m] * dt, thu[m], 1)[0]
rep = {"theta_range": [float(th.min()), float(th.max())], "dtheta_dt_unwrapped": slope, "omega_mean": float(om[m].mean()), "ratio": slope / float(om[m].mean()),
       "fr_theta": slope / (2 * math.pi), "fr_omega": float(om[m].mean()) / (2 * math.pi), "theta_view_equal": bool(np.allclose(th, thr)),
       "step_dtheta_first": float(np.diff(thu)[m][:5].mean()), "omega_dt": float(om[m].mean() * dt)}
json.dump(rep, open(os.path.join(OUT, "diag_theta2.json"), "w"), indent=2); app.close()
