# -*- coding: utf-8 -*-
"""s10_gui_array.py — 권상 모터를 3×10 배열(30대)로 복제해 GUI에서 동시 구동. 배열 USD 저장.
사용: C:\ISSACS~1\python.bat s10_gui_array.py [--rows 3 --cols 10] [--dx 1.4 --dy 1.2] [--hz 480] [--faults] [--headless]
- 각 인스턴스 = 물리 USD 의 아티큘레이션 프림(/World/HoistMotor/HoistMotor) 참조 → 독립 강체·Revolute 조인트
- 구동: v2 토크 제어 루프(벡터화, 30대 동시). GUI 실시간성을 위해 기본 480 Hz(데이터 생성용 아님)
- --faults : 인스턴스별 결함 모드 순환 배정(brb/ecc/itsc/bpfo/bpfi, severe) — 시각 확인용
출력: sim/usd/hoist_motor_array_{rows}x{cols}.usd, sim/output/s10_status.txt
"""
import sys, os, math, argparse, json, traceback, itertools
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); OUT = os.path.join(ROOT, "output"); sys.path.insert(0, os.path.dirname(__file__))
def _hook(t, v, tb): open(os.path.join(OUT, "s10_error.txt"), "w", encoding="utf-8").write("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = _hook
ap = argparse.ArgumentParser(); ap.add_argument("--rows", type=int, default=3); ap.add_argument("--cols", type=int, default=10)
ap.add_argument("--dx", type=float, default=1.4); ap.add_argument("--dy", type=float, default=1.2); ap.add_argument("--hz", type=int, default=480)
ap.add_argument("--faults", action="store_true"); ap.add_argument("--headless", action="store_true"); ap.add_argument("--load", default="rated"); ap.add_argument("--slow", type=float, default=1.0)
ap.add_argument("--rpm_start", type=float, default=0.0, help="속도 램프 모드: 1번 모터 rpm (X축 방향 번호, 행 순서). 0 이면 토크 제어 모드")
ap.add_argument("--rpm_step", type=float, default=50.0, help="속도 램프 모드: 다음 모터마다 증가 rpm")
ap.add_argument("--shaft_ext", type=float, default=1.0, help="DE 노출 샤프트 시각 길이 배율 (2.0 = 2배). 시각 전용 자식 실린더 추가, 물리 무변경")
ap.add_argument("--stripe_frac", type=float, default=0.0, help="샤프트(연장 후) 길이 대비 빨간 선 길이 비율 (예 0.667). 0 이면 선 없음")
args = ap.parse_args()
RPM_MODE = args.rpm_start > 0
import yaml, numpy as np
from motor_torque_model import InductionMotorTorque
from fault_injector import FaultInjector
CFG = yaml.safe_load(open(os.path.join(ROOT, "config", "motor.yaml"), encoding="utf-8")); V = lambda d: d["value"] if isinstance(d, dict) else d
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": args.headless, "width": 1600, "height": 900})
import carb; carb.settings.get_settings().set("/physics/cudaDevice", -1)
from isaacsim.core.api import World
from isaacsim.core.utils.stage import get_current_stage, create_new_stage
from isaacsim.core.prims import Articulation
from isaacsim.core.utils.viewports import set_camera_view
from omni.physx import get_physx_simulation_interface
from pxr import Usd, UsdGeom, UsdPhysics, PhysxSchema, UsdLux, Gf, Sdf
dt = 1.0 / args.hz
create_new_stage()
world = World(stage_units_in_meters=1.0, physics_dt=dt, rendering_dt=1 / 60)
stage = get_current_stage()
# PhysicsScene: CPU, TGS, MBP
scene = None
for p in stage.Traverse():
    if p.IsA(UsdPhysics.Scene): scene = p; break
if scene is None: scene = UsdPhysics.Scene.Define(stage, "/physicsScene").GetPrim()
ps = PhysxSchema.PhysxSceneAPI.Apply(scene); ps.CreateEnableGPUDynamicsAttr(False); ps.CreateBroadphaseTypeAttr("MBP"); ps.CreateSolverTypeAttr("TGS"); ps.CreateTimeStepsPerSecondAttr(args.hz)
SRC = os.path.join(ROOT, "usd", "hoist_motor_physics_v01.usd"); SRC_PRIM = "/World/HoistMotor/HoistMotor"
UsdGeom.Xform.Define(stage, "/World"); UsdGeom.Xform.Define(stage, "/World/Motors")
paths = []
for r, c in itertools.product(range(args.rows), range(args.cols)):
    path = f"/World/Motors/M_r{r}_c{c}"
    prim = stage.DefinePrim(path, "Xform"); prim.GetReferences().AddReference(SRC, SRC_PRIM)
    xf = UsdGeom.Xformable(prim); xf.ClearXformOpOrder(); xf.AddTranslateOp().Set(Gf.Vec3d(c * args.dx, -r * args.dy, 0.0))
    paths.append(path)
# ---- 샤프트 시각 연장 + 빨간 선 (자식 프림, 물리 API 없음 → 회전 상속) ----
from pxr import UsdShade
R_SHAFT = 0.0275; L_EXPOSED = 0.110          # DE 노출부: x 0 ~ 0.110 m (CAD, 미확인(추정: IEC 200L))
L_total = L_EXPOSED * args.shaft_ext           # 연장 후 노출 길이 (x = 0.110 − L_total ~ 0.110)
x_end = L_EXPOSED - L_total
def emissive_mat(path, rgb):
    mat = UsdShade.Material.Define(stage, path); sh = UsdShade.Shader.Define(stage, path + "/PreviewSurface"); sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb)); sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.6); mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface"); return mat
