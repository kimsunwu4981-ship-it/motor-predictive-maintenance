# -*- coding: utf-8 -*-
"""s2_setup_physics.py — 물리 속성 설정 + 아티큘레이션/조인트 드라이브 구성 (S2+S3).
결과: sim/usd/hoist_motor_physics_v01.usd (USD 저장), sim/output/s2_report.json
- 고정부 HM_Frame_Assy: RigidBody + 충돌 프록시(실린더/박스) + FixedJoint(월드)
- 회전부 HM_Rotor_Assy: RigidBody + 충돌 프록시 + 명시 질량/관성
- RevoluteJoint(축 X) + Angular Drive(velocity 모드)
"""
import sys, os, json, traceback, math
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "output")
def _hook(t, v, tb):
    open(os.path.join(OUT, "s2_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
import yaml
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8"))
CAD = json.load(open(os.path.join(ROOT, "config", "cad_mass_properties.json"), encoding="utf-8"))
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})
import carb
carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema, Gf, Sdf

def V(d): return d["value"] if isinstance(d, dict) else d
phys_dt = V(CFG["physics"]["physics_dt"])
world = World(stage_units_in_meters=1.0, physics_dt=phys_dt, rendering_dt=1/60)
stage = get_current_stage()
SRC = os.path.join(ROOT, "usd", "hoist_motor_v01.usd")
add_reference_to_stage(usd_path=SRC, prim_path="/World/HoistMotor")

# PhysicsScene: CPU, TGS, MBP
scene_prim = None
for p in stage.Traverse():
    if p.IsA(UsdPhysics.Scene): scene_prim = p; break
if scene_prim is None: scene_prim = UsdPhysics.Scene.Define(stage, "/physicsScene").GetPrim()
ps = PhysxSchema.PhysxSceneAPI.Apply(scene_prim)
ps.CreateEnableGPUDynamicsAttr(False); ps.CreateBroadphaseTypeAttr("MBP"); ps.CreateSolverTypeAttr("TGS")
ps.CreateTimeStepsPerSecondAttr(int(round(1.0 / phys_dt)))
ps.CreateEnableCCDAttr(False); ps.CreateEnableStabilizationAttr(False)
UsdPhysics.Scene(scene_prim).CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1)); UsdPhysics.Scene(scene_prim).CreateGravityMagnitudeAttr(9.81)

BASE = "/World/HoistMotor/HoistMotor"
FRAME = BASE + "/HM_Frame_Assy"; ROTOR = BASE + "/HM_Rotor_Assy"
# ---- 충돌 프록시 (시각 메시에는 충돌 미지정) ----
def make_collider(parent, name, kind, size, pos, axis="X"):
    path = parent + "/" + name
    if kind == "cyl":
        g = UsdGeom.Cylinder.Define(stage, path); g.CreateRadiusAttr(size[0]); g.CreateHeightAttr(size[1]); g.CreateAxisAttr(axis)
    else:
        g = UsdGeom.Cube.Define(stage, path); g.CreateSizeAttr(1.0)
        UsdGeom.Xformable(g).AddScaleOp().Set(Gf.Vec3f(*size))
    UsdGeom.Xformable(g).AddTranslateOp().Set(Gf.Vec3d(*pos)) if kind == "cyl" else UsdGeom.Xformable(g).GetOrderedXformOps()[0]
    if kind != "cyl":
        xf = UsdGeom.Xformable(g); ops = xf.GetOrderedXformOps()
        t = xf.AddTranslateOp(); t.Set(Gf.Vec3d(*pos)); xf.SetXformOpOrder([t] + ops)
    g.CreatePurposeAttr(UsdGeom.Tokens.guide)   # 렌더 제외
    UsdPhysics.CollisionAPI.Apply(g.GetPrim())
    return path
cols = {
    "frame_body": make_collider(FRAME, "collision_frame_body", "cyl", (0.20, 0.78), (0.50, 0, 0)),
    "frame_feet": make_collider(FRAME, "collision_frame_feet", "box", (0.40, 0.395, 0.20), (0.425, 0, -0.10)),
    "frame_tbox": make_collider(FRAME, "collision_tbox", "box", (0.25, 0.20, 0.15), (0.425, 0, 0.275)),
    "rotor_shaft": make_collider(ROTOR, "collision_rotor_shaft", "cyl", (0.0275, 0.85), (0.425, 0, 0)),
    "rotor_core": make_collider(ROTOR, "collision_rotor_core", "cyl", (0.109, 0.26), (0.425, 0, 0)),
}
# 프레임-로터 충돌 상호 제외 (로터는 베어링으로 지지되므로 접촉 계산 불필요)
for a in ("frame_body", "frame_feet", "frame_tbox"):
    for b in ("rotor_shaft", "rotor_core"):
        pa = stage.GetPrimAtPath(cols[a]); pb = stage.GetPrimAtPath(cols[b])
        fa = UsdPhysics.FilteredPairsAPI.Apply(pa); fa.CreateFilteredPairsRel().AddTarget(Sdf.Path(cols[b]))

