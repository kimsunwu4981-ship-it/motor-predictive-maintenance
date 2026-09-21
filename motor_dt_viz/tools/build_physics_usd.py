# -*- coding: utf-8 -*-
"""build_physics_usd.py — 부품별 prim USD 에 물리 구조를 부여한다 (Isaac Sim 4.5 headless).

입력:  motor_dt_viz/assets/motor_parts.usd   (부품 11개 독립 prim)
출력:  motor_dt_viz/assets/motor_physics.usd (RigidBody 2 + Revolute 1 + 충돌 프록시)

기존 sim/usd/hoist_motor_physics_v01.usd 와 동일한 물리 구성을 쓰되,
시각 메시만 부품 단위로 분리되어 부품별 머티리얼 바인딩이 가능하다.
원본 USD 는 수정하지 않는다 (Hard Rule 2).

실행: C:\\ISSACS~1\\python.bat motor_dt_viz\\tools\\build_physics_usd.py
"""
import os
import sys
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "docs")
os.makedirs(OUT_DIR, exist_ok=True)


def _hook(t, v, tb):
    with open(os.path.join(OUT_DIR, "build_physics_error.txt"), "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(t, v, tb)))


sys.excepthook = _hook
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

CFG_DIR = os.path.join(ROOT, "config")
motor_cfg = yaml.safe_load(open(os.path.join(CFG_DIR, "motor.yaml"), encoding="utf-8"))
MECH = motor_cfg["mechanics"]
V = lambda d: d["value"] if isinstance(d, dict) else d  # noqa: E731

SRC = os.path.join(ROOT, "assets", "motor_parts.usd")
DST = os.path.join(ROOT, "assets", "motor_physics.usd")

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": True})
import carb  # noqa: E402

carb.settings.get_settings().set("/physics/cudaDevice", -1)

from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.utils.stage import get_current_stage, open_stage  # noqa: E402
from pxr import Gf, PhysxSchema, Sdf, UsdGeom, UsdPhysics  # noqa: E402

open_stage(SRC)
world = World(stage_units_in_meters=1.0, physics_dt=1 / 240, rendering_dt=1 / 60)
stage = get_current_stage()

MOTOR = "/World/Motor"
STATIC = MOTOR + "/Static"
ROTATING = MOTOR + "/Rotating"

# ---------------------------------------------------------------- PhysicsScene
scene_prim = None
for p in stage.Traverse():
    if p.IsA(UsdPhysics.Scene):
        scene_prim = p
        break
if scene_prim is None:
    scene_prim = UsdPhysics.Scene.Define(stage, "/physicsScene").GetPrim()
ps = PhysxSchema.PhysxSceneAPI.Apply(scene_prim)
ps.CreateEnableGPUDynamicsAttr(False)      # CPU PhysX (CLAUDE.md 환경 규칙)
ps.CreateBroadphaseTypeAttr("MBP")
ps.CreateSolverTypeAttr("TGS")
ps.CreateTimeStepsPerSecondAttr(240)
UsdPhysics.Scene(scene_prim).CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
UsdPhysics.Scene(scene_prim).CreateGravityMagnitudeAttr(9.81)


def add_collider(parent: str, name: str, kind: str, size, pos):
    """충돌 프록시 (purpose=guide → 렌더 제외). 시각 메시에는 충돌을 주지 않는다."""
    path = f"{parent}/{name}"
    if kind == "cyl":
        g = UsdGeom.Cylinder.Define(stage, path)
        g.CreateRadiusAttr(size[0])
        g.CreateHeightAttr(size[1])
        g.CreateAxisAttr("X")
        UsdGeom.Xformable(g).AddTranslateOp().Set(Gf.Vec3d(*pos))
    else:
        g = UsdGeom.Cube.Define(stage, path)
        g.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(g)
        t = xf.AddTranslateOp()
        t.Set(Gf.Vec3d(*pos))
        xf.AddScaleOp().Set(Gf.Vec3f(*size))
    g.CreatePurposeAttr(UsdGeom.Tokens.guide)
    UsdPhysics.CollisionAPI.Apply(g.GetPrim())
    return path


cols = {
    "frame_body": add_collider(STATIC, "collision_frame_body", "cyl", (0.20, 0.78), (0.50, 0, 0)),
    "frame_feet": add_collider(STATIC, "collision_frame_feet", "box", (0.40, 0.395, 0.20), (0.425, 0, -0.10)),
    "tbox": add_collider(STATIC, "collision_tbox", "box", (0.25, 0.20, 0.15), (0.425, 0, 0.275)),
    "rotor_shaft": add_collider(ROTATING, "collision_rotor_shaft", "cyl", (0.0275, 0.85), (0.425, 0, 0)),
    "rotor_core": add_collider(ROTATING, "collision_rotor_core", "cyl", (0.109, 0.26), (0.425, 0, 0)),
}
# 고정부↔회전부 접촉 계산 제외 (베어링으로 지지되므로 불필요)
for a in ("frame_body", "frame_feet", "tbox"):
    for b in ("rotor_shaft", "rotor_core"):
        f = UsdPhysics.FilteredPairsAPI.Apply(stage.GetPrimAtPath(cols[a]))
        f.CreateFilteredPairsRel().AddTarget(Sdf.Path(cols[b]))

# ---------------------------------------------------------------- RigidBody
def rigid(path: str, mass: float, com, inertia):
    prim = stage.GetPrimAtPath(path)
    UsdPhysics.RigidBodyAPI.Apply(prim).CreateKinematicEnabledAttr(False)
    ma = UsdPhysics.MassAPI.Apply(prim)
    ma.CreateMassAttr(float(mass))
    ma.CreateCenterOfMassAttr(Gf.Vec3f(*com))
    ma.CreateDiagonalInertiaAttr(Gf.Vec3f(*inertia))
    ma.CreatePrincipalAxesAttr(Gf.Quatf(1.0, 0.0, 0.0, 0.0))   # 무효 쿼터니언(0,0,0,0) 방지
    rb = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    rb.CreateSolverPositionIterationCountAttr(16)
    rb.CreateMaxAngularVelocityAttr(1.0e6)                     # deg/s 상한 해제
    rb.CreateAngularDampingAttr(0.0)
    rb.CreateSleepThresholdAttr(0.0)
    return prim


m_static = float(V(MECH["static_mass_kg"]))
m_rotor = float(V(MECH["rotor_mass_kg"]))
ixx = float(V(MECH["rotor_inertia_kgm2"]))
rigid(STATIC, m_static, (0.425, 0.0, 0.0), (7.21, 12.0, 12.0))
rigid(ROTATING, m_rotor, (0.4254, 0.0, 0.0), (ixx, 1.850, 1.850))

# ---------------------------------------------------------------- Articulation
art_root = stage.GetPrimAtPath(MOTOR)
UsdPhysics.ArticulationRootAPI.Apply(art_root)
PhysxSchema.PhysxArticulationAPI.Apply(art_root).CreateSolverPositionIterationCountAttr(32)

fj = UsdPhysics.FixedJoint.Define(stage, MOTOR + "/JT_World_Static_Fixed")
fj.CreateBody1Rel().SetTargets([Sdf.Path(STATIC)])

rj = UsdPhysics.RevoluteJoint.Define(stage, MOTOR + "/JT_Static_Rotating_Rev")
rj.CreateBody0Rel().SetTargets([Sdf.Path(STATIC)])
rj.CreateBody1Rel().SetTargets([Sdf.Path(ROTATING)])
rj.CreateAxisAttr("X")
jpos = Gf.Vec3f(0.425, 0.0, 0.0)          # 베어링 중심선
rj.CreateLocalPos0Attr(jpos)
rj.CreateLocalPos1Attr(jpos)
rj.CreateLocalRot0Attr(Gf.Quatf(1, 0, 0, 0))
rj.CreateLocalRot1Attr(Gf.Quatf(1, 0, 0, 0))
rj.CreateLowerLimitAttr(-1e9)
rj.CreateUpperLimitAttr(1e9)
pj = PhysxSchema.PhysxJointAPI.Apply(rj.GetPrim())
pj.CreateArmatureAttr(0.0)
pj.CreateMaxJointVelocityAttr(1.0e6)
pj.CreateJointFrictionAttr(0.0)

drv = UsdPhysics.DriveAPI.Apply(rj.GetPrim(), "angular")
drv.CreateTypeAttr("force")
drv.CreateStiffnessAttr(0.0)
drv.CreateDampingAttr(0.0)                 # 토크 제어 루프에서 런타임 설정
drv.CreateMaxForceAttr(1.0e4)
drv.CreateTargetVelocityAttr(0.0)

world.reset()
for _ in range(3):
    world.step(render=False)

stage.GetRootLayer().Export(DST)

# ---------------------------------------------------------------- 검증
parts = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
report = {
    "out": DST,
    "mesh_prims": parts,
    "mesh_count": len(parts),
    "static_mass": m_static,
    "rotor_mass": m_rotor,
    "rotor_ixx": ixx,
    "joint": MOTOR + "/JT_Static_Rotating_Rev",
}
import json  # noqa: E402

with open(os.path.join(OUT_DIR, "build_physics_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

simulation_app.close()