mat_red = emissive_mat("/World/Looks/StripeRed", (1, 0, 0)); mat_white = emissive_mat("/World/Looks/DotWhite", (1, 1, 1))
mat_steel = UsdShade.Material.Define(stage, "/World/Looks/ShaftSteel"); shs = UsdShade.Shader.Define(stage, "/World/Looks/ShaftSteel/PreviewSurface"); shs.CreateIdAttr("UsdPreviewSurface")
shs.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.35, 0.33, 0.30)); shs.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(1.0); shs.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)
mat_steel.CreateSurfaceOutput().ConnectToSource(shs.ConnectableAPI(), "surface")
for path in paths:
    rotor = path + "/HM_Rotor_Assy"; mk = rotor + "/RotMarker"; UsdGeom.Xform.Define(stage, mk)
    if args.shaft_ext > 1.0:   # 연장 실린더: x 에서 x_end ~ 0 (기존 축단 끝 x=0 에 이어 붙임)
        ext = UsdGeom.Cylinder.Define(stage, mk + "/ShaftExt"); ext.CreateAxisAttr("X"); ext.CreateRadiusAttr(R_SHAFT); ext.CreateHeightAttr(-x_end)
        UsdGeom.Xformable(ext).AddTranslateOp().Set(Gf.Vec3d(x_end / 2, 0, 0)); UsdShade.MaterialBindingAPI.Apply(ext.GetPrim()).Bind(mat_steel)
    if args.stripe_frac > 0:   # 빨간 선: 연장 후 샤프트 길이의 stripe_frac, 축단 끝(x_end)에서 시작, 표면 위 얇은 박스
        Ls = L_total * args.stripe_frac; thick = 0.02 * R_SHAFT; width = 0.08 * 2 * math.pi * R_SHAFT
        st = UsdGeom.Cube.Define(stage, mk + "/Stripe"); st.CreateSizeAttr(1.0); xs = UsdGeom.Xformable(st)
        xs.AddTranslateOp().Set(Gf.Vec3d(x_end + Ls / 2, 0, R_SHAFT + thick / 2)); xs.AddScaleOp().Set(Gf.Vec3f(Ls, width, thick)); UsdShade.MaterialBindingAPI.Apply(st.GetPrim()).Bind(mat_red)
        dot = UsdGeom.Cube.Define(stage, mk + "/DirDot"); dot.CreateSizeAttr(1.0); xd = UsdGeom.Xformable(dot)   # 원주상 90° 흰 점(방향 인식)
        xd.AddTranslateOp().Set(Gf.Vec3d(x_end + Ls / 2, R_SHAFT + thick * 1.5, 0)); xd.AddScaleOp().Set(Gf.Vec3f(0.6 * width, thick * 3, 0.6 * width)); UsdShade.MaterialBindingAPI.Apply(dot.GetPrim()).Bind(mat_white)
