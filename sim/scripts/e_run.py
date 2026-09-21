# -*- coding: utf-8 -*-
"""e_run.py — v2.0 토크 제어 루프 러너 (E2 검증 / E4 baseline / E6 결함 런 공용). headless, CPU PhysX, PhysX 직접 스텝.
매 step: ω → s → T_motor(s) + T_ripple(결함) + T_friction − T_load → apply effort; 전류 I_abc(t) 병렬 생성(동일 s, fr)
사용: python.bat e_run.py --load rated|half [--fault MODE --severity S] [--seed N] [--outdir DIR] [--tag T]
"""
import sys, os, json, time, traceback, math, argparse, hashlib, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output"); sys.path.insert(0, os.path.dirname(__file__))
def _hook(t, v, tb): open(os.path.join(OUT, "e_run_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
ap = argparse.ArgumentParser()
ap.add_argument("--load", default="rated", choices=["half", "rated"]); ap.add_argument("--fault", default="none"); ap.add_argument("--severity", default="none")
ap.add_argument("--seed", type=int, default=None); ap.add_argument("--outdir", default=OUT); ap.add_argument("--tag", default=""); ap.add_argument("--hold_s", type=float, default=None)
args = ap.parse_args()
import yaml, numpy as np
from motor_torque_model import InductionMotorTorque, ConstantLoad
from current_generator import CurrentGenerator
from fault_injector import FaultInjector
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8")); V = lambda d: d["value"] if isinstance(d, dict) else d
seed = args.seed if args.seed is not None else int(CFG["meta"]["seed"]); np.random.seed(seed)
cfg_hash = hashlib.sha256(open(os.path.join(ROOT, "config", "motor.yaml"), "rb").read()).hexdigest()[:12]
HZ = int(CFG["e_run"]["physics_hz"]); dt = 1.0 / HZ
settle = float(CFG["e_run"]["settle_s"]); hold = args.hold_s or float(CFG["e_run"]["hold_s"]); tail = float(CFG["e_run"]["stop_tail_s"])
stop_s = settle + hold; total_s = stop_s + tail; N = int(round(total_s * HZ))

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import open_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from omni.physx import get_physx_simulation_interface
open_stage(os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"))
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
BASE = "/World/HoistMotor/HoistMotor"; world.reset()
art = SingleArticulation(prim_path=BASE, name="hoist_motor"); art.initialize(); av = art._articulation_view; ctrl = art.get_articulation_controller()
# 드라이브 비활성: stiffness=damping=0 (속도 지령 무효), 토크 상한은 루프에서 클립하므로 PhysX max effort 는 여유 있게
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([float(CFG["torque_control"]["drive_damping"])])); av.set_max_efforts(np.array([[1.0e4]]))
av.set_joint_velocities(np.array([[0.0]])); av.set_joint_positions(np.array([[0.0]]))
kp_chk, kd_chk = ctrl.get_gains(); inert = av.get_body_inertias()[0, 1, 0]
motor = InductionMotorTorque(CFG); load = ConstantLoad(motor.T_rated, float(CFG["torque_control"]["load_fractions"][args.load]))
fi = FaultInjector(args.fault, args.severity, CFG, seed=seed)
b = CFG["bearings"]["DE"]; cg = CurrentGenerator(args.fault, args.severity, CFG, seed=seed + 1, bearing=(int(b["Z"]), float(b["Bd_mm"]), float(b["Pd_mm"]), float(b["contact_deg"])))
sim = get_physx_simulation_interface()
cols = {k: np.zeros(N) for k in ("t", "omega", "alpha", "slip", "theta", "T_motor", "T_fault", "T_load", "T_fric", "T_applied", "T_measured", "Ia", "Ib", "Ic")}
prev = 0.0; running = True; theta = 0.0
for i in range(N):
    t = i * dt
    omega = float(art.get_joint_velocities()[0])
    # θ 는 PhysX 조인트 위치 대신 ω 의 float64 적분을 사용 — PhysX 위치는 누적각 >600 rad 에서 float32 오차로 ω 와 0.8% 불일치 (diag_theta2.json)
    theta += omega * dt
    s = motor.slip(omega); fr = omega / (2 * math.pi)
    if t >= stop_s: running = False
    T_m, _ = motor.torque(omega) if running else (0.0, s)
    T_f = fi.torque_v2(t, s, fr, theta) if running else 0.0
    T_l = load.torque(omega); T_fr = motor.friction(omega)
    T_app = T_m + T_f + T_l + T_fr
    ctrl.apply_action(ArticulationAction(joint_efforts=np.array([T_app])))
    try: T_meas = float(art.get_measured_joint_efforts()[0])
    except Exception: T_meas = float("nan")
    I = cg.sample(t, s, fr) if running else np.zeros(3)
    sim.simulate(dt, t); sim.fetch_results()
    c = cols; c["t"][i] = t; c["omega"][i] = omega; c["alpha"][i] = (omega - prev) / dt; c["slip"][i] = s; c["theta"][i] = theta; c["T_motor"][i] = T_m; c["T_fault"][i] = T_f
    c["T_load"][i] = T_l; c["T_fric"][i] = T_fr; c["T_applied"][i] = T_app; c["T_measured"][i] = T_meas; c["Ia"][i], c["Ib"][i], c["Ic"][i] = I; prev = omega
# ---- 검증 ----
rpm = cols["omega"] * 60 / (2 * math.pi); m = (cols["t"] >= settle) & (cols["t"] < stop_s)
op = motor.expected_operating_point(load.T)
rpm_mean = float(rpm[m].mean()); rpm_err = (rpm_mean - motor.n_rated) / motor.n_rated * 100
s_mean = float(cols["slip"][m].mean())
idx = np.argmax(rpm >= 0.9 * op["rpm"]); t90 = float(cols["t"][idx]) if rpm[idx] >= 0.9 * op["rpm"] else None
t90_theory = float(inert) * 0.9 * op["rpm"] * 2 * math.pi / 60 / (motor.T_max - load.T)
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
name = (f"baseline_{args.load}_{seed}" if args.fault == "none" else f"fault_{args.fault}_{args.severity}_{args.load}_{seed}") + (f"_{args.tag}" if args.tag else "")
os.makedirs(args.outdir, exist_ok=True)
np.savez_compressed(os.path.join(args.outdir, name + ".npz"), **cols)
meta = {
    "name": name, "created": stamp, "isaac_sim": "4.5.0", "physics_hz": HZ, "physics_dt": dt, "seed": seed, "config_sha256_12": cfg_hash,
    "generation": {"speed_torque_channel": "physx_torque_control", "current_channel": "analytic", "fault_signature": "analytic_injection", "caveat": "주입 시그니처의 재생산 — FEM/실측 유도 데이터 아님"},
    "load": args.load, "load_torque_Nm": load.T, "fault": args.fault, "severity": args.severity, "fault_params": fi.describe(), "current_params": cg.describe(),
    "torque_model": {"mode": CFG["torque_control"]["mode"], "T_rated": motor.T_rated, "s_rated": motor.s_rated, "T_max": motor.T_max, "b_mech": motor.b_mech, "n_sync": motor.n_sync},
    "drive_check": {"kp": float(kp_chk[0]), "kd": float(kd_chk[0]), "rotor_Ixx": float(inert)},
    "theta_source": "float64 integral of PhysX joint velocity (PhysX joint position rejected: float32 accumulation drift, see diag_theta2.json)",
    "timeline": {"settle_s": settle, "hold_s": hold, "stop_s": stop_s, "total_s": total_s, "n_samples": N, "df_Hz": 1.0 / hold},
    "verify": {"rpm_rated": motor.n_rated, "rpm_mean_hold": rpm_mean, "rpm_err_pct_vs_rated": rpm_err, "rpm_expected_model": op["rpm"], "rpm_err_pct_vs_model": (rpm_mean - op["rpm"]) / op["rpm"] * 100,
               "rpm_within_1pct": bool(abs(rpm_err) <= float(CFG["torque_control"]["expected_rpm_tol_pct"])), "slip_mean": s_mean, "slip_rated": motor.s_rated, "slip_expected_model": op["slip"],
               "t90_s": t90, "t90_theory_s": t90_theory, "rpm_std_hold": float(rpm[m].std()), "T_measured_max": float(np.nanmax(np.abs(cols["T_measured"])))},
    "columns": list(cols.keys()),
}
json.dump(meta, open(os.path.join(args.outdir, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(os.path.join(OUT, "e_run_last.txt"), "w", encoding="utf-8").write(os.path.join(args.outdir, name))
simulation_app.close()
