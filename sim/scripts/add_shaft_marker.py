# -*- coding: utf-8 -*-
"""add_shaft_marker.py — 샤프트 회전 시각화 마커(빨간 스트라이프 + 흰 방향 큐브) 추가. Isaac Sim 4.5.

실행 방법
  (A) Script Editor: 스테이지를 연 상태에서 이 파일 내용을 붙여 넣고 실행 → 현재 스테이지에 마커 생성 (시뮬 검증은 건너뜀)
  (B) python.bat:    C:\ISSACS~1\python.bat add_shaft_marker.py [--stage <usd>] [--save] [--demo_rpm 90] [--no-verify]
      → 스테이지를 열어 마커 생성, 1 s 시뮬 스텝으로 스트라이프 월드좌표 변화 assert, (--save 시) *_marker.usd 로 별도 저장

설계: 샤프트(joint body1) prim 의 자식 Xform `RotMarker` 아래 UsdGeom.Cube 2개. 물리 API(Collision/RigidBody) 미부착 →
      부모 강체의 회전을 그대로 상속. 텍스처/UV 불필요. 기존 메시·조인트·물리 설정은 수정하지 않는다.
회전 앨리어싱: 정격 1170 rpm(19.5 rps)은 30 fps 에서 프레임당 234° 회전 → 회전으로 보이지 않음.
      옵션 A: DEMO_RPM(기본 90 rpm → 30 fps 에서 프레임당 18°) 로 데모 구동 — **시각화 전용, PdM 데이터와 무관**
      옵션 B: Movie Capture 120 fps 캡처 → 30 fps 재생(4배 슬로모션) — 실행 로그에 안내 출력
"""
# ---------------- 파라미터 블록 ----------------
SHAFT_PATH_HINT     = ""        # 비우면 자동 탐색. 예: "/World/HoistMotor/HoistMotor/HM_Rotor_Assy"
SHAFT_NAME_KEYWORDS = ("shaft", "rotor", "drum")
STRIPE_WIDTH_RATIO  = 0.08      # 원주 대비 폭
STRIPE_THICK_RATIO  = 0.02      # 반경 대비 두께
STRIPE_COLOR        = (1.0, 0.0, 0.0)
DOT_COLOR           = (1.0, 1.0, 1.0)
DOT_SIZE_RATIO      = 0.6       # 흰 큐브 한 변 = 스트라이프 폭 × 비율
MARKER_NAME         = "RotMarker"
DEMO_RPM            = 90.0      # 옵션 A 데모 회전수 (시각화 전용). 0 이면 데모 구동 안 함
VERIFY_SECONDS      = 1.0
PHYSICS_HZ          = 240
# ------------------------------------------------
import sys, os, math, argparse

def _in_script_editor():
    try:
        import omni.usd
        return omni.usd.get_context().get_stage() is not None and "isaacsim" not in " ".join(sys.argv).lower() and not any(a.startswith("--") for a in sys.argv[1:])
    except Exception:
        return False

STANDALONE = not _in_script_editor()
if STANDALONE:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "usd", "hoist_motor_physics_v01.usd"))
    ap.add_argument("--save", action="store_true"); ap.add_argument("--demo_rpm", type=float, default=DEMO_RPM)
    ap.add_argument("--no-verify", action="store_true"); ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--gui", action="store_true", help="GUI 로 열고 데모 회전 유지")
    args = ap.parse_args(); DEMO_RPM = args.demo_rpm
    from isaacsim import SimulationApp
    simulation_app = SimulationApp({"headless": not args.gui})
    import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
    from isaacsim.core.utils.stage import open_stage
    open_stage(os.path.abspath(args.stage))

import omni.usd
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Gf, Sdf
stage = omni.usd.get_context().get_stage()
MPU = UsdGeom.GetStageMetersPerUnit(stage) or 1.0
log = lambda *a: print("[marker]", *a, flush=True)
bbc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy", "guide"])
def wbound(prim):
    r = bbc.ComputeWorldBound(prim).ComputeAlignedRange(); return r.GetMin(), r.GetMax()

# ---- 1~3. Revolute joint → body1 → 샤프트 후보 ----
joints = [p for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)]
if not joints: raise SystemExit("[marker] RevoluteJoint 없음 — 중단")
cands = []
for j in joints:
    b1 = UsdPhysics.Joint(j).GetBody1Rel().GetTargets(); b0 = UsdPhysics.Joint(j).GetBody0Rel().GetTargets()
    if b1: cands.append((j, stage.GetPrimAtPath(b1[0]), stage.GetPrimAtPath(b0[0]) if b0 else None))