# 조명·바닥
# 배경: 어두운 돔(배경이 희게 보이지 않도록) + 태양광, 바닥: 검정 무광 대형 판
dl = UsdLux.DomeLight.Define(stage, "/World/DomeLight"); dl.CreateIntensityAttr(150.0); dl.CreateColorAttr(Gf.Vec3f(0.02, 0.02, 0.02))
sun = UsdLux.DistantLight.Define(stage, "/World/Sun"); sun.CreateIntensityAttr(1200.0); UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-55, 30, 0))
fill = UsdLux.DistantLight.Define(stage, "/World/Fill"); fill.CreateIntensityAttr(900.0); UsdGeom.Xformable(fill).AddRotateXYZOp().Set(Gf.Vec3f(-60, -120, 0))
fill2 = UsdLux.DistantLight.Define(stage, "/World/Fill2"); fill2.CreateIntensityAttr(700.0); UsdGeom.Xformable(fill2).AddRotateXYZOp().Set(Gf.Vec3f(-50, 150, 0))
# 과노출 방지: 자동 노출(히스토그램) OFF, 고정 톤매핑; 고속 회전 잔상 방지: TAA/DLSS 대신 FXAA
_s = carb.settings.get_settings(); _s.set("/rtx/post/aa/op", 1)   # FXAA (고속 회전부 TAA/DLSS 잔상 방지). 노출/톤매핑은 기본(자동) 유지
# 그림자 제거: 모든 라이트 shadow:enable=False + RTX 그림자 비활성
for L in (dl, sun, fill, fill2):
    UsdLux.ShadowAPI.Apply(L.GetPrim()).CreateShadowEnableAttr(False)
carb.settings.get_settings().set("/rtx/shadows/enabled", False)
carb.settings.get_settings().set("/rtx/ambientOcclusion/enabled", False)
W = (args.cols - 1) * args.dx + 1.6; H = (args.rows - 1) * args.dy + 1.2
g = UsdGeom.Cube.Define(stage, "/World/GroundVisual"); g.CreateSizeAttr(1.0); gx = UsdGeom.Xformable(g); gx.AddTranslateOp().Set(Gf.Vec3d((args.cols - 1) * args.dx / 2 + 0.45, -(args.rows - 1) * args.dy / 2, -0.24)); gx.AddScaleOp().Set(Gf.Vec3f(W * 3, H * 3, 0.03))
g.CreateDisplayColorAttr([Gf.Vec3f(0.0, 0.0, 0.0)])
mat_black = UsdShade.Material.Define(stage, "/World/Looks/GroundBlack"); shb = UsdShade.Shader.Define(stage, "/World/Looks/GroundBlack/PreviewSurface"); shb.CreateIdAttr("UsdPreviewSurface")
shb.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.01, 0.01, 0.01)); shb.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.9); shb.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(0.05)
mat_black.CreateSurfaceOutput().ConnectToSource(shb.ConnectableAPI(), "surface"); UsdShade.MaterialBindingAPI.Apply(g.GetPrim()).Bind(mat_black)
ARR = os.path.join(ROOT, "usd", f"hoist_motor_array_{args.rows}x{args.cols}.usd"); stage.GetRootLayer().Export(ARR)
cx = (args.cols - 1) * args.dx / 2 + 0.45; cy = -(args.rows - 1) * args.dy / 2
D = max(W, H)   # 배열 크기에 비례한 카메라 거리 (전체가 프레임에 들어오도록)
set_camera_view(eye=[cx - 0.40 * D, cy - 1.20 * D - 3.0, 0.75 * D + 3.0], target=[cx, cy - 0.05 * D, 0.0])
world.reset()
arts = Articulation(prim_paths_expr="/World/Motors/M_r*_c*", name="motors"); arts.initialize()
n = arts.count; print("articulations:", n)
arts.set_gains(kps=np.zeros((n, 1)), kds=np.zeros((n, 1))); arts.set_max_efforts(np.full((n, 1), 1.0e4))
arts.set_joint_velocities(np.zeros((n, 1))); arts.set_joint_positions(np.zeros((n, 1)))
motor = InductionMotorTorque(CFG)
if args.slow != 1.0: motor.w_sync /= args.slow; motor.n_sync /= args.slow; motor.n_rated /= args.slow
T_load = motor.T_rated * float(CFG["torque_control"]["load_fractions"][args.load]) / args.slow
modes = ["none", "brb", "ecc_static", "ecc_dynamic", "itsc", "bpfo", "bpfi"]
inj = []
for i in range(n):
    m = modes[i % len(modes)] if args.faults else "none"
    sev = {"brb": "severe", "ecc_static": "e30", "ecc_dynamic": "e30", "itsc": "t10", "bpfo": "severe", "bpfi": "severe"}.get(m, "none")
    inj.append(FaultInjector(m, sev, CFG, seed=100 + i))