# ---- RigidBody + 질량 ----
nameplate = V(CFG["motor"]["nameplate_mass_kg"])
rot = CAD["_groups"]["rotor_assy"]; m_rotor = rot["mass_kg"]; Ixx = rot["Ixx_kgm2"]
# 회전부 횡관성(Iyy, Izz) — 질량중심 기준으로 환산 (CAD 원점기준 I - m d²)
d = rot["com_x_m"]; Iyy_o = sum(CAD[n]["I_origin_kgm2"][1] for n in rot["parts"]); Iyy = Iyy_o - m_rotor * d * d
m_frame = nameplate - m_rotor   # 명판 총중량 기준 배분 (프레임측 = 285 - 회전부 CAD 질량)
frame_cad = CAD["_groups"]["frame_assy_cad"]["mass_kg"]
def rigid(path, mass, com, inertia, kinematic=False):
    p = stage.GetPrimAtPath(path)
    rb = UsdPhysics.RigidBodyAPI.Apply(p); rb.CreateKinematicEnabledAttr(kinematic)
    ma = UsdPhysics.MassAPI.Apply(p); ma.CreateMassAttr(float(mass)); ma.CreateCenterOfMassAttr(Gf.Vec3f(*com)); ma.CreateDiagonalInertiaAttr(Gf.Vec3f(*inertia))
    ma.CreatePrincipalAxesAttr(Gf.Quatf(1.0, 0.0, 0.0, 0.0))   # 필수: 기본값 (0,0,0,0)은 무효 쿼터니언 → PhysX 관성 오적용 (진단으로 확인)
    PhysxSchema.PhysxRigidBodyAPI.Apply(p).CreateSolverPositionIterationCountAttr(16)
    return p
frame_com = [0.425, 0.0, 0.0]
frame_I = [CAD["HM_Frame"]["I_origin_kgm2"][0] * (m_frame / frame_cad) * 2.2, 12.0, 12.0]  # 근사(고정부라 동역학 영향 없음)
rigid(FRAME, m_frame, frame_com, frame_I)
rigid(ROTOR, m_rotor, [d, 0.0, 0.0], [Ixx, Iyy, Iyy])
rb_r = PhysxSchema.PhysxRigidBodyAPI(stage.GetPrimAtPath(ROTOR)); rb_r.CreateAngularDampingAttr(0.0)
rb_r.CreateMaxAngularVelocityAttr(1.0e6)     # 단위 deg/s (기본 5729.58 deg/s = 100 rad/s) → 상한 해제
rb_r.CreateSleepThresholdAttr(0.0); rb_r.CreateLinearDampingAttr(0.0)

# ---- 아티큘레이션: 프레임 고정(FixedJoint to world) + Revolute(X) ----
art_root = stage.GetPrimAtPath(BASE)
UsdPhysics.ArticulationRootAPI.Apply(art_root); PhysxSchema.PhysxArticulationAPI.Apply(art_root).CreateSolverPositionIterationCountAttr(32)
fj = UsdPhysics.FixedJoint.Define(stage, BASE + "/JT_World_Frame_Fixed")
fj.CreateBody1Rel().SetTargets([Sdf.Path(FRAME)])   # body0 없음 = 월드
rj = UsdPhysics.RevoluteJoint.Define(stage, BASE + "/JT_Frame_Rotor_Rev")
rj.CreateBody0Rel().SetTargets([Sdf.Path(FRAME)]); rj.CreateBody1Rel().SetTargets([Sdf.Path(ROTOR)])
rj.CreateAxisAttr("X")
jpos = Gf.Vec3f(0.425, 0.0, 0.0)   # 베어링 중심선(축선) 위, 프레임 중앙
rj.CreateLocalPos0Attr(jpos); rj.CreateLocalPos1Attr(jpos)
rj.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0)); rj.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
rj.CreateLowerLimitAttr(-1e9); rj.CreateUpperLimitAttr(1e9)
pj = PhysxSchema.PhysxJointAPI.Apply(rj.GetPrim()); pj.CreateArmatureAttr(0.0)
pj.CreateMaxJointVelocityAttr(1.0e6)          # deg/s — 아티큘레이션 조인트 속도 상한 해제
pj.CreateJointFrictionAttr(0.0)
drv = UsdPhysics.DriveAPI.Apply(rj.GetPrim(), "angular")
drv.CreateTypeAttr("force")
drv.CreateStiffnessAttr(float(V(CFG["drive"]["stiffness"])))
damp = float(V(CFG["drive"]["damping_Nms_per_rad"]))
drv.CreateDampingAttr(damp)                     # USD angular drive: damping 단위 N·m·s/rad (각속도 deg/s 입력 → 내부 변환)
drv.CreateMaxForceAttr(float(V(CFG["drive"]["max_force_Nm"])))
drv.CreateTargetVelocityAttr(0.0)               # 실행 스크립트에서 설정 (deg/s)

world.reset()
for _ in range(5): world.step(render=False)
DST = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd")
stage.GetRootLayer().Export(DST)
rep = {
    "usd_out": DST, "physics_hz": int(round(1 / phys_dt)),
    "frame": {"mass_kg": m_frame, "source": "명판 285 kg − 회전부 CAD 질량 (MFR+CAD)", "cad_mass_kg": frame_cad, "com": frame_com, "inertia_note": "고정부(FixedJoint) — 동역학 무관, 근사값"},
    "rotor": {"mass_kg": m_rotor, "com_x_m": d, "Ixx_kgm2": Ixx, "Iyy_Izz_kgm2": Iyy, "source": "CAD 물성(Fusion), 형상 미확인(추정: IEC 200L)"},
    "joint": {"path": BASE + "/JT_Frame_Rotor_Rev", "axis": "X", "pos_m": [0.425, 0, 0]},
    "drive": {"type": "force/velocity", "stiffness": 0.0, "damping_Nms_per_rad": damp, "max_force_Nm": float(V(CFG["drive"]["max_force_Nm"])), "target_rpm": CFG["drive"]["target_rpm"]},
    "colliders": cols,
}
json.dump(rep, open(os.path.join(OUT, "s2_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
simulation_app.close()