if SHAFT_PATH_HINT:
    cands = [c for c in cands if str(c[1].GetPath()) == SHAFT_PATH_HINT] or cands
if len(cands) > 1:
    pri = [c for c in cands if any(k in c[1].GetName().lower() for k in SHAFT_NAME_KEYWORDS)]
    if len(pri) == 1: cands = pri
    else:
        log("샤프트 후보가 여럿 — SHAFT_PATH_HINT 로 지정하세요:"); [log("  ", str(c[1].GetPath()), "(joint", str(c[0].GetPath()) + ")") for c in cands]; raise SystemExit(2)
joint, shaft, body0 = cands[0]
# ---- 4. 축 방향 ----
axis_tok = str(joint.GetAttribute("physics:axis").Get() or "X"); AX = {"X": 0, "Y": 1, "Z": 2}[axis_tok]
# ---- 5. 반경·노출 길이 ----
sub = [p for p in Usd.PrimRange(shaft) if p != shaft and any(k in p.GetName().lower() for k in ("shaft",)) and (p.IsA(UsdGeom.Gprim))]
src = sub[0] if sub else shaft
mn, mx = wbound(src); ext = [mx[i] - mn[i] for i in range(3)]
radial = [i for i in range(3) if i != AX]; radius = 0.5 * min(ext[radial[0]], ext[radial[1]])
smn, smx = wbound(shaft)
if body0 is not None and body0.IsValid():
    fmn, fmx = wbound(body0)
    seg = (smn[AX], fmn[AX]) if smn[AX] < fmn[AX] - 1e-6 else ((fmx[AX], smx[AX]) if smx[AX] > fmx[AX] + 1e-6 else (smn[AX], smx[AX]))
else:
    seg = (smn[AX], smx[AX])
length = seg[1] - seg[0]; center_ax = 0.5 * (seg[0] + seg[1])
# 축선(반경 방향 중심): 샤프트 소스 바운드 중심
axis_center = [0.5 * (mn[i] + mx[i]) for i in range(3)]
log("joint:", joint.GetPath(), "| shaft(body1):", shaft.GetPath(), "| body0:", body0.GetPath() if body0 else None)
log(f"axis={axis_tok} radius={radius*MPU:.4f} m exposed_len={length*MPU:.4f} m seg=({seg[0]:.3f},{seg[1]:.3f}) src={src.GetPath()}")
if radius <= 0 or length <= 0: raise SystemExit("[marker] 반경/길이 계산 실패")

# ---- 마커 생성 (멱등) ----
mpath = shaft.GetPath().AppendChild(MARKER_NAME)
if stage.GetPrimAtPath(mpath).IsValid(): stage.RemovePrim(mpath); log("기존 마커 삭제:", mpath)
marker = UsdGeom.Xform.Define(stage, mpath)
# 샤프트 로컬 좌표: 샤프트 prim 월드 → 로컬 변환
xf_cache = UsdGeom.XformCache(); w2l = xf_cache.GetLocalToWorldTransform(shaft).GetInverse()
def local(pt_world): return w2l.Transform(Gf.Vec3d(*pt_world))
thick = STRIPE_THICK_RATIO * radius; width = STRIPE_WIDTH_RATIO * 2 * math.pi * radius
r_ax = radial[0]; t_ax = radial[1]      # 스트라이프는 r_ax 방향 표면, 흰 큐브는 t_ax 방향(90°)
def make_cube(name, size3, center_world, color, emissive=True):
    c = UsdGeom.Cube.Define(stage, mpath.AppendChild(name)); c.CreateSizeAttr(1.0)
    x = UsdGeom.Xformable(c); x.AddTranslateOp().Set(local(center_world)); x.AddScaleOp().Set(Gf.Vec3f(*size3))
    c.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    mat = UsdShade.Material.Define(stage, mpath.AppendChild(name + "_Mat")); sh = UsdShade.Shader.Define(stage, mpath.AppendChild(name + "_Mat").AppendChild("PreviewSurface"))
    sh.CreateIdAttr("UsdPreviewSurface"); sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    if emissive: sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6); mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat)
    return c