# 모터 번호: X축(열) 방향으로 1..cols, 다음 행 이어서 → 번호 k (1-based) = r*cols + c + 1 (prim 경로 순서와 동일)
order = {arts.prim_paths[i]: i for i in range(n)}
idx_of = {}
for k, path in enumerate(paths): idx_of[path] = order[path]
rpm_target = np.zeros(n)
for k, path in enumerate(paths): rpm_target[order[path]] = args.rpm_start + k * args.rpm_step
assign = {paths[k]: {"no": k + 1, "fault": inj[order[paths[k]]].mode, "target_rpm": (float(rpm_target[order[paths[k]]]) if RPM_MODE else None)} for k in range(n)}
json.dump({"array_usd": ARR, "count": n, "mode": ("rpm_ramp" if RPM_MODE else "torque_control"), "rpm_start": args.rpm_start, "rpm_step": args.rpm_step, "assignment": assign},
          open(os.path.join(OUT, "s10_array_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
if RPM_MODE:   # 속도 램프 모드: 인스턴스별 속도 드라이브(런타임 게인, USD 미변경). 시각화 전용 — 물리 토크 모델과 무관
    arts.set_gains(kps=np.zeros((n, 1)), kds=np.full((n, 1), 50.0)); arts.set_max_efforts(np.full((n, 1), 2000.0))
    from isaacsim.core.utils.types import ArticulationAction
    w_target = (rpm_target * 2 * math.pi / 60).reshape(n, 1)
sim = get_physx_simulation_interface(); t = 0.0; theta = np.zeros(n); frame = 0; sub = max(1, int(round((1 / 60) / dt)))
a = motor.T_rated / motor.s_rated
while simulation_app.is_running():
    for _ in range(sub):
        if RPM_MODE:
            arts.set_joint_velocity_targets(w_target)
        else:
            w = arts.get_joint_velocities().reshape(-1); theta += w * dt; s = (motor.w_sync - w) / motor.w_sync; fr = w / (2 * math.pi)
            T = np.clip(a * s, -motor.T_max, motor.T_max) - T_load * np.where(w > 1.0, 1.0, np.maximum(w, 0.0)) - motor.b_mech * w
            if args.faults: T += np.array([inj[i].torque_v2(t, s[i], fr[i], theta[i]) for i in range(n)])
            arts.set_joint_efforts(T.reshape(n, 1))
        sim.simulate(dt, t); sim.fetch_results(); t += dt
    if not args.headless: world.render()
    frame += 1
    if frame % 60 == 0:
        w = arts.get_joint_velocities().reshape(-1) * 60 / (2 * math.pi)
        first = float(w[order[paths[0]]]); last = float(w[order[paths[-1]]])
        open(os.path.join(OUT, "s10_status.txt"), "w", encoding="utf-8").write(json.dumps({"t": round(t, 1), "count": n, "mode": ("rpm_ramp" if RPM_MODE else "torque_control"), "rpm_no1": round(first, 1), "rpm_no%d" % n: round(last, 1), "rpm_min": round(float(w.min()), 1), "rpm_max": round(float(w.max()), 1), "faults": args.faults}))
    if args.headless and t > 3.0: break
simulation_app.close()
