# -*- coding: utf-8 -*-
"""s4_run_baseline.py — 정상 구동 baseline (기동 → 정속 유지 → 정지). headless, CPU PhysX.
사용: python.bat s4_run_baseline.py [--load noload|rated] [--seed N] [--tag TAG] [--fault MODE --severity S]
출력: sim/output/baseline_{load}_{YYYYmmdd_HHMMSS}.npz + .json (메타데이터)
결함 주입(S5/S6)은 --fault 옵션으로 동일 스크립트가 처리한다 (FaultInjector).
"""
import sys, os, json, time, traceback, math, argparse, hashlib, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "output"); sys.path.insert(0, os.path.dirname(__file__))
def _hook(t, v, tb):
    open(os.path.join(OUT, "s4_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
ap = argparse.ArgumentParser()
ap.add_argument("--load", default="noload", choices=["noload", "rated"])
ap.add_argument("--seed", type=int, default=None)
ap.add_argument("--tag", default="")
ap.add_argument("--fault", default="none")
ap.add_argument("--severity", default="none")
ap.add_argument("--outdir", default=OUT)
ap.add_argument("--total_s", type=float, default=None)
args = ap.parse_args()
import yaml, numpy as np
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
def V(d): return d["value"] if isinstance(d, dict) else d
seed = args.seed if args.seed is not None else int(CFG["meta"]["seed"]); np.random.seed(seed)
cfg_hash = hashlib.sha256(open(os.path.join(ROOT, "config", "motor.yaml"), "rb").read()).hexdigest()[:12]

from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb
carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import UsdPhysics, PhysxSchema, Gf, Sdf
from omni.physx import get_physx_simulation_interface
from s5_fault_injector import FaultInjector

phys_dt = float(V(CFG["physics"]["physics_dt"])); HZ = int(round(1 / phys_dt))
from isaacsim.core.utils.stage import open_stage
USD = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd")
open_stage(USD)                                              # 물리 USD(씬·조인트 포함)를 스테이지로 직접 오픈
world = World(stage_units_in_meters=1.0, physics_dt=phys_dt, rendering_dt=1 / 60, physics_prim_path="/physicsScene")
stage = get_current_stage()
BASE = "/World/HoistMotor/HoistMotor"; JOINT = BASE + "/JT_Frame_Rotor_Rev"; ROTOR = BASE + "/HM_Rotor_Assy"
assert stage.GetPrimAtPath(BASE).IsValid(), "BASE prim missing: " + BASE
world.reset()
art = SingleArticulation(prim_path=BASE, name="hoist_motor"); art.initialize()
dof = art.dof_names; print("dof:", dof)
drv = UsdPhysics.DriveAPI(stage.GetPrimAtPath(JOINT), "angular")
T_rated = float(V(CFG["motor"]["rated_torque_Nm"])); rpm_t = float(CFG["drive"]["target_rpm"]); w_t = rpm_t * 2 * math.pi / 60
load_T = float(CFG["baseline"]["load_torque_Nm"][args.load])
hold_s = float(CFG["baseline"]["ramp_hold_s"]); stop_s = float(CFG["baseline"]["stop_at_s"]); total_s = args.total_s or float(CFG["baseline"]["total_s"])
N = int(round(total_s * HZ))
fi = FaultInjector(mode=args.fault, severity=args.severity, cfg=CFG, seed=seed)
# 드라이브 게인/토크 상한을 Isaac Core API 로 명시 설정 (USD 값이 초기화 시 덮이는 것 방지). 단위: rad 기준
dmp_cfg = float(V(CFG["drive"]["damping_Nms_per_rad"])); mf_cfg = float(V(CFG["drive"]["max_force_Nm"]))
ctrl = art.get_articulation_controller()
ctrl.set_gains(kps=np.array([0.0]), kds=np.array([dmp_cfg]))
art._articulation_view.set_max_efforts(np.array([[mf_cfg]]))
kp_chk, kd_chk = ctrl.get_gains(); me_chk = float(art._articulation_view.get_max_efforts()[0][0])
print("gains:", kp_chk, kd_chk, "max_effort:", me_chk)
# 링크 질량/관성: USD MassAPI 가 아티큘레이션에 반영되지 않는 경우 대비 → API 로 명시 설정 후 검증
CADP = json.load(open(os.path.join(ROOT, "config", "cad_mass_properties.json"), encoding="utf-8"))
rot = CADP["_groups"]["rotor_assy"]; m_rotor = rot["mass_kg"]; Ixx_cfg = rot["Ixx_kgm2"]
Iyy_cfg = sum(CADP[n]["I_origin_kgm2"][1] for n in rot["parts"]) - m_rotor * rot["com_x_m"] ** 2
av = art._articulation_view
body_names = list(av.body_names); print("bodies:", body_names)
m0 = av.get_body_masses().copy(); I0 = av.get_body_inertias().copy()
print("mass before:", m0.tolist()); print("inertia before:", np.round(I0, 4).tolist())
ri = body_names.index("HM_Rotor_Assy")
masses = m0.copy(); masses[0, ri] = m_rotor
inert = I0.copy(); inert[0, ri, :] = [Ixx_cfg, 0, 0, 0, Iyy_cfg, 0, 0, 0, Iyy_cfg]
av.set_body_masses(masses); av.set_body_inertias(inert)
m1 = av.get_body_masses(); I1 = av.get_body_inertias()
print("mass after:", m1.tolist()); print("inertia after:", np.round(I1, 4).tolist())
body_props = {"body_names": body_names, "mass_before": m0.tolist(), "inertia_before": I0.tolist(), "mass_after": m1.tolist(), "inertia_after": I1.tolist()}
# 각속도 목표: 시작 시 곧바로 정격 지령(직입 기동 근사)
target = w_t
ctrl.apply_action(ArticulationAction(joint_velocities=np.array([target])))
t = np.zeros(N); pos = np.zeros(N); vel = np.zeros(N); acc = np.zeros(N); tq_drive = np.zeros(N); tq_load = np.zeros(N); tq_fault = np.zeros(N); tq_meas = np.zeros(N)
prev_v = 0.0
physx_sim = get_physx_simulation_interface()
art._articulation_view.set_joint_velocities(np.array([[0.0]])); art._articulation_view.set_joint_positions(np.array([[0.0]]))
for i in range(N):
    tt = i * phys_dt
    if tt >= stop_s and target != 0.0:
        target = 0.0; ctrl.apply_action(ArticulationAction(joint_velocities=np.array([0.0])))
    v = float(art.get_joint_velocities()[0]); p = float(art.get_joint_positions()[0])
    # 부하 토크(정격 부하 시 회전 반대 방향 일정 토크, 저속에서 선형 감소) + 결함 리플 토크
    T_l = -load_T * (1.0 if v > 1.0 else (v / 1.0)) if load_T else 0.0
    T_f = fi.torque(tt, v, p)
    ctrl.apply_action(ArticulationAction(joint_velocities=np.array([target]), joint_efforts=np.array([T_l + T_f])))
    # 드라이브 토크 추정(설정식) + 실측 조인트 토크(PhysX 반력)
    T_d = max(-mf_cfg, min(mf_cfg, dmp_cfg * (target - v)))
    try: T_m = float(art.get_measured_joint_efforts()[0])
    except Exception: T_m = float("nan")
    # World.step(render=False) 는 physics_dt 를 1/60 로 스텝함(진단 diag_dt.json) → PhysX 를 직접 dt 로 스텝
    physx_sim.simulate(phys_dt, tt); physx_sim.fetch_results()
    t[i] = tt; pos[i] = p; vel[i] = v; acc[i] = (v - prev_v) / phys_dt; tq_drive[i] = T_d; tq_load[i] = T_l; tq_fault[i] = T_f; tq_meas[i] = T_m; prev_v = v
# ---- 검증 ----
rpm = vel * 60 / (2 * math.pi)
m_hold = (t >= stop_s - hold_s) & (t < stop_s)
rpm_exp = float(CFG["drive"]["expected_rpm"][args.load])          # 부하별 기대 정속 (정격부하 = 1170 rpm)
rpm_mean = float(rpm[m_hold].mean()); rpm_err = (rpm_mean - rpm_exp) / rpm_exp * 100
# 기동 시간(기대 정속의 90% 도달)
idx = np.argmax(rpm >= 0.9 * rpm_exp); t90 = float(t[idx]) if rpm[idx] >= 0.9 * rpm_exp else None
J = 0.468093; dmp0 = float(kd_chk[0]); mf0 = me_chk
# 이론 기동시간: 토크 제한 구간(mf0) + 지수 구간(τ=J/damping) 근사
t_theory = J * w_t * 0.9 / (mf0 - load_T) if mf0 > load_T else None
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
name = (f"baseline_{args.load}" if args.fault == "none" else f"fault_{args.fault}_{args.severity}_{args.load}") + (f"_{args.tag}" if args.tag else "") + f"_{stamp}"
os.makedirs(args.outdir, exist_ok=True)
np.savez_compressed(os.path.join(args.outdir, name + ".npz"), t=t, pos_rad=pos, vel_rads=vel, acc_rads2=acc, torque_drive_Nm=tq_drive, torque_load_Nm=tq_load, torque_fault_Nm=tq_fault, torque_measured_Nm=tq_meas)
meta = {
    "name": name, "generation": "analytic_injection" if args.fault != "none" else "baseline_rigid_body",
    "isaac_sim": "4.5.0", "physics_hz": HZ, "physics_dt": phys_dt, "seed": seed, "config_sha256_12": cfg_hash,
    "load": args.load, "load_torque_Nm": load_T, "fault": args.fault, "severity": args.severity, "fault_params": fi.describe(),
    "drive": {"damping": dmp0, "max_force": mf0, "target_rpm": rpm_t, "stop_at_s": stop_s},
    "rotor_Ixx_kgm2": J, "dof_names": list(dof), "n_samples": N, "duration_s": total_s,
    "verify": {"rpm_expected": rpm_exp, "rpm_mean_hold": rpm_mean, "rpm_err_pct": rpm_err, "rpm_within_1pct": abs(rpm_err) <= 1.0, "t90_s": t90, "t90_theory_s": t_theory,
               "rpm_std_hold": float(rpm[m_hold].std()), "rpm_max": float(rpm.max())},
    "columns": ["t", "pos_rad", "vel_rads", "acc_rads2", "torque_drive_Nm", "torque_load_Nm", "torque_fault_Nm", "torque_measured_Nm"],
    "drive_check": {"kp": float(kp_chk[0]), "kd": float(kd_chk[0]), "max_effort": me_chk},
    "body_props": body_props,
}
json.dump(meta, open(os.path.join(args.outdir, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(os.path.join(OUT, "s4_last.txt"), "w", encoding="utf-8").write(name)
simulation_app.close()