size = [0, 0, 0]; size[AX] = length; size[r_ax] = thick; size[t_ax] = width
cen = list(axis_center); cen[AX] = center_ax; cen[r_ax] = axis_center[r_ax] + radius + thick / 2
stripe = make_cube("Stripe", size, cen, STRIPE_COLOR)
d = DOT_SIZE_RATIO * width; dsize = [0, 0, 0]; dsize[AX] = d; dsize[r_ax] = d; dsize[t_ax] = thick * 3
dcen = list(axis_center); dcen[AX] = center_ax; dcen[t_ax] = axis_center[t_ax] + radius + thick * 1.5
dot = make_cube("DirDot", dsize, dcen, DOT_COLOR)
for p in Usd.PrimRange(marker.GetPrim()):
    assert not p.HasAPI(UsdPhysics.CollisionAPI) and not p.HasAPI(UsdPhysics.RigidBodyAPI)
log("생성:", stripe.GetPath(), dot.GetPath(), f"| stripe size(ax,thick,width)=({length:.4f},{thick:.5f},{width:.4f})")
log("옵션 B: Movie Capture 를 120 fps 로 캡처 후 30 fps 로 재생하면 4배 슬로모션으로 회전이 보입니다.")
log(f"옵션 A: DEMO_RPM={DEMO_RPM} (30 fps 기준 프레임당 {DEMO_RPM*6/30:.1f}°) — 시각화 전용, PdM 데이터와 무관")

# ---- 검증 (standalone 전용): 1 s 스텝 후 Stripe 월드좌표 변화 ----
if STANDALONE:
    if args.save:
        out = os.path.splitext(os.path.abspath(args.stage))[0] + "_marker.usd"; stage.GetRootLayer().Export(out); log("저장:", out)
    if not args.no_verify or args.gui:
        import numpy as np
        from isaacsim.core.api import World
        from isaacsim.core.prims import SingleArticulation
        from omni.physx import get_physx_simulation_interface
        dt = 1.0 / PHYSICS_HZ
        scene_path = next((str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)), "/physicsScene")
        world = World(stage_units_in_meters=MPU, physics_dt=dt, rendering_dt=1 / 60, physics_prim_path=scene_path); world.reset()
        root = shaft
        while root.GetParent().IsValid() and not root.HasAPI(UsdPhysics.ArticulationRootAPI): root = root.GetParent()
        art = SingleArticulation(prim_path=str(root.GetPath()), name="art"); art.initialize(); av = art._articulation_view
        # 런타임 전용 데모 구동(USD 미변경): 속도 드라이브 게인 + 목표 DEMO_RPM
        w_demo = DEMO_RPM * 2 * math.pi / 60
        av.set_gains(kps=np.zeros((1, 1)), kds=np.full((1, 1), 50.0)); av.set_max_efforts(np.full((1, 1), 500.0))
        from isaacsim.core.utils.types import ArticulationAction
        sim = get_physx_simulation_interface()
        def stripe_world():
            return UsdGeom.XformCache().GetLocalToWorldTransform(stripe.GetPrim()).Transform(Gf.Vec3d(0, 0, 0))
        p0 = stripe_world(); t = 0.0
        steps = int(VERIFY_SECONDS * PHYSICS_HZ)
        for i in range(steps):
            art.get_articulation_controller().apply_action(ArticulationAction(joint_velocities=np.array([w_demo])))
            sim.simulate(dt, t); sim.fetch_results(); t += dt
        p1 = stripe_world(); w = float(art.get_joint_velocities()[0])
        moved = (p1 - p0).GetLength()
        log(f"검증: Stripe 월드좌표 {tuple(round(v,4) for v in p0)} → {tuple(round(v,4) for v in p1)} | 이동 {moved:.4f} m | 조인트 {w*60/(2*math.pi):.1f} rpm")
        assert moved > 1e-4, "Stripe 가 움직이지 않음 — 부모 강체 회전 상속 실패"
        log("VERIFY_OK")
        if args.gui:
            log("GUI 데모 유지 중 (창을 닫으면 종료)")
            while simulation_app.is_running():
                for _ in range(max(1, int(round((1 / 60) / dt)))):
                    art.get_articulation_controller().apply_action(ArticulationAction(joint_velocities=np.array([w_demo]))); sim.simulate(dt, t); sim.fetch_results(); t += dt
                world.render()
    simulation_app.close()
